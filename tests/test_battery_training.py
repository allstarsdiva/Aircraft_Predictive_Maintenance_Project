"""Tests for battery SOH feature extraction and grouped training helpers."""

import numpy as np
import pandas as pd

from src.data.battery import load_battery_measurement, load_battery_metadata
from src.features import BATTERY_CURVE_FEATURES, extract_battery_discharge_features
from src.modeling import BatterySOHModelBundle, ModelMetrics
from src.train_battery import split_battery_groups


def test_discharge_curve_features_are_finite():
    metadata = load_battery_metadata()
    uid = int(metadata.loc[metadata["type"] == "discharge", "uid"].iloc[0])
    samples = load_battery_measurement(uid, metadata).samples
    features = extract_battery_discharge_features(samples)

    assert tuple(features) == BATTERY_CURVE_FEATURES
    assert np.isfinite(list(features.values())).all()
    assert features["duration_seconds"] > 0
    assert features["charge_throughput_ah"] > 0


def test_battery_group_split_has_no_overlap():
    table = pd.DataFrame(
        {
            "battery_id": np.repeat([f"B{i:04d}" for i in range(10)], 3),
            "uid": range(30),
            "feature": np.arange(30),
            "soh_percent": np.arange(30),
        }
    )
    train, validation = split_battery_groups(table, validation_size=0.2)

    assert set(train["battery_id"]).isdisjoint(validation["battery_id"])
    assert train["battery_id"].nunique() == 8
    assert validation["battery_id"].nunique() == 2


class IdentityTransformer:
    def transform(self, frame):
        return frame.to_numpy()


class FirstFeatureModel:
    def predict(self, values):
        return values[:, 0]


def test_battery_bundle_validates_and_clips_predictions():
    bundle = BatterySOHModelBundle(
        feature_columns=("feature",),
        preprocessor=IdentityTransformer(),
        model=FirstFeatureModel(),
        model_name="test",
        validation_metrics=ModelMetrics(0, 0, 1, 0),
    )
    result = bundle.predict_feature_frame(pd.DataFrame({"feature": [-10, 200]}))

    assert result.tolist() == [0, 150]
