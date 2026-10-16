# Aircraft Predictive Maintenance Project - Implementation Summary

**Updated:** 2026-10-17  
**Purpose:** A detailed snapshot of the project's scope, implementation, model evidence, decisions, issues, and remaining work. Paths below are repository-relative.

> **Status in one sentence:** The five-system educational prototype, processed datasets, research models, FastAPI routes, React workspace, and substantial validation/documentation are implemented; model evidence remains dataset-specific and several research models are not ready for real maintenance decisions.

## 1. Project Objective and Scope

The project is an educational predictive-maintenance decision-support prototype for five aircraft-related systems:

| System | Dataset | Project task |
|---|---|---|
| Engine | NASA C-MAPSS | Degradation / remaining useful life (RUL) regression |
| Battery | NASA PCoE Li-Ion | State of health (SOH) and experimental RUL regression |
| Hydraulic | UCI Hydraulic Systems | Cooler, valve, pump, and accumulator condition classification |
| Fuel | Aircraft Fuel Distribution System | Normal/abnormal anomaly detection |
| Landing gear | Aircraft Landing Gear Digital Twin | Fault classification and RUL-percent regression |

Avionics and flight-operation anomaly detection were explicitly left out because the user did not confirm that dataset. The previously supplied React frontend was reviewed and integrated through the project's workspace rather than treated as a separate simulated application.

The intended output is a single dashboard backed by subsystem-specific models and preprocessing. It is not connected to live aircraft, is not certified, and must not replace inspections, approved procedures, or engineering judgment. Risk bands and confidence values are demonstration outputs, not approved maintenance limits.

## 2. Overall Progress

`PROJECT_PROGRESS.md` records **90% weighted estimated implementation completion**. This is a weighted estimate of the complete five-system application, not model accuracy, validation coverage, or aviation readiness. The roadmap has 176/183 items checked (96.2% by raw count); overlapping sign-off items make that a separate, unweighted measure. The clean pinned Python environment reproduced all 232 Python tests on 2026-10-17; the frontend's clean install/build remains unverified.

| Workstream | Current state |
|---|---|
| Scope, directory structure, roadmap, and project definition | Complete |
| Dataset acquisition, inventory, validation, and preprocessing | Complete for the five selected systems; several source/version questions remain |
| EDA and model development | Implemented for all five systems; performance and validation strength vary by task |
| Saved pipelines and FastAPI | Five subsystem workflows and research-release safeguards implemented |
| React workspace | AI Predictions accepts JSON/CSV requests and now runs schema/training-support preflight checks before model inference; Fleet and Maintenance remain distinct research/example views |
| Testing, reports, and presentation | Full Python suite: 232 passed in both configured and fresh pinned Python environments on 2026-10-17. Eight-slide panel-ready Markdown draft updated; dated source/model/report backup created and hash-verified. Independent validation, clean frontend setup/build, per-case explanations/trends, and a polished PowerPoint deck remain |

The project is **not 100% complete**: independent representative data, model calibration, source verification, clean frontend setup/build, per-prediction explanations/trends, validated healthy/high-risk demo cases, and a polished final slide deck remain. Python environment reproduction is complete; full-project clean reproduction is not.

## 3. Data and Preprocessing Completed

All selected raw data are organized under `data/raw/<component>/`, with processed tables under `data/processed/<component>/`. The inventory, schemas, source notes, and processing decisions are documented under `docs/` and `reports/`.

| System | Local data / processed output | Work completed and important caveats |
|---|---|---|
| Engine | C-MAPSS FD001-FD004; FD001 processed feature table has 20,631 train/test rows in its combined labeled feature output | Validated loader, per-engine RUL labels, causal rolling/trend features, EDA, grouped splits, and official FD001 terminal-RUL evaluation. All four training subsets are now available for research experiments. |
| Battery | 34 battery IDs; 7,565 metadata-referenced measurement CSVs. `discharge_cycles.csv`, `soh_features.csv`, and `rul_features.csv` | Charge/discharge/impedance parsing, chronological cycle table, SOH, curve features, observed/censored EOL distinctions, and discharge-throughput reconstruction. Original MATLAB/conversion provenance remains incomplete. |
| Hydraulic | 2,205 cycles, 17 sensor matrices, 5 source targets; `cycle_features.csv` has 119 model features plus labels/metadata | Validated sampling rates and cycle alignment; extracted seven statistics per sensor; preserved stable/unstable flags; removed virtual-proxy features from the cooler model. |
| Fuel | Five scenario CSVs x 171 rows x 8 sensors = 855 rows; `scenario_features.csv` has 32 engineered model features | Validated numeric schema, row ordering, and reproducible causal rolling features. `is_abnormal` is inferred from scenario membership; it is **not** a row-level active-fault annotation. |
| Landing gear | 1,500 simulated events, four fault classes, six allowed model inputs | Validated rows, labels, RUL bounds, and unique run IDs; excluded `RunID` and targets from model features to prevent leakage. The local source-version/mass-range discrepancy remains open. |

