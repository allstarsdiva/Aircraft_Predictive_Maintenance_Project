"""Scoped candidate training; never overwrite deployed models or unrelated tasks.

Selection uses grouped CV inside the historical audit's fitting partition.
Calibration and evaluation remain disjoint. All data are previously inspected
development data, not a new external validation set.
"""
from dataclasses import dataclass, replace
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge, LinearRegression
from sklearn.model_selection import GroupKFold
from sklearn.svm import SVC, SVR
from threadpoolctl import threadpool_limits

from src.audit_finalization import partition_groups, snapshots, split_record
from src.data.cmapss import load_training_with_rul, load_test_with_rul
from src.model_release import verified_release, sha256
from src.preprocessing import add_causal_engine_features
from src.readiness_modeling import FeatureSupport, ReadinessClassificationBundle, _transformed
from src.retrain_readiness import _fit_final_model, regression_metrics, classification_metrics, conservative_error_quantile, fit_confidence_calibration
from src.train_hydraulic import hydraulic_condition_groups

ROOT = Path(__file__).resolve().parents[1]
TASKS = ('engine', 'battery_soh', 'battery_rul', 'hydraulic_valve', 'hydraulic_accumulator')
FILES = {'engine': 'engine_fd001_bundle.joblib', 'battery_soh': 'battery_soh_bundle.joblib',
    'battery_rul': 'battery_rul_bundle.joblib',
    'hydraulic_valve': 'hydraulic/valve_condition_percent_bundle.joblib',
    'hydraulic_accumulator': 'hydraulic/accumulator_pressure_bar_bundle.joblib'}
SEED = 20260911


@dataclass
class Candidate:
    name: str
    model: object
    features: tuple
    upper: float | None


def load_task(task, release):
    if task not in TASKS:
        raise ValueError('Task is outside the authorized retraining scope')
    bundle = joblib.load(release / 'models/readiness' / FILES[task])
    if task == 'engine':
        table = add_causal_engine_features(load_training_with_rul('FD001')).reset_index(drop=True)
        groups, target = table.unit_id, 'rul'
    elif task.startswith('battery'):
        file, target = ('soh_features.csv', 'soh_percent') if task == 'battery_soh' else ('rul_features.csv', 'rul_cycles')
        table = pd.read_csv(ROOT / 'data/processed/battery' / file)
        groups = table.battery_id
    else:
        table = pd.read_csv(ROOT / 'data/processed/hydraulic/cycle_features.csv')
        table = table.loc[table.stable_flag == 0].reset_index(drop=True)
        groups, target = hydraulic_condition_groups(table), bundle.target_name
    return table, np.asarray(groups), target, bundle


