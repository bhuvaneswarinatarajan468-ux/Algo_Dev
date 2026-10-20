"""SMA-crossover backtesting for Algo.

Reuses the crossover logic in scanner.py (add_smas / find_all_crossovers) so
the backtester and the live scanner always agree on what counts as a signal.

Look-ahead bias rule: a crossover detected using day T's close triggers a
trade that executes at day T+1's OPEN, never at day T's own close.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

import scanner

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CANDLES_DIR = DATA_DIR / "candles"
JOBS_DIR = DATA_DIR / "jobs"
CHUNK_DAYS = 365


def _ensure_dirs() -> None:
    CANDLES_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Cost assumptions
#
# [VERIFY] These percentages approximate Indian equity delivery trading costs
# (STT, exchange transaction charges, GST, stamp duty) as of this writing.
# Tax rates change - verify current rates before relying on these numbers.
# ---------------------------------------------------------------------------

@dataclass
class CostParams:
    brokerage_pct: float = 0.0       # Zerodha charges zero brokerage on equity delivery
    stt_pct: float = 0.1             # Securities Transaction Tax, both legs, delivery
    exchange_pct: float = 0.00345    # NSE transaction charges, both legs
    gst_pct: float = 18.0            # GST on (brokerage + exchange charges)
    stamp_duty_pct: float = 0.015    # Stamp duty, buy side only
    slippage_pct: float = 0.05       # Assumed slippage, each side

    def buy_cost_pct(self) -> float:
        return (
            self.brokerage_pct
            + self.stt_pct
            + self.exchange_pct
            + self.stamp_duty_pct
            + self.slippage_pct
            + self.gst_pct / 100 * (self.brokerage_pct + self.exchange_pct)
        )

    def sell_cost_pct(self) -> float:
        return (
            self.brokerage_pct
            + self.stt_pct
            + self.exchange_pct
            + self.slippage_pct
            + self.gst_pct / 100 * (self.brokerage_pct + self.exchange_pct)
        )

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "CostParams":
        if not data:
            return cls()
        defaults = asdict(cls())
        merged = {**defaults, **{k: v for k, v in data.items() if k in defaults}}
        return cls(**merged)


# ---------------------------------------------------------------------------
# Candle fetching with disk cache + chunking for long ranges
# ---------------------------------------------------------------------------

def _cache_path(token: int) -> Path:
    return CANDLES_DIR / f"{token}.csv"


def _load_cache(token: int) -> Optional[pd.DataFrame]:
    path = _cache_path(token)
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["date"])
    return df if not df.empty else None


def _save_cache(token: int, df: pd.DataFrame) -> None:
    _ensure_dirs()
    df.to_csv(_cache_path(token), index=False)


def _fetch_chunked(kite, token: int, start: datetime, end: datetime) -> pd.DataFrame:
    frames = []
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=CHUNK_DAYS), end)
        time.sleep(scanner.KITE_RATE_LIMIT_DELAY)
        frames.append(scanner.fetch_historical_data(kite, token, cur, chunk_end))
        cur = chunk_end + timedelta(days=1)
    if not frames:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    return pd.concat(frames, ignore_index=True)


def fetch_candles_range(kite, token: int, start: datetime, end: datetime) -> pd.DataFrame:
    """Fetch daily candles for [start, end], using and extending a disk cache."""
    cached = _load_cache(token)
    to_fetch: list[tuple[datetime, datetime]] = []

    if cached is None or cached.empty:
        to_fetch.append((start, end))
    else:
        cached_min = cached["date"].min()
        cached_max = cached["date"].max()
        if start < cached_min:
            to_fetch.append((start, cached_min - timedelta(days=1)))
        if end > cached_max:
            to_fetch.append((cached_max + timedelta(days=1), end))

    new_frames = [cached] if cached is not None else []
    for s, e in to_fetch:
        if s > e:
            continue
        new_frames.append(_fetch_chunked(kite, token, s, e))

    if len(new_frames) > (1 if cached is not None else 0):
        combined = pd.concat(new_frames, ignore_index=True)
        combined = combined.drop_duplicates(subset="date", keep="last").sort_values("date").reset_index(drop=True)
        _save_cache(token, combined)
        cached = combined
    elif cached is None:
        cached = pd.concat(new_frames, ignore_index=True) if new_frames else pd.DataFrame(
            columns=["date", "open", "high", "low", "close", "volume"]
        )

    mask = (cached["date"] >= start) & (cached["date"] <= end)
    return cached[mask].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Trade simulation (no look-ahead: signal on close[T], trade at open[T+1])
# ---------------------------------------------------------------------------

def simulate_trades(df: pd.DataFrame, short: int, long: int, allow_short: bool = False) -> list[dict]:
    """Walk a stock's SMA crossovers and produce unsized trades.

    Each trade has: type ('long'/'short'), entry_date, entry_price,
    exit_date, exit_price, exit_reason.
    """
    df = scanner.add_smas(df, short, long).reset_index(drop=True)
    crossovers = scanner.find_all_crossovers(df)
    n = len(df)
    trades: list[dict] = []
    position: Optional[dict] = None

    for _, cross in crossovers.iterrows():
        pos_idx = int(cross["position"])
        entry_idx = pos_idx + 1
        if entry_idx >= n:
            continue  # crossover on the final candle - no next-day open to trade at
        entry_date = df.loc[entry_idx, "date"]
        entry_price = float(df.loc[entry_idx, "open"])

        if cross["signal"] == "bullish":
            if position and position["type"] == "short":
                trades.append(_close(position, entry_date, entry_price, "bullish_crossover"))
                position = None
            if position is None:
                position = {"type": "long", "entry_date": entry_date, "entry_price": entry_price}
        elif cross["signal"] == "bearish":
            if position and position["type"] == "long":
                trades.append(_close(position, entry_date, entry_price, "bearish_crossover"))
                position = None
            if position is None and allow_short:
                position = {"type": "short", "entry_date": entry_date, "entry_price": entry_price}

    if position is not None:
        last_date = df.loc[n - 1, "date"]
        last_close = float(df.loc[n - 1, "close"])
        trades.append(_close(position, last_date, last_close, "open_at_end"))

    return trades


def _close(position: dict, exit_date, exit_price: float, exit_reason: str) -> dict:
    return {
        "type": position["type"],
        "entry_date": position["entry_date"],
        "entry_price": position["entry_price"],
        "exit_date": exit_date,
        "exit_price": exit_price,
        "exit_reason": exit_reason,
    }


def size_and_cost_trade(trade: dict, capital: float, costs: CostParams) -> dict:
    """Attach quantity, costs, and net P&L to an unsized trade."""
    qty = max(int(capital // trade["entry_price"]), 0)
    entry_value = qty * trade["entry_price"]
    exit_value = qty * trade["exit_price"]

    if trade["type"] == "long":
        gross_pnl = (trade["exit_price"] - trade["entry_price"]) * qty
        entry_cost = entry_value * costs.buy_cost_pct() / 100
        exit_cost = exit_value * costs.sell_cost_pct() / 100
    else:
        gross_pnl = (trade["entry_price"] - trade["exit_price"]) * qty
        entry_cost = entry_value * costs.sell_cost_pct() / 100
        exit_cost = exit_value * costs.buy_cost_pct() / 100

    total_cost = entry_cost + exit_cost
    net_pnl = gross_pnl - total_cost
    return_pct = (net_pnl / entry_value * 100) if entry_value > 0 else 0.0
    holding_days = (trade["exit_date"] - trade["entry_date"]).days

    return {
        **trade,
        "qty": qty,
        "entry_value": round(entry_value, 2),
        "exit_value": round(exit_value, 2),
        "cost": round(total_cost, 2),
        "pnl": round(net_pnl, 2),
        "return_pct": round(return_pct, 2),
        "holding_days": holding_days,
    }


# ---------------------------------------------------------------------------
# Equity curve + metrics (single stock; capital is reused per trade, not
# compounded, matching "starting capital per trade" in the UI)
# ---------------------------------------------------------------------------

def build_equity_curve(df: pd.DataFrame, trades: list[dict], capital: float) -> list[dict]:
    """Daily equity: capital + realized P&L to date + unrealized P&L of an open trade."""
    df = df.reset_index(drop=True)
    curve = []
    trade_idx = 0
    realized = 0.0
    open_trade = None

    for _, row in df.iterrows():
        date = row["date"]
        while trade_idx < len(trades) and trades[trade_idx]["entry_date"] <= date and open_trade is None:
            open_trade = trades[trade_idx]
        if open_trade and date >= open_trade["entry_date"]:
            if date >= open_trade["exit_date"]:
                realized += open_trade["pnl"]
                open_trade = None
                trade_idx += 1
                equity = capital + realized
            else:
                sign = 1 if trades[trade_idx]["type"] == "long" else -1
                unrealized = (row["close"] - open_trade["entry_price"]) * open_trade["qty"] * sign
                equity = capital + realized + unrealized
        else:
            equity = capital + realized
        curve.append({"date": date.strftime("%Y-%m-%d"), "equity": round(equity, 2)})

    return curve


def compute_drawdown(equity_curve: list[dict]) -> list[dict]:
    peak = float("-inf")
    out = []
    for point in equity_curve:
        peak = max(peak, point["equity"])
        dd = (point["equity"] / peak - 1) * 100 if peak > 0 else 0.0
        out.append({"date": point["date"], "drawdown_pct": round(dd, 2)})
    return out


def compute_metrics(trades: list[dict], equity_curve: list[dict], capital: float, buy_hold_return_pct: float) -> dict:
    if not equity_curve:
        return {
            "total_return_pct": 0.0, "cagr_pct": 0.0, "num_trades": 0, "win_rate_pct": 0.0,
            "avg_win_pct": 0.0, "avg_loss_pct": 0.0, "profit_factor": None, "max_drawdown_pct": 0.0,
            "buy_hold_return_pct": buy_hold_return_pct,
        }

    final_equity = equity_curve[-1]["equity"]
    total_return_pct = (final_equity / capital - 1) * 100 if capital > 0 else 0.0

    start_date = datetime.strptime(equity_curve[0]["date"], "%Y-%m-%d")
    end_date = datetime.strptime(equity_curve[-1]["date"], "%Y-%m-%d")
    days = max((end_date - start_date).days, 1)
    years = days / 365.0
    cagr_pct = ((final_equity / capital) ** (1 / years) - 1) * 100 if capital > 0 and years > 0 and final_equity > 0 else 0.0

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    win_rate_pct = (len(wins) / len(trades) * 100) if trades else 0.0
    avg_win_pct = sum(t["return_pct"] for t in wins) / len(wins) if wins else 0.0
    avg_loss_pct = sum(t["return_pct"] for t in losses) / len(losses) if losses else 0.0
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

    drawdowns = compute_drawdown(equity_curve)
    max_drawdown_pct = min((d["drawdown_pct"] for d in drawdowns), default=0.0)

    return {
        "total_return_pct": round(total_return_pct, 2),
        "cagr_pct": round(cagr_pct, 2),
        "num_trades": len(trades),
        "win_rate_pct": round(win_rate_pct, 2),
        "avg_win_pct": round(avg_win_pct, 2),
        "avg_loss_pct": round(avg_loss_pct, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "buy_hold_return_pct": round(buy_hold_return_pct, 2),
    }


def buy_and_hold_curve(df: pd.DataFrame, capital: float) -> list[dict]:
    df = df.reset_index(drop=True)
    if df.empty:
        return []
    first_close = float(df.loc[0, "close"])
    qty = capital / first_close if first_close > 0 else 0
    return [
        {"date": row["date"].strftime("%Y-%m-%d"), "equity": round(qty * float(row["close"]), 2)}
        for _, row in df.iterrows()
    ]


# ---------------------------------------------------------------------------
# Single-stock backtest
# ---------------------------------------------------------------------------

def run_single_backtest(
    kite, symbol: str, token: int, short: int, long: int,
    start: datetime, end: datetime, capital: float,
    allow_short: bool, costs: CostParams,
) -> dict:
    df = fetch_candles_range(kite, token, start, end)
    if len(df) < long + 2:
        raise ValueError(f"Not enough history for {symbol} in the selected date range")

    raw_trades = simulate_trades(df, short, long, allow_short)
    trades = [size_and_cost_trade(t, capital, costs) for t in raw_trades]
    equity_curve = build_equity_curve(df, trades, capital)
    bh_curve = buy_and_hold_curve(df, capital)
    bh_return_pct = (bh_curve[-1]["equity"] / capital - 1) * 100 if bh_curve else 0.0
    metrics = compute_metrics(trades, equity_curve, capital, bh_return_pct)
    drawdown = compute_drawdown(equity_curve)

    trades_out = [
        {
            **{k: v for k, v in t.items() if k not in ("entry_date", "exit_date")},
            "symbol": symbol,
            "entry_date": t["entry_date"].strftime("%Y-%m-%d"),
            "exit_date": t["exit_date"].strftime("%Y-%m-%d"),
        }
        for t in trades
    ]

    return {
        "symbol": symbol,
        "summary": metrics,
        "equity_curve": equity_curve,
        "buy_hold_curve": bh_curve,
        "drawdown": drawdown,
        "trades": trades_out,
    }


# ---------------------------------------------------------------------------
# Parameter sweep (single stock only - kept bounded in scope)
# ---------------------------------------------------------------------------

def run_parameter_sweep(
    kite, symbol: str, token: int, short_values: list[int], long_values: list[int],
    start: datetime, end: datetime, capital: float, allow_short: bool, costs: CostParams,
) -> list[dict]:
    df = fetch_candles_range(kite, token, start, end)
    if df.empty:
        return []

    df = df.reset_index(drop=True)
    split_idx = int(len(df) * 0.7)
    split_date = df.loc[split_idx, "date"]

    results = []
    for short in short_values:
        for long in long_values:
            if short >= long:
                continue
            try:
                raw_trades = simulate_trades(df, short, long, allow_short)
            except Exception:  # noqa: BLE001
                continue
            sized = [size_and_cost_trade(t, capital, costs) for t in raw_trades]
            in_sample = [t for t in sized if t["entry_date"] < split_date]
            out_sample = [t for t in sized if t["entry_date"] >= split_date]

            results.append({
                "short": short,
                "long": long,
                "in_sample_return_pct": round(sum(t["return_pct"] for t in in_sample), 2) if in_sample else 0.0,
                "in_sample_trades": len(in_sample),
                "out_sample_return_pct": round(sum(t["return_pct"] for t in out_sample), 2) if out_sample else 0.0,
                "out_sample_trades": len(out_sample),
            })

    return results


# ---------------------------------------------------------------------------
# Background job store (persisted to disk, per-process in-memory lock)
# ---------------------------------------------------------------------------

_jobs_lock = threading.Lock()


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _write_job(job_id: str, data: dict) -> None:
    _ensure_dirs()
    with _jobs_lock:
        _job_path(job_id).write_text(json.dumps(data), encoding="utf-8")


def get_job(job_id: str) -> Optional[dict]:
    path = _job_path(job_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def create_universe_job(
    kite, symbol_tokens: dict[str, int], short: int, long: int,
    start: datetime, end: datetime, capital: float, allow_short: bool, costs: CostParams,
) -> str:
    job_id = uuid.uuid4().hex
    _write_job(job_id, {
        "status": "running",
        "progress": {"done": 0, "total": len(symbol_tokens)},
        "result": None,
        "error": None,
    })

    thread = threading.Thread(
        target=_run_universe_job,
        args=(job_id, kite, symbol_tokens, short, long, start, end, capital, allow_short, costs),
        daemon=True,
    )
    thread.start()
    return job_id


def _run_universe_job(
    job_id: str, kite, symbol_tokens: dict[str, int], short: int, long: int,
    start: datetime, end: datetime, capital: float, allow_short: bool, costs: CostParams,
) -> None:
    per_stock: list[dict] = []
    all_trades_raw: list[dict] = []
    stock_frames: dict[str, pd.DataFrame] = {}
    done = 0

    try:
        for symbol, token in symbol_tokens.items():
            try:
                df = fetch_candles_range(kite, token, start, end)
                if len(df) >= long + 2:
                    raw_trades = simulate_trades(df, short, long, allow_short)
                    for t in raw_trades:
                        all_trades_raw.append({**t, "symbol": symbol})
                    stock_frames[symbol] = df
            except Exception:  # noqa: BLE001
                pass
            done += 1
            job = get_job(job_id) or {}
            job["progress"] = {"done": done, "total": len(symbol_tokens)}
            _write_job(job_id, job)

        # Equal-weight sizing: split total capital across stocks concurrently open
        # at each trade's entry moment. This is a simplifying assumption, shown
        # on screen - it is not a continuously-rebalanced portfolio.
        all_trades_raw.sort(key=lambda t: t["entry_date"])
        sized_trades = []
        for t in all_trades_raw:
            concurrent = sum(
                1 for other in all_trades_raw
                if other["entry_date"] <= t["entry_date"] < other["exit_date"]
                or other["entry_date"] == t["entry_date"]
            )
            concurrent = max(concurrent, 1)
            slot_capital = capital / concurrent
            sized = size_and_cost_trade(t, slot_capital, costs)
            sized["symbol"] = t["symbol"]
            sized_trades.append(sized)

        per_stock = _summarize_per_stock(sized_trades, stock_frames, capital, len(symbol_tokens))
        combined_equity = _combined_equity_curve(sized_trades, stock_frames, capital)
        combined_bh = _combined_buy_hold_curve(stock_frames, capital)
        bh_return_pct = (combined_bh[-1]["equity"] / capital - 1) * 100 if combined_bh else 0.0
        metrics = compute_metrics(sized_trades, combined_equity, capital, bh_return_pct)
        drawdown = compute_drawdown(combined_equity)

        trades_out = [
            {
                **{k: v for k, v in t.items() if k not in ("entry_date", "exit_date")},
                "entry_date": t["entry_date"].strftime("%Y-%m-%d"),
                "exit_date": t["exit_date"].strftime("%Y-%m-%d"),
            }
            for t in sized_trades
        ]

        result = {
            "summary": metrics,
            "equity_curve": combined_equity,
            "buy_hold_curve": combined_bh,
            "drawdown": drawdown,
            "trades": trades_out,
            "per_stock": per_stock,
            "assumption": (
                "Equal-weight model: total capital is split evenly across stocks "
                "that are in a position at the moment each trade opens. This is a "
                "simplification, not a continuously rebalanced portfolio."
            ),
        }
        _write_job(job_id, {
            "status": "done",
            "progress": {"done": len(symbol_tokens), "total": len(symbol_tokens)},
            "result": result,
            "error": None,
        })
    except Exception as exc:  # noqa: BLE001
        _write_job(job_id, {
            "status": "error",
            "progress": {"done": done, "total": len(symbol_tokens)},
            "result": None,
            "error": str(exc),
        })


def _summarize_per_stock(sized_trades, stock_frames, capital, universe_size) -> list[dict]:
    by_symbol: dict[str, list[dict]] = {}
    for t in sized_trades:
        by_symbol.setdefault(t["symbol"], []).append(t)

    out = []
    for symbol, trades in by_symbol.items():
        total_pnl = sum(t["pnl"] for t in trades)
        total_entry_value = sum(t["entry_value"] for t in trades) or 1
        out.append({
            "symbol": symbol,
            "num_trades": len(trades),
            "return_pct": round(total_pnl / total_entry_value * 100, 2),
            "pnl": round(total_pnl, 2),
        })
    out.sort(key=lambda r: r["return_pct"], reverse=True)
    return out


def _combined_equity_curve(sized_trades, stock_frames, capital) -> list[dict]:
    all_dates = sorted(set(d for df in stock_frames.values() for d in df["date"]))
    if not all_dates:
        return []

    realized = 0.0
    closed_ids = set()
    curve = []
    for date in all_dates:
        for i, t in enumerate(sized_trades):
            if i in closed_ids:
                continue
            if t["exit_date"] <= date:
                realized += t["pnl"]
                closed_ids.add(i)

        unrealized = 0.0
        for i, t in enumerate(sized_trades):
            if i in closed_ids:
                continue
            if t["entry_date"] <= date < t["exit_date"]:
                df = stock_frames.get(t["symbol"])
                if df is None:
                    continue
                row = df[df["date"] == date]
                if row.empty:
                    continue
                price = float(row.iloc[0]["close"])
                sign = 1 if t["type"] == "long" else -1
                unrealized += (price - t["entry_price"]) * t["qty"] * sign

        curve.append({"date": date.strftime("%Y-%m-%d"), "equity": round(capital + realized + unrealized, 2)})

    return curve


def _combined_buy_hold_curve(stock_frames: dict[str, pd.DataFrame], capital: float) -> list[dict]:
    if not stock_frames:
        return []
    per_stock_capital = capital / len(stock_frames)
    all_dates = sorted(set(d for df in stock_frames.values() for d in df["date"]))
    qty_by_symbol = {}
    for symbol, df in stock_frames.items():
        first_close = float(df.iloc[0]["close"])
        qty_by_symbol[symbol] = per_stock_capital / first_close if first_close > 0 else 0

    curve = []
    for date in all_dates:
        total = 0.0
        for symbol, df in stock_frames.items():
            row = df[df["date"] == date]
            if row.empty:
                continue
            total += qty_by_symbol[symbol] * float(row.iloc[0]["close"])
        curve.append({"date": date.strftime("%Y-%m-%d"), "equity": round(total, 2)})
    return curve
