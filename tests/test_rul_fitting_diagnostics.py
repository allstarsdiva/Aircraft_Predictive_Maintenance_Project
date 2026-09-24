import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

from src.audit_finalization import partition_groups, split_record
from src.rul_fitting_diagnostics import fitting_partition, quality_checks, source_battery_review, grouped_oof, summarize_oof
from src.targeted_retraining import Candidate


def test_only_prespecified_fitting_units_are_returned():
    table = pd.DataFrame({'battery_id': np.repeat(list('ABCDE'), 3), 'value': np.arange(15)})
    groups = table.battery_id.to_numpy()
    expected = split_record(groups, partition_groups(groups))
    fitting = fitting_partition(table, 'battery_id', expected)
    assert set(fitting.battery_id) == set(expected['fit']['groups'])
    assert not set(fitting.battery_id) & set(expected['evaluation']['groups'])
    with pytest.raises(ValueError, match='partition'):
        fitting_partition(table, 'battery_id', {})


def test_engine_quality_detects_gaps_and_inconsistent_labels():
    frame = pd.DataFrame({'unit_id': [1, 1, 1], 'cycle': [1, 2, 4], 'rul': [3, 2, 1], 'sensor_1': [1., 1., np.nan]})
    quality = quality_checks('engine', frame)
    assert quality['per_unit'][0]['cycle_gaps'] == 1
    assert quality['per_unit'][0]['label_mismatch_rows'] == 1
    assert quality['nonfinite_by_column']['sensor_1'] == 1


def test_source_crossing_review_filters_out_nonfitting_batteries():
    rows = []
    for cycle, capacity in enumerate([2., 1.8, .1, 1.7, 1.6, 1.5], 1):
        rows.append(dict(type='discharge', start_time=f'[2020 1 {cycle} 0 0 0]', battery_id='B0006',
                         test_id=cycle, uid=cycle, filename=f'{cycle}.csv', Capacity=capacity))
    # This malformed nonfitting row must be excluded before parsing or labeling.
    rows.append(dict(type='discharge', start_time='invalid', battery_id='B0005', test_id=1, uid=99, filename='99.csv', Capacity='bad'))
    fitting = pd.DataFrame({'battery_id': ['B0006'] * 3, 'uid': [1, 2, 3], 'discharge_cycle': [1, 2, 3],
                            'observed_eol_cycle': [3, 3, 3], 'rul_cycles': [2, 1, 0]})
    original = fitting.copy(deep=True)
    result = source_battery_review(pd.DataFrame(rows), fitting)
    assert result['processed_source_label_mismatch_rows'] == 0
    crossing = result['crossings'][0]
    assert crossing['following_above_threshold_count'] == 3
    assert crossing['review_first_crossing_stability']
    assert result['fitting_units_only'] == ['B0006']
    pd.testing.assert_frame_equal(fitting, original)


def test_oof_scores_every_row_once_with_disjoint_units():
    frame = pd.DataFrame({'battery_id': np.repeat(list('ABC'), 12), 'discharge_cycle': np.tile(np.arange(1, 13), 3),
                          'ambient_temperature': 24., 'uid': np.arange(36)})
    frame['rul_cycles'] = 12 - frame.discharge_cycle
    candidate = Candidate('linear', LinearRegression(), ('discharge_cycle',), None)
    scored, folds = grouped_oof('battery_rul', frame, candidate)
    assert len(scored) == len(frame)
    assert len(folds) == 3 and all(not set(f['training_units']) & set(f['validation_units']) for f in folds)
    assert summarize_oof(scored)['all_cycles']['row_mae'] < 1e-10
    assert set(scored.phase) == {'early', 'middle', 'late'}


def test_engine_cap_floor_is_reported_without_changing_labels():
    frame = pd.DataFrame({'unit_id': np.repeat([1, 2, 3], 20), 'cycle': np.tile(np.arange(1, 21), 3)})
    frame['rul'] = 20 - frame.cycle
    candidate = Candidate('linear_capped', LinearRegression(), ('cycle',), 10.)
    original = frame.copy(deep=True)
    scored, _ = grouped_oof('engine', frame, candidate)
    assert scored.fixed_checkpoint.sum() == 15
    assert scored.cap_error_floor.max() == 9.
    assert (scored.predicted <= 10).all()
    pd.testing.assert_frame_equal(frame, original)


def test_group_balanced_error_is_distinct_from_row_weighted_error():
    frame = pd.DataFrame({'unit': ['A'] * 9 + ['B'], 'cycle': range(10), 'error': [0.] * 9 + [10.],
                          'phase': 'early', 'rul_band': '>100', 'fixed_checkpoint': True,
                          'lifetime_above_training_max': False, 'cap_error_floor': 0.})
    summary = summarize_oof(frame)['all_cycles']
    assert summary['row_mae'] == 1.
    assert summary['unit_mean_mae'] == 5.
