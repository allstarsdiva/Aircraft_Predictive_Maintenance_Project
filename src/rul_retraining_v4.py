"""Bounded method comparison using fitting-only diagnostics; no promotion."""
import argparse
import json
import platform

import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.base import clone
from threadpoolctl import threadpool_limits

from src.audit_finalization import partition_groups
from src.model_release import verified_release, sha256
from src.rul_methods import RULMethodRegressor, robust_battery_features, fit_method_candidate
from src.rul_retraining_v2 import run, replay, TASKS
from src.targeted_retraining import Candidate, ROOT, load_task

EXPERIMENT = 'rul-methods-v4-20260912'
PREVIOUS = {'engine': 'rul-retrain-20260912', 'battery_rul': 'battery-history-20260911'}


def feature_transform(task, table):
    if task not in TASKS:
        raise ValueError('Only battery and engine RUL are in scope')
    return robust_battery_features(table) if task == 'battery_rul' else table


def candidate_grid(task, table, previous):
    if task not in TASKS:
        raise ValueError('Only battery and engine RUL are in scope')
    features = tuple(previous.feature_columns)
    grid = [Candidate('previous_candidate_spec', clone(previous.model), features, previous.target_maximum)]
    if task == 'engine':
        for cap in (175., 225., None):
            for method, depth in (('xgb', 3), ('xgb', 5), ('blend', 3)):
                grid.append(Candidate(f'balanced_{method}_depth{depth}_cap{cap}',
                    RULMethodRegressor(task=task, method=method, depth=depth), features, cap))
        grid.append(Candidate('unweighted_xgb_depth3_cap175',
            RULMethodRegressor(task=task, group_balanced=False), features, 175.))
    else:
        robust = tuple(c for c in table if c.startswith('robust_'))
        if len(robust) != 10:
            raise ValueError('Robust battery features are incomplete')
        compact = ('discharge_cycle', 'ambient_temperature', 'current_abs_mean',
                   'temperature_mean', 'voltage_end', 'duration_seconds') + robust
        for view, columns in (('history', features + robust), ('compact', compact)):
            for method, depth, logarithm in (('xgb', 2, False), ('xgb', 3, False),
                                              ('xgb', 2, True), ('blend', 2, False),
                                              ('extra', 2, False)):
                grid.append(Candidate(f'balanced_{view}_{method}_depth{depth}_log{logarithm}',
                    RULMethodRegressor(task=task, method=method, depth=depth,
                                       iterations=300, log_target=logarithm), columns, None))
    if any(set(c.features) - set(table.columns) for c in grid):
        raise ValueError('Unavailable causal features')
    return grid


def fitting_diagnostics(task, release):
    table, groups, target, _ = load_task(task, release)
    fit = table.iloc[partition_groups(groups)[0]]
    group_column = 'unit_id' if task == 'engine' else 'battery_id'
    records = []
    for group, rows in fit.groupby(group_column):
        record = {'group': str(group), 'rows': len(rows),
                  'maximum_rul': float(rows[target].max()),
                  'unweighted_training_fraction': len(rows) / len(fit)}
        if task == 'battery_rul':
            record.update(ambient_temperature_median=float(rows.ambient_temperature.median()),
                          current_median=float(rows.current_abs_mean.median()),
                          throughput_minimum=float(rows.charge_throughput_ah.min()))
        records.append(record)
    return {'groups': records, 'fitting_rows': len(fit), 'fitting_groups': len(records),
            'equal_weight_fraction': 1 / len(records), 'evaluation_data_used': False,
            'interpretation': 'Unequal trajectory lengths affect row-weighted loss; battery operating regimes differ.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks', nargs='+', choices=TASKS, default=list(TASKS))
    parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    if len(set(args.tasks)) != len(args.tasks):
        parser.error('Duplicate tasks are not allowed')
    output = ROOT / 'models/candidates' / EXPERIMENT
    if args.replay:
        for task in args.tasks:
            print(json.dumps(replay(task, experiment=EXPERIMENT), indent=2))
        return
    if any((output / task).exists() for task in args.tasks):
        parser.error('Preserve existing completed tasks')
    release, manifest = verified_release()
    relative = 'data/processed/battery/rul_features.csv'
    if sha256(ROOT / relative) != manifest['data_hashes'][relative]:
        raise ValueError('Battery source differs from baseline release')
    for filename, expected in manifest['engine_source_hashes'].items():
        if sha256(ROOT / 'data/raw/engine' / filename) != expected:
            raise ValueError('Engine source differs from baseline release')
    pointer = ROOT / 'models/releases/current.json'
    pointer_before = sha256(pointer)
    serving = {name: sha256(ROOT / name) for name in manifest['files']
               if name.startswith('models/') and name.endswith('.joblib')}
    output.mkdir(parents=True, exist_ok=True)
    with threadpool_limits(limits=2):
        for task in args.tasks:
            diagnostic_path = output / f'{task}_fitting_diagnostics.json'
            if diagnostic_path.exists():
                raise FileExistsError('Preserve earlier diagnostics; inspect unfinished experiment')
            diagnostic_path.write_text(json.dumps(fitting_diagnostics(task, release), indent=2), encoding='utf-8')
            result = run(task, output, release, previous_experiment=PREVIOUS[task],
                grid_factory=candidate_grid, model_prefix='rul_v4',
                fit_function=fit_method_candidate, feature_transform=feature_transform)
            result['environment'] = {'python': platform.python_version(), 'numpy': np.__version__,
                                     'pandas': pd.__version__, 'sklearn': sklearn.__version__,
                                     'xgboost': xgboost.__version__}
            result['method_protocol'] = 'Fixed grid, equal-unit fitting weights for new methods, fixed 50/50 ensemble weights; no outer tuning.'
            (output / task / 'evaluation.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    assert sha256(pointer) == pointer_before
    assert all(sha256(ROOT / name) == digest for name, digest in serving.items())
    verified_release()
    print(f'Complete: {len(serving)} serving artifacts and active release unchanged.', flush=True)


if __name__ == '__main__':
    main()
