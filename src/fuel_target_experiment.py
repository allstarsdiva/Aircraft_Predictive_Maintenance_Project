"""Non-deployed, nested temporal experiment for the fuel accuracy target.

Reuses previously inspected development data: never an independent final test.
Run: python -m src.fuel_target_experiment
"""
from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.fuel_system import FUEL_SENSOR_COLUMNS, load_fuel_system_dataset
from src.fuel_robust_modeling import FuelSteadyEnvelope, FuelSteadyEnvelopeBundle, segments
from src.improve_fuel import outer_plan, predict_scenarios
from src.model_improvements import fuel_detection_metrics
from src.model_release import sha256
from src.train_fuel import conservative_quantile

ROOT = Path(__file__).resolve().parents[1]


def trailing_mean(frame, window):
    """Causal means reset at gaps and scenario boundaries; no IDs as features."""
    if window not in (5, 9, 15):
        raise ValueError('Supported temporal windows are 5, 9, and 15')
    chunks = segments(frame)
    result = frame.copy().reset_index(drop=True)
    columns = result.columns.get_indexer(FUEL_SENSOR_COLUMNS)
    for indices in chunks:
        result.iloc[indices, columns] = (
            frame.iloc[indices].loc[:, FUEL_SENSOR_COLUMNS]
            .rolling(window, min_periods=1).mean().to_numpy())
    return result


@dataclass(frozen=True)
class TemporalCandidate:
    aggregation: str
    window: int
    consistency: bool
    quantile: float


# Fixed before outer evaluation. Do not expand based on outer test results.
CANDIDATES = tuple(TemporalCandidate(aggregation, window, consistency, quantile)
    for aggregation in ('max', 'mahalanobis') for window in (5, 9, 15)
    for consistency in (False, True) for quantile in (.95, .975, .99))


@dataclass
class TemporalDetector:
    envelope: FuelSteadyEnvelope
    window: int
    feature_columns: tuple = FUEL_SENSOR_COLUMNS

    def anomaly_score(self, frame):
        return self.envelope.anomaly_score(trailing_mean(frame, self.window))


def fit_temporal(normal_fit, calibration, candidate):
    if calibration['is_abnormal'].astype(bool).any():
        raise ValueError('Threshold calibration requires normal samples only')
    envelope = FuelSteadyEnvelope.fit(trailing_mean(normal_fit, candidate.window),
        candidate.aggregation, 1, candidate.consistency)
    detector = TemporalDetector(envelope, candidate.window)
    threshold = conservative_quantile(detector.anomaly_score(calibration), candidate.quantile)
    return FuelSteadyEnvelopeBundle(detector, threshold, 1, 1,
        1-candidate.quantile, {}, 'temporal_nested_development_only')


def select_temporal(normal, faults, blocks, available, candidates=CANDIDATES):
    results = []
    for candidate in candidates:
        normal_predictions, fault_predictions = [], []
        for position, validation in enumerate(available):
            calibration = available[(position+1) % len(available)]
            fitting = [index for index in available if index not in (validation, calibration)]
            bundle = fit_temporal(normal.iloc[np.concatenate([blocks[i] for i in fitting])],
                                  normal.iloc[blocks[calibration]], candidate)
            normal_predictions.extend(bundle.predict_feature_frame(normal.iloc[blocks[validation]]))
            fault_predictions.extend(predict_scenarios(bundle, faults))
        fpr = float(np.mean(normal_predictions))
        recall = float(np.mean(fault_predictions))
        balanced = .5*(1-fpr+recall)
        results.append({'parameters': asdict(candidate), 'balanced_accuracy': balanced,
            'normal_false_alarm_rate': fpr, 'abnormal_detection_rate': recall,
            'selection_score': balanced-2*max(fpr-.10, 0)})
    best = max(range(len(candidates)), key=lambda i: results[i]['selection_score'])
    return candidates[best], results