Avionics is not part of this inventory or the current model scope.

## 4. Current Model Evidence by System

These numbers use different tasks and validation populations; they should not be ranked as if they were one common accuracy score. "Conditional pass" means an internal project gate, not real-world or aircraft readiness.

### Engine RUL

- The readiness pipeline uses a **Random Forest** selected from grouped engine-ID validation. The readiness report gives grouped OOF MAE **11.56 cycles**, RMSE **16.28**, and R-squared **0.847**.
- Its official NASA FD001 terminal-test evaluation reports MAE **13.80 cycles**, RMSE **18.61**, and R-squared **0.799**. The nominal 95% prediction interval covered **85%** of those 100 engines, so uncertainty calibration is still incomplete.
- A separate retained research candidate from `rul-retrain-20260912` has an audit MAE/RMSE of approximately **17.04/28.19 cycles**, and an official FD001 check of **10.63/16.27**. Those are different evaluation populations and must not be mixed with the readiness-model grouped OOF score.
- A frozen full-trajectory protocol now scores all 12,440 cycles from 60 fitting engines and includes phase, worst-engine, and near-failure regression gates.
- **Recent use of the other raw C-MAPSS training data:** FD002 (260 engines), FD003 (100), and FD004 (249) were tested as supplementary training data. FD001 test files were not used to fit/select these models. Adding 25% or 50% supplemental weight gave balanced-phase MAE **35.56** and **37.02**, versus the FD001-only baseline **19.60**. A targeted FD003-only mixture at 5% or 10% gave **34.64** and **34.66**. All failed the frozen gates; the best engine model and active release were preserved.
- The local FD004 count is **249 train / 248 test**. The included readme reverses these counts; the validated local inventory/counts were used.

Evidence: `reports/ENGINE_FD001_OFFICIAL_TEST.md`, `reports/RUL_RETRAINING_20260912.md`, `docs/ENGINE_VALIDATION_PROTOCOL_V1.md`, and `models/candidates/engine-cross-subset-20260925/`.

### Battery SOH and RUL

- SOH uses discharge-curve inputs and battery-grouped validation: MAE **2.62 percentage points**, RMSE **5.17**, R-squared **0.950** in the readiness evidence.
- RUL uses leave-one-battery-out evaluation on only **nine independent batteries**: MAE **9.36 cycles**, RMSE **12.32**, R-squared **0.862**. The empirical interval radius is about **18.58 cycles**; the small number of independent batteries limits confidence in this estimate.
- NASA Capacity was confirmed as discharge capacity to 2.7 V, distinct from full-discharge current throughput. Twenty-one inspected curves reproduced source capacities within about 0.0000044 Ah using the first recorded sample at/below 2.7 V. No labels were rewritten.
- B0042/B0043 operating-temperature history and the CSV conversion/provenance remain unresolved. Retained labels and models were not changed merely to improve scores.

Evidence: `reports/BATTERY_SOURCE_REVIEW_20260915.md`, `reports/BATTERY_DATA_VALIDATION.md`, and `reports/metrics/readiness_v2_retraining.json`.

### Hydraulic condition models

The current readiness bundles use separate estimators by target:

| Target | Selected model | Internal result |
|---|---|---|
| Cooler condition | Logistic Regression | Stable grouped accuracy/balanced accuracy/macro F1: **100%**; source-designated unstable-cycle accuracy: **94.97%** |
| Valve condition | Logistic Regression | Accuracy **83.99%**, balanced accuracy **83.94%**, macro F1 **83.86%**. Accepted predictions: **61.08% coverage**, **91.86% accepted accuracy**. Unstable-cycle challenge is much weaker. |
| Pump leakage | Extra Trees Classifier | Accuracy **99.10%**, balanced accuracy **99.10%**, macro F1 **99.10%** |
| Accumulator pressure | Random Forest Classifier | Accuracy/balanced accuracy/macro F1 about **88.82%**; accepted-prediction coverage **92.68%**, accepted accuracy **92.33%**. |

