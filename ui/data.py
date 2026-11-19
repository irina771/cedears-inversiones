"""Capa de datos para la UI: caché de sesión, filtros y series históricas."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import streamlit as st

from cedears import sandbox, storage
from cedears.config import settings
from cedears.iol_client import IOLAuthError, IOLError
from cedears.market import Analysis, MarketDataService

CACHE_KEY = "analysis"


@st.cache_resource(show_spinner=False)
def get_service() -> MarketDataService:
    return MarketDataService()


def _fresh(analysis: Analysis, ttl: int) -> bool:
    age = (datetime.now(timezone.utc) - analysis.fetched_at).total_seconds()
    return age < ttl and not analysis.empty


def get_analysis(force: bool = False) -> Analysis | None:
    """Devuelve el análisis, usando caché de sesión y mostrando progreso."""
    if settings.sandbox:
        return sandbox.build_sandbox_analysis()

    cached: Analysis | None = st.session_state.get(CACHE_KEY)
    if cached is not None and not force and _fresh(cached, max(settings.snapshot_ttl, 60)):
        return cached

    service = get_service()
    with st.status("Conectando con IOL Inversiones…", expanded=False) as status:
        try:
            def progress(done: int, total: int, symbol: str) -> None:
                status.update(label=f"Descargando historial · {done}/{total} · {symbol}")

            analysis = service.analysis(force=force, progress=progress)
        except IOLAuthError as exc:
            status.update(label="Credenciales de IOL no válidas", state="error")
            st.session_state["iol_error"] = str(exc)
            return st.session_state.get(CACHE_KEY)
        except IOLError as exc:
            status.update(label="No se pudo actualizar", state="error")
            st.session_state["iol_error"] = str(exc)
            return st.session_state.get(CACHE_KEY)

        if analysis.empty:
            status.update(label="La API no devolvió cotizaciones", state="error")
            return analysis

        st.session_state[CACHE_KEY] = analysis
        status.update(label="Datos actualizados", state="complete")
        st.session_state.pop("iol_error", None)
    return analysis


def invalidate() -> None:
    st.session_state.pop(CACHE_KEY, None)


# ------------------------------------------------------------------- filtros
def apply_filters(frame: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Aplica los filtros del panel lateral."""
    if frame is None or frame.empty:
        return frame

    data = frame.copy()
    if filters.get("tickers"):
        data = data[data["symbol"].isin(filters["tickers"])]
    if filters.get("companies"):
        data = data[data["company"].isin(filters["companies"])]
    if filters.get("sectors"):
        data = data[data["sector"].isin(filters["sectors"])]
    if filters.get("types"):
        data = data[data["type"].isin(filters["types"])]
    if filters.get("trends"):
        data = data[data["tendencia"].isin(filters["trends"])]
    if filters.get("classifications"):
        data = data[data["clasificacion"].isin(filters["classifications"])]

    var_min, var_max = filters.get("var_range", (-100.0, 100.0))
    data = data[data["variacion_diaria"].between(var_min, var_max) | data["variacion_diaria"].isna()]

    min_volume = filters.get("min_volume", 0) or 0
    if min_volume:
        data = data[data["monto_ars"].fillna(0) >= min_volume]

    return data.reset_index(drop=True)


# ------------------------------------------------------------------ histórico
def history_frame(symbols: list[str], start: date, end: date | None = None) -> pd.DataFrame:
    """Serie larga (date, symbol, value) desde la caché de barras o el sandbox."""
    end = end or date.today()
    frames: list[pd.DataFrame] = []
    for symbol in symbols:
        if settings.sandbox:
            bars = sandbox.bars_for(symbol)
        else:
            bars = storage.load_bars(symbol, "BCBA")
        if bars is None or bars.empty:
            continue
        subset = bars[(bars["date"] >= pd.Timestamp(start)) & (bars["date"] <= pd.Timestamp(end))]
        if subset.empty:
            continue
        frames.append(
            pd.DataFrame(
                {
                    "date": subset["date"].values,
                    "symbol": symbol,
                    "value": subset["close"].astype(float).values,
                    "volume": subset["volume"].values,
                }
            )
        )
    if not frames:
        return pd.DataFrame(columns=["date", "symbol", "value", "volume"])
    return pd.concat(frames, ignore_index=True)


def last_price_before(symbol: str, target: date) -> tuple[float | None, pd.Timestamp | None]:
    """Último cierre disponible en o antes de ``target`` (sin inventar datos)."""
    if settings.sandbox:
        bars = sandbox.bars_for(symbol)
    else:
        bars = storage.load_bars(symbol, "BCBA")
    if bars is None or bars.empty:
        return None, None
    subset = bars[bars["date"] <= pd.Timestamp(target)]
    if subset.empty:
        return None, None
    row = subset.iloc[-1]
    return float(row["close"]), pd.Timestamp(row["date"])


def period_start(period: str, end: date | None = None) -> date:
    end = end or date.today()
    mapping = {
        "7 días": timedelta(days=7),
        "1 mes": timedelta(days=30),
        "5 meses": timedelta(days=152),
        "1 año": timedelta(days=365),
        "5 años": timedelta(days=365 * 5),
    }
    return end - mapping.get(period, timedelta(days=365))


def history_available(symbol: str) -> int:
    if settings.sandbox:
        bars = sandbox.bars_for(symbol)
    else:
        bars = storage.load_bars(symbol, "BCBA")
    return 0 if bars is None else len(bars)
