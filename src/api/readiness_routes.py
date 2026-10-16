"""Readiness-v2 prediction routes with intervals, support checks, and abstention."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status

from src.api.readiness_schemas import (
    BatteryReadinessResponse,
    EngineReadinessResponse,
    HydraulicReadinessResponse,
    InputQualityResponse,
    InputQualityTask,
    InputSupport,
    LandingGearObservableRequest,
    LandingGearReadinessResponse,
    ReadinessClassificationResult,
    ReadinessRegressionResult,
    ReadinessStatus,
)
from src.api.schemas import EnginePredictionRequest
from src.api.subsystem_schemas import BatteryPredictionRequest, FuelPredictionRequest, HydraulicPredictionRequest
from src.eda_hydraulic import HYDRAULIC_TARGETS
from src.features import extract_battery_discharge_features
from src.preprocessing import add_causal_engine_features
from src.readiness_modeling import ReadinessClassificationBundle, ReadinessRegressionBundle
from src.model_release import artifact_root, metrics_root

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_ROOT = artifact_root()
METRICS_PATH = metrics_root() / "readiness_v2_retraining.json"

router = APIRouter(prefix="/api/v2", tags=["readiness-v2"])


def _load(path: Path, expected_type):
    if not path.is_file():
        raise FileNotFoundError(f"Readiness model not found: {path}")
    bundle = joblib.load(path)
    if not isinstance(bundle, expected_type):
        raise TypeError(f"Unexpected readiness artifact: {type(bundle).__name__}")
    return bundle


def _service_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@lru_cache(maxsize=1)
def get_engine_readiness() -> ReadinessRegressionBundle:
    return _load(MODEL_ROOT / "engine_fd001_bundle.joblib", ReadinessRegressionBundle)


@lru_cache(maxsize=1)
def get_battery_readiness() -> tuple[ReadinessRegressionBundle, ReadinessRegressionBundle]:
    return (
        _load(MODEL_ROOT / "battery_soh_bundle.joblib", ReadinessRegressionBundle),
        _load(MODEL_ROOT / "battery_rul_bundle.joblib", ReadinessRegressionBundle),
    )


@lru_cache(maxsize=1)
def get_hydraulic_readiness() -> dict[str, ReadinessClassificationBundle]:
    return {
        target: _load(
            MODEL_ROOT / "hydraulic" / f"{target}_bundle.joblib",
            ReadinessClassificationBundle,
        )
        for target in HYDRAULIC_TARGETS
    }


@lru_cache(maxsize=1)
def get_landing_readiness() -> tuple[ReadinessClassificationBundle, ReadinessRegressionBundle]:
    return (
        _load(MODEL_ROOT / "landing_gear_fault_bundle.joblib", ReadinessClassificationBundle),
        _load(MODEL_ROOT / "landing_gear_rul_bundle.joblib", ReadinessRegressionBundle),
    )


def _require(loader):
    try:
        return loader()
    except (FileNotFoundError, TypeError, OSError) as exc:
        raise _service_error(exc) from exc


def _top_model_features(bundle, limit: int = 5) -> list[dict[str, str | float]]:
    """Expose global model importance, explicitly not a per-case cause."""
    model = bundle.model
    feature_importances = getattr(model, "feature_importances_", None)
    coefficients = getattr(model, "coef_", None)
    if feature_importances is not None:
        scores = np.asarray(feature_importances, dtype=float).reshape(-1)
    elif coefficients is not None:
        values = np.asarray(coefficients, dtype=float)
        scores = np.abs(values).mean(axis=0) if values.ndim > 1 else np.abs(values)
    else:
        return []
    names = getattr(model, "feature_names_in_", None)
    if names is None:
        names = getattr(bundle.preprocessor, "get_feature_names_out", lambda *_: bundle.feature_columns)(bundle.feature_columns)
    names = [str(name).replace("num__", "").replace("cat__", "") for name in names]
    if len(names) != len(scores) or not np.isfinite(scores).all() or not np.any(scores > 0):
        return []
    maximum = float(scores.max())
    order = np.argsort(scores)[::-1][:limit]
    return [
        {"feature": names[index], "relative_importance": round(float(scores[index] / maximum * 100), 2)}
        for index in order if scores[index] > 0
    ]


def _regression_result(bundle: ReadinessRegressionBundle, frame: pd.DataFrame) -> ReadinessRegressionResult:
    predicted, lower, upper = bundle.predict_interval(frame)
    support = bundle.assess_input(frame)
    return ReadinessRegressionResult(
        value=round(float(predicted[-1]), 3),
        lower=round(float(lower[-1]), 3),
        upper=round(float(upper[-1]), 3),
        interval_level=round(1 - bundle.interval_alpha, 3),
        unit=bundle.target_unit,
        accepted=not bool(support["abstain"]),
        input_support=InputSupport(**support),
        top_model_features=_top_model_features(bundle),
    )


def _input_quality_task(bundle, frame: pd.DataFrame) -> InputQualityTask:
    support = bundle.assess_input(frame)
    hard = support["hard_range_violations"]
    tail = support["tail_range_warnings"]
    review = bool(support["abstain"] or tail)
    detail = (
        "Some model inputs are outside the observed training range. Check values and units; correct possible entry errors, or continue only after review."
        if hard else
        "Some model inputs are near the edge of the observed training range. Check values and units, then continue only after review."
        if tail else
        "No training-support range warnings were found for this model task."
    )
    return InputQualityTask(
        status="review_required" if review else "within_training_range",
        hard_range_violations=hard,
        tail_range_warnings=tail,
        detail=detail,
    )


def _input_quality_response(component: str, checks: dict[str, InputQualityTask], notes: list[str]) -> InputQualityResponse:
    review_required = any(check.status != "within_training_range" for check in checks.values())
    return InputQualityResponse(
        component=component,
        review_required=review_required,
        checks=checks,
        notes=notes,
    )


def _classification_result(
    bundle: ReadinessClassificationBundle, frame: pd.DataFrame
) -> ReadinessClassificationResult:
    predicted, confidence, accepted = bundle.predict_with_readiness(frame)
    support = bundle.assess_input(frame)
    value = int(predicted[-1])
    return ReadinessClassificationResult(
        value=value,
        label=bundle.class_names.get(value),
        calibrated_confidence=round(float(confidence[-1]), 4),
        accepted=bool(accepted[-1]),
        input_support=InputSupport(**support),
        top_model_features=_top_model_features(bundle),
    )


@router.post("/predict/engine", response_model=EngineReadinessResponse)
def predict_engine_readiness(request: EnginePredictionRequest) -> EngineReadinessResponse:
    bundle = _require(get_engine_readiness)
    frame = pd.DataFrame([record.model_dump() for record in request.records])
    frame = frame.sort_values("cycle").reset_index(drop=True)
    featured = add_causal_engine_features(frame)
    result = _regression_result(bundle, featured.tail(1))
    warnings = [
        "The interval is calibrated from grouped simulated-engine residuals.",
        "After removing the artificial interval cap, the nominal 95% interval covered 93% of previously inspected official test engines; point predictions remain capped at 125 cycles.",
        "No prediction is validated for operational maintenance control."
    ]
    if not result.accepted:
        warnings.insert(0, "Engineering review required: input is outside training support.")
    return EngineReadinessResponse(
        unit_id=int(frame.iloc[-1]["unit_id"]), latest_cycle=int(frame.iloc[-1]["cycle"]),
        model=bundle.model_name, rul=result, warnings=warnings,
    )


def _battery_frame(request: BatteryPredictionRequest) -> pd.DataFrame:
    samples = pd.DataFrame([{
        "Voltage_measured": item.voltage_measured,
        "Current_measured": item.current_measured,
        "Temperature_measured": item.temperature_measured,
        "Current_load": item.current_load,
        "Voltage_load": item.voltage_load,
        "Time": item.time,
    } for item in request.samples])
    try:
        features = extract_battery_discharge_features(samples)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return pd.DataFrame([{
        "discharge_cycle": request.discharge_cycle,
        "ambient_temperature": request.ambient_temperature,
        **features,
    }])


@router.post("/predict/battery", response_model=BatteryReadinessResponse)
def predict_battery_readiness(request: BatteryPredictionRequest) -> BatteryReadinessResponse:
    soh_bundle, rul_bundle = _require(get_battery_readiness)
    frame = _battery_frame(request)
    soh = _regression_result(soh_bundle, frame)
    rul = _regression_result(rul_bundle, frame)
    warnings = [
        "Battery RUL remains limited to nine observed-EOL laboratory batteries.",
        "Separate-group calibration diagnostics showed interval undercoverage; interval levels are nominal, not verified guarantees.",
        "Reject or review any result marked accepted=false."
    ]
    return BatteryReadinessResponse(
        battery_id=request.battery_id, discharge_cycle=request.discharge_cycle,
        soh_model=soh_bundle.model_name, soh=soh,
        rul_model=rul_bundle.model_name, rul=rul, warnings=warnings,
    )


@router.post("/predict/hydraulic", response_model=HydraulicReadinessResponse)
def predict_hydraulic_readiness(request: HydraulicPredictionRequest) -> HydraulicReadinessResponse:
    bundles = _require(get_hydraulic_readiness)
    required = set().union(*(bundle.feature_columns for bundle in bundles.values()))
    supplied = set(request.features)
    missing = required - supplied
    if missing:
        raise HTTPException(status_code=422, detail={
            "missing_features": sorted(missing),
            "unexpected_features": sorted(supplied - required),
        })
    frame = pd.DataFrame([request.features])
    results = {target: _classification_result(bundle, frame) for target, bundle in bundles.items()}
    warnings = ["Low-confidence conditions abstain and require engineering review.",
                "Current confidence and acceptance figures are development estimates; a separate calibration audit did not validate every target."]
    if not request.operating_condition_stable:
        warnings.append("Primary training used stable cycles; unstable-cycle predictions are not accepted.")
        for result in results.values():
            result.accepted = False
    return HydraulicReadinessResponse(
        cycle_id=request.cycle_id, predictions=results, warnings=warnings
    )


@router.post("/predict/landing-gear", response_model=LandingGearReadinessResponse)
def predict_landing_readiness(request: LandingGearObservableRequest) -> LandingGearReadinessResponse:
    fault_bundle, rul_bundle = _require(get_landing_readiness)
    frame = pd.DataFrame([request.model_dump()])
    return LandingGearReadinessResponse(
        fault_model=fault_bundle.model_name,
        fault=_classification_result(fault_bundle, frame),
        rul_model=rul_bundle.model_name,
        rul=_regression_result(rul_bundle, frame),
        warnings=[
            "Uses observable inputs only; latent stiffness and damping were removed.",
            "Still validated only on synthetic digital-twin events."
        ],
    )


@router.post("/preflight/engine", response_model=InputQualityResponse)
def preflight_engine_input(request: EnginePredictionRequest) -> InputQualityResponse:
    """Validate an engine request and assess support without producing a prediction."""
    bundle = _require(get_engine_readiness)
    frame = pd.DataFrame([record.model_dump() for record in request.records])
    frame = frame.sort_values("cycle").reset_index(drop=True)
    featured = add_causal_engine_features(frame)
    notes = [
        "Cycle is an operating-cycle count. The source does not publish physical units for the anonymized operating settings or sensor_1 through sensor_21.",
        "The API orders engine rows by cycle before assessment.",
    ]
    input_cycles = [record.cycle for record in request.records]
    if input_cycles != sorted(input_cycles):
        notes.append("Input cycles were not in ascending order; the prediction API sorts them by cycle.")
    checks = {"rul": _input_quality_task(bundle, featured.tail(1))}
    recent_cycles = sorted(input_cycles)[-10:]
    if len(recent_cycles) < 10 or any(right - left != 1 for left, right in zip(recent_cycles, recent_cycles[1:])):
        checks["rul"].status = "review_required"
        checks["rul"].detail = "Fewer than 10 consecutive recent cycles were supplied; the model's 10-cycle features have limited history."
        notes.append("The engine model uses 5- and 10-cycle rolling features; provide at least the latest 10 consecutive cycles for fuller feature context.")
    return _input_quality_response("Engine", checks, notes)


@router.post("/preflight/battery", response_model=InputQualityResponse)
def preflight_battery_input(request: BatteryPredictionRequest) -> InputQualityResponse:
    """Validate battery request structure and check derived features against model support."""
    soh_bundle, rul_bundle = _require(get_battery_readiness)
    frame = _battery_frame(request)
    times = [sample.time for sample in request.samples]
    notes = ["Expected units are V for voltage, A for current, degrees C for temperature, and seconds for time. Numeric JSON does not carry unit tags, so the API cannot verify the submitted units; preserve the source current sign convention."]
    if times != sorted(times):
        notes.append("Battery samples arrived out of order; feature extraction sorts them by time before calculating summaries.")
    if len(times) < 5:
        notes.append("Fewer than five readings were supplied; summarize cautiously because sample-history features have little context.")
    checks = {
        "soh": _input_quality_task(soh_bundle, frame),
        "rul": _input_quality_task(rul_bundle, frame),
    }
    return _input_quality_response("Battery", checks, notes)


@router.post("/preflight/hydraulic", response_model=InputQualityResponse)
def preflight_hydraulic_input(request: HydraulicPredictionRequest) -> InputQualityResponse:
    """Check exact hydraulic feature names, model ranges, and supported condition."""
    bundles = _require(get_hydraulic_readiness)
    required = set().union(*(bundle.feature_columns for bundle in bundles.values()))
    supplied = set(request.features)
    missing, unexpected = required - supplied, supplied - required
    if missing or unexpected:
        raise HTTPException(status_code=422, detail={
            "missing_features": sorted(missing),
            "unexpected_features": sorted(unexpected),
        })
    frame = pd.DataFrame([request.features])
    checks = {target: _input_quality_task(bundle, frame) for target, bundle in bundles.items()}
    notes = ["Feature units follow their source sensors: PS pressure bar, EPS1 W, FS flow L/min, TS temperature degrees C, VS vibration mm/s, CE/SE percent, and CP kW. Summary statistics retain the source sensor unit. Numeric JSON does not carry unit tags, so submitted units cannot be verified."]
    if not request.operating_condition_stable:
        notes.append("This is marked as an unstable condition; the current readiness models require review for unstable hydraulic inputs.")
        for check in checks.values():
            check.status = "review_required"
            check.detail = "Unstable hydraulic conditions are outside the primary validation scope; review before proceeding."
    return _input_quality_response("Hydraulic", checks, notes)


@router.post("/preflight/landing-gear", response_model=InputQualityResponse)
def preflight_landing_input(request: LandingGearObservableRequest) -> InputQualityResponse:
    """Check landing-gear observables against each readiness model's training support."""
    fault_bundle, rul_bundle = _require(get_landing_readiness)
    frame = pd.DataFrame([request.model_dump()])
    notes = ["Expected units: max_deflection m, max_velocity m/s, settling_time s, and mass kg. Numeric JSON does not carry unit tags, so the API cannot verify the submitted units."]
    checks = {
        "fault": _input_quality_task(fault_bundle, frame),
        "rul": _input_quality_task(rul_bundle, frame),
    }
    return _input_quality_response("Landing Gear", checks, notes)