The perfect stable cooler score reflects a controlled hydraulic test-rig dataset, not perfect aircraft performance. Valve and accumulator scores fall on unstable cycles, and the dataset's operating conditions are limited.

Evidence: `reports/HYDRAULIC_DATA_VALIDATION.md`, `reports/HYDRAULIC_EDA_AND_BASELINES.md`, `reports/TARGETED_RETRAINING_20260911.md`, and `reports/metrics/readiness_v2_retraining.json`.

### Fuel anomaly detection

- The current retained research model is the **robust steady-sensor envelope**. Its nested, scenario-aware development score is accuracy **50.88%**, balanced accuracy **68.64%**, macro F1 **50.21%**, abnormal-row detection **39.04%**, and normal false-alarm rate **1.75%**.
- There are 684 scenario-labeled abnormal rows and 171 normal rows. Predicting every row abnormal would achieve 80% ordinary accuracy, so ordinary accuracy alone is misleading. The current model does not achieve the user's earlier >90% target; that target is not supported by the present data/evidence.
- A 36-configuration temporal experiment reached accuracy **51.93%**, balanced accuracy **66.89%**, detection **41.96%**, and false alarms **8.19%**; it was not promoted because the balanced score was lower and false alarms higher.
- Recent all-sensor and CLF/CLV_S central-line experiments were also evaluated on aligned nested scenario/block folds. They increased false alarms substantially and were rejected. Their scripts/reports are separate; none overwrote or activated the current model.
- The dataset has only one normal trajectory and four abnormal scenario trajectories. Public scenario labels do not establish exact per-row fault onset/recovery, sample period, or verified component-level fault type. Nested scores are development evidence, not independent validation.

Evidence: `reports/FUEL_NESTED_IMPROVEMENT.md`, `reports/FUEL_90_PERCENT_PLAN.md`, `reports/FUEL_LABEL_VERIFICATION.md`, and the dated experiment folders under `reports/metrics/fuel-*-nested-20260925/`.

### Landing gear

- Fault classification uses observable inputs and excludes `RunID`. Readiness evidence gives accuracy **95.07%**, balanced accuracy **95.36%**, and macro F1 **94.95%** on the local simulated dataset.
- RUL-percent regression reports MAE **1.37 percentage points**, RMSE **2.63**, and R-squared **0.992** on internal data splits.
- These results apply to the local digital-twin dataset. The local mass range (about 1,001-4,998 kg) conflicts with the current published data-card range (3,000-6,400 kg); archive/version equivalence needs resolution.

Evidence: `reports/LANDING_GEAR_DATA_VALIDATION.md`, `reports/metrics/landing_gear_baselines.json`, and `reports/metrics/readiness_v2_retraining.json`.

## 5. Application and Integration

- **FastAPI** provides health/model metadata, examples, and subsystem prediction routes. It loads checksum-verified research-release artifacts and validates input schemas before prediction.
- **Input preflight** adds `POST /api/v2/preflight/{component}` for each of the five systems. It validates the same request schemas and uses the saved readiness bundles' observed training-support ranges where available. Hard-range/tail warnings pause inference for explicit review; invalid schemas block it. Fuel is explicitly marked not range-assessed because its experimental detector has no separate calibrated support gate. Units cannot be verified because request formats carry no unit metadata.
- **React** main entry (frontend-src/main.jsx) loads aircraft-maintenance-dashboard-enhanced.jsx. AI Predictions embeds frontend-src/ModelWorkspace.jsx. Fleet and Maintenance use frontend-src/ModelOperations.jsx to fetch backend dataset examples and call all five trained model endpoints. These results are not aircraft fleet telemetry or maintenance records. Fuel is visibly marked experimental.
- API responses include task/model information and warnings or uncertainty where implemented. The engine workspace now displays a prototype RUL band (High at 30 cycles or less, Medium at 31-60, Low above 60) and warns that these are demonstration thresholds, not certified maintenance limits.
- The frozen research release and pointer safeguards are documented in `reports/FINALIZATION_AUDIT.md`. Model experiments in this summary kept the active release unchanged.

