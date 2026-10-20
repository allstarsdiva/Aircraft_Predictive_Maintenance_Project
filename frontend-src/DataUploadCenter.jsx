import React, { useMemo, useRef, useState } from "react";
import {
  AlertTriangle, CheckCircle2, CircleDot, ClipboardCheck, Download, Droplets,
  FileJson, FileSpreadsheet, Fuel, Gauge, History, Loader2, Play, Trash2, UploadCloud, X, Zap,
} from "lucide-react";
import { csvToPayload } from "./requestFiles.js";
import { friendlyApiError, parseJsonObject } from "./uploadValidation.js";
import { getResultGuidance } from "./resultGuidance.js";

/* ============================================================================
   DATA UPLOAD CENTER
   A maintenance engineer uploads one dataset file for one subsystem, checks it
   against the trained model's input rules, then runs the model. Files are read
   in the browser and sent only to the local prediction API; they never change
   the simulated fleet shown on the other pages.
============================================================================ */

const MAX_FILE_BYTES = 20 * 1024 * 1024; // the API accepts request bodies up to 25 MB

// Column lists mirror the backend request schemas (src/api/*_schemas.py).
const ENGINE_COLUMNS = [
  "unit_id", "cycle", "operational_setting_1", "operational_setting_2", "operational_setting_3",
  ...Array.from({ length: 21 }, (_, i) => `sensor_${i + 1}`),
];
const BATTERY_SAMPLE_COLUMNS = ["voltage_measured", "current_measured", "temperature_measured", "current_load", "voltage_load", "time"];
const HYDRAULIC_SENSORS = ["ps1", "ps2", "ps3", "ps4", "ps5", "ps6", "eps1", "fs1", "fs2", "ts1", "ts2", "ts3", "ts4", "vs1", "ce", "cp", "se"];
const HYDRAULIC_STATISTICS = ["mean", "std", "min", "max", "range", "rms", "slope"];
const HYDRAULIC_FEATURES = HYDRAULIC_SENSORS.flatMap((sensor) => HYDRAULIC_STATISTICS.map((stat) => `${sensor}_${stat}`));
const LANDING_COLUMNS = ["max_deflection", "max_velocity", "settling_time", "mass"];
const FUEL_COLUMNS = ["FTL", "CTL", "FTF", "FTV_S", "CLF", "CLV_S", "FTT", "CRTT"];

const zeros = (keys) => Object.fromEntries(keys.map((key) => [key, 0]));

const SUBSYSTEMS = [
  {
    key: "engine",
    label: "Engine",
    icon: Gauge,
    source: "NASA C-MAPSS FD001 (turbofan simulation)",
    task: "Remaining useful life (cycles)",
    perFile: "One engine's cycle history: one row per cycle, a single unit_id.",
    skeleton: { subset: "FD001", records: [zeros(ENGINE_COLUMNS)] },
    predict: "/api/v2/predict/engine",
  },
  {
    key: "battery",
    label: "Battery",
    icon: Zap,
    source: "NASA PCoE lithium-ion cells (laboratory data, not aircraft electrical-bus data)",
    task: "State of health (%) and remaining useful life (cycles)",
    perFile: "One discharge cycle: one row per reading; battery_id, discharge_cycle and ambient_temperature repeat on every row.",
    skeleton: { samples: [zeros(BATTERY_SAMPLE_COLUMNS)] },
    predict: "/api/v2/predict/battery",
  },
  {
    key: "hydraulic",
    label: "Hydraulic",
    icon: Droplets,
    source: "UCI hydraulic test rig (condition monitoring dataset)",
    task: "Cooler, valve, pump-leakage and accumulator condition classes",
    perFile: "Exactly one operating cycle: one row of 119 sensor summary features.",
    skeleton: { features: zeros(HYDRAULIC_FEATURES) },
    predict: "/api/v2/predict/hydraulic",
  },
  {
    key: "landing-gear",
    label: "Landing Gear",
    icon: CircleDot,
    source: "Dornier 228 digital twin (synthetic landing events)",
    task: "Fault class and remaining useful life (%)",
    perFile: "Exactly one landing event: one row of four measurements.",
    skeleton: zeros(LANDING_COLUMNS),
    predict: "/api/v2/predict/landing-gear",
  },
  {
    key: "fuel-system",
    label: "Fuel System",
    icon: Fuel,
    source: "Kaggle aircraft fuel distribution (experimental detector)",
    task: "Anomaly detection over ordered readings",
    perFile: "Ordered fuel-system readings: one row per sample, oldest first.",
    skeleton: { samples: [zeros(FUEL_COLUMNS)] },
    predict: "/api/predict/fuel-system",
  },
];

