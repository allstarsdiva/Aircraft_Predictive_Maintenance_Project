"""Protected champions, condition-aware training, and fail-closed retention."""
import argparse
import json
import shutil

import joblib
import numpy as np
from sklearn.base import clone
from threadpoolctl import threadpool_limits

from src.model_release import verified_release, sha256
from src.rul_condition_methods import ConditionRULRegressor, fit_condition_candidate
from src.rul_retraining_v2 import run, replay, select_on_fitting, TASKS
from src.targeted_retraining import Candidate, ROOT

EXPERIMENT = 'rul-protected-v5-20260913'
PREVIOUS = {'engine': 'rul-retrain-20260912', 'battery_rul': 'battery-history-20260911'}


def candidate_grid(task, table, previous):
    if task not in TASKS:
        raise ValueError('Only battery and engine RUL are in scope')
    features = tuple(previous.feature_columns)
    grid = [Candidate('previous_candidate_spec', clone(previous.model), features, previous.target_maximum)]
    if task == 'engine':
        for mode, balanced in (('direct', False), ('lifetime', False), ('lifetime', True)):
            grid.append(Candidate(f'{mode}_balanced{balanced}', ConditionRULRegressor(
                task=task, mode=mode, group_balanced=balanced), features, None))
        for fraction in (.25, .5, .75):
            grid.append(Candidate(f'lifetime_blend_{fraction}', ConditionRULRegressor(
                task=task, mode='blend', lifetime_fraction=fraction), features, None))
    else:
        conditions = ('ambient_temperature', 'current_abs_mean', 'voltage_end')
        features = tuple(dict.fromkeys(features + conditions))
        grid.append(Candidate('global_lifetime', ConditionRULRegressor(mode='lifetime'), features, None))
        for alpha in (10., 100.):
            grid.append(Candidate(f'lifetime_ridge_{alpha}', ConditionRULRegressor(
                mode='lifetime', learner='ridge', ridge_alpha=alpha), features, None))
        for clusters, strength in ((2, .5), (3, .5), (2, .8)):
            for mode in ('direct', 'lifetime'):
                grid.append(Candidate(f'conditions{clusters}_{mode}_local{strength}',
                    ConditionRULRegressor(mode=mode, clusters=clusters, local_strength=strength), features, None))
    if any(set(c.features) - set(table.columns) for c in grid):
        raise ValueError('Required observed features unavailable')
    return grid


def safe_inner_selection(task, fit, groups, target, candidates, *, fit_function=None):
    _, scores = select_on_fitting(task, fit, groups, target, candidates, fit_function=fit_function)
    baseline = scores[0]
    worst_before = max(g['mae'] for g in baseline['groups'])
    eligible = [0]
    for index, score in enumerate(scores):
        checks = {
            'mae_improves_at_least_one_percent': score['group_mean_mae'] <= .99 * baseline['group_mean_mae'],
            'rmse_no_worse': score['group_mean_rmse'] <= baseline['group_mean_rmse'] + 1e-10,
            'worst_unit_mae_no_worse': max(g['mae'] for g in score['groups']) <= worst_before + 1e-10}
        checks = {key: bool(value) for key, value in checks.items()}
        score['inner_nonregression_checks'] = checks
        score['inner_eligible'] = index == 0 or all(checks.values())
        if index and score['inner_eligible']:
            eligible.append(index)
    best = min(eligible, key=lambda index: scores[index]['selection_loss'])
    print(f'{task}: safe inner selection={candidates[best].name}', flush=True)
    return candidates[best], scores


def nonregression_gate(task, report):
    """Research-retention check only; never a certification/deployment gate."""
    if task not in TASKS:
        raise ValueError('Unsupported task')
    reasons = []
    comparisons = [('audit', report.get('evaluation_metrics'), report.get('previous_candidate_metrics'))]
    if task == 'engine':
        comparisons.append(('official', report.get('official_test_regression_check'),
                            report.get('previous_candidate_official_check')))
    for name, current, baseline in comparisons:
        keys = ('mae', 'rmse', 'interval_coverage', 'mean_interval_width')
        if not isinstance(current, dict) or not isinstance(baseline, dict):
            reasons.append(f'{name}: missing evidence')
            continue
        try:
            valid = all(np.isfinite(float(part[key])) for part in (current, baseline) for key in keys)
            valid = valid and all(part['mae'] >= 0 and part['rmse'] >= 0 and part['mean_interval_width'] >= 0
                                  and 0 <= part['interval_coverage'] <= 1 for part in (current, baseline))
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            reasons.append(f'{name}: incomplete or invalid metrics')
            continue
        for key in ('mae', 'rmse', 'mean_interval_width'):
            if current[key] > baseline[key] + 1e-8:
                reasons.append(f'{name}: {key} worsened')
        if current['interval_coverage'] + 1e-8 < baseline['interval_coverage']:
            reasons.append(f'{name}: interval coverage worsened')
        if name == 'audit' and current['mae'] > .99 * baseline['mae']:
            reasons.append('audit: less than one-percent MAE improvement')
    if report.get('selected_candidate') == 'previous_candidate_spec':
        reasons.append('retained baseline specification selected; no new improvement')
    selection = report.get('selection', [])
    selected = next((item for item in selection if item.get('candidate') == report.get('selected_candidate')), None)
    if selected is None or not selected.get('inner_eligible', False):
        reasons.append('missing or failed fitting-only safety checks')
    return {'eligible_research_replacement': not reasons, 'reasons': reasons,
            'automatically_deployed': False, 'independent_validation_required': True}


