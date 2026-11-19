"""Tests del cliente de IOL con sesiones simuladas (sin red)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from cedears.iol_client import IOLAuthError, IOLAPIError, IOLClient, infer_ratio


class DummyResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload


class DummySession:
    def __init__(self, token_status: int = 200):
        self.headers: dict = {}
        self.token_calls = 0
        self.get_calls: list[tuple[str, dict]] = []
        self.token_status = token_status
        self.fail_next_get_401 = False

    def post(self, url, json=None, timeout=None):
        self.token_calls += 1
        if self.token_status != 200:
            return DummyResponse(self.token_status, {"error": "bad credentials"})
        return DummyResponse(
            200,
            {
                "data": {
                    "access_token": "token-abc",
                    "refresh_token": "refresh-abc",
                    "expires_in": 900,
                    "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
                    "token_type": "bearer",
                }
            },
        )

    def get(self, url, params=None, headers=None, timeout=None):
        self.get_calls.append((url, params or {}))
        if self.fail_next_get_401:
            self.fail_next_get_401 = False
            return DummyResponse(401, {"error": "expired"})
        if url.endswith("/health"):
            return DummyResponse(200, {"data": {"status": "ok", "version": "1.0.0"}})
        if url.endswith("/screener"):
            return DummyResponse(
                200,
                {
                    "data": [
                        {
                            "instrument": {"symbol": "ggal", "name": "Grupo Galicia", "market": "bcba"},
                            "quotes": {"last": 100.0, "open": 98.0, "high": 101.0, "low": 97.0, "close": 99.0, "change_percent": 1.01, "volume": 1000},
                            "book": {"bid": {"price": 99.9}, "ask": {"price": 100.1}},
                        }
                    ]
                },
            )
        return DummyResponse(200, {"data": {"bars": []}})


def _client(tmp_path, token_status: int = 200) -> tuple[IOLClient, DummySession]:
    client = IOLClient(username="u", password="p", token_path=tmp_path / "tok.json")
    session = DummySession(token_status)
    client.session = session
    return client, session


def test_authenticate_is_cached(tmp_path):
    client, session = _client(tmp_path)
    token = client.authenticate()
    assert token == "token-abc"
    client.authenticate()
    assert session.token_calls == 1


def test_invalid_credentials_raise(tmp_path):
    client, _ = _client(tmp_path, token_status=401)
    with pytest.raises(IOLAuthError):
        client.authenticate()


def test_missing_credentials(tmp_path, monkeypatch):
    client = IOLClient(username="", password="", token_path=tmp_path / "tok.json")
    client.session = DummySession()
    with pytest.raises(IOLAuthError):
        client.authenticate()


def test_token_reused_after_reload(tmp_path):
    client, _ = _client(tmp_path)
    client.authenticate()
    second = IOLClient(username="u", password="p", token_path=tmp_path / "tok.json")
    session = DummySession()
    second.session = session
    second.authenticate()
    assert session.token_calls == 0


def test_screener_normalization(tmp_path):
    client, _ = _client(tmp_path)
    frame = client.screener("AR", "cedears", "general")
    assert list(frame.columns) >= ["symbol", "last", "change_percent", "volume"]
    assert frame.iloc[0]["symbol"] == "GGAL"
    assert frame.iloc[0]["change_percent"] == pytest.approx(1.01)
    assert frame.iloc[0]["bid"] == pytest.approx(99.9)


def test_change_percent_is_computed_when_missing(tmp_path):
    client, session = _client(tmp_path)

    def fake_get(url, params=None, headers=None, timeout=None):
        return DummyResponse(
            200,
            {"data": [{"instrument": {"symbol": "AAPL", "name": "Apple"}, "quotes": {"last": 110.0, "close": 100.0}}]},
        )

    session.get = fake_get  # type: ignore[assignment]
    frame = client.screener("AR", "cedears", "general")
    assert frame.iloc[0]["change_percent"] == pytest.approx(10.0)


def test_retry_after_401(tmp_path):
    client, session = _client(tmp_path)
    session.fail_next_get_401 = True
    data = client._get("/broker/market-data/screener", {"country": "AR"})
    assert data[0]["instrument"]["symbol"] == "ggal"
    assert session.token_calls == 2


def test_api_error_raises(tmp_path):
    client, session = _client(tmp_path)
    session.get = lambda *a, **k: DummyResponse(400, {"error": "bad request"})  # type: ignore[assignment]
    with pytest.raises(IOLAPIError):
        client._get("/broker/market-data/AAPL/quote")


def test_infer_ratio():
    ratio, error = infer_ratio(price_ars=2500, underlying_usd=50, ccl=1000)
    assert ratio == pytest.approx(20)
    assert error == pytest.approx(0.0)

    ratio2, error2 = infer_ratio(price_ars=2450, underlying_usd=50, ccl=1000)
    assert ratio2 == pytest.approx(20)
    assert error2 == pytest.approx(0.02, rel=0.05)

    assert infer_ratio(None, 50, 1000) == (None, None)
