import numpy as np
import pandas as pd
import pytest

from src.battery_cutoff_review import cutoff_integral
from src.engine_validation_protocol import aligned_predictions, compare_candidate, score_predictions


def reference():
    frame = pd.DataFrame({'unit': np.repeat(['1', '2'], 9), 'cycle': np.tile(np.arange(1., 10.), 2),
                          'fold': np.repeat([1, 2], 9)})
    frame['actual'] = 9 - frame.cycle
    frame['predicted'] = frame.actual + 2.
    return frame


def test_cutoff_interpolates_first_crossing_and_excludes_later_rebound():
    result = cutoff_integral([0., 3600., 7200.], [4., 2., 4.], [-1., -1., -1.], cutoff=3.)
    assert result['cutoff_interpolated_ah'] == pytest.approx(.5)
    assert result['full_throughput_ah'] == pytest.approx(2.)
    assert result['crossing_seconds'] == pytest.approx(1800.)
    assert result['last_above_sample_ah'] == 0.
    assert result['first_below_sample_ah'] == 1.


def test_cutoff_does_not_invent_unobserved_capacity():
    assert cutoff_integral([0, 1], [4., 3.], [-1, -1])['status'] == 'no_observed_crossing'
    assert cutoff_integral([0, 1], [2., 3.], [-1, -1])['status'] == 'starts_at_or_below_cutoff'


@pytest.mark.parametrize('time,voltage,current', [([1, 0], [4, 2], [-1, -1]),
    ([0, 1], [4, np.nan], [-1, -1]), ([0, 1], [4], [-1, -1])])
def test_cutoff_rejects_invalid_curves(time, voltage, current):
    with pytest.raises(ValueError):
        cutoff_integral(time, voltage, current)


def test_protocol_accepts_improvement_but_not_baseline_as_new_gain():
    baseline = reference()
    assert not compare_candidate(baseline, baseline)['eligible_for_outer_checks']
    better = baseline.assign(predicted=baseline.actual + 1.)
    result = compare_candidate(better, baseline)
    assert result['eligible_for_outer_checks'] and not result['deployed']
    assert result['outer_audit_official_and_uncertainty_gates_still_required']
    assert result['candidate']['balanced_phase_mae'] == 1.


def test_protocol_does_not_accept_average_gain_with_late_phase_regression():
    baseline = reference()
    candidate = baseline.assign(predicted=baseline.actual)
    candidate.loc[candidate.cycle > 6, 'predicted'] += 3.
    result = compare_candidate(candidate, baseline)
    assert result['candidate']['balanced_phase_mae'] < result['baseline']['balanced_phase_mae']
    assert not result['eligible_for_outer_checks']
    assert not result['checks']['late_unit_mean_mae_no_worse']


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'extra_unit', 'fold', 'label', 'nan', 'null_unit', 'empty'])
def test_protocol_rejects_incomplete_or_changed_evidence(change):
    baseline = reference()
    candidate = baseline.copy()
    if change == 'missing': candidate = candidate.iloc[1:]
    elif change == 'duplicate': candidate = pd.concat([candidate, candidate.iloc[:1]])
    elif change == 'extra_unit': candidate.loc[0, 'unit'] = '99'
    elif change == 'fold': candidate.loc[0, 'fold'] = 99
    elif change == 'label': candidate.loc[0, 'actual'] = 999.
    elif change == 'nan': candidate.loc[0, 'predicted'] = np.nan
    elif change == 'null_unit': candidate.loc[0, 'unit'] = None
    elif change == 'empty': candidate = candidate.iloc[:0]
    with pytest.raises(ValueError):
        aligned_predictions(candidate, baseline)


def test_order_and_csv_numeric_types_do_not_change_results():
    baseline = reference()
    shuffled = baseline.sample(frac=1., random_state=1).copy()
    shuffled['unit'] = shuffled.unit.astype(int)
    shuffled['cycle'] = shuffled.cycle.astype(int)
    result = aligned_predictions(shuffled, baseline)
    assert score_predictions(result) == score_predictions(baseline)


def test_every_unit_must_have_every_phase():
    baseline = reference()
    with pytest.raises(ValueError, match='three phases'):
        score_predictions(baseline.loc[baseline.cycle > 3])
