"""Stage the verified fuel candidate for a NEW research release; keep fuel experimental."""
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import joblib
from src.model_release import sha256
from src.fuel_robust_modeling import FuelSteadyEnvelopeBundle


def main():
    report_path = ROOT / 'reports/metrics/fuel_nested/evaluation.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    source = ROOT / 'models/candidates/fuel_steady_envelope_bundle.joblib'
    if not report['improves_paired_development_evaluation']:
        raise ValueError('Candidate did not pass the predefined development improvement rule')
    if sha256(source) != report['candidate_sha256']:
        raise ValueError('Candidate artifact no longer matches evaluated artifact')
    candidate = joblib.load(source)
    if not isinstance(candidate, FuelSteadyEnvelopeBundle):
        raise TypeError('Unexpected candidate artifact type')
    destination = ROOT / 'models/readiness/fuel_phase_residual_bundle.joblib'
    metrics_path = ROOT / 'reports/metrics/readiness_v2_retraining.json'
    metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
    previous = metrics['fuel_system']
    if previous['best_model'] == candidate.detector_name:
        raise ValueError('Fuel candidate already staged; use a new experiment for another update')
    metrics['fuel_system'] = {
        'best_model': candidate.detector_name, 'metrics': report['metrics'],
        'validation_protocol': report['protocol'], 'independent_external_test': False,
        'paired_baseline_metrics': report['paired_baseline_metrics'],
        'previous_development_results': previous, 'readiness_gate': 'fail',
        'reason': 'One normal mission, scenario-level labels, and limited detection; still experimental.',
        'model_path': destination.relative_to(ROOT).as_posix(),
        'selected_parameters': report['selected_parameters'],
    }
    metrics['protocol_version'] = 'readiness-v2.3-fuel-nested'
    shutil.copy2(source, destination)
    metrics_path.write_text(json.dumps(metrics, indent=2, allow_nan=False), encoding='utf-8')
    print('Staged verified experimental fuel candidate; freeze a new release to activate it.')


if __name__ == '__main__':
    main()
