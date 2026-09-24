import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression
from src.rul_retraining_v2 import engine_trends,battery_trends,select_on_fitting,engine_checkpoints,replay,SENSORS
from src.targeted_retraining import Candidate


def battery():
    return pd.DataFrame({'battery_id':['B0005']*40,'discharge_cycle':np.arange(1,41),
        'charge_throughput_ah':np.linspace(2,1.4,40),'duration_seconds':np.arange(40)+100,
        'voltage_mean':np.linspace(4,3,40)})


def test_new_battery_features_ignore_future_and_labels():
    frame=battery()
    full=battery_trends(frame)
    for length in (1,5,12,25):
        pd.testing.assert_frame_equal(full.iloc[:length].reset_index(drop=True),battery_trends(frame.iloc[:length]),atol=1e-9,rtol=1e-9)
    labelled=frame.assign(rul_cycles=999,observed_eol_cycle=999,soh_percent=0)
    result=battery_trends(labelled)
    pd.testing.assert_frame_equal(full,result[full.columns])


def test_engine_trends_ignore_future_and_reset_units():
    rng=np.random.default_rng(6)
    frame=pd.DataFrame({f'sensor_{i}':rng.normal(size=70) for i in SENSORS})
    frame=frame.assign(unit_id=1,cycle=np.arange(1,71))
    full=engine_trends(frame)
    for length in (1,5,12,25,60):
        pd.testing.assert_frame_equal(full.iloc[:length].reset_index(drop=True),engine_trends(frame.iloc[:length]))
    combined=engine_trends(pd.concat([frame,frame.assign(unit_id=2)]))
    pd.testing.assert_frame_equal(combined.iloc[70:].reset_index(drop=True),engine_trends(frame.assign(unit_id=2)))


def test_group_selection_uses_only_supplied_groups_and_scoped_tasks():
    frame=pd.DataFrame({'battery_id':np.repeat(['A','B','C'],10),'x':np.arange(30.),'y':np.arange(30.)*2})
    grid=[Candidate('linear',LinearRegression(),('x',),None)]
    _,results=select_on_fitting('battery_rul',frame,frame.battery_id.to_numpy(),'y',grid)
    assert {g['group'] for g in results[0]['groups']}=={'A','B','C'}
    assert results[0]['group_mean_mae']<1e-10
    with pytest.raises(ValueError,match='scope'):
        select_on_fitting('fuel',frame,frame.battery_id.to_numpy(),'y',grid)


def test_engine_sampling_is_fixed_and_never_changes_labels():
    frame=pd.DataFrame({'unit_id':[1]*100,'cycle':np.arange(1,101),'rul':np.arange(99,-1,-1)})
    check=engine_checkpoints(frame)
    assert check.cycle.tolist()==[20,40,60,80,100]
    assert check.rul.tolist()==[80,60,40,20,0]


def test_replay_rejects_unrelated_models():
    with pytest.raises(ValueError,match='scope'):
        replay('battery_soh')
