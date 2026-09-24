# Fuel-System Dataset Validation and Preprocessing

## Outcome

All five extracted Aircraft Fuel Distribution System CSV files pass structural
validation. The source, creators, reference paper, DOI, hypothetical nature,
and Kaggle license have been recorded. The individual abnormal scenario fault
names remain unpublished, so the pipeline uses neutral labels.

## Validation Results

- Scenario files: 5
- Rows per scenario: 171
- Total rows: 855
- Numeric sensor columns: 8
- Normal rows: 171
- Abnormal rows: 684
- Missing or non-finite values: 0
- Duplicate sensor snapshots: 0
- Mismatched schemas: 0

| Sensor | Observed minimum | Observed maximum |
|---|---:|---:|
| `FTL` | 21.480 | 100.227 |
| `CTL` | 31.954 | 103.584 |
| `FTF` | 0.789 | 5.338 |
| `FTV_S` | 0.796 | 5.310 |
| `CLF` | -0.307 | 2.809 |
| `CLV_S` | -0.313 | 2.776 |
| `FTT` | -65.420 | -19.103 |
| `CRTT` | -20.344 | -19.677 |

## Processed Output

`data/processed/fuel_system/scenario_features.csv` contains 855 rows and 36
columns. Eight raw measurements and 24 within-scenario causal changes/rolling
statistics provide 32 candidate model features. Scenario ID, scenario code,
sample order, and binary normal/abnormal label are retained separately.

Reproduce the output with:

```powershell
.\.venv\Scripts\python.exe -m src.preprocess_fuel
```

Detailed machine-readable validation evidence is stored in
`reports/metrics/fuel_system_data_validation.json`.

## Modeling Limitation

The dataset has only one normal trajectory. Consequently, an ordinary random
train/test split would measure recognition of nearby rows rather than
generalization to a new normal flight or simulation. The next experiment should
prioritize normal-only anomaly detection with blocked temporal evaluation and
state this limitation prominently.
