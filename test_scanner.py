"""Offline tests for the SMA crossover logic in scanner.py.

These tests use synthetic price series only - no network access and no Kite
session required.
"""
from datetime import datetime, timedelta

import pandas as pd
import pytest

import scanner


def make_df(closes: list[float], start: str = "2024-01-01") -> pd.DataFrame:
    dates = [datetime.fromisoformat(start) + timedelta(days=i) for i in range(len(closes))]
    return pd.DataFrame({
        "date": dates,
        "open": closes,
        "high": closes,
        "low": closes,
        "close": closes,
        "volume": [1000] * len(closes),
    })


def test_bullish_crossover_detected():
    # Flat for a while, then a sharp ramp up so the short SMA crosses above the long SMA.
    closes = [100.0] * 35 + [100 + i * 3 for i in range(1, 16)]
    df = scanner.add_smas(make_df(closes), short=5, long=20)
    crossovers = scanner.find_all_crossovers(df)

    assert not crossovers.empty
    assert "bullish" in crossovers["signal"].values
    bullish_rows = crossovers[crossovers["signal"] == "bullish"]
    for _, row in bullish_rows.iterrows():
        assert row["sma_short"] > row["sma_long"]


def test_bearish_crossover_detected():
    # Flat for a while, then a sharp decline so the short SMA crosses below the long SMA.
    closes = [100.0] * 35 + [100 - i * 3 for i in range(1, 16)]
    df = scanner.add_smas(make_df(closes), short=5, long=20)
    crossovers = scanner.find_all_crossovers(df)

    assert not crossovers.empty
    assert "bearish" in crossovers["signal"].values
    bearish_rows = crossovers[crossovers["signal"] == "bearish"]
    for _, row in bearish_rows.iterrows():
        assert row["sma_short"] < row["sma_long"]


def test_no_signal_on_flat_prices():
    closes = [100.0] * 60
    df = scanner.add_smas(make_df(closes), short=5, long=20)
    crossovers = scanner.find_all_crossovers(df)
    assert crossovers.empty

    hit = scanner.most_recent_crossover_in_lookback(df, crossovers, lookback=20)
    assert hit is None


def test_more_recent_crossover_scores_higher_weight():
    lookback = 20
    # A crossover right at the last bar should score 100.
    closes_recent = [100.0] * 35 + [100 + i * 3 for i in range(1, 16)]
    df_recent = scanner.add_smas(make_df(closes_recent), short=5, long=20)
    crossovers_recent = scanner.find_all_crossovers(df_recent)
    hit_recent = scanner.most_recent_crossover_in_lookback(df_recent, crossovers_recent, lookback)

    # The same crossover, but followed by a few more flat days - still in the lookback
    # window, but further back than the "recent" case above.
    closes_older = [100.0] * 35 + [100 + i * 3 for i in range(1, 16)] + [250.0] * 5
    df_older = scanner.add_smas(make_df(closes_older), short=5, long=20)
    crossovers_older = scanner.find_all_crossovers(df_older)
    hit_older = scanner.most_recent_crossover_in_lookback(df_older, crossovers_older, lookback)

    assert hit_recent is not None
    assert hit_older is not None
    assert hit_recent["bars_ago"] < hit_older["bars_ago"]
    assert hit_recent["weight"] > hit_older["weight"]


def test_crossover_outside_lookback_window_is_ignored():
    lookback = 5
    # Crossover happens, then 10 more flat days pass - well outside a 5-day lookback.
    closes = [100.0] * 35 + [100 + i * 3 for i in range(1, 16)] + [250.0] * 10
    df = scanner.add_smas(make_df(closes), short=5, long=20)
    crossovers = scanner.find_all_crossovers(df)
    hit = scanner.most_recent_crossover_in_lookback(df, crossovers, lookback)
    assert hit is None


def test_too_little_history_yields_no_crossovers():
    # Fewer rows than the long SMA period means sma_long is never computable.
    closes = [100.0, 101.0, 102.0, 101.5, 103.0]
    df = scanner.add_smas(make_df(closes), short=5, long=20)
    assert df["sma_long"].isna().all()

    crossovers = scanner.find_all_crossovers(df)
    assert crossovers.empty


def test_validate_periods_rejects_short_not_less_than_long():
    with pytest.raises(scanner.ScanValidationError):
        scanner.validate_periods(short=30, long=30, lookback=20)
    with pytest.raises(scanner.ScanValidationError):
        scanner.validate_periods(short=40, long=30, lookback=20)


def test_validate_periods_rejects_bad_lookback():
    with pytest.raises(scanner.ScanValidationError):
        scanner.validate_periods(short=6, long=30, lookback=0)
    with pytest.raises(scanner.ScanValidationError):
        scanner.validate_periods(short=6, long=30, lookback=500)


def test_validate_periods_accepts_sensible_values():
    scanner.validate_periods(short=6, long=30, lookback=20)  # should not raise
