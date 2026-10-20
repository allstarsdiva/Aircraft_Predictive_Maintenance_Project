// Ported from tests/frontend_input_guidance.test.mjs (TypeScript, run with `npm test`).
import test from 'node:test';
import assert from 'node:assert/strict';
import { getInputUnitGuidance } from '../input-guidance.ts';

test('every prediction component has explicit unit guidance', () => {
  for (const component of ['engine', 'battery', 'hydraulic', 'landing-gear', 'fuel-system']) {
    assert.ok(getInputUnitGuidance(component).length >= 2, `${component} needs field/unit guidance`);
  }
});

test('unknown units stay explicit and known fuel overshoots are not told to clip', () => {
  const engine = getInputUnitGuidance('engine').join(' ').toLowerCase();
  const fuel = getInputUnitGuidance('fuel-system').join(' ').toLowerCase();
  assert.match(engine, /units are not provided/);
  assert.match(fuel, /not published/);
  assert.match(fuel, /do not clip/);
});
