from fastapi.testclient import TestClient

from src.api import prediction_history
from src.api.app import app

client = TestClient(app)


def _run(asset_id="TAIL-TEST-01", **overrides):
    record = {
        "component": "engine",
        "asset_id": asset_id,
        "source": "uploaded_file",
        "summary": "Estimated RUL: 42 cycles",
        "review_required": False,
        "model_release": "readiness-v2-test",
        "input_digest": "a" * 64,
    }
    record.update(overrides)
    return record


def test_prediction_history_persists_a_minimal_record_without_sensor_payload(monkeypatch, tmp_path):
    database = tmp_path / "prediction-history.sqlite3"
    monkeypatch.setattr(prediction_history, "HISTORY_DB_PATH", database)

    saved = client.post("/api/prediction-history", json=_run(asset_id="  PROJECT-ASSET-7  "))

    assert saved.status_code == 201, saved.text
    entry = saved.json()
    assert entry["asset_id"] == "PROJECT-ASSET-7"
    assert entry["created_at_utc"].endswith("Z")
    assert entry["review_required"] is False
    assert "raw" not in entry
    assert client.get("/api/prediction-history").json() == [entry]
    assert client.get("/api/prediction-history", params={"asset_id": "PROJECT-ASSET-7"}).json() == [entry]
    assert client.get("/api/prediction-history", params={"asset_id": "OTHER-ASSET"}).json() == []
    assert "sensor_1" not in database.read_text(errors="ignore")


def test_prediction_history_rejects_raw_payload_and_invalid_digest(monkeypatch, tmp_path):
    monkeypatch.setattr(prediction_history, "HISTORY_DB_PATH", tmp_path / "history.sqlite3")

    raw_payload = client.post("/api/prediction-history", json={**_run(), "raw_sensor_values": {"sensor_1": 42}})
    invalid_digest = client.post("/api/prediction-history", json=_run(input_digest="not-a-sha256"))

    assert raw_payload.status_code == 422
    assert invalid_digest.status_code == 422
    assert client.get("/api/prediction-history").json() == []


def test_prediction_history_validates_subsystem_and_caps_list_length(monkeypatch, tmp_path):
    monkeypatch.setattr(prediction_history, "HISTORY_DB_PATH", tmp_path / "history.sqlite3")

    invalid = client.post("/api/prediction-history", json=_run(component="avionics"))
    too_many = client.get("/api/prediction-history", params={"limit": 201})

    assert invalid.status_code == 422
    assert too_many.status_code == 422



def test_prediction_outcome_can_be_recorded_and_persists_without_sensor_data(monkeypatch, tmp_path):
    monkeypatch.setattr(prediction_history, "HISTORY_DB_PATH", tmp_path / "history.sqlite3")
    saved = client.post("/api/prediction-history", json=_run()).json()

    assert saved["outcome_status"] == "unreviewed"
    updated = client.patch(
        f"/api/prediction-history/{saved['id']}/outcome",
        json={"outcome_status": "confirmed_fault"},
    )

    assert updated.status_code == 200, updated.text
    entry = updated.json()
    assert entry["outcome_status"] == "confirmed_fault"
    assert entry["outcome_updated_at_utc"].endswith("Z")
    assert client.get("/api/prediction-history").json()[0] == entry
    assert "sensor_1" not in (tmp_path / "history.sqlite3").read_text(errors="ignore")


def test_prediction_outcome_rejects_unknown_status_and_unknown_entry(monkeypatch, tmp_path):
    monkeypatch.setattr(prediction_history, "HISTORY_DB_PATH", tmp_path / "history.sqlite3")
    saved = client.post("/api/prediction-history", json=_run()).json()

    invalid = client.patch(
        f"/api/prediction-history/{saved['id']}/outcome", json={"outcome_status": "fixed"},
    )
    missing = client.patch(
        "/api/prediction-history/not-a-real-id/outcome", json={"outcome_status": "inconclusive"},
    )

    assert invalid.status_code == 422
    assert missing.status_code == 404
