# Project review presentation (8-slide, panel-ready draft)

Use this as slide content and speaker notes. Fill in student, course, and date
on Slide 1. The metrics are dataset-specific internal research results, not a
single cross-component accuracy score or proof of aircraft readiness.

## Slide 1 - Aircraft Predictive Maintenance

**A multi-system research prototype**

- Components: engine, battery, hydraulics, fuel, and landing gear
- Status: 90% implementation estimate; research use only
- Presenter: [Name] | Course: [Course] | Review: [Date]

Speaker note: “This project connects five separate predictive-maintenance
models to one application. It is not certified and is not used to make real
aircraft maintenance decisions.”

## Slide 2 - Problem and objective

- Sensor datasets contain patterns related to degradation and component
  condition.
- The project estimates RUL or SOH where the dataset provides suitable labels;
  other systems classify condition or abnormal patterns.
- The objective is to make model outputs inspectable through a backend and
  dashboard workflow.

Speaker note: “The models answer different questions, so we do not combine them
into one universal aircraft-health score.”

## Slide 3 - Data and model tasks

| System | Dataset | Model output |
|---|---|---|
| Engine | NASA C-MAPSS FD001 | Remaining useful life in cycles |
| Battery | NASA PCoE Li-ion | State of health and experimental RUL |
| Hydraulics | UCI hydraulic test rig | Cooler, valve, pump, and accumulator condition |
| Fuel | Aircraft Fuel Distribution System | Experimental normal/abnormal detection |
| Landing gear | Landing-gear digital-twin data | Fault class and RUL estimate |

Speaker note: “Each system has its own schema, preprocessing, target, and
validation split. Landing gear is synthetic; fuel labels and the amount of
normal data are limited.”

## Slide 4 - How the application works

**Request data -> validation/preprocessing -> saved model -> FastAPI response
-> review in the React workspace**

- API routes serve the five subsystem models and report validation warnings.
- Saved releases fingerprint model and supporting files.
- CI checks frontend tests/build and a backend API test subset; it does not
  deploy the site.

Speaker note: “The full project regression suite also runs locally with the
datasets and saved artifacts. The current Python suite passed 232 tests in both
the configured and a fresh pinned environment.”

## Slide 5 - Selected results

| Task | Current evidence |
|---|---|
| Engine RUL | Official unseen FD001 test: MAE 13.80 cycles; RMSE 18.61 |
| Battery SOH / RUL | Grouped MAE 2.62 percentage points / leave-one-battery-out MAE 9.36 cycles |
| Hydraulic valve | 83.99% overall accuracy; 91.86% accepted accuracy at 61.08% coverage |
| Landing-gear fault | 95.07% internal digital-twin accuracy |
| Fuel anomaly | 68.64% nested-development balanced accuracy; readiness gate failed |

Speaker note: “These results use different metrics and evaluation designs. The
valve accepted score applies only to accepted predictions, and the fuel result
is development evidence, not independent testing. More detail is in
`docs/FINAL_RESULTS_AND_LIMITATIONS.md`.”

## Slide 6 - What is implemented

- Five subsystem inference routes, input validation, and saved model pipelines
- JSON/CSV requests, preflight checks, result exports, and prediction history
- Research release checks, automated tests, reproducibility instructions, and
  GitHub Actions CI configuration

Speaker note: “The dashboard demonstrates the inference workflow using model
inputs and dataset examples. It does not receive live fleet telemetry.”

## Slide 7 - Limitations and responsible use

- No independent aircraft or aircraft-representative performance validation
- Fuel readiness gate failed; battery uncertainty calibration and hydraulic
  condition coverage still need work.
- Landing-gear source/version provenance remains unresolved.
- Displayed risk bands are prototype examples—not approved maintenance limits.

Speaker note: “The output is educational decision support only. It must not be
used to dispatch, release, defer, or schedule aircraft maintenance.”

## Slide 8 - What is needed next

- Obtain independent data with reviewed event labels and provenance.
- Complete per-prediction explanations and sensor trends in the dashboard.
- Resolve remaining source/calibration issues, then repeat the frozen
  evaluation protocol.
- Finish the clean frontend setup/build check and final presentation styling.

Speaker note: “The project is not 100% complete because these validation and
presentation steps are still open. A successful API prediction is not proof of
real-world aircraft performance.”

## Likely panel questions

- **Why use different models?** The five datasets have different sensors,
  targets, and physical meanings.
- **How did you reduce data leakage?** Use the component-specific grouped split
  protocols; correlated engines, batteries, scenarios, or conditions are not
  treated as independent random rows where the validation report requires
  grouping.
- **Is the project aircraft-ready?** No. Independent validation, calibration,
  provenance, and formal safety assessment are incomplete.
- **What does 91.86% valve accuracy mean?** It is accepted-prediction accuracy
  at 61.08% coverage; lower-confidence cases are not included in that number.
- **What does the fuel score mean?** It is nested development evidence on a
  small scenario dataset with only one normal trajectory; readiness failed.
