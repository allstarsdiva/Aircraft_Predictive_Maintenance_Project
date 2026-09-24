"""Leakage-resistant features and robustness helpers for readiness retraining."""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
    VotingRegressor,
)
from sklearn.feature_selection import VarianceThreshold
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.eda_fuel import FUEL_NON_FEATURE_COLUMNS
from src.eda_hydraulic import HYDRAULIC_NON_FEATURE_COLUMNS


COOLER_PROXY_PREFIXES = ("ce_", "cp_", "se_")


def cooler_proxy_free_features(table: pd.DataFrame) -> tuple[str, ...]:
    """Return measured-sensor features without virtual cooler proxy channels."""

    features = tuple(
        column
        for column in table.columns
        if column not in HYDRAULIC_NON_FEATURE_COLUMNS
        and not column.lower().startswith(COOLER_PROXY_PREFIXES)
    )
    if not features:
        raise ValueError("No proxy-free hydraulic features are available")
    return features


def perturb_validation_features(
    validation: pd.DataFrame,
    reference_train: pd.DataFrame,
    features: tuple[str, ...],
    *,
    noise_fraction: float = 0.05,
    dropout_fraction: float = 0.03,
    random_state: int = 42,
) -> pd.DataFrame:
    """Apply deterministic feature noise and median replacement to a test fold.

    Noise magnitude is a fraction of the training-fold standard deviation. A
    dropout is represented by a training-median replacement, matching the
    conservative imputation available to an online inference service.
    """

    if noise_fraction < 0 or not 0 <= dropout_fraction < 1:
        raise ValueError("Invalid robustness perturbation parameters")
    result = validation.copy()
    result = result.astype({feature: 'float64' for feature in features})
    train_values = reference_train.loc[:, features].to_numpy(dtype=float)
    values = result.loc[:, features].to_numpy(dtype=float)
    if not np.isfinite(train_values).all() or not np.isfinite(values).all():
        raise ValueError("Robustness inputs must be finite")
    scale = np.std(train_values, axis=0, ddof=0)
    medians = np.median(train_values, axis=0)
    rng = np.random.default_rng(random_state)
    values = values + rng.normal(0.0, noise_fraction * scale, size=values.shape)
    dropped = rng.random(values.shape) < dropout_fraction
    values[dropped] = np.broadcast_to(medians, values.shape)[dropped]
    result.loc[:, features] = values
    return result


def engine_regressor_candidates(random_state: int = 42) -> dict[str, Any]:
    """Return diverse, regularized engine candidates for grouped selection."""

    forest = RandomForestRegressor(
        n_estimators=400,
        max_depth=20,
        min_samples_leaf=2,
        max_features="sqrt",
        n_jobs=-1,
        random_state=random_state,
    )
    extra = ExtraTreesRegressor(
        n_estimators=300,
        max_depth=24,
        min_samples_leaf=2,
        max_features=0.7,
        n_jobs=-1,
        random_state=random_state,
    )
    histogram = HistGradientBoostingRegressor(
        learning_rate=0.05,
        max_iter=300,
        max_leaf_nodes=31,
        min_samples_leaf=20,
        l2_regularization=1.0,
        random_state=random_state,
    )
    return {
        "random_forest": forest,
        "extra_trees": extra,
        "hist_gradient_boosting": histogram,
        "forest_soft_voting": VotingRegressor(
            [("rf", clone(forest)), ("extra", clone(extra))], n_jobs=-1
        ),
    }


def cooler_classifier_candidates(random_state: int = 42) -> dict[str, Any]:
    return {
        "logistic_regression": LogisticRegression(
            max_iter=4000, class_weight="balanced", random_state=random_state
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=400,
            min_samples_leaf=3,
            max_features="sqrt",
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=random_state,
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=400,
            min_samples_leaf=3,
            max_features="sqrt",
            class_weight="balanced",
            n_jobs=-1,
            random_state=random_state,
        ),
    }


def add_fuel_phase_features(table: pd.DataFrame, phase_bins: int = 6) -> pd.DataFrame:
    """Add causal mission-progress context shared by aligned fuel trajectories."""

    if phase_bins < 2 or "sample_index" not in table:
        raise ValueError("Fuel phase features require sample_index and >=2 bins")
    result = table.copy()
    maximum = result.groupby("scenario_id")["sample_index"].transform("max")
    denominator = np.maximum(maximum.to_numpy(dtype=float) - 1.0, 1.0)
    phase = (result["sample_index"].to_numpy(dtype=float) - 1.0) / denominator
    result["phase_fraction"] = phase
    result["phase_sin"] = np.sin(2 * np.pi * phase)
    result["phase_cos"] = np.cos(2 * np.pi * phase)
    result["phase_bin"] = np.minimum((phase * phase_bins).astype(int), phase_bins - 1)
    return result


