# Landing-Gear Digital-Twin Data Dictionary

Source: [Aircraft Landing Gear Digital Twin Dataset: PdM/SHM on Kaggle](https://www.kaggle.com/datasets/mohammedbellosani/aircraft-landing-gear-digital-twin-datasetpdmshm)

Accessed: 2026-09-02  
Creator: Mohammed Bello Sani  
License shown on source page: CC BY-SA 4.0  
Local file: `data/raw/landing_gear/LandingGear_Balanced_Dataset.csv`  
Local SHA-256: `05b21f70387dae522312ae6f3ed8a24c0dacbdc83fdab34feb601052fd387724`

## Scope and Generation

The source describes physics-informed synthetic landing events produced by a MATLAB Simscape Multibody digital twin of a Dornier 228 oleo-pneumatic landing-gear shock strut. Each row is one simulated landing event. This dataset is suitable for research demonstrations; it is not operational fleet evidence or a certified maintenance source.

## Raw Schema

| Column | Meaning | Unit / values | Project role |
|---|---|---|---|
| `RunID` | Unique simulation-run identifier | Integer | Identifier only; excluded from model inputs |
| `Max_Deflection` | Peak shock-strut compression during impact | m | Feature |
| `Max_Velocity` | Maximum vertical strut-piston velocity | m/s | Feature |
| `Settling_Time` | Time for oscillations to decay within 2% of steady state | s | Feature |
| `Mass` | Simulated aircraft landing mass | kg | Feature |
| `K_Stiffness` | Gas-spring stiffness coefficient | Latent physics parameter; unit not stated | Feature |
| `B_Damping` | Hydraulic damping coefficient | Latent physics parameter; unit not stated | Feature |
| `Fault_Code` | Ground-truth fault class | 0-3 | Classification target |
| `RUL` | Ground-truth remaining useful life | %, 100=new and 0=failure | Regression target |

## Fault Codes

| Code | Meaning | Local rows |
|---:|---|---:|
| 0 | Normal operation | 300 |
| 1 | Nitrogen gas leak (reduced stiffness) | 500 |
| 2 | Worn seal (reduced damping) | 500 |
| 3 | Early structural degradation | 200 |

## Processed Schema

`data/processed/landing_gear/validated_runs.csv` uses snake-case names, preserves the six physical features and two targets, and adds:

- `is_fault`: 0 for normal and 1 for fault codes 1-3.
- `fault_name`: documented human-readable fault label.

No scaling, imputation, or target-derived feature engineering is applied to the complete table. Any scaler or feature transform must be fitted only on a model-training split. `run_id`, `fault_code`, `fault_name`, `is_fault`, and `rul_percent` are not inputs to the multiclass model; this avoids identifier and target leakage.

## Validation Findings and Limitations

- The local file contains 1,500 rows, nine columns, no missing/non-finite values, no duplicate rows, and no duplicate run identifiers.
- `RunID` is ordered in four contiguous fault blocks (1-300, 301-800, 801-1300, and 1301-1500). It must never be used as a predictive feature.
- The local mass range is approximately 1,001-4,998 kg. The currently published Kaggle description instead states 3,000-6,400 kg. This unresolved source/local-version discrepancy must be reported and the exact downloaded archive version retained before publication-quality claims.
- The class distribution is not equal despite the filename containing “Balanced”; stratified evaluation and macro-averaged classification metrics are required.
- Rows are synthetic independent landing events, not longitudinal measurements of one physical gear. RUL is a supplied percentage target, not observed time-to-failure from an in-service aircraft.

## Suggested Citation

The source page requests citation of Sani, M. B., and Uhiah, O. (2026), “Physics-Informed Digital Twin for Predictive Maintenance of Aircraft Landing Gear Systems,” listed there as under review/in press. Verify the final bibliographic record before a formal submission.
