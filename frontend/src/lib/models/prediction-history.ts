import type { PredictionResponse, PredictionValue } from "./types.ts";

const number = (value: unknown) =>
  typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: 3 }) : String(value ?? "Unavailable");

export function summarizeHistoryPrediction(component: string, data: PredictionResponse): string {
  if (component === "engine") return `Estimated RUL: ${number(data.rul?.value)} ${data.rul?.unit || "cycles"}`;
  if (component === "battery") return `SOH: ${number(data.soh?.value)}%; estimated RUL: ${number(data.rul?.value)} ${data.rul?.unit || "cycles"}`;
  if (component === "hydraulic")
    return Object.entries(data.predictions || {})
      .map(([name, result]) => `${name.replaceAll("_", " ")}: ${result.label ?? result.value}`)
      .join("; ");
  if (component === "landing-gear") return `Fault: ${data.fault?.label ?? data.fault?.value}; estimated RUL: ${number(data.rul?.value)} ${data.rul?.unit || "percent"}`;
  if (component === "fuel-system")
    return `${data.flagged_samples} of ${data.input_samples} samples flagged; latest sample ${data.latest_is_abnormal ? "flagged" : "not flagged"}`;
  throw new Error(`Unknown prediction-history component: ${component}`);
}

export function predictionNeedsReview(component: string, data: PredictionResponse): boolean {
  if (component === "fuel-system") return true;
  const results: (PredictionValue | undefined)[] =
    component === "engine"
      ? [data.rul]
      : component === "battery"
        ? [data.soh, data.rul]
        : component === "hydraulic"
          ? Object.values(data.predictions || {})
          : component === "landing-gear"
            ? [data.fault, data.rul]
            : [];
  return results.length === 0 || results.some((result) => result?.accepted !== true);
}
