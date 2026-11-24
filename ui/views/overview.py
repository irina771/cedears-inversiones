"""Vista: resumen del mercado (pantalla inicial)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from cedears import charts
from cedears.market import Analysis, market_summary
from ui import components as ui


def render(analysis: Analysis, frame: pd.DataFrame) -> None:
    summary = market_summary(frame)
    ui.page_header(
        "Dashboard CEDEARs",
        "Panorama de CEDEARs y acciones argentinas · variaciones, amplitud y rankings del día",
    )

    if frame is None or frame.empty:
        ui.empty_state("Sin instrumentos para mostrar", "Revisá la conexión con IOL y volvé a actualizar los datos.")
        return

    # ------------------------------------------------------------------ CCL
    ui.ccl_card(analysis.ccl, analysis.ccl_history)

    # -------------------------------------------------------------- amplitud
    total = summary.get("total", 0)
    suben = summary.get("suben", 0)
    bajan = summary.get("bajan", 0)
    pct_suben = suben / total * 100 if total else float("nan")
    pct_bajan = bajan / total * 100 if total else float("nan")

    ui.kpi_grid(
        [
            ui.kpi("Subiendo", f"{suben}", f"{ui.fmt_pct(pct_suben, 1, signed=False)} · CEDEARs en verde", accent="#16C784"),
            ui.kpi("Bajando", f"{bajan}", f"{ui.fmt_pct(pct_bajan, 1, signed=False)} · CEDEARs en rojo", accent="#EA3943"),
            ui.kpi("Top ganador", ui.fmt_pct(summary.get("mejor_var")),
                   f'{summary.get("mejor_ticker", "")} · {summary.get("mejor_empresa", "")}', accent="#16C784"),
            ui.kpi("Volumen total", ui.fmt_money(summary.get("volumen_total")),
                   "Monto operado en ARS", accent="#22D3EE"),
        ],
        columns=2,
    )

    # ------------------------------------------------------------- rankings
    ui.section("Rankings del día", "Top ganancias y top caídas · primeros 5 puestos")
    ranked = frame.dropna(subset=["variacion_diaria"])
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-sub">Top ganancias</div>', unsafe_allow_html=True)
        st.markdown(ui.rank_list(ranked.nlargest(5, "variacion_diaria")), unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="section-sub">Top caídas</div>', unsafe_allow_html=True)
        st.markdown(ui.rank_list(ranked.nsmallest(5, "variacion_diaria")), unsafe_allow_html=True)

    # ---------------------------------------------------------- indicadores
    ui.section("Indicadores de mercado", "Distribución de subidas y bajadas del universo")
    left, right = st.columns([1, 2])
    with left:
        st.plotly_chart(
            charts.breadth_donut(summary.get("suben", 0), summary.get("bajan", 0), summary.get("laterales", 0)),
            width="stretch",
            config={"displayModeBar": False},
        )
    with right:
        st.plotly_chart(charts.distribution_histogram(frame), width="stretch", config={"displayModeBar": False})

    ui.section("Heatmap del mercado", "Tamaño por monto operado · color por variación diaria")
    st.markdown(charts.market_heatmap(frame), unsafe_allow_html=True)
