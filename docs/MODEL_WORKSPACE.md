# Use the connected model workspace

From the project folder, start the backend in one PowerShell terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api.app:app --reload
```

Restart an already-running backend after activating a frozen model release.
In a second terminal:

```powershell
npm run dev
```

Open the local URL printed by Vite (normally http://127.0.0.1:5173).
Select Engine, Battery, Hydraulic, Landing gear, or Fuel system. Choose example A
or B, inspect the JSON, and select **Run prediction**. Each result comes from the
backend. Example labels describe dataset records and do not imply that the model
must get every example right. Hydraulic A is stable; B is unstable and must require
review. Fuel expects a complete ordered trajectory starting at the mission origin.

You can paste or import your own request JSON. When an input changes, old results
are cleared and the dataset reference labels no longer apply. Model acceptance
only means the input passes the current development rule. Read the interval,
confidence, support warnings, and finalization audit before interpreting a result.

The **Open simulated visual demo** button displays the original fleet mock-up.
Its generated telemetry is explicitly separate from backend predictions.

## Addresses

- Backend API and Swagger: http://127.0.0.1:8000/docs
- Development frontend: normally http://127.0.0.1:5173
- Built frontend: `npm run build`, then `npm run preview` (normally port 4173)
- Vite proxies `/api` to port 8000. To target a different local backend:

```powershell
$env:AIRCRAFT_API_TARGET = 'http://127.0.0.1:8001'
npm run preview
```

An optional `VITE_API_BASE_URL` supports a separately configured API origin.
The backend must allow that origin through its CORS configuration.

## Research release

The active model snapshot is recorded in `models/releases/current.json`.
The fuel improvement release is `research-fuel-20260910`; its experimental detector
returns `robust_steady_sensor_envelope`. The dashboard displays nested fuel metrics
from the release evidence. It remains disabled for readiness-v2 predictions.
Frozen model, evidence, and source hashes are verified when a backend starts.
Do not edit snapshot files. The dashboard identifies the active release and
displays the separate calibration audit. See `reports/FINALIZATION_AUDIT.md`.

To create a new reviewed snapshot after audit and tests, choose an unused ID:

```powershell
.\.venv\Scripts\python.exe scripts\freeze_research_release.py research-rc-your-new-id
```

This command snapshots the working `models/readiness` artifacts and activates the
new release. It does not retrain the models or establish final validation.

## Browser verification

On this Windows machine with Node 24 and Microsoft Edge installed:

```powershell
node scripts/browser_workspace_smoke.mjs http://127.0.0.1:4173
```

The check starts its own hidden headless browser, exercises all five models,
invalid input, unstable hydraulic rejection, disconnected-backend behavior and
mobile layout, then closes that browser. Results are written to
`reports/metrics/workspace_browser_check.json`; a screenshot is saved under
`reports/figures/model-workspace.png`. It requires running backend and frontend
servers and leaves its uniquely named temporary browser profile for inspection.
