"""Feature extraction shared by subsystem model pipelines."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.data.battery import (
    build_battery_discharge_table,
    load_battery_measurement,
    load_battery_metadata,
)

BATTERY_CURVE_FEATURES = (
    "sample_count",
    "duration_seconds",
    "voltage_start",
    "voltage_end",
    "voltage_min",
    "voltage_max",
    "voltage_mean",
    "voltage_std",
    "voltage_drop",
    "current_abs_mean",
    "current_std",
    "temperature_start",
    "temperature_end",
    "temperature_mean",
    "temperature_max",
    "temperature_rise",
    "load_current_abs_mean",
    "load_voltage_mean",
    "load_voltage_min",
    "charge_throughput_ah",
    "energy_throughput_wh",
)


def extract_battery_discharge_features(samples: pd.DataFrame) -> dict[str, float]:
    """Summarize one discharge curve without using its capacity label."""

    required = {
        "Voltage_measured",
        "Current_measured",
        "Temperature_measured",
        "Current_load",
        "Voltage_load",
        "Time",
    }
    missing = required.difference(samples.columns)
    if missing:
        raise ValueError(f"Missing discharge measurement columns: {sorted(missing)}")
    if len(samples) < 2:
        raise ValueError("At least two discharge samples are required.")
    ordered = samples.sort_values("Time")
    time_values = ordered["Time"].to_numpy(dtype=float)
    if np.any(np.diff(time_values) < 0):
        raise ValueError("Discharge time values must be monotonic after sorting.")
    voltage = ordered["Voltage_measured"].to_numpy(dtype=float)
    current = ordered["Current_measured"].to_numpy(dtype=float)
    temperature = ordered["Temperature_measured"].to_numpy(dtype=float)
    load_current = ordered["Current_load"].to_numpy(dtype=float)
    load_voltage = ordered["Voltage_load"].to_numpy(dtype=float)

    features = {
        "sample_count": float(len(ordered)),
        "duration_seconds": float(time_values[-1] - time_values[0]),
        "voltage_start": float(voltage[0]),
        "voltage_end": float(voltage[-1]),
        "voltage_min": float(voltage.min()),
        "voltage_max": float(voltage.max()),
        "voltage_mean": float(voltage.mean()),
        "voltage_std": float(voltage.std(ddof=0)),
        "voltage_drop": float(voltage[0] - voltage[-1]),
        "current_abs_mean": float(np.abs(current).mean()),
        "current_std": float(current.std(ddof=0)),
        "temperature_start": float(temperature[0]),
        "temperature_end": float(temperature[-1]),
        "temperature_mean": float(temperature.mean()),
        "temperature_max": float(temperature.max()),
        "temperature_rise": float(temperature[-1] - temperature[0]),
        "load_current_abs_mean": float(np.abs(load_current).mean()),
        "load_voltage_mean": float(load_voltage.mean()),
        "load_voltage_min": float(load_voltage.min()),
        "charge_throughput_ah": float(
            np.trapezoid(np.abs(current), time_values) / 3600.0
        ),
        "energy_throughput_wh": float(
            np.trapezoid(voltage * np.abs(current), time_values) / 3600.0
        ),
    }
    if not np.isfinite(list(features.values())).all():
        raise ValueError("Battery feature extraction produced non-finite values.")
    return features


def build_battery_soh_feature_table(
    discharge_table: pd.DataFrame | None = None,
    data_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Build one SOH-training row per positive-capacity discharge test."""

    metadata = load_battery_metadata(data_dir)
    discharge = (
        discharge_table
        if discharge_table is not None
        else build_battery_discharge_table(metadata, data_dir)
    )
    valid = discharge.loc[discharge["valid_capacity"]].copy()
    rows: list[dict[str, object]] = []

    for record in valid.itertuples(index=False):
        measurement = load_battery_measurement(int(record.uid), metadata, data_dir)
        features = extract_battery_discharge_features(measurement.samples)
        rows.append(
            {
                "battery_id": record.battery_id,
                "uid": int(record.uid),
                "discharge_cycle": int(record.discharge_cycle),
                "ambient_temperature": int(record.ambient_temperature),
                **features,
                "soh_percent": float(record.soh_percent),
            }
        )
    table = pd.DataFrame(rows)
    if len(table) != int(discharge["valid_capacity"].sum()):
        raise RuntimeError("Battery SOH feature rows do not match valid capacities.")
    return table.sort_values(["battery_id", "discharge_cycle"]).reset_index(drop=True)
