"""Cross-validation routines that include deterministic sensor perturbations."""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.feature_selection import VarianceThreshold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.model_improvements import perturb_validation_features


def robust_classification_oof(
    table: pd.DataFrame,
    features: tuple[str, ...],
    target: str,
    model: Any,
    folds: Iterable[tuple[np.ndarray, np.ndarray]],
    *,
    noise_fraction: float = 0.05,
    dropout_fraction: float = 0.03,
    random_state: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return clean predictions/confidence and perturbed-fold predictions."""

    clean = np.full(len(table), -1, dtype=int)
    noisy = np.full(len(table), -1, dtype=int)
    confidence = np.full(len(table), np.nan)
    for fold_number, (train_indices, validation_indices) in enumerate(folds):
        train = table.iloc[train_indices]
        validation = table.iloc[validation_indices]
        perturbed = perturb_validation_features(
            validation,
            train,
            features,
            noise_fraction=noise_fraction,
            dropout_fraction=dropout_fraction,
            random_state=random_state + fold_number,
        )
        preprocessor = Pipeline(
            [
                ("variance", VarianceThreshold(threshold=0.0)),
                ("scaler", StandardScaler()),
            ]
        )
        train_values = preprocessor.fit_transform(train.loc[:, features])
        validation_values = preprocessor.transform(validation.loc[:, features])
        noisy_values = preprocessor.transform(perturbed.loc[:, features])
        names = np.asarray(features)[
            preprocessor.named_steps["variance"].get_support()
        ]
        fitted = clone(model).fit(
            pd.DataFrame(train_values, columns=names), train[target]
        )
        clean_probabilities = fitted.predict_proba(
            pd.DataFrame(validation_values, columns=names)
        )
        positions = clean_probabilities.argmax(axis=1)
        clean[validation_indices] = fitted.classes_[positions].astype(int)
        confidence[validation_indices] = clean_probabilities[
            np.arange(len(positions)), positions
        ]
        noisy[validation_indices] = fitted.predict(
            pd.DataFrame(noisy_values, columns=names)
        ).astype(int)
    if (clean < 0).any() or (noisy < 0).any() or not np.isfinite(confidence).all():
        raise RuntimeError("Robust classification folds did not cover every row")
    return clean, confidence, noisy
