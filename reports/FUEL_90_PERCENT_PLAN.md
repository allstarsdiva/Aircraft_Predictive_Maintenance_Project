# Fuel model: path toward above 90% accuracy

Date: 2026-09-10

## Outcome

Above 90% accuracy has **not** been achieved. A new 36-configuration temporal
experiment did not improve the existing model's balanced accuracy. It was not
deployed; release `research-fuel-20260910` remains unchanged. No labels were
changed and no difficult rows were removed.

| Metric | Existing nested development evaluation | New temporal experiment |
|---|---:|---:|
| Overall accuracy | 50.88% | 51.93% |
| Balanced accuracy | 68.64% | 66.89% |
| Abnormal-row detection | 39.04% | 41.96% |
| Normal-row false alarms | 1.75% | 8.19% |

These scores evaluate fold-specific model-selection procedures, not an
independent test of the exact final deployed artifact. The data have already
influenced earlier development. Neither score establishes real-aircraft readiness.

## What was tried

- Causal trailing means over 5, 9, and 15 sensor snapshots.
- Maximum standardized deviation and covariance-aware anomaly scores.
- With and without paired-sensor difference features.
- Normal-calibration threshold quantiles of 95%, 97.5%, and 99%.
- Normal-only fitting, separate normal-block threshold calibration, and inner
  selection excluding the outer test fault scenario and normal block.
- Four outer evaluations, each holding out a whole abnormal scenario and one
  normal block; every source row evaluated once. Comparison uses exactly the
  previous evaluation's row IDs and fold assignments.

The candidate grid was fixed before scoring outer folds. Selection used the
existing balanced-accuracy objective penalizing false alarms above 10%.
Nothing in this experiment writes model weights or changes the active release.
Longer averages can delay abrupt-fault alerts; the sampling interval and actual
fault-onset times are not available, so delay in seconds cannot be reported.

## Why accuracy alone is insufficient

There are 855 rows: 684 labelled abnormal and 171 labelled normal. Always
predicting abnormal would score 80% accuracy while falsely alerting on every
normal row. It is not a useful solution.

At this class balance:

`accuracy = 0.8 * abnormal_detection_rate + 0.2 * (1 - normal_false_alarm_rate)`

At 5% false alarms, 90% accuracy requires 88.75% abnormal detection; strictly
above 90% requires more than that. Current detection is 39.04%.

Suggested research acceptance targets, not aviation certification criteria:

- Overall accuracy strictly above 90% on a genuinely untouched test set.
- Balanced accuracy at least 90%, to prevent class prevalence hiding errors.
- Normal false-alarm rate at most 5%, with per-fault recall and uncertainty reported.
- Evaluate all eligible test rows, including uncertain predictions. If abstention
  is introduced, report coverage and full-set results beside accepted-only accuracy.

These targets are proposals for this project, not guarantees or published standards.

## Immediate priority: labels and independent runs

1. **Verify what each row means.** Request fault-onset and recovery annotations,
   fault type, severity, sample interval, and scenario-generation documentation
   from the dataset creators. Keep an annotation-source reference for each event.
   A file labelled abnormal does not prove every row already contains an active,
   observable fault. Do not infer labels from the model's own alert positions.
2. **Obtain additional independent runs.** Include repeated healthy runs and each
   relevant failure under varied initial tank levels, loads, valve schedules,
   temperatures, noise, and fault onset/severity. Repeated rows or noisy copies
   of the same five files are not independent runs. A practical pilot could seek
   20-30 healthy runs and 10-20 per verified fault type; these are planning numbers,
   not a statistically justified validation sample size or a promise of 90%.
3. **Record a run manifest.** For each source file retain `run_id`, `source_version`,
   `source_file`, `sha256`, `parent_run_id`, `operating_condition`, `sample_period_s`,
   `fault_type`, `fault_onset_sample`, `fault_end_sample`, `annotation_source`, and
   `split`. Unknown values must remain unknown. All derivatives of one parent run
   belong in the same split. Do not silently interpret unknown labels as healthy.
4. **Freeze a new evaluation split before development.** With sufficient runs,
   reserve whole runs for train, tuning, calibration, and final test. Fit scaling,
   imputation, feature selection, and models on training only; tune using validation;
   choose alert thresholds on calibration; open final test once. Keep entire runs
   and any derivatives together. Test unseen operating conditions separately.
5. **Retrain on the verified target.** Compare the existing anomaly detector with
   supervised tree models using raw sensors, causal changes, trailing statistics,
   and verified physical relationships. Use real labels for supervised training;
   do not use scenario IDs, file names, or future observations as predictor inputs.
   Sequence models should wait until there are enough independent sequences.
6. **Evaluate and promote only after passing the agreed checks.** Report confusion
   counts, ordinary and balanced accuracy, per-fault recall, normal false alarms,
   and uncertainty resampled at the independent-run level. Report fault-alert delay
   only against verified onset times. If a final test is used to guide more tuning,
   it becomes development data and a new final test is needed.

Do not fabricate a 90% result by switching to random-row splits, scoring only late
trajectory rows, selecting confident predictions without coverage, or testing on
training data. Synthetic training augmentation is acceptable if clearly labelled
and confined to training; it cannot substitute for independent validation.

## Error audit

For Scenarios One and Four, the existing model alerts on 0% of the first 114 rows
and 82.46% of the last 57 rows. The temporal experiment alerts on 87.72% of the last
57 rows of Scenario One and 92.98% of Scenario Four. These are descriptive slices
of inspected development predictions, **not** valid replacement headline scores.
They do not establish the true fault onset or prove early rows are healthy.

## Reproduction and evidence

Run from the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m src.fuel_target_experiment
```

The experiment expects the previous nested evaluation at
`reports/metrics/fuel_nested/outer_predictions.csv` and validates matching row/fold
identities. Rerunning overwrites only the experiment's own metric outputs.

- Experiment: `src/fuel_target_experiment.py`
- Leakage/causality tests: `tests/test_fuel_target_experiment.py`
- Machine-readable results: `reports/metrics/fuel_target_experiment/evaluation.json`
- Paired predictions: `reports/metrics/fuel_target_experiment/outer_predictions.csv`
- Existing active-release pointer: `models/releases/current.json`

Dataset provenance and the associated paper are linked by the creators in the
[University of York dataset record](https://pure.york.ac.uk/portal/en/datasets/aircraft-fuel-distribution-system/),
checked 2026-09-10. Local file counts and label limitations are documented in
`docs/data_dictionaries/FUEL_SYSTEM_AFDS.md`; the public record does not supply
row-level onset annotations.

Overall project implementation remains **90% estimated**. This is separate from
fuel accuracy and is not a measure of aircraft deployment readiness.
