# Aircraft Predictive Maintenance Project Roadmap

## Project Objective

Build a multi-system predictive-maintenance application for aircraft engines, batteries, hydraulics, fuel systems, and landing gear. The system will estimate Remaining Useful Life (RUL) or State of Health (SOH) where supported and classify faults or abnormal conditions for the remaining systems.

## Finalized Datasets

| Aircraft system | Dataset | Project use |
|---|---|---|
| Engine | NASA C-MAPSS | Engine degradation and RUL prediction |
| Electrical / Battery | NASA PCoE Li-Ion Battery Dataset | Battery SOH and RUL prediction |
| Hydraulic | UCI Hydraulic Systems Dataset | Hydraulic condition and fault prediction |
| Fuel System | Aircraft Fuel Distribution System Dataset (Kaggle / IEEE DataPort) | Normal/abnormal condition classification |
| Landing Gear | Aircraft Landing Gear Digital Twin Dataset: PdM/SHM (Kaggle) | Fault classification and RUL prediction |

The detailed scope, users, inputs, outputs, metrics, and success criteria are defined in `docs/PROJECT_DEFINITION.md`.

---

# 50% Completion: Working Machine-Learning Prototype

The project is considered 50% complete when the complete basic machine-learning pipeline works—from loading sensor data to producing and evaluating an RUL prediction.

## 1. Define the Problem

- [x] Define RUL, SOH, fault classification, and anomaly classification targets by subsystem.
- [x] Write a clear problem statement.
- [x] Define the intended users of the system.
- [x] Identify the expected input sensor values and prediction output.
- [x] Choose initial regression and classification success metrics.

### Expected deliverable

See `docs/PROJECT_DEFINITION.md` for the approved project definition and initial success criteria.

## 2. Set Up the Project Structure

- [x] Create folders for raw data, processed data, notebooks, source code, models, reports, and the application.
- [x] Create a Python virtual environment.
- [x] Add the required Python packages to `requirements.txt`.
- [x] Create a `.gitignore` file.
- [x] Initialize version control if required.

### Recommended structure

```text
aircraft-predictive-maintenance/
├── app/
├── data/
│   ├── raw/
│   └── processed/
├── models/
├── notebooks/
├── reports/
│   └── figures/
├── src/
│   ├── preprocessing.py
│   ├── features.py
│   ├── train.py
│   └── predict.py
├── .gitignore
├── README.md
└── requirements.txt
```

## 3. Obtain and Understand the Dataset

- [x] Download and extract the NASA C-MAPSS dataset.
- [x] Store the supplied dataset files under subsystem folders in `data/raw/` without modifying their contents.
- [x] Document every C-MAPSS source column and derived RUL field in `docs/data_dictionaries/ENGINE_CMAPSS.md`.
- [x] Identify engine IDs, operating cycles, operating settings, and sensor columns.
- [x] Record dataset files, sizes, row counts, unit counts, schemas, and observed labels in `docs/DATA_INVENTORY.md`.

### Expected deliverable

A data dictionary and a notebook that successfully loads and displays the dataset.

## 3B. Validate the Battery Dataset

- [x] Load and validate all cleaned NASA battery metadata.
- [x] Verify one-to-one metadata references for 7,565 measurement CSVs.
- [x] Parse charge, discharge, and complex impedance schemas safely.
- [x] Normalize scientific timestamps and cleaned-data missing placeholders.
- [x] Document all battery metadata and measurement columns.
- [x] Build and save the chronological battery discharge-cycle table.
- [x] Define SOH for 2,750 valid records and defensible RUL labels for nine observed-EOL batteries.

## 4B. Perform Battery Degradation EDA

- [x] Audit missing, zero, extreme, and protocol-dependent capacity measurements.
- [x] Plot capacity degradation across all 34 batteries.
- [x] Analyze SOH distribution using the documented 2.0 Ah rating.
- [x] Distinguish observed EOL, left-censored, right-censored, and undocumented-threshold batteries.
- [x] Exclude invalid and post-EOL rows from direct RUL training eligibility.
- [x] Save the reproducible notebook, processed table, findings, and figures.

### Expected deliverable

The loader is implemented in `src/data/battery.py`, the schema is recorded in `docs/data_dictionaries/BATTERY_NASA_PCOE.md`, and validation findings are in `reports/BATTERY_DATA_VALIDATION.md`.

## 4. Perform Exploratory Data Analysis

