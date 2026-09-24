"""Tests for landing-gear model validation and saved bundles."""

import numpy as np
import pandas as pd
import pytest

from src.landing_gear_modeling import LandingGearFaultBundle, LandingGearRULBundle
from src.train_landing_gear import landing_gear_folds


def test_stratified_folds_cover_every_row_once_without_overlap():
    table = pd.DataFrame({
        "fault_code": np.repeat([0, 1, 2, 3], 10),
        "value": np.arange(40),
    })
    folds = landing_gear_folds(table, n_splits=5, random_state=42)
    validation = np.concatenate([indices for _, indices in folds])

    assert sorted(validation.tolist()) == list(range(40))
    for train, held_out in folds:
        assert set(train).isdisjoint(held_out)
        assert set(table.iloc[held_out]["fault_code"]) == {0, 1, 2, 3}


class IdentityTransformer:
    def transform(self, frame):
        return frame.to_numpy()


class ThresholdClassifier:
    def predict(self, values):
        return (values[:, 0] > 0).astype(int)


class WideRegressor:
    def predict(self, values):
        return values[:, 0] * 100


def test_landing_gear_bundles_predict_and_clip_rul():
    fault = LandingGearFaultBundle(
        feature_columns=("feature",), preprocessor=IdentityTransformer(),
        model=ThresholdClassifier(), model_name="test", feature_set="observable",
        class_names={0: "normal", 1: "fault"}, validation_metrics={},
    )
    rul = LandingGearRULBundle(
        feature_columns=("feature",), preprocessor=IdentityTransformer(),
        model=WideRegressor(), model_name="test", feature_set="observable",
        validation_metrics={},
    )
    frame = pd.DataFrame({"feature": [-1.0, 0.5, 2.0]})

    assert fault.predict_feature_frame(frame).tolist() == [0, 1, 1]
    assert rul.predict_feature_frame(frame).tolist() == [0.0, 50.0, 100.0]


def test_landing_gear_bundle_rejects_missing_features():
    bundle = LandingGearFaultBundle(
        feature_columns=("feature",), preprocessor=IdentityTransformer(),
        model=ThresholdClassifier(), model_name="test", feature_set="observable",
        class_names={}, validation_metrics={},
    )
    with pytest.raises(ValueError, match="Missing landing-gear features"):
        bundle.predict_feature_frame(pd.DataFrame({"wrong": [1.0]}))
