# UCI Hydraulic Systems Data Dictionary

## Observation Unit

One row represents one 60-second load cycle of the hydraulic test rig. All 17
sensor files and `profile.txt` contain 2,205 rows in the same cycle order.
`cycle_id` is a derived one-based row identifier; it is not a model input.

## Raw Sensor Files

| Sensor | Physical quantity | Unit | Sampling rate | Samples per cycle |
|---|---|---|---:|---:|
| `PS1`-`PS6` | Pressure | bar | 100 Hz | 6,000 |
| `EPS1` | Motor power | W | 100 Hz | 6,000 |
| `FS1`-`FS2` | Volume flow | l/min | 10 Hz | 600 |
| `TS1`-`TS4` | Temperature | degrees C | 1 Hz | 60 |
| `VS1` | Vibration | mm/s | 1 Hz | 60 |
| `CE` | Virtual cooling efficiency | percent | 1 Hz | 60 |
| `CP` | Virtual cooling power | kW | 1 Hz | 60 |
| `SE` | Efficiency factor | percent | 1 Hz | 60 |

Each tab-delimited file is a numeric matrix. Rows align by load cycle and
columns are chronological samples inside that cycle. The loader rejects an
incorrect row count, sample count, nonnumeric value, missing value, or infinity.

## Condition Targets

| Processed column | Meaning | Labels |
|---|---|---|
| `cooler_condition_percent` | Cooler efficiency condition | 3, 20, 100 |
| `valve_condition_percent` | Valve switching condition | 73, 80, 90, 100 |
| `pump_leakage_severity` | Internal pump leakage | 0, 1, 2 |
| `accumulator_pressure_bar` | Hydraulic accumulator condition | 90, 100, 115, 130 |
| `stable_flag` | Whether static conditions may not yet have been reached | 0, 1 |

The source defines `stable_flag = 0` as stable and `stable_flag = 1` as
potentially unstable. It is retained as data-quality context and must not be
used as a predictor when evaluating the other four condition targets.

Condition meanings:

- Cooler: 100 full efficiency, 20 reduced efficiency, 3 near-total failure.
- Valve: 100 optimal, 90 small lag, 80 severe lag, 73 near-total failure.
- Pump: 0 no leakage, 1 weak leakage, 2 severe leakage.
- Accumulator: 130 optimal, 115 slightly reduced, 100 severely reduced,
  90 near-total failure.

## Processed Features

For each sensor, `data/processed/hydraulic/cycle_features.csv` contains seven
statistics calculated independently inside the current cycle:

| Suffix | Definition |
|---|---|
| `_mean` | Arithmetic mean |
| `_std` | Population standard deviation |
| `_min` | Minimum sample |
| `_max` | Maximum sample |
| `_range` | Maximum minus minimum |
| `_rms` | Root mean square |
| `_slope` | Least-squares change over normalized cycle time |

This produces 119 sensor features plus `cycle_id` and five target/context
columns, for 125 columns total. The raw waveform files remain unchanged.

## Modeling Rules

- Exclude `cycle_id` and all five label columns from input features.
- Fit imputation, scaling, selection, and model parameters on training data only.
- Do not randomly mix immediately adjacent cycles without testing for temporal
  leakage; the source describes target values as degradation processes.
- Report results for stable cycles and separately audit potentially unstable
  cycles.
- Treat model output as experimental decision support, not a certified
  maintenance diagnosis.
