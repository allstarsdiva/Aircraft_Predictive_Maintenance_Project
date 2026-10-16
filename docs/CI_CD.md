# CI and build delivery

The GitHub Actions workflow at `.github/workflows/ci.yml` runs for pushes,
pull requests, and manual dispatches.

## Checks

- Frontend: installs the locked npm dependencies, runs `npm run test:frontend`,
  then creates the production build with `npm run build`.
- Backend: installs `requirements-lock.txt`, compiles the Python source, and runs
  API security and prediction-history tests that do not require local datasets or
  trained model artifacts.
- Delivery: only after both jobs pass, publishes the built frontend as a
  downloadable GitHub Actions artifact named `aircraft-dashboard-<commit-sha>`.

The complete Python model/data regression suite is not run in GitHub Actions
because the project excludes raw/processed datasets and trained model files from
Git. Run that suite locally in the configured project environment with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

## Using it

Push this repository to GitHub with Actions enabled. Open the **Actions** tab to
see each run. After a successful run, download the verified frontend build from
the run's **Artifacts** section. This workflow does not deploy to a public host;
automated deployment should be added only after selecting a hosting provider and
configuring its credentials as repository secrets.
