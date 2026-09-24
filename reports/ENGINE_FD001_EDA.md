# NASA C-MAPSS FD001 EDA Findings

Analysis date: 2026-08-21

Notebook: `notebooks/01_engine_cmapss_eda.ipynb`

## Integrity Results

| Check | Result |
|---|---:|
| Rows | 20,631 |
| Engines | 100 |
| Source columns | 26 |
| Sensor columns | 21 |
| Missing values | 0 |
| Duplicate unit/cycle pairs | 0 |
| Minimum derived training RUL | 0 cycles |
| Maximum derived training RUL | 361 cycles |

All engine trajectories reach a zero-RUL failure row, as required by the training-label definition.

## Engine Lifetimes

| Statistic | Lifetime |
|---|---:|
| Minimum | 128 cycles |
| Median | 199 cycles |
| Maximum | 362 cycles |

The range confirms that model validation must be grouped by engine. A random row split would allow different cycles from the same degradation trajectory to appear in both training and validation data.

## Constant Sensors

The following measurements have only one value throughout FD001:

- `sensor_1`
- `sensor_5`
- `sensor_10`
- `sensor_16`
- `sensor_18`
- `sensor_19`

These six columns cannot contribute predictive variation in FD001 and should be removed by a variance filter fitted only on the training partition. Fifteen sensor columns remain variable.

## Strongest Linear RUL Associations

| Sensor | Pearson correlation with RUL |
|---|---:|
| `sensor_11` | -0.6962 |
| `sensor_4` | -0.6789 |
| `sensor_12` | 0.6720 |
| `sensor_7` | 0.6572 |
| `sensor_15` | -0.6427 |

These correlations show useful degradation signals but are not sufficient on their own for final feature selection. Nonlinear relationships, operating conditions, and validation performance must also be considered.

## Healthy Versus Near-Failure Shift

For exploratory comparison only:

- Healthy observations: RUL above 120 cycles.
- Near-failure observations: RUL at or below 30 cycles.

The largest standardized mean changes occur in the same five sensors:

| Sensor | Standardized near-failure minus healthy shift |
|---|---:|
| `sensor_11` | 2.2274 |
| `sensor_4` | 2.1728 |
| `sensor_12` | -2.1449 |
| `sensor_7` | -2.0987 |
| `sensor_15` | 2.0636 |

These analysis bands are not approved aircraft-maintenance thresholds.

## Generated Figures

- `reports/figures/engine/fd001_engine_lifetimes.png`
- `reports/figures/engine/fd001_sensor_distributions.png`
- `reports/figures/engine/fd001_sensor_rul_correlations.png`
- `reports/figures/engine/fd001_normalized_degradation_trends.png`

## Modeling Implications

- Partition by `unit_id` before fitting preprocessing or models.
- Fit a variance filter on training engines to remove constant columns.
- Scale only the variable sensors, using parameters learned from training engines.
- Establish a simple non-temporal baseline before adding rolling or sequence features.
- Do not rename anonymized C-MAPSS sensors as physical measurements in the frontend.
- Evaluate MAE and RMSE on engines that were not used for fitting.
