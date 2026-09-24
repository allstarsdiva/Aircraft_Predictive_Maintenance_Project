"""Fitting-only grouped error and source-quality audit; no model promotion."""
import argparse
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut
from threadpoolctl import threadpool_limits

from src.audit_finalization import partition_groups, split_record
from src.battery_history_retraining import history_features
from src.data.battery import build_battery_discharge_table, parse_start_time, resolve_measurement_path
from src.data.cmapss import load_training_with_rul
from src.model_release import verified_release, sha256
from src.preprocessing import add_causal_engine_features
from src.rul_retraining_v2 import engine_trends, engine_checkpoints
from src.rul_retraining_v5 import verify_champions
from src.targeted_retraining import ROOT, Candidate, fit_candidate, prediction

TASKS = ('battery_rul', 'engine')
OUTPUT = 'reports/metrics/rul_fitting_diagnostics_20260914'


def fitting_partition(table, group_column, expected):
    groups = table[group_column].to_numpy()
    partition = partition_groups(groups)
    if split_record(groups, partition) != expected:
        raise ValueError('Group partition no longer matches retained experiment')
    selected = table.iloc[partition[0]].copy().reset_index(drop=True)
    if set(selected[group_column].astype(str)) != set(expected['fit']['groups']):
        raise ValueError('Unexpected fitting units')
    return selected


def feature_frame(task, table):
    if task == 'engine':
        return engine_trends(add_causal_engine_features(table))
    if task == 'battery_rul':
        return table.merge(history_features(table), on=['battery_id', 'discharge_cycle'], validate='one_to_one')
    raise ValueError('Unsupported task')


def quality_checks(task, table):
    group_column, cycle, target = ('unit_id', 'cycle', 'rul') if task == 'engine' else ('battery_id', 'discharge_cycle', 'rul_cycles')
    numeric = table.select_dtypes(include='number')
    nonfinite = {column: int((~np.isfinite(numeric[column].to_numpy(float))).sum()) for column in numeric}
    units, flags = [], []
    for unit, group in table.groupby(group_column, sort=True):
        group = group.sort_values(cycle)
        diffs = group[cycle].diff().dropna()
        lifetime = group[cycle] + group[target]
        record = {'unit': str(unit), 'rows': len(group), 'first_cycle': int(group[cycle].min()),
                  'last_cycle': int(group[cycle].max()), 'cycle_gaps': int((diffs > 1).sum()),
                  'lifetime_values': int(lifetime.nunique()), 'observed_lifetime': float(lifetime.iloc[0]),
                  'training_row_fraction': len(group) / len(table)}
        if task == 'engine':
            record['label_mismatch_rows'] = int((lifetime != group[cycle].max()).sum())
        else:
            record.update(ambient_temperature=float(group.ambient_temperature.median()),
                          median_current=float(group.current_abs_mean.median()),
                          label_mismatch_rows=int((lifetime != group.observed_eol_cycle).sum()))
            prior_median = group.charge_throughput_ah.shift(1).rolling(5, min_periods=3).median()
            suspicious = group.charge_throughput_ah < .5 * prior_median
            nonpositive = (group.duration_seconds <= 0) | (group.charge_throughput_ah <= 0) | (group.current_abs_mean <= 0)
            for index in group.index[suspicious | nonpositive]:
                flags.append({'unit': str(unit), 'cycle': int(group.loc[index, cycle]),
                              'uid': int(group.loc[index, 'uid']),
                              'throughput_ah': float(group.loc[index, 'charge_throughput_ah']),
                              'duration_seconds': float(group.loc[index, 'duration_seconds']),
                              'large_downward_jump': bool(suspicious.loc[index]),
                              'nonpositive_measurement': bool(nonpositive.loc[index])})
        units.append(record)
    return {'rows': len(table), 'units': len(units),
            'duplicate_unit_cycles': int(table.duplicated([group_column, cycle]).sum()),
            'negative_rul_rows': int((table[target] < 0).sum()),
            'nonfinite_by_column': {key: value for key, value in nonfinite.items() if value},
            'constant_numeric_columns': [column for column in numeric if numeric[column].nunique(dropna=False) <= 1],
            'per_unit': units, 'review_flags': flags,
            'flag_rule': 'Throughput below half of preceding five-discharge median (>=3 prior points), or nonpositive duration/current/throughput. Review only; no rows removed.'}


