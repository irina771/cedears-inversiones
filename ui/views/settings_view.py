"""Vista: configuración, diagnóstico y estado de los datos."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from cedears import storage
from cedears.config import settings
from cedears.iol_client import IOLAuthError, IOLClient, IOLError
from cedears.market import Analysis
from ui import components as ui
from ui import data as data_layer


def _mask(value: str) -> str:
    if not value:
        return "no configurado"
    return value[0] + "•" * (len(value) - 1)


def render(analysis: Analysis, frame) -> None:
    ui.page_header(
        "Configuración y datos",
        "Diagnóstico de la conexión con IOL, credenciales (sin exponerlas) y estado de la caché",
        ui.data_status(analysis) if analysis else "sin datos",
    )

    creds_ok = bool(settings.username and settings.password)
    ui.kpi_grid(
        [
            ui.kpi("Credenciales IOL", "Configuradas" if creds_ok else "Faltan", f"usuario {_mask(settings.username)}", accent="#16C784" if creds_ok else "#EA3943"),
            ui.kpi("Endpoint", settings.base_url.replace("https://", ""), "API REST v1", accent="#22D3EE"),
            ui.kpi("Modo sandbox", "Activo" if settings.sandbox else "Desactivado", "CEDEARS_SANDBOX", accent="#F5B301" if settings.sandbox else "#8A9BB4"),
            ui.kpi("Caché local", f"{storage.db_size_bytes()/1024:.0f} KB", str(settings.db_path.name), accent="#8B5CF6"),
        ]
    )

    ui.section("Prueba de conexión", "Verifica el estado del servicio, la autenticación y la disponibilidad del screener")
    if st.button("Ejecutar diagnóstico"):
        _diagnose()

    if settings.sandbox:
        ui.banner("Modo sandbox activo: no se consulta la API. Los datos mostrados son sintéticos.", "danger")

    ui.section("Estado de la caché", "Evita golpear la API en cada interacción")
    stats = storage.cache_stats()
    cache_table = pd.DataFrame(
        [
            {"Indicador": "Entradas clave-valor", "Valor": stats["kv_entries"]},
            {"Indicador": "Filas de barras diarias", "Valor": stats["bar_rows"]},
            {"Indicador": "Símbolos con histórico", "Valor": stats["symbols"]},
            {"Indicador": "Última escritura", "Valor": stats["last_update"] or "—"},
            {"Indicador": "TTL de cotizaciones", "Valor": f"{settings.snapshot_ttl} s"},
            {"Indicador": "TTL de barras", "Valor": f"{settings.bars_ttl // 3600} h"},
        ]
    )
    ui.styled_table(cache_table, height=280)

    if st.button("Vaciar caché y recargar"):
        storage.clear_cache()
        data_layer.invalidate()
        st.cache_resource.clear()
        st.success("Caché vaciada. La próxima carga descargará datos desde IOL.")
        st.rerun()

    ui.section("Variables de entorno", "Definí estos valores en el archivo .env (nunca en el código)")
    st.code(
        "\n".join(
            [
                "IOL_USERNAME=tu_usuario",
                "IOL_PASSWORD=tu_password",
                "# opcionales",
                "IOL_BASE_URL=https://api.iolinversiones.com",
                "IOL_PANEL=general",
                "CEDEARS_SANDBOX=0",
                "CEDEARS_SNAPSHOT_TTL=90",
                "CEDEARS_BARS_TTL=21600",
                "CEDEARS_MAX_WORKERS=6",
            ]
        ),
        language="ini",
    )

    ui.section("Fuentes de datos", "")
    st.markdown(
        """
| Dato | Fuente | Endpoint / URL |
|---|---|---|
| Cotizaciones de CEDEARs y acciones | IOL API v1 | `GET /broker/market-data/screener` |
| Cotización individual | IOL API v1 | `GET /broker/market-data/{symbol}/quote` |
| Histórico OHLCV diario | IOL API v1 | `GET /broker/market-data/{symbol}/bars` |
| Catálogo de tipos y paneles | IOL API v1 | `GET /broker/assets/types`, `/broker/assets/panels` |
| CCL actual | dolarapi.com | `https://dolarapi.com/v1/dolares/contadoconliqui` |
| Serie histórica de CCL | argentinadatos.com | `https://api.argentinadatos.com/v1/cotizaciones/dolares/contadoconliqui` |
| Ratios de conversión | Catálogo local editable | `data/cedears_universe.csv` |
| Dividendos | Carga manual | `data/dividends.csv` |
        """
    )
    ui.disclaimer(
        "Las credenciales nunca se muestran completas ni se registran en logs. El token se guarda en "
        ".cache/iol_token.json (excluido del repositorio) y se renueva automáticamente."
    )


def _diagnose() -> None:
    client = IOLClient()
    try:
        health = client.health()
        st.success(f"Servicio operativo · versión {health.get('version', '?')} · uptime {int(health.get('uptime', 0))} s")
    except IOLError as exc:
        st.error(f"Sin respuesta de /health: {exc}")
        return

    try:
        client.authenticate(force=True)
        st.success("Autenticación OAuth correcta (token renovado).")
    except IOLAuthError as exc:
        st.error(f"Autenticación fallida: {exc}")
        return

    try:
        catalog = data_layer.get_service().catalog(force=True)
        st.info(
            f"Catálogo: cedears='{catalog.get('cedears_type')}', acciones='{catalog.get('stocks_type')}', "
            f"panel='{catalog.get('cedears_panel')}', tipos disponibles: {catalog.get('types', 'n/d')}"
        )
        frame = client.screener("AR", catalog["cedears_type"], catalog["cedears_panel"])
        if frame.empty:
            st.warning("El screener respondió sin instrumentos. Revisá el tipo de asset o el panel configurado.")
        else:
            st.success(f"Screener OK · {len(frame)} instrumentos · ejemplo: {', '.join(frame['symbol'].head(5))}")
    except IOLError as exc:
        st.error(f"Error consultando el screener: {exc}")
