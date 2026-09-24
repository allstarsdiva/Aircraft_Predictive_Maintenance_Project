"""Snapshot model files, evidence, code, and dependency versions; activate on success."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.model_release import sha256, verified_release


def freeze(release_id):
    if not release_id or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in release_id):
        raise ValueError('Use lowercase letters, numbers, hyphens, or underscores')
    if not (ROOT / 'reports/metrics/finalization_audit/audit.json').is_file():
        raise FileNotFoundError('Run python -m src.audit_finalization first')
    base = ROOT / 'models/releases' / release_id
    base.mkdir(parents=True, exist_ok=False)
    paths = list((ROOT / 'models/readiness').rglob('*.joblib'))
    paths += list((ROOT / 'reports/metrics/finalization_audit').glob('*'))
    paths += list((ROOT / 'reports/metrics/fuel_nested').glob('*'))
    paths += [p for p in [ROOT / 'scripts/promote_fuel_candidate.py', ROOT / 'reports/FUEL_NESTED_IMPROVEMENT.md'] if p.is_file()]
    browser_evidence = ROOT / 'reports/metrics/workspace_browser_check.json'
    if browser_evidence.exists():
        paths.append(browser_evidence)
    paths += [ROOT / 'reports/metrics/readiness_v2_retraining.json']
    paths += list((ROOT / 'src').rglob('*.py'))
    paths += list((ROOT / 'tests').glob('*.py'))
    paths += [ROOT / 'requirements.txt', ROOT / 'package-lock.json']
    paths += [ROOT / 'package.json', ROOT / 'index.html', ROOT / 'pytest.ini',
              ROOT / 'aircraft-maintenance-dashboard-enhanced.jsx',
              ROOT / 'reports/FINALIZATION_AUDIT.md', ROOT / 'docs/MODEL_WORKSPACE.md']
    paths += [ROOT / 'scripts/freeze_research_release.py', ROOT / 'vite.config.js']
    paths += [ROOT / 'scripts/browser_workspace_smoke.mjs']
    paths += list((ROOT / 'frontend-src').glob('*'))
    entries = {}
    for path in paths:
        relative = path.relative_to(ROOT)
        destination = base / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        entries[relative.as_posix()] = sha256(destination)
    manifest = {
        'release_id': release_id, 'status': 'research_candidate_not_final_validated_model',
        'files': entries, 'fuel_status': 'experimental_only',
        'python_version': sys.version.split()[0],
        'packages': {p: importlib.metadata.version(p) for p in ['numpy', 'pandas', 'scikit-learn', 'joblib', 'fastapi']},
        'evidence': 'reports/metrics/finalization_audit/audit.json',
        'known_limits': ['Historical confidence estimates reuse calibration data',
                         'Engine serving interval coverage is 93 percent versus nominal 95 on previously inspected official tests',
                         'Fresh external validation and landing archive provenance unresolved'],
        'data_hashes': {p.relative_to(ROOT).as_posix(): sha256(p)
                        for p in (ROOT / 'data/processed').rglob('*.csv')},
        'engine_source_hashes': {name: sha256(ROOT / 'data/raw/engine' / name)
                                for name in ['train_FD001.txt', 'test_FD001.txt', 'RUL_FD001.txt']},
    }
    path = base / 'manifest.json'
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    pointer = ROOT / 'models/releases/current.json'
    temporary = pointer.with_suffix('.tmp')
    config = {'release_id': release_id, 'manifest_sha256': sha256(path)}
    verified_release(ROOT, config)  # verify the candidate before changing the pointer
    temporary.write_text(json.dumps(config, indent=2), encoding='utf-8')
    temporary.replace(pointer)
    verified_release()
    print(f'Activated verified research release: {release_id}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('release_id')
    freeze(parser.parse_args().release_id)