def source_battery_review(metadata, fitting):
    # Filter before parsing times or reconstructing any labels.
    ids = set(fitting.battery_id)
    selected = metadata.loc[metadata.battery_id.isin(ids)].copy()
    selected['start_time'] = selected.start_time.map(parse_start_time)
    selected['Capacity'] = pd.to_numeric(selected.Capacity, errors='coerce')
    discharge = build_battery_discharge_table(metadata=selected)
    joined = fitting.merge(discharge[['uid', 'discharge_cycle', 'observed_eol_cycle', 'rul_cycles', 'Capacity']],
                           on='uid', how='left', suffixes=('', '_source'), validate='one_to_one', indicator=True)
    mismatch = joined['_merge'] != 'both'
    for name in ('discharge_cycle', 'observed_eol_cycle', 'rul_cycles'):
        mismatch |= ~np.isclose(joined[name], joined[f'{name}_source'], equal_nan=False)
    crossings = []
    for battery, group in discharge.groupby('battery_id', sort=True):
        group = group.sort_values('discharge_cycle')
        eol = group.observed_eol_cycle.iloc[0]
        if not np.isfinite(eol):
            crossings.append({'unit': battery, 'source_has_eol': False})
            continue
        crossing = group.loc[group.discharge_cycle == eol].iloc[0]
        after = group.loc[(group.discharge_cycle > eol) & group.valid_capacity].head(3)
        before = group.loc[(group.discharge_cycle < eol) & group.valid_capacity].tail(5)
        above = after.Capacity > crossing.eol_capacity_ah
        crossings.append({'unit': battery, 'source_has_eol': True, 'first_crossing_cycle': int(eol),
                          'crossing_uid': int(crossing.uid), 'source_filename': str(crossing.filename),
                          'threshold_ah': float(crossing.eol_capacity_ah), 'crossing_capacity_ah': float(crossing.Capacity),
                          'prior_five_valid_median_ah': float(before.Capacity.median()) if len(before) else None,
                          'following_valid_cycles': after.discharge_cycle.astype(int).tolist(),
                          'following_capacities_ah': after.Capacity.astype(float).tolist(),
                          'following_above_threshold_count': int(above.sum()),
                          'review_first_crossing_stability': bool(above.any())})
    return {'fitting_units_only': sorted(ids), 'processed_source_label_mismatch_rows': int(mismatch.sum()),
            'processed_rows_checked': len(joined), 'crossings': crossings,
            'note': 'Post-crossing records of fitting batteries are inspected for label provenance only; never used in model fitting or predictor features. A recovery flag is not proof a label is wrong.'}


def grouped_oof(task, frame, specification):
    group_column, cycle, target = ('unit_id', 'cycle', 'rul') if task == 'engine' else ('battery_id', 'discharge_cycle', 'rul_cycles')
    groups = frame[group_column].to_numpy()
    splitter = GroupKFold(3) if task == 'engine' else LeaveOneGroupOut()
    rows, folds = [], []
    for number, (train, validation) in enumerate(splitter.split(frame, groups=groups), 1):
        fitting, checking = frame.iloc[train], frame.iloc[validation]
        if set(fitting[group_column]) & set(checking[group_column]):
            raise ValueError('Inner unit overlap')
        prep, model = fit_candidate(fitting, target, specification, False)
        predicted = prediction(checking, specification, prep, model, False)
        actual = checking[target].to_numpy(float)
        observed = checking[cycle].to_numpy(float)
        age_fraction = observed / (observed + actual)
        scored = pd.DataFrame({'unit': checking[group_column].astype(str).to_numpy(),
            'cycle': observed, 'fold': number, 'actual': actual, 'predicted': predicted,
            'error': predicted - actual,
            'phase': np.select([age_fraction <= 1/3, age_fraction <= 2/3], ['early', 'middle'], default='late'),
            'rul_band': np.select([actual <= 30, actual <= 100], ['0-30', '31-100'], default='>100'),
            'cap_error_floor': np.maximum(actual - specification.upper, 0) if specification.upper is not None else 0.,
            'lifetime_above_training_max': observed + actual > (fitting[cycle] + fitting[target]).max()})
        if task == 'engine':
            checkpoints = engine_checkpoints(checking)
            keys = set(zip(checkpoints[group_column].astype(str), checkpoints[cycle]))
            scored['fixed_checkpoint'] = [(unit, cycle_value) in keys for unit, cycle_value in zip(scored.unit, scored.cycle)]
        else:
            scored['ambient_temperature'] = checking.ambient_temperature.to_numpy(float)
            scored['uid'] = checking.uid.to_numpy()
            scored['fixed_checkpoint'] = True
        rows.append(scored)
        folds.append({'fold': number, 'training_units': sorted(fitting[group_column].astype(str).unique()),
                      'validation_units': sorted(checking[group_column].astype(str).unique()),
                      'training_rows': len(fitting), 'validation_rows': len(checking)})
        print(f'{task}: diagnostic fold {number} complete', flush=True)
    result = pd.concat(rows, ignore_index=True).sort_values(['unit', 'cycle']).reset_index(drop=True)
    if len(result) != len(frame) or result.duplicated(['unit', 'cycle']).any():
        raise ValueError('Each fitting row must be scored exactly once out of fold')
    return result, folds


