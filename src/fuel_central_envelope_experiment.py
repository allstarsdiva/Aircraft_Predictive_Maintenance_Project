"""Nested evaluation of a global normal-envelope specialist for CLF/CLV_S.

Unlike the rejected position-profile variant, this detector learns the central
line's normal robust range across its fitting rows. A separate normal block sets
the threshold. Results and any OR fusion remain research-only.
"""
from dataclasses import asdict, dataclass
import json

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

from src.data.fuel_system import load_fuel_system_dataset
from src.fuel_phase_modeling import causal_persistence
from src.fuel_robust_modeling import segments
from src.improve_fuel import outer_plan, predict_scenarios
from src.model_improvements import fuel_detection_metrics
from src.model_release import ROOT, sha256, verified_release
from src.train_fuel import conservative_quantile
from src.fuel_central_line_experiment import central_features

EXPERIMENT = 'fuel-central-envelope-nested-20260925'
AGGREGATIONS = ('max', 'mahalanobis')
SMOOTHING = (1, 3, 5)
QUANTILES = (0.90, 0.95, 0.975, 0.99)
PERSISTENCE = ((1, 1), (5, 3))


@dataclass(frozen=True)
class Candidate:
    aggregation: str
    smoothing: int
    quantile: float
    window: int
    required: int


CANDIDATES = tuple(Candidate(aggregation, smoothing, quantile, window, required)
    for aggregation in AGGREGATIONS for smoothing in SMOOTHING
    for quantile in QUANTILES for window, required in PERSISTENCE)


@dataclass
class CentralLineEnvelope:
    center: np.ndarray
    scale: np.ndarray
    precision: np.ndarray
    aggregation: str
    smoothing: int

    @classmethod
    def fit(cls, normal_fit, candidate):
        if 'is_abnormal' in normal_fit and normal_fit.is_abnormal.astype(bool).any():
            raise ValueError('Central-line envelope must fit normal rows only')
        values = central_features(normal_fit, candidate.smoothing)
        if len(values) < 12:
            raise ValueError('Central-line envelope requires at least twelve normal rows')
        center = np.median(values, axis=0)
        mad = np.median(np.abs(values - center), axis=0) * 1.4826
        scale = np.maximum(np.where(mad > 1e-9, mad, values.std(axis=0)), 1e-6)
        standardized = (values - center) / scale
        precision = LedoitWolf().fit(standardized).precision_
        return cls(center, scale, precision, candidate.aggregation, candidate.smoothing)

    def anomaly_score(self, frame):
        standardized = (central_features(frame, self.smoothing) - self.center) / self.scale
        if self.aggregation == 'max':
            return np.abs(standardized).max(axis=1)
        if self.aggregation == 'mahalanobis':
            quadratic = np.einsum('ij,jk,ik->i', standardized, self.precision, standardized)
            return np.sqrt(np.maximum(quadratic, 0))
        raise ValueError(f'Unknown central-line score aggregation: {self.aggregation}')


@dataclass
class Bundle:
    detector: CentralLineEnvelope
    threshold: float
    window: int
    required: int

    def predict_feature_frame(self, frame):
        raw = (self.detector.anomaly_score(frame) > self.threshold).astype(int)
        result = np.zeros(len(frame), dtype=int)
        for indices in segments(frame):
            result[indices] = causal_persistence(raw[indices], self.window, self.required)
        return result


def fit_bundle(normal_fit, calibration, candidate):
    if calibration.is_abnormal.astype(bool).any():
        raise ValueError('Central-line threshold calibration requires normal rows')
    detector = CentralLineEnvelope.fit(normal_fit, candidate)
    threshold = conservative_quantile(detector.anomaly_score(calibration), candidate.quantile)
    return Bundle(detector, threshold, candidate.window, candidate.required)


