from types import SimpleNamespace

import pandas as pd
import pytest
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor

from src.rul_retraining_v6 import candidate_grid, choose_engine, load_frozen_reference
from src.targeted_retraining import Candidate


@pytest.mark.parametrize('task,model,cap', [
    ('engine', HistGradientBoostingRegressor(), 175.),
    ('battery_rul', ExtraTreesRegressor(), None),
])
def test_grid_preserves_champion_and_features(task, model, cap):
    previous = SimpleNamespace(model=model, feature_columns=('observed',), target_maximum=cap)
    before = model.get_params().copy()
    grid = candidate_grid(task, pd.DataFrame({'observed': [1]}), previous)
    assert len(grid) == 6
    assert grid[0].name == 'previous_candidate_spec'
    assert grid[0].model is not model
    assert grid[0].upper == cap
    assert all(item.features == ('observed',) for item in grid)
    assert model.get_params() == before


def test_failed_guard_cannot_win_with_better_average():
    candidates = [Candidate('previous_candidate_spec', None, (), None), Candidate('challenger', None, (), None)]
    scores = [{'selection_loss': 20., 'inner_eligible': True}, {'selection_loss': 10., 'inner_eligible': False}]
    assert choose_engine(candidates, scores) == 0
    scores[1]['inner_eligible'] = True
    assert choose_engine(candidates, scores) == 1


def test_missing_baseline_rejected():
    with pytest.raises(ValueError, match='baseline-first'):
        choose_engine([Candidate('challenger', None, (), None)], [])


def test_frozen_reference_intact():
    protocol, frame = load_frozen_reference()
    assert len(frame) == 12440
    assert frame.unit.nunique() == 60
    assert len(protocol['folds']) == 3


def test_unknown_task_rejected():
    with pytest.raises(ValueError, match='authorized'):
        candidate_grid('fuel', pd.DataFrame(), None)
