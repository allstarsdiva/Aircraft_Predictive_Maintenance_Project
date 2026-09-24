# Aircraft Predictive Maintenance System: Project Definition

## 1. Problem Statement

Aircraft generate large amounts of operational and condition-monitoring data. Maintenance teams need a consistent way to turn that data into early warnings about degradation, faults, abnormal operation, and remaining component life.

This project will build a multi-system predictive-maintenance application covering engines, batteries, hydraulics, fuel systems, and landing gear. Each subsystem will have its own preprocessing and machine-learning pipeline because its dataset, features, and prediction target are different. The application will present their results through one common dashboard.

The system is intended as an educational decision-support prototype. It is not a certified airworthiness system and must not replace inspections, approved maintenance procedures, or qualified engineering judgment.

## 2. Project Objectives

The project will:

1. Ingest and validate data for five aircraft-related subsystems.
2. Detect degradation, faults, or abnormal operating conditions.
3. Estimate Remaining Useful Life (RUL) where the dataset supports it.
4. Estimate State of Health (SOH) for aircraft battery data.
5. Return clear predictions, confidence information, and maintenance-risk levels.
6. Explain the measurements that most influenced each prediction.
7. Compare each trained model with a simple baseline on unseen data.

## 3. Finalized Systems and Datasets

| Aircraft system | Finalized dataset | Primary use | ML task |
|---|---|---|---|
| Engine | NASA C-MAPSS | Engine degradation and RUL prediction | Regression |
| Electrical / Battery | NASA PCoE Li-Ion Battery Dataset | Battery SOH and RUL prediction | Regression |
| Hydraulic | UCI Hydraulic Systems Dataset | Hydraulic condition and fault prediction | Classification |
| Fuel System | Aircraft Fuel Distribution System Dataset (Kaggle / IEEE DataPort) | Normal/abnormal fuel-system condition prediction | Binary or multiclass classification, depending on labels |
| Landing Gear | Aircraft Landing Gear Digital Twin Dataset: PdM/SHM (Kaggle) | Landing-gear fault classification and RUL prediction | Classification and regression |

Dataset licenses, access requirements, versions, citations, and exact label definitions must be verified and recorded before model development.

## 4. Intended Users

### Primary users

- Aircraft maintenance engineers reviewing component condition.
- Reliability engineers studying degradation and failure patterns.
- Maintenance planners prioritizing inspections and maintenance work.
- Data scientists comparing predictive-maintenance models.

### Secondary users

- Project reviewers, instructors, and students using the application for demonstration and research.

## 5. Inputs and Outputs

### Common inputs

- A supported subsystem selection.
- A dataset file or a validated set of sensor measurements.
- Equipment, unit, flight, or cycle identifiers where available.
- Time, operating-cycle, or sequence information where required.

### Subsystem inputs and outputs

| System | Example inputs | Required outputs |
|---|---|---|
| Engine | Engine ID, operating cycle, operating settings, engine sensors | Predicted RUL in cycles and maintenance-risk level |
| Battery | Battery/cell ID, cycle, voltage, current, temperature, capacity-related measurements | Predicted SOH, predicted RUL, and risk level |
| Hydraulic | Pressure, flow, temperature, vibration, power, and condition sensors supplied by the dataset | Predicted component condition/fault class and class probability |
| Fuel System | Flow, pressure, valve, pump, tank, or simulation measurements supplied by the finalized dataset | Normal/abnormal or named fault class and class probability |
| Landing Gear | Load, strain, vibration, position, cycle, or digital-twin features supplied by the dataset | Fault class and, when labels permit, predicted RUL |

The exact feature schemas will be recorded in separate data dictionaries after each dataset is obtained.

## 6. Maintenance-Risk Presentation

Regression outputs will be translated into configurable maintenance-risk bands. Initial demonstration bands are:

- **High:** predicted RUL is at or below the subsystem's urgent threshold.
- **Medium:** predicted RUL is above the urgent threshold but below the warning threshold.
- **Low:** predicted RUL is above the warning threshold.

Classification outputs will use the predicted condition, probability, and an approved class-to-risk mapping. Thresholds must be derived from dataset behavior and documented; they must not be presented as real aircraft maintenance limits.

## 7. Evaluation Metrics

### RUL and SOH regression

- Mean Absolute Error (MAE) as the primary, easily interpreted metric.
- Root Mean Squared Error (RMSE) to penalize large prediction errors.
- R-squared as a supporting measure, not the sole success criterion.
- NASA scoring function for C-MAPSS when comparison with published engine results is useful.

### Fault and anomaly classification

- Macro F1-score as the primary metric when classes are imbalanced.
- Balanced accuracy as a secondary overall metric.
- Per-class precision and recall.
- Confusion matrix.
- ROC-AUC or PR-AUC when appropriate for binary classification.

### Validation rules

- Split by engine, battery, aircraft, flight, or physical unit rather than randomly splitting correlated rows.
- Fit scaling and feature transformations using training data only.
- Keep a final unseen test set that is not used for tuning.
- Compare every final model with a simple baseline.
- Report performance per subsystem instead of combining incompatible tasks into one score.

## 8. Initial Success Criteria

A subsystem prototype is successful when:

- Its full preprocessing and prediction pipeline runs reproducibly.
- It performs better than the documented baseline on unseen units or sequences.
- Regression reports MAE and RMSE; classification reports macro F1 and per-class recall.
- The test split contains no unit or sequence leakage from training.
- The application validates inputs and displays a prediction with uncertainty or confidence information.
- Known limitations and unsafe interpretations are documented.

The overall project is successful when all five confirmed subsystem pipelines satisfy these requirements and are accessible through one dashboard.

## 9. Scope Boundaries

### Included

- Offline dataset ingestion and validation.
- Exploratory analysis and feature engineering.
- Model training, comparison, and saved prediction pipelines.
- A dashboard for predictions and subsystem results.
- Model explanations, documented limitations, and reproducible tests.

### Not included

- Connection to live aircraft systems.
- Automatic maintenance scheduling or work-order approval.
- Safety-critical control actions.
- Certification for operational aviation use.
- Claims that research-dataset thresholds are approved maintenance limits.
- Avionics or flight-operation anomaly prediction.

## 10. First Implementation Priority

The engine pipeline using NASA C-MAPSS will be implemented first as the reference pipeline. Its project conventions will then be reused where appropriate for the other subsystems, while keeping each subsystem's labels, preprocessing, validation, and metrics separate.
