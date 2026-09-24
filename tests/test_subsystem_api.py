"""End-to-end API tests for non-engine subsystem predictions."""

from fastapi.testclient import TestClient
import pandas as pd

from src.api.app import app
from src.data.battery import load_battery_measurement, load_battery_metadata
from src.data.fuel_system import FUEL_SENSOR_COLUMNS, load_fuel_scenario

client = TestClient(app)


def _battery_payload():
    metadata = load_battery_metadata()
    uid = int(metadata.loc[metadata["type"] == "discharge", "uid"].iloc[0])
    measurement = load_battery_measurement(uid, metadata)
    samples = measurement.samples
    return {
        "battery_id": measurement.metadata["battery_id"],
        "discharge_cycle": 1,
        "ambient_temperature": float(measurement.metadata["ambient_temperature"]),
        "samples": [
            {
                "voltage_measured": float(row.Voltage_measured),
                "current_measured": float(row.Current_measured),
                "temperature_measured": float(row.Temperature_measured),
                "current_load": float(row.Current_load),
                "voltage_load": float(row.Voltage_load),
                "time": float(row.Time),
            }
            for row in samples.itertuples(index=False)
        ],
    }


def test_battery_prediction_runs_from_raw_discharge_curve():
    response = client.post("/api/predict/battery", json=_battery_payload())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["component"] == "Battery"
    assert 0 <= body["predicted_soh_percent"] <= 150
    assert body["predicted_rul_cycles"] >= 0
    assert body["rul_lower_90_cycles"] <= body["predicted_rul_cycles"]
    assert body["rul_upper_90_cycles"] >= body["predicted_rul_cycles"]
    assert body["experimental_rul"] is True


def test_battery_request_rejects_duplicate_times():
    payload = _battery_payload()
    payload["samples"] = payload["samples"][:2]
    payload["samples"][1]["time"] = payload["samples"][0]["time"]
    response = client.post("/api/predict/battery", json=payload)

    assert response.status_code == 422
    assert "time values must be unique" in response.text


def test_fuel_prediction_builds_causal_features_from_ordered_samples():
    frame = load_fuel_scenario("normal").head(8)
    payload = {"samples": frame.loc[:, FUEL_SENSOR_COLUMNS].to_dict(orient="records")}
    response = client.post("/api/predict/fuel-system", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["component"] == "Fuel System"
    assert body["input_samples"] == 8
    assert isinstance(body["latest_is_abnormal"], bool)
    assert isinstance(body["latest_anomaly_margin"], float)


def test_hydraulic_prediction_uses_exact_processed_feature_contract():
    table = pd.read_csv("data/processed/hydraulic/cycle_features.csv")
    feature_columns = [
        column for column in table.columns
        if column not in {
            "cycle_id", "cooler_condition_percent", "valve_condition_percent",
            "pump_leakage_severity", "accumulator_pressure_bar", "stable_flag",
        }
    ]
    payload = {
        "cycle_id": int(table.iloc[0]["cycle_id"]),
        "features": {
            column: float(table.iloc[0][column]) for column in feature_columns
        },
        "operating_condition_stable": True,
    }
    response = client.post("/api/predict/hydraulic", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body["predictions"]) == {
        "cooler_condition_percent", "valve_condition_percent",
        "pump_leakage_severity", "accumulator_pressure_bar",
    }


def test_hydraulic_prediction_rejects_incomplete_features():
    response = client.post(
        "/api/predict/hydraulic",
        json={"cycle_id": 1, "features": {"ps1_mean": 1.0}},
    )

    assert response.status_code == 422
    assert "missing_features" in response.text


def test_landing_gear_prediction_returns_fault_and_rul():
    row = pd.read_csv("data/processed/landing_gear/validated_runs.csv").iloc[0]
    payload = {
        column: float(row[column])
        for column in (
            "max_deflection", "max_velocity", "settling_time", "mass",
            "k_stiffness", "b_damping",
        )
    }
    response = client.post("/api/predict/landing-gear", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fault_code"] in {0, 1, 2, 3}
    assert body["fault_name"]
    assert 0 <= body["predicted_rul_percent"] <= 100


def test_subsystem_model_registry_reports_all_saved_models():
    response = client.get("/api/models/subsystems")

    assert response.status_code == 200, response.text
    models = response.json()["models"]
    assert len(models) == 9
    assert all(item["available"] for item in models.values())
