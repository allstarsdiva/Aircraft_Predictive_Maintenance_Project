"""Load and validate the cleaned NASA PCoE Li-ion battery CSV dataset."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

BATTERY_METADATA_COLUMNS = (
    "type",
    "start_time",
    "ambient_temperature",
    "battery_id",
    "test_id",
    "uid",
    "filename",
    "Capacity",
    "Re",
    "Rct",
)
BATTERY_TEST_TYPES = ("charge", "discharge", "impedance")
RATED_CAPACITY_AH = 2.0
DOCUMENTED_EOL_CAPACITY_AH = {
    **{battery: 1.4 for battery in ("B0005", "B0006", "B0007", "B0018")},
    **{battery: 1.6 for battery in ("B0033", "B0034", "B0036")},
    **{battery: 1.6 for battery in ("B0038", "B0039", "B0040")},
    **{
        battery: 1.4
        for battery in (
            "B0041",
            "B0042",
            "B0043",
            "B0044",
            "B0045",
            "B0046",
            "B0047",
            "B0048",
        )
    },
    **{battery: 1.4 for battery in ("B0053", "B0054", "B0055", "B0056")},
}
MEASUREMENT_COLUMNS = {
    "charge": (
        "Voltage_measured",
        "Current_measured",
        "Temperature_measured",
        "Current_charge",
        "Voltage_charge",
        "Time",
    ),
    "discharge": (
        "Voltage_measured",
        "Current_measured",
        "Temperature_measured",
        "Current_load",
        "Voltage_load",
        "Time",
    ),
    "impedance": (
        "Sense_current",
        "Battery_current",
        "Current_ratio",
        "Battery_impedance",
        "Rectified_Impedance",
    ),
}
_NUMBER_PATTERN = re.compile(
    r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
)
_MISSING_TEXT = frozenset({"", "[]"})


class BatteryDataError(ValueError):
    """Raised when battery files do not match the expected cleaned schema."""


@dataclass(frozen=True)
class BatteryMeasurement:
    """One charge, discharge, or impedance test and its metadata."""

    metadata: pd.Series
    samples: pd.DataFrame


def default_battery_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "raw" / "battery" / "cleaned_dataset"


def _data_dir(data_dir: str | Path | None) -> Path:
    return Path(data_dir) if data_dir is not None else default_battery_data_dir()


def parse_start_time(value: str) -> pd.Timestamp:
    """Convert a NASA six-value date vector into a pandas timestamp."""

    values = [float(item) for item in _NUMBER_PATTERN.findall(value)]
    if len(values) != 6:
        raise BatteryDataError(f"Invalid battery start_time vector: {value!r}")
    year, month, day, hour, minute = (int(item) for item in values[:5])
    try:
        base = pd.Timestamp(year, month, day, hour, minute, 0)
        return base + pd.to_timedelta(values[5], unit="s")
    except (ValueError, OverflowError) as exc:
        raise BatteryDataError(f"Invalid battery start_time vector: {value!r}") from exc


def _optional_complex(value: str) -> complex:
    if value.strip() in _MISSING_TEXT:
        return complex(np.nan, np.nan)
    try:
        return complex(value.strip())
    except ValueError as exc:
        raise BatteryDataError(f"Invalid complex impedance value: {value!r}") from exc


def resolve_measurement_path(data_dir: Path, filename: str) -> Path:
    """Resolve a metadata filename without permitting path traversal."""

    candidate_name = Path(filename)
    if candidate_name.name != filename or candidate_name.suffix.lower() != ".csv":
        raise BatteryDataError(f"Unsafe or unsupported measurement filename: {filename!r}")
    path = data_dir / "data" / filename
    if not path.is_file():
        raise FileNotFoundError(f"Battery measurement file not found: {path}")
    return path


def load_battery_metadata(data_dir: str | Path | None = None) -> pd.DataFrame:
    """Load metadata with normalized numeric, complex, and timestamp fields."""

    root = _data_dir(data_dir)
    path = root / "metadata.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Battery metadata file not found: {path}")
    metadata = pd.read_csv(path, dtype=str, keep_default_na=False)

    if tuple(metadata.columns) != BATTERY_METADATA_COLUMNS:
        raise BatteryDataError(
            f"Unexpected metadata columns: {metadata.columns.tolist()}"
        )
    if metadata.empty:
        raise BatteryDataError("Battery metadata is empty.")
    unknown_types = set(metadata["type"]).difference(BATTERY_TEST_TYPES)
    if unknown_types:
        raise BatteryDataError(f"Unknown battery test types: {sorted(unknown_types)}")

    for column in ("ambient_temperature", "test_id", "uid"):
        metadata[column] = pd.to_numeric(metadata[column], errors="raise").astype("int64")
    capacity_text = metadata["Capacity"].replace(list(_MISSING_TEXT), np.nan)
    metadata["Capacity"] = pd.to_numeric(capacity_text, errors="raise")
    metadata["Re"] = metadata["Re"].map(_optional_complex).astype("complex128")
    metadata["Rct"] = metadata["Rct"].map(_optional_complex).astype("complex128")
    metadata["start_time"] = metadata["start_time"].map(parse_start_time)

    if metadata["uid"].duplicated().any():
        raise BatteryDataError("Duplicate battery metadata uid values found.")
    if metadata["filename"].duplicated().any():
        raise BatteryDataError("Duplicate battery measurement filenames found.")
    if (metadata["ambient_temperature"] < -100).any():
        raise BatteryDataError("Implausible ambient temperature found.")

    for filename in metadata["filename"]:
        resolve_measurement_path(root, filename)
    return metadata


def _load_samples(path: Path, test_type: str) -> pd.DataFrame:
    samples = pd.read_csv(path, dtype=str, keep_default_na=False)
    expected = MEASUREMENT_COLUMNS[test_type]
    if tuple(samples.columns) != expected:
        raise BatteryDataError(
            f"Unexpected {test_type} columns in {path.name}: {samples.columns.tolist()}"
        )
    if samples.empty:
        raise BatteryDataError(f"Battery measurement file is empty: {path}")

    if test_type == "impedance":
        for column in expected:
            samples[column] = samples[column].map(_optional_complex)
            samples[column] = samples[column].astype("complex128")
    else:
        for column in expected:
            samples[column] = pd.to_numeric(samples[column], errors="raise")
        if samples.isna().any().any():
            raise BatteryDataError(f"Missing numeric samples found in {path.name}.")
    return samples


def load_battery_measurement(
    uid: int,
    metadata: pd.DataFrame | None = None,
    data_dir: str | Path | None = None,
) -> BatteryMeasurement:
    """Load one measurement record by its globally unique metadata UID."""

    root = _data_dir(data_dir)
    records = metadata if metadata is not None else load_battery_metadata(root)
    match = records.loc[records["uid"] == uid]
    if match.empty:
        raise KeyError(f"Battery measurement uid not found: {uid}")
    if len(match) != 1:
        raise BatteryDataError(f"Battery measurement uid is not unique: {uid}")
    record = match.iloc[0].copy()
    path = resolve_measurement_path(root, str(record["filename"]))
    samples = _load_samples(path, str(record["type"]))
    return BatteryMeasurement(metadata=record, samples=samples)


def summarize_battery_dataset(
    metadata: pd.DataFrame | None = None,
    data_dir: str | Path | None = None,
) -> dict[str, object]:
    """Return stable dimensions and target-availability counts."""

    records = metadata if metadata is not None else load_battery_metadata(data_dir)
    return {
        "metadata_rows": len(records),
        "battery_ids": int(records["battery_id"].nunique()),
        "measurement_files": int(records["filename"].nunique()),
        "test_types": {
            key: int(value)
            for key, value in records["type"].value_counts().sort_index().items()
        },
        "capacity_labels": int(records["Capacity"].notna().sum()),
        "resistance_labels": int(
            np.isfinite(records["Re"].to_numpy(dtype="complex128").real).sum()
        ),
        "charge_transfer_labels": int(
            np.isfinite(records["Rct"].to_numpy(dtype="complex128").real).sum()
        ),
        "ambient_temperature_min": int(records["ambient_temperature"].min()),
        "ambient_temperature_max": int(records["ambient_temperature"].max()),
    }


def build_battery_discharge_table(
    metadata: pd.DataFrame | None = None,
    data_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Create chronological SOH and documented-EOL RUL records.

    SOH is measured against the documented 2.0 Ah rated capacity. RUL is only
    available for battery groups whose source README states an EOL capacity and
    whose observed positive-capacity trajectory reaches that threshold.
    """

    records = metadata if metadata is not None else load_battery_metadata(data_dir)
    discharge = (
        records.loc[records["type"] == "discharge"]
        .sort_values(["battery_id", "start_time", "test_id", "uid"])
        .reset_index(drop=True)
        .copy()
    )
    discharge["discharge_cycle"] = (
        discharge.groupby("battery_id", sort=False).cumcount() + 1
    ).astype("int64")
    discharge["valid_capacity"] = discharge["Capacity"].notna() & (
        discharge["Capacity"] > 0
    )
    discharge["soh_percent"] = np.where(
        discharge["valid_capacity"],
        discharge["Capacity"] / RATED_CAPACITY_AH * 100.0,
        np.nan,
    )
    discharge["eol_capacity_ah"] = discharge["battery_id"].map(
        DOCUMENTED_EOL_CAPACITY_AH
    )
    initial_valid_capacity = (
        discharge.loc[discharge["valid_capacity"]]
        .groupby("battery_id")["Capacity"]
        .first()
    )
    discharge["initial_valid_capacity_ah"] = discharge["battery_id"].map(
        initial_valid_capacity
    )
    eligible_batteries = set(
        discharge.loc[
            discharge["eol_capacity_ah"].notna()
            & (
                discharge["initial_valid_capacity_ah"]
                > discharge["eol_capacity_ah"]
            ),
            "battery_id",
        ]
    )
    crossing = discharge.loc[
        discharge["valid_capacity"]
        & discharge["battery_id"].isin(eligible_batteries)
        & discharge["eol_capacity_ah"].notna()
        & (discharge["Capacity"] <= discharge["eol_capacity_ah"])
    ]
    first_eol_cycle = crossing.groupby("battery_id")["discharge_cycle"].min()
    discharge["observed_eol_cycle"] = discharge["battery_id"].map(first_eol_cycle)
    discharge["rul_cycles"] = np.where(
        discharge["observed_eol_cycle"].notna(),
        np.maximum(
            discharge["observed_eol_cycle"] - discharge["discharge_cycle"], 0
        ),
        np.nan,
    )
    discharge["at_or_after_documented_eol"] = (
        discharge["observed_eol_cycle"].notna()
        & (discharge["discharge_cycle"] >= discharge["observed_eol_cycle"])
    )
    discharge["rul_label_status"] = "no_documented_threshold"
    has_threshold = discharge["eol_capacity_ah"].notna()
    starts_below = has_threshold & (
        discharge["initial_valid_capacity_ah"] <= discharge["eol_capacity_ah"]
    )
    discharge.loc[starts_below, "rul_label_status"] = (
        "starts_at_or_below_threshold"
    )
    right_censored = (
        has_threshold
        & ~starts_below
        & discharge["observed_eol_cycle"].isna()
    )
    discharge.loc[right_censored, "rul_label_status"] = "right_censored"
    discharge.loc[
        discharge["observed_eol_cycle"].notna(), "rul_label_status"
    ] = "observed_eol"
    discharge["rul_training_eligible"] = (
        discharge["valid_capacity"]
        & discharge["rul_cycles"].notna()
        & (discharge["discharge_cycle"] <= discharge["observed_eol_cycle"])
    )
    return discharge


