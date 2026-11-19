"""Métricas financieras del dashboard.

Todas las funciones son puras (entrada -> salida) para poder testearlas sin red.
Las fórmulas se documentan en ``docs/METRICAS.md``.

Convenciones
------------
* Porcentajes expresados en puntos porcentuales (12.5 = 12,5%).
* Si falta un dato el resultado es ``NaN`` y la UI muestra ``N/D``.
* Nunca se rellenan series faltantes con valores inventados.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

TRADING_DAYS_7D = 7
TRADING_DAYS_30D = 30
TRADING_DAYS_52W = 365
AVG_VOLUME_WINDOW = 20


@dataclass(frozen=True)
class TrendConfig:
    """Umbrales para clasificar la tendencia (modificables desde la UI)."""

    monthly_positive: float = 5.0
    monthly_negative: float = -5.0
    weekly_positive: float = 2.0
    weekly_negative: float = -2.0


@dataclass(frozen=True)
class ScoreWeights:
    """Ponderaciones del score (deben sumar 1)."""

    trend_7d: float = 0.4
    relative_volume: float = 0.3
    volatility: float = 0.3

    def normalized(self) -> "ScoreWeights":
        total = self.trend_7d + self.relative_volume + self.volatility
        if total <= 0:
            return ScoreWeights()
        return ScoreWeights(
            self.trend_7d / total, self.relative_volume / total, self.volatility / total
        )


# --------------------------------------------------------------------- helpers
def safe_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """División que devuelve NaN en lugar de inf cuando el denominador es 0."""
    den = denominator.replace(0, np.nan)
    return numerator / den


def pct_rank(series: pd.Series) -> pd.Series:
    """Rango percentil (0-100) robusto a valores extremos.

    Es la normalización usada por el score: no depende de la escala del volumen
    absoluto y evita que un outlier aplaste al resto.
    """
    clean = pd.to_numeric(series, errors="coerce")
    valid = clean.notna()
    if valid.sum() == 0:
        return pd.Series(np.nan, index=series.index, dtype=float)
    if valid.sum() == 1:
        result = pd.Series(np.nan, index=series.index, dtype=float)
        result[valid] = 50.0
        return result
    return clean.rank(pct=True, na_option="keep") * 100


def signed_rank(series: pd.Series) -> pd.Series:
    """Lleva el rango a [-1, 1] de forma simétrica (0 = mediana de la muestra).

    Con ``n`` valores válidos: ``2 × (rank − 1) / (n − 1) − 1``. A diferencia
    de restar 0,5 al percentil, la mediana queda exactamente en 0.
    """
    clean = pd.to_numeric(series, errors="coerce")
    n = int(clean.notna().sum())
    if n == 0:
        return pd.Series(np.nan, index=series.index, dtype=float)
    if n == 1:
        result = pd.Series(np.nan, index=series.index, dtype=float)
        result[clean.notna()] = 0.0
        return result
    ranks = clean.rank(method="average", na_option="keep")
    return 2 * (ranks - 1) / (n - 1) - 1


# ------------------------------------------------------------------- métricas
def daily_volatility(high: float, low: float, open_price: float) -> float:
    """volatilidad = (maximo - minimo) / apertura * 100."""
    if not high or not low or not open_price or open_price <= 0:
        return np.nan
    if high < low:
        return np.nan
    return (high - low) / open_price * 100


def discount_from_high(price: float, max_52w: float) -> float:
    """descuento = (max_52w - precio) / max_52w * 100."""
    if not price or not max_52w or max_52w <= 0:
        return np.nan
    return (max_52w - price) / max_52w * 100


def relative_volume(volume: float, avg_volume: float) -> float:
    """volumen_relativo = volumen_hoy / volumen_promedio."""
    if not volume or not avg_volume or avg_volume <= 0:
        return np.nan
    return volume / avg_volume


def pct_change_from(reference: float, current: float) -> float:
    if not reference or reference <= 0 or current is None or pd.isna(current):
        return np.nan
    return (current / reference - 1) * 100


def intraday_recovery(low: float, last: float, high: float) -> float:
    """Posición del precio dentro del rango del día: 0 = mínimo, 1 = máximo."""
    if pd.isna(low) or pd.isna(last) or pd.isna(high) or high <= low:
        return np.nan
    return (last - low) / (high - low)


def liquidity_bucket(amount_ars: float, low: float = 5_000_000, high: float = 50_000_000) -> str:
    """Clasifica liquidez según monto operado estimado en ARS."""
    if amount_ars is None or pd.isna(amount_ars):
        return "N/D"
    if amount_ars < low:
        return "Baja"
    if amount_ars < high:
        return "Media"
    return "Alta"


# -------------------------------------------------------------- features hist.
def history_features(bars: pd.DataFrame, asof: pd.Timestamp | None = None) -> dict[str, float]:
    """Calcula variaciones y máximo de 52 semanas a partir de barras diarias.

    ``bars`` debe tener columnas date, high, low, close, volume. Se ignoran
    fechas duplicadas y se ordena ascendente.
    """
    result = {
        "var_7d": np.nan,
        "var_30d": np.nan,
        "max_52w": np.nan,
        "descuento_52w": np.nan,
        "volumen_promedio": np.nan,
        "barras": 0,
        "ultima_rueda": pd.NaT,
    }
    if bars is None or bars.empty:
        return result

    frame = bars.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"]).drop_duplicates(subset="date", keep="last")
    frame = frame.sort_values("date")
    if frame["close"].isna().all():
        return result

    asof_ts = frame["date"].max() if asof is None else pd.Timestamp(asof)
    if asof_ts is not None and getattr(asof_ts, "tzinfo", None) is not None:
        asof_ts = asof_ts.tz_convert(None)
    frame = frame[frame["date"] <= asof_ts]
    if frame.empty:
        return result

    last_close = frame["close"].dropna().iloc[-1]
    result["barras"] = int(len(frame))
    result["ultima_rueda"] = frame["date"].iloc[-1]

    for label, days in (("var_7d", TRADING_DAYS_7D), ("var_30d", TRADING_DAYS_30D)):
        cutoff = frame["date"].iloc[-1] - pd.Timedelta(days=days)
        past = frame[frame["date"] <= cutoff]
        if not past.empty:
            result[label] = pct_change_from(past["close"].iloc[-1], last_close)

    window = frame[frame["date"] >= frame["date"].iloc[-1] - pd.Timedelta(days=TRADING_DAYS_52W)]
    if not window.empty:
        max_52w = window["high"].max() if "high" in window and window["high"].notna().any() else window["close"].max()
        result["max_52w"] = float(max_52w)
        result["descuento_52w"] = discount_from_high(last_close, max_52w)

    past_volume = frame["volume"].iloc[:-1].tail(AVG_VOLUME_WINDOW)
    if past_volume.notna().any():
        result["volumen_promedio"] = float(past_volume.mean())
    return result


def trend_label(var_7d: float, var_30d: float, config: TrendConfig | None = None) -> str:
    """Clasifica la tendencia: el mes manda y la semana define el corto plazo.

    * ``var_30d >= +5%`` → Positiva
    * ``var_30d <= -5%`` → Negativa
    * si el mes es lateral (|var_30d| < 5%), decide la semana: ``var_7d >= +2%``
      o ``var_7d <= -2%``; en otro caso, Lateral.
    """
    config = config or TrendConfig()
    if pd.isna(var_7d) and pd.isna(var_30d):
        return "N/D"

    monthly = var_30d if not pd.isna(var_30d) else np.nan
    weekly = var_7d if not pd.isna(var_7d) else np.nan

    if not np.isnan(monthly) and monthly >= config.monthly_positive:
        return "Positiva"
    if not np.isnan(monthly) and monthly <= config.monthly_negative:
        return "Negativa"

    if not np.isnan(weekly):
        if weekly >= config.weekly_positive and (np.isnan(monthly) or monthly > config.monthly_negative):
            return "Positiva"
        if weekly <= config.weekly_negative and (np.isnan(monthly) or monthly < config.monthly_positive):
            return "Negativa"
    return "Lateral"


# --------------------------------------------------------------------- score
def compute_score(
    frame: pd.DataFrame,
    weights: ScoreWeights | None = None,
    trend_col: str = "var_7d",
    volume_col: str = "volumen_relativo",
    volatility_col: str = "volatilidad_pct",
) -> pd.DataFrame:
    """Score de 0 a 100 combinando tendencia, volumen relativo y volatilidad.

    Cada componente se normaliza por rango percentil dentro del universo
    analizado y se lleva a [-1, 1]. El score final es
    ``(raw + 1) / 2 * 100`` para mostrarlo en escala 0-100.

    Es un ranking comparativo, **no** una predicción de rentabilidad.
    """
    weights = (weights or ScoreWeights()).normalized()
    out = frame.copy()
    if out.empty:
        for column in ("z_tendencia", "z_volumen", "z_volatilidad", "score_raw", "score"):
            out[column] = pd.Series(dtype=float)
        return out

    for column in (trend_col, volume_col, volatility_col):
        if column not in out:
            out[column] = np.nan

    out["z_tendencia"] = signed_rank(out[trend_col])
    out["z_volumen"] = signed_rank(out[volume_col])
    out["z_volatilidad"] = signed_rank(out[volatility_col])

    has_data = out[[trend_col, volume_col, volatility_col]].notna().any(axis=1)
    raw = (
        out["z_tendencia"].fillna(0) * weights.trend_7d
        + out["z_volumen"].fillna(0) * weights.relative_volume
        - out["z_volatilidad"].fillna(0) * weights.volatility
    )
    out["score_raw"] = raw
    out["score"] = (raw + 1) / 2 * 100
    out.loc[~has_data, ["score_raw", "score"]] = np.nan

    out["componente_tendencia"] = pct_rank(out[trend_col])
    out["componente_volumen"] = pct_rank(out[volume_col])
    out["componente_volatilidad"] = pct_rank(out[volatility_col])
    return out


def score_weights_dict(weights: ScoreWeights) -> dict[str, float]:
    w = weights.normalized()
    return {
        "tendencia_7d": round(w.trend_7d, 3),
        "volumen_relativo": round(w.relative_volume, 3),
        "volatilidad": round(w.volatility, 3),
    }
