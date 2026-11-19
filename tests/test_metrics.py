"""Tests de métricas financieras."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cedears import metrics


def _bars(prices: list[float], start: str = "2024-01-01", volumes: list[float] | None = None) -> pd.DataFrame:
    dates = pd.date_range(start, periods=len(prices), freq="D")
    volumes = volumes or [1_000.0] * len(prices)
    return pd.DataFrame(
        {
            "date": dates,
            "open": prices,
            "high": [p * 1.02 for p in prices],
            "low": [p * 0.98 for p in prices],
            "close": prices,
            "volume": volumes,
        }
    )


def test_daily_volatility_formula():
    assert metrics.daily_volatility(110, 90, 100) == pytest.approx(20.0)
    assert np.isnan(metrics.daily_volatility(110, 90, 0))
    assert np.isnan(metrics.daily_volatility(None, 90, 100))


def test_discount_from_high_formula():
    assert metrics.discount_from_high(80, 100) == pytest.approx(20.0)
    assert metrics.discount_from_high(120, 100) == pytest.approx(-20.0)
    assert np.isnan(metrics.discount_from_high(80, None))


def test_relative_volume():
    assert metrics.relative_volume(200, 100) == pytest.approx(2.0)
    assert np.isnan(metrics.relative_volume(200, 0))
    assert np.isnan(metrics.relative_volume(None, 100))


def test_pct_change_from():
    assert metrics.pct_change_from(100, 110) == pytest.approx(10.0)
    assert metrics.pct_change_from(100, 90) == pytest.approx(-10.0)
    assert np.isnan(metrics.pct_change_from(0, 90))


def test_trend_label_rules():
    assert metrics.trend_label(2.0, 15.0) == "Positiva"
    assert metrics.trend_label(-1.0, -10.0) == "Negativa"
    assert metrics.trend_label(0.5, 1.0) == "Lateral"
    assert metrics.trend_label(np.nan, np.nan) == "N/D"
    assert metrics.trend_label(3.0, -1.0) == "Positiva"
    # Mes lateral: decide la semana
    assert metrics.trend_label(-3.0, 1.0) == "Negativa"
    assert metrics.trend_label(-3.0, -0.5) == "Negativa"
    assert metrics.trend_label(3.0, 0.5) == "Positiva"


def test_history_features_seven_and_thirty_days():
    prices = [100 + i for i in range(60)]
    bars = _bars(prices)
    features = metrics.history_features(bars)

    last = prices[-1]
    assert features["var_7d"] == pytest.approx((last / prices[-8] - 1) * 100, rel=1e-6)
    assert features["var_30d"] == pytest.approx((last / prices[-31] - 1) * 100, rel=1e-6)
    assert features["max_52w"] == pytest.approx(max(p * 1.02 for p in prices))
    assert features["barras"] == 60


def test_history_features_without_data():
    features = metrics.history_features(pd.DataFrame())
    assert features["barras"] == 0
    assert np.isnan(features["var_7d"])


def test_volume_average_excludes_last_session():
    volumes = [100.0] * 25 + [1_000.0]
    features = metrics.history_features(_bars([100.0] * len(volumes), volumes=volumes))
    assert features["volumen_promedio"] == pytest.approx(100.0)


def test_pct_rank_bounds_and_nan():
    series = pd.Series([1.0, 2.0, np.nan, 3.0])
    ranked = metrics.pct_rank(series)
    assert ranked.max() == pytest.approx(100.0)
    assert ranked.min() == pytest.approx(100 / 3, rel=1e-3)
    assert np.isnan(ranked.iloc[2])

    empty = metrics.pct_rank(pd.Series([np.nan, np.nan]))
    assert empty.isna().all()


def test_signed_rank_range():
    series = pd.Series([1.0, 5.0, 10.0])
    signed = metrics.signed_rank(series)
    assert signed.min() == pytest.approx(-1.0)
    assert signed.max() == pytest.approx(1.0)
    assert signed.iloc[1] == pytest.approx(0.0)
    assert metrics.signed_rank(pd.Series([np.nan, np.nan])).isna().all()


def test_liquidity_bucket():
    assert metrics.liquidity_bucket(1_000_000) == "Baja"
    assert metrics.liquidity_bucket(10_000_000) == "Media"
    assert metrics.liquidity_bucket(100_000_000) == "Alta"
    assert metrics.liquidity_bucket(np.nan) == "N/D"


def test_intraday_recovery():
    assert metrics.intraday_recovery(90, 110, 110) == pytest.approx(1.0)
    assert metrics.intraday_recovery(90, 90, 110) == pytest.approx(0.0)
    assert np.isnan(metrics.intraday_recovery(100, 100, 100))
