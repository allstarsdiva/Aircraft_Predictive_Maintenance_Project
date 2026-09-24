# Hydraulic Dataset Validation and Preprocessing

## Outcome

The extracted UCI Hydraulic Systems dataset is complete and internally aligned.
All 17 documented sensor matrices contain 2,205 finite numeric rows, and every
row corresponds to the same 60-second cycle in the five-column target profile.

## Validation Results

- Operating cycles: 2,205
- Raw sensor matrices: 17
- Missing or non-finite sensor values: 0
- Stable cycles (`stable_flag = 0`): 1,449
- Potentially unstable cycles (`stable_flag = 1`): 756
- Sensor sample dimensions: correct at 60, 600, or 6,000 per cycle according
  to the documented sampling rate

### Target Distribution

| Target | Class counts |
|---|---|
| Cooler condition | 3: 732; 20: 732; 100: 741 |
| Valve condition | 73: 360; 80: 360; 90: 360; 100: 1,125 |
| Pump leakage | 0: 1,221; 1: 492; 2: 492 |
| Accumulator pressure | 90: 808; 100: 399; 115: 399; 130: 599 |

## Processed Output

Each waveform is summarized per cycle with mean, standard deviation, minimum,
maximum, range, root mean square, and normalized-time slope. The resulting
`data/processed/hydraulic/cycle_features.csv` contains:

- 2,205 rows
- 119 model feature columns
- Five target/context columns
- One cycle identifier
- 125 columns total

The transformation is reproducible with:

```powershell
.\.venv\Scripts\python.exe -m src.preprocess_hydraulic
```

Machine-readable validation evidence is stored in
`reports/metrics/hydraulic_data_validation.json`.

## Modeling Decision

The next stage will compare classification baselines for all four component
targets. Validation must account for cycle order because adjacent operating
cycles may be highly similar. The stability flag will be used for filtering and
robustness analysis, not as an input that could leak operating-state context.
