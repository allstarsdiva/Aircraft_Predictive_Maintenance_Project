# Model Retest and Tryout - 2026-09-09

> Audit correction (2026-09-10): the earlier hydraulic tryout inverted the UCI
> stability flag. Flag 0 means stable; flag 1 means unstable. The 161-row selection
> and cycle 147 example below used flag-1 rows while sending stable=true to the API.
> They do not establish correct stable-operation acceptance. Historical accepted
> accuracies also reused calibration data for scoring. See FINALIZATION_AUDIT.md
> and metrics/finalization_audit/audit.json for the corrected assessment.

## Outcome

The current readiness-v2.2 models, saved artifacts, and FastAPI prediction routes
were retested successfully. The system is a strong research prototype, but it is
not validated or certified for real-aircraft maintenance decisions. Nine model
tasks have a conditional readiness pass. The fuel-system readiness gate remains
failed.

## Verification Completed

- Complete automated suite: **95 tests passed**.
- Readiness artifacts loaded: **11 of 11**.
- Registered API model tasks available: **9 of 9**.
- Readiness gates: **9 conditional passes and 1 failure (fuel)**.
- Representative real-dataset records were sent through every active subsystem
  API route.

## Holdout and Grouped-Validation Scorecard

| Subsystem task | Validation result | Assessment |
|---|---|---|
| Engine RUL | Official NASA test: MAE 13.80 cycles, RMSE 18.61, R^2 0.799 | Good research baseline; interval coverage and external shift still require work |
| Battery SOH | Battery-grouped MAE 2.62 percentage points, R^2 0.950 | Strong on the available laboratory batteries |
| Battery RUL | Leave-one-battery-out MAE 9.36 cycles, R^2 0.862 | Good result, limited by nine observed-EOL batteries |
| Hydraulic cooler | Stable accuracy 100%; unstable challenge 94.97% | Strong within the UCI rig; perfect stable separation should not be generalized to aircraft |
| Hydraulic valve | All-row accuracy 83.99%; accepted accuracy 91.86% at 61.08% coverage | Useful with abstention; weak on unstable cycles |
| Hydraulic pump | Accuracy 99.10%; unstable challenge 99.87% | Very strong within this dataset |
| Hydraulic accumulator | All-row accuracy 88.82%; accepted accuracy 92.33% at 92.68% coverage | Useful with abstention; weaker on unstable cycles |
| Landing-gear fault | Mass-grouped accuracy 95.07% | Strong within the synthetic digital-twin dataset |
| Landing-gear RUL | MAE 1.37 percentage points, R^2 0.992 | Strong within the synthetic generator only |
| Fuel alert detector | Balanced accuracy 61.99%, detection 27.49%, false alarms 3.51% | Not good enough for readiness because sensitivity is low |

## Live API Tryout

- Engine FD001 test unit 1: actual terminal RUL **112 cycles**; predicted
  **122.88 cycles**; absolute error **10.88 cycles**. The prediction was accepted
  and the actual value was inside the reported 95% interval of 86.38-125 cycles.
- Battery B0047 example: actual SOH **83.72%**; predicted **83.85%**; absolute
  error **0.13 percentage points**. The SOH and RUL outputs were accepted.
- Hydraulic cycle 1: the API rejected all four outputs as outside model support;
  the cooler class was wrong. This demonstrates that the support gate prevented
  an unsafe accepted result.
- Hydraulic cycle 147: all four classes matched their labels and all four were
  accepted. There were 161 stable rows where all four current fitted models were
  both accepted and correct; this is an integration tryout, not new holdout evidence.
- Landing-gear example: fault class was correct and accepted. RUL absolute error
  was **2.16 percentage points** and the result was accepted.
- Fuel normal scenario: **0 of 171** samples were flagged. Each of the four failure
  scenarios ended with an abnormal alert, but only about **27.5%-28.1%** of their
  samples were flagged. This confirms low false alarms and weak sensitivity.

## Interpretation

The strongest current models are battery SOH, hydraulic cooler/pump, and the two
landing-gear tasks within their source datasets. Engine and battery RUL are useful
research baselines with meaningful errors and uncertainty intervals. Hydraulic
valve and accumulator predictions should be used only when accepted; unstable
conditions remain a weakness. Fuel is the clear bottleneck and must remain blocked
from readiness-v2.

The live examples prove that saved artifacts and API integration work. Model
quality claims must continue to use the grouped/holdout scorecard rather than the
individual examples, because individual rows are demonstrations rather than an
independent evaluation set.

## Commands Used

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

The authoritative machine-readable metrics remain in
`reports/metrics/readiness_v2_retraining.json`.
