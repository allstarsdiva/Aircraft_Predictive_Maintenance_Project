"""Real examples pass through all five routes and preserve source semantics."""
import pytest
from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)


@pytest.mark.parametrize('component', ['engine', 'battery', 'hydraulic', 'landing-gear', 'fuel-system'])
@pytest.mark.parametrize('variant', ['normal', 'challenge'])
def test_dataset_examples_produce_real_predictions(component, variant):
    sample = client.get(f'/api/workspace/examples/{component}', params={'variant': variant})
    assert sample.status_code == 200, sample.text
    body = sample.json()
    response = client.post(body['endpoint'], json=body['payload'])
    assert response.status_code == 200, response.text
    assert body['source'] and body['actual']
    if component == 'hydraulic':
        assert body['payload']['operating_condition_stable'] == (variant == 'normal')
        if variant == 'challenge':
            assert all(not row['accepted'] for row in response.json()['predictions'].values())
            assert 'stable_flag=1' in body['source']
        else:
            assert 'stable_flag=0' in body['source']


def test_evidence_distinguishes_diagnostics_from_external_validation():
    response = client.get('/api/workspace/evidence')
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['release_status'] == 'research_candidate_only'
    assert data['audit']['independent_external_test'] is False
    assert data['audit']['tasks']['fuel']['status'] == 'blocked'


def test_unknown_subsystem_is_not_a_file_path():
    assert client.get('/api/workspace/examples/avionics').status_code == 422
