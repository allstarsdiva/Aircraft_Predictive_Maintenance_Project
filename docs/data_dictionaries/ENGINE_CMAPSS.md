# NASA C-MAPSS Engine Data Dictionary

## Prediction Target

The engine pipeline predicts Remaining Useful Life (`rul`) in operating cycles.

- Training RUL: `maximum cycle for the unit - current cycle`.
- Test terminal RUL: supplied by the corresponding `RUL_FD00x.txt` row.
- Earlier test-row RUL: `terminal RUL + final observed cycle - current cycle`.

RUL is zero at the recorded failure cycle in the training trajectories.

## Train and Test Columns

| Position | Project name | Type | Description |
|---:|---|---|---|
| 1 | `unit_id` | integer | Engine/unit trajectory identifier within a subset |
| 2 | `cycle` | integer | Operating-cycle number within the engine trajectory |
| 3 | `operational_setting_1` | numeric | First simulated operating-condition setting |
| 4 | `operational_setting_2` | numeric | Second simulated operating-condition setting |
| 5 | `operational_setting_3` | numeric | Third simulated operating-condition setting |
| 6-26 | `sensor_1`-`sensor_21` | numeric | Twenty-one simulated sensor measurements |

The source package does not assign physical names or units to the anonymized operating settings and sensor columns. The application must retain these neutral names and must not relabel them as temperature, vibration, pressure, or RPM without authoritative evidence.

## Subsets

| Subset | Operating conditions | Fault modes |
|---|---:|---:|
| FD001 | 1 | 1 (HPC degradation) |
| FD002 | 6 | 1 (HPC degradation) |
| FD003 | 1 | 2 (HPC and fan degradation) |
| FD004 | 6 | 2 (HPC and fan degradation) |

## Leakage Boundary

An engine/unit must remain entirely within one model partition. Rows from the same unit cannot be randomly divided across training and validation sets. Scaling, feature selection, and other fitted transformations must use training engines only.

## Frontend Mapping

The frontend can display:

- Component type: `Engine`.
- RUL: model prediction in cycles.
- Risk: derived from documented demonstration thresholds.
- Health score: a separately defined, transparent transformation or model output.
- Sensor cards: selected anonymized `sensor_n` values and trends.

The frontend's current simulated Engine labels—Temperature, Vibration, Pressure, and RPM—do not correspond to named C-MAPSS columns and will be replaced when live data is connected.
