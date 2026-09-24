"""Train and evaluate baseline C-MAPSS engine RUL models."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import joblib

_matplotlib_cache = Path(tempfile.gettempdir()) / "aircraft-matplotlib-cache"
_matplotlib_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_matplotlib_cache))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error

from src.modeling import EngineModelBundle, ModelMetrics
from src.preprocessing import PreparedEngineData, prepare_engine_training_data


def evaluate_predictions(y_true: pd.Series, predictions: np.ndarray) -> dict[str, float]:
    """Calculate the agreed regression metrics."""

    return {
        "mae": float(mean_absolute_error(y_true, predictions)),
        "rmse": float(root_mean_squared_error(y_true, predictions)),
        "r2": float(r2_score(y_true, predictions)),
    }


def baseline_models(random_state: int = 42) -> dict[str, Any]:
    """Return simple and nonlinear baseline regressors."""

    return {
        "median_dummy": DummyRegressor(strategy="median"),
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(
            n_estimators=250,
            max_depth=20,
            min_samples_leaf=2,
            max_features="sqrt",
            n_jobs=-1,
            random_state=random_state,
        ),
    }


def _fit_models(
    prepared: PreparedEngineData,
    random_state: int,
    capped_rul: int,
) -> tuple[dict[str, Any], dict[str, ModelMetrics], dict[str, np.ndarray]]:
    fitted: dict[str, Any] = {}
    metrics: dict[str, ModelMetrics] = {}
    predictions: dict[str, np.ndarray] = {}

    for name, model in baseline_models(random_state).items():
        started = time.perf_counter()
        model.fit(prepared.X_train, prepared.y_train)
        elapsed = time.perf_counter() - started
        predicted = np.clip(model.predict(prepared.X_validation), 0, capped_rul)
        scores = evaluate_predictions(prepared.y_validation, predicted)
        fitted[name] = model
        predictions[name] = predicted
        metrics[name] = ModelMetrics(training_seconds=elapsed, **scores)

    return fitted, metrics, predictions


def _save_figures(
    y_true: pd.Series,
    metrics: dict[str, ModelMetrics],
    predictions: dict[str, np.ndarray],
    best_name: str,
    figure_dir: Path,
) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)

    names = list(metrics)
    mae_values = [metrics[name].mae for name in names]
    rmse_values = [metrics[name].rmse for name in names]
    x = np.arange(len(names))
    width = 0.36
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - width / 2, mae_values, width, label="MAE", color="#0891b2")
    ax.bar(x + width / 2, rmse_values, width, label="RMSE", color="#7c3aed")
    ax.set_xticks(x, [name.replace("_", " ").title() for name in names])
    ax.set_ylabel("Error (RUL cycles)")
    ax.set_title("FD001 Baseline Validation Error")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_dir / "fd001_baseline_model_errors.png", dpi=160)
    plt.close(fig)

    best_predictions = predictions[best_name]
    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    ax.scatter(y_true, best_predictions, s=10, alpha=0.28, color="#0891b2")
    ax.plot([0, 125], [0, 125], linestyle="--", color="#f59e0b", label="Ideal")
    ax.set(
        title=f"FD001 Actual vs Predicted RUL: {best_name.replace('_', ' ').title()}",
        xlabel="Actual capped RUL (cycles)",
        ylabel="Predicted RUL (cycles)",
        xlim=(0, 130),
        ylim=(0, 130),
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_dir / "fd001_best_actual_vs_predicted.png", dpi=160)
    plt.close(fig)


def train_engine_baselines(
    project_root: Path,
    subset: str = "FD001",
    capped_rul: int = 125,
    random_state: int = 42,
) -> dict[str, Any]:
    """Train baselines, persist results, and return the report payload."""

    prepared = prepare_engine_training_data(
        subset=subset,
        validation_size=0.2,
        random_state=random_state,
        capped_rul=capped_rul,
    )
    fitted, metrics, predictions = _fit_models(prepared, random_state, capped_rul)
    best_name = min(metrics, key=lambda name: metrics[name].rmse)

    raw_feature_columns = tuple(
        prepared.pipeline.feature_names_in_.tolist()
    )
    bundle = EngineModelBundle(
        subset=subset,
        capped_rul=capped_rul,
        feature_columns=raw_feature_columns,
        preprocessor=prepared.pipeline,
        model=fitted[best_name],
        model_name=best_name,
        validation_metrics=metrics[best_name],
    )

    model_dir = project_root / "models" / "engine"
    metrics_dir = project_root / "reports" / "metrics"
    figure_dir = project_root / "reports" / "figures" / "engine"
    model_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "fd001_baseline_bundle.joblib"
    metrics_path = metrics_dir / "engine_fd001_baselines.json"
    predictions_path = metrics_dir / "engine_fd001_validation_predictions.csv"

    joblib.dump(bundle, model_path, compress=3)
    result = {
        "subset": subset,
        "capped_rul": capped_rul,
        "random_state": random_state,
        "train_engines": len(prepared.train_units),
        "validation_engines": len(prepared.validation_units),
        "train_rows": len(prepared.X_train),
        "validation_rows": len(prepared.X_validation),
        "retained_features": prepared.X_train.shape[1],
        "best_model": best_name,
        "metrics": {name: asdict(score) for name, score in metrics.items()},
        "model_path": str(model_path.relative_to(project_root)),
    }
    metrics_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    prediction_frame = pd.DataFrame(
        {"actual_rul": prepared.y_validation.to_numpy(), **predictions}
    )
    prediction_frame.to_csv(predictions_path, index=False)
    _save_figures(
        prepared.y_validation, metrics, predictions, best_name, figure_dir
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", default="FD001")
    parser.add_argument("--capped-rul", type=int, default=125)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = train_engine_baselines(
        root, args.subset, args.capped_rul, args.random_state
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
