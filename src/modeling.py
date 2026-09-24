"""Stable, serializable model artifact types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ModelMetrics:
    """Validation metrics and basic training diagnostics."""

    mae: float
    rmse: float
    r2: float
    training_seconds: float


@dataclass
class EngineModelBundle:
    """Serializable preprocessing and regression components."""

    subset: str
    capped_rul: int
    feature_columns: tuple[str, ...]
    preprocessor: Any
    model: Any
    model_name: str
    validation_metrics: ModelMetrics
    prediction_offset: float = 0.0

    def predict_feature_frame(self, frame: pd.DataFrame) -> np.ndarray:
        """Predict RUL from an already causally engineered feature frame."""

        missing = set(self.feature_columns).difference(frame.columns)
        if missing:
            raise ValueError(f"Missing model features: {sorted(missing)}")
        transformed = self.preprocessor.transform(frame.loc[:, self.feature_columns])
        model_feature_names = getattr(self.model, "feature_names_in_", None)
        if model_feature_names is not None:
            transformed = pd.DataFrame(
                transformed, columns=model_feature_names, index=frame.index
            )
        predictions = self.model.predict(transformed) - self.prediction_offset
        return np.clip(predictions, 0, self.capped_rul)


@dataclass
class BatterySOHModelBundle:
    """Serializable battery SOH preprocessing and regression components."""

    feature_columns: tuple[str, ...]
    preprocessor: Any
    model: Any
    model_name: str
    validation_metrics: ModelMetrics

    def predict_feature_frame(self, frame: pd.DataFrame) -> np.ndarray:
        missing = set(self.feature_columns).difference(frame.columns)
        if missing:
            raise ValueError(f"Missing battery SOH features: {sorted(missing)}")
        transformed = self.preprocessor.transform(frame.loc[:, self.feature_columns])
        model_feature_names = getattr(self.model, "feature_names_in_", None)
        if model_feature_names is not None:
            transformed = pd.DataFrame(
                transformed, columns=model_feature_names, index=frame.index
            )
        return np.clip(self.model.predict(transformed), 0, 150)


@dataclass
class BatteryRULModelBundle:
    """Experimental battery RUL model with an empirical prediction interval."""

    feature_columns: tuple[str, ...]
    preprocessor: Any
    model: Any
    model_name: str
    validation_metrics: ModelMetrics
    interval_alpha: float
    absolute_error_quantile: float

    def predict_feature_frame(self, frame: pd.DataFrame) -> np.ndarray:
        """Predict non-negative remaining discharge cycles."""

        missing = set(self.feature_columns).difference(frame.columns)
        if missing:
            raise ValueError(f"Missing battery RUL features: {sorted(missing)}")
        transformed = self.preprocessor.transform(frame.loc[:, self.feature_columns])
        model_feature_names = getattr(self.model, "feature_names_in_", None)
        if model_feature_names is not None:
            transformed = pd.DataFrame(
                transformed, columns=model_feature_names, index=frame.index
            )
        return np.clip(self.model.predict(transformed), 0, None)

    def predict_interval(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return point, lower, and upper experimental RUL predictions."""

        predicted = self.predict_feature_frame(frame)
        lower = np.clip(predicted - self.absolute_error_quantile, 0, None)
        upper = predicted + self.absolute_error_quantile
        return predicted, lower, upper


@dataclass
class HydraulicClassificationBundle:
    """Serializable preprocessing and classifier for one hydraulic target."""

    target_column: str
    feature_columns: tuple[str, ...]
    class_labels: tuple[int, ...]
    preprocessor: Any
    model: Any
    model_name: str
    validation_metrics: dict[str, float]
    stable_flag_training_value: int = 0

    def predict_feature_frame(self, frame: pd.DataFrame) -> np.ndarray:
        missing = set(self.feature_columns).difference(frame.columns)
        if missing:
            raise ValueError(f"Missing hydraulic features: {sorted(missing)}")
        transformed = self.preprocessor.transform(frame.loc[:, self.feature_columns])
        model_feature_names = getattr(self.model, "feature_names_in_", None)
        if model_feature_names is not None:
            transformed = pd.DataFrame(
                transformed, columns=model_feature_names, index=frame.index
            )
        return self.model.predict(transformed)
