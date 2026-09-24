"""Tune a phase-residual fuel detector under blocked normal evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from src.data.fuel_system import FUEL_SENSOR_COLUMNS
from src.fuel_phase_modeling import (
    FuelPhaseResidualBundle,
    FuelPhaseResidualDetector,
    causal_persistence,
)
from src.model_improvements import fuel_detection_metrics
from src.train_fuel import conservative_quantile, contiguous_fuel_blocks


@dataclass(frozen=True)
class FuelPhaseCandidate:
    aggregation: str
    threshold_quantile: float
    persistence_window: int
    persistence_required: int

    @property
    def name(self) -> str:
        return (
            f"{self.aggregation}_q{self.threshold_quantile:.3f}_"
            f"p{self.persistence_required}of{self.persistence_window}"
        )


def fuel_phase_candidates() -> tuple[FuelPhaseCandidate, ...]:
    return tuple(
        FuelPhaseCandidate(aggregation, quantile, window, required)
        for aggregation in ("mean", "p75", "top2_mean", "max")
        for quantile in (0.80, 0.85, 0.90, 0.925, 0.95, 0.975, 0.99)
        for window, required in ((1, 1), (5, 3), (7, 4))
    )


def _blocked_predictions(
    normal: pd.DataFrame,
    abnormal: pd.DataFrame,
    candidate: FuelPhaseCandidate,
) -> tuple[np.ndarray, np.ndarray, list[float]]:
    blocks = contiguous_fuel_blocks(normal, n_blocks=6)
    normal_predictions = np.full(len(normal), -1, dtype=int)
    abnormal_votes: list[np.ndarray] = []
    thresholds: list[float] = []
    all_positions = set(range(len(normal)))

    for fold_number, test_indices in enumerate(blocks):
        calibration_indices = blocks[(fold_number - 1) % len(blocks)]
        train_indices = np.asarray(
            sorted(
                all_positions
                .difference(test_indices)
                .difference(calibration_indices)
            ),
            dtype=int,
        )
        detector = FuelPhaseResidualDetector.fit(
            normal.iloc[train_indices],
            FUEL_SENSOR_COLUMNS,
            aggregation=candidate.aggregation,
        )
        calibration_scores = detector.anomaly_score(normal.iloc[calibration_indices])
        threshold = conservative_quantile(
            calibration_scores, candidate.threshold_quantile
        )
        thresholds.append(threshold)
        normal_scores = detector.anomaly_score(normal.iloc[test_indices])
        normal_predictions[test_indices] = (normal_scores > threshold).astype(int)
        abnormal_scores = detector.anomaly_score(abnormal)
        abnormal_votes.append((abnormal_scores > threshold).astype(int))

    votes = np.column_stack(abnormal_votes)
    abnormal_predictions = (
        votes.sum(axis=1) >= votes.shape[1] // 2 + 1
    ).astype(int)
    normal_predictions = causal_persistence(
        normal_predictions,
        candidate.persistence_window,
        candidate.persistence_required,
    )
    smoothed_abnormal = np.empty_like(abnormal_predictions)
    for scenario in abnormal["scenario_id"].unique():
        mask = abnormal["scenario_id"].to_numpy() == scenario
        smoothed_abnormal[mask] = causal_persistence(
            abnormal_predictions[mask],
            candidate.persistence_window,
            candidate.persistence_required,
        )
    return normal_predictions, smoothed_abnormal, thresholds


def evaluate_phase_candidate(
    table: pd.DataFrame, candidate: FuelPhaseCandidate
) -> dict[str, Any]:
    normal = (
        table.loc[table["scenario_id"] == "normal"]
        .sort_values("sample_index")
        .reset_index(drop=True)
    )
    abnormal = table.loc[table["scenario_id"] != "normal"].reset_index(drop=True)
    normal_pred, abnormal_pred, thresholds = _blocked_predictions(
        normal, abnormal, candidate
    )
    evaluation = pd.concat([normal, abnormal], ignore_index=True)
    predicted = np.concatenate([normal_pred, abnormal_pred])
    metrics = fuel_detection_metrics(evaluation, predicted)
    metrics["fold_threshold_median"] = float(np.median(thresholds))
    metrics["selection_score"] = float(
        metrics["balanced_accuracy"]
        - 0.75 * max(metrics["normal_false_alarm_rate"] - 0.10, 0.0)
    )
    return metrics


def tune_fuel_phase_detector(project_root: Path) -> dict[str, Any]:
    table = pd.read_csv(
        project_root / "data" / "processed" / "fuel_system" / "scenario_features.csv"
    )
    candidates: dict[str, dict[str, Any]] = {}
    definitions = {candidate.name: candidate for candidate in fuel_phase_candidates()}
    for name, candidate in definitions.items():
        candidates[name] = evaluate_phase_candidate(table, candidate)
    selected_name = max(
        candidates,
        key=lambda name: (
            candidates[name]["selection_score"],
            candidates[name]["balanced_accuracy"],
        ),
    )
    selected = definitions[selected_name]
    selected_metrics = candidates[selected_name]
    normal = (
        table.loc[table["scenario_id"] == "normal"]
        .sort_values("sample_index")
        .reset_index(drop=True)
    )
    detector = FuelPhaseResidualDetector.fit(
        normal, FUEL_SENSOR_COLUMNS, aggregation=selected.aggregation
    )
    bundle = FuelPhaseResidualBundle(
        detector=detector,
        threshold=float(selected_metrics["fold_threshold_median"]),
        persistence_window=selected.persistence_window,
        persistence_required=selected.persistence_required,
        expected_false_alarm_rate=1 - selected.threshold_quantile,
        validation_metrics={
            key: float(value)
            for key, value in selected_metrics.items()
            if isinstance(value, (int, float))
        },
        validation_protocol=(
            "six_contiguous_normal_test_blocks_with_separate_calibration_block_"
            "and_abnormal_majority_vote"
        ),
    )
    model_path = (
        project_root / "models" / "readiness" / "fuel_phase_residual_bundle.joblib"
    )
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, model_path, compress=3)
    output = {
        "selected_model": "phase_aligned_residual_detector",
        "selected_candidate": selected_name,
        "selected_parameters": {
            "aggregation": selected.aggregation,
            "threshold_quantile": selected.threshold_quantile,
            "persistence_window": selected.persistence_window,
            "persistence_required": selected.persistence_required,
        },
        "metrics": selected_metrics,
        "candidate_metrics": candidates,
        "model_path": str(model_path.relative_to(project_root)),
        "normal_trajectories": int(normal["scenario_id"].nunique()),
        "readiness_gate": "fail",
        "reason": "Only one independent normal trajectory is available.",
    }
    metrics_path = project_root / "reports" / "metrics" / "fuel_phase_tuning.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(tune_fuel_phase_detector(root), indent=2))


if __name__ == "__main__":
    main()
