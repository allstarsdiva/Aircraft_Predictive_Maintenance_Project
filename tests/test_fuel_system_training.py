"""Tests for blocked fuel-system anomaly detection."""

import numpy as np
import pandas as pd
import pytest

from src.train_fuel import (
    FuelAnomalyModelBundle,
    conservative_quantile,
    contiguous_fuel_blocks,
)


def test_contiguous_blocks_cover_normal_trajectory_once():
    normal = pd.DataFrame({"sample_index": range(1, 31)})
    blocks = contiguous_fuel_blocks(normal, n_blocks=3)
    assert [len(block) for block in blocks] == [10, 10, 10]
    assert np.concatenate(blocks).tolist() == list(range(30))
    assert set(blocks[0]).isdisjoint(blocks[1])


def test_conservative_threshold_uses_higher_observed_score():
    assert conservative_quantile(np.arange(1.0, 21.0), 0.95) == 20.0
    with pytest.raises(ValueError, match="between zero and one"):
        conservative_quantile(np.arange(3.0), 1.0)


class IdentityTransformer:
    def transform(self, frame):
        return frame.to_numpy()


class FirstFeatureDetector:
    def decision_function(self, values):
        return -values[:, 0]


def _bundle() -> FuelAnomalyModelBundle:
    return FuelAnomalyModelBundle(
        feature_columns=("feature",),
        preprocessors=(IdentityTransformer(),) * 3,
        detectors=(FirstFeatureDetector(),) * 3,
        thresholds=(5.0, 7.0, 9.0),
        score_scales=(1.0, 1.0, 1.0),
        detector_name="test",
        expected_false_alarm_rate=0.05,
        validation_metrics={},
    )


def test_fuel_bundle_uses_majority_vote_and_median_margin():
    frame = pd.DataFrame({"feature": [4.0, 8.0, 10.0]})
    assert _bundle().predict_feature_frame(frame).tolist() == [0, 1, 1]
    assert _bundle().predict_anomaly_score(frame).tolist() == [-3.0, 1.0, 3.0]


def test_fuel_bundle_rejects_missing_features():
    with pytest.raises(ValueError, match="Missing fuel-system features"):
        _bundle().predict_feature_frame(pd.DataFrame({"wrong": [1.0]}))
