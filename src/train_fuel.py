"""Normal-only, temporally blocked fuel-system anomaly experiment."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.covariance import LedoitWolf
from sklearn.ensemble import IsolationForest
from sklearn.feature_selection import VarianceThreshold
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

_cache = Path(tempfile.gettempdir()) / "aircraft-matplotlib-cache"
_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_cache))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.eda_fuel import FUEL_NON_FEATURE_COLUMNS
from src.fuel_modeling import FuelAnomalyModelBundle


def contiguous_fuel_blocks(normal: pd.DataFrame, n_blocks: int = 6) -> list[np.ndarray]:
    """Return non-overlapping blocks covering the ordered normal trajectory."""

    if n_blocks < 3 or len(normal) < n_blocks * 5:
        raise ValueError("Fuel evaluation needs at least three useful temporal blocks.")
    if not normal.sort_values("sample_index").index.equals(pd.RangeIndex(len(normal))):
        raise ValueError("Normal fuel rows must have a reset ordered index.")
    blocks = [
        np.asarray(block, dtype=int)
        for block in np.array_split(np.arange(len(normal)), n_blocks)
    ]
    if sorted(np.concatenate(blocks).tolist()) != list(range(len(normal))):
        raise RuntimeError("Fuel blocks do not cover the normal trajectory once.")
    return blocks


def build_fuel_preprocessor() -> Pipeline:
    return Pipeline([
        ("variance", VarianceThreshold(threshold=0.0)),
        ("scaler", StandardScaler()),
    ])


def _detectors(random_state: int) -> dict[str, Any]:
    return {
        "shrinkage_mahalanobis": LedoitWolf(),
        "isolation_forest": IsolationForest(
            n_estimators=400, contamination="auto", random_state=random_state,
            n_jobs=-1,
        ),
        "one_class_svm": OneClassSVM(kernel="rbf", gamma="scale", nu=0.05),
    }


def anomaly_scores(detector: Any, values: np.ndarray) -> np.ndarray:
    return FuelAnomalyModelBundle._raw_scores(detector, values)


def conservative_quantile(values: np.ndarray, quantile: float) -> float:
    if not 0 < quantile < 1:
        raise ValueError("quantile must be between zero and one.")
    scores = np.asarray(values, dtype=float)
    if scores.size == 0 or not np.isfinite(scores).all():
        raise ValueError("Calibration scores must be non-empty and finite.")
    return float(np.quantile(scores, quantile, method="higher"))


def _fit_detector(
    detector: Any, train: pd.DataFrame, feature_columns: tuple[str, ...]
) -> tuple[Pipeline, Any]:
    preprocessor = build_fuel_preprocessor()
    values = preprocessor.fit_transform(train.loc[:, feature_columns])
    return preprocessor, clone(detector).fit(values)


def _evaluate_candidate(
    detector: Any,
    normal: pd.DataFrame,
    abnormal: pd.DataFrame,
    feature_columns: tuple[str, ...],
    threshold_quantile: float,
) -> tuple[dict[str, object], np.ndarray, np.ndarray, np.ndarray]:
    blocks = contiguous_fuel_blocks(normal)
    normal_predictions = np.full(len(normal), -1, dtype=int)
    normal_margins = np.full(len(normal), np.nan, dtype=float)
    abnormal_votes, abnormal_margins = [], []
    all_positions = set(range(len(normal)))

    for test_number, test_indices in enumerate(blocks):
        calibration_indices = blocks[(test_number - 1) % len(blocks)]
        train_indices = np.asarray(sorted(
            all_positions.difference(test_indices).difference(calibration_indices)
        ), dtype=int)
        preprocessor, fitted = _fit_detector(
            detector, normal.iloc[train_indices], feature_columns
        )
        calibration_scores = anomaly_scores(
            fitted,
            preprocessor.transform(
                normal.iloc[calibration_indices].loc[:, feature_columns]
            ),
        )
        threshold = conservative_quantile(calibration_scores, threshold_quantile)
        scale = max(float(np.std(calibration_scores, ddof=0)), 1e-12)
        test_scores = anomaly_scores(
            fitted,
            preprocessor.transform(normal.iloc[test_indices].loc[:, feature_columns]),
        )
        normal_predictions[test_indices] = (test_scores > threshold).astype(int)
        normal_margins[test_indices] = (test_scores - threshold) / scale
        abnormal_scores = anomaly_scores(
            fitted, preprocessor.transform(abnormal.loc[:, feature_columns])
        )
        abnormal_votes.append((abnormal_scores > threshold).astype(int))
        abnormal_margins.append((abnormal_scores - threshold) / scale)

    if (normal_predictions < 0).any() or not np.isfinite(normal_margins).all():
        raise RuntimeError("Blocked normal evaluation did not cover every row.")
    votes = np.column_stack(abnormal_votes)
    abnormal_predictions = (
        votes.sum(axis=1) >= votes.shape[1] // 2 + 1
    ).astype(int)
    abnormal_score = np.median(np.column_stack(abnormal_margins), axis=1)
    actual = np.concatenate([
        np.zeros(len(normal), dtype=int), np.ones(len(abnormal), dtype=int)
    ])
    predicted = np.concatenate([normal_predictions, abnormal_predictions])
    scenario_rates = {
        scenario: float(abnormal_predictions[
            abnormal["scenario_id"].to_numpy() == scenario
        ].mean())
        for scenario in ("one", "two", "three", "four")
    }
    metrics: dict[str, object] = {
        "accuracy": float(accuracy_score(actual, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(actual, predicted)),
        "macro_f1": float(f1_score(actual, predicted, average="macro")),
        "normal_false_alarm_rate": float(normal_predictions.mean()),
        "abnormal_detection_rate": float(abnormal_predictions.mean()),
        "scenario_detection_rates": scenario_rates,
    }
    return metrics, normal_predictions, abnormal_predictions, np.concatenate([
        normal_margins, abnormal_score
    ])


def _fit_deployment_ensemble(
    detector: Any,
    normal: pd.DataFrame,
    feature_columns: tuple[str, ...],
    threshold_quantile: float,
    detector_name: str,
    validation_metrics: dict[str, float],
) -> FuelAnomalyModelBundle:
    blocks = contiguous_fuel_blocks(normal)
    all_positions = set(range(len(normal)))
    preprocessors, fitted_detectors, thresholds, scales = [], [], [], []
    for calibration_indices in blocks:
        train_indices = np.asarray(
            sorted(all_positions.difference(calibration_indices)), dtype=int
        )
        preprocessor, fitted = _fit_detector(
            detector, normal.iloc[train_indices], feature_columns
        )
        scores = anomaly_scores(
            fitted,
            preprocessor.transform(
                normal.iloc[calibration_indices].loc[:, feature_columns]
            ),
        )
        preprocessors.append(preprocessor)
        fitted_detectors.append(fitted)
        thresholds.append(conservative_quantile(scores, threshold_quantile))
        scales.append(max(float(np.std(scores, ddof=0)), 1e-12))
    return FuelAnomalyModelBundle(
        feature_columns=feature_columns,
        preprocessors=tuple(preprocessors),
        detectors=tuple(fitted_detectors),
        thresholds=tuple(thresholds),
        score_scales=tuple(scales),
        detector_name=detector_name,
        expected_false_alarm_rate=1 - threshold_quantile,
        validation_metrics=validation_metrics,
    )


def train_fuel_anomaly_baselines(
    project_root: Path,
    feature_table: pd.DataFrame | None = None,
    random_state: int = 42,
    threshold_quantile: float = 0.95,
) -> dict[str, object]:
    """Compare normal-only detectors using blocked normal evaluation."""

    table = feature_table.copy() if feature_table is not None else pd.read_csv(
        project_root / "data" / "processed" / "fuel_system" / "scenario_features.csv"
    )
    normal = table.loc[table["scenario_id"] == "normal"].sort_values(
        "sample_index"
    ).reset_index(drop=True)
    abnormal = table.loc[table["scenario_id"] != "normal"].reset_index(drop=True)
    feature_columns = tuple(
        column for column in table.columns if column not in FUEL_NON_FEATURE_COLUMNS
    )
    metrics, predictions = {}, {}
    for name, detector in _detectors(random_state).items():
        result, normal_pred, abnormal_pred, scores = _evaluate_candidate(
            detector, normal, abnormal, feature_columns, threshold_quantile
        )
        metrics[name] = result
        predictions[name] = (normal_pred, abnormal_pred, scores)
    best_name = max(metrics, key=lambda name: (
        float(metrics[name]["balanced_accuracy"]),
        float(metrics[name]["macro_f1"]),
    ))
    bundle = _fit_deployment_ensemble(
        _detectors(random_state)[best_name], normal, feature_columns,
        threshold_quantile, best_name,
        {key: float(value) for key, value in metrics[best_name].items()
         if isinstance(value, (int, float))},
    )

    model_dir = project_root / "models" / "fuel_system"
    metrics_dir = project_root / "reports" / "metrics"
    figure_dir = project_root / "reports" / "figures" / "fuel_system"
    for directory in (model_dir, metrics_dir, figure_dir):
        directory.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "normal_anomaly_bundle.joblib"
    joblib.dump(bundle, model_path, compress=3)

    output_rows = pd.concat([
        normal.assign(evaluation_kind="blocked_normal_test"),
        abnormal.assign(evaluation_kind="abnormal_scenario"),
    ], ignore_index=True)[
        ["scenario_id", "sample_index", "is_abnormal", "evaluation_kind"]
    ]
    for name, (normal_pred, abnormal_pred, scores) in predictions.items():
        output_rows[f"{name}_prediction"] = np.concatenate([
            normal_pred, abnormal_pred
        ])
        output_rows[f"{name}_standardized_score"] = scores
    output_rows.to_csv(
        metrics_dir / "fuel_system_blocked_predictions.csv", index=False
    )

    names = list(metrics)
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.bar(x - 0.18, [1 - float(metrics[name]["normal_false_alarm_rate"])
                      for name in names], 0.36, label="Normal specificity")
    ax.bar(x + 0.18, [float(metrics[name]["abnormal_detection_rate"])
                      for name in names], 0.36, label="Abnormal detection rate")
    ax.set(
        title="Fuel Normal-Only Detector Comparison", ylabel="Rate",
        xticks=x, xticklabels=[name.replace("_", " ").title() for name in names],
        ylim=(0, 1.05),
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_dir / "fuel_anomaly_model_comparison.png", dpi=160)
    plt.close(fig)

    selected_scores = predictions[best_name][2]
    plot_table = output_rows[["scenario_id", "sample_index"]].copy()
    plot_table["score"] = selected_scores
    fig, ax = plt.subplots(figsize=(12, 6))
    for scenario, rows in plot_table.groupby("scenario_id", sort=False):
        ax.plot(rows["sample_index"], rows["score"], label=scenario.title())
    ax.axhline(0, color="#111827", linestyle="--", label="Calibrated threshold")
    ax.set(
        title=f"Fuel Anomaly Margins ({best_name.replace('_', ' ').title()})",
        xlabel="Ordered sample index", ylabel="Standardized anomaly margin",
    )
    ax.legend(ncol=3)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(figure_dir / "fuel_selected_anomaly_scores.png", dpi=160)
    plt.close(fig)

    output = {
        "experimental": True,
        "normal_training_rows": len(normal),
        "abnormal_evaluation_rows": len(abnormal),
        "features": len(feature_columns),
        "normal_temporal_blocks": 6,
        "threshold_quantile": threshold_quantile,
        "best_model": best_name,
        "selection_metric": "balanced_accuracy_then_macro_f1",
        "candidate_metrics": metrics,
        "model_path": str(model_path.relative_to(project_root)),
        "validation_statement": (
            "Within-dataset blocked evaluation only; one normal trajectory cannot "
            "establish generalization to a new normal flight or simulation."
        ),
    }
    (metrics_dir / "fuel_system_anomaly_baselines.json").write_text(
        json.dumps(output, indent=2), encoding="utf-8"
    )
    return output


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(train_fuel_anomaly_baselines(root), indent=2))


if __name__ == "__main__":
    main()
