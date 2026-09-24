# Engine and battery RUL retraining — 2026-09-12

## Decision

Retain the new engine as an improved research candidate. Keep the previous
2026-09-11 battery-history candidate: the new battery model did not improve the
fixed audit. No serving models or active release were replaced. Hydraulic, SOH,
landing gear, and fuel were not retrained or modified.

| Fixed audit metric | Previous candidate | New candidate | Proposed target |
|---|---:|---:|---:|
| Engine MAE, cycles | 24.70 | 17.04 | <=15; not met |
| Engine RMSE, cycles | 37.88 | 28.19 | <=20; not met |
| Battery RUL MAE, cycles | 11.20 | 12.78 | <=10; not met |
| Battery RUL RMSE, cycles | 13.42 | 14.67 | Reported diagnostic |

## Engine official FD001 regression check

| Metric | Deployed model's saved result | Previous candidate | New candidate |
|---|---:|---:|---:|
| MAE, cycles | 13.80 | 14.44 | 10.63 |
| RMSE, cycles | 18.61 | 19.49 | 16.27 |
| R-squared | 0.7994 | 0.7800 | 0.8467 |

The new candidate meets the numerical FD001 benchmark target but not the broader
random-truncation audit target. Official FD001 labels were not used in this
round's model selection, but have been inspected in earlier development; this
is not a fresh external test. Deployed and candidate models use different fitting
populations; only the two candidate comparisons use matching fitting groups.

## What changed

- Engine: additional causal 20-cycle exponential averages, deviations from an
  initial baseline, 20/50-observation slopes, and 30-cycle variability for 14
  sensors. The initial baseline grows using only available observations until
  ten observations exist. No future engine observations become model inputs.
- Engine candidates: Extra Trees, histogram gradient boosting, and distance-
  weighted nearest neighbours; tree models tested caps of 125, 175, and no cap.
  The selected model is histogram gradient boosting on combined features with
  a 175-cycle training/prediction cap. Raw evaluation labels remain unchanged.
- Battery: smoothed charge-throughput slopes over 5/15/30 past discharges,
  capacity margin to the source-documented EOL threshold, and bounded linear
  life-extrapolation proxies. Thresholds are documented metadata, not learned
  battery-ID predictors; observed EOL cycles and RUL labels are never inputs.
  Non-decreasing/insufficient slope uses an explicit proxy sentinel, not a claim
  of known remaining life. All measurements come from completed discharges.
- Battery candidates: Extra Trees, Random Forest, gradient boosting with squared
  and absolute error, and Ridge; physical-feature and combined-feature views.

Each task compared 15 configurations, including the previous candidate's exact
model specification, for 30 total. Engine selection used three grouped folds and
five fixed trajectory fractions per validation engine. Battery selection used
leave-one-battery-out inside fitting groups. Each group contributes equally to
the selection loss. The scoring rule and candidate grid were fixed before outer
scoring; no candidate was switched based on outer results.

The new battery winner had fitting-only mean per-battery validation MAE 6.58,
but audit MAE 12.78. This discrepancy is precisely why selection scores are not
reported as final performance and why the previous battery candidate is retained.

## Calibration remains unresolved

| Candidate | Nominal interval coverage | Audit coverage | Mean audit interval width |
|---|---:|---:|---:|
| New engine | 95% | 90% | 91.10 cycles |
| New battery RUL | 90% | 6.4% | 8.79 cycles |

The engine's official FD001 interval coverage is 97%, with mean width 90.72 cycles.
High coverage alone is not proof of useful precision; interval widths are reported.
The battery audit still has one calibration battery and one evaluation battery,
so the threshold learned from one trajectory does not generalize reliably.
Calibration/evaluation groups were not added to model fitting to improve a score.

## Reproducibility and scope

- Training: `src/rul_retraining_v2.py`
- Tests: `tests/test_rul_retraining_v2.py`
- New artifacts: `models/candidates/rul-retrain-20260912/{engine,battery_rul}/`
- Each task stores `candidate.joblib`, `evaluation.json`, `audit_inputs.csv`, and
  `audit_predictions.csv`; engine also stores `official_predictions.csv`.
- The report records group partitions, all inner scores, selected features/model
  parameters, calibration size, and artifact/input SHA-256 hashes.
- Source data were verified against the baseline release. New features do not
  overwrite any existing raw or processed files.

Verify and try the saved candidates from the project root:

```powershell
.\.venv\Scripts\python.exe -m src.rul_retraining_v2 --replay
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Replay verifies hashes and reproduces saved predictions/intervals using exact
CSV floating-point loading; it does not provide a fresh accuracy estimate.
Without `--replay`, the trainer refuses to overwrite completed experiment tasks.

All data and audit labels have influenced earlier work. Group isolation prevents
within-run leakage but does not turn this development experiment into independent
validation or establish aircraft readiness. The new engine also requires its
causal trend extractor at serving time; the current backend is unchanged.

## Verification completed

- Full automated suite: 136 passed in 10.56 seconds.
- Both saved candidates replayed with matching predictions and intervals.
- All 11 serving model artifacts match the frozen release hashes; the active
  research release and its manifest pointer remain unchanged.

## Next steps

Validate engine generalization across early-life and near-failure trajectories
without narrowing the test population to make the target pass. Retain the
2026-09-11 battery-history candidate pending more representative independent
battery runs and a defensible calibration design. Do not promote the new battery
candidate or report its fitting-only score as its test error.

Overall implementation remains 90% estimated. Retraining is complete for this
round; the broader numerical targets and final-readiness conditions are not met.
