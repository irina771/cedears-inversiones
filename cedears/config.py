"""Configuración de la aplicación.

Todas las credenciales y parámetros sensibles se leen de variables de entorno
(archivo ``.env`` en la raíz del proyecto). Nunca se hardcodean en el código.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / ".cache"
CONFIG_DIR = ROOT / "config"

for directory in (DATA_DIR, CACHE_DIR, CONFIG_DIR):
    directory.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return default if value is None else value.strip()


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)) or default)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(_env(name, str(default)) or default))
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name, "1" if default else "0").lower()
    return raw in {"1", "true", "yes", "si", "sí", "on"}


@dataclass(frozen=True)
class Settings:
    """Parámetros de ejecución leídos del entorno."""

    username: str = _env("IOL_USERNAME")
    password: str = _env("IOL_PASSWORD")
    base_url: str = _env("IOL_BASE_URL", "https://api.iolinversiones.com").rstrip("/")

    # Descubrimiento de catálogos (se auto-detectan si quedan vacíos)
    asset_type_cedears: str = _env("IOL_ASSET_TYPE_CEDEARS")
    asset_type_stocks: str = _env("IOL_ASSET_TYPE_STOCKS")
    panel: str = _env("IOL_PANEL", "general")
    term: str = _env("IOL_TERM", "T0")

    # Caché
    snapshot_ttl: int = _env_int("CEDEARS_SNAPSHOT_TTL", 90)
    bars_ttl: int = _env_int("CEDEARS_BARS_TTL", 6 * 3600)
    fx_ttl: int = _env_int("CEDEARS_FX_TTL", 600)
    db_path: Path = CACHE_DIR / "cedears.sqlite3"
    token_path: Path = CACHE_DIR / "iol_token.json"

    # Fuentes complementarias (documentadas en docs/DATOS.md)
    ccl_url: str = _env("CCL_URL", "https://dolarapi.com/v1/dolares/contadoconliqui")
    ccl_history_url: str = _env(
        "CCL_HISTORY_URL",
        "https://api.argentinadatos.com/v1/cotizaciones/dolares/contadoconliqui",
    )

    request_timeout: float = _env_float("IOL_TIMEOUT", 20.0)
    max_workers: int = _env_int("CEDEARS_MAX_WORKERS", 6)
    sandbox: bool = _env_bool("CEDEARS_SANDBOX", False)

    universe_path: Path = DATA_DIR / "cedears_universe.csv"
    dividends_path: Path = DATA_DIR / "dividends.csv"

    @property
    def is_configured(self) -> bool:
        """True si hay credenciales de IOL disponibles."""
        return bool(self.username and self.password) or self.sandbox


settings = Settings()
