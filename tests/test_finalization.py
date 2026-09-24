"""Regression checks for audit isolation, support handling, and frozen releases."""
import json
import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.isotonic import IsotonicRegression
from sklearn.preprocessing import StandardScaler

from src.audit_finalization import partition_groups
from src.model_release import sha256, verified_release
from src.readiness_modeling import FeatureSupport, ReadinessClassificationBundle, ReadinessRegressionBundle
from src.retrain_readiness import fit_confidence_calibration


def test_fit_calibration_evaluation_groups_never_overlap():
    groups = np.repeat(np.arange(20), 3)
    split = partition_groups(groups)
    assert sorted(np.concatenate(split).tolist()) == list(range(len(groups)))
    for i in range(3):
        for j in range(i):
            assert set(groups[split[i]]).isdisjoint(groups[split[j]])
    assert all(np.array_equal(a,b) for a,b in zip(split, partition_groups(groups)))


def test_confidence_rejects_all_when_accuracy_and_coverage_cannot_both_hold():
    raw = np.linspace(0.1, 1, 20)
    correct = np.zeros(20, dtype=bool)
    correct[-1] = True
    calibrator, threshold, metrics = fit_confidence_calibration(raw, correct)
    assert threshold > 1
    assert metrics['accepted_coverage'] == 0
    assert not (calibrator.predict(raw) >= threshold).any()


def test_one_unsupported_row_does_not_reject_supported_batch_rows():
    train = pd.DataFrame({'x': [0., 1.]})
    prep = StandardScaler().fit(train)
    model = DummyClassifier(strategy='most_frequent').fit(prep.transform(train), [0, 0])
    calibration = IsotonicRegression(out_of_bounds='clip').fit([.5,1.], [1.,1.])
    bundle = ReadinessClassificationBundle('test', 'class', ('x',), prep, model,
        'dummy', {}, calibration, .8, {}, FeatureSupport.fit(train, ('x',)))
    _, _, accepted = bundle.predict_with_readiness(pd.DataFrame({'x': [.5, 100.]}))
    assert accepted.tolist() == [True, False]


def test_frozen_artifact_corruption_is_detected(tmp_path):
    base = tmp_path / 'models/releases/test-release'
    base.mkdir(parents=True)
    artifact = base / 'model.bin'
    artifact.write_bytes(b'original')
    manifest = base / 'manifest.json'
    manifest.write_text(json.dumps({'files': {'model.bin': sha256(artifact)}}))
    (base.parent / 'current.json').write_text(json.dumps({
        'release_id': 'test-release', 'manifest_sha256': sha256(manifest)}))
    assert verified_release(tmp_path)[0] == base
    artifact.write_bytes(b'changed')
    with pytest.raises(ValueError, match='integrity'):
        verified_release(tmp_path)


def test_engine_interval_is_not_clipped_to_training_target_cap():
    train = pd.DataFrame({'x': [0., 1.]})
    prep = StandardScaler().fit(train)
    model = DummyRegressor(strategy='constant', constant=120.).fit(prep.transform(train), [120., 120.])
    bundle = ReadinessRegressionBundle('engine', 'rul', 'cycles', ('x',), prep,
        model, 'dummy', {}, .05, 20., FeatureSupport.fit(train, ('x',)), target_maximum=125.)
    predicted, lower, upper = bundle.predict_interval(train)
    assert predicted.tolist() == [120., 120.]
    assert lower.tolist() == [100., 100.]
    assert upper.tolist() == [140., 140.]
    bundle.component = 'landing_gear'
    bundle.target_maximum = 100.
    assert bundle.predict_interval(train)[2].tolist() == [100., 100.]
