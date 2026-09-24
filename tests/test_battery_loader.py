"""Validation tests for the cleaned NASA battery dataset loader."""

import numpy as np
import pandas as pd
import pytest

from src.data.battery import (
    DOCUMENTED_EOL_CAPACITY_AH,
    MEASUREMENT_COLUMNS,
    BatteryDataError,
    default_battery_data_dir,
    build_battery_discharge_table,
    load_battery_measurement,
    load_battery_metadata,
    parse_start_time,
    resolve_measurement_path,
    summarize_battery_dataset,
    summarize_battery_discharge_table,
)


@pytest.fixture(scope="module")
def metadata():
    return load_battery_metadata()


def test_metadata_dimensions_and_identifiers(metadata):
    summary = summarize_battery_dataset(metadata)

    assert summary["metadata_rows"] == 7_565
    assert summary["measurement_files"] == 7_565
    assert summary["battery_ids"] == 34
    assert summary["test_types"] == {
        "charge": 2_815,
        "discharge": 2_794,
        "impedance": 1_956,
    }
    assert metadata["uid"].is_unique
    assert metadata["filename"].is_unique
    assert pd.api.types.is_datetime64_any_dtype(metadata["start_time"])


@pytest.mark.parametrize("test_type", ["charge", "discharge", "impedance"])
def test_representative_measurement_schema(metadata, test_type):
    uid = int(metadata.loc[metadata["type"] == test_type, "uid"].iloc[0])
    measurement = load_battery_measurement(uid, metadata)

    assert tuple(measurement.samples.columns) == MEASUREMENT_COLUMNS[test_type]
    assert not measurement.samples.empty
    if test_type == "impedance":
        assert all(np.issubdtype(dtype, np.complexfloating) for dtype in measurement.samples.dtypes)
    else:
        assert all(np.issubdtype(dtype, np.number) for dtype in measurement.samples.dtypes)


def test_placeholder_targets_are_normalized(metadata):
    non_discharge = metadata.loc[metadata["type"] != "discharge"]

    assert non_discharge["Capacity"].isna().all()
    assert summarize_battery_dataset(metadata)["capacity_labels"] == 2_769


def test_start_time_vector_parsing():
    timestamp = parse_start_time("[2010. 7. 21. 15. 0. 35.093]")
    scientific = parse_start_time(
        "[2.0100e+03 7.0000e+00 2.1000e+01 2.1000e+01 2.0000e+00 5.6984e+01]"
    )

    assert timestamp == pd.Timestamp("2010-07-21 15:00:35.093")
    assert scientific == pd.Timestamp("2010-07-21 21:02:56.984")


def test_measurement_path_rejects_traversal():
    with pytest.raises(BatteryDataError, match="Unsafe"):
        resolve_measurement_path(default_battery_data_dir(), "../00001.csv")


def test_unknown_uid_is_rejected(metadata):
    with pytest.raises(KeyError, match="uid not found"):
        load_battery_measurement(999_999, metadata)


def test_discharge_table_is_chronological_and_preserves_all_rows(metadata):
    table = build_battery_discharge_table(metadata)

    assert len(table) == 2_794
    assert table["battery_id"].nunique() == 34
    assert (
        table.groupby("battery_id")["discharge_cycle"].min() == 1
    ).all()
    assert all(
        group["start_time"].is_monotonic_increasing
        for _, group in table.groupby("battery_id")
    )


def test_soh_excludes_missing_and_zero_capacity(metadata):
    table = build_battery_discharge_table(metadata)
    summary = summarize_battery_discharge_table(table)

    assert summary["valid_capacity_rows"] == 2_750
    assert summary["missing_capacity_rows"] == 25
    assert summary["zero_capacity_rows"] == 19
    assert table.loc[~table["valid_capacity"], "soh_percent"].isna().all()


def test_documented_eol_rules_are_not_assigned_to_unknown_groups(metadata):
    table = build_battery_discharge_table(metadata)

    assert len(DOCUMENTED_EOL_CAPACITY_AH) == 22
    assert DOCUMENTED_EOL_CAPACITY_AH["B0005"] == 1.4
    assert DOCUMENTED_EOL_CAPACITY_AH["B0033"] == 1.6
    assert table.loc[table["battery_id"] == "B0049", "eol_capacity_ah"].isna().all()
    assert table.loc[table["rul_cycles"].notna(), "rul_cycles"].ge(0).all()


def test_left_and_right_censored_batteries_do_not_receive_rul(metadata):
    table = build_battery_discharge_table(metadata)

    invalid_statuses = {"starts_at_or_below_threshold", "right_censored"}
    assert table.loc[
        table["rul_label_status"].isin(invalid_statuses), "rul_cycles"
    ].isna().all()
    assert table.loc[table["battery_id"] == "B0007", "rul_label_status"].eq(
        "right_censored"
    ).all()


def test_rul_training_flag_excludes_post_eol_and_invalid_capacity(metadata):
    table = build_battery_discharge_table(metadata)
    eligible = table.loc[table["rul_training_eligible"]]

    assert len(eligible) == 493
    assert eligible["battery_id"].nunique() == 9
    assert eligible["valid_capacity"].all()
    assert (eligible["discharge_cycle"] <= eligible["observed_eol_cycle"]).all()
