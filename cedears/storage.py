"""Caché local en SQLite.

Se usa para no golpear la API en cada interacción del dashboard y para poder
mostrar datos con su fecha real de actualización cuando la API no responde.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .config import settings

_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bars (
    symbol TEXT NOT NULL,
    market TEXT NOT NULL,
    date   TEXT NOT NULL,
    open   REAL,
    high   REAL,
    low    REAL,
    close  REAL,
    volume REAL,
    PRIMARY KEY (symbol, market, date)
);
CREATE TABLE IF NOT EXISTS kv (
    key        TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _LOCK, _connect() as conn:
        conn.executescript(_SCHEMA)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def save_json(key: str, payload: Any) -> None:
    init_db()
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO kv(key, payload, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
            (key, json.dumps(payload, ensure_ascii=False), _iso(utcnow())),
        )


def load_json(key: str, ttl_seconds: int | None = None) -> tuple[Any, datetime] | None:
    """Devuelve (payload, updated_at) o None si no existe o expiró."""
    init_db()
    with _LOCK, _connect() as conn:
        row = conn.execute("SELECT payload, updated_at FROM kv WHERE key=?", (key,)).fetchone()
    if not row:
        return None
    updated_at = datetime.fromisoformat(row[1])
    if ttl_seconds is not None:
        age = (utcnow() - updated_at).total_seconds()
        if age > ttl_seconds:
            return None
    try:
        return json.loads(row[0]), updated_at
    except json.JSONDecodeError:
        return None


def delete_key(key: str) -> None:
    init_db()
    with _LOCK, _connect() as conn:
        conn.execute("DELETE FROM kv WHERE key=?", (key,))


def save_bars(symbol: str, market: str, bars: pd.DataFrame) -> None:
    """Guarda barras diarias OHLCV (idempotente)."""
    if bars is None or bars.empty:
        return
    init_db()
    frame = bars.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    rows = [
        (
            symbol.upper(),
            market.upper(),
            row.date,
            _num(row.open),
            _num(row.high),
            _num(row.low),
            _num(row.close),
            _num(row.volume),
        )
        for row in frame.itertuples(index=False)
    ]
    with _LOCK, _connect() as conn:
        conn.executemany(
            "INSERT INTO bars(symbol, market, date, open, high, low, close, volume) "
            "VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(symbol, market, date) DO UPDATE SET "
            "open=excluded.open, high=excluded.high, low=excluded.low, "
            "close=excluded.close, volume=excluded.volume",
            rows,
        )


def _num(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def load_bars(symbol: str, market: str, start: str | None = None) -> pd.DataFrame:
    init_db()
    query = "SELECT date, open, high, low, close, volume FROM bars WHERE symbol=? AND market=?"
    params: list[Any] = [symbol.upper(), market.upper()]
    if start:
        query += " AND date>=?"
        params.append(start)
    query += " ORDER BY date"
    with _LOCK, _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    frame = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    if not frame.empty:
        frame["date"] = pd.to_datetime(frame["date"])
    return frame


def bars_updated_at(symbol: str, market: str) -> datetime | None:
    frame = load_bars(symbol, market)
    if frame.empty:
        return None
    return frame["date"].max().to_pydatetime().replace(tzinfo=timezone.utc)


def clear_cache(prefix: str | None = None) -> None:
    """Borra caché. Si se indica prefix, solo las claves kv que empiezan igual."""
    init_db()
    with _LOCK, _connect() as conn:
        if prefix:
            conn.execute("DELETE FROM kv WHERE key LIKE ?", (prefix + "%",))
            conn.execute("DELETE FROM bars WHERE symbol LIKE ?", (prefix + "%",))
        else:
            conn.execute("DELETE FROM kv")
            conn.execute("DELETE FROM bars")


def cache_stats() -> dict[str, Any]:
    init_db()
    with _LOCK, _connect() as conn:
        kv = conn.execute("SELECT COUNT(*) FROM kv").fetchone()[0]
        bars = conn.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
        symbols = conn.execute("SELECT COUNT(DISTINCT symbol) FROM bars").fetchone()[0]
        last = conn.execute("SELECT MAX(updated_at) FROM kv").fetchone()[0]
    return {"kv_entries": kv, "bar_rows": bars, "symbols": symbols, "last_update": last}


def db_size_bytes() -> int:
    path = Path(settings.db_path)
    return path.stat().st_size if path.exists() else 0
