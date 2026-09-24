# Aircraft Fuel Distribution System Data Dictionary

## Provenance

- Dataset: Aircraft Fuel Distribution System
- Creators: Koorosh Aslansefat, Youcef Gheraibia, Sohag Kabir, Ioannis Sorokos, and Yiannis Papadopoulos
- DOI recorded by York: `10.21227/15gk-s444`
- DOI on the IEEE open-access record: `10.21227/c0kw-c455`; archive/version equivalence remains unverified (checked 2026-09-10).
- Public dataset record: https://pure.york.ac.uk/portal/en/datasets/aircraft-fuel-distribution-system/
- Kaggle distribution: https://www.kaggle.com/datasets/kooaslansefat/aircraft-fuel-distribution-system
- Local download source: the Kaggle distribution above, confirmed by the user on 2026-09-10. Exact downloaded version/archive has not been supplied; equivalence to IEEE archives is not assumed.
- Kaggle license: CC BY-SA 4.0
- Reference paper: Gheraibia et al., "Safety + AI: A Novel Approach to Update Safety Models Using Artificial Intelligence," IEEE Access 7 (2019), DOI `10.1109/ACCESS.2019.2941566`
- Access date: 2026-08-21

The authors describe the aircraft fuel-distribution example and its data as
hypothetical and illustrative. It is not operational fleet telemetry.

## Observation Unit

One CSV row is one ordered sensor snapshot inside a scenario trajectory. Each
of the five files contains 171 rows. The source does not publish the elapsed
time or sampling interval, so `sample_index` is an order identifier rather than
a physical timestamp.

## Sensors

| Column | Meaning supported by the reference paper | Unit status |
|---|---|---|
| `FTL` | Front tank level sensor | Percentage is indicated by the paper narrative |
| `CTL` | Central tank level sensor; the paper uses `CRTL` | Percentage is indicated by the paper narrative |
| `FTF` | Flow sensor on the front/port-engine fuel path | Not published with CSVs |
| `FTV_S` | Sensor on the front-tank valve | Rate unit not published with CSVs |
| `CLF` | Flow sensor on the central-line fuel path | Not published with CSVs |
| `CLV_S` | Sensor on the central-line valve | Rate unit not published with CSVs |
| `FTT` | Front tank temperature sensor | Degrees Celsius in the paper narrative |
| `CRTT` | Central reservation tank temperature sensor | Degrees Celsius in the paper narrative |

## Labels

| Processed column | Meaning |
|---|---|
| `scenario_id` | Neutral source label: `normal`, `one`, `two`, `three`, or `four` |
| `scenario_code` | Numeric encoding 0-4 in the same order |
| `is_abnormal` | 0 for the normal file and 1 for Scenarios One-Four |
| `sample_index` | One-based row order inside the source scenario |

The dataset page authoritatively states that it contains one normal and four
abnormal scenarios. A 2026-09-10 source audit found numbered scenario descriptions
and time-interval references in the associated paper. These are not a verified
mapping to exact CSV fault-start rows or individual component-failure labels.
The local CSVs have no timestamp or row-level annotation columns, and the loader
assigns `is_abnormal` from scenario membership, not the active fault state per row.
Keep the neutral scenario identifiers and leave exact onset/recovery unknown.
See `reports/FUEL_LABEL_VERIFICATION.md` and the evidence-tracking manifest
`docs/data_dictionaries/FUEL_ONSET_VERIFICATION.csv`. Blank timing fields in that
manifest mean unknown; it is not a replacement training-label table.

## Causal Processed Features

For every sensor the processed table retains the raw measurement and adds:

- One-snapshot change: `_delta_1`
- Five-snapshot trailing mean: `_rolling_mean_5`
- Five-snapshot trailing population standard deviation: `_rolling_std_5`

All rolling operations reset at scenario boundaries and use only the current
and previous rows. This gives 32 model features and four identifiers/labels,
for 36 columns total.

## Validation Constraint

There is only one normal trajectory and four abnormal trajectories. A random
row split would put neighboring observations from the same source trajectory
into both training and validation and would exaggerate generalization. Model
results must use scenario-aware temporal blocks or one-class anomaly detection,
and must be described as within-dataset experimental evidence.
