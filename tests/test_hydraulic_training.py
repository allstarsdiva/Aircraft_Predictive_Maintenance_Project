"""Tests for leakage-aware hydraulic classifier helpers."""

import numpy as np
import pandas as pd

from src.eda_hydraulic import HYDRAULIC_TARGETS
from src.modeling import HydraulicClassificationBundle
from src.train_hydraulic import grouped_hydraulic_folds, hydraulic_condition_groups


def _factorial_table() -> pd.DataFrame:
    rows = []
    cycle = 1
    for cooler in (3, 20, 100):
        for valve in (73, 80, 90, 100):
            for pump in (0, 1, 2):
                for accumulator in (90, 100, 115, 130):
                    for _ in range(2):
                        rows.append(
                            {
                                "cycle_id": cycle,
                                "cooler_condition_percent": cooler,
                                "valve_condition_percent": valve,
                                "pump_leakage_severity": pump,
                                "accumulator_pressure_bar": accumulator,
                                "stable_flag": 0,
                                "feature": float(cycle),
                            }
                        )
                        cycle += 1
    return pd.DataFrame(rows)


def test_condition_groups_join_all_four_targets():
    table = _factorial_table()
    groups = hydraulic_condition_groups(table)
    assert groups.nunique() == 144
    assert groups.iloc[0] == "3|73|0|90"


def test_grouped_folds_never_split_a_condition_combination():
    table = _factorial_table()
    groups = hydraulic_condition_groups(table)
    folds = grouped_hydraulic_folds(
        table, HYDRAULIC_TARGETS[0], n_splits=3, random_state=42
    )
    for train_indices, validation_indices in folds:
        assert set(groups.iloc[train_indices]).isdisjoint(groups.iloc[validation_indices])


class IdentityTransformer:
    def transform(self, frame):
        return frame.to_numpy()


class ThresholdClassifier:
    def predict(self, values):
        return np.where(values[:, 0] > 0, 1, 0)


def test_hydraulic_bundle_validates_and_predicts_features():
    bundle = HydraulicClassificationBundle(
        target_column="target",
        feature_columns=("feature",),
        class_labels=(0, 1),
        preprocessor=IdentityTransformer(),
        model=ThresholdClassifier(),
        model_name="test",
        validation_metrics={"macro_f1": 1.0},
    )
    result = bundle.predict_feature_frame(pd.DataFrame({"feature": [-1.0, 2.0]}))
    assert result.tolist() == [0, 1]
