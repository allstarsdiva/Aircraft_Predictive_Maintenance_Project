# Engine and battery RUL: third retraining round

Date: 2026-09-12. Scope: engine RUL and battery RUL only.

## Outcome

Neither new candidate improved the retained candidate on the fixed development
audit. Keep the second-round engine candidate and the original battery-history
candidate. No deployment changes were made. All attempted models and their
selection scores remain available; this unsuccessful replacement is not hidden.

Errors below are in cycles; lower is better. These are not accuracy percentages.

| Evaluation | Retained candidate MAE / RMSE | New candidate MAE / RMSE | Decision |
|---|---:|---:|---|
| Engine, fixed development audit | 17.04 / 28.19 | 17.86 / 28.72 | Keep retained candidate; targets <=15 / <=20 remain unmet |
| Engine, official NASA FD001 check | 10.63 / 16.27 | 11.52 / 16.93 | Both meet numerical benchmark targets; new candidate is worse |
| Battery RUL, fixed development audit | 11.20 / 13.42 | 11.29 / 13.79 | Keep retained candidate; MAE target <=10 remains unmet |

The previous round's rejected battery candidate scored MAE 12.78. This round
improves on that rejected attempt, not on the retained 11.20-cycle candidate.

## Training changes and selection

The grid was fixed before outer scoring. Only fitting groups were supplied to
the grid builder and model selector. Neither calibration groups, audit groups,
nor official engine labels were used to select configurations within this round.

- Engine: 10 configurations including the retained model specification. The
  other nine use histogram gradient boosting with 7/15/31 leaves, 300/450
  iterations, stronger regularization, learning rate 0.035, and training caps
  of 175, 225, or none. Existing causal sensor-history features are unchanged.
- Battery: 15 configurations including the retained model specification.
  Twelve support-vector regressors vary C and gamma across the existing history
  view and a compact physical/trend view. Two Extra Trees configurations vary
  leaf size with 350 trees and a 0.5 feature fraction.
- All preprocessing is fitted within the respective training fold. Unit IDs,
  observed EOL cycles, and target labels are not predictors. Evaluation labels
  are not capped or modified to improve the scores.
- Engine selection: three grouped folds within 60 fitting engines, five fixed
  checkpoints per validation trajectory, equal per-engine contribution.
- Battery selection: leave-one-battery-out within seven fitting batteries,
  equal per-battery contribution. One separate battery calibrates intervals;
  B0005 is the unchanged evaluation battery (125 rows).

The selected engine is `hist_leaf7_iter450_cap175.0`; the selected battery is
`extra_history_leaf3`. Their inner selection scores improved slightly, but the
fixed outer audit did not. Selection scores are not reported as test accuracy.

## Uncertainty and validation limits

| New candidate | Nominal interval coverage | Audit coverage | Mean interval width, cycles |
|---|---:|---:|---:|
| Engine | 95% | 85% | 95.77 |
| Battery RUL | 90% | 5.6% | 6.44 |

Engine official FD001 interval coverage is 99%, but its mean interval width is
95.35 cycles. Wide intervals and poor audit calibration remain concerns; higher
coverage on one benchmark is not sufficient evidence of useful uncertainty.
Battery calibration remains particularly unreliable with only one calibration
battery. No unsupported calibration fix or aircraft-readiness claim is made.

These datasets and audit results have been inspected in previous development.
Keeping groups disjoint within a run prevents within-run leakage, but repeated
development testing is not independent external validation. Retaining an earlier
candidate based on these comparisons does not change that limitation.

## Files and reproducibility

- Trainer: `src/rul_retraining_v3.py`, using the shared v2 training/evaluation code.
- Tests: `tests/test_rul_retraining_v3.py` and existing causal-feature tests.
- Outputs: `models/candidates/rul-retrain-v3-20260912/{engine,battery_rul}/`.
- Each task stores the selected model, exact audit inputs and predictions, and
  `evaluation.json` with the full grid results, group splits and integrity hashes.
- Engine additionally stores the official FD001 predictions.
- Retained engine: `models/candidates/rul-retrain-20260912/engine/`.
- Retained battery: `models/candidates/battery-history-20260911/battery_rul/`.

Run from the project root:

```powershell
.\.venv\Scripts\python.exe -m src.rul_retraining_v3 --replay
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Replay checks hashes and reproduces saved predictions and intervals; it is not
a new performance evaluation. Training refuses to overwrite completed tasks.

Verification completed:

- 140 automated tests passed in 26.36 seconds.
- Both new and both previous-round saved candidates replayed successfully.
- The active release passed integrity checks. All 11 serving artifacts and the
  release pointer were unchanged across training.
- Fuel, hydraulic, battery SOH, landing gear, raw/processed source files, and
  backend/frontend behavior were not modified by this experiment.

## Next step

Keep the better retained candidates. Before another broad search, use fitting-only
cross-validation errors to investigate early-life engine errors and battery-to-
battery differences. Freeze the next protocol and obtain additional independent
battery trajectories and engine validation evidence. Do not keep tuning against
the same outer audit or narrow its population simply to make numerical targets
pass. Calibration and serving-time history integration remain outstanding.

Overall project implementation remains 90% estimated, not aircraft readiness.
