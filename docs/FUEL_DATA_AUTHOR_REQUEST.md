# Fuel dataset author request — draft, not sent

Use the author-message option on the
[IEEE DataPort dataset page](https://ieee-dataport.org/open-access/aircraft-fuel-distribution-system/).
It requires the user's account. No account access, email, or external message has
been attempted. Review this draft before sending.

## Subject

Request for fault-onset annotations and time mapping for Aircraft Fuel Distribution System dataset

## Message

Dear Dr. Aslansefat and co-authors,

I am using your Aircraft Fuel Distribution System dataset for an academic
predictive-maintenance project and want to evaluate online anomaly detection
without incorrectly assigning abnormal labels to healthy portions of a run.

I downloaded the dataset from your Kaggle distribution:
https://www.kaggle.com/datasets/kooaslansefat/aircraft-fuel-distribution-system

My extracted files are Scenario_Normal.csv, Scenario_One.csv, Scenario_Two.csv,
Scenario_Three.csv, and Scenario_Four.csv. Each contains 171 rows and the columns
FTL, CTL, FTF, FTV_S, CLF, CLV_S, FTT, and CRTT, with no timestamps or label columns.

Could you please clarify:

1. Do these filenames correspond directly to the numbered scenarios in your
   2019 Safety + AI paper? Which source archive/version should we cite?
2. How do CSV data rows map to the paper's time axis? Please specify start time,
   sampling interval, units, and whether indexing is zero-based or one-based.
3. For each abnormal file, what are the fault-injection/start and recovery/end
   rows? If multiple events or gradual degradation exist, could you provide their
   separate boundaries and explain whether these mark injection, observable
   degradation, or system failure?
4. Are rows before each event intended to be normal, or does the abnormal label
   deliberately describe the entire scenario rather than the current sensor state?
5. Are a ground-truth annotation file, event log, generator, or additional independent
   normal/fault runs available for academic use?
6. What is the relationship between dataset DOIs 10.21227/15gk-s444 and
   10.21227/c0kw-c455? Are their archives identical or different versions?

I can provide file checksums to identify the local copies precisely. I will retain
scenario-level labels and mark exact onset times unknown until confirmed.

Thank you for your guidance.

[Your name and institution]

## Suggested response format

One row per event with: source filename, file checksum/version, event/fault type,
onset data-row number, end data-row number (or continues through end of run),
indexing convention, time origin, sampling interval/unit, pre-event label,
and annotation/generator reference. Unknown fields may remain explicitly unknown.
