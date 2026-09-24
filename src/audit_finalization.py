"""Reproducible calibration diagnostics; never overwrite serving models.

The data have already influenced development. Disjoint groups below prevent
within-run fitting/calibration/evaluation overlap, but are not a new external test.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone

from src.data.cmapss import load_training_with_rul, load_test_with_rul
from src.preprocessing import add_causal_engine_features
from src.readiness_modeling import FeatureSupport, _transformed
from src.retrain_readiness import (
    _fit_final_model, classification_metrics, regression_metrics,
    conservative_error_quantile, fit_confidence_calibration,
)
from src.train_hydraulic import hydraulic_condition_groups

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260909


def partition_groups(groups, seed=SEED):
    groups = np.asarray(groups)
    unique = np.unique(groups)
    if len(unique) < 5:
        raise ValueError('At least five groups are required')
    unique = np.random.default_rng(seed).permutation(unique)
    count = max(1, len(unique) // 5)
    parts = (unique[2 * count:], unique[:count], unique[count:2 * count])
    return tuple(np.flatnonzero(np.isin(groups, part)) for part in parts)


def supported_rows(support, frame):
    support.assess(frame)
    values = frame.loc[:, support.feature_columns].to_numpy(float)
    return ((values >= support.hard_minimum) &
            (values <= support.hard_maximum)).all(axis=1)


def split_record(groups, split):
    groups = np.asarray(groups)
    return {name: {'rows': len(indices), 'groups': [str(x) for x in np.unique(groups[indices])]}
            for name, indices in zip(('fit', 'calibration', 'evaluation'), split)}


def audit_classifier(table, groups, bundle, key, output_dir):
    split = partition_groups(groups)
    fit, calibration, evaluation = (table.iloc[idx].copy() for idx in split)
    features, target = bundle.feature_columns, bundle.target_name
    prep, model = _fit_final_model(fit, features, target, clone(bundle.model))
    if set(model.classes_) != set(table[target]):
        return {'status': 'insufficient_class_support', 'split': split_record(groups, split)}

    def predict(frame):
        probabilities = model.predict_proba(_transformed(frame, features, prep, model))
        positions = probabilities.argmax(axis=1)
        return model.classes_[positions], probabilities[np.arange(len(frame)), positions]

    cal_pred, cal_raw = predict(calibration)
    calibrator, threshold, cal_metrics = fit_confidence_calibration(
        cal_raw, cal_pred == calibration[target].to_numpy())
    predicted, raw = predict(evaluation)
    confidence = calibrator.predict(raw)
    support = FeatureSupport.fit(fit, features)
    accepted = (confidence >= threshold) & supported_rows(support, evaluation)
    correct = predicted == evaluation[target].to_numpy()
    pd.DataFrame({'source_index': split[2], 'group': np.asarray(groups)[split[2]],
                  'actual': evaluation[target], 'predicted': predicted,
                  'confidence': confidence, 'accepted': accepted}).to_csv(output_dir / f'{key}.csv', index=False)
    return {'status': 'diagnostic_only', 'split': split_record(groups, split),
            'calibration_metrics': cal_metrics,
            'evaluation_metrics': {**classification_metrics(evaluation[target], predicted),
                'accepted_coverage': float(accepted.mean()),
                'accepted_accuracy': float(correct[accepted].mean()) if accepted.any() else None,
                'accepted_count': int(accepted.sum())},
            'confidence_threshold': threshold,
            'independent_external_test': False}


def snapshots(frame):
    # One predeclared random truncation per engine; no terminal-failure-only calibration.
    rng = np.random.default_rng(SEED)
    return pd.DataFrame([group.iloc[int(rng.integers(max(1, len(group)//5), len(group)))]
                         for _, group in frame.groupby('unit_id', sort=True)]).reset_index(drop=True)


def audit_regressor(table, groups, bundle, target, key, output_dir, engine=False):
    split = partition_groups(groups)
    fit, calibration, evaluation = (table.iloc[idx].copy() for idx in split)
    features = bundle.feature_columns
    fit[target] = fit[target].clip(lower=bundle.target_minimum, upper=bundle.target_maximum)
    prep, model = _fit_final_model(fit, features, target, clone(bundle.model))
    if engine:
        calibration, evaluation = snapshots(calibration), snapshots(evaluation)

    def predict(frame):
        return np.clip(model.predict(_transformed(frame, features, prep, model)),
                       bundle.target_minimum, bundle.target_maximum)

    radius = conservative_error_quantile(calibration[target] - predict(calibration), bundle.interval_alpha)
    predicted = predict(evaluation)
    lower = np.maximum(predicted - radius, bundle.target_minimum)
    # Engine cap is a modeling convention, not a physical upper bound for true RUL.
    upper = predicted + radius
    if not engine and bundle.target_maximum is not None:
        upper = np.minimum(upper, bundle.target_maximum)
    actual = evaluation[target].to_numpy(float)
    support = FeatureSupport.fit(fit, features)
    accepted = supported_rows(support, evaluation)
    pd.DataFrame({'source_index': evaluation.index, 'actual': actual, 'predicted': predicted,
                  'lower': lower, 'upper': upper, 'supported': accepted}).to_csv(output_dir / f'{key}.csv', index=False)
    return {'status': 'diagnostic_only', 'split': split_record(groups, split),
            'calibration_units': len(calibration), 'evaluation_rows': len(evaluation),
            'interval_radius': radius, 'nominal_interval_level': 1-bundle.interval_alpha,
            'evaluation_metrics': {**regression_metrics(actual, predicted),
                'interval_coverage': float(((actual >= lower) & (actual <= upper)).mean()),
                'mean_interval_width': float((upper-lower).mean()),
                'supported_coverage': float(accepted.mean())},
            'independent_external_test': False}


def run():
    output_dir = ROOT / 'reports' / 'metrics' / 'finalization_audit'
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {'seed': SEED, 'status': 'research_candidate_only',
               'independent_external_test': False,
               'scope': 'Disjoint fit/calibration/evaluation groups on previously used development datasets; fixed current model specifications; no parameter search or promotion.',
               'findings': [
                   'Previous hydraulic tryout inverted stable_flag: 0=stable, 1=unstable. Its 161-row selection was not stable validation.',
                   'Published accepted accuracies reused the calibration predictions for threshold selection and scoring; treat as development estimates.',
                   'Fuel candidate selection reused all scenario evaluation scores; no untouched final fuel set remains.',
                   'Removed the artificial 125-cycle engine interval cap; point prediction cap and fitted calibration radius remain unchanged.',
                   'Historical official FD001 results have been inspected repeatedly; further checks are regression audits.',
                   'Batch support now rejects unfamiliar rows individually.',
               ], 'tasks': {}}
    tasks = results['tasks']
    models = ROOT / 'models' / 'readiness'
    engine = joblib.load(models / 'engine_fd001_bundle.joblib')
    table = add_causal_engine_features(load_training_with_rul('FD001'))
    tasks['engine'] = audit_regressor(table, table.unit_id, engine, 'rul', 'engine', output_dir, True)
    test = add_causal_engine_features(load_test_with_rul('FD001'))
    terminal = test.loc[test.groupby('unit_id').cycle.idxmax()]
    predicted, lower, upper = engine.predict_interval(terminal)
    tasks['engine']['current_artifact_official_regression_check'] = {
        **regression_metrics(terminal.rul, predicted),
        'interval_coverage': float(((terminal.rul >= lower) & (terminal.rul <= upper)).mean()),
        'legacy_capped_interval_coverage': float(((terminal.rul >= lower) & (terminal.rul <= np.minimum(upper, 125))).mean()),
        'true_rul_above_125_count': int((terminal.rul > 125).sum()),
        'test_count': len(terminal)}
    print('Engine audit complete', flush=True)
    for task, filename, target in [('battery_soh', 'soh_features.csv', 'soh_percent'),
                                    ('battery_rul', 'rul_features.csv', 'rul_cycles')]:
        table = pd.read_csv(ROOT / 'data/processed/battery' / filename)
        tasks[task] = audit_regressor(table, table.battery_id, joblib.load(models / f'{task}_bundle.joblib'), target, task, output_dir)
        print(f'{task} audit complete', flush=True)
    table = pd.read_csv(ROOT / 'data/processed/hydraulic/cycle_features.csv')
    table = table.loc[table.stable_flag == 0].reset_index(drop=True)
    for path in sorted((models / 'hydraulic').glob('*.joblib')):
        bundle = joblib.load(path)
        key = f'hydraulic_{bundle.target_name}'
        tasks[key] = audit_classifier(table, hydraulic_condition_groups(table), bundle, key, output_dir)
        print(f'{key} audit complete', flush=True)
    table = pd.read_csv(ROOT / 'data/processed/landing_gear/validated_runs.csv')
    groups = pd.qcut(table.mass, q=20, labels=False, duplicates='drop')
    tasks['landing_fault'] = audit_classifier(table, groups, joblib.load(models / 'landing_gear_fault_bundle.joblib'), 'landing_fault', output_dir)
    tasks['landing_rul'] = audit_regressor(table, groups, joblib.load(models / 'landing_gear_rul_bundle.joblib'), 'rul_percent', 'landing_rul', output_dir)
    tasks['fuel'] = {'status': 'blocked', 'reason': 'One normal trajectory and tuning reuse; more independent missions required.'}
    (output_dir / 'audit.json').write_text(json.dumps(results, indent=2, allow_nan=False), encoding='utf-8')
    print('Audit saved to reports/metrics/finalization_audit/audit.json', flush=True)
    return results


if __name__ == '__main__':
    run()
