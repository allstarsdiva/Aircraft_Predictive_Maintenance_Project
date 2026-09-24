# Battery capacity definition and transition review

Completed 2026-09-15 after resuming the interrupted review. No models, labels,
raw measurements, or processed training features were changed.

## Resolved: Capacity is not full-discharge throughput

NASA defines the dataset's Capacity field using discharge to 2.7 V, even though
some experiments continue below that voltage. Its stated EOL criterion is a
decline from 2 Ah to 1.4 Ah. These definitions are confirmed by the official
[NASA dataset description](https://data.nasa.gov/dataset/li-ion-battery-aging-datasets)
and the locally supplied experiment READMEs.

Our `charge_throughput_ah` feature integrates absolute measured current over the
entire recorded discharge. It is a different quantity, not an incorrectly named
copy of the source Capacity label. Neither field should silently replace the other.

We checked all 21 fitting-battery curves traced by the earlier diagnostic.
Integration through the first recorded sample at or below 2.7 V reproduced their
source capacities with maximum absolute difference 0.0000043842 Ah. This empirical
agreement resolves the apparent integration discrepancy in these inspected curves;
it does not verify every record in the converted dataset or its full provenance.

| Battery/cycle | Source Capacity | Integration through first sample <=2.7 V | Full-discharge throughput |
|---|---:|---:|---:|
| B0042 / 41 | 1.565595 Ah | 1.565597 Ah | 1.591754 Ah |
| B0042 / 42 | 0.070701 Ah | 0.070701 Ah | 1.163078 Ah |
| B0043 / 41 | 1.469474 Ah | 1.469474 Ah | 1.485577 Ah |
| B0043 / 42 | 0.057034 Ah | 0.057035 Ah | 0.077227 Ah |

The review also calculates a linearly interpolated crossing estimate. It is a
different numerical convention: for B0042 cycle 42 it gives 0.065163 Ah, whereas
the first-below-sample convention gives 0.070701 Ah. The latter matches the source.
Interpolation was not used to rewrite the labels. Four records fall marginally
outside the strict neighboring-sample bracket; their endpoint discrepancies are
still within the maximum tolerance above, not grounds for relabeling.

## Verified source notes and remaining uncertainty

The supplied `README_41_42_43_44.txt` describes nominal 4 C experiments with
1 A / 4 A loads, differing termination voltages, and a 1.4 Ah criterion. It also
notes that some very low-capacity runs had not been fully explained. The supplied
`README_45_46_47_48.txt` describes 4 C / 1 A experiments and carries the same
low-capacity caveat. The room-temperature README describes the B0005/B0006/B0007/
B0018 group and confirms its 1.4 Ah threshold and capacity-to-2.7 V convention.

The converted local B0042/B0043 histories contain 22 C observations followed by
4 C at the first threshold crossing. The available summaries do not explain
that earlier history in sufficient detail to verify the complete chronology.
No original `.mat` files were found under the project's raw battery directory,
and the CSV converter/transformation history remains undocumented.

The project's RUL labels use the first positive source Capacity at or below the
documented threshold. That first-crossing rule is a project labeling convention;
the source's broad EOL criterion does not by itself settle the treatment of every
temperature transition or subsequent capacity recovery.

Decision: keep the existing labels and threshold. Do not remove B0042/B0043,
substitute full throughput for Capacity, or redefine EOL merely to improve scores.
The numeric capacity mismatch no longer supports a claim of preprocessing error.
Original NASA records or verified conversion documentation are still needed
before authorizing a change to the temperature history or transition labels.

## Implementation and evidence

- Review code: `src/battery_cutoff_review.py`.
- Evidence: `reports/metrics/rul_fitting_diagnostics_20260914/battery_cutoff_review.json`.
- The evidence records input hashes, all 21 results, interpolated and sample-based
  cutoffs, source capacities, and unresolved provenance flags.
- Tests: `tests/test_cutoff_and_engine_protocol.py`; they check first crossings,
  voltage rebound, absent crossings, invalid curves, and engine selection guards.
- The review only used fitting-battery curves. It did not inspect new audit or
  official engine predictions, tune a model, or change a source file.

## Next justified step

A separately versioned 2.7 V capacity feature, derived only from each completed
discharge, is now justified for a future battery experiment. Preserve the existing
whole-discharge throughput as a distinct feature and validate across held-out
batteries. This review does not yet add that feature to training or deployment.
Verify original-record provenance before changing any labels or operating-history
interpretation.

Verification: 17 new tests passed; full project suite 188 passed and 2 known
fuel-data failures (24.85 seconds). The malformed fuel CSV was left untouched.
Retained model performance and overall 90% implementation estimate are unchanged.
