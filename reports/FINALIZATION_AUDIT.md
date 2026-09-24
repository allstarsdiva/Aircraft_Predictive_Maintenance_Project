# Finalization audit - 2026-09-10

> Subsequent fuel update: research-fuel-20260910 replaces only the experimental
> fuel detector using nested development evaluation. See FUEL_NESTED_IMPROVEMENT.md.
> Other models and the unresolved calibration findings below remain unchanged.

## Decision

Freeze the existing trained models as **research-rc-20260910-r2**, with the engine
interval correction and row-wise support fix. Do not promote the diagnostic refits
as final validated models. The live model workspace is connected to all five
subsystems; operational calibration and external validation remain unfinished.

## Corrections

- Hydraulic source flag **0 means stable; 1 means unstable**. The previous retest
  selected flag-1 rows and incorrectly sent `operating_condition_stable=true`.
  Its claim about 161 stable accepted rows was incorrect. Current example routes
  derive the boolean from the actual source flag, and unstable examples are tested
  to reject all four target predictions.
- `predict_with_readiness` previously applied a whole-batch support decision to
  every row. It now checks each row independently.
- Confidence calibration now rejects everything if no candidate meets both its
  calibration accuracy and minimum coverage requirements.
- The engine's 125-cycle training target cap no longer clips its uncertainty
  interval. Point predictions and the fitted error radius are unchanged. On the
  already inspected 100 official FD001 engines, interval coverage changes from
  **85% to 93%**, still below the nominal 95%. MAE remains **13.80 cycles**.

## Evaluation design

The diagnostic audit uses seed 20260909 and fixed current model specifications.
Entire groups are assigned to fitting, calibration, and evaluation partitions.
Preprocessing and the model are fitted only on fitting groups. Confidence/radius
calibration uses the calibration groups; scores below use evaluation groups.
Group identities are saved in the JSON report, along with prediction CSVs.

Groups are engine IDs, battery IDs, hydraulic condition combinations, and landing
mass bins. Engine calibration/evaluation uses one deterministic random truncation
per engine and raw remaining life. Other regression radii use row residuals within
their assigned groups: temporal dependence and the small number of batteries mean
nominal interval levels are not guaranteed.

All these datasets have already influenced development. This is a controlled
internal diagnostic, **not a newly untouched or external final test**. Its smaller
refitted models and evaluation populations differ from the historical OOF and
official-test evaluations, so changes are not a like-for-like improvement claim.

## Separate calibration/evaluation diagnostics

| Task | Evaluation score | Calibration finding |
|---|---|---|
| Engine diagnostic refit | MAE 25.40 cycles; RMSE 37.98 | 85% coverage vs nominal 95% on 20 random engine snapshots |
| Battery SOH | MAE 3.18 percentage points | 61.18% coverage vs nominal 90% |
| Battery RUL | MAE 13.75 cycles | 25.60% coverage vs nominal 90%; only one calibration and one evaluation battery |
| Hydraulic cooler | 100% accuracy | 100% accepted accuracy at 92.86% coverage |
| Hydraulic pump | 100% accuracy | 100% accepted accuracy at 90% coverage |
| Hydraulic accumulator | 81.43% accuracy | 91.09% accepted accuracy at 72.14% coverage |
| Hydraulic valve | 74.29% accuracy | No accepted predictions; calibration failed the requested rule |
| Landing fault | 93.67% accuracy | 93.54% accepted accuracy at 98% coverage |
| Landing RUL | MAE 1.48 percentage points | 89.67% coverage vs nominal 90% |
| Fuel | No new final score | One normal trajectory; candidate selection already used all scenarios |

Historical hydraulic accepted scores and fuel selected-candidate scores reused
calibration/selection data for reporting. They remain available as development
estimates, not independently established final accuracy. The API now explicitly
labels its old readiness gates as historical development gates and reports
`finalization_ready: false`.

## Frozen release

`models/releases/research-rc-20260910-r2/` contains the 11 existing readiness model
artifacts, source/test code, frontend source, dependency lock information, original
development metrics, current audit and prediction CSVs. The manifest records SHA-256
hashes and processed-data fingerprints. `models/releases/current.json` identifies
the active snapshot and the manifest hash. New backend processes verify all files
before loading readiness models and the experimental fuel detector. A changed or
missing frozen file fails verification. Legacy v1 non-fuel routes remain legacy
artifacts; the live workspace uses readiness-v2 for those four subsystems.

No archived release is overwritten. To create a later reviewed research snapshot,
use a new release identifier. Restart the backend after changing the active release.
Serving Python dependencies are recorded, not installed into an isolated release
environment; clean-environment reproduction remains a separate check.

## Application integration

The default React entry point is `frontend-src/ModelWorkspace.jsx`. It requests
dataset examples from `/api/workspace/examples/{component}` and sends their input
to the actual prediction endpoint. Users can edit or import request JSON. Reference
labels are separated from model inputs and hidden as comparisons after editing.
Inputs, example switches, and reconnects clear stale predictions. Errors, uncertainty,
input-support warnings, and rejected outputs are displayed. Fuel has an explicit
experimental label. The original randomly generated fleet view remains accessible
only through a clearly labeled simulated-demo button.

## Remaining finalization requirements

1. Obtain fresh independent evaluation data; historical data cannot become unseen
   merely by choosing a different random seed.
2. Investigate battery interval coverage across more independent batteries and
   hydraulic valve acceptance across unseen condition groups.
3. Acquire additional independent normal fuel missions and failure trajectories.
4. Resolve the landing dataset archive/version discrepancy.
5. Complete clean-environment setup, explainability, and the final presentation.

## Reproduce

Verification completed: **112 automated tests passed**, the production frontend
build passed, and the installed headless Edge browser passed all ten workflow
checks with no runtime exceptions. Checks include all five prediction views,
unstable hydraulic rejection, invalid JSON/stale-result clearing, the simulated
demo label, a 390px mobile layout, and disconnected-backend behavior. Evidence:
`reports/metrics/workspace_browser_check.json` and
`reports/figures/model-workspace.png`.

```powershell
.\.venv\Scripts\python.exe -m src.audit_finalization
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
npm run build
```

The audit writes diagnostic evidence and never replaces serving model weights.
The machine-readable audit is `reports/metrics/finalization_audit/audit.json`.
