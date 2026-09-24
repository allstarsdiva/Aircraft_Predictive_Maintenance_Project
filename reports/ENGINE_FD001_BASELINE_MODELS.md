# C-MAPSS FD001 Baseline Model Report

Training implementation: `src/train.py`

Evaluation date: 2026-08-21

## Experiment Design

- Target: RUL capped at 125 cycles.
- Training partition: 80 complete engines, 16,561 rows.
- Validation partition: 20 complete unseen engines, 4,070 rows.
- Engine overlap: 0.
- Retained features after training-fitted preprocessing: 43.
- All models use the same split, engineered features, and preprocessing.
- Predictions are clipped to the physical project range of 0-125 cycles.

## Validation Results

| Model | MAE | RMSE | R-squared |
|---|---:|---:|---:|
| Median dummy | 35.94 | 44.93 | -0.160 |
| Linear Regression | 12.89 | 17.05 | 0.833 |
| **Random Forest** | **9.93** | **14.38** | **0.881** |

Random Forest reduces RMSE by approximately 15.7% compared with Linear Regression and 68.0% compared with the median dummy model. It is therefore selected as the initial engine baseline.

## Random Forest Configuration

- Trees: 250.
- Maximum depth: 20.
- Minimum samples per leaf: 2.
- Features considered per split: square root of available features.
- Random seed: 42.
- Parallel training enabled.

## Error by Actual RUL Band

| Actual capped RUL | Rows | MAE | RMSE |
|---|---:|---:|---:|
| 0-30 cycles | 620 | 5.16 | 7.70 |
| 31-60 cycles | 600 | 13.70 | 18.72 |
| 61-90 cycles | 600 | 17.34 | 20.55 |
| 91-125 cycles | 2,250 | 8.26 | 12.32 |

Mean prediction bias is +0.39 cycles. The largest individual absolute validation error is 63.68 cycles. The weakest band is 61-90 cycles, which should receive special attention during feature refinement and tuning.

## Saved Outputs

- Model bundle: `models/engine/fd001_baseline_bundle.joblib` (approximately 28.5 MB).
- Machine-readable metrics: `reports/metrics/engine_fd001_baselines.json`.
- Validation predictions: `reports/metrics/engine_fd001_validation_predictions.csv`.
- Error comparison: `reports/figures/engine/fd001_baseline_model_errors.png`.
- Actual-versus-predicted chart: `reports/figures/engine/fd001_best_actual_vs_predicted.png`.

The model artifact contains the fitted variance filter, scaler, selected Random Forest, input feature schema, RUL cap, and validation metrics. A separate-process reload and sample prediction succeeded.

## Limitations and Next Actions

- Results are from the internal 20-engine validation split, not the official FD001 test set.
- Metrics are row-weighted, so longer engine trajectories contribute more observations.
- The 125-cycle cap changes the early-life regression target and must remain consistent during inference and evaluation.
- Risk thresholds have not yet been calibrated.
- Hyperparameters are an informed baseline, not a tuned final configuration.
- Final evaluation must use official test trajectories and supplied terminal RUL labels.
