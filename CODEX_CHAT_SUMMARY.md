# Codex Chat and Project Implementation Summary

## Purpose of This File

This document summarizes the requirements, decisions, implementation work,
commands, results, errors, fixes, and next steps discussed during the project
conversation. Paths are repository-relative, and no credentials, secrets, or
user-specific filesystem paths are included.

## User Requirements

The user requested a step-by-step implementation of an aircraft predictive
maintenance project, including:

- Define what constitutes 50% and 100% project completion.
- Create Markdown roadmaps for those milestones.
- Build the project directory and environment incrementally.
- Use these confirmed aircraft systems and datasets:
  - Engine: NASA C-MAPSS for degradation and RUL prediction.
  - Electrical/battery: NASA PCoE Li-Ion data for SOH and RUL prediction.
  - Hydraulic: UCI Hydraulic Systems for condition/fault classification.
  - Fuel system: Aircraft Fuel Distribution System data for normal/abnormal detection.
  - Landing gear: Aircraft Landing Gear Digital Twin data for fault classification and RUL prediction.
- Exclude avionics and flight-operation anomaly prediction from the project.
- Use the extracted datasets already placed under `data/raw/`.
- Review the supplied React frontend and connect it to the project later.
- Store processed data in component-specific directories.
- Proceed one roadmap step at a time whenever the user says `next`.
- Report the overall project completion percentage after every completed step.
- When reporting progress conversationally, provide only the overall percentage,
  not a separate percentage for each subsystem.
- Preserve safety limitations: predictions are experimental decision support,
  not certified aircraft maintenance decisions.

## Major Scope and Design Decisions

### Confirmed scope

The project contains five active subsystems: engine, battery, hydraulic, fuel
system, and landing gear. Avionics is explicitly excluded from the confirmed
scope.

### Data organization

Raw files remain unchanged under component directories in `data/raw/`.
Generated data is stored under:

```text
data/processed/
├── engine/
├── battery/
├── hydraulic/
├── fuel_system/
└── landing_gear/
```

`data/processed/manifest.json` records processed file dimensions, descriptions,
sizes, and SHA-256 hashes.

### Leakage prevention

Different datasets require different validation controls:

- Engine records are split by complete engine ID.
- Battery records are split by complete battery ID.
- Battery RUL uses leave-one-battery-out validation.
- Hydraulic validation holds out complete four-component condition combinations.
- Fuel-system rolling features reset at scenario boundaries.
- Random row splitting is prohibited for the fuel dataset because it has only
  one normal trajectory and four abnormal trajectories.

### Model selection

Algorithms are selected separately for each target. There is no assumption that
one algorithm is best for all aircraft subsystems.

### Frontend decision

The supplied React dashboard was reviewed. It currently uses simulated/random
values. It will be connected later through the FastAPI backend after the
remaining prediction endpoints are implemented.

## Project Setup Completed

The repository now includes:

- Python virtual environment in `.venv/`.
- Dependency list in `requirements.txt`.
- Source, test, model, report, notebook, API, raw-data, and processed-data directories.
- `.gitignore` and initialized Git repository.
- `PROJECT_ROADMAP.md`, `PROJECT_PROGRESS.md`, and project-definition documentation.

Primary technologies include pandas, NumPy, scikit-learn, Matplotlib, joblib,
FastAPI, React, pytest, and optional SHAP/XGBoost support.

## Engine Implementation

### Completed work

- Implemented a validated NASA C-MAPSS loader in `src/data/cmapss.py`.
- Documented columns in `docs/data_dictionaries/ENGINE_CMAPSS.md`.
- Added RUL labels and a 125-cycle capped training target.
- Completed FD001 EDA and saved figures.
- Added causal sensor changes, rolling means, and rolling deviations.
- Removed zero-variance features using training-fitted preprocessing.
- Standardized retained features without fitting on validation engines.
- Compared median, Linear Regression, and Random Forest baselines.
- Tuned Random Forest variants with engine-grouped cross-validation.
- Evaluated the model on the official NASA FD001 test set of 100 unseen engines.
- Saved reusable engine model bundles.
- Implemented engine prediction, health, validation, and model-metadata support
  through FastAPI.

### Main engine result

- Selected family: tuned Random Forest.
- Official unseen-test MAE: 13.91 cycles.
- Official unseen-test RMSE: 18.71 cycles.
- Official unseen-test R-squared: 0.797.
- Safety calibration reduced the grouped near-failure late-prediction rate from
  approximately 72% to 35.3%.

