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
or B, inspect the JSON, and select **Check data & predict**. The API validates the
request schema and checks available model training support before it runs a
prediction. If a support warning appears, review it and explicitly continue if
you still want the research prediction. Example labels describe dataset records
and do not imply that the model must get every example right. Hydraulic A is
stable; B is unstable and requires review. Fuel expects a complete ordered
trajectory starting at the mission origin and always requires a review because
there is no separate calibrated preflight support gate.

Engine inputs with fewer than 10 consecutive recent cycles pause for review
because the engine feature pipeline uses 5- and 10-cycle rolling windows.
Battery sample-count support is checked after the same time-sorting and feature
extraction used for prediction. These checks identify limited model context;
they do not certify that a submitted trajectory is complete.

Before running a prediction, acknowledge that you checked the request's fields,
sequence, and units. This confirmation is reset when you change the input or
select another example. It is a user reminder, not a unit-conversion or aircraft
sensor validation feature.

The input panel now has a component-specific unit guide, also available for the
all-components upload. Battery, hydraulic, landing-gear, and some fuel units are
documented; C-MAPSS sensor units and several fuel flow/valve units are not
published in the supplied sources and are left explicitly unknown. The API
rejects negative battery voltages and negative fuel tank levels. It intentionally
does not cap fuel tank readings at 100 because the supplied data includes small
over-100 readings. These checks do not verify unit selection or aircraft
physical validity.

You can paste or import your own request JSON. When an input changes, old results
are cleared and the dataset reference labels no longer apply. Model acceptance
only means the input passes the current development rule. Read the interval,
confidence, support warnings, and finalization audit before interpreting a result.
The all-components upload runs the same preflight checks on all five subsystem
requests before any of its prediction calls. Invalid schemas block the request;
support warnings pause for explicit confirmation. The request formats do not
include unit metadata, so this check cannot verify units or guarantee physical
sensor quality.

After a successful single-model prediction, use Download prediction report to
save a timestamped JSON record of the model release, preflight result, output,
and a SHA-256 digest of the request text. The five-model workflow has a matching
Download all-components report action. The download actions are also repeated at
the bottom of the AI Predictions section. Reports deliberately omit raw sensor
values; retain the original request separately if you need to reproduce a run.
The report export does not persist data to the backend or count as independent
validation.

The **Fleet** tab is a high-level integration/coverage overview. Since no
aircraft registry or live telemetry feed is connected, it explicitly reports
zero aircraft connected and fleet health unavailable; its chart summarizes
model-check states for normal dataset examples, not aircraft health. **Download
Fleet results (.json)** exports the visible five-subsystem snapshot, dataset
example source, model outputs, and model-check status. This action is repeated
at the bottom of the Fleet section.

The **Maintenance** tab uses challenge dataset examples and groups component
outputs as Critical, Caution, or Monitor. Critical is reserved for a positive
landing-gear fault or fuel anomaly result; Caution means a model abstained or
reported input-support warnings. Neither category is a maintenance diagnosis or
approved severity limit, and no engine/battery RUL cutoff is fabricated. This
view includes per-component graphs: regression intervals for RUL/SOH,
classification confidence for hydraulic and landing gear, fuel detector sample
counts, and dataset sensor traces where applicable. Fuel's input trace is
downsampled for display only; the complete sequence is still sent to the model.
None of these charts is live telemetry.
**Download Maintenance results (.json)** exports the challenge-example outputs,
attention levels, review explanations, and any unavailable model states. This
action is repeated at the bottom of the Maintenance section.

The AI Predictions page also shows an important-limitations summary before the
input workflow. It highlights the lack of independent aircraft validation, the
battery interval-coverage shortfall, the hydraulic valve diagnostic abstention,
the blocked fuel readiness gate and unresolved onset labels, and the synthetic
landing-gear data provenance. Figures are loaded from the saved audit and are
development diagnostics, not new or external test results.

Each Maintenance component card can be expanded to inspect its dataset-example
inputs (with sequence sizes and representative last readings), the component's
sub-models (for example battery SOH/RUL or the four hydraulic targets), and
returned feature-importance/deviation details. Model feature importance is
global rather than a case-specific explanation. The Fuel detector returns
normal-envelope deviation scores instead of ranked model feature importance.

## Addresses

- Backend API and Swagger: http://127.0.0.1:8000/docs
- Development frontend: normally http://127.0.0.1:5173
- Built frontend: `npm run build`, then `npm run preview` (normally port 4173)
- Vite proxies `/api` to port 8000. To target a different local backend:

```powershell
$env:AIRCRAFT_API_TARGET = 'http://127.0.0.1:8001'
npm run preview
```

## Optional API access protection

Local development remains open by default. To enable the optional shared-key
guard, set the same long, random `AIRCRAFT_API_KEY` in the backend process and
the Vite Node process. `AIRCRAFT_API_AUTH_REQUIRED=true` makes the backend fail
closed if the key is missing. Keep this key out of source control and never use
a `VITE_`-prefixed variable for it (those variables are exposed to the browser).

In PowerShell, set the backend variables in its terminal before starting Uvicorn:

```powershell
$env:AIRCRAFT_API_KEY = 'set-the-same-long-random-secret-in-both-terminals'
$env:AIRCRAFT_API_AUTH_REQUIRED = 'true'
$env:AIRCRAFT_ALLOWED_ORIGINS = 'http://127.0.0.1:5173,http://localhost:5173'
.\.venv\Scripts\python.exe -m uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, set the identical key before Vite starts so its server-side
proxy adds the `X-API-Key` header to local `/api` requests:

```powershell
$env:AIRCRAFT_API_KEY = 'set-the-same-long-random-secret-in-both-terminals'
npm run dev
```

When a key is configured, API routes require it, `/docs`, `/redoc`, and the
OpenAPI schema are disabled, while `GET /api/health` remains public for the
connection indicator. Requests are limited to 120 per minute per observed client
address and bodies to 25 MiB by default; set `AIRCRAFT_API_RATE_LIMIT_PER_MINUTE`
or `AIRCRAFT_API_MAX_BODY_BYTES` to change these server-side limits. These
in-process limits are development guardrails, not production-grade edge controls.
Behind a reverse proxy, the API may see every visitor as the proxy's address,
and multiple workers each maintain separate counters.

The shared key only gates access; it does not create user accounts or per-user
permissions. For public hosting, use HTTPS and put authentication plus robust
rate/size limits at a trusted reverse proxy or hosting platform. Keep the key
only between that server-side proxy and FastAPI; do not put it in the built React
app or point `VITE_API_BASE_URL` directly at a protected API. Configure
`AIRCRAFT_ALLOWED_ORIGINS` with only the exact browser origins you host.

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
