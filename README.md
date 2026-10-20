# Algo_Dev

Algo is a trading analysis app that scans Nifty 100 stocks for moving-average crossover signals and backtests strategies with trading costs. Built with Python, React, and Zerodha Kite Connect, it helps evaluate trading ideas without placing orders.

**Algo only ever displays signals. It never places, modifies, or cancels orders.**

It scans the Nifty 100 for SMA crossovers (bullish/bearish) and shows them in
a dashboard, with a backtester to see how the same rule performed historically.

## Prerequisites

- Python 3.10 or later
- A Zerodha Kite Connect developer app (API key + secret) from
  [developers.kite.trade](https://developers.kite.trade/)
- VS Code (recommended) on Windows

## Setup (VS Code on Windows)

1. Open this folder (`Algo`) in VS Code.
2. Open a terminal in VS Code (`` Ctrl+` ``).
3. Create and activate a virtual environment:

   ```powershell
   python -m venv venv
   venv\Scripts\activate
   ```

4. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

5. Build the frontend (one-time, or whenever you change files in `frontend/`):

   ```powershell
   cd frontend
   npm install
   npm run build
   cd ..
   ```

   This produces `frontend/dist`, which FastAPI serves directly at `/` -
   so you only need one command and one port to run the whole app.

6. Copy the environment template and fill in your real Kite API key/secret:

   ```powershell
   copy .env.example .env
   ```

   Edit `.env` and set:

   ```
   KITE_API_KEY=your-actual-api-key
   KITE_API_SECRET=your-actual-api-secret
   ```

   In your Kite Connect app settings, set the **Redirect URL** to:

   ```
   http://127.0.0.1:8000/callback
   ```

7. Run the app:

   ```powershell
   python app.py
   ```

8. Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.
9. Click **Log in with Zerodha**, complete the Kite login, and you'll be
   redirected back automatically (or paste the `request_token` manually if
   the redirect doesn't land back on the app).

The server keeps running until you stop it with `Ctrl+C` in the terminal.

## Running the tests

```powershell
pytest -v
```

These are fully offline (synthetic price data, no Kite session required).

## How signals work

- Universe: Nifty 100, fetched from the official NSE CSV and cached locally
  as `nifty100.csv` (falls back to the cached file if NSE is unreachable).
- Each stock's daily candles (~200 calendar days) are fetched via
  `kite.historical_data`, respecting Kite's historical API rate limit
  (0.4s between requests, one retry on failure). Candles are cached in
  memory for 10 minutes, so repeat scans are fast.
- A bullish crossover is when the short SMA moves from at-or-below the long
  SMA to above it; a bearish crossover is the reverse.
- Only the most recent crossover within the chosen lookback window is
  reported per stock, scored by recency (100 = crossover on the latest
  candle, decaying to 0 at the edge of the lookback window).

**Signals are most reliable after market close** - during market hours the
day's candle is still forming and crossovers can flip before the close.

## How the Backtest tab works

Open the **Backtest** tab, pick a single stock or "All Nifty 100", set the
SMA periods, a date range, and starting capital, then click **Run Backtest**.

- A signal is calculated on day T's close, but the trade executes at day
  T+1's **open** - never at T's own close - so the backtest can't cheat by
  seeing the future.
- Long-only by default (buy on a bullish crossover, sell on the next
  bearish crossover). Turn on "Also short on bearish crossovers" to also
  simulate short trades - note that shorting delivery stocks in India isn't
  actually possible, so this is an intraday-style simulation only.
- Trading costs (brokerage, STT, exchange charges, GST, stamp duty,
  slippage) are deducted from every trade. Defaults are editable under
  "Trading costs" - **[VERIFY]** these are illustrative figures; confirm
  current rates before relying on them.
- "All Nifty 100" runs as a background job (it can take a while to fetch
  history for 100 stocks), with a progress indicator. It uses a simple
  equal-weight model: capital is split evenly across whatever stocks are
  in a position at the moment each trade opens - this is a simplification,
  not a continuously rebalanced portfolio, and is stated on screen.
- Candle data is cached under `data/` (git-ignored) so repeat backtests
  over the same stocks don't re-fetch from Kite.
- The optional **parameter sweep** tests a grid of short/long combinations
  on a single stock, split into an in-sample period (first 70% of the
  range) and an out-of-sample period (last 30%) - if a combination only
  looks good in-sample, it's likely overfit.
- Backtests use today's Nifty 100 membership, so results have survivorship
  bias, and past performance never predicts future results.

## Troubleshooting

- **"KITE_API_KEY / KITE_API_SECRET not set"** - copy `.env.example` to
  `.env` and fill in real values, then restart `python app.py`.
- **401 / "Session expired"** - Kite access tokens expire daily; log in
  again from the dashboard.
- **Symbols reported as "unmatched"** - Kite's instrument list occasionally
  lags NSE's index composition; these are skipped rather than failing the
  whole scan.
