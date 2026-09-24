# C-MAPSS FD001 Official Test Evaluation

Evaluation implementation: `src/evaluate.py`

Evaluation date: 2026-08-21

## Protocol

1. Select Random Forest using only the internal engine-grouped validation experiment.
2. Refit preprocessing and the selected model using all 100 FD001 training engines.
3. Build causal features for each official test trajectory.
4. Predict only at each test engine's final observed cycle.
5. Compare the 100 predictions with NASA's supplied terminal RUL labels.

No official test labels are used for preprocessing, feature selection, model fitting, or hyperparameter selection in this evaluation.

## Official Raw-RUL Results

| Metric | Result |
|---|---:|
| Test engines | 100 |
| MAE | 13.91 cycles |
| RMSE | 18.71 cycles |
| R-squared | 0.797 |
| Median absolute error | 10.06 cycles |
| Mean signed error | +0.26 cycles |
| NASA asymmetric score | 624.90 |

A positive signed error means predicted RUL is greater than actual RUL. This is a late or optimistic prediction and receives the larger NASA penalty.

## Capped-Target Results

The model was trained with RUL capped at 125 cycles. For a target-aligned secondary comparison, official labels were also capped at 125:

| Metric | Result |
|---|---:|
| MAE | 12.84 cycles |
| RMSE | 17.48 cycles |
| R-squared | 0.810 |

The raw-label results remain the primary official benchmark.

## Performance by Actual Terminal RUL

| Actual RUL band | Engines | MAE | RMSE | Mean signed error |
|---|---:|---:|---:|---:|
| 0-30 | 25 | 9.19 | 15.07 | +8.49 |
| 31-60 | 14 | 10.98 | 12.65 | +6.49 |
| 61-90 | 15 | 19.03 | 22.58 | +7.80 |
| 91-125 | 35 | 11.86 | 16.46 | -2.49 |
| Above 125 | 11 | 27.91 | 30.11 | -27.91 |

The large negative error above 125 cycles is expected because predictions are capped at 125. The more important safety-oriented issue is positive bias in the 0-30 band: the model tends to overestimate remaining life for the engines closest to failure.

## Largest Absolute Errors

| Unit | Actual RUL | Predicted RUL | Absolute error |
|---:|---:|---:|---:|
| 45 | 114.0 | 59.50 | 54.50 |
| 74 | 126.0 | 77.32 | 48.68 |
| 55 | 137.0 | 94.99 | 42.01 |
| 18 | 28.0 | 68.27 | 40.27 |
| 37 | 21.0 | 61.14 | 40.14 |

Units 18 and 37 are especially important because the model substantially overestimates RUL close to failure.

## Saved Outputs

- Full-training model bundle: `models/engine/fd001_official_test_bundle.joblib`.
- Metrics: `reports/metrics/engine_fd001_official_test.json`.
- Per-engine predictions: `reports/metrics/engine_fd001_official_test_predictions.csv`.
- Actual-versus-predicted chart: `reports/figures/engine/fd001_official_test_actual_vs_predicted.png`.
- Ordered prediction chart: `reports/figures/engine/fd001_official_test_ordered_predictions.png`.

The saved bundle was reloaded successfully in a separate process. It contains the full-training variance filter, scaler, Random Forest, input schema, and official test metrics.

## Next Improvement Target

Tune models and decision thresholds with special attention to late predictions below 30 RUL. Candidate approaches include asymmetric sample weighting, quantile-style objectives, conservative prediction calibration, and grouped cross-validation. The official test set must not be repeatedly used for selecting among these alternatives; tuning should return to grouped validation or grouped cross-validation.
