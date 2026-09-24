"""Stable, serializable landing-gear model bundles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


def _transform(frame: pd.DataFrame, feature_columns: tuple[str, ...], preprocessor: Any, model: Any):
    missing = set(feature_columns).difference(frame.columns)
    if missing:
        raise ValueError(f"Missing landing-gear features: {sorted(missing)}")
    transformed = preprocessor.transform(frame.loc[:, feature_columns])
    names = getattr(model, "feature_names_in_", None)
    if names is not None:
        transformed = pd.DataFrame(transformed, columns=names, index=frame.index)
    return transformed


@dataclass
class LandingGearFaultBundle:
    """Preprocessor and multiclass model for one-event fault diagnosis."""

    feature_columns: tuple[str, ...]
    preprocessor: Any
    model: Any
    model_name: str
    feature_set: str
    class_names: dict[int, str]
    validation_metrics: dict[str, float]

    def predict_feature_frame(self, frame: pd.DataFrame) -> np.ndarray:
        values = _transform(frame, self.feature_columns, self.preprocessor, self.model)
        return self.model.predict(values).astype(int)


@dataclass
class LandingGearRULBundle:
    """Preprocessor and regressor for landing-gear RUL percentage."""

    feature_columns: tuple[str, ...]
    preprocessor: Any
    model: Any
    model_name: str
    feature_set: str
    validation_metrics: dict[str, float]

    def predict_feature_frame(self, frame: pd.DataFrame) -> np.ndarray:
        values = _transform(frame, self.feature_columns, self.preprocessor, self.model)
        return np.clip(self.model.predict(values), 0.0, 100.0)
