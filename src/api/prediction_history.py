"""Minimal persisted history for user-submitted model runs; raw sensor data is never stored."""

from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field, field_validator

from src.api.schemas import StrictModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HISTORY_DB_PATH = Path(os.getenv(
    "AIRCRAFT_PREDICTION_HISTORY_DB",
    str(PROJECT_ROOT / "data" / "processed" / "prediction_history.sqlite3"),
))

Component = Literal["engine", "battery", "hydraulic", "landing-gear", "fuel-system"]
Source = Literal["dataset_example", "uploaded_file", "edited_input", "all_components_bundle"]
OutcomeStatus = Literal["confirmed_fault", "no_fault_found", "inconclusive"]


class PredictionHistoryCreate(StrictModel):
    component: Component
    asset_id: str | None = Field(default=None, max_length=80)
    source: Source
    summary: str = Field(min_length=1, max_length=500)
    review_required: bool
    model_release: str | None = Field(default=None, max_length=120)
    input_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @field_validator("asset_id", mode="before")
    @classmethod
    def normalize_asset_id(cls, value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None


class PredictionHistoryEntry(PredictionHistoryCreate):
    id: str
    created_at_utc: str
    outcome_status: str = "unreviewed"
    outcome_updated_at_utc: str | None = None


class PredictionOutcomeUpdate(StrictModel):
    outcome_status: OutcomeStatus


router = APIRouter(prefix="/api/prediction-history", tags=["prediction-history"])


def _connect() -> sqlite3.Connection:
    HISTORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(HISTORY_DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE IF NOT EXISTS prediction_history (
            id TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            component TEXT NOT NULL,
            asset_id TEXT,
            source TEXT NOT NULL,
            summary TEXT NOT NULL,
            review_required INTEGER NOT NULL,
            model_release TEXT,
            input_digest TEXT,
            outcome_status TEXT NOT NULL DEFAULT 'unreviewed',
            outcome_updated_at_utc TEXT
        )
    """)
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(prediction_history)")}
    if "outcome_status" not in columns:
        connection.execute("ALTER TABLE prediction_history ADD COLUMN outcome_status TEXT NOT NULL DEFAULT 'unreviewed'")
    if "outcome_updated_at_utc" not in columns:
        connection.execute("ALTER TABLE prediction_history ADD COLUMN outcome_updated_at_utc TEXT")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_prediction_history_created ON prediction_history(created_at_utc DESC)")
    connection.commit()
    return connection


def _entry(row: sqlite3.Row) -> PredictionHistoryEntry:
    return PredictionHistoryEntry(
        id=row["id"], created_at_utc=row["created_at_utc"], component=row["component"],
        asset_id=row["asset_id"], source=row["source"], summary=row["summary"],
        review_required=bool(row["review_required"]), model_release=row["model_release"],
        input_digest=row["input_digest"], outcome_status=row["outcome_status"],
        outcome_updated_at_utc=row["outcome_updated_at_utc"],
    )


@router.post("", response_model=PredictionHistoryEntry, status_code=201)
def save_prediction_history(record: PredictionHistoryCreate) -> PredictionHistoryEntry:
    entry_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    with closing(_connect()) as connection:
        connection.execute(
            """INSERT INTO prediction_history
               (id, created_at_utc, component, asset_id, source, summary, review_required, model_release, input_digest)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (entry_id, created_at, record.component, record.asset_id, record.source,
             record.summary, int(record.review_required), record.model_release, record.input_digest),
        )
        connection.commit()
        row = connection.execute("SELECT * FROM prediction_history WHERE id = ?", (entry_id,)).fetchone()
    return _entry(row)


@router.get("", response_model=list[PredictionHistoryEntry])
def list_prediction_history(
    asset_id: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PredictionHistoryEntry]:
    with closing(_connect()) as connection:
        if asset_id and asset_id.strip():
            rows = connection.execute(
                "SELECT * FROM prediction_history WHERE asset_id = ? ORDER BY created_at_utc DESC, rowid DESC LIMIT ?",
                (asset_id.strip(), limit),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM prediction_history ORDER BY created_at_utc DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [_entry(row) for row in rows]


@router.patch("/{entry_id}/outcome", response_model=PredictionHistoryEntry)
def update_prediction_outcome(entry_id: str, update: PredictionOutcomeUpdate) -> PredictionHistoryEntry:
    updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    with closing(_connect()) as connection:
        cursor = connection.execute(
            "UPDATE prediction_history SET outcome_status = ?, outcome_updated_at_utc = ? WHERE id = ?",
            (update.outcome_status, updated_at, entry_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Prediction history entry was not found.")
        connection.commit()
        row = connection.execute("SELECT * FROM prediction_history WHERE id = ?", (entry_id,)).fetchone()
    return _entry(row)
