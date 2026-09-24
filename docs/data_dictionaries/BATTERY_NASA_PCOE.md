# NASA PCoE Li-Ion Battery Data Dictionary

## Local Dataset Form

Location: `data/raw/battery/cleaned_dataset/`

The supplied dataset is a cleaned CSV conversion containing one metadata table and one measurement CSV per charge, discharge, or impedance test. It is not the original NASA MATLAB archive. The converter, cleaning steps, version, source URL, and license still need to be recorded.

## Metadata Columns

| Column | Normalized type | Meaning |
|---|---|---|
| `type` | string | Charge, discharge, or impedance experiment |
| `start_time` | datetime | Test start time parsed from the six-value NASA date vector |
| `ambient_temperature` | integer | Test ambient temperature |
| `battery_id` | string | Battery/cell identifier |
| `test_id` | integer | Test index within an experiment sequence |
| `uid` | integer | Globally unique record identifier |
| `filename` | string | Measurement CSV referenced by the record |
| `Capacity` | float/nullable | Discharge capacity when provided |
| `Re` | complex/nullable | Estimated electrolyte resistance for impedance tests |
| `Rct` | complex/nullable | Estimated charge-transfer resistance for impedance tests |

The cleaned metadata uses `[]` as a missing-value placeholder. The loader converts it to a proper missing value. Some `Re` and `Rct` values are complex and must not be coerced directly to float.

## Charge Measurement Columns

| Column | Meaning |
|---|---|
| `Voltage_measured` | Measured battery terminal voltage |
| `Current_measured` | Measured battery current |
| `Temperature_measured` | Measured battery temperature |
| `Current_charge` | Charger current |
| `Voltage_charge` | Charger voltage |
| `Time` | Elapsed time within the test |

## Discharge Measurement Columns

| Column | Meaning |
|---|---|
| `Voltage_measured` | Measured battery terminal voltage |
| `Current_measured` | Measured battery current |
| `Temperature_measured` | Measured battery temperature |
| `Current_load` | Applied load current |
| `Voltage_load` | Load voltage |
| `Time` | Elapsed time within the test |

## Impedance Measurement Columns

All impedance measurement columns contain complex values. Some cleaned CSV rows contain blank impedance fields; the loader preserves these as complex missing values for later missing-data analysis.

| Column | Meaning |
|---|---|
| `Sense_current` | Complex sensed current |
| `Battery_current` | Complex battery current |
| `Current_ratio` | Complex sense-to-battery current ratio |
| `Battery_impedance` | Complex battery impedance |
| `Rectified_Impedance` | Complex rectified impedance |

## Initial Modeling Boundary

SOH modeling begins with discharge records that contain positive capacity. The source documentation describes a rated capacity of 2.0 Ah, so:

```text
SOH (%) = measured discharge capacity / 2.0 Ah * 100
```

The chronological `discharge_cycle` is defined independently within each battery.

### Documented EOL thresholds

| Batteries | Source stopping rule |
|---|---|
| B0005, B0006, B0007, B0018 | 1.4 Ah (30% fade) |
| B0033, B0034, B0036 | 1.6 Ah (20% fade) |
| B0038, B0039, B0040 | 1.6 Ah (20% fade) |
| B0041-B0048 | 1.4 Ah (30% fade) |
| B0053-B0056 | 1.4 Ah (30% fade) |

B0049-B0052 ended after experiment-control software failure, so their final records are not treated as battery EOL. The available READMEs for B0025-B0032 do not state an EOL capacity. Those groups receive SOH labels when capacity is valid but no RUL labels.

For documented-threshold batteries that begin above the threshold and later cross it, `rul_cycles` counts discharge cycles until the first observed positive capacity at or below that threshold. If a threshold is never observed, RUL remains missing (`right_censored`). Batteries whose first valid capacity is already at or below their experiment threshold are marked `starts_at_or_below_threshold` and receive no RUL label because a degradation countdown is not observed.

`rul_training_eligible` is true only for positive-capacity records from an observed-EOL battery on or before its first threshold crossing. Post-EOL records are excluded from direct RUL training to prevent repeated zero-RUL rows from dominating the target.
