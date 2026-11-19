"""Vista: simulador de inversión histórica."""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
import streamlit as st

from cedears import charts, fx
from cedears.market import Analysis
from ui import components as ui
from ui import data as data_layer

PRESETS = {"1 mes": 30, "5 meses": 152, "1 año": 365, "5 años": 365 * 5}
CAPITALS = [100_000, 500_000, 1_000_000]


def _price_now(symbol: str, frame: pd.DataFrame) -> tuple[float | None, str]:
    row = frame[frame["symbol"] == symbol]
    if not row.empty and pd.notna(row.iloc[0]["last"]):
        return float(row.iloc[0]["last"]), "último precio de la API"
    price, stamp = data_layer.last_price_before(symbol, date.today())
    return price, f"cierre del {stamp:%d/%m/%Y}" if stamp is not None else "sin datos"


def simulate(symbol: str, capital: float, start: date, frame: pd.DataFrame, ccl_hist: pd.DataFrame) -> dict | None:
    start_price, start_stamp = data_layer.last_price_before(symbol, start)
    if start_price is None or not start_price:
        return None
    end_price, price_source = _price_now(symbol, frame)
    if end_price is None:
        return None

    units = math.floor(capital / start_price)
    invested = units * start_price
    remaining = capital - invested
    value = units * end_price
    pnl = value - invested
    pnl_pct = (end_price / start_price - 1) * 100

    ccl_start = fx.ccl_on(ccl_hist, start_stamp) if start_stamp is not None else None
    ccl_now = float(ccl_hist["ccl"].iloc[-1]) if ccl_hist is not None and not ccl_hist.empty else None
    value_usd = value / ccl_now if ccl_now else None
    invested_usd = capital / ccl_start if ccl_start else None
    pnl_usd = value_usd - capital / ccl_start if (value_usd is not None and ccl_start) else None
    pnl_usd_pct = (end_price / start_price * ccl_start / ccl_now - 1) * 100 if (ccl_start and ccl_now) else None

    return {
        "symbol": symbol,
        "start_date": start_stamp,
        "end_date": date.today(),
        "start_price": start_price,
        "end_price": end_price,
        "units": units,
        "invested": invested,
        "remaining": remaining,
        "value": value,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "value_usd": value_usd,
        "invested_usd": invested_usd,
        "pnl_usd": pnl_usd,
        "pnl_usd_pct": pnl_usd_pct,
        "ccl_start": ccl_start,
        "ccl_now": ccl_now,
        "price_source": price_source,
    }


