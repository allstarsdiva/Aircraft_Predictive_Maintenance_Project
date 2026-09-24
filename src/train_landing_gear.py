"""Stratified landing-gear fault-classification and RUL baselines."""

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
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.feature_selection import VarianceThreshold
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

_cache = Path(tempfile.gettempdir()) / "aircraft-matplotlib-cache"
_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_cache))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.data.landing_gear import LANDING_GEAR_FAULT_NAMES
from src.eda_landing_gear import (
    LANDING_GEAR_OBSERVABLE_FEATURES,
    LANDING_GEAR_PHYSICS_FEATURES,
)
from src.landing_gear_modeling import LandingGearFaultBundle, LandingGearRULBundle


def landing_gear_folds(
    table: pd.DataFrame, n_splits: int = 5, random_state: int = 42
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Create deterministic folds stratified by fault class."""

    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    folds = list(splitter.split(table, table["fault_code"]))
    validation_rows = np.concatenate([validation for _, validation in folds])
    if sorted(validation_rows.tolist()) != list(range(len(table))):
        raise RuntimeError("Landing-gear folds do not cover every event exactly once")
    for train, validation in folds:
        if set(train) & set(validation):
            raise RuntimeError("Landing-gear row leakage detected")
    return folds


def build_landing_gear_preprocessor() -> Pipeline:
    return Pipeline([
        ("variance", VarianceThreshold(threshold=0.0)),
        ("scaler", StandardScaler()),
    ])


def _classifiers(random_state: int) -> dict[str, Any]:
    return {
        "most_frequent": DummyClassifier(strategy="most_frequent"),
        "logistic_regression": LogisticRegression(
            max_iter=3000, class_weight="balanced", random_state=random_state
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=400, min_samples_leaf=2, max_features="sqrt",
            class_weight="balanced_subsample", n_jobs=-1, random_state=random_state,
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=400, min_samples_leaf=2, max_features="sqrt",
            class_weight="balanced", n_jobs=-1, random_state=random_state,
        ),
    }


def _regressors(random_state: int) -> dict[str, Any]:
    return {
        "median_dummy": DummyRegressor(strategy="median"),
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(
            n_estimators=400, min_samples_leaf=2, max_features="sqrt",
            n_jobs=-1, random_state=random_state,
        ),
        "extra_trees": ExtraTreesRegressor(
            n_estimators=400, min_samples_leaf=2, max_features="sqrt",
            n_jobs=-1, random_state=random_state,
        ),
    }


def _prepared_fold(
    table: pd.DataFrame,
    train: np.ndarray,
    validation: np.ndarray,
    features: tuple[str, ...],
) -> tuple[Pipeline, pd.DataFrame, pd.DataFrame]:
    preprocessor = build_landing_gear_preprocessor()
    train_values = preprocessor.fit_transform(table.iloc[train].loc[:, features])
    validation_values = preprocessor.transform(table.iloc[validation].loc[:, features])
    retained = np.asarray(features)[
        preprocessor.named_steps["variance"].get_support()
    ]
    return (
        preprocessor,
        pd.DataFrame(train_values, columns=retained),
        pd.DataFrame(validation_values, columns=retained),
    )


def _classification_metrics(actual: pd.Series, predicted: np.ndarray) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(actual, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(actual, predicted)),
        "macro_f1": float(f1_score(actual, predicted, average="macro")),
    }


def _regression_metrics(actual: pd.Series, predicted: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
        "r2": float(r2_score(actual, predicted)),
    }


def _oof_classification(
    table: pd.DataFrame, features: tuple[str, ...], model: Any,
    folds: list[tuple[np.ndarray, np.ndarray]],
) -> np.ndarray:
    predicted = np.full(len(table), -1, dtype=int)
    for train, validation in folds:
        _, X_train, X_validation = _prepared_fold(table, train, validation, features)
        fitted = clone(model).fit(X_train, table.iloc[train]["fault_code"])
        predicted[validation] = fitted.predict(X_validation).astype(int)
    if (predicted < 0).any():
        raise RuntimeError("Fault validation did not predict every event")
    return predicted


def _oof_regression(
    table: pd.DataFrame, features: tuple[str, ...], model: Any,
    folds: list[tuple[np.ndarray, np.ndarray]],
) -> np.ndarray:
    predicted = np.full(len(table), np.nan, dtype=float)
    for train, validation in folds:
        _, X_train, X_validation = _prepared_fold(table, train, validation, features)
        fitted = clone(model).fit(X_train, table.iloc[train]["rul_percent"])
        predicted[validation] = np.clip(fitted.predict(X_validation), 0.0, 100.0)
    if not np.isfinite(predicted).all():
        raise RuntimeError("RUL validation did not predict every event")
    return predicted


def _fit_final(
    table: pd.DataFrame, features: tuple[str, ...], model: Any, target: str
) -> tuple[Pipeline, Any]:
    preprocessor = build_landing_gear_preprocessor()
    values = preprocessor.fit_transform(table.loc[:, features])
    retained = np.asarray(features)[preprocessor.named_steps["variance"].get_support()]
    fitted = clone(model).fit(pd.DataFrame(values, columns=retained), table[target])
    return preprocessor, fitted


def train_landing_gear_baselines(
    project_root: Path,
    feature_table: pd.DataFrame | None = None,
    random_state: int = 42,
) -> dict[str, object]:
    """Compare observable and physics-assisted classifiers/regressors."""

    table = feature_table.copy() if feature_table is not None else pd.read_csv(
        project_root / "data" / "processed" / "landing_gear" / "validated_runs.csv"
    )
    feature_sets = {
        "observable": LANDING_GEAR_OBSERVABLE_FEATURES,
        "physics_assisted": LANDING_GEAR_PHYSICS_FEATURES,
    }
    folds = landing_gear_folds(table, random_state=random_state)
    classification_results: dict[str, dict[str, dict[str, float]]] = {}
    regression_results: dict[str, dict[str, dict[str, float]]] = {}
    class_predictions: dict[tuple[str, str], np.ndarray] = {}
    rul_predictions: dict[tuple[str, str], np.ndarray] = {}

    for feature_set, features in feature_sets.items():
        classification_results[feature_set] = {}
        for name, model in _classifiers(random_state).items():
            predicted = _oof_classification(table, features, model, folds)
            class_predictions[(feature_set, name)] = predicted
            classification_results[feature_set][name] = _classification_metrics(
                table["fault_code"], predicted
            )
        regression_results[feature_set] = {}
        for name, model in _regressors(random_state).items():
            predicted = _oof_regression(table, features, model, folds)
            rul_predictions[(feature_set, name)] = predicted
            regression_results[feature_set][name] = _regression_metrics(
                table["rul_percent"], predicted
            )

    class_choice = max(
        class_predictions,
        key=lambda key: (
            classification_results[key[0]][key[1]]["macro_f1"],
            classification_results[key[0]][key[1]]["balanced_accuracy"],
        ),
    )
    rul_choice = min(
        rul_predictions,
        key=lambda key: (
            regression_results[key[0]][key[1]]["rmse"],
            regression_results[key[0]][key[1]]["mae"],
        ),
    )
    class_feature_set, class_model_name = class_choice
    rul_feature_set, rul_model_name = rul_choice
    class_features = feature_sets[class_feature_set]
    rul_features = feature_sets[rul_feature_set]

    class_preprocessor, class_model = _fit_final(
        table, class_features, _classifiers(random_state)[class_model_name], "fault_code"
    )
    rul_preprocessor, rul_model = _fit_final(
        table, rul_features, _regressors(random_state)[rul_model_name], "rul_percent"
    )
    class_bundle = LandingGearFaultBundle(
        feature_columns=class_features,
        preprocessor=class_preprocessor,
        model=class_model,
        model_name=class_model_name,
        feature_set=class_feature_set,
        class_names=LANDING_GEAR_FAULT_NAMES,
        validation_metrics=classification_results[class_feature_set][class_model_name],
    )
    rul_bundle = LandingGearRULBundle(
        feature_columns=rul_features,
        preprocessor=rul_preprocessor,
        model=rul_model,
        model_name=rul_model_name,
        feature_set=rul_feature_set,
        validation_metrics=regression_results[rul_feature_set][rul_model_name],
    )

    model_dir = project_root / "models" / "landing_gear"
    metrics_dir = project_root / "reports" / "metrics"
    figure_dir = project_root / "reports" / "figures" / "landing_gear"
    for directory in (model_dir, metrics_dir, figure_dir):
        directory.mkdir(parents=True, exist_ok=True)
    fault_model_path = model_dir / "fault_classifier_bundle.joblib"
    rul_model_path = model_dir / "rul_regressor_bundle.joblib"
    joblib.dump(class_bundle, fault_model_path, compress=3)
    joblib.dump(rul_bundle, rul_model_path, compress=3)

    output_rows = table[["run_id", "fault_code", "fault_name", "rul_percent"]].copy()
    for key, predicted in class_predictions.items():
        output_rows[f"fault__{key[0]}__{key[1]}"] = predicted
    for key, predicted in rul_predictions.items():
        output_rows[f"rul__{key[0]}__{key[1]}"] = predicted
    output_rows.to_csv(metrics_dir / "landing_gear_oof_predictions.csv", index=False)

    selected_fault_predictions = class_predictions[class_choice]
    fig, ax = plt.subplots(figsize=(7, 6))
    ConfusionMatrixDisplay.from_predictions(
        table["fault_code"], selected_fault_predictions,
        labels=sorted(LANDING_GEAR_FAULT_NAMES), cmap="Blues", colorbar=False, ax=ax,
    )
    ax.set_title(
        f"Landing-Gear Faults: {class_model_name.replace('_', ' ').title()} "
        f"({class_feature_set.replace('_', ' ').title()})"
    )
    fig.tight_layout()
    fig.savefig(figure_dir / "landing_gear_fault_confusion_matrix.png", dpi=160)
    plt.close(fig)

    selected_rul_predictions = rul_predictions[rul_choice]
    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    ax.scatter(table["rul_percent"], selected_rul_predictions, s=14, alpha=0.45)
    ax.plot([0, 100], [0, 100], "--", color="#dc2626", label="Ideal")
    ax.set(
        title=f"Landing-Gear RUL: {rul_model_name.replace('_', ' ').title()}",
        xlabel="Actual RUL (%)", ylabel="Predicted RUL (%)", xlim=(0, 100), ylim=(0, 100),
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_dir / "landing_gear_rul_actual_vs_predicted.png", dpi=160)
    plt.close(fig)

    result = {
        "rows": len(table),
        "validation": "five_fold_stratified_by_fault_code_random_state_42",
        "run_id_used_as_feature": False,
        "classification": {
            "best_feature_set": class_feature_set,
            "best_model": class_model_name,
            "selection_metric": "macro_f1_then_balanced_accuracy",
            "best_metrics": classification_results[class_feature_set][class_model_name],
            "candidate_metrics": classification_results,
            "model_path": str(fault_model_path.relative_to(project_root)),
        },
        "rul_regression": {
            "best_feature_set": rul_feature_set,
            "best_model": rul_model_name,
            "selection_metric": "rmse_then_mae",
            "best_metrics": regression_results[rul_feature_set][rul_model_name],
            "candidate_metrics": regression_results,
            "model_path": str(rul_model_path.relative_to(project_root)),
        },
        "validation_statement": (
            "Random stratified out-of-fold evaluation of independent synthetic events. "
            "It does not establish performance on real aircraft or a different simulator."
        ),
    }
    (metrics_dir / "landing_gear_baselines.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(train_landing_gear_baselines(root), indent=2))


if __name__ == "__main__":
    main()
