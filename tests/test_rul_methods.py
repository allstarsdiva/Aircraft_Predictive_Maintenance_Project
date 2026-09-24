from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesRegressor

from src.rul_methods import equal_group_weights, robust_battery_features, RULMethodRegressor, fit_method_candidate
from src.rul_retraining_v2 import select_on_fitting
from src.rul_retraining_v4 import candidate_grid, feature_transform
from src.targeted_retraining import Candidate


def history():
    return pd.DataFrame({'battery_id': ['B0006'] * 35, 'discharge_cycle': np.arange(1, 36),
                         'charge_throughput_ah': np.linspace(2., 1.4, 35)})


def test_each_fitting_group_has_equal_weight_and_mean_one():
    groups = ['A'] * 10 + ['B'] * 2 + ['C']
    weights = equal_group_weights(groups)
    sums = pd.DataFrame({'group': groups, 'weight': weights}).groupby('group').weight.sum()
    np.testing.assert_allclose(sums, len(groups) / 3)
    assert weights.mean() == pytest.approx(1.)
    with pytest.raises(ValueError):
        equal_group_weights([])


def test_robust_features_are_prefix_invariant_and_ignore_labels():
    frame = history()
    full = robust_battery_features(frame)
    for length in (1, 3, 9, 22):
        pd.testing.assert_frame_equal(full.iloc[:length], robust_battery_features(frame.iloc[:length]))
    labelled = robust_battery_features(frame.assign(rul_cycles=1000, observed_eol_cycle=2000))
    pd.testing.assert_frame_equal(full, labelled[full.columns])


def test_single_capacity_spike_is_not_copied_into_robust_history():
    frame = history()
    frame.loc[20, 'charge_throughput_ah'] = .01
    result = robust_battery_features(frame)
    assert result.loc[20, 'robust_capacity_median5'] > 1.5
    assert result.loc[20, 'charge_throughput_ah'] == .01  # raw data not altered
    combined = robust_battery_features(pd.concat([frame, frame.assign(battery_id='B0005')]))
    pd.testing.assert_frame_equal(combined.iloc[35:].reset_index(drop=True),
                                 robust_battery_features(frame.assign(battery_id='B0005')))


def test_robust_features_reject_bad_keys_and_unknown_metadata():
    with pytest.raises(ValueError, match='Unique'):
        robust_battery_features(pd.concat([history(), history()]))
    with pytest.raises(ValueError, match='threshold'):
        robust_battery_features(history().assign(battery_id='unknown'))


@pytest.mark.parametrize('method,logarithm', [('xgb', False), ('xgb', True), ('blend', False), ('extra', False)])
def test_new_methods_clone_fit_and_round_trip(tmp_path, method, logarithm):
    frame = pd.DataFrame({'x': np.arange(40.), 'z': np.sin(np.arange(40.))})
    model = RULMethodRegressor(task='battery_rul', method=method, iterations=8, log_target=logarithm)
    restored_spec = clone(model)
    assert restored_spec.get_params() == model.get_params()
    restored_spec.fit(frame, np.arange(40.), sample_weight=np.ones(40))
    predicted = restored_spec.predict(frame)
    assert predicted.shape == (40,) and np.isfinite(predicted).all() and (predicted >= 0).all()
    destination = tmp_path / 'model.joblib'
    joblib.dump(restored_spec, destination)
    np.testing.assert_allclose(predicted, joblib.load(destination).predict(frame))
    with pytest.raises(ValueError, match='order'):
        restored_spec.predict(frame[['z', 'x']])


def test_identity_and_label_predictors_are_rejected():
    with pytest.raises(ValueError, match='identity'):
        RULMethodRegressor().fit(pd.DataFrame({'unit_id': [1, 2]}), [10., 20.])


def test_weighted_preprocessor_and_model_use_only_fitting_rows():
    table = pd.DataFrame({'battery_id': ['A'] * 10 + ['B'] * 2, 'x': [0.] * 10 + [10.] * 2,
                          'target': np.arange(12.)})
    candidate = Candidate('weighted', RULMethodRegressor(task='battery_rul', iterations=4), ('x',), None)
    prep, model = fit_method_candidate(table, 'target', candidate, False)
    assert prep.named_steps['scaler'].mean_[0] == pytest.approx(5.)
    assert model.feature_names_in_.tolist() == ['x']


def test_training_hook_receives_disjoint_inner_groups():
    frame = pd.DataFrame({'battery_id': np.repeat(['A', 'B', 'C'], 8), 'x': np.arange(24.), 'target': np.arange(24.)})
    candidate = Candidate('weighted', RULMethodRegressor(task='battery_rul', iterations=3), ('x',), None)
    seen = []
    def trainer(table, target, specification, classifier):
        seen.append(set(table.battery_id))
        return fit_method_candidate(table, target, specification, classifier)
    _, scores = select_on_fitting('battery_rul', frame, frame.battery_id.to_numpy(), 'target',
                                 [candidate], fit_function=trainer)
    assert len(seen) == 3 and all(len(groups) == 2 for groups in seen)
    assert {g['group'] for g in scores[0]['groups']} == {'A', 'B', 'C'}


def test_bounded_grids_and_scope():
    previous = SimpleNamespace(model=ExtraTreesRegressor(), feature_columns=('cycle',), target_maximum=175.)
    assert len(candidate_grid('engine', pd.DataFrame(columns=['cycle']), previous)) == 11
    table = robust_battery_features(history()).assign(cycle=1, ambient_temperature=24.,
        current_abs_mean=2., temperature_mean=25., voltage_end=3., duration_seconds=3000.)
    assert len(candidate_grid('battery_rul', table, previous)) == 11
    with pytest.raises(ValueError, match='scope'):
        feature_transform('fuel', table)
