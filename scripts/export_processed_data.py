"""Export reproducible subsystem-processed tables and their manifest."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.battery import build_battery_discharge_table
from src.data.cmapss import load_training_with_rul
from src.preprocess_landing_gear import save_processed_landing_gear
from src.preprocessing import add_causal_engine_features, split_engine_units


PROCESSED_ROOT = PROJECT_ROOT / "data" / "processed"


def _file_entry(path: Path, rows: int, columns: int, description: str) -> dict[str, object]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "rows": rows,
        "columns": columns,
        "bytes": path.stat().st_size,
        "sha256": digest,
        "description": description,
    }


def export_engine() -> list[dict[str, object]]:
    output_dir = PROCESSED_ROOT / "engine"
    output_dir.mkdir(parents=True, exist_ok=True)
    labeled = add_causal_engine_features(load_training_with_rul("FD001"))
    labeled_path = output_dir / "fd001_labeled_features.csv"
    labeled.to_csv(labeled_path, index=False)

    split = split_engine_units(labeled, validation_size=0.2, random_state=42)
    unit_split = pd.DataFrame(
        {
            "unit_id": sorted(split.train_units | split.validation_units),
        }
    )
    unit_split["split"] = unit_split["unit_id"].map(
        lambda unit: "train" if unit in split.train_units else "validation"
    )
    split_path = output_dir / "fd001_unit_split.csv"
    unit_split.to_csv(split_path, index=False)
    return [
        _file_entry(
            labeled_path,
            len(labeled),
            len(labeled.columns),
            "FD001 source columns, causal trend features, and raw RUL labels.",
        ),
        _file_entry(
            split_path,
            len(unit_split),
            len(unit_split.columns),
            "Deterministic engine-level 80/20 train-validation assignment.",
        ),
    ]


def export_battery() -> list[dict[str, object]]:
    output_dir = PROCESSED_ROOT / "battery"
    output_dir.mkdir(parents=True, exist_ok=True)
    discharge = build_battery_discharge_table()
    columns = [
        "battery_id",
        "uid",
        "filename",
        "start_time",
        "ambient_temperature",
        "test_id",
        "discharge_cycle",
        "Capacity",
        "valid_capacity",
        "soh_percent",
        "eol_capacity_ah",
        "initial_valid_capacity_ah",
        "observed_eol_cycle",
        "rul_cycles",
        "at_or_after_documented_eol",
        "rul_label_status",
        "rul_training_eligible",
    ]
    path = output_dir / "discharge_cycles.csv"
    discharge[columns].to_csv(path, index=False)
    entries = [
        _file_entry(
            path,
            len(discharge),
            len(columns),
            "Chronological discharge cycles with SOH, censoring, and eligible RUL labels.",
        )
    ]
    features_path = output_dir / "soh_features.csv"
    if features_path.is_file():
        features = pd.read_csv(features_path)
        entries.append(
            _file_entry(
                features_path,
                len(features),
                len(features.columns),
                "Curve-derived discharge features and SOH targets for grouped modeling.",
            )
        )
    rul_features_path = output_dir / "rul_features.csv"
    if rul_features_path.is_file():
        rul_features = pd.read_csv(rul_features_path)
        entries.append(
            _file_entry(
                rul_features_path,
                len(rul_features),
                len(rul_features.columns),
                "Curve-derived features for direct-RUL rows from observed-EOL batteries.",
            )
        )
    return entries


def export_hydraulic() -> list[dict[str, object]]:
    output_dir = PROCESSED_ROOT / "hydraulic"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "cycle_features.csv"
    if not path.is_file():
        return []
    table = pd.read_csv(path)
    return [
        _file_entry(
            path,
            len(table),
            len(table.columns),
            "Validated cycle-level sensor statistics and hydraulic condition targets.",
        )
    ]


def export_fuel_system() -> list[dict[str, object]]:
    output_dir = PROCESSED_ROOT / "fuel_system"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "scenario_features.csv"
    if not path.is_file():
        return []
    table = pd.read_csv(path)
    return [
        _file_entry(
            path,
            len(table),
            len(table.columns),
            "Five fuel-system trajectories with neutral scenario labels and causal features.",
        )
    ]


def export_landing_gear() -> list[dict[str, object]]:
    output_dir = PROCESSED_ROOT / "landing_gear"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = save_processed_landing_gear(output_dir / "validated_runs.csv")
    table = pd.read_csv(path)
    return [
        _file_entry(
            path,
            len(table),
            len(table.columns),
            "Validated synthetic landing events with normalized labels and leakage-safe feature definitions.",
        )
    ]


def main() -> None:
    for component in (
        "engine",
        "battery",
        "hydraulic",
        "fuel_system",
        "landing_gear",
    ):
        (PROCESSED_ROOT / component).mkdir(parents=True, exist_ok=True)
    manifest = {
        "engine": {"status": "processed", "files": export_engine()},
        "battery": {"status": "processed", "files": export_battery()},
        "hydraulic": {
            "status": "processed" if (PROCESSED_ROOT / "hydraulic" / "cycle_features.csv").is_file() else "not_processed",
            "files": export_hydraulic(),
        },
        "fuel_system": {
            "status": "processed" if (PROCESSED_ROOT / "fuel_system" / "scenario_features.csv").is_file() else "not_processed",
            "files": export_fuel_system(),
        },
        "landing_gear": {"status": "processed", "files": export_landing_gear()},
    }
    path = PROCESSED_ROOT / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
