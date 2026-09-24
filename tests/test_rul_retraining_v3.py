from types import SimpleNamespace

import pandas as pd
import pytest
from sklearn.ensemble import ExtraTreesRegressor

from src.rul_retraining_v3 import candidate_grid, PREVIOUS, EXPERIMENT


def previous():
    return SimpleNamespace(model=ExtraTreesRegressor(n_estimators=3),
                           feature_columns=('cycle',), target_maximum=175.)


def test_engine_grid_is_bounded_and_keeps_baseline():
    baseline = previous()
    grid = candidate_grid('engine', pd.DataFrame(columns=['cycle']), baseline)
    assert len(grid) == 10
    assert grid[0].model is not baseline.model
    assert grid[0].model.get_params() == baseline.model.get_params()
    assert all(c.features == ('cycle',) for c in grid)
    assert {c.upper for c in grid} == {175., 225., None}


def test_battery_grid_has_no_label_or_identity_features():
    columns = ['cycle', 'discharge_cycle', 'charge_throughput_ah', 'duration_seconds',
               'voltage_mean', 'temperature_mean', 'trend_capacity_margin',
               'trend_capacity_slope_15', 'trend_capacity_slope_30']
    grid = candidate_grid('battery_rul', pd.DataFrame(columns=columns), previous())
    assert len(grid) == 15
    for candidate in grid:
        assert not {'battery_id', 'rul_cycles', 'observed_eol_cycle', 'soh_percent'} & set(candidate.features)


def test_grid_rejects_out_of_scope_or_missing_inputs():
    with pytest.raises(ValueError, match='scope'):
        candidate_grid('fuel', pd.DataFrame(), previous())
    with pytest.raises(ValueError, match='inputs'):
        candidate_grid('battery_rul', pd.DataFrame(columns=['cycle']), previous())


def test_previous_candidates_and_output_are_separate():
    assert PREVIOUS['engine'] == 'rul-retrain-20260912'
    assert PREVIOUS['battery_rul'] == 'battery-history-20260911'
    assert EXPERIMENT not in PREVIOUS.values()
