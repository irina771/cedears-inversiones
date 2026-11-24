"""Tema visual: paleta Base44-like, tipografía Wix Madefor y CSS de la app."""

from __future__ import annotations

import streamlit as st

BG = "#09090B"
BG_SOFT = "#0D0D10"
PANEL = "#111117"
PANEL_ALT = "#13131B"
BORDER = "#2A2828"
TEXT = "#FAFAFA"
MUTED = "#8A8A8A"
GREEN = "#16C784"
RED = "#EA3943"
AMBER = "#F5B301"
CYAN = "#22D3EE"
VIOLET = "#8B5CF6"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Wix+Madefor+Text:wght@400;500;600;700&family=Wix+Madefor+Display:wght@400;500;600;700&family=Azeret+Mono:wght@400;500;700&display=swap');

:root {
  --bg: #09090B;
  --panel: #111117;
  --panel-alt: #13131B;
  --border: #2A2828;
  --text: #FAFAFA;
  --muted: #8A8A8A;
  --green: #16C784;
  --red: #EA3943;
  --amber: #F5B301;
  --cyan: #22D3EE;
  --violet: #8B5CF6;
}

html, body, .stApp, [data-testid="stAppViewContainer"] {
  background: #09090B !important;
  color: var(--text);
  font-family: 'Wix Madefor Text', system-ui, sans-serif;
}

[data-testid="stHeader"] { background: transparent; height: 0; }
[data-testid="stToolbar"] { right: 1rem; }
.block-container { padding: 1.1rem 1.6rem 2.2rem 1.6rem; max-width: 1500px; }

section[data-testid="stSidebar"] {
  background: #09090B;
  border-right: none;
  border-left: none;
}
section[data-testid="stSidebar"] .block-container { padding: 1rem 0.9rem; }

/* NavBar: quitar círculos del radio, dejar iconos */
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div:first-child { display: none; }
.status-chip .dot { display: none; }

/* NavBar: sidebar a la dcha, collapsible */
.stAppViewContainer { flex-direction: row-reverse; }
/* Sin borde cuando está colapsada (evita la línea de 1px) */
section[data-testid="stSidebar"][data-collapsed="true"] { border: none; overflow: hidden; }
section[data-testid="stSidebar"]:not([data-collapsed="true"]) {
  border-right: none;
  border-left: 1px solid var(--border);
  width: 264px !important;
  min-width: 264px !important;
}

/* NavBar: sin animación de apertura/cierre */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div,
section[data-testid="stSidebar"] * { transition: none !important; }

/* Icono de hamburguesa: oculta el icono de flecha de Streamlit */
button[data-testid="stExpandSidebarButton"],
section[data-testid="stSidebar"] button[kind="headerNoPadding"] {
  display: grid;
  place-items: center;
  padding: 0.4rem;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
}
button[data-testid="stExpandSidebarButton"] > span,
section[data-testid="stSidebar"] button[kind="headerNoPadding"] > span { display: none; }
section[data-testid="stSidebar"] button[kind="headerNoPadding"] { visibility: visible !important; opacity: 1 !important; }
button[data-testid="stExpandSidebarButton"]::before,
section[data-testid="stSidebar"] button[kind="headerNoPadding"]::before {
  content: "☰";
  font-size: 16px;
  line-height: 1;
  color: var(--text);
}
/* El toggle de expandir: hamburguesa fija arriba a la dcha */
button[data-testid="stExpandSidebarButton"] {
  position: fixed;
  top: 0.9rem;
  right: 1rem;
  z-index: 999991;
}

