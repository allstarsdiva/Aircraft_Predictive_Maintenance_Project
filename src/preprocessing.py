"""Leakage-safe preprocessing for the C-MAPSS engine RUL pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_selection import VarianceThreshold
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.data.cmapss import load_training_with_rul

DEFAULT_TREND_SENSORS = (
    "sensor_11",
    "sensor_4",
    "sensor_12",
    "sensor_7",
    "sensor_15",
)
DEFAULT_ROLLING_WINDOWS = (5, 10)
NON_FEATURE_COLUMNS = frozenset({"unit_id", "rul"})


@dataclass(frozen=True)
class EngineDataSplit:
    """Raw grouped partitions and their targets."""

    train: pd.DataFrame
    validation: pd.DataFrame
    feature_columns: tuple[str, ...]

    @property
    def X_train(self) -> pd.DataFrame:
        return self.train.loc[:, self.feature_columns]

    @property
    def y_train(self) -> pd.Series:
        return self.train["rul"]

    @property
    def X_validation(self) -> pd.DataFrame:
        return self.validation.loc[:, self.feature_columns]

    @property
    def y_validation(self) -> pd.Series:
        return self.validation["rul"]

    @property
    def train_units(self) -> frozenset[int]:
        return frozenset(self.train["unit_id"].unique().tolist())

    @property
    def validation_units(self) -> frozenset[int]:
        return frozenset(self.validation["unit_id"].unique().tolist())


@dataclass(frozen=True)
class PreparedEngineData:
    """Transformed features plus the fitted preprocessing pipeline."""

    X_train: pd.DataFrame
    y_train: pd.Series
    X_validation: pd.DataFrame
    y_validation: pd.Series
    train_units: frozenset[int]
    validation_units: frozenset[int]
    pipeline: Pipeline


def add_causal_engine_features(
    frame: pd.DataFrame,
    sensors: Iterable[str] = DEFAULT_TREND_SENSORS,
    windows: Iterable[int] = DEFAULT_ROLLING_WINDOWS,
) -> pd.DataFrame:
    """Add changes and past-looking rolling features within each engine.

    Every rolling value at cycle t uses only observations at cycles <= t. The
    function therefore remains suitable for online prediction and avoids
    future-cycle leakage.
    """

    required = {"unit_id", "cycle"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    chosen_sensors = tuple(sensors)
    chosen_windows = tuple(windows)
    missing_sensors = set(chosen_sensors).difference(frame.columns)
    if missing_sensors:
        raise ValueError(f"Unknown sensor columns: {sorted(missing_sensors)}")
    if any(window < 2 for window in chosen_windows):
        raise ValueError("Rolling windows must be at least 2 cycles.")

    result = frame.sort_values(["unit_id", "cycle"]).copy()
    grouped = result.groupby("unit_id", sort=False)

    for sensor in chosen_sensors:
        result[f"{sensor}_delta"] = grouped[sensor].diff().fillna(0.0)
        for window in chosen_windows:
            rolling = grouped[sensor].rolling(window=window, min_periods=1)
            result[f"{sensor}_rolling_mean_{window}"] = (
                rolling.mean().reset_index(level=0, drop=True)
            )
            result[f"{sensor}_rolling_std_{window}"] = (
                rolling.std(ddof=0).reset_index(level=0, drop=True).fillna(0.0)
            )

    if result.isna().any().any():
        raise ValueError("Feature engineering produced missing values.")
    return result


def split_engine_units(
    frame: pd.DataFrame,
    validation_size: float = 0.2,
    random_state: int = 42,
) -> EngineDataSplit:
    """Split whole engine trajectories into train and validation partitions."""

    if not 0 < validation_size < 1:
        raise ValueError("validation_size must be between 0 and 1.")
    if not {"unit_id", "rul"}.issubset(frame.columns):
        raise ValueError("frame must contain unit_id and rul columns.")

    splitter = GroupShuffleSplit(
        n_splits=1, test_size=validation_size, random_state=random_state
    )
    train_indices, validation_indices = next(
        splitter.split(frame, groups=frame["unit_id"])
    )
    train = frame.iloc[train_indices].copy()
    validation = frame.iloc[validation_indices].copy()
    feature_columns = tuple(
        column for column in frame.columns if column not in NON_FEATURE_COLUMNS
    )
    split = EngineDataSplit(train, validation, feature_columns)

    overlap = split.train_units.intersection(split.validation_units)
    if overlap:
        raise RuntimeError(f"Engine leakage detected for units: {sorted(overlap)}")
    return split


def build_engine_preprocessor() -> Pipeline:
    """Remove training-constant features and standardize retained features."""

    return Pipeline(
        steps=[
            ("variance", VarianceThreshold(threshold=0.0)),
            ("scaler", StandardScaler()),
        ]
    )


def transformed_feature_names(
    pipeline: Pipeline, input_features: Iterable[str]
) -> tuple[str, ...]:
    """Return names retained by the fitted variance filter."""

    selector = pipeline.named_steps["variance"]
    names = np.asarray(tuple(input_features), dtype=object)
    return tuple(names[selector.get_support()].tolist())


def prepare_engine_training_data(
    subset: str = "FD001",
    validation_size: float = 0.2,
    random_state: int = 42,
    capped_rul: int | None = 125,
) -> PreparedEngineData:
    """Load, label, engineer, group-split, filter, and scale engine data."""

    frame = load_training_with_rul(subset)
    if capped_rul is not None:
        if capped_rul < 1:
            raise ValueError("capped_rul must be positive or None.")
        frame["rul"] = frame["rul"].clip(upper=capped_rul)

    featured = add_causal_engine_features(frame)
    split = split_engine_units(featured, validation_size, random_state)
    pipeline = build_engine_preprocessor()

    train_values = pipeline.fit_transform(split.X_train)
    validation_values = pipeline.transform(split.X_validation)
    output_columns = transformed_feature_names(pipeline, split.feature_columns)

    X_train = pd.DataFrame(
        train_values, columns=output_columns, index=split.X_train.index
    )
    X_validation = pd.DataFrame(
        validation_values, columns=output_columns, index=split.X_validation.index
    )
    return PreparedEngineData(
        X_train=X_train,
        y_train=split.y_train.copy(),
        X_validation=X_validation,
        y_validation=split.y_validation.copy(),
        train_units=split.train_units,
        validation_units=split.validation_units,
        pipeline=pipeline,
    )


def save_engine_preprocessor(pipeline: Pipeline, path: str | Path) -> Path:
    """Persist a fitted pipeline for training and API inference."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, destination)
    return destination


def load_engine_preprocessor(path: str | Path) -> Pipeline:
    """Load a previously fitted engine preprocessing pipeline."""

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Preprocessor not found: {source}")
    return joblib.load(source)
