import numpy as np
import pandas as pd
import pytest

from src.data.fuel_system import FUEL_SENSOR_COLUMNS
from src.fuel_target_experiment import TemporalCandidate, fit_temporal, select_temporal, trailing_mean
from src.improve_fuel import outer_plan


def frame(n=100):
    rng = np.random.default_rng(64)
    data = pd.DataFrame(rng.normal(size=(n, 8)), columns=FUEL_SENSOR_COLUMNS)
    return data.assign(scenario_id='normal', sample_index=np.arange(1, n+1), is_abnormal=0)


def test_temporal_prefix_and_gap_and_scenario_reset():
    data = frame()
    np.testing.assert_allclose(trailing_mean(data, 9).FTF[:20], trailing_mean(data.iloc[:20], 9).FTF)
    with_gap = pd.concat([data.iloc[:20], data.iloc[40:60]])
    np.testing.assert_allclose(trailing_mean(with_gap, 9).FTF[20:], trailing_mean(data.iloc[40:60], 9).FTF)
    other = data.copy().assign(scenario_id='other')
    combined = pd.concat([data, other])
    np.testing.assert_allclose(trailing_mean(combined, 9).FTF[100:], trailing_mean(other, 9).FTF)


def test_temporal_prediction_causality_and_fit_guards():
    data = frame()
    candidate = TemporalCandidate('mahalanobis', 5, True, .975)
    model = fit_temporal(data.iloc[:60], data.iloc[60:80], candidate)
    query = data.copy()
    query.loc[25:, 'FTF'] = 100
    np.testing.assert_array_equal(model.predict_feature_frame(query)[:40], model.predict_feature_frame(query.iloc[:40]))
    assert model.predict_feature_frame(query)[35:].mean() == 1
    with pytest.raises(ValueError, match='normal samples only'):
        fit_temporal(data.assign(is_abnormal=1), data, candidate)
    with pytest.raises(ValueError, match='normal samples only'):
        fit_temporal(data, data.assign(is_abnormal=1), candidate)
    with pytest.raises(ValueError, match='finite'):
        model.predict_feature_frame(data.assign(FTF=np.nan))
    with pytest.raises(ValueError, match='windows'):
        trailing_mean(data, 0)


def test_temporal_selection_never_reads_outer_normal_block():
    normal = frame()
    faults = normal.assign(scenario_id='fault', is_abnormal=1, FTF=20)
    blocks, plan = outer_plan(normal, ['a', 'b', 'c', 'd'])
    available = plan[0]['development_blocks']
    candidates = (TemporalCandidate('max', 5, False, .95), TemporalCandidate('max', 9, False, .99))
    before = select_temporal(normal, faults, blocks, available, candidates)
    changed = normal.copy()
    changed.loc[blocks[0], list(FUEL_SENSOR_COLUMNS)] = 1e12
    assert before == select_temporal(changed, faults, blocks, available, candidates)
