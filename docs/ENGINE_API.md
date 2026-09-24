# Engine Prediction API

## Run Locally

From the project root with the virtual environment activated:

```powershell
uvicorn src.api.app:app --reload
```

Interactive API documentation is then available at `http://127.0.0.1:8000/docs`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Service health and API version |
| GET | `/api/models/engine` | Loaded engine model metadata |
| POST | `/api/predict/engine` | Predict latest engine RUL from a supplied trajectory |

## Prediction Request

The request contains one engine trajectory. Every record requires:

- `unit_id`
- `cycle`
- `operational_setting_1` through `operational_setting_3`
- `sensor_1` through `sensor_21`

All records must have the same positive `unit_id`, and cycle numbers must be unique. Unknown fields, missing sensors, NaN, and infinite values are rejected.

```json
{
  "subset": "FD001",
  "records": [
    {
      "unit_id": 1,
      "cycle": 1,
      "operational_setting_1": -0.0007,
      "operational_setting_2": -0.0004,
      "operational_setting_3": 100.0,
      "sensor_1": 518.67,
      "sensor_2": 641.82,
      "sensor_3": 1589.70,
      "sensor_4": 1400.60,
      "sensor_5": 14.62,
      "sensor_6": 21.61,
      "sensor_7": 554.36,
      "sensor_8": 2388.06,
      "sensor_9": 9046.19,
      "sensor_10": 1.30,
      "sensor_11": 47.47,
      "sensor_12": 521.66,
      "sensor_13": 2388.02,
      "sensor_14": 8138.62,
      "sensor_15": 8.4195,
      "sensor_16": 0.03,
      "sensor_17": 392,
      "sensor_18": 2388,
      "sensor_19": 100.0,
      "sensor_20": 39.06,
      "sensor_21": 23.419
    }
  ]
}
```

Supplying at least 10 recent, sequential cycles is recommended because the model uses 5-cycle and 10-cycle rolling features. The API sorts records by cycle before prediction.

## Prediction Response

```json
{
  "component": "Engine",
  "subset": "FD001",
  "unit_id": 1,
  "latest_cycle": 1,
  "input_cycles": 1,
  "model": "random_forest_baseline_rf",
  "prediction": {
    "task": "rul_regression",
    "value": 119.4,
    "unit": "cycles",
    "confidence": null
  },
  "risk": "Low",
  "recommendation": "No Immediate Action Required",
  "thresholds": {
    "high_max_rul": 30.0,
    "medium_max_rul": 60.0
  },
  "warnings": [
    "Fewer than 10 cycles were supplied; rolling degradation features have limited history."
  ]
}
```

The risk bands are project demonstration thresholds, not approved aviation-maintenance limits.

## Frontend Access

CORS is enabled for common local React development addresses on ports 3000 and 5173. The supplied frontend can call this endpoint after its simulated data layer is replaced with an API client.
