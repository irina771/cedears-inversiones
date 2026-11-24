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
        <div class="page-head">
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
    <div class="kpi" style="--accent:{accent}">
      <div class="kpi-label">{html.escape(label)}</div>
      <div class="kpi-value">{value}</div>
      {delta_html}
      {hint_html}
    </div>
    """
    )


def kpi_grid(cards: list[str]) -> None:
    st.markdown('<div class="kpi-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)


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
