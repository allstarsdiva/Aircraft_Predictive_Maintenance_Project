# Full-trajectory protected RUL retraining - 2026-09-15

## Outcome

Trained and compared 12 configurations including two retained baselines. No new
challenger passed the predeclared fitting-only safety checks. Both original best
research candidates remain retained; neither they nor any serving model changed.
The selected baseline specifications were refitted and their audit predictions
reproduced. This run establishes no predictive-performance improvement.

RUL errors are in cycles, not percentage accuracy. Lower is better.

| Evaluation | Best before MAE / RMSE | Retained after MAE / RMSE |
|---|---:|---:|
| Engine fixed development audit | 17.04 / 28.19 | 17.04 / 28.19 |
| Engine official FD001 | 10.63 / 16.27 | 10.63 / 16.27 |
| Battery RUL fixed development audit | 11.20 / 13.42 | 11.20 / 13.42 |

## Engine experiment

Used the frozen full-trajectory protocol in `docs/ENGINE_VALIDATION_PROTOCOL_V1.md`.
All 12,440 cycles of 60 fitting engines were scored out of fold, with exactly the
frozen three unit-grouped splits. Retraining the baseline reproduced the frozen
OOF predictions. True lifetime defines evaluation phases only, never predictors.

Preserved the best engine's observed features and other estimator settings.
Compared target caps 200, 225, and no cap, plus smaller seven-leaf trees with
stronger regularization at caps 200 and 225. Baseline cap remains 175.

| Configuration | Fitting OOF balanced-phase MAE | Pass fitting gate? |
|---|---:|---|
| Retained baseline | 19.5991 | Baseline fallback |
| Cap 200, 15 leaves, L2 5 | 19.7824 | No |
| Cap 225, 15 leaves, L2 5 | 20.4097 | No |
| No cap, 15 leaves, L2 5 | 21.4014 | No |
| Cap 200, 7 leaves, L2 15 | 20.0912 | No |
| Cap 225, 7 leaves, L2 15 | 20.8102 | No |

These OOF scores are fitting-only selection evidence, not the fixed-audit or
official-test scores in the first table. Failed challengers were not evaluated
against outer/official labels. No post-result search expansion was performed.

## Battery experiment

Kept the retained causal-history features, original labels, and fixed fitting,
calibration, and audit groups. No source capacity or temperature values changed.
Compared three 400-tree Extra Trees configurations and two 400-tree Random
Forests using a fixed seed, varying leaf size and feature subsampling.

Leave-one-battery-out selection on the seven fitting batteries required >=1%
lower mean per-battery MAE, no higher mean RMSE, and no higher worst-battery MAE.

| Configuration | Fitting macro MAE | Fitting macro RMSE | Result |
|---|---:|---:|---|
| Retained baseline | 7.3840 | 8.7877 | Retain |
| Extra Trees, leaf 2, features 0.5 | 7.3708 | 8.5546 | Gain below 1% |
| Extra Trees, leaf 3, features 0.6 | 7.4227 | 8.9470 | MAE/RMSE worse |
| Extra Trees, leaf 5, features 0.8 | 7.3079 | 9.1142 | RMSE worse despite MAE gain |
| Random Forest, leaf 2, features 0.6 | 7.9937 | 9.9150 | MAE/RMSE worse |
| Random Forest, leaf 4, features 0.8 | 7.8561 | 10.1171 | MAE/RMSE worse |

## Protection and verification

- Wrote the bounded search specification before training; saved checksum-verified
  copies of both champions and their evaluation reports in this experiment.
- Engine selection enforces all-phase, overall, worst-unit, and near-failure
  no-regression checks. A 1% balanced-phase MAE gain is also required.
- The existing outer research-retention gate additionally requires >=1% audit
  MAE gain and no regression in audit/official errors or interval quality.
- Verified all protected source hashes, champion originals/copies, all 11 serving
  artifacts, and the active release pointer after training. No automatic deployment.
- Both saved candidates replay their audit predictions and intervals correctly.
- Focused safety suite: 38 passed. Full suite: 194 passed, 2 known fuel failures.
  The two failures are caused by the existing malformed CLF field in
  `data/raw/fuel_system/Scenario_Two.csv` line 8. Fuel was not changed.

Artifacts: `models/candidates/rul-protected-v6-20260915/` (protocol, protected
champions, complete engine OOF predictions/checks, both evaluations, completion).
Implementation: `src/rul_retraining_v6.py`; tests: `tests/test_rul_retraining_v6.py`.

From the project root:

```powershell
.\.venv\Scripts\python.exe -m src.rul_retraining_v6 --status
.\.venv\Scripts\python.exe -m src.rul_retraining_v6 --replay
```

The training command without flags refuses to overwrite this completed run.

## Limitations and next steps

Protection means no measured regression replaces the best model in this workflow,
not guaranteed performance on future aircraft. Previously inspected audit/official
sets remain development evidence, not fresh independent validation. Battery audit
interval coverage remains only 6.4% at nominal 90%; uncertainty is unresolved.

Retain both best models. Next substantive battery experiment should use a
separately versioned causal 2.7 V cutoff-capacity feature after source verification,
without changing labels or mixing full-discharge throughput with source capacity.
Independent operating-condition/lifetime trajectories remain important. For engine,
evaluate a separately predeclared causal degradation representation under the same
frozen gate; do not relax thresholds to force acceptance.

Overall project implementation remains 90%; no aircraft readiness is claimed.
