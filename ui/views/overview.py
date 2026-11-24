"""Vista: resumen del mercado (pantalla inicial)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from cedears import charts, fx, metrics
from cedears.market import Analysis, market_summary
from ui import components as ui


def _spy_variation(analysis: Analysis) -> tuple[float, str]:
    frame = analysis.frame
    spy = frame[frame["symbol"] == "SPY"]
    if not spy.empty and pd.notna(spy.iloc[0]["variacion_diaria"]):
        return float(spy.iloc[0]["variacion_diaria"]), "CEDEAR SPY (ARS)"
    us = analysis.us_prices
    if us is not None and not us.empty:
        row = us[us["symbol"] == "SPY"]
        if not row.empty and pd.notna(row.iloc[0]["change_percent"]):
            return float(row.iloc[0]["change_percent"]), "SPY (NYSE, USD)"
    return float("nan"), "sin dato"


def render(analysis: Analysis, frame: pd.DataFrame) -> None:
    summary = market_summary(frame)
    ui.page_header(
        "Resumen del mercado",
        "Panorama de CEDEARs y acciones argentinas · variaciones, amplitud y rankings del día",
        ui.data_status(analysis),
    )

    if frame is None or frame.empty:
        ui.empty_state("Sin instrumentos con los filtros actuales", "Ajustá los filtros del panel lateral.")
        return

    spy_var, spy_label = _spy_variation(analysis)
    ccl = analysis.ccl
    ccl_var = fx.ccl_change(analysis.ccl_history, days=7) if analysis.ccl_history is not None else None

    breadth = summary.get("breadth", float("nan"))
    market_state = "Mercado positivo" if breadth > 10 else "Mercado negativo" if breadth < -10 else "Mercado mixto"
    state_tone = "green" if breadth > 10 else "red" if breadth < -10 else "amber"

    ui.kpi_grid(
        [
            ui.kpi("CEDEARs analizados", f'{summary.get("total", 0):,}'.replace(",", "."),
                   f'{summary.get("analizados", 0)} con variación válida', accent="#22D3EE"),
            ui.kpi("En subida", f'{summary.get("suben", 0)}',
                   f'{summary.get("pct_suben", 0):.0f}% del total', accent="#16C784"),
            ui.kpi("En bajada", f'{summary.get("bajan", 0)}',
                   "amplitud " + ui.fmt_pct(breadth), accent="#EA3943"),
            ui.kpi("Mayor ganancia", ui.fmt_pct(summary.get("mejor_var")),
                   f'{summary.get("mejor_ticker", "")} · {summary.get("mejor_empresa", "")}', accent="#16C784"),
            ui.kpi("Mayor caída", ui.fmt_pct(summary.get("peor_var")),
                   f'{summary.get("peor_ticker", "")} · {summary.get("peor_empresa", "")}', accent="#EA3943"),
            ui.kpi("SPY", ui.fmt_pct(spy_var), spy_label, accent="#8B5CF6"),
            ui.kpi("CCL", ccl.label if ccl else "N/D",
                   f'7d {ui.fmt_pct(ccl_var)} · {ccl.source if ccl else "sin datos"}', accent="#F5B301"),
        ]
    )

    amplitude_pill = ui.pill(f"Amplitud {ui.fmt_pct(breadth)}", "cyan")
    median_pill = ui.pill(f"Mediana {ui.fmt_pct(summary.get('var_mediana'))}", "muted")
    st.markdown(
        '<div style="margin:0.8rem 0 0.2rem 0">'
        + ui.pill(market_state, state_tone)
        + " "
        + amplitude_pill
        + " "
        + median_pill
        + "</div>",
        unsafe_allow_html=True,
    )

    # ---------------------------------------------------------- indicadores
    ui.section("Indicadores de mercado", "Distribución de subidas y bajadas del universo filtrado")
    left, right = st.columns([1, 2])
    with left:
        st.plotly_chart(
            charts.breadth_donut(summary.get("suben", 0), summary.get("bajan", 0), summary.get("laterales", 0)),
            width="stretch",
            config={"displayModeBar": False},
        )
    with right:
        st.plotly_chart(charts.distribution_histogram(frame), width="stretch", config={"displayModeBar": False})

    ui.section("Heatmap del mercado", "Tamaño por monto operado · color por variación diaria · filtrá por sector en la barra lateral")
    st.markdown(charts.market_heatmap(frame), unsafe_allow_html=True)

    # ------------------------------------------------------------- rankings
    ui.section("Rankings del día", "Top ganancias y top caídas · primeros 5 puestos")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f'<div class="section-sub">Top ganancias</div>', unsafe_allow_html=True)
        top_up = frame.nlargest(5, "variacion_diaria")[["symbol", "company", "variacion_diaria", "volumen_relativo"]].copy()
        top_up.insert(0, "Pos", range(1, len(top_up) + 1))
        top_up.columns = ["Pos", "Ticker", "Empresa", "Var. día", "Vol. rel."]
        ui.styled_table(top_up, pct_columns=["Var. día"], height=280)

    with col2:
        st.markdown(f'<div class="section-sub">Top caídas</div>', unsafe_allow_html=True)
        top_down = frame.nsmallest(5, "variacion_diaria")[["symbol", "company", "variacion_diaria", "volumen_relativo"]].copy()
        top_down.insert(0, "Pos", range(1, len(top_down) + 1))
        top_down.columns = ["Pos", "Ticker", "Empresa", "Var. día", "Vol. rel."]
        ui.styled_table(top_down, pct_columns=["Var. día"], height=280)

    ui.disclaimer(
        "Los precios provienen de la API de IOL (plazo T0) y pueden tener demora respecto del mercado en vivo. "
        "El volumen relativo se calcula contra el promedio de 20 ruedas. N/D = dato no disponible."
    )