- [x] Check for missing values and duplicate records in C-MAPSS FD001.
- [x] Examine FD001 sensor distributions and ranges.
- [x] Identify constant or nearly constant FD001 sensors.
- [x] Analyze FD001 sensor correlations with RUL.
- [x] Plot selected sensor values across normalized engine life.
- [x] Compare healthy cycles with cycles close to failure.
- [x] Save important charts in `reports/figures/engine/`.

### Expected deliverable

Completed in `notebooks/01_engine_cmapss_eda.ipynb`, with findings summarized in `reports/ENGINE_FD001_EDA.md`.

## 4C. Validate and Prepare the Hydraulic Dataset

- [x] Validate all 17 sensor matrices against the documented sampling rates.
- [x] Confirm 2,205 cycle-aligned rows and five valid profile labels.
- [x] Confirm that raw sensor matrices contain no missing or non-finite values.
- [x] Extract seven waveform statistics per sensor and cycle.
- [x] Save 119 model features with the condition targets under the hydraulic component directory.
- [x] Document target meanings, stability semantics, and leakage controls.
- [x] Perform hydraulic EDA and train component-condition classification baselines.

## 4D. Validate and Prepare the Fuel-System Dataset

- [x] Confirm the dataset creators, DOI, reference paper, hypothetical-data status, and license.
- [x] Validate five aligned schemas, 855 numeric rows, and neutral scenario labels.
- [x] Confirm zero missing, non-finite, and duplicate sensor snapshots.
- [x] Preserve the normal/abnormal target without inventing unpublished fault names.
- [x] Create causal changes and trailing statistics within each scenario only.
- [x] Save 32 model features under the fuel-system processed directory.
- [x] Document the single-normal-trajectory validation limitation.
- [x] Perform fuel-system EDA and train a scenario-aware anomaly-detection baseline.

## 4E. Validate and Prepare the Landing-Gear Dataset

- [x] Record the source page, creator, license, schema, fault meanings, and local SHA-256 checksum.
- [x] Validate 1,500 numeric landing events, unique run identifiers, fault codes, and RUL bounds.
- [x] Confirm zero missing, non-finite, and duplicate records.
- [x] Normalize column and fault names in a processed component table.
- [x] Exclude the fault-ordered `RunID` and all target-derived fields from model inputs.
- [x] Document the source/local mass-range discrepancy and synthetic-data limitation.
- [x] Perform landing-gear EDA and train fault-classification and RUL baselines.

## 5. Prepare the Data

- [x] Calculate RUL for every FD001 training record and cap the baseline target at 125 cycles.
- [x] Remove unusable zero-variance FD001 columns using a training-fitted filter.
- [x] Validate missing, duplicate, and malformed FD001 records before preprocessing.
- [x] Standardize retained features using parameters fitted on training engines only.
- [x] Create causal changes, rolling averages, and rolling deviations for selected sensors.
- [x] Split the data by engine ID to prevent data leakage.
- [x] Save reusable preprocessing logic in `src/preprocessing.py`.

### Important rule

Records from one engine must not be divided between training and validation sets. Split by engine ID rather than randomly splitting individual rows.

## 5B. Prepare Battery SOH Data

- [x] Extract voltage, current, temperature, load, duration, charge-throughput, and energy features from 2,750 discharge curves.
- [x] Exclude capacity and SOH targets from model inputs.
- [x] Store battery processed tables under `data/processed/battery/`.
- [x] Split complete battery IDs between training and validation.
- [x] Fit variance filtering and scaling on training batteries only.

## 6. Train Baseline Models

- [x] Train a median reference and Linear Regression baseline for FD001.
- [x] Train a stronger Random Forest baseline for FD001.
- [x] Use the same engine-grouped train-validation split for fair comparison.
- [x] Record model parameters and experiment results.
- [x] Save the best initial model bundle in `models/engine/`.

## 6B. Train Battery SOH Baselines

- [x] Train median, Linear Regression, and Random Forest SOH baselines.
- [x] Evaluate on seven batteries excluded from training.
- [x] Record MAE, RMSE, R-squared, per-battery error, and extreme-SOH behavior.
- [x] Save the selected Linear Regression bundle in `models/battery/`.
- [x] Build the separate, uncertainty-aware battery RUL experiment.

## 7. Evaluate the Prototype

- [x] Calculate Mean Absolute Error (MAE).
- [x] Calculate Root Mean Squared Error (RMSE).
- [x] Calculate R-squared.
- [x] Plot actual RUL against predicted RUL.
- [x] Examine errors by RUL band and the largest individual error.
- [x] Test predictions on 20 engines not used for fitting.
- [x] Document the baseline prototype's limitations.

