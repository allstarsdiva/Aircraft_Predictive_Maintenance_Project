const SECTION_LABELS = {
  fleet: 'Fleet',
  maintenance: 'Maintenance',
};

export function createSectionResultsFile({ section, variant, entries, createdAt = new Date().toISOString() }) {
  if (!SECTION_LABELS[section]) throw new Error(`Unsupported results section: ${section}`);
  if (!Array.isArray(entries)) throw new Error('Results entries must be an array.');
  return {
    report_schema: 'aircraft-predictive-maintenance-section-results/v1',
    section,
    section_title: SECTION_LABELS[section],
    created_at_utc: createdAt,
    example_type: variant,
    data_scope: section === 'fleet'
      ? 'Saved-model checks on normal dataset examples. This is not live fleet telemetry or aircraft-level health.'
      : 'Saved-model checks on challenge dataset examples. These are not work orders, maintenance diagnoses, or approved severity levels.',
    component_count: entries.length,
    results: entries.map(entry => ({
      component: entry.component,
      component_title: entry.title,
      attention_level: entry.level,
      review_reason: entry.reason,
      dataset_example: entry.source || null,
      model: entry.model || null,
      result_summary: entry.summary || null,
      prediction: entry.prediction || null,
      dataset_reference_labels: entry.referenceLabels || null,
      error: entry.error || null,
    })),
    limitations: [
      'No raw sensor request values are included in this report.',
      'Dataset example predictions are demonstrations and do not establish real-aircraft performance.',
      'Reference labels are sample metadata and do not make this replay an independent evaluation.',
      'Fuel anomaly results are experimental; model flags require engineering review.',
    ],
  };
}
