"""Leakage-safe preparation of the landing-gear event table."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.landing_gear import (
    LANDING_GEAR_FAULT_NAMES,
    LANDING_GEAR_FEATURE_COLUMNS,
    load_landing_gear_dataset,
)

LANDING_GEAR_MODEL_FEATURES = tuple(column.lower() for column in LANDING_GEAR_FEATURE_COLUMNS)
LANDING_GEAR_RENAME_MAP = {
    "RunID": "run_id",
    "Max_Deflection": "max_deflection",
    "Max_Velocity": "max_velocity",
    "Settling_Time": "settling_time",
    "Mass": "mass",
    "K_Stiffness": "k_stiffness",
    "B_Damping": "b_damping",
    "Fault_Code": "fault_code",
    "RUL": "rul_percent",
}


def prepare_landing_gear_table(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    """Create a normalized event table without fitting dataset-wide transforms."""

    raw = load_landing_gear_dataset() if frame is None else frame.copy()
    required = set(LANDING_GEAR_RENAME_MAP)
    missing = sorted(required - set(raw.columns))
    if missing:
        raise ValueError(f"Missing landing-gear columns: {missing}")

    prepared = raw.loc[:, list(LANDING_GEAR_RENAME_MAP)].rename(
        columns=LANDING_GEAR_RENAME_MAP
    )
    prepared["is_fault"] = (prepared["fault_code"] != 0).astype(int)
    prepared["fault_name"] = prepared["fault_code"].map(LANDING_GEAR_FAULT_NAMES)
    if prepared["fault_name"].isna().any():
        raise ValueError("Unknown landing-gear fault code found")
    return prepared


def save_processed_landing_gear(
    output_path: str | Path | None = None,
) -> Path:
    """Validate and save the reproducible component-level modeling table."""

    path = (
        Path(output_path)
        if output_path is not None
        else Path(__file__).resolve().parents[1]
        / "data"
        / "processed"
        / "landing_gear"
        / "validated_runs.csv"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    prepare_landing_gear_table().to_csv(path, index=False)
    return path


if __name__ == "__main__":
    print(save_processed_landing_gear())
