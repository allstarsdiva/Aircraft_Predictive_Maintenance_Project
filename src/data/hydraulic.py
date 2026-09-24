"""Load and validate the UCI hydraulic condition-monitoring dataset."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

HYDRAULIC_CYCLES = 2205
PROFILE_COLUMNS = (
    "cooler_condition_percent",
    "valve_condition_percent",
    "pump_leakage_severity",
    "accumulator_pressure_bar",
    "stable_flag",
)
PROFILE_ALLOWED_VALUES = {
    "cooler_condition_percent": frozenset({3, 20, 100}),
    "valve_condition_percent": frozenset({73, 80, 90, 100}),
    "pump_leakage_severity": frozenset({0, 1, 2}),
    "accumulator_pressure_bar": frozenset({90, 100, 115, 130}),
    "stable_flag": frozenset({0, 1}),
}


@dataclass(frozen=True)
class HydraulicSensorSpec:
    physical_quantity: str
    unit: str
    sampling_hz: int

    @property
    def samples_per_cycle(self) -> int:
        return self.sampling_hz * 60


HYDRAULIC_SENSORS = {
    **{
        f"PS{number}": HydraulicSensorSpec("pressure", "bar", 100)
        for number in range(1, 7)
    },
    "EPS1": HydraulicSensorSpec("motor power", "W", 100),
    "FS1": HydraulicSensorSpec("volume flow", "l/min", 10),
    "FS2": HydraulicSensorSpec("volume flow", "l/min", 10),
    **{
        f"TS{number}": HydraulicSensorSpec("temperature", "degC", 1)
        for number in range(1, 5)
    },
    "VS1": HydraulicSensorSpec("vibration", "mm/s", 1),
    "CE": HydraulicSensorSpec("cooling efficiency", "%", 1),
    "CP": HydraulicSensorSpec("cooling power", "kW", 1),
    "SE": HydraulicSensorSpec("efficiency factor", "%", 1),
}


class HydraulicDataError(ValueError):
    """Raised when a hydraulic source file violates the documented schema."""


def default_hydraulic_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "raw" / "hydraulic"


def _root(data_dir: str | Path | None) -> Path:
    return Path(data_dir) if data_dir is not None else default_hydraulic_data_dir()


def _read_numeric_matrix(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Hydraulic source file not found: {path}")
    try:
        frame = pd.read_csv(path, sep=r"\s+", header=None, dtype=np.float64)
    except (ValueError, pd.errors.ParserError) as exc:
        raise HydraulicDataError(f"Could not parse numeric matrix: {path.name}") from exc
    if frame.empty:
        raise HydraulicDataError(f"Hydraulic source file is empty: {path.name}")
    if not np.isfinite(frame.to_numpy()).all():
        raise HydraulicDataError(f"Non-finite values found in {path.name}")
    return frame


def load_hydraulic_profile(
    data_dir: str | Path | None = None,
    expected_cycles: int = HYDRAULIC_CYCLES,
) -> pd.DataFrame:
    """Load the five cycle-level condition labels."""

    profile = _read_numeric_matrix(_root(data_dir) / "profile.txt")
    if profile.shape != (expected_cycles, len(PROFILE_COLUMNS)):
        raise HydraulicDataError(
            "Unexpected profile shape: "
            f"{profile.shape}; expected {(expected_cycles, len(PROFILE_COLUMNS))}"
        )
    profile.columns = PROFILE_COLUMNS
    if not np.equal(profile.to_numpy(), np.floor(profile.to_numpy())).all():
        raise HydraulicDataError("Hydraulic profile labels must be integers.")
    profile = profile.astype("int64")
    for column, allowed in PROFILE_ALLOWED_VALUES.items():
        observed = set(profile[column].unique())
        if not observed.issubset(allowed):
            raise HydraulicDataError(
                f"Unexpected {column} labels: {sorted(observed.difference(allowed))}"
            )
    profile.insert(0, "cycle_id", np.arange(1, expected_cycles + 1, dtype=int))
    return profile


def load_hydraulic_sensor(
    sensor: str,
    data_dir: str | Path | None = None,
    expected_cycles: int = HYDRAULIC_CYCLES,
) -> pd.DataFrame:
    """Load one sensor matrix and enforce cycle and sampling dimensions."""

    normalized = sensor.upper()
    if normalized not in HYDRAULIC_SENSORS:
        raise KeyError(f"Unknown hydraulic sensor: {sensor}")
    spec = HYDRAULIC_SENSORS[normalized]
    frame = _read_numeric_matrix(_root(data_dir) / f"{normalized}.txt")
    expected_shape = (expected_cycles, spec.samples_per_cycle)
    if frame.shape != expected_shape:
        raise HydraulicDataError(
            f"Unexpected {normalized} shape: {frame.shape}; expected {expected_shape}"
        )
    return frame


def hydraulic_profile_summary(profile: pd.DataFrame) -> dict[str, object]:
    """Return stable label counts for inventory and reporting."""

    return {
        "cycles": len(profile),
        "stable_cycles": int((profile["stable_flag"] == 0).sum()),
        "potentially_unstable_cycles": int((profile["stable_flag"] == 1).sum()),
        "target_counts": {
            column: {
                str(key): int(value)
                for key, value in profile[column].value_counts().sort_index().items()
            }
            for column in PROFILE_COLUMNS[:-1]
        },
    }
