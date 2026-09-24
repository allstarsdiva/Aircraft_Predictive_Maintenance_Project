"""Freeze and enforce a full-trajectory, unit/phase-balanced selection protocol."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.model_release import sha256
from src.targeted_retraining import ROOT

PROTOCOL = 'reports/protocols/engine_full_trajectory_v1_20260915.json'
REFERENCE = 'reports/metrics/rul_fitting_diagnostics_20260914/engine_oof.csv'
DIAGNOSTIC = 'reports/metrics/rul_fitting_diagnostics_20260914/diagnostics.json'
PHASES = ('early', 'middle', 'late')


def aligned_predictions(candidate, reference):
    required = {'unit', 'cycle', 'fold', 'predicted'}
    if not required.issubset(candidate) or not (required | {'actual'}).issubset(reference):
        raise ValueError('Complete unit/cycle/fold/prediction evidence required')
    frames = []
    for original in (candidate, reference):
        frame = original.copy()
        if frame.empty or frame.unit.isna().any():
            raise ValueError('Nonempty evidence and nonmissing units required')
        frame['unit'] = frame.unit.astype(str)
        columns = ['cycle', 'fold', 'predicted'] + (['actual'] if 'actual' in frame else [])
        if frame.unit.isna().any() or not np.isfinite(frame[columns].to_numpy(float)).all():
            raise ValueError('Finite evidence required')
        if (frame.cycle <= 0).any() or (frame.predicted < 0).any():
            raise ValueError('Positive cycles and nonnegative predictions required')
        if frame.duplicated(['unit', 'cycle']).any():
            raise ValueError('Duplicate prediction rows')
        frames.append(frame.sort_values(['unit', 'cycle']).reset_index(drop=True))
    current, baseline = frames
    if len(current) != len(baseline) or not current[['unit', 'cycle', 'fold']].equals(baseline[['unit', 'cycle', 'fold']]):
        # Numeric CSV representations may use integer versus float cycle columns.
        if len(current) != len(baseline) or current.unit.tolist() != baseline.unit.tolist() or not np.array_equal(
                current[['cycle', 'fold']].to_numpy(), baseline[['cycle', 'fold']].to_numpy()):
            raise ValueError('Missing/extra rows, units, or changed fold assignments')
    if 'actual' in current and not np.array_equal(current.actual.to_numpy(), baseline.actual.to_numpy()):
        raise ValueError('Evaluation labels changed')
    if (baseline.actual < 0).any():
        raise ValueError('Nonnegative original labels required')
    baseline['predicted'] = current.predicted.to_numpy(float)
    return baseline


def score_predictions(frame):
    if frame.empty:
        raise ValueError('Nonempty full-trajectory evidence required')
    data = frame.copy()
    fraction = data.cycle / (data.cycle + data.actual)
    data['phase'] = np.select([fraction <= 1/3, fraction <= 2/3], ['early', 'middle'], default='late')
    data['error'] = data.predicted - data.actual
    grouped = data.groupby('unit')
    phase = {}
    for name in PHASES:
        subset = data.loc[data.phase == name]
        if set(subset.unit) != set(data.unit):
            raise ValueError('Every fitting unit must contribute all three phases')
        errors = subset.groupby('unit').error
        phase[name] = {'unit_mean_mae': float(errors.apply(lambda x: np.abs(x).mean()).mean()),
                       'unit_mean_rmse': float(errors.apply(lambda x: np.sqrt(np.mean(x ** 2))).mean())}
    unit_mae = grouped.error.apply(lambda x: np.abs(x).mean())
    near = data.loc[data.actual <= 30].groupby('unit').error
    return {'rows': len(data), 'units': int(data.unit.nunique()), 'phase_metrics': phase,
            'balanced_phase_mae': float(np.mean([phase[name]['unit_mean_mae'] for name in PHASES])),
            'unit_mean_mae': float(unit_mae.mean()),
            'unit_mean_rmse': float(grouped.error.apply(lambda x: np.sqrt(np.mean(x ** 2))).mean()),
            'worst_unit_mae': float(unit_mae.max()),
            'near_failure_unit_mae': float(near.apply(lambda x: np.abs(x).mean()).mean()),
            'near_failure_over_by_10_rate': float(near.apply(lambda x: (x > 10).mean()).mean())}


def compare_candidate(candidate, reference):
    aligned = aligned_predictions(candidate, reference)
    baseline = score_predictions(aligned_predictions(reference, reference))
    current = score_predictions(aligned)
    checks = {'balanced_phase_mae_improves_1pct': current['balanced_phase_mae'] <= .99 * baseline['balanced_phase_mae']
              and current['balanced_phase_mae'] < baseline['balanced_phase_mae'] - 1e-10}
    for key in ('unit_mean_mae', 'unit_mean_rmse', 'worst_unit_mae', 'near_failure_unit_mae', 'near_failure_over_by_10_rate'):
        checks[f'{key}_no_worse'] = current[key] <= baseline[key] + 1e-10
    for phase in PHASES:
        for metric in ('unit_mean_mae', 'unit_mean_rmse'):
            checks[f'{phase}_{metric}_no_worse'] = current['phase_metrics'][phase][metric] <= baseline['phase_metrics'][phase][metric] + 1e-10
    checks = {key: bool(value) for key, value in checks.items()}
    return {'baseline': baseline, 'candidate': current, 'checks': checks,
            'eligible_for_outer_checks': all(checks.values()), 'deployed': False,
            'outer_audit_official_and_uncertainty_gates_still_required': True}


def freeze():
    destination = ROOT / PROTOCOL
    seal = destination.with_suffix('.sha256')
    if destination.exists() or seal.exists():
        raise FileExistsError('Protocol is frozen; create a separately versioned protocol to revise it')
    evidence = json.loads((ROOT / DIAGNOSTIC).read_text())
    expected = evidence['tasks']['engine']['oof_sha256']
    if sha256(ROOT / REFERENCE) != expected:
        raise ValueError('Baseline prediction evidence changed')
    for relative, digest in evidence['sources'].items():
        if sha256(ROOT / relative) != digest:
            raise ValueError('Protected source/model changed')
    reference = pd.read_csv(ROOT / REFERENCE, float_precision='round_trip', dtype={'unit': str})
    specification = {'version': 1, 'date': '2026-09-15', 'scope': 'Inner fitting-only candidate selection; not aircraft readiness.',
        'reference': REFERENCE, 'reference_sha256': expected, 'diagnostic_sha256': sha256(ROOT / DIAGNOSTIC),
        'scorer_sha256': sha256(Path(__file__)),
        'fitting_units': evidence['tasks']['engine']['fitting_units'], 'folds': evidence['tasks']['engine']['folds'],
        'coverage': 'Every recorded cycle of every fitting unit, including the earliest cycles; no row exclusions.',
        'weighting': 'Equal weight to each unit within each phase, then equal one-third weight to each phase.',
        'phase_definition': 'cycle/(cycle+true_RUL): <=1/3 early, <=2/3 middle, otherwise late; scoring only, never predictors.',
        'selection': 'At least 1% better balanced-phase MAE; no regression in overall, worst-unit, any phase MAE/RMSE, or near-failure measures.',
        'required_after_selection': 'Existing fixed audit, official FD001, and uncertainty non-regression gates; fresh independent validation before readiness claims.',
        'score_does_not_prove_training_lineage': True,
        'baseline': score_predictions(aligned_predictions(reference, reference)),
        'champion_replaced': False, 'hyperparameter_search_performed': False}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(specification, stream, indent=2, allow_nan=False)
    with seal.open('x', encoding='ascii') as stream:
        stream.write(sha256(destination) + '\n')
    print(json.dumps({'frozen_protocol': PROTOCOL, 'baseline': specification['baseline']}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--freeze', action='store_true')
    actions.add_argument('--candidate', type=Path, help='Complete fitting-only OOF CSV; never official or outer-audit predictions')
    args = parser.parse_args()
    if args.freeze:
        freeze()
        return
    destination = ROOT / PROTOCOL
    if sha256(destination) != destination.with_suffix('.sha256').read_text().strip():
        raise ValueError('Frozen protocol checksum mismatch')
    specification = json.loads(destination.read_text())
    if sha256(Path(__file__)) != specification['scorer_sha256']:
        raise ValueError('Scoring implementation changed since protocol freeze')
    if sha256(ROOT / specification['reference']) != specification['reference_sha256']:
        raise ValueError('Frozen baseline predictions changed')
    reference = pd.read_csv(ROOT / specification['reference'], float_precision='round_trip', dtype={'unit': str})
    candidate = pd.read_csv(args.candidate, float_precision='round_trip', dtype={'unit': str})
    print(json.dumps(compare_candidate(candidate, reference), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
