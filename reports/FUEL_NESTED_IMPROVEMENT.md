# Fuel anomaly improvement - 2026-09-10

The robust steady-sensor envelope improves internal development evaluation and is
staged for the experimental fuel endpoint. It does not pass the readiness gate.

## Paired comparison

Both algorithms were refitted and evaluated on the same outer held-out rows.
Each outer fold holds out one entire failure scenario and one contiguous normal
block. The baseline uses the previous phase-template settings; the new method
selects its settings only inside the remaining normal blocks and fault scenarios.

| Metric | Phase-template baseline in this protocol | New selection pipeline |
|---|---:|---:|
| Accuracy | 42.92% | 50.88% |
| Balanced accuracy | 64.11% | 68.64% |
| Abnormal-sample detection | 28.80% | 39.04% |
| Normal false-alarm rate | 0.58% | 1.75% |
| Macro F1 | 42.87% | 50.21% |

Balanced accuracy improves by 4.53 percentage points and detection by 10.23 points.
The cost is a false-alarm increase of 1.17 points (one to three flagged normal rows
out of 171). The predeclared experimental promotion rule required over one point
of balanced-accuracy gain, false alarms no higher than 10%, and sensitivity no worse
than the paired baseline. The candidate meets that rule.

The earlier published phase-model values (61.99% balanced accuracy, 27.49% detection,
3.51% false alarms) used a different evaluation/aggregation protocol. Do not use those
as a like-for-like baseline for the new method.

## Algorithm

The selected final candidate uses FTF, FTV_S, FTT and CRTT, which are comparatively
steady in the available normal mission. Three-sample trailing median smoothing
reduces isolated sensor noise. Per-sensor median/MAD scaling and Ledoit-Wolf
shrinkage covariance produce a Mahalanobis anomaly score. A 99th-percentile score
threshold is fitted on a separate 43-row normal calibration block; the normal
distribution is fitted on the remaining 128 rows. The selected final candidate
uses no extra persistence beyond the causal smoothing.

Forty-eight candidate configurations compared max versus covariance scores,
one- versus three-sample smoothing, optional sensor-pair differences, three
threshold quantiles, and two persistence rules. The selected candidate does not
use the optional pair features. The other four sensor channels are not directly
modeled by this selected envelope, so it cannot cover every possible fuel fault.

Final artifact: `models/candidates/fuel_steady_envelope_bundle.joblib`.
Serving compatibility path in a new research snapshot:
`models/readiness/fuel_phase_residual_bundle.joblib`. Despite the legacy filename,
the returned model name is `robust_steady_sensor_envelope`.

## Scenario results from outer folds

| Held-out scenario | Abnormal-sample detection |
|---|---:|
| One | 27.49% |
| Two | 47.95% |
| Three | 53.22% |
| Four | 27.49% |

The new model improves detection mostly in scenarios two and three. The dataset
provides whole-scenario abnormal labels, not verified fault-onset times. Early
unflagged samples cannot be relabeled as healthy to inflate accuracy, and the first
alert is not a measured detection delay from a known fault onset.

## Evaluation boundaries

- All five source trajectories have influenced earlier development. This is nested
  internal evaluation, not newly unseen external validation.
- Inner normal validation blocks and fault scenarios exclude each outer test set.
  The model is fitted only on normal fitting rows; thresholds use a separate normal
  calibration block. Normal histories reset at gaps, preventing smoothing across
  held-out blocks. Each outer source row is evaluated exactly once.
- Outer fold scores evaluate the model-selection procedure. The final selected
  configuration is tuned on the available development scenarios and is not itself
  given a new independent final test.
- Final-artifact replay gives 69.66% balanced accuracy, 39.33% detection and zero
  alarms on the known normal mission. This includes normal fitting rows and is
  stored as **replay, not validation**. Use the outer-fold scorecard for reporting.
- There is still only one normal mission. Three false alarms among its correlated
  samples do not establish false-alarm performance across independent missions.

## Verification and activation

118 automated tests passed, including new tests for single-sensor faults,
prediction-prefix invariance, scenario/gap resets, invalid input, and inner-selection
independence from outer normal test values. The frontend build passed.

The experimental update is stored in a new verified research snapshot. Previous
snapshots remain available. The dashboard obtains performance from the backend
evidence endpoint rather than a hardcoded detection number. Fuel stays explicitly
experimental and readiness-v2 fuel prediction stays disabled.

```powershell
.\.venv\Scripts\python.exe -m src.improve_fuel
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe scripts\promote_fuel_candidate.py
.\.venv\Scripts\python.exe scripts\freeze_research_release.py your-new-research-release-id
```

`promote_fuel_candidate.py` verifies the artifact hash and improvement rule before
staging it. It refuses duplicate staging. The general `src.retrain_readiness`
command still reproduces the older baseline experiments; rerun the dedicated fuel
improvement/staging workflow before freezing a new release after a full retrain.

Machine-readable results, fold partitions, selected configurations, artifact hash,
and replay diagnostics: `reports/metrics/fuel_nested/evaluation.json`.
Per-row outer predictions: `reports/metrics/fuel_nested/outer_predictions.csv`.

Next evidence needed: multiple independent normal missions, additional failure
trajectories, and verified fault-onset labels. Sensitivity remains too low for final
fuel-model validation despite the measured improvement.
