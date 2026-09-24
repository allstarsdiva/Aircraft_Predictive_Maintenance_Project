"""Second scoped RUL experiment: causal trends and group-balanced selection.

Never activates artifacts. Previously inspected development groups remain the
same fitting/calibration/evaluation groups as the historical audit.
"""
from dataclasses import replace
import argparse
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut
from sklearn.neighbors import KNeighborsRegressor
from threadpoolctl import threadpool_limits

from src.audit_finalization import partition_groups, snapshots, split_record
from src.battery_history_retraining import history_features
from src.data.battery import DOCUMENTED_EOL_CAPACITY_AH
from src.data.cmapss import load_test_with_rul
from src.model_release import verified_release, sha256
from src.preprocessing import add_causal_engine_features
from src.readiness_modeling import FeatureSupport
from src.retrain_readiness import regression_metrics, conservative_error_quantile
from src.targeted_retraining import ROOT, Candidate, load_task, fit_candidate, prediction, evaluate, target_pass

SEED=20260912
TASKS=('battery_rul','engine')
PREVIOUS={'engine':'targeted-20260911','battery_rul':'battery-history-20260911'}
SENSORS=(2,3,4,7,8,9,11,12,13,14,15,17,20,21)


def engine_trends(table):
    if table.empty or table.duplicated(['unit_id','cycle']).any():
        raise ValueError('Unique nonempty engine cycles required')
    chunks=[]
    for _,group in table.groupby('unit_id',sort=False):
        group=group.sort_values('cycle').reset_index(drop=True)
        out=group.copy()
        features={}
        if not np.isfinite(group[['cycle',*[f'sensor_{i}' for i in SENSORS]]].to_numpy(float)).all():
            raise ValueError('Finite engine measurements required')
        for number in SENSORS:
            values=group[f'sensor_{number}']
            # First ten observed cycles; growing causal baseline until ten exist.
            initial=values.iloc[:10].expanding().mean().reindex(group.index,method='ffill')
            smooth=values.ewm(span=20,adjust=False).mean()
            prefix=f'long_sensor_{number}'
            features[f'{prefix}_ewm20']=smooth
            features[f'{prefix}_relative_initial']=smooth-initial
            for lag in (20,50):
                elapsed=group.cycle-group.cycle.shift(lag)
                features[f'{prefix}_slope_{lag}']=((smooth-smooth.shift(lag))/elapsed).fillna(0.)
            features[f'{prefix}_std30']=values.rolling(30,min_periods=1).std(ddof=0)
        chunks.append(pd.concat([out,pd.DataFrame(features)],axis=1))
    return pd.concat(chunks,ignore_index=True)


def battery_trends(table):
    base=history_features(table)
    table=table.sort_values(['battery_id','discharge_cycle']).reset_index(drop=True)
    table=table.merge(base,on=['battery_id','discharge_cycle'],validate='one_to_one',sort=False)
    chunks=[]
    for battery,group in table.groupby('battery_id',sort=False):
        if battery not in DOCUMENTED_EOL_CAPACITY_AH:
            raise ValueError('Documented EOL threshold required for battery proxy features')
        group=group.reset_index(drop=True)
        x=group.discharge_cycle.astype(float)
        q=group.charge_throughput_ah.astype(float)
        if not np.isfinite(q).all():
            raise ValueError('Finite charge throughput required')
        smooth=q.ewm(span=5,adjust=False).mean()
        extras={'trend_capacity_ewm5':smooth,
                'trend_capacity_margin':smooth-DOCUMENTED_EOL_CAPACITY_AH[battery]}
        for window in (5,15,30):
            xmean=x.rolling(window,min_periods=2).mean()
            qmean=smooth.rolling(window,min_periods=2).mean()
            cov=(x*smooth).rolling(window,min_periods=2).mean()-xmean*qmean
            var=(x*x).rolling(window,min_periods=2).mean()-xmean*xmean
            slope=(cov/var.where(var>1e-12)).fillna(0.)
            extras[f'trend_capacity_slope_{window}']=slope
            declining=slope < -1e-4
            extras[f'trend_capacity_declining_{window}']=declining.astype(float)
            extras[f'trend_life_proxy_{window}']=pd.Series(np.where(declining,
                (smooth-DOCUMENTED_EOL_CAPACITY_AH[battery])/(-slope.clip(upper=-1e-4)),500.)).clip(0,500)
        chunks.append(pd.concat([group,pd.DataFrame(extras)],axis=1))
    return pd.concat(chunks,ignore_index=True)


