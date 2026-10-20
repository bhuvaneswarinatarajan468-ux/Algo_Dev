"""Algo - a semi-automated trading signal scanner built on Zerodha Kite Connect.

This application only ever displays signals. It never places, modifies, or
cancels orders.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import os

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from kiteconnect import KiteConnect
from pydantic import BaseModel, Field

import backtest
import scanner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("algo.app")

load_dotenv()

BASE_DIR = Path(__file__).parent
SESSION_FILE = BASE_DIR / ".session.json"
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

KITE_API_KEY = os.getenv("KITE_API_KEY", "")
KITE_API_SECRET = os.getenv("KITE_API_SECRET", "")
REDIRECT_URL = "http://127.0.0.1:8000/callback"

@asynccontextmanager
async def lifespan(app: FastAPI):
    if is_configured():
        _load_saved_session()
    else:
        logger.warning("KITE_API_KEY / KITE_API_SECRET not set - copy .env.example to .env and fill them in")
    yield


app = FastAPI(title="Algo", lifespan=lifespan)

_kite: Optional[KiteConnect] = None
_session_date: Optional[str] = None


def is_configured() -> bool:
    return bool(KITE_API_KEY and KITE_API_SECRET)


def get_kite() -> KiteConnect:
    global _kite
    if _kite is None:
        if not is_configured():
            raise HTTPException(status_code=500, detail="Kite API credentials are not configured")
        _kite = KiteConnect(api_key=KITE_API_KEY)
    return _kite


def is_logged_in() -> bool:
    return _session_date == date.today().isoformat() and _kite is not None and bool(getattr(_kite, "access_token", None))


def _load_saved_session() -> None:
    """On startup, reuse today's saved access token if present and still valid."""
    global _session_date
    if not is_configured() or not SESSION_FILE.exists():
        return
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read session file: %s", exc)
        return

    saved_date = data.get("date")
    access_token = data.get("access_token")
    if not saved_date or not access_token:
        return
    if saved_date != date.today().isoformat():
        logger.info("Saved session is from a previous day; a fresh login is required")
        return

    kite = get_kite()
    kite.set_access_token(access_token)
    try:
        kite.profile()  # verify the token is actually still valid
    except Exception as exc:  # noqa: BLE001
        logger.info("Saved access token is no longer valid: %s", exc)
        kite.set_access_token(None)
        return

    _session_date = saved_date
    logger.info("Reused saved Kite session from %s", saved_date)


def _save_session(access_token: str) -> None:
    today = date.today().isoformat()
    SESSION_FILE.write_text(json.dumps({"access_token": access_token, "date": today}), encoding="utf-8")
    global _session_date
    _session_date = today


def _expire_session() -> None:
    global _session_date
    _session_date = None
    if _kite is not None:
        _kite.set_access_token(None)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    request_token: str


@app.get("/api/status")
def api_status():
    login_url = None
    if is_configured():
        login_url = get_kite().login_url()
    return {
        "configured": is_configured(),
        "logged_in": is_logged_in(),
        "login_url": login_url,
    }


def _exchange_request_token(request_token: str) -> dict:
    kite = get_kite()
    try:
        session_data = kite.generate_session(request_token, api_secret=KITE_API_SECRET)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Kite login exchange failed")
        raise HTTPException(status_code=401, detail=f"Could not complete Kite login: {exc}") from exc

    access_token = session_data["access_token"]
    kite.set_access_token(access_token)
    _save_session(access_token)
    return session_data


@app.get("/callback")
def kite_callback(request_token: Optional[str] = None, status: Optional[str] = None):
    if status != "success" or not request_token:
        return RedirectResponse(url="/?login_error=1")
    try:
        _exchange_request_token(request_token)
    except HTTPException:
        return RedirectResponse(url="/?login_error=1")
    return RedirectResponse(url="/")


@app.post("/api/login")
def api_login(payload: LoginRequest):
    _exchange_request_token(payload.request_token)
    return {"ok": True}


@app.get("/api/profile")
def api_profile():
    if not is_logged_in():
        raise HTTPException(status_code=401, detail="Not logged in")
    kite = get_kite()
    try:
        profile = kite.profile()
    except Exception as exc:  # noqa: BLE001
        if exc.__class__.__name__ == "TokenException":
            _expire_session()
            raise HTTPException(status_code=401, detail="Session expired, please log in again") from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "user_name": profile.get("user_name"),
        "user_id": profile.get("user_id"),
        "products": profile.get("products", []),
        "exchanges": profile.get("exchanges", []),
    }


# ---------------------------------------------------------------------------
# Symbols (for the backtest stock selector)
# ---------------------------------------------------------------------------

@app.get("/api/symbols")
def api_symbols():
    if not is_logged_in():
        raise HTTPException(status_code=401, detail="Not logged in")
    try:
        symbols = scanner.get_nifty100_symbols()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"symbols": symbols}


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

