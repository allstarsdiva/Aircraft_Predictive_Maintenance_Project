"""Load and validate the Aircraft Fuel Distribution System dataset."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

FUEL_SENSOR_COLUMNS = (
    "FTL",
    "CTL",
    "FTF",
    "FTV_S",
    "CLF",
    "CLV_S",
    "FTT",
    "CRTT",
)
FUEL_SCENARIO_FILES = {
    "normal": "Scenario_Normal.csv",
    "one": "Scenario_One.csv",
    "two": "Scenario_Two.csv",
    "three": "Scenario_Three.csv",
    "four": "Scenario_Four.csv",
}
FUEL_SCENARIO_CODES = {
    scenario: code for code, scenario in enumerate(FUEL_SCENARIO_FILES)
}
FUEL_ROWS_PER_SCENARIO = 171


class FuelSystemDataError(ValueError):
    """Raised when a fuel-system CSV violates the verified local schema."""


def default_fuel_system_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "raw" / "fuel_system"


def _root(data_dir: str | Path | None) -> Path:
    return Path(data_dir) if data_dir is not None else default_fuel_system_data_dir()


def load_fuel_scenario(
    scenario: str,
    data_dir: str | Path | None = None,
    expected_rows: int = FUEL_ROWS_PER_SCENARIO,
) -> pd.DataFrame:
    """Load one scenario while preserving its source-row chronology."""

    normalized = scenario.lower()
    if normalized not in FUEL_SCENARIO_FILES:
        raise KeyError(f"Unknown fuel-system scenario: {scenario}")
    path = _root(data_dir) / FUEL_SCENARIO_FILES[normalized]
    if not path.is_file():
        raise FileNotFoundError(f"Fuel-system scenario file not found: {path}")
    try:
        frame = pd.read_csv(path)
    except (ValueError, pd.errors.ParserError) as exc:
        raise FuelSystemDataError(f"Could not parse {path.name}") from exc
    if tuple(frame.columns) != FUEL_SENSOR_COLUMNS:
        raise FuelSystemDataError(
            f"Unexpected columns in {path.name}: {frame.columns.tolist()}"
        )
    if len(frame) != expected_rows:
        raise FuelSystemDataError(
            f"Unexpected rows in {path.name}: {len(frame)}; expected {expected_rows}"
        )
    for column in FUEL_SENSOR_COLUMNS:
        try:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise FuelSystemDataError(
                f"Nonnumeric values in {path.name} column {column}"
            ) from exc
    if not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise FuelSystemDataError(f"Missing or non-finite values found in {path.name}")
    frame.insert(0, "sample_index", np.arange(1, len(frame) + 1, dtype=int))
    frame.insert(0, "is_abnormal", int(normalized != "normal"))
    frame.insert(0, "scenario_code", FUEL_SCENARIO_CODES[normalized])
    frame.insert(0, "scenario_id", normalized)
    return frame


def load_fuel_system_dataset(
    data_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Combine all five verified scenarios into one chronological table."""

    table = pd.concat(
        [load_fuel_scenario(scenario, data_dir) for scenario in FUEL_SCENARIO_FILES],
        ignore_index=True,
    )
    expected_rows = FUEL_ROWS_PER_SCENARIO * len(FUEL_SCENARIO_FILES)
    if len(table) != expected_rows:
        raise RuntimeError("Combined fuel-system row count is inconsistent.")
    if table.duplicated(subset=["scenario_id", "sample_index"]).any():
        raise FuelSystemDataError("Duplicate fuel scenario/sample identifiers found.")
    return table


def summarize_fuel_system_dataset(table: pd.DataFrame) -> dict[str, object]:
    """Return structural and label diagnostics for reporting."""

    return {
        "rows": len(table),
        "sensor_columns": len(FUEL_SENSOR_COLUMNS),
        "scenario_counts": {
            key: int(value)
            for key, value in table["scenario_id"].value_counts(sort=False).items()
        },
        "binary_target_counts": {
            str(key): int(value)
            for key, value in table["is_abnormal"].value_counts().sort_index().items()
        },
        "missing_values": int(table.isna().sum().sum()),
        "duplicate_sensor_rows": int(
            table.duplicated(subset=list(FUEL_SENSOR_COLUMNS)).sum()
        ),
        "sensor_ranges": {
            column: {
                "min": float(table[column].min()),
                "max": float(table[column].max()),
            }
            for column in FUEL_SENSOR_COLUMNS
        },
    }
