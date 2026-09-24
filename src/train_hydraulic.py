"""Leakage-aware baseline classification for UCI hydraulic conditions."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.feature_selection import VarianceThreshold
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    f1_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

_matplotlib_cache = Path(tempfile.gettempdir()) / "aircraft-matplotlib-cache"
_matplotlib_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_matplotlib_cache))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.data.hydraulic import PROFILE_COLUMNS
from src.eda_hydraulic import HYDRAULIC_NON_FEATURE_COLUMNS, HYDRAULIC_TARGETS
from src.modeling import HydraulicClassificationBundle


def hydraulic_condition_groups(table: pd.DataFrame) -> pd.Series:
    """Assign identical four-component condition combinations to one group."""

    return table.loc[:, HYDRAULIC_TARGETS].astype(str).agg("|".join, axis=1)


def build_hydraulic_preprocessor() -> Pipeline:
    return Pipeline(
        [
            ("variance", VarianceThreshold(threshold=0.0)),
            ("scaler", StandardScaler()),
        ]
    )


def _models(random_state: int) -> dict[str, Any]:
    return {
        "most_frequent": DummyClassifier(strategy="most_frequent"),
        "logistic_regression": LogisticRegression(
            max_iter=3000, class_weight="balanced", random_state=random_state
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=350,
            min_samples_leaf=2,
            max_features="sqrt",
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=random_state,
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=350,
            min_samples_leaf=2,
            max_features="sqrt",
            class_weight="balanced",
            n_jobs=-1,
            random_state=random_state,
        ),
    }


def grouped_hydraulic_folds(
    table: pd.DataFrame,
    target: str,
    n_splits: int = 5,
    random_state: int = 42,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Create stratified folds with whole condition combinations held out."""

    groups = hydraulic_condition_groups(table)
    splitter = StratifiedGroupKFold(
        n_splits=n_splits, shuffle=True, random_state=random_state
    )
    folds = list(splitter.split(table, table[target], groups=groups))
    for train_indices, validation_indices in folds:
        train_groups = set(groups.iloc[train_indices])
        validation_groups = set(groups.iloc[validation_indices])
        if train_groups & validation_groups:
            raise RuntimeError("Hydraulic condition-group leakage detected.")
    return folds


def _oof_predictions(
    table: pd.DataFrame,
    target: str,
    feature_columns: tuple[str, ...],
    model: Any,
    random_state: int,
) -> np.ndarray:
    predicted = np.full(len(table), -1, dtype=np.int64)
    for train_indices, validation_indices in grouped_hydraulic_folds(
        table, target, random_state=random_state
    ):
        preprocessor = build_hydraulic_preprocessor()
        train_values = preprocessor.fit_transform(
            table.iloc[train_indices].loc[:, feature_columns]
        )
        validation_values = preprocessor.transform(
            table.iloc[validation_indices].loc[:, feature_columns]
        )
        retained = np.asarray(feature_columns)[
            preprocessor.named_steps["variance"].get_support()
        ]
        fitted = clone(model)
        fitted.fit(
            pd.DataFrame(train_values, columns=retained),
            table.iloc[train_indices][target],
        )
        predicted[validation_indices] = fitted.predict(
            pd.DataFrame(validation_values, columns=retained)
        ).astype(np.int64)
    if (predicted < 0).any():
        raise RuntimeError("Hydraulic validation did not predict every stable cycle.")
    return predicted


def _classification_metrics(actual: pd.Series, predicted: np.ndarray) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(actual, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(actual, predicted)),
        "macro_f1": float(f1_score(actual, predicted, average="macro")),
    }


