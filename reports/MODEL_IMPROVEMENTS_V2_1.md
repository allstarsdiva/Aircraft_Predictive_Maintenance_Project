# Readiness-v2.1 Model Improvements

> Fuel update: readiness-v2.2 adds a low-false-alarm phase-residual alert model while retaining the Extra Trees challenger as an offline review tier. See `reports/FUEL_MODEL_IMPROVEMENT.md` for current fuel results.

## Outcome

The engine, hydraulic cooler, and fuel-system experiments were upgraded without
artificially targeting a lower or higher score. The implementation now favors
leakage resistance, robustness evidence, and explicit failure gates.

## Engine RUL

Four regressors were compared using five-fold cross-validation grouped by complete
engine ID. The official NASA test set was not used for selection. Random Forest was
retained because its grouped RMSE was within 1% of the best candidate and it gave
the most stable established baseline.

| Evaluation | MAE | RMSE | R-squared |
|---|---:|---:|---:|
| Grouped out-of-fold | 11.56 cycles | 16.28 cycles | 0.847 |
| Official FD001 test | 13.80 cycles | 18.61 cycles | 0.799 |
| Sensor stress test | 13.78 cycles | 18.60 cycles | 0.800 |

The stress test adds Gaussian feature noise equal to 2% of the training standard
deviation and replaces 1% of tested sensor features with training medians. The
model keeps its conditional readiness pass. Its empirical 95% interval covers 85%
of official test engines, so external calibration remains necessary.

## Hydraulic Cooler

The cooler model now excludes all 21 summary features derived from the virtual
`CE`, `CP`, and `SE` channels. It uses 98 measured pressure, flow, temperature,
vibration, and motor-power features.

| Evaluation | Accuracy | Balanced accuracy | Macro F1 |
|---|---:|---:|---:|
| Stable grouped folds | 100.00% | 100.00% | 100.00% |
| 5% noise + 3% median replacement | 100.00% | 100.00% | 100.00% |
| Source-designated unstable cycles | 94.97% | 94.97% | 95.02% |

The stable rig conditions remain perfectly separable even after proxy removal.
The 94.97% unstable-cycle result is the more realistic challenge result to present;
the score was measured, not manually reduced.

## Fuel Anomaly Detection

The original normal-only One-Class SVM remains available for reproducibility. A
new supervised challenger adds four mission-phase features and holds out one
complete failure scenario per fold, together with a contiguous block of normal
operation.

| Fuel model | Balanced accuracy | Detection rate | False-alarm rate |
|---|---:|---:|---:|
| Normal-only One-Class SVM | 57.38% | 39.33% | 24.56% |
| Phase-aware Extra Trees challenger | 60.89% | 93.13% | 71.35% |

The challenger finds substantially more faults, but its false-alarm rate is unsafe.
Only one normal trajectory exists, and each held-out normal phase is unfamiliar to
the model. The fuel readiness gate therefore remains failed and no readiness-v2
fuel prediction endpoint is enabled. Additional independent normal missions are a
data requirement, not a hyperparameter problem.

## Artifacts and Verification

- Engine artifact: `models/readiness/engine_fd001_bundle.joblib`
- Cooler artifact: `models/readiness/hydraulic/cooler_condition_percent_bundle.joblib`
- Fuel challenger: `models/readiness/fuel_system_challenger_bundle.joblib`
- Complete metrics: `reports/metrics/readiness_v2_retraining.json`
- Automated verification at v2.1: 91 tests passed; the current v2.2 suite contains 95 tests

All models remain research prototypes and are not validated or certified for
aircraft maintenance decisions.
