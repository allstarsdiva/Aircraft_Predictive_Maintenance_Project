import { parseJsonObject } from './uploadValidation.js';

export const BATCH_COMPONENT_KEYS = ['engine', 'battery', 'hydraulic', 'landing-gear', 'fuel-system'];

export function parseComponentBundle(text) {
  const bundle = parseJsonObject(text, 'Download the all-components example to see the required structure.');
  const missing = BATCH_COMPONENT_KEYS.filter(key => !(key in bundle));
  const unexpected = Object.keys(bundle).filter(key => !BATCH_COMPONENT_KEYS.includes(key));
  if (missing.length || unexpected.length) {
    const issues = [];
    if (missing.length) issues.push(`Missing: ${missing.join(', ')}`);
    if (unexpected.length) issues.push(`Unexpected: ${unexpected.join(', ')}`);
    throw new Error(`Bundle must contain exactly the five subsystem sections. ${issues.join('. ')}.`);
  }
  for (const key of BATCH_COMPONENT_KEYS) {
    const payload = bundle[key];
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      throw new Error(`The ${key} section must contain one JSON request object.`);
    }
  }
  return bundle;
}

export function makeComponentBundle(examples) {
  const bundle = {};
  for (const key of BATCH_COMPONENT_KEYS) {
    if (!examples?.[key]?.payload) throw new Error(`The ${key} example is not available.`);
    bundle[key] = examples[key].payload;
  }
  return bundle;
}
