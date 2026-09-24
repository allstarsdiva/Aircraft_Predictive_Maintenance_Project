"""Focused tests for engine baseline training utilities."""

import numpy as np
import pandas as pd

from src.modeling import EngineModelBundle, ModelMetrics
from src.train import evaluate_predictions


class IdentityTransformer:
    def transform(self, frame):
        return frame.to_numpy()


class SumModel:
    def predict(self, values):
        return values.sum(axis=1)


def test_evaluate_predictions_returns_agreed_metrics():
    scores = evaluate_predictions(pd.Series([0.0, 10.0]), np.array([2.0, 8.0]))

    assert scores["mae"] == 2.0
    assert scores["rmse"] == 2.0
    assert scores["r2"] == 0.84


def test_bundle_validates_features_and_clips_physical_range():
    bundle = EngineModelBundle(
        subset="FD001",
        capped_rul=125,
        feature_columns=("a", "b"),
        preprocessor=IdentityTransformer(),
        model=SumModel(),
        model_name="test",
        validation_metrics=ModelMetrics(0, 0, 1, 0),
    )
    predicted = bundle.predict_feature_frame(
        pd.DataFrame({"a": [-10, 100], "b": [1, 100]})
    )

    assert predicted.tolist() == [0, 125]
