# Stronger RUL methods: controlled experiment

Date: 2026-09-12. Scope: engine RUL and battery RUL only.

## Outcome and retention decision

Implemented and compared new methods, but did not establish an improvement on
the unchanged audit. Keep the previously retained engine and battery candidates;
no serving model or release pointer was replaced.

All errors below are cycles, not accuracy percentages. Lower is better.

| Evaluation | Retained MAE / RMSE | Selected in this round MAE / RMSE | Outcome |
|---|---:|---:|---|
| Engine, fixed development audit | 17.04 / 28.19 | 17.04 / 28.19 | Baseline specification won selection; unchanged |
| Engine, official FD001 check | 10.63 / 16.27 | 10.63 / 16.27 | Unchanged; meets numerical benchmark targets only |
| Battery RUL, fixed development audit | 11.20 / 13.42 | 13.57 / 17.32 | New candidate is worse; do not replace retained model |

The broader engine targets (MAE <=15, RMSE <=20) and battery MAE target (<=10)
remain unmet. The official FD001 numerical result does not establish aircraft
readiness or compensate for a failed broader audit.

## Fitting-only investigation

The seven battery fitting groups contain 10 to 109 rows. Without weighting,
B0006 supplies 33.3% of fitting rows, while B0047 supplies 3.1%. Fitting batteries
also differ in ambient temperature (4, 22, 24 degrees C), current, and discharge
endpoint. A very low isolated throughput measurement appears in B0043. These
observations motivated robust features and group-balanced fitting, not deletion
of difficult evaluation rows.

Earlier fitting-only engine fold scores show much larger errors for some units
than others. This motivated a different boosting algorithm and fixed ensembles.
Machine-readable fitting diagnostics are saved with this experiment. They use
no calibration or evaluation rows.

## Methods actually tested

The predeclared grid contained 11 configurations per task, 22 total, including
the retained specification for each task. New candidates used:

1. XGBoost regression with regularization, row/column subsampling, and shallow
   trees. This is a new learner in these RUL experiments, not another seed-only
   rerun of the previous histogram boosting grid.
2. Equal total fitting weight per battery/engine. The weight for each row is
   inverse group size, normalized to mean one. The same weights are applied to
   standardization and model fitting. Unit IDs route weights but are never
   predictors. An unweighted engine XGBoost configuration is also included.
3. Robust, causal battery features: trailing five-discharge capacity medians,
   seven-discharge median absolute deviation, initial-relative capacity, and
   median pairwise slopes over the preceding 7/21 discharges. Life proxies use
   the source-documented EOL threshold, a decline flag, and a bounded sentinel
   when extrapolation is not meaningful. Raw measurements and labels are retained.
4. A log1p RUL target option for battery models; predictions are inverted to
   cycles before scoring. This changes training loss, not evaluation labels.
5. Fixed 50/50 ensembles: XGBoost with histogram gradient boosting for engine,
   or with Extra Trees for battery. Ensemble weights were fixed before scoring,
   not fitted against audit or official benchmark results.

Engine caps of 175, 225, and none were compared; battery had full-history and
compact operating-condition/robust-feature views. Existing preprocessing and
past-only engine features were retained. The experiment does not add deep
sequence models or claim that greater algorithm complexity guarantees improvement.

Implementation references: [XGBoost parameter documentation](https://xgboost.readthedocs.io/en/stable/parameter.html?highlight=gblinear)
and [XGBoost sample-weight API](https://xgboost.readthedocs.io/en/release_3.1.0/python/python_api.html).
The installed and tested version is pinned separately to 3.0.5; the API reference
is supporting documentation, not a claim that this project uses version 3.1.

## Selection and honest generalization check

Engine selection used three grouped folds within the 60 fitting engines, with
five fixed checkpoints per validation trajectory. Battery selection used
leave-one-battery-out within seven fitting batteries. Validation loss gives each
unit equal influence. Separate calibration and audit groups were unchanged.

The battery winner, `balanced_compact_xgb_depth2_logTrue`, reduced fitting-only
mean per-battery validation MAE from 7.38 to 5.64. Its errors improved on five of
seven fitting validation batteries, but worsened on B0006 and B0048. The separate
B0005 audit MAE worsened to 13.57. Thus the fitting-only gain did not transfer to
this held-out battery and is not presented as an accuracy improvement.

For engine, the previous specification had the lowest selection loss. It was
refitted on the same fitting units and reproduced the previous audit and official
results. No alternative engine was substituted using outer scores.

All datasets and outer results have been inspected during earlier development.
Disjoint groups prevent within-run leakage, not accumulated development-set
overfitting. This is not fresh external validation. Selecting an earlier candidate
for retention also does not make the old audit an independent final test.

## Uncertainty remains unresolved

| Selected candidate | Nominal interval coverage | Audit coverage | Mean audit width, cycles |
|---|---:|---:|---:|
| Engine baseline refit | 95% | 90% | 91.10 |
| New battery candidate | 90% | 31.2% | 13.14 |

Battery coverage increased from the retained model's 6.4%, but remains far below
90% and comes with wider intervals and worse point errors. It is not a successful
calibration fix. Only one independent calibration battery and one evaluation
battery are available in this split; 125 rows are not 125 independent batteries.

## Files, environment, and verification

- Methods/features: `src/rul_methods.py`.
- Experiment runner: `src/rul_retraining_v4.py`; shared runner hooks in
  `src/rul_retraining_v2.py` preserve earlier defaults.
- Tests: `tests/test_rul_methods.py` plus existing RUL and project tests.
- Dependency pin: `requirements-rul-experiments.txt` (`xgboost==3.0.5`).
- Outputs: `models/candidates/rul-methods-v4-20260912/`.
- Each task stores `candidate.joblib`, `evaluation.json`, exact audit inputs,
  predictions, intervals, group splits, complete inner scores, and hashes.
- Engine also stores official FD001 predictions. The experiment root stores
  fitting-only diagnostic files.

Runtime: Python 3.14.7, NumPy 2.5.2, pandas 3.0.5, scikit-learn 1.9.0,
XGBoost 3.0.5. No new models were connected to backend/frontend inference.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-rul-experiments.txt
.\.venv\Scripts\python.exe -m src.rul_retraining_v4 --replay
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Replay reproduces existing predictions, not a new test. The training command
without `--replay` refuses to overwrite completed tasks.

Verification: 21 focused tests passed before training; the full suite passed
152 tests in 27.82 seconds. Both new candidates and both second-round candidates
replayed successfully. All 11 serving artifacts and the active release pointer
were unchanged across training; the frozen release passed integrity validation.
Raw/processed data, fuel, hydraulic, battery SOH, and landing gear were untouched.

## Next useful step

Keep the current stronger candidates. Before another search, obtain additional
independent battery runs representing the intended temperature/current and life
range, and define a fresh engine evaluation protocol that includes early-life
trajectories. Investigate unit/regime generalization using fitting-only checks;
freeze model selection before looking at new evaluation results. Repeatedly
trying algorithms on the same small audit cannot establish reliable improvement.

Overall implementation remains 90% estimated; no aircraft-readiness claim.
