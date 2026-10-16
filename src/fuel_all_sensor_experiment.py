"""Nested, non-deployed evaluation of an all-channel fuel anomaly envelope.

This experiment expands the normal-only robust envelope from four to all eight
sensor channels. It preserves the existing release and candidate artifacts.
Labels remain scenario-membership labels, not verified row-level fault states.
"""
from dataclasses import asdict, dataclass
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

from src.audit_finalization import snapshots
from src.data.fuel_system import FUEL_SENSOR_COLUMNS, load_fuel_system_dataset
from src.fuel_phase_modeling import causal_persistence
from src.improve_fuel import outer_plan, predict_scenarios
from src.model_improvements import fuel_detection_metrics
from src.model_release import ROOT, sha256, verified_release
from src.fuel_robust_modeling import segments
from src.train_fuel import conservative_quantile

EXPERIMENT = 'fuel-all-sensor-nested-20260925'
SMOOTHING_WINDOWS = (1, 3)
AGGREGATIONS = ('max', 'mahalanobis')
QUANTILES = (0.95, 0.975, 0.99)
PERSISTENCE = ((1, 1), (5, 3))


@dataclass(frozen=True)
class Candidate:
    aggregation: str
    smoothing: int
    quantile: float
    window: int
    required: int


CANDIDATES = tuple(Candidate(aggregation, smoothing, quantile, window, required)
    for aggregation in AGGREGATIONS for smoothing in SMOOTHING_WINDOWS
    for quantile in QUANTILES for window, required in PERSISTENCE)


def all_sensor_features(frame, smoothing):
    if smoothing not in SMOOTHING_WINDOWS:
        raise ValueError('Unsupported causal smoothing window')
    chunks = segments(frame)
    values = frame.loc[:, FUEL_SENSOR_COLUMNS].to_numpy(float).copy()
    if smoothing > 1:
        for indices in chunks:
            values[indices] = frame.iloc[indices].loc[:, FUEL_SENSOR_COLUMNS].rolling(
                smoothing, min_periods=1).median().to_numpy(float)
    if not np.isfinite(values).all():
        raise ValueError('All-channel fuel features must be finite')
    return values


@dataclass
class AllSensorEnvelope:
    center: np.ndarray
    scale: np.ndarray
    precision: np.ndarray
    aggregation: str
    smoothing: int

    @classmethod
    def fit(cls, normal, candidate):
        if 'is_abnormal' in normal and normal.is_abnormal.astype(bool).any():
            raise ValueError('All-channel envelope may fit normal rows only')
        values = all_sensor_features(normal, candidate.smoothing)
        if len(values) < 12:
            raise ValueError('At least twelve normal fitting rows are required')
        center = np.median(values, axis=0)
        mad = np.median(np.abs(values - center), axis=0) * 1.4826
        scale = np.maximum(np.where(mad > 1e-9, mad, values.std(axis=0)), 1e-6)
        standardized = (values - center) / scale
        precision = LedoitWolf().fit(standardized).precision_
        return cls(center, scale, precision, candidate.aggregation, candidate.smoothing)

    def anomaly_score(self, frame):
        standardized = (all_sensor_features(frame, self.smoothing) - self.center) / self.scale
        if self.aggregation == 'max':
            return np.abs(standardized).max(axis=1)
        if self.aggregation == 'mahalanobis':
            square = np.einsum('ij,jk,ik->i', standardized, self.precision, standardized)
            return np.sqrt(np.maximum(square, 0))
        raise ValueError(f'Unsupported aggregation: {self.aggregation}')


@dataclass
class AllSensorBundle:
    detector: AllSensorEnvelope
    threshold: float
    persistence_window: int
    persistence_required: int
    expected_false_alarm_rate: float
    validation_metrics: dict
    validation_protocol: str

    def predict_anomaly_score(self, frame):
        return self.detector.anomaly_score(frame) - self.threshold

    def predict_feature_frame(self, frame):
        raw = (self.predict_anomaly_score(frame) > 0).astype(int)
        result = np.zeros(len(frame), dtype=int)
        for indices in segments(frame):
            result[indices] = causal_persistence(
                raw[indices], self.persistence_window, self.persistence_required)
        return result


