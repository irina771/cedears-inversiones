"""Vista: comparación ARS vs USD y CCL implícito."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from cedears import charts
from cedears.iol_client import infer_ratio
from cedears.market import Analysis
from ui import components as ui


def build_table(frame: pd.DataFrame, ccl_ref: float | None) -> pd.DataFrame:
    data = frame[(frame["type"] == "CEDEAR") & frame["underlying_usd"].notna()].copy()
    if data.empty or not ccl_ref:
        return pd.DataFrame()

    rows = []
    for row in data.itertuples():
        ratio_catalog = getattr(row, "ratio", np.nan)
        ratio_catalog = None if pd.isna(ratio_catalog) else float(ratio_catalog)
        inferred, error = infer_ratio(row.last, row.underlying_usd, ccl_ref)
        ratio_used = ratio_catalog or inferred
        if not ratio_used:
            continue

        implied = row.last * ratio_used / row.underlying_usd if row.underlying_usd else np.nan
        theoretical = row.underlying_usd / ratio_used * ccl_ref if ratio_used else np.nan
        gap = (row.last / theoretical - 1) * 100 if theoretical else np.nan
        ratio_warning = ""
        if ratio_catalog and inferred and abs(ratio_catalog - inferred) / ratio_catalog > 0.10:
            ratio_warning = "revisar ratio"

        rows.append(
            {
                "Ticker": row.symbol,
                "Empresa": row.company,
                "Precio ARS": row.last,
                "Subyacente USD": row.underlying_usd,
                "Ratio usado": ratio_used,
                "Origen ratio": "catálogo" if ratio_catalog else "inferido",
                "CCL ref.": ccl_ref,
                "CCL implícito": implied,
                "Diferencia vs CCL": (implied / ccl_ref - 1) * 100 if implied else np.nan,
                "Precio teórico ARS": theoretical,
                "Brecha vs teórico": gap,
                "Var. día": row.variacion_diaria,
                "Var. subyacente": getattr(row, "underlying_var", np.nan),
                "Aviso": ratio_warning,
            }
        )
    return pd.DataFrame(rows)


def render(analysis: Analysis, frame: pd.DataFrame) -> None:
    ui.page_header(
        "ARS vs USD · CCL",
        "Precio local, precio del activo subyacente y tipo de cambio implícito · sin interpretación de arbitraje",
        ui.data_status(analysis),
    )

    ccl = analysis.ccl
    if ccl is None or not ccl.value:
        ui.banner(
            "No hay cotización de CCL disponible. La comparación ARS/USD queda deshabilitada para no "
            "estimar con datos faltantes.",
            "warn",
        )
    else:
        ui.kpi_grid(
            [
                ui.kpi("CCL de referencia", ccl.label, f'{ccl.source}', accent="#F5B301"),
                ui.kpi("CCL actualizado", ccl.updated_at.astimezone().strftime("%d/%m %H:%M") if ccl.updated_at else "N/D", accent="#22D3EE"),
                ui.kpi("CEDEARs con subyacente", str(int(frame["underlying_usd"].notna().sum() if "underlying_usd" in frame else 0)), "precio USD disponible", accent="#8B5CF6"),
                ui.kpi("Ratios en catálogo", str(int(frame["ratio"].notna().sum() if "ratio" in frame else 0)), "verificados manualmente", accent="#16C784"),
            ]
        )

    table = build_table(frame, ccl.value if ccl else None)
    if table.empty:
        ui.empty_state(
            "No se pudo construir la comparación",
            "Se necesita el precio del subyacente en USD. Verificá que el screener de EE.UU. esté disponible.",
        )
        _explain()
        return

    ui.section("Tabla de comparación", "El CCL implícito surge de precio ARS, precio USD del subyacente y ratio de conversión")
    filter_col, _ = st.columns([2, 2])
    with filter_col:
        min_gap = st.slider("Mostrar brechas de al menos (valor absoluto %)", 0.0, 20.0, 0.0, 0.5)
    shown = table[table["Brecha vs teórico"].abs().fillna(0) >= min_gap]
    shown = shown.sort_values("Brecha vs teórico", ascending=False)

    display = shown[
        [
            "Ticker", "Empresa", "Precio ARS", "Subyacente USD", "Ratio usado", "Origen ratio",
            "CCL ref.", "CCL implícito", "Diferencia vs CCL", "Var. día", "Var. subyacente", "Aviso",
        ]
    ]
    ui.styled_table(
        display,
        pct_columns=["Diferencia vs CCL", "Var. día", "Var. subyacente"],
        height=min(640, 40 + 34 * len(display)),
        decimals=2,
    )

    if not shown.empty:
        gaps = shown["Brecha vs teórico"].dropna()
        fig = go.Figure(
            go.Histogram(
                x=gaps,
                nbinsx=24,
                marker=dict(color=[charts.GREEN if v > 0 else charts.RED for v in gaps], line=dict(width=0)),
                hovertemplate="Brecha %{x:.2f}%<br>%{y} CEDEARs<extra></extra>",
            )
        )
        fig.add_vline(x=0, line=dict(color="rgba(230,237,247,0.5)", width=1, dash="dash"))
        fig.update_layout(xaxis_title="Brecha entre precio de mercado y precio teórico (%)", yaxis_title="CEDEARs")
        fig = charts._layout(fig, height=280)
        fig.update_xaxes(ticksuffix="%")
        ui.section("Distribución de la brecha", "Positivo = el CEDEAR cotiza por encima del teórico")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    # ------------------------------------------------------------- detalle
    ui.section("Detalle de un instrumento", "Cómo se compone el precio local")
    ticker = st.selectbox("Ticker", shown["Ticker"].tolist() if not shown.empty else table["Ticker"].tolist())
    row = table[table["Ticker"] == ticker].iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Precio CEDEAR (ARS)", ui.fmt_money(row["Precio ARS"]))
    c2.metric("Subyacente (USD)", ui.fmt_money(row["Subyacente USD"], 2, "US$"))
    c3.metric("Ratio usado", f'1:{row["Ratio usado"]:.0f}' if row["Ratio usado"] else "N/D", row["Origen ratio"])
    c4.metric("CCL implícito", ui.fmt_money(row["CCL implícito"], 1), ui.fmt_pct(row["Diferencia vs CCL"]))

    st.markdown(
        f"""
