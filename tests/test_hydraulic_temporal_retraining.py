import numpy as np
import pandas as pd
import pytest
from src.hydraulic_temporal_retraining import phase_features, phase_candidates


def test_phase_features_are_independent_between_cycles():
    data=np.tile(np.arange(6000.),(2,1))
    before=phase_features(data,'PS1')
    data[1,:]=9999
    after=phase_features(data,'PS1')
    np.testing.assert_allclose(before.iloc[0],after.iloc[0])
    assert before.ps1_phase_mean_00.iloc[0]==49.5
    assert before.ps1_phase_relative_01.iloc[0]==100


def test_complete_finite_cycles_required():
    with pytest.raises(ValueError,match='complete'):
        phase_features(np.zeros((2,5900)),'PS1')
    with pytest.raises(ValueError,match='Finite'):
        phase_features(np.full((2,6000),np.nan),'PS1')


def test_phase_candidates_have_only_sensor_predictors():
    features=phase_features(np.zeros((2,6000)),'PS1').columns
    for candidate in phase_candidates(features):
        assert candidate.features and all(f.startswith('ps1_phase_') for f in candidate.features)


def test_phase_feature_csv_round_trip_preserves_support_boundaries(tmp_path):
    values=np.random.default_rng(2).normal(size=(3,6000))
    features=phase_features(values,'PS1')
    path=tmp_path/'phase.csv'
    features.to_csv(path,index=False)
    restored=pd.read_csv(path,float_precision='round_trip')
    np.testing.assert_array_equal(features.to_numpy(),restored.to_numpy())
