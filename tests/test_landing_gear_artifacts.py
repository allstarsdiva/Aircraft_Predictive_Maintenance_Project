"""Integration checks for saved landing-gear model artifacts."""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.landing_gear_modeling import LandingGearFaultBundle, LandingGearRULBundle

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_saved_landing_gear_bundles_load_and_predict():
    table = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "landing_gear" / "validated_runs.csv"
    ).head(5)
    fault_bundle = joblib.load(
        PROJECT_ROOT / "models" / "landing_gear" / "fault_classifier_bundle.joblib"
    )
    rul_bundle = joblib.load(
        PROJECT_ROOT / "models" / "landing_gear" / "rul_regressor_bundle.joblib"
    )

    assert isinstance(fault_bundle, LandingGearFaultBundle)
    assert isinstance(rul_bundle, LandingGearRULBundle)
    fault_predictions = fault_bundle.predict_feature_frame(table)
    rul_predictions = rul_bundle.predict_feature_frame(table)
    assert len(fault_predictions) == len(table)
    assert set(fault_predictions).issubset({0, 1, 2, 3})
    assert len(rul_predictions) == len(table)
    assert np.isfinite(rul_predictions).all()
    assert ((rul_predictions >= 0) & (rul_predictions <= 100)).all()


def test_saved_bundles_reject_missing_features():
    fault_bundle = joblib.load(
        PROJECT_ROOT / "models" / "landing_gear" / "fault_classifier_bundle.joblib"
    )
    incomplete = pd.DataFrame({"max_velocity": [0.5]})

    try:
        fault_bundle.predict_feature_frame(incomplete)
    except ValueError as exc:
        assert "Missing landing-gear features" in str(exc)
    else:
        raise AssertionError("Missing landing-gear features were accepted")
