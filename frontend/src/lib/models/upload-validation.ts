import type { JsonObject } from "./types.ts";

const EXAMPLE_HINT = "Compare the request with the selected system's downloaded JSON example.";

export function parseJsonObject(text: string, exampleHint = EXAMPLE_HINT): JsonObject {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    throw new Error("This file is not valid JSON. Check commas, quotes, and brackets, then try again.");
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`The file must contain one JSON object. ${exampleHint}`);
  }
  return value as JsonObject;
}

interface ValidationIssue {
  loc?: (string | number)[];
  msg?: string;
}

export function friendlyApiError(status: number, detail: unknown): string {
  if (status === 401) return "The prediction service rejected its API key. Check the server-side AIRCRAFT_API_KEY configuration.";
  if (status === 429) return "The API request limit was reached. Wait a minute, then try again.";
  if (status === 413) return "This request is too large for the API. Reduce the number of readings or split the upload.";
  if (status === 502) return "Cannot reach the FastAPI backend. Start it on port 8000, then try again.";
  if (status === 503 && typeof detail === "string" && detail.toLowerCase().includes("authentication")) {
    return "API authentication is required, but no server key is configured. Set AIRCRAFT_API_KEY for the backend and the Next.js server.";
  }
  if (status === 503) return "A required model is unavailable. Check that the backend and model release are installed, then try again.";
  if (Array.isArray(detail)) {
    const issues = (detail as ValidationIssue[]).map((issue) => {
      const path = (issue.loc || []).filter((part) => part !== "body").join(".");
      const message = issue.msg === "Field required" ? "is required" : issue.msg || "has an invalid value";
      return `${path ? `${path}: ` : ""}${message}`;
    });
    return `Input validation failed: ${issues.slice(0, 5).join("; ")}${issues.length > 5 ? `; and ${issues.length - 5} more` : ""}. Correct the listed fields. Check each value's type, range, and units using the selected system's downloaded JSON example and unit guidance.`;
  }
  if (detail && typeof detail === "object") {
    const d = detail as { missing_features?: string[]; unexpected_features?: string[] };
    if (d.missing_features || d.unexpected_features) {
      const summarize = (values?: string[]) =>
        values?.length ? `${values.slice(0, 4).join(", ")}${values.length > 4 ? ` and ${values.length - 4} more` : ""}` : "none";
      return `The feature names do not match this model. Missing: ${summarize(d.missing_features)}. Unexpected: ${summarize(d.unexpected_features)}. Compare the hydraulic feature names with the selected system's downloaded JSON example.`;
    }
  }
  if (status >= 500) return "The backend could not complete this prediction. Check that it is running and review its terminal for details.";
  return typeof detail === "string" ? detail : JSON.stringify(detail || "Request failed.");
}
