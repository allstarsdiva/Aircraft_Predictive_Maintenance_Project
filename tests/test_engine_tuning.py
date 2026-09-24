"""Tests for safety-oriented engine tuning helpers."""

import numpy as np
import pandas as pd

from src.tune import safety_metrics, safety_sample_weights


def test_safety_weights_prioritize_low_rul_rows():
    target = pd.Series([10, 45, 100])
    weights = safety_sample_weights(target, 3.0, 1.5)

    assert weights.tolist() == [3.0, 1.5, 1.0]


def test_positive_near_failure_bias_increases_safety_objective():
    actual = pd.Series([10.0, 20.0, 80.0, 100.0])
    optimistic = safety_metrics(actual, np.array([20.0, 30.0, 80.0, 100.0]))
    conservative = safety_metrics(actual, np.array([5.0, 15.0, 80.0, 100.0]))

    assert optimistic["near_failure_bias"] > 0
    assert conservative["near_failure_bias"] < 0
    assert optimistic["safety_objective"] > conservative["safety_objective"]
