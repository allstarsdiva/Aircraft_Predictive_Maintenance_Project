"""FastAPI entry point for aircraft predictive-maintenance services."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from src.api.schemas import (
    EngineModelInfo,
    EnginePredictionRequest,
    EnginePredictionResponse,
    HealthResponse,
    PredictionValue,
)
from src.modeling import EngineModelBundle
from src.preprocessing import add_causal_engine_features
from src.api.subsystem_routes import router as subsystem_router
from src.api.readiness_routes import router as readiness_router
from src.api.workspace_routes import router as workspace_router

API_VERSION = "0.4.1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENGINE_MODEL_PATH = (
    PROJECT_ROOT / "models" / "engine" / "fd001_tuned_bundle.joblib"
)


def engine_model_path() -> Path:
    configured = os.getenv("ENGINE_MODEL_PATH")
    return Path(configured) if configured else DEFAULT_ENGINE_MODEL_PATH


@lru_cache(maxsize=1)
def get_engine_bundle() -> EngineModelBundle:
    path = engine_model_path()
    if not path.is_file():
        raise FileNotFoundError(f"Engine model bundle not found: {path}")
    bundle = joblib.load(path)
    if not isinstance(bundle, EngineModelBundle):
        raise TypeError(f"Unexpected engine artifact type: {type(bundle).__name__}")
    return bundle


def require_engine_bundle() -> EngineModelBundle:
    try:
        return get_engine_bundle()
    except (FileNotFoundError, TypeError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def risk_from_rul(predicted_rul: float) -> tuple[str, str]:
    """Map demonstration RUL thresholds to the dashboard contract."""

    if predicted_rul <= 30:
        return "High", "Inspect Immediately"
    if predicted_rul <= 60:
        return "Medium", "Monitor Closely"
    return "Low", "No Immediate Action Required"


app = FastAPI(
    title="Aircraft Predictive Maintenance API",
    description=(
        "Research prototype API for subsystem condition and RUL predictions. "
        "Outputs are not certified aircraft maintenance limits."
    ),
    version=API_VERSION,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(subsystem_router)
app.include_router(readiness_router)
app.include_router(workspace_router)


@app.get("/api/health", response_model=HealthResponse, tags=["service"])
def health() -> HealthResponse:
    return HealthResponse(version=API_VERSION)


@app.get("/api/models/engine", response_model=EngineModelInfo, tags=["engine"])
def engine_model_info(
    bundle: EngineModelBundle = Depends(require_engine_bundle),
) -> EngineModelInfo:
    return EngineModelInfo(
        available=True,
        subset=bundle.subset,
        model=bundle.model_name,
        capped_rul=bundle.capped_rul,
        prediction_offset=bundle.prediction_offset,
        raw_input_features=len(bundle.feature_columns),
        retained_features=int(bundle.model.n_features_in_),
        grouped_cv_mae=bundle.validation_metrics.mae,
        grouped_cv_rmse=bundle.validation_metrics.rmse,
    )


@app.post(
    "/api/predict/engine",
    response_model=EnginePredictionResponse,
    tags=["engine"],
)
def predict_engine(
    request: EnginePredictionRequest,
    bundle: EngineModelBundle = Depends(require_engine_bundle),
) -> EnginePredictionResponse:
    frame = pd.DataFrame([record.model_dump() for record in request.records])
    frame = frame.sort_values("cycle").reset_index(drop=True)
    featured = add_causal_engine_features(frame)
    predictions = bundle.predict_feature_frame(featured)
    predicted_rul = round(float(predictions[-1]), 3)
    latest = frame.iloc[-1]
    risk, recommendation = risk_from_rul(predicted_rul)
    warnings: list[str] = []
    if len(frame) < 10:
        warnings.append(
            "Fewer than 10 cycles were supplied; rolling degradation features have limited history."
        )
    if frame["cycle"].diff().dropna().gt(1).any():
        warnings.append(
            "Cycle gaps were detected; rolling features use supplied observations only."
        )

    return EnginePredictionResponse(
        unit_id=int(latest["unit_id"]),
        latest_cycle=int(latest["cycle"]),
        input_cycles=len(frame),
        model=bundle.model_name,
        prediction=PredictionValue(value=predicted_rul),
        risk=risk,
        recommendation=recommendation,
        thresholds={"high_max_rul": 30.0, "medium_max_rul": 60.0},
        warnings=warnings,
    )