def fit_bundle(normal_fit, normal_calibration, candidate):
    if normal_calibration.is_abnormal.astype(bool).any():
        raise ValueError('Threshold calibration requires normal samples only')
    detector = AllSensorEnvelope.fit(normal_fit, candidate)
    threshold = conservative_quantile(detector.anomaly_score(normal_calibration), candidate.quantile)
    return AllSensorBundle(detector, threshold, candidate.window, candidate.required,
        1 - candidate.quantile, {}, 'all_sensor_nested_normal_fit_and_separate_calibration')


def tune_inside(normal, faults, blocks, available):
    results = {}
    for candidate in CANDIDATES:
        normal_predictions, fault_predictions = [], []
        for position, validation in enumerate(available):
            calibration = available[(position + 1) % len(available)]
            fitting = [index for index in available if index not in (validation, calibration)]
            normal_fit = normal.iloc[np.concatenate([blocks[index] for index in fitting])]
            bundle = fit_bundle(normal_fit, normal.iloc[blocks[calibration]], candidate)
            normal_predictions.extend(bundle.predict_feature_frame(normal.iloc[blocks[validation]]).tolist())
            fault_predictions.append(predict_scenarios(bundle, faults))
        false_alarm = float(np.mean(normal_predictions))
        detection = float(np.mean(fault_predictions))
        balanced = 0.5 * (1 - false_alarm + detection)
        results[asdict(candidate).__repr__()] = {
            'candidate': asdict(candidate), 'normal_false_alarm_rate': false_alarm,
            'abnormal_detection_rate': detection, 'balanced_accuracy': balanced,
            'selection_score': balanced - 2 * max(false_alarm - 0.10, 0),
        }
    best = max(results.values(), key=lambda result: result['selection_score'])
    return Candidate(**best['candidate']), results


