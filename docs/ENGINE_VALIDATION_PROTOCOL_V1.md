# Engine RUL validation protocol v1

Frozen: 2026-09-15. Purpose: selecting future research candidates using fitting
data. This is not a production qualification, safety standard, or accuracy gain.

## Fixed evidence and coverage

The machine-readable protocol is
`reports/protocols/engine_full_trajectory_v1_20260915.json`, with a SHA-256 sidecar.
It pins the scorer implementation, retained baseline predictions, exact 60 fitting
engine IDs, and three grouped folds from the completed fitting-only diagnostic.
Every one of the 12,440 recorded fitting cycles must be included. No earliest
cycles, difficult units, unsupported predictions, or high-RUL rows may be omitted.

This replaces the five-checkpoint criterion for the planned next experiment, not
the results of historical experiments. Historical trainers remain unchanged; the
next trainer must explicitly use this validator and the frozen fold assignments.

## Weighting and score

Define diagnostic phase using `cycle / (cycle + true_RUL)`:

- Early: fraction <=1/3.
- Middle: fraction >1/3 and <=2/3.
- Late: fraction >2/3.

Phase is derived from validation labels for scoring only. It must never be a model
input or require knowledge of an engine's future lifetime at inference time.

Within each phase, compute MAE per engine and average equally over engines.
The primary score is the equal one-third average of those three phase scores.
RMSE uses the same per-engine-then-phase breakdown for guard checks. All stages
must be represented for every fitting engine.

| Retained baseline diagnostic | MAE, cycles | RMSE, cycles |
|---|---:|---:|
| Early phase, mean per engine | 34.12 | 36.41 |
| Middle phase, mean per engine | 19.47 | 22.30 |
| Late phase, mean per engine | 5.21 | 6.75 |
| All cycles, mean per engine | 19.56 | 25.93 |

Primary balanced-phase MAE: 19.599117 cycles. This is a fitting-only diagnostic
baseline, not a replacement for the existing outer audit MAE 17.04 or official
FD001 MAE 10.63. Different evaluation populations must not be mixed in comparison.

## Acceptance conditions

A candidate is eligible to proceed to outer checks only when all conditions hold:

1. Balanced-phase MAE improves by at least 1% over the frozen baseline.
2. All-cycle mean per-engine MAE/RMSE and worst-engine MAE do not worsen.
3. No phase's mean per-engine MAE or RMSE worsens.
4. For true RUL <=30, mean per-engine MAE and the per-engine-averaged rate of
   overestimation by more than 10 cycles do not worsen. This descriptive threshold
   is not an aircraft operational safety limit.
5. Predictions cover exactly the same unit/cycle keys and fold assignments.
   Missing/extra/duplicate rows, changed labels, and invalid predictions fail.

At inference, the model may not see labels or future samples. All feature
transformations and models must be fitted only on each fold's training units.
CSV checks cannot prove training lineage: the future training runner must record
and verify its inputs, feature definitions, group splits, and fitted artifacts.

Passing this inner gate does not authorize replacement. The existing fixed outer
audit, official FD001, and uncertainty non-regression checks still apply. Do not
relax those checks after seeing a candidate's results. Independent validation
remains necessary before any readiness claim.

## Usage

From the project root, using the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m src.engine_validation_protocol --candidate path\to\candidate_oof.csv
```

The CSV requires `unit`, `cycle`, `fold`, and `predicted`. If `actual` is supplied,
it must exactly match the frozen labels. Row order may differ, but coverage may not.
The command checks the protocol, scorer, and baseline hashes, then returns JSON.
Automation must inspect `eligible_for_outer_checks`; successful command execution
alone is not acceptance. No deployment or artifact replacement is performed.

The `--freeze` command has already been run and refuses to overwrite this version.
Changing its code or reference invalidates the saved checksums. A justified protocol
revision must be separately versioned and documented, not silently substituted.

Validation: self-comparison of the baseline correctly returns false for improvement.
New tests also cover missing rows, fold/label changes, stage regressions hidden by
average gains, invalid values, and harmless row-order/numeric-type differences.
No new engine model was trained or promoted in this step.
