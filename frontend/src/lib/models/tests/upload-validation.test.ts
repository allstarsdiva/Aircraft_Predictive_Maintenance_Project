// Ported from tests/frontend_upload_validation.test.mjs (TypeScript, run with `npm test`).
import test from 'node:test';
import assert from 'node:assert/strict';
import { friendlyApiError, parseJsonObject } from '../upload-validation.ts';

test('valid JSON request uploads parse as a single object', () => {
  const payload = { samples: [{ voltage_measured: 3.8, time: 0 }] };
  assert.deepEqual(parseJsonObject(JSON.stringify(payload)), payload);
});

test('malformed JSON gives a correction users can follow', () => {
  assert.throws(() => parseJsonObject('{"samples": [}'), (error: Error) => {
    assert.match(error.message, /not valid JSON/i);
    assert.match(error.message, /commas, quotes, and brackets/i);
    return true;
  });
});

test('arrays, scalars, and null are rejected with an example-file hint', () => {
  for (const text of ['[]', '42', 'null', '"payload"']) {
    assert.throws(() => parseJsonObject(text), /one JSON object.*downloaded JSON example/i);
  }
});

test('missing request fields are named and the example file is recommended', () => {
  const message = friendlyApiError(422, [{
    loc: ['body', 'samples', 0, 'voltage_measured'], msg: 'Field required',
  }]);
  assert.match(message, /samples\.0\.voltage_measured: is required/);
  assert.match(message, /downloaded JSON example/i);
});

test('unusual values surface the field rule and point users to unit guidance', () => {
  const message = friendlyApiError(422, [{
    loc: ['body', 'mass'], msg: 'Input should be greater than 0',
  }]);
  assert.match(message, /mass: Input should be greater than 0/);
  assert.match(message, /type, range, and units/i);
});

test('hydraulic feature-name errors include the exact fields to compare', () => {
  const message = friendlyApiError(422, { missing_features: ['ps1_mean'], unexpected_features: ['pressure'] });
  assert.match(message, /Missing: ps1_mean/);
  assert.match(message, /Unexpected: pressure/);
  assert.match(message, /downloaded JSON example/i);
});
