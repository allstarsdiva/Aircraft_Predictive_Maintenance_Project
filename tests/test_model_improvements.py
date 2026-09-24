"""Tests for leakage-resistant and robustness model helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.model_improvements import (
    add_fuel_phase_features,
    cooler_proxy_free_features,
    fuel_detection_metrics,
    perturb_validation_features,
    unseen_fuel_scenario_oof,
)


def test_cooler_proxy_features_are_removed():
    table = pd.DataFrame(
        {
            "cycle_id": [1],
            "cooler_condition_percent": [100],
            "valve_condition_percent": [100],
            "pump_leakage_severity": [0],
            "accumulator_pressure_bar": [130],
            "stable_flag": [0],
            "ce_mean": [1.0],
            "cp_std": [2.0],
            "ts1_mean": [3.0],
        }
    )
    assert cooler_proxy_free_features(table) == ("ts1_mean",)


def test_perturbation_is_deterministic_and_preserves_nonfeatures():
    train = pd.DataFrame({"x": np.arange(10.0), "label": np.arange(10)})
    validation = pd.DataFrame({"x": [2.0, 4.0], "label": [7, 8]})
    first = perturb_validation_features(
        validation, train, ("x",), random_state=7
    )
    second = perturb_validation_features(
        validation, train, ("x",), random_state=7
    )
    assert first.equals(second)
    assert first["label"].tolist() == [7, 8]
    assert not np.allclose(first["x"], validation["x"])


def _fuel_table() -> pd.DataFrame:
    rows = []
    for scenario_number, scenario in enumerate(("normal", "one", "two", "three", "four")):
        for sample in range(1, 13):
            rows.append(
                {
                    "scenario_id": scenario,
                    "scenario_code": scenario_number,
                    "sample_index": sample,
                    "is_abnormal": int(scenario != "normal"),
                    "sensor": float(sample + 5 * (scenario != "normal")),
                }
            )
    return add_fuel_phase_features(pd.DataFrame(rows))


def test_fuel_phase_features_are_finite_and_bounded():
    table = _fuel_table()
    assert table["phase_fraction"].between(0, 1).all()
    assert np.isfinite(table[["phase_sin", "phase_cos", "phase_bin"]]).all().all()


def test_unseen_scenario_oof_covers_every_row_once():
    from sklearn.linear_model import LogisticRegression

    table = _fuel_table()
    features = ("sensor", "phase_fraction", "phase_sin", "phase_cos", "phase_bin")
    predicted, confidence, indices = unseen_fuel_scenario_oof(
        table, LogisticRegression(max_iter=1000), features
    )
    assert len(predicted) == len(table)
    assert np.array_equal(indices, table.index.to_numpy())
    assert np.isfinite(confidence).all()
    metrics = fuel_detection_metrics(table, predicted)
    assert 0 <= metrics["balanced_accuracy"] <= 1
