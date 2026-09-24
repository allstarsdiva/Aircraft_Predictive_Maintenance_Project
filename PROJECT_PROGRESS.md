# Project Progress

Last updated: 2026-09-15

## Overall Completion: 90% (implementation estimate)

This percentage measures the full five-system application, including models, backend, frontend integration, testing, and documentation. It is not the percentage of only the engine model.

| Workstream | Weight | Earned | Current status |
|---|---:|---:|---|
| Scope, environment, and project setup | 10% | 10% | Complete |
| Dataset acquisition, provenance, and schemas | 10% | 9% | All schemas and source pages recorded; exact landing-gear archive/version remains unresolved because its published and local mass ranges conflict |
| EDA and preprocessing for five systems | 20% | 20% | EDA and leakage-safe preprocessing complete for all five confirmed systems |
| Model development and unseen-unit validation | 25% | 22% | Scoped retraining produced valve, accumulator, and SOH candidates meeting numerical targets in audit and grouped checks; engine/RUL, calibration, input integration, and independent validation remain unresolved; fuel unchanged |
| Saved pipelines and FastAPI backend | 15% | 14% | Verified versioned research snapshot, all prediction routes, examples and audit evidence API implemented |
| React frontend integration | 10% | 8% | Default workspace calls all five backend models; original fleet demo remains explicitly simulated; real trends and explanations remain |
| Explainability, system testing, documentation, and demo | 10% | 7% | Latest full suite: 194 passed, 2 fuel-data failures; protected v6 retraining and full-trajectory checks complete; best models retained; explainability and final presentation remain |
| **Total** | **100%** | **90%** | **Implementation in progress; models are not finally validated** |

## Scoped Model Retraining ? 2026-09-11

Only engine, battery SOH/RUL, hydraulic valve, and hydraulic accumulator were
retrained. Passing tasks and fuel were excluded. New candidates are saved
separately; all 11 serving model artifacts and the active release are unchanged.

- Valve: audit balanced accuracy 75.57% -> 100%; grouped cross-check 100%.
- Accumulator: audit balanced accuracy 84.46% -> 97.25%; grouped cross-check 99.03%.
- Battery SOH: audit MAE 3.18 -> 1.39 percentage points; grouped cross-check 1.78.
- Battery RUL: audit MAE 13.75 -> 11.20 cycles; target <=10 remains unmet.
- Engine: audit MAE 25.40 -> 24.70 and RMSE 37.98 -> 37.88; targets remain unmet.

Three candidates meet numerical targets, not final readiness. Waveform/history
inputs require integration, hydraulic support coverage is limited, and battery
intervals remain under-calibrated. These are reused development-data evaluations,
not fresh external tests. Full suite: 131 passed; saved candidate replay verified.
Details and tryout commands: `reports/TARGETED_RETRAINING_20260911.md`.

## Engine and Battery RUL Retraining - 2026-09-12

Compared 15 configurations per task, with grouped model selection restricted to
fitting units. New models are saved separately; no serving artifacts were replaced.

- Engine: fixed-audit MAE 24.70 -> 17.04 cycles and RMSE 37.88 -> 28.19.
  Official FD001 check: MAE 10.63, RMSE 16.27; numerical targets met on that
  benchmark only, not on the broader audit. Retain as a research candidate.
- Battery RUL: fixed-audit MAE 11.20 -> 12.78; the new candidate is worse.
  Retain the previous battery-history candidate. Target <=10 remains unmet.
- Calibration remains unresolved; repeated development evaluations do not
  establish independent validation or real-aircraft readiness.
- Both new candidates reproduce their saved predictions. All 136 tests pass;
  all 11 serving artifacts match the frozen release and its pointer is unchanged.

Details: `reports/RUL_RETRAINING_20260912.md`. Overall completion remains 90%.

## Third RUL Retraining Round - 2026-09-12

