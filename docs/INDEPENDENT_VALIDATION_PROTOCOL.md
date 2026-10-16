# Independent validation protocol

## Current gate

The current release is research-only and has **no independent real-aircraft validation**. This protocol prepares a safe evaluation intake; it does not make existing rows independent by changing their random split or assigning them a new name. The empty file `independent_validation_manifest_template.csv` is intentionally only a header. Do not fill it with invented or inferred values.

## Intake requirements

Create one manifest row per independent group (for example, an engine, battery, hydraulic operating-condition/run group, complete fuel mission, or landing-gear event/run group). Record source/version, terms of access, acquisition time, raw-file SHA-256, and the label-generation method. Keep original raw files immutable and record who verified the labels.

Use two disjoint partitions: `external_calibration` for any planned uncertainty/calibration assessment and `frozen_test` for final scoring. Assign entire independent groups before inspecting outcomes. A frozen-test group must not have been used for model fitting, feature/model selection, thresholds, or calibration. Do not use same-trajectory rows as separate groups.

## Subsystem-specific minimum evidence

| System | What an independent group should represent | Required outcomes / metadata |
|---|---|---|
| Engine | A separate engine trajectory, preferably from a distinct operating regime/source | ordered sensor cycles, failure/censoring definition, terminal RUL source, regime and unit metadata |
| Battery | A separate physical battery through observed end-of-life for RUL assessment | cell identity, cycle and temperature history, capacity measurement procedure, EOL definition |
| Hydraulic | A separate run/condition combination, including unstable conditions | source condition labels, run/cycle grouping, operating regime and sensor-to-cycle alignment |
| Fuel | A complete mission/scenario, not random rows from a known trajectory | multiple normal missions and abnormal cases, timestamp/sample interval, independently verified fault type and onset/recovery labels |
| Landing gear | A distinct test/run from a documented, versioned digital twin or physical test program | source archive/version, mass/load regime, fault and RUL label definitions, run identity |

These are evidence requirements for this project, not claims of aircraft certification. Never describe a digital-twin or rig holdout as real-aircraft validation.

## Gate check

Run the metadata-only intake check from the repository root:

```powershell
.\.venv\Scripts\python.exe -m src.check_independent_validation docs/independent_validation_manifest_template.csv
```

The blank template should remain blocked. A structural pass only means the manifest is complete and internally consistent; it does not verify a source, labels, sufficient sample size, or model performance. Domain review and a frozen, group-disjoint evaluation are still required. The frozen test must remain untouched until all model and threshold decisions are locked.

## Reporting

Report task-appropriate metrics, group counts, uncertainty/coverage and abstention rates, subgroup performance, and data limitations. Do not collapse all five systems into one accuracy number. Preserve the release/model hashes and the final prediction-level evaluation records so the results can be reproduced.
