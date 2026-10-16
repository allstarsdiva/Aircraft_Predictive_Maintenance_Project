"""Nested research experiment for central fuel-line anomaly detection.

The specialist monitors CLF/CLV_S against a normal, mission-position profile.
It is evaluated both alone and as a fixed OR-alert lane beside the current fuel
detector. It never updates or deploys the active model.
"""
from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.fuel_system import load_fuel_system_dataset
from src.fuel_phase_modeling import causal_persistence
from src.fuel_robust_modeling import segments
from src.improve_fuel import outer_plan, predict_scenarios
from src.model_improvements import fuel_detection_metrics
from src.model_release import ROOT, sha256, verified_release
from src.train_fuel import conservative_quantile

EXPERIMENT = 'fuel-central-line-nested-20260925'
SENSORS = ('CLF', 'CLV_S')
SMOOTHING = (1, 3, 5)
QUANTILES = (0.90, 0.95, 0.975, 0.99)
PERSISTENCE = ((1, 1), (5, 3))


@dataclass(frozen=True)
class Candidate:
    smoothing: int
    quantile: float
    window: int
    required: int


CANDIDATES = tuple(Candidate(smoothing, quantile, window, required)
    for smoothing in SMOOTHING for quantile in QUANTILES
    for window, required in PERSISTENCE)


def central_features(frame, smoothing):
    if smoothing not in SMOOTHING:
        raise ValueError('Unsupported central-line smoothing window')
    missing = set(SENSORS).difference(frame.columns)
    if missing:
        raise ValueError(f'Missing central-line sensor(s): {sorted(missing)}')
    chunks = segments(frame)
    values = frame.loc[:, SENSORS].to_numpy(float).copy()
    if smoothing > 1:
        for indices in chunks:
            values[indices] = frame.iloc[indices].loc[:, SENSORS].rolling(
                smoothing, min_periods=1).median().to_numpy(float)
    if not np.isfinite(values).all():
        raise ValueError('Central-line sensor values must be finite')
    return values


@dataclass
class CentralLineProfile:
    positions: np.ndarray
    expected_values: np.ndarray
    scales: np.ndarray
    smoothing: int

    @classmethod
    def fit(cls, normal_fit, candidate):
        if 'is_abnormal' in normal_fit and normal_fit.is_abnormal.astype(bool).any():
            raise ValueError('Central-line profile must be fit using normal rows only')
        positions = normal_fit.sample_index.to_numpy(float)
        values = central_features(normal_fit, candidate.smoothing)
        order = np.argsort(positions)
        positions, values = positions[order], values[order]
        if len(positions) < 12 or len(np.unique(positions)) != len(positions):
            raise ValueError('Central-line normal profile requires >=12 unique positions')

        # Estimate sensor noise from adjacent normal observations; the separate
        # calibration block sets the alert threshold, not these feature scales.
        adjacent = np.diff(positions) == 1
        differences = np.diff(values, axis=0)[adjacent]
        scales = np.empty(values.shape[1], dtype=float)
        for column in range(values.shape[1]):
            sample = differences[:, column]
            if sample.size:
                median = np.median(sample)
                noise = np.median(np.abs(sample - median)) * 1.4826 / np.sqrt(2.0)
            else:
                noise = 0.0
            # A small scale floor prevents a single quantized sensor step from
            # creating an infinite score; calibration still controls alerts.
            scales[column] = max(float(noise), 1e-3)
        return cls(positions, values, scales, candidate.smoothing)

    def anomaly_score(self, frame):
        observed = central_features(frame, self.smoothing)
        positions = frame.sample_index.to_numpy(float)
        expected = np.column_stack([
            np.interp(positions, self.positions, self.expected_values[:, column])
            for column in range(len(SENSORS))
        ])
        residual = np.abs(observed - expected) / self.scales
        return residual.max(axis=1)


@dataclass
class CentralLineBundle:
    profile: CentralLineProfile
    threshold: float
    persistence_window: int
    persistence_required: int
    expected_false_alarm_rate: float
    validation_protocol: str = 'central_line_normal_fit_separate_block_calibration'

    def predict_anomaly_score(self, frame):
        return self.profile.anomaly_score(frame) - self.threshold

    def predict_feature_frame(self, frame):
        raw = (self.predict_anomaly_score(frame) > 0).astype(int)
        result = np.zeros(len(frame), dtype=int)
        for indices in segments(frame):
            result[indices] = causal_persistence(
                raw[indices], self.persistence_window, self.persistence_required)
        return result


