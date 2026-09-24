"""Third bounded RUL experiment; never promotes or overwrites serving models."""
import argparse
import json

from sklearn.base import clone
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.svm import SVR
from threadpoolctl import threadpool_limits

from src.model_release import verified_release, sha256
from src.rul_retraining_v2 import run, replay, TASKS
from src.targeted_retraining import Candidate, ROOT

EXPERIMENT = 'rul-retrain-v3-20260912'
PREVIOUS = {'engine': 'rul-retrain-20260912', 'battery_rul': 'battery-history-20260911'}
SEED = 20260912


def candidate_grid(task, table, previous):
    """Predeclared grid: no evaluation data/labels influence its configurations."""
    if task not in TASKS:
        raise ValueError('Only battery and engine RUL are in scope')
    features = tuple(previous.feature_columns)
    candidates = [Candidate('previous_candidate_spec', clone(previous.model),
                            features, previous.target_maximum)]
    if task == 'engine':
        # Keep causal v2 features; compare higher capacity and regularization.
        for cap in (175., 225., None):
            for leaves, iterations, regularization in ((7, 450, 10.), (15, 450, 10.), (31, 300, 20.)):
                name = f'hist_leaf{leaves}_iter{iterations}_cap{cap}'
                candidates.append(Candidate(name, HistGradientBoostingRegressor(
                    max_iter=iterations, max_leaf_nodes=leaves, min_samples_leaf=25,
                    learning_rate=.035, l2_regularization=regularization,
                    early_stopping=False, random_state=SEED), features, cap))
    else:
        # Small independent-group count motivates smooth, regularized regressors
        # and a compact view instead of adding further correlated sensor fields.
        compact = ('discharge_cycle', 'charge_throughput_ah', 'duration_seconds',
                   'voltage_mean', 'temperature_mean', 'trend_capacity_margin',
                   'trend_capacity_slope_15', 'trend_capacity_slope_30')
        for view, columns in (('history', features), ('compact', compact)):
            for c in (30., 100., 300.):
                for gamma in (.01, .1):
                    candidates.append(Candidate(f'svr_{view}_C{c}_gamma{gamma}',
                        SVR(C=c, gamma=gamma, epsilon=.5), columns, None))
        for leaf in (3, 6):
            candidates.append(Candidate(f'extra_history_leaf{leaf}', ExtraTreesRegressor(
                n_estimators=350, min_samples_leaf=leaf, max_features=.5,
                n_jobs=2, random_state=SEED), features, None))
    if any(set(c.features) - set(table.columns) for c in candidates):
        raise ValueError('Candidate requires unavailable causal inputs')
    return candidates


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
        parser.error('Preserve existing results: selected task outputs already exist')
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
    with threadpool_limits(limits=2):
        for task in args.tasks:
            run(task, output, release, previous_experiment=PREVIOUS[task],
                grid_factory=candidate_grid, model_prefix='rul_v3')
    assert sha256(pointer) == pointer_before
    assert all(sha256(ROOT / name) == digest for name, digest in serving.items())
    verified_release()
    print(f'Complete: {len(serving)} serving artifacts and active release unchanged.', flush=True)


if __name__ == '__main__':
    main()
