/**
 * Simulated fleet data layer.
 *
 * Everything here is SIMULATED demonstration data. generateFleet() stands in
 * for a fleet REST endpoint and tickFleet() stands in for a telemetry stream;
 * neither is connected to an aircraft or to the trained models.
 *
 * Generation takes a random-number source so the first render is seeded and
 * deterministic: the server and the browser then produce the same fleet and
 * React hydrates without a mismatch. Live jitter afterwards uses Math.random.
 */
import type { Aircraft, AircraftStatus, ComponentType, FleetComponent, Risk, Rng, Sensor, SensorDef, TrendPoint } from "./types.ts";

export const COMPONENT_DEFS: Record<ComponentType, { sensors: SensorDef[] }> = {
  Engine: {
    sensors: [
      { key: "temperature", label: "Temperature", unit: "°C", range: [550, 950] },
      { key: "vibration", label: "Vibration", unit: "mm/s", range: [0.5, 12] },
      { key: "pressure", label: "Pressure", unit: "psi", range: [180, 420] },
      { key: "rpm", label: "RPM", unit: "rpm", range: [8000, 15000] },
    ],
  },
  "Landing Gear": {
    sensors: [
      { key: "strutPressure", label: "Strut Pressure", unit: "psi", range: [800, 1600] },
      { key: "brakeTemp", label: "Brake Temp", unit: "°C", range: [80, 400] },
      { key: "tirePressure", label: "Tire Pressure", unit: "psi", range: [180, 220] },
      { key: "shockAbsorb", label: "Shock Absorption", unit: "%", range: [60, 100] },
    ],
  },
  Hydraulic: {
    sensors: [
      { key: "fluidPressure", label: "Fluid Pressure", unit: "psi", range: [2800, 3200] },
      { key: "fluidTemp", label: "Fluid Temp", unit: "°C", range: [40, 110] },
      { key: "flowRate", label: "Flow Rate", unit: "L/min", range: [10, 45] },
      { key: "contamination", label: "Contamination", unit: "ppm", range: [0, 25] },
    ],
  },
  Electrical: {
    sensors: [
      { key: "voltage", label: "Voltage", unit: "V", range: [110, 130] },
      { key: "current", label: "Current", unit: "A", range: [5, 60] },
      { key: "batteryHealth", label: "Battery Health", unit: "%", range: [40, 100] },
      { key: "load", label: "System Load", unit: "%", range: [10, 95] },
    ],
  },
  Fuel: {
    sensors: [
      { key: "flowRate", label: "Flow Rate", unit: "L/h", range: [800, 2600] },
      { key: "tankPressure", label: "Tank Pressure", unit: "psi", range: [12, 30] },
      { key: "temperature", label: "Temperature", unit: "°C", range: [-10, 45] },
      { key: "contamination", label: "Contamination", unit: "ppm", range: [0, 20] },
    ],
  },
};

export const COMPONENT_TYPES = Object.keys(COMPONENT_DEFS) as ComponentType[];
const AIRCRAFT_TYPES = ["Boeing 737-800", "Airbus A320neo", "Boeing 777-300ER", "Airbus A350-900", "Boeing 787-9", "Embraer E190"];
const AIRLINE_CODES = ["AA", "DL", "UA", "SW", "BA", "LH", "EK", "QF", "AF"];

export const RECOMMENDATION: Record<Risk, string> = {
  High: "Inspect Immediately",
  Medium: "Monitor Closely",
  Low: "No Action Required",
};

export function slugOf(type: ComponentType): string {
  return type.toLowerCase().replace(/\s+/g, "-");
}

export function typeFromSlug(slug: string): ComponentType | undefined {
  return COMPONENT_TYPES.find((t) => slugOf(t) === slug);
}

