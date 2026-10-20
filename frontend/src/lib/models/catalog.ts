import type { ComponentKey } from "./types.ts";

export interface ModelSystem {
  key: ComponentKey;
  title: string;
  subtitle: string;
  metric: string;
  endpoint: string;
  preflight: string;
}

/** The five trained subsystem models served by the FastAPI backend. */
export const MODEL_SYSTEMS: ModelSystem[] = [
  { key: "engine", title: "Engine", subtitle: "Remaining useful life", metric: "RUL", endpoint: "/api/v2/predict/engine", preflight: "/api/v2/preflight/engine" },
  { key: "battery", title: "Electrical / Battery", subtitle: "Health & remaining life", metric: "SOH + RUL", endpoint: "/api/v2/predict/battery", preflight: "/api/v2/preflight/battery" },
  { key: "hydraulic", title: "Hydraulic", subtitle: "Four condition checks", metric: "4 outputs", endpoint: "/api/v2/predict/hydraulic", preflight: "/api/v2/preflight/hydraulic" },
  { key: "landing-gear", title: "Landing gear", subtitle: "Fault & remaining life", metric: "Fault + RUL", endpoint: "/api/v2/predict/landing-gear", preflight: "/api/v2/preflight/landing-gear" },
  { key: "fuel-system", title: "Fuel system", subtitle: "Anomaly screening", metric: "Experimental", endpoint: "/api/predict/fuel-system", preflight: "/api/v2/preflight/fuel-system" },
];

export function systemFor(key: ComponentKey): ModelSystem {
  const system = MODEL_SYSTEMS.find((s) => s.key === key);
  if (!system) throw new Error(`Unknown model system: ${key}`);
  return system;
}

export const formatNumber = (value: unknown, digits = 3): string =>
  typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: digits }) : String(value ?? "Unavailable");

export const labelOf = (text: string): string => text.replaceAll("_", " ");
