// Ported from tests/frontend_prediction_report.test.mjs (TypeScript, run with `npm test`).
import test from 'node:test';
import assert from 'node:assert/strict';
import { makePredictionReport, sha256Text } from '../prediction-report.ts';

test('prediction report contains a stable input digest and omits raw request data', async () => {
  const requestText = '{"records":[{"cycle":1,"sensor_2":42.5}]}';
  const report = await makePredictionReport({
    component: 'engine', title: 'Engine', releaseId: 'research-2026-10', requestText,
    inputSummary: '1 engine cycle | 2 input fields per reading', source: 'user supplied JSON',
    preflight: { schema_valid: true, review_required: false },
    prediction: { model: 'engine-rul', rul: { value: 12.4, unit: 'cycles' } },
  });
  assert.equal(report.input.sha256, await sha256Text(requestText));
  assert.equal(report.input.raw_sensor_values_included, false);
  assert.equal(JSON.stringify(report).includes('42.5'), false);
  assert.equal(report.model_release, 'research-2026-10');
  assert.equal(report.prediction.rul?.value, 12.4);
  assert.ok(Number.isFinite(Date.parse(report.created_at_utc)));
});

test('SHA-256 helper emits the standard lowercase hexadecimal digest', async () => {
  assert.equal(await sha256Text('abc'), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
});