### Important limitation

The engine model is based on simulated C-MAPSS data and is not a certified
aircraft prognostics system.

## Battery Implementation

### Dataset validation and preprocessing

- Implemented metadata and measurement loading in `src/data/battery.py`.
- Validated 7,565 referenced measurement files.
- Safely parsed charge, discharge, and complex impedance measurements.
- Normalized scientific timestamp formats and cleaned missing placeholders.
- Created a chronological discharge-cycle table.
- Defined SOH relative to the documented 2.0 Ah rated capacity.
- Distinguished observed EOL, right-censored, left-censored/starts-below-threshold,
  and undocumented-threshold batteries.
- Extracted 21 discharge-curve features, including voltage, current,
  temperature, load, duration, charge throughput, and energy.

### Battery SOH model

Algorithms compared:

- Median reference.
- Linear Regression.
- Random Forest.

Selected model and validation results:

- Selected model: Linear Regression.
- Validation split: seven complete batteries held out.
- MAE: 3.985 percentage points SOH.
- RMSE: 10.627 percentage points SOH.
- R-squared: 0.887.

The model is very accurate for ordinary SOH values but has substantially larger
errors on anomalously low-SOH records, especially battery B0042. Its full
discharge-curve inputs mean it is a post-discharge estimate, not a live
mid-flight SOH estimate.

### Experimental battery RUL model

Only nine batteries and 493 eligible pre-EOL cycles provide direct RUL labels.
The experiment therefore uses leave-one-battery-out validation and an empirical
uncertainty interval.

Algorithms compared:

- Median reference.
- Ridge Regression.
- Random Forest.

Selected result:

- Selected model: Random Forest.
- MAE: 9.32 cycles.
- RMSE: 12.28 cycles.
- R-squared: 0.863.
- Macro battery RMSE: 9.55 cycles.
- Empirical 90% error radius: approximately 18.55 cycles.
- Empirical out-of-fold interval coverage: approximately 90.26%.

The interval is based on only nine independent observed-EOL trajectories and is
not a certified coverage guarantee.

## Hydraulic Implementation

### Validation and preprocessing

- Implemented `src/data/hydraulic.py` and `src/preprocess_hydraulic.py`.
- Validated all 17 sensor matrices.
- Confirmed 2,205 aligned 60-second operating cycles.
- Validated 1 Hz, 10 Hz, and 100 Hz sensor sample dimensions.
- Confirmed zero missing and non-finite raw values.
- Preserved four component-condition targets plus the stability flag.
- Extracted mean, standard deviation, minimum, maximum, range, RMS, and
  normalized-time slope for every sensor.
- Created 119 model features and a 125-column processed table.

### EDA findings

- No missing or duplicate processed feature rows were found.
- Three constant features were identified and removed by the training-fitted
  variance filter.
- Cooler condition is strongly associated with temperature, cooling, flow, and
  motor-power features.
- Pump leakage is strongly associated with efficiency and flow features.
- Valve behavior is most associated with within-cycle slopes.
- Accumulator condition has weaker univariate separation and is the harder target.

### Hydraulic model comparison

Training uses 1,449 stable cycles. Five-fold validation groups all cycles with
the same cooler/valve/pump/accumulator condition combination, producing 144
independent condition groups.

Algorithms compared:

- Most-frequent reference.
- Logistic Regression.
- Random Forest.
- Extra Trees.

Selected models:

| Target | Selected algorithm | Macro F1 |
|---|---|---:|
| Cooler condition | Logistic Regression | 1.000 |
| Valve condition | Logistic Regression | 0.839 |
| Pump leakage | Extra Trees | 0.991 |
| Accumulator pressure | Random Forest | 0.886 |

The perfect cooler result reflects strong separation in a controlled test-rig
dataset and must not be presented as perfect real-aircraft performance.

The 756 potentially unstable cycles were evaluated only as a descriptive
stress test. Valve and accumulator performance declined substantially, which
supports adding an unstable-condition warning or abstention behavior later.

## Fuel-System Implementation

### Provenance decision

Public records confirmed:

- Dataset DOI: `10.21227/15gk-s444`.
- Reference paper DOI: `10.1109/ACCESS.2019.2941566`.
- Kaggle distribution license: CC BY-SA 4.0.
- The data is hypothetical and illustrative rather than operational fleet telemetry.
- The dataset contains one normal and four abnormal scenarios.

