# Protected RUL retraining - 2026-09-13

## Decision: keep the best previously retained candidates

Completed 17 configurations (10 battery, 7 engine). No challenger qualified for
replacement. The retained research models and every serving artifact are unchanged.
Protected, checksum-verified copies of both retained models and their evaluation
reports were made before training. Rejected experiments remain separately archived.

Errors are cycles; lower is better. RUL regression is not percentage accuracy.

| Evaluation | Retained MAE / RMSE | Selected in this experiment MAE / RMSE | Retention |
|---|---:|---:|---|
| Battery RUL fixed audit | 11.20 / 13.42 | 20.63 / 21.38 | Reject challenger; keep original battery-history model |
| Engine fixed audit | 17.04 / 28.19 | 17.04 / 28.19 | Prior specification won selection; keep original candidate |
| Engine official FD001 | 10.63 / 16.27 | 10.63 / 16.27 | Unchanged |

The retained engine meets the proposed official FD001 numerical benchmark target,
but not the broader audit MAE/RMSE targets. Battery MAE <=10 remains unmet.

## New protection mechanisms

- Before training, copy each retained model and evaluation report into this
  experiment's `champions/` directory. Pin source and snapshot SHA-256 hashes in
  `champions.json`; verify source models, snapshots, and reports afterward.
- Refuse to overwrite an existing experiment or champion snapshot.
- Preserve the active release pointer and all 11 serving artifacts, checking
  their hashes even if training raises an exception.
- Fit-only selection requires at least 1% lower mean per-unit MAE, no worse mean
  per-unit RMSE, and no worse maximum per-unit MAE. Otherwise select the baseline.
  This maximum-error guard does not imply every individual unit improves.
- A second, fail-closed research-retention gate requires at least 1% better audit
  MAE, no worse RMSE, no lower interval coverage, and no wider mean intervals.
  Engine official FD001 metrics must also not regress. Missing/nonfinite evidence
  is rejected. Selecting the baseline itself is not counted as an improvement.
- Gate decisions record the exact retained path and hash. No automatic serving
  deployment occurs, even if a future challenger passes the research gate.

These checks prevent replacement by a measured regression in this workflow.
They cannot guarantee performance on future aircraft or establish certification.

## Training conditions tested

Battery experiments compared global and condition-specific models. Soft condition
groups use observed ambient temperature, current, and discharge-end voltage; unit
identifiers are not predictors. Cluster centers, scaling, and expert weights are
learned within fitting folds only. Local experts are blended with the global
model at predeclared strengths to limit specialization. All rows remain in the
audit; no operating conditions or difficult predictions are removed from scoring.

Lifetime-residual models learn `RUL + observed_cycle` and subtract the current
observed cycle at prediction time. This is a training-target transformation, not
use of a test unit's final lifetime. The inverse cycle-scaling parameters come
only from each fitting fold. Regularized linear lifetime models were included
to allow extrapolation; tree-based lifetime models and direct/lifetime blends
were also tested. Engine comparisons included weighted and unweighted fitting.

Engine selection retained the same three grouped folds and five validation
checkpoints per trajectory. Battery used leave-one-battery-out within seven
fitting batteries. Calibration and audit groups were unchanged. The protocol
was written before training and not relaxed after seeing results.

The global lifetime battery model improved inner mean per-battery MAE from 7.38
to 6.08 and passed the fit-only checks. Its separate audit worsened to MAE 20.63,
RMSE 21.38, and interval coverage 3.2% versus the retained model's 6.4%. The outer
gate rejected it automatically. This is evidence that the retention safeguard
worked, not that battery generalization improved.

Repeated use of these datasets makes this a development comparison, not new
independent validation. Uncertainty remains inadequate, particularly with only
one battery used for calibration and one for evaluation.

## Files and commands

- Estimators: `src/rul_condition_methods.py`.
- Guarded trainer and retention gate: `src/rul_retraining_v5.py`.
- Tests: `tests/test_rul_protection.py`.
- Artifacts: `models/candidates/rul-protected-v5-20260913/`.
- Protected originals: the artifact directory's `champions/` subdirectory.
- Each task has an evaluation report, selected model, exact audit inputs and
  predictions; engine additionally has official predictions.

From the project root, show and verify the models actually retained:

```powershell
.\.venv\Scripts\python.exe -m src.rul_retraining_v5 --status
```

`--replay` instead reproduces this round's experimental predictions, including
the rejected battery model. It is a reproducibility check, not a command to
activate that model. The default trainer refuses to overwrite this completed run.

## Verification and separate fuel-data issue

- Pre-training focused checks: 19 passed after correcting an input-validation
  error-message ordering issue and an incorrect test fixture type.
- Final focused RUL suite: 36 passed in 7.95 seconds, including extrapolation,
  condition-model serialization, batch invariance, and anti-regression checks.
- Both experimental model replays matched saved predictions and intervals.
- Retained-model status and all protected model/report hashes verified.
- All 11 serving artifacts and the active release pointer were unchanged.
- Full project suite: 165 passed, 2 failed in 18.99 seconds. The suite is NOT green.

Both full-suite failures are fuel-loader tests. The current raw file
`data/raw/fuel_system/Scenario_Two.csv`, line 8, has the nonnumeric CLF field
`-0.009823072789679040.0731628363593168`, which appears to join two numeric values
without a delimiter. The source needs confirmation before repair; no value was
guessed and no fuel data/code/model was changed by this work. These failures are
outside the RUL experiment, not evidence of successful full-system validation.

## Remaining work

Keep the protected candidates. Additional independent battery trajectories
representing the intended operating conditions and lifetime range are needed to
evaluate generalization credibly. Freeze the next evaluation protocol before
using new data. Engine audit targets, calibration, and serving-time history-input
integration remain unresolved. Separately, confirm and repair the malformed fuel
source row before expecting a green full-project test run.

Overall project implementation remains 90% estimated; this is not aircraft readiness.
