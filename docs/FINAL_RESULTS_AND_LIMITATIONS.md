# Results, scope, and limitations

This is a university-level multi-dataset research prototype. It is not an
aircraft-certified or operational maintenance system. Scores below come from
different tasks and evaluation designs; they cannot be ranked as one common
"accuracy" score.

## Representative results in the saved reports

| Subsystem/task | Reported result | Evaluation context and caution |
|---|---|---|
| Engine RUL | Selected Random Forest: grouped OOF MAE 11.56, RMSE 16.28, R-squared 0.847; official FD001 test MAE 13.80, RMSE 18.61, R-squared 0.799 | Official test contains 100 unseen NASA engines. Its nominal 95% interval covered 85%; uncertainty calibration is incomplete. |
| Battery SOH | Grouped OOF MAE 2.62 percentage points, RMSE 5.17, R-squared 0.950 | Internal battery-group evaluation; the small dataset and unresolved temperature-history/provenance issues limit generalization. |
| Battery RUL | Leave-one-battery-out MAE 9.36 cycles, RMSE 12.32, R-squared 0.862 | Only nine independent batteries; empirical interval radius is about 18.58 cycles and is not a field-calibrated guarantee. |
| Hydraulic cooler | Grouped accuracy/balanced accuracy/macro F1: 100%; unstable-cycle challenge accuracy 94.97% | Internal hydraulic-rig data; not aircraft validation. |
| Hydraulic valve | Accuracy 83.99%; accepted coverage 61.08%, accepted accuracy 91.86% | Abstains on lower-confidence cases; unstable-cycle challenge is weak (45.77% accuracy). Accepted-only accuracy must be read with coverage. |
| Hydraulic pump | Accuracy 99.10%; balanced accuracy 99.10%; macro F1 99.10% | Internal hydraulic-rig evaluation; not aircraft validation. |
| Hydraulic accumulator | Accuracy 88.82%; accepted coverage 92.68%, accepted accuracy 92.33% | Accepted-only accuracy must be read with coverage; unstable-cycle challenge accuracy is 60.05%. |
| Landing fault / RUL | Fault accuracy 95.07%, balanced accuracy 95.36%; RUL MAE 1.37, RMSE 2.63, R-squared 0.992 | Internal digital-twin evaluation; the dataset archive/version and mass-range provenance remain unresolved. |
| Fuel anomaly | Nested development: accuracy 50.88%, balanced accuracy 68.64%, normal false-alarm rate 1.75%, abnormal detection 39.04% | Readiness gate failed. Only one normal trajectory and scenario-level labels are available; not an independent external test. |

Primary source: `reports/metrics/readiness_v2_retraining.json` (protocol
`readiness-v2.3-fuel-nested`). Engine official-test metrics are also recorded in
`reports/metrics/readiness_v2_retraining.json`; the earlier baseline in
`reports/metrics/engine_fd001_official_test.json` is a different model and must
not be conflated with it. The numbers are dataset-specific research evidence,
not guaranteed current field performance or aircraft readiness.

## What has been implemented

- Dataset-specific validation and preprocessing for five systems.
- Saved pipelines/models, grouped evaluation work, and audit reports.
- FastAPI prediction routes and a React workspace connected to those routes.
- Input checks, warning/abstention behavior, release fingerprints, and automated
  regression tests.
- Dataset example replay for normal/challenge-style demonstrations; these are
  not verified healthy/high-risk aircraft cases.

## Limitations and remaining work

- No fresh independent aircraft or aircraft-representative validation data.
- C-MAPSS, battery, hydraulic, and landing datasets do not establish
  performance on real aircraft fleets; landing data are synthetic.
- Battery uncertainty is under-calibrated; hydraulic condition support and
  acceptance need more independent condition groups.
- Fuel has unresolved sample-level fault-onset labels, only limited normal
  trajectories, and a failed readiness gate.
- Landing archive/version and mass-range provenance remain unresolved.
- The React workspace gives model outputs and audit evidence but does not yet
  provide validated per-prediction sensor attribution across every component.
- A clean Python environment created from `requirements-lock.txt` passed all
  232 Python tests on 2026-10-17. Clean frontend dependency installation/build
  has not yet been rechecked in a fresh environment.

## Safe interpretation

Treat outputs as educational research decision support. Do not use these
predictions to dispatch, release, defer, or schedule aircraft maintenance.
Maintenance risk thresholds are prototype display bands rather than approved
engineering limits. A model's acceptance is not a safety approval.