## 6. Testing and Verification

- Full Python regression suite on 2026-09-26: **196 passed**. On 2026-10-02, **25 targeted readiness/workspace API tests** passed, along with **10 frontend tests**, a successful production build, and the 12-check headless browser smoke test including single-component and all-components preflight flows.
- Fuel preprocessing was regenerated in a temporary location and exactly reproduced all 855 processed rows and values. The local raw `Scenario_Two.csv` parsed with the expected eight sensors and matched its recorded fingerprint. This confirms local structural reproducibility, not archive provenance or event labels.
- The current headless-browser smoke test covers single-component preflight, all-components preflight and confirmation, all five prediction routes, invalid input, Fleet/Maintenance views, mobile layout, and backend disconnection.
- Previous test runs had two fuel parsing failures when `Scenario_Two.csv` was malformed. The current file now parses and the two affected tests passed; no scenario labels were edited to resolve the issue.

## 7. Key Decisions and Corrections

1. Use five confirmed systems only; exclude avionics.
2. Preserve raw files and neutral fuel scenario IDs. Do not infer fuel fault-onset rows from model alerts or paper intervals.
3. Split correlated data by engine, battery, condition group, scenario, or time block instead of random rows.
4. Keep candidate models separate and reject candidates that fail predefined non-regression checks. Recent engine and fuel candidates did not replace their retained champions.
5. Treat C-MAPSS, hydraulic rig, fuel simulation, battery bench, and landing-gear digital-twin results as dataset-specific evidence, not aircraft fleet validation.
6. Do not present selected/accepted-only accuracy without coverage; do not use ordinary accuracy alone on imbalanced fuel labels.
7. Maintain a separate research candidate/release process. No latest exploratory experiment changed active serving weights.

Other documented technical issues include long-running hydraulic preprocessing (the existing process was allowed to complete), constant-input EDA warnings (constant channels excluded from correlation analysis), and IEEE DataPort access restrictions (provenance was cross-checked from public records; no inaccessible archive was silently substituted).

## 8. Reproducibility Commands

Run these from the repository root in PowerShell. The dated experiment runners preserve existing output folders and refuse to overwrite them; use a new experiment identifier for a repeat run.

```powershell
# Full project test suite
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider

# Frontend production build
npm run build

# Start the API
.\.venv\Scripts\python.exe -m uvicorn src.api.app:app --reload

# Evaluate the frozen engine cross-subset experiments
.\.venv\Scripts\python.exe -m src.engine_cross_subset_retraining

# Run the separate fuel exploratory evaluations
.\.venv\Scripts\python.exe -m src.fuel_all_sensor_experiment
.\.venv\Scripts\python.exe -m src.fuel_central_line_experiment
.\.venv\Scripts\python.exe -m src.fuel_central_envelope_experiment
```

The targeted FD003-only engine run used 5% and 10% auxiliary shares through an explicit experiment configuration; details and OOF predictions are stored under `models/candidates/engine-fd003-transfer-20260925/`.

Reproduce that targeted configuration in a fresh output folder by setting the experiment name before calling the runner:

```powershell
.\.venv\Scripts\python.exe -c "from src import engine_cross_subset_retraining as e; e.EXPERIMENT='engine-fd003-transfer-20260925'; e.EXTRA_SUBSETS=('FD003',); e.MIX_SHARES=(0.05,0.10); e.run()"
```

## 9. Remaining Work - Recommended Order

1. Obtain independent aircraft-representative data and reviewed labels. For fuel, this means more independent normal missions, abnormal runs, and verified onset/recovery annotations; see `docs/FUEL_DATA_AUTHOR_REQUEST.md`.
2. Resolve landing-gear archive/version and mass-range discrepancies and document battery cleaned-CSV conversion provenance.
3. Continue calibration only with separated groups and enough independent units; keep the current fuel readiness gate failed until new evidence supports changing it.
4. When frontend work resumes, add per-prediction explanations/trends, run a fresh frontend install/build, and prepare a polished PowerPoint deck. The current eight-slide Markdown draft is at `docs/PROJECT_REVIEW_PRESENTATION.md`.
5. Do not label cases healthy or high risk as aircraft states without approved domain thresholds. Current examples are dataset replays and displayed RUL risk bands are prototypes.
6. A dated source/model/report/documentation archive is in the designated backup folder. Raw/processed datasets were excluded and should be backed up separately if required.