def train_hydraulic_baselines(
    project_root: Path,
    feature_table: pd.DataFrame | None = None,
    random_state: int = 42,
) -> dict[str, object]:
    """Compare classifiers for four targets and save one bundle per target."""

    full_table = (
        feature_table.copy()
        if feature_table is not None
        else pd.read_csv(
            project_root / "data" / "processed" / "hydraulic" / "cycle_features.csv"
        )
    )
    table = full_table.loc[full_table["stable_flag"] == 0].reset_index(drop=True)
    feature_columns = tuple(
        column for column in table.columns if column not in HYDRAULIC_NON_FEATURE_COLUMNS
    )
    condition_groups = hydraulic_condition_groups(table)
    results: dict[str, object] = {}
    prediction_table = table[["cycle_id", *HYDRAULIC_TARGETS]].copy()
    unstable_table = full_table.loc[full_table["stable_flag"] == 1].reset_index(drop=True)
    unstable_prediction_table = unstable_table[["cycle_id", *HYDRAULIC_TARGETS]].copy()
    selected_predictions: dict[str, np.ndarray] = {}

    model_dir = project_root / "models" / "hydraulic"
    metrics_dir = project_root / "reports" / "metrics"
    figure_dir = project_root / "reports" / "figures" / "hydraulic"
    for directory in (model_dir, metrics_dir, figure_dir):
        directory.mkdir(parents=True, exist_ok=True)

    for target in HYDRAULIC_TARGETS:
        candidates: dict[str, dict[str, float]] = {}
        predictions: dict[str, np.ndarray] = {}
        started = time.perf_counter()
        for name, model in _models(random_state).items():
            predicted = _oof_predictions(
                table, target, feature_columns, model, random_state
            )
            candidates[name] = _classification_metrics(table[target], predicted)
            predictions[name] = predicted
            prediction_table[f"{target}__{name}"] = predicted
        validation_seconds = time.perf_counter() - started
        best_name = max(candidates, key=lambda name: candidates[name]["macro_f1"])
        best_predictions = predictions[best_name]
        selected_predictions[target] = best_predictions

        preprocessor = build_hydraulic_preprocessor()
        transformed = preprocessor.fit_transform(table.loc[:, feature_columns])
        retained = np.asarray(feature_columns)[
            preprocessor.named_steps["variance"].get_support()
        ]
        final_model = clone(_models(random_state)[best_name])
        final_model.fit(
            pd.DataFrame(transformed, columns=retained), table[target]
        )
        bundle = HydraulicClassificationBundle(
            target_column=target,
            feature_columns=feature_columns,
            class_labels=tuple(sorted(int(value) for value in table[target].unique())),
            preprocessor=preprocessor,
            model=final_model,
            model_name=best_name,
            validation_metrics=candidates[best_name],
        )
        model_path = model_dir / f"{target}_bundle.joblib"
        joblib.dump(bundle, model_path, compress=3)
        unstable_predictions = bundle.predict_feature_frame(unstable_table)
        unstable_prediction_table[f"{target}__prediction"] = unstable_predictions
        report = classification_report(
            table[target],
            best_predictions,
            labels=list(bundle.class_labels),
            output_dict=True,
            zero_division=0,
        )
        results[target] = {
            "classes": list(bundle.class_labels),
            "best_model": best_name,
            "selection_metric": "macro_f1",
            "candidate_metrics": candidates,
            "classification_report": report,
            "potentially_unstable_descriptive_metrics": _classification_metrics(
                unstable_table[target], unstable_predictions
            ),
            "potentially_unstable_metrics_are_validation": False,
            "validation_seconds": validation_seconds,
            "model_path": str(model_path.relative_to(project_root)),
        }

    prediction_table.to_csv(
        metrics_dir / "hydraulic_grouped_oof_predictions.csv", index=False
    )
    unstable_prediction_table.to_csv(
        metrics_dir / "hydraulic_unstable_descriptive_predictions.csv", index=False
    )

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    for ax, target in zip(axes.flat, HYDRAULIC_TARGETS):
        target_result = results[target]
        ConfusionMatrixDisplay.from_predictions(
            table[target],
            selected_predictions[target],
            labels=target_result["classes"],
            cmap="Blues",
            colorbar=False,
            ax=ax,
        )
        ax.set_title(
            f"{target.replace('_', ' ').title()}\n{str(target_result['best_model']).replace('_', ' ').title()}"
        )
    fig.suptitle("Hydraulic Stable-Cycle Grouped Validation")
    fig.tight_layout()
    fig.savefig(figure_dir / "hydraulic_best_model_confusion_matrices.png", dpi=160)
    plt.close(fig)

    model_names = list(_models(random_state))
    x = np.arange(len(HYDRAULIC_TARGETS))
    width = 0.19
    fig, ax = plt.subplots(figsize=(13, 6))
    for offset, name in enumerate(model_names):
        scores = [results[target]["candidate_metrics"][name]["macro_f1"] for target in HYDRAULIC_TARGETS]
        ax.bar(x + (offset - 1.5) * width, scores, width, label=name.replace("_", " ").title())
    ax.set(
        title="Hydraulic Classifier Comparison",
        ylabel="Grouped out-of-fold macro F1",
        xticks=x,
        xticklabels=[target.replace("_", "\n") for target in HYDRAULIC_TARGETS],
        ylim=(0, 1.05),
    )
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(figure_dir / "hydraulic_model_comparison.png", dpi=160)
    plt.close(fig)

    output = {
        "training_rows": len(table),
        "excluded_potentially_unstable_rows": int((full_table["stable_flag"] == 1).sum()),
        "features": len(feature_columns),
        "condition_groups": int(condition_groups.nunique()),
        "validation": "five_fold_stratified_grouped_by_complete_condition_combination",
        "targets": results,
    }
    (metrics_dir / "hydraulic_baselines.json").write_text(
        json.dumps(output, indent=2), encoding="utf-8"
    )
    return output


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(train_hydraulic_baselines(root), indent=2))


if __name__ == "__main__":
    main()
