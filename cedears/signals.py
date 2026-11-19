"""Señales analíticas: clasificación, oportunidades de rebote y alertas.

Nada de esto es una recomendación de inversión ni una predicción: son filtros
cuantitativos para priorizar el análisis del usuario.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ClassificationConfig:
    """Umbrales de la clasificación semáforo."""

    big_drop: float = -3.0
    high_rel_volume: float = 1.2
    low_rel_volume: float = 0.6
    high_volatility: float = 6.0
    deep_discount: float = 20.0
    persistent_drop_30d: float = -15.0


@dataclass(frozen=True)
class AlertThresholds:
    """Umbrales configurables de alertas."""

    drop_warn: float = 5.0
    drop_crit: float = 10.0
    rise_warn: float = 5.0
    volume_rel: float = 2.0
    discount: float = 30.0
    trend_change: bool = True


LABEL_GREEN = "Verde · Oportunidad potencial"
LABEL_YELLOW = "Amarillo · Neutral"
LABEL_RED = "Rojo · Riesgo"


def _num(row: pd.Series, key: str) -> float:
    value = row.get(key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def classify_row(row: pd.Series, config: ClassificationConfig | None = None) -> tuple[str, str]:
    """Devuelve (etiqueta, motivos separados por ' · ')."""
    config = config or ClassificationConfig()
    var_d = _num(row, "variacion_diaria")
    var_7d = _num(row, "var_7d")
    var_30d = _num(row, "var_30d")
    vol_rel = _num(row, "volumen_relativo")
    volatilidad = _num(row, "volatilidad_pct")
    descuento = _num(row, "descuento_52w")
    recuperacion = _num(row, "recuperacion_intradiaria")

    risk_reasons: list[str] = []
    if var_30d <= config.persistent_drop_30d:
        risk_reasons.append(f"caída mensual {var_30d:.1f}%")
    if volatilidad >= config.high_volatility:
        risk_reasons.append(f"volatilidad {volatilidad:.1f}%")
    if not np.isnan(vol_rel) and vol_rel < config.low_rel_volume:
        risk_reasons.append(f"volumen {vol_rel:.2f}x el promedio")

    opportunity_reasons: list[str] = []
    if var_d <= config.big_drop:
        opportunity_reasons.append(f"caída diaria {var_d:.1f}%")
    if not np.isnan(vol_rel) and vol_rel >= config.high_rel_volume:
        opportunity_reasons.append(f"volumen {vol_rel:.2f}x el promedio")
    if not np.isnan(recuperacion) and recuperacion >= 0.6:
        opportunity_reasons.append(f"recupera {recuperacion*100:.0f}% del rango del día")
    if descuento >= config.deep_discount:
        opportunity_reasons.append(f"{descuento:.1f}% debajo del máximo de 52 semanas")

    if opportunity_reasons and len(opportunity_reasons) >= 2:
        return LABEL_GREEN, " · ".join(opportunity_reasons)
    if risk_reasons:
        return LABEL_RED, " · ".join(risk_reasons)
    if opportunity_reasons:
        return LABEL_YELLOW, " · ".join(opportunity_reasons) + " (confirmación insuficiente)"
    flat = "movimiento lateral"
    if not np.isnan(var_7d) and not np.isnan(var_30d):
        flat = f"7d {var_7d:+.1f}% / 30d {var_30d:+.1f}%"
    return LABEL_YELLOW, flat


def add_classification(frame: pd.DataFrame, config: ClassificationConfig | None = None) -> pd.DataFrame:
    config = config or ClassificationConfig()
    out = frame.copy()
    if out.empty:
        out["clasificacion"] = pd.Series(dtype=str)
        out["motivos"] = pd.Series(dtype=str)
        return out
    labels = out.apply(lambda row: classify_row(row, config), axis=1)
    out["clasificacion"] = [item[0] for item in labels]
    out["motivos"] = [item[1] for item in labels]
    return out


def rebound_score(row: pd.Series, config: ClassificationConfig | None = None) -> float:
    """Score 0-100 de señales de posible rebote (no es una probabilidad)."""
    config = config or ClassificationConfig()
    var_d = _num(row, "variacion_diaria")
    vol_rel = _num(row, "volumen_relativo")
    recuperacion = _num(row, "recuperacion_intradiaria")
    descuento = _num(row, "descuento_52w")
    var_7d = _num(row, "var_7d")
    var_30d = _num(row, "var_30d")

    components: list[tuple[float, float]] = []

    if not np.isnan(var_d):
        caida = np.clip(-var_d / abs(config.big_drop * 3), 0, 1)
        components.append((caida, 0.25))
    if not np.isnan(vol_rel):
        volumen = np.clip((vol_rel - 0.8) / 1.7, 0, 1)
        components.append((volumen, 0.25))
    if not np.isnan(recuperacion):
        components.append((float(np.clip(recuperacion, 0, 1)), 0.20))
    if not np.isnan(descuento):
        components.append((float(np.clip(descuento / 40, 0, 1)), 0.15))
    if not np.isnan(var_7d) and not np.isnan(var_30d):
        mejora = np.clip((var_7d - var_30d + 10) / 20, 0, 1)
        components.append((float(mejora), 0.15))

    if not components:
        return np.nan
    weight = sum(w for _, w in components)
    return sum(value * w for value, w in components) / weight * 100


def add_rebound(frame: pd.DataFrame, config: ClassificationConfig | None = None) -> pd.DataFrame:
    config = config or ClassificationConfig()
    out = frame.copy()
    if out.empty:
        out["score_rebote"] = pd.Series(dtype=float)
        out["senales_rebote"] = pd.Series(dtype=str)
        return out
    out["score_rebote"] = out.apply(lambda row: rebound_score(row, config), axis=1)
    out["senales_rebote"] = out.apply(lambda row: _rebound_flags(row, config), axis=1)
    return out


def _rebound_flags(row: pd.Series, config: ClassificationConfig) -> str:
    var_d = _num(row, "variacion_diaria")
    vol_rel = _num(row, "volumen_relativo")
    recuperacion = _num(row, "recuperacion_intradiaria")
    descuento = _num(row, "descuento_52w")
    var_7d = _num(row, "var_7d")
    var_30d = _num(row, "var_30d")
    flags: list[str] = []
    if not np.isnan(var_d) and var_d <= config.big_drop:
        flags.append("caída fuerte")
    if not np.isnan(vol_rel) and vol_rel >= config.high_rel_volume:
        flags.append("volumen elevado")
    if not np.isnan(recuperacion) and recuperacion >= 0.6:
        flags.append("recupera intradía")
    if not np.isnan(descuento) and descuento >= config.deep_discount:
        flags.append("lejos del máximo 52s")
    if not np.isnan(var_7d) and not np.isnan(var_30d) and var_7d > var_30d:
        flags.append("mejora de corto plazo")
    return " · ".join(flags) if flags else "sin señales"


def build_alerts(frame: pd.DataFrame, thresholds: AlertThresholds | None = None) -> pd.DataFrame:
    """Genera alertas a partir de los umbrales configurados."""
    thresholds = thresholds or AlertThresholds()
    columns = ["severidad", "tipo", "ticker", "empresa", "detalle", "valor"]
    if frame is None or frame.empty:
        return pd.DataFrame(columns=columns)

    alerts: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        var_d = _num(row, "variacion_diaria")
        vol_rel = _num(row, "volumen_relativo")
        descuento = _num(row, "descuento_52w")
        var_7d = _num(row, "var_7d")
        var_30d = _num(row, "var_30d")
        base = {"ticker": row.get("symbol"), "empresa": row.get("company", "")}

        if not np.isnan(var_d):
            if var_d <= -abs(thresholds.drop_crit):
                alerts.append({**base, "severidad": "Crítica", "tipo": "Caída > umbral crítico",
                               "detalle": f"Cae {var_d:.2f}% en el día", "valor": var_d})
            elif var_d <= -abs(thresholds.drop_warn):
                alerts.append({**base, "severidad": "Alta", "tipo": "Caída > umbral",
                               "detalle": f"Cae {var_d:.2f}% en el día", "valor": var_d})
            if var_d >= abs(thresholds.rise_warn):
                alerts.append({**base, "severidad": "Media", "tipo": "Subida > umbral",
                               "detalle": f"Sube {var_d:.2f}% en el día", "valor": var_d})

        if not np.isnan(vol_rel) and vol_rel >= thresholds.volume_rel:
            alerts.append({**base, "severidad": "Media", "tipo": "Volumen anormal",
                           "detalle": f"Volumen {vol_rel:.2f}x el promedio de 20 ruedas", "valor": vol_rel})

        if not np.isnan(descuento) and descuento >= thresholds.discount:
            alerts.append({**base, "severidad": "Baja", "tipo": "Lejos del máximo 52s",
                           "detalle": f"{descuento:.1f}% debajo del máximo de 52 semanas", "valor": descuento})

        if thresholds.trend_change and not np.isnan(var_7d) and not np.isnan(var_30d):
            if var_7d > 0 and var_30d < 0:
                alerts.append({**base, "severidad": "Media", "tipo": "Cambio de tendencia",
                               "detalle": f"Semana {var_7d:+.1f}% vs mes {var_30d:+.1f}% (posible giro alcista)",
                               "valor": var_7d})
            elif var_7d < 0 and var_30d > 0:
                alerts.append({**base, "severidad": "Alta", "tipo": "Cambio de tendencia",
                               "detalle": f"Semana {var_7d:+.1f}% vs mes {var_30d:+.1f}% (pérdida de impulso)",
                               "valor": var_7d})

    alerts_frame = pd.DataFrame(alerts, columns=columns)
    if not alerts_frame.empty:
        order = {"Crítica": 0, "Alta": 1, "Media": 2, "Baja": 3}
        alerts_frame["_orden"] = alerts_frame["severidad"].map(order).fillna(9)
        alerts_frame = alerts_frame.sort_values(["_orden", "ticker"]).drop(columns="_orden")
    return alerts_frame.reset_index(drop=True)
