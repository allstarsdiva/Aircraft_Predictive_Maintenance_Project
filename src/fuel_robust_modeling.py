"""Normal-only fuel envelope: causal smoothing and steady sensor relationships."""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

from src.data.fuel_system import FUEL_SENSOR_COLUMNS
from src.fuel_phase_modeling import FuelPhaseResidualBundle, causal_persistence

STEADY_SENSORS = ('FTF', 'FTV_S', 'FTT', 'CRTT')


def segments(frame):
    if frame.empty:
        raise ValueError('Fuel samples cannot be empty')
    missing = set(FUEL_SENSOR_COLUMNS).difference(frame.columns)
    if missing:
        raise ValueError(f'Missing fuel features: {sorted(missing)}')
    if not np.isfinite(frame.loc[:, FUEL_SENSOR_COLUMNS].to_numpy(float)).all():
        raise ValueError('Fuel samples must be finite')
    scenario = frame['scenario_id'].to_numpy() if 'scenario_id' in frame else np.repeat('request', len(frame))
    positions = frame['sample_index'].to_numpy(float) if 'sample_index' in frame else np.arange(len(frame))
    if not np.isfinite(positions).all():
        raise ValueError('Fuel sample positions must be finite')
    changed = scenario[1:] != scenario[:-1]
    difference = np.diff(positions)
    if ((difference <= 0) & ~changed).any():
        raise ValueError('Fuel samples must be ordered with unique positions')
    starts = np.r_[0, np.flatnonzero(changed | (difference != 1)) + 1]
    return tuple(np.arange(start, end) for start, end in zip(starts, np.r_[starts[1:], len(frame)]))


def steady_features(frame, smoothing=1, consistency=False):
    if smoothing not in (1, 3):
        raise ValueError('Supported smoothing windows are 1 and 3')
    chunks = segments(frame)
    features = frame.loc[:, STEADY_SENSORS].reset_index(drop=True).copy()
    if consistency:
        for name, left, right in [('flow_pair_difference', 'FTF', 'FTV_S'),
                                  ('collector_pair_difference', 'CLF', 'CLV_S'),
                                  ('temperature_difference', 'FTT', 'CRTT')]:
            features[name] = frame[left].to_numpy() - frame[right].to_numpy()
    if smoothing > 1:
        for indices in chunks:
            features.iloc[indices] = features.iloc[indices].rolling(smoothing, min_periods=1).median().to_numpy()
    return features.to_numpy(float)


@dataclass
class FuelSteadyEnvelope:
    center: np.ndarray
    scale: np.ndarray
    precision: np.ndarray
    aggregation: str
    smoothing: int
    consistency: bool
    feature_columns: tuple = FUEL_SENSOR_COLUMNS

    @classmethod
    def fit(cls, normal, aggregation='max', smoothing=1, consistency=False):
        if aggregation not in ('max', 'mahalanobis'):
            raise ValueError('Unknown fuel score aggregation')
        if 'is_abnormal' in normal and normal['is_abnormal'].astype(bool).any():
            raise ValueError('Envelope fitting requires normal samples only')
        values = steady_features(normal, smoothing, consistency)
        if len(values) < 12:
            raise ValueError('At least twelve normal fitting rows are required')
        center = np.median(values, axis=0)
        mad = np.median(np.abs(values-center), axis=0) * 1.4826
        # Per-channel fallback avoids borrowing incompatible physical units.
        scale = np.maximum(np.where(mad > 1e-9, mad, values.std(axis=0)), 1e-6)
        covariance = LedoitWolf().fit((values-center)/scale)
        return cls(center, scale, covariance.precision_, aggregation, smoothing, consistency)

    def anomaly_score(self, frame):
        values = (steady_features(frame, self.smoothing, self.consistency)-self.center)/self.scale
        if self.aggregation == 'max':
            return np.abs(values).max(axis=1)
        return np.sqrt(np.maximum(np.einsum('ij,jk,ik->i', values, self.precision, values), 0))


@dataclass
class FuelSteadyEnvelopeBundle(FuelPhaseResidualBundle):
    @property
    def detector_name(self):
        return 'robust_steady_sensor_envelope'

    def predict_feature_frame(self, frame):
        raw = (self.predict_anomaly_score(frame) > 0).astype(int)
        result = np.zeros(len(frame), dtype=int)
        for indices in segments(frame):
            result[indices] = causal_persistence(raw[indices], self.persistence_window, self.persistence_required)
        return result
