"""Tests de la caché local y del catálogo de instrumentos."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from cedears import storage, universe
from cedears.config import settings


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    patched = replace(settings, db_path=tmp_path / "test.sqlite3")
    monkeypatch.setattr(storage, "settings", patched)
    storage.init_db()
    return patched


def test_save_and_load_bars(temp_db):
    bars = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-03"]),
            "open": [1.0, 2.0, 2.5],
            "high": [2.0, 3.0, 3.5],
            "low": [0.5, 1.5, 2.0],
            "close": [1.5, 2.5, 3.0],
            "volume": [10, 20, 30],
        }
    )
    storage.save_bars("aapl", "bcba", bars)
    loaded = storage.load_bars("AAPL", "BCBA")
    assert len(loaded) == 2  # la fecha duplicada se actualiza, no se duplica
    assert loaded["close"].iloc[-1] == pytest.approx(3.0)


def test_json_ttl(temp_db):
    storage.save_json("k", {"v": 1})
    assert storage.load_json("k")[0] == {"v": 1}
    assert storage.load_json("k", ttl_seconds=3600) is not None
    assert storage.load_json("k", ttl_seconds=-1) is None


def test_clear_cache_by_prefix(temp_db):
    storage.save_json("iol:test", {"a": 1})
    storage.save_json("fx:test", {"a": 2})
    storage.clear_cache("iol")
    assert storage.load_json("iol:test") is None
    assert storage.load_json("fx:test") is not None


def test_universe_load_and_defaults():
    frame = universe.load_universe()
    assert not frame.empty
    assert {"symbol", "company", "type", "sector"}.issubset(frame.columns)
    assert frame["symbol"].is_unique

    snapshot = pd.DataFrame(
        [{"symbol": "AAPL", "name": "Apple", "last": 100.0}, {"symbol": "ZZZZ", "name": "Desconocida", "last": 1.0}]
    )
    merged = universe.attach_universe(snapshot, frame).set_index("symbol")
    assert merged.loc["AAPL", "sector"] == "Tecnología"
    assert merged.loc["AAPL", "type"] == "CEDEAR"
    assert merged.loc["ZZZZ", "sector"] == "Otros"
    assert merged.loc["ZZZZ", "company"] == "Desconocida"
    assert pd.isna(merged.loc["ZZZZ", "ratio"])


def test_sectors_order():
    frame = pd.DataFrame({"sector": ["Otros", "Tecnología", "Salud", None]})
    order = universe.sectors_in(frame)
    assert order[0] == "Tecnología"
    assert "Otros" in order
