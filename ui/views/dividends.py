"""Vista: dividendos (con datos que el usuario puede cargar)."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from cedears.config import settings
from cedears.market import Analysis
from ui import components as ui

TEMPLATE = """symbol,ex_date,pay_date,amount_per_share,currency,ratio_applied,source,notes
# Ejemplo de formato (borrá estas líneas y cargá datos verificados)
# KO,2025-11-14,2025-12-01,0.51,USD,5,BYMA,Importe por CEDEAR ya ajustado por ratio
"""


def _load() -> pd.DataFrame:
    path = settings.dividends_path
    if not path.exists():
        return pd.DataFrame()
    try:
        frame = pd.read_csv(path, comment="#")
    except (OSError, pd.errors.ParserError):
        return pd.DataFrame()
    if frame.empty or "symbol" not in frame:
        return pd.DataFrame()
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    for column in ("ex_date", "pay_date"):
        frame[column] = pd.to_datetime(frame.get(column), errors="coerce")
    frame["amount_per_share"] = pd.to_numeric(frame.get("amount_per_share"), errors="coerce")
    return frame


def render(analysis: Analysis, frame: pd.DataFrame) -> None:
    ui.page_header(
        "Dividendos",
        "Información de dividendos del activo subyacente y su equivalente por CEDEAR",
        ui.data_status(analysis),
    )

    ui.banner(
        "La API REST v1 de IOL utilizada por este dashboard <b>no expone dividendos</b> (ni históricos ni "
        "calendario de pagos). Para no inventar datos, la sección queda vacía hasta que se cargue el archivo "
        "<span class='mono'>data/dividends.csv</span> con información verificada.",
        "warn",
    )

    ui.section("Por qué no se calculan automáticamente", "")
    st.markdown(
        """
Un dividendo de un CEDEAR no es igual al dividendo de la acción subyacente:

* el importe se ajusta por el **ratio de conversión**,
* intervienen **retenciones** y el tipo de cambio del momento del pago,
* las fechas de corte y pago locales pueden diferir de las del mercado de origen,
* algunos CEDEARs reinvierten o capitalizan en lugar de pagar.

Por eso, cualquier cifra de dividendos debe provenir de una fuente verificable (BYMA, CNV, comunicaciones
del broker) y registrarse explícitamente. La aplicación solo agrega y rinde esos datos, sin estimarlos.
        """
    )

    dividends = _load()
    if dividends.empty:
        ui.section("Cómo cargar dividendos", "")
        st.markdown(
            f"""
1. Descargá la plantilla y guardala como `data/dividends.csv`.
2. Completá una fila por pago, con el importe **por CEDEAR** ya ajustado por ratio
   (o indicá `ratio_applied` y el importe por acción subyacente).
3. Volvé a esta pantalla: los totales y el rendimiento por dividendos se calculan automáticamente.

```csv
{TEMPLATE.strip()}
```
            """
        )
        st.download_button(
            "Descargar plantilla CSV",
            data=TEMPLATE.encode("utf-8-sig"),
            file_name="dividends.csv",
            mime="text/csv",
        )
        return

    ui.section("Dividendos registrados", f"{len(dividends)} pagos cargados")
    display = dividends[["symbol", "ex_date", "pay_date", "amount_per_share", "currency", "ratio_applied", "source"]].copy()
    display.columns = ["Ticker", "Fecha de corte", "Fecha de pago", "Importe por CEDEAR", "Moneda", "Ratio aplicado", "Fuente"]
    ui.styled_table(display.sort_values("Fecha de pago", ascending=False), height=min(480, 40 + 34 * len(display)))

    # ------------------------------------------------------------- totales
    last_year = date.today() - timedelta(days=365)
    recent = dividends[dividends["ex_date"] >= pd.Timestamp(last_year)]
    totals = (
        recent.groupby("symbol")["amount_per_share"].sum().reset_index().rename(columns={"amount_per_share": "Dividendos 12m"})
    )
    prices = frame[["symbol", "last"]].rename(columns={"symbol": "Ticker", "last": "Precio"})
    totals = totals.rename(columns={"symbol": "Ticker"}).merge(prices, on="Ticker", how="left")
    totals["Rendimiento por dividendos"] = totals["Dividendos 12m"] / totals["Precio"] * 100

    ui.section("Dividendos acumulados y rendimiento", "Últimos 12 meses · importes por CEDEAR")
    ui.styled_table(
        totals.sort_values("Rendimiento por dividendos", ascending=False),
        pct_columns=["Rendimiento por dividendos"],
        height=min(420, 40 + 34 * len(totals)),
        decimals=2,
    )

    ui.disclaimer(
        "Los importes corresponden a lo cargado en el archivo. Verificá que estén expresados por CEDEAR y en la "
        "moneda indicada; la aplicación no convierte monedas ni aplica retenciones."
    )
