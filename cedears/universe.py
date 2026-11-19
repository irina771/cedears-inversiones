"""Catálogo de instrumentos (CEDEARs y acciones argentinas) y su enriquecimiento."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import settings

REQUIRED_COLUMNS = [
    "symbol",
    "company",
    "type",
    "underlying",
    "underlying_market",
    "sector",
    "ratio",
    "ratio_source",
    "notes",
]

SECTOR_ORDER = [
    "Tecnología",
    "Comunicaciones",
    "Consumo",
    "Salud",
    "Energía",
    "Bancos y finanzas",
    "Industria",
    "Materiales",
    "Agro",
    "Inmobiliario",
    "Servicios públicos",
    "ETF / Índices",
    "Otros",
]


def load_universe(path: Path | None = None) -> pd.DataFrame:
    """Lee ``data/cedears_universe.csv`` (editable por el usuario)."""
    path = path or settings.universe_path
    if not path.exists():
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    frame = pd.read_csv(path, dtype=str).fillna("")
    for column in REQUIRED_COLUMNS:
        if column not in frame:
            frame[column] = ""
    frame["symbol"] = frame["symbol"].str.upper().str.strip()
    frame["ratio"] = pd.to_numeric(frame["ratio"], errors="coerce")
    frame = frame.drop_duplicates(subset="symbol", keep="first")
    return frame


def attach_universe(snapshot: pd.DataFrame, universe: pd.DataFrame | None = None) -> pd.DataFrame:
    """Agrega empresa, tipo de activo, sector y ratio a un snapshot de mercado.

    Los símbolos que no están en el catálogo se mantienen con sector ``Otros``
    y sin ratio (se muestra N/D, nunca un valor inventado).
    """
    if snapshot is None or snapshot.empty:
        return pd.DataFrame(columns=["symbol", "company", "type", "sector", "ratio"])

    frame = snapshot.copy()
    universe = load_universe() if universe is None else universe

    if universe.empty:
        frame["company"] = frame.get("name", "")
        frame["type"] = "CEDEAR"
        frame["sector"] = "Otros"
        frame["ratio"] = pd.NA
        frame["underlying"] = ""
        frame["underlying_market"] = ""
        return frame

    merged = frame.drop(
        columns=[c for c in ("company", "type", "underlying", "underlying_market", "sector", "ratio") if c in frame.columns]
    ).merge(
        universe[["symbol", "company", "type", "underlying", "underlying_market", "sector", "ratio"]],
        on="symbol",
        how="left",
    )
    merged["company"] = merged["company"].fillna("")
    merged["name"] = merged.get("name", "").fillna("")
    empty_company = merged["company"].str.len() == 0
    merged.loc[empty_company, "company"] = merged.loc[empty_company, "name"]
    merged["type"] = merged["type"].fillna("").replace("", "CEDEAR")
    merged["sector"] = merged["sector"].fillna("").replace("", "Otros")
    merged["underlying"] = merged["underlying"].fillna("")
    merged["underlying_market"] = merged["underlying_market"].fillna("")
    return merged


def sectors_in(frame: pd.DataFrame) -> list[str]:
    """Sectores presentes ordenados según el orden canónico del catálogo."""
    if frame is None or frame.empty or "sector" not in frame:
        return []
    present = set(frame["sector"].dropna().unique())
    ordered = [s for s in SECTOR_ORDER if s in present]
    return ordered + sorted(present - set(ordered))