def candidates_for(task, bundle):
    features = bundle.feature_columns
    upper = getattr(bundle, 'target_maximum', None)
    candidates = [Candidate('existing_specification', clone(bundle.model), features, upper)]
    if task.startswith('hydraulic'):
        physical = tuple(f for f in features if f.startswith(('ps', 'fs', 'eps', 'vs')))
        for name, chosen in [('all', features), ('pressure_flow', physical)]:
            for c in (1., 10., 100.):
                candidates.append(Candidate(f'svc_{name}_C{c:g}', SVC(C=c, kernel='rbf',
                    gamma='scale', class_weight='balanced', probability=True, random_state=SEED), chosen, None))
            candidates.append(Candidate(f'extra_trees_{name}', ExtraTreesClassifier(n_estimators=250,
                min_samples_leaf=1, max_features=.8, class_weight='balanced', n_jobs=2,
                random_state=SEED), chosen, None))
    elif task == 'engine':
        for cap in (125., None):
            candidates.append(Candidate(f'extra_trees_cap{cap}', ExtraTreesRegressor(n_estimators=180,
                min_samples_leaf=3, max_features=.7, n_jobs=2, random_state=SEED), features, cap))
            candidates.append(Candidate(f'hist_gradient_cap{cap}', HistGradientBoostingRegressor(
                max_iter=180, learning_rate=.05, max_leaf_nodes=15, l2_regularization=5,
                min_samples_leaf=30, early_stopping=False, random_state=SEED), features, cap))
    else:
        for alpha in (1., 10., 100.):
            candidates.append(Candidate(f'ridge_{alpha:g}', Ridge(alpha=alpha), features, upper))
        if task == 'battery_soh':
            capacity = ('charge_throughput_ah',)
            physical = ('charge_throughput_ah', 'energy_throughput_wh', 'duration_seconds',
                        'current_abs_mean', 'temperature_mean', 'voltage_mean')
            candidates.extend([Candidate('throughput_linear', LinearRegression(), capacity, upper),
                Candidate('physical_ridge', Ridge(alpha=10), physical, upper)])
        for c in (10., 100.):
            candidates.append(Candidate(f'svr_C{c:g}', SVR(C=c, epsilon=.1, gamma='scale'), features, upper))
        candidates.append(Candidate('extra_trees', ExtraTreesRegressor(n_estimators=250,
            min_samples_leaf=2, max_features=.8, n_jobs=2, random_state=SEED), features, upper))
        candidates.append(Candidate('hist_gradient', HistGradientBoostingRegressor(max_iter=180,
            learning_rate=.05, max_leaf_nodes=7, l2_regularization=10, min_samples_leaf=15,
            early_stopping=False, random_state=SEED), features, upper))
    return candidates


def fit_candidate(table, target, candidate, classifier):
    fitting = table.copy()
    if not classifier:
        fitting[target] = fitting[target].clip(lower=0, upper=candidate.upper)
    prep, model = _fit_final_model(fitting, candidate.features, target, candidate.model)
    return prep, model


def prediction(frame, candidate, prep, model, classifier):
    transformed = _transformed(frame, candidate.features, prep, model)
    if classifier:
        probs = model.predict_proba(transformed)
        return model.classes_[probs.argmax(axis=1)]
    return np.clip(model.predict(transformed), 0, candidate.upper)


def select_candidate(fit, groups, target, candidates, classifier, engine=False):
    """Only receives fitting data; neither calibration nor evaluation is accessible."""
    folds = list(GroupKFold(n_splits=min(3, len(np.unique(groups)))).split(fit, groups=groups))
    results = []
    for candidate in candidates:
        actual, predicted = [], []
        for training, validation in folds:
            prep, model = fit_candidate(fit.iloc[training], target, candidate, classifier)
            check = snapshots(fit.iloc[validation]) if engine else fit.iloc[validation]
            if classifier and set(model.classes_) != set(fit[target]):
                raise ValueError('Inner fitting partition is missing target classes')
            actual.extend(check[target].tolist())
            predicted.extend(prediction(check, candidate, prep, model, classifier))
        metrics = classification_metrics(actual, predicted) if classifier else regression_metrics(actual, predicted)
        # No outer scores, accepted-only metrics, or official engine labels used.
        score = metrics['balanced_accuracy'] if classifier else -metrics['mae']
        if engine:
            score = -(metrics['mae']/15 + metrics['rmse']/20)
        results.append({'name': candidate.name, 'metrics': metrics, 'selection_score': score,
            'features': list(candidate.features), 'target_upper': candidate.upper,
            'model_parameters': candidate.model.get_params(deep=False)})
        print(f'  {candidate.name}: selection={score:.4f}', flush=True)
    best = max(range(len(candidates)), key=lambda i: results[i]['selection_score'])
    return candidates[best], results


def target_pass(task, metrics):
    if task == 'engine':
        return metrics['mae'] <= 15 and metrics['rmse'] <= 20
    if task == 'battery_soh':
        return metrics['mae'] <= 3
    if task == 'battery_rul':
        return metrics['mae'] <= 10
    if task in ('hydraulic_valve', 'hydraulic_accumulator'):
        return metrics['balanced_accuracy'] >= .90
    raise ValueError('Task is outside the authorized retraining scope')


