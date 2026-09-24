"""API contracts for readiness-v2 predictions and abstention."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from src.api.schemas import EnginePredictionRequest, StrictModel
from src.api.subsystem_schemas import (
    BatteryPredictionRequest,
    HydraulicPredictionRequest,
)


class InputSupport(StrictModel):
    within_hard_training_range: bool
    hard_range_violations: list[str]
    tail_range_warnings: list[str]
    abstain: bool


class ReadinessRegressionResult(StrictModel):
    value: float
    lower: float
    upper: float
    interval_level: float
    unit: str
    accepted: bool
    input_support: InputSupport


class ReadinessClassificationResult(StrictModel):
    value: int
    label: str | None = None
    calibrated_confidence: float
    accepted: bool
    input_support: InputSupport


class EngineReadinessResponse(StrictModel):
    component: Literal["Engine"] = "Engine"
    protocol: Literal["readiness-v2"] = "readiness-v2"
    unit_id: int
    latest_cycle: int
    model: str
    rul: ReadinessRegressionResult
    warnings: list[str]


class BatteryReadinessResponse(StrictModel):
    component: Literal["Battery"] = "Battery"
    protocol: Literal["readiness-v2"] = "readiness-v2"
    battery_id: str
    discharge_cycle: int
    soh_model: str
    soh: ReadinessRegressionResult
    rul_model: str
    rul: ReadinessRegressionResult
    warnings: list[str]


class HydraulicReadinessResponse(StrictModel):
    component: Literal["Hydraulic"] = "Hydraulic"
    protocol: Literal["readiness-v2"] = "readiness-v2"
    cycle_id: int
    predictions: dict[str, ReadinessClassificationResult]
    warnings: list[str]


class LandingGearObservableRequest(StrictModel):
    max_deflection: float = Field(gt=0)
    max_velocity: float = Field(gt=0)
    settling_time: float = Field(gt=0)
    mass: float = Field(gt=0)


class LandingGearReadinessResponse(StrictModel):
    component: Literal["Landing Gear"] = "Landing Gear"
    protocol: Literal["readiness-v2"] = "readiness-v2"
    fault_model: str
    fault: ReadinessClassificationResult
    rul_model: str
    rul: ReadinessRegressionResult
    warnings: list[str]


class ReadinessStatus(StrictModel):
    real_aircraft_validated: Literal[False] = False
    finalization_ready: Literal[False] = False
    gate_basis: Literal["historical_development_metrics"] = "historical_development_metrics"
    status: Literal["pre_deployment_research_only"] = "pre_deployment_research_only"
    model_gates: dict[str, str]
    fuel_prediction_enabled: bool
    statement: str


__all__ = [
    "BatteryPredictionRequest",
    "EnginePredictionRequest",
    "HydraulicPredictionRequest",
]
