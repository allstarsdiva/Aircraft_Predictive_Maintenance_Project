"""Read-only reconstruction of documented 2.7 V capacity conventions."""
import json

import numpy as np
import pandas as pd

from src.model_release import sha256
from src.targeted_retraining import ROOT


def cutoff_integral(time, voltage, current, cutoff=2.7):
    if not np.isfinite(cutoff) or cutoff <= 0:
        raise ValueError('Positive finite voltage cutoff required')
    time, voltage, current = (np.asarray(values, dtype=float) for values in (time, voltage, current))
    if any(values.ndim != 1 for values in (time, voltage, current)) or not (len(time) == len(voltage) == len(current)) or len(time) < 2:
        raise ValueError('Aligned one-dimensional curves with at least two samples required')
    if not all(np.isfinite(values).all() for values in (time, voltage, current)) or (np.diff(time) < 0).any():
        raise ValueError('Finite chronological curves required')
    current = np.abs(current)
    full = float(np.trapezoid(current, time) / 3600)
    positions = np.flatnonzero(voltage <= cutoff)
    if not len(positions):
        return {'status': 'no_observed_crossing', 'full_throughput_ah': full}
    index = int(positions[0])
    if index == 0:
        return {'status': 'starts_at_or_below_cutoff', 'full_throughput_ah': full}
    fraction = (voltage[index - 1] - cutoff) / (voltage[index - 1] - voltage[index])
    cross_time = time[index - 1] + fraction * (time[index] - time[index - 1])
    cross_current = current[index - 1] + fraction * (current[index] - current[index - 1])
    aligned = float(np.trapezoid(np.r_[current[:index], cross_current], np.r_[time[:index], cross_time]) / 3600)
    return {'status': 'crossing_observed', 'full_throughput_ah': full,
            'cutoff_interpolated_ah': aligned, 'crossing_seconds': float(cross_time),
            'last_above_sample_ah': float(np.trapezoid(current[:index], time[:index]) / 3600),
            'first_below_sample_ah': float(np.trapezoid(current[:index + 1], time[:index + 1]) / 3600)}


def main():
    folder = ROOT / 'reports/metrics/rul_fitting_diagnostics_20260914'
    destination = folder / 'battery_cutoff_review.json'
    if destination.exists():
        raise FileExistsError('Preserve the completed cutoff review')
    trace_path = folder / 'raw_source_trace.json'
    trace = json.loads(trace_path.read_text())
    diagnostic_path = folder / 'diagnostics.json'
    if sha256(diagnostic_path) != trace['diagnostics_sha256']:
        raise ValueError('Diagnostic evidence changed')
    diagnostic = json.loads(diagnostic_path.read_text())
    for relative, digest in diagnostic['sources'].items():
        if sha256(ROOT / relative) != digest:
            raise ValueError('Protected source/model changed')
    readmes = [ROOT / 'data/raw/battery/cleaned_dataset/extra_infos' / filename for filename in
               ('README_05_06_07_18.txt', 'README_41_42_43_44.txt', 'README_45_46_47_48.txt')]
    hashes = {path: sha256(path) for path in readmes}
    for path in readmes:
        if 'for discharge till 2.7V' not in path.read_text():
            raise ValueError('Local documented capacity convention changed')
    records = []
    for row in trace['records']:
        if row['unit'] not in trace['fitting_units_only']:
            raise ValueError('Nonfitting battery cannot enter review')
        path = ROOT / row['raw_file']
        if sha256(path) != row['sha256']:
            raise ValueError('Raw curve changed')
        hashes[path] = row['sha256']
        samples = pd.read_csv(path)
        result = cutoff_integral(samples.Time, samples.Voltage_measured, samples.Current_measured)
        result.update(unit=row['unit'], cycle=row['cycle'], uid=row['uid'], raw_file=row['raw_file'],
                      source_capacity_ah=row['source_capacity_ah'], ambient_temperature=row['ambient_temperature'])
        if result['status'] == 'crossing_observed':
            result['source_within_neighbor_sample_integrals'] = bool(
                result['last_above_sample_ah'] <= row['source_capacity_ah'] <= result['first_below_sample_ah'])
            result['source_minus_interpolated_ah'] = row['source_capacity_ah'] - result['cutoff_interpolated_ah']
        records.append(result)
    if not all(sha256(path) == digest for path, digest in hashes.items()):
        raise ValueError('Review inputs changed')
    report = {'source_trace_sha256': sha256(trace_path),
              'source_url': 'https://data.nasa.gov/dataset/li-ion-battery-aging-datasets',
              'input_hashes': {path.relative_to(ROOT).as_posix(): digest for path, digest in hashes.items()},
              'documented_capacity_voltage_v': 2.7, 'documented_eol_ah': 1.4,
              'local_matlab_originals_available': any((ROOT / 'data/raw/battery').rglob('*.mat')),
              'csv_conversion_provenance_verified': False,
              'labels_or_features_changed': False, 'records': records,
              'interpretation': 'Full-discharge throughput and cutoff capacity differ by definition. Linear interpolation of sampled curves is a diagnostic reconstruction, not verification of the original Capacity calculation algorithm.'}
    destination.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(f'Cutoff review saved for {len(records)} fitting curves; data and models unchanged.')


if __name__ == '__main__':
    main()
