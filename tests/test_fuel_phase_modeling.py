"""Tests for phase-aligned fuel residual detection."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.fuel_phase_modeling import FuelPhaseResidualDetector, causal_persistence


def test_causal_persistence_requires_repeated_alerts():
    result = causal_persistence([0, 1, 0, 1, 1, 0], window=5, required=3)
    assert result.tolist() == [0, 0, 0, 0, 1, 1]


def test_causal_persistence_rejects_invalid_rule():
    with pytest.raises(ValueError, match="1 <= required"):
        causal_persistence([0, 1], window=2, required=3)


def test_phase_detector_scores_matching_profile_below_shifted_profile():
    normal = pd.DataFrame(
        {
            "sample_index": np.arange(1, 11),
            "a": np.linspace(0, 9, 10),
            "b": np.linspace(10, 20, 10),
        }
    )
    detector = FuelPhaseResidualDetector.fit(normal, ("a", "b"))
    matching = normal.iloc[[3, 6]]
    shifted = matching.assign(a=lambda frame: frame["a"] + 10)
    assert detector.anomaly_score(matching).max() == pytest.approx(0.0)
    assert detector.anomaly_score(shifted).min() > 0


def test_phase_detector_validates_features():
    normal = pd.DataFrame({"sample_index": [1, 2], "a": [0.0, 1.0]})
    detector = FuelPhaseResidualDetector.fit(normal, ("a",))
    with pytest.raises(ValueError, match="Missing fuel residual features"):
        detector.anomaly_score(pd.DataFrame({"sample_index": [1]}))
