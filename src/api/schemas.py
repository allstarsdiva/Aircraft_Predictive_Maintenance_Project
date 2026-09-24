"""Typed request and response contracts for the prediction API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class EngineCycleRecord(StrictModel):
    unit_id: int = Field(ge=1)
    cycle: int = Field(ge=1)
    operational_setting_1: float
    operational_setting_2: float
    operational_setting_3: float
    sensor_1: float
    sensor_2: float
    sensor_3: float
    sensor_4: float
    sensor_5: float
    sensor_6: float
    sensor_7: float
    sensor_8: float
    sensor_9: float
    sensor_10: float
    sensor_11: float
    sensor_12: float
    sensor_13: float
    sensor_14: float
    sensor_15: float
    sensor_16: float
    sensor_17: float
    sensor_18: float
    sensor_19: float
    sensor_20: float
    sensor_21: float


class EnginePredictionRequest(StrictModel):
    subset: Literal["FD001"] = "FD001"
    records: list[EngineCycleRecord] = Field(min_length=1, max_length=10_000)

    @model_validator(mode="after")
    def validate_trajectory(self) -> "EnginePredictionRequest":
        unit_ids = {record.unit_id for record in self.records}
        if len(unit_ids) != 1:
            raise ValueError("All records must belong to one engine unit_id.")
        cycles = [record.cycle for record in self.records]
        if len(cycles) != len(set(cycles)):
            raise ValueError("Engine cycle values must be unique.")
        return self


class PredictionValue(StrictModel):
    task: Literal["rul_regression"] = "rul_regression"
    value: float
    unit: Literal["cycles"] = "cycles"
    confidence: float | None = None


class EnginePredictionResponse(StrictModel):
    component: Literal["Engine"] = "Engine"
    subset: Literal["FD001"] = "FD001"
    unit_id: int
    latest_cycle: int
    input_cycles: int
    model: str
    prediction: PredictionValue
    risk: Literal["Low", "Medium", "High"]
    recommendation: str
    thresholds: dict[str, float]
    warnings: list[str]


class HealthResponse(StrictModel):
    status: Literal["ok"] = "ok"
    service: Literal["aircraft-predictive-maintenance-api"] = (
        "aircraft-predictive-maintenance-api"
    )
    version: str


class EngineModelInfo(StrictModel):
    available: bool
    subset: str | None = None
    model: str | None = None
    capped_rul: int | None = None
    prediction_offset: float | None = None
    raw_input_features: int | None = None
    retained_features: int | None = None
    grouped_cv_mae: float | None = None
    grouped_cv_rmse: float | None = None
