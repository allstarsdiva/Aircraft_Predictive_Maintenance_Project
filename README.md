# Aircraft Predictive Maintenance Project

An educational research prototype for predicting degradation and abnormal
conditions across five aircraft-related systems: engine, battery, hydraulics,
fuel, and landing gear. Each subsystem has a dataset-specific pipeline exposed
through FastAPI and a React model workspace.

> This is not a certified aviation system. Model outputs are research decision
> support only; they must not replace approved maintenance procedures,
> inspections, or qualified engineering judgment.

## Run locally

Requirements: Python 3.14.7 for the checked-in verified environment, Node.js/npm,
and the extracted datasets/model artifacts in this repository. See the pinned
environment instructions in `docs/REPRODUCIBILITY_AND_DEMO.md`.

In PowerShell, from the repository root, run:

    .\.venv\Scripts\python.exe -m uvicorn src.api.app:app --reload

In a second terminal, run npm install followed by npm run dev.
Open the local URL printed by Vite. FastAPI's interactive API reference is at
http://127.0.0.1:8000/docs.

The Vite app opens the fleet dashboard (`aircraft-maintenance-dashboard-previous.jsx`):
Fleet and Maintenance views run on a simulated fleet, and the Data Upload tab
sends a CSV/JSON file for one subsystem to the live backend's input-check and
prediction endpoints. To open the backend-connected model workspace instead,
change the import in `frontend-src/main.jsx` to
`../aircraft-maintenance-dashboard-enhanced.jsx`.

A second, TypeScript frontend (Next.js App Router) lives in `frontend/`. Run it
with `cd frontend`, `npm install`, `npm run dev`, then open http://127.0.0.1:3000.
It proxies `/api` to the same FastAPI backend; see [frontend/README.md](frontend/README.md).

Run automated tests and build the frontend with:

    .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
    npm run test:frontend
    npm run build

For a clean Windows environment and one-command verification, see
[reproducibility and demo setup](docs/REPRODUCIBILITY_AND_DEMO.md) and run
`.\scripts\verify_project.ps1` from PowerShell.

## CI and build delivery

GitHub Actions runs frontend tests/build and backend syntax plus artifact-independent
API tests on pushes and pull requests. When both jobs pass, it publishes the built
frontend as a downloadable workflow artifact; it does not deploy the app to a host.
The complete model/data-dependent Python suite remains part of local verification
because datasets and trained model artifacts are not stored in this repository.
See [CI workflow details](docs/CI_CD.md).

## Project contents

- src/ - data preparation, model training/evaluation, and FastAPI service.
- frontend-src/ - React (Vite) model workspace and the dashboard's Data Upload section.
- frontend/ - Next.js 16 + TypeScript dashboard (fleet, analytics, maintenance, models).
- docs/final-submission/ - project report, presentations, research paper, synopsis.
- data/raw/ and data/processed/ - source and derived datasets.
- models/releases/ - fingerprinted research model snapshots.
- docs/ - dataset dictionaries, API contracts, architecture, and demo.
- reports/ - validation, model comparison, and finalization evidence.
- tests/ - automated regression and API tests.

## Systems and status

The workspace exposes Engine (NASA C-MAPSS), Battery (NASA PCoE), Hydraulic
(UCI), Fuel (Aircraft Fuel Distribution System), and Landing Gear (digital-twin
dataset) views. Evaluation metrics differ by task and split, so they should not
be collapsed into one accuracy score. Fuel remains experimental and its
readiness gate is failed. Battery RUL calibration, hydraulic support, landing
data provenance, and independent aircraft-representative validation remain
open. See [the final results and limitations](docs/FINAL_RESULTS_AND_LIMITATIONS.md)
and [the finalization audit](reports/FINALIZATION_AUDIT.md) before interpreting
any metric.

## Documentation

- [API routes and contracts](docs/API.md)
- [Dataset inventory](docs/DATA_INVENTORY.md)
- [Processed-data layout](docs/PROCESSED_DATA_LAYOUT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Demonstration guide](docs/DEMO_GUIDE.md)
- [Independent validation protocol](docs/INDEPENDENT_VALIDATION_PROTOCOL.md)
- [Future telemetry and monitoring prerequisites](docs/TELEMETRY_MONITORING_PLAN.md)
- [Reproducibility and verification](docs/REPRODUCIBILITY_AND_DEMO.md)
- [Project-review slides](docs/PROJECT_REVIEW_PRESENTATION.md)
- [Final submission: report, presentations, paper, synopsis](docs/final-submission/README.md)
