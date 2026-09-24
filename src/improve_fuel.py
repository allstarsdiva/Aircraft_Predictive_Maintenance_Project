"""Nested development evaluation for fuel anomaly improvements.

Outer test: one whole fault scenario plus one contiguous normal block. All
candidate selection happens inside the remaining scenarios and normal blocks.
Past development has inspected the dataset; this is not a new external test.
"""
from dataclasses import asdict, dataclass
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.data.fuel_system import load_fuel_system_dataset, FUEL_SENSOR_COLUMNS
from src.fuel_phase_modeling import FuelPhaseResidualBundle, FuelPhaseResidualDetector
from src.fuel_robust_modeling import FuelSteadyEnvelope, FuelSteadyEnvelopeBundle
from src.model_improvements import fuel_detection_metrics
from src.train_fuel import conservative_quantile
from src.model_release import sha256

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Candidate:
    aggregation: str
    smoothing: int
    consistency: bool
    quantile: float
    window: int
    required: int

    @property
    def name(self):
        return f'{self.aggregation}_s{self.smoothing}_c{int(self.consistency)}_q{self.quantile}_p{self.required}of{self.window}'


BASELINE = Candidate('phase_p75', 1, False, .975, 7, 4)
CANDIDATES = tuple(Candidate(agg, smooth, consistency, q, window, count)
    for agg in ('max', 'mahalanobis') for smooth in (1, 3) for consistency in (False, True)
    for q in (.95, .975, .99) for window, count in ((1, 1), (5, 3)))


def fit_bundle(normal_fit, normal_calibration, candidate):
    if normal_calibration['is_abnormal'].astype(bool).any():
        raise ValueError('Threshold calibration requires normal samples only')
    if candidate.aggregation == 'phase_p75':
        detector = FuelPhaseResidualDetector.fit(normal_fit, FUEL_SENSOR_COLUMNS, 'p75')
        bundle_type = FuelPhaseResidualBundle
    else:
        detector = FuelSteadyEnvelope.fit(normal_fit, candidate.aggregation, candidate.smoothing, candidate.consistency)
        bundle_type = FuelSteadyEnvelopeBundle
    threshold = conservative_quantile(detector.anomaly_score(normal_calibration), candidate.quantile)
    return bundle_type(detector, threshold, candidate.window, candidate.required,
                       1-candidate.quantile, {}, 'normal_fit_and_separate_block_calibration')


def predict_scenarios(bundle, frame):
    predictions = np.empty(len(frame), dtype=int)
    for scenario in frame.scenario_id.unique():
        indices = np.flatnonzero(frame.scenario_id.to_numpy() == scenario)
        predictions[indices] = bundle.predict_feature_frame(frame.iloc[indices])
    return predictions


def outer_plan(normal, fault_names):
    blocks = tuple(np.asarray(x) for x in np.array_split(np.arange(len(normal)), len(fault_names)))
    return blocks, [{'test_scenario': scenario, 'test_block': i,
                     'development_blocks': [j for j in range(len(blocks)) if j != i]}
                    for i, scenario in enumerate(fault_names)]


def tune_inside(normal, faults, blocks, available):
    """No outer scenario or normal test block is supplied to selection."""
    results = {}
    for candidate in CANDIDATES:
        normal_pred, normal_actual, abnormal_pred = [], [], []
        for position, validation in enumerate(available):
            calibration = available[(position + 1) % len(available)]
            training = [index for index in available if index not in (validation, calibration)]
            normal_fit = normal.iloc[np.concatenate([blocks[index] for index in training])]
            bundle = fit_bundle(normal_fit, normal.iloc[blocks[calibration]], candidate)
            validation_frame = normal.iloc[blocks[validation]]
            normal_pred.extend(bundle.predict_feature_frame(validation_frame).tolist())
            normal_actual.extend(validation_frame.sample_index.astype(int).tolist())
            abnormal_pred.append(predict_scenarios(bundle, faults))
        fpr = float(np.mean(normal_pred))
        detection = float(np.mean(abnormal_pred))
        balanced = .5 * (1-fpr+detection)
        results[candidate.name] = {'normal_false_alarm_rate': fpr, 'abnormal_detection_rate': detection,
            'balanced_accuracy': balanced, 'selection_score': balanced - 2*max(fpr-.10, 0),
            'normal_validation_positions': normal_actual}
    # Selection definition fixed before outer scoring; favor simplest candidate on ties.
    best = max(CANDIDATES, key=lambda c: results[c.name]['selection_score'])
    return best, results


def prediction_records(frame, predicted, baseline, fold):
    rows = frame.loc[:, ['scenario_id', 'sample_index', 'is_abnormal']].copy()
    rows['fold'] = fold
    rows['predicted'] = predicted
    rows['baseline_predicted'] = baseline
    return rows


