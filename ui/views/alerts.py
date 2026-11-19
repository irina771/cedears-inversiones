"""Vista: alertas configurables."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from cedears import signals
from cedears.market import Analysis
from ui import components as ui


def render(analysis: Analysis, frame: pd.DataFrame) -> None:
    ui.page_header(
        "Alertas",
        "Umbrales personalizables evaluados sobre las cotizaciones actuales",
        ui.data_status(analysis),
    )

    if frame is None or frame.empty:
        ui.empty_state("Sin datos con los filtros actuales")
        return

    with st.expander("Configurar umbrales", expanded=True):
        col1, col2, col3 = st.columns(3)
        drop_warn = col1.number_input("Caída > (%)", min_value=0.5, max_value=50.0, value=5.0, step=0.5)
        drop_crit = col1.number_input("Caída crítica > (%)", min_value=1.0, max_value=80.0, value=10.0, step=0.5)
        rise_warn = col2.number_input("Subida > (%)", min_value=0.5, max_value=50.0, value=5.0, step=0.5)
        volume_rel = col2.number_input("Volumen anormal (x promedio)", min_value=1.0, max_value=10.0, value=2.0, step=0.1)
        discount = col3.number_input("Distancia al máximo 52s > (%)", min_value=5.0, max_value=90.0, value=30.0, step=1.0)
        trend_change = col3.checkbox("Alertar cambios de tendencia", value=True)

    thresholds = signals.AlertThresholds(
        drop_warn=drop_warn,
        drop_crit=drop_crit,
        rise_warn=rise_warn,
        volume_rel=volume_rel,
        discount=discount,
        trend_change=trend_change,
    )
    alerts = signals.build_alerts(frame, thresholds)

    if alerts.empty:
        ui.kpi_grid([ui.kpi("Alertas activas", "0", "ningún umbral se superó", accent="#16C784")])
        ui.banner("Sin alertas con los umbrales actuales.", "info")
        _power_bi_note()
        return

    counts = alerts["severidad"].value_counts()
    ui.kpi_grid(
        [
            ui.kpi("Alertas activas", str(len(alerts)), "total", accent="#22D3EE"),
            ui.kpi("Críticas", str(int(counts.get("Crítica", 0))), "prioridad máxima", accent="#EA3943"),
            ui.kpi("Altas", str(int(counts.get("Alta", 0))), accent="#F5B301"),
            ui.kpi("Media / Baja", str(int(counts.get("Media", 0) + counts.get("Baja", 0))), accent="#8A9BB4"),
        ]
    )

    ui.section("Alertas detectadas", "Ordenadas por severidad")
    display = alerts[["severidad", "tipo", "ticker", "empresa", "detalle"]].copy()
    display.columns = ["Severidad", "Tipo", "Ticker", "Empresa", "Detalle"]
    st.dataframe(display, width="stretch", hide_index=True, height=min(560, 40 + 34 * len(display)))

    st.download_button(
        "Descargar alertas (CSV)",
        data=alerts.to_csv(index=False).encode("utf-8-sig"),
        file_name="alertas_cedears.csv",
        mime="text/csv",
    )

    ui.section("Detalle por tipo", "")
    summary = (
        alerts.groupby(["tipo", "severidad"]).size().reset_index(name="cantidad").sort_values("cantidad", ascending=False)
    )
    summary.columns = ["Tipo", "Severidad", "Cantidad"]
    ui.styled_table(summary, height=min(400, 40 + 34 * len(summary)))

    ui.disclaimer(
        "Las alertas se evalúan al actualizar los datos (no hay monitoreo en segundo plano). "
        "Los valores se recalculan en cada refresco según los umbrales elegidos."
    )
    _power_bi_note()


def _power_bi_note() -> None:
    with st.expander("¿Power BI?"):
        st.markdown(
            """
La integración con Power BI requeriría publicar un dataset (Power BI Service, licencia Pro/Premium) y
un mecanismo de credenciales adicional. Para mantener el proyecto simple y sin costos se priorizó el
sistema de alertas integrado, con exportación a CSV y base SQLite (`.cache/cedears.sqlite3`), que
Power BI Desktop puede consumir localmente si se necesita.
            """
        )
