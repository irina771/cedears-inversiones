"""Modo sandbox: datos sintéticos para probar la interfaz sin credenciales.

IMPORTANTE: estos datos **no son cotizaciones reales**. Se generan con una
semilla fija y solo se habilitan definiendo ``CEDEARS_SANDBOX=1``. La UI los
marca con un banner rojo y la fuente figura como "Sandbox".
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

from . import market
from .fx import FXQuote
from .iol_client import STANDARD_RATIOS
from .universe import load_universe

SANDBOX_WARNING = (
    "MODO SANDBOX: las cifras son SINTÉTICAS, generadas solo para probar la interfaz. "
    "No son cotizaciones reales ni deben usarse para decidir inversiones."
)

_BARS: dict[str, pd.DataFrame] = {}
_CACHE: market.Analysis | None = None


def _business_days(years: int = 5) -> pd.DatetimeIndex:
    end = pd.Timestamp(date.today())
    start = end - pd.Timedelta(days=365 * years)
    return pd.bdate_range(start, end)


def _series(rng: np.random.Generator, dates: pd.DatetimeIndex, start_price: float, drift: float, vol: float) -> pd.DataFrame:
    steps = len(dates)
    shocks = rng.normal(drift, vol, steps)
    prices = start_price * np.exp(np.cumsum(shocks))
    highs = prices * (1 + np.abs(rng.normal(0, 0.006, steps)))
    lows = prices * (1 - np.abs(rng.normal(0, 0.006, steps)))
    opens = prices * (1 + rng.normal(0, 0.003, steps))
    volumes = rng.lognormal(mean=13, sigma=0.5, size=steps)
    return pd.DataFrame(
        {
            "date": dates,
            "open": np.round(opens, 2),
            "high": np.round(np.maximum.reduce([opens, prices, highs]), 2),
            "low": np.round(np.minimum.reduce([opens, prices, lows]), 2),
            "close": np.round(prices, 2),
            "volume": np.round(volumes, 0),
        }
    )


def _build() -> tuple[pd.DataFrame, pd.DataFrame, float, pd.DataFrame]:
    global _BARS
    rng = np.random.default_rng(20261119)
    universe = load_universe()
    if universe.empty:
        return pd.DataFrame(), pd.DataFrame(), 1500.0, pd.DataFrame()

    cedears = universe[universe["type"] == "CEDEAR"].head(48)
    acciones = universe[universe["type"] == "Acción"].head(10)
    selected = pd.concat([cedears, acciones], ignore_index=True)

    dates = _business_days(5)
    ccl_base = 1450.0
    ccl_series = ccl_base * np.exp(np.cumsum(rng.normal(0.0009, 0.004, len(dates))))
    ccl_frame = pd.DataFrame({"date": dates, "ccl": np.round(ccl_series, 2)})
    ccl_now = float(ccl_frame["ccl"].iloc[-1])

    rows: list[dict] = []
    _BARS = {}
    for _, item in selected.iterrows():
        symbol = item["symbol"]
        ratio = float(rng.choice(STANDARD_RATIOS[3:12]))
        start_price = float(rng.uniform(400, 18000))
        bars = _series(rng, dates, start_price, drift=rng.normal(0.0004, 0.0008), vol=rng.uniform(0.012, 0.038))
        _BARS[symbol] = bars

        today = bars.iloc[-1]
        prev = bars.iloc[-2]
        last = float(today["close"])
        change = (last / float(prev["close"]) - 1) * 100
        rows.append(
            {
                "symbol": symbol,
                "name": item["company"],
                "market": "BCBA",
                "currency": "ARS",
                "last": last,
                "open": float(today["open"]),
                "high": float(today["high"]),
                "low": float(today["low"]),
                "previous_close": float(prev["close"]),
                "change_percent": change,
                "volume": float(today["volume"]),
                "bid": last * 0.999,
                "ask": last * 1.001,
                "underlying": item["underlying"],
                "ratio_sandbox": ratio,
            }
        )

    snapshot = pd.DataFrame(rows)
    us_rows = []
    for row in snapshot.itertuples():
        if not row.underlying:
            continue
        us_price = row.last * row.ratio_sandbox / ccl_now
        us_rows.append(
            {
                "symbol": row.underlying,
                "name": row.name,
                "last": round(us_price, 2),
                "change_percent": round(float(rng.normal(0, 1.4)), 2),
            }
        )
    return snapshot, pd.DataFrame(us_rows), ccl_now, ccl_frame


def bars_for(symbol: str) -> pd.DataFrame:
    return _BARS.get(symbol, pd.DataFrame())


def build_sandbox_analysis() -> market.Analysis:
    """Construye un Analysis sintético con la misma estructura que el real."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    snapshot, us, ccl_value, ccl_frame = _build()
    quote = FXQuote(ccl_value, datetime.now(timezone.utc), "sandbox")
    frame = market.enrich_snapshot(snapshot, bars_for=bars_for, us=us, ccl_quote=quote)

    _CACHE = market.Analysis(
        frame=frame,
        fetched_at=datetime.now(timezone.utc),
        source="Sandbox (datos sintéticos)",
        stale=False,
        warnings=[SANDBOX_WARNING],
        ccl=quote,
        ccl_history=ccl_frame,
        us_prices=us,
    )
    return _CACHE


def reset() -> None:
    global _CACHE, _BARS
    _CACHE = None
    _BARS = {}