**Descomposición**

```
precio_teórico_ARS = (precio_subyacente_USD / ratio) × CCL
{ui.fmt_money(row['Subyacente USD'], 2, 'US$')} / {row['Ratio usado']:.0f} × {ui.fmt_money(row['CCL implícito'], 1)} = {ui.fmt_money(row['Precio teórico ARS'])}
precio de mercado   = {ui.fmt_money(row['Precio ARS'])}
brecha              = {ui.fmt_pct(row['Brecha vs teórico'])}
```
        """
    )
    if row["Aviso"]:
        ui.banner(
            "El ratio del catálogo difiere más de 10% del ratio inferido por precios. "
            "Puede haber un ajuste corporativo (split, dividendo) o un ratio desactualizado en "
            "<span class='mono'>data/cedears_universe.csv</span>.",
            "warn",
        )

    _explain()


def _explain() -> None:
    ui.section("Cómo leer esta sección", "")
    st.markdown(
        """
El precio de un CEDEAR en pesos depende de tres cosas:

1. **Precio del activo subyacente** (la acción o ETF en EE.UU., en dólares).
2. **Tipo de cambio** implícito (CCL) del mercado local.
3. **Ratio de conversión**: cuántos CEDEARs equivalen a una acción subyacente.

Las diferencias entre el precio de mercado y el precio teórico **no son arbitraje seguro**. Pueden
explicarse por:

* desfasaje horario (BYMA opera antes y después de NYSE),
* premio o descuento local por oferta/demanda,
* liquidez y spreads distintos,
* ratios desactualizados por splits o dividendos,
* comisiones, impuestos y restricciones de transferencia entre mercados.

El ratio del catálogo se puede completar y verificar en `data/cedears_universe.csv`. Cuando no está
cargado, la aplicación usa un **ratio inferido** a partir de los precios reales (marcado como
"inferido"), que sirve para ordenar la comparación pero debe verificarse antes de operar.
        """
    )
