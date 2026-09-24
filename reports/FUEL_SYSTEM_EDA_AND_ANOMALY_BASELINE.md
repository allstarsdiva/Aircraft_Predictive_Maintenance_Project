# Fuel-System EDA and Anomaly Baseline

## Outcome

Fuel-system EDA and a normal-only anomaly-detection experiment are complete.
The experiment is technically reproducible, but its blocked row-level result is
weak and must not be presented as a deployment-ready classifier. Only one
normal trajectory is available, so new-normal-trajectory generalization cannot
be measured.

## Data and EDA

- Five neutral scenarios with 171 ordered samples each.
- One normal trajectory and four authoritatively abnormal trajectories.
- Eight raw sensors and 32 causal model features.
- No missing, non-finite, or duplicate feature rows.
- All four abnormal scenarios show large mean shifts in `FTF` and `FTV_S`.
- Scenarios Two and Three additionally show very large `FTT` shifts.

These shifts are descriptive associations only. The public dataset does not
provide authoritative individual fault-event names for Scenarios One-Four.

## Evaluation Design

The normal trajectory is divided into six contiguous time blocks. For each
evaluation fold:

1. Four normal blocks fit the preprocessor and detector.
2. One separate normal block calibrates the 95th-percentile alert threshold.
3. One separate normal block measures false alarms.
4. No abnormal row is used to fit preprocessing, detectors, or thresholds.
5. The six fold detectors vote on each abnormal row.

This is stricter than a random row split, but it remains within-dataset evidence
because the project has only one normal source trajectory.

## Model Comparison

| Detector | Normal specificity | Abnormal detection | Balanced accuracy | Macro F1 |
|---|---:|---:|---:|---:|
| Shrinkage Mahalanobis | 0.719 | 0.395 | 0.557 | 0.443 |
| Isolation Forest | **0.877** | 0.257 | 0.567 | 0.381 |
| One-Class SVM | 0.754 | **0.393** | **0.574** | **0.451** |

One-Class SVM is retained as the best experimental candidate by balanced
accuracy and then macro F1. Its scenario-specific row detection rates are:

| Neutral abnormal scenario | Detection rate |
|---|---:|
| One | 0.298 |
| Two | 0.468 |
| Three | 0.497 |
| Four | 0.310 |

## Interpretation

The selected detector produces persistent alerts in all four abnormal files,
with the first three-consecutive-row alert between ordered samples 94 and 124.
However, it also produces a persistent normal-trajectory alert beginning near
sample 104. The normal operating trajectory changes over time, and one example
is not enough to distinguish every valid operating phase from faults.

The result should therefore be described as a completed experimental baseline
that exposed a data limitation—not as a high-accuracy model. A reliable fuel
model requires additional independent normal trajectories, documented event
onset times, or both.

## Saved Evidence

- Model bundle: `models/fuel_system/normal_anomaly_bundle.joblib`
- EDA metrics: `reports/metrics/fuel_system_eda.json`
- Model metrics: `reports/metrics/fuel_system_anomaly_baselines.json`
- Row predictions: `reports/metrics/fuel_system_blocked_predictions.csv`
- Figures: `reports/figures/fuel_system/`

Reproduce with:

```powershell
.\.venv\Scripts\python.exe -m src.eda_fuel
.\.venv\Scripts\python.exe -m src.train_fuel
```
