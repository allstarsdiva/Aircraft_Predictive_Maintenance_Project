// Ported from tests/frontend_result_guidance.test.mjs (TypeScript, run with `npm test`).
import test from 'node:test';
import assert from 'node:assert/strict';
import { getResultGuidance } from '../result-guidance.ts';

const components = ['engine', 'battery', 'hydraulic', 'landing-gear', 'fuel-system'];

test('every subsystem result explains the metric and its interpretation limit', () => {
  for (const component of components) {
    const guidance = getResultGuidance(component);
    assert.ok(guidance?.meaning, `${component} needs a plain-language meaning`);
    assert.ok(guidance?.caveat, `${component} needs an interpretation limit`);
    assert.ok(guidance.meaning.length <= 220, `${component} meaning should stay concise`);
    assert.ok(guidance.caveat.length <= 240, `${component} caveat should stay concise`);
  }
});

test('guidance defines units/scale without promising operational readiness', () => {
  assert.match(getResultGuidance('engine')!.meaning, /cycles/i);
  assert.match(getResultGuidance('battery')!.meaning, /percentage.*cycles/i);
  assert.match(getResultGuidance('landing-gear')!.meaning, /RUL percentage/i);
  assert.match(getResultGuidance('fuel-system')!.meaning, /scaled difference, not a probability/i);
  assert.match(getResultGuidance('hydraulic')!.caveat, /not a confirmed aircraft-system diagnosis/i);
});

test('unknown subsystem keys do not invent result guidance', () => {
  assert.equal(getResultGuidance('avionics'), null);
});
