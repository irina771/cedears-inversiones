"""Vista: empresas argentinas vs CEDEARs de empresas de EE.UU."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from cedears import charts
from cedears.market import Analysis
from ui import components as ui

IMPACT_TICKERS = ["GGAL", "YPF", "PAMP", "BMA", "SUPV", "TGS", "CEPU", "EDN", "TRAN", "ALUA", "TXAR", "BYMA"]


def render(analysis: Analysis, frame: pd.DataFrame) -> None:
    ui.page_header(
        "Empresas argentinas",
        "Acciones locales frente a CEDEARs de compañías de EE.UU. · no todo instrumento argentino es CEDEAR",
        ui.data_status(analysis),
    )

    if frame is None or frame.empty:
        ui.empty_state("Sin datos con los filtros actuales")
        return

    local = frame[frame["type"] == "Acción"].copy()
    cedears = frame[frame["type"] == "CEDEAR"].copy()

    ui.banner(
        "En el mercado local conviven <b>acciones argentinas</b> (YPF, GGAL, PAMP…) y <b>CEDEARs</b>, "
        "que son certificados locales que representan acciones extranjeras. Aquí se separan por tipo "
        "según el catálogo del proyecto, que se puede editar en <span class='mono'>data/cedears_universe.csv</span>.",
        "info",
    )

    if local.empty:
        ui.empty_state(
            "No se encontraron acciones argentinas en los datos actuales",
            "El screener de acciones locales puede no estar disponible con tu plan o panel; revisá Configuración y datos.",
        )
        return

    ui.kpi_grid(
        [
            ui.kpi("Acciones argentinas", str(len(local)), "tipo Acción", accent="#22D3EE"),
            ui.kpi("Var. mediana del día", ui.fmt_pct(local["variacion_diaria"].median()), "acciones locales", accent="#F5B301"),
            ui.kpi("Mejor del día", f'{local.nlargest(1, "variacion_diaria").iloc[0]["symbol"]}',
                   ui.fmt_pct(local["variacion_diaria"].max()), accent="#16C784"),
            ui.kpi("CEDEARs comparados", str(len(cedears)), "universo filtrado", accent="#8B5CF6"),
        ]
    )

    ui.section("Comparación entre empresas argentinas", "Seleccioná tickers para comparar variaciones")
    available = sorted(local["symbol"].unique())
    defaults = [t for t in IMPACT_TICKERS if t in available] or available[:4]
    selected = st.multiselect("Tickers argentinos", available, default=defaults, key="ar_tickers")

    chosen = local[local["symbol"].isin(selected)].drop_duplicates(subset="symbol")
    if not chosen.empty:
        st.plotly_chart(
            charts.grouped_bar(
                chosen["symbol"].tolist(),
                {
                    "Día": chosen["variacion_diaria"].fillna(0).tolist(),
                    "7 días": chosen["var_7d"].fillna(0).tolist(),
                    "30 días": chosen["var_30d"].fillna(0).tolist(),
                },
            ),
            width="stretch",
            config={"displayModeBar": False},
        )

    table = chosen[
        ["symbol", "company", "sector", "last", "variacion_diaria", "var_7d", "var_30d", "volumen_relativo", "tendencia"]
    ].copy()
    table.columns = ["Ticker", "Empresa", "Sector", "Precio", "Var. día", "7 días", "30 días", "Vol. rel.", "Tendencia"]
    ui.styled_table(
        table.sort_values("Var. día", ascending=False),
        pct_columns=["Var. día", "7 días", "30 días"],
        height=min(520, 40 + 34 * len(table)),
    )

    # -------------------------------------------------- argentinas vs EE.UU.
    ui.section(
        "Argentinas vs CEDEARs de EE.UU.",
        "Medianas del universo filtrado: el comportamiento de las acciones locales no replica al de los CEDEARs",
    )
    comparison = pd.DataFrame(
        {
            "Métrica": ["Var. día", "Var. 7d", "Var. 30d", "Volatilidad diaria", "Volumen relativo", "Desc. 52s"],
            "Acciones AR": [
                local["variacion_diaria"].median(),
                local["var_7d"].median(),
                local["var_30d"].median(),
                local["volatilidad_pct"].median(),
                local["volumen_relativo"].median(),
                local["descuento_52w"].median(),
            ],
            "CEDEARs EE.UU.": [
                cedears["variacion_diaria"].median() if not cedears.empty else None,
                cedears["var_7d"].median() if not cedears.empty else None,
                cedears["var_30d"].median() if not cedears.empty else None,
                cedears["volatilidad_pct"].median() if not cedears.empty else None,
                cedears["volumen_relativo"].median() if not cedears.empty else None,
                cedears["descuento_52w"].median() if not cedears.empty else None,
            ],
        }
    )
    left, right = st.columns([3, 2])
    with left:
        ui.styled_table(comparison.set_index("Métrica").reset_index(), height=300, decimals=2)
    with right:
        st.plotly_chart(
            charts.grouped_bar(
                ["Rendimiento 7d", "Rendimiento 30d"],
                {
                    "Acciones AR": [local["var_7d"].median() or 0, local["var_30d"].median() or 0],
                    "CEDEARs EE.UU.": [
                        cedears["var_7d"].median() if not cedears.empty else 0,
                        cedears["var_30d"].median() if not cedears.empty else 0,
                    ],
                },
                height=300,
            ),
            width="stretch",
            config={"displayModeBar": False},
        )

    # ------------------------------------------------------------- sectores
    ui.section("Ranking por sector", "Mejores y peores variaciones del día dentro de cada sector")
    sector_summary = (
        frame.groupby("sector")
        .agg(
            instrumentos=("symbol", "count"),
            var_mediana=("variacion_diaria", "median"),
            var_7d=("var_7d", "median"),
            var_30d=("var_30d", "median"),
            mejor=("variacion_diaria", "max"),
        )
        .reset_index()
        .sort_values("var_mediana", ascending=False)
    )
    sector_summary.columns = ["Sector", "Instrumentos", "Var. mediana día", "7 días", "30 días", "Mejor var. día"]
    ui.styled_table(
        sector_summary,
        pct_columns=["Var. mediana día", "7 días", "30 días", "Mejor var. día"],
        height=min(460, 40 + 34 * len(sector_summary)),
    )

    ui.disclaimer(
        "El catálogo de tipos de activo y sectores es editable. Los ADR de empresas argentinas cotizan en "
        "Nueva York y sus ratios de conversión pueden diferir de 1:1; por eso no se comparan automáticamente "
        "contra su ADR sin verificar el ratio."
    )
