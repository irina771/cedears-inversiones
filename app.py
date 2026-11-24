"""Cedears Inversiones — dashboard de análisis de CEDEARs del mercado argentino.

Ejecutar con:  streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cedears.config import settings  # noqa: E402
from cedears.universe import sectors_in  # noqa: E402
from ui import components as ui  # noqa: E402
from ui import data as data_layer  # noqa: E402
from ui import theme  # noqa: E402
from ui.views import (  # noqa: E402
    alerts,
    argentina,
    arsusd,
    dips,
    history,
    momentum,
    overview,
    scores,
    simulator,
)

st.set_page_config(
    page_title="Cedears Inversiones",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

theme.inject_theme()

PAGES = {
    "Resumen del mercado": overview.render,
    "Simulador de inversión": simulator.render,
    "Histórico y evolución": history.render,
    "CEDEARs en baja · rebotes": dips.render,
    "Momentum · top ganancias": momentum.render,
    "Empresas argentinas": argentina.render,
    "ARS vs USD · CCL": arsusd.render,
    "Score y clasificación": scores.render,
    "Alertas": alerts.render,
}


def sidebar_brand() -> None:
    st.sidebar.markdown(
        """
        <div class="brand">
          <div class="brand-mark">CI</div>
          <div>
            <div class="brand-title">Cedears Inversiones</div>
            <div class="brand-sub">Mercado argentino</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_filters(frame) -> dict:
    """Filtros globales del panel lateral."""
    filters: dict = {}
    with st.sidebar.expander("Filtros", expanded=False):
        tickers = sorted(frame["symbol"].dropna().unique())
        filters["tickers"] = st.multiselect("Ticker", tickers, placeholder="Todos")

        companies = sorted(frame["company"].dropna().unique())
        filters["companies"] = st.multiselect("Empresa", companies, placeholder="Todas")

        sectors = sectors_in(frame)
        filters["sectors"] = st.multiselect("Sector", sectors, placeholder="Todos")

        filters["types"] = st.multiselect(
            "Tipo de activo", sorted(frame["type"].dropna().unique()), placeholder="Todos"
        )
        filters["trends"] = st.multiselect(
            "Tendencia", ["Positiva", "Lateral", "Negativa", "N/D"], placeholder="Todas"
        )
        filters["classifications"] = st.multiselect(
            "Clasificación",
            ["Verde · Oportunidad potencial", "Amarillo · Neutral", "Rojo · Riesgo"],
            placeholder="Todas",
        )
        var_range = st.slider("Variación diaria (%)", -30.0, 30.0, (-30.0, 30.0), 0.5)
        filters["var_range"] = var_range
        filters["min_volume"] = st.number_input(
            "Volumen mínimo (millones de ARS)", min_value=0.0, value=0.0, step=1.0
        ) * 1_000_000

    return filters


def setup_screen() -> None:
    ui.page_header(
        "Cedears Inversiones",
        "Dashboard de análisis de CEDEARs y acciones argentinas con datos de la API de IOL",
        "sin conexión configurada",
    )
    ui.banner(
        "No hay credenciales de IOL configuradas. El dashboard necesita un usuario y contraseña de "
        "IOL Inversiones (los mismos de la app) para consultar datos reales.",
        "warn",
    )
    st.markdown(
        """
### Configuración en 3 pasos

1. Copiá el archivo de ejemplo y completá tus credenciales:

```bash
copy .env.example .env      # Windows
cp .env.example .env        # Linux / macOS
```

```ini
IOL_USERNAME=tu_usuario
IOL_PASSWORD=tu_password
```

2. Verificá la conexión desde la terminal:

```bash
python scripts/check_iol.py
```

3. Volvé a esta pantalla y presioná **Actualizar datos** en la barra lateral.

> Las credenciales se leen de variables de entorno y nunca se guardan en el código ni en el repositorio.
> El archivo `.env` está excluido por `.gitignore`.

**¿Querés ver la interfaz sin credenciales?** Ejecutá `set CEDEARS_SANDBOX=1` (Windows) o
`export CEDEARS_SANDBOX=1` (Linux/macOS) y reiniciá la app. El modo sandbox usa datos
sintéticos claramente identificados y sirve solo para probar la interfaz.
        """
    )
    if settings.sandbox:
        ui.banner("Modo sandbox activo: los datos son sintéticos.", "danger")


def main() -> None:
    sidebar_brand()

    if not settings.is_configured:
        st.sidebar.markdown(
            f'<div class="small">Sin credenciales<br>v1.0 · {settings.base_url}</div>',
            unsafe_allow_html=True,
        )
        setup_screen()
        return

    page = st.sidebar.radio("Navegación", list(PAGES), label_visibility="collapsed")

    if st.sidebar.button("Actualizar datos", use_container_width=True):
        data_layer.invalidate()
        st.cache_resource.clear()
        st.rerun()

    analysis = data_layer.get_analysis()
    error = st.session_state.get("iol_error")
    if error:
        ui.banner(f"No se pudo conectar con IOL: {error}", "danger")

    if analysis is None or analysis.empty:
        st.sidebar.markdown('<div class="small">Sin datos disponibles</div>', unsafe_allow_html=True)
        ui.page_header(page, "Sin datos disponibles", "desconectado")
        ui.banner(
            "No hay cotizaciones para mostrar. Revisá la configuración de credenciales y la conexión "
            "con api.iolinversiones.com.",
            "danger",
        )
        return

    for message in analysis.warnings:
        ui.banner(message, "danger" if analysis.stale else "info")

    filters = render_filters(analysis.frame)
    frame = data_layer.apply_filters(analysis.frame, filters)

    st.sidebar.markdown(
        '<div class="small" style="margin-top:0.9rem">Herramienta de análisis. No constituye '
        "recomendación de inversión.</div>",
        unsafe_allow_html=True,
    )

    PAGES[page](analysis, frame)


if __name__ == "__main__":
    main()
