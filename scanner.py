"""Signal scanning logic for Algo.

This module never places orders. It only computes SMA-crossover signals
from historical candle data fetched through Kite Connect.
"""
from __future__ import annotations

import io
import time
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger("algo.scanner")

NIFTY100_CSV_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty100list.csv"
NIFTY100_CACHE_FILE = Path(__file__).parent / "nifty100.csv"

KITE_RATE_LIMIT_DELAY = 0.4  # seconds between historical_data calls (Kite allows ~3 req/s)
CANDLE_CACHE_TTL_SECONDS = 10 * 60  # 10 minutes
DEFAULT_SCAN_HISTORY_DAYS = 200

MIN_LOOKBACK = 1
MAX_LOOKBACK = 120
MIN_SMA_PERIOD = 2
MAX_SMA_PERIOD = 250

_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/csv,*/*",
}


class SessionExpiredError(Exception):
    """Raised when Kite rejects the access token (expired/invalid session)."""


class ScanValidationError(Exception):
    """Raised when scan parameters fail validation."""


# ---------------------------------------------------------------------------
# Nifty 100 universe
# ---------------------------------------------------------------------------

def get_nifty100_symbols(timeout: float = 10.0) -> list[str]:
    """Return the current Nifty 100 constituent symbols.

    Downloads the official NSE CSV and caches it locally. Falls back to the
    local cache file if the download fails for any reason.
    """
    try:
        resp = requests.get(NIFTY100_CSV_URL, headers=_NSE_HEADERS, timeout=timeout)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        symbols = _extract_symbols(df)
        NIFTY100_CACHE_FILE.write_text(resp.text, encoding="utf-8")
        return symbols
    except Exception as exc:  # noqa: BLE001 - deliberately broad, we fall back
        logger.warning("Nifty 100 download failed (%s), falling back to cache", exc)
        if NIFTY100_CACHE_FILE.exists():
            df = pd.read_csv(NIFTY100_CACHE_FILE)
            return _extract_symbols(df)
        raise RuntimeError(
            "Could not download the Nifty 100 list and no local cache "
            f"({NIFTY100_CACHE_FILE.name}) is available."
        ) from exc


def _extract_symbols(df: pd.DataFrame) -> list[str]:
    if "Symbol" not in df.columns:
        raise ValueError("Nifty 100 CSV is missing the 'Symbol' column")
    return [str(s).strip() for s in df["Symbol"].dropna().tolist()]


# ---------------------------------------------------------------------------
# Instrument mapping
# ---------------------------------------------------------------------------

_instrument_cache: Optional[tuple[float, list[dict]]] = None
INSTRUMENT_CACHE_TTL_SECONDS = 10 * 60


def _get_nse_instruments(kite) -> list[dict]:
    global _instrument_cache
    now = time.time()
    if _instrument_cache and (now - _instrument_cache[0]) < INSTRUMENT_CACHE_TTL_SECONDS:
        return _instrument_cache[1]
    try:
        instruments = kite.instruments("NSE")
    except Exception as exc:
        if _is_token_error(exc):
            raise SessionExpiredError(str(exc)) from exc
        raise
    _instrument_cache = (now, instruments)
    return instruments


def map_symbols_to_tokens(kite, symbols: list[str]) -> tuple[dict[str, int], list[str]]:
    """Map NSE equity symbols to instrument tokens via kite.instruments("NSE")."""
    instruments = _get_nse_instruments(kite)

    lookup: dict[str, int] = {}
    for inst in instruments:
        if inst.get("instrument_type") == "EQ":
            lookup[inst["tradingsymbol"]] = inst["instrument_token"]

    mapped: dict[str, int] = {}
    unmatched: list[str] = []
    for sym in symbols:
        token = lookup.get(sym)
        if token is None:
            unmatched.append(sym)
        else:
            mapped[sym] = token
    return mapped, unmatched


def _is_token_error(exc: Exception) -> bool:
    return exc.__class__.__name__ == "TokenException"


# ---------------------------------------------------------------------------
# Candle fetching (scan use: ~200 days, in-memory cached for 10 minutes)
# ---------------------------------------------------------------------------

_candle_cache: dict[int, tuple[float, pd.DataFrame]] = {}


def _candles_to_df(candles: list[dict]) -> pd.DataFrame:
    if not candles:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(candles)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.drop_duplicates(subset="date", keep="last").sort_values("date").reset_index(drop=True)
    return df[["date", "open", "high", "low", "close", "volume"]]


def fetch_historical_data(kite, token: int, from_date: datetime, to_date: datetime, retries: int = 1) -> pd.DataFrame:
    """Fetch daily candles for one instrument, retrying once on transient failure."""
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            candles = kite.historical_data(token, from_date, to_date, "day")
            return _candles_to_df(candles)
        except Exception as exc:  # noqa: BLE001
            if _is_token_error(exc):
                raise SessionExpiredError(str(exc)) from exc
            last_exc = exc
            if attempt < retries:
                time.sleep(KITE_RATE_LIMIT_DELAY)
                continue
    raise RuntimeError(f"Failed to fetch historical data for token {token}: {last_exc}")


def fetch_candles_for_scan(kite, token: int, days: int = DEFAULT_SCAN_HISTORY_DAYS) -> pd.DataFrame:
    """Fetch ~`days` of daily candles for scanning, using a 10-minute in-memory cache."""
    now = time.time()
    cached = _candle_cache.get(token)
    if cached and (now - cached[0]) < CANDLE_CACHE_TTL_SECONDS:
        return cached[1]

    time.sleep(KITE_RATE_LIMIT_DELAY)
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)
    df = fetch_historical_data(kite, token, from_date, to_date)
    _candle_cache[token] = (now, df)
    return df


def clear_candle_cache() -> None:
    _candle_cache.clear()


# ---------------------------------------------------------------------------
# SMA crossover logic (shared by the live scanner and the backtester)
# ---------------------------------------------------------------------------

def validate_periods(short: int, long: int, lookback: Optional[int] = None) -> None:
    if short < MIN_SMA_PERIOD or short > MAX_SMA_PERIOD:
        raise ScanValidationError(f"short period must be between {MIN_SMA_PERIOD} and {MAX_SMA_PERIOD}")
    if long < MIN_SMA_PERIOD or long > MAX_SMA_PERIOD:
        raise ScanValidationError(f"long period must be between {MIN_SMA_PERIOD} and {MAX_SMA_PERIOD}")
    if short >= long:
        raise ScanValidationError("short period must be less than long period")
    if lookback is not None:
        if lookback < MIN_LOOKBACK or lookback > MAX_LOOKBACK:
            raise ScanValidationError(f"lookback must be between {MIN_LOOKBACK} and {MAX_LOOKBACK}")


def add_smas(df: pd.DataFrame, short: int, long: int) -> pd.DataFrame:
    """Return a copy of df with 'sma_short' and 'sma_long' columns added."""
    out = df.copy()
    out["sma_short"] = out["close"].rolling(window=short, min_periods=short).mean()
    out["sma_long"] = out["close"].rolling(window=long, min_periods=long).mean()
    return out


def find_all_crossovers(df: pd.DataFrame) -> pd.DataFrame:
    """Find every SMA crossover in df (must already have sma_short/sma_long columns).

    Bullish: short SMA moves from at-or-below the long SMA to above it.
    Bearish: the reverse (at-or-above to below).

    Returns a DataFrame indexed by the original integer position (column
    'position') with columns: date, signal ('bullish'/'bearish'), close,
    sma_short, sma_long.
    """
    valid = df.dropna(subset=["sma_short", "sma_long"]).copy()
    if len(valid) < 2:
        return pd.DataFrame(columns=["position", "date", "signal", "close", "sma_short", "sma_long"])

    valid["position"] = valid.index
    prev_short = valid["sma_short"].shift(1)
    prev_long = valid["sma_long"].shift(1)

    bullish = (prev_short <= prev_long) & (valid["sma_short"] > valid["sma_long"])
    bearish = (prev_short >= prev_long) & (valid["sma_short"] < valid["sma_long"])

    valid["signal"] = None
    valid.loc[bullish, "signal"] = "bullish"
    valid.loc[bearish, "signal"] = "bearish"

    crossovers = valid[valid["signal"].notna()][["position", "date", "signal", "close", "sma_short", "sma_long"]]
    return crossovers.reset_index(drop=True)


def most_recent_crossover_in_lookback(df: pd.DataFrame, crossovers: pd.DataFrame, lookback: int) -> Optional[dict]:
    """Pick the most recent crossover within `lookback` trading days of df's last row."""
    if df.empty or crossovers.empty:
        return None
    last_position = len(df) - 1
    in_window = crossovers[(last_position - crossovers["position"]) <= lookback]
    if in_window.empty:
        return None
    latest = in_window.loc[in_window["position"].idxmax()]
    bars_ago = int(last_position - latest["position"])
    weight = 100.0 * (1 - bars_ago / lookback)
    return {
        "position": int(latest["position"]),
        "date": latest["date"],
        "signal": latest["signal"],
        "close": float(latest["close"]),
        "sma_short": float(latest["sma_short"]),
        "sma_long": float(latest["sma_long"]),
        "bars_ago": bars_ago,
        "weight": round(weight, 1),
    }


def build_sparkline(df: pd.DataFrame, crossover_position: Optional[int], window: int = 40) -> dict:
    """Return the last `window` SMA values plus the crossover's offset within that window."""
    tail = df.tail(window).reset_index(drop=True)
    sma_short = [None if pd.isna(v) else round(float(v), 2) for v in tail["sma_short"]]
    sma_long = [None if pd.isna(v) else round(float(v), 2) for v in tail["sma_long"]]

    crossover_index = None
    if crossover_position is not None:
        start_position = len(df) - len(tail)
        offset = crossover_position - start_position
        if 0 <= offset < len(tail):
            crossover_index = offset

    return {"sma_short": sma_short, "sma_long": sma_long, "crossover_index": crossover_index}


@dataclass
class ScanOutcome:
    results: list[dict]
    scanned: int
    skipped: list[str]
    failed: list[str]
    unmatched: list[str]


def scan_universe(kite, symbol_tokens: dict[str, int], short: int, long: int, lookback: int) -> ScanOutcome:
    """Scan every symbol for the most recent SMA crossover within `lookback` days."""
    results: list[dict] = []
    skipped: list[str] = []
    failed: list[str] = []

    for symbol, token in symbol_tokens.items():
        try:
            df = fetch_candles_for_scan(kite, token)
        except SessionExpiredError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to fetch candles for %s: %s", symbol, exc)
            failed.append(symbol)
            continue

        if len(df) < long + 1:
            skipped.append(symbol)
            continue

        df = add_smas(df, short, long)
        crossovers = find_all_crossovers(df)
        hit = most_recent_crossover_in_lookback(df, crossovers, lookback)
        if hit is None:
            continue

        sparkline = build_sparkline(df, hit["position"])
        last_row = df.iloc[-1]
        results.append({
            "symbol": symbol,
            "signal": hit["signal"],
            "crossover_date": hit["date"].strftime("%Y-%m-%d"),
            "bars_ago": hit["bars_ago"],
            "weight": hit["weight"],
            "close": round(float(last_row["close"]), 2),
            "sma_short": round(float(last_row["sma_short"]), 2) if not pd.isna(last_row["sma_short"]) else None,
            "sma_long": round(float(last_row["sma_long"]), 2) if not pd.isna(last_row["sma_long"]) else None,
            "sparkline": sparkline,
        })

    results.sort(key=lambda r: r["bars_ago"])
    return ScanOutcome(results=results, scanned=len(symbol_tokens), skipped=skipped, failed=failed, unmatched=[])
