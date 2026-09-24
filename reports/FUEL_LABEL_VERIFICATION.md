# Fuel label verification

Checked: 2026-09-10

## Result: partially verified; exact row-level onset remains unresolved

The public sources support normal/abnormal **scenario** labels. They do not
provide a verified mapping from paper time intervals to rows in our extracted
CSV files. No training labels, raw/processed data, model weights, or release
pointer were changed. No author was contacted.

## Authoritative sources checked

The user confirmed on 2026-09-10 that the local files were downloaded from the
creator's Kaggle page linked below. This resolves the reported download platform,
not the exact archive version or missing row-level fault annotations. The DOI
discrepancy concerns related source records, not uncertainty about the user's
stated download source. No IEEE re-download is required merely to establish that.

- [IEEE DataPort dataset](https://ieee-dataport.org/open-access/aircraft-fuel-distribution-system):
  explicitly describes one normal and four abnormal scenarios. The public page
  lists a ZIP, but downloading it and messaging the author require login.
- [Creator's Kaggle data card](https://www.kaggle.com/datasets/kooaslansefat/aircraft-fuel-distribution-system):
  indexed description corroborates the five-part scenario structure. Direct page
  extraction returned no readable body; the indexed description was available.
- [York dataset record](https://pure.york.ac.uk/portal/en/datasets/aircraft-fuel-distribution-system/):
  links the source paper and records DOI `10.21227/15gk-s444`.
- [Original paper, Case Study Evaluation, Figures 11-16](https://doi.org/10.1109/access.2019.2941566):
  relevant narrative was available through indexed publisher text. Direct DOI,
  repository PDF, and ResearchGate PDF retrieval failed; a full PDF was not
  downloaded or visually checked.

## What the paper establishes

| Paper scenario | Reported timing/behavior, not CSV ground truth |
|---|---|
| 1 | Fuel-starvation observation and anomaly detection after interval 13; FTF and FTV-S change. |
| 2 | FTT starts falling after interval 10, reaches about -45 C after 12; flow then decreases. |
| 3 | More severe cooling to about -65 C; the narrative describes loss of engine fuel flow. |
| 4 | Central-tank delivery stops after interval 12, with CLF/CLV-S showing no flow. |

Source: [Gheraibia et al., 2019](https://doi.org/10.1109/access.2019.2941566).
The reported detection time is not necessarily the injected fault's start time.

## Local-file audit

`data/raw/fuel_system/` contains only the five CSVs: 171 rows and eight sensor
columns each. There is no timestamp, row-level label, event log, or README in
that folder. The loader creates `is_abnormal` from the filename and generates
one-based `sample_index`; neither field comes from an annotation column.

Descriptive means over each file's last 30 rows:

| Local scenario | FTT | CLF | CLV_S | FTF | FTV_S |
|---|---:|---:|---:|---:|---:|
| normal | -20.009 | 2.481 | 2.505 | 5.033 | 4.976 |
| one | -20.023 | 2.494 | 2.498 | 1.756 | 1.768 |
| two | -44.965 | 2.491 | 2.482 | 1.756 | 1.751 |
| three | -64.436 | 2.497 | 2.506 | 1.732 | 1.775 |
| four | -19.995 | -0.015 | 0.018 | 1.768 | 1.747 |

These patterns are broadly consistent with the numbered narratives, an inference
only. They cannot certify file identity, event boundaries, physical units, or
individual failed components. In particular, do not assume exact agreement with
every paper plot or statement from these summary statistics.

## Provenance discrepancy

The IEEE open-access record displays DOI `10.21227/c0kw-c455`, while York records
`10.21227/15gk-s444`. Both have the same dataset title and creators. Their archive
equivalence/version relationship has not been established. Preserve both references
and ask which one corresponds to these files; do not silently replace one DOI
with the other. Local SHA-256 values are recorded in
`docs/data_dictionaries/FUEL_ONSET_VERIFICATION.csv` for future matching.

## Rules until confirmation arrives

- Keep existing `is_abnormal` explicitly described as a scenario-membership label.
- Leave onset, recovery, and sampling-period fields unknown. Blank manifest fields
  mean unknown, never zero or healthy. The manifest is evidence tracking, not a
  new training-label source.
- Do not translate interval 13 into row 13, 130, or 131 without a verified time axis.
- Do not use model alert positions, visual change points, or desired accuracy to
  create ground-truth labels. Any provisional expert annotation must be separately
  identified and cannot be advertised as creator-confirmed ground truth.

## Next action requiring external information

Use the ready-to-send draft in `docs/FUEL_DATA_AUTHOR_REQUEST.md` via the IEEE
dataset page's author-message option, or provide an original annotation file or
generator from the creators. Confirmation must specify the exact file version,
row-index convention, time mapping, onset/recovery per event, and label semantics.
After receipt, verify hashes and annotation bounds before creating a versioned
row-level label table and rerunning evaluation.

Step status: public-source audit completed; obtaining exact annotations is still
pending. Accuracy is unchanged. Overall implementation remains 90% estimated.