// index.css applies `button { font: inherit }` unlayered, which overrides text-* classes on buttons.
const TEXT_12 = { fontSize: 12, lineHeight: "16px" };
const TEXT_11 = { fontSize: 11, lineHeight: "16px" };

const ROW_LIMITS = { engine: [1, 10000], battery: [2, 20000], "fuel-system": [1, 10000] };

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatNumber(value, digits = 2) {
  if (typeof value !== "number" || !Number.isFinite(value)) return String(value ?? "—");
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

const humanise = (text) => String(text).replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

/** Rows as a flat table, used for counts and the preview. */
function tableRows(key, payload) {
  if (key === "engine") return payload.records || [];
  if (key === "battery") {
    return (payload.samples || []).map((sample) => ({
      battery_id: payload.battery_id, discharge_cycle: payload.discharge_cycle, ambient_temperature: payload.ambient_temperature, ...sample,
    }));
  }
  if (key === "hydraulic") return [{ cycle_id: payload.cycle_id, operating_condition_stable: payload.operating_condition_stable, ...(payload.features || {}) }];
  if (key === "landing-gear") return [payload];
  return payload.samples || [];
}

/** Turn the uploaded text into an API request, plus anything worth flagging before sending it. */
function parseUpload(system, file) {
  const isJson = /\.json$/i.test(file.name) || file.text.trimStart().startsWith("{");
  const payload = isJson ? parseJsonObject(file.text, "Compare it with the CSV template for this subsystem.") : csvToPayload(system.key, file.text, system.skeleton);
  const rows = tableRows(system.key, payload);
  if (!rows.length) throw new Error(`No readings were found for ${system.label}. Check that the file matches this subsystem's template.`);

  const issues = [];
  const limits = ROW_LIMITS[system.key];
  if (limits && (rows.length < limits[0] || rows.length > limits[1])) {
    issues.push(`${system.label} files must contain between ${limits[0].toLocaleString()} and ${limits[1].toLocaleString()} rows; this one has ${rows.length.toLocaleString()}.`);
  }
  if (system.key === "engine") {
    const units = new Set(rows.map((row) => row.unit_id));
    if (units.size > 1) issues.push(`The file contains ${units.size} engines (unit_id values). Upload one engine per file.`);
    const cycles = rows.map((row) => row.cycle);
    if (new Set(cycles).size !== cycles.length) issues.push("Cycle values must be unique within one engine.");
  }
  if (system.key === "hydraulic" && Object.keys(payload.features || {}).length > 200) {
    issues.push("The API accepts at most 200 hydraulic features per cycle.");
  }
  return { payload, rows, columns: Object.keys(rows[0] || {}), format: isJson ? "JSON" : "CSV", issues };
}

async function postJson(path, payload) {
  let response;
  try {
    response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  } catch {
    throw new Error("Could not reach the prediction API. Check that the backend is running on port 8000.");
  }
  let body = null;
  try { body = await response.json(); } catch { /* non-JSON error body */ }
  if (!response.ok) throw new Error(friendlyApiError(response.status, body?.detail));
  return body;
}

function download(filename, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/* ---------------------------------------------------------------- pieces */

function Panel({ children, className = "" }) {
  return <div className={`rounded-xl border border-slate-800 bg-slate-900/60 p-4 ${className}`}>{children}</div>;
}

function StepTitle({ step, title, hint }) {
  return (
    <div className="mb-3">
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-cyan-400/15 font-mono text-[10px] font-bold text-cyan-300 ring-1 ring-cyan-400/40">{step}</span>
        <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
      </div>
      {hint && <p className="mt-1 pl-7 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

const TONES = {
  ok: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
  warn: "border-amber-400/30 bg-amber-400/10 text-amber-300",
  bad: "border-red-400/30 bg-red-400/10 text-red-300",
  muted: "border-slate-700 bg-slate-800/60 text-slate-300",
};

function Chip({ tone = "muted", children }) {
  return <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${TONES[tone]}`}>{children}</span>;
}

function Interval({ label, result, unit }) {
  if (!result || typeof result.value !== "number") return null;
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 font-mono text-xl font-bold text-slate-100">
        {formatNumber(result.value, 1)} <span className="text-xs font-normal text-slate-400">{unit || result.unit}</span>
      </div>
      {typeof result.lower === "number" && (
        <div className="mt-0.5 text-[11px] text-slate-500">
          {Math.round((result.interval_level ?? 0.9) * 100)}% interval: {formatNumber(result.lower, 1)} – {formatNumber(result.upper, 1)}
        </div>
      )}
      {typeof result.accepted === "boolean" && (
        <div className="mt-2">{result.accepted ? <Chip tone="ok">Accepted</Chip> : <Chip tone="warn">Review required</Chip>}</div>
      )}
    </div>
  );
}

function Classification({ label, result }) {
  if (!result) return null;
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{humanise(label)}</div>
      <div className="mt-1 text-sm font-semibold text-slate-100">{result.label ?? `Class ${result.value}`}</div>
      {typeof result.calibrated_confidence === "number" && (
        <div className="mt-0.5 text-[11px] text-slate-500">Confidence estimate {formatNumber(result.calibrated_confidence * 100, 0)}%</div>
      )}
      {typeof result.accepted === "boolean" && (
        <div className="mt-2">{result.accepted ? <Chip tone="ok">Accepted</Chip> : <Chip tone="warn">Review required</Chip>}</div>
      )}
    </div>
  );
}

/** The backend's demonstration engine thresholds (src/api/app.py risk_from_rul). */
function enginePriority(rul) {
  if (rul <= 30) return { priority: "High", recommendation: "Inspect Immediately", tone: "bad" };
  if (rul <= 60) return { priority: "Medium", recommendation: "Monitor Closely", tone: "warn" };
  return { priority: "Low", recommendation: "No Immediate Action Required", tone: "ok" };
}

function PredictionSummary({ systemKey, result }) {
  if (systemKey === "engine") {
    const rul = result.rul?.value;
    const p = typeof rul === "number" ? enginePriority(rul) : null;
    return (
      <div className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <Interval label={`RUL · engine ${result.unit_id ?? ""}, cycle ${result.latest_cycle ?? ""}`} result={result.rul} unit="cycles" />
          {p && (
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
              <div className="text-[11px] uppercase tracking-wide text-slate-500">Maintenance priority</div>
              <div className="mt-1.5"><Chip tone={p.tone}>{p.priority}</Chip></div>
              <div className="mt-1.5 text-sm font-semibold text-slate-100">{p.recommendation}</div>
              <div className="mt-0.5 text-[11px] text-slate-500">Backend demonstration thresholds: RUL ≤ 30 high, ≤ 60 medium.</div>
            </div>
          )}
        </div>
      </div>
    );
  }
  if (systemKey === "battery") {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        <Interval label={`State of health · ${result.battery_id ?? ""}`} result={result.soh} unit="%" />
        <Interval label="Remaining useful life" result={result.rul} unit="cycles" />
      </div>
    );
  }
  if (systemKey === "hydraulic") {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        {Object.entries(result.predictions || {}).map(([name, value]) => <Classification key={name} label={name} result={value} />)}
      </div>
    );
  }
  if (systemKey === "landing-gear") {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        <Classification label="Fault class" result={result.fault} />
        <Interval label="Remaining useful life" result={result.rul} />
      </div>
    );
  }
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
        <div className="text-[11px] uppercase tracking-wide text-slate-500">Flagged readings</div>
        <div className="mt-1 font-mono text-xl font-bold text-slate-100">
          {formatNumber(result.flagged_samples, 0)} <span className="text-xs font-normal text-slate-400">of {formatNumber(result.input_samples, 0)}</span>
        </div>
      </div>
      <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
        <div className="text-[11px] uppercase tracking-wide text-slate-500">Latest reading</div>
        <div className="mt-1.5">{result.latest_is_abnormal ? <Chip tone="warn">Flagged</Chip> : <Chip tone="ok">Not flagged</Chip>}</div>
      </div>
      <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
        <div className="text-[11px] uppercase tracking-wide text-slate-500">Last three readings</div>
        <div className="mt-1.5">{result.persistent_last_three ? <Chip tone="warn">All flagged</Chip> : <Chip tone="muted">Not persistent</Chip>}</div>
      </div>
    </div>
  );
}

function PreflightSummary({ result }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {result.review_required ? <Chip tone="warn"><AlertTriangle className="h-3 w-3" /> Review required</Chip> : <Chip tone="ok"><CheckCircle2 className="h-3 w-3" /> Within training range</Chip>}
        <span className="text-xs text-slate-500">File structure is valid for the {result.component} model.</span>
      </div>
      <ul className="space-y-2">
        {Object.entries(result.checks || {}).map(([task, check]) => (
          <li key={task} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-semibold text-slate-200">{humanise(task)}</span>
              <Chip tone={check.status === "within_training_range" ? "ok" : check.status === "not_assessed" ? "muted" : "warn"}>{humanise(check.status)}</Chip>
            </div>
            <p className="mt-1 text-xs text-slate-400">{check.detail}</p>
            {check.hard_range_violations?.length > 0 && <p className="mt-1 text-[11px] text-red-300">Outside training range: {check.hard_range_violations.join(", ")}</p>}
            {check.tail_range_warnings?.length > 0 && <p className="mt-1 text-[11px] text-amber-300">Near edge of training range: {check.tail_range_warnings.join(", ")}</p>}
          </li>
        ))}
      </ul>
      {result.notes?.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-[11px] text-slate-500">
          {result.notes.map((note) => <li key={note}>{note}</li>)}
        </ul>
      )}
    </div>
  );
}

function ErrorNote({ message }) {
  return (
    <div className="flex gap-2 rounded-md border border-red-400/30 bg-red-400/10 p-2.5 text-xs text-red-200">
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

/* ---------------------------------------------------------------- main view */

export default function DataUploadCenter() {
  const [systemKey, setSystemKey] = useState("engine");
  const [file, setFile] = useState(null); // { name, size, text }
  const [readError, setReadError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(null); // "check" | "predict" | null
  const [preflight, setPreflight] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [apiError, setApiError] = useState({ check: "", predict: "" });
  const [history, setHistory] = useState([]);
  const [entryId, setEntryId] = useState(null);
  const inputRef = useRef(null);

  const system = SUBSYSTEMS.find((s) => s.key === systemKey);
  const parsed = useMemo(() => {
    if (!file) return null;
    try {
      return { ok: true, ...parseUpload(system, file) };
    } catch (error) {
      return { ok: false, error: error.message };
    }
  }, [file, system]);
  const canSend = parsed?.ok && parsed.issues.length === 0 && !busy;

  function resetResults() {
    setPreflight(null);
    setPrediction(null);
    setApiError({ check: "", predict: "" });
  }

  function logUpload(entry) {
    setHistory((prev) => [entry, ...prev].slice(0, 8));
  }

  function updateLog(status) {
    setHistory((prev) => prev.map((entry) => (entry.id === entryId ? { ...entry, status, system: system.label } : entry)));
  }

  async function acceptFile(picked) {
    if (!picked) return;
    setReadError("");
    resetResults();
    if (!/\.(csv|json)$/i.test(picked.name)) {
      setReadError("Only .csv or .json files can be uploaded.");
      return;
    }
    if (picked.size > MAX_FILE_BYTES) {
      setReadError(`This file is ${formatBytes(picked.size)}. The limit is ${formatBytes(MAX_FILE_BYTES)}; split it into smaller files.`);
      return;
    }
    const text = await picked.text();
    const next = { name: picked.name, size: picked.size, text };
    setFile(next);
    let rows = 0;
    let status = "Needs fixing";
    try {
      const result = parseUpload(system, next);
      rows = result.rows.length;
      status = result.issues.length ? "Needs fixing" : "Ready";
    } catch { /* shown in the file panel */ }
    const id = `${Date.now()}`;
    setEntryId(id);
    logUpload({ id, name: picked.name, system: system.label, rows, status, time: new Date() });
  }

  function changeSystem(key) {
    setSystemKey(key);
    resetResults();
  }

  async function runCheck() {
    resetResults();
    setBusy("check");
    try {
      setPreflight(await postJson(`/api/v2/preflight/${system.key}`, parsed.payload));
      updateLog("Checked");
    } catch (error) {
      setApiError({ check: error.message, predict: "" });
      updateLog("Check failed");
    } finally {
      setBusy(null);
    }
  }

  async function runPrediction() {
    setApiError((prev) => ({ ...prev, predict: "" }));
    setPrediction(null);
    setBusy("predict");
    try {
      setPrediction(await postJson(system.predict, parsed.payload));
      updateLog("Predicted");
    } catch (error) {
      setApiError((prev) => ({ ...prev, predict: error.message }));
      updateLog("Prediction failed");
    } finally {
      setBusy(null);
    }
  }

  function downloadResult() {
    const report = {
      generated_at: new Date().toISOString(),
      subsystem: system.label,
      file: { name: file.name, format: parsed.format, rows: parsed.rows.length },
      input_check: preflight,
      prediction,
      note: "Model output for maintenance review; not a certified airworthiness decision.",
    };
    download(`${system.key}-result-${Date.now()}.json`, JSON.stringify(report, null, 2), "application/json");
  }

  const guidance = getResultGuidance(system.key);
  const previewColumns = parsed?.ok ? parsed.columns.slice(0, 7) : [];

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-slate-500">
          <UploadCloud className="h-3.5 w-3.5" /> Data Upload
        </div>
        <h2 className="text-xl font-bold tracking-tight text-slate-100">Upload maintenance data</h2>
        <p className="max-w-3xl text-xs leading-5 text-slate-400">
          Upload a CSV or JSON file for one subsystem, check it against the trained model's input rules, then run the model.
          Files are read in your browser and sent only to the local prediction API. They do not change the simulated fleet on the other pages.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <Panel>
            <StepTitle step={1} title="Choose the subsystem" hint="Each subsystem has its own model and file layout." />
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
              {SUBSYSTEMS.map((s) => {
                const active = s.key === systemKey;
                return (
                  <button
                    key={s.key}
                    type="button"
                    onClick={() => changeSystem(s.key)}
                    aria-pressed={active}
                    className={`flex flex-col items-start gap-2 rounded-lg border p-3 text-left transition ${
                      active ? "border-cyan-400/50 bg-cyan-400/10" : "border-slate-800 bg-slate-950/40 hover:border-slate-700"
                    }`}
                  >
                    <s.icon className={`h-4 w-4 ${active ? "text-cyan-300" : "text-slate-500"}`} />
                    <span className={`text-xs font-semibold ${active ? "text-slate-100" : "text-slate-300"}`}>{s.label}</span>
                  </button>
                );
              })}
            </div>
            <p className="mt-3 text-[11px] text-slate-500">
              <span className="text-slate-400">{system.task}.</span> Data source: {system.source}.
            </p>
          </Panel>

          <Panel>
            <StepTitle step={2} title="Upload the file" hint={system.perFile} />
            {!file ? (
              <div
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => { e.preventDefault(); setDragging(false); acceptFile(e.dataTransfer.files?.[0]); }}
                className={`flex flex-col items-center justify-center rounded-lg border border-dashed px-4 py-10 text-center transition ${
                  dragging ? "border-cyan-400/70 bg-cyan-400/5" : "border-slate-700 bg-slate-950/40"
                }`}
              >
                <UploadCloud className={`h-8 w-8 ${dragging ? "text-cyan-300" : "text-slate-600"}`} />
                <p className="mt-3 text-sm text-slate-300">Drag and drop your {system.label.toLowerCase()} file here</p>
                <p className="mt-1 text-xs text-slate-500">CSV or JSON · up to {formatBytes(MAX_FILE_BYTES)}</p>
                <button
                  type="button"
                  onClick={() => inputRef.current?.click()}
                  style={TEXT_12}
                  className="mt-4 rounded-md bg-cyan-400/15 px-3 py-1.5 text-xs font-semibold text-cyan-300 ring-1 ring-cyan-400/40 transition hover:bg-cyan-400/25"
                >
                  Browse files
                </button>
              </div>
            ) : (
              <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                <div className="flex items-start gap-3">
                  {parsed?.format === "JSON" ? <FileJson className="mt-0.5 h-5 w-5 text-slate-400" /> : <FileSpreadsheet className="mt-0.5 h-5 w-5 text-slate-400" />}
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold text-slate-100">{file.name}</div>
                    <div className="text-[11px] text-slate-500">
                      {formatBytes(file.size)}
                      {parsed?.ok && ` · ${parsed.format} · ${parsed.rows.length.toLocaleString()} row${parsed.rows.length === 1 ? "" : "s"} · ${parsed.columns.length} columns`}
                    </div>
                  </div>
                  <button type="button" onClick={() => inputRef.current?.click()} style={TEXT_11} className="rounded-md px-2 py-1 text-[11px] font-semibold text-slate-400 hover:text-slate-200">
                    Replace
                  </button>
                  <button type="button" onClick={() => { setFile(null); resetResults(); }} aria-label="Remove file" className="rounded-md p-1 text-slate-500 hover:text-red-300">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                {parsed && !parsed.ok && (
                  <div className="mt-3 flex gap-2 rounded-md border border-red-400/30 bg-red-400/10 p-2.5 text-xs text-red-200">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    <span>{parsed.error}</span>
                  </div>
                )}
                {parsed?.ok && parsed.issues.length > 0 && (
                  <ul className="mt-3 space-y-1 rounded-md border border-amber-400/30 bg-amber-400/10 p-2.5 text-xs text-amber-200">
                    {parsed.issues.map((issue) => <li key={issue} className="flex gap-2"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />{issue}</li>)}
                  </ul>
                )}

                {parsed?.ok && (
                  <div className="mt-3 overflow-x-auto rounded-md border border-slate-800">
                    <table className="w-full min-w-[520px] text-[11px]">
                      <thead>
                        <tr className="border-b border-slate-800 text-left text-slate-500">
                          {previewColumns.map((c) => <th key={c} className="px-2.5 py-1.5 font-medium">{c}</th>)}
                          {parsed.columns.length > previewColumns.length && <th className="px-2.5 py-1.5 font-medium">+{parsed.columns.length - previewColumns.length} more</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {parsed.rows.slice(0, 5).map((row, i) => (
                          <tr key={i} className="border-b border-slate-800/60 last:border-0">
                            {previewColumns.map((c) => <td key={c} className="px-2.5 py-1.5 font-mono text-slate-300">{formatNumber(row[c], 4)}</td>)}
                            {parsed.columns.length > previewColumns.length && <td className="px-2.5 py-1.5 text-slate-600">…</td>}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {parsed.rows.length > 5 && <div className="border-t border-slate-800 px-2.5 py-1.5 text-[10px] text-slate-600">Showing the first 5 of {parsed.rows.length.toLocaleString()} rows</div>}
                  </div>
                )}

                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={!canSend}
                    onClick={runCheck}
                    style={TEXT_12}
                  className="flex items-center gap-1.5 rounded-md bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {busy === "check" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ClipboardCheck className="h-3.5 w-3.5" />} Check data
                  </button>
                  <button
                    type="button"
                    disabled={!canSend}
                    onClick={runPrediction}
                    style={TEXT_12}
                  className="flex items-center gap-1.5 rounded-md bg-cyan-400/15 px-3 py-1.5 text-xs font-semibold text-cyan-300 ring-1 ring-cyan-400/40 transition hover:bg-cyan-400/25 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {busy === "predict" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />} Run prediction
                  </button>
                </div>
              </div>
            )}
            {readError && (
              <div className="mt-3 flex items-start gap-2 rounded-md border border-red-400/30 bg-red-400/10 p-2.5 text-xs text-red-200">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span className="flex-1">{readError}</span>
                <button type="button" onClick={() => setReadError("")} aria-label="Dismiss" className="text-red-300 hover:text-red-100"><X className="h-3.5 w-3.5" /></button>
              </div>
            )}
            <input
              ref={inputRef}
              type="file"
              accept=".csv,.json,text/csv,application/json"
              className="hidden"
              onChange={(e) => { acceptFile(e.target.files?.[0]); e.target.value = ""; }}
            />
          </Panel>

          {(apiError.check || apiError.predict || preflight || prediction) && (
            <Panel>
              <StepTitle step={3} title="Results" hint="Model output for maintenance review, not a certified airworthiness decision." />
              {(preflight || apiError.check) && (
                <div className="mb-4">
                  <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Input check</div>
                  {apiError.check ? <ErrorNote message={apiError.check} /> : <PreflightSummary result={preflight} />}
                </div>
              )}
              {apiError.predict && (
                <div>
                  <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Prediction</div>
                  <ErrorNote message={apiError.predict} />
                </div>
              )}
              {prediction && (
                <div>
                  <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Prediction</div>
                  <PredictionSummary systemKey={system.key} result={prediction} />
                  {prediction.warnings?.length > 0 && (
                    <ul className="mt-3 space-y-1 text-[11px] text-amber-200/90">
                      {prediction.warnings.map((w) => <li key={w} className="flex gap-1.5"><AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />{w}</li>)}
                    </ul>
                  )}
                  {guidance && (
                    <p className="mt-3 text-[11px] leading-5 text-slate-500">
                      <span className="text-slate-400">{guidance.meaning}</span> {guidance.caveat}
                    </p>
                  )}
                </div>
              )}
              {(preflight || prediction) && (
                <button
                  type="button"
                  onClick={downloadResult}
                  style={TEXT_12}
                  className="mt-4 flex items-center gap-1.5 rounded-md bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:bg-slate-700"
                >
                  <Download className="h-3.5 w-3.5" /> Download result (JSON)
                </button>
              )}
            </Panel>
          )}
        </div>

        <div className="space-y-4">
          <Panel>
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-200">
              <History className="h-3.5 w-3.5 text-slate-500" /> Recent uploads
            </div>
            {history.length === 0 ? (
              <p className="text-xs text-slate-500">No files uploaded in this session yet.</p>
            ) : (
              <ul className="divide-y divide-slate-800">
                {history.map((entry) => (
                  <li key={entry.id} className="flex items-center gap-2 py-2">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-xs text-slate-200">{entry.name}</div>
                      <div className="text-[10px] text-slate-500">
                        {entry.system} · {entry.rows.toLocaleString()} rows · {entry.time.toLocaleTimeString()}
                      </div>
                    </div>
                    <Chip tone={entry.status === "Predicted" || entry.status === "Checked" || entry.status === "Ready" ? "ok" : "warn"}>{entry.status}</Chip>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-[10px] text-slate-600">Kept for this browser session only.</p>
          </Panel>
        </div>
      </div>
    </div>
  );
}
