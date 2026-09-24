# Battery SOH Baseline Model Report

Training implementation: `src/train_battery.py`

Feature implementation: `src/features.py`

Evaluation date: 2026-08-21

## Experiment Design

- Target: SOH percentage based on measured capacity / 2.0 Ah.
- Rows: 2,750 positive-capacity discharge tests.
- Batteries: 34.
- Training: 27 batteries, 2,328 rows.
- Validation: 7 completely unseen batteries, 422 rows.
- Battery overlap: 0.
- Input features: 23; all retained after training-fitted variance filtering.

Current-capacity and SOH values are not model inputs. Features are calculated from the discharge voltage, current, temperature, load, and time curves plus cycle and ambient-temperature context.

## Validation Results

| Model | MAE | RMSE | R-squared |
|---|---:|---:|---:|
| Median dummy | 24.69% | 35.20% | -0.241 |
| **Linear Regression** | **3.98%** | **10.63%** | **0.887** |
| Random Forest | 5.58% | 13.27% | 0.824 |

Linear Regression is selected as the initial SOH model.

## Validation by Battery

| Battery | Rows | MAE | RMSE | Mean bias |
|---|---:|---:|---:|---:|
| B0029 | 40 | 0.62% | 0.74% | -0.60% |
| B0038 | 47 | 0.78% | 1.37% | -0.40% |
| B0042 | 111 | 12.80% | 20.60% | +11.60% |
| B0044 | 111 | 0.73% | 1.05% | +0.59% |
| B0047 | 69 | 0.56% | 0.64% | -0.56% |
| B0049 | 24 | 1.36% | 1.83% | -1.03% |
| B0050 | 20 | 2.39% | 3.11% | -2.20% |

B0042 contains many extremely low-capacity runs that the source documentation explicitly says have not been fully analyzed. Those observations dominate aggregate RMSE.

## Extreme-SOH Diagnostic

| Validation range | Rows | MAE | RMSE | R-squared |
|---|---:|---:|---:|---:|
| SOH at least 20% | 324 | 0.75% | 1.11% | 0.994 |
| SOH below 20% | 98 | 14.68% | 21.96% | -155.108 |

The model must therefore return an out-of-distribution warning for extremely low SOH until those experiment anomalies are modeled separately.

## Saved Outputs

- Features: `data/processed/battery/soh_features.csv`.
- Model bundle: `models/battery/soh_baseline_bundle.joblib`.
- Metrics: `reports/metrics/battery_soh_baselines.json`.
- Validation predictions: `reports/metrics/battery_soh_validation_predictions.csv`.
- Chart: `reports/figures/battery/battery_soh_actual_vs_predicted.png`.

The saved bundle was reloaded in a separate process and produced a valid SOH prediction.

## Limitations

- Full discharge duration and integrated current are highly informative because capacity itself is derived from discharge behavior. This model estimates SOH after a discharge curve is available; it is not yet an early-cycle or instantaneous estimator.
- Protocol differences across temperature, current, and cutoff voltage remain significant.
- Extremely low-capacity observations need explicit anomaly handling.
- Direct battery RUL modeling remains separate and has only nine eligible trajectories.

## Verification

- Processed data is reproducible and component-scoped.
- Grouped splitting prevents battery leakage.
- Curve features are finite and exclude the target.
- Model serialization and clipping behavior are tested.
- **41 automated tests pass.**
