# Fuel-System Dataset Validation and Preprocessing

## Reverification - 2026-09-25

The current five raw scenario CSVs pass the fuel loader tests. The full test suite
passes 196 tests. Regenerating preprocessing in a temporary directory produced
855 rows whose columns and values exactly match the checked-in processed feature
table. `Scenario_Two.csv` has eight separate numeric sensor columns; its SHA-256
matches the fingerprint already recorded in `docs/data_dictionaries/FUEL_ONSET_VERIFICATION.csv`.

This confirms structural and preprocessing consistency only. It does not verify
the source archive version or provide row-level fault-onset labels. The existing
scenario-membership labels and model metrics are unchanged.

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
