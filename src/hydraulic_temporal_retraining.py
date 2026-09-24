"""Cycle-phase features for valve/accumulator only; offline completed-cycle input."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from src.data.hydraulic import HYDRAULIC_SENSORS, load_hydraulic_sensor
from src.model_release import verified_release, sha256
from src.targeted_retraining import ROOT, SEED, Candidate, load_task, run_task

SENSORS = ('PS1','PS2','PS3','PS4','PS5','PS6','EPS1','FS1','FS2')


def phase_features(values, sensor):
    if sensor not in SENSORS:
        raise ValueError('Unsupported phase-feature sensor')
    matrix = np.asarray(values, float)
    hz = HYDRAULIC_SENSORS[sensor].sampling_hz
    if matrix.ndim != 2 or matrix.shape[1] != hz*60 or not np.isfinite(matrix).all():
        raise ValueError('Finite complete 60-second cycles are required')
    seconds = matrix.reshape(len(matrix), 60, hz)
    means, stds = seconds.mean(axis=2), seconds.std(axis=2)
    centered = means - means[:, :1]
    return pd.DataFrame({f'{sensor.lower()}_phase_{kind}_{i:02d}': values[:,i]
        for kind, values in [('mean',means),('std',stds),('relative',centered)] for i in range(60)})


def build_phase_table():
    parts, hashes = [], {}
    for sensor in SENSORS:
        parts.append(phase_features(load_hydraulic_sensor(sensor).to_numpy(), sensor))
        hashes[f'{sensor}.txt'] = sha256(ROOT/'data/raw/hydraulic'/f'{sensor}.txt')
        print(f'Extracted 1-second phase summaries: {sensor}',flush=True)
    table = pd.concat(parts,axis=1)
    table.insert(0,'cycle_id',np.arange(1,len(table)+1))
    return table, hashes


def phase_candidates(features):
    candidates = []
    views = {'all':tuple(features),
        'relative':tuple(f for f in features if '_relative_' in f or '_std_' in f),
        'ps1_ps2_ps3':tuple(f for f in features if f.startswith(('ps1_','ps2_','ps3_')))}
    for name, selected in views.items():
        for c in (.1, 10.):
            candidates.append(Candidate(f'phase_logistic_{name}_C{c}',LogisticRegression(
                C=c, max_iter=3000, class_weight='balanced', random_state=SEED),selected,None))
        candidates.append(Candidate(f'phase_lda_{name}',LinearDiscriminantAnalysis(
            solver='lsqr',shrinkage='auto'),selected,None))
        candidates.append(Candidate(f'phase_extra_{name}',ExtraTreesClassifier(n_estimators=180,
            min_samples_leaf=2,max_features='sqrt',class_weight='balanced',n_jobs=2,
            random_state=SEED),selected,None))
    return candidates


def main():
    release, _ = verified_release()
    output=ROOT/'models/candidates/hydraulic-phase-20260911'
    if output.exists():
        raise FileExistsError('Preserve previous results; use a separate version for new experiments')
    features, hashes = build_phase_table()
    output.mkdir(parents=True)
    path=ROOT/'data/processed/hydraulic/cycle_temporal_features_v1.csv'
    if path.exists():
        raise FileExistsError('Do not overwrite existing waveform features')
    features.to_csv(path,index=False)
    hashes['profile.txt']=sha256(ROOT/'data/raw/hydraulic/profile.txt')
    evidence={'feature_file':path.relative_to(ROOT).as_posix(),'sha256':sha256(path),
        'raw_sha256':hashes,'rows':len(features),'feature_count':len(features.columns)-1,
        'requires_complete_cycle':True,'seconds_per_cycle':60,
        'scope':'Only valve and accumulator; no future-cycle or label-derived features.',
        'protocol':'Follow-up development experiment after summary-feature candidates; reused outer split is not an independent final test.'}
    (output/'features.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    grid=phase_candidates(features.columns[1:])
    with threadpool_limits(limits=2):
        for task in ('hydraulic_valve','hydraulic_accumulator'):
            print(f'Starting phase-aware {task}',flush=True)
            run_task(task,output,release,feature_table=features,candidate_grid=grid)
    verified_release()


if __name__=='__main__':
    main()