## 10. Main Evidence Index

- Scope and success criteria: `docs/PROJECT_DEFINITION.md`
- Step roadmap: `PROJECT_ROADMAP.md`
- Weighted project status: `PROJECT_PROGRESS.md`
- Dataset counts and provenance gaps: `docs/DATA_INVENTORY.md`
- Frozen engine full-trajectory checks: `docs/ENGINE_VALIDATION_PROTOCOL_V1.md`
- Overall model integration/finalization audit: `reports/FINALIZATION_AUDIT.md`
- Fuel nested score and limitations: `reports/FUEL_NESTED_IMPROVEMENT.md`
- Fuel label/onset verification: `reports/FUEL_LABEL_VERIFICATION.md`
- Battery source review: `reports/BATTERY_SOURCE_REVIEW_20260915.md`
- Hydraulic and landing-gear component reports: `reports/HYDRAULIC_EDA_AND_BASELINES.md`, `reports/LANDING_GEAR_DATA_VALIDATION.md`
- Machine-readable current readiness results: `reports/metrics/readiness_v2_retraining.json`

## 11. 2026-09-30 Project Updates

- Added CSV example downloads and CSV upload for the five existing subsystem request formats. CSV is converted into the same validated JSON payload used by the current prediction API; it does not introduce a new inference path or discard time-series rows.
- Added an automated frontend request-file test suite covering all five subsystems, malformed columns/rows, battery metadata consistency, and subsystem-specific input constraints.
- Added model-level global feature-importance summaries where the saved estimator supports them. The UI labels these as global signals, not case-specific causes. Fuel results additionally show the latest sample's scaled departure from the fitted normal envelope; this is a diagnostic cue, not proof of a fault.
- Added an independent-validation manifest checker, blank manifest template, and protocol. The checker verifies required evidence metadata and partition separation only; it does not validate model performance. No independent aircraft dataset or verified event labels have been supplied, so aircraft-level external validation remains **not performed**.
- Added a reproducibility/demo guide and a PowerShell verification script. The clean-environment setup is documented; it has not been claimed as tested in a newly provisioned environment.
- No model was retrained and no active model artifact or serving weight was changed in this update.
- Replaced the generated Fleet and Maintenance display with per-subsystem inference cards sourced from the saved API models. Removed simulated telemetry controls from the rendered navigation. The views explicitly identify dataset-example inputs and do not invent aircraft identifiers, fleet health, priorities, or maintenance recommendations.
- Added component-specific graphs to both model-backed views: RUL/SOH prediction intervals, hydraulic/landing-gear confidence, fuel flagged-sample counts, and available dataset input traces. Fuel traces are downsampled for display only; inference still receives the full request.

## 12. 2026-10-02 Upload Quality Preflight

- Added five no-prediction preflight endpoints under `/api/v2/preflight/` using the same Pydantic request schemas as inference.
- Engine, battery, hydraulic, and landing-gear checks report whether derived model inputs are inside observed training support or require review. Battery ordering and unstable hydraulic condition are also flagged.
- Engine data with fewer than 10 consecutive recent cycles pauses for review because the implemented causal feature pipeline uses 5- and 10-cycle rolling windows. Battery samples are time-sorted by the existing feature extractor and sample-count support is checked.
- Fuel preflight validates the schema but explicitly reports that distribution support is not assessed; fuel requests require explicit user review before continuing.
- AI Predictions now checks inputs before inference for both single-system and all-components uploads. Schema failures block inference; range/support warnings pause for explicit confirmation. Unit metadata is not present in the request formats and is not guessed.
- Verification: 25 targeted API tests, 10 frontend tests, successful build, and 12 browser checks passed. Vite still emits a non-blocking JavaScript bundle-size warning.

Remaining implementation work includes obtaining truly independent, labeled data for external validation; testing the clean-environment recipe on a fresh environment; and optional per-case explanation/time-series visualization. These are not represented as completed by the CSV, feature-importance, or manifest tooling.

## 13. 2026-10-03 Auditability and Reproducibility Follow-up

