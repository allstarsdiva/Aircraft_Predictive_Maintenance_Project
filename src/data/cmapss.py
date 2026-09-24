"""Load and validate the NASA C-MAPSS turbofan degradation dataset."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

CMAPSS_SUBSETS = ("FD001", "FD002", "FD003", "FD004")
CMAPSS_COLUMNS = (
    "unit_id",
    "cycle",
    "operational_setting_1",
    "operational_setting_2",
    "operational_setting_3",
    *(f"sensor_{number}" for number in range(1, 22)),
)

Split = Literal["train", "test"]


class CmapssDataError(ValueError):
    """Raised when C-MAPSS files do not match the expected schema."""


def default_engine_data_dir() -> Path:
    """Return the repository's default raw C-MAPSS directory."""

    return Path(__file__).resolve().parents[2] / "data" / "raw" / "engine"


def _validate_subset(subset: str) -> str:
    normalized = subset.upper()
    if normalized not in CMAPSS_SUBSETS:
        choices = ", ".join(CMAPSS_SUBSETS)
        raise ValueError(f"Unknown C-MAPSS subset {subset!r}; expected one of {choices}.")
    return normalized


def _data_dir(data_dir: str | Path | None) -> Path:
    return Path(data_dir) if data_dir is not None else default_engine_data_dir()


def _require_file(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"C-MAPSS file not found: {path}")
    return path


def load_cmapss(
    subset: str = "FD001",
    split: Split = "train",
    data_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Load one C-MAPSS train or test split with validated column names.

    The returned frame has one row per engine operating cycle and 26 columns:
    unit ID, cycle, three operating settings, and 21 sensor measurements.
    """

    normalized_subset = _validate_subset(subset)
    if split not in ("train", "test"):
        raise ValueError("split must be either 'train' or 'test'.")

    path = _require_file(_data_dir(data_dir) / f"{split}_{normalized_subset}.txt")
    frame = pd.read_csv(path, sep=r"\s+", header=None)

    if frame.empty:
        raise CmapssDataError(f"C-MAPSS file is empty: {path}")
    if frame.shape[1] != len(CMAPSS_COLUMNS):
        raise CmapssDataError(
            f"Expected {len(CMAPSS_COLUMNS)} columns in {path.name}, "
            f"found {frame.shape[1]}."
        )

    frame.columns = CMAPSS_COLUMNS
    frame["unit_id"] = pd.to_numeric(frame["unit_id"], errors="raise").astype("int64")
    frame["cycle"] = pd.to_numeric(frame["cycle"], errors="raise").astype("int64")

    if frame.isna().any().any():
        missing = int(frame.isna().sum().sum())
        raise CmapssDataError(f"Found {missing} missing values in {path.name}.")
    if (frame[["unit_id", "cycle"]] < 1).any().any():
        raise CmapssDataError(f"Unit IDs and cycles must be positive in {path.name}.")
    if frame.duplicated(["unit_id", "cycle"]).any():
        raise CmapssDataError(f"Duplicate unit/cycle rows found in {path.name}.")

    return frame


def load_test_rul(
    subset: str = "FD001",
    data_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Load additional RUL after each test engine's final observed cycle."""

    normalized_subset = _validate_subset(subset)
    path = _require_file(_data_dir(data_dir) / f"RUL_{normalized_subset}.txt")
    labels = pd.read_csv(path, sep=r"\s+", header=None)

    if labels.empty or labels.shape[1] != 1:
        raise CmapssDataError(f"Expected one non-empty RUL column in {path.name}.")

    labels.columns = ["additional_rul"]
    labels["additional_rul"] = pd.to_numeric(
        labels["additional_rul"], errors="raise"
    ).astype("int64")
    labels.insert(0, "unit_id", range(1, len(labels) + 1))

    if (labels["additional_rul"] < 0).any():
        raise CmapssDataError(f"Negative RUL label found in {path.name}.")
    return labels


def load_training_with_rul(
    subset: str = "FD001",
    data_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Load training cycles and calculate RUL, where failure-cycle RUL is zero."""

    frame = load_cmapss(subset=subset, split="train", data_dir=data_dir)
    final_cycles = frame.groupby("unit_id")["cycle"].transform("max")
    return frame.assign(rul=(final_cycles - frame["cycle"]).astype("int64"))


def load_test_with_rul(
    subset: str = "FD001",
    data_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Load test cycles and derive RUL for every observed row."""

    frame = load_cmapss(subset=subset, split="test", data_dir=data_dir)
    labels = load_test_rul(subset=subset, data_dir=data_dir)
    unit_ids = sorted(frame["unit_id"].unique().tolist())

    if unit_ids != labels["unit_id"].tolist():
        raise CmapssDataError(
            f"Test units and RUL labels do not align for {_validate_subset(subset)}."
        )

    final_cycles = frame.groupby("unit_id")["cycle"].transform("max")
    frame = frame.merge(labels, on="unit_id", how="left", validate="many_to_one")
    frame["rul"] = (
        frame["additional_rul"] + final_cycles - frame["cycle"]
    ).astype("int64")
    return frame.drop(columns="additional_rul")


def summarize_cmapss(
    subset: str = "FD001",
    data_dir: str | Path | None = None,
) -> dict[str, int | str]:
    """Return dimensions used by dataset checks and project reports."""

    normalized_subset = _validate_subset(subset)
    train = load_cmapss(normalized_subset, "train", data_dir)
    test = load_cmapss(normalized_subset, "test", data_dir)
    labels = load_test_rul(normalized_subset, data_dir)
    return {
        "subset": normalized_subset,
        "columns": len(CMAPSS_COLUMNS),
        "train_rows": len(train),
        "train_units": int(train["unit_id"].nunique()),
        "test_rows": len(test),
        "test_units": int(test["unit_id"].nunique()),
        "test_rul_labels": len(labels),
    }