def engine_checkpoints(table):
    """Fixed evaluation sampling rule, never a model input or training label change."""
    chunks=[]
    for _,group in table.groupby('unit_id',sort=True):
        positions=np.unique(np.maximum(0,np.ceil(np.array([.2,.4,.6,.8,1.])*len(group)).astype(int)-1))
        chunks.append(group.iloc[positions])
    return pd.concat(chunks,ignore_index=True)


def candidate_grid(task,table,previous):
    original=tuple(previous.feature_columns)
    candidates=[Candidate('previous_candidate_spec',clone(previous.model),original,previous.target_maximum)]
    if task=='engine':
        long=tuple(f for f in table if f.startswith('long_'))
        views={'trends':('cycle',)+long,'combined':original+long}
        for view,features in views.items():
            for cap in (125.,175.,None):
                candidates.append(Candidate(f'extra_{view}_cap{cap}',ExtraTreesRegressor(n_estimators=200,
                    min_samples_leaf=2,max_features=.7,n_jobs=2,random_state=SEED),features,cap))
                candidates.append(Candidate(f'hist_{view}_cap{cap}',HistGradientBoostingRegressor(max_iter=220,
                    max_leaf_nodes=15,min_samples_leaf=25,learning_rate=.05,l2_regularization=5,
                    early_stopping=False,random_state=SEED),features,cap))
        for neighbors in (20,50):
            candidates.append(Candidate(f'knn_trends_{neighbors}',KNeighborsRegressor(n_neighbors=neighbors,
                weights='distance',n_jobs=2),views['trends'],None))
    else:
        trends=tuple(f for f in table if f.startswith('trend_'))
        physical=('discharge_cycle','ambient_temperature','charge_throughput_ah','energy_throughput_wh',
            'duration_seconds','voltage_mean','temperature_mean','current_abs_mean')
        for view,features in {'combined':original+trends,'physical':physical+trends}.items():
            for leaf in (1,3,6):
                candidates.append(Candidate(f'extra_{view}_leaf{leaf}',ExtraTreesRegressor(n_estimators=300,
                    min_samples_leaf=leaf,max_features=.8,n_jobs=2,random_state=SEED),features,None))
            candidates.append(Candidate(f'rf_{view}',RandomForestRegressor(n_estimators=250,
                min_samples_leaf=2,max_features=.8,n_jobs=2,random_state=SEED),features,None))
            for loss in ('squared_error','absolute_error'):
                candidates.append(Candidate(f'hist_{view}_{loss}',HistGradientBoostingRegressor(max_iter=250,
                    max_leaf_nodes=7,min_samples_leaf=10,learning_rate=.05,l2_regularization=10,
                    loss=loss,early_stopping=False,random_state=SEED),features,None))
            candidates.append(Candidate(f'ridge_{view}',Ridge(alpha=10),features,None))
    return candidates


def select_on_fitting(task,fit,groups,target,candidates,*,fit_function=None):
    if task not in TASKS:
        raise ValueError('Only battery and engine RUL are in scope')
    trainer=fit_function or fit_candidate
    splitter=LeaveOneGroupOut() if task=='battery_rul' else GroupKFold(n_splits=3)
    folds=list(splitter.split(fit,groups=groups))
    results=[]
    for candidate in candidates:
        group_errors=[]
        for fitting,checking in folds:
            prep,model=trainer(fit.iloc[fitting],target,candidate,False)
            validation=engine_checkpoints(fit.iloc[checking]) if task=='engine' else fit.iloc[checking]
            predicted=prediction(validation,candidate,prep,model,False)
            group_column='unit_id' if task=='engine' else 'battery_id'
            for group in validation[group_column].unique():
                mask=validation[group_column].to_numpy()==group
                actual=validation.loc[mask,target].to_numpy()
                errors=predicted[mask]-actual
                group_errors.append({'group':str(group),'mae':float(np.abs(errors).mean()),
                    'rmse':float(np.sqrt(np.mean(errors**2)))})
        mae=float(np.mean([g['mae'] for g in group_errors]))
        rmse=float(np.mean([g['rmse'] for g in group_errors]))
        score=mae if task=='battery_rul' else mae/15+rmse/20
        results.append({'candidate':candidate.name,'group_mean_mae':mae,'group_mean_rmse':rmse,
            'selection_loss':score,'groups':group_errors,'features':list(candidate.features),
            'target_cap':candidate.upper,'model_parameters':candidate.model.get_params(deep=False)})
        print(f'{task} {candidate.name}: group MAE={mae:.3f}; loss={score:.3f}',flush=True)
    best=min(range(len(candidates)),key=lambda i:results[i]['selection_loss'])
    return candidates[best],results


