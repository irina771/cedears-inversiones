"""Tema visual: paleta, tipografía y CSS inyectado en Streamlit."""

from __future__ import annotations

import streamlit as st

BG = "#060B18"
BG_SOFT = "#0A1120"
PANEL = "#0E1626"
PANEL_ALT = "#111C30"
BORDER = "#1E2C44"
TEXT = "#E6EDF7"
MUTED = "#8A9BB4"
GREEN = "#16C784"
RED = "#EA3943"
AMBER = "#F5B301"
CYAN = "#22D3EE"
VIOLET = "#8B5CF6"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap');

:root {
  --bg: #060B18;
  --panel: #0E1626;
  --border: #1E2C44;
  --text: #E6EDF7;
  --muted: #8A9BB4;
  --green: #16C784;
  --red: #EA3943;
  --amber: #F5B301;
  --cyan: #22D3EE;
}

html, body, .stApp, [data-testid="stAppViewContainer"] {
  background: radial-gradient(1200px 600px at 15% -10%, #0D1B33 0%, #060B18 45%, #04070F 100%) !important;
  color: var(--text);
  font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
}

[data-testid="stHeader"] { background: transparent; height: 0; }
[data-testid="stToolbar"] { right: 1rem; }
.block-container { padding: 1.1rem 1.6rem 2.2rem 1.6rem; max-width: 1500px; }

section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #070D1A 0%, #050912 100%);
  border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] .block-container { padding: 1rem 0.9rem; }

h1, h2, h3, h4 { color: var(--text); letter-spacing: -0.02em; }
p, span, label, div { color: var(--text); }
a { color: var(--cyan); }

/* Navegación lateral */
section[data-testid="stSidebar"] div[role="radiogroup"] { gap: 0.15rem; }
section[data-testid="stSidebar"] div[role="radiogroup"] label {
  padding: 0.45rem 0.6rem;
  border-radius: 9px;
  border: 1px solid transparent;
  transition: all 0.15s ease;
  cursor: pointer;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
  background: rgba(34,211,238,0.07);
  border-color: rgba(34,211,238,0.22);
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
  background: linear-gradient(90deg, rgba(34,211,238,0.16), rgba(34,211,238,0.04));
  border-color: rgba(34,211,238,0.45);
  box-shadow: inset 3px 0 0 var(--cyan);
}
section[data-testid="stSidebar"] div[role="radiogroup"] label p { font-size: 0.86rem; font-weight: 500; }
section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child { display: none; }

