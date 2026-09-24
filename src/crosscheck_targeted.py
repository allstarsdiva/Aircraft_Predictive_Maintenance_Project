"""Paired fixed-specification grouped checks for the three improved candidates.

Previously used development data: scores are not new independent validation.
No tuning, calibration changes, or artifact promotion happens here.
"""
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from threadpoolctl import threadpool_limits

from src.targeted_retraining import ROOT, Candidate, load_task, fit_candidate, prediction, target_pass
from src.model_release import verified_release, sha256
from src.retrain_readiness import classification_metrics, regression_metrics
from src.train_hydraulic import grouped_hydraulic_folds


def main():
    release,_=verified_release()
    output=ROOT/'reports/metrics/targeted_retraining_20260911'
    output.mkdir(parents=True,exist_ok=True)
    results={}
    with threadpool_limits(limits=2):
        for task in ('hydraulic_valve','hydraulic_accumulator','battery_soh'):
            directory='targeted-20260911' if task=='battery_soh' else 'hydraulic-phase-20260911'
            artifact=ROOT/'models/candidates'/directory/task/'candidate.joblib'
            winner=joblib.load(artifact)
            table,groups,target,old=load_task(task,release)
            classifier=task.startswith('hydraulic')
            if classifier:
                extra=pd.read_csv(ROOT/'data/processed/hydraulic/cycle_temporal_features_v1.csv', float_precision='round_trip')
                extra=extra.set_index('cycle_id').loc[table.cycle_id].reset_index(drop=True)
                table=pd.concat([table,extra],axis=1)
                folds=list(grouped_hydraulic_folds(table,target,random_state=42))
            else:
                folds=list(GroupKFold(n_splits=5).split(table,groups=groups))
            task_results={}
            records=table[[target]].rename(columns={target:'actual'}).copy()
            records['group']=groups
            records['source_index']=table.index
            fold_numbers=np.full(len(table),-1,dtype=int)
            for label,bundle in [('previous',old),('candidate',winner)]:
                candidate=Candidate(label,bundle.model,bundle.feature_columns,getattr(bundle,'target_maximum',None))
                predicted=np.full(len(table),np.nan)
                for number,(fitting,checking) in enumerate(folds):
                    assert set(groups[fitting]).isdisjoint(groups[checking])
                    prep,model=fit_candidate(table.iloc[fitting],target,candidate,classifier)
                    predicted[checking]=prediction(table.iloc[checking],candidate,prep,model,classifier)
                    fold_numbers[checking]=number
                assert np.isfinite(predicted).all() and (fold_numbers>=0).all()
                metrics=classification_metrics(table[target],predicted) if classifier else regression_metrics(table[target],predicted)
                records[label]=predicted
                task_results[label]={'metrics':metrics,'meets_target':target_pass(task,metrics)}
            records['fold']=fold_numbers
            records.to_csv(output/f'{task}_paired_oof.csv',index=False)
            task_results.update(candidate_sha256=sha256(artifact),fold_count=len(folds),
                independent_external_test=False,
                note='Fixed winner chosen in earlier inner CV; this whole-dataset check reuses development data, not nested selection or external validation.')
            results[task]=task_results
            print(task,json.dumps(task_results),flush=True)
    (output/'paired_crosscheck.json').write_text(json.dumps(results,indent=2,allow_nan=False),encoding='utf-8')
    verified_release()


if __name__=='__main__':
    main()
