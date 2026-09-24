# Fuel-System Model Improvement

> Superseded for the active experimental model: see FUEL_NESTED_IMPROVEMENT.md.
> The new nested comparison reports 68.64% balanced accuracy and 39.04% detection.
> Numbers below document the older phase-template experiment.

## Result

Fuel modeling now uses two experimental tiers because the available data cannot
support one model that simultaneously provides high detection and low false alarms.

| Model and purpose | Accuracy | Balanced accuracy | Detection | False alarms |
|---|---:|---:|---:|---:|
| Previous One-Class SVM | 46.55% | 57.38% | 39.33% | 24.56% |
| Extra Trees review tier | 80.23% | 60.89% | 93.13% | 71.35% |
| Phase-residual alert tier | 41.29% | 61.99% | 27.49% | 3.51% |

Ordinary accuracy is not the selection metric because 80% of the rows are labeled
abnormal. Predicting every row as abnormal would therefore achieve 80% accuracy.
Balanced accuracy, detection rate, and false-alarm rate are reported together.

## Changes Implemented

- Added a normal sensor template aligned by mission sample position.
- Compared mean, 75th-percentile, top-two-mean, and maximum residual aggregation.
- Compared calibration quantiles from 0.80 through 0.99.
- Used a separate contiguous normal calibration block for each test fold.
- Added causal persistence rules of one sample, three-of-five, and four-of-seven.
- Selected the candidate using balanced accuracy with a penalty above a 10%
  false-alarm rate.
- Retained the high-sensitivity Extra Trees model only as a review tier.
- Switched the legacy experimental API endpoint to the low-false-alarm phase model.

The selected alert candidate uses the 75th-percentile residual, a 97.5th-percentile
calibration threshold, and requires four positive samples in a trailing seven-sample
window.

## Validation Boundary

The phase detector uses six contiguous normal test blocks, a different contiguous
calibration block, and the remaining normal rows for fitting. Abnormal decisions are
aggregated across the six fitted detectors. This avoids random-row evaluation, but
all normal rows still come from one trajectory.

The phase detector reduces false alarms substantially but misses many weak anomalies.
The Extra Trees model detects nearly all anomalies but falsely flags most normal
rows. Neither model passes readiness. Multiple independent normal missions are still
required before the threshold, detection rate, or false-alarm rate can be trusted.

## Artifacts

- `models/readiness/fuel_phase_residual_bundle.joblib`
- `models/readiness/fuel_system_challenger_bundle.joblib`
- `reports/metrics/fuel_phase_tuning.json`
- `reports/metrics/readiness_v2_retraining.json`

These models are research artifacts and must not be used for aircraft maintenance
decisions.
