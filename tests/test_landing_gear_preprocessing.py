"""Tests for landing-gear validation and leakage-safe preparation."""

from pathlib import Path

import pandas as pd
import pytest

from src.data.landing_gear import (
    LANDING_GEAR_EXPECTED_ROWS,
    LANDING_GEAR_FAULT_NAMES,
    LANDING_GEAR_RAW_COLUMNS,
    LandingGearDataError,
    load_landing_gear_dataset,
)
from src.preprocess_landing_gear import (
    LANDING_GEAR_MODEL_FEATURES,
    prepare_landing_gear_table,
    save_processed_landing_gear,
)


def test_real_landing_gear_dataset_has_expected_shape_and_targets():
    frame = load_landing_gear_dataset()

    assert len(frame) == LANDING_GEAR_EXPECTED_ROWS
    assert tuple(frame.columns) == LANDING_GEAR_RAW_COLUMNS
    assert frame["Fault_Code"].value_counts().sort_index().to_dict() == {
        0: 300,
        1: 500,
        2: 500,
        3: 200,
    }
    assert frame.isna().sum().sum() == 0
    assert frame["RunID"].is_unique
    assert frame["RUL"].between(0, 100).all()


def test_landing_gear_loader_rejects_wrong_schema(tmp_path: Path):
    path = tmp_path / "bad.csv"
    pd.DataFrame({"wrong": [1]}).to_csv(path, index=False)

    with pytest.raises(LandingGearDataError, match="Unexpected columns"):
        load_landing_gear_dataset(path, expected_rows=1)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("RunID", 0, "positive integers"),
        ("Fault_Code", 9, "Unknown Fault_Code"),
        ("RUL", 101, "between 0 and 100"),
        ("Mass", -1, "must be positive"),
    ],
)
def test_landing_gear_loader_rejects_invalid_values(
    tmp_path: Path, column: str, value: float, message: str
):
    source = load_landing_gear_dataset().head(1)
    source.loc[source.index[0], column] = value
    path = tmp_path / "invalid.csv"
    source.to_csv(path, index=False)

    with pytest.raises(LandingGearDataError, match=message):
        load_landing_gear_dataset(path, expected_rows=1)


def test_prepared_table_keeps_identifier_and_targets_out_of_model_features():
    prepared = prepare_landing_gear_table()

    assert set(LANDING_GEAR_MODEL_FEATURES).issubset(prepared.columns)
    assert "run_id" not in LANDING_GEAR_MODEL_FEATURES
    assert "fault_code" not in LANDING_GEAR_MODEL_FEATURES
    assert "rul_percent" not in LANDING_GEAR_MODEL_FEATURES
    assert prepared["fault_name"].notna().all()
    assert set(prepared["fault_name"]) == set(LANDING_GEAR_FAULT_NAMES.values())
    assert (prepared["is_fault"] == (prepared["fault_code"] != 0).astype(int)).all()


def test_processed_table_can_be_exported(tmp_path: Path):
    path = save_processed_landing_gear(tmp_path / "validated_runs.csv")
    exported = pd.read_csv(path)

    assert path.is_file()
    assert len(exported) == LANDING_GEAR_EXPECTED_ROWS
    assert exported["run_id"].is_unique
