"""Retrain subsystem models with stricter validation and readiness safeguards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, RandomForestRegressor
from sklearn.feature_selection import VarianceThreshold
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut, StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.data.cmapss import load_test_with_rul, load_training_with_rul
from src.data.landing_gear import LANDING_GEAR_FAULT_NAMES
from src.eda_hydraulic import HYDRAULIC_NON_FEATURE_COLUMNS, HYDRAULIC_TARGETS
from src.eda_landing_gear import LANDING_GEAR_OBSERVABLE_FEATURES
from src.model_improvements import (
    add_fuel_phase_features,
    cooler_classifier_candidates,
    cooler_proxy_free_features,
    engine_regressor_candidates,
    fuel_challenger_candidates,
    fuel_detection_metrics,
    fuel_feature_columns,
    perturb_validation_features,
    unseen_fuel_scenario_oof,
)
from src.preprocessing import NON_FEATURE_COLUMNS, add_causal_engine_features
from src.robust_validation import robust_classification_oof
from src.readiness_modeling import (
    FeatureSupport,
    ReadinessClassificationBundle,
    ReadinessRegressionBundle,
)
from src.train_fuel import train_fuel_anomaly_baselines
from src.train_hydraulic import grouped_hydraulic_folds, hydraulic_condition_groups
from src.tune_fuel_phase import tune_fuel_phase_detector

BATTERY_SOH_EXCLUDED = frozenset({"battery_id", "uid", "soh_percent"})
BATTERY_RUL_EXCLUDED = frozenset({
    "battery_id", "uid", "soh_percent", "rul_cycles", "observed_eol_cycle"
})


def _preprocessor() -> Pipeline:
    return Pipeline([
        ("variance", VarianceThreshold(threshold=0.0)),
        ("scaler", StandardScaler()),
    ])


def _fit_transform(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    features: tuple[str, ...],
) -> tuple[Pipeline, pd.DataFrame, pd.DataFrame]:
    preprocessor = _preprocessor()
    train_values = preprocessor.fit_transform(train.loc[:, features])
    validation_values = preprocessor.transform(validation.loc[:, features])
    names = np.asarray(features)[preprocessor.named_steps["variance"].get_support()]
    return (
        preprocessor,
        pd.DataFrame(train_values, columns=names, index=train.index),
        pd.DataFrame(validation_values, columns=names, index=validation.index),
    )


def regression_metrics(actual: Iterable[float], predicted: Iterable[float]) -> dict[str, float]:
    actual_values = np.asarray(actual, dtype=float)
    predicted_values = np.asarray(predicted, dtype=float)
    return {
        "mae": float(mean_absolute_error(actual_values, predicted_values)),
        "rmse": float(np.sqrt(mean_squared_error(actual_values, predicted_values))),
        "r2": float(r2_score(actual_values, predicted_values)),
    }


def classification_metrics(actual: Iterable[int], predicted: Iterable[int]) -> dict[str, float]:
    actual_values = np.asarray(actual, dtype=int)
    predicted_values = np.asarray(predicted, dtype=int)
    return {
        "accuracy": float(accuracy_score(actual_values, predicted_values)),
        "balanced_accuracy": float(balanced_accuracy_score(actual_values, predicted_values)),
        "macro_f1": float(f1_score(actual_values, predicted_values, average="macro")),
    }


def conservative_error_quantile(errors: Iterable[float], alpha: float = 0.10) -> float:
    values = np.abs(np.asarray(errors, dtype=float))
    if values.size == 0 or not np.isfinite(values).all() or not 0 < alpha < 1:
        raise ValueError("Finite errors and alpha between zero and one are required")
    rank = min(int(np.ceil((values.size + 1) * (1 - alpha))), values.size)
    return float(np.partition(values, rank - 1)[rank - 1])


def _regression_oof(
    table: pd.DataFrame,
    features: tuple[str, ...],
    target: str,
    model: Any,
    folds: Iterable[tuple[np.ndarray, np.ndarray]],
    lower: float = 0.0,
    upper: float | None = None,
) -> np.ndarray:
    predictions = np.full(len(table), np.nan)
    for train_indices, validation_indices in folds:
        train = table.iloc[train_indices]
        validation = table.iloc[validation_indices]
        _, X_train, X_validation = _fit_transform(train, validation, features)
        fitted = clone(model).fit(X_train, train[target])
        predictions[validation_indices] = np.clip(
            fitted.predict(X_validation), lower, upper
        )
    if not np.isfinite(predictions).all():
        raise RuntimeError("Regression OOF predictions did not cover every row")
    return predictions


def _classification_oof(
    table: pd.DataFrame,
    features: tuple[str, ...],
    target: str,
    model: Any,
    folds: Iterable[tuple[np.ndarray, np.ndarray]],
) -> tuple[np.ndarray, np.ndarray]:
    classes = np.asarray(sorted(table[target].unique()), dtype=int)
    predictions = np.full(len(table), -1, dtype=int)
    confidence = np.full(len(table), np.nan)
    for train_indices, validation_indices in folds:
        train = table.iloc[train_indices]
        validation = table.iloc[validation_indices]
        _, X_train, X_validation = _fit_transform(train, validation, features)
        fitted = clone(model).fit(X_train, train[target])
        probabilities = fitted.predict_proba(X_validation)
        positions = probabilities.argmax(axis=1)
        predictions[validation_indices] = fitted.classes_[positions].astype(int)
        confidence[validation_indices] = probabilities[np.arange(len(positions)), positions]
        if set(fitted.classes_) != set(classes):
            raise RuntimeError("A classification fold is missing target classes")
    if (predictions < 0).any() or not np.isfinite(confidence).all():
        raise RuntimeError("Classification OOF predictions did not cover every row")
    return predictions, confidence


def fit_confidence_calibration(
    raw_confidence: np.ndarray,
    correct: np.ndarray,
    target_accepted_accuracy: float = 0.90,
    minimum_coverage: float = 0.20,
) -> tuple[IsotonicRegression, float, dict[str, float]]:
    calibrator = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
    calibrator.fit(np.asarray(raw_confidence, float), np.asarray(correct, int))
    calibrated = calibrator.predict(raw_confidence)
    # Reject everything when no threshold satisfies accuracy and coverage.
    threshold = float(np.nextafter(1.0, np.inf))
    for candidate in np.unique(calibrated):
        accepted = calibrated >= candidate
        coverage = float(accepted.mean())
        if coverage >= minimum_coverage and float(correct[accepted].mean()) >= target_accepted_accuracy:
            threshold = float(candidate)
            break
    accepted = calibrated >= threshold
    return calibrator, threshold, {
        "confidence_threshold": threshold,
        "accepted_coverage": float(accepted.mean()),
        "accepted_accuracy": float(correct[accepted].mean()) if accepted.any() else 0.0,
    }


def _fit_final_model(
    table: pd.DataFrame, features: tuple[str, ...], target: str, model: Any
) -> tuple[Pipeline, Any]:
    preprocessor = _preprocessor()
    values = preprocessor.fit_transform(table.loc[:, features])
    names = np.asarray(features)[preprocessor.named_steps["variance"].get_support()]
    fitted = clone(model).fit(pd.DataFrame(values, columns=names), table[target])
    return preprocessor, fitted


def retrain_engine(project_root: Path, random_state: int = 42) -> dict[str, object]:
    """Select an engine regressor by grouped engines, then stress-test it."""

    table = load_training_with_rul("FD001")
    table["rul"] = table["rul"].clip(upper=125)
    table = add_causal_engine_features(table).reset_index(drop=True)
    features = tuple(column for column in table.columns if column not in NON_FEATURE_COLUMNS)
    groups = table["unit_id"].to_numpy()
    folds = list(GroupKFold(n_splits=5).split(table, groups=groups))

    candidate_models = engine_regressor_candidates(random_state)
    candidate_metrics: dict[str, dict[str, float]] = {}
    candidate_predictions: dict[str, np.ndarray] = {}
    actual = table["rul"].to_numpy(dtype=float)
    near_failure = actual <= 30
    for name, candidate in candidate_models.items():
        predicted = _regression_oof(
            table, features, "rul", candidate, folds, upper=125
        )
        metrics = regression_metrics(actual, predicted)
        near_error = predicted[near_failure] - actual[near_failure]
        metrics["near_failure_late_rate"] = float((near_error > 0).mean())
        metrics["near_failure_bias"] = float(near_error.mean())
        metrics["selection_score"] = float(
            metrics["rmse"] + 0.5 * max(metrics["near_failure_bias"], 0.0)
        )
        candidate_metrics[name] = metrics
        candidate_predictions[name] = predicted

    best_grouped_rmse = min(
        metrics["rmse"] for metrics in candidate_metrics.values()
    )
    near_best = {
        name
        for name, metrics in candidate_metrics.items()
        if metrics["rmse"] <= best_grouped_rmse * 1.01
    }
    preference = (
        "random_forest",
        "forest_soft_voting",
        "extra_trees",
        "hist_gradient_boosting",
    )
    selected_name = next(name for name in preference if name in near_best)
    model = candidate_models[selected_name]
    oof = candidate_predictions[selected_name]
    radius = conservative_error_quantile(table["rul"] - oof, alpha=0.05)
    preprocessor, fitted = _fit_final_model(table, features, "rul", model)
    bundle = ReadinessRegressionBundle(
        component="engine", target_name="rul", target_unit="cycles",
        feature_columns=features, preprocessor=preprocessor, model=fitted,
        model_name=f"group_selected_{selected_name}",
        validation_metrics=regression_metrics(table["rul"], oof),
        interval_alpha=0.05, absolute_error_quantile=radius,
        feature_support=FeatureSupport.fit(table, features), target_maximum=125,
        validation_protocol=(
            "five_fold_grouped_by_engine_id_with_candidate_selection_and_sensor_stress_test"
        ),
    )
    test = load_test_with_rul("FD001")
    test = add_causal_engine_features(test)
    terminal = test.loc[test.groupby("unit_id")["cycle"].idxmax()].sort_values("unit_id")
    predicted, lower, upper = bundle.predict_interval(terminal)
    actual_test = terminal["rul"].to_numpy(float)
    official = {
        **regression_metrics(actual_test, predicted),
        "interval_95_coverage": float(
            ((actual_test >= lower) & (actual_test <= upper)).mean()
        ),
        "interval_mean_width": float(np.mean(upper - lower)),
    }
    stress_features = tuple(feature for feature in features if feature != "cycle")
    perturbed_terminal = perturb_validation_features(
        terminal,
        table,
        stress_features,
        noise_fraction=0.02,
        dropout_fraction=0.01,
        random_state=random_state,
    )
    robust_predicted = bundle.predict_feature_frame(perturbed_terminal)
    robustness = {
        **regression_metrics(actual_test, robust_predicted),
        "noise_fraction_of_training_std": 0.02,
        "median_replacement_fraction": 0.01,
    }
    path = project_root / "models" / "readiness" / "engine_fd001_bundle.joblib"
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path, compress=3)
    gate_passed = (
        official["rmse"] <= 20
        and official["interval_95_coverage"] >= 0.85
        and robustness["rmse"] <= 25
    )
    return {
        "model_path": str(path.relative_to(project_root)),
        "selected_model": selected_name,
        "selection_used_official_test": False,
        "selection_rule": (
            "prefer the established simpler model when grouped RMSE is within "
            "one percent of the best candidate"
        ),
        "candidate_grouped_oof_metrics": candidate_metrics,
        "grouped_oof_metrics": bundle.validation_metrics,
        "official_test_metrics": official,
        "sensor_stress_test_metrics": robustness,
        "interval_error_quantile": radius,
        "readiness_gate": "conditional_pass" if gate_passed else "fail",
    }

def retrain_battery_soh(project_root: Path) -> dict[str, object]:
    table = pd.read_csv(project_root / "data" / "processed" / "battery" / "soh_features.csv")
    features = tuple(column for column in table.columns if column not in BATTERY_SOH_EXCLUDED)
    groups = table["battery_id"].to_numpy()
    folds = list(GroupKFold(n_splits=5).split(table, groups=groups))
    model = LinearRegression()
    oof = _regression_oof(table, features, "soh_percent", model, folds, upper=150)
    radius = conservative_error_quantile(table["soh_percent"] - oof)
    preprocessor, fitted = _fit_final_model(table, features, "soh_percent", model)
    bundle = ReadinessRegressionBundle(
        component="battery", target_name="soh", target_unit="percent",
        feature_columns=features, preprocessor=preprocessor, model=fitted,
        model_name="grouped_linear_regression", validation_metrics=regression_metrics(table["soh_percent"], oof),
        interval_alpha=0.10, absolute_error_quantile=radius,
        feature_support=FeatureSupport.fit(table, features), target_maximum=150,
        validation_protocol="five_fold_grouped_by_battery_id",
    )
    path = project_root / "models" / "readiness" / "battery_soh_bundle.joblib"
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path, compress=3)
    return {
        "model_path": str(path.relative_to(project_root)),
        "grouped_oof_metrics": bundle.validation_metrics,
        "interval_error_quantile": radius,
        "readiness_gate": "conditional_pass" if bundle.validation_metrics["mae"] <= 5 else "fail",
    }


def retrain_battery_rul(project_root: Path, random_state: int = 42) -> dict[str, object]:
    table = pd.read_csv(project_root / "data" / "processed" / "battery" / "rul_features.csv")
    features = tuple(column for column in table.columns if column not in BATTERY_RUL_EXCLUDED)
    groups = table["battery_id"].to_numpy()
    folds = list(LeaveOneGroupOut().split(table, groups=groups))
    model = RandomForestRegressor(
        n_estimators=500, max_depth=12, min_samples_leaf=3,
        max_features="sqrt", n_jobs=-1, random_state=random_state,
    )
    oof = _regression_oof(table, features, "rul_cycles", model, folds)
    radius = conservative_error_quantile(table["rul_cycles"] - oof)
    preprocessor, fitted = _fit_final_model(table, features, "rul_cycles", model)
    bundle = ReadinessRegressionBundle(
        component="battery", target_name="rul", target_unit="cycles",
        feature_columns=features, preprocessor=preprocessor, model=fitted,
        model_name="logo_random_forest", validation_metrics=regression_metrics(table["rul_cycles"], oof),
        interval_alpha=0.10, absolute_error_quantile=radius,
        feature_support=FeatureSupport.fit(table, features),
        validation_protocol="leave_one_battery_out",
    )
    path = project_root / "models" / "readiness" / "battery_rul_bundle.joblib"
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path, compress=3)
    return {
        "model_path": str(path.relative_to(project_root)),
        "logo_metrics": bundle.validation_metrics,
        "interval_error_quantile": radius,
        "independent_batteries": int(table["battery_id"].nunique()),
        "readiness_gate": "conditional_pass" if bundle.validation_metrics["mae"] <= 12 else "fail",
    }


def _hydraulic_model(target: str, random_state: int) -> Any:
    if target in {"cooler_condition_percent", "valve_condition_percent"}:
        return LogisticRegression(max_iter=4000, class_weight="balanced", random_state=random_state)
    if target == "pump_leakage_severity":
        return ExtraTreesClassifier(
            n_estimators=500, min_samples_leaf=2, max_features="sqrt",
            class_weight="balanced", n_jobs=-1, random_state=random_state,
        )
    return RandomForestClassifier(
        n_estimators=500, min_samples_leaf=2, max_features="sqrt",
        class_weight="balanced_subsample", n_jobs=-1, random_state=random_state,
    )


def retrain_hydraulic(project_root: Path, random_state: int = 42) -> dict[str, object]:
    """Retrain hydraulic tasks; remove cooler proxies and stress-test sensors."""

    full = pd.read_csv(project_root / "data" / "processed" / "hydraulic" / "cycle_features.csv")
    table = full.loc[full["stable_flag"] == 0].reset_index(drop=True)
    unstable = full.loc[full["stable_flag"] == 1].reset_index(drop=True)
    all_features = tuple(
        column for column in table.columns if column not in HYDRAULIC_NON_FEATURE_COLUMNS
    )
    output: dict[str, object] = {}
    model_dir = project_root / "models" / "readiness" / "hydraulic"
    model_dir.mkdir(parents=True, exist_ok=True)
    for target in HYDRAULIC_TARGETS:
        folds = grouped_hydraulic_folds(table, target, random_state=random_state)
        candidate_details: dict[str, object] | None = None
        if target == "cooler_condition_percent":
            features = cooler_proxy_free_features(table)
            candidate_details = {}
            candidate_outputs: dict[str, tuple[Any, np.ndarray, np.ndarray]] = {}
            for name, candidate in cooler_classifier_candidates(random_state).items():
                clean_pred, candidate_confidence, noisy_pred = robust_classification_oof(
                    table,
                    features,
                    target,
                    candidate,
                    folds,
                    noise_fraction=0.05,
                    dropout_fraction=0.03,
                    random_state=random_state,
                )
                clean_metrics = classification_metrics(table[target], clean_pred)
                noisy_metrics = classification_metrics(table[target], noisy_pred)
                robust_score = 0.5 * (
                    clean_metrics["macro_f1"] + noisy_metrics["macro_f1"]
                )
                candidate_details[name] = {
                    "clean_metrics": clean_metrics,
                    "sensor_stress_metrics": noisy_metrics,
                    "robust_selection_score": robust_score,
                }
                candidate_outputs[name] = (
                    candidate,
                    clean_pred,
                    candidate_confidence,
                )
            selected_name = max(
                candidate_details,
                key=lambda name: candidate_details[name]["robust_selection_score"],
            )
            model, predicted, confidence = candidate_outputs[selected_name]
            stress_metrics = candidate_details[selected_name]["sensor_stress_metrics"]
            model_name = f"proxy_free_robust_{selected_name}"
        else:
            features = all_features
            model = _hydraulic_model(target, random_state)
            predicted, confidence = _classification_oof(
                table, features, target, model, folds
            )
            stress_metrics = None
            selected_name = type(model).__name__
            model_name = f"readiness_{selected_name}"

        correct = predicted == table[target].to_numpy()
        calibrator, threshold, abstention = fit_confidence_calibration(confidence, correct)
        preprocessor, fitted = _fit_final_model(table, features, target, model)
        metrics = {**classification_metrics(table[target], predicted), **abstention}
        if stress_metrics is not None:
            metrics.update(
                {f"sensor_stress_{key}": value for key, value in stress_metrics.items()}
            )
        bundle = ReadinessClassificationBundle(
            component="hydraulic", target_name=target, feature_columns=features,
            preprocessor=preprocessor, model=fitted,
            model_name=model_name, class_names={},
            confidence_calibrator=calibrator, confidence_threshold=threshold,
            validation_metrics=metrics, feature_support=FeatureSupport.fit(table, features),
            validation_protocol=(
                "five_fold_grouped_by_complete_condition_combination_stable_cycles_"
                "proxy_free_with_sensor_stress_test"
                if target == "cooler_condition_percent"
                else "five_fold_grouped_by_complete_condition_combination_stable_cycles"
            ),
        )
        path = model_dir / f"{target}_bundle.joblib"
        joblib.dump(bundle, path, compress=3)
        unstable_pred = bundle.predict_feature_frame(unstable)
        unstable_metrics = classification_metrics(unstable[target], unstable_pred)
        gate_passed = metrics["accepted_accuracy"] >= 0.90
        if target == "cooler_condition_percent":
            gate_passed = (
                gate_passed
                and metrics["sensor_stress_macro_f1"] >= 0.85
                and unstable_metrics["balanced_accuracy"] >= 0.85
            )
        target_output: dict[str, object] = {
            "model_path": str(path.relative_to(project_root)),
            "selected_model": selected_name,
            "feature_count": len(features),
            "metrics": metrics,
            "unstable_cycle_challenge_metrics": unstable_metrics,
            "readiness_gate": "conditional_pass" if gate_passed else "fail",
        }
        if target == "cooler_condition_percent":
            removed = sorted(set(all_features) - set(features))
            target_output.update(
                {
                    "proxy_features_removed": removed,
                    "candidate_robustness_metrics": candidate_details,
                    "stress_test": {
                        "noise_fraction_of_training_std": 0.05,
                        "median_replacement_fraction": 0.03,
                    },
                }
            )
        output[target] = target_output
    return output

def landing_mass_regime_folds(
    table: pd.DataFrame, n_splits: int = 5, random_state: int = 42
) -> list[tuple[np.ndarray, np.ndarray]]:
    groups = pd.qcut(table["mass"], q=20, labels=False, duplicates="drop")
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    folds = list(splitter.split(table, table["fault_code"], groups=groups))
    for train, validation in folds:
        if set(groups.iloc[train]) & set(groups.iloc[validation]):
            raise RuntimeError("Landing-gear mass-regime leakage detected")
    return folds


def retrain_landing_gear(project_root: Path, random_state: int = 42) -> dict[str, object]:
    table = pd.read_csv(project_root / "data" / "processed" / "landing_gear" / "validated_runs.csv")
    features = LANDING_GEAR_OBSERVABLE_FEATURES
    folds = landing_mass_regime_folds(table, random_state=random_state)
    classifier = RandomForestClassifier(
        n_estimators=500, min_samples_leaf=2, max_features="sqrt",
        class_weight="balanced_subsample", n_jobs=-1, random_state=random_state,
    )
    class_pred, confidence = _classification_oof(
        table, features, "fault_code", classifier, folds
    )
    correct = class_pred == table["fault_code"].to_numpy()
    calibrator, threshold, abstention = fit_confidence_calibration(confidence, correct)
    class_preprocessor, fitted_classifier = _fit_final_model(
        table, features, "fault_code", classifier
    )
    class_metrics = {**classification_metrics(table["fault_code"], class_pred), **abstention}
    class_bundle = ReadinessClassificationBundle(
        component="landing_gear", target_name="fault_code", feature_columns=features,
        preprocessor=class_preprocessor, model=fitted_classifier,
        model_name="observable_mass_regime_random_forest",
        class_names=LANDING_GEAR_FAULT_NAMES, confidence_calibrator=calibrator,
        confidence_threshold=threshold, validation_metrics=class_metrics,
        feature_support=FeatureSupport.fit(table, features),
        validation_protocol="five_fold_stratified_grouped_by_mass_regime",
    )

    regressor = RandomForestRegressor(
        n_estimators=500, min_samples_leaf=2, max_features="sqrt",
        n_jobs=-1, random_state=random_state,
    )
    rul_pred = _regression_oof(
        table, features, "rul_percent", regressor, folds, upper=100
    )
    radius = conservative_error_quantile(table["rul_percent"] - rul_pred)
    rul_preprocessor, fitted_regressor = _fit_final_model(
        table, features, "rul_percent", regressor
    )
    rul_metrics = regression_metrics(table["rul_percent"], rul_pred)
    rul_bundle = ReadinessRegressionBundle(
        component="landing_gear", target_name="rul", target_unit="percent",
        feature_columns=features, preprocessor=rul_preprocessor, model=fitted_regressor,
        model_name="observable_mass_regime_random_forest",
        validation_metrics=rul_metrics, interval_alpha=0.10,
        absolute_error_quantile=radius,
        feature_support=FeatureSupport.fit(table, features), target_maximum=100,
        validation_protocol="five_fold_stratified_grouped_by_mass_regime",
    )
    model_dir = project_root / "models" / "readiness"
    fault_path = model_dir / "landing_gear_fault_bundle.joblib"
    rul_path = model_dir / "landing_gear_rul_bundle.joblib"
    joblib.dump(class_bundle, fault_path, compress=3)
    joblib.dump(rul_bundle, rul_path, compress=3)
    return {
        "observable_features_only": True,
        "fault": {
            "model_path": str(fault_path.relative_to(project_root)),
            "metrics": class_metrics,
            "readiness_gate": "conditional_pass" if class_metrics["accepted_accuracy"] >= 0.90 else "fail",
        },
        "rul": {
            "model_path": str(rul_path.relative_to(project_root)),
            "metrics": rul_metrics,
            "interval_error_quantile": radius,
            "readiness_gate": "conditional_pass" if rul_metrics["mae"] <= 5 else "fail",
        },
    }


def retrain_fuel_challenger(
    project_root: Path, random_state: int = 42
) -> dict[str, object]:
    """Train a supervised challenger with complete failure-scenario holdouts."""

    raw_table = pd.read_csv(
        project_root / "data" / "processed" / "fuel_system" / "scenario_features.csv"
    )
    table = add_fuel_phase_features(raw_table)
    features = fuel_feature_columns(table)
    candidates: dict[str, dict[str, object]] = {}
    prediction_cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for name, model in fuel_challenger_candidates(random_state).items():
        predicted, confidence, indices = unseen_fuel_scenario_oof(
            table, model, features
        )
        if not np.array_equal(indices, table.index.to_numpy()):
            raise RuntimeError("Fuel challenger predictions lost source ordering")
        metrics = fuel_detection_metrics(table, predicted)
        candidates[name] = metrics
        prediction_cache[name] = (predicted, confidence)
    selected_name = max(
        candidates,
        key=lambda name: (
            candidates[name]["balanced_accuracy"],
            candidates[name]["macro_f1"],
        ),
    )
    selected_model = fuel_challenger_candidates(random_state)[selected_name]
    selected_predicted, selected_confidence = prediction_cache[selected_name]
    correct = selected_predicted == table["is_abnormal"].to_numpy(dtype=int)
    calibrator, threshold, abstention = fit_confidence_calibration(
        selected_confidence,
        correct,
        target_accepted_accuracy=0.90,
        minimum_coverage=0.20,
    )
    preprocessor, fitted = _fit_final_model(
        table, features, "is_abnormal", selected_model
    )
    selected_metrics = {
        **candidates[selected_name],
        **abstention,
    }
    bundle = ReadinessClassificationBundle(
        component="fuel_system",
        target_name="is_abnormal",
        feature_columns=features,
        preprocessor=preprocessor,
        model=fitted,
        model_name=f"unseen_scenario_{selected_name}",
        class_names={0: "normal", 1: "anomaly"},
        confidence_calibrator=calibrator,
        confidence_threshold=threshold,
        validation_metrics={
            key: float(value)
            for key, value in selected_metrics.items()
            if isinstance(value, (int, float))
        },
        feature_support=FeatureSupport.fit(table, features),
        validation_protocol=(
            "leave_one_complete_failure_scenario_out_with_contiguous_normal_blocks"
        ),
    )
    path = (
        project_root
        / "models"
        / "readiness"
        / "fuel_system_challenger_bundle.joblib"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path, compress=3)
    return {
        "model_path": str(path.relative_to(project_root)),
        "selected_model": selected_name,
        "candidate_metrics": candidates,
        "metrics": selected_metrics,
        "phase_features": ["phase_fraction", "phase_sin", "phase_cos", "phase_bin"],
        "complete_failure_scenarios_held_out": 4,
        "readiness_gate": "fail",
        "reason": (
            "The challenger generalizes across known failure scenarios, but one normal "
            "trajectory cannot establish false-alarm performance on a new mission."
        ),
    }

def retrain_all(project_root: Path, random_state: int = 42) -> dict[str, object]:
    results = {
        "protocol_version": "readiness-v2.2",
        "real_aircraft_validated": False,
        "engine": retrain_engine(project_root, random_state),
        "battery_soh": retrain_battery_soh(project_root),
        "battery_rul": retrain_battery_rul(project_root, random_state),
        "hydraulic": retrain_hydraulic(project_root, random_state),
        "landing_gear": retrain_landing_gear(project_root, random_state),
    }
    fuel = train_fuel_anomaly_baselines(project_root, random_state=random_state)
    fuel_challenger = retrain_fuel_challenger(project_root, random_state)
    fuel_phase = tune_fuel_phase_detector(project_root)
    results["fuel_system"] = {
        "retrained": True,
        "normal_only_detector": {
            "best_model": fuel["best_model"],
            "metrics": fuel["candidate_metrics"][fuel["best_model"]],
        },
        "high_sensitivity_review_model": fuel_challenger,
        "low_false_alarm_alert_model": fuel_phase,
        "best_model": fuel_phase["selected_model"],
        "metrics": fuel_phase["metrics"],
        "operating_policy": (
            "Phase-residual positives are experimental alerts; Extra Trees positives "
            "are review candidates only."
        ),
        "readiness_gate": "fail",
        "reason": "One normal trajectory cannot establish external generalization.",
    }
    results["summary"] = {
        "status": "pre_deployment_research_only",
        "statement": (
            "Readiness safeguards improve uncertainty handling and abstention but do "
            "not replace validation on independent aircraft-representative data."
        ),
    }
    metrics_dir = project_root / "reports" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "readiness_v2_retraining.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    return results


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(retrain_all(root), indent=2))


if __name__ == "__main__":
    main()