@app.get("/api/signals")
def api_signals(
    short: int = Query(6, description="Short SMA period"),
    long: int = Query(30, description="Long SMA period"),
    lookback: int = Query(20, description="Lookback window in trading days"),
):
    if not is_logged_in():
        raise HTTPException(status_code=401, detail="Not logged in")

    try:
        scanner.validate_periods(short, long, lookback)
    except scanner.ScanValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    kite = get_kite()
    try:
        symbols = scanner.get_nifty100_symbols()
        symbol_tokens, unmatched = scanner.map_symbols_to_tokens(kite, symbols)
        outcome = scanner.scan_universe(kite, symbol_tokens, short, long, lookback)
    except scanner.SessionExpiredError as exc:
        _expire_session()
        raise HTTPException(status_code=401, detail="Session expired, please log in again") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    analyzed = outcome.scanned - len(outcome.skipped) - len(outcome.failed)
    return {
        "results": outcome.results,
        "total": len(symbols),
        "analyzed": analyzed,
        "skipped": outcome.skipped,
        "failed": outcome.failed,
        "unmatched": unmatched,
        "params": {"short": short, "long": long, "lookback": lookback},
    }


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

class CostInput(BaseModel):
    brokerage_pct: float = 0.0
    stt_pct: float = 0.1
    exchange_pct: float = 0.00345
    gst_pct: float = 18.0
    stamp_duty_pct: float = 0.015
    slippage_pct: float = 0.05


class SingleBacktestRequest(BaseModel):
    symbol: str
    short: int = 6
    long: int = 30
    start: str
    end: str
    capital: float = 100000
    allow_short: bool = False
    costs: CostInput = Field(default_factory=CostInput)


class AllBacktestRequest(BaseModel):
    short: int = 6
    long: int = 30
    start: str
    end: str
    capital: float = 100000
    allow_short: bool = False
    costs: CostInput = Field(default_factory=CostInput)


class SweepRequest(BaseModel):
    symbol: str
    short_values: list[int] = Field(default_factory=lambda: [5, 8, 10, 12, 15])
    long_values: list[int] = Field(default_factory=lambda: [20, 30, 40, 50, 60])
    start: str
    end: str
    capital: float = 100000
    allow_short: bool = False
    costs: CostInput = Field(default_factory=CostInput)


def _parse_date(value: str, field_name: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} date: {value}") from exc


def _require_login_and_kite():
    if not is_logged_in():
        raise HTTPException(status_code=401, detail="Not logged in")
    return get_kite()


def _resolve_symbol(kite, symbol: str) -> int:
    tokens, unmatched = scanner.map_symbols_to_tokens(kite, [symbol])
    if symbol in unmatched or symbol not in tokens:
        raise HTTPException(status_code=400, detail=f"Unknown NSE symbol: {symbol}")
    return tokens[symbol]


@app.post("/api/backtest/single")
def api_backtest_single(req: SingleBacktestRequest):
    kite = _require_login_and_kite()
    try:
        scanner.validate_periods(req.short, req.long)
    except scanner.ScanValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    start = _parse_date(req.start, "start")
    end = _parse_date(req.end, "end")
    if start >= end:
        raise HTTPException(status_code=400, detail="start date must be before end date")

    try:
        token = _resolve_symbol(kite, req.symbol)
        result = backtest.run_single_backtest(
            kite, req.symbol, token, req.short, req.long, start, end,
            req.capital, req.allow_short, backtest.CostParams.from_dict(req.costs.model_dump()),
        )
    except scanner.SessionExpiredError as exc:
        _expire_session()
        raise HTTPException(status_code=401, detail="Session expired, please log in again") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result


@app.post("/api/backtest/all")
def api_backtest_all(req: AllBacktestRequest):
    kite = _require_login_and_kite()
    try:
        scanner.validate_periods(req.short, req.long)
    except scanner.ScanValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    start = _parse_date(req.start, "start")
    end = _parse_date(req.end, "end")
    if start >= end:
        raise HTTPException(status_code=400, detail="start date must be before end date")

    try:
        symbols = scanner.get_nifty100_symbols()
        symbol_tokens, _unmatched = scanner.map_symbols_to_tokens(kite, symbols)
    except scanner.SessionExpiredError as exc:
        _expire_session()
        raise HTTPException(status_code=401, detail="Session expired, please log in again") from exc

    job_id = backtest.create_universe_job(
        kite, symbol_tokens, req.short, req.long, start, end,
        req.capital, req.allow_short, backtest.CostParams.from_dict(req.costs.model_dump()),
    )
    return {"job_id": job_id}


@app.get("/api/backtest/jobs/{job_id}")
def api_backtest_job(job_id: str):
    job = backtest.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    return job


@app.post("/api/backtest/sweep")
def api_backtest_sweep(req: SweepRequest):
    kite = _require_login_and_kite()
    start = _parse_date(req.start, "start")
    end = _parse_date(req.end, "end")
    if start >= end:
        raise HTTPException(status_code=400, detail="start date must be before end date")

    try:
        token = _resolve_symbol(kite, req.symbol)
        results = backtest.run_parameter_sweep(
            kite, req.symbol, token, req.short_values, req.long_values, start, end,
            req.capital, req.allow_short, backtest.CostParams.from_dict(req.costs.model_dump()),
        )
    except scanner.SessionExpiredError as exc:
        _expire_session()
        raise HTTPException(status_code=401, detail="Session expired, please log in again") from exc

    return {"results": results}


# ---------------------------------------------------------------------------
# Frontend (built React app, if present)
# ---------------------------------------------------------------------------

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/", response_class=HTMLResponse)
    def root_placeholder():
        return (
            "<html><body style='font-family: sans-serif; padding: 2rem;'>"
            "<h1>Algo backend is running</h1>"
            "<p>The frontend has not been built yet. API endpoints are available under "
            "<code>/api/*</code>.</p>"
            "</body></html>"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
