"""Safety-oriented grouped cross-validation for the FD001 engine model."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GroupKFold

_matplotlib_cache = Path(tempfile.gettempdir()) / "aircraft-matplotlib-cache"
_matplotlib_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_matplotlib_cache))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.data.cmapss import load_training_with_rul
from src.evaluate import nasa_asymmetric_score
from src.modeling import EngineModelBundle, ModelMetrics
from src.preprocessing import (
    NON_FEATURE_COLUMNS,
    add_causal_engine_features,
    build_engine_preprocessor,
    transformed_feature_names,
)
from src.train import evaluate_predictions


@dataclass(frozen=True)
class TuningCandidate:
    name: str
    max_depth: int | None
    min_samples_leaf: int
    max_features: str | float
    near_failure_weight: float = 1.0
    warning_weight: float = 1.0


def tuning_candidates() -> tuple[TuningCandidate, ...]:
    return (
        TuningCandidate("baseline_rf", 20, 2, "sqrt"),
        TuningCandidate("regularized_leaf4", 18, 4, "sqrt"),
        TuningCandidate("regularized_leaf8", 15, 8, "sqrt"),
        TuningCandidate("broader_features", 18, 3, 0.5),
        TuningCandidate("safety_weighted", 20, 2, "sqrt", 3.0, 1.5),
        TuningCandidate("safety_regularized", 18, 4, 0.5, 3.0, 1.5),
    )


def safety_sample_weights(
    target: pd.Series,
    near_failure_weight: float,
    warning_weight: float,
) -> np.ndarray:
    """Increase fitting importance below 60 RUL without using future data."""

    return np.where(
        target.to_numpy() <= 30,
        near_failure_weight,
        np.where(target.to_numpy() <= 60, warning_weight, 1.0),
    )


def safety_metrics(actual: pd.Series, predicted: np.ndarray) -> dict[str, float]:
    """Calculate accuracy and late-prediction diagnostics."""

    standard = evaluate_predictions(actual, predicted)
    near_mask = actual.to_numpy() <= 30
    near_errors = predicted[near_mask] - actual.to_numpy()[near_mask]
    near_bias = float(near_errors.mean())
    nasa_average = nasa_asymmetric_score(actual, predicted) / len(actual)
    objective = (
        standard["rmse"]
        + 1.5 * max(near_bias, 0.0)
        + 0.5 * nasa_average
    )
    return {
        **standard,
        "nasa_average_penalty": float(nasa_average),
        "near_failure_bias": near_bias,
        "near_failure_late_rate": float((near_errors > 0).mean()),
        "safety_objective": float(objective),
    }


def _engine_frame(subset: str, capped_rul: int) -> tuple[pd.DataFrame, tuple[str, ...]]:
    frame = load_training_with_rul(subset)
    frame["rul"] = frame["rul"].clip(upper=capped_rul)
    frame = add_causal_engine_features(frame)
    features = tuple(
        column for column in frame.columns if column not in NON_FEATURE_COLUMNS
    )
    return frame, features


def _prepared_folds(
    frame: pd.DataFrame,
    features: tuple[str, ...],
    folds: int,
) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    splitter = GroupKFold(n_splits=folds)
    groups = frame["unit_id"]

    for train_indices, validation_indices in splitter.split(frame, groups=groups):
        train = frame.iloc[train_indices]
        validation = frame.iloc[validation_indices]
        preprocessor = build_engine_preprocessor()
        train_values = preprocessor.fit_transform(train.loc[:, features])
        validation_values = preprocessor.transform(validation.loc[:, features])
        output_columns = transformed_feature_names(preprocessor, features)
        prepared.append(
            {
                "train_indices": train_indices,
                "validation_indices": validation_indices,
                "X_train": pd.DataFrame(train_values, columns=output_columns),
                "X_validation": pd.DataFrame(
                    validation_values, columns=output_columns
                ),
                "y_train": train["rul"].reset_index(drop=True),
            }
        )
    return prepared


def _cross_validated_predictions(
    frame: pd.DataFrame,
    prepared_folds: list[dict[str, Any]],
    candidate: TuningCandidate,
    random_state: int,
) -> tuple[np.ndarray, float]:
    predictions = np.empty(len(frame), dtype=float)
    started = time.perf_counter()

    for fold in prepared_folds:
        model = RandomForestRegressor(
            n_estimators=160,
            max_depth=candidate.max_depth,
            min_samples_leaf=candidate.min_samples_leaf,
            max_features=candidate.max_features,
            n_jobs=-1,
            random_state=random_state,
        )
        weights = safety_sample_weights(
            fold["y_train"],
            candidate.near_failure_weight,
            candidate.warning_weight,
        )
        model.fit(fold["X_train"], fold["y_train"], sample_weight=weights)
        predictions[fold["validation_indices"]] = model.predict(
            fold["X_validation"]
        )

    return predictions, time.perf_counter() - started


def _fit_selected_full_model(
    frame: pd.DataFrame,
    features: tuple[str, ...],
    candidate: TuningCandidate,
    offset: float,
    subset: str,
    capped_rul: int,
    random_state: int,
    selected_metrics: dict[str, float],
) -> EngineModelBundle:
    preprocessor = build_engine_preprocessor()
    values = preprocessor.fit_transform(frame.loc[:, features])
    output_columns = transformed_feature_names(preprocessor, features)
    transformed = pd.DataFrame(values, columns=output_columns)
    model = RandomForestRegressor(
        n_estimators=250,
        max_depth=candidate.max_depth,
        min_samples_leaf=candidate.min_samples_leaf,
        max_features=candidate.max_features,
        n_jobs=-1,
        random_state=random_state,
    )
    weights = safety_sample_weights(
        frame["rul"], candidate.near_failure_weight, candidate.warning_weight
    )
    started = time.perf_counter()
    model.fit(transformed, frame["rul"], sample_weight=weights)
    training_seconds = time.perf_counter() - started
    metrics = ModelMetrics(
        mae=selected_metrics["mae"],
        rmse=selected_metrics["rmse"],
        r2=selected_metrics["r2"],
        training_seconds=training_seconds,
    )
    return EngineModelBundle(
        subset=subset,
        capped_rul=capped_rul,
        feature_columns=features,
        preprocessor=preprocessor,
        model=model,
        model_name=f"random_forest_{candidate.name}",
        validation_metrics=metrics,
        prediction_offset=offset,
    )


def tune_engine_model(
    project_root: Path,
    subset: str = "FD001",
    capped_rul: int = 125,
    folds: int = 5,
    random_state: int = 42,
) -> dict[str, Any]:
    """Select a safety-oriented candidate using grouped OOF predictions."""

    frame, features = _engine_frame(subset, capped_rul)
    prepared = _prepared_folds(frame, features, folds)
    offsets = (0.0, 3.0, 5.0, 7.0, 10.0)
    results: list[dict[str, Any]] = []
    prediction_cache: dict[str, np.ndarray] = {}

    for candidate in tuning_candidates():
        raw_predictions, elapsed = _cross_validated_predictions(
            frame, prepared, candidate, random_state
        )
        prediction_cache[candidate.name] = raw_predictions
        for offset in offsets:
            adjusted = np.clip(raw_predictions - offset, 0, capped_rul)
            metrics = safety_metrics(frame["rul"], adjusted)
            results.append(
                {
                    "candidate": candidate.name,
                    "offset": offset,
                    "cross_validation_seconds": elapsed,
                    "parameters": asdict(candidate),
                    **metrics,
                }
            )

    selected = min(results, key=lambda result: result["safety_objective"])
    selected_candidate = next(
        candidate
        for candidate in tuning_candidates()
        if candidate.name == selected["candidate"]
    )
    selected_predictions = np.clip(
        prediction_cache[selected_candidate.name] - selected["offset"],
        0,
        capped_rul,
    )
    baseline = next(
        result
        for result in results
        if result["candidate"] == "baseline_rf" and result["offset"] == 0
    )
    bundle = _fit_selected_full_model(
        frame,
        features,
        selected_candidate,
        selected["offset"],
        subset,
        capped_rul,
        random_state,
        selected,
    )

    model_dir = project_root / "models" / "engine"
    metrics_dir = project_root / "reports" / "metrics"
    figure_dir = project_root / "reports" / "figures" / "engine"
    model_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "fd001_tuned_bundle.joblib"
    results_path = metrics_dir / "engine_fd001_grouped_tuning.json"
    predictions_path = metrics_dir / "engine_fd001_tuned_oof_predictions.csv"
    joblib.dump(bundle, model_path, compress=3)

    oof = pd.DataFrame(
        {
            "unit_id": frame["unit_id"],
            "cycle": frame["cycle"],
            "actual_rul": frame["rul"],
            "predicted_rul": selected_predictions,
        }
    )
    oof["error"] = oof["predicted_rul"] - oof["actual_rul"]
    oof.to_csv(predictions_path, index=False)

    candidate_best = []
    for candidate in tuning_candidates():
        candidate_results = [
            result for result in results if result["candidate"] == candidate.name
        ]
        candidate_best.append(
            min(candidate_results, key=lambda result: result["safety_objective"])
        )
    figure_rows = sorted(candidate_best, key=lambda row: row["safety_objective"])
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(
        [row["candidate"].replace("_", " ") for row in figure_rows],
        [row["safety_objective"] for row in figure_rows],
        color="#0891b2",
    )
    ax.set(
        title="FD001 Grouped CV Safety Objective by Candidate",
        xlabel="Lower is better",
    )
    fig.tight_layout()
    fig.savefig(figure_dir / "fd001_grouped_tuning_objective.png", dpi=160)
    plt.close(fig)

    payload = {
        "subset": subset,
        "folds": folds,
        "engines": int(frame["unit_id"].nunique()),
        "rows": len(frame),
        "selection_rule": "RMSE + 1.5 * positive near-failure bias + 0.5 * average NASA penalty",
        "official_test_used_for_selection": False,
        "baseline": baseline,
        "selected": selected,
        "all_results": results,
        "model_path": str(model_path.relative_to(project_root)),
    }
    results_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", default="FD001")
    parser.add_argument("--capped-rul", type=int, default=125)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = tune_engine_model(
        root, args.subset, args.capped_rul, args.folds, args.random_state
    )
    print(json.dumps({"baseline": result["baseline"], "selected": result["selected"], "model_path": result["model_path"]}, indent=2))


if __name__ == "__main__":
    main()
