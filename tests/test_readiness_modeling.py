"""Tests for readiness uncertainty, support, calibration, and split helpers."""

import numpy as np
import pandas as pd
import pytest

from src.readiness_modeling import FeatureSupport
from src.retrain_readiness import (
    conservative_error_quantile,
    fit_confidence_calibration,
    landing_mass_regime_folds,
)


def test_feature_support_flags_hard_range_and_tail_values():
    train = pd.DataFrame({"a": np.arange(100.0), "b": np.arange(100.0) + 10})
    support = FeatureSupport.fit(train, ("a", "b"))

    normal = support.assess(pd.DataFrame({"a": [50.0], "b": [60.0]}))
    outside = support.assess(pd.DataFrame({"a": [101.0], "b": [60.0]}))
    assert normal["abstain"] is False
    assert outside["abstain"] is True
    assert outside["hard_range_violations"] == ["a"]


def test_feature_support_rejects_missing_and_nonfinite_inputs():
    support = FeatureSupport.fit(pd.DataFrame({"a": [1.0, 2.0]}), ("a",))
    with pytest.raises(ValueError, match="Missing readiness features"):
        support.assess(pd.DataFrame({"wrong": [1.0]}))
    with pytest.raises(ValueError, match="must be finite"):
        support.assess(pd.DataFrame({"a": [np.inf]}))


def test_conservative_error_quantile_uses_finite_sample_rank():
    errors = np.arange(1.0, 21.0)
    assert conservative_error_quantile(errors, alpha=0.10) == 19.0
    with pytest.raises(ValueError):
        conservative_error_quantile([], alpha=0.10)


def test_confidence_calibration_finds_high_accuracy_acceptance_region():
    confidence = np.linspace(0.1, 1.0, 100)
    correct = confidence >= 0.55
    calibrator, threshold, metrics = fit_confidence_calibration(
        confidence, correct, target_accepted_accuracy=0.90
    )
    assert 0 <= threshold <= 1
    assert metrics["accepted_accuracy"] >= 0.90
    assert metrics["accepted_coverage"] >= 0.20
    assert np.isfinite(calibrator.predict([0.5])).all()


def test_landing_mass_regime_folds_keep_bins_separate():
    rows = []
    for code in range(4):
        for index in range(50):
            rows.append({"fault_code": code, "mass": 1000 + index * 80 + code})
    table = pd.DataFrame(rows).sort_values("mass").reset_index(drop=True)
    groups = pd.qcut(table["mass"], q=20, labels=False, duplicates="drop")
    folds = landing_mass_regime_folds(table, n_splits=5)
    validation = np.concatenate([held for _, held in folds])
    assert sorted(validation.tolist()) == list(range(len(table)))
    for train, held in folds:
        assert set(groups.iloc[train]).isdisjoint(groups.iloc[held])
