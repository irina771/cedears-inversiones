"""Componentes reutilizables de la interfaz."""

from __future__ import annotations

import html
import re
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

from ui import theme

ND = "N/D"


def compact(markup: str) -> str:
    """Colapsa saltos de línea: Markdown interpreta la indentación como código."""
    return re.sub(r"\s*\n\s*", "", markup).strip()


def fmt_num(value, decimals: int = 2, suffix: str = "", prefix: str = "") -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)) or pd.isna(value):
        return ND
    if isinstance(value, (int, np.integer)):
        return f"{prefix}{value:,}{suffix}".replace(",", ".")
    text = f"{prefix}{value:,.{decimals}f}{suffix}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(value, decimals: int = 2, signed: bool = True) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)) or pd.isna(value):
        return ND
    pattern = f"{{:+.{decimals}f}}%" if signed else f"{{:.{decimals}f}}%"
    return pattern.format(value).replace(".", ",")


def fmt_money(value, decimals: int = 0, symbol: str = "$") -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)) or pd.isna(value):
        return ND
    return f"{symbol}{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def tone_for(value) -> str:
    if value is None or pd.isna(value):
        return "neu"
    return "pos" if value > 0 else "neg" if value < 0 else "neu"


def pill(text: str, kind: str = "muted") -> str:
    return f'<span class="pill pill-{kind}">{html.escape(text)}</span>'


def classification_pill(label: str) -> str:
    mapping = {
        "Verde · Oportunidad potencial": "green",
        "Amarillo · Neutral": "amber",
        "Rojo · Riesgo": "red",
    }
    return pill(label, mapping.get(label, "muted"))


def trend_pill(trend: str) -> str:
    mapping = {"Positiva": "green", "Negativa": "red", "Lateral": "cyan", "N/D": "muted"}
    label = "Tendencia N/D" if trend in ("N/D", "") else f"Tendencia {trend.lower()}"
    return pill(label, mapping.get(trend, "muted"))


def page_header(title: str, subtitle: str, status_html: str | None = None) -> None:
    status = f'<div class="status-chip"><span class="dot"></span>{status_html}</div>' if status_html else ""
    st.markdown(
        compact(
            f"""
        <div class="page-head notranslate">
          <div>
            <div class="page-title">{html.escape(title)}</div>
            <div class="page-sub">{subtitle}</div>
          </div>
          {status}
        </div>
        """
        ),
        unsafe_allow_html=True,
    )


def section(title: str, subtitle: str = "") -> None:
    sub = f'<div class="section-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        compact(
            f"""
        <div class="section-head">
          <div class="accent-bar"></div>
          <div class="section-title">{title}</div>
          {sub}
        </div>
        """
        ),
        unsafe_allow_html=True,
    )


def kpi(label: str, value: str, hint: str = "", delta: str = "", delta_tone: str = "neu", accent: str = theme.CYAN) -> str:
    delta_html = f'<div class="kpi-delta {delta_tone}">{delta}</div>' if delta else ""
    hint_html = f'<div class="kpi-hint">{hint}</div>' if hint else ""
    return compact(
        f"""
    <div class="kpi notranslate" style="--accent:{accent}">
      <div class="kpi-label">{html.escape(label)}</div>
      <div class="kpi-value">{value}</div>
      {delta_html}
      {hint_html}
    </div>
    """
    )


def kpi_grid(cards: list[str], columns: int | None = None) -> None:
    style = f' style="grid-template-columns:repeat({columns},minmax(0,1fr))"' if columns else ""
    st.markdown(f'<div class="kpi-grid"{style}>' + "".join(cards) + "</div>", unsafe_allow_html=True)


def _sparkline(values: list[float], width: int = 620, height: int = 62, pad: int = 4) -> str:
    """Mini serie SVG (sin dependencias de plotly.js)."""
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    step = (width - 2 * pad) / (len(values) - 1)
    points = []
    for i, value in enumerate(values):
        x = pad + i * step
        y = height - pad - (value - lo) / span * (height - 2 * pad)
        points.append(f"{x:.1f},{y:.1f}")

    rising = values[-1] >= values[0]
    stroke = theme.GREEN if rising else theme.RED
    fill = "rgba(22,199,132,0.12)" if rising else "rgba(234,57,67,0.12)"
    area = f"{width - pad},{height - pad} {pad},{height - pad}"
    return compact(
        f"""
    <svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" role="img" aria-label="Serie histórica CCL">
      <polygon points="{points[0]} {' '.join(points)} {area}" fill="{fill}" stroke="none"></polygon>
      <polyline points="{' '.join(points)}" fill="none" stroke="{stroke}" stroke-width="1.8"
                stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"></polyline>
    </svg>
    """
    )


