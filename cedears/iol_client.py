"""Cliente de la API de IOL Inversiones (REST v1).

Documentación oficial: https://developers.iolinversiones.com
Base: https://api.iolinversiones.com

Autenticación: OAuth 2.0 password grant -> ``access_token`` JWT de 15 minutos.
Se cachea en disco y se renueva automáticamente con el ``refresh_token``.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import requests

from .config import settings

logger = logging.getLogger(__name__)

# Ratios estándar de CEDEARs (BYMA): se usan para validar/inferir ratios.
STANDARD_RATIOS = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 16, 18, 20, 24, 25, 30, 36, 40, 50, 60, 75, 100]


class IOLError(Exception):
    """Error genérico de la integración con IOL."""


class IOLAuthError(IOLError):
    """Credenciales inválidas o token no renovable."""


class IOLAPIError(IOLError):
    """La API respondió con un error de negocio o de red."""

    def __init__(self, message: str, status: int | None = None, path: str | None = None):
        super().__init__(message)
        self.status = status
        self.path = path


class IOLClient:
    """Cliente HTTP con manejo de token, reintentos y *rate limiting* suave."""

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        token_path=None,
    ) -> None:
        self.username = username or settings.username
        self.password = password or settings.password
        self.base_url = (base_url or settings.base_url).rstrip("/")
        self.timeout = timeout or settings.request_timeout
        self.token_path = token_path or settings.token_path
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "cedears-inversiones/1.0 (+https://github.com/irina771/cedears-inversiones)",
            }
        )
        self._token: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._load_token()

    # ------------------------------------------------------------------ token
    def _load_token(self) -> None:
        try:
            if self.token_path.exists():
                self._token = json.loads(self.token_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._token = {}

    def _save_token(self, payload: dict[str, Any]) -> None:
        self._token = payload
        try:
            self.token_path.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:  # no es crítico: el token también vive en memoria
            logger.debug("No se pudo persistir el token en disco")

    @property
    def token_expires_at(self) -> datetime | None:
        raw = self._token.get("expires_at")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None

    def _token_is_valid(self, margin: int = 90) -> bool:
        expires = self.token_expires_at
        if not self._token.get("access_token") or expiry_missing(expires):
            return False
        return expires - timedelta(seconds=margin) > datetime.now(timezone.utc)

    def _request_token(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/auth/token", json=payload, timeout=self.timeout
        )
        if response.status_code == 401:
            raise IOLAuthError("Credenciales de IOL rechazadas (401). Revisá IOL_USERNAME / IOL_PASSWORD.")
        if response.status_code >= 400:
            raise IOLAuthError(f"No se pudo obtener token: HTTP {response.status_code} {response.text[:200]}")
        body = response.json()
        data = body.get("data") or {}
        if not data.get("access_token"):
            raise IOLAuthError(f"Respuesta de autenticación inesperada: {str(body)[:200]}")
        if not data.get("expires_at"):
            data["expires_at"] = (
                datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 900)))
            ).isoformat(timespec="seconds")
        self._save_token(data)
        return data

    def authenticate(self, force: bool = False) -> str:
        """Devuelve un access_token válido, renovándolo si es necesario."""
        with self._lock:
            if not force and self._token_is_valid():
                return self._token["access_token"]

            refresh = self._token.get("refresh_token")
            if refresh and not force:
                try:
                    self._request_token({"grant_type": "refresh_token", "refresh_token": refresh})
                    return self._token["access_token"]
                except IOLError as exc:
                    logger.info("Refresh token inválido (%s); se reintenta con usuario/clave", exc)

            if not (self.username and self.password):
                raise IOLAuthError(
                    "Faltan credenciales. Configurá IOL_USERNAME e IOL_PASSWORD en el archivo .env "
                    "(ver .env.example)."
                )
            self._request_token(
                {"grant_type": "password", "username": self.username, "password": self.password}
            )
            return self._token["access_token"]

    # ---------------------------------------------------------------- requests
    def _get(self, path: str, params: dict[str, Any] | None = None, retries: int = 2) -> Any:
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            token = self.authenticate(force=attempt > 0)
            try:
                response = self.session.get(
                    f"{self.base_url}{path}",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_error = IOLAPIError(f"Error de red en {path}: {exc}", path=path)
                time.sleep(0.6 * (attempt + 1))
                continue

            if response.status_code == 401 and attempt < retries:
                continue  # token vencido: reintenta con login nuevo
            if response.status_code == 429 or response.status_code >= 500:
                last_error = IOLAPIError(
                    f"{path} respondió HTTP {response.status_code}", response.status_code, path
                )
                time.sleep(0.8 * (attempt + 1))
                continue
            if response.status_code >= 400:
                raise IOLAPIError(
                    f"{path} respondió HTTP {response.status_code}: {response.text[:300]}",
                    response.status_code,
                    path,
                )
            try:
                body = response.json()
            except ValueError as exc:
                raise IOLAPIError(f"Respuesta no JSON en {path}", response.status_code, path) from exc
            if body.get("error"):
                raise IOLAPIError(f"{path}: {body['error']}", response.status_code, path)
            return body.get("data")

        raise last_error or IOLAPIError(f"No se pudo completar {path}", path=path)

    # ---------------------------------------------------------------- endpoints
    def health(self) -> dict[str, Any]:
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
            return response.json().get("data", {})
        except requests.RequestException as exc:
            raise IOLAPIError(f"API inaccesible: {exc}", path="/health") from exc

    def asset_types(self, country: str = "AR") -> list[dict[str, str]]:
        return self._get("/broker/assets/types", {"country": country}) or []

    def panels(self, country: str = "AR", asset_type: str = "") -> list[dict[str, str]]:
        return self._get("/broker/assets/panels", {"country": country, "asset_type": asset_type}) or []

    def screener(self, country: str, asset_type: str, panel: str, term: str | None = None) -> pd.DataFrame:
        data = self._get(
            "/broker/market-data/screener",
            {"country": country, "asset_type": asset_type, "panel": panel, "term": term or settings.term},
        )
        return _screener_to_frame(data or [])

    def quote(self, symbol: str, market: str = "BCBA", term: str | None = None) -> dict[str, Any]:
        return self._get(
            f"/broker/market-data/{symbol}/quote",
            {"market": market, "term": term or settings.term},
        ) or {}

    def bars(self, symbol: str, market: str, date_from: str, date_to: str) -> pd.DataFrame:
        """Barras diarias OHLCV. Formato de fechas: ``yyyy-MM-dd HH:mm:ss``."""
        data = self._get(
            f"/broker/market-data/{symbol}/bars",
            {"market": market, "from": date_from, "to": date_to},
        ) or {}
        rows = data.get("bars") or []
        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        if "datetime" in frame:
            frame["date"] = pd.to_datetime(frame["datetime"], errors="coerce", utc=True).dt.tz_convert(None)
        elif "timestamp" in frame:
            frame["date"] = pd.to_datetime(frame["timestamp"], unit="s", errors="coerce")
        frame = frame.dropna(subset=["date"]).sort_values("date")
        for column in ("open", "high", "low", "close", "volume"):
            if column not in frame:
                frame[column] = None
        return frame[["date", "open", "high", "low", "close", "volume"]].reset_index(drop=True)


def expiry_missing(expires: datetime | None) -> bool:
    """True si no hay fecha de expiración utilizable."""
    if expires is None:
        return True
    if expires.tzinfo is None:
        return False
    return expires <= datetime.now(timezone.utc)


def _screener_to_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Normaliza la respuesta del screener a un DataFrame plano."""
    records: list[dict[str, Any]] = []
    for item in rows:
        instrument = item.get("instrument") or {}
        quotes = item.get("quotes") or {}
        if not instrument.get("symbol"):
            continue
        last = _f(quotes.get("last"))
        close = _f(quotes.get("close"))
        change = _f(quotes.get("change_percent"))
        if change is None and last is not None and close:
            change = (last / close - 1) * 100
        records.append(
            {
                "symbol": str(instrument["symbol"]).upper(),
                "name": instrument.get("name") or "",
                "market": (instrument.get("market") or "").upper(),
                "currency": instrument.get("currency") or "",
                "last": last,
                "open": _f(quotes.get("open")),
                "high": _f(quotes.get("high")),
                "low": _f(quotes.get("low")),
                "previous_close": close,
                "change_percent": change,
                "volume": _f(quotes.get("volume")),
                "bid": _f((item.get("book") or {}).get("bid", {}).get("price")),
                "ask": _f((item.get("book") or {}).get("ask", {}).get("price")),
            }
        )
    frame = pd.DataFrame.from_records(records)
    if not frame.empty:
        frame = frame.drop_duplicates(subset="symbol", keep="last").reset_index(drop=True)
    return frame


def _f(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        number = float(value)
        return number if pd.notna(number) else None
    except (TypeError, ValueError):
        return None


def infer_ratio(price_ars: float | None, underlying_usd: float | None, ccl: float | None) -> tuple[float | None, float | None]:
    """Infiere el ratio de conversión a partir de precios reales.

    ratio = precio_subyacente_USD * CCL / precio_CEDEAR_ARS

    Devuelve (ratio_redondeado, error_relativo). El error relativo mide qué tan
    lejos está el ratio observado del ratio estándar más cercano (0.05 = 5%).
    """
    if not price_ars or not underlying_usd or not ccl or price_ars <= 0:
        return None, None
    observed = underlying_usd * ccl / price_ars
    if observed <= 0:
        return None, None
    best = min(STANDARD_RATIOS, key=lambda r: abs(r - observed) / r)
    error = abs(best - observed) / best
    return float(best), float(error)
