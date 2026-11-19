"""Tests del simulador de inversión."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from ui import data as data_layer
from ui.views import simulator


@pytest.fixture()
def frame():
    return pd.DataFrame([{"symbol": "AAPL", "last": 150.0, "variacion_diaria": 1.0}])


def test_simulate_profit(monkeypatch, frame):
    monkeypatch.setattr(data_layer, "last_price_before", lambda symbol, target: (100.0, pd.Timestamp("2024-01-02")))
    ccl = pd.DataFrame({"date": pd.to_datetime(["2024-01-02", "2025-01-02"]), "ccl": [1000.0, 1250.0]})

    result = simulator.simulate("AAPL", 100_000, date(2024, 1, 2), frame, ccl)
    assert result is not None
    assert result["units"] == 1000
    assert result["invested"] == pytest.approx(100_000)
    assert result["value"] == pytest.approx(150_000)
    assert result["pnl"] == pytest.approx(50_000)
    assert result["pnl_pct"] == pytest.approx(50.0)
    # 150.000 ARS / 1.250 CCL = 120 USD vs 100 USD invertidos
    assert result["value_usd"] == pytest.approx(120.0)
    assert result["pnl_usd_pct"] == pytest.approx(20.0)


def test_simulate_uses_whole_units(monkeypatch, frame):
    monkeypatch.setattr(data_layer, "last_price_before", lambda symbol, target: (123.0, pd.Timestamp("2024-01-02")))
    result = simulator.simulate("AAPL", 100_000, date(2024, 1, 2), frame, pd.DataFrame())
    assert result is not None
    assert result["units"] == 813
    assert result["remaining"] == pytest.approx(100_000 - 813 * 123.0)


def test_simulate_without_history_returns_none(monkeypatch, frame):
    monkeypatch.setattr(data_layer, "last_price_before", lambda symbol, target: (None, None))
    assert simulator.simulate("AAPL", 100_000, date(2024, 1, 2), frame, pd.DataFrame()) is None


def test_simulate_loss(monkeypatch, frame):
    monkeypatch.setattr(data_layer, "last_price_before", lambda symbol, target: (200.0, pd.Timestamp("2024-01-02")))
    result = simulator.simulate("AAPL", 100_000, date(2024, 1, 2), frame, pd.DataFrame())
    assert result is not None
    assert result["pnl"] < 0
    assert result["pnl_pct"] == pytest.approx(-25.0)
