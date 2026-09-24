"""Serializable uncertainty, input-support, and abstention model wrappers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class FeatureSupport:
    """Training-data support limits used to flag unfamiliar inputs."""

    feature_columns: tuple[str, ...]
    hard_minimum: np.ndarray
    hard_maximum: np.ndarray
    lower_quantile: np.ndarray
    upper_quantile: np.ndarray

    @classmethod
    def fit(cls, frame: pd.DataFrame, feature_columns: tuple[str, ...]) -> "FeatureSupport":
        values = frame.loc[:, feature_columns].to_numpy(dtype=float)
        if values.size == 0 or not np.isfinite(values).all():
            raise ValueError("Feature-support data must be non-empty and finite")
        return cls(
            feature_columns=feature_columns,
            hard_minimum=values.min(axis=0),
            hard_maximum=values.max(axis=0),
            lower_quantile=np.quantile(values, 0.01, axis=0),
            upper_quantile=np.quantile(values, 0.99, axis=0),
        )

    def assess(self, frame: pd.DataFrame) -> dict[str, object]:
        missing = set(self.feature_columns).difference(frame.columns)
        if missing:
            raise ValueError(f"Missing readiness features: {sorted(missing)}")
        values = frame.loc[:, self.feature_columns].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("Readiness features must be finite")
        hard = (values < self.hard_minimum) | (values > self.hard_maximum)
        tail = (values < self.lower_quantile) | (values > self.upper_quantile)
        hard_names = sorted({
            self.feature_columns[index]
            for index in np.flatnonzero(hard.any(axis=0))
        })
        tail_names = sorted({
            self.feature_columns[index]
            for index in np.flatnonzero(tail.any(axis=0))
        })
        return {
            "within_hard_training_range": not bool(hard.any()),
            "hard_range_violations": hard_names,
            "tail_range_warnings": tail_names,
            "abstain": bool(hard.any()),
        }


def _transformed(
    frame: pd.DataFrame,
    feature_columns: tuple[str, ...],
    preprocessor: Any,
    model: Any,
) -> Any:
    missing = set(feature_columns).difference(frame.columns)
    if missing:
        raise ValueError(f"Missing model features: {sorted(missing)}")
    values = preprocessor.transform(frame.loc[:, feature_columns])
    names = getattr(model, "feature_names_in_", None)
    if names is not None:
        values = pd.DataFrame(values, columns=names, index=frame.index)
    return values


@dataclass
class ReadinessRegressionBundle:
    """Regression model with empirical uncertainty and input support checks."""

    component: str
    target_name: str
    target_unit: str
    feature_columns: tuple[str, ...]
    preprocessor: Any
    model: Any
    model_name: str
    validation_metrics: dict[str, float]
    interval_alpha: float
    absolute_error_quantile: float
    feature_support: FeatureSupport
    target_minimum: float = 0.0
    target_maximum: float | None = None
    validation_protocol: str = ""

    def predict_feature_frame(self, frame: pd.DataFrame) -> np.ndarray:
        values = _transformed(frame, self.feature_columns, self.preprocessor, self.model)
        predicted = np.asarray(self.model.predict(values), dtype=float)
        return np.clip(predicted, self.target_minimum, self.target_maximum)

    def predict_interval(
        self, frame: pd.DataFrame
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        predicted = self.predict_feature_frame(frame)
        # Engine's 125-cycle training cap is not a physical bound on true RUL.
        interval_maximum = None if self.component == "engine" else self.target_maximum
        lower = np.clip(
            predicted - self.absolute_error_quantile,
            self.target_minimum,
            interval_maximum,
        )
        upper = np.clip(
            predicted + self.absolute_error_quantile,
            self.target_minimum,
            interval_maximum,
        )
        return predicted, lower, upper

    def assess_input(self, frame: pd.DataFrame) -> dict[str, object]:
        return self.feature_support.assess(frame)


@dataclass
class ReadinessClassificationBundle:
    """Classifier with empirical confidence calibration and abstention."""

    component: str
    target_name: str
    feature_columns: tuple[str, ...]
    preprocessor: Any
    model: Any
    model_name: str
    class_names: dict[int, str]
    confidence_calibrator: Any
    confidence_threshold: float
    validation_metrics: dict[str, float]
    feature_support: FeatureSupport
    validation_protocol: str = ""

    def predict_with_readiness(
        self, frame: pd.DataFrame
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        values = _transformed(frame, self.feature_columns, self.preprocessor, self.model)
        probabilities = np.asarray(self.model.predict_proba(values), dtype=float)
        positions = probabilities.argmax(axis=1)
        predicted = np.asarray(self.model.classes_)[positions].astype(int)
        raw_confidence = probabilities[np.arange(len(probabilities)), positions]
        confidence = np.asarray(
            self.confidence_calibrator.predict(raw_confidence), dtype=float
        )
        # One unfamiliar row must not cause rejection of an entire batch.
        self.feature_support.assess(frame)
        raw = frame.loc[:, self.feature_support.feature_columns].to_numpy(float)
        supported = ((raw >= self.feature_support.hard_minimum) &
                     (raw <= self.feature_support.hard_maximum)).all(axis=1)
        accepted = (confidence >= self.confidence_threshold) & supported
        return predicted, confidence, accepted

    def predict_feature_frame(self, frame: pd.DataFrame) -> np.ndarray:
        return self.predict_with_readiness(frame)[0]

    def assess_input(self, frame: pd.DataFrame) -> dict[str, object]:
        return self.feature_support.assess(frame)
