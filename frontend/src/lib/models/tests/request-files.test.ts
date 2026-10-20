// Ported from tests/frontend_request_files.test.mjs (TypeScript, run with `npm test`).
import test from 'node:test';
import assert from 'node:assert/strict';
import { csvToPayload, payloadToCsv } from '../request-files.ts';
import type { JsonObject } from '../types.ts';
import { BATCH_COMPONENT_KEYS, makeComponentBundle, parseComponentBundle } from '../batch-requests.ts';

const engine = {
  subset: 'FD001',
  records: [{ unit_id: 7, cycle: 1, sensor_1: 12.5 }, { unit_id: 7, cycle: 2, sensor_1: 13.5 }],
};
const battery = {
  battery_id: 'B0005', discharge_cycle: 4, ambient_temperature: 24,
  samples: [{ voltage_measured: 3.2, current_measured: -1, temperature_measured: 24, current_load: -1, voltage_load: 3, time: 0 },
    { voltage_measured: 3.1, current_measured: -1, temperature_measured: 25, current_load: -1, voltage_load: 3, time: 1 }],
};
const hydraulic = { cycle_id: 12, operating_condition_stable: true, features: { ps1_mean: 3.2, fs1_std: 0.4 } };
const landing = { max_deflection: 12.5, max_velocity: 4.2, settling_time: 2.5, mass: 3000 };
const fuel = { samples: [{ FTL: 1, CTL: 2, FTF: 3, FTV_S: 4, CLF: 5, CLV_S: 6, FTT: 7, CRTT: 8 },
  { FTL: 1.1, CTL: 2.1, FTF: 3.1, FTV_S: 4.1, CLF: 5.1, CLV_S: 6.1, FTT: 7.1, CRTT: 8.1 }] };

for (const [name, payload] of [['engine', engine], ['battery', battery], ['hydraulic', hydraulic], ['landing-gear', landing], ['fuel-system', fuel]] as [string, JsonObject][]) {
  test(`${name} CSV example round-trips to the complete API payload`, () => {
    assert.deepEqual(csvToPayload(name, payloadToCsv(name, payload), payload), payload);
  });
}

test('CSV importer rejects missing columns instead of silently dropping values', () => {
  assert.throws(() => csvToPayload('fuel-system', 'FTL,CTL\n1,2', fuel), /columns do not match/);
});

test('CSV importer rejects inconsistent battery metadata', () => {
  const csv = payloadToCsv('battery', battery).replace('B0005,4,24,3.1', 'B0006,4,24,3.1');
  assert.throws(() => csvToPayload('battery', csv, battery), /must stay the same/);
});

test('CSV importer validates one-row subsystem inputs and boolean values', () => {
  assert.throws(() => csvToPayload('landing-gear', `${payloadToCsv('landing-gear', landing)}\r\n${payloadToCsv('landing-gear', landing).split('\r\n')[1]}`, landing), /exactly one event/);
  assert.throws(() => csvToPayload('hydraulic', payloadToCsv('hydraulic', hydraulic).replace(',true,', ',maybe,'), hydraulic), /must be true, false/);
});

test('all-components bundle accepts exactly five object payloads', () => {
  const expected = Object.fromEntries(BATCH_COMPONENT_KEYS.map(key => [key, { sample: key }]));
  assert.deepEqual(parseComponentBundle(JSON.stringify(expected)), expected);
  assert.deepEqual(makeComponentBundle(Object.fromEntries(BATCH_COMPONENT_KEYS.map(key => [key, { payload: expected[key] }]))), expected);
});

test('all-components bundle rejects missing keys, extra keys, and non-object requests', () => {
  assert.throws(() => parseComponentBundle('{"engine":{}}'), /exactly the five subsystem sections/);
  const extra = Object.fromEntries([...BATCH_COMPONENT_KEYS.map(key => [key, {}]), ['avionics', {}]]);
  assert.throws(() => parseComponentBundle(JSON.stringify(extra)), /Unexpected: avionics/);
  const invalid = Object.fromEntries(BATCH_COMPONENT_KEYS.map(key => [key, {}]));
  invalid.battery = [];
  assert.throws(() => parseComponentBundle(JSON.stringify(invalid)), /battery section must contain one JSON request object/);
});