def evaluate(bundle, frame, target, classifier):
    if classifier:
        predicted, confidence, accepted = bundle.predict_with_readiness(frame)
        correct = predicted == frame[target].to_numpy()
        metrics = {**classification_metrics(frame[target], predicted),
            'accepted_coverage': float(accepted.mean()),
            'accepted_accuracy': float(correct[accepted].mean()) if accepted.any() else None}
        records = pd.DataFrame({'actual': frame[target].to_numpy(), 'predicted': predicted,
            'confidence': confidence, 'accepted': accepted})
    else:
        predicted, lower, upper = bundle.predict_interval(frame)
        actual = frame[target].to_numpy()
        metrics = {**regression_metrics(actual, predicted),
            'interval_coverage': float(((actual >= lower) & (actual <= upper)).mean()),
            'mean_interval_width': float(np.mean(upper-lower))}
        records = pd.DataFrame({'actual': actual, 'predicted': predicted, 'lower': lower, 'upper': upper})
    for column in ('unit_id', 'cycle', 'battery_id', 'discharge_cycle', 'cycle_id'):
        if column in frame:
            records[column] = frame[column].to_numpy()
    return metrics, records


def run_task(task, output, release, feature_table=None, candidate_grid=None):
    table, groups, target, existing = load_task(task, release)
    if feature_table is not None:
        if task.startswith('hydraulic'):
            extra = feature_table.set_index('cycle_id').loc[table.cycle_id].reset_index(drop=True)
        elif task == 'battery_rul':
            keys = ['battery_id', 'discharge_cycle']
            wanted = pd.MultiIndex.from_frame(table[keys])
            extra = feature_table.set_index(keys).loc[wanted].reset_index(drop=True)
        else:
            raise ValueError('Extra features are scoped to hydraulic and battery RUL targets')
        if len(extra) != len(table) or set(extra.columns).intersection(table.columns):
            raise ValueError('Waveform features must match cycles without replacing existing columns')
        table = pd.concat([table, extra], axis=1)
    split = partition_groups(groups)
    train_idx, cal_idx, eval_idx = split
    fit, calibration, evaluation = (table.iloc[idx].copy() for idx in split)
    classifier = isinstance(existing, ReadinessClassificationBundle)
    selected, tuning = select_candidate(fit, groups[train_idx], target, candidate_grid or candidates_for(task, existing),
        classifier, task == 'engine')
    prep, model = fit_candidate(fit, target, selected, classifier)
    if classifier and set(model.classes_) != set(table[target]):
        raise ValueError('Fitting partition is missing classes')
    if task == 'engine':
        calibration, evaluation = snapshots(calibration), snapshots(evaluation)
    changes = dict(model=model, preprocessor=prep, feature_columns=selected.features,
        model_name=f'targeted_{selected.name}', feature_support=FeatureSupport.fit(fit, selected.features),
        validation_protocol='grouped_inner_selection_then_separate_calibration_and_evaluation_development_only')
    if classifier:
        probs = model.predict_proba(_transformed(calibration, selected.features, prep, model))
        positions = probs.argmax(axis=1)
        raw = probs[np.arange(len(probs)), positions]
        calibrator, threshold, cal_details = fit_confidence_calibration(raw,
            model.classes_[positions] == calibration[target].to_numpy())
        changes.update(confidence_calibrator=calibrator, confidence_threshold=threshold)
    else:
        cal_pred = prediction(calibration, selected, prep, model, False)
        radius = conservative_error_quantile(calibration[target]-cal_pred, existing.interval_alpha)
        changes.update(target_maximum=selected.upper, absolute_error_quantile=radius)
        cal_details = {'radius': radius, 'nominal_interval_level': 1-existing.interval_alpha,
            'calibration_rows': len(calibration), 'independent_calibration_groups': len(np.unique(groups[cal_idx]))}
    candidate = replace(existing, **changes)
    metrics, records = evaluate(candidate, evaluation, target, classifier)
    candidate.validation_metrics = metrics
    key = {'hydraulic_valve':'hydraulic_valve_condition_percent',
           'hydraulic_accumulator':'hydraulic_accumulator_pressure_bar'}.get(task, task)
    old_audit = json.loads((release/'reports/metrics/finalization_audit/audit.json').read_text())['tasks'][key]
    if old_audit['split'] != split_record(groups, split):
        raise RuntimeError('Comparison requires exactly matching historical audit groups')
    prior = old_audit['evaluation_metrics']
    improved = metrics['balanced_accuracy'] > prior['balanced_accuracy'] if classifier else metrics['mae'] < prior['mae']
    if task == 'engine':
        improved = improved and metrics['rmse'] < prior['rmse']
    destination = output/task
    destination.mkdir(parents=True, exist_ok=False)
    records.to_csv(destination/'evaluation_predictions.csv', index=False)
    joblib.dump(candidate, destination/'candidate.joblib', compress=3)
    # Validate exact bundle serialization on evaluation inputs.
    reloaded = joblib.load(destination/'candidate.joblib')
    np.testing.assert_allclose(candidate.predict_feature_frame(evaluation), reloaded.predict_feature_frame(evaluation))
    result = {'task':task, 'selected_name':selected.name, 'target':target,
        'source_release':release.name, 'split':split_record(groups, split), 'selection':tuning,
        'calibration':cal_details, 'evaluation_metrics':metrics, 'paired_historical_audit_metrics':prior,
        'meets_numerical_target':target_pass(task, metrics), 'improves_paired_audit':bool(improved),
        'independent_external_test':False, 'deployed':False,
        'candidate_sha256':sha256(destination/'candidate.joblib'),
        'limitations':['Previously inspected development data; fixed outer split is not a new final test.',
            'Candidate is trained only on fitting groups; calibration and evaluation groups are not refitted.',
            'Confidence calibration metrics are fitting diagnostics; accepted evaluation results are separate.',
            'Temporal dependence and few independent batteries limit interval guarantees.']}
    if task == 'engine':
        official = add_causal_engine_features(load_test_with_rul('FD001'))
        official = official.loc[official.groupby('unit_id').cycle.idxmax()]
        check, predictions = evaluate(candidate, official, 'rul', False)
        result['official_test_regression_check'] = check
        result['official_test_target_pass'] = target_pass(task, check)
        predictions.to_csv(destination/'official_predictions.csv', index=False)
        result['official_check_note'] = 'Candidate fit uses fewer engines than deployed model; previously inspected official labels, not used for selection.'
    (destination/'evaluation.json').write_text(json.dumps(result, indent=2, allow_nan=False),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('task','selected_name','evaluation_metrics','meets_numerical_target','improves_paired_audit')}, indent=2),flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tasks', nargs='+', choices=TASKS, default=list(TASKS))
    parser.add_argument('--run-id', default='targeted-20260911')
    args = parser.parse_args()
    if not args.run_id or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in args.run_id):
        parser.error('run-id must contain lowercase letters, digits, and hyphens only')
    if len(set(args.tasks)) != len(args.tasks):
        parser.error('duplicate tasks are not allowed')
    release, manifest = verified_release()
    output = ROOT/'models/candidates'/args.run_id
    if any((output/task).exists() for task in args.tasks):
        parser.error('candidate outputs already exist; choose a new run-id')
    before = sha256(ROOT/'models/releases/current.json')
    results = {}
    with threadpool_limits(limits=2):
        for task in args.tasks:
            print(f'Starting {task}',flush=True)
            results[task] = run_task(task, output, release)
    if sha256(ROOT/'models/releases/current.json') != before:
        raise RuntimeError('Active release changed while experiment was running')
    verified_release()  # Hash-check every archived artifact, including excluded tasks.
    print('All requested candidates complete. Active release and excluded models remain unchanged.',flush=True)


if __name__ == '__main__':
    main()
