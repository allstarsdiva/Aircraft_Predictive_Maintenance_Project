# Future telemetry and model monitoring

## Current state

There is no aircraft registry, authorized operational telemetry feed, or
operational maintenance-label pipeline in this project. Fleet and Maintenance
therefore use clearly labeled dataset replays; they do not show live aircraft
health. Do not substitute generated values, dashboard timers, or model examples
for incoming telemetry.

## Prerequisites before implementation

1. Obtain written authorization and document the source, access terms, retention
   limits, and privacy/security owner for any operational data.
2. Define stable aircraft/component identifiers (pseudonymous where possible),
   timestamps/time zones, sensor names and units, missing-value conventions,
   sampling intervals, and maintenance/fault label provenance.
3. Preserve immutable source records and a manifest containing collection
   period, data version, checksums, and label-generation/review process.
4. Freeze model release IDs and approved input schemas before comparing
   incoming data with development data.

## Monitoring workflow once authorized data exists

- Start with data-quality checks: schema, units, time order, gaps, duplicates,
  and impossible values. Reject or quarantine malformed records; never silently
  coerce them into predictions.
- Track input-support and distribution changes by subsystem and operating
  regime. Report the selected statistic, baseline window, current window,
  sample/group counts, and uncertainty; do not call a drift signal a fault.
- Measure predictive performance only after independently reviewed outcomes
  become available. Use component-appropriate metrics and group by complete
  engine, battery, mission, run, or landing event to avoid row leakage.
- Keep review alerts advisory. Thresholds require domain approval; no automated
  maintenance action, work-order creation, or aircraft clearance is in scope.
- Keep a versioned, access-controlled audit trail of source hashes, model
  release, quality checks, prediction, later verified outcome, and reviewer.

Until the prerequisites are met, the UI must continue to show that live fleet
health is unavailable. This plan is not an operational monitoring or
airworthiness approval.
