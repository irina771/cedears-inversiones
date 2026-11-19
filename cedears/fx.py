"""Tipo de cambio CCL (Contado con Liquidación).

IOL no expone una cotización pública de CCL en su API REST v1 (solo el CCL
diario dentro del histórico de cartera). Para no inventar el dato se usa una
fuente pública complementaria, documentada en ``docs/DATOS.md``:

* ``dolarapi.com`` -> CCL actual.
* ``argentinadatos.com`` -> serie histórica diaria de CCL.

Ambas son gratuitas y se cachean localmente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

from . import storage
from .config import settings

CCL_KEY = "fx:ccl_current"
CCL_HISTORY_KEY = "fx:ccl_history"


@dataclass(frozen=True)
class FXQuote:
    value: float | None
    updated_at: datetime | None
    source: str
    stale: bool = False

    @property
    def label(self) -> str:
        if self.value is None:
            return "N/D"
        return f"${self.value:,.1f}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_ccl(force: bool = False) -> FXQuote:
    """CCL actual (venta). Devuelve N/D si la fuente falla y no hay caché."""
    if not force:
        cached = storage.load_json(CCL_KEY, ttl_seconds=settings.fx_ttl)
        if cached:
            payload, updated = cached
            return FXQuote(payload.get("value"), updated, payload.get("source", "dolarapi.com"))

    try:
        response = requests.get(settings.ccl_url, timeout=12)
        response.raise_for_status()
        payload = response.json()
        value = float(payload.get("venta") or payload.get("compra"))
        updated_raw = payload.get("fechaActualizacion") or payload.get("fecha")
        storage.save_json(CCL_KEY, {"value": value, "source": "dolarapi.com", "raw_date": updated_raw})
        return FXQuote(value, _now(), "dolarapi.com")
    except (requests.RequestException, ValueError, TypeError):
        cached = storage.load_json(CCL_KEY)
        if cached:
            payload, updated = cached
            return FXQuote(payload.get("value"), updated, "caché local", stale=True)
        return FXQuote(None, None, "sin datos", stale=True)


def get_ccl_history(force: bool = False) -> pd.DataFrame:
    """Serie diaria de CCL. Devuelve DataFrame(date, ccl) o vacío."""
    if not force:
        cached = storage.load_json(CCL_HISTORY_KEY, ttl_seconds=12 * 3600)
        if cached:
            frame = pd.DataFrame(cached[0])
            if not frame.empty:
                frame["date"] = pd.to_datetime(frame["date"])
                return frame

    try:
        response = requests.get(settings.ccl_history_url, timeout=15)
        response.raise_for_status()
        rows = response.json()
        frame = pd.DataFrame(rows)
        if frame.empty:
            return pd.DataFrame(columns=["date", "ccl"])
        frame["date"] = pd.to_datetime(frame["fecha"], errors="coerce")
        frame["ccl"] = pd.to_numeric(frame["venta"], errors="coerce")
        frame = frame.dropna(subset=["date", "ccl"])[["date", "ccl"]].sort_values("date")
        storage.save_json(CCL_HISTORY_KEY, frame.assign(date=frame["date"].dt.strftime("%Y-%m-%d")).to_dict("records"))
        return frame
    except (requests.RequestException, ValueError, KeyError):
        cached = storage.load_json(CCL_HISTORY_KEY)
        if cached:
            frame = pd.DataFrame(cached[0])
            if not frame.empty:
                frame["date"] = pd.to_datetime(frame["date"])
                return frame
        return pd.DataFrame(columns=["date", "ccl"])


def ccl_on(frame: pd.DataFrame, target: date | pd.Timestamp) -> float | None:
    """CCL más cercano hacia atrás para una fecha dada (último valor <= fecha)."""
    if frame is None or frame.empty:
        return None
    target_ts = pd.Timestamp(target)
    subset = frame[frame["date"] <= target_ts]
    if subset.empty:
        subset = frame.iloc[[0]]
    return float(subset["ccl"].iloc[-1])


def ccl_change(frame: pd.DataFrame, days: int = 7) -> float | None:
    """Variación porcentual del CCL en los últimos ``days`` días."""
    if frame is None or len(frame) < 2:
        return None
    last = frame.iloc[-1]
    cutoff = last["date"] - pd.Timedelta(days=days)
    previous = frame[frame["date"] <= cutoff]
    reference = previous.iloc[-1] if not previous.empty else frame.iloc[0]
    if not reference["ccl"]:
        return None
    return (last["ccl"] / reference["ccl"] - 1) * 100


def ccl_history_between(frame: pd.DataFrame, start: date, end: date | None = None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["date", "ccl"])
    end_ts = pd.Timestamp(end or date.today())
    mask = (frame["date"] >= pd.Timestamp(start) - timedelta(days=3)) & (frame["date"] <= end_ts)
    return frame[mask].copy()
