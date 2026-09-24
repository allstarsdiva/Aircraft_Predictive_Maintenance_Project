"""Tests for the experimental grouped battery RUL pipeline."""

from pathlib import Path

import numpy as np
import pandas as pd

from src.modeling import BatteryRULModelBundle, ModelMetrics
from src.train_battery_rul import (
    build_battery_rul_feature_table,
    conformal_absolute_error_quantile,
)


class IdentityTransformer:
    def transform(self, frame):
        return frame.to_numpy()


class FirstFeatureModel:
    def predict(self, values):
        return values[:, 0]


def test_rul_feature_join_keeps_only_eligible_rows():
    features = pd.DataFrame(
        {
            "battery_id": ["B1", "B1", "B2"],
            "uid": [1, 2, 3],
            "discharge_cycle": [1, 2, 1],
            "feature": [4.0, 3.0, 2.0],
            "soh_percent": [100.0, 90.0, 95.0],
        }
    )
    discharge = pd.DataFrame(
        {
            "uid": [1, 2, 3],
            "rul_cycles": [5.0, 4.0, np.nan],
            "observed_eol_cycle": [6.0, 6.0, np.nan],
            "rul_training_eligible": [True, True, False],
        }
    )
    result = build_battery_rul_feature_table(
        Path("."), soh_features=features, discharge_cycles=discharge
    )

    assert result["uid"].tolist() == [1, 2]
    assert result["rul_cycles"].tolist() == [5.0, 4.0]


def test_conformal_quantile_uses_conservative_finite_sample_rank():
    errors = np.arange(1.0, 11.0)
    assert conformal_absolute_error_quantile(errors, alpha=0.2) == 9.0


def test_battery_rul_bundle_returns_non_negative_interval():
    bundle = BatteryRULModelBundle(
        feature_columns=("feature",),
        preprocessor=IdentityTransformer(),
        model=FirstFeatureModel(),
        model_name="test",
        validation_metrics=ModelMetrics(0, 0, 1, 0),
        interval_alpha=0.1,
        absolute_error_quantile=3.0,
    )
    point, lower, upper = bundle.predict_interval(
        pd.DataFrame({"feature": [-1.0, 10.0]})
    )

    assert point.tolist() == [0.0, 10.0]
    assert lower.tolist() == [0.0, 7.0]
    assert upper.tolist() == [3.0, 13.0]