def tune_inside(normal, faults, blocks, available):
    results = []
    for candidate in CANDIDATES:
        normal_votes, fault_votes = [], []
        for position, validation in enumerate(available):
            calibration = available[(position + 1) % len(available)]
            fitting = [index for index in available if index not in (validation, calibration)]
            bundle = fit_bundle(normal.iloc[np.concatenate([blocks[index] for index in fitting])],
                                normal.iloc[blocks[calibration]], candidate)
            normal_votes.extend(bundle.predict_feature_frame(normal.iloc[blocks[validation]]).tolist())
            fault_votes.append(predict_scenarios(bundle, faults))
        fpr, recall = float(np.mean(normal_votes)), float(np.mean(fault_votes))
        balanced = 0.5 * (1 - fpr + recall)
        results.append({'parameters': asdict(candidate), 'normal_false_alarm_rate': fpr,
                        'abnormal_detection_rate': recall, 'balanced_accuracy': balanced,
                        'selection_score': balanced - 2 * max(fpr - 0.05, 0)})
    best = max(range(len(results)), key=lambda index: results[index]['selection_score'])
    return CANDIDATES[best], results


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
    names = tuple(sorted(set(table.scenario_id) - {'normal'}))
    blocks, plan = outer_plan(normal, names)
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
        evaluation = pd.concat([normal.iloc[blocks[fold['test_block']]],
            table.loc[table.scenario_id == scenario]], ignore_index=True)
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
        print(f'Global central-line fold {fold_number + 1}/4 complete: {asdict(selected)}', flush=True)

    predictions = pd.concat(prediction_rows, ignore_index=True)
    if len(predictions) != len(table) or predictions.duplicated(['scenario_id', 'sample_index']).any():
        raise ValueError('Central-line outer evaluation must cover every row exactly once')
    baseline = pd.read_csv(baseline_path)
    keys = ['scenario_id', 'sample_index', 'is_abnormal', 'fold']
    paired = predictions.merge(baseline[keys + ['predicted']], on=keys, how='outer',
        validate='one_to_one', suffixes=('', '_baseline'), indicator=True)
    if not (paired['_merge'] == 'both').all():
        raise ValueError('Central-line and retained predictions do not share exact rows/folds')
    specialist = fuel_detection_metrics(paired, paired.predicted)
    retained = fuel_detection_metrics(paired, paired.predicted_baseline)
    paired['combined_predicted'] = np.maximum(paired.predicted, paired.predicted_baseline)
    combined = fuel_detection_metrics(paired, paired.combined_predicted)
    no_worse = lambda candidate: {
        'balanced_accuracy': candidate['balanced_accuracy'] >= retained['balanced_accuracy'],
        'detection': candidate['abnormal_detection_rate'] >= retained['abnormal_detection_rate'],
        'false_alarms': candidate['normal_false_alarm_rate'] <= retained['normal_false_alarm_rate'],
    }
    report = {
        'protocol': EXPERIMENT, 'independent_external_test': False,
        'sensors': ['CLF', 'CLV_S'], 'candidate_count': len(CANDIDATES),
        'central_line_specialist_metrics': specialist,
        'retained_model_metrics': retained,
        'fixed_or_combination_metrics': combined,
        'strict_no_worse_than_retained': {
            'specialist': no_worse(specialist), 'or_combination': no_worse(combined)},
        'deployed': False, 'model_artifact_written': False,
        'folds': folds, 'protected_hashes': protected,
        'limitations': [
            'All five known scenario trajectories have influenced earlier development; this is not independent external validation.',
            'Scenario-level labels do not identify row-level fault onset or recovery.',
            'Only one normal trajectory is available, so independent-mission false-alarm performance is unknown.',
            'This global envelope assumes the central-line normal range is stable across operating conditions.',
        ],
    }
    destination.mkdir(parents=True, exist_ok=False)
    predictions.to_csv(destination / 'outer_predictions.csv', index=False)
    (destination / 'evaluation.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    paths = {'baseline_predictions': baseline_path, 'baseline_report': baseline_report_path,
             'champion': champion_path, 'release_pointer': release_pointer}
    for relative, expected in protected.items():
        path = paths[relative] if relative in paths else ROOT / relative
        if sha256(path) != expected:
            raise ValueError(f'Protected fuel source changed during experiment: {relative}')
    verified_release()
    print(json.dumps({key: report[key] for key in (
        'central_line_specialist_metrics', 'retained_model_metrics',
        'fixed_or_combination_metrics', 'strict_no_worse_than_retained', 'deployed')},
        indent=2), flush=True)
    return report


if __name__ == '__main__':
    run()
