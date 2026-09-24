"""FastAPI routes for battery, fuel, hydraulic, and landing-gear models."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TypeVar

import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status

from src.api.subsystem_schemas import (
    BatteryPredictionRequest,
    BatteryPredictionResponse,
    FuelPredictionRequest,
    FuelPredictionResponse,
    HydraulicPredictionRequest,
    HydraulicPredictionResponse,
    LandingGearPredictionRequest,
    LandingGearPredictionResponse,
    SubsystemModelRegistry,
    SubsystemModelStatus,
)
from src.eda_hydraulic import HYDRAULIC_TARGETS
from src.features import extract_battery_discharge_features
from src.fuel_modeling import FuelAnomalyModelBundle
from src.fuel_phase_modeling import FuelPhaseResidualBundle
from src.landing_gear_modeling import LandingGearFaultBundle, LandingGearRULBundle
from src.modeling import (
    BatteryRULModelBundle,
    BatterySOHModelBundle,
    HydraulicClassificationBundle,
)
from src.preprocess_fuel import add_causal_fuel_features
from src.model_release import artifact_root

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_ROOT = PROJECT_ROOT / "models"
BATTERY_SOH_PATH = MODEL_ROOT / "battery" / "soh_baseline_bundle.joblib"
BATTERY_RUL_PATH = MODEL_ROOT / "battery" / "rul_experimental_bundle.joblib"
FUEL_MODEL_PATH = artifact_root() / "fuel_phase_residual_bundle.joblib"
LANDING_FAULT_PATH = MODEL_ROOT / "landing_gear" / "fault_classifier_bundle.joblib"
LANDING_RUL_PATH = MODEL_ROOT / "landing_gear" / "rul_regressor_bundle.joblib"
HYDRAULIC_MODEL_PATHS = {
    target: MODEL_ROOT / "hydraulic" / f"{target}_bundle.joblib"
    for target in HYDRAULIC_TARGETS
}

router = APIRouter()
T = TypeVar("T")


def _load_bundle(path: Path, expected_type: type[T]) -> T:
    if not path.is_file():
        raise FileNotFoundError(f"Model bundle not found: {path}")
    bundle = joblib.load(path)
    if not isinstance(bundle, expected_type):
        raise TypeError(
            f"Unexpected artifact type at {path.name}: {type(bundle).__name__}"
        )
    return bundle


def _unavailable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
    )


@lru_cache(maxsize=1)
def get_battery_bundles() -> tuple[BatterySOHModelBundle, BatteryRULModelBundle]:
    return (
        _load_bundle(BATTERY_SOH_PATH, BatterySOHModelBundle),
        _load_bundle(BATTERY_RUL_PATH, BatteryRULModelBundle),
    )


def require_battery_bundles() -> tuple[BatterySOHModelBundle, BatteryRULModelBundle]:
    try:
        return get_battery_bundles()
    except (FileNotFoundError, TypeError, OSError) as exc:
        raise _unavailable(exc) from exc


@lru_cache(maxsize=1)
def get_fuel_bundle() -> FuelPhaseResidualBundle:
    return _load_bundle(FUEL_MODEL_PATH, FuelPhaseResidualBundle)


def require_fuel_bundle() -> FuelPhaseResidualBundle:
    try:
        return get_fuel_bundle()
    except (FileNotFoundError, TypeError, OSError) as exc:
        raise _unavailable(exc) from exc


@lru_cache(maxsize=1)
def get_hydraulic_bundles() -> dict[str, HydraulicClassificationBundle]:
    return {
        target: _load_bundle(path, HydraulicClassificationBundle)
        for target, path in HYDRAULIC_MODEL_PATHS.items()
    }


def require_hydraulic_bundles() -> dict[str, HydraulicClassificationBundle]:
    try:
        return get_hydraulic_bundles()
    except (FileNotFoundError, TypeError, OSError) as exc:
        raise _unavailable(exc) from exc


@lru_cache(maxsize=1)
def get_landing_gear_bundles() -> tuple[LandingGearFaultBundle, LandingGearRULBundle]:
    return (
        _load_bundle(LANDING_FAULT_PATH, LandingGearFaultBundle),
        _load_bundle(LANDING_RUL_PATH, LandingGearRULBundle),
    )


def require_landing_gear_bundles() -> tuple[LandingGearFaultBundle, LandingGearRULBundle]:
    try:
        return get_landing_gear_bundles()
    except (FileNotFoundError, TypeError, OSError) as exc:
        raise _unavailable(exc) from exc


@router.post(
    "/api/predict/battery",
    response_model=BatteryPredictionResponse,
    tags=["battery"],
)
def predict_battery(
    request: BatteryPredictionRequest,
    bundles: tuple[BatterySOHModelBundle, BatteryRULModelBundle] = Depends(
        require_battery_bundles
    ),
) -> BatteryPredictionResponse:
    soh_bundle, rul_bundle = bundles
    samples = pd.DataFrame([
        {
            "Voltage_measured": item.voltage_measured,
            "Current_measured": item.current_measured,
            "Temperature_measured": item.temperature_measured,
            "Current_load": item.current_load,
            "Voltage_load": item.voltage_load,
            "Time": item.time,
        }
        for item in request.samples
    ])
    try:
        extracted = extract_battery_discharge_features(samples)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    frame = pd.DataFrame([{
        "discharge_cycle": request.discharge_cycle,
        "ambient_temperature": request.ambient_temperature,
        **extracted,
    }])
    soh = float(soh_bundle.predict_feature_frame(frame)[0])
    rul, lower, upper = rul_bundle.predict_interval(frame)
    warnings = [
        "Battery RUL is experimental and was validated on only nine observed-EOL batteries.",
        "The interval is empirical and is not a certified coverage guarantee.",
    ]
    return BatteryPredictionResponse(
        battery_id=request.battery_id,
        discharge_cycle=request.discharge_cycle,
        soh_model=soh_bundle.model_name,
        predicted_soh_percent=round(soh, 3),
        rul_model=rul_bundle.model_name,
        predicted_rul_cycles=round(float(rul[0]), 3),
        rul_lower_90_cycles=round(float(lower[0]), 3),
        rul_upper_90_cycles=round(float(upper[0]), 3),
        warnings=warnings,
    )


@router.post(
    "/api/predict/fuel-system",
    response_model=FuelPredictionResponse,
    tags=["fuel-system"],
)
def predict_fuel_system(
    request: FuelPredictionRequest,
    bundle: FuelPhaseResidualBundle = Depends(require_fuel_bundle),
) -> FuelPredictionResponse:
    rows = [item.model_dump() for item in request.samples]
    frame = pd.DataFrame(rows)
    frame.insert(0, "sample_index", np.arange(1, len(frame) + 1))
    frame.insert(0, "scenario_code", 0)
    frame.insert(0, "scenario_id", "request")
    featured = add_causal_fuel_features(frame)
    predicted = bundle.predict_feature_frame(featured)
    margins = bundle.predict_anomaly_score(featured)
    window = min(3, len(predicted))
    warnings = [
        "Fuel anomaly detection remains experimental: one normal trajectory cannot establish new-mission false-alarm performance.",
        "No alert does not establish a healthy system; scenario-level abnormal labels do not provide verified fault-onset times."
    ]
    if len(frame) < 5:
        warnings.append(
            "Fewer than five samples were supplied; rolling features have limited history."
        )
    return FuelPredictionResponse(
        input_samples=len(frame),
        model=bundle.detector_name,
        latest_is_abnormal=bool(predicted[-1]),
        latest_anomaly_margin=round(float(margins[-1]), 6),
        flagged_samples=int(predicted.sum()),
        persistent_last_three=bool(len(predicted) >= 3 and np.all(predicted[-3:] == 1)),
        warnings=warnings,
    )


@router.post(
    "/api/predict/hydraulic",
    response_model=HydraulicPredictionResponse,
    tags=["hydraulic"],
)
def predict_hydraulic(
    request: HydraulicPredictionRequest,
    bundles: dict[str, HydraulicClassificationBundle] = Depends(
        require_hydraulic_bundles
    ),
) -> HydraulicPredictionResponse:
    expected = set(next(iter(bundles.values())).feature_columns)
    supplied = set(request.features)
    if supplied != expected:
        raise HTTPException(
            status_code=422,
            detail={
                "missing_features": sorted(expected - supplied),
                "unexpected_features": sorted(supplied - expected),
            },
        )
    frame = pd.DataFrame([request.features])
    predictions = {
        target: int(bundle.predict_feature_frame(frame)[0])
        for target, bundle in bundles.items()
    }
    warnings = []
    if not request.operating_condition_stable:
        warnings.append(
            "Primary hydraulic validation used stable cycles; valve and accumulator predictions degrade on unstable cycles."
        )
    warnings.append("Predictions support inspection and do not replace engineering judgment.")
    return HydraulicPredictionResponse(
        cycle_id=request.cycle_id,
        predictions=predictions,
        models={target: bundle.model_name for target, bundle in bundles.items()},
        warnings=warnings,
    )


@router.post(
    "/api/predict/landing-gear",
    response_model=LandingGearPredictionResponse,
    tags=["landing-gear"],
)
def predict_landing_gear(
    request: LandingGearPredictionRequest,
    bundles: tuple[LandingGearFaultBundle, LandingGearRULBundle] = Depends(
        require_landing_gear_bundles
    ),
) -> LandingGearPredictionResponse:
    fault_bundle, rul_bundle = bundles
    frame = pd.DataFrame([request.model_dump()])
    fault_code = int(fault_bundle.predict_feature_frame(frame)[0])
    rul = float(rul_bundle.predict_feature_frame(frame)[0])
    return LandingGearPredictionResponse(
        fault_model=fault_bundle.model_name,
        fault_code=fault_code,
        fault_name=fault_bundle.class_names[fault_code],
        rul_model=rul_bundle.model_name,
        predicted_rul_percent=round(rul, 3),
        feature_set=fault_bundle.feature_set,
        warnings=[
            "Validated only within one synthetic digital-twin dataset; not real-aircraft performance.",
            "Physics-assisted predictions require stiffness and damping estimates.",
        ],
    )


@router.get(
    "/api/models/subsystems",
    response_model=SubsystemModelRegistry,
    tags=["service"],
)
def subsystem_model_registry() -> SubsystemModelRegistry:
    specs = {
        "battery_soh": (BATTERY_SOH_PATH, BatterySOHModelBundle, "soh_regression", False),
        "battery_rul": (BATTERY_RUL_PATH, BatteryRULModelBundle, "rul_regression", True),
        "fuel_anomaly": (FUEL_MODEL_PATH, FuelPhaseResidualBundle, "anomaly_detection", True),
        "landing_fault": (LANDING_FAULT_PATH, LandingGearFaultBundle, "fault_classification", True),
        "landing_rul": (LANDING_RUL_PATH, LandingGearRULBundle, "rul_regression", True),
    }
    models: dict[str, SubsystemModelStatus] = {}
    for name, (path, expected_type, task, experimental) in specs.items():
        try:
            bundle = _load_bundle(path, expected_type)
            model_name = getattr(bundle, "model_name", getattr(bundle, "detector_name", None))
            raw_metrics = getattr(bundle, "validation_metrics", {})
            metrics = (
                {key: float(value) for key, value in vars(raw_metrics).items()
                 if key != "training_seconds"}
                if not isinstance(raw_metrics, dict)
                else {key: float(value) for key, value in raw_metrics.items()}
            )
            models[name] = SubsystemModelStatus(
                available=True, task=task, model=model_name,
                validation_metrics=metrics, experimental=experimental,
            )
        except (FileNotFoundError, TypeError, OSError):
            models[name] = SubsystemModelStatus(
                available=False, task=task, experimental=experimental
            )
    try:
        hydraulic = get_hydraulic_bundles()
        for target, bundle in hydraulic.items():
            models[f"hydraulic_{target}"] = SubsystemModelStatus(
                available=True,
                task="condition_classification",
                model=bundle.model_name,
                validation_metrics={
                    key: float(value) for key, value in bundle.validation_metrics.items()
                },
            )
    except (FileNotFoundError, TypeError, OSError):
        for target in HYDRAULIC_TARGETS:
            models[f"hydraulic_{target}"] = SubsystemModelStatus(
                available=False, task="condition_classification"
            )
    return SubsystemModelRegistry(models=models)
