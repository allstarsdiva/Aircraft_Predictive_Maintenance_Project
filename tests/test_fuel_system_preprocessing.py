"""Tests for fuel-system validation and causal preprocessing."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data.fuel_system import (
    FUEL_ROWS_PER_SCENARIO,
    FUEL_SENSOR_COLUMNS,
    FuelSystemDataError,
    load_fuel_scenario,
    load_fuel_system_dataset,
)
from src.preprocess_fuel import add_causal_fuel_features


def test_real_fuel_dataset_has_expected_scenarios_and_binary_labels():
    table = load_fuel_system_dataset()

    assert len(table) == FUEL_ROWS_PER_SCENARIO * 5
    assert table.groupby("scenario_id").size().to_dict() == {
        "four": 171,
        "normal": 171,
        "one": 171,
        "three": 171,
        "two": 171,
    }
    assert table["is_abnormal"].value_counts().sort_index().to_dict() == {
        0: 171,
        1: 684,
    }
    assert table.isna().sum().sum() == 0


def test_fuel_loader_rejects_wrong_schema(tmp_path: Path):
    bad = pd.DataFrame(np.ones((2, 2)), columns=["wrong", "columns"])
    bad.to_csv(tmp_path / "Scenario_Normal.csv", index=False)

    with pytest.raises(FuelSystemDataError, match="Unexpected columns"):
        load_fuel_scenario("normal", tmp_path, expected_rows=2)


def test_causal_features_reset_at_each_scenario():
    rows = []
    for scenario_code, scenario in enumerate(("normal", "one")):
        for sample_index, value in enumerate((1.0, 3.0), start=1):
            row = {
                "scenario_id": scenario,
                "scenario_code": scenario_code,
                "sample_index": sample_index,
                "is_abnormal": int(scenario != "normal"),
            }
            row.update({column: value for column in FUEL_SENSOR_COLUMNS})
            rows.append(row)
    result = add_causal_fuel_features(pd.DataFrame(rows), rolling_window=2)

    first_rows = result.loc[result["sample_index"] == 1]
    assert first_rows["FTL_delta_1"].tolist() == [0.0, 0.0]
    assert result.loc[result["scenario_id"] == "normal", "FTL_delta_1"].tolist() == [0.0, 2.0]
    assert result.loc[result["scenario_id"] == "normal", "FTL_rolling_mean_2"].tolist() == [1.0, 2.0]