The public dataset description and extracted files do not map Scenarios
One-Four to authoritative individual fault names. The project therefore retains
neutral scenario IDs and does not invent valve, tank, pump, or sensor fault names.

### Validation and preprocessing

- Implemented `src/data/fuel_system.py` and `src/preprocess_fuel.py`.
- Validated five CSVs with 171 rows each, for 855 rows total.
- Validated eight shared numeric sensor columns.
- Confirmed zero missing, non-finite, and duplicate sensor rows.
- Preserved an ordered sample index inside each scenario.
- Defined `is_abnormal = 0` only for the normal file and `1` for the four
  authoritatively abnormal files.
- Added one-step changes, five-row trailing means, and five-row trailing
  standard deviations for every sensor.
- Ensured causal rolling calculations reset at scenario boundaries.
- Created 32 model features and a 36-column processed table.

### Fuel modeling limitation

There is only one normal trajectory. Randomly splitting its rows would allow
nearby observations from the same trajectory to appear in training and testing,
creating misleading performance. The next experiment should use a normal-only
anomaly detector and scenario-aware temporal evaluation, with results described
as within-dataset evidence only.

## Current Processed Data

| Component | Processed file | Rows | Columns |
|---|---|---:|---:|
| Engine | `data/processed/engine/fd001_labeled_features.csv` | 20,631 | 52 |
| Engine | `data/processed/engine/fd001_unit_split.csv` | 100 | 2 |
| Battery | `data/processed/battery/discharge_cycles.csv` | 2,794 | 17 |
| Battery | `data/processed/battery/soh_features.csv` | 2,750 | 26 |
| Battery | `data/processed/battery/rul_features.csv` | 493 | 28 |
| Hydraulic | `data/processed/hydraulic/cycle_features.csv` | 2,205 | 125 |
| Fuel system | `data/processed/fuel_system/scenario_features.csv` | 855 | 36 |

Landing-gear processing had not started at this stage. Avionics is excluded.

## Saved Model Artifacts

Models are stored under component directories:

```text
models/
├── engine/
├── battery/
│   ├── soh_baseline_bundle.joblib
│   └── rul_experimental_bundle.joblib
└── hydraulic/
    ├── cooler_condition_percent_bundle.joblib
    ├── valve_condition_percent_bundle.joblib
    ├── pump_leakage_severity_bundle.joblib
    └── accumulator_pressure_bar_bundle.joblib
```

Fuel-system and landing-gear model bundles have not yet been created.

## Important Reports and Documentation

- `PROJECT_ROADMAP.md`: 50% and 100% milestones and task checklists.
- `PROJECT_PROGRESS.md`: weighted overall project progress.
- `docs/PROJECT_DEFINITION.md`: scope, users, targets, and success criteria.
- `docs/PROCESSED_DATA_LAYOUT.md`: processed directory layout.
- `docs/DATA_INVENTORY.md`: raw dataset inventory and provenance gaps.
- `reports/ENGINE_FD001_OFFICIAL_TEST.md`: official engine-test evaluation.
- `reports/BATTERY_SOH_BASELINE_MODELS.md`: battery SOH results.
- `reports/BATTERY_RUL_EXPERIMENT.md`: experimental battery RUL results.
- `reports/HYDRAULIC_DATA_VALIDATION.md`: hydraulic schema validation.
- `reports/HYDRAULIC_EDA_AND_BASELINES.md`: hydraulic EDA and model comparison.
- `reports/FUEL_SYSTEM_DATA_VALIDATION.md`: fuel validation and limitations.

## Commands Used for Reproduction

Commands were run from the repository root using the local virtual environment.

### Run all tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Latest verified result: 53 tests passed.

### Rebuild the processed-data manifest

```powershell
.\.venv\Scripts\python.exe scripts\export_processed_data.py
```

### Train or evaluate implemented pipelines

```powershell
.\.venv\Scripts\python.exe -m src.train
.\.venv\Scripts\python.exe -m src.evaluate
.\.venv\Scripts\python.exe -m src.tune
.\.venv\Scripts\python.exe -m src.train_battery
.\.venv\Scripts\python.exe -m src.train_battery_rul
.\.venv\Scripts\python.exe -m src.preprocess_hydraulic
.\.venv\Scripts\python.exe -m src.eda_hydraulic
.\.venv\Scripts\python.exe -m src.train_hydraulic
.\.venv\Scripts\python.exe -m src.preprocess_fuel
```

