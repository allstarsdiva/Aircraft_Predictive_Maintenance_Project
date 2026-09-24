"""Grouped baseline training for NASA battery SOH regression."""

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
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_selection import VarianceThreshold
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

_matplotlib_cache = Path(tempfile.gettempdir()) / "aircraft-matplotlib-cache"
_matplotlib_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_matplotlib_cache))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.features import build_battery_soh_feature_table
from src.modeling import BatterySOHModelBundle, ModelMetrics
from src.train import evaluate_predictions

BATTERY_ID_COLUMNS = frozenset({"battery_id", "uid", "soh_percent"})


def split_battery_groups(
    table: pd.DataFrame,
    validation_size: float = 0.2,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep each battery entirely in training or validation."""

    splitter = GroupShuffleSplit(
        n_splits=1, test_size=validation_size, random_state=random_state
    )
    train_indices, validation_indices = next(
        splitter.split(table, groups=table["battery_id"])
    )
    train = table.iloc[train_indices].copy()
    validation = table.iloc[validation_indices].copy()
    if set(train["battery_id"]) & set(validation["battery_id"]):
        raise RuntimeError("Battery leakage detected across model partitions.")
    return train, validation


def build_battery_preprocessor() -> Pipeline:
    return Pipeline(
        [
            ("variance", VarianceThreshold(threshold=0.0)),
            ("scaler", StandardScaler()),
        ]
    )


def _models(random_state: int) -> dict[str, Any]:
    return {
        "median_dummy": DummyRegressor(strategy="median"),
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(
            n_estimators=250,
            max_depth=18,
            min_samples_leaf=2,
            max_features="sqrt",
            n_jobs=-1,
            random_state=random_state,
        ),
    }


def train_battery_soh_baselines(
    project_root: Path,
    feature_table: pd.DataFrame | None = None,
    random_state: int = 42,
) -> dict[str, Any]:
    """Extract features, compare models, and save the best SOH bundle."""

    table = feature_table if feature_table is not None else build_battery_soh_feature_table()
    processed_dir = project_root / "data" / "processed" / "battery"
    processed_dir.mkdir(parents=True, exist_ok=True)
    features_path = processed_dir / "soh_features.csv"
    table.to_csv(features_path, index=False)

    train, validation = split_battery_groups(table, random_state=random_state)
    feature_columns = tuple(
        column for column in table.columns if column not in BATTERY_ID_COLUMNS
    )
    preprocessor = build_battery_preprocessor()
    train_values = preprocessor.fit_transform(train.loc[:, feature_columns])
    validation_values = preprocessor.transform(validation.loc[:, feature_columns])
    retained = np.asarray(feature_columns)[
        preprocessor.named_steps["variance"].get_support()
    ].tolist()
    X_train = pd.DataFrame(train_values, columns=retained)
    X_validation = pd.DataFrame(validation_values, columns=retained)
    y_train = train["soh_percent"].reset_index(drop=True)
    y_validation = validation["soh_percent"].reset_index(drop=True)

    fitted: dict[str, Any] = {}
    metrics: dict[str, ModelMetrics] = {}
    predictions: dict[str, np.ndarray] = {}
    for name, model in _models(random_state).items():
        started = time.perf_counter()
        model.fit(X_train, y_train)
        elapsed = time.perf_counter() - started
        predicted = np.clip(model.predict(X_validation), 0, 150)
        fitted[name] = model
        predictions[name] = predicted
        metrics[name] = ModelMetrics(
            training_seconds=elapsed,
            **evaluate_predictions(y_validation, predicted),
        )
    best_name = min(metrics, key=lambda name: metrics[name].rmse)
    bundle = BatterySOHModelBundle(
        feature_columns=feature_columns,
        preprocessor=preprocessor,
        model=fitted[best_name],
        model_name=best_name,
        validation_metrics=metrics[best_name],
    )

    model_dir = project_root / "models" / "battery"
    metrics_dir = project_root / "reports" / "metrics"
    figure_dir = project_root / "reports" / "figures" / "battery"
    model_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "soh_baseline_bundle.joblib"
    joblib.dump(bundle, model_path, compress=3)

    prediction_table = validation[["battery_id", "uid", "discharge_cycle"]].copy()
    prediction_table["actual_soh"] = validation["soh_percent"]
    for name, predicted in predictions.items():
        prediction_table[name] = predicted
    prediction_table.to_csv(
        metrics_dir / "battery_soh_validation_predictions.csv", index=False
    )

    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    ax.scatter(y_validation, predictions[best_name], s=14, alpha=0.45, color="#7c3aed")
    ax.plot([0, 140], [0, 140], "--", color="#f59e0b", label="Ideal")
    ax.set(
        title=f"Battery SOH: Actual vs Predicted ({best_name.replace('_', ' ').title()})",
        xlabel="Actual SOH (%)",
        ylabel="Predicted SOH (%)",
        xlim=(0, 140),
        ylim=(0, 140),
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_dir / "battery_soh_actual_vs_predicted.png", dpi=160)
    plt.close(fig)

    result = {
        "rows": len(table),
        "batteries": int(table["battery_id"].nunique()),
        "train_rows": len(train),
        "validation_rows": len(validation),
        "train_batteries": sorted(train["battery_id"].unique().tolist()),
        "validation_batteries": sorted(validation["battery_id"].unique().tolist()),
        "input_features": len(feature_columns),
        "retained_features": len(retained),
        "best_model": best_name,
        "metrics": {name: asdict(value) for name, value in metrics.items()},
        "model_path": str(model_path.relative_to(project_root)),
        "features_path": str(features_path.relative_to(project_root)),
    }
    (metrics_dir / "battery_soh_baselines.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(train_battery_soh_baselines(root, random_state=args.random_state), indent=2))


if __name__ == "__main__":
    main()
