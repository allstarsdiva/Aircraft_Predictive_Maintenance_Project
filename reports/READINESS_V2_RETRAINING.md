# Readiness-v2 Model Retraining

> Update: readiness-v2.2 adds engine candidate selection and stress testing, a proxy-free cooler model, and a two-tier fuel experiment. See `reports/FUEL_MODEL_IMPROVEMENT.md`, `reports/MODEL_IMPROVEMENTS_V2_1.md`, and `reports/metrics/readiness_v2_retraining.json` for the current results.

## Outcome

The engine, battery, hydraulic, fuel-system, and landing-gear models were retrained under stricter subsystem-specific protocols. The resulting artifacts are **pre-deployment research models**, not real-aircraft-validated or certified models. A conditional pass means the model may continue into external validation while enforcing uncertainty and abstention; it does not authorize maintenance use.

Nine prediction tasks received a conditional pass. The fuel-system detector failed because its one normal trajectory cannot establish generalization and its abnormal detection remains weak.

## Readiness Protections Added

- Training-only preprocessing within every validation fold.
- Complete-engine, complete-battery, complete-condition, or mass-regime holdouts.
- Empirical prediction intervals for RUL and SOH regressions.
- Empirical confidence calibration and abstention for classifiers.
- Hard training-range rejection and 1%-99% tail warnings for model features.
- A dedicated API response field showing whether a prediction is accepted.
- Explicit blocking of fuel predictions from the readiness-v2 interface.

## Engine RUL

| Evaluation | MAE | RMSE | R-squared |
|---|---:|---:|---:|
| Five-fold engine-grouped OOF | 11.56 cycles | 16.28 | 0.847 |
| Official NASA FD001 test | 13.80 cycles | 18.61 | 0.799 |

The previous official-test result was MAE 13.91 and RMSE 18.71, so retraining produced a small measurable improvement. A grouped-residual 95% interval was added. On the official test it covered 85% of engines with a mean interval width of 60.03 cycles. This undercoverage relative to 95% is visible evidence of simulation/test distribution shift, so the engine gate is conditional rather than operational.

## Battery

| Task | Protocol | MAE | RMSE | R-squared | Error radius |
|---|---|---:|---:|---:|---:|
| SOH | Five-fold grouped by battery | 2.62 points | 5.17 | 0.950 | 5.21 points (90%) |
| RUL | Leave one battery out | 9.36 cycles | 12.32 | 0.862 | 18.58 cycles (90%) |

The new SOH figures use five grouped folds over all available battery IDs, whereas the earlier result used one seven-battery holdout; they must not be presented as a direct like-for-like improvement. Battery RUL remains limited by only nine observed-EOL trajectories.

## Hydraulic Conditions

| Target | Accuracy on all grouped OOF rows | Accepted coverage | Accuracy among accepted predictions |
|---|---:|---:|---:|
| Cooler | 100.00% | 100.00% | 100.00% |
| Valve | 83.99% | 61.08% | 91.86% |
| Pump leakage | 99.10% | 100.00% | 99.10% |
| Accumulator | 88.82% | 92.68% | 92.33% |

Confidence abstention raises the reliability of valve and accumulator predictions that are accepted. Low-confidence events are returned for engineering review instead of being silently treated as trustworthy. Source-designated unstable cycles are always rejected by the v2 endpoint.

## Landing Gear

The v2 models remove latent stiffness and damping and use only maximum deflection, maximum velocity, settling time, and mass. Five-fold validation holds complete mass regimes out of training.

| Task | Result |
|---|---:|
| Fault accuracy | 95.07% |
| Fault balanced accuracy | 95.36% |
| Fault macro F1 | 94.95% |
| Accepted fault coverage / accuracy | 100% / 95.07% |
| RUL MAE | 1.37 percentage points |
| RUL RMSE | 2.63 percentage points |
| RUL R-squared | 0.992 |
| RUL 90% error radius | 4.66 percentage points |

This is more deployment-relevant than the earlier 99.8% physics-assisted score, but it is still validation within one synthetic generator.

## Fuel System

Two complementary experimental models were evaluated, but the subsystem still failed the readiness gate:

| Fuel tier | Accuracy | Balanced accuracy | Detection rate | False-alarm rate |
|---|---:|---:|---:|---:|
| High-sensitivity Extra Trees review model | 80.23% | 60.89% | 93.13% | 71.35% |
| Low-false-alarm phase-residual alert model | 41.29% | 61.99% | 27.49% | 3.51% |

Ordinary accuracy is misleading because 80% of evaluated rows are abnormal. The phase-residual detector improves balanced accuracy by 1.10 percentage points and sharply reduces false alarms, but its sensitivity is too low. Calibration cannot create missing operational diversity: only one independent normal trajectory is available. The legacy experimental endpoint uses the low-false-alarm model; fuel remains disabled in readiness-v2.

## Saved Artifacts

All accepted artifacts are under `models/readiness/`. Machine-readable results are stored in `reports/metrics/readiness_v2_retraining.json`.

Reproduce the complete retraining run with:

```powershell
.\.venv\Scripts\python.exe -m src.retrain_readiness
```

## API

- `POST /api/v2/predict/engine`
- `POST /api/v2/predict/battery`
- `POST /api/v2/predict/hydraulic`
- `POST /api/v2/predict/landing-gear`
- `GET /api/v2/readiness`

The v2 endpoints expose interval/confidence information, input-support diagnostics, and an accepted/abstained decision. No v2 fuel prediction route is provided.

## Remaining Evidence Required

Real-aircraft readiness still requires independent aircraft or aircraft-representative test data, time/fleet-separated evaluation, verified maintenance ground truth, environmental and sensor-shift tests, prospective shadow operation, human-factors review, and the applicable aviation assurance process.