def fit_bundle(normal_fit, normal_calibration, candidate):
    if normal_calibration.is_abnormal.astype(bool).any():
        raise ValueError('Central-line threshold must use normal calibration only')
    profile = CentralLineProfile.fit(normal_fit, candidate)
    threshold = conservative_quantile(
        profile.anomaly_score(normal_calibration), candidate.quantile)
    return CentralLineBundle(profile, threshold, candidate.window, candidate.required,
                             1 - candidate.quantile)


def tune_inside(normal, faults, blocks, available):
    results = []
    for candidate in CANDIDATES:
        normal_votes, fault_votes = [], []
        for position, validation in enumerate(available):
            calibration = available[(position + 1) % len(available)]
            fitting = [index for index in available if index not in (validation, calibration)]
            bundle = fit_bundle(
                normal.iloc[np.concatenate([blocks[index] for index in fitting])],
                normal.iloc[blocks[calibration]], candidate)
            normal_votes.extend(bundle.predict_feature_frame(normal.iloc[blocks[validation]]).tolist())
            fault_votes.append(predict_scenarios(bundle, faults))
        false_alarm = float(np.mean(normal_votes))
        detection = float(np.mean(fault_votes))
        balanced = 0.5 * (1 - false_alarm + detection)
        results.append({
            'parameters': asdict(candidate), 'normal_false_alarm_rate': false_alarm,
            'abnormal_detection_rate': detection, 'balanced_accuracy': balanced,
            'selection_score': balanced - 2 * max(false_alarm - 0.05, 0),
        })
    best = max(range(len(CANDIDATES)), key=lambda index: results[index]['selection_score'])
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
        print(f'Central-line fold {fold_number + 1}/4 complete: {asdict(selected)}', flush=True)

    predictions = pd.concat(prediction_rows, ignore_index=True)
    if len(predictions) != len(table) or predictions.duplicated(['scenario_id', 'sample_index']).any():
        raise ValueError('Central-line outer evaluation must cover every row exactly once')
    baseline = pd.read_csv(baseline_path)
    keys = ['scenario_id', 'sample_index', 'is_abnormal', 'fold']
    paired = predictions.merge(baseline[keys + ['predicted']], on=keys, how='outer',
        validate='one_to_one', suffixes=('', '_baseline'), indicator=True)
    if not (paired['_merge'] == 'both').all():
        raise ValueError('Central-line and retained predictions do not share exact rows/folds')
    standalone = fuel_detection_metrics(paired, paired.predicted)
    current = fuel_detection_metrics(paired, paired.predicted_baseline)
    paired['combined_predicted'] = np.maximum(paired.predicted, paired.predicted_baseline)
    combined = fuel_detection_metrics(paired, paired.combined_predicted)
    report = {
        'protocol': EXPERIMENT, 'independent_external_test': False,
        'sensors': list(SENSORS), 'candidate_count': len(CANDIDATES),
        'central_line_specialist_metrics': standalone,
        'retained_model_metrics': current,
        'fixed_or_combination_metrics': combined,
        'strict_no_worse_than_retained': {
            'specialist': {
                'balanced_accuracy': standalone['balanced_accuracy'] >= current['balanced_accuracy'],
                'detection': standalone['abnormal_detection_rate'] >= current['abnormal_detection_rate'],
                'false_alarms': standalone['normal_false_alarm_rate'] <= current['normal_false_alarm_rate'],
            },
            'or_combination': {
                'balanced_accuracy': combined['balanced_accuracy'] >= current['balanced_accuracy'],
                'detection': combined['abnormal_detection_rate'] >= current['abnormal_detection_rate'],
                'false_alarms': combined['normal_false_alarm_rate'] <= current['normal_false_alarm_rate'],
            },
        },
        'deployed': False, 'model_artifact_written': False,
        'folds': folds,
        'protected_hashes': protected,
        'limitations': [
            'All five known scenario trajectories have influenced prior development; this is not external validation.',
            'Scenario-level abnormal labels do not establish row-level fault onset or recovery.',
            'The only normal trajectory cannot establish false-alarm performance across independent missions.',
            'The position-aligned profile assumes sample order is comparable across missions; the sample interval is unknown.',
        ],
    }
    destination.mkdir(parents=True, exist_ok=False)
    predictions.to_csv(destination / 'outer_predictions.csv', index=False)
    (destination / 'evaluation.json').write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    paths = {
        'baseline_predictions': baseline_path, 'baseline_report': baseline_report_path,
        'champion': champion_path, 'release_pointer': release_pointer,
    }
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
