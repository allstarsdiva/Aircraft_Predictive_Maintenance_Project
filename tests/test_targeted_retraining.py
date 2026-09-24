import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

from src.targeted_retraining import Candidate, fit_candidate, prediction, select_candidate, target_pass, load_task
from src.audit_finalization import partition_groups


def test_only_authorized_tasks_are_allowed():
    with pytest.raises(ValueError, match='scope'):
        load_task('fuel', None)
    with pytest.raises(ValueError, match='scope'):
        target_pass('landing_fault', {})


def test_targets_use_full_balanced_accuracy_and_both_engine_errors():
    assert target_pass('hydraulic_valve', {'balanced_accuracy':.90})
    assert not target_pass('hydraulic_valve', {'balanced_accuracy':.85,'accepted_accuracy':.99})
    assert target_pass('engine', {'mae':15,'rmse':20})
    assert not target_pass('engine', {'mae':14,'rmse':21})
    assert not target_pass('battery_soh', {'mae':3.01})
    assert target_pass('battery_rul', {'mae':10})


def test_fit_does_not_modify_targets_and_uncapped_predictions_remain_uncapped():
    table = pd.DataFrame({'sensor':np.arange(200.), 'rul':np.arange(200.)})
    candidate = Candidate('linear', LinearRegression(), ('sensor',), None)
    prep, model = fit_candidate(table, 'rul', candidate, False)
    assert prediction(table.tail(1), candidate, prep, model, False)[0] > 125
    capped = Candidate('capped', LinearRegression(), ('sensor',), 125)
    fit_candidate(table, 'rul', capped, False)
    assert table.rul.max() == 199


def test_inner_selection_is_unaffected_by_outer_labels_or_features():
    table = pd.DataFrame({'x':np.arange(60.), 'y':np.arange(60.)*2})
    groups = np.repeat(np.arange(10), 6)
    fitting, calibration, evaluation = partition_groups(groups)
    assert set(groups[fitting]).isdisjoint(groups[calibration])
    assert set(groups[fitting]).isdisjoint(groups[evaluation])
    candidates = [Candidate('linear', LinearRegression(), ('x',), None)]
    _, before = select_candidate(table.iloc[fitting], groups[fitting], 'y', candidates, False)
    table.loc[np.r_[calibration,evaluation], ['x','y']] = 1e12
    _, after = select_candidate(table.iloc[fitting], groups[fitting], 'y', candidates, False)
    assert before == after
