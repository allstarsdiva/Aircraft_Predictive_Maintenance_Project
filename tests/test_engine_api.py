"""API contract and end-to-end engine inference tests."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import DEFAULT_ENGINE_MODEL_PATH, app, get_engine_bundle
from src.data.cmapss import load_cmapss


client = TestClient(app)


def _request_records(rows=10):
    frame = load_cmapss("FD001", "test")
    unit = frame.loc[frame["unit_id"] == 1].head(rows)
    records = []
    for row in unit.to_dict(orient="records"):
        records.append(
            {
                key: int(value) if key in {"unit_id", "cycle"} else float(value)
                for key, value in row.items()
            }
        )
    return records


def test_health_endpoint():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_request_rejects_multiple_engines():
    records = _request_records(2)
    records[1]["unit_id"] = 2
    response = client.post(
        "/api/predict/engine", json={"subset": "FD001", "records": records}
    )

    assert response.status_code == 422
    assert "one engine" in response.text


def test_request_rejects_unknown_sensor_field():
    records = _request_records(1)
    records[0]["invented_sensor"] = 10.0
    response = client.post(
        "/api/predict/engine", json={"subset": "FD001", "records": records}
    )

    assert response.status_code == 422


@pytest.mark.skipif(
    not Path(DEFAULT_ENGINE_MODEL_PATH).is_file(),
    reason="Tuned engine bundle is not available.",
)
def test_engine_prediction_runs_end_to_end():
    get_engine_bundle.cache_clear()
    response = client.post(
        "/api/predict/engine",
        json={"subset": "FD001", "records": _request_records(12)},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["component"] == "Engine"
    assert body["unit_id"] == 1
    assert body["latest_cycle"] == 12
    assert 0 <= body["prediction"]["value"] <= 125
    assert body["risk"] in {"Low", "Medium", "High"}


@pytest.mark.skipif(
    not Path(DEFAULT_ENGINE_MODEL_PATH).is_file(),
    reason="Tuned engine bundle is not available.",
)
def test_engine_model_metadata_matches_bundle():
    response = client.get("/api/models/engine")

    assert response.status_code == 200
    assert response.json()["retained_features"] == 43
    assert response.json()["prediction_offset"] == 5.0
