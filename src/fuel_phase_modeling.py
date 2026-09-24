"""Phase-aligned residual detection for the fuel-system trajectories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


def causal_persistence(
    predicted: Iterable[int], window: int = 5, required: int = 3
) -> np.ndarray:
    """Require repeated anomaly votes in a trailing window before alerting."""

    values = np.asarray(tuple(predicted), dtype=int)
    if window < 1 or required < 1 or required > window:
        raise ValueError("Persistence requires 1 <= required <= window")
    if values.size == 0 or not np.isin(values, [0, 1]).all():
        raise ValueError("Persistence predictions must be non-empty and binary")
    cumulative = np.concatenate([[0], np.cumsum(values)])
    starts = np.maximum(np.arange(values.size) + 1 - window, 0)
    counts = cumulative[np.arange(1, values.size + 1)] - cumulative[starts]
    return (counts >= required).astype(int)


@dataclass
class FuelPhaseResidualDetector:
    """Normal-template detector conditioned on mission sample position."""

    feature_columns: tuple[str, ...]
    sample_positions: np.ndarray
    template_values: np.ndarray
    feature_scales: np.ndarray
    aggregation: str = "top2_mean"

    @classmethod
    def fit(
        cls,
        normal: pd.DataFrame,
        feature_columns: tuple[str, ...],
        aggregation: str = "top2_mean",
    ) -> "FuelPhaseResidualDetector":
        required = {"sample_index", *feature_columns}
        missing = required.difference(normal.columns)
        if missing:
            raise ValueError(f"Missing fuel template columns: {sorted(missing)}")
        ordered = normal.sort_values("sample_index")
        positions = ordered["sample_index"].to_numpy(dtype=float)
        values = ordered.loc[:, feature_columns].to_numpy(dtype=float)
        if len(positions) < 2 or len(np.unique(positions)) != len(positions):
            raise ValueError("Fuel template needs unique ordered sample positions")
        if not np.isfinite(values).all():
            raise ValueError("Fuel template features must be finite")
        scales = np.std(values, axis=0, ddof=0)
        nonzero = scales[scales > 1e-9]
        fallback = float(np.median(nonzero)) if nonzero.size else 1.0
        scales = np.where(scales > 1e-9, scales, fallback)
        return cls(feature_columns, positions, values, scales, aggregation)

    def expected_values(self, frame: pd.DataFrame) -> np.ndarray:
        if "sample_index" not in frame:
            raise ValueError("Fuel phase detector requires sample_index")
        query = frame["sample_index"].to_numpy(dtype=float)
        expected = np.column_stack(
            [
                np.interp(
                    query,
                    self.sample_positions,
                    self.template_values[:, column],
                )
                for column in range(len(self.feature_columns))
            ]
        )
        return expected

    def anomaly_score(self, frame: pd.DataFrame) -> np.ndarray:
        missing = set(self.feature_columns).difference(frame.columns)
        if missing:
            raise ValueError(f"Missing fuel residual features: {sorted(missing)}")
        observed = frame.loc[:, self.feature_columns].to_numpy(dtype=float)
        residuals = np.abs(observed - self.expected_values(frame)) / self.feature_scales
        if self.aggregation == "mean":
            return residuals.mean(axis=1)
        if self.aggregation == "p75":
            return np.quantile(residuals, 0.75, axis=1)
        if self.aggregation == "max":
            return residuals.max(axis=1)
        if self.aggregation == "top2_mean":
            count = min(2, residuals.shape[1])
            return np.partition(residuals, -count, axis=1)[:, -count:].mean(axis=1)
        raise ValueError(f"Unknown fuel residual aggregation: {self.aggregation}")


@dataclass
class FuelPhaseResidualBundle:
    """Serializable full-template detector with calibrated alert persistence."""

    detector: FuelPhaseResidualDetector
    threshold: float
    persistence_window: int
    persistence_required: int
    expected_false_alarm_rate: float
    validation_metrics: dict[str, float]
    validation_protocol: str

    @property
    def detector_name(self) -> str:
        return "phase_aligned_residual_detector"

    def predict_anomaly_score(self, frame: pd.DataFrame) -> np.ndarray:
        """Return anomaly margin; positive values exceed the alert threshold."""

        return self.detector.anomaly_score(frame) - self.threshold

    def predict_feature_frame(self, frame: pd.DataFrame) -> np.ndarray:
        raw = (self.predict_anomaly_score(frame) > 0).astype(int)
        return causal_persistence(
            raw, self.persistence_window, self.persistence_required
        )
