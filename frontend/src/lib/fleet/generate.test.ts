import test from "node:test";
import assert from "node:assert/strict";
import { COMPONENT_TYPES, generateFleet, riskFromRUL, seededRng, slugOf, tickFleet, typeFromSlug } from "./generate.ts";

test("seeded fleet generation is deterministic (server and browser render the same fleet)", () => {
  assert.deepEqual(generateFleet(seededRng(42)), generateFleet(seededRng(42)));
  assert.notDeepEqual(generateFleet(seededRng(42)), generateFleet(seededRng(43)));
});

test("every aircraft carries exactly the five project subsystems and no avionics", () => {
  for (const aircraft of generateFleet(seededRng(7))) {
    assert.deepEqual(aircraft.components.map((c) => c.type), COMPONENT_TYPES);
    assert.equal(aircraft.components.some((c) => (c.type as string) === "Avionics"), false);
  }
});

test("risk bands follow the RUL thresholds and a tick keeps values in range", () => {
  assert.equal(riskFromRUL(30), "High");
  assert.equal(riskFromRUL(31), "Medium");
  assert.equal(riskFromRUL(151), "Low");
  const next = tickFleet(generateFleet(seededRng(1)), seededRng(2));
  for (const c of next.flatMap((a) => a.components)) {
    assert.ok(c.health >= 3 && c.health <= 99);
    assert.ok(c.rul >= 0);
    assert.equal(c.risk, riskFromRUL(c.rul));
  }
});

test("component slugs round-trip", () => {
  for (const type of COMPONENT_TYPES) assert.equal(typeFromSlug(slugOf(type)), type);
});
