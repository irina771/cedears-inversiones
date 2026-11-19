"""Gráficos interactivos (Plotly) con estética de plataforma financiera."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

GREEN = "#16C784"
RED = "#EA3943"
AMBER = "#F5B301"
CYAN = "#22D3EE"
VIOLET = "#8B5CF6"
MUTED = "#8A9BB4"
TEXT = "#E6EDF7"
GRID = "rgba(148,163,184,0.12)"
PANEL = "rgba(0,0,0,0)"

PALETTE = [CYAN, GREEN, AMBER, VIOLET, "#F97316", "#38BDF8", "#F472B6", "#A3E635", "#94A3B8", "#FB7185"]

FONT = "Inter, 'Segoe UI', system-ui, sans-serif"


def _layout(fig: go.Figure, height: int = 360, legend: bool = False, margin_top: int = 20) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor=PANEL,
        plot_bgcolor=PANEL,
        font=dict(family=FONT, color=TEXT, size=12),
        margin=dict(l=10, r=16, t=margin_top, b=10),
        hoverlabel=dict(bgcolor="#0E1626", bordercolor="#22304A", font=dict(color=TEXT, family=FONT)),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"),
        dragmode="pan",
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor="rgba(148,163,184,0.2)")
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor="rgba(148,163,184,0.2)")
    return fig


def _color(value: float) -> str:
    if value is None or pd.isna(value):
        return MUTED
    return GREEN if value > 0 else RED if value < 0 else MUTED


def variacion_bar(frame: pd.DataFrame, value_col: str = "variacion_diaria", top_n: int = 12, positive: bool = False, height: int | None = None) -> go.Figure:
    """Barras horizontales de variación (verdes o rojas)."""
    if frame is None or frame.empty:
        return empty_figure("Sin datos para graficar")

    data = frame.dropna(subset=[value_col]).copy()
    if data.empty:
        return empty_figure("Sin datos para graficar")
    data = data.nlargest(top_n, value_col) if positive else data.nsmallest(top_n, value_col)
    data = data.sort_values(value_col)

    colors = [GREEN if v > 0 else RED for v in data[value_col]]
    labels = data["symbol"].astype(str)
    text = [f"{v:+.2f}%" for v in data[value_col]]

    fig = go.Figure(
        go.Bar(
            x=data[value_col],
            y=labels,
            orientation="h",
            marker=dict(
                color=colors,
                line=dict(width=0),
                cornerradius=4,
                opacity=0.92,
            ),
            text=text,
            textposition="outside",
            textfont=dict(color=TEXT, size=11),
            customdata=np.stack(
                [data.get("company", pd.Series([""] * len(data))), data.get("monto_ars", pd.Series([np.nan] * len(data)))],
                axis=-1,
            ),
            hovertemplate="<b>%{y}</b> · %{customdata[0]}<br>Variación: %{x:+.2f}%<br>Monto: $%{customdata[1]:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(xaxis_title="Variación (%)", yaxis_title="")
    fig.update_xaxes(ticksuffix="%")
    return _layout(fig, height=height or max(280, 26 * len(data) + 80))


def breadth_donut(up: int, down: int, flat: int = 0) -> go.Figure:
    fig = go.Figure(
        go.Pie(
            labels=["Suben", "Bajan", "Sin cambio"],
            values=[up, down, flat],
            hole=0.68,
            marker=dict(colors=[GREEN, RED, "#334155"], line=dict(color="#0B1220", width=2)),
            textinfo="percent",
            textfont=dict(size=12, color=TEXT),
            hovertemplate="%{label}: %{value} CEDEARs<extra></extra>",
            sort=False,
        )
    )
    total = up + down + flat
    fig.add_annotation(
        text=f"<b>{up}/{total}</b><br><span style='font-size:11px;color:{MUTED}'>en suba</span>",
        showarrow=False,
        font=dict(size=16, color=TEXT),
    )
    return _layout(fig, height=260, margin_top=10)


def market_treemap(frame: pd.DataFrame) -> go.Figure:
    """Mapa de calor jerárquico: sector -> ticker, color = variación diaria."""
    if frame is None or frame.empty:
        return empty_figure("Sin datos")
    data = frame.dropna(subset=["variacion_diaria"]).copy()
    if data.empty:
        return empty_figure("Sin datos")

    data["monto_ars"] = data["monto_ars"].fillna(data["monto_ars"].median())
    data["label"] = data.apply(
        lambda r: f"{r['symbol']}<br><span style='font-size:10px'>{r['variacion_diaria']:+.2f}%</span>", axis=1
    )
    limit = float(np.nanmax(np.abs(data["variacion_diaria"]))) or 1.0

    fig = go.Figure(
        go.Treemap(
            labels=data["label"],
            parents=data["sector"].fillna("Otros"),
            values=data["monto_ars"].clip(lower=1),
            customdata=np.stack([data["company"], data["variacion_diaria"], data["var_7d"], data["var_30d"]], axis=-1),
            texttemplate="%{label}",
            hovertemplate=(
                "<b>%{label}</b><br>%{customdata[0]}<br>Día: %{customdata[1]:+.2f}%"
                "<br>7d: %{customdata[2]:+.2f}%<br>30d: %{customdata[3]:+.2f}%<extra></extra>"
            ),
            marker=dict(
                colors=data["variacion_diaria"],
                colorscale=[[0, RED], [0.5, "#1B2A41"], [1, GREEN]],
                cmin=-limit,
                cmax=limit,
                line=dict(color="#0B1220", width=1),
                colorbar=dict(title="Var. día", ticksuffix="%", thickness=10, len=0.7, tickfont=dict(color=MUTED)),
            ),
            textfont=dict(size=12, color="#F8FAFC"),
            tiling=dict(pad=2),
            branchvalues="total",
        )
    )
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    return _layout(fig, height=440, margin_top=10)


def heatmap_metrics(frame: pd.DataFrame, top_n: int = 30) -> go.Figure:
    """Heatmap ticker x métrica, con intensidad proporcional a cada variación."""
    if frame is None or frame.empty:
        return empty_figure("Sin datos")

    data = frame.copy()
    sort_col = "monto_ars" if "monto_ars" in data else "variacion_diaria"
    data = data.nlargest(min(top_n, len(data)), sort_col)
    cols = [("variacion_diaria", "Día"), ("var_7d", "7 días"), ("var_30d", "30 días")]
    matrix = data[[c for c, _ in cols]].to_numpy(dtype=float).T

    fig = go.Figure(
        go.Heatmap(
            z=matrix,
            x=data["symbol"],
            y=[label for _, label in cols],
            colorscale=[[0, RED], [0.5, "#1B2A41"], [1, GREEN]],
            zmid=0,
            hovertemplate="<b>%{x}</b> · %{y}: %{z:+.2f}%<extra></extra>",
            colorbar=dict(title="%", ticksuffix="%", thickness=10, len=0.8, tickfont=dict(color=MUTED)),
            xgap=2,
            ygap=2,
        )
    )
    fig.update_xaxes(tickangle=-45, tickfont=dict(size=10))
    return _layout(fig, height=320)


def risk_return_scatter(frame: pd.DataFrame, y_col: str = "var_30d") -> go.Figure:
    """Riesgo (volatilidad) vs rendimiento (variación)."""
    if frame is None or frame.empty:
        return empty_figure("Sin datos")
    data = frame.dropna(subset=["volatilidad_pct", y_col]).copy()
    if data.empty:
        return empty_figure("Sin datos suficientes")

    size = np.sqrt(data["monto_ars"].fillna(0).clip(lower=0))
    size = 6 + 34 * (size / size.max() if size.max() else 0)

    fig = go.Figure(
        go.Scatter(
            x=data["volatilidad_pct"],
            y=data[y_col],
            mode="markers+text",
            text=data["symbol"],
            textposition="top center",
            textfont=dict(size=9, color=MUTED),
            marker=dict(
                size=size,
                color=data["variacion_diaria"],
                colorscale=[[0, RED], [0.5, "#334155"], [1, GREEN]],
                cmid=0,
                line=dict(color="rgba(230,237,247,0.35)", width=1),
                opacity=0.9,
                colorbar=dict(title="Var. día", ticksuffix="%", thickness=10, len=0.7, tickfont=dict(color=MUTED)),
            ),
            customdata=np.stack([data["company"], data["var_7d"], data["volumen_relativo"]], axis=-1),
            hovertemplate=(
                "<b>%{text}</b> · %{customdata[0]}<br>Volatilidad: %{x:.2f}%<br>"
                f"Rendimiento: %{{y:+.2f}}%<br>7d: %{{customdata[1]:+.2f}}%<br>Vol. rel.: %{{customdata[2]:.2f}}x<extra></extra>"
            ),
        )
    )
    fig.add_hline(y=0, line=dict(color="rgba(148,163,184,0.4)", width=1, dash="dot"))
    fig.add_vline(x=float(data["volatilidad_pct"].median()), line=dict(color="rgba(148,163,184,0.3)", width=1, dash="dot"))
    fig.update_layout(xaxis_title="Volatilidad diaria (%)", yaxis_title="Rendimiento (%)")
    fig.update_xaxes(ticksuffix="%")
    fig.update_yaxes(ticksuffix="%")
    return _layout(fig, height=480)


def evolution_chart(series: pd.DataFrame, normalize: bool = True, title: str | None = None) -> go.Figure:
    """Líneas de evolución. ``series``: columnas date, symbol, value."""
    if series is None or series.empty:
        return empty_figure("Sin histórico disponible")

    fig = go.Figure()
    for index, (symbol, group) in enumerate(series.groupby("symbol")):
        group = group.sort_values("date")
        values = group["value"].astype(float)
        if normalize and len(values) and values.iloc[0]:
            values = values / values.iloc[0] * 100
        fig.add_trace(
            go.Scatter(
                x=group["date"],
                y=values,
                mode="lines",
                name=str(symbol),
                line=dict(color=PALETTE[index % len(PALETTE)], width=2),
                hovertemplate="<b>%{x|%d/%m/%Y}</b><br>" + str(symbol) + ": %{y:,.2f}<extra></extra>",
            )
        )
    fig.update_layout(yaxis_title="Base 100" if normalize else "Precio (ARS)", hovermode="x unified")
    return _layout(fig, height=440, legend=True, margin_top=40)


def distribution_histogram(frame: pd.DataFrame) -> go.Figure:
    if frame is None or frame.empty:
        return empty_figure("Sin datos")
    data = frame["variacion_diaria"].dropna()
    if data.empty:
        return empty_figure("Sin datos")

    colors = [GREEN if edge > 0 else RED for edge in data]
    fig = go.Figure(
        go.Histogram(
            x=data,
            nbinsx=28,
            marker=dict(color=colors, line=dict(width=0)),
            hovertemplate="Variación %{x:.1f}%<br>%{y} CEDEARs<extra></extra>",
        )
    )
    fig.add_vline(x=0, line=dict(color="rgba(230,237,247,0.5)", width=1, dash="dash"))
    fig.update_layout(xaxis_title="Variación diaria (%)", yaxis_title="Cantidad", bargap=0.05)
    fig.update_xaxes(ticksuffix="%")
    return _layout(fig, height=260)


def score_breakdown(frame: pd.DataFrame, top_n: int = 15) -> go.Figure:
    """Componentes normalizados del score por ticker."""
    if frame is None or frame.empty:
        return empty_figure("Sin datos")
    data = frame.dropna(subset=["score"]).nlargest(min(top_n, len(frame)), "score").sort_values("score")
    fig = go.Figure()
    fig.add_trace(go.Bar(y=data["symbol"], x=data["componente_tendencia"], name="Tendencia 7d", orientation="h", marker_color=CYAN))
    fig.add_trace(go.Bar(y=data["symbol"], x=data["componente_volumen"], name="Volumen rel.", orientation="h", marker_color=AMBER))
    fig.add_trace(go.Bar(y=data["symbol"], x=data["componente_volatilidad"], name="Volatilidad (resta)", orientation="h", marker_color=RED))
    fig.update_layout(barmode="group", xaxis_title="Percentil (0-100)")
    return _layout(fig, height=max(320, 26 * len(data) + 90), legend=True, margin_top=40)


def gauge(value: float, title: str, vmin: float = -100, vmax: float = 100, suffix: str = "%") -> go.Figure:
    color = GREEN if value >= 0 else RED
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=0 if pd.isna(value) else value,
            number=dict(suffix=suffix, font=dict(size=26, color=TEXT), valueformat="+.1f"),
            title=dict(text=title, font=dict(size=12, color=MUTED)),
            gauge=dict(
                axis=dict(range=[vmin, vmax], tickcolor=MUTED, tickfont=dict(size=9, color=MUTED)),
                bar=dict(color=color, thickness=0.55),
                bgcolor="rgba(148,163,184,0.08)",
                borderwidth=0,
                steps=[
                    dict(range=[vmin, 0], color="rgba(234,57,67,0.10)"),
                    dict(range=[0, vmax], color="rgba(22,199,132,0.10)"),
                ],
                threshold=dict(line=dict(color=TEXT, width=2), value=0),
            ),
        )
    )
    return _layout(fig, height=200, margin_top=10)


def grouped_bar(categories: list[str], series: dict[str, list[float]], y_title: str = "%", height: int = 400) -> go.Figure:
    """Barras agrupadas para comparar métricas entre activos o grupos."""
    fig = go.Figure()
    for index, (name, values) in enumerate(series.items()):
        fig.add_trace(
            go.Bar(
                x=categories,
                y=values,
                name=name,
                marker_color=PALETTE[index % len(PALETTE)],
                hovertemplate="<b>%{x}</b><br>" + name + ": %{y:+.2f}%<extra></extra>",
            )
        )
    fig.update_layout(barmode="group", yaxis_title=y_title, bargap=0.25, bargroupgap=0.08)
    fig.update_yaxes(ticksuffix="%")
    return _layout(fig, height=height, legend=True, margin_top=40)


def lollipop_score(frame: pd.DataFrame, top_n: int = 12, best: bool = True) -> go.Figure:
    """Ranking de score con barras finas y marcadores."""
    if frame is None or frame.empty:
        return empty_figure("Sin datos")
    data = frame.dropna(subset=["score"]).sort_values("score", ascending=not best).head(top_n)
    data = data.sort_values("score")
    colors = [GREEN if v >= 50 else RED for v in data["score"]]
    fig = go.Figure(
        go.Bar(
            x=data["score"],
            y=data["symbol"],
            orientation="h",
            marker=dict(color=colors, cornerradius=4),
            text=[f"{v:.0f}" for v in data["score"]],
            textposition="outside",
            textfont=dict(color=TEXT, size=11),
            hovertemplate="<b>%{y}</b><br>Score: %{x:.1f}/100<extra></extra>",
        )
    )
    fig.update_layout(xaxis_title="Score (0-100)", xaxis_range=[0, 105])
    return _layout(fig, height=max(280, 26 * len(data) + 80))


def empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=f"<span style='color:{MUTED}'>{message}</span>", showarrow=False, font=dict(size=13))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _layout(fig, height=200)