def protect_champion(task, output):
    source = ROOT / 'models/candidates' / PREVIOUS[task] / task
    report = json.loads((source / 'evaluation.json').read_text())
    model_path = source / 'candidate.joblib'
    if sha256(model_path) != report['candidate_sha256']:
        raise ValueError('Champion integrity mismatch')
    snapshot = output / 'champions' / task
    snapshot.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(model_path, snapshot / 'candidate.joblib')
    shutil.copyfile(source / 'evaluation.json', snapshot / 'evaluation.json')
    assert sha256(snapshot / 'candidate.joblib') == report['candidate_sha256']
    return {'source': model_path.relative_to(ROOT).as_posix(),
            'snapshot': (snapshot / 'candidate.joblib').relative_to(ROOT).as_posix(),
            'sha256': report['candidate_sha256'], 'source_report_sha256': sha256(source / 'evaluation.json'),
            'audit_metrics': report['evaluation_metrics'], 'deployed': False}


def verify_champions(champions):
    for champion in champions.values():
        for key in ('source', 'snapshot'):
            if sha256(ROOT / champion[key]) != champion['sha256']:
                raise ValueError('Protected champion changed')
        for key in ('source', 'snapshot'):
            source_report = (ROOT / champion[key]).parent / 'evaluation.json'
            if sha256(source_report) != champion['source_report_sha256']:
                raise ValueError('Champion evaluation report changed')


def retained_status(output, tasks):
    champions = json.loads((output / 'champions.json').read_text())
    verify_champions(champions)
    results = []
    for task in tasks:
        if task not in TASKS or task not in champions:
            raise ValueError('Task has no protected champion')
        report = json.loads((output / task / 'evaluation.json').read_text())
        decision = report['retention_decision']
        expected = nonregression_gate(task, report)
        if any(decision.get(key) != value for key, value in expected.items()):
            raise ValueError('Stored retention decision differs from safety gate')
        accepted = expected['eligible_research_replacement']
        path = ((output / task / 'candidate.joblib').relative_to(ROOT).as_posix()
                if accepted else champions[task]['source'])
        expected_hash = report['candidate_sha256'] if accepted else champions[task]['sha256']
        if decision['retained_research_model'] != path or decision['retained_model_sha256'] != expected_hash:
            raise ValueError('Retained model reference differs from safety decision')
        if sha256(ROOT / path) != expected_hash:
            raise ValueError('Retained model hash mismatch')
        metrics = report['evaluation_metrics'] if accepted else report['previous_candidate_metrics']
        item = {'task': task, 'retained_model': path, 'audit_mae': metrics['mae'], 'audit_rmse': metrics['rmse'],
                'new_candidate_retained': accepted, 'protected_champions_verified': True, 'deployed': False}
        if task == 'engine':
            item['official_metrics'] = report['official_test_regression_check'] if accepted else report['previous_candidate_official_check']
        results.append(item)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks', nargs='+', choices=TASKS, default=list(TASKS))
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--replay', action='store_true')
    actions.add_argument('--status', action='store_true', help='Verify and show retained models, not rejected challengers')
    args = parser.parse_args()
    if len(set(args.tasks)) != len(args.tasks):
        parser.error('Duplicate tasks forbidden')
    output = ROOT / 'models/candidates' / EXPERIMENT
    if args.status:
        print(json.dumps(retained_status(output, args.tasks), indent=2))
        return
    if args.replay:
        for task in args.tasks:
            print(json.dumps(replay(task, experiment=EXPERIMENT), indent=2))
        verify_champions(json.loads((output / 'champions.json').read_text()))
        print('Protected champion hashes verified.')
        return
    if output.exists():
        parser.error('Preserve prior run and protected champions; output already exists')
    release, manifest = verified_release()
    relative = 'data/processed/battery/rul_features.csv'
    if sha256(ROOT / relative) != manifest['data_hashes'][relative]:
        raise ValueError('Battery source changed')
    for name, digest in manifest['engine_source_hashes'].items():
        if sha256(ROOT / 'data/raw/engine' / name) != digest:
            raise ValueError('Engine source changed')
    pointer = ROOT / 'models/releases/current.json'
    pointer_before = sha256(pointer)
    serving = {name: sha256(ROOT / name) for name in manifest['files']
               if name.startswith('models/') and name.endswith('.joblib')}
    output.mkdir(parents=True)
    champions = {task: protect_champion(task, output) for task in args.tasks}
    (output / 'champions.json').write_text(json.dumps(champions, indent=2), encoding='utf-8')
    protocol = {'minimum_audit_mae_improvement': .01, 'other_metrics_must_not_regress':
                ['audit_rmse', 'audit_interval_coverage', 'audit_interval_width', 'engine_official_metrics'],
                'inner_guard': 'mean MAE improves >=1%, mean RMSE and worst-unit MAE do not worsen',
                'no_test_rows_removed': True, 'deployed_models_untouched': True}
    (output / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    try:
        with threadpool_limits(limits=2):
            for task in args.tasks:
                report = run(task, output, release, previous_experiment=PREVIOUS[task],
                    grid_factory=candidate_grid, model_prefix='rul_v5', fit_function=fit_condition_candidate,
                    selection_function=safe_inner_selection)
                gate = nonregression_gate(task, report)
                gate['retained_research_model'] = ((output / task / 'candidate.joblib').relative_to(ROOT).as_posix()
                    if gate['eligible_research_replacement'] else champions[task]['source'])
                gate['retained_model_sha256'] = sha256(ROOT / gate['retained_research_model'])
                report['retention_decision'] = gate
                (output / task / 'evaluation.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
                print(json.dumps({'task': task, 'retention_decision': gate}, indent=2), flush=True)
    finally:
        verify_champions(champions)
        assert sha256(pointer) == pointer_before
        assert all(sha256(ROOT / name) == digest for name, digest in serving.items())
        verified_release()
    print('Protected retraining complete; champions and serving models unchanged.', flush=True)


if __name__ == '__main__':
    main()
