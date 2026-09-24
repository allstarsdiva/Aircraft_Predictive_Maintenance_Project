import copy
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesRegressor

from src.rul_condition_methods import ConditionRULRegressor, fit_condition_candidate
from src.rul_retraining_v5 import nonregression_gate, safe_inner_selection, candidate_grid, verify_champions, protect_champion
from src.targeted_retraining import Candidate
from src.model_release import sha256


def report():
    before = {'mae': 10., 'rmse': 15., 'interval_coverage': .9, 'mean_interval_width': 40.}
    current = dict(before, mae=9.5, rmse=14.5)
    return {'evaluation_metrics': current, 'previous_candidate_metrics': before,
            'official_test_regression_check': current.copy(), 'previous_candidate_official_check': before.copy(),
            'selected_candidate': 'challenger', 'selection': [{'candidate': 'challenger', 'inner_eligible': True}]}


def test_gate_requires_strict_improvement_and_does_not_deploy():
    decision = nonregression_gate('engine', report())
    assert decision['eligible_research_replacement'] and not decision['automatically_deployed']
    unchanged = report()
    unchanged['evaluation_metrics'] = unchanged['previous_candidate_metrics'].copy()
    assert not nonregression_gate('battery_rul', unchanged)['eligible_research_replacement']


@pytest.mark.parametrize('field,value', [('rmse', 16.), ('interval_coverage', .8),
                                       ('mean_interval_width', 41.), ('mae', np.nan)])
def test_gate_rejects_any_audit_regression_or_invalid_metric(field, value):
    evidence = report()
    evidence['evaluation_metrics'][field] = value
    assert not nonregression_gate('battery_rul', evidence)['eligible_research_replacement']


def test_official_regression_and_missing_evidence_fail_closed():
    evidence = report()
    evidence['official_test_regression_check']['mae'] = 11.
    assert not nonregression_gate('engine', evidence)['eligible_research_replacement']
    assert not nonregression_gate('engine', {})['eligible_research_replacement']
    evidence = report()
    evidence['selection'] = []
    assert not nonregression_gate('battery_rul', evidence)['eligible_research_replacement']
    with pytest.raises(ValueError):
        nonregression_gate('fuel', evidence)


@pytest.mark.parametrize('mode,clusters', [('direct', 2), ('lifetime', 1), ('lifetime', 2), ('blend', 1)])
def test_condition_models_round_trip_and_batch_invariance(tmp_path, mode, clusters):
    rng = np.random.default_rng(42)
    frame = pd.DataFrame({'discharge_cycle': np.arange(1., 41.), 'ambient_temperature': np.repeat([4., 24.], 20),
        'current_abs_mean': np.repeat([1., 2.], 20), 'voltage_end': rng.uniform(2.5, 3.5, 40)})
    model = clone(ConditionRULRegressor(mode=mode, clusters=clusters)).fit(frame, 60 - frame.discharge_cycle)
    predicted = model.predict(frame)
    assert predicted.shape == (40,) and (predicted >= 0).all()
    np.testing.assert_allclose(predicted[:7], model.predict(frame.iloc[:7]))
    path = tmp_path / 'candidate.joblib'
    joblib.dump(model, path)
    np.testing.assert_allclose(predicted, joblib.load(path).predict(frame))
    if mode == 'lifetime':
        # Constant training lifetime must become lifetime minus observed age.
        np.testing.assert_allclose(predicted, 60 - frame.discharge_cycle, atol=1e-10)


def test_cycle_inverse_transform_is_fitted_on_training_only():
    table = pd.DataFrame({'battery_id': ['A'] * 20 + ['B'] * 20, 'discharge_cycle': np.arange(1., 41.),
                          'target': 60 - np.arange(1., 41.)})
    specification = Candidate('lifetime', ConditionRULRegressor(mode='lifetime'), ('discharge_cycle',), None)
    prep, model = fit_condition_candidate(table, 'target', specification, False)
    inputs = pd.DataFrame(prep.transform(table[['discharge_cycle']]), columns=['discharge_cycle'])
    np.testing.assert_allclose(model.predict(inputs), table.target, atol=1e-10)
    with pytest.raises(ValueError, match='Identity'):
        ConditionRULRegressor().fit(table, table.target)


def test_inner_guard_keeps_baseline_when_mean_improves_but_worst_unit_worsens(monkeypatch):
    scores = [dict(candidate='base', group_mean_mae=10., group_mean_rmse=12., selection_loss=10.,
                   groups=[{'mae': 14.}, {'mae': 6.}]),
              dict(candidate='new', group_mean_mae=9., group_mean_rmse=11., selection_loss=9.,
                   groups=[{'mae': 15.}, {'mae': 3.}])]
    candidates = [SimpleNamespace(name='base'), SimpleNamespace(name='new')]
    monkeypatch.setattr('src.rul_retraining_v5.select_on_fitting', lambda *args, **kwargs: ('new', copy.deepcopy(scores)))
    selected, results = safe_inner_selection('battery_rul', None, None, None, candidates)
    assert selected is candidates[0] and not results[1]['inner_eligible']


def test_protected_snapshot_detects_tampering(tmp_path, monkeypatch):
    import json
    root = tmp_path
    monkeypatch.setattr('src.rul_retraining_v5.ROOT', root)
    source = root / 'models/candidates/battery-history-20260911/battery_rul'
    source.mkdir(parents=True)
    joblib.dump({'model': 'original'}, source / 'candidate.joblib')
    (source / 'evaluation.json').write_text(json.dumps({'candidate_sha256': sha256(source / 'candidate.joblib'),
                                                       'evaluation_metrics': {'mae': 10.}}))
    protected = {'battery_rul': protect_champion('battery_rul', root / 'experiment')}
    verify_champions(protected)
    with pytest.raises(FileExistsError):
        protect_champion('battery_rul', root / 'experiment')
    joblib.dump({'model': 'changed'}, source / 'candidate.joblib')
    with pytest.raises(ValueError, match='changed'):
        verify_champions(protected)


def test_new_grids_are_bounded_and_scoped():
    previous = SimpleNamespace(model=ExtraTreesRegressor(), feature_columns=('cycle',), target_maximum=175.)
    table = pd.DataFrame(columns=['cycle', 'ambient_temperature', 'current_abs_mean', 'voltage_end'])
    assert len(candidate_grid('engine', table, previous)) == 7
    assert len(candidate_grid('battery_rul', table, previous)) == 10
    with pytest.raises(ValueError, match='scope'):
        candidate_grid('fuel', table, previous)


def test_regularized_lifetime_can_extrapolate_without_future_inputs():
    observed = pd.DataFrame({'discharge_cycle': np.arange(1., 21.)})
    target = observed.discharge_cycle.to_numpy() + 100.
    model = ConditionRULRegressor(mode='lifetime', learner='ridge', ridge_alpha=.001).fit(observed, target)
    predicted = model.predict(pd.DataFrame({'discharge_cycle': [40.]}))[0]
    assert predicted > target.max()
    assert predicted == pytest.approx(140., abs=1.)