Compared another 10 engine and 15 battery configurations with unchanged fitting,
calibration, and audit groups. Neither new candidate improved the retained model.

- Engine: fixed-audit MAE 17.04 -> 17.86 cycles; RMSE 28.19 -> 28.72.
  Official FD001 MAE 10.63 -> 11.52; RMSE 16.27 -> 16.93.
- Battery RUL: fixed-audit MAE 11.20 -> 11.29; RMSE 13.42 -> 13.79.
- Keep the second-round engine and original battery-history research candidates.
  New results are archived separately; no serving model was replaced.
- All 140 tests pass. Both new and previous-round candidates replay correctly;
  all 11 serving artifacts and the active release pointer remain unchanged.

Details: `reports/RUL_RETRAINING_V3_20260912.md`. Overall completion remains 90%;
broader audit targets, calibration, and independent validation remain unresolved.

## Stronger RUL Methods - 2026-09-12

Implemented and tested XGBoost, equal-unit fitting weights, robust causal battery
trends, log-target regression, and fixed model ensembles (22 configurations).

- Engine: retained specification won grouped selection; fixed-audit MAE/RMSE
  remain 17.04/28.19 cycles and official FD001 remains 10.63/16.27.
- Battery: fitting-only mean per-unit validation MAE improved 7.38 -> 5.64,
  but audit MAE worsened 11.20 -> 13.57. Keep the prior battery candidate.
- No improvement on the fixed audit was established. No serving model was
  replaced; all 11 serving artifact hashes and the release pointer are unchanged.
- Full suite: 152 tests passed. New and prior saved candidates replay correctly.

Details: `reports/RUL_METHODS_V4_20260912.md`. Overall completion remains 90%.
Independent validation and reliable battery uncertainty remain priorities.

## Protected RUL Retraining - 2026-09-13

Saved checksum-verified champion copies and added fit-only and outer-audit
non-regression gates. Compared 17 condition-aware/lifetime configurations.

- Engine: retained candidate unchanged, audit MAE/RMSE 17.04/28.19 cycles;
  official FD001 remains 10.63/16.27.
- Battery: new lifetime candidate audit MAE 20.63 was automatically rejected;
  retained battery-history candidate remains 11.20 MAE / 13.42 RMSE.
- No serving models or active release pointer changed; protected source and
  snapshot hashes verified. Use `python -m src.rul_retraining_v5 --status` with
  the project virtual environment to inspect the retained research models.
- Final focused RUL suite: 36 passed. Full suite: 165 passed, 2 failed because
  `data/raw/fuel_system/Scenario_Two.csv` line 8 contains a malformed numeric
  field. Fuel data were left untouched; source confirmation/repair is separate.

Details: `reports/RUL_PROTECTED_RETRAINING_20260913.md`. Overall completion remains
90%; no independently validated model improvement or aircraft readiness is claimed.

## Fitting-Only RUL Diagnostics - 2026-09-14

Completed grouped diagnostics on 60 fitting engines and 7 fitting batteries;
no calibration/audit/official test groups were scored and no models were changed.

- Engine: mean per-unit MAE is 34.12/19.47/5.21 cycles in early/middle/late
  thirds. The 175-cycle cap and limited earliest-cycle validation coverage
  warrant attention; these are diagnostic scores, not new test accuracy.
- Battery: all 327 labels match source reconstruction. B0042/B0043 reach the
  labeled EOL at a 22 C -> 4 C operating-condition transition. Capacity metadata
  and the EOL convention need source review before any justified label change.
- All 21 traced raw curves reproduce processed charge throughput. Retained
  candidates, all 11 serving artifacts, input files, and release pointer are unchanged.
- Diagnostic/protection tests: 21 passed. Full suite: 171 passed, 2 known
  fuel-data failures. Fuel remains outside this task and was not changed.

Details and next-step priorities: `reports/RUL_FITTING_DIAGNOSTICS_20260914.md`.
Overall implementation remains 90%; no predictive-performance improvement is claimed.

