"""Research RUL methods: robust causal trends and unit-balanced estimators."""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.utils.validation import check_is_fitted

from src.data.battery import DOCUMENTED_EOL_CAPACITY_AH
from src.retrain_readiness import _preprocessor
from src.targeted_retraining import fit_candidate


def equal_group_weights(groups):
    groups = pd.Series(np.asarray(groups))
    if groups.empty or groups.isna().any():
        raise ValueError('Nonempty, nonmissing fitting groups required')
    weights = 1.0 / groups.map(groups.value_counts()).to_numpy(float)
    return weights / weights.mean()


def robust_battery_features(table):
    required = ['battery_id', 'discharge_cycle', 'charge_throughput_ah']
    if not set(required).issubset(table) or table.empty:
        raise ValueError('Nonempty battery histories required')
    if table.duplicated(required[:2]).any():
        raise ValueError('Unique battery cycles required')
    if not np.isfinite(table[required[1:]].to_numpy(float)).all():
        raise ValueError('Finite battery histories required')
    chunks = []
    for battery, group in table.groupby('battery_id', sort=False):
        group = group.sort_values('discharge_cycle').reset_index(drop=True)
        if battery not in DOCUMENTED_EOL_CAPACITY_AH:
            raise ValueError('Documented battery EOL threshold required')
        cycles = group.discharge_cycle.to_numpy(float)
        q = group.charge_throughput_ah
        # Only completed discharges at or before the prediction time are used.
        smooth = q.rolling(5, min_periods=1).median()
        initial = q.iloc[:5].expanding().median().reindex(group.index, method='ffill')
        margin = smooth - DOCUMENTED_EOL_CAPACITY_AH[battery]
        features = {'robust_capacity_median5': smooth,
                    'robust_capacity_margin': margin,
                    'robust_capacity_relative_initial': smooth - initial,
                    'robust_capacity_mad7': q.rolling(7, min_periods=1).apply(
                        lambda values: np.median(np.abs(values - np.median(values))), raw=True)}
        for window in (7, 21):
            slopes = []
            for end in range(len(group)):
                start = max(0, end + 1 - window)
                x = cycles[start:end + 1]
                y = smooth.iloc[start:end + 1].to_numpy()
                left, right = np.triu_indices(len(x), k=1)
                slopes.append(float(np.median((y[right] - y[left]) / (x[right] - x[left])))
                              if len(left) else 0.)
            slope = np.asarray(slopes)
            declining = slope < -1e-4
            features[f'robust_capacity_slope{window}'] = slope
            features[f'robust_declining{window}'] = declining.astype(float)
            features[f'robust_life_proxy{window}'] = np.clip(np.where(
                declining, margin.to_numpy() / -np.minimum(slope, -1e-4), 500.), 0, 500)
        chunks.append(pd.concat([group, pd.DataFrame(features)], axis=1))
    return pd.concat(chunks, ignore_index=True)


class RULMethodRegressor(RegressorMixin, BaseEstimator):
    """Fixed XGBoost/tree ensemble; weights never learned from audit results."""
    def __init__(self, task='engine', method='xgb', depth=3, iterations=400,
                 group_balanced=True, log_target=False, seed=20260912):
        self.task = task
        self.method = method
        self.depth = depth
        self.iterations = iterations
        self.group_balanced = group_balanced
        self.log_target = log_target
        self.seed = seed

    def fit(self, X, y, sample_weight=None):
        if self.task not in ('engine', 'battery_rul') or self.method not in ('xgb', 'blend', 'extra'):
            raise ValueError('Unsupported RUL method or task')
        if not isinstance(X, pd.DataFrame):
            raise ValueError('Named feature frame required')
        if {'unit_id', 'battery_id', 'uid', 'rul', 'rul_cycles', 'observed_eol_cycle', 'soh_percent'} & set(X):
            raise ValueError('Labels and identity columns cannot be predictors')
        y = np.asarray(y, dtype=float)
        if y.ndim != 1 or not np.isfinite(y).all() or np.any(y < 0):
            raise ValueError('Finite nonnegative one-dimensional RUL required')
        self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        self.n_features_in_ = X.shape[1]
        self.models_ = []
        target = np.log1p(y) if self.log_target else y
        if self.method != 'extra':
            from xgboost import XGBRegressor
            boosted = XGBRegressor(n_estimators=self.iterations, max_depth=self.depth,
                learning_rate=.035, min_child_weight=5 if self.task == 'engine' else 2,
                reg_lambda=10., reg_alpha=.1, subsample=.8, colsample_bytree=.8,
                max_bin=128, tree_method='hist', objective='reg:squarederror',
                random_state=self.seed, n_jobs=2, verbosity=0)
            boosted.fit(X, target, sample_weight=sample_weight)
            self.models_.append(boosted)
        if self.method in ('blend', 'extra'):
            if self.task == 'engine' and self.method == 'blend':
                other = HistGradientBoostingRegressor(max_iter=220, max_leaf_nodes=15,
                    min_samples_leaf=25, learning_rate=.05, l2_regularization=5,
                    early_stopping=False, random_state=self.seed)
            else:
                other = ExtraTreesRegressor(n_estimators=250, min_samples_leaf=2,
                    max_features=.8, n_jobs=2, random_state=self.seed)
            other.fit(X, target, sample_weight=sample_weight)
            self.models_.append(other)
        self.weights_ = np.array([.5, .5]) if len(self.models_) == 2 else np.array([1.])
        return self

    def predict(self, X):
        check_is_fitted(self, 'models_')
        if not isinstance(X, pd.DataFrame) or list(X.columns) != list(self.feature_names_in_):
            raise ValueError('Predictor names and order must match training')
        predictions = np.asarray([model.predict(X) for model in self.models_], dtype=float)
        if self.log_target:
            predictions = np.expm1(np.clip(predictions, 0, 20))
        return np.maximum(0, np.average(predictions, axis=0, weights=self.weights_))


def fit_method_candidate(table, target, candidate, classifier):
    if not isinstance(candidate.model, RULMethodRegressor):
        return fit_candidate(table, target, candidate, classifier)
    if classifier:
        raise ValueError('Only RUL regressors are in scope')
    group_column = 'unit_id' if candidate.model.task == 'engine' else 'battery_id'
    weights = equal_group_weights(table[group_column]) if candidate.model.group_balanced else None
    prep = _preprocessor()
    # Equal group influence also applies to fitted standardization, not just loss.
    values = prep.fit_transform(table.loc[:, candidate.features], scaler__sample_weight=weights)
    names = np.asarray(candidate.features)[prep.named_steps['variance'].get_support()]
    values = pd.DataFrame(values, columns=names, index=table.index)
    model = clone(candidate.model).fit(values, table[target].clip(0, candidate.upper), sample_weight=weights)
    return prep, model
