"""Vista: CEDEARs en baja y posibles rebotes."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from cedears import charts, signals
from cedears.market import Analysis
from ui import components as ui


def render(analysis: Analysis, frame: pd.DataFrame) -> None:
    ui.page_header(
        "CEDEARs en baja",
        "Caídas del día y señales que ameritan investigación · no son predicciones de rebote",
        ui.data_status(analysis),
    )

    if frame is None or frame.empty:
        ui.empty_state("Sin datos con los filtros actuales")
        return

    controls, info = st.columns([2, 3])
    with controls:
        max_drop = st.slider("Mostrar caídas de al menos", -25.0, 0.0, -1.0, 0.5, format="%.1f%%")
        min_volume = st.slider("Volumen relativo mínimo (0 = sin filtro)", 0.0, 3.0, 0.0, 0.1)
        limit = st.slider("Cantidad de filas", 10, 100, 30, 5)

    drops = frame[frame["variacion_diaria"] <= max_drop].copy()
    if min_volume > 0:
        drops = drops[drops["volumen_relativo"].fillna(0) >= min_volume]
    drops = drops.sort_values("variacion_diaria", ascending=True)

    with info:
        ui.kpi_grid(
            [
                ui.kpi("CEDEARs en baja", str(len(drops)), "según filtros"), 
                ui.kpi("Caída media", ui.fmt_pct(drops["variacion_diaria"].mean()) if not drops.empty else "N/D", accent="#EA3943"),
                ui.kpi("Con volumen alto", str(int((drops["volumen_relativo"].fillna(0) >= 1.2).sum())), "≥ 1,2x promedio", accent="#F5B301"),
            ]
        )

    if drops.empty:
        ui.empty_state("No hay instrumentos que cumplan el criterio de caída", "Probá bajar el umbral mínimo.")
        return

    ui.section("Mayores caídas del día", "Ordenadas de mayor a menor caída (variacionDiaria ASC)")
    st.plotly_chart(
        charts.variacion_bar(drops, top_n=min(15, len(drops))),
        width="stretch",
        config={"displayModeBar": False},
    )

    table = drops.head(limit)[
        [
            "symbol", "company", "last", "variacion_diaria", "high", "low", "volume",
            "var_7d", "var_30d", "volumen_relativo", "liquidez",
        ]
    ].copy()
    table.columns = [
        "Ticker", "Empresa", "Precio", "Var. día", "Máx. día", "Mín. día", "Volumen",
        "7 días", "30 días", "Vol. rel.", "Liquidez",
    ]
    ui.styled_table(
        table,
        pct_columns=["Var. día", "7 días", "30 días"],
        height=min(620, 40 + 35 * len(table)),
        decimals=2,
    )

    # --------------------------------------------------------------- rebotes
    ui.section(
        "Posibles oportunidades de rebote",
        "Señales combinadas: caída, volumen, recuperación intradiaria, descuento vs máximo 52s y tendencia",
    )
    ui.banner(
        "Una caída no garantiza un rebote. Estas señales solo priorizan qué mirar: verifiquen fundamentos, "
        "noticias y liquidez antes de operar. El score de rebote no es una probabilidad.",
        "warn",
    )

    rebound = frame.copy()
    rebound = signals.add_rebound(rebound)
    candidates = rebound[rebound["score_rebote"].fillna(0) >= 40].sort_values("score_rebote", ascending=False)

    if candidates.empty:
        ui.empty_state("Ningún instrumento alcanza 40 puntos de señales de rebote", "Bajá el umbral desde el código o esperá otra rueda.")
    else:
        top = candidates.head(limit)[
            [
                "symbol", "company", "variacion_diaria", "volumen_relativo", "recuperacion_intradiaria",
                "descuento_52w", "var_7d", "var_30d", "score_rebote", "senales_rebote",
            ]
        ].copy()
        top["recuperacion_intradiaria"] = top["recuperacion_intradiaria"] * 100
        top.columns = [
            "Ticker", "Empresa", "Var. día", "Vol. rel.", "Recupera del rango (%)",
            "Desc. 52s", "7 días", "30 días", "Score rebote", "Señales detectadas",
        ]
        ui.styled_table(
            top,
            pct_columns=["Var. día", "Desc. 52s", "7 días", "30 días", "Recupera del rango (%)"],
            height=min(560, 40 + 35 * len(top)),
            decimals=1,
        )

    with st.expander("Cómo se calcula el score de rebote"):
        st.markdown(
            """
Se combinan cinco señales, cada una normalizada entre 0 y 1 y ponderada:

| Señal | Peso | Criterio |
|---|---|---|
| Caída del día | 25% | más negativo = más puntos (hasta -9%) |
| Volumen relativo | 25% | 0,8x = 0 puntos · 2,5x = máximo |
| Recuperación intradiaria | 20% | posición del precio dentro del rango del día |
| Descuento vs máximo 52s | 15% | 40% de descuento = máximo |
| Mejora de corto plazo | 15% | variación 7d por encima de la de 30d |

El resultado se muestra en escala 0-100. **No** es una probabilidad ni una recomendación.
            """
        )
    ui.disclaimer("Volumen en unidades operadas según la API de IOL. Liquidez estimada como volumen × último precio en ARS.")
