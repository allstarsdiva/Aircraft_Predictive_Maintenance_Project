# Hydraulic EDA and Classification Baselines

## Scope

The experiment predicts four UCI hydraulic component conditions from 119
cycle-level waveform statistics. Primary training and validation use the 1,449
cycles for which the source marks operating conditions as stable. The 756
potentially unstable cycles are retained only for a separate descriptive audit.

## EDA Findings

- No missing, non-finite, or duplicate feature rows were found.
- `ps2_min`, `ps3_min`, and `se_min` are constant in the full processed table;
  the training-fitted variance filter removes constant inputs.
- Cooler condition has strong associations with cooling, flow, motor-power,
  and temperature measurements.
- Pump leakage is strongly associated with `SE` efficiency and `FS1` flow.
- Valve condition is most associated with within-cycle slopes, especially
  `SE`, `PS2`, and `FS1`.
- Accumulator condition is harder to separate; its strongest univariate
  associations are much weaker than those of cooler and pump targets.

Figures are stored in `reports/figures/hydraulic/`, and machine-readable EDA
results are in `reports/metrics/hydraulic_eda.json`.

## Leakage-Aware Validation

The stable cycles form 144 distinct combinations of cooler, valve, pump, and
accumulator conditions. Five-fold stratified grouped validation keeps every
complete condition combination entirely inside one fold. This prevents cycles
with the same experimental condition vector from being divided between model
training and validation.

The compared algorithms are:

- Most-frequent class reference
- Class-balanced Logistic Regression
- Class-balanced Random Forest
- Class-balanced Extra Trees

Model selection uses grouped out-of-fold macro F1 so each class contributes
equally.

## Selected Models

| Target | Selected algorithm | Accuracy | Balanced accuracy | Macro F1 |
|---|---|---:|---:|---:|
| Cooler condition | Logistic Regression | 1.000 | 1.000 | 1.000 |
| Valve condition | Logistic Regression | 0.840 | 0.839 | 0.839 |
| Pump leakage | Extra Trees | 0.991 | 0.991 | 0.991 |
| Accumulator pressure | Random Forest | 0.886 | 0.886 | 0.886 |

Random Forest and Extra Trees also achieved perfect cooler scores. Logistic
Regression was retained because it ties on the selection metric while being the
simpler model.

## Potentially Unstable Cycle Audit

Models fitted on all stable cycles were also applied to the 756 cycles marked
potentially unstable. These measurements are transition/robustness diagnostics,
not independent validation results.

| Target | Descriptive accuracy on potentially unstable cycles |
|---|---:|
| Cooler condition | 0.960 |
| Valve condition | 0.458 |
| Pump leakage | 0.999 |
| Accumulator pressure | 0.598 |

The large valve and accumulator degradation confirms that predictions during
unsettled operation require an explicit warning or abstention rule in the final
application.

## Saved Artifacts

One preprocessing-and-model bundle is saved for each target under
`models/hydraulic/`. Detailed candidate metrics, per-class scores, grouped
out-of-fold predictions, and unstable-cycle diagnostics are stored under
`reports/metrics/`.

Reproduce the work with:

```powershell
.\.venv\Scripts\python.exe -m src.eda_hydraulic
.\.venv\Scripts\python.exe -m src.train_hydraulic
```

These classifiers are experimental decision-support models and are not
certified hydraulic diagnostic systems.
