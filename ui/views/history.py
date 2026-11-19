"""Vista: histórico y evolución (sección posterior al dashboard)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from cedears import charts, fx
from cedears.market import Analysis
from ui import components as ui
from ui import data as data_layer

PERIODS = ["7 días", "1 mes", "5 meses", "1 año", "5 años"]


def _returns_matrix(symbols: list[str], frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    today = pd.Timestamp.today().normalize()
    for symbol in symbols:
        row = {"Ticker": symbol}
        for period in PERIODS:
            start = pd.Timestamp(data_layer.period_start(period))
            series = data_layer.history_frame([symbol], start)
            if series.empty:
                row[period] = np.nan
                continue
            first = series["value"].iloc[0]
            last = series["value"].iloc[-1]
            row[period] = (last / first - 1) * 100 if first else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def _usd_adjust(series: pd.DataFrame, ccl_history: pd.DataFrame) -> pd.DataFrame:
    if series.empty or ccl_history is None or ccl_history.empty:
        return pd.DataFrame()
    frame = series.copy()
    ccl = ccl_history.sort_values("date")
    frame["ccl"] = frame["date"].apply(lambda d: fx.ccl_on(ccl, d))
    frame = frame.dropna(subset=["ccl"])
    frame["value"] = frame["value"] / frame["ccl"]
    return frame


def render(analysis: Analysis, frame: pd.DataFrame) -> None:
    ui.page_header(
        "Histórico y evolución",
        "Rendimientos por período, comparación contra SPY y series normalizadas · en ARS o USD (CCL)",
        ui.data_status(analysis),
    )

    if frame is None or frame.empty:
        ui.empty_state("Sin datos con los filtros actuales")
        return

    available = sorted(frame["symbol"].dropna().unique())
    defaults = [t for t in ["SPY", "AAPL", "YPF", "GGAL", "KO"] if t in available][:3] or available[:3]

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        selected = st.multiselect("Tickers a comparar", available, default=defaults, key="hist_tickers")
    with col2:
        period = st.selectbox("Período", PERIODS, index=3)
    with col3:
        currency = st.radio("Moneda", ["ARS", "USD (CCL)"], horizontal=True)

    if not selected:
        ui.empty_state("Seleccioná al menos un ticker")
        return

    start = data_layer.period_start(period)
    with_spy = list(dict.fromkeys(selected + (["SPY"] if "SPY" in available else [])))

    series = data_layer.history_frame(with_spy, start)
    if series.empty:
        ui.empty_state(
            "Sin histórico para el período",
            "La caché de barras todavía no tiene datos de estos tickers. Actualizá los datos o elegí otro período.",
        )
        return

    if currency.startswith("USD"):
        adjusted = _usd_adjust(series, analysis.ccl_history)
        if adjusted.empty:
            ui.banner("No hay serie de CCL suficiente para convertir a dólares. Se muestra en ARS.", "warn")
        else:
            series = adjusted

    ui.section("Evolución comparada", "Series normalizadas a base 100 al inicio del período")
    st.plotly_chart(
        charts.evolution_chart(series[series["symbol"].isin(with_spy)], normalize=True),
        width="stretch",
        config={"displayModeBar": False},
    )

    # ------------------------------------------------------- comparación SPY
    comparison_rows = []
    for symbol in with_spy:
        data = series[series["symbol"] == symbol].sort_values("date")
        if data.empty:
            continue
        values = data["value"].astype(float)
        returns = values.pct_change().dropna()
        total = (values.iloc[-1] / values.iloc[0] - 1) * 100 if values.iloc[0] else np.nan
        comparison_rows.append(
            {
                "Ticker": symbol,
                "Rendimiento": total,
                "Volatilidad diaria": returns.std() * 100,
                "Volatilidad anualizada": returns.std() * np.sqrt(252) * 100,
                "Días": len(data),
                "Desde": data["date"].min().strftime("%d/%m/%Y"),
                "Hasta": data["date"].max().strftime("%d/%m/%Y"),
            }
        )

    comparison = pd.DataFrame(comparison_rows)
    if "SPY" in comparison["Ticker"].values:
        spy_return = comparison.loc[comparison["Ticker"] == "SPY", "Rendimiento"].iloc[0]
        comparison["Diferencia vs SPY"] = comparison["Rendimiento"] - spy_return

    ui.section("Rendimiento y volatilidad", f"Período: {period} · moneda: {currency}")
    ui.styled_table(
        comparison,
        pct_columns=["Rendimiento", "Volatilidad diaria", "Volatilidad anualizada", "Diferencia vs SPY"],
        height=min(480, 40 + 34 * len(comparison)),
        decimals=2,
    )

    if "Diferencia vs SPY" in comparison:
        ui.banner(
            f"SPY rindió {ui.fmt_pct(spy_return)} en el período. La columna <b>Diferencia vs SPY</b> muestra "
            "el exceso o déficit de cada activo contra el índice de referencia, sin ajustar por riesgo.",
            "info",
        )

    # ---------------------------------------------------- matriz de períodos
    ui.section("Rendimiento por período", "Todos los períodos calculados con el histórico disponible (sin rellenar datos faltantes)")
    matrix = _returns_matrix(selected, frame)
    ui.styled_table(
        matrix,
        pct_columns=PERIODS,
        height=min(480, 40 + 34 * len(matrix)),
        decimals=2,
    )

    st.download_button(
        "Descargar series del período (CSV)",
        data=series.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"historico_{period.replace(' ', '_')}.csv",
        mime="text/csv",
    )

    ui.disclaimer(
        "El histórico proviene de las barras diarias de IOL (endpoint /bars) cacheadas localmente. "
        "La conversión a USD usa el CCL de referencia diario (argentinadatos.com). "
        "No se incluyen dividendos, comisiones ni impuestos."
    )
