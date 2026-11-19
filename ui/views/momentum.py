"""Vista: momentum y top ganancias del día."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from cedears import charts
from cedears.market import Analysis
from ui import components as ui


def render(analysis: Analysis, frame: pd.DataFrame) -> None:
    ui.page_header(
        "Momentum · top ganancias",
        "Subas del día y calidad del movimiento según volumen y tendencia previa",
        ui.data_status(analysis),
    )

    if frame is None or frame.empty:
        ui.empty_state("Sin datos con los filtros actuales")
        return

    upward = frame[frame["variacion_diaria"] > 0].copy()
    upward = upward.sort_values("variacion_diaria", ascending=False)

    if upward.empty:
        ui.empty_state("Ningún instrumento sube con los filtros actuales", "Revisá los filtros o esperá la próxima rueda.")
        return

    confirmed = upward[upward["volumen_relativo"].fillna(0) >= 1.2]
    weak = upward[upward["volumen_relativo"].fillna(0) < 0.8]

    ui.kpi_grid(
        [
            ui.kpi("En subida", str(len(upward)), "variación diaria > 0", accent="#16C784"),
            ui.kpi("Con volumen alto", str(len(confirmed)), "≥ 1,2x el promedio", accent="#22D3EE"),
            ui.kpi("Con poco volumen", str(len(weak)), "< 0,8x el promedio", accent="#F5B301"),
            ui.kpi("Mejor del día", f'{upward.iloc[0]["symbol"]}', ui.fmt_pct(upward.iloc[0]["variacion_diaria"]), accent="#16C784"),
        ]
    )

    ui.section("Top ganancias del día", "Barras verdes · ranking por variación diaria")
    st.plotly_chart(
        charts.variacion_bar(upward, top_n=min(15, len(upward)), positive=True),
        width="stretch",
        config={"displayModeBar": False},
    )

    table = upward.head(30)[
        ["symbol", "company", "sector", "last", "variacion_diaria", "volume", "var_7d", "var_30d", "volumen_relativo", "tendencia"]
    ].copy()
    table.columns = [
        "Ticker", "Empresa", "Sector", "Precio", "Var. día", "Volumen", "7 días", "30 días", "Vol. rel.", "Tendencia",
    ]
    ui.styled_table(
        table,
        pct_columns=["Var. día", "7 días", "30 días"],
        height=min(600, 40 + 34 * len(table)),
        decimals=2,
    )

    ui.section(
        "Calidad del movimiento",
        "Misma suba, distinto respaldo: el volumen relativo indica si el movimiento tuvo participación",
    )
    left, right = st.columns(2)

    with left:
        ui.banner("<b>Subidas con volumen elevado</b> · movimiento acompañado por mayor participación", "info")
        strong = confirmed.head(10)[["symbol", "company", "variacion_diaria", "volumen_relativo", "var_30d"]]
        strong.columns = ["Ticker", "Empresa", "Var. día", "Vol. rel.", "30 días"]
        ui.styled_table(strong, pct_columns=["Var. día", "30 días"], height=360)

    with right:
        ui.banner("<b>Subidas con poco volumen</b> · requieren confirmación", "warn")
        light = weak.head(10)[["symbol", "company", "variacion_diaria", "volumen_relativo", "var_30d"]]
        light.columns = ["Ticker", "Empresa", "Var. día", "Vol. rel.", "30 días"]
        ui.styled_table(light, pct_columns=["Var. día", "30 días"], height=360)

    # ------------------------------------------------------------ giros
    ui.section(
        "Posibles giros: suben hoy, venían cayendo",
        "Variación diaria positiva con variación mensual negativa · etapa temprana, mayor incertidumbre",
    )
    turning = upward[(upward["var_30d"].fillna(0) < -5) & (upward["var_7d"].fillna(0) > upward["var_30d"].fillna(0))]
    if turning.empty:
        ui.empty_state("No hay instrumentos con ese patrón hoy")
    else:
        turning = turning.sort_values("variacion_diaria", ascending=False)
        turning_table = turning.head(15)[["symbol", "company", "variacion_diaria", "var_7d", "var_30d", "volumen_relativo", "score"]]
        turning_table.columns = ["Ticker", "Empresa", "Var. día", "7 días", "30 días", "Vol. rel.", "Score"]
        ui.styled_table(turning_table, pct_columns=["Var. día", "7 días", "30 días"], height=400)

    ui.disclaimer(
        "Momentum es una señal descriptiva del movimiento reciente. No anticipa continuidad: "
        "las subidas pueden revertirse, especialmente con volumen bajo."
    )