## 50% Completion Checklist

The project has reached 50% when all the following are true:

- [x] The problem and prediction target are documented.
- [x] The raw engine dataset is available and understood.
- [x] Engine data validation and preprocessing run successfully.
- [x] Engine RUL labels are calculated correctly.
- [x] FD001 exploratory analysis and charts are complete.
- [x] Training and validation data are separated by engine ID.
- [x] Multiple baseline engine models have been trained.
- [x] MAE and RMSE results have been recorded.
- [x] The saved engine bundle can produce an RUL prediction from engineered sensor data.
- [ ] The README explains how to run the prototype.

### 50% milestone output

A reproducible machine-learning prototype that reads aircraft engine sensor data, prepares the data, trains a model, predicts RUL, and reports its initial accuracy.

---

# 100% Completion: Tested and Demonstrable Application

The second half of the project turns the prototype into a reliable, explainable, documented, and usable predictive-maintenance application.

## 8. Improve Features and Models

- [x] Compare Linear Regression, Random Forest, regularized forests, and safety-weighted forests for FD001.
- [x] Keep sequence models deferred because the traditional FD001 baseline is sufficient for the prototype.
- [x] Test causal changes and rolling degradation statistics.
- [x] Remove zero-variance features and exclude unit identifiers from model inputs.
- [x] Tune the best engine model using five-fold cross-validation grouped by engine ID.
- [x] Track all engine tuning candidates, offsets, metrics, and out-of-fold predictions.

## 9. Validate the Final Model

- [x] Evaluate the selected FD001 baseline on the fully unseen official NASA test set.
- [x] Compare the safety-calibrated engine model with the original Random Forest baseline using grouped out-of-fold predictions.
- [x] Report official MAE, RMSE, R-squared, and NASA asymmetric score.
- [x] Evaluate official-test performance across terminal-RUL bands.
- [x] Analyze optimistic and conservative maintenance-warning errors.
- [x] Confirm grouped validation and no use of official labels during model fitting.
- [x] Document assumptions, worst test engines, and baseline failure cases.

## 10. Create the Prediction Pipeline

- [x] Save the fitted FD001 variance filter and scaler in the engine bundle.
- [x] Save the tuned full-training FD001 Random Forest.
- [x] Build an end-to-end engine path for feature engineering, preprocessing, and prediction.
- [x] Validate all 26 C-MAPSS input names, values, units, cycles, and trajectory ownership.
- [x] Return typed HTTP validation and service errors for invalid engine input.
- [x] Add documented Low, Medium, and High engine demonstration-risk categories.

## 10B. Expose the Remaining Subsystem Models

- [x] Add a raw-discharge battery endpoint for SOH and experimental RUL with an empirical interval.
- [x] Add an ordered-trajectory fuel anomaly endpoint using causal feature generation.
- [x] Add a strict 119-feature hydraulic endpoint for all four component-condition models.
- [x] Add a combined landing-gear fault and RUL endpoint.
- [x] Add lazy artifact loading, HTTP 503 handling, typed responses, warnings, and a subsystem model registry.
- [x] Document all backend routes and input contracts in docs/API.md.

## 10C. Readiness-Oriented Retraining

- [x] Retrain engine RUL with complete-engine folds and evaluate once on the official NASA test engines.
- [x] Retrain battery SOH with five battery-grouped folds and battery RUL with leave-one-battery-out validation.
- [x] Retrain hydraulic targets with complete-condition grouping and confidence-based abstention.
- [x] Retrain landing gear with observable inputs only and held-out mass regimes.
- [x] Add empirical RUL/SOH intervals and training-support checks.
- [x] Add readiness-v2 FastAPI routes with accepted/abstained decisions.
- [x] Re-evaluate fuel and block it from readiness-v2 after its gate failed.
- [x] Compare four engine regressors using engine-grouped folds and add a sensor-noise/dropout stress test.
- [x] Remove virtual CE/CP/SE proxy channels from cooler training and evaluate unstable cycles separately.
- [x] Add a phase-aware fuel challenger with complete unseen-failure-scenario holdouts; retain the failed deployment gate because false alarms remain unsafe.
- [x] Add a low-false-alarm phase-residual fuel model with threshold tuning and causal persistence; retain the Extra Trees model as a high-sensitivity review tier.
- [x] Improve experimental fuel detection with a steady-sensor covariance envelope, nested scenario/block evaluation, and separate calibration; retain the failed readiness gate.
- [ ] Validate the v2 models on independent aircraft or aircraft-representative data.

