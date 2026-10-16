import test from 'node:test';
import assert from 'node:assert/strict';
import { createSectionResultsFile } from '../frontend-src/sectionResults.js';

test('Fleet export keeps model checks distinct from live aircraft health', () => {
  const report = createSectionResultsFile({
    section: 'fleet', variant: 'normal', createdAt: '2026-10-03T10:00:00.000Z',
    entries: [{ component: 'engine', title: 'Engine', level: 'Monitor', reason: 'No model alert',
      source: 'NASA FD001 test example', model: 'engine-rul', summary: 'RUL 42 cycles',
      prediction: { rul: { value: 42, unit: 'cycles' } }, referenceLabels: { rul_cycles: 40 } }],
  });
  assert.equal(report.section_title, 'Fleet');
  assert.match(report.data_scope, /not live fleet telemetry/);
  assert.equal(report.results[0].prediction.rul.value, 42);
  assert.deepEqual(report.results[0].dataset_reference_labels, { rul_cycles: 40 });
});

test('Maintenance export includes unavailable components and avoids raw example payloads', () => {
  const report = createSectionResultsFile({
    section: 'maintenance', variant: 'challenge',
    entries: [
      { component: 'fuel-system', title: 'Fuel system', level: 'Critical', reason: 'Review flags',
        source: 'Scenario one', model: 'experimental-envelope', summary: '3 samples flagged',
        prediction: { flagged_samples: 3 }, referenceLabels: { scenario_is_abnormal: true } },
      { component: 'battery', title: 'Battery', level: 'Unavailable', reason: 'Backend unavailable', error: 'Model unavailable' },
    ],
  });
  assert.match(report.data_scope, /not work orders/);
  assert.equal(report.component_count, 2);
  assert.equal(report.results[1].attention_level, 'Unavailable');
  assert.equal(JSON.stringify(report).includes('voltage_measured'), false);
});

test('section exporter rejects unknown sections and malformed entries', () => {
  assert.throws(() => createSectionResultsFile({ section: 'telemetry', entries: [] }), /Unsupported results section/);
  assert.throws(() => createSectionResultsFile({ section: 'fleet', entries: {} }), /must be an array/);
});
