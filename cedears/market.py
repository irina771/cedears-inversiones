"""Servicio de datos de mercado: IOL + caché + métricas.

Es la única capa que habla con la API. El resto de la aplicación consume un
``Analysis`` (DataFrame enriquecido + metadatos de frescura).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Iterable

import numpy as np
import pandas as pd

from . import fx, metrics, signals, storage
from .config import settings
from .iol_client import IOLAuthError, IOLClient, IOLError
from .universe import attach_universe, load_universe

logger = logging.getLogger(__name__)

CATALOG_KEY = "iol:catalog"
SNAPSHOT_KEY = "iol:snapshot"
BARS_FETCH_KEY = "iol:bars_ts"

ProgressFn = Callable[[int, int, str], None]


@dataclass
class Analysis:
    """Resultado listo para la UI."""

    frame: pd.DataFrame
    fetched_at: datetime
    source: str = "IOL API"
    stale: bool = False
    warnings: list[str] = field(default_factory=list)
    ccl: fx.FXQuote | None = None
    ccl_history: pd.DataFrame = field(default_factory=pd.DataFrame)
    us_prices: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def empty(self) -> bool:
        return self.frame is None or self.frame.empty


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MarketDataService:
    """Orquesta descarga, caché y cálculo de métricas."""

    def __init__(self, client: IOLClient | None = None) -> None:
        self._client = client
        self._warnings: list[str] = []

    # ------------------------------------------------------------------ client
    @property
    def client(self) -> IOLClient:
        if self._client is None:
            self._client = IOLClient()
        return self._client

    # -------------------------------------------------------------- discovery
    def _pick_type(self, types: list[dict[str, str]], kind: str) -> str:
        """Busca el id de tipo de asset que corresponda a ``kind``."""
        needles = {
            "cedears": ("cedear",),
            "stocks": ("accion", "stock", "equity"),
            "ce": ("cedear",),
        }[kind]
        for item in types:
            text = f"{item.get('id','')} {item.get('name','')}".lower()
            if any(needle in text for needle in needles):
                return str(item.get("id"))
        return ""

    def catalog(self, force: bool = False) -> dict[str, str]:
        """Descubre tipos de asset y paneles disponibles (cacheado 24 h)."""
        if not force:
            cached = storage.load_json(CATALOG_KEY, ttl_seconds=24 * 3600)
            if cached:
                return cached[0]

        catalog: dict[str, str] = {
            "cedears_type": settings.asset_type_cedears,
            "stocks_type": settings.asset_type_stocks,
            "us_type": "",
            "cedears_panel": settings.panel,
            "stocks_panel": settings.panel,
            "us_panel": "",
            "types": "",
        }
        try:
            types_ar = self.client.asset_types("AR")
            catalog["types"] = ", ".join(f"{t.get('id')}={t.get('name')}" for t in types_ar)
            if not catalog["cedears_type"]:
                catalog["cedears_type"] = self._pick_type(types_ar, "cedears") or "cedears"
            if not catalog["stocks_type"]:
                catalog["stocks_type"] = self._pick_type(types_ar, "stocks") or "acciones"
            try:
                panels = self.client.panels("AR", catalog["cedears_type"])
                ids = [str(p.get("id")) for p in panels if p.get("id")]
                if ids:
                    preferred = [p for p in ids if p.lower() in {"general", "panel_general", "todos"}]
                    catalog["cedears_panel"] = (preferred or ids)[0]
                    catalog["stocks_panel"] = catalog["cedears_panel"]
                    catalog["panels"] = ", ".join(ids)
            except IOLError as exc:
                logger.info("No se pudieron listar paneles: %s", exc)

            try:
                types_us = self.client.asset_types("US")
                catalog["us_type"] = self._pick_type(types_us, "stocks")
                if catalog["us_type"]:
                    panels_us = self.client.panels("US", catalog["us_type"])
                    ids_us = [str(p.get("id")) for p in panels_us if p.get("id")]
                    if ids_us:
                        catalog["us_panel"] = ids_us[0]
            except IOLError as exc:
                logger.info("No se pudo descubrir el catálogo US: %s", exc)
        except IOLAuthError:
            raise
        except IOLError as exc:
            self._warnings.append(f"No se pudo descubrir el catálogo de IOL: {exc}")

        storage.save_json(CATALOG_KEY, catalog)
        return catalog

    # ---------------------------------------------------------------- snapshot
    def _fetch_screener(self, country: str, asset_type: str, panel: str) -> pd.DataFrame:
        frame = self.client.screener(country, asset_type, panel)
        if frame.empty:
            return frame
        frame = frame.copy()
        frame["market"] = frame["market"].replace("", np.nan)
        return frame

    def snapshot(self, force: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, datetime, bool]:
        """Cotizaciones actuales: (cedears AR, acciones AR, subyacentes US, fecha, stale)."""
        if not force:
            cached = storage.load_json(SNAPSHOT_KEY, ttl_seconds=settings.snapshot_ttl)
            if cached:
                payload, updated = cached
                return (
                    pd.DataFrame(payload.get("cedears", [])),
                    pd.DataFrame(payload.get("stocks", [])),
                    pd.DataFrame(payload.get("us", [])),
                    updated,
                    False,
                )

        catalog = self.catalog()
        warnings: list[str] = []
        try:
            cedears = self._fetch_screener("AR", catalog["cedears_type"], catalog["cedears_panel"])
        except IOLError as exc:
            cedears = pd.DataFrame()
            warnings.append(f"No se pudo obtener el screener de CEDEARs: {exc}")

        try:
            stocks = self._fetch_screener("AR", catalog["stocks_type"], catalog["stocks_panel"])
        except IOLError as exc:
            stocks = pd.DataFrame()
            warnings.append(f"No se pudo obtener el screener de acciones: {exc}")

        us = pd.DataFrame()
        if catalog.get("us_type"):
            try:
                us = self._fetch_screener("US", catalog["us_type"], catalog.get("us_panel") or "general")
            except IOLError as exc:
                warnings.append(f"No se pudo obtener el screener de EE.UU.: {exc}")

        if cedears.empty and stocks.empty:
            cached = storage.load_json(SNAPSHOT_KEY)
            if cached:
                payload, updated = cached
                self._warnings.extend(warnings)
                self._warnings.append(
                    f"Se muestran las últimas cotizaciones guardadas ({updated.astimezone().strftime('%d/%m/%Y %H:%M')})."
                )
                return (
                    pd.DataFrame(payload.get("cedears", [])),
                    pd.DataFrame(payload.get("stocks", [])),
                    pd.DataFrame(payload.get("us", [])),
                    updated,
                    True,
                )
            raise IOLError("; ".join(warnings) or "Sin datos de mercado")

        self._warnings.extend(warnings)
        payload = {
            "cedears": _records(cedears),
            "stocks": _records(stocks),
            "us": _records(us),
        }
        storage.save_json(SNAPSHOT_KEY, payload)
        return cedears, stocks, us, _now(), False

    # -------------------------------------------------------------------- bars
    def get_bars(self, symbol: str, market: str = "BCBA", days: int = 1500, force: bool = False, refresh_hours: float | None = None) -> pd.DataFrame:
        """Barras diarias con caché en SQLite."""
        key = f"{BARS_FETCH_KEY}:{market}:{symbol}"
        ttl_hours = settings.bars_ttl if refresh_hours is None else refresh_hours * 3600
        cached_meta = storage.load_json(key)
        fresh = bool(cached_meta and (_now() - cached_meta[1]).total_seconds() < ttl_hours)
        if not force and fresh:
            frame = storage.load_bars(symbol, market)
            if not frame.empty:
                return frame

        start = date.today() - timedelta(days=days)
        try:
            frame = self.client.bars(
                symbol, market, f"{start.isoformat()} 00:00:00", f"{date.today().isoformat()} 23:59:59"
            )
        except IOLError as exc:
            logger.info("Sin barras para %s: %s", symbol, exc)
            frame = pd.DataFrame()

        if not frame.empty:
            storage.save_bars(symbol, market, frame)
            storage.save_json(key, {"fetched": _now().isoformat()})
        else:
            storage.save_json(key, {"fetched": _now().isoformat(), "empty": True})
        return storage.load_bars(symbol, market)

    def warm_history(self, symbols: Iterable[str], market: str = "BCBA", days: int = 1500, progress: ProgressFn | None = None, force: bool = False) -> dict[str, int]:
        """Descarga barras en paralelo. Devuelve {symbol: cantidad de barras}."""
        symbols = [s for s in dict.fromkeys(symbols) if s]
        results: dict[str, int] = {}
        total = len(symbols)
        if not total:
            return results
        with ThreadPoolExecutor(max_workers=max(1, settings.max_workers)) as pool:
            futures = {pool.submit(self.get_bars, symbol, market, days, force): symbol for symbol in symbols}
            for done, future in enumerate(as_completed(futures), start=1):
                symbol = futures[future]
                try:
                    results[symbol] = len(future.result())
                except Exception as exc:  # noqa: BLE001 - una barra rota no debe romper todo
                    logger.warning("Error historial %s: %s", symbol, exc)
                    results[symbol] = 0
                if progress:
                    progress(done, total, symbol)
        return results

    # ---------------------------------------------------------------- analysis
    def analysis(
        self,
        force: bool = False,
        progress: ProgressFn | None = None,
        max_symbols: int = 0,
        include_us: bool = True,
    ) -> Analysis:
        """Construye el DataFrame analítico completo."""
        self._warnings = []
        cedears, stocks, us, fetched_at, stale = self.snapshot(force=force)

        frames = [f for f in (cedears, stocks) if f is not None and not f.empty]
        if not frames:
            return Analysis(pd.DataFrame(), fetched_at, stale=stale, warnings=list(self._warnings))

        snapshot = pd.concat(frames, ignore_index=True).drop_duplicates(subset="symbol", keep="first")
        if max_symbols and len(snapshot) > max_symbols:
            snapshot = snapshot.sort_values("volume", ascending=False).head(max_symbols).copy()

        self.warm_history(snapshot["symbol"].tolist(), progress=progress, force=False)

        ccl_quote = fx.get_ccl(force=force)
        ccl_hist = fx.get_ccl_history(force=force)
        frame = enrich_snapshot(
            snapshot,
            bars_for=lambda symbol: storage.load_bars(symbol, "BCBA"),
            us=us if include_us else None,
            ccl_quote=ccl_quote,
        )

        return Analysis(
            frame=frame,
            fetched_at=fetched_at,
            source="IOL API v1",
            stale=stale,
            warnings=list(self._warnings),
            ccl=ccl_quote,
            ccl_history=ccl_hist,
            us_prices=us,
        )


def _records(frame: pd.DataFrame | None) -> list[dict]:
    if frame is None or frame.empty:
        return []
    clean = frame.replace({np.nan: None})
    return clean.to_dict("records")


def enrich_snapshot(
    snapshot: pd.DataFrame,
    bars_for: Callable[[str], pd.DataFrame],
    us: pd.DataFrame | None = None,
    ccl_quote: fx.FXQuote | None = None,
) -> pd.DataFrame:
    """Agrega universo, métricas diarias, históricas, score y señales.

    ``bars_for`` permite inyectar el origen de las barras (caché real o
    sandbox), de modo que la lógica de cálculo sea idéntica en ambos casos.
    """
    if snapshot is None or snapshot.empty:
        return pd.DataFrame()

    frame = attach_universe(snapshot)
    frame["subida"] = frame["change_percent"].fillna(0) > 0
    frame = frame.reset_index(drop=True)

    features = [metrics.history_features(bars_for(symbol)) for symbol in frame["symbol"]]
    frame = frame.join(pd.DataFrame(features))

    frame["variacion_diaria"] = frame["change_percent"]
    frame["volatilidad_pct"] = [
        metrics.daily_volatility(h, l, o if o else pc)
        for h, l, o, pc in zip(frame["high"], frame["low"], frame["open"], frame["previous_close"])
    ]
    frame["volumen_relativo"] = [
        metrics.relative_volume(v, a) for v, a in zip(frame["volume"], frame["volumen_promedio"])
    ]
    frame["recuperacion_intradiaria"] = [
        metrics.intraday_recovery(l, c, h) for l, c, h in zip(frame["low"], frame["last"], frame["high"])
    ]
    frame["monto_ars"] = frame["volume"] * frame["last"]
    frame["liquidez"] = frame["monto_ars"].apply(metrics.liquidity_bucket)
    frame["tendencia"] = [
        metrics.trend_label(v7, v30) for v7, v30 in zip(frame["var_7d"], frame["var_30d"])
    ]

    frame = metrics.compute_score(frame)
    frame = signals.add_classification(frame)
    frame = signals.add_rebound(frame)

    if us is not None and not us.empty and "symbol" in us:
        us_small = us[["symbol", "last", "change_percent"]].rename(
            columns={"symbol": "underlying", "last": "underlying_usd", "change_percent": "underlying_var"}
        )
        frame = frame.merge(us_small, on="underlying", how="left")
    else:
        frame["underlying_usd"] = np.nan
        frame["underlying_var"] = np.nan

    if ccl_quote is not None and ccl_quote.value:
        frame["ccl_ref"] = ccl_quote.value
        frame["precio_usd_ccl"] = frame["last"] / ccl_quote.value
    else:
        frame["ccl_ref"] = np.nan
        frame["precio_usd_ccl"] = np.nan

    return frame


def market_summary(frame: pd.DataFrame) -> dict[str, float]:
    """Indicadores agregados para el dashboard principal."""
    if frame is None or frame.empty:
        return {}
    var = frame["variacion_diaria"].dropna()
    up = int((var > 0).sum())
    down = int((var < 0).sum())
    flat = int((var == 0).sum())
    total = int(var.count())

    best = frame.loc[frame["variacion_diaria"].idxmax()] if total else None
    worst = frame.loc[frame["variacion_diaria"].idxmin()] if total else None

    return {
        "total": int(len(frame)),
        "analizados": total,
        "suben": up,
        "bajan": down,
        "laterales": flat,
        "breadth": (up - down) / total * 100 if total else np.nan,
        "pct_suben": up / total * 100 if total else np.nan,
        "mejor_ticker": best["symbol"] if best is not None else "",
        "mejor_empresa": best.get("company", "") if best is not None else "",
        "mejor_var": float(best["variacion_diaria"]) if best is not None else np.nan,
        "peor_ticker": worst["symbol"] if worst is not None else "",
        "peor_empresa": worst.get("company", "") if worst is not None else "",
        "peor_var": float(worst["variacion_diaria"]) if worst is not None else np.nan,
        "volumen_total": float(frame["monto_ars"].sum(skipna=True)),
        "var_mediana": float(var.median()) if total else np.nan,
    }
