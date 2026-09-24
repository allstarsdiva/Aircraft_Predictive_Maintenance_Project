# Raw Dataset Inventory

Inventory date: 2026-08-21

## Status Summary

| System | Location | Files | Approx. size | Validation status |
|---|---|---:|---:|---|
| Engine | `data/raw/engine/` | 14 | 43.25 MB | Complete C-MAPSS FD001-FD004 train/test/RUL package found |
| Battery | `data/raw/battery/` | 7,575 | 558.87 MB | Metadata and all referenced measurement CSVs found |
| Hydraulic | `data/raw/hydraulic/` | 20 | 530.50 MB | All documented sensor matrices, targets, and documentation found |
| Fuel system | `data/raw/fuel_system/` | 5 | 0.12 MB | Five scenario CSVs validated; provenance, paper, and license recorded |
| Landing gear | `data/raw/landing_gear/` | 1 | 0.13 MB | Schema, source, license, labels, and local checksum recorded; source/local mass-range mismatch remains |

The avionics subsystem is excluded from the project; its raw and processed data directories have been removed.

## Engine: NASA C-MAPSS

### Package contents

- Four subsets: FD001, FD002, FD003, and FD004.
- One training file, one test file, and one test-RUL file per subset.
- Source `readme.txt` and the damage-propagation reference PDF.

### Observed dimensions

| Subset | Conditions | Fault modes | Train rows | Train engines | Test rows | Test engines | RUL labels |
|---|---:|---:|---:|---:|---:|---:|---:|
| FD001 | 1 | 1 | 20,631 | 100 | 13,096 | 100 | 100 |
| FD002 | 6 | 1 | 53,759 | 260 | 33,991 | 259 | 259 |
| FD003 | 1 | 2 | 24,720 | 100 | 16,596 | 100 | 100 |
| FD004 | 6 | 2 | 61,249 | 249 | 41,214 | 248 | 248 |
| **Total** | - | - | **160,359** | **709** | **104,897** | **707** | **707** |

The observed FD004 unit counts are 249 train and 248 test. These counts should be used instead of the reversed counts printed near the top of the included readme.

### Row schema

Each train/test row has 26 whitespace-separated columns:

1. `unit_id`
2. `cycle`
3. `operational_setting_1`
4. `operational_setting_2`
5. `operational_setting_3`
6. `sensor_1`
7. `sensor_2`
8. `sensor_3`
9. `sensor_4`
10. `sensor_5`
11. `sensor_6`
12. `sensor_7`
13. `sensor_8`
14. `sensor_9`
15. `sensor_10`
16. `sensor_11`
17. `sensor_12`
18. `sensor_13`
19. `sensor_14`
20. `sensor_15`
21. `sensor_16`
22. `sensor_17`
23. `sensor_18`
24. `sensor_19`
25. `sensor_20`
26. `sensor_21`

Each `RUL_FD00x.txt` row gives the additional operating cycles remaining after the final observed row for the corresponding test engine.

## Battery: NASA PCoE Li-Ion Battery Data

### Observed dimensions

- Metadata rows: 7,565.
- Measurement CSV files: 7,565.
- Referenced files missing from disk: 0.
- Unique battery IDs: 34.
- Test records: 2,815 charge, 2,794 discharge, and 1,956 impedance.

### Metadata schema

| Column | Meaning |
|---|---|
| `type` | Charge, discharge, or impedance test |
| `start_time` | Recorded start-time vector |
| `ambient_temperature` | Ambient temperature for the test |
| `battery_id` | Battery identifier |
| `test_id` | Test number within a battery experiment |
| `uid` | Unique measurement-record identifier |
| `filename` | Referenced measurement CSV filename |
| `Capacity` | Measured discharge capacity when applicable |
| `Re` | Estimated electrolyte resistance when applicable |
| `Rct` | Estimated charge-transfer resistance when applicable |

### Measurement schemas

- Charge CSV: `Voltage_measured`, `Current_measured`, `Temperature_measured`, `Current_charge`, `Voltage_charge`, `Time`.
- Discharge CSV: `Voltage_measured`, `Current_measured`, `Temperature_measured`, `Current_load`, `Voltage_load`, `Time`.
- Impedance CSV: `Sense_current`, `Battery_current`, `Current_ratio`, `Battery_impedance`, `Rectified_Impedance`.

The supplied folder is named `cleaned_dataset`, indicating a CSV conversion or cleaned derivative of the original NASA MATLAB package. Its exact converter/source and transformation history must be documented before treating it as provenance-equivalent to the original archive.

