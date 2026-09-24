# C-MAPSS FD001 Preprocessing Report

Implementation: `src/preprocessing.py`

Validation date: 2026-08-21

## Pipeline Order

1. Load the validated FD001 training split.
2. Calculate RUL as each engine's final cycle minus its current cycle.
3. Cap baseline RUL at 125 cycles to reduce emphasis on the early-life plateau.
4. Add causal change and rolling features within each engine.
5. Split complete engines into training and validation partitions.
6. Fit zero-variance filtering on training engines only.
7. Fit standard scaling on training engines only.
8. Transform validation engines using the fitted training parameters.

## Split Results

| Partition | Engines | Rows |
|---|---:|---:|
| Training | 80 | 16,561 |
| Validation | 20 | 4,070 |

Engine overlap between partitions: **0**.

The split uses `GroupShuffleSplit` with `random_state=42`. The unit identifier is retained for partition auditing but is excluded from model features.

## Causal Features

The five sensors with the strongest exploratory RUL relationships receive these features:

- One-cycle change (`delta`).
- Rolling mean over 5 cycles.
- Rolling standard deviation over 5 cycles.
- Rolling mean over 10 cycles.
- Rolling standard deviation over 10 cycles.

Selected sensors: `sensor_11`, `sensor_4`, `sensor_12`, `sensor_7`, and `sensor_15`.

Every rolling window uses the current and previous cycles from the same engine. It does not use future cycles or values from another engine.

## Feature Filtering

The raw feature set contains cycle, three operating settings, 21 sensors, and 25 engineered trend features. Training-fitted zero-variance filtering removes:

- `operational_setting_3`
- `sensor_1`
- `sensor_5`
- `sensor_10`
- `sensor_16`
- `sensor_18`
- `sensor_19`

Retained model features: **43**.

## Scaling

`StandardScaler` is fitted after variance filtering using only the 80 training engines. Validation data is never used to calculate feature means, standard deviations, or retained columns.

## Validation

The automated suite verifies:

- Causal features reset at each engine boundary.
- Engine groups do not overlap across partitions.
- Constant measurements are removed.
- Training features are centered after scaling.
- Baseline targets stay between 0 and 125 cycles.
- The fitted preprocessing pipeline produces identical results after save/load.

Test result: **13 passed**.
