"""Uncertainty-aware experimental battery RUL training.

Only batteries that reach a documented end-of-life capacity threshold provide
direct RUL labels. Leave-one-battery-out validation is used because this subset
contains just nine independent battery trajectories.
"""

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
from sklearn.base import clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_selection import VarianceThreshold
from sklearn.linear_model import Ridge
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

_matplotlib_cache = Path(tempfile.gettempdir()) / "aircraft-matplotlib-cache"
_matplotlib_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_matplotlib_cache))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.modeling import BatteryRULModelBundle, ModelMetrics
from src.train import evaluate_predictions

BATTERY_RUL_EXCLUDED_COLUMNS = frozenset(
    {
        "battery_id",
        "uid",
        "soh_percent",
        "rul_cycles",
        "observed_eol_cycle",
    }
)


def build_battery_rul_feature_table(
    project_root: Path,
    soh_features: pd.DataFrame | None = None,
    discharge_cycles: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Join curve features to direct, pre-EOL RUL labels by measurement UID."""

    processed = project_root / "data" / "processed" / "battery"
    features = (
        soh_features.copy()
        if soh_features is not None
        else pd.read_csv(processed / "soh_features.csv")
    )
    discharge = (
        discharge_cycles.copy()
        if discharge_cycles is not None
        else pd.read_csv(processed / "discharge_cycles.csv")
    )
    eligible = discharge.loc[
        discharge["rul_training_eligible"].astype(bool),
        ["uid", "rul_cycles", "observed_eol_cycle"],
    ]
    if eligible["uid"].duplicated().any() or features["uid"].duplicated().any():
        raise ValueError("Battery UID values must be unique before the RUL join.")
    table = features.merge(eligible, on="uid", how="inner", validate="one_to_one")
    if len(table) != len(eligible):
        raise ValueError("Not every eligible battery RUL label has curve features.")
    if table["rul_cycles"].isna().any() or (table["rul_cycles"] < 0).any():
        raise ValueError("Battery RUL targets must be finite and non-negative.")
    return table.sort_values(["battery_id", "discharge_cycle"]).reset_index(drop=True)


def build_battery_rul_preprocessor() -> Pipeline:
    return Pipeline(
        [
            ("variance", VarianceThreshold(threshold=0.0)),
            ("scaler", StandardScaler()),
        ]
    )


def _models(random_state: int) -> dict[str, Any]:
    return {
        "median_dummy": DummyRegressor(strategy="median"),
        "ridge": Ridge(alpha=10.0),
        "random_forest": RandomForestRegressor(
            n_estimators=400,
            max_depth=12,
            min_samples_leaf=3,
            max_features="sqrt",
            n_jobs=-1,
            random_state=random_state,
        ),
    }


def conformal_absolute_error_quantile(
    absolute_errors: np.ndarray, alpha: float = 0.10
) -> float:
    """Finite-sample conformal-style quantile using the conservative rank."""

    errors = np.asarray(absolute_errors, dtype=float)
    if errors.size == 0 or not np.isfinite(errors).all():
        raise ValueError("Calibration errors must be non-empty and finite.")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between zero and one.")
    rank = min(int(np.ceil((errors.size + 1) * (1 - alpha))), errors.size)
    return float(np.partition(errors, rank - 1)[rank - 1])


def _cross_validated_predictions(
    table: pd.DataFrame,
    feature_columns: tuple[str, ...],
    model: Any,
) -> np.ndarray:
    predictions = np.full(len(table), np.nan, dtype=float)
    groups = table["battery_id"].to_numpy()
    target = table["rul_cycles"].to_numpy(dtype=float)
    for train_indices, validation_indices in LeaveOneGroupOut().split(table, groups=groups):
        preprocessor = build_battery_rul_preprocessor()
        train_values = preprocessor.fit_transform(
            table.iloc[train_indices].loc[:, feature_columns]
        )
        validation_values = preprocessor.transform(
            table.iloc[validation_indices].loc[:, feature_columns]
        )
        retained = np.asarray(feature_columns)[
            preprocessor.named_steps["variance"].get_support()
        ]
        fitted = clone(model)
        fitted.fit(pd.DataFrame(train_values, columns=retained), target[train_indices])
        fold_predictions = fitted.predict(
            pd.DataFrame(validation_values, columns=retained)
        )
        predictions[validation_indices] = np.clip(fold_predictions, 0, None)
    if not np.isfinite(predictions).all():
        raise RuntimeError("Leave-one-battery-out prediction did not cover every row.")
    return predictions


def _macro_battery_metrics(
    table: pd.DataFrame, predictions: np.ndarray
) -> tuple[float, float, list[dict[str, object]]]:
    scored = table[["battery_id", "rul_cycles"]].copy()
    scored["prediction"] = predictions
    per_battery: list[dict[str, object]] = []
    for battery_id, rows in scored.groupby("battery_id", sort=True):
        errors = rows["prediction"] - rows["rul_cycles"]
        per_battery.append(
            {
                "battery_id": battery_id,
                "rows": len(rows),
                "mae": float(errors.abs().mean()),
                "rmse": float(np.sqrt(np.mean(np.square(errors)))),
                "bias": float(errors.mean()),
            }
        )
    return (
        float(np.mean([item["mae"] for item in per_battery])),
        float(np.mean([item["rmse"] for item in per_battery])),
        per_battery,
    )


def train_battery_rul_experiment(
    project_root: Path,
    feature_table: pd.DataFrame | None = None,
    random_state: int = 42,
    interval_alpha: float = 0.10,
) -> dict[str, Any]:
    """Compare grouped RUL models, fit the winner, and save its bundle."""

    table = (
        feature_table.copy()
        if feature_table is not None
        else build_battery_rul_feature_table(project_root)
    )
    if table["battery_id"].nunique() < 3:
        raise ValueError("At least three battery trajectories are required.")
    feature_columns = tuple(
        column for column in table.columns if column not in BATTERY_RUL_EXCLUDED_COLUMNS
    )
    target = table["rul_cycles"].to_numpy(dtype=float)

    metrics: dict[str, dict[str, float]] = {}
    all_predictions: dict[str, np.ndarray] = {}
    per_battery_results: dict[str, list[dict[str, object]]] = {}
    started = time.perf_counter()
    for name, model in _models(random_state).items():
        predicted = _cross_validated_predictions(table, feature_columns, model)
        row_metrics = evaluate_predictions(pd.Series(target), predicted)
        macro_mae, macro_rmse, per_battery = _macro_battery_metrics(table, predicted)
        metrics[name] = {
            **row_metrics,
            "macro_battery_mae": macro_mae,
            "macro_battery_rmse": macro_rmse,
        }
        all_predictions[name] = predicted
        per_battery_results[name] = per_battery
    validation_seconds = time.perf_counter() - started
    best_name = min(metrics, key=lambda name: metrics[name]["macro_battery_rmse"])
    best_predictions = all_predictions[best_name]
    error_quantile = conformal_absolute_error_quantile(
        np.abs(target - best_predictions), alpha=interval_alpha
    )
    interval_lower = np.clip(best_predictions - error_quantile, 0, None)
    interval_upper = best_predictions + error_quantile
    coverage = float(np.mean((target >= interval_lower) & (target <= interval_upper)))
    mean_width = float(np.mean(interval_upper - interval_lower))

    preprocessor = build_battery_rul_preprocessor()
    transformed = preprocessor.fit_transform(table.loc[:, feature_columns])
    retained = np.asarray(feature_columns)[
        preprocessor.named_steps["variance"].get_support()
    ]
    final_model = clone(_models(random_state)[best_name])
    fit_started = time.perf_counter()
    final_model.fit(pd.DataFrame(transformed, columns=retained), target)
    fit_seconds = time.perf_counter() - fit_started
    chosen_metrics = metrics[best_name]
    bundle = BatteryRULModelBundle(
        feature_columns=feature_columns,
        preprocessor=preprocessor,
        model=final_model,
        model_name=best_name,
        validation_metrics=ModelMetrics(
            mae=chosen_metrics["mae"],
            rmse=chosen_metrics["rmse"],
            r2=chosen_metrics["r2"],
            training_seconds=fit_seconds,
        ),
        interval_alpha=interval_alpha,
        absolute_error_quantile=error_quantile,
    )

    processed_dir = project_root / "data" / "processed" / "battery"
    model_dir = project_root / "models" / "battery"
    metrics_dir = project_root / "reports" / "metrics"
    figure_dir = project_root / "reports" / "figures" / "battery"
    for directory in (processed_dir, model_dir, metrics_dir, figure_dir):
        directory.mkdir(parents=True, exist_ok=True)
    feature_path = processed_dir / "rul_features.csv"
    model_path = model_dir / "rul_experimental_bundle.joblib"
    table.to_csv(feature_path, index=False)
    joblib.dump(bundle, model_path, compress=3)

    prediction_table = table[
        ["battery_id", "uid", "discharge_cycle", "observed_eol_cycle", "rul_cycles"]
    ].copy()
    for name, predicted in all_predictions.items():
        prediction_table[name] = predicted
    prediction_table["interval_lower_90"] = interval_lower
    prediction_table["interval_upper_90"] = interval_upper
    prediction_table.to_csv(
        metrics_dir / "battery_rul_logo_predictions.csv", index=False
    )

    fig, ax = plt.subplots(figsize=(7, 6.5))
    ax.scatter(target, best_predictions, s=17, alpha=0.55, color="#0f766e")
    limit = max(float(target.max()), float(best_predictions.max())) + 5
    ax.plot([0, limit], [0, limit], "--", color="#f59e0b", label="Ideal")
    ax.set(
        title=f"Battery RUL: Leave-One-Battery-Out ({best_name.replace('_', ' ').title()})",
        xlabel="Actual RUL (cycles)",
        ylabel="Predicted RUL (cycles)",
        xlim=(0, limit),
        ylim=(0, limit),
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_dir / "battery_rul_actual_vs_predicted.png", dpi=160)
    plt.close(fig)

    result = {
        "experimental": True,
        "rows": len(table),
        "batteries": int(table["battery_id"].nunique()),
        "validation": "leave_one_battery_out",
        "input_features": len(feature_columns),
        "retained_features": len(retained),
        "best_model": best_name,
        "selection_metric": "macro_battery_rmse",
        "metrics": metrics,
        "per_battery_metrics": per_battery_results[best_name],
        "uncertainty": {
            "method": "cross_validated_absolute_residual_quantile",
            "nominal_coverage": 1 - interval_alpha,
            "empirical_oof_coverage": coverage,
            "absolute_error_quantile_cycles": error_quantile,
            "mean_interval_width_cycles": mean_width,
            "warning": "Empirical interval from nine observed-EOL batteries; not a certified guarantee.",
        },
        "validation_seconds": validation_seconds,
        "model_path": str(model_path.relative_to(project_root)),
        "features_path": str(feature_path.relative_to(project_root)),
    }
    (metrics_dir / "battery_rul_experiment.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--interval-alpha", type=float, default=0.10)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = train_battery_rul_experiment(
        root,
        random_state=args.random_state,
        interval_alpha=args.interval_alpha,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
