"""Temporal causality, normal-only fitting, and nested selection isolation."""
import numpy as np
import pandas as pd
import pytest

from src.data.fuel_system import FUEL_SENSOR_COLUMNS, load_fuel_system_dataset
from src.fuel_robust_modeling import FuelSteadyEnvelope, steady_features
from src.improve_fuel import Candidate, fit_bundle, outer_plan, tune_inside


def normal_frame(n=50):
    rng = np.random.default_rng(21)
    values = rng.normal(0, .1, (n,8)) + np.array([70,80,5,5,1,1,-20,-20])
    table = pd.DataFrame(values, columns=FUEL_SENSOR_COLUMNS)
    table['sample_index'] = np.arange(1,n+1)
    table['scenario_id'] = 'normal'
    table['is_abnormal'] = 0
    return table


def test_prediction_prefix_never_depends_on_future_samples():
    normal = normal_frame()
    bundle = fit_bundle(normal.iloc[:30], normal.iloc[30:], Candidate('mahalanobis',3,False,.99,5,3))
    query = normal.copy()
    query.loc[20:, 'FTF'] = .5
    np.testing.assert_allclose(bundle.predict_anomaly_score(query)[:25], bundle.predict_anomaly_score(query.iloc[:25]))
    np.testing.assert_array_equal(bundle.predict_feature_frame(query)[:25], bundle.predict_feature_frame(query.iloc[:25]))


def test_one_sensor_fault_is_detected_and_scenario_history_resets():
    normal = normal_frame()
    bundle = fit_bundle(normal.iloc[:30], normal.iloc[30:], Candidate('max',3,False,.99,5,3))
    faulty = normal.copy()
    faulty['FTT'] = -40.
    faulty['scenario_id'] = 'fault'
    assert bundle.predict_feature_frame(faulty)[5:].mean() == 1
    combined = pd.concat([faulty, normal], ignore_index=True)
    np.testing.assert_array_equal(bundle.predict_feature_frame(combined)[len(faulty):], bundle.predict_feature_frame(normal))


def test_missing_nonfinite_and_unordered_inputs_are_rejected():
    frame = normal_frame()
    model = FuelSteadyEnvelope.fit(frame)
    with pytest.raises(ValueError, match='Missing fuel'):
        model.anomaly_score(frame.drop(columns='FTF'))
    bad = frame.copy()
    bad.loc[0,'FTF'] = np.inf
    with pytest.raises(ValueError, match='finite'):
        model.anomaly_score(bad)
    with pytest.raises(ValueError, match='ordered'):
        model.anomaly_score(frame.iloc[::-1])
    bad = frame.copy()
    bad['is_abnormal'] = 1
    with pytest.raises(ValueError, match='normal samples only'):
        FuelSteadyEnvelope.fit(bad)


def test_features_reset_at_missing_time_segments():
    frame = normal_frame()
    indices = np.r_[np.arange(10), np.arange(20,30)]
    combined = steady_features(frame.iloc[indices],3)
    np.testing.assert_allclose(combined[10:], steady_features(frame.iloc[20:30],3))


def test_outer_test_normal_values_do_not_change_inner_selection(monkeypatch):
    from src import improve_fuel
    table = load_fuel_system_dataset()
    normal = table.loc[table.scenario_id == 'normal'].reset_index(drop=True)
    names = sorted(set(table.scenario_id)-{'normal'})
    blocks, plan = outer_plan(normal, names)
    fold = plan[0]
    faults = table.loc[(table.scenario_id != 'normal') & (table.scenario_id != fold['test_scenario'])]
    monkeypatch.setattr(improve_fuel, 'CANDIDATES', (Candidate('max',1,False,.99,1,1),))
    selected, before = tune_inside(normal, faults, blocks, fold['development_blocks'])
    modified = normal.copy()
    modified.loc[blocks[fold['test_block']], list(FUEL_SENSOR_COLUMNS)] = 1e9
    selected_after, after = tune_inside(modified, faults, blocks, fold['development_blocks'])
    assert selected == selected_after and before == after
    for metrics in before.values():
        assert set(metrics['normal_validation_positions']).isdisjoint(normal.iloc[blocks[fold['test_block']]].sample_index)


def test_outer_normal_blocks_partition_all_samples_once():
    normal = normal_frame(171)
    blocks, plan = outer_plan(normal, ['one','two','three','four'])
    assert sorted(np.concatenate(blocks).tolist()) == list(range(171))
    for fold in plan:
        assert fold['test_block'] not in fold['development_blocks']
