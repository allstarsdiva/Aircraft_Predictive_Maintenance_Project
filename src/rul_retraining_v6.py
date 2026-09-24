"""Bounded, full-trajectory protected RUL experiment. Never deploys models."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from threadpoolctl import threadpool_limits

from src import engine_validation_protocol as engine_protocol
from src.model_release import sha256, verified_release
from src.rul_fitting_diagnostics import grouped_oof
from src.rul_retraining_v2 import run, replay, TASKS
from src.rul_retraining_v5 import (
    PREVIOUS, protect_champion, verify_champions, nonregression_gate,
    safe_inner_selection, retained_status,
)
from src.targeted_retraining import ROOT, Candidate

EXPERIMENT = 'rul-protected-v6-20260915'
SEED = 20260915
ENGINE_SETTINGS = ((200., 15, 5.), (225., 15, 5.), (None, 15, 5.),
                   (200., 7, 15.), (225., 7, 15.))
BATTERY_SETTINGS = (('extra', 2, .5), ('extra', 3, .6), ('extra', 5, .8),
                    ('forest', 2, .6), ('forest', 4, .8))


def candidate_grid(task, table, previous):
    if task not in TASKS:
        raise ValueError('Only engine and battery RUL are authorized')
    features = tuple(previous.feature_columns)
    grid = [Candidate('previous_candidate_spec', clone(previous.model), features, previous.target_maximum)]
    if task == 'engine':
        for cap, leaves, regularization in ENGINE_SETTINGS:
            model = clone(previous.model).set_params(max_leaf_nodes=leaves, l2_regularization=regularization)
            grid.append(Candidate(f'hist_cap{cap}_leaves{leaves}_l2{regularization}', model, features, cap))
    else:
        for kind, leaf, fraction in BATTERY_SETTINGS:
            estimator = ExtraTreesRegressor if kind == 'extra' else RandomForestRegressor
            model = estimator(n_estimators=400, min_samples_leaf=leaf, max_features=fraction,
                              n_jobs=2, random_state=SEED)
            grid.append(Candidate(f'{kind}_leaf{leaf}_features{fraction}', model, features, previous.target_maximum))
    if any(set(c.features) - set(table.columns) for c in grid):
        raise ValueError('Missing retained-model features')
    return grid


def load_frozen_reference():
    path = ROOT / engine_protocol.PROTOCOL
    if sha256(path) != path.with_suffix('.sha256').read_text().strip():
        raise ValueError('Frozen protocol seal mismatch')
    protocol = json.loads(path.read_text())
    if sha256(Path(engine_protocol.__file__)) != protocol['scorer_sha256']:
        raise ValueError('Frozen scorer changed')
    if sha256(ROOT / engine_protocol.DIAGNOSTIC) != protocol['diagnostic_sha256']:
        raise ValueError('Diagnostic evidence changed')
    if sha256(ROOT / protocol['reference']) != protocol['reference_sha256']:
        raise ValueError('Frozen OOF evidence changed')
    return protocol, pd.read_csv(ROOT / protocol['reference'], dtype={'unit': str}, float_precision='round_trip')


def choose_engine(candidates, scores):
    if not candidates or candidates[0].name != 'previous_candidate_spec' or len(candidates) != len(scores):
        raise ValueError('Matching candidates and baseline-first scores required')
    eligible = [0] + [i for i, score in enumerate(scores) if i and score['inner_eligible']]
    return min(eligible, key=lambda i: scores[i]['selection_loss'])


def selector_for(output):
    def select(task, fit, groups, target, candidates, *, fit_function=None):
        if task == 'battery_rul':
            return safe_inner_selection(task, fit, groups, target, candidates, fit_function=fit_function)
        if task != 'engine':
            raise ValueError('Unauthorized task')
        protocol, reference = load_frozen_reference()
        if sorted(fit.unit_id.astype(str).unique()) != protocol['fitting_units']:
            raise ValueError('Fitting units differ from frozen protocol')
        destination = output / 'engine_inner'
        destination.mkdir(exist_ok=False)
        scores = []
        for index, candidate in enumerate(candidates):
            rows, folds = grouped_oof(task, fit, candidate)
            if folds != protocol['folds']:
                raise ValueError('Folds differ from frozen protocol')
            aligned = engine_protocol.aligned_predictions(rows, reference)
            if index == 0:
                expected = engine_protocol.aligned_predictions(reference, reference)
                np.testing.assert_allclose(aligned.predicted, expected.predicted, atol=1e-8, rtol=1e-8)
            comparison = engine_protocol.compare_candidate(rows, reference)
            path = destination / f'{candidate.name}.csv'
            rows.to_csv(path, index=False)
            metrics = comparison['candidate']
            score = {'candidate': candidate.name, 'selection_loss': metrics['balanced_phase_mae'],
                     'group_mean_mae': metrics['unit_mean_mae'], 'group_mean_rmse': metrics['unit_mean_rmse'],
                     'features': list(candidate.features), 'target_cap': candidate.upper,
                     'model_parameters': candidate.model.get_params(deep=False),
                     'inner_eligible': index == 0 or comparison['eligible_for_outer_checks'],
                     'full_trajectory_comparison': comparison,
                     'oof_path': path.relative_to(ROOT).as_posix(), 'oof_sha256': sha256(path)}
            scores.append(score)
            print(f"engine {candidate.name}: balanced-phase MAE={metrics['balanced_phase_mae']:.4f}; "
                  f"challenger passes={comparison['eligible_for_outer_checks']}", flush=True)
            with (destination / f'{candidate.name}.json').open('x', encoding='utf-8') as stream:
                json.dump(score, stream, indent=2, allow_nan=False)
        best = choose_engine(candidates, scores)
        return candidates[best], scores
    return select


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--status', action='store_true')
    actions.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'models/candidates' / EXPERIMENT
    if args.status:
        print(json.dumps(retained_status(output, TASKS), indent=2))
        return
    if args.replay:
        for task in TASKS:
            print(json.dumps(replay(task, experiment=EXPERIMENT), indent=2))
        verify_champions(json.loads((output / 'champions.json').read_text()))
        return
    if output.exists():
        parser.error('Prior run exists; refusing to overwrite models or evidence')
    load_frozen_reference()
    release, manifest = verified_release()
    evidence = json.loads((ROOT / engine_protocol.DIAGNOSTIC).read_text())
    protected = dict(evidence['sources'])
    protected['models/releases/current.json'] = sha256(ROOT / 'models/releases/current.json')
    protected.update({name: sha256(ROOT / name) for name in manifest['files']
                      if name.startswith('models/') and name.endswith('.joblib')})
    for relative, digest in protected.items():
        if sha256(ROOT / relative) != digest:
            raise ValueError(f'Protected source changed: {relative}')
    output.mkdir(parents=True, exist_ok=False)
    champions = {task: protect_champion(task, output) for task in TASKS}
    write_json(output / 'champions.json', champions)
    write_json(output / 'protocol.json', {
        'experiment': EXPERIMENT, 'engine_settings': ENGINE_SETTINGS, 'battery_settings': BATTERY_SETTINGS,
        'battery_seed': SEED, 'battery_trees': 400, 'baseline_included_for_both': True,
        'engine_protocol': engine_protocol.PROTOCOL, 'engine_protocol_sha256': sha256(ROOT / engine_protocol.PROTOCOL),
        'trainer_sha256': sha256(Path(__file__)), 'protected_sources': protected,
        'feature_and_label_changes': False, 'engine_inner': 'Frozen all-cycle unit/phase balanced selection',
        'battery_inner': 'Leave-one-battery-out; >=1% macro MAE gain, macro RMSE/worst-unit MAE no worse',
        'outer_gate': '>=1% audit MAE gain; audit/official RMSE, MAE, coverage and width no regression',
        'independent_validation': False, 'automatic_deployment': False,
        'candidate_count_including_baselines': 12})
    try:
        with threadpool_limits(limits=2):
            for task in ('engine', 'battery_rul'):
                report = run(task, output, release, previous_experiment=PREVIOUS[task],
                             grid_factory=candidate_grid, model_prefix='rul_v6',
                             selection_function=selector_for(output))
                gate = nonregression_gate(task, report)
                gate['retained_research_model'] = ((output / task / 'candidate.joblib').relative_to(ROOT).as_posix()
                    if gate['eligible_research_replacement'] else champions[task]['source'])
                gate['retained_model_sha256'] = sha256(ROOT / gate['retained_research_model'])
                report['retention_decision'] = gate
                report['selection_protocol'] = engine_protocol.PROTOCOL if task == 'engine' else 'v5_battery_group_nonregression'
                # Update only the report generated by this run, never prior evidence.
                (output / task / 'evaluation.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
                print(json.dumps({'task': task, 'retention_decision': gate}, indent=2), flush=True)
    finally:
        verify_champions(champions)
        for relative, digest in protected.items():
            if sha256(ROOT / relative) != digest:
                raise ValueError(f'Protected file changed during experiment: {relative}')
        verified_release()
    write_json(output / 'completion.json', {'completed': True, 'protected_files_verified': True,
                                          'retained': retained_status(output, TASKS), 'deployed': False})
    print('Protected retraining complete; existing best models and serving release unchanged.', flush=True)


if __name__ == '__main__':
    main()
