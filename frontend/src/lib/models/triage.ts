/**
 * Pure helpers that interpret one model response for the coverage and review
 * screens. They never invent severity: "Critical" means a model returned a
 * positive fault/anomaly output; "Caution" means a model gate or input-support
 * warning asked for review.
 */
import { formatNumber, labelOf, type ModelSystem } from "./catalog.ts";
import type { DatasetExample, JsonObject, PredictionResponse } from "./types.ts";

export interface ModelRun {
  system: ModelSystem;
  example?: DatasetExample;
  result?: PredictionResponse;
  error?: string;
}

export type AttentionLevel = "Critical" | "Caution" | "Monitor" | "Unavailable";
export const ATTENTION_ORDER: AttentionLevel[] = ["Critical", "Caution", "Monitor", "Unavailable"];

export function outputSummary(key: string, data: PredictionResponse): string {
  if (key === "engine") return `Estimated remaining useful life: ${formatNumber(data.rul?.value)} ${data.rul?.unit || "cycles"}`;
  if (key === "battery") return `Estimated SOH: ${formatNumber(data.soh?.value)}%; RUL: ${formatNumber(data.rul?.value)} ${data.rul?.unit || "cycles"}`;
  if (key === "hydraulic")
    return Object.entries(data.predictions || {})
      .map(([name, result]) => `${labelOf(name)}: ${result.label ?? result.value}`)
      .join(" / ");
  if (key === "landing-gear")
    return `Fault model output: ${data.fault?.label ?? data.fault?.value}; RUL estimate: ${formatNumber(data.rul?.value)} ${data.rul?.unit || "percent"}`;
  return `${data.latest_is_abnormal ? "Latest sample flagged" : "No alert on latest sample"}; ${data.flagged_samples} of ${data.input_samples} samples flagged`;
}

export function acceptance(data: PredictionResponse): boolean | null {
  if (data.soh && typeof data.soh.accepted === "boolean") return data.soh.accepted && data.rul?.accepted !== false;
  if (data.fault && typeof data.fault.accepted === "boolean") return data.fault.accepted && data.rul?.accepted !== false;
  if (data.rul && typeof data.rul.accepted === "boolean") return data.rul.accepted;
  const checks = Object.values(data.predictions || {}).filter((item) => typeof item.accepted === "boolean");
  return checks.length ? checks.every((item) => item.accepted) : null;
}

export function modelName(data: PredictionResponse): string {
  return data.model || data.rul_model || data.fault_model || data.soh_model || "Saved subsystem model";
}

export function triage(run: ModelRun): { level: AttentionLevel; reason: string } {
  if (!run.result) return { level: "Unavailable", reason: run.error || "No model response." };
  const data = run.result;
  if (run.system.key === "fuel-system" && (data.latest_is_abnormal || (data.flagged_samples ?? 0) > 0))
    return {
      level: "Critical",
      reason: `${data.flagged_samples} of ${data.input_samples} example samples were flagged; this experimental detector needs engineering review.`,
    };
  if (run.system.key === "landing-gear" && Number(data.fault?.value) > 0)
    return { level: "Critical", reason: `Model flagged ${data.fault?.label || `fault class ${data.fault?.value}`} in this synthetic landing-event example.` };
  const results = run.system.key === "hydraulic" ? Object.values(data.predictions || {}) : [data.rul, data.soh, data.fault].filter(Boolean);
  if (results.some((r) => r?.accepted === false || r?.input_support?.abstain))
    return { level: "Caution", reason: "At least one output was not accepted by its model gate; it is marked for review, not diagnosed as faulty." };
  if (results.some((r) => r?.input_support?.tail_range_warnings?.length))
    return { level: "Caution", reason: "Input includes values near/outside a model’s well-supported range; review the result." };
  return { level: "Monitor", reason: "No model alert was returned for this example. This is not a maintenance clearance." };
}

export interface InputTrace {
  title: string;
  xLabel: string;
  series: { name: string; rows: { step: number; value: number }[] }[];
}

/** Dataset input series for display (one series per chart: no dual axes). */
export function inputTrace(run: ModelRun): InputTrace | null {
  const payload: JsonObject = run.example?.payload || {};
  const finite = (rows: { step: number; value: number }[]) => rows.filter((r) => Number.isFinite(r.value) && Number.isFinite(r.step));
  if (run.system.key === "engine" && Array.isArray(payload.records)) {
    return {
      title: "Engine input trace",
      xLabel: "Cycle",
      series: [{ name: "sensor_2", rows: finite(payload.records.map((row: JsonObject, i: number) => ({ step: Number(row.cycle ?? i + 1), value: Number(row.sensor_2) }))) }],
    };
  }
  if (run.system.key === "battery" && Array.isArray(payload.samples)) {
    return {
      title: "Battery input trace",
      xLabel: "Sample time (s)",
      series: [
        { name: "Voltage (V)", rows: finite(payload.samples.map((row: JsonObject, i: number) => ({ step: Number(row.time ?? i), value: Number(row.voltage_measured) }))) },
        { name: "Temperature (°C)", rows: finite(payload.samples.map((row: JsonObject, i: number) => ({ step: Number(row.time ?? i), value: Number(row.temperature_measured) }))) },
      ],
    };
  }
  if (run.system.key === "fuel-system" && Array.isArray(payload.samples)) {
    const source: JsonObject[] = payload.samples;
    const stride = Math.max(1, Math.ceil(source.length / 180));
    const pick = (key: string) =>
      finite(source.flatMap((row, index) => (index % stride === 0 || index === source.length - 1 ? [{ step: index, value: Number(row[key]) }] : [])));
    return {
      title: `Fuel input trace (showing ${Math.ceil(source.length / stride)} of ${source.length} samples)`,
      xLabel: "Sample index",
      series: [
        { name: "FTL", rows: pick("FTL") },
        { name: "FTF", rows: pick("FTF") },
      ],
    };
  }
  return null;
}