### Start the FastAPI backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api.app:app
```

## Errors, Warnings, and Solutions

### Patch context failure in a Markdown tree

An `apply_patch` operation failed because the expected box-drawing characters
in `docs/PROCESSED_DATA_LAYOUT.md` were encoded differently from the visible
terminal output. The fix was to patch stable table lines separately instead of
matching the corrupted tree characters.

### Patch context mismatch in progress tracking

A later documentation patch expected an older progress heading while the file
contained an inconsistent newer heading and older weighted total. The update
was split into smaller patches and both the heading and weighted total were
reconciled to 51%.

### Inline Python syntax error

A long PowerShell one-line Python inspection command had an unclosed
parenthesis. It was replaced with a simpler command that loaded and summarized
the fuel CSVs without nested conditional expressions.

### Long hydraulic preprocessing job

The full hydraulic preprocessing command exceeded the initial command-yield
window because it scans several large 100 Hz matrices. The existing process was
polled until completion rather than restarted. It successfully generated all
2,205 rows and 119 features.

### Constant-input correlation warning

Hydraulic EDA initially emitted a constant-input Spearman warning. The solution
was to exclude constant stable-cycle columns from correlation calculations;
the training pipeline already removes them with `VarianceThreshold`.

### Unstable-cycle classification warning

Scikit-learn warned that some predictions on potentially unstable hydraulic
cycles included classes absent from that descriptive subset. Those results were
explicitly marked as non-validation diagnostics and were not used for model
selection.

### IEEE DataPort access restriction

Direct automated access to IEEE DataPort was blocked by site rules. Provenance
was instead cross-checked through the public University of York dataset record,
the Kaggle dataset page, the DOI record, and the open reference paper.

### Transient command-helper failure

A final read-only workspace inspection command encountered a process-helper
setup error. No files were changed by that failed command; summary creation
continued using the already verified project state.

## Progress History

Recorded overall progress increased as follows:

- 38% after engine completion and battery SOH baseline work.
- 40% after the experimental battery RUL pipeline.
- 43% after hydraulic validation and preprocessing.
- 48% after hydraulic EDA and grouped model comparison.
- 51% after fuel-system provenance, validation, and preprocessing.

Current weighted overall project completion: **51%**.

## Immediate Next Step

Perform fuel-system EDA and implement a scenario-aware anomaly-detection
baseline. The recommended initial approach is:

1. Analyze sensor trajectories and the onset/structure of each neutral abnormal scenario.
2. Define blocked temporal evaluation that does not randomly mix neighboring rows.
3. Fit preprocessing only on the training portion of normal data.
4. Compare a simple statistical-distance baseline with Isolation Forest and,
   if justified, One-Class SVM.
5. Calibrate the alert threshold using held-out normal blocks.
6. Report normal false-alarm rate and abnormal detection rate separately for
   Scenarios One-Four.
7. Save the model, threshold, predictions, figures, report, and automated tests.
8. Clearly state that results cannot demonstrate new-trajectory generalization
   because only one normal source trajectory exists.

## Later Next Steps

After the fuel anomaly experiment:

1. Confirm landing-gear source provenance, units, and fault-code meanings.
2. Validate and preprocess landing-gear data.
3. Train landing-gear fault-classification and RUL baselines.
4. Add battery, hydraulic, fuel, and landing-gear FastAPI endpoints.
5. Replace simulated React data with real API responses.
6. Add feature importance and understandable prediction explanations.
7. Add unstable-input warnings, confidence/uncertainty displays, and safe
   abstention behavior where appropriate.
8. Complete end-to-end frontend/API/model tests.
9. Finish the README, architecture diagram, screenshots, presentation, and final demonstration.

## Review-Panel Presentation Guidance Already Provided

The suggested review presentation emphasizes:

- The predictive-maintenance problem and five-system scope.
- The end-to-end raw-data-to-model architecture.
- Leakage-safe validation decisions.
- Engine, battery, and hydraulic results.
- Saved model artifacts and passing automated tests.
- Honest limitations, especially simulated/test-rig data, battery RUL sample
  size, unstable hydraulic states, and the unconnected frontend.
- A short live demonstration of tests, reports, processed data, and the engine API.

The project should be presented as a working research prototype at 51%
completion, not as a certified or deployment-ready aircraft maintenance system.
