"""Versioned research artifacts with integrity checks before loading."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verified_release(root=ROOT, config=None):
    root = Path(root).resolve()
    pointer = root / 'models/releases/current.json'
    if config is None:
        if not pointer.exists():
            return None
        config = json.loads(pointer.read_text(encoding='utf-8'))
    base = (root / 'models/releases' / config['release_id']).resolve()
    if base.parent != (root / 'models/releases').resolve():
        raise ValueError('Invalid release identifier')
    manifest_path = base / 'manifest.json'
    if sha256(manifest_path) != config['manifest_sha256']:
        raise ValueError('Release manifest integrity check failed')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for name, expected in manifest['files'].items():
        path = (base / name).resolve()
        if not path.is_relative_to(base) or sha256(path) != expected:
            raise ValueError(f'Release integrity check failed: {name}')
    return base, manifest


@lru_cache(maxsize=1)
def active_release():
    return verified_release()


def artifact_root():
    release = active_release()
    return (release[0] if release else ROOT) / 'models/readiness'


def metrics_root():
    release = active_release()
    return (release[0] if release else ROOT) / 'reports/metrics'
