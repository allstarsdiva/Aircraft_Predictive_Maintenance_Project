# Predictive-Maintenance API

Run from the project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api.app:app --reload
```

Interactive OpenAPI documentation is then available at `http://127.0.0.1:8000/docs`.

## Service Routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/health` | Service health and API version |
| GET | `/api/models/engine` | Selected engine-model metadata |
| GET | `/api/models/subsystems` | Availability and validation metrics for nine non-engine model artifacts |

## Prediction Routes

| Method | Route | Accepted input | Output |
|---|---|---|---|
| POST | `/api/predict/engine` | One ordered FD001 engine trajectory with 26 source fields per cycle | Latest RUL cycles, risk, recommendation, and warnings |
| POST | `/api/predict/battery` | Battery ID, cycle number, ambient temperature, and raw discharge samples | SOH percentage and experimental RUL point/90% interval |
| POST | `/api/predict/fuel-system` | Ordered samples containing the eight published sensor fields | Latest anomaly flag/margin, count of flagged samples, and persistence flag |
| POST | `/api/predict/hydraulic` | One cycle ID and exactly 119 precomputed waveform-summary features | Cooler, valve, pump, and accumulator condition classes |
| POST | `/api/predict/landing-gear` | Six documented event/physics inputs | Fault code/name and RUL percentage |

All request models forbid unexpected top-level fields and reject missing or non-finite numeric values. Model files are loaded lazily and cached; a missing or wrong artifact returns HTTP 503 instead of silently substituting simulated output.

## Battery Input Example

```json
{
  "battery_id": "B0005",
  "discharge_cycle": 1,
  "ambient_temperature": 24,
  "samples": [
    {
      "voltage_measured": 4.19,
      "current_measured": 0.0,
      "temperature_measured": 24.3,
      "current_load": 0.0,
      "voltage_load": 0.0,
      "time": 0.0
    },
    {
      "voltage_measured": 3.98,
      "current_measured": -2.0,
      "temperature_measured": 24.5,
      "current_load": -2.0,
      "voltage_load": 3.95,
      "time": 10.0
    }
  ]
}
```

The API derives the same 21 curve statistics used during model training, then adds discharge cycle and ambient temperature. Battery RUL is explicitly marked experimental because only nine observed-EOL battery trajectories were available.

## Hydraulic Feature Contract

The hydraulic endpoint accepts cycle-level summaries rather than tens of thousands of waveform values. It requires seven statistics (`mean`, `std`, `min`, `max`, `range`, `rms`, and `slope`) for each of the 17 sensors, totaling 119 features. The precise names are available in each saved hydraulic bundle and in `data/processed/hydraulic/cycle_features.csv`.

## Limitations

- Fuel detection has weak within-dataset validation and one normal reference trajectory.
- Landing-gear results come from one synthetic generator and use latent stiffness/damping estimates.
- Hydraulic primary validation used source-designated stable cycles.
- Predictions are research decision support. They do not replace inspection, engineering judgment, or certified maintenance procedures.