def error_summary(rows):
    if rows.empty:
        return {'rows': 0, 'units': 0}
    errors = rows.error.to_numpy(float)
    grouped = rows.groupby('unit').error
    return {'rows': len(rows), 'units': int(rows.unit.nunique()),
            'row_mae': float(np.abs(errors).mean()), 'row_rmse': float(np.sqrt(np.mean(errors ** 2))),
            'unit_mean_mae': float(grouped.apply(lambda values: np.abs(values).mean()).mean()),
            'unit_mean_rmse': float(grouped.apply(lambda values: np.sqrt(np.mean(values ** 2))).mean()),
            'bias': float(errors.mean()), 'over_by_more_than_10_rate': float((errors > 10).mean()),
            'cap_imposed_mae_floor': float(rows.cap_error_floor.mean())}


def summarize_oof(rows):
    result = {'all_cycles': error_summary(rows),
              'fixed_checkpoints': error_summary(rows.loc[rows.fixed_checkpoint]),
              'by_phase': {str(key): error_summary(group) for key, group in rows.groupby('phase')},
              'by_rul_band': {str(key): error_summary(group) for key, group in rows.groupby('rul_band')},
              'by_unit': {str(key): error_summary(group) for key, group in rows.groupby('unit')},
              'beyond_training_lifetime': error_summary(rows.loc[rows.lifetime_above_training_max])}
    if 'ambient_temperature' in rows:
        result['by_temperature'] = {str(key): error_summary(group) for key, group in rows.groupby('ambient_temperature')}
    return result