export function modelInputGroups(run: ModelRun): { title: string; note?: string; values: JsonObject }[] {
  const payload: JsonObject = run.example?.payload || {};
  const key = run.system.key;
  if (key === "engine") {
    const rows: JsonObject[] = payload.records || [];
    return [
      {
        title: "Engine cycle and sensor inputs",
        note: `${rows.length} ordered cycles · ${Object.keys(rows.at(-1) || {}).length} fields in the latest cycle`,
        values: rows.at(-1) || {},
      },
    ];
  }
  if (key === "battery") {
    const samples: JsonObject[] = payload.samples || [];
    return [
      {
        title: "Battery and discharge context",
        values: { battery_id: payload.battery_id, discharge_cycle: payload.discharge_cycle, ambient_temperature: payload.ambient_temperature, samples_in_cycle: samples.length },
      },
      { title: "Measured electrical/thermal signals · last sample", note: "Full ordered sample sequence is sent to the model.", values: samples.at(-1) || {} },
    ];
  }
  if (key === "hydraulic")
    return [
      { title: "Cycle context", values: { cycle_id: payload.cycle_id, operating_condition_stable: payload.operating_condition_stable } },
      { title: "Hydraulic sensor-derived model features", note: `${Object.keys(payload.features || {}).length} measured/engineered inputs`, values: payload.features || {} },
    ];
  if (key === "landing-gear") return [{ title: "Landing-event observable inputs", values: payload }];
  const samples: JsonObject[] = payload.samples || [];
  return [{ title: "Fuel-system sensor features · last sample", note: `${samples.length} ordered samples · full trajectory is sent to the model.`, values: samples.at(-1) || {} }];
}

export function importanceGroups(run: ModelRun): { title: string; rows: { feature: string; relative_importance: number }[] }[] {
  const result = run.result || {};
  const key = run.system.key;
  if (key === "engine") return [{ title: "Engine RUL model · global feature importance", rows: result.rul?.top_model_features || [] }];
  if (key === "battery")
    return [
      { title: "Battery SOH model · global feature importance", rows: result.soh?.top_model_features || [] },
      { title: "Battery RUL model · global feature importance", rows: result.rul?.top_model_features || [] },
    ];
  if (key === "hydraulic")
    return Object.entries(result.predictions || {}).map(([target, prediction]) => ({
      title: `${labelOf(target)} model · global feature importance`,
      rows: prediction.top_model_features || [],
    }));
  if (key === "landing-gear")
    return [
      { title: "Landing-gear fault model · global feature importance", rows: result.fault?.top_model_features || [] },
      { title: "Landing-gear RUL model · global feature importance", rows: result.rul?.top_model_features || [] },
    ];
  return [
    {
      title: "Fuel detector · largest deviations from its normal envelope",
      rows: (result.largest_normal_envelope_deviations || []).map((row) => ({ feature: row.feature, relative_importance: row.scaled_deviation })),
    },
  ];
}

/** Short one-line summary of a request text for the workspace. */
export function summarizeRequest(component: string, input: string): { state: "empty" | "invalid" | "ready"; title: string; detail: string } {
  if (!input.trim()) return { state: "empty", title: "No request data loaded", detail: "Choose an example or import a JSON file to get started." };
  let payload: unknown;
  try {
    payload = JSON.parse(input);
  } catch {
    return { state: "invalid", title: "JSON needs attention", detail: "Open the full JSON editor and fix the formatting, or import a valid JSON file." };
  }
  if (!payload || Array.isArray(payload) || typeof payload !== "object") {
    return { state: "invalid", title: "Request must be one JSON object", detail: "Open the full JSON editor to review the request structure." };
  }
  const obj = payload as JsonObject;
  const collectionName = component === "engine" ? "records" : ["battery", "fuel-system"].includes(component) ? "samples" : null;
  const collection: unknown[] | null = collectionName && Array.isArray(obj[collectionName]) ? obj[collectionName] : null;
  const itemCount = collection ? collection.length : 1;
  const first = collection?.[0];
  const fieldCount =
    component === "hydraulic"
      ? Object.keys(obj.features || {}).length
      : first && typeof first === "object"
        ? Object.keys(first as object).length
        : Object.keys(obj).length;
  const subject =
    component === "engine"
      ? itemCount === 1
        ? "engine cycle"
        : "engine cycles"
      : component === "battery"
        ? itemCount === 1
          ? "battery reading"
          : "battery readings"
        : component === "fuel-system"
          ? itemCount === 1
            ? "fuel-system reading"
            : "fuel-system readings"
          : component === "hydraulic"
            ? "hydraulic cycle"
            : "landing event";
  const fieldsText = fieldCount ? ` | ${fieldCount} input fields per reading` : "";
  return {
    state: "ready",
    title: "JSON format valid",
    detail: `${itemCount.toLocaleString()} ${subject}${fieldsText}. The API checks the request schema and available model training support before prediction.`,
  };
}