/** Small, fast, seedable PRNG (mulberry32). */
export function seededRng(seed: number): Rng {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const clamp = (v: number, min: number, max: number) => Math.max(min, Math.min(max, v));

export function riskFromRUL(rul: number): Risk {
  if (rul <= 30) return "High";
  if (rul <= 150) return "Medium";
  return "Low";
}

function makeTools(rng: Rng) {
  const rand = (min: number, max: number) => rng() * (max - min) + min;
  const randInt = (min: number, max: number) => Math.floor(rand(min, max + 1));
  return { rand, randInt };
}

function healthForRisk(risk: Risk, randInt: (a: number, b: number) => number): number {
  if (risk === "High") return randInt(12, 42);
  if (risk === "Medium") return randInt(45, 76);
  return randInt(80, 99);
}

function buildTrend(rng: Rng, endValue: number, points: number, volatility: number): TrendPoint[] {
  const { rand } = makeTools(rng);
  const drift = rand(-volatility, volatility);
  const start = clamp(endValue - drift * points, 0, 100);
  const out: TrendPoint[] = [];
  for (let i = 0; i < points; i++) {
    const t = i / (points - 1);
    const base = start + (endValue - start) * t;
    out.push({ cycle: i, value: Math.round(clamp(base + rand(-volatility, volatility), 0, 100)) });
  }
  out[out.length - 1].value = Math.round(endValue);
  return out;
}

function buildRULTrend(rng: Rng, endRUL: number, points: number): TrendPoint[] {
  const { rand, randInt } = makeTools(rng);
  const start = endRUL + randInt(20, 80);
  const out: TrendPoint[] = [];
  for (let i = 0; i < points; i++) {
    const t = i / (points - 1);
    const val = start + (endRUL - start) * t + rand(-4, 4);
    out.push({ cycle: i, value: Math.max(0, Math.round(val)) });
  }
  out[out.length - 1].value = endRUL;
  return out;
}

function makeComponent(rng: Rng, type: ComponentType): FleetComponent {
  const { rand, randInt } = makeTools(rng);
  const rul = randInt(4, 300);
  const risk = riskFromRUL(rul);
  const health = healthForRisk(risk, randInt);
  const failureProbability = risk === "High" ? randInt(55, 92) : risk === "Medium" ? randInt(18, 48) : randInt(1, 15);
  const volatility = risk === "High" ? 9 : risk === "Medium" ? 5 : 2;

  const sensors: Sensor[] = COMPONENT_DEFS[type].sensors.map((s) => {
    const [lo, hi] = s.range;
    const skew = risk === "High" ? rand(0.7, 1.15) : risk === "Medium" ? rand(0.4, 0.85) : rand(0.15, 0.55);
    const value = lo + (hi - lo) * clamp(skew, 0, 1.15);
    return { ...s, value: Math.round(value * 10) / 10, trend: buildTrend(rng, clamp(skew * 100, 0, 100), 16, volatility) };
  });

  return {
    type,
    slug: slugOf(type),
    health,
    rul,
    risk,
    priority: risk,
    recommendation: RECOMMENDATION[risk],
    failureProbability,
    healthTrend: buildTrend(rng, health, 20, volatility),
    rulTrend: buildRULTrend(rng, rul, 20),
    sensors,
  };
}

export function aircraftStatus(components: FleetComponent[]): AircraftStatus {
  if (components.some((c) => c.risk === "High")) return "Critical";
  if (components.some((c) => c.risk === "Medium")) return "Warning";
  return "Healthy";
}

const average = (values: number[]) => Math.round(values.reduce((a, v) => a + v, 0) / Math.max(values.length, 1));

export function generateFleet(rng: Rng, count = 9): Aircraft[] {
  const { randInt } = makeTools(rng);
  return Array.from({ length: count }, (_, i) => {
    const components = COMPONENT_TYPES.map((type) => makeComponent(rng, type));
    return {
      id: `AC-${1000 + i}`,
      tail: `N${randInt(100, 999)}${AIRLINE_CODES[randInt(0, AIRLINE_CODES.length - 1)]}`,
      model: AIRCRAFT_TYPES[randInt(0, AIRCRAFT_TYPES.length - 1)],
      status: aircraftStatus(components),
      overallHealth: average(components.map((c) => c.health)),
      flightHours: randInt(1200, 48000),
      components,
    };
  });
}

/** One simulated telemetry tick: jitter health and sensors, wear RUL down. */
export function tickFleet(prev: Aircraft[], rng: Rng = Math.random): Aircraft[] {
  const { rand } = makeTools(rng);
  return prev.map((ac) => {
    const components = ac.components.map((c) => {
      const jitter = c.risk === "High" ? 3 : c.risk === "Medium" ? 1.5 : 0.5;
      const health = Math.round(clamp(c.health + rand(-jitter, jitter * 0.6), 3, 99));
      const rul = Math.max(0, Math.round(c.rul - rand(0, 0.4)));
      const risk = riskFromRUL(rul);
      return {
        ...c,
        health,
        rul,
        risk,
        priority: risk,
        recommendation: RECOMMENDATION[risk],
        sensors: c.sensors.map((s) => ({
          ...s,
          value: Math.round((s.value + rand(-1, 1) * (s.range[1] - s.range[0]) * 0.01) * 10) / 10,
        })),
      };
    });
    return { ...ac, components, status: aircraftStatus(components), overallHealth: average(components.map((c) => c.health)) };
  });
}

/** Element-wise mean of equally long trend series (fleet-level trend lines). */
export function meanTrend(series: TrendPoint[][]): TrendPoint[] {
  if (!series.length) return [];
  const length = Math.min(...series.map((s) => s.length));
  return Array.from({ length }, (_, i) => ({
    cycle: i,
    value: Math.round((series.reduce((a, s) => a + s[i].value, 0) / series.length) * 10) / 10,
  }));
}