@router.post("/preflight/fuel-system", response_model=InputQualityResponse)
def preflight_fuel_input(request: FuelPredictionRequest) -> InputQualityResponse:
    """Validate the fuel request structure; this experimental detector has no separate OOD gate."""
    notes = [
        "Fuel request structure and numeric fields are valid, but this detector has no separate calibrated training-support check.",
        "FTL/CTL use the source-paper percent interpretation and cannot be negative; readings above 100 are retained because small overshoots occur in the supplied data.",
        "FTT/CRTT are described in degrees C; units for FTF, FTV_S, CLF, and CLV_S are unpublished. Numeric JSON has no unit tags; preserve the sample order because verified timestamps are unavailable.",
    ]
    if len(request.samples) < 5:
        notes.append("Fewer than five readings were supplied; rolling features have limited history.")
    return InputQualityResponse(
        component="Fuel System",
        review_required=True,
        checks={"anomaly_detection": InputQualityTask(
            status="not_assessed",
            detail="Only request structure was checked. Range/distribution suitability is not assessed before prediction.",
        )},
        notes=notes,
    )


@router.get("/readiness", response_model=ReadinessStatus)
def readiness_status() -> ReadinessStatus:
    if not METRICS_PATH.is_file():
        raise HTTPException(status_code=503, detail="Readiness metrics are unavailable")
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    gates = {
        "engine": metrics["engine"]["readiness_gate"],
        "battery_soh": metrics["battery_soh"]["readiness_gate"],
        "battery_rul": metrics["battery_rul"]["readiness_gate"],
        "landing_fault": metrics["landing_gear"]["fault"]["readiness_gate"],
        "landing_rul": metrics["landing_gear"]["rul"]["readiness_gate"],
        "fuel_system": metrics["fuel_system"]["readiness_gate"],
    }
    gates.update({
        f"hydraulic_{target}": result["readiness_gate"]
        for target, result in metrics["hydraulic"].items()
    })
    return ReadinessStatus(
        model_gates=gates,
        fuel_prediction_enabled=False,
        statement=(
            "Conditional pass means suitable for continued pre-deployment research, "
            "not approved or validated for aircraft maintenance decisions."
        ),
    )