def trace_sources(output):
    destination = output / 'raw_source_trace.json'
    if destination.exists():
        raise FileExistsError('Preserve earlier raw-source trace')
    evidence_path = output / 'diagnostics.json'
    evidence = json.loads(evidence_path.read_text())
    for relative, digest in evidence['sources'].items():
        if sha256(ROOT / relative) != digest:
            raise ValueError('Diagnostic source or protected model changed')
    ids = evidence['tasks']['battery_rul']['fitting_units']
    fitting = pd.read_csv(ROOT / 'data/processed/battery/rul_features.csv')
    fitting = fitting.loc[fitting.battery_id.isin(ids)].copy()
    base = ROOT / 'data/raw/battery/cleaned_dataset'
    metadata = pd.read_csv(base / 'metadata.csv')
    metadata = metadata.loc[metadata.battery_id.isin(ids)].set_index('uid', verify_integrity=True)
    records, hashes = [], {}
    for unit, group in fitting.groupby('battery_id', sort=True):
        for _, row in group.sort_values('discharge_cycle').tail(3).iterrows():
            source = metadata.loc[row.uid]
            path = resolve_measurement_path(base, str(source.filename))
            hashes[path] = sha256(path)
            samples = pd.read_csv(path)
            values = samples[['Time', 'Current_measured']].to_numpy(float)
            if not np.isfinite(values).all() or (np.diff(values[:, 0]) < 0).any():
                raise ValueError('Invalid raw curve requires manual review')
            integrated = float(np.trapezoid(np.abs(values[:, 1]), values[:, 0]) / 3600)
            records.append({'unit': unit, 'cycle': int(row.discharge_cycle), 'uid': int(row.uid),
                'raw_file': path.relative_to(ROOT).as_posix(), 'sha256': hashes[path],
                'ambient_temperature': float(source.ambient_temperature), 'samples': len(samples),
                'duration_seconds': float(values[-1, 0] - values[0, 0]),
                'source_capacity_ah': float(source.Capacity), 'integrated_abs_ah': integrated,
                'processed_throughput_ah': float(row.charge_throughput_ah),
                'processed_integration_matches': bool(np.isclose(integrated, row.charge_throughput_ah, atol=1e-10, rtol=1e-10)),
                'mean_abs_current': float(np.abs(values[:, 1]).mean()), 'end_voltage': float(samples.Voltage_measured.iloc[-1])})
    if not all(sha256(path) == digest for path, digest in hashes.items()):
        raise ValueError('Raw curves changed during trace')
    result = {'diagnostics_sha256': sha256(evidence_path), 'fitting_units_only': ids, 'records': records,
              'note': 'Last three processed fitting cycles per battery. Raw integration is not assumed identical to the source Capacity convention. No labels changed.'}
    destination.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(f'Raw trace complete: {len(records)} fitting cycles; all raw files unchanged.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks', nargs='+', choices=TASKS, default=list(TASKS))
    parser.add_argument('--trace-sources', action='store_true', help='Trace existing battery diagnostic findings to raw curves without refitting')
    args = parser.parse_args()
    if len(set(args.tasks)) != len(args.tasks):
        parser.error('Duplicate tasks not allowed')
    output = ROOT / OUTPUT
    if args.trace_sources:
        trace_sources(output)
        return
    if output.exists():
        parser.error('Preserve the existing diagnostic run')
    release, manifest = verified_release()
    champions_file = ROOT / 'models/candidates/rul-protected-v5-20260913/champions.json'
    champions = json.loads(champions_file.read_text())
    verify_champions(champions)
    battery_path = ROOT / 'data/processed/battery/rul_features.csv'
    engine_path = ROOT / 'data/raw/engine/train_FD001.txt'
    metadata_path = ROOT / 'data/raw/battery/cleaned_dataset/metadata.csv'
    expected = {battery_path: manifest['data_hashes']['data/processed/battery/rul_features.csv'],
                engine_path: manifest['engine_source_hashes']['train_FD001.txt']}
    for path, digest in expected.items():
        if sha256(path) != digest:
            raise ValueError('Fitting data changed since retained experiment')
    protected = [ROOT / name for name in manifest['files'] if name.startswith('models/') and name.endswith('.joblib')]
    protected += [ROOT / 'models/releases/current.json', champions_file, battery_path, engine_path, metadata_path]
    hashes = {path: sha256(path) for path in protected}
    output.mkdir(parents=True)
    report = {'scope': 'Fitting-unit diagnostics only; no model selection, outer evaluation, or promotion.',
              'independent_external_test': False, 'phases': 'Thirds of observed lifetime, derived from labels for evaluation only, never predictors.',
              'sources': {path.relative_to(ROOT).as_posix(): digest for path, digest in hashes.items()}, 'tasks': {}}
    try:
        with threadpool_limits(limits=2):
            for task in args.tasks:
                prior = json.loads((ROOT / champions[task]['source']).with_name('evaluation.json').read_text())
                bundle = joblib.load(ROOT / champions[task]['source'])
                raw = load_training_with_rul('FD001') if task == 'engine' else pd.read_csv(battery_path)
                group_column = 'unit_id' if task == 'engine' else 'battery_id'
                fitting = fitting_partition(raw, group_column, prior['split'])
                quality = quality_checks(task, fitting)
                frame = feature_frame(task, fitting)
                specification = Candidate('retained_specification', clone(bundle.model), tuple(bundle.feature_columns), bundle.target_maximum)
                oof, folds = grouped_oof(task, frame, specification)
                task_result = {'fitting_units': sorted(fitting[group_column].astype(str).unique()),
                    'quality': quality, 'folds': folds, 'error_summary': summarize_oof(oof),
                    'target_cap': bundle.target_maximum, 'retained_source': champions[task]['source']}
                if task == 'battery_rul':
                    task_result['source_label_review'] = source_battery_review(pd.read_csv(metadata_path), fitting)
                path = output / f'{task}_oof.csv'
                oof.to_csv(path, index=False)
                task_result['oof_sha256'] = sha256(path)
                report['tasks'][task] = task_result
        report['integrity_unchanged'] = all(sha256(path) == digest for path, digest in hashes.items())
        verify_champions(champions)
        if not report['integrity_unchanged']:
            raise ValueError('Protected files changed during diagnostics')
        (output / 'diagnostics.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    finally:
        verify_champions(champions)
        for path, digest in hashes.items():
            if sha256(path) != digest:
                raise ValueError('Protected data/model changed during diagnostics')
        verified_release()
    print('Diagnostics complete; source data, retained models, and serving models unchanged.', flush=True)


if __name__ == '__main__':
    main()
