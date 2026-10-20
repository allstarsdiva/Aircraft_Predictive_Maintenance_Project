/** Types for the FastAPI prediction service responses used by the UI. */

export type ComponentKey = "engine" | "battery" | "hydraulic" | "landing-gear" | "fuel-system";

/** Request payloads are free-form JSON objects validated by the backend. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type JsonObject = Record<string, any>;

export interface InputSupport {
  abstain?: boolean;
  hard_range_violations?: string[];
  tail_range_warnings?: string[];
}

export interface FeatureImportance {
  feature: string;
  relative_importance: number;
}

export interface PredictionValue {
  value: number | string;
  unit?: string;
  label?: string;
  accepted?: boolean;
  lower?: number;
  upper?: number;
  interval_level?: number;
  calibrated_confidence?: number;
  input_support?: InputSupport;
  top_model_features?: FeatureImportance[];
}

export interface EnvelopeDeviation {
  feature: string;
  scaled_deviation: number;
}

export interface PredictionResponse {
  component?: string;
  model?: string;
  rul_model?: string;
  fault_model?: string;
  soh_model?: string;
  rul?: PredictionValue;
  soh?: PredictionValue;
  fault?: PredictionValue;
  predictions?: Record<string, PredictionValue>;
  warnings?: string[];
  latest_is_abnormal?: boolean;
  flagged_samples?: number;
  input_samples?: number;
  latest_anomaly_margin?: number;
  largest_normal_envelope_deviations?: EnvelopeDeviation[];
  [key: string]: unknown;
}

export interface PreflightCheck {
  status: string;
  detail?: string;
  hard_range_violations?: string[];
  tail_range_warnings?: string[];
}

export interface PreflightReport {
  review_required: boolean;
  schema_valid: boolean;
  checks?: Record<string, PreflightCheck>;
  notes?: string[];
  [key: string]: unknown;
}

export interface DatasetExample {
  payload: JsonObject;
  source: string;
  actual?: unknown;
  evaluation_note?: string;
}

export interface Evidence {
  release_id: string;
  fuel_evaluation?: { metrics?: { abnormal_detection_rate: number; normal_false_alarm_rate: number } };
  [key: string]: unknown;
}

export interface HistoryEntry {
  id: number | string;
  component: string;
  created_at_utc: string;
  summary: string;
  asset_id?: string | null;
  source: string;
  review_required: boolean;
}
