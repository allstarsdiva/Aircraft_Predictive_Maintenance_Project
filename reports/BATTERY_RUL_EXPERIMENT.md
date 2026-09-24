# Experimental Battery RUL Model

## Purpose

This experiment estimates remaining discharge cycles until a battery first
reaches its source-documented end-of-life capacity threshold. It is separate
from the SOH model and is intentionally marked experimental because only nine
battery trajectories contain directly observed end-of-life labels.

## Data and Leakage Controls

- 493 valid, pre-EOL discharge cycles from nine batteries.
- Curve-derived voltage, current, temperature, load, duration, throughput, and
  energy features plus cycle and ambient-temperature context.
- Capacity, SOH, observed EOL cycle, and RUL are excluded from model inputs.
- Each validation fold holds out one complete battery; individual cycles from
  a held-out battery never appear in training.
- Model selection uses the mean RMSE across batteries so long trajectories do
  not decide the result solely because they contain more rows.

## Leave-One-Battery-Out Results

| Model | MAE (cycles) | RMSE (cycles) | R-squared | Macro battery RMSE |
|---|---:|---:|---:|---:|
| Median reference | 29.37 | 36.70 | -0.223 | 30.22 |
| Ridge | 10.18 | 12.45 | 0.859 | 11.94 |
| Random Forest | **9.32** | **12.28** | **0.863** | **9.55** |

Random Forest is selected and refitted on all nine observed-EOL batteries.
The serialized artifact is `models/battery/rul_experimental_bundle.joblib`.

## Experimental Uncertainty Interval

The absolute leave-one-battery-out residuals provide a conservative finite-
sample 90% error quantile of 18.55 cycles. The saved bundle returns the point
prediction and an interval formed from that error radius, clipped at zero.

- Nominal interval coverage: 90%
- Empirical out-of-fold coverage: 90.26%
- Mean interval width after clipping at zero: 35.28 cycles

This is an empirical cross-validated interval, not a certified coverage
guarantee. Nine independent observed-EOL batteries are too few to establish
reliable performance across unseen chemistries, operating profiles, or sensor
conditions.

## Limitations

- End-of-life is a dataset threshold, not a universal aviation maintenance rule.
- Several labeled trajectories are short, ranging from 10 to 125 cycles.
- Error varies materially by battery; B0042 and B0005 are the hardest held-out
  trajectories.
- Full discharge-curve features are only available after the discharge test and
  therefore do not represent real-time, mid-flight prediction.
- The output supports experimentation and demonstration only. It must not be
  used for certified maintenance or flight-safety decisions.

## Reproduction

Run:

```powershell
.\.venv\Scripts\python.exe -m src.train_battery_rul
```

Detailed metrics are stored in `reports/metrics/battery_rul_experiment.json`;
out-of-fold predictions are stored in
`reports/metrics/battery_rul_logo_predictions.csv`.
