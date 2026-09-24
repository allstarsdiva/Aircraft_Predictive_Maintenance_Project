"""Past-only battery discharge trends for a separate RUL research candidate."""
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.svm import SVR
from threadpoolctl import threadpool_limits

from src.model_release import verified_release, sha256
from src.targeted_retraining import ROOT, SEED, Candidate, load_task, run_task


def history_features(table):
    required = ['battery_id','discharge_cycle','charge_throughput_ah','duration_seconds','voltage_mean']
    missing = set(required)-set(table.columns)
    if missing:
        raise ValueError(f'Missing history inputs: {sorted(missing)}')
    if table.empty or table.duplicated(['battery_id','discharge_cycle']).any():
        raise ValueError('Nonempty unique battery cycles required')
    if not np.isfinite(table[required[1:]].to_numpy(float)).all():
        raise ValueError('Finite battery history required')
    chunks=[]
    for battery, group in table.groupby('battery_id',sort=False):
        group=group.sort_values('discharge_cycle').reset_index(drop=True)
        out=group[['battery_id','discharge_cycle']].copy()
        out['history_count']=np.arange(1,len(group)+1)
        for name in ('charge_throughput_ah','duration_seconds','voltage_mean'):
            values=group[name]
            out[f'history_{name}_relative_first']=values-values.iloc[0]
            for window in (5,15):
                out[f'history_{name}_mean_{window}']=values.rolling(window,min_periods=1).mean()
                out[f'history_{name}_std_{window}']=values.rolling(window,min_periods=1).std(ddof=0)
                # Fixed lag: appending future cycles must not change earlier features.
                lag=window-1
                if lag:
                    denominator=group.discharge_cycle-group.discharge_cycle.shift(lag)
                    out[f'history_{name}_slope_{window}']=((values-values.shift(lag))/denominator).fillna(0)
                else:
                    out[f'history_{name}_slope_{window}']=0.
        chunks.append(out)
    return pd.concat(chunks,ignore_index=True)


def main():
    release,_=verified_release()
    table,_,_,existing=load_task('battery_rul',release)
    features=history_features(table)
    output=ROOT/'models/candidates/battery-history-20260911'
    if output.exists():
        raise FileExistsError('Preserve earlier candidate outputs')
    path=ROOT/'data/processed/battery/rul_history_features_v1.csv'
    if path.exists():
        raise FileExistsError('Preserve earlier history features')
    features.to_csv(path,index=False)
    output.mkdir(parents=True)
    (output/'features.json').write_text(json.dumps({'feature_file':path.relative_to(ROOT).as_posix(),
        'sha256':sha256(path),'input_sha256':sha256(ROOT/'data/processed/battery/rul_features.csv'),
        'requires_past_discharge_history':True,'future_cycles_used':False,
        'label_columns_used':False,'deployed':False,
        'limitation':'Follow-up development experiment; reused audit split is not a new final test.'},indent=2),encoding='utf-8')
    chosen=existing.feature_columns+tuple(f for f in features if f not in ('battery_id','discharge_cycle'))
    grid=[]
    for alpha in (1.,10.,100.):
        grid.append(Candidate(f'history_ridge_{alpha}',Ridge(alpha=alpha),chosen,None))
    for leaf in (7,15):
        grid.append(Candidate(f'history_hist_{leaf}',HistGradientBoostingRegressor(max_iter=250,
            max_leaf_nodes=leaf,min_samples_leaf=10,learning_rate=.05,l2_regularization=10,
            early_stopping=False,random_state=SEED),chosen,None))
    grid.append(Candidate('history_extra',ExtraTreesRegressor(n_estimators=250,
        min_samples_leaf=2,max_features=.8,n_jobs=2,random_state=SEED),chosen,None))
    for c in (10.,100.):
        grid.append(Candidate(f'history_svr_{c}',SVR(C=c,epsilon=.1),chosen,None))
    with threadpool_limits(limits=2):
        run_task('battery_rul',output,release,feature_table=features,candidate_grid=grid)
    verified_release()


if __name__=='__main__':
    main()
