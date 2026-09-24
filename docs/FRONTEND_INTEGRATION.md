# Frontend Integration Contract

> Updated 2026-09-10: the default entry point is now the backend-connected
> `frontend-src/ModelWorkspace.jsx`. All five subsystem predictions, dataset examples,
> and audit evidence are fetched from FastAPI. The original fleet view described
> below remains an explicitly labeled simulated demo. See MODEL_WORKSPACE.md.

## Reviewed Frontend

File: `aircraft-maintenance-dashboard-enhanced.jsx`

The supplied file is a React component using Recharts, Lucide React, and Tailwind utility classes. It currently generates a random fleet in the browser and simulates telemetry changes every 2.5 seconds.

## Backend Shape Expected by the Frontend

The comments and UI structure anticipate:

- `GET /api/fleet` for the fleet summary and aircraft list.
- `GET /api/aircraft/{id}` for one aircraft and its component predictions.
- `GET /api/component/{id}/history` for chart data.
- `WS /ws/telemetry` for live sensor and prediction updates.

FastAPI is the selected backend because it supports typed REST responses and WebSockets in the same Python service.

## Reusable Component Response

The backend adapter should return a stable common envelope:

```json
{
  "type": "Engine",
  "health": 74,
  "risk": "Medium",
  "priority": "Medium",
  "recommendation": "Monitor Closely",
  "prediction": {
    "task": "rul_regression",
    "value": 83.4,
    "unit": "cycles",
    "confidence": null
  },
  "sensors": [],
  "healthTrend": [],
  "predictionTrend": []
}
```

The nested `prediction` object is required because not every subsystem produces RUL:

| Frontend component | Actual model output |
|---|---|
| Engine | RUL regression |
| Electrical / Battery | SOH and RUL regression |
| Hydraulic | Component-condition classification |
| Fuel | Normal/abnormal or scenario classification |
| Landing Gear | Fault classification and RUL regression |

## Required Frontend Corrections During Integration

- Avionics has been removed because it is excluded from the project scope.
- Do not show RUL for classification-only hydraulic and fuel predictions.
- Replace simulated sensor definitions with the actual dataset feature schema.
- Display battery voltage on the Li-ion dataset's scale instead of the simulated 110-130 V range.
- Represent model confidence separately from failure probability unless the trained model truly estimates failure probability.
- Replace `generateFleet()` and `useLiveTelemetry()` with API and WebSocket clients.
- Add loading, empty, validation-error, and backend-unavailable states.

## Development Sequence

1. Build and validate dataset loaders.
2. Train and save subsystem pipelines.
3. Implement typed FastAPI prediction and dashboard adapters.
4. Scaffold the React application around the supplied component.
5. Replace simulated data with REST calls.
6. Add WebSocket updates only after static API integration is stable.
