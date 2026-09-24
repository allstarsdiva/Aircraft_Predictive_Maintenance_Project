"""Typed API contracts for non-engine aircraft subsystems."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from src.api.schemas import StrictModel


class BatteryDischargeSample(StrictModel):
    voltage_measured: float
    current_measured: float
    temperature_measured: float
    current_load: float
    voltage_load: float
    time: float = Field(ge=0)


class BatteryPredictionRequest(StrictModel):
    battery_id: str = Field(min_length=1, max_length=64)
    discharge_cycle: int = Field(ge=1)
    ambient_temperature: float = Field(ge=-100, le=200)
    samples: list[BatteryDischargeSample] = Field(min_length=2, max_length=20_000)

    @model_validator(mode="after")
    def validate_times(self) -> "BatteryPredictionRequest":
        times = [sample.time for sample in self.samples]
        if len(times) != len(set(times)):
            raise ValueError("Battery sample time values must be unique.")
        if max(times) <= min(times):
            raise ValueError("Battery samples must span a positive time interval.")
        return self


class BatteryPredictionResponse(StrictModel):
    component: Literal["Battery"] = "Battery"
    battery_id: str
    discharge_cycle: int
    soh_model: str
    predicted_soh_percent: float
    rul_model: str
    predicted_rul_cycles: float
    rul_lower_90_cycles: float
    rul_upper_90_cycles: float
    experimental_rul: Literal[True] = True
    warnings: list[str]


class FuelSample(StrictModel):
    FTL: float
    CTL: float
    FTF: float
    FTV_S: float
    CLF: float
    CLV_S: float
    FTT: float
    CRTT: float


class FuelPredictionRequest(StrictModel):
    samples: list[FuelSample] = Field(min_length=1, max_length=10_000)


class FuelPredictionResponse(StrictModel):
    component: Literal["Fuel System"] = "Fuel System"
    input_samples: int
    model: str
    latest_is_abnormal: bool
    latest_anomaly_margin: float
    flagged_samples: int
    persistent_last_three: bool
    warnings: list[str]


class HydraulicPredictionRequest(StrictModel):
    cycle_id: int = Field(ge=1)
    features: dict[str, float] = Field(min_length=1, max_length=200)
    operating_condition_stable: bool = True


class HydraulicPredictionResponse(StrictModel):
    component: Literal["Hydraulic"] = "Hydraulic"
    cycle_id: int
    predictions: dict[str, int]
    models: dict[str, str]
    warnings: list[str]


class LandingGearPredictionRequest(StrictModel):
    max_deflection: float = Field(gt=0)
    max_velocity: float = Field(gt=0)
    settling_time: float = Field(gt=0)
    mass: float = Field(gt=0)
    k_stiffness: float = Field(gt=0)
    b_damping: float = Field(gt=0)


class LandingGearPredictionResponse(StrictModel):
    component: Literal["Landing Gear"] = "Landing Gear"
    fault_model: str
    fault_code: int
    fault_name: str
    rul_model: str
    predicted_rul_percent: float
    feature_set: str
    warnings: list[str]


class SubsystemModelStatus(StrictModel):
    available: bool
    task: str
    model: str | None = None
    validation_metrics: dict[str, float] = Field(default_factory=dict)
    experimental: bool = False


class SubsystemModelRegistry(StrictModel):
    models: dict[str, SubsystemModelStatus]
