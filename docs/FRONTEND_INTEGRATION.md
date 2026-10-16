# Frontend Integration Contract

> Updated 2026-09-30: Vite entry frontend-src/main.jsx imports
> aircraft-maintenance-dashboard-enhanced.jsx. AI Predictions calls FastAPI
> using uploaded input. Fleet is a high-level model-coverage snapshot;
> Maintenance groups challenge-example model outputs for component review. There
> is no live aircraft registry or telemetry integration. See MODEL_WORKSPACE.md.
 ## Reviewed Frontend

File: `aircraft-maintenance-dashboard-enhanced.jsx`

The supplied file is a React component using Lucide React and Tailwind utility classes. It is the main dashboard shell. The AI Predictions workspace uses user-provided input; Fleet and Maintenance use only backend dataset examples and returned trained-model outputs. There is no aircraft fleet registry, live telemetry, or maintenance-work-order feed connected.

## Current API integration

- `GET /api/workspace/examples/{component}?variant=normal` provides the representative examples used by Fleet.
- `GET /api/workspace/examples/{component}?variant=challenge` provides the challenge examples used by Maintenance review.
- `POST /api/v2/preflight/{component}` validates each request against its API schema and, where supported, reports saved-model training-support warnings before inference.
- `POST /api/v2/predict/engine`, `/api/v2/predict/battery`, `/api/v2/predict/hydraulic`, and `/api/v2/predict/landing-gear` call the corresponding saved models.
- `POST /api/predict/fuel-system` calls the experimental fuel detector.
- `GET /api/workspace/evidence` returns release and evaluation caveats for the AI Predictions workspace.

AI Predictions submits user-provided JSON/CSV-derived request bodies. Fleet checks endpoint coverage with normal dataset examples and presents an honest “aircraft connected: 0 / fleet health unavailable” state because no aircraft registry or telemetry feed exists. Maintenance calls the models with challenge examples and groups model-detected faults as Critical, unsupported/abstained inputs as Caution, and the rest as Monitor. Those are research-example review labels, not real aircraft diagnoses, maintenance thresholds, work orders, or live queues. No `/api/fleet`, aircraft-history, or WebSocket telemetry service is connected.

Responses intentionally remain task-specific rather than being coerced into a fabricated common aircraft-health or maintenance-priority schema:

| Frontend component | Actual model output |
|---|---|
| Engine | RUL regression |
| Electrical / Battery | SOH and RUL regression |
| Hydraulic | Component-condition classification |
| Fuel | Normal/abnormal or scenario classification |
| Landing Gear | Fault classification and RUL regression |

## Current behavior and limitations

- Avionics has been removed because it is excluded from the project scope.
- Do not show RUL for classification-only hydraulic and fuel predictions.
- The archived prior dashboard is preserved in `aircraft-maintenance-dashboard-previous.jsx`; it is not imported by the current app because it contains generated demo aircraft/telemetry data.
- Fleet and Maintenance are now distinct: Fleet shows coverage and model-check distribution, while Maintenance shows the per-component Critical/Caution/Monitor review list with task-specific result graphs.
- Critical is used only for an explicit positive landing-gear fault or fuel anomaly output. Caution means model abstention/input-support warning, not a confirmed maintenance condition. No RUL critical-cycle cutoff is invented.
- The dashboard has no real aircraft registry, uploaded-telemetry ingestion, persistent prediction history, WebSocket stream, or work-order API. Those require data sources and backend contracts that are not currently available.
- Loading, per-model errors, and model warning displays are present. Fuel remains experimental; all outputs remain research-only.

## Original integration sequence (completed prototype scope)

1. Build and validate dataset loaders.
2. Train and save subsystem pipelines.
3. Implement typed FastAPI prediction and dashboard adapters.
4. Scaffold the React application around the supplied component.
5. Replace the Fleet and Maintenance mock views with saved-model API calls on backend dataset examples.
6. Defer live aircraft records and WebSocket ingestion until a real source, schema, and safety review are available.