/* Tarjetas KPI */
.kpi-grid { display: grid; gap: 0.7rem; grid-template-columns: repeat(auto-fit, minmax(168px, 1fr)); }
.kpi {
  background: linear-gradient(160deg, rgba(20,32,54,0.95), rgba(10,17,32,0.95));
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 0.85rem 0.95rem;
  position: relative;
  overflow: hidden;
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}
.kpi:hover { transform: translateY(-2px); border-color: rgba(34,211,238,0.35); box-shadow: 0 10px 26px rgba(0,0,0,0.35); }
.kpi::before { content: ""; position: absolute; inset: 0 auto 0 0; width: 3px; background: var(--accent, #22D3EE); opacity: 0.85; }
.kpi-label { font-size: 0.7rem; letter-spacing: 0.09em; text-transform: uppercase; color: var(--muted); font-weight: 600; }
.kpi-value { font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 1.42rem; font-weight: 600; margin-top: 0.25rem; line-height: 1.15; }
.kpi-hint { font-size: 0.72rem; color: var(--muted); margin-top: 0.28rem; line-height: 1.25; }
.kpi-delta { font-size: 0.78rem; font-weight: 600; margin-top: 0.15rem; font-family: 'JetBrains Mono', monospace; }
.pos { color: var(--green) !important; }
.neg { color: var(--red) !important; }
.neu { color: var(--muted) !important; }

/* Encabezados de sección */
.section-head { display: flex; align-items: baseline; gap: 0.7rem; margin: 1.35rem 0 0.55rem 0; }
.section-title { font-size: 1.08rem; font-weight: 650; letter-spacing: -0.01em; }
.section-sub { font-size: 0.78rem; color: var(--muted); }
.accent-bar { width: 4px; height: 18px; border-radius: 4px; background: linear-gradient(180deg, var(--cyan), #0E7490); }

/* Pills / badges */
.pill { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.16rem 0.55rem; border-radius: 999px; font-size: 0.71rem; font-weight: 600; border: 1px solid; }
.pill-green { color: #6EE7B7; border-color: rgba(22,199,132,0.45); background: rgba(22,199,132,0.12); }
.pill-red { color: #FCA5A5; border-color: rgba(234,57,67,0.45); background: rgba(234,57,67,0.12); }
.pill-amber { color: #FCD34D; border-color: rgba(245,179,1,0.45); background: rgba(245,179,1,0.12); }
.pill-cyan { color: #67E8F9; border-color: rgba(34,211,238,0.45); background: rgba(34,211,238,0.10); }
.pill-muted { color: #CBD5E1; border-color: rgba(148,163,184,0.35); background: rgba(148,163,184,0.10); }

/* Banners de estado */
.banner { border-radius: 12px; padding: 0.7rem 0.9rem; font-size: 0.83rem; border: 1px solid; margin-bottom: 0.7rem; }
.banner-warn { background: rgba(245,179,1,0.10); border-color: rgba(245,179,1,0.40); color: #FDE68A; }
.banner-danger { background: rgba(234,57,67,0.10); border-color: rgba(234,57,67,0.45); color: #FECACA; }
.banner-info { background: rgba(34,211,238,0.07); border-color: rgba(34,211,238,0.30); color: #A5F3FC; }

/* Marca */
.brand { display: flex; align-items: center; gap: 0.6rem; padding: 0.2rem 0.1rem 0.9rem 0.1rem; border-bottom: 1px solid var(--border); margin-bottom: 0.9rem; }
.brand-mark { width: 34px; height: 34px; border-radius: 10px; background: linear-gradient(135deg, #22D3EE, #2563EB 60%, #7C3AED); display: grid; place-items: center; font-weight: 700; color: #04121F; font-size: 0.9rem; box-shadow: 0 6px 18px rgba(34,211,238,0.25); }
.brand-title { font-size: 0.98rem; font-weight: 700; letter-spacing: -0.01em; line-height: 1.1; }
.brand-sub { font-size: 0.66rem; color: var(--muted); letter-spacing: 0.14em; text-transform: uppercase; }

/* Cabecera del dashboard */
.page-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; margin-bottom: 0.9rem; flex-wrap: wrap; }
.page-title { font-size: 1.55rem; font-weight: 700; letter-spacing: -0.03em; margin: 0; }
.page-sub { font-size: 0.82rem; color: var(--muted); margin-top: 0.2rem; }
.status-chip { display: inline-flex; align-items: center; gap: 0.45rem; padding: 0.35rem 0.7rem; border-radius: 10px; background: rgba(22,199,132,0.08); border: 1px solid rgba(22,199,132,0.35); font-size: 0.74rem; color: #A7F3D0; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: #16C784; box-shadow: 0 0 0 4px rgba(22,199,132,0.15); }

/* Streamlit widgets */
.stButton > button, .stDownloadButton > button {
  background: linear-gradient(135deg, rgba(34,211,238,0.18), rgba(37,99,235,0.16));
  border: 1px solid rgba(34,211,238,0.35);
  color: #E6F6FF; border-radius: 10px; font-weight: 600; font-size: 0.82rem;
  padding: 0.42rem 0.9rem; transition: all 0.15s ease;
}
.stButton > button:hover { border-color: rgba(34,211,238,0.75); box-shadow: 0 0 0 3px rgba(34,211,238,0.10); }
[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; }

div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, .stTextInput input, .stNumberInput input {
  background: #0B1322 !important; border-color: #1E2C44 !important; color: var(--text) !important;
}
.stSlider [data-baseweb="slider"] div[role="slider"] { background: var(--cyan); }
[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
[data-testid="stDataFrame"] * { font-family: 'Inter', sans-serif; }
[data-testid="stExpander"] { border: 1px solid var(--border); border-radius: 12px; background: rgba(14,22,38,0.55); }
[data-testid="stExpander"] summary { font-size: 0.85rem; font-weight: 600; }
hr { border-color: var(--border); }
.stTabs [data-baseweb="tab-list"] { gap: 0.4rem; }
.stTabs [data-baseweb="tab"] { background: rgba(14,22,38,0.8); border: 1px solid var(--border); border-radius: 10px; padding: 0.3rem 0.8rem; }
.stTabs [aria-selected="true"] { border-color: rgba(34,211,238,0.5); color: var(--cyan) !important; }
.small { font-size: 0.75rem; color: var(--muted); }
.mono { font-family: 'JetBrains Mono', monospace; }
</style>
"""


def inject_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
