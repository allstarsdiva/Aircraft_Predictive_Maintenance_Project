# Readiness-v2 API Contract

> 2026-09-10 update: API 0.4.0 serves verified research snapshots. Historical
> gates are explicitly labeled development metrics with finalization_ready=false.
> The engine interval no longer clips at 125 cycles (93% observed coverage on the
> previously inspected official test). See MODEL_WORKSPACE.md and
> ../reports/FINALIZATION_AUDIT.md for the new calibration audit and live UI.

The readiness-v2 routes supplement the original prototype endpoints. They return a model prediction together with uncertainty or calibrated confidence and an explicit acceptance decision.

## Acceptance Meaning

- `accepted: true`: the input is inside the hard training range and meets the model's empirical confidence rule where applicable.
- `accepted: false`: the application must show **Engineering review required** and must not present the number or class as an actionable maintenance conclusion.
- `tail_range_warnings`: features outside the central 1%-99% training range; these require attention even when the hard-range gate accepts the input.
- `hard_range_violations`: features outside every value observed during training; these cause abstention.

## Routes

| Route | Readiness additions |
|---|---|
| `POST /api/v2/predict/engine` | 95% grouped-residual RUL interval and input-support assessment |
| `POST /api/v2/predict/battery` | Separate 90% SOH/RUL intervals and support assessment |
| `POST /api/v2/predict/hydraulic` | Calibrated correctness confidence and target-specific abstention |
| `POST /api/v2/predict/landing-gear` | Observable-only input contract, confidence, RUL interval, and OOD rejection |
| `GET /api/v2/readiness` | Model gates, non-certification statement, and fuel-disabled status |

The engine, battery, and hydraulic request bodies remain compatible with their v1 counterparts. The v2 landing-gear route intentionally accepts only four observable inputs and removes the latent `k_stiffness` and `b_damping` values.
Readiness-v2.2 keeps the hydraulic request compatible while the cooler artifact ignores the virtual `CE`, `CP`, and `SE` feature families. Those fields remain available to the other three hydraulic target models. Neither fuel model is exposed through readiness-v2 because fuel still fails its deployment gate.

## Fuel Policy

There is no readiness-v2 fuel prediction endpoint. The fuel subsystem still fails its readiness gate. The legacy route now uses the low-false-alarm phase-residual detector and remains experimental. The high-sensitivity Extra Trees model is retained offline as a review tier; it is not an operational alert model.

## Run Locally

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api.app:app --reload
```

Open `http://127.0.0.1:8000/docs` to inspect and execute the typed contracts.