def render(analysis: Analysis, frame: pd.DataFrame) -> None:
    ui.page_header(
        "Simulador de inversión",
        "¿Cuánto tendría hoy si hubiera invertido antes? · sobre precios históricos reales",
        ui.data_status(analysis),
    )

    if frame is None or frame.empty:
        ui.empty_state("Sin datos con los filtros actuales")
        return

    symbols = sorted(frame["symbol"].dropna().unique())
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        symbol = st.selectbox("CEDEAR / acción", symbols, index=symbols.index("SPY") if "SPY" in symbols else 0)
    with col2:
        capital = st.number_input("Capital inicial (ARS)", min_value=10_000, max_value=1_000_000_000, value=100_000, step=10_000)
    with col3:
        preset = st.selectbox("Período", list(PRESETS), index=2)

    col4, col5 = st.columns([1, 3])
    with col4:
        custom = st.checkbox("Elegir fecha manual", value=False)
    with col5:
        start = (
            st.date_input("Fecha de inversión", value=date.today() - timedelta(days=PRESETS[preset]), max_value=date.today())
            if custom
            else date.today() - timedelta(days=PRESETS[preset])
        )

    result = simulate(symbol, capital, start, frame, analysis.ccl_history)
    if result is None:
        ui.banner(
            "No hay precios históricos suficientes para ese ticker y fecha. No se estiman valores faltantes.",
            "warn",
        )
        return

    if result["start_date"].date() != start:
        ui.banner(
            f"La fecha elegida ({start:%d/%m/%Y}) no tiene rueda con datos. Se usó el último cierre disponible: "
            f"<b>{result['start_date']:%d/%m/%Y}</b>.",
            "warn",
        )

    tone = "pos" if result["pnl"] >= 0 else "neg"
    ui.kpi_grid(
        [
            ui.kpi("Capital invertido", ui.fmt_money(result["invested"]), f'{result["units"]:,} unidades'.replace(",", "."), accent="#22D3EE"),
            ui.kpi("Valor actual", ui.fmt_money(result["value"]), result["price_source"], accent="#8B5CF6"),
            ui.kpi("Ganancia / pérdida", ui.fmt_money(result["pnl"]), ui.fmt_pct(result["pnl_pct"]), accent=("#16C784" if result["pnl"] >= 0 else "#EA3943")),
            ui.kpi("En dólares (CCL)", ui.fmt_money(result["pnl_usd"], 0, "US$") if result["pnl_usd"] is not None else "N/D",
                   f'Retorno USD {ui.fmt_pct(result["pnl_usd_pct"])}', accent="#F5B301"),
        ]
    )

    ui.section("Detalle de la operación", "")
    details = pd.DataFrame(
        {
            "Concepto": [
                "Ticker", "Fecha de compra usada", "Precio de compra", "Unidades compradas",
                "Efectivo remanente", "Precio actual", "Valor de la posición",
                "Resultado en ARS", "Resultado en USD (CCL)",
            ],
            "Valor": [
                result["symbol"],
                result["start_date"].strftime("%d/%m/%Y"),
                ui.fmt_money(result["start_price"], 2),
                f'{result["units"]:,}'.replace(",", "."),
                ui.fmt_money(result["remaining"], 2),
                ui.fmt_money(result["end_price"], 2) if result["end_price"] else "N/D",
                ui.fmt_money(result["value"]),
                f'{ui.fmt_money(result["pnl"])} ({ui.fmt_pct(result["pnl_pct"])})',
                f'{ui.fmt_money(result["pnl_usd"], 0, "US$")} ({ui.fmt_pct(result["pnl_usd_pct"])})'
                if result["pnl_usd"] is not None
                else "N/D",
            ],
        }
    )
    ui.styled_table(details, height=380)

    # ---------------------------------------------------------- escenarios
    ui.section("Mismo activo, distintos capitales", "Cantidades enteras de CEDEARs; el remanente no se invierte")
    scenarios = []
    for amount in sorted(set(CAPITALS + [int(capital)])):
        outcome = simulate(symbol, float(amount), start, frame, analysis.ccl_history)
        if outcome is None:
            continue
        scenarios.append(
            {
                "Capital": amount,
                "Unidades": outcome["units"],
                "Invertido": outcome["invested"],
                "Valor actual": outcome["value"],
                "Resultado": outcome["pnl"],
                "Retorno %": outcome["pnl_pct"],
                "Retorno USD %": outcome["pnl_usd_pct"],
            }
        )
    scenario_frame = pd.DataFrame(scenarios)
    ui.styled_table(
        scenario_frame,
        pct_columns=["Retorno %", "Retorno USD %"],
        height=min(320, 40 + 34 * len(scenario_frame)),
    )

    # ------------------------------------------------------------ gráfico
    series = data_layer.history_frame([symbol], result["start_date"].date())
    if not series.empty:
        ui.section("Evolución de la posición", "Precio de cierre desde la fecha de compra")
        st.plotly_chart(
            charts.evolution_chart(series, normalize=False),
            width="stretch",
            config={"displayModeBar": False},
        )

    ui.section("Supuestos y advertencias", "")
    st.markdown(
        """
* Se usan **precios de cierre reales** de las barras diarias de IOL. No se interpolan ni inventan precios.
* Se compran **unidades enteras**: el dinero que no alcanza para otra unidad queda fuera de la inversión.
* **No** se incluyen comisiones, derechos de mercado, impuestos, ni dividendos cobrados.
* El resultado en dólares usa el CCL de referencia diario (argentinadatos.com) al inicio y al final del período.
* Los precios históricos ya reflejan **splits y ajustes** del activo; un cambio de ratio del CEDEAR puede
  alterar la cantidad de certificados por acción y no está contemplado automáticamente.
* El rendimiento pasado no anticipa resultados futuros. Esta herramienta es educativa.
        """
    )
