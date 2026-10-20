"""Offline tests for backtest.py using synthetic price data.

These prove the three properties that matter most for a trustworthy
backtest: no look-ahead (trade at next day's open, not today's close),
costs reduce returns, and any position still open at the end is closed
out at the last available price.
"""
from datetime import datetime, timedelta

import pandas as pd

import backtest


def make_df(opens: list[float], closes: list[float], start: str = "2024-01-01") -> pd.DataFrame:
    dates = [datetime.fromisoformat(start) + timedelta(days=i) for i in range(len(closes))]
    return pd.DataFrame({
        "date": dates,
        "open": opens,
        "high": [max(o, c) for o, c in zip(opens, closes)],
        "low": [min(o, c) for o, c in zip(opens, closes)],
        "close": closes,
        "volume": [1000] * len(closes),
    })


def bullish_ramp_df():
    # Flat for a while, then a ramp that produces a clean bullish crossover.
    closes = [100.0] * 35 + [100 + i * 3 for i in range(1, 16)]
    # Opens deliberately different from the previous close so a same-day-close
    # execution and a next-day-open execution would give different prices.
    opens = [c - 7 for c in closes]
    return make_df(opens, closes)


def test_trade_executes_at_next_day_open_not_same_day_close():
    df = bullish_ramp_df()
    trades = backtest.simulate_trades(df, short=5, long=20, allow_short=False)

    assert len(trades) >= 1
    trade = trades[0]

    crossovers = backtest.scanner.find_all_crossovers(backtest.scanner.add_smas(df, 5, 20))
    cross_position = int(crossovers.iloc[0]["position"])
    df_reset = df.reset_index(drop=True)

    same_day_close = float(df_reset.loc[cross_position, "close"])
    next_day_open = float(df_reset.loc[cross_position + 1, "open"])

    assert trade["entry_price"] == next_day_open
    assert trade["entry_price"] != same_day_close
    assert trade["entry_date"] == df_reset.loc[cross_position + 1, "date"]


def test_costs_reduce_returns():
    df = bullish_ramp_df()
    # Extend with a downturn so the long position actually closes with a
    # realized, costable trade rather than being left open at the end.
    closes = df["close"].tolist() + [180.0 - i * 3 for i in range(1, 10)]
    opens = df["open"].tolist() + [c + 2 for c in closes[-9:]]
    df2 = make_df(opens, closes)

    raw_trades = backtest.simulate_trades(df2, short=5, long=20, allow_short=False)
    assert len(raw_trades) >= 1
    trade = raw_trades[0]

    zero_cost = backtest.CostParams(
        brokerage_pct=0, stt_pct=0, exchange_pct=0, gst_pct=0, stamp_duty_pct=0, slippage_pct=0
    )
    with_cost = backtest.CostParams(
        brokerage_pct=0, stt_pct=0.1, exchange_pct=0.00345, gst_pct=18, stamp_duty_pct=0.015, slippage_pct=0.05
    )

    sized_zero = backtest.size_and_cost_trade(trade, capital=100000, costs=zero_cost)
    sized_with_cost = backtest.size_and_cost_trade(trade, capital=100000, costs=with_cost)

    assert sized_zero["cost"] == 0
    assert sized_with_cost["cost"] > 0
    assert sized_with_cost["pnl"] < sized_zero["pnl"]
    assert sized_with_cost["return_pct"] < sized_zero["return_pct"]


def test_open_trade_closed_at_end_of_period():
    # A bullish crossover near the end of the data with no subsequent
    # bearish crossover - the position must still be closed at the last row.
    df = bullish_ramp_df()
    trades = backtest.simulate_trades(df, short=5, long=20, allow_short=False)

    assert len(trades) == 1
    trade = trades[0]
    last_row = df.iloc[-1]

    assert trade["exit_reason"] == "open_at_end"
    assert trade["exit_date"] == last_row["date"]
    assert trade["exit_price"] == float(last_row["close"])


def test_bearish_crossover_closes_long_before_end():
    closes = [100.0] * 35 + [100 + i * 3 for i in range(1, 16)] + [200 - i * 4 for i in range(1, 16)]
    opens = [c - 1 for c in closes]
    df = make_df(opens, closes)

    trades = backtest.simulate_trades(df, short=5, long=20, allow_short=False)
    assert len(trades) >= 1
    assert trades[0]["exit_reason"] == "bearish_crossover"


def test_short_disabled_by_default_means_no_short_trades():
    closes = [100.0] * 35 + [100 - i * 3 for i in range(1, 16)]
    opens = [c + 5 for c in closes]
    df = make_df(opens, closes)

    trades = backtest.simulate_trades(df, short=5, long=20, allow_short=False)
    assert all(t["type"] != "short" for t in trades)


def test_short_enabled_opens_short_on_bearish_crossover():
    closes = [100.0] * 35 + [100 - i * 3 for i in range(1, 16)]
    opens = [c + 5 for c in closes]
    df = make_df(opens, closes)

    trades = backtest.simulate_trades(df, short=5, long=20, allow_short=True)
    assert any(t["type"] == "short" for t in trades)


def test_equity_curve_starts_near_capital_and_tracks_realized_pnl():
    df = bullish_ramp_df()
    trades_raw = backtest.simulate_trades(df, short=5, long=20, allow_short=False)
    costs = backtest.CostParams()
    trades = [backtest.size_and_cost_trade(t, 100000, costs) for t in trades_raw]
    curve = backtest.build_equity_curve(df, trades, 100000)

    assert curve[0]["equity"] == 100000
    assert curve[-1]["equity"] == round(100000 + sum(t["pnl"] for t in trades), 2)