def summarize_battery_discharge_table(table: pd.DataFrame) -> dict[str, object]:
    """Summarize SOH label quality and documented-EOL RUL availability."""

    eol_batteries = table.loc[
        table["observed_eol_cycle"].notna(), "battery_id"
    ].nunique()
    return {
        "discharge_rows": len(table),
        "batteries": int(table["battery_id"].nunique()),
        "valid_capacity_rows": int(table["valid_capacity"].sum()),
        "missing_capacity_rows": int(table["Capacity"].isna().sum()),
        "zero_capacity_rows": int((table["Capacity"] == 0).sum()),
        "documented_threshold_batteries": len(DOCUMENTED_EOL_CAPACITY_AH),
        "observed_eol_batteries": int(eol_batteries),
        "rul_labeled_rows": int(table["rul_cycles"].notna().sum()),
        "rul_training_eligible_rows": int(table["rul_training_eligible"].sum()),
        "rul_label_status_batteries": {
            key: int(value)
            for key, value in (
                table.groupby("battery_id")["rul_label_status"]
                .first()
                .value_counts()
                .sort_index()
                .items()
            )
        },
        "soh_min": float(table["soh_percent"].min()),
        "soh_median": float(table["soh_percent"].median()),
        "soh_max": float(table["soh_percent"].max()),
    }
