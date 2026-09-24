# RUL fitting-only error and data-quality report

Date: 2026-09-14. Scope: engine RUL and battery RUL diagnostics only.

Follow-up on 2026-09-15: the source Capacity/full-throughput discrepancy was
resolved for all 21 inspected curves by using the documented 2.7 V cutoff.
See `reports/BATTERY_SOURCE_REVIEW_20260915.md`; transition provenance remains
unresolved. The historical diagnostic values below have not been changed.

## Outcome

The diagnostic identifies concrete priorities before further model search:

1. Engine errors concentrate early in life and at long prediction horizons.
   The retained 175-cycle cap imposes a substantial error floor there, while
   the historical five-checkpoint selection underrepresents the earliest cycles.
2. Battery end-of-life labels need an operating-protocol review, especially for
   B0042/B0043, where the first threshold crossing coincides with a temperature
   and discharge-condition change. This is not proof that those labels are wrong.
3. The inspected raw charge-throughput integrations match the processed data;
   changing that calculation without a source-based reason is not justified.

No source data, labels, retained models, release pointer, or serving models were
changed. No new model was selected or promoted. Existing audit performance remains
engine MAE/RMSE 17.04/28.19, battery 11.20/13.42 cycles, and official FD001 engine
10.63/16.27. The diagnostic scores below are NOT replacements for those results.

## Method and isolation

- Restricted analysis to the retained experiment's fitting units before computing
  model features: 60 engine units / 12,440 rows, and 7 batteries / 327 rows.
- Refit the retained model specifications inside three grouped engine folds and
  seven leave-one-battery-out folds. Every fitting row was scored exactly once
  by a model trained on other units. Preprocessing was also fitted within folds.
- Did not score calibration groups, outer audit groups, or official test engines.
- Compared full trajectories with the old five engine checkpoints. No hyperparameter
  search, threshold tuning, or selective removal of difficult rows was performed.
- Lifetime phase uses thirds of the observed complete lifetime for diagnostic
  grouping only. It is derived from labels and never supplied as a predictor.
- Reviewed source metadata and some post-threshold records of fitting batteries
  only, for label provenance. Post-threshold records were not added to training.

This remains development analysis on previously inspected datasets, not fresh
external validation or evidence of aircraft readiness.

## Engine findings

| Lifetime phase | Rows | Mean per-engine MAE | Row-weighted MAE |
|---|---:|---:|---:|
| Early third | 4,128 | 34.12 | 40.18 |
| Middle third | 4,148 | 19.47 | 19.90 |
| Late third | 4,164 | 5.21 | 5.34 |

All errors are cycles. Within true RUL 0-30, row-weighted MAE is 3.11; above
100 cycles it is 33.49. These conditional scores must not be called overall
model accuracy. Near-failure overestimation by more than 10 cycles occurs in
2.58% of the 0-30 RUL diagnostic rows; this is a descriptive threshold, not an
aircraft operational safety limit or a remeasurement of earlier calibration claims.

The model cannot predict above 175 cycles. Even a perfect predictor under that
cap has row-weighted MAE of at least 21.86 cycles in the early-third sample,
because its minimum error is `max(actual_RUL - 175, 0)`. Actual early-third MAE
is 40.18: the cap contributes a structural limitation but does not explain every
error. This bound does not prove that removing the cap will improve a fitted model.

The historical five checkpoints at 20%, 40%, 60%, 80%, and 100% of each trajectory
give mean per-engine MAE 15.18. Across all cycles, it is 19.56 (row-weighted MAE
21.76). This sample-design difference explains why a good checkpoint-selection
score can coexist with weak early-life behavior. The next protocol should cover
the earliest cycles explicitly, without dropping the existing audit/benchmark.

Worst full-trajectory fitting-validation units are 69 (MAE 71.71), 92 (55.99),
96 (55.56), 67 (53.60), and 5 (42.34). Unit 69's lifetime exceeds the maximum
lifetime seen in its inner training fold, illustrating a generalization challenge.

Engine fitting data have no duplicate unit/cycle keys, nonfinite numeric values,
cycle gaps, negative labels, or inconsistent run-to-failure labels. Seven columns
are constant: operational setting 3 and sensors 1, 5, 10, 16, 18, 19. Constant
inputs are not an explanation for the long-horizon error; the existing fitted
preprocessor already removes zero-variance predictors.

## Battery findings

| Fitting battery | Rows | Observed EOL cycle | Out-of-fold MAE |
|---|---:|---:|---:|
| B0006 | 109 | 109 | 8.67 |
| B0018 | 97 | 97 | 10.07 |
| B0042 | 41 | 42 | 15.78 |
| B0043 | 41 | 42 | 5.38 |
| B0046 | 17 | 17 | 4.39 |
| B0047 | 10 | 10 | 5.57 |
| B0048 | 12 | 12 | 1.83 |

