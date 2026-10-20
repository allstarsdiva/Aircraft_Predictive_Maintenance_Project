import { parseJsonObject } from "./upload-validation.ts";
import type { ComponentKey, JsonObject } from "./types.ts";

export const BATCH_COMPONENT_KEYS: ComponentKey[] = ["engine", "battery", "hydraulic", "landing-gear", "fuel-system"];

export type ComponentBundle = Record<ComponentKey, JsonObject>;

export function parseComponentBundle(text: string): ComponentBundle {
  const bundle = parseJsonObject(text, "Download the all-components example to see the required structure.");
  const missing = BATCH_COMPONENT_KEYS.filter((key) => !(key in bundle));
  const unexpected = Object.keys(bundle).filter((key) => !(BATCH_COMPONENT_KEYS as string[]).includes(key));
  if (missing.length || unexpected.length) {
    const issues: string[] = [];
    if (missing.length) issues.push(`Missing: ${missing.join(", ")}`);
    if (unexpected.length) issues.push(`Unexpected: ${unexpected.join(", ")}`);
    throw new Error(`Bundle must contain exactly the five subsystem sections. ${issues.join(". ")}.`);
  }
  for (const key of BATCH_COMPONENT_KEYS) {
    const payload = bundle[key];
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new Error(`The ${key} section must contain one JSON request object.`);
    }
  }
  return bundle as ComponentBundle;
}

export function makeComponentBundle(examples: Partial<Record<string, { payload?: JsonObject }>>): ComponentBundle {
  const bundle = {} as ComponentBundle;
  for (const key of BATCH_COMPONENT_KEYS) {
    const payload = examples?.[key]?.payload;
    if (!payload) throw new Error(`The ${key} example is not available.`);
    bundle[key] = payload;
  }
  return bundle;
}