## Battery Source Review and Frozen Engine Protocol - 2026-09-15

- Confirmed that NASA Capacity is discharge capacity to 2.7 V, not full-discharge
  charge throughput. Sample-aligned integration reproduces all 21 inspected fitting
  capacities within 0.0000044 Ah. No label or feature was rewritten.
- CSV conversion provenance and the B0042/B0043 temperature-history interpretation
  remain unresolved; original MATLAB files are not present locally.
- Froze a versioned engine protocol covering all 12,440 cycles of 60 fitting
  engines, with equal unit/phase weighting and non-regression gates for each phase,
  worst-unit error, and near-failure behavior. No new model was trained or promoted.
- Tests: 17 new tests passed; full suite 188 passed, 2 known fuel-data failures.
  Protected best models and serving configuration remain unchanged.

Details: `reports/BATTERY_SOURCE_REVIEW_20260915.md` and
`docs/ENGINE_VALIDATION_PROTOCOL_V1.md`. Overall implementation remains 90%.

## Full-Trajectory Protected RUL Retraining - 2026-09-15

- Compared 12 configurations including two baselines under predeclared safeguards.
- Engine: all five challengers failed the frozen all-cycle fitting gate; retained
  audit MAE/RMSE 17.04/28.19 and official FD001 10.63/16.27 cycles.
- Battery: best challenger fitting MAE improved 7.3840 -> 7.3079, but RMSE
  worsened 8.7877 -> 9.1142; rejected. Retained audit remains 11.20/13.42.
- Original champions, all 11 serving artifacts, source inputs, and release pointer
  verified unchanged. Both selected baseline refits replay correctly.
- Focused safety suite: 38 passed; full suite: 194 passed, 2 known fuel-data
  failures. No model improvement or independent aircraft validation is claimed.

Details: `reports/RUL_PROTECTED_RETRAINING_V6_20260915.md`. Overall remains 90%.

## Fuel Label Verification

Public-source audit completed: normal/abnormal scenario membership is supported,
but exact CSV fault-onset rows and the time-axis mapping remain unverified.
The paper contains scenario descriptions; two source records list different
dataset DOIs, with archive equivalence unresolved. Labels and models are unchanged.
See `reports/FUEL_LABEL_VERIFICATION.md`; an author-request draft is prepared in
`docs/FUEL_DATA_AUTHOR_REQUEST.md` but has not been sent. Exact annotation
confirmation remains pending. Overall implementation estimate remains 90%.

## Fuel 90% Accuracy Target Experiment

Tested 36 causal temporal configurations with nested scenario-aware validation.
Accuracy was 51.93%, balanced accuracy 66.89%, and normal false alarms 8.19%.
The experiment was not promoted: the existing research release retains 68.64%
balanced development accuracy and 1.75% false alarms. Verified fault-onset labels
and additional independent runs are the next priority; above 90% is not achieved.
See `reports/FUEL_90_PERCENT_PLAN.md` for results and the data/validation plan.
Full regression check: 121 tests passed. Overall implementation estimate remains 90%.

## Engine Pipeline Completion: 90%

| Engine task | Status |
|---|---|
| Dataset extraction and inventory | Complete |
| Validated loader and data dictionary | Complete |
| RUL labeling and EDA | Complete |
| Grouped split, causal features, filtering, and scaling | Complete |
| Baseline model training and comparison | Complete: Random Forest selected |
| Test-set evaluation and error analysis | Complete on 100 official NASA test engines |
| Saved end-to-end prediction pipeline | Versioned research model and raw API adapter complete; calibration work remains |
| FastAPI/frontend connection | Complete in the backend-connected model workspace |

## Percentage Update Rule

After every completed project step, update this file and report:

1. Overall five-system completion.
2. The active subsystem's completion when applicable.
3. The evidence used to mark the step complete, such as tests, generated reports, or model metrics.
 
