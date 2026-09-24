import numpy as np
import pandas as pd
import pytest
from src.battery_history_retraining import history_features


def data():
    return pd.DataFrame({'battery_id':['A']*30,'discharge_cycle':np.arange(1,31),
        'charge_throughput_ah':np.linspace(2,1.4,30),'duration_seconds':np.arange(30)+100,
        'voltage_mean':np.linspace(4,3,30)})


def test_history_features_do_not_use_future_cycles_or_labels():
    frame=data()
    full=history_features(frame)
    for length in (1,3,5,12,20):
        partial=history_features(frame.iloc[:length])
        pd.testing.assert_frame_equal(full.iloc[:length].reset_index(drop=True),partial)
    pd.testing.assert_frame_equal(full,history_features(frame.assign(rul_cycles=999,soh_percent=0)))


def test_history_resets_for_each_battery_and_invalid_input_fails():
    first=data()
    second=data().assign(battery_id='B',charge_throughput_ah=20.)
    combined=history_features(pd.concat([first,second]))
    pd.testing.assert_frame_equal(combined.iloc[30:].reset_index(drop=True),history_features(second))
    with pytest.raises(ValueError,match='unique'):
        history_features(pd.concat([first,first]))