/* Heatmap del mercado (celdas HTML) */
.heat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(62px, 1fr)); gap: 3px; align-items: stretch; }
.heat-cell {
  display: flex; flex-direction: column; justify-content: center; gap: 1px;
  border-radius: 3px; padding: 3px 5px;
  background: rgba(255,255,255,0.035);
  color: #F8FAFC; font-size: 10px; font-weight: 600; line-height: 1.2;
  transition: background 0.12s ease;
}
.heat-cell:hover { background: rgba(255,255,255,0.06); }
.heat-cell .heat-sym { font-size: 10px; font-weight: 700; }
.heat-cell .heat-chg { font-size: 9px; opacity: 0.92; }
.heat-empty { color: var(--muted); font-size: 0.85rem; padding: 1.2rem; text-align: center; }

h1, h2, h3, h4 {
  color: var(--text);
  font-family: 'Wix Madefor Display', 'Wix Madefor Text', system-ui, sans-serif;
  letter-spacing: -0.01em;
}
p, span, label, div { color: var(--text); }
a { color: var(--cyan); }

/* Navegación lateral */
section[data-testid="stSidebar"] div[role="radiogroup"] { gap: 0.15rem; }
section[data-testid="stSidebar"] div[role="radiogroup"] label {
  padding: 0.42rem 0.62rem;
  border-radius: 4px;
  border: 1px solid transparent;
  transition: all 0.12s ease;
  cursor: pointer;
  font-family: 'Wix Madefor Text', system-ui, sans-serif;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
  background: rgba(255,255,255,0.05);
  border-color: var(--border);
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
  background: rgba(255,255,255,0.08);
  border-color: rgba(255,255,255,0.25);
}
section[data-testid="stSidebar"] div[role="radiogroup"] label p { font-size: 0.86rem; font-weight: 500; }
section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child { display: none; }

