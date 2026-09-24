# FD001 Safety-Oriented Grouped Tuning

Implementation: `src/tune.py`

Tuning date: 2026-08-21

## Selection Protocol

- Five-fold cross-validation grouped by engine ID.
- All 100 training engines participate in out-of-fold evaluation.
- Variance filtering and scaling are refitted inside every fold.
- Six Random Forest configurations are compared.
- Each configuration is evaluated with prediction offsets of 0, 3, 5, 7, and 10 cycles.
- NASA official test labels are not used for candidate or offset selection.

The selection objective is:

```text
RMSE + 1.5 * positive near-failure bias + 0.5 * average NASA penalty
```

Only positive bias below or equal to 30 RUL receives the additional bias penalty because positive errors overestimate remaining life.

## Baseline Versus Selected Calibration

| Metric | Baseline RF | Selected RF with 5-cycle offset |
|---|---:|---:|
| MAE | 11.59 | 13.31 |
| RMSE | 16.34 | 17.17 |
| R-squared | 0.846 | 0.830 |
| Average NASA penalty | 5.96 | 5.04 |
| Near-failure mean bias | +4.60 | -0.13 |
| Near-failure late-prediction rate | 72.0% | 35.3% |
| Safety objective | 26.21 | 19.69 |

The selected calibration reduces the average NASA penalty by approximately 15.5% and changes near-failure predictions from materially optimistic to approximately unbiased. The late-prediction rate falls by 36.7 percentage points. This safety improvement costs approximately 0.83 additional RMSE cycles and 1.72 additional MAE cycles.

## Candidate Outcome

All six candidates selected a 5-cycle conservative offset as their best safety/accuracy balance. The original Random Forest configuration achieved the lowest combined safety objective. Weighted and more regularized candidates reduced some late predictions but did not improve the full objective enough to replace it.

Selected configuration:

- Trees in final refit: 250.
- Maximum depth: 20.
- Minimum samples per leaf: 2.
- Features per split: square root.
- Prediction offset: 5 cycles.
- RUL output bounds: 0-125 cycles.

## Saved Outputs

- Tuned bundle: `models/engine/fd001_tuned_bundle.joblib`.
- Full tuning results: `reports/metrics/engine_fd001_grouped_tuning.json`.
- Out-of-fold predictions: `reports/metrics/engine_fd001_tuned_oof_predictions.csv`.
- Candidate objective chart: `reports/figures/engine/fd001_grouped_tuning_objective.png`.

The tuned bundle was reloaded successfully in a separate process and applies its conservative offset during prediction.

## Interpretation Boundary

This calibration is an engineering-project choice, not a certified aviation safety threshold. Its purpose is to demonstrate how model selection can explicitly account for the greater practical risk of optimistic near-failure predictions.
