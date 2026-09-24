# Engine Prediction API Implementation

Implementation date: 2026-08-21

## Completed Service

The FastAPI service loads the tuned FD001 model bundle and exposes strict, typed endpoints for health, model metadata, and engine RUL prediction.

| Method | Endpoint | Result |
|---|---|---|
| GET | `/api/health` | API status and version |
| GET | `/api/models/engine` | Loaded model, RUL cap, offset, feature counts, and grouped-CV metrics |
| POST | `/api/predict/engine` | Latest-cycle RUL, risk, recommendation, thresholds, and input warnings |

## End-to-End Flow

```text
JSON trajectory
  -> strict 26-column validation
  -> cycle ordering
  -> causal rolling/change features
  -> fitted variance filter
  -> fitted standard scaler
  -> tuned Random Forest
  -> conservative 5-cycle offset
  -> 0-125 RUL bounds
  -> risk and recommendation response
```

## Validation Behavior

The API rejects:

- Missing required settings or sensors.
- Unknown input fields.
- NaN and infinite numeric values.
- Non-positive unit IDs or cycles.
- Duplicate cycle values.
- Requests containing more than one engine ID.
- Unsupported C-MAPSS subsets.

It returns warnings when fewer than 10 cycles are supplied or when supplied cycle numbers contain gaps.

## Demonstration Risk Mapping

| Predicted RUL | Risk | Recommendation |
|---|---|---|
| 0-30 cycles | High | Inspect Immediately |
| 30-60 cycles | Medium | Monitor Closely |
| Above 60 cycles | Low | No Immediate Action Required |

These are project demonstration thresholds, not approved aviation-maintenance limits.

## Verified Response

A real request containing the first 12 observations of FD001 official test engine 1 returned HTTP 200:

```json
{
  "component": "Engine",
  "subset": "FD001",
  "unit_id": 1,
  "latest_cycle": 12,
  "input_cycles": 12,
  "model": "random_forest_baseline_rf",
  "prediction": {
    "task": "rul_regression",
    "value": 117.219,
    "unit": "cycles",
    "confidence": null
  },
  "risk": "Low",
  "recommendation": "No Immediate Action Required",
  "thresholds": {
    "high_max_rul": 30.0,
    "medium_max_rul": 60.0
  },
  "warnings": []
}
```

## Frontend Readiness

CORS permits local React development servers on ports 3000 and 5173. The supplied frontend can consume the endpoint after its simulated engine data layer is replaced with an HTTP client. Other subsystem cards must remain simulated or explicitly unavailable until their corresponding APIs and models exist.

## Verification

- 25 automated tests pass.
- The tuned bundle loads through the service dependency.
- Model metadata reports 43 retained features and a 5-cycle offset.
- Real FD001 trajectory inference returns a schema-valid response.
- OpenAPI documentation is generated automatically at `/docs`.