- Added single-model and all-components JSON report downloads in AI Predictions. Each successful entry records the UTC export time, subsystem, active release/model identifier, preflight response, prediction response, and SHA-256 of the request text; raw sensor inputs are deliberately excluded.
- Added Fleet and Maintenance JSON result downloads. Each exports all five visible subsystem checks with source/example context, attention status, explanation, model outputs, reference labels, and any failed endpoints; both files explicitly state that they are dataset replays rather than live aircraft records.
- Added unit tests verifying the digest and confirming exported reports do not contain raw sample values.
- Added a pinned Python environment snapshot for the verified API/test/model-evaluation environment; pinned direct frontend dependencies to the versions in package-lock.json and expanded the frontend test script to include the report tests.
- Documented telemetry authorization, provenance, data-quality, drift/performance monitoring, and human-review prerequisites. No live telemetry was fabricated or connected because an authorized operational feed is not present.
- The independent-validation manifest remains empty and correctly blocked. A metadata gate is not a performance evaluation; genuinely independent groups and reviewed labels are still required.
- Verification on 2026-10-03: 209 Python tests passed; 12 frontend tests passed; npm ci dry-run passed; pip check reported no broken requirements; direct production build passed. The combined PowerShell verifier repeatedly hit Vite EPERM while writing a temporary config under node_modules; invoking the approved npm build command directly succeeded. Vite still reports a non-blocking bundle-size warning.
- No training, model selection, calibration threshold, or active model artifact was changed.

## 14. 2026-10-04 Results Downloads for All Three Views

- AI Predictions provides JSON exports for a single subsystem run and for the five-subsystem upload.
- Repeated the JSON download actions at the end of AI Predictions, Fleet, and Maintenance in addition to their existing result/header locations.
- Fleet and Maintenance now each provide a section-level JSON export containing the five visible model checks, source/example metadata, status/review reason, concise result, full prediction response, dataset reference labels, and failed-service errors where applicable.
- Fleet exports are explicitly scoped to normal dataset examples; Maintenance exports are challenge dataset examples. Both exports say they are not live aircraft records or independent evaluation. Raw sensor request values are not included.
- Verification: all 15 frontend tests pass and the production build succeeds. The existing non-blocking Vite bundle-size warning remains.

## 15. 2026-10-17 Non-frontend completion pass

- Ran the full local Python regression suite: **232 passed** in 40.66 seconds.
  A non-blocking joblib warning reported unavailable Windows physical-core
  detection; it fell back to the logical-core count.
- Recreated an isolated virtual environment from `requirements-lock.txt` and
  reran the full Python suite: **232 passed** in 50.95 seconds. This verifies
  the pinned Python setup with the available datasets and model artifacts; a
  clean frontend install/build remains unchecked while frontend work is paused.
- Updated `docs/FINAL_RESULTS_AND_LIMITATIONS.md` to use the active
  readiness-v2.3 metrics, clearly separate the older engine baseline, and show
  accepted-prediction coverage and fuel's failed development gate.
- Rewrote `docs/PROJECT_REVIEW_PRESENTATION.md` as an eight-slide review draft
  with current results, speaker notes, and likely panel questions. This is a
  slide-ready Markdown draft, not a generated PowerPoint file.
- Created and read-verified the dated backup
  `aircraft-pm-project-backup-2026-10-17.zip` in the designated backup folder:
  883 entries, 454,293,178 bytes, SHA-256
  `8F60F3D29AF1A9C9DC8BAB4CD087D9A9D1A0070CDF7E6B2A294C6A98861594DF`.
  It contains source, models, reports, and docs; raw/processed datasets,
  environments, and Git internals were intentionally excluded.
- The FastAPI prediction-history service and GitHub Actions CI workflow are
  documented in `docs/API.md` and `docs/CI_CD.md`. CI is configured to test the
  frontend, compile the backend, and run artifact-independent backend tests,
  then publish a build artifact; it does not deploy the application. A run on
  the project's GitHub repository has not been verified here.
- Frontend implementation was intentionally left unchanged during this pass.
- Overall implementation remains **90%**. External evaluation requires
  independent, reviewed data; source/provenance and calibration gaps remain;
  fresh frontend setup/build has not been verified; frontend explanations/trends
  and the polished final presentation are still outstanding.