### Example output

```text
Predicted Remaining Useful Life: 38 cycles
Maintenance Risk: High
Recommended Action: Schedule inspection soon
```

## 11. Add Model Explainability

- [ ] Show the most influential sensor measurements.
- [ ] Add feature-importance charts.
- [ ] Use SHAP or another appropriate explanation method if needed.
- [ ] Explain predictions in language understandable to maintenance personnel.
- [ ] State that predictions support—not replace—engineering judgment.

## 12. Build the User Interface

- [x] Build a React model workspace backed by FastAPI.
- [x] Allow users to enter or upload request JSON and load dataset examples.
- [x] Display predicted RUL, uncertainty intervals, confidence, and review decisions.
- [ ] Display the maintenance-risk category.
- [ ] Show sensor trends and model explanations.
- [x] Provide clear validation and error messages.
- [ ] Make the interface suitable for a project demonstration.

## 13. Test the Complete System

- [x] Test engine preprocessing functions.
- [x] Test the tuned engine prediction path through FastAPI.
- [x] Test valid, missing, malformed, cross-engine, and unexpected input fields.
- [x] Verify that saved engine bundles load correctly.
- [x] Retest all saved readiness artifacts and representative dataset samples through the FastAPI routes.
- [x] Run an end-to-end browser test from dataset input to displayed prediction for all five subsystems.
- [x] Audit disjoint fitting, calibration, and evaluation groups; record unresolved calibration and provenance issues.
- [x] Freeze a research candidate with verified model, data, source, and dependency fingerprints.
- [ ] Confirm that the setup works in a clean environment.

## 14. Complete Documentation

- [ ] Finish the README with setup and usage instructions.
- [ ] Document the dataset and preprocessing decisions.
- [ ] Explain the selected algorithms.
- [ ] Include model comparisons and final results.
- [ ] Add an architecture or workflow diagram.
- [ ] Document limitations, safety considerations, and future improvements.
- [ ] Add screenshots of the application.

## 15. Prepare the Final Demonstration

- [ ] Create a short presentation.
- [ ] Prepare sample healthy and high-risk engine cases.
- [ ] Demonstrate the full prediction workflow.
- [ ] Explain the model results without excessive technical jargon.
- [ ] Prepare answers about data leakage, model accuracy, and limitations.
- [ ] Back up the source code, trained model, report, and presentation.

## 100% Completion Checklist

The project is complete when all the following are true:

- [ ] The full workflow runs from raw sensor data to prediction.
- [ ] Multiple models have been compared fairly.
- [ ] The final model has been evaluated on unseen engines.
- [ ] Preprocessing and prediction use one reproducible pipeline.
- [ ] The trained model and preprocessing components are saved.
- [ ] The application displays RUL and maintenance risk.
- [ ] Predictions include understandable explanations.
- [ ] Invalid inputs are handled safely.
- [ ] Automated or documented tests pass.
- [ ] Setup, usage, results, and limitations are documented.
- [ ] The application and presentation are ready for demonstration.

### 100% milestone output

A tested application that accepts aircraft engine sensor data, predicts Remaining Useful Life, communicates maintenance risk, explains the prediction, and includes complete technical documentation and demonstration material.

---

# Suggested Completion Timeline

| Phase | Work | Project completion |
|---|---|---:|
| Planning and setup | Problem definition, environment, and project structure | 10% |
| Data preparation | Dataset study, cleaning, RUL labels, and splitting | 25% |
| Analysis | Exploratory analysis and feature engineering | 35% |
| Prototype modeling | Baseline models and initial evaluation | 50% |
| Model improvement | Feature refinement, tuning, and comparison | 65% |
| Final pipeline | Saved model, preprocessing, and input validation | 75% |
| Application | Interface, risk levels, charts, and explanations | 85% |
| Testing | Unit, edge-case, and end-to-end testing | 92% |
| Documentation and demo | Final report, README, presentation, and demonstration | 100% |

# Recommended Technology Stack

- **Language:** Python
- **Data processing:** pandas and NumPy
- **Visualization:** Matplotlib and Seaborn
- **Machine learning:** scikit-learn and optionally XGBoost
- **Explainability:** SHAP
- **Application:** Streamlit
- **Model storage:** joblib
- **Testing:** pytest
- **Version control:** Git

# Final Success Criteria

The final system should be reproducible, avoid data leakage, produce measurable results on unseen engines, and clearly communicate that its output is decision support for predictive maintenance rather than a certified aircraft-safety decision.