Mean per-battery MAE is 7.38; row-weighted MAE is 9.00. Those are inner diagnostic
scores, not the retained model's 11.20-cycle outer audit result. The two longer
batteries supply about 63% of fitting rows. Only one fitting battery contributes
RUL values above 100, so this horizon has very limited independent coverage.

All 327 processed labels match reconstruction from the source metadata's existing
first-positive-capacity-crossing rule. There are no duplicate cycle keys, negative
RUL labels, or nonfinite numeric values. B0042 and B0043 each have one cycle gap
in the eligible processed rows; these gaps are recorded for review, not filled.

### End-of-life and operating-condition review

| Battery/cycle | Source capacity | Integrated throughput | Ambient condition |
|---|---:|---:|---|
| B0042, cycle 41 | 1.5656 Ah | 1.5918 Ah | 22 C |
| B0042, cycle 42 (labeled EOL) | 0.0707 Ah | 1.1631 Ah | 4 C |
| B0043, cycle 41 | 1.4695 Ah | 1.4856 Ah | 22 C |
| B0043, cycle 42 (labeled EOL) | 0.0570 Ah | 0.0772 Ah | 4 C |

B0042's mean absolute current changes from about 2.00 A to 3.94 A, while B0043's
changes from about 1.86 A to 0.27 A. Both source traces shorten from about 2,862
to 1,055 seconds at the labeled EOL cycle. Their large capacity changes therefore
coincide with changed operating conditions, not an isolated smooth-aging trend.

The 21 inspected raw curves (last three processed fitting cycles per battery)
all reproduce the stored charge-throughput feature to numerical tolerance.
For B0042 cycle 42, the source Capacity field differs substantially from the
integrated measured-current throughput. These quantities must not be assumed
interchangeable without understanding the source's measurement convention.
Neither value was substituted for the other.

Inference: these labels may partly reflect protocol changes rather than only
intrinsic degradation. Verify the source experiment and its intended EOL convention
before deciding whether to normalize conditions, model separate regimes, or treat
transitions as censoring boundaries. Do not relabel simply to improve error scores.

B0046, B0047, and B0048 each have above-threshold capacity readings among the next
three valid discharges after their first crossing. That warrants review of the
first-crossing interpretation, but does not by itself invalidate the existing
threshold-based labels. B0006/B0018 remain below the threshold in those checks.

## Recommended next work, in priority order

1. Review the source experiment notes and metadata/curve linkage for B0042/B0043
   around the protocol transition. Confirm the capacity and EOL definitions.
   Record any justified preprocessing/label change in a new dataset version;
   retain the original data and model champions for comparison.
2. Freeze an engine selection protocol with explicit early/middle/late coverage
   and per-unit scoring across the available trajectory. Keep existing audit,
   official benchmark, and uncertainty non-regression checks. Evaluate cap and
   long-horizon approaches against that protocol, not selected easy rows.
3. Add independent battery trajectories covering the intended temperature/current
   conditions and longer lifetimes, plus several independent calibration batteries.
   Similar rows from the same battery do not substitute for independent units.
4. Only then perform a bounded challenger comparison. Preserve the protected
   candidates unless the predeclared evidence supports replacement. None of these
   recommendations has been silently implemented as a model or label change here.

## Artifacts and verification

- Code: `src/rul_fitting_diagnostics.py`.
- Tests: `tests/test_rul_fitting_diagnostics.py`.
- Results: `reports/metrics/rul_fitting_diagnostics_20260914/diagnostics.json`.
- Row-level evidence: adjacent `engine_oof.csv` and `battery_rul_oof.csv`.
- Raw-curve evidence and hashes: adjacent `raw_source_trace.json`.

The completed run is protected from overwrite. Its source-trace command is
`python -m src.rul_fitting_diagnostics --trace-sources`; it also refuses to replace
an existing trace. Use the project virtual-environment Python for these commands.

Six diagnostic tests passed before the data run. Final diagnostic/protection
suite: 21 passed. Full project suite: 171 passed, 2 failed in 36.70 seconds; the
known malformed numeric field in fuel `Scenario_Two.csv` still causes those two
failures. Fuel was left untouched, and the full suite is not green.

Retained source/snapshot hashes, all 11 serving artifacts, the release pointer,
and the diagnostic input files verified unchanged. Overall project implementation
remains 90% estimated. This step improves diagnostic evidence, not model accuracy.
