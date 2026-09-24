# Targeted retraining results — 2026-09-11

## Outcome

Three of five requested model candidates now meet the proposed numerical targets
on both the fixed audit split and a separate grouped development cross-check.
Engine and battery RUL remain below the stricter audit targets. No deployed model
was replaced. Fuel, cooler, pump, and both landing-gear models were left unchanged.

| Task | Audit before | Candidate audit | Target | Result |
|---|---:|---:|---|---|
| Hydraulic valve | Balanced accuracy 75.57% | 100.00% | >=90% | Numerical target met |
| Hydraulic accumulator | Balanced accuracy 84.46% | 97.25% | >=90% | Numerical target met |
| Battery SOH | MAE 3.18 percentage points | 1.39 percentage points | <=3 | Numerical target met |
| Battery RUL | MAE 13.75 cycles | 11.20 cycles | <=10 | Improved, target not met |
| Engine RUL | MAE 25.40; RMSE 37.98 cycles | MAE 24.70; RMSE 37.88 | MAE <=15; RMSE <=20 | Improved slightly, target not met |

The before/after audit uses matching fitting, calibration, and evaluation group
assignments and unchanged labels. Candidates are selected using grouped CV inside
the fitting partition only. Calibration groups are not used to fit the prediction
model or select candidate configurations. Scores include all evaluation rows,
not just predictions accepted by the confidence/support guard.

All source datasets and this audit split have influenced prior development.
The phase-feature and history experiments are follow-up development, not a fresh
final holdout. No external aircraft-readiness claim is supported.

## Models and features

- Valve: shrinkage linear discriminant analysis on within-cycle pressure/flow/power
  variability and changes relative to the first second.
- Accumulator: Extra Trees classifier on one-second cycle-phase features.
- SOH: regularized histogram gradient boosting using existing discharge features.
- Battery RUL: Extra Trees with past-only discharge-history means, variability,
  fixed-lag slopes, and changes from the first available discharge.
- Engine: Extra Trees with the existing causal sensor features and a 125-cycle cap;
  uncapped Extra Trees and gradient boosting were also tested but did not win the
  predeclared inner-selection objective.

73 configurations were evaluated across the initial five-task comparison and two
follow-up experiments. Candidate choice was not made by maximizing outer audit
accuracy. Failed candidates and their evaluation records remain saved separately.

## Paired grouped cross-check of the three numerical passes

Fixed winning model specifications were compared with the previous specifications
on identical five-fold group splits. Each fold refits preprocessing and models.
This whole-dataset check reuses development data and is not nested selection or
independent validation. It measures the fixed specification, not an independently
tested final artifact trained on all data.

| Task | Previous | Candidate |
|---|---:|---:|
| Valve balanced accuracy | 83.94% | 100.00% |
| Accumulator balanced accuracy | 88.85% | 99.03% |
| Battery SOH MAE | 2.62 percentage points | 1.78 percentage points |

Evidence: `reports/metrics/targeted_retraining_20260911/paired_crosscheck.json`
and the adjacent paired OOF prediction CSVs.

## Why these are candidates, not a silent production replacement

1. **Hydraulic input compatibility:** the new classifiers require completed-cycle
   waveform features that cannot be reconstructed from existing whole-cycle
   averages. The original v2/dashboard input contract is unchanged. New features
   must be explicitly supplied by an extractor/integration step before promotion.
2. **Hydraulic support:** only 46.43% of valve and 43.21% of accumulator audit
   predictions pass the existing conservative confidence/range checks. Accepted
   accuracy is 100% and 98.35%, respectively. The full-set scores above do not
   hide those rejected cases. Do not weaken guards merely to inflate coverage.
3. **SOH calibration:** nominal 90% intervals cover 85.96% of audit rows, improved
   from 61.18% but still below nominal. Point-error success does not fix calibration.
4. **Battery RUL calibration:** history-model intervals cover only 6.4% against
   nominal 90%; the audit has just one calibration battery and one evaluation
   battery. The candidate must not replace the existing system based on MAE alone.
   The history candidate also needs an explicit multi-discharge input contract;
   a single current discharge does not supply its required history.