def run():
    destination = ROOT / 'reports/metrics' / EXPERIMENT
    if destination.exists():
        raise FileExistsError(f'Preserving existing experiment output: {destination}')
    baseline_path = ROOT / 'reports/metrics/fuel_nested/outer_predictions.csv'
    baseline_report_path = ROOT / 'reports/metrics/fuel_nested/evaluation.json'
    champion_path = ROOT / 'models/candidates/fuel_steady_envelope_bundle.joblib'
    release_pointer = ROOT / 'models/releases/current.json'
    protected = {
        'baseline_predictions': sha256(baseline_path),
        'baseline_report': sha256(baseline_report_path),
        'champion': sha256(champion_path),
        'release_pointer': sha256(release_pointer),
    }
    table = load_fuel_system_dataset()
    source_hashes = {f'data/raw/fuel_system/{path.name}': sha256(path)
        for path in sorted((ROOT / 'data/raw/fuel_system').glob('Scenario_*.csv'))}
    if len(source_hashes) != 5:
        raise ValueError('Expected all five source fuel scenarios')
    protected.update(source_hashes)
    normal = table.loc[table.scenario_id == 'normal'].reset_index(drop=True)
    fault_names = tuple(sorted(set(table.scenario_id) - {'normal'}))
    blocks, plan = outer_plan(normal, fault_names)
    prediction_rows, folds = [], []
    for fold_number, fold in enumerate(plan):
        scenario = fold['test_scenario']
        available = fold['development_blocks']
        dev_faults = table.loc[(table.scenario_id != 'normal') &
                               (table.scenario_id != scenario)].reset_index(drop=True)
        selected, tuning = tune_inside(normal, dev_faults, blocks, available)
        calibration = available[0]
        fit_indices = np.concatenate([blocks[index] for index in available[1:]])
        bundle = fit_bundle(normal.iloc[fit_indices], normal.iloc[blocks[calibration]], selected)
        evaluation = pd.concat([
            normal.iloc[blocks[fold['test_block']]],
            table.loc[table.scenario_id == scenario],
        ], ignore_index=True)
        predicted = predict_scenarios(bundle, evaluation)
        rows = evaluation.loc[:, ['scenario_id', 'sample_index', 'is_abnormal']].copy()
        rows['fold'] = fold_number
        rows['predicted'] = predicted
        prediction_rows.append(rows)
        folds.append({**fold, 'selected_parameters': asdict(selected),
            'fit_normal_positions': normal.iloc[fit_indices].sample_index.astype(int).tolist(),
            'calibration_normal_positions': normal.iloc[blocks[calibration]].sample_index.astype(int).tolist(),
            'tuning_scenarios': sorted(dev_faults.scenario_id.unique()),
            'evaluation_metrics': fuel_detection_metrics(evaluation, predicted),
            'tuning_candidate_count': len(tuning)})
        print(f'All-sensor fold {fold_number + 1}/4 complete: {asdict(selected)}', flush=True)

    predictions = pd.concat(prediction_rows, ignore_index=True)
    if len(predictions) != len(table) or predictions.duplicated(['scenario_id', 'sample_index']).any():
        raise ValueError('All-sensor outer evaluation must cover each row exactly once')
    baseline = pd.read_csv(baseline_path)
    keys = ['scenario_id', 'sample_index', 'is_abnormal', 'fold']
    paired = predictions.merge(baseline[keys + ['predicted']], on=keys, how='outer',
        validate='one_to_one', suffixes=('', '_baseline'), indicator=True)
    if not (paired['_merge'] == 'both').all():
        raise ValueError('All-sensor and retained predictions do not share exact rows/folds')
    metrics = fuel_detection_metrics(paired, paired.predicted)
    previous_metrics = fuel_detection_metrics(paired, paired.predicted_baseline)
    strict_nonregression = {
        'accuracy_no_worse': metrics['accuracy'] >= previous_metrics['accuracy'],
        'balanced_accuracy_no_worse': metrics['balanced_accuracy'] >= previous_metrics['balanced_accuracy'],
        'macro_f1_no_worse': metrics['macro_f1'] >= previous_metrics['macro_f1'],
        'detection_no_worse': metrics['abnormal_detection_rate'] >= previous_metrics['abnormal_detection_rate'],
        'false_alarm_no_worse': metrics['normal_false_alarm_rate'] <= previous_metrics['normal_false_alarm_rate'],
    }
    report = {
        'protocol': EXPERIMENT, 'independent_external_test': False,
        'sensor_columns_used': list(FUEL_SENSOR_COLUMNS), 'candidate_count': len(CANDIDATES),
        'metrics': metrics, 'paired_retained_model_metrics': previous_metrics,
        'strict_nonregression_checks': strict_nonregression,
        'eligible_to_replace_research_champion': all(strict_nonregression.values()),
        'deployed': False, 'model_artifact_written': False,
        'folds': folds, 'protected_hashes': protected,
        'limitations': [
            'This is nested development evaluation on the same five known scenario trajectories, not independent validation.',
            'Scenario-level abnormal labels do not reveal row-level fault onset or recovery.',
            'The only normal trajectory cannot establish false-alarm performance across independent missions.',
            'All eight sensor channels are included; the published CSVs do not provide sampling interval or field units for all sensors.',
        ],
    }
    destination.mkdir(parents=True, exist_ok=False)
    predictions.to_csv(destination / 'outer_predictions.csv', index=False)
    (destination / 'evaluation.json').write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    for relative, expected in protected.items():
        path = ROOT / relative if relative.startswith('data/') else {
            'baseline_predictions': baseline_path,
            'baseline_report': baseline_report_path,
            'champion': champion_path,
            'release_pointer': release_pointer,
        }.get(relative)
        if relative.startswith('data/'):
            path = ROOT / relative
        if sha256(path) != expected:
            raise ValueError(f'Protected fuel source changed during experiment: {relative}')
    verified_release()
    print(json.dumps({key: report[key] for key in (
        'metrics', 'paired_retained_model_metrics', 'strict_nonregression_checks',
        'eligible_to_replace_research_champion', 'deployed')}, indent=2), flush=True)
    return report


if __name__ == '__main__':
    run()
