# NASA Battery Degradation EDA

Notebook: `notebooks/02_battery_degradation_eda.ipynb`

Analysis date: 2026-08-21

## Chronological Discharge Table

| Item | Result |
|---|---:|
| Discharge records | 2,794 |
| Batteries | 34 |
| Positive-capacity/SOH records | 2,750 |
| Missing capacity | 25 |
| Zero capacity | 19 |
| Median observed SOH | 71.53% |
| Minimum observed SOH | 1.63% |
| Maximum observed SOH | 132.01% |

SOH uses the documented 2.0 Ah rating. Values above 100% are retained because measured capacity can exceed the nominal rating under some test conditions. Extremely low values are also retained and flagged for modeling because NASA's source notes unresolved low-capacity runs in several experiment groups.

## RUL Label Audit

| Battery-level status | Batteries |
|---|---:|
| Observed above-threshold-to-EOL trajectory | 9 |
| Starts at or below documented threshold | 12 |
| Right-censored before threshold | 1 |
| No documented EOL threshold | 12 |

The nine direct-RUL batteries are B0005, B0006, B0018, B0042, B0043, B0044, B0046, B0047, and B0048.

Their first observed EOL cycles are:

| Battery | First documented-EOL cycle |
|---|---:|
| B0047 | 10 |
| B0048 | 12 |
| B0046 | 17 |
| B0042 | 42 |
| B0043 | 42 |
| B0044 | 42 |
| B0018 | 97 |
| B0006 | 109 |
| B0005 | 125 |

Although 1,020 rows belong to observed-EOL batteries, only **493 positive-capacity rows on or before the first threshold crossing** are marked `rul_training_eligible`. Post-EOL observations are excluded from direct RUL training.

## Important Quality Findings

- B0052 has only four positive-capacity records and cannot support a reliable degradation trajectory by itself.
- There are 195 SOH observations below 20%, reflecting documented anomalously low-capacity runs.
- Four observations exceed 110% SOH.
- Experiment groups use different temperatures, currents, load profiles, voltage cutoffs, and stopping rules.
- B0049-B0052 ended after software failure, not documented battery EOL.
- B0025-B0032 have no documented EOL threshold in the supplied READMEs.

## Saved Outputs

- Processed table: `data/processed/battery/discharge_cycles.csv`.
- Capacity-label quality: `reports/figures/battery/battery_capacity_label_quality.png`.
- Capacity trajectories: `reports/figures/battery/battery_capacity_trajectories.png`.
- SOH and RUL status: `reports/figures/battery/battery_soh_and_rul_status.png`.
- Observed EOL cycles: `reports/figures/battery/battery_observed_eol_cycles.png`.

## Modeling Decision

The next battery prototype should prioritize **SOH regression**, because it has 2,750 labeled observations across all 34 batteries. Data splitting must be grouped by battery ID.

Direct RUL regression will be treated as a secondary, higher-uncertainty experiment using only 493 eligible records across nine complete trajectories. Censored and protocol-incompatible records must not receive invented RUL labels.

## Verification

- Seven notebook code cells execute successfully.
- The processed discharge table is reproducible from raw metadata.
- Chronology, SOH validity, censoring, and pre-EOL eligibility are tested.
- **38 automated tests pass.**
