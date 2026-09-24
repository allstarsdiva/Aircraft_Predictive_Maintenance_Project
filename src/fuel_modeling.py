"""Stable serializable artifact type for fuel-system anomaly detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class FuelAnomalyModelBundle:
    """Normal-only detector ensemble with per-fold calibrated thresholds."""

    feature_columns: tuple[str, ...]
    preprocessors: tuple[Any, ...]
    detectors: tuple[Any, ...]
    thresholds: tuple[float, ...]
    score_scales: tuple[float, ...]
    detector_name: str
    expected_false_alarm_rate: float
    validation_metrics: dict[str, float]

    @staticmethod
    def _raw_scores(detector: Any, values: np.ndarray) -> np.ndarray:
        if hasattr(detector, "mahalanobis"):
            return np.asarray(detector.mahalanobis(values), dtype=float)
        if hasattr(detector, "decision_function"):
            return -np.asarray(detector.decision_function(values), dtype=float).ravel()
        raise TypeError("Fuel anomaly detector has no supported score method.")

    def _fold_margins(self, frame: pd.DataFrame) -> np.ndarray:
        missing = set(self.feature_columns).difference(frame.columns)
        if missing:
            raise ValueError(f"Missing fuel-system features: {sorted(missing)}")
        if not (
            len(self.preprocessors) == len(self.detectors)
            == len(self.thresholds) == len(self.score_scales)
        ):
            raise RuntimeError("Fuel anomaly ensemble components are inconsistent.")
        margins = []
        features = frame.loc[:, self.feature_columns]
        for preprocessor, detector, threshold, scale in zip(
            self.preprocessors, self.detectors, self.thresholds, self.score_scales
        ):
            raw = self._raw_scores(detector, preprocessor.transform(features))
            margins.append((raw - threshold) / max(float(scale), 1e-12))
        return np.column_stack(margins)

    def predict_anomaly_score(self, frame: pd.DataFrame) -> np.ndarray:
        """Return median standardized anomaly margin; positive means abnormal."""

        return np.median(self._fold_margins(frame), axis=1)

    def predict_feature_frame(self, frame: pd.DataFrame) -> np.ndarray:
        """Return one when a majority of ensemble detectors flag an anomaly."""

        margins = self._fold_margins(frame)
        return (
            (margins > 0).sum(axis=1) >= margins.shape[1] // 2 + 1
        ).astype(int)