def fuel_feature_columns(table: pd.DataFrame) -> tuple[str, ...]:
    return tuple(
        column for column in table.columns if column not in FUEL_NON_FEATURE_COLUMNS
    )


def fuel_challenger_candidates(random_state: int = 42) -> dict[str, Any]:
    return {
        "logistic_regression": LogisticRegression(
            max_iter=4000, class_weight="balanced", random_state=random_state
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=500,
            min_samples_leaf=3,
            max_features="sqrt",
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=random_state,
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=500,
            min_samples_leaf=3,
            max_features="sqrt",
            class_weight="balanced",
            n_jobs=-1,
            random_state=random_state,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_iter=300,
            max_leaf_nodes=31,
            min_samples_leaf=12,
            l2_regularization=1.0,
            class_weight="balanced",
            random_state=random_state,
        ),
    }


def _preprocessor() -> Pipeline:
    return Pipeline(
        [("variance", VarianceThreshold(threshold=0.0)), ("scaler", StandardScaler())]
    )


def unseen_fuel_scenario_oof(
    table: pd.DataFrame,
    model: Any,
    features: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Evaluate faults only when their complete scenario is absent from training.

    Each normal sample is also held out exactly once in a contiguous block. This
    avoids random-row leakage across the single available normal trajectory.
    """

    scenarios = tuple(sorted(set(table["scenario_id"]) - {"normal"}))
    normal = table.loc[table["scenario_id"] == "normal"].sort_values("sample_index")
    normal_blocks = np.array_split(normal.index.to_numpy(), len(scenarios))
    evaluation_indices: list[np.ndarray] = []
    predictions: list[np.ndarray] = []
    confidence: list[np.ndarray] = []
    for fold_number, (scenario, normal_test) in enumerate(zip(scenarios, normal_blocks)):
        abnormal_test = table.index[table["scenario_id"] == scenario].to_numpy()
        test_indices = np.concatenate([normal_test, abnormal_test])
        train_mask = ~table.index.isin(test_indices)
        train = table.loc[train_mask]
        validation = table.loc[test_indices]
        preprocessor = _preprocessor()
        train_values = preprocessor.fit_transform(train.loc[:, features])
        validation_values = preprocessor.transform(validation.loc[:, features])
        names = np.asarray(features)[
            preprocessor.named_steps["variance"].get_support()
        ]
        fitted = clone(model).fit(
            pd.DataFrame(train_values, columns=names), train["is_abnormal"]
        )
        probabilities = fitted.predict_proba(
            pd.DataFrame(validation_values, columns=names)
        )
        positions = probabilities.argmax(axis=1)
        evaluation_indices.append(test_indices)
        predictions.append(fitted.classes_[positions].astype(int))
        confidence.append(probabilities[np.arange(len(positions)), positions])
    indices = np.concatenate(evaluation_indices)
    if len(indices) != len(table) or len(np.unique(indices)) != len(table):
        raise RuntimeError("Fuel scenario holdouts must cover every row exactly once")
    order = np.argsort(indices)
    return (
        np.concatenate(predictions)[order],
        np.concatenate(confidence)[order],
        indices[order],
    )


def fuel_detection_metrics(
    table: pd.DataFrame, predicted: Iterable[int]
) -> dict[str, Any]:
    actual = table["is_abnormal"].to_numpy(dtype=int)
    values = np.asarray(predicted, dtype=int)
    normal = actual == 0
    abnormal = actual == 1
    return {
        "accuracy": float(accuracy_score(actual, values)),
        "balanced_accuracy": float(balanced_accuracy_score(actual, values)),
        "macro_f1": float(f1_score(actual, values, average="macro")),
        "normal_false_alarm_rate": float(values[normal].mean()),
        "abnormal_detection_rate": float(values[abnormal].mean()),
        "scenario_detection_rates": {
            scenario: float(values[table["scenario_id"].to_numpy() == scenario].mean())
            for scenario in sorted(set(table["scenario_id"]) - {"normal"})
        },
    }