5. **Engine trade-off:** its candidate official FD001 check is MAE 14.44/RMSE 19.49,
   meeting that benchmark target but worse than the deployed 13.80/18.61. It uses
   fewer fitting engines, so this is not a like-for-like full-training comparison.

Four of the 20 engine audit snapshots have true RUL above 125. With a hard
125-cycle prediction ceiling, the lowest mathematically possible RMSE on those
20 labels is 30.12 cycles, even if every other prediction is perfect. The <=20
audit target therefore requires a different, successfully validated uncapped
formulation. Simply changing the ceiling did not produce that result here.
The original ground truth and audit metric have not been altered to force a pass.

## Files and reproducibility

Candidate artifacts, inner-selection scores, calibration details, split records,
checksums, and evaluation predictions are stored under:

- `models/candidates/targeted-20260911/` — initial five-task comparison.
- `models/candidates/hydraulic-phase-20260911/` — improved valve and accumulator.
- `models/candidates/battery-history-20260911/` — improved but below-target RUL.

Additional feature tables are component-specific and do not overwrite originals:

- `data/processed/hydraulic/cycle_temporal_features_v1.csv`
- `data/processed/battery/rul_history_features_v1.csv`

Hydraulic extraction generates 1,620 phase features from nine sensors. Full
60-second cycles are required; this is not an in-cycle early-warning claim.
Battery trends use current/past measurements, never future cycles, battery IDs
as predictors, SOH labels, observed EOL, or RUL labels as inputs. New feature
manifests record source hashes. Original battery/hydraulic processed tables were
checked against the active frozen release; they match.

Training entry points (existing run directories are protected from overwrite):

```powershell
.\.venv\Scripts\python.exe -m src.targeted_retraining --run-id new-unique-run
.\.venv\Scripts\python.exe -m src.hydraulic_temporal_retraining
.\.venv\Scripts\python.exe -m src.battery_history_retraining
.\.venv\Scripts\python.exe -m src.crosscheck_targeted
```

The waveform/history entry points use fixed versioned output names and refuse
to rerun over existing outputs; create a new explicit experiment version for
changes. Do not delete earlier results to hide unsuccessful experiments.

Try a saved candidate without changing the backend:

```powershell
.\.venv\Scripts\python.exe -m src.try_targeted_candidate --task hydraulic_valve
.\.venv\Scripts\python.exe -m src.try_targeted_candidate --task hydraulic_accumulator
.\.venv\Scripts\python.exe -m src.try_targeted_candidate --task battery_soh
.\.venv\Scripts\python.exe -m src.try_targeted_candidate --task battery_rul
.\.venv\Scripts\python.exe -m src.try_targeted_candidate --task engine
```

These commands execute the saved model on its audit inputs, check candidate and
extra-feature hashes, and print metrics plus sample predictions. This is replay,
not a fresh performance test.

## Verification and next steps

Final regression suite: **131 tests passed**. All five saved candidate replay
checks match their recorded audit metrics. All 11 working serving artifacts and
the frozen active release passed hash checks and remain unchanged.

CSV round-trip precision was corrected after a tiny parsing difference changed
one hydraulic support decision; exact feature recovery is now regression-tested.

New tests cover authorized scope, full-set target definitions, immutable targets,
fitting/calibration/evaluation isolation, waveform row independence, complete-cycle
input validation, battery-history reset, and prefix invariance. A short-history
window bug was caught and corrected before history-model training.

Next: validate calibration across additional independent batteries; design and
test hydraulic completed-waveform inputs and support handling; investigate an
engine formulation that generalizes across early-life and near-failure conditions.
Any final promotion must include compatible inputs, calibrated uncertainty, honest
evidence updates, and regression tests while preserving the excluded models.

Implementation progress remains 90% estimated: model development advanced, but
input integration, calibration, and independent validation are still outstanding.
