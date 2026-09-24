"""Build cycle-level features from UCI hydraulic sensor waveforms."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.hydraulic import (
    HYDRAULIC_SENSORS,
    default_hydraulic_data_dir,
    hydraulic_profile_summary,
    load_hydraulic_profile,
    load_hydraulic_sensor,
)

HYDRAULIC_SUMMARY_STATISTICS = (
    "mean",
    "std",
    "min",
    "max",
    "range",
    "rms",
    "slope",
)


def summarize_sensor_cycles(values: pd.DataFrame, sensor: str) -> pd.DataFrame:
    """Extract fixed-width waveform statistics for every operating cycle."""

    matrix = values.to_numpy(dtype=np.float64, copy=False)
    if matrix.ndim != 2 or matrix.shape[1] < 2:
        raise ValueError("A hydraulic sensor matrix needs at least two samples per cycle.")
    normalized = sensor.lower()
    minimum = matrix.min(axis=1)
    maximum = matrix.max(axis=1)
    time = np.linspace(0.0, 1.0, matrix.shape[1], dtype=np.float64)
    centered_time = time - time.mean()
    slope = matrix @ centered_time / np.square(centered_time).sum()
    result = pd.DataFrame(
        {
            f"{normalized}_mean": matrix.mean(axis=1),
            f"{normalized}_std": matrix.std(axis=1),
            f"{normalized}_min": minimum,
            f"{normalized}_max": maximum,
            f"{normalized}_range": maximum - minimum,
            f"{normalized}_rms": np.sqrt(np.mean(np.square(matrix), axis=1)),
            f"{normalized}_slope": slope,
        }
    )
    if not np.isfinite(result.to_numpy()).all():
        raise ValueError(f"Non-finite summary features produced for {sensor}.")
    return result


def build_hydraulic_feature_table(
    data_dir: str | Path | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Validate all raw files and return one feature row per aligned cycle."""

    root = Path(data_dir) if data_dir is not None else default_hydraulic_data_dir()
    profile = load_hydraulic_profile(root)
    feature_parts: list[pd.DataFrame] = []
    sensor_inventory: dict[str, object] = {}
    for sensor, spec in HYDRAULIC_SENSORS.items():
        values = load_hydraulic_sensor(sensor, root)
        feature_parts.append(summarize_sensor_cycles(values, sensor))
        sensor_inventory[sensor] = {
            "physical_quantity": spec.physical_quantity,
            "unit": spec.unit,
            "sampling_hz": spec.sampling_hz,
            "cycles": len(values),
            "samples_per_cycle": values.shape[1],
        }
    features = pd.concat(feature_parts, axis=1)
    table = pd.concat([profile.reset_index(drop=True), features], axis=1)
    expected_columns = 1 + 5 + len(HYDRAULIC_SENSORS) * len(
        HYDRAULIC_SUMMARY_STATISTICS
    )
    if table.shape != (len(profile), expected_columns):
        raise RuntimeError(f"Unexpected processed hydraulic shape: {table.shape}")
    report = {
        **hydraulic_profile_summary(profile),
        "raw_sensor_files": len(HYDRAULIC_SENSORS),
        "processed_rows": len(table),
        "processed_columns": len(table.columns),
        "feature_columns": len(features.columns),
        "summary_statistics": list(HYDRAULIC_SUMMARY_STATISTICS),
        "sensors": sensor_inventory,
        "missing_values": int(table.isna().sum().sum()),
    }
    return table, report


def preprocess_hydraulic_dataset(project_root: Path) -> dict[str, object]:
    """Create the processed table and machine-readable validation report."""

    table, report = build_hydraulic_feature_table(
        project_root / "data" / "raw" / "hydraulic"
    )
    processed_dir = project_root / "data" / "processed" / "hydraulic"
    metrics_dir = project_root / "reports" / "metrics"
    processed_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    output_path = processed_dir / "cycle_features.csv"
    table.to_csv(output_path, index=False)
    report["processed_path"] = str(output_path.relative_to(project_root))
    (metrics_dir / "hydraulic_data_validation.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(preprocess_hydraulic_dataset(root), indent=2))


if __name__ == "__main__":
    main()
