"""Tests for official C-MAPSS test-set evaluation helpers."""

import numpy as np

from src.evaluate import nasa_asymmetric_score, official_terminal_rows


def test_nasa_score_is_zero_for_perfect_predictions():
    actual = np.array([10.0, 50.0, 100.0])

    assert nasa_asymmetric_score(actual, actual) == 0.0


def test_nasa_score_penalizes_late_prediction_more_than_early_prediction():
    actual = np.array([50.0])
    early = nasa_asymmetric_score(actual, np.array([40.0]))
    late = nasa_asymmetric_score(actual, np.array([60.0]))

    assert late > early > 0


def test_official_terminal_rows_align_with_fd001_labels():
    terminal = official_terminal_rows("FD001")

    assert len(terminal) == 100
    assert terminal["unit_id"].nunique() == 100
    assert terminal["unit_id"].tolist() == list(range(1, 101))
    assert (terminal["rul"] >= 0).all()
