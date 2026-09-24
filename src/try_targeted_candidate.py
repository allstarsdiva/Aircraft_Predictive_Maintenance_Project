"""Replay a saved scoped candidate on its audit inputs without deployment.

Example: python -m src.try_targeted_candidate --task hydraulic_valve
This is previously evaluated dataset replay, not new validation.
"""
import argparse
import json
import joblib
import pandas as pd

from src.audit_finalization import partition_groups, snapshots
from src.model_release import verified_release, sha256
from src.targeted_retraining import ROOT, TASKS, load_task, evaluate

RUNS={'engine':'targeted-20260911','battery_soh':'targeted-20260911',
      'battery_rul':'battery-history-20260911',
      'hydraulic_valve':'hydraulic-phase-20260911',
      'hydraulic_accumulator':'hydraulic-phase-20260911'}


def replay(task):
    if task not in TASKS:
        raise ValueError('Task outside authorized candidate scope')
    release,_=verified_release()
    directory=ROOT/'models/candidates'/RUNS[task]/task
    report=json.loads((directory/'evaluation.json').read_text())
    artifact=directory/'candidate.joblib'
    if sha256(artifact)!=report['candidate_sha256']:
        raise ValueError('Candidate checksum differs from evaluated artifact')
    table,groups,target,_=load_task(task,release)
    feature_evidence=directory.parent/'features.json'
    if feature_evidence.exists():
        evidence=json.loads(feature_evidence.read_text())
        path=ROOT/evidence['feature_file']
        if sha256(path)!=evidence['sha256']:
            raise ValueError('Candidate feature file checksum mismatch')
        extra=pd.read_csv(path, float_precision='round_trip')
        keys=['cycle_id'] if task.startswith('hydraulic') else ['battery_id','discharge_cycle']
        table=table.merge(extra,on=keys,how='left',validate='one_to_one',sort=False)
    _,_,checking=partition_groups(groups)
    check=table.iloc[checking]
    if task=='engine':
        check=snapshots(check)
    bundle=joblib.load(artifact)
    metrics,records=evaluate(bundle,check,target,task.startswith('hydraulic'))
    import numpy as np
    for name, expected in report['evaluation_metrics'].items():
        if expected is not None and not np.isclose(metrics[name], expected, atol=1e-10, rtol=1e-10):
            raise ValueError(f'Replay metric differs from evaluated artifact: {name}')
    return {'task':task,'model':bundle.model_name,'deployed':False,
        'evaluation_note':'Replay of previously inspected development audit; not a new test.',
        'metrics':metrics,'first_five_predictions':records.head(5).to_dict(orient='records')}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--task',required=True,choices=TASKS)
    print(json.dumps(replay(parser.parse_args().task),indent=2,allow_nan=False))
