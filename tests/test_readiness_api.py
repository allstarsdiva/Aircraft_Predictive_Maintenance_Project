"""End-to-end checks for readiness-v2 intervals and abstention."""

import pandas as pd
from fastapi.testclient import TestClient

from src.api.app import app
from src.data.battery import load_battery_measurement, load_battery_metadata
from src.data.cmapss import load_cmapss

client = TestClient(app)


def _engine_records():
    frame = load_cmapss("FD001", "test")
    rows = frame.loc[frame["unit_id"] == 1].head(12)
    return [{
        key: int(value) if key in {"unit_id", "cycle"} else float(value)
        for key, value in row.items()
    } for row in rows.to_dict(orient="records")]


def _battery_payload():
    metadata = load_battery_metadata()
    uid = int(metadata.loc[metadata["type"] == "discharge", "uid"].iloc[0])
    measurement = load_battery_measurement(uid, metadata)
    return {
        "battery_id": str(measurement.metadata["battery_id"]),
        "discharge_cycle": 1,
        "ambient_temperature": float(measurement.metadata["ambient_temperature"]),
        "samples": [{
            "voltage_measured": float(row.Voltage_measured),
            "current_measured": float(row.Current_measured),
            "temperature_measured": float(row.Temperature_measured),
            "current_load": float(row.Current_load),
            "voltage_load": float(row.Voltage_load),
            "time": float(row.Time),
        } for row in measurement.samples.itertuples(index=False)],
    }


def test_engine_readiness_returns_interval_and_support_state():
    response = client.post(
        "/api/v2/predict/engine", json={"subset": "FD001", "records": _engine_records()}
    )
    assert response.status_code == 200, response.text
    rul = response.json()["rul"]
    assert rul["lower"] <= rul["value"] <= rul["upper"]
    assert rul["interval_level"] == 0.95
    assert isinstance(rul["accepted"], bool)


def test_battery_readiness_returns_soh_and_rul_intervals():
    response = client.post("/api/v2/predict/battery", json=_battery_payload())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["soh"]["lower"] <= body["soh"]["value"] <= body["soh"]["upper"]
    assert body["rul"]["lower"] <= body["rul"]["value"] <= body["rul"]["upper"]


def test_hydraulic_readiness_returns_confidence_and_abstention():
    row = pd.read_csv("data/processed/hydraulic/cycle_features.csv").iloc[0]
    excluded = {
        "cycle_id", "cooler_condition_percent", "valve_condition_percent",
        "pump_leakage_severity", "accumulator_pressure_bar", "stable_flag",
    }
    payload = {
        "cycle_id": 1,
        "features": {key: float(value) for key, value in row.items() if key not in excluded},
        "operating_condition_stable": True,
    }
    response = client.post("/api/v2/predict/hydraulic", json=payload)
    assert response.status_code == 200, response.text
    assert len(response.json()["predictions"]) == 4
    for result in response.json()["predictions"].values():
        assert 0 <= result["calibrated_confidence"] <= 1
        assert isinstance(result["accepted"], bool)


def test_landing_readiness_uses_only_observable_features_and_rejects_ood():
    response = client.post("/api/v2/predict/landing-gear", json={
        "max_deflection": 0.3, "max_velocity": 0.65,
        "settling_time": 0.36, "mass": 3000,
    })
    assert response.status_code == 200, response.text
    assert "observable" in response.json()["fault_model"]

    outside = client.post("/api/v2/predict/landing-gear", json={
        "max_deflection": 3.0, "max_velocity": 6.5,
        "settling_time": 3.6, "mass": 30000,
    })
    assert outside.status_code == 200
    assert outside.json()["fault"]["accepted"] is False
    assert outside.json()["rul"]["accepted"] is False


def test_readiness_status_blocks_fuel_and_never_claims_aircraft_validation():
    response = client.get("/api/v2/readiness")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["real_aircraft_validated"] is False
    assert body["fuel_prediction_enabled"] is False
    assert body["model_gates"]["fuel_system"] == "fail"
