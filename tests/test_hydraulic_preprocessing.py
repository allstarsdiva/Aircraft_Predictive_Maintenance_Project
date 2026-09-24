"""Tests for UCI hydraulic loading and cycle feature extraction."""

import numpy as np
import pandas as pd

from src.data.hydraulic import (
    HYDRAULIC_CYCLES,
    PROFILE_COLUMNS,
    hydraulic_profile_summary,
    load_hydraulic_profile,
    load_hydraulic_sensor,
)
from src.preprocess_hydraulic import summarize_sensor_cycles


def test_real_hydraulic_profile_has_documented_schema_and_counts():
    profile = load_hydraulic_profile()
    summary = hydraulic_profile_summary(profile)

    assert len(profile) == HYDRAULIC_CYCLES
    assert tuple(profile.columns) == ("cycle_id", *PROFILE_COLUMNS)
    assert summary["stable_cycles"] == 1449
    assert summary["potentially_unstable_cycles"] == 756


def test_real_one_hertz_sensor_has_aligned_cycles():
    sensor = load_hydraulic_sensor("TS1")
    assert sensor.shape == (HYDRAULIC_CYCLES, 60)
    assert np.isfinite(sensor.to_numpy()).all()


def test_hydraulic_cycle_statistics_have_expected_values():
    values = pd.DataFrame([[1.0, 2.0, 3.0], [4.0, 4.0, 4.0]])
    result = summarize_sensor_cycles(values, "PS1")

    assert result.columns.tolist() == [
        "ps1_mean",
        "ps1_std",
        "ps1_min",
        "ps1_max",
        "ps1_range",
        "ps1_rms",
        "ps1_slope",
    ]
    assert result.loc[0, "ps1_mean"] == 2.0
    assert result.loc[0, "ps1_range"] == 2.0
    assert result.loc[0, "ps1_slope"] == 2.0
    assert result.loc[1, "ps1_std"] == 0.0
