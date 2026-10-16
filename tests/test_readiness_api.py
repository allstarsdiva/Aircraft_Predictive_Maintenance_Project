"""End-to-end checks for readiness-v2 intervals and abstention."""

import pandas as pd
import pytest
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
    assert rul["top_model_features"]
    assert all(0 < item["relative_importance"] <= 100 for item in rul["top_model_features"])


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


@pytest.mark.parametrize("component", ["engine", "battery", "hydraulic", "landing-gear", "fuel-system"])
def test_preflight_checks_dataset_examples_without_returning_predictions(component):
    example = client.get(f"/api/workspace/examples/{component}", params={"variant": "normal"})
    assert example.status_code == 200, example.text
    response = client.post(f"/api/v2/preflight/{component}", json=example.json()["payload"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema_valid"] is True
    assert "review_required" in body
    assert body["checks"]
    assert "prediction" not in body
    notes = " ".join(body["notes"]).lower()
    if component == "engine":
        assert "physical units" in notes and "does not publish" in notes
    elif component == "battery":
        assert "voltage" in notes and "degrees c" in notes and "cannot verify" in notes
    elif component == "hydraulic":
        assert "bar" in notes and "l/min" in notes and "cannot be verified" in notes
    elif component == "landing-gear":
        assert "max_deflection m" in notes and "mass kg" in notes
    if component == "fuel-system":
        assert body["review_required"] is True
        assert body["checks"]["anomaly_detection"]["status"] == "not_assessed"
        assert "percent" in notes and "unpublished" in notes


def test_preflight_schema_errors_reject_without_running_prediction():
    response = client.post("/api/v2/preflight/landing-gear", json={
        "max_deflection": 0.3, "max_velocity": 0.65, "settling_time": 0.36,
        "mass": 3000, "unexpected_sensor": 5,
    })
    assert response.status_code == 422
    assert "prediction" not in response.json()


@pytest.mark.parametrize(
    ("component", "missing_key"),
    [
        ("engine", "records"),
        ("battery", "samples"),
        ("hydraulic", "features"),
        ("landing-gear", "max_deflection"),
        ("fuel-system", "samples"),
    ],
)
def test_preflight_rejects_incomplete_uploads_with_a_field_path(component, missing_key):
    example = client.get(f"/api/workspace/examples/{component}", params={"variant": "normal"})
    assert example.status_code == 200, example.text
    payload = dict(example.json()["payload"])
    payload.pop(missing_key)

    response = client.post(f"/api/v2/preflight/{component}", json=payload)

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(missing_key in error["loc"] and error["msg"] == "Field required" for error in errors)
    assert "prediction" not in response.json()


@pytest.mark.parametrize(
    ("component", "invalid_path"),
    [
        ("engine", ("records", 0, "sensor_1")),
        ("battery", ("samples", 0, "voltage_measured")),
        ("hydraulic", ("cycle_id",)),
        ("landing-gear", ("mass",)),
        ("fuel-system", ("samples", 0, "FTL")),
    ],
)
def test_preflight_rejects_malformed_numeric_upload_values(component, invalid_path):
    example = client.get(f"/api/workspace/examples/{component}", params={"variant": "normal"})
    assert example.status_code == 200, example.text
    payload = example.json()["payload"]
    target = payload
    for key in invalid_path[:-1]:
        target = target[key]
    target[invalid_path[-1]] = "not-a-number"

    response = client.post(f"/api/v2/preflight/{component}", json=payload)

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(list(invalid_path) == error["loc"][1:] for error in errors)
    assert "prediction" not in response.json()


@pytest.mark.parametrize("component", ["engine", "battery", "hydraulic", "landing-gear"])
def test_preflight_flags_extreme_but_numeric_values_with_specific_review_guidance(component):
    example = client.get(f"/api/workspace/examples/{component}", params={"variant": "normal"})
    assert example.status_code == 200, example.text
    payload = example.json()["payload"]
    if component == "engine":
        for record in payload["records"]:
            for key in record:
                if key.startswith("sensor_"):
                    record[key] = 1e9
    elif component == "battery":
        for sample in payload["samples"]:
            sample["voltage_measured"] = 1e9
    elif component == "hydraulic":
        payload["features"] = {key: 1e9 for key in payload["features"]}
    else:
        payload.update({"max_deflection": 3.0, "max_velocity": 6.5, "settling_time": 3.6, "mass": 30000})

    response = client.post(f"/api/v2/preflight/{component}", json=payload)

    assert response.status_code == 200, response.text
    report = response.json()
    assert report["review_required"] is True
    assert any(
        "check values and units" in check["detail"].lower()
        for check in report["checks"].values()
        if check["status"] == "review_required"
    )
    assert "prediction" not in report


def test_fuel_preflight_allows_documented_sensor_overshoot_but_explains_no_range_gate():
    example = client.get("/api/workspace/examples/fuel-system", params={"variant": "normal"})
    payload = example.json()["payload"]
    payload["samples"][0]["FTL"] = 100.22

    response = client.post("/api/v2/preflight/fuel-system", json=payload)

    assert response.status_code == 200, response.text
    report = response.json()
    assert report["review_required"] is True
    assert report["checks"]["anomaly_detection"]["status"] == "not_assessed"
    assert any("above 100 are retained" in note for note in report["notes"])
    assert "prediction" not in report


def test_preflight_flags_landing_gear_values_outside_training_support():
    response = client.post("/api/v2/preflight/landing-gear", json={
        "max_deflection": 3.0, "max_velocity": 6.5,
        "settling_time": 3.6, "mass": 30000,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["review_required"] is True
    assert body["checks"]["fault"]["hard_range_violations"]
    assert body["checks"]["rul"]["hard_range_violations"]


def test_battery_preflight_reports_out_of_order_samples_are_sorted():
    payload = _battery_payload()
    payload["samples"] = list(reversed(payload["samples"]))
    response = client.post("/api/v2/preflight/battery", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert any("sorts them by time" in note for note in body["notes"])


def test_engine_preflight_requires_review_for_short_rolling_history():
    payload = {"subset": "FD001", "records": _engine_records()[:3]}
    response = client.post("/api/v2/preflight/engine", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["review_required"] is True
    assert "10 consecutive recent cycles" in body["checks"]["rul"]["detail"]
