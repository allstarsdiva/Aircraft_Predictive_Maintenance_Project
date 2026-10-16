"""Evaluate FD002-FD004 training data as supplementary engine RUL data.

The active release and retained champion are never overwritten. FD001 fitting
engines define the frozen grouped OOF score; FD001 calibration/audit groups are
untouched until a candidate passes the frozen inner gate. C-MAPSS test files are
not used for training or candidate selection.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from src import engine_validation_protocol as protocol
from src.audit_finalization import partition_groups, snapshots, split_record
from src.data.cmapss import load_training_with_rul, load_test_with_rul
from src.model_release import ROOT, sha256, verified_release
from src.preprocessing import add_causal_engine_features
from src.readiness_modeling import FeatureSupport
from src.retrain_readiness import _preprocessor, conservative_error_quantile
from src.rul_retraining_v2 import engine_trends
from src.targeted_retraining import Candidate, evaluate, prediction
from src.rul_retraining_v5 import nonregression_gate

EXPERIMENT = 'engine-cross-subset-20260925'
PREVIOUS_ENGINE_RUN = 'rul-retrain-20260912'
MIX_SHARES = (0.25, 0.50)
EXTRA_SUBSETS = ('FD002', 'FD003', 'FD004')


def _read_protocol():
    protocol_path = ROOT / protocol.PROTOCOL
    if sha256(protocol_path) != protocol_path.with_suffix('.sha256').read_text().strip():
        raise ValueError('Frozen engine protocol seal mismatch')
    frozen = json.loads(protocol_path.read_text())
    if sha256(Path(protocol.__file__)) != frozen['scorer_sha256']:
        raise ValueError('Frozen scorer changed')
    if sha256(ROOT / protocol.REFERENCE) != frozen['reference_sha256']:
        raise ValueError('Frozen OOF reference changed')
    return frozen, pd.read_csv(ROOT / protocol.REFERENCE, dtype={'unit': str}, float_precision='round_trip')


def _load_training():
    frames = []
    next_id = 100
    hashes = {}
    for subset in ('FD001', *EXTRA_SUBSETS):
        relative = f'data/raw/engine/train_{subset}.txt'
        hashes[relative] = sha256(ROOT / relative)
        frame = load_training_with_rul(subset)
        if subset != 'FD001':
            frame['unit_id'] = frame.unit_id + next_id
            next_id = int(frame.unit_id.max())
        frame['source_subset'] = subset
        frames.append(frame)
    raw = pd.concat(frames, ignore_index=True)
    if raw.duplicated(['unit_id', 'cycle']).any():
        raise ValueError('Cross-subset unit remapping failed')
    feature_table = engine_trends(add_causal_engine_features(raw)).reset_index(drop=True)
    return feature_table, hashes


def _fit_augmented(train_target, auxiliary, candidate, extra_share):
    if not 0 < extra_share < 1:
        raise ValueError('Supplemental-data share must be between zero and one')
    combined = pd.concat([train_target, auxiliary], ignore_index=True)
    combined = combined.copy()
    combined['rul'] = combined.rul.clip(lower=0, upper=candidate.upper)

    weights = np.zeros(len(combined), dtype=float)
    for subset, share in [('FD001', 1.0 - extra_share),
                          *((name, extra_share / len(EXTRA_SUBSETS)) for name in EXTRA_SUBSETS)]:
        subset_mask = combined.source_subset.to_numpy() == subset
        subset_frame = combined.loc[subset_mask]
        units = subset_frame.unit_id.nunique()
        for _, indices in subset_frame.groupby('unit_id', sort=False).groups.items():
            positions = np.asarray(list(indices), dtype=int)
            weights[positions] = share / units / len(positions)
    if not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError('Invalid equal-subset/equal-engine fitting weights')

    prep = _preprocessor()
    transformed = prep.fit_transform(combined.loc[:, candidate.features])
    feature_names = np.asarray(candidate.features)[prep.named_steps['variance'].get_support()]
    transformed = pd.DataFrame(transformed, columns=feature_names, index=combined.index)
    model = clone(candidate.model)
    model.fit(transformed, combined.rul.to_numpy(float), sample_weight=weights)
    return prep, model


def _candidate_oof(target, auxiliary, candidate, extra_share, frozen):
    expected_folds = frozen['folds']
    fitting_units = set(frozen['fitting_units'])
    target = target.loc[target.unit_id.astype(str).isin(fitting_units)].copy().reset_index(drop=True)
    groups = target.unit_id.to_numpy()
    if sorted(map(str, np.unique(groups))) != frozen['fitting_units']:
        raise ValueError('FD001 fitting-unit coverage differs from the frozen protocol')
    rows = []
    seen_folds = []
    for number, fold in enumerate(expected_folds, start=1):
        train_units = set(fold['training_units'])
        validation_units = set(fold['validation_units'])
        training = target.loc[target.unit_id.astype(str).isin(train_units)]
        checking = target.loc[target.unit_id.astype(str).isin(validation_units)].copy()
        if set(training.unit_id.astype(str)) & set(checking.unit_id.astype(str)):
            raise ValueError('FD001 engine overlap across a grouped fold')
        if sorted(training.unit_id.astype(str).unique()) != fold['training_units']:
            raise ValueError('FD001 training fold differs from the frozen protocol')
        if sorted(checking.unit_id.astype(str).unique()) != fold['validation_units']:
            raise ValueError('FD001 validation fold differs from the frozen protocol')
        prep, model = _fit_augmented(training, auxiliary, candidate, extra_share)
        scored = checking.sort_values(['unit_id', 'cycle']).copy()
        scored['predicted'] = prediction(scored, candidate, prep, model, False)
        scored['fold'] = number
        rows.append(scored[['unit_id', 'cycle', 'fold', 'rul', 'predicted']].rename(
            columns={'unit_id': 'unit', 'rul': 'actual'}))
        seen_folds.append({'fold': number, 'training_units': fold['training_units'],
                           'validation_units': fold['validation_units']})
        print(f'  supplemental share {extra_share:.0%}, fold {number} complete', flush=True)
    result = pd.concat(rows, ignore_index=True).sort_values(['unit', 'cycle']).reset_index(drop=True)
    if len(result) != len(target) or result.duplicated(['unit', 'cycle']).any():
        raise ValueError('OOF prediction coverage must equal every FD001 fitting cycle')
    return result, seen_folds


def run():
    output = ROOT / 'models/candidates' / EXPERIMENT
    if output.exists():
        raise FileExistsError(f'Preserving existing experiment: {output}')
    frozen, reference = _read_protocol()
    previous_dir = ROOT / 'models/candidates' / PREVIOUS_ENGINE_RUN / 'engine'
    previous_report = json.loads((previous_dir / 'evaluation.json').read_text())
    previous_path = previous_dir / 'candidate.joblib'
    if sha256(previous_path) != previous_report['candidate_sha256']:
        raise ValueError('Retained engine model hash mismatch')
    champion = joblib.load(previous_path)
    if sha256(ROOT / protocol.DIAGNOSTIC) != frozen['diagnostic_sha256']:
        raise ValueError('Frozen engine diagnostic changed')

    release, manifest = verified_release()
    pointer = ROOT / 'models/releases/current.json'
    protected = {
        'models/releases/current.json': sha256(pointer),
        previous_path.relative_to(ROOT).as_posix(): sha256(previous_path),
        'models/readiness/engine_fd001_bundle.joblib': sha256(ROOT / 'models/readiness/engine_fd001_bundle.joblib'),
    }
    source_table, source_hashes = _load_training()
    protected.update(source_hashes)
    fd001 = source_table.loc[source_table.source_subset == 'FD001'].reset_index(drop=True)
    auxiliary = source_table.loc[source_table.source_subset != 'FD001'].reset_index(drop=True)
    expected_auxiliary_counts = {'FD002': 260, 'FD003': 100, 'FD004': 249}
    actual_auxiliary_counts = {
        subset: int(auxiliary.loc[auxiliary.source_subset == subset, 'unit_id'].nunique())
        for subset in EXTRA_SUBSETS
    }
    if actual_auxiliary_counts != {subset: expected_auxiliary_counts[subset] for subset in EXTRA_SUBSETS}:
        raise ValueError('Unexpected supplementary training-unit counts')
    candidate = Candidate('cross_subset_hist_cap175', clone(champion.model),
                          tuple(champion.feature_columns), champion.target_maximum)

    # Reproduce the existing full-trajectory baseline before comparing transfer.
    fitting_units = set(frozen['fitting_units'])
    fit_target = fd001.loc[fd001.unit_id.astype(str).isin(fitting_units)].copy().reset_index(drop=True)
    groups = fd001.unit_id.to_numpy()
    split = partition_groups(groups)
    split_info = split_record(groups, split)
    if split_info != previous_report['split']:
        raise ValueError('Original FD001 fitting/calibration/audit split changed')
    from src.rul_fitting_diagnostics import grouped_oof
    baseline_rows, baseline_folds = grouped_oof('engine', fit_target, Candidate(
        'baseline_refit', clone(champion.model), tuple(champion.feature_columns), champion.target_maximum))
    np.testing.assert_allclose(baseline_rows.predicted.to_numpy(), reference.sort_values(['unit', 'cycle']).predicted.to_numpy(),
                               atol=1e-8, rtol=1e-8)
    if baseline_folds != frozen['folds']:
        raise ValueError('Baseline grouped folds differ from the frozen record')
    baseline_comparison = protocol.compare_candidate(baseline_rows, reference)
    if baseline_comparison['eligible_for_outer_checks']:
        raise ValueError('Baseline self-comparison cannot qualify as an improvement')

    output.mkdir(parents=True, exist_ok=False)
    (output / 'engine').mkdir()
    (output / 'inner').mkdir()
    write_json = lambda path, value: path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    write_json(output / 'protocol.json', {
        'experiment': EXPERIMENT, 'frozen_engine_protocol': protocol.PROTOCOL,
        'frozen_protocol_sha256': sha256(ROOT / protocol.PROTOCOL), 'folds_sha256': sha256(ROOT / protocol.REFERENCE),
        'supplementary_training_subsets': list(EXTRA_SUBSETS),
        'supplementary_engine_counts': {
            subset: int(auxiliary.loc[auxiliary.source_subset == subset, 'unit_id'].nunique())
            for subset in EXTRA_SUBSETS
        },
        'training_only': [f'data/raw/engine/train_{subset}.txt' for subset in EXTRA_SUBSETS],
        'test_files_used_for_fit_or_selection': False,
        'mixture_shares': list(MIX_SHARES),
        'weighting': 'Equal total weight per source subset, equal engine weight within subset, equal cycle weight within engine.',
        'features_labels_api_contract_unchanged': True,
        'retained_champion_sha256': sha256(previous_path), 'protected_sources': protected,
        'outer_checks': 'Only run if frozen all-cycle fitting gate passes; no deployment in this experiment.'
    })
    write_json(output / 'baseline_full_trajectory.json', baseline_comparison)
    if sha256(previous_path) != previous_report['candidate_sha256']:
        raise ValueError('Retained engine model changed before the experiment')

    all_checks = []
    with threadpool_limits(limits=2):
        for share in MIX_SHARES:
            predictions, folds = _candidate_oof(fit_target, auxiliary, candidate, share, frozen)
            comparison = protocol.compare_candidate(predictions, reference)
            csv_path = output / 'inner' / f'fd001_oof_extra_share_{int(share * 100)}.csv'
            predictions.to_csv(csv_path, index=False)
            result = {'extra_training_share': share, 'folds': folds, 'comparison': comparison,
                      'oof_path': csv_path.relative_to(ROOT).as_posix(), 'oof_sha256': sha256(csv_path),
                      'outer_checks_run': False}
            write_json(output / 'inner' / f'fd001_oof_extra_share_{int(share * 100)}.json', result)
            all_checks.append(result)
            print(json.dumps({'extra_share': share,
                              'balanced_phase_mae': comparison['candidate']['balanced_phase_mae'],
                              'eligible_for_outer_checks': comparison['eligible_for_outer_checks']}, indent=2), flush=True)

        eligible = [item for item in all_checks if item['comparison']['eligible_for_outer_checks']]
        if eligible:
            selected = min(eligible, key=lambda item: item['comparison']['candidate']['balanced_phase_mae'])
            share = selected['extra_training_share']
            fitting, calibration, evaluation = (fd001.iloc[idx].copy() for idx in split)
            calibration, evaluation = snapshots(calibration), snapshots(evaluation)
            prep, model = _fit_augmented(fitting, auxiliary, candidate, share)
            cal_pred = prediction(calibration, candidate, prep, model, False)
            radius = conservative_error_quantile(calibration.rul.to_numpy(float) - cal_pred, champion.interval_alpha)
            bundle = __import__('dataclasses').replace(
                champion, model=model, preprocessor=prep, feature_columns=candidate.features,
                model_name=f'cross_subset_{int(share * 100)}pct_extra', target_maximum=candidate.upper,
                absolute_error_quantile=radius, feature_support=FeatureSupport.fit(fitting, candidate.features),
                validation_protocol='FD001 grouped frozen full-trajectory selection with auxiliary FD002-FD004 training data; development-only')
            evaluation_metrics, audit_rows = evaluate(bundle, evaluation, 'rul', False)
            baseline_audit, _ = evaluate(champion, evaluation, 'rul', False)
            for key, value in previous_report['evaluation_metrics'].items():
                if not np.isclose(baseline_audit[key], value, atol=1e-8, rtol=1e-8):
                    raise ValueError(f'Baseline audit replay mismatch: {key}')
            test = engine_trends(add_causal_engine_features(load_test_with_rul('FD001')))
            terminal = test.loc[test.groupby('unit_id').cycle.idxmax()]
            official_metrics, official_rows = evaluate(bundle, terminal, 'rul', False)
            old_official, _ = evaluate(champion, terminal, 'rul', False)
            for key, value in previous_report['official_test_regression_check'].items():
                if not np.isclose(old_official[key], value, atol=1e-8, rtol=1e-8):
                    raise ValueError(f'Baseline official replay mismatch: {key}')
            selection = [{'candidate': f'extra_share_{int(x["extra_training_share"] * 100)}pct',
                          'inner_eligible': bool(x['comparison']['eligible_for_outer_checks'])}
                         for x in all_checks]
            selected_name = f'extra_share_{int(share * 100)}pct'
            report = {'task': 'engine', 'selected_candidate': selected_name, 'selection': selection,
                'evaluation_metrics': evaluation_metrics, 'previous_candidate_metrics': baseline_audit,
                'official_test_regression_check': official_metrics, 'previous_candidate_official_check': old_official,
                'official_used_for_selection': False, 'deployed': False,
                'inner_comparison': selected['comparison'], 'calibration': {'radius': radius,
                    'nominal_coverage': 1 - bundle.interval_alpha, 'rows': len(calibration)},
                'validation_note': 'All source datasets and FD001 audit/official labels were inspected during earlier project development; these checks are not independent final validation.'}
            decision = nonregression_gate('engine', report)
            destination = output / 'engine'
            joblib.dump(bundle, destination / 'candidate.joblib', compress=3)
            report['candidate_sha256'] = sha256(destination / 'candidate.joblib')
            report['retention_decision'] = decision
            report['retained_research_model'] = ('candidate.joblib' if decision['eligible_research_replacement']
                                                 else previous_path.relative_to(ROOT).as_posix())
            report['retained_model_sha256'] = report['candidate_sha256'] if decision['eligible_research_replacement'] else sha256(previous_path)
            audit_rows.to_csv(destination / 'audit_predictions.csv', index=False)
            official_rows.to_csv(destination / 'official_predictions.csv', index=False)
            write_json(destination / 'evaluation.json', report)
            restored = joblib.load(destination / 'candidate.joblib')
            np.testing.assert_allclose(bundle.predict_feature_frame(evaluation), restored.predict_feature_frame(evaluation), atol=1e-10, rtol=1e-10)
            print(json.dumps({'outer_audit': evaluation_metrics, 'previous_audit': baseline_audit,
                              'official_fd001': official_metrics, 'previous_official': old_official,
                              'retention_decision': decision}, indent=2), flush=True)
        else:
            report = {'task': 'engine', 'selected_candidate': None, 'inner_results': all_checks,
                      'outer_checks_run': False, 'deployed': False,
                      'retained_research_model': previous_path.relative_to(ROOT).as_posix(),
                      'retained_model_sha256': sha256(previous_path),
                      'reason': 'No extra-data mixture passed the predeclared full-trajectory FD001 fitting gate.'}
            write_json(output / 'engine' / 'evaluation.json', report)

    for relative, expected in protected.items():
        if sha256(ROOT / relative) != expected:
            raise ValueError(f'Protected source changed during experiment: {relative}')
    verified_release()
    write_json(output / 'completion.json', {'complete': True, 'deployed': False,
        'retained_model': report['retained_research_model'], 'retained_model_sha256': report['retained_model_sha256'],
        'protected_sources_verified': True, 'active_release_unchanged': True})
    print('Cross-subset engine experiment finished; active release and best prior model were protected.', flush=True)


if __name__ == '__main__':
    run()