/* Tarjetas KPI */
.kpi-grid { display: grid; gap: 0.7rem; grid-template-columns: repeat(auto-fit, minmax(168px, 1fr)); }
.kpi {
  background: rgba(255,255,255,0.035);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.8rem 0.9rem;
  position: relative;
  overflow: hidden;
  transition: transform 0.12s ease, border-color 0.12s ease;
}
.kpi:hover { transform: translateY(-1px); border-color: rgba(255,255,255,0.25); }
.kpi::before { content: ""; position: absolute; inset: 0 auto 0 0; width: 2px; background: var(--accent, #22D3EE); opacity: .85; }
.kpi-label {
  font-family: 'Wix Madefor Text', system-ui, sans-serif;
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 600;
}
.kpi-value {
  font-family: 'Azeret Mono', ui-monospace, monospace;
  font-size: 1.35rem;
  font-weight: 600;
  margin-top: 0.2rem;
  line-height: 1.15;
}
.kpi-hint { font-size: 0.7rem; color: var(--muted); margin-top: 0.2rem; line-height: 1.25; }
.kpi-delta { font-size: 0.72rem; font-weight: 600; margin-top: 0.12rem; font-family: 'Azeret Mono', monospace; }
.pos { color: var(--green) !important; }
.neg { color: var(--red) !important; }
.neu { color: var(--muted) !important; }

/* Encabezados de sección */
.section-head { display: flex; align-items: baseline; gap: 0.7rem; margin: 1.35rem 0 0.55rem 0; }
.section-title { font-size: 1.06rem; font-weight: 650; letter-spacing: -0.01em; }
.section-sub { font-size: 0.78rem; color: var(--muted); }
.accent-bar { width: 3px; height: 18px; border-radius: 2px; background: var(--cyan); }

/* Pills / badges */
.pill { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600; border: 1px solid; }
.pill-green { color: var(--green); border-color: rgba(22,199,132,0.5); background: rgba(22,199,132,0.08); }
.pill-red { color: var(--red); border-color: rgba(234,57,67,0.5); background: rgba(234,57,67,0.08); }
.pill-amber { color: var(--amber); border-color: rgba(245,179,1,0.5); background: rgba(245,179,1,0.08); }
.pill-cyan { color: var(--cyan); border-color: rgba(34,211,238,0.5); background: rgba(34,211,238,0.08); }
.pill-muted { color: var(--muted); border-color: rgba(138,138,138,0.35); background: rgba(138,138,138,0.08); }

/* Banners de estado */
.banner { border-radius: 6px; padding: 0.6rem 0.8rem; font-size: 0.8rem; border: 1px solid; margin-bottom: 0.6rem; }
.banner-warn { background: rgba(245,179,1,0.08); border-color: rgba(245,179,1,0.4); color: #FDE68A; }
.banner-danger { background: rgba(234,57,67,0.08); border-color: rgba(234,57,67,0.4); color: #FECACA; }
.banner-info { background: rgba(34,211,238,0.07); border-color: rgba(34,211,238,0.25); color: #A5F3FC; }

/* Marca */
.brand { display: flex; align-items: center; gap: 0.6rem; padding: 0.2rem 0.1rem 0.9rem 0.1rem; border-bottom: 1px solid var(--border); margin-bottom: 0.9rem; }
.brand-mark {
  width: 30px; height: 30px; border-radius: 6px;
  background: linear-gradient(135deg, #22D3EE, #2563EB 60%, #7C3AED);
  display: grid; place-items: center; font-weight: 700;
  color: #04121F; font-size: 0.85rem; box-shadow: 0 4px 14px rgba(34,211,238,0.2);
}
.brand-title { font-size: 0.95rem; font-weight: 700; letter-spacing: -0.01em; line-height: 1.1; }
.brand-sub { font-size: 0.62rem; color: var(--muted); letter-spacing: 0.12em; text-transform: uppercase; }

/* Cabecera del dashboard */
.page-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; margin-bottom: 0.9rem; flex-wrap: wrap; }
.page-title { font-size: 1.45rem; font-weight: 700; letter-spacing: -0.03em; margin: 0; }
.page-sub { font-size: 0.8rem; color: var(--muted); margin-top: 0.15rem; }
.status-chip { display: inline-flex; align-items: center; gap: 0.45rem; padding: 0.3rem 0.7rem; border-radius: 6px; background: rgba(22,199,132,0.08); border: 1px solid rgba(22,199,132,0.35); font-size: 0.74rem; color: #A7F3D0; }
.dot { width: 6px; height: 6px; border-radius: 50%; background: #16C784; box-shadow: 0 0 0 4px rgba(22,199,132,0.12); }

/* Streamlit widgets */
.stButton > button, .stDownloadButton > button {
  background: rgba(255,255,255,0.06);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 4px;
  font-weight: 500;
  font-size: 0.82rem;
  padding: 0.4rem 0.9rem;
  transition: border-color .12s ease, background .12s ease;
}
.stButton > button:hover { border-color: rgba(255,255,255,0.3); background: rgba(255,255,255,0.1); }
[data-testid="stMetricValue"] { font-family: 'Azeret Mono', monospace; }

div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, .stTextInput input, .stNumberInput input {
  background: #0B1322 !important; border-color: var(--border) !important; color: var(--text) !important;
}
.stSlider [data-baseweb="slider"] div[role="slider"] { background: var(--cyan); }
[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
[data-testid="stDataFrame"] * { font-family: 'Wix Madefor Text', sans-serif; }
[data-testid="stExpander"] { border: 1px solid var(--border); border-radius: 6px; background: rgba(14,22,38,0.5); }
[data-testid="stExpander"] summary { font-size: 0.85rem; font-weight: 600; }
hr { border-color: var(--border); }
.stTabs [data-baseweb="tab-list"] { gap: 0.4rem; }
.stTabs [data-baseweb="tab"] { background: rgba(14,22,38,0.8); border: 1px solid var(--border); border-radius: 4px; padding: 0.3rem 0.8rem; }
.stTabs [aria-selected="true"] { border-color: rgba(34,211,238,0.5); color: var(--cyan) !important; }
.small { font-size: 0.75rem; color: var(--muted); }
.mono { font-family: 'Azeret Mono', monospace; }
</style>
"""


def inject_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