def run():
    table = load_fuel_system_dataset()
    normal = table.loc[table.scenario_id == 'normal'].reset_index(drop=True)
    faults = table.loc[table.scenario_id != 'normal'].reset_index(drop=True)
    blocks, plan = outer_plan(normal, tuple(sorted(faults.scenario_id.unique())))
    rows, folds = [], []
    for number, fold in enumerate(plan):
        available = fold['development_blocks']
        development_faults = faults.loc[faults.scenario_id != fold['test_scenario']]
        selected, tuning = select_temporal(normal, development_faults, blocks, available)
        bundle = fit_temporal(normal.iloc[np.concatenate([blocks[i] for i in available[1:]])],
                              normal.iloc[blocks[available[0]]], selected)
        evaluation = pd.concat([normal.iloc[blocks[fold['test_block']]],
            faults.loc[faults.scenario_id == fold['test_scenario']]], ignore_index=True)
        record = evaluation.loc[:, ['scenario_id', 'sample_index', 'is_abnormal']].copy()
        record['fold'] = number
        record['predicted'] = predict_scenarios(bundle, evaluation)
        rows.append(record)
        folds.append({**fold, 'selected_parameters': asdict(selected), 'tuning': tuning,
            'fit_normal_positions': normal.iloc[np.concatenate([blocks[i] for i in available[1:]])].sample_index.tolist(),
            'calibration_normal_positions': normal.iloc[blocks[available[0]]].sample_index.tolist(),
            'test_normal_positions': normal.iloc[blocks[fold['test_block']]].sample_index.tolist(),
            'tuning_scenarios': sorted(development_faults.scenario_id.unique())})
        print(f'Temporal fold {number+1}/4 complete: {selected}', flush=True)
    predictions = pd.concat(rows, ignore_index=True)
    if len(predictions) != len(table) or predictions.duplicated(['scenario_id', 'sample_index']).any():
        raise RuntimeError('Every row must be evaluated exactly once')
    baseline_path = ROOT / 'reports/metrics/fuel_nested/outer_predictions.csv'
    baseline = pd.read_csv(baseline_path)
    keys = ['scenario_id', 'sample_index', 'is_abnormal', 'fold']
    paired = predictions.merge(baseline[keys+['predicted']], on=keys,
        how='outer', validate='one_to_one', suffixes=('', '_previous'), indicator=True)
    if not (paired['_merge'] == 'both').all():
        raise RuntimeError('Baseline and temporal evaluation rows/folds must match')
    metrics = fuel_detection_metrics(paired, paired.predicted)
    previous = fuel_detection_metrics(paired, paired.predicted_previous)
    # Descriptive audit of the SAME development errors, not new validation.
    paired['trajectory_third_not_fault_phase'] = pd.cut(paired.sample_index,
        bins=[0, 57, 114, 171], labels=['first', 'middle', 'last'])
    error_audit = []
    for (scenario, third), group in paired.groupby(['scenario_id', 'trajectory_third_not_fault_phase'], observed=True):
        error_audit.append({'scenario_id': scenario, 'trajectory_third_not_fault_phase': str(third),
            'rows': len(group), 'temporal_alert_rate': float(group.predicted.mean()),
            'previous_alert_rate': float(group.predicted_previous.mean())})
    abnormal_fraction = float(table.is_abnormal.mean())
    output = {'protocol': 'fuel-temporal-nested-development-v1', 'independent_external_test': False,
        'candidate_count': len(CANDIDATES), 'metrics': metrics, 'paired_previous_metrics': previous,
        'baseline_predictions_sha256': sha256(baseline_path), 'folds': folds,
        'target': {'accuracy_strictly_above': .90, 'normal_false_alarm_rate_at_most': .05,
            'balanced_accuracy_at_least': .90,
            'all_abnormal_baseline_accuracy': abnormal_fraction,
            'detection_rate_required_for_90_accuracy_at_5_percent_fpr':
                (.90-(1-abnormal_fraction)*.95)/abnormal_fraction},
        'meets_development_target': metrics['accuracy'] > .90 and metrics['balanced_accuracy'] >= .90
            and metrics['normal_false_alarm_rate'] <= .05,
        'improves_previous_development': metrics['balanced_accuracy'] > previous['balanced_accuracy']+.01
            and metrics['normal_false_alarm_rate'] <= .10
            and metrics['abnormal_detection_rate'] >= previous['abnormal_detection_rate'],
        'deployed': False, 'error_audit': error_audit,
        'limitations': ['Repeatedly inspected development data; not external validation.',
            'One normal trajectory cannot establish new-mission false alarms.',
            'Scenario labels do not establish row-level fault onset; no labels were changed.',
            'Windows use sample counts, not seconds; sample interval is unknown.',
            'Longer smoothing can delay abrupt-fault alerts; delay needs verified onset labels.']}
    destination = ROOT / 'reports/metrics/fuel_target_experiment'
    destination.mkdir(parents=True, exist_ok=True)
    paired.to_csv(destination / 'outer_predictions.csv', index=False)
    (destination / 'evaluation.json').write_text(json.dumps(output, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({k: output[k] for k in ('metrics', 'paired_previous_metrics',
        'meets_development_target', 'improves_previous_development', 'deployed')}, indent=2), flush=True)
    return output


if __name__ == '__main__':
    run()
