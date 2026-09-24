"""Official NASA C-MAPSS test-set evaluation for the selected engine model."""

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
import numpy as np
import pandas as pd

_matplotlib_cache = Path(tempfile.gettempdir()) / "aircraft-matplotlib-cache"
_matplotlib_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_matplotlib_cache))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.data.cmapss import load_test_with_rul, load_training_with_rul
from src.modeling import EngineModelBundle, ModelMetrics
from src.preprocessing import (
    NON_FEATURE_COLUMNS,
    add_causal_engine_features,
    build_engine_preprocessor,
    transformed_feature_names,
)
from src.train import baseline_models, evaluate_predictions


def nasa_asymmetric_score(
    actual: np.ndarray | pd.Series, predicted: np.ndarray | pd.Series
) -> float:
    """Return the PHM08 score, which penalizes late predictions more heavily."""

    errors = np.asarray(predicted, dtype=float) - np.asarray(actual, dtype=float)
    penalties = np.where(
        errors < 0,
        np.exp(-errors / 13.0) - 1.0,
        np.exp(errors / 10.0) - 1.0,
    )
    return float(penalties.sum())


def official_terminal_rows(subset: str = "FD001") -> pd.DataFrame:
    """Return one final observed row and NASA RUL label per official test unit."""

    test = load_test_with_rul(subset)
    featured = add_causal_engine_features(test)
    terminal_indices = featured.groupby("unit_id")["cycle"].idxmax()
    terminal = featured.loc[terminal_indices].sort_values("unit_id").reset_index(drop=True)

    if terminal["unit_id"].duplicated().any():
        raise RuntimeError("Official test evaluation contains duplicate unit IDs.")
    return terminal


def _fit_full_training_model(
    subset: str,
    capped_rul: int,
    random_state: int,
) -> tuple[EngineModelBundle, pd.DataFrame, float]:
    train = load_training_with_rul(subset)
    train["rul"] = train["rul"].clip(upper=capped_rul)
    train = add_causal_engine_features(train)
    feature_columns = tuple(
        column for column in train.columns if column not in NON_FEATURE_COLUMNS
    )
    preprocessor = build_engine_preprocessor()
    transformed_values = preprocessor.fit_transform(train.loc[:, feature_columns])
    output_columns = transformed_feature_names(preprocessor, feature_columns)
    transformed = pd.DataFrame(
        transformed_values, columns=output_columns, index=train.index
    )
    model: Any = baseline_models(random_state)["random_forest"]
    started = time.perf_counter()
    model.fit(transformed, train["rul"])
    training_seconds = time.perf_counter() - started
    provisional_metrics = ModelMetrics(
        mae=float("nan"),
        rmse=float("nan"),
        r2=float("nan"),
        training_seconds=training_seconds,
    )
    bundle = EngineModelBundle(
        subset=subset,
        capped_rul=capped_rul,
        feature_columns=feature_columns,
        preprocessor=preprocessor,
        model=model,
        model_name="random_forest",
        validation_metrics=provisional_metrics,
    )
    return bundle, train, training_seconds


def _save_official_figures(predictions: pd.DataFrame, figure_dir: Path) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    ax.scatter(
        predictions["actual_rul"],
        predictions["predicted_rul"],
        color="#0891b2",
        alpha=0.7,
    )
    upper = max(150, int(predictions["actual_rul"].max()) + 5)
    ax.plot([0, upper], [0, upper], "--", color="#f59e0b", label="Ideal")
    ax.set(
        title="FD001 Official Test: Actual vs Predicted Terminal RUL",
        xlabel="NASA actual RUL (cycles)",
        ylabel="Predicted RUL (cycles)",
        xlim=(0, upper),
        ylim=(0, upper),
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_dir / "fd001_official_test_actual_vs_predicted.png", dpi=160)
    plt.close(fig)

    ordered = predictions.sort_values("actual_rul")
    fig, ax = plt.subplots(figsize=(11, 5))
    positions = np.arange(len(ordered))
    ax.plot(positions, ordered["actual_rul"], label="NASA actual", color="#f59e0b")
    ax.plot(positions, ordered["predicted_rul"], label="Predicted", color="#0891b2")
    ax.set(
        title="FD001 Official Test Predictions Ordered by Actual RUL",
        xlabel="Test engine ordered by actual RUL",
        ylabel="RUL (cycles)",
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_dir / "fd001_official_test_ordered_predictions.png", dpi=160)
    plt.close(fig)


def evaluate_official_fd001(
    project_root: Path,
    subset: str = "FD001",
    capped_rul: int = 125,
    random_state: int = 42,
) -> dict[str, Any]:
    """Retrain on all training units and evaluate official terminal labels."""

    bundle, train, training_seconds = _fit_full_training_model(
        subset, capped_rul, random_state
    )
    terminal = official_terminal_rows(subset)
    predicted = bundle.predict_feature_frame(terminal)
    actual_raw = terminal["rul"].astype(float)
    actual_capped = actual_raw.clip(upper=capped_rul)
    raw_metrics = evaluate_predictions(actual_raw, predicted)
    capped_metrics = evaluate_predictions(actual_capped, predicted)
    official_score = nasa_asymmetric_score(actual_raw, predicted)

    bundle.validation_metrics = ModelMetrics(
        training_seconds=training_seconds, **raw_metrics
    )
    predictions = pd.DataFrame(
        {
            "unit_id": terminal["unit_id"].astype(int),
            "last_observed_cycle": terminal["cycle"].astype(int),
            "actual_rul": actual_raw,
            "actual_capped_rul": actual_capped,
            "predicted_rul": predicted,
        }
    )
    predictions["error"] = predictions["predicted_rul"] - predictions["actual_rul"]
    predictions["absolute_error"] = predictions["error"].abs()

    model_dir = project_root / "models" / "engine"
    metrics_dir = project_root / "reports" / "metrics"
    figure_dir = project_root / "reports" / "figures" / "engine"
    model_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "fd001_official_test_bundle.joblib"
    predictions_path = metrics_dir / "engine_fd001_official_test_predictions.csv"
    metrics_path = metrics_dir / "engine_fd001_official_test.json"
    joblib.dump(bundle, model_path, compress=3)
    predictions.to_csv(predictions_path, index=False)

    worst = predictions.nlargest(5, "absolute_error")
    result = {
        "subset": subset,
        "training_engines": int(train["unit_id"].nunique()),
        "training_rows": len(train),
        "official_test_engines": len(terminal),
        "capped_rul": capped_rul,
        "retained_features": int(bundle.model.n_features_in_),
        "model": bundle.model_name,
        "raw_rul_metrics": raw_metrics,
        "capped_rul_metrics": capped_metrics,
        "nasa_asymmetric_score": official_score,
        "mean_error": float(predictions["error"].mean()),
        "median_absolute_error": float(predictions["absolute_error"].median()),
        "worst_test_units": worst[
            ["unit_id", "actual_rul", "predicted_rul", "absolute_error"]
        ].to_dict(orient="records"),
        "model_path": str(model_path.relative_to(project_root)),
    }
    metrics_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    _save_official_figures(predictions, figure_dir)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", default="FD001")
    parser.add_argument("--capped-rul", type=int, default=125)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = evaluate_official_fd001(
        root, args.subset, args.capped_rul, args.random_state
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
