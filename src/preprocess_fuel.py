"""Causal preprocessing for Aircraft Fuel Distribution System scenarios."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.fuel_system import (
    FUEL_SENSOR_COLUMNS,
    load_fuel_system_dataset,
    summarize_fuel_system_dataset,
)


def add_causal_fuel_features(
    table: pd.DataFrame, rolling_window: int = 5
) -> pd.DataFrame:
    """Add within-scenario changes and trailing statistics without future rows."""

    if rolling_window < 2:
        raise ValueError("rolling_window must be at least two.")
    required = {"scenario_id", "scenario_code", "sample_index", *FUEL_SENSOR_COLUMNS}
    missing = required.difference(table.columns)
    if missing:
        raise ValueError(f"Missing fuel-system columns: {sorted(missing)}")
    ordered = table.sort_values(["scenario_code", "sample_index"]).reset_index(drop=True)
    result = ordered.copy()
    grouped = ordered.groupby("scenario_id", sort=False)
    for column in FUEL_SENSOR_COLUMNS:
        result[f"{column}_delta_1"] = grouped[column].diff().fillna(0.0)
        result[f"{column}_rolling_mean_{rolling_window}"] = grouped[column].transform(
            lambda values: values.rolling(rolling_window, min_periods=1).mean()
        )
        result[f"{column}_rolling_std_{rolling_window}"] = grouped[column].transform(
            lambda values: values.rolling(rolling_window, min_periods=1).std(ddof=0)
        )
    numeric = result.select_dtypes(include=[np.number])
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise RuntimeError("Fuel preprocessing produced non-finite features.")
    return result


def preprocess_fuel_system_dataset(project_root: Path) -> dict[str, object]:
    """Validate raw scenarios and save a modeling-ready causal feature table."""

    raw = load_fuel_system_dataset(project_root / "data" / "raw" / "fuel_system")
    processed = add_causal_fuel_features(raw)
    processed_dir = project_root / "data" / "processed" / "fuel_system"
    metrics_dir = project_root / "reports" / "metrics"
    processed_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    output_path = processed_dir / "scenario_features.csv"
    processed.to_csv(output_path, index=False)
    report = {
        **summarize_fuel_system_dataset(raw),
        "raw_feature_columns": len(FUEL_SENSOR_COLUMNS),
        "derived_feature_columns": len(FUEL_SENSOR_COLUMNS) * 3,
        "model_feature_columns": len(FUEL_SENSOR_COLUMNS) * 4,
        "processed_rows": len(processed),
        "processed_columns": len(processed.columns),
        "rolling_window": 5,
        "processed_path": str(output_path.relative_to(project_root)),
        "scenario_semantics": {
            "normal": "authoritatively identified normal scenario",
            "one_to_four": "authoritatively abnormal; individual fault names not published with the extracted files",
        },
        "validation_warning": (
            "Only one normal and four abnormal trajectories are available. "
            "Random row splitting would overstate generalization."
        ),
    }
    (metrics_dir / "fuel_system_data_validation.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(preprocess_fuel_system_dataset(root), indent=2))


if __name__ == "__main__":
    main()
