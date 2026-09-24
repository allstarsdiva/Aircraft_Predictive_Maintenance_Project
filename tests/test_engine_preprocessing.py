"""Tests for leakage-safe engine preprocessing."""

import numpy as np

from src.data.cmapss import load_training_with_rul
from src.preprocessing import (
    add_causal_engine_features,
    load_engine_preprocessor,
    prepare_engine_training_data,
    save_engine_preprocessor,
)


def test_causal_features_do_not_cross_engine_boundaries():
    frame = load_training_with_rul("FD001")
    featured = add_causal_engine_features(frame)
    first_cycles = featured.loc[featured.groupby("unit_id")["cycle"].idxmin()]

    assert (first_cycles["sensor_11_delta"] == 0).all()
    assert not featured.isna().any().any()


def test_grouped_split_has_no_engine_leakage():
    prepared = prepare_engine_training_data("FD001")

    assert len(prepared.train_units) == 80
    assert len(prepared.validation_units) == 20
    assert prepared.train_units.isdisjoint(prepared.validation_units)


def test_constant_features_are_removed_and_training_is_scaled():
    prepared = prepare_engine_training_data("FD001")

    for column in (
        "sensor_1",
        "sensor_5",
        "sensor_10",
        "sensor_16",
        "sensor_18",
        "sensor_19",
    ):
        assert column not in prepared.X_train.columns
    assert np.allclose(prepared.X_train.mean().to_numpy(), 0.0, atol=1e-10)


def test_rul_is_capped_for_baseline_training():
    prepared = prepare_engine_training_data("FD001", capped_rul=125)

    assert prepared.y_train.max() == 125
    assert prepared.y_validation.max() == 125
    assert prepared.y_train.min() == 0


def test_fitted_pipeline_round_trip(tmp_path):
    prepared = prepare_engine_training_data("FD001")
    path = save_engine_preprocessor(
        prepared.pipeline, tmp_path / "engine_preprocessor.joblib"
    )
    restored = load_engine_preprocessor(path)

    assert np.allclose(
        restored.transform(
            add_causal_engine_features(load_training_with_rul("FD001"))
            .drop(columns=["unit_id", "rul"])
            .iloc[:10]
        ),
        prepared.pipeline.transform(
            add_causal_engine_features(load_training_with_rul("FD001"))
            .drop(columns=["unit_id", "rul"])
            .iloc[:10]
        ),
    )
