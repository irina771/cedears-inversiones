"""Tests del score cuantitativo."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cedears.metrics import ScoreWeights, compute_score, score_weights_dict


def _frame(volumes: list[float] | None = None) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": ["A", "B", "C", "D"],
            "var_7d": [10.0, 5.0, -2.0, -8.0],
            "volumen_relativo": [2.0, 1.1, 0.9, 0.5],
            "volatilidad_pct": [1.0, 2.0, 4.0, 8.0],
        }
    )


def test_score_between_0_and_100():
    scored = compute_score(_frame())
    assert scored["score"].between(0, 100).all()


def test_score_ordering_respects_weights():
    scored = compute_score(_frame(), ScoreWeights(1.0, 0.0, 0.0)).set_index("symbol")
    assert scored.loc["A", "score"] > scored.loc["B", "score"] > scored.loc["C", "score"]


def test_weights_are_normalized():
    weights = ScoreWeights(2.0, 1.0, 1.0).normalized()
    assert weights.trend_7d + weights.relative_volume + weights.volatility == pytest.approx(1.0)
    assert weights.trend_7d == pytest.approx(0.5)
    assert score_weights_dict(ScoreWeights(2, 1, 1))["tendencia_7d"] == pytest.approx(0.5)


def test_absolute_volume_does_not_distort():
    """Escalar el volumen por una constante no debe cambiar el score relativo."""
    base = _frame()
    scaled = base.copy()
    scaled["volumen_relativo"] = scaled["volumen_relativo"] * 1_000
    scored_base = compute_score(base).set_index("symbol")["score"]
    scored_scaled = compute_score(scaled).set_index("symbol")["score"]
    pd.testing.assert_series_equal(scored_base, scored_scaled, check_names=False)


def test_components_are_exposed():
    scored = compute_score(_frame())
    for column in ("componente_tendencia", "componente_volumen", "componente_volatilidad", "score_raw", "score"):
        assert column in scored.columns


def test_missing_data_yields_nan_score():
    frame = _frame()
    frame.loc[0, ["var_7d", "volumen_relativo", "volatilidad_pct"]] = np.nan
    scored = compute_score(frame)
    assert np.isnan(scored.loc[0, "score"])


def test_empty_frame():
    scored = compute_score(pd.DataFrame())
    assert scored.empty
