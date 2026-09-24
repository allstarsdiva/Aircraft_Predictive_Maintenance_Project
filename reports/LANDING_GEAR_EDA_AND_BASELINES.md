# Landing-Gear EDA and Baseline Models

## Outcome

Landing-gear exploratory analysis, multiclass fault classification, and RUL-percentage regression are complete for the checksummed local synthetic dataset. Five-fold stratified out-of-fold predictions were used so every reported score comes from a model that did not train on that event.

## Exploratory Findings

- The table contains 1,500 events, six candidate numeric inputs, four fault classes, and no missing or duplicate feature rows.
- Fault classes are not equally represented: 300 normal, 500 nitrogen gas leak, 500 worn seal, and 200 early structural degradation.
- Maximum velocity has the strongest linear relationship with RUL (`r = -0.950`), followed by settling time (`r = -0.815`).
- Mass has almost no linear relationship with RUL (`r = -0.007`).
- `RunID` changes in contiguous class blocks and was excluded from every model.
- RUL values for normal events occupy 85.01%-99.93%; gas-leak and worn-seal events span 0%-99.8%; early structural-degradation events occupy 70%-84.93%.

## Evaluation Design

The same deterministic five-fold split, stratified by fault code with random state 42, was used for all candidates. Preprocessing was fitted separately inside each training fold. Two input views were compared:

1. **Observable:** maximum deflection, maximum velocity, settling time, and mass.
2. **Physics-assisted:** the four observable inputs plus latent stiffness and damping coefficients.

The physics-assisted view is useful for the supplied digital twin but requires stiffness and damping estimates that are not confirmed as direct aircraft sensor measurements.

## Fault Classification

| Feature set | Model | Accuracy | Balanced accuracy | Macro F1 |
|---|---|---:|---:|---:|
| Observable | Most-frequent baseline | 33.33% | 25.00% | 12.50% |
| Observable | Logistic Regression | 84.73% | 87.37% | 84.05% |
| Observable | Random Forest | 95.47% | 95.64% | 95.42% |
| Observable | Extra Trees | 94.40% | 95.59% | 94.39% |
| Physics-assisted | Logistic Regression | 90.13% | 91.37% | 89.33% |
| Physics-assisted | **Random Forest** | **99.80%** | **99.67%** | **99.76%** |
| Physics-assisted | Extra Trees | 97.67% | 97.80% | 97.55% |

The selected Random Forest made three out-of-fold errors among 1,500 events: one normal event and two early-structural-degradation events were classified as worn-seal events. Nitrogen gas leak and worn seal each achieved 100% recall in this synthetic evaluation.

Saved bundle: `models/landing_gear/fault_classifier_bundle.joblib`

## RUL Regression

| Feature set | Model | MAE (percentage points) | RMSE | R-squared |
|---|---|---:|---:|---:|
| Observable | Median baseline | 24.80 | 31.27 | -0.114 |
| Observable | Linear Regression | 5.53 | 7.22 | 0.941 |
| Observable | Random Forest | 1.34 | 2.64 | 0.992 |
| Observable | Extra Trees | 1.69 | 2.84 | 0.991 |
| Physics-assisted | Linear Regression | 4.93 | 6.85 | 0.946 |
| Physics-assisted | **Random Forest** | **1.08** | **2.38** | **0.994** |
| Physics-assisted | Extra Trees | 1.30 | 2.49 | 0.993 |

The selected Random Forest's mean absolute error is 1.08 RUL percentage points. Error is uneven across classes: normal events have a 3.87-point MAE, while gas-leak, worn-seal, and early-structural-degradation events have MAEs of 0.26, 0.34, and 0.79 points respectively. The largest individual out-of-fold error is 22.39 points.

Saved bundle: `models/landing_gear/rul_regressor_bundle.joblib`

## Artifacts

- `reports/metrics/landing_gear_eda.json`
- `reports/metrics/landing_gear_baselines.json`
- `reports/metrics/landing_gear_oof_predictions.csv`
- `reports/figures/landing_gear/landing_gear_feature_distributions.png`
- `reports/figures/landing_gear/landing_gear_rul_relationships.png`
- `reports/figures/landing_gear/landing_gear_fault_confusion_matrix.png`
- `reports/figures/landing_gear/landing_gear_rul_actual_vs_predicted.png`

## Interpretation Limits

These results measure interpolation among independent events created by one synthetic generator. They do not demonstrate generalization to another simulator, a physical test rig, or an operational aircraft. The near-perfect physics-assisted classification likely reflects strong synthetic generation rules and access to latent stiffness/damping parameters. The observable-only Random Forest result (95.47% accuracy) is the more relevant reference when those latent estimates are unavailable. Outputs are research decision support and must not replace engineering inspection or certified maintenance procedures.
