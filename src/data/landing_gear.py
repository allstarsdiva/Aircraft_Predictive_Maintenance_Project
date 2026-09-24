"""Load and validate the aircraft landing-gear digital-twin dataset."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

LANDING_GEAR_RAW_COLUMNS = (
    "RunID",
    "Max_Deflection",
    "Max_Velocity",
    "Settling_Time",
    "Mass",
    "K_Stiffness",
    "B_Damping",
    "Fault_Code",
    "RUL",
)
LANDING_GEAR_FEATURE_COLUMNS = (
    "Max_Deflection",
    "Max_Velocity",
    "Settling_Time",
    "Mass",
    "K_Stiffness",
    "B_Damping",
)
LANDING_GEAR_FAULT_NAMES = {
    0: "normal_operation",
    1: "nitrogen_gas_leak",
    2: "worn_seal",
    3: "early_structural_degradation",
}
LANDING_GEAR_EXPECTED_ROWS = 1_500


class LandingGearDataError(ValueError):
    """Raised when the landing-gear CSV violates its documented schema."""


def default_landing_gear_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "raw"
        / "landing_gear"
        / "LandingGear_Balanced_Dataset.csv"
    )


def load_landing_gear_dataset(
    path: str | Path | None = None,
    expected_rows: int | None = LANDING_GEAR_EXPECTED_ROWS,
) -> pd.DataFrame:
    """Load the event table and enforce schema, identifiers, and target bounds."""

    source = Path(path) if path is not None else default_landing_gear_path()
    if not source.is_file():
        raise FileNotFoundError(f"Landing-gear dataset not found: {source}")
    try:
        frame = pd.read_csv(source)
    except (ValueError, pd.errors.ParserError) as exc:
        raise LandingGearDataError(f"Could not parse {source.name}") from exc

    if tuple(frame.columns) != LANDING_GEAR_RAW_COLUMNS:
        raise LandingGearDataError(
            f"Unexpected columns in {source.name}: {frame.columns.tolist()}"
        )
    if expected_rows is not None and len(frame) != expected_rows:
        raise LandingGearDataError(
            f"Unexpected rows in {source.name}: {len(frame)}; expected {expected_rows}"
        )

    for column in LANDING_GEAR_RAW_COLUMNS:
        try:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise LandingGearDataError(f"Nonnumeric values in column {column}") from exc
    if not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise LandingGearDataError("Missing or non-finite values found")

    run_ids = frame["RunID"].to_numpy(dtype=float)
    if (run_ids <= 0).any() or not np.equal(run_ids, np.floor(run_ids)).all():
        raise LandingGearDataError("RunID values must be positive integers")
    if frame["RunID"].duplicated().any():
        raise LandingGearDataError("Duplicate RunID values found")

    fault_codes = frame["Fault_Code"].to_numpy(dtype=float)
    if not np.equal(fault_codes, np.floor(fault_codes)).all():
        raise LandingGearDataError("Fault_Code values must be integers")
    unknown_codes = sorted(set(frame["Fault_Code"].astype(int)) - LANDING_GEAR_FAULT_NAMES.keys())
    if unknown_codes:
        raise LandingGearDataError(f"Unknown Fault_Code values: {unknown_codes}")

    if not frame["RUL"].between(0.0, 100.0, inclusive="both").all():
        raise LandingGearDataError("RUL values must be percentages between 0 and 100")
    if (frame[list(LANDING_GEAR_FEATURE_COLUMNS)] <= 0).any().any():
        raise LandingGearDataError("Physical feature values must be positive")

    frame["RunID"] = frame["RunID"].astype(int)
    frame["Fault_Code"] = frame["Fault_Code"].astype(int)
    return frame


def summarize_landing_gear_dataset(frame: pd.DataFrame) -> dict[str, object]:
    """Return compact structural diagnostics for reporting and tests."""

    return {
        "rows": len(frame),
        "columns": len(frame.columns),
        "missing_values": int(frame.isna().sum().sum()),
        "duplicate_rows": int(frame.duplicated().sum()),
        "duplicate_run_ids": int(frame["RunID"].duplicated().sum()),
        "fault_counts": {
            str(code): int(count)
            for code, count in frame["Fault_Code"].value_counts().sort_index().items()
        },
        "rul_range_percent": {
            "min": float(frame["RUL"].min()),
            "max": float(frame["RUL"].max()),
        },
        "feature_ranges": {
            column: {
                "min": float(frame[column].min()),
                "max": float(frame[column].max()),
            }
            for column in LANDING_GEAR_FEATURE_COLUMNS
        },
    }
