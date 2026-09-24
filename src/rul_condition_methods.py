"""Condition-aware and lifetime-residual RUL research estimators."""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.cluster import KMeans
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.utils.validation import check_is_fitted

from src.rul_methods import equal_group_weights
from src.retrain_readiness import _preprocessor
from src.targeted_retraining import fit_candidate


class ConditionRULRegressor(RegressorMixin, BaseEstimator):
    def __init__(self, task='battery_rul', mode='direct', clusters=1,
                 local_strength=.5, lifetime_fraction=.5, group_balanced=False,
                 seed=20260912, learner='trees', ridge_alpha=10.):
        self.task = task
        self.mode = mode
        self.clusters = clusters
        self.local_strength = local_strength
        self.lifetime_fraction = lifetime_fraction
        self.group_balanced = group_balanced
        self.seed = seed
        self.learner = learner
        self.ridge_alpha = ridge_alpha

    def _estimator(self):
        if self.learner == 'ridge':
            return Ridge(alpha=self.ridge_alpha)
        if self.task == 'engine':
            return HistGradientBoostingRegressor(max_iter=220, max_leaf_nodes=15,
                min_samples_leaf=25, learning_rate=.05, l2_regularization=5,
                early_stopping=False, random_state=self.seed)
        return ExtraTreesRegressor(n_estimators=250, min_samples_leaf=2,
            max_features=.8, n_jobs=2, random_state=self.seed)

    def _age(self, X):
        return X[self.cycle_column_].to_numpy(float) * self.cycle_scale_ + self.cycle_mean_

    def _gates(self, X):
        values = X.loc[:, self.condition_columns_].to_numpy(float)
        distances = ((values[:, None, :] - self.centers_[None, :, :]) ** 2).sum(axis=2)
        logits = -distances / (2 * self.gate_width_ ** 2)
        gates = np.exp(logits - logits.max(axis=1, keepdims=True))
        return gates / gates.sum(axis=1, keepdims=True)

    def fit(self, X, y, sample_weight=None, *, cycle_mean=0., cycle_scale=1.):
        if self.task not in ('engine', 'battery_rul') or self.mode not in ('direct', 'lifetime', 'blend'):
            raise ValueError('Unsupported RUL task or mode')
        if self.learner not in ('trees', 'ridge') or self.ridge_alpha <= 0:
            raise ValueError('Unsupported learner or regularization')
        if self.clusters < 1 or not 0 <= self.local_strength <= 1 or not 0 <= self.lifetime_fraction <= 1:
            raise ValueError('Invalid condition or blending settings')
        if self.task == 'engine' and self.clusters != 1:
            raise ValueError('Condition experts are scoped to battery')
        if not isinstance(X, pd.DataFrame):
            raise ValueError('Finite named predictors required')
        forbidden = {'unit_id', 'battery_id', 'uid', 'rul', 'rul_cycles', 'observed_eol_cycle', 'soh_percent'}
        if forbidden & set(X):
            raise ValueError('Identity and label predictors forbidden')
        if not np.isfinite(X.to_numpy(float)).all():
            raise ValueError('Finite named predictors required')
        self.cycle_column_ = 'cycle' if self.task == 'engine' else 'discharge_cycle'
        if self.cycle_column_ not in X or not np.isfinite([cycle_mean, cycle_scale]).all() or cycle_scale <= 0:
            raise ValueError('Valid observed cycle transform required')
        self.cycle_mean_, self.cycle_scale_ = cycle_mean, cycle_scale
        self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        self.n_features_in_ = X.shape[1]
        y = np.asarray(y, dtype=float)
        if y.ndim != 1 or len(y) != len(X) or not np.isfinite(y).all() or (y < 0).any():
            raise ValueError('Finite nonnegative RUL labels required')
        self.modes_ = ['direct', 'lifetime'] if self.mode == 'blend' else [self.mode]
        weights = np.ones(len(X)) if sample_weight is None else np.asarray(sample_weight, dtype=float)
        if weights.shape != y.shape or not np.isfinite(weights).all() or (weights <= 0).any():
            raise ValueError('Positive finite fitting weights required')
        self.centers_ = None
        gates = None
        if self.clusters > 1:
            self.condition_columns_ = ('ambient_temperature', 'current_abs_mean', 'voltage_end')
            if not set(self.condition_columns_).issubset(X):
                raise ValueError('Operating-condition inputs required')
            conditions = X.loc[:, self.condition_columns_].to_numpy(float)
            count = min(self.clusters, len(np.unique(conditions, axis=0)))
            clusters = KMeans(n_clusters=count, n_init=10, random_state=self.seed).fit(conditions, sample_weight=weights)
            self.centers_ = clusters.cluster_centers_
            self.gate_width_ = max(1., float(np.median(np.min(clusters.transform(conditions), axis=1))))
            gates = self._gates(X)
        self.global_models_, self.local_models_ = [], []
        for mode in self.modes_:
            target = y + self._age(X) if mode == 'lifetime' else y.copy()
            # Only the direct member of an engine blend uses the retained cap.
            if self.task == 'engine' and self.mode == 'blend' and mode == 'direct':
                target = np.minimum(target, 175.)
            global_model = self._estimator().fit(X, target, sample_weight=weights)
            self.global_models_.append(global_model)
            local = []
            if gates is not None:
                for position in range(gates.shape[1]):
                    localized = weights * np.maximum(gates[:, position], 1e-3)
                    localized *= len(localized) / localized.sum()
                    local.append(self._estimator().fit(X, target, sample_weight=localized))
            self.local_models_.append(local)
        return self

    def predict(self, X):
        check_is_fitted(self, 'global_models_')
        if not isinstance(X, pd.DataFrame) or list(X.columns) != list(self.feature_names_in_):
            raise ValueError('Predictor order must match fitting')
        predictions = []
        gates = None if self.centers_ is None else self._gates(X)
        for mode, global_model, local in zip(self.modes_, self.global_models_, self.local_models_):
            value = global_model.predict(X)
            if local:
                localized = np.column_stack([model.predict(X) for model in local])
                value = (1 - self.local_strength) * value + self.local_strength * (gates * localized).sum(axis=1)
            if mode == 'lifetime':
                value = value - self._age(X)
            if self.task == 'engine' and self.mode == 'blend' and mode == 'direct':
                value = np.minimum(value, 175.)
            predictions.append(np.maximum(0, value))
        if self.mode == 'blend':
            return (1 - self.lifetime_fraction) * predictions[0] + self.lifetime_fraction * predictions[1]
        return predictions[0]


def fit_condition_candidate(table, target, candidate, classifier):
    if not isinstance(candidate.model, ConditionRULRegressor):
        return fit_candidate(table, target, candidate, classifier)
    if classifier:
        raise ValueError('Only RUL regression is in scope')
    task = candidate.model.task
    group_column, cycle = ('unit_id', 'cycle') if task == 'engine' else ('battery_id', 'discharge_cycle')
    weights = equal_group_weights(table[group_column]) if candidate.model.group_balanced else None
    prep = _preprocessor()
    values = prep.fit_transform(table.loc[:, candidate.features], scaler__sample_weight=weights)
    names = np.asarray(candidate.features)[prep.named_steps['variance'].get_support()]
    if cycle not in names:
        raise ValueError('Varying observed cycles required for lifetime learning')
    position = list(names).index(cycle)
    values = pd.DataFrame(values, columns=names, index=table.index)
    scaler = prep.named_steps['scaler']
    model = clone(candidate.model).fit(values, table[target].clip(0, candidate.upper), sample_weight=weights,
        cycle_mean=float(scaler.mean_[position]), cycle_scale=float(scaler.scale_[position]))
    return prep, model