## Hydraulic: UCI Hydraulic Systems

### Observed dimensions

- Labeled operating cycles: 2,205.
- Target columns per cycle: 5.
- Raw sensor matrices: 17.
- Documentation files: `description.txt` and `documentation.txt`.

### Sensor matrices

| Prefix | Measurement | Unit | Sampling rate |
|---|---|---|---:|
| `PS1`-`PS6` | Pressure | bar | 100 Hz |
| `EPS1` | Motor power | W | 100 Hz |
| `FS1`-`FS2` | Volume flow | l/min | 10 Hz |
| `TS1`-`TS4` | Temperature | degrees C | 1 Hz |
| `VS1` | Vibration | mm/s | 1 Hz |
| `CE` | Cooling efficiency (virtual) | percent | 1 Hz |
| `CP` | Cooling power (virtual) | kW | 1 Hz |
| `SE` | Efficiency factor | percent | 1 Hz |

Each sensor-matrix row is one 60-second load cycle; columns are samples within that cycle.

### Target schema (`profile.txt`)

| Column | Target | Observed labels |
|---:|---|---|
| 1 | Cooler condition (%) | 3, 20, 100 |
| 2 | Valve condition (%) | 73, 80, 90, 100 |
| 3 | Internal pump leakage | 0, 1, 2 |
| 4 | Hydraulic accumulator pressure (bar) | 90, 100, 115, 130 |
| 5 | Stable-condition flag | 0, 1 |

## Fuel System

### Observed dimensions

| File / inferred label | Rows | Columns |
|---|---:|---:|
| `Scenario_Normal.csv` | 171 | 8 |
| `Scenario_One.csv` | 171 | 8 |
| `Scenario_Two.csv` | 171 | 8 |
| `Scenario_Three.csv` | 171 | 8 |
| `Scenario_Four.csv` | 171 | 8 |
| **Total** | **855** | **8** |

All files share these columns: `FTL`, `CTL`, `FTF`, `FTV_S`, `CLF`, `CLV_S`, `FTT`, and `CRTT`. The public dataset record confirms one normal and four abnormal hypothetical scenarios. Sensor meanings, provenance, DOI, reference paper, and CC BY-SA 4.0 Kaggle license are documented in `docs/data_dictionaries/FUEL_SYSTEM_AFDS.md`. Individual abnormal fault names and several flow/rate units are not published, so the project retains neutral scenario identifiers.

## Landing Gear

### Observed dimensions

- Rows: 1,500.
- Columns: 9.
- Fault classes: 4.

### Schema

| Column | Documented interpretation |
|---|---|
| `RunID` | Unique simulation-run identifier; excluded from model inputs |
| `Max_Deflection` | Peak shock-strut compression during impact (m) |
| `Max_Velocity` | Maximum vertical strut-piston velocity (m/s) |
| `Settling_Time` | Time for oscillations to decay within 2% of steady state (s) |
| `Mass` | Simulated aircraft landing mass (kg) |
| `K_Stiffness` | Gas-spring stiffness coefficient (latent physics parameter) |
| `B_Damping` | Hydraulic damping coefficient (latent physics parameter) |
| `Fault_Code` | Ground-truth fault-class target |
| `RUL` | Remaining Useful Life percentage (100=new, 0=failure) |

### Fault distribution

| Fault code | Rows |
|---:|---:|
| 0 - Normal operation | 300 |
| 1 - Nitrogen gas leak | 500 |
| 2 - Worn seal | 500 |
| 3 - Early structural degradation | 200 |

The Kaggle source describes synthetic events from a MATLAB Simscape Multibody digital twin of a Dornier 228 oleo-pneumatic shock strut and lists a CC BY-SA 4.0 license. Full definitions and the local SHA-256 checksum are recorded in `docs/data_dictionaries/LANDING_GEAR_DIGITAL_TWIN.md`. The local mass range (about 1,001-4,998 kg) conflicts with the current data-card claim (3,000-6,400 kg), so the precise source archive/version still requires confirmation.

## Outstanding Dataset Documentation

- Record a source URL, access date, citation, license, and archive/version identifier for every dataset.
- Record the battery CSV conversion/cleaning source and transformations.
- Obtain authoritative individual fault-event names for fuel Scenarios One-Four if the creators release them.
- Resolve the landing-gear source/local mass-range discrepancy and retain its exact Kaggle archive/version metadata.
- Generate SHA-256 checksums after the raw-data folders are finalized.