def run(task,output,release,*,previous_experiment=None,grid_factory=None,model_prefix='rul_v2',
        fit_function=None,feature_transform=None,selection_function=None):
    if task not in TASKS:
        raise ValueError('Only battery and engine RUL are in scope')
    table,_,target,_=load_task(task,release)
    previous_dir=ROOT/'models/candidates'/(previous_experiment or PREVIOUS[task])/task
    prior_report=json.loads((previous_dir/'evaluation.json').read_text())
    if sha256(previous_dir/'candidate.joblib')!=prior_report['candidate_sha256']:
        raise ValueError('Previous candidate checksum mismatch')
    previous=joblib.load(previous_dir/'candidate.joblib')
    table=engine_trends(table) if task=='engine' else battery_trends(table)
    if feature_transform is not None:
        table=feature_transform(task,table)
    trainer=fit_function or fit_candidate
    group_column='unit_id' if task=='engine' else 'battery_id'
    groups=table[group_column].to_numpy()
    split=partition_groups(groups)
    split_info=split_record(groups,split)
    if split_info!=prior_report['split']:
        raise ValueError('Previous comparison partitions differ')
    fitting,calibration,evaluation=(table.iloc[idx].copy() for idx in split)
    grid=(grid_factory or candidate_grid)(task,fitting,previous)
    selector=selection_function or select_on_fitting
    selected,tuning=selector(task,fitting,groups[split[0]],target,grid,fit_function=trainer)
    prep,model=trainer(fitting,target,selected,False)
    if task=='engine':
        calibration,evaluation=snapshots(calibration),snapshots(evaluation)
    radius=conservative_error_quantile(calibration[target]-prediction(calibration,selected,prep,model,False),previous.interval_alpha)
    bundle=replace(previous,model=model,preprocessor=prep,feature_columns=selected.features,
        model_name=f'{model_prefix}_{selected.name}',target_maximum=selected.upper,absolute_error_quantile=radius,
        feature_support=FeatureSupport.fit(fitting,selected.features),
        validation_protocol='group_balanced_inner_selection_separate_calibration_and_fixed_audit_development_only')
    metrics,records=evaluate(bundle,evaluation,target,False)
    before,_=evaluate(previous,evaluation,target,False)
    for key,value in prior_report['evaluation_metrics'].items():
        if not np.isclose(before[key],value,atol=1e-8,rtol=1e-8):
            raise ValueError(f'Previous audit replay differs: {key}')
    bundle.validation_metrics=metrics
    destination=output/task
    destination.mkdir(parents=True,exist_ok=False)
    joblib.dump(bundle,destination/'candidate.joblib',compress=3)
    restored=joblib.load(destination/'candidate.joblib')
    np.testing.assert_allclose(bundle.predict_feature_frame(evaluation),restored.predict_feature_frame(evaluation))
    records.to_csv(destination/'audit_predictions.csv',index=False)
    # Preserve exactly the supplied feature values for reproducible replay.
    evaluation.loc[:,selected.features].to_csv(destination/'audit_inputs.csv',index=False)
    result={'task':task,'source_release':release.name,'selected_candidate':selected.name,'split':split_info,
        'selection':tuning,'evaluation_metrics':metrics,'previous_candidate_metrics':before,
        'previous_experiment':previous_experiment or PREVIOUS[task],
        'candidate_sha256':sha256(destination/'candidate.joblib'),
        'audit_inputs_sha256':sha256(destination/'audit_inputs.csv'),
        'meets_numerical_target':target_pass(task,metrics),
        'improves_previous_mae':metrics['mae']<before['mae'],
        'independent_external_test':False,'deployed':False,
        'calibration':{'rows':len(calibration),'groups':len(np.unique(groups[split[1]])),
            'nominal_coverage':1-bundle.interval_alpha,'radius':radius},
        'limitations':['All datasets and audit labels previously inspected; not new independent validation.',
            'Battery has few independent groups; interval coverage is not guaranteed.',
            'New trend inputs require their causal feature generator; current API is not changed.']}
    if task=='engine':
        test=engine_trends(add_causal_engine_features(load_test_with_rul('FD001')))
        if feature_transform is not None:
            test=feature_transform(task,test)
        terminal=test.loc[test.groupby('unit_id').cycle.idxmax()]
        official,official_rows=evaluate(bundle,terminal,'rul',False)
        previous_official,_=evaluate(previous,terminal,'rul',False)
        result.update(official_test_regression_check=official,previous_candidate_official_check=previous_official,
            official_target_pass=target_pass(task,official),official_used_for_selection=False)
        official_rows.to_csv(destination/'official_predictions.csv',index=False)
    (destination/'evaluation.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('task','selected_candidate','evaluation_metrics','previous_candidate_metrics','meets_numerical_target')},indent=2),flush=True)
    return result


def replay(task,*,experiment='rul-retrain-20260912'):
    if task not in TASKS:
        raise ValueError('Only battery and engine RUL are in scope')
    destination=ROOT/'models/candidates'/experiment/task
    report=json.loads((destination/'evaluation.json').read_text())
    for name,key in [('candidate.joblib','candidate_sha256'),('audit_inputs.csv','audit_inputs_sha256')]:
        if sha256(destination/name)!=report[key]:
            raise ValueError(f'Saved candidate replay checksum mismatch: {name}')
    bundle=joblib.load(destination/'candidate.joblib')
    inputs=pd.read_csv(destination/'audit_inputs.csv',float_precision='round_trip')
    stored=pd.read_csv(destination/'audit_predictions.csv',float_precision='round_trip')
    predicted,lower,upper=bundle.predict_interval(inputs)
    np.testing.assert_allclose(predicted,stored.predicted,rtol=1e-10,atol=1e-10)
    np.testing.assert_allclose(lower,stored.lower,rtol=1e-10,atol=1e-10)
    np.testing.assert_allclose(upper,stored.upper,rtol=1e-10,atol=1e-10)
    return {'task':task,'model':bundle.model_name,'replay_matches_saved_predictions':True,
        'evaluation_metrics':regression_metrics(stored.actual,predicted),
        'note':'Replay of the existing development audit, not an independent test. Candidate is not deployed.'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tasks',nargs='+',choices=TASKS,default=list(TASKS))
    parser.add_argument('--replay',action='store_true',help='Verify and replay saved candidates without training')
    args=parser.parse_args()
    if len(set(args.tasks))!=len(args.tasks):
        parser.error('Duplicate tasks are not allowed')
    if args.replay:
        for task in args.tasks:
            print(json.dumps(replay(task),indent=2))
        return
    output=ROOT/'models/candidates/rul-retrain-20260912'
    if any((output/task).exists() for task in args.tasks):
        parser.error('Preserve existing results: selected task outputs already exist')
    release,manifest=verified_release()
    for relative in ('data/processed/battery/rul_features.csv',):
        if sha256(ROOT/relative)!=manifest['data_hashes'][relative]:
            raise ValueError('Source dataset differs from baseline release')
    for filename,digest in manifest['engine_source_hashes'].items():
        if sha256(ROOT/'data/raw/engine'/filename)!=digest:
            raise ValueError('Engine source dataset differs from baseline release')
    pointer_before=sha256(ROOT/'models/releases/current.json')
    with threadpool_limits(limits=2):
        for task in args.tasks:
            run(task,output,release)
    assert sha256(ROOT/'models/releases/current.json')==pointer_before
    verified_release()
    print('Scoped RUL retraining complete; active release unchanged.',flush=True)


if __name__=='__main__':
    main()
