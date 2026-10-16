# Project demonstration guide

## Before the review

1. From the repository root, start the API in a terminal:
   .\.venv\Scripts\python.exe -m uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000
2. In a second terminal, run `npm run dev` and open the local Vite address.
3. Select AI Predictions; confirm the workspace says Prediction service connected and shows the research release.
4. Show the concise input summary, and optionally import a CSV or open “View or edit full JSON.” The CSV example button downloads headers and rows matching the selected model request shape.
5. After a prediction, explain that feature bars are global model importance, not a case-specific cause. Fuel deviations are relative to the saved normal envelope, not proof of a fault.
6. Keep the evaluation status visible when discussing metrics. Fleet reports no aircraft feed and model coverage; Maintenance groups challenge-example model outputs, not actual work orders or maintenance diagnoses.

## Suggested five-minute flow

1. Introduce the five components and explain that each uses its own dataset and
   model, rather than a single universal aircraft model.
2. Select Engine. Leave Example A selected, run the request, and point out the
   predicted RUL, prototype risk band, and warnings.
3. Select Example B and run it. Explain that this is another previously
   inspected NASA dataset example, not an independent test.
4. Briefly open Battery, Hydraulic, Landing Gear, and Fuel to show the shared
   workflow and their different outputs. Fuel is explicitly experimental.
5. Open the per-model evaluation evidence; point out that no independent
   aircraft validation is recorded and that the fuel readiness gate is blocked.
   Close by saying outputs do not replace engineering review.

## CSV request files

The workspace exports a CSV example for each currently selected system and
accepts a matching CSV or JSON request. Keep every required column and preserve
time/sample ordering for engine, battery, and fuel trajectories. Battery CSVs
repeat battery ID, cycle, and ambient temperature on every sample row. Hydraulic
and landing-gear CSVs contain exactly one cycle/event row. Import conversion is
strict and rejects missing or unexpected columns rather than silently dropping
them. CSV files are converted to the same JSON request body used by the API;
this does not retrain models or create a new validation split.

## Example cases

The workspace loads examples from
GET /api/workspace/examples/{component}?variant=normal or variant=challenge.
These cases are for repeatable interface demonstrations. The engine examples
replay NASA FD001 official test units 1 and 81, which have already been
inspected during development. They must not be described as new, untouched
validation. Battery and hydraulic examples also come from local datasets;
landing examples come from a synthetic dataset. Fuel remains a development
demonstration only.

## Reviewer questions to prepare for

- Why separate models? The subsystems have different sensors, labels, and
  physical meaning.
- How was leakage limited? Grouped splits were used where applicable; see each
  subsystem validation report for its actual split.
- What do scores mean? Regression uses error in cycles/percentage points;
  classification uses class metrics. There is no single cross-system accuracy.
- Is the system aircraft-ready? No. External validation, calibration, source
  provenance, and formal safety assessment are not complete.
- What does a high risk band mean? It is a prototype RUL threshold for display,
  not an approved maintenance limit or a maintenance instruction.

## Recovery

If the backend is unavailable, restart the API and use Reconnect / reload. Do
use Fleet as a model-coverage snapshot (real fleet health is unavailable without aircraft data) and Maintenance as a research-example triage view. Neither tab is live aircraft telemetry.
