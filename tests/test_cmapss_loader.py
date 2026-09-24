"""Validation tests for the NASA C-MAPSS loader."""

import pytest

from src.data.cmapss import (
    CMAPSS_COLUMNS,
    load_cmapss,
    load_test_rul,
    load_test_with_rul,
    load_training_with_rul,
    summarize_cmapss,
)


EXPECTED = {
    "FD001": (20_631, 100, 13_096, 100),
    "FD002": (53_759, 260, 33_991, 259),
    "FD003": (24_720, 100, 16_596, 100),
    "FD004": (61_249, 249, 41_214, 248),
}


@pytest.mark.parametrize("subset", EXPECTED)
def test_observed_dimensions_match_inventory(subset):
    train_rows, train_units, test_rows, test_units = EXPECTED[subset]
    summary = summarize_cmapss(subset)

    assert summary["columns"] == 26
    assert summary["train_rows"] == train_rows
    assert summary["train_units"] == train_units
    assert summary["test_rows"] == test_rows
    assert summary["test_units"] == test_units
    assert summary["test_rul_labels"] == test_units


def test_loader_assigns_expected_schema():
    frame = load_cmapss("FD001", "train")

    assert tuple(frame.columns) == CMAPSS_COLUMNS
    assert not frame.isna().any().any()
    assert not frame.duplicated(["unit_id", "cycle"]).any()


def test_training_rul_reaches_zero_for_every_engine():
    frame = load_training_with_rul("FD001")

    assert frame["rul"].min() == 0
    assert (frame.groupby("unit_id")["rul"].min() == 0).all()


def test_test_terminal_rul_matches_provided_labels():
    frame = load_test_with_rul("FD001")
    terminal = frame.loc[frame.groupby("unit_id")["cycle"].idxmax()]
    expected = load_test_rul("FD001")

    assert terminal["rul"].tolist() == expected["additional_rul"].tolist()


def test_invalid_subset_is_rejected():
    with pytest.raises(ValueError, match="Unknown C-MAPSS subset"):
        load_cmapss("FD999", "train")
