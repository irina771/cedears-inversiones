"""Vista: score cuantitativo y clasificación inteligente."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from cedears import charts, metrics, signals
from cedears.market import Analysis
from ui import components as ui


def render(analysis: Analysis, frame: pd.DataFrame) -> None:
    ui.page_header(
        "Score y clasificación",
        "Ranking comparativo de tendencia, volumen y volatilidad · no es una predicción de rentabilidad",
        ui.data_status(analysis),
    )

    if frame is None or frame.empty:
        ui.empty_state("Sin datos con los filtros actuales")
        return

    with st.expander("Ponderaciones del score", expanded=True):
        col1, col2, col3 = st.columns(3)
        w_trend = col1.slider("Tendencia 7 días", 0.0, 1.0, 0.4, 0.05)
        w_volume = col2.slider("Volumen relativo", 0.0, 1.0, 0.3, 0.05)
        w_volatility = col3.slider("Volatilidad (resta)", 0.0, 1.0, 0.3, 0.05)
        st.caption(
            "Los pesos se normalizan para sumar 1. El volumen se usa en términos relativos "
            "(volumen de hoy / promedio de 20 ruedas) para que el tamaño del activo no distorsione el ranking."
        )

    weights = metrics.ScoreWeights(w_trend, w_volume, w_volatility)
    scored = metrics.compute_score(frame, weights)
    scored = signals.add_classification(scored)
    scored = scored.sort_values("score", ascending=False)

    counts = scored["clasificacion"].value_counts()
    ui.kpi_grid(
        [
            ui.kpi("Mejor score", f'{scored.iloc[0]["symbol"]}', f'{scored.iloc[0]["score"]:.1f} / 100', accent="#16C784"),
            ui.kpi("Peor score", f'{scored.iloc[-1]["symbol"]}', f'{scored.iloc[-1]["score"]:.1f} / 100', accent="#EA3943"),
            ui.kpi("Score mediano", f'{scored["score"].median():.1f}', "universo filtrado", accent="#22D3EE"),
            ui.kpi("Verde", str(int(counts.get(signals.LABEL_GREEN, 0))), "oportunidad potencial", accent="#16C784"),
            ui.kpi("Amarillo", str(int(counts.get(signals.LABEL_YELLOW, 0))), "neutral", accent="#F5B301"),
            ui.kpi("Rojo", str(int(counts.get(signals.LABEL_RED, 0))), "riesgo", accent="#EA3943"),
        ]
    )

    left, right = st.columns(2)
    with left:
        ui.section("Mejores scores", "Combinación de tendencia, volumen y baja volatilidad")
        st.plotly_chart(charts.lollipop_score(scored, 12, best=True), width="stretch", config={"displayModeBar": False})
    with right:
        ui.section("Mayor riesgo relativo", "Peores combinaciones del universo filtrado")
        st.plotly_chart(charts.lollipop_score(scored, 12, best=False), width="stretch", config={"displayModeBar": False})

    ui.section("Componentes del score", "Percentiles por separado para entender de dónde sale cada puntaje")
    st.plotly_chart(charts.score_breakdown(scored, 15), width="stretch", config={"displayModeBar": False})

    ui.section("Ranking detallado")
    table = scored[
        [
            "symbol", "company", "sector", "score", "componente_tendencia", "componente_volumen",
            "componente_volatilidad", "var_7d", "volumen_relativo", "volatilidad_pct",
            "tendencia", "clasificacion", "motivos",
        ]
    ].head(60).copy()
    table.columns = [
        "Ticker", "Empresa", "Sector", "Score", "P. tendencia", "P. volumen", "P. volatilidad",
        "Var. 7d", "Vol. rel.", "Volatilidad", "Tendencia", "Clasificación", "Motivos",
    ]
    ui.styled_table(
        table,
        pct_columns=["Var. 7d", "Volatilidad"],
        height=560,
        decimals=1,
    )

    st.download_button(
        "Descargar ranking (CSV)",
        data=scored.to_csv(index=False).encode("utf-8-sig"),
        file_name="ranking_cedears.csv",
        mime="text/csv",
    )

    _explain(weights)


def _explain(weights: metrics.ScoreWeights) -> None:
    weights = weights.normalized()
    ui.section("Metodología", "")
    st.markdown(
        f"""
**Normalización.** Cada componente se transforma con su *rango percentil* dentro del universo filtrado
(0 a 100) y luego se lleva al intervalo [-1, 1]:

```
n(x) = 2 × percentil(x)/100 − 1
```

El rango percentil es robusto a valores extremos: un volumen gigante no aplasta al resto como pasaría
con una normalización min-max.

**Fórmula aplicada ahora mismo:**

```
score_raw = {weights.trend_7d:.2f} × n(var_7d)
          + {weights.relative_volume:.2f} × n(volumen_relativo)
          − {weights.volatility:.2f} × n(volatilidad_diaria)

score = (score_raw + 1) / 2 × 100        → escala 0-100
```

* `var_7d` = variación de los últimos 7 días calendario.
* `volumen_relativo` = volumen del día / promedio de las 20 ruedas anteriores.
* `volatilidad_diaria` = (máximo − mínimo) / apertura × 100.

**Clasificación.**

| Etiqueta | Criterio |
|---|---|
| Verde · Oportunidad potencial | al menos 2 señales simultáneas: caída ≥ 3%, volumen ≥ 1,2x, recuperación intradiaria ≥ 60% o descuento ≥ 20% vs máximo 52s |
| Rojo · Riesgo | caída mensual ≤ −15%, volatilidad ≥ 6% diaria o volumen < 0,6x el promedio |
| Amarillo · Neutral | todo lo demás |

La etiqueta **Verde** no implica recomendación de compra: indica que hay señales que ameritan
investigación (fundamentos, noticias, liquidez). El score es un ranking relativo entre los activos
analizados, no un pronóstico.
        """
    )