def run():
    table = load_fuel_system_dataset()
    normal = table.loc[table.scenario_id == 'normal'].reset_index(drop=True)
    fault_names = tuple(sorted(set(table.scenario_id)-{'normal'}))
    faults = table.loc[table.scenario_id != 'normal'].reset_index(drop=True)
    blocks, plan = outer_plan(normal, fault_names)
    rows, folds = [], []
    for number, fold in enumerate(plan):
        scenario = fold['test_scenario']
        available = fold['development_blocks']
        dev_faults = faults.loc[faults.scenario_id != scenario].reset_index(drop=True)
        selected, tuning = tune_inside(normal, dev_faults, blocks, available)
        calibration = available[0]
        train_indices = np.concatenate([blocks[index] for index in available[1:]])
        fit = normal.iloc[train_indices]
        cal = normal.iloc[blocks[calibration]]
        bundle = fit_bundle(fit, cal, selected)
        baseline_bundle = fit_bundle(fit, cal, BASELINE)
        evaluation = pd.concat([normal.iloc[blocks[fold['test_block']]], faults.loc[faults.scenario_id == scenario]], ignore_index=True)
        predicted = predict_scenarios(bundle, evaluation)
        old = predict_scenarios(baseline_bundle, evaluation)
        rows.append(prediction_records(evaluation, predicted, old, number))
        folds.append({**fold, 'fit_normal_positions': fit.sample_index.astype(int).tolist(),
            'calibration_normal_positions': cal.sample_index.astype(int).tolist(),
            'test_normal_positions': normal.iloc[blocks[fold['test_block']]].sample_index.astype(int).tolist(),
            'tuning_scenarios': sorted(dev_faults.scenario_id.unique()),
            'selected_parameters': asdict(selected), 'selected_name': selected.name,
            'tuning_results': tuning, 'evaluation_metrics': fuel_detection_metrics(evaluation, predicted),
            'baseline_metrics': fuel_detection_metrics(evaluation, old)})
        print(f"Fold {number+1}: held out {scenario}; selected {selected.name}", flush=True)
    predictions = pd.concat(rows, ignore_index=True)
    if predictions.duplicated(['scenario_id', 'sample_index']).any() or len(predictions) != len(table):
        raise RuntimeError('Outer evaluation did not cover each dataset row exactly once')
    metrics = fuel_detection_metrics(predictions, predictions.predicted)
    baseline_metrics = fuel_detection_metrics(predictions, predictions.baseline_predicted)
    # Final hyperparameter selection uses all development scenarios, without looking
    # at outer fold scores. Reserve normal block 0 for final calibration thereafter.
    selected, final_tuning = tune_inside(normal, faults, blocks, list(range(len(blocks))))
    final_cal = blocks[0]
    final_fit = np.concatenate(blocks[1:])
    bundle = fit_bundle(normal.iloc[final_fit], normal.iloc[final_cal], selected)
    bundle.validation_metrics = {key: float(value) for key, value in metrics.items() if isinstance(value, (float, int))}
    bundle.validation_protocol = 'nested_leave_one_failure_scenario_out_with_contiguous_normal_blocks_and_separate_calibration'
    improvement = (metrics['balanced_accuracy'] > baseline_metrics['balanced_accuracy'] + .01
                   and metrics['normal_false_alarm_rate'] <= .10
                   and metrics['abnormal_detection_rate'] >= baseline_metrics['abnormal_detection_rate'])
    output = {'protocol': 'fuel-nested-development-v1', 'independent_external_test': False,
        'candidate_count': len(CANDIDATES), 'metrics': metrics, 'paired_baseline_metrics': baseline_metrics,
        'improves_paired_development_evaluation': improvement,
        'promotion_rule': 'Balanced accuracy improves by >1 point, false alarms <=10%, and sensitivity no worse than paired baseline.',
        'selected_parameters': asdict(selected), 'selected_name': selected.name,
        'final_fit_normal_positions': normal.iloc[final_fit].sample_index.astype(int).tolist(),
        'final_calibration_normal_positions': normal.iloc[final_cal].sample_index.astype(int).tolist(),
        'folds': folds, 'final_tuning': final_tuning,
        'readiness_gate': 'fail',
        'limitations': ['All source scenarios have influenced previous development; no fresh independent test.',
            'Only one normal trajectory; blocked rows cannot establish new-mission false-alarm performance.',
            'Labels identify complete abnormal scenarios; fault-onset timestamps are not supplied.',
            'Envelope monitors four steady sensors and optional consistency differences; other faults may be missed.',
            'Reported nested scores evaluate model selection across folds, not resubstitution accuracy of the final artifact.']}
    destination = ROOT / 'reports/metrics/fuel_nested'
    destination.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(destination / 'outer_predictions.csv', index=False)
    model_path = ROOT / 'models/candidates/fuel_steady_envelope_bundle.joblib'
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, model_path, compress=3)
    output['candidate_sha256'] = sha256(model_path)
    output['candidate_path'] = model_path.relative_to(ROOT).as_posix()
    # Descriptive final-artifact replay is separate from nested evaluation.
    replay = predict_scenarios(bundle, table)
    output['final_artifact_replay_not_validation'] = fuel_detection_metrics(table, replay)
    output['first_alert_sample_by_scenario_not_fault_onset'] = {
        scenario: (int(table.loc[(table.scenario_id == scenario) & (replay == 1), 'sample_index'].iloc[0])
                   if ((table.scenario_id == scenario) & (replay == 1)).any() else None)
        for scenario in fault_names}
    (destination / 'evaluation.json').write_text(json.dumps(output, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'candidate': selected.name, 'new': metrics, 'paired_baseline': baseline_metrics, 'improvement': improvement}, indent=2), flush=True)
    return output


if __name__ == '__main__':
    run()
