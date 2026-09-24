# Landing-Gear Dataset Validation and Preparation

## Result

The extracted digital-twin CSV is structurally valid and has been converted into a reproducible, leakage-safe processed table. The loader enforces the documented schema, numeric values, unique positive run identifiers, supported fault codes, positive physical features, and RUL percentages from 0 to 100.

## Local Audit

- 1,500 simulated landing events and nine raw columns.
- Zero missing or non-finite values.
- Zero duplicate rows and zero duplicate `RunID` values.
- Fault counts: normal 300, nitrogen gas leak 500, worn seal 500, early structural degradation 200.
- RUL range: 0.0%-99.93%.
- Six model inputs: maximum deflection, maximum velocity, settling time, mass, stiffness, and damping.

## Leakage Controls

`RunID` exactly follows fault-class blocks in this file, so it is retained only for traceability and explicitly excluded from model features. Fault labels, the derived binary fault flag, the human-readable label, and RUL are also excluded from model inputs. No global scaling was performed; transformations will be learned from training data only during the modeling step.

## Source Consistency Warning

The local mass values range from about 1,001 to 4,998 kg, but the current Kaggle data card states a range of 3,000-6,400 kg. The title, columns, fault definitions, and row concept match the published data card, but the precise local archive/version cannot yet be proven. Results must therefore be described as applying to this checksummed local file, and the mismatch must remain visible until the original downloaded archive metadata is retained or the creator clarifies it.

## Modeling Implications

- Use stratified splits and macro F1 because class counts differ.
- Compare simple and tree-based classifiers on the six permitted inputs.
- Evaluate RUL separately and report MAE, RMSE, and R-squared.
- Inspect whether synthetic generation rules make classification or RUL prediction unrealistically easy.
- Treat performance as within-dataset feasibility, not evidence of real-aircraft generalization.