def ccl_card(quote, history: pd.DataFrame, days: int = 30) -> None:
    """Tarjeta del CCL: valor, variación del período y serie a lo largo."""
    hist = pd.DataFrame() if history is None else history.copy()
    if not hist.empty and "ccl" in hist.columns:
        if "date" in hist.columns:
            hist = hist.sort_values("date")
        hist = hist.dropna(subset=["ccl"]).tail(days)
    series = [float(v) for v in hist["ccl"].tolist()] if not hist.empty else []

    last = quote.value if quote is not None and quote.value is not None else (series[-1] if series else None)
    change = (series[-1] / series[0] - 1) * 100 if len(series) >= 2 and series[0] else None
    tone = "pos" if (change or 0) > 0 else "neg" if (change or 0) < 0 else "neu"
    caption = f"últimos {len(series)} días" if series else "sin serie histórica"
    spark = _sparkline(series)

    st.markdown(
        compact(
            f"""
    <div class="ccl-card notranslate">
      <div class="ccl-info">
        <div class="kpi-label">Dólar CCL</div>
        <div class="ccl-value">{fmt_money(last, 1)}</div>
        <div class="ccl-change {tone}">{('30d ' + fmt_pct(change)) if change is not None else ND}</div>
        <div class="ccl-caption">{caption}</div>
      </div>
      <div class="ccl-spark">{spark}</div>
    </div>
    """
        ),
        unsafe_allow_html=True,
    )


def rank_list(frame: pd.DataFrame, value_col: str = "variacion_diaria") -> str:
    """Ranking como cards (posición, ticker, empresa y variación)."""
    if frame is None or frame.empty:
        return '<div class="rank-empty">Sin datos</div>'
    cards = []
    for pos, (_, row) in enumerate(frame.iterrows(), start=1):
        value = row.get(value_col)
        tone = "pos" if value > 0 else "neg" if value < 0 else "neu"
        company = row.get("company")
        company = "" if company is None or pd.isna(company) else str(company)
        cards.append(
            compact(
                f"""
        <div class="rank-item">
          <div class="rank-pos">{pos}</div>
          <div class="rank-main">
            <div class="rank-ticker">{html.escape(str(row.get('symbol', '')))}</div>
            <div class="rank-company">{html.escape(company)}</div>
          </div>
          <div class="rank-var {tone}">{fmt_pct(value)}</div>
        </div>
        """
            )
        )
    return '<div class="rank-list notranslate">' + "".join(cards) + "</div>"


def banner(text: str, kind: str = "info") -> None:
    st.markdown(compact(f'<div class="banner banner-{kind}">{text}</div>'), unsafe_allow_html=True)


def data_status(analysis, extra: str = "") -> str:
    """Texto de frescura de datos para la cabecera."""
    if analysis is None or analysis.frame is None:
        return "sin datos"
    stamp = analysis.fetched_at.astimezone().strftime("%d/%m/%Y %H:%M")
    suffix = f" · {extra}" if extra else ""
    return f"{analysis.source} · actualizado {stamp}{suffix}"


def pct_style(value) -> str:
    if value is None or pd.isna(value):
        return f"color: {theme.MUTED}"
    if value > 0:
        return f"color: {theme.GREEN}"
    if value < 0:
        return f"color: {theme.RED}"
    return f"color: {theme.MUTED}"


def heat_style(value) -> str:
    """Fondo proporcional a la variación (verde/rojo), texto legible."""
    if value is None or pd.isna(value):
        return ""
    intensity = min(abs(float(value)) / 6, 1)
    if value > 0:
        return f"background-color: rgba(22,199,132,{0.10 + 0.35 * intensity:.2f}); color: #D1FAE5"
    if value < 0:
        return f"background-color: rgba(234,57,67,{0.10 + 0.35 * intensity:.2f}); color: #FEE2E2"
    return ""


def styled_table(
    frame: pd.DataFrame,
    pct_columns: list[str] | None = None,
    heat_columns: list[str] | None = None,
    height: int | None = None,
    column_config: dict | None = None,
    decimals: int = 2,
    key: str | None = None,
) -> None:
    """DataFrame con formato español, colores y orden/búsqueda nativos."""
    if frame is None or frame.empty:
        banner("No hay datos para mostrar con los filtros seleccionados.", "info")
        return

    pct_columns = [c for c in (pct_columns or []) if c in frame.columns]
    heat_columns = [c for c in (heat_columns or []) if c in frame.columns]
    display = frame.copy()

    formatters = {}
    for column in display.columns:
        if column in pct_columns or column in heat_columns:
            formatters[column] = lambda v: ND if pd.isna(v) else f"{v:+.2f}%".replace(".", ",")
        elif pd.api.types.is_float_dtype(display[column]):
            formatters[column] = lambda v, d=decimals: ND if pd.isna(v) else f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")

    styler = display.style
    if formatters:
        styler = styler.format(formatters, na_rep=ND)
    if pct_columns:
        styler = styler.map(pct_style, subset=pct_columns)
    if heat_columns:
        styler = styler.map(heat_style, subset=heat_columns)

    st.dataframe(
        styler,
        width="stretch",
        hide_index=True,
        height=height,
        column_config=column_config or None,
        key=key,
    )


def disclaimer(text: str) -> None:
    st.markdown(f'<div class="small" style="margin-top:0.4rem">{text}</div>', unsafe_allow_html=True)


def empty_state(message: str, hint: str = "") -> None:
    st.markdown(
        compact(
            f"""
        <div style="text-align:center;padding:2.4rem 1rem;border:1px dashed {theme.BORDER};border-radius:8px;background:rgba(255,255,255,0.03)">
          <div style="font-size:1rem;font-weight:600;margin-bottom:0.35rem">{message}</div>
          <div class="small">{hint}</div>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )


def now_label() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")
