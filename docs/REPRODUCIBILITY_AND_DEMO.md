# Reproducibility and project verification

## Clean Windows setup

Run from the project root in PowerShell. These commands create a local virtual environment and install pinned dependencies for the verified Python 3.14.7 environment; they do not download or modify model artifacts.

requirements-lock.txt records the installed API, testing, and model-evaluation
environment. package.json and package-lock.json pin the frontend dependencies.
The broader requirements.txt remains the editable list for optional notebooks
and training tools; do not use it when reproducing the verified demo environment.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
npm ci
```

Then run the repeatable verification suite:

```powershell
.\scripts\verify_project.ps1
```

The verifier runs the Python regression suite, frontend tests, the production build, and confirms that the external-validation intake remains blocked while its template is empty. To skip the full Python suite:

```powershell
.\scripts\verify_project.ps1 -SkipPythonTests
```

For manual service startup, use two terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000
```

```powershell
npm run dev
```

Open the Vite URL (normally `http://127.0.0.1:5173`). Keep both terminals open. AI Predictions calls the FastAPI model endpoints using uploaded data. Fleet and Maintenance run the saved models on backend-provided dataset examples; they are not live fleet or maintenance records.

## Demo integrity

- Use the selected dataset examples for repeatable API demonstrations; describe them as replays, not new test results.
- Do not label a sample as an operationally healthy or high-risk aircraft case unless that interpretation is supported by a reviewed domain threshold.
- Show the release ID, task-appropriate metrics, uncertainty/acceptance, and limitations. The models are research prototypes and are not approved for maintenance decisions.
- The fuel model remains experimental and its readiness gate remains blocked.
- Back up source, the active release manifest/artifacts, reports, and slides together. Verify the release checksums after restoring a backup.
- A source/model/report/documentation archive was created on 2026-10-17 as
  `aircraft-pm-project-backup-2026-10-17.zip` in the designated backup folder.
  SHA-256: `8F60F3D29AF1A9C9DC8BAB4CD087D9A9D1A0070CDF7E6B2A294C6A98861594DF`.
  Raw/processed datasets, local environments, and Git internals are not included;
  preserve the original dataset files separately if a full data backup is needed.

## External evaluation data

The manifest template and evaluation gate are documented in `INDEPENDENT_VALIDATION_PROTOCOL.md`. A clean build or successful API prediction does not count as independent model validation.
