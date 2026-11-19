"""Tests de clasificación, rebotes y alertas."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cedears import signals


def _row(**kwargs) -> pd.Series:
    base = {
        "symbol": "TEST",
        "company": "Test",
        "variacion_diaria": 0.0,
        "var_7d": 0.0,
        "var_30d": 0.0,
        "volumen_relativo": 1.0,
        "volatilidad_pct": 2.0,
        "descuento_52w": 5.0,
        "recuperacion_intradiaria": 0.5,
    }
    base.update(kwargs)
    return pd.Series(base)


def test_green_needs_two_signals():
    row = _row(variacion_diaria=-6.0, volumen_relativo=1.5, descuento_52w=25.0)
    label, reasons = signals.classify_row(row)
    assert label == signals.LABEL_GREEN
    assert "caída diaria" in reasons


def test_single_signal_is_yellow():
    row = _row(variacion_diaria=-6.0, volumen_relativo=1.0, descuento_52w=5.0, recuperacion_intradiaria=0.2)
    label, reasons = signals.classify_row(row)
    assert label == signals.LABEL_YELLOW
    assert "confirmación insuficiente" in reasons


def test_red_on_persistent_drop():
    row = _row(var_30d=-20.0, variacion_diaria=1.0)
    label, reasons = signals.classify_row(row)
    assert label == signals.LABEL_RED
    assert "caída mensual" in reasons


def test_red_on_high_volatility_only():
    row = _row(volatilidad_pct=9.0)
    assert signals.classify_row(row)[0] == signals.LABEL_RED


def test_rebound_score_bounds():
    high = _row(variacion_diaria=-9.0, volumen_relativo=3.0, recuperacion_intradiaria=1.0, descuento_52w=40.0, var_7d=5, var_30d=-10)
    low = _row(variacion_diaria=0.0, volumen_relativo=0.1, recuperacion_intradiaria=0.0, descuento_52w=0.0, var_7d=-5, var_30d=-10)
    assert 0 <= signals.rebound_score(high) <= 100
    assert signals.rebound_score(high) > signals.rebound_score(low)


def test_alerts_thresholds():
    frame = pd.DataFrame(
        [
            _row(symbol="DROP5", variacion_diaria=-6.0),
            _row(symbol="DROP10", variacion_diaria=-12.0),
            _row(symbol="RISE", variacion_diaria=7.0),
            _row(symbol="VOL", variacion_diaria=1.0, volumen_relativo=3.0),
        ]
    )
    alerts = signals.build_alerts(frame)
    types = set(alerts["tipo"])
    assert "Caída > umbral" in types
    assert "Caída > umbral crítico" in types
    assert "Subida > umbral" in types
    assert "Volumen anormal" in types
    # La caída de -12% no debe generar también la alerta de -5%
    assert len(alerts[alerts["ticker"] == "DROP10"]) == 1
    assert alerts.iloc[0]["severidad"] == "Crítica"


def test_alerts_disable_trend_change():
    frame = pd.DataFrame([_row(var_7d=5.0, var_30d=-6.0)])
    with_trend = signals.build_alerts(frame, signals.AlertThresholds(trend_change=True))
    without = signals.build_alerts(frame, signals.AlertThresholds(trend_change=False))
    assert "Cambio de tendencia" in set(with_trend["tipo"])
    assert "Cambio de tendencia" not in set(without["tipo"])


def test_alerts_custom_thresholds():
    frame = pd.DataFrame([_row(variacion_diaria=-3.0)])
    assert signals.build_alerts(frame, signals.AlertThresholds(drop_warn=2.0)).shape[0] == 1
    assert signals.build_alerts(frame, signals.AlertThresholds(drop_warn=5.0)).shape[0] == 0


def test_alerts_empty_frame():
    alerts = signals.build_alerts(pd.DataFrame())
    assert alerts.empty
    assert list(alerts.columns) == ["severidad", "tipo", "ticker", "empresa", "detalle", "valor"]
