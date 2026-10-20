"use client";

import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { motion } from "framer-motion";
import { Activity, ArrowRight, CheckCircle2, CircleDot, Cpu, Download, FileJson2, Layers, Loader2, Sparkles, Upload } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { EmptyState, PageBody, PageHeader, Section } from "@/components/shell/page-parts";
import {
  ConnectionDot,
  Disclosure,
  ErrorBox,
  FuelResultCard,
  InputQualityReport,
  Notice,
  PredictionCard,
  ResultMeaning,
  SYSTEM_ICONS,
  UnitGuidance,
} from "@/components/models/shared";
import { isAbort, postJson, request } from "@/lib/api/client";
import { downloadContent, downloadJson } from "@/lib/download";
import { MODEL_SYSTEMS, formatNumber, labelOf, systemFor } from "@/lib/models/catalog";
import { csvToPayload, payloadToCsv } from "@/lib/models/request-files";
import { BATCH_COMPONENT_KEYS, makeComponentBundle, parseComponentBundle, type ComponentBundle } from "@/lib/models/batch-requests";
import { makePredictionReport, sha256Text } from "@/lib/models/prediction-report";
import { parseJsonObject } from "@/lib/models/upload-validation";
import { predictionNeedsReview, summarizeHistoryPrediction } from "@/lib/models/prediction-history";
import { summarizeRequest } from "@/lib/models/triage";
import type { ComponentKey, DatasetExample, Evidence, PredictionResponse, PredictionValue, PreflightReport } from "@/lib/models/types";
import { cn } from "@/lib/utils";

type ApiStatus = "checking" | "online" | "offline";
type HistoryNotice = { kind: "info" | "success" | "error"; text: string } | null;
type RunRecord = { requestText: string; preflight: PreflightReport; prediction: PredictionResponse; inputSummary: string; source: string };
type BatchQuality = {
  fingerprint: string;
  checks: Record<string, { ok: true; report: PreflightReport } | { ok: false; error: string }>;
  schemaValid: boolean;
  reviewRequired: boolean;
};
type BatchResults = Record<string, { ok: true; data: PredictionResponse } | { ok: false; error: string }>;

function batchSummary(component: ComponentKey, data: PredictionResponse): string {
  if (component === "engine") return `Estimated RUL: ${formatNumber(data.rul?.value)} ${data.rul?.unit ?? ""}`;
  if (component === "battery") return `SOH: ${formatNumber(data.soh?.value)}%; estimated RUL: ${formatNumber(data.rul?.value)} ${data.rul?.unit ?? ""}`;
  if (component === "hydraulic")
    return Object.entries(data.predictions || {})
      .map(([name, result]) => `${labelOf(name)}: ${result.label ?? result.value}`)
      .join("; ");
  if (component === "landing-gear") return `Fault: ${data.fault?.label ?? data.fault?.value}; estimated RUL: ${formatNumber(data.rul?.value)} ${data.rul?.unit ?? ""}`;
  return `${data.latest_is_abnormal ? "Latest sample flagged" : "No alert on latest sample"}; ${data.flagged_samples} of ${data.input_samples} samples flagged`;
}

function FileButton({ label, accept, disabled, onFile }: { label: string; accept: string; disabled?: boolean; onFile: (file: File) => void }) {
  return (
    <label className={cn(buttonVariants({ variant: "outline", size: "sm" }), "relative cursor-pointer", disabled && "pointer-events-none opacity-50")}>
      <Upload />
      {label}
      <input
        aria-label={label}
        type="file"
        accept={accept}
        disabled={disabled}
        className="sr-only"
        onChange={(event: ChangeEvent<HTMLInputElement>) => {
          const file = event.target.files?.[0];
          if (file) onFile(file);
          event.target.value = "";
        }}
      />
    </label>
  );
}

export function PredictView() {
  const [component, setComponent] = useState<ComponentKey>("engine");
  const [variant, setVariant] = useState<"normal" | "challenge">("normal");
  const [sample, setSample] = useState<DatasetExample | null>(null);
  const [input, setInput] = useState("");
  const [fileName, setFileName] = useState("");
  const [inputQuality, setInputQuality] = useState<{ sourceText: string; report: PreflightReport } | null>(null);
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [runRecord, setRunRecord] = useState<RunRecord | null>(null);
  const [reportError, setReportError] = useState("");
  const [reportSaving, setReportSaving] = useState(false);
  const [historySaveNotice, setHistorySaveNotice] = useState<HistoryNotice>(null);
  const [assetId, setAssetId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [runStage, setRunStage] = useState<"quality" | "prediction">("quality");
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [evidenceError, setEvidenceError] = useState("");
  const [batchPayload, setBatchPayload] = useState<ComponentBundle | null>(null);
  const [batchFileName, setBatchFileName] = useState("");
  const [batchTemplateLoading, setBatchTemplateLoading] = useState(false);
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchError, setBatchError] = useState("");
  const [batchResults, setBatchResults] = useState<BatchResults | null>(null);
  const [batchQuality, setBatchQuality] = useState<BatchQuality | null>(null);
  const [batchAcknowledged, setBatchAcknowledged] = useState(false);
  const [inputAcknowledged, setInputAcknowledged] = useState(false);
  const [batchOpen, setBatchOpen] = useState(false);
  const [reload, setReload] = useState(0);
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const batchController = useRef<AbortController | null>(null);

  useEffect(() => () => batchController.current?.abort(), []);

  useEffect(() => {
    const abort = new AbortController();
    setApiStatus("checking");
    setEvidence(null);
    setEvidenceError("");
    request("/api/health", { signal: abort.signal })
      .then(() => setApiStatus("online"))
      .catch((err) => {
        if (!isAbort(err)) {
          setApiStatus("offline");
          generation.current += 1;
          controller.current?.abort();
          setRunning(false);
          setResult(null);
        }
      });
    request<Evidence>("/api/workspace/evidence", { signal: abort.signal })
      .then(setEvidence)
      .catch((err) => {
        if (!isAbort(err)) setEvidenceError((err as Error).message);
      });
    return () => abort.abort();
  }, [reload]);

  useEffect(() => {
    generation.current += 1;
    controller.current?.abort();
    const abort = new AbortController();
    setLoading(true);
    setRunning(false);
    setSample(null);
    setInput("");
    setFileName("");
    setInputQuality(null);
    setInputAcknowledged(false);
    setResult(null);
    setRunRecord(null);
    setReportError("");
    setError("");
    request<DatasetExample>(`/api/workspace/examples/${component}?variant=${variant}`, { signal: abort.signal })
      .then((data) => {
        setSample(data);
        setInput(JSON.stringify(data.payload, null, 2));
      })
      .catch((err) => {
        if (!isAbort(err)) setError((err as Error).message);
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => {
      abort.abort();
      controller.current?.abort();
    };
  }, [component, variant]);

  function edit(value: string) {
    generation.current += 1;
    controller.current?.abort();
    setRunning(false);
    setInput(value);
    setFileName("");
    setInputQuality(null);
    setInputAcknowledged(false);
    setResult(null);
    setRunRecord(null);
    setReportError("");
    setError("");
  }

  const exampleText = sample ? JSON.stringify(sample.payload, null, 2) : null;
  const matchesSample = sample != null && input === exampleText;
  const sourceKind = matchesSample ? "dataset_example" : fileName ? "uploaded_file" : "edited_input";

  async function saveHistory(key: ComponentKey, data: PredictionResponse, requestText: string, source: string) {
    let inputDigest: string | null;
    try {
      inputDigest = await sha256Text(requestText);
    } catch {
      inputDigest = null;
    }
    return postJson("/api/prediction-history", {
      component: key,
      asset_id: assetId.trim() || null,
      source,
      summary: summarizeHistoryPrediction(key, data),
      review_required: predictionNeedsReview(key, data),
      model_release: evidence?.release_id || null,
      input_digest: inputDigest,
    });
  }

  async function runPrediction(confirmReview: boolean) {
    if (!inputAcknowledged) return;
    setError("");
    setResult(null);
    setRunRecord(null);
    setReportError("");
    setHistorySaveNotice(null);
    setBatchResults(null);
    const current = ++generation.current;
    const system = systemFor(component);
    try {
      const payload = JSON.parse(input);
      if (!payload || Array.isArray(payload) || typeof payload !== "object") throw new Error("Input must be a JSON object.");
      controller.current?.abort();
      controller.current = new AbortController();
      setRunning(true);
      setRunStage("quality");
      let checked = inputQuality?.sourceText === input ? inputQuality.report : null;
      if (!checked) {
        checked = await postJson<PreflightReport>(system.preflight, payload, controller.current.signal);
        if (current !== generation.current) return;
        setInputQuality({ sourceText: input, report: checked });
      }
      if (checked.review_required && !confirmReview) return;
      setRunStage("prediction");
      const data = await postJson<PredictionResponse>(system.endpoint, payload, controller.current.signal);
      if (current !== generation.current) return;
      setResult(data);
      const source = matchesSample ? sample?.source ?? "Dataset example" : fileName ? "User-uploaded file" : "User-edited request";
      setRunRecord({ requestText: input, preflight: checked, prediction: data, inputSummary: summarizeRequest(component, input).detail, source });
      setHistorySaveNotice({ kind: "info", text: "Saving this result to prediction history…" });
      try {
        await saveHistory(component, data, input, sourceKind);
        if (current === generation.current) setHistorySaveNotice({ kind: "success", text: "Saved to prediction history. Raw sensor values were not stored." });
      } catch {
        if (current === generation.current)
          setHistorySaveNotice({
            kind: "error",
            text: "Prediction completed, but could not be saved to history. Check the backend and refresh Model coverage.",
          });
      }
    } catch (err) {
      if (current === generation.current && !isAbort(err)) setError((err as Error).message);
    } finally {
      if (current === generation.current) setRunning(false);
    }
  }

  async function downloadPredictionReport() {
    if (!runRecord || !result) return;
    setReportError("");
    setReportSaving(true);
    try {
      const report = await makePredictionReport({ component, title: systemFor(component).title, releaseId: evidence?.release_id, ...runRecord });
      downloadJson(report, `${component}-prediction-report-${report.created_at_utc.slice(0, 10)}.json`);
    } catch (err) {
      setReportError((err as Error).message || "Could not create the prediction report.");
    } finally {
      setReportSaving(false);
    }
  }

  async function importRequestFile(file: File) {
    const current = ++generation.current;
    controller.current?.abort();
    setRunning(false);
    setResult(null);
    setError("");
    setFileName("");
    setInputQuality(null);
    setInputAcknowledged(false);
    try {
      if (file.size > 5_000_000) throw new Error("Choose a JSON file smaller than 5 MB.");
      const text = await file.text();
      let parsed;
      if (file.name.toLowerCase().endsWith(".csv")) {
        if (!sample?.payload) throw new Error("Wait for the selected system example to load before importing CSV.");
        parsed = csvToPayload(component, text, sample.payload);
      } else parsed = parseJsonObject(text);
      if (current === generation.current) {
        setInput(JSON.stringify(parsed, null, 2));
        setFileName(file.name);
      }
    } catch (err) {
      if (current === generation.current)
        setError(err instanceof SyntaxError ? "This file is not valid JSON. Check commas, quotes, and brackets, then try again." : (err as Error).message);
    }
  }

  async function downloadBatchTemplate() {
    setBatchError("");
    setBatchTemplateLoading(true);
    try {
      const examples = await Promise.all(
        MODEL_SYSTEMS.map(async ({ key }) => [key, await request<DatasetExample>(`/api/workspace/examples/${key}?variant=normal`)] as const),
      );
      downloadJson(makeComponentBundle(Object.fromEntries(examples)), "all-aircraft-components-example.json");
    } catch (err) {
      setBatchError((err as Error).message);
    } finally {
      setBatchTemplateLoading(false);
    }
  }

  async function importBatchFile(file: File) {
    setBatchError("");
    setBatchResults(null);
    setBatchPayload(null);
    setBatchFileName("");
    setBatchQuality(null);
    setBatchAcknowledged(false);
    try {
      if (file.size > 20_000_000) throw new Error("Choose an all-components JSON file smaller than 20 MB.");
      setBatchPayload(parseComponentBundle(await file.text()));
      setBatchFileName(file.name);
    } catch (err) {
      setBatchError(err instanceof SyntaxError ? "This file is not valid JSON. Check its commas, quotes, and brackets." : (err as Error).message);
    }
  }

  async function runBatch(confirmReview = false) {
    if (!batchPayload || batchRunning || !batchAcknowledged) return;
    setBatchError("");
    setBatchResults(null);
    setBatchRunning(true);
    setHistorySaveNotice(null);
    batchController.current?.abort();
    const active = new AbortController();
    batchController.current = active;
    try {
      const fingerprint = JSON.stringify(batchPayload);
      let quality = batchQuality?.fingerprint === fingerprint ? batchQuality : null;
      if (!quality) {
        const outcomes = await Promise.allSettled(MODEL_SYSTEMS.map((s) => postJson<PreflightReport>(s.preflight, batchPayload[s.key], active.signal)));
        const checks = Object.fromEntries(
          MODEL_SYSTEMS.map(({ key }, index) => {
            const outcome = outcomes[index];
            return [
              key,
              outcome.status === "fulfilled"
                ? { ok: true as const, report: outcome.value }
                : { ok: false as const, error: (outcome.reason as Error)?.message || "Quality check failed." },
            ];
          }),
        );
        quality = {
          fingerprint,
          checks,
          schemaValid: Object.values(checks).every((c) => c.ok),
          reviewRequired: Object.values(checks).some((c) => c.ok && c.report.review_required),
        };
        setBatchQuality(quality);
      }
      if (!quality.schemaValid) {
        setBatchError("One or more component requests failed their schema check. Fix those sections in the JSON bundle, then upload it again. No predictions were run.");
        return;
      }
      if (quality.reviewRequired && !confirmReview) return;
      const outcomes = await Promise.allSettled(MODEL_SYSTEMS.map((s) => postJson<PredictionResponse>(s.endpoint, batchPayload[s.key], active.signal)));
      const results: BatchResults = Object.fromEntries(
        MODEL_SYSTEMS.map(({ key }, index) => {
          const outcome = outcomes[index];
          return [
            key,
            outcome.status === "fulfilled"
              ? { ok: true as const, data: outcome.value }
              : { ok: false as const, error: (outcome.reason as Error)?.message || "Prediction request failed." },
          ];
        }),
      );
      setBatchResults(results);
      setHistorySaveNotice({ kind: "info", text: "Saving successful subsystem results to prediction history…" });
      const saves = MODEL_SYSTEMS.flatMap(({ key }) => {
        const outcome = results[key];
        if (!outcome?.ok) return [];
        return [saveHistory(key, outcome.data, JSON.stringify(batchPayload[key]), batchFileName ? "uploaded_file" : "all_components_bundle")];
      });
      const saved = (await Promise.allSettled(saves)).filter((o) => o.status === "fulfilled").length;
      setHistorySaveNotice(
        saves.length === 0
          ? { kind: "error", text: "No subsystem predictions were returned, so no results were saved to history." }
          : saved === saves.length
            ? { kind: "success", text: `Saved ${saved} subsystem results to prediction history. Raw sensor values were not stored.` }
            : { kind: "error", text: `Saved ${saved} of ${saves.length} subsystem results; some could not be saved. Check the backend and refresh Model coverage.` },
      );
    } finally {
      setBatchRunning(false);
    }
  }

  async function downloadBatchReport() {
    if (!batchResults || !batchPayload) return;
    setBatchError("");
    try {
      const reports = await Promise.all(
        MODEL_SYSTEMS.map(async ({ key, title }) => {
          const outcome = batchResults[key];
          if (!outcome?.ok) return [key, { status: "request_failed", error: outcome?.error || "No result returned." }] as const;
          const check = batchQuality?.checks?.[key];
          const report = await makePredictionReport({
            component: key,
            title,
            releaseId: evidence?.release_id,
            requestText: JSON.stringify(batchPayload[key]),
            inputSummary: summarizeRequest(key, JSON.stringify(batchPayload[key])).detail,
            source: batchFileName ? "User-uploaded all-components file" : "User-supplied all-components request",
            preflight: check?.ok ? check.report : { status: "not_available" },
            prediction: outcome.data,
          });
          return [key, report] as const;
        }),
      );
      const record = {
        report_schema: "aircraft-predictive-maintenance-batch-report/v1",
        created_at_utc: new Date().toISOString(),
        model_release: evidence?.release_id || "unavailable",
        reports: Object.fromEntries(reports),
        limitations: [
          "Independent subsystem predictions; this is not a combined aircraft-level model.",
          "Research prototype output only; not approved for aircraft maintenance decisions.",
          "Raw sensor values are excluded; each successful subsystem includes a request-text SHA-256 digest.",
        ],
      };
      downloadJson(record, `all-components-prediction-report-${record.created_at_utc.slice(0, 10)}.json`);
    } catch (err) {
      setBatchError((err as Error).message || "Could not create the all-components report.");
    }
  }

  const requestSummary = useMemo(() => summarizeRequest(component, input), [component, input]);
  const fuelMetrics = evidence?.fuel_evaluation?.metrics;
  const predictions: Record<string, PredictionValue> =
    result?.predictions ||
    Object.fromEntries((["rul", "soh", "fault"] as const).filter((key) => result?.[key]).map((key) => [key, result![key] as PredictionValue]));
  const engineRul = result?.component === "Engine" && typeof result.rul?.value === "number" ? result.rul.value : null;
  const engineRisk = engineRul == null ? null : engineRul <= 30 ? "High" : engineRul <= 60 ? "Medium" : "Low";
  const batchFingerprintMatches = batchPayload != null && batchQuality?.fingerprint === JSON.stringify(batchPayload);

  return (
    <PageBody>
      <PageHeader
        eyebrow="Trained models · research prototype"
        title="AI predictions"
        description="Choose an aircraft system, add its sensor data, and review a model-generated assessment. Not approved for aircraft maintenance decisions."
        actions={
          <Card className="flex items-center gap-3 px-3 py-2" aria-live="polite">
            <ConnectionDot status={apiStatus} />
            <span className="min-w-0">
              <span className="block text-[12px] font-medium">
                {apiStatus === "checking" ? "Connecting to prediction service" : apiStatus === "offline" ? "Prediction service unavailable" : "Prediction service connected"}
              </span>
              <span className="block truncate text-[11px] text-muted-foreground">
                {apiStatus === "checking"
                  ? "Checking FastAPI…"
                  : apiStatus === "offline"
                    ? "Start the backend, then retry."
                    : evidence
                      ? `Model release: ${evidence.release_id}`
                      : "Model release details unavailable"}
              </span>
            </span>
            <Button variant="outline" size="sm" onClick={() => setReload((v) => v + 1)}>
              <CircleDot /> Check
            </Button>
          </Card>
        }
      />

      {evidenceError ? (
        <div className="mb-4">
          <ErrorBox title="Could not load model release details">
            <p>{evidenceError}</p>
            <p>Confirm the backend is running, then use Check to retry.</p>
          </ErrorBox>
        </div>
      ) : null}

      <ol className="mb-5 grid gap-3 sm:grid-cols-3" aria-label="Prediction steps">
        {[
          ["01", "Choose a system", "Select the component to assess"],
          ["02", "Add sensor data", "Use a sample or your JSON/CSV file"],
          ["03", "Review the result", "Check estimates and warnings"],
        ].map(([n, title, sub], i) => (
          <li key={n} className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted font-mono text-[11px] font-medium">{n}</span>
            <span className="min-w-0 flex-1">
              <span className="block text-[13px] font-semibold">{title}</span>
              <span className="block text-[11px] text-muted-foreground">{sub}</span>
            </span>
            {i < 2 ? <ArrowRight className="h-4 w-4 text-ink-4" /> : <CheckCircle2 className="h-4 w-4 text-ink-4" />}
          </li>
        ))}
      </ol>

      <div className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Step 1 · Choose an aircraft system</div>
      <nav aria-label="Aircraft subsystem" className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {MODEL_SYSTEMS.map(({ key, title, subtitle, metric }) => {
          const Icon = SYSTEM_ICONS[key];
          const selected = component === key;
          return (
            <button
              key={key}
              type="button"
              aria-pressed={selected}
              onClick={() => setComponent(key)}
              className={cn(
                "relative rounded-xl border bg-card p-4 text-left transition-colors",
                selected ? "border-primary" : "border-border hover:border-hairline-strong hover:bg-hover",
              )}
            >
              {selected ? <motion.span layoutId="system-ring" className="pointer-events-none absolute inset-0 rounded-xl ring-1 ring-primary" /> : null}
              <span className={cn("flex h-8 w-8 items-center justify-center rounded-md", selected ? "bg-primary text-primary-foreground" : "bg-muted")}>
                <Icon className="h-4 w-4" />
              </span>
              <span className="mt-3 block text-[13px] font-semibold">{title}</span>
              <span className="block text-[11px] text-muted-foreground">{subtitle}</span>
              <Badge variant="muted" className="mt-2 rounded-md uppercase tracking-wide">
                {metric}
              </Badge>
            </button>
          );
        })}
      </nav>

      <Card className="mt-4 flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
        <label htmlFor="history-asset-id" className="min-w-0">
          <span className="block text-[13px] font-medium">Optional project asset ID</span>
          <span className="block text-[11px] text-muted-foreground">
            Groups saved prediction runs in Model coverage. Use an internal ID, not a registration number or personal information.
          </span>
        </label>
        <Input id="history-asset-id" maxLength={80} value={assetId} onChange={(e) => setAssetId(e.target.value)} placeholder="e.g. TEST-AIRCRAFT-01" className="sm:w-64" />
      </Card>

      <div className="mt-4 grid grid-cols-1 items-start gap-4 xl:grid-cols-2">
        <Section
          title={
            <span className="flex items-center gap-2">
              <FileJson2 className="h-4 w-4" /> Step 2 · Provide sensor data
            </span>
          }
          description="Start with a dataset example or load your own JSON/CSV file."
        >
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <label htmlFor="sample-variant" className="text-[12px] text-muted-foreground">
                Dataset example
              </label>
              <NativeSelect id="sample-variant" value={variant} onChange={(e) => setVariant(e.target.value as "normal" | "challenge")}>
                <option value="normal">Normal example{component === "hydraulic" ? " (stable)" : ""}</option>
                <option value="challenge">Challenge example{component === "hydraulic" ? " (unstable)" : ""}</option>
              </NativeSelect>
            </div>
            <p className="text-[12px] text-muted-foreground">
              {loading ? "Loading dataset example…" : matchesSample ? sample?.source : "Custom JSON — dataset reference labels do not apply"}
            </p>
            <UnitGuidance components={MODEL_SYSTEMS.filter((s) => s.key === component)} />

            <div
              role="status"
              aria-live="polite"
              className={cn(
                "flex items-start gap-3 rounded-lg border p-3",
                requestSummary.state === "invalid" ? "border-destructive/30 bg-destructive/5" : "border-border bg-muted/40",
              )}
            >
              {requestSummary.state === "ready" ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> : <FileJson2 className="mt-0.5 h-4 w-4 shrink-0" />}
              <span className="min-w-0 flex-1">
                <span className="block text-[13px] font-semibold">{requestSummary.title}</span>
                <span className="block text-[12px] text-muted-foreground">{requestSummary.detail}</span>
              </span>
              {requestSummary.state === "ready" ? <Badge variant="default">JSON OK</Badge> : null}
            </div>

            {inputQuality?.sourceText === input ? <InputQualityReport report={inputQuality.report} /> : null}

            <Disclosure summary={<><FileJson2 className="h-3.5 w-3.5" /> View or edit full JSON <Badge variant="muted">Advanced</Badge></>}>
              <label className="mb-1.5 block text-[12px] font-medium" htmlFor="model-input">
                Prediction request JSON
              </label>
              <Textarea
                id="model-input"
                spellCheck={false}
                value={input}
                onChange={(e) => edit(e.target.value)}
                placeholder="Select an example or import a .json request file"
                className="h-80"
              />
              <p className="mt-1.5 text-[11px] text-muted-foreground">The complete request is sent to the model API. JSON files must contain one object, not a list.</p>
            </Disclosure>

            <label className="flex items-start gap-2.5 rounded-lg border border-border p-3 text-[12px] text-ink-2">
              <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[var(--ink)]" checked={inputAcknowledged} onChange={(e) => setInputAcknowledged(e.target.checked)} />
              <span>
                I checked that this request uses the expected fields, sequence, and units. The app cannot verify physical units or whether these readings describe a real
                aircraft condition.
              </span>
            </label>

            <div className="flex flex-wrap gap-2">
              <Button onClick={() => runPrediction(false)} disabled={loading || running || !input.trim() || !inputAcknowledged}>
                {running ? <Loader2 className="animate-spin" /> : <Sparkles />}
                {running ? (runStage === "quality" ? "Checking input…" : "Running model…") : "Check data & predict"}
              </Button>
              {inputQuality?.sourceText === input && inputQuality.report.review_required && !running && !result && requestSummary.state === "ready" ? (
                <Button variant="outline" onClick={() => runPrediction(true)}>
                  I reviewed the warnings — continue
                </Button>
              ) : null}
              <FileButton label="Import JSON / CSV" accept=".json,.csv,application/json,text/csv" onFile={importRequestFile} />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="ghost" size="sm" onClick={() => exampleText && edit(exampleText)} disabled={!sample || loading || running}>
                Reset to selected example
              </Button>
              <Button variant="ghost" size="sm" onClick={() => sample && downloadJson(sample.payload, `${component}-request-example.json`)} disabled={!sample || loading}>
                Download example JSON
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => sample && downloadContent(payloadToCsv(component, sample.payload), `${component}-example-template.csv`, "text/csv;charset=utf-8")}
                disabled={!sample || loading}
              >
                Download CSV example
              </Button>
            </div>
            {fileName ? (
              <Notice kind="success">
                File ready: <strong>{fileName}</strong>. Review the JSON, then run the prediction.
              </Notice>
            ) : null}
            {sample?.evaluation_note ? <p className="text-[11px] text-muted-foreground">{sample.evaluation_note}</p> : null}
          </div>
        </Section>

        <Section
          title={
            <span className="flex items-center gap-2">
              <Cpu className="h-4 w-4" /> Step 3 · Prediction results
            </span>
          }
          description="Model output and review guidance appear here."
          className="xl:sticky xl:top-4"
        >
          <div className="space-y-3" aria-live="polite">
            {historySaveNotice && !batchResults ? <Notice kind={historySaveNotice.kind}>{historySaveNotice.text}</Notice> : null}
            {error ? (
              <ErrorBox title="Could not run prediction">
                <p>{error}</p>
              </ErrorBox>
            ) : null}
            {running ? (
              <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/40 p-4">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span>
                  <span className="block text-[13px] font-semibold">Running prediction</span>
                  <span className="block text-[12px] text-muted-foreground">Sending your request to the selected model…</span>
                </span>
              </div>
            ) : null}
            {!result && !running && !error ? (
              <EmptyState icon={Activity} title="Ready when you are">
                Choose a system, review its sample data, then run a prediction to see the model output here.
              </EmptyState>
            ) : null}
            {engineRisk ? (
              <div className={cn("rounded-lg border p-3", engineRisk === "High" ? "border-destructive/30 bg-destructive/5" : "border-border bg-muted/40")} role="status">
                <div className={cn("text-[13px] font-semibold", engineRisk === "High" && "text-destructive")}>Prototype maintenance-risk band: {engineRisk}</div>
                <div className="mt-0.5 text-[12px] text-muted-foreground">
                  Demonstration RUL thresholds (High: 30 cycles or less; Medium: 31–60; Low: above 60). This is not an approved maintenance limit.
                </div>
              </div>
            ) : null}
            {Object.entries(predictions).map(([name, prediction]) => (
              <PredictionCard key={name} name={name} result={prediction} />
            ))}
            {result?.component === "Fuel System" ? <FuelResultCard result={result} metrics={fuelMetrics} /> : null}
            {result?.warnings?.map((warning, index) => (
              <Notice key={index} kind="info">
                {warning}
              </Notice>
            ))}
            {result ? <ResultMeaning component={component} /> : null}
            {result ? (
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="outline" size="sm" onClick={downloadPredictionReport} disabled={reportSaving || !runRecord}>
                  <Download /> {reportSaving ? "Preparing report…" : "Download prediction report (.json)"}
                </Button>
                <span className="text-[11px] text-muted-foreground">Includes model/check details and an input hash, not raw sensor values.</span>
              </div>
            ) : null}
            {reportError ? <ErrorBox title="Report not created">{reportError}</ErrorBox> : null}
            {matchesSample && sample ? (
              <Disclosure summary="Reference labels for this dataset example">
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap font-mono text-[11px]">{JSON.stringify(sample.actual, null, 2)}</pre>
              </Disclosure>
            ) : null}
            {result ? (
              <Disclosure summary="Complete backend response">
                <pre className="max-h-80 overflow-auto whitespace-pre-wrap font-mono text-[11px]">{JSON.stringify(result, null, 2)}</pre>
              </Disclosure>
            ) : null}
          </div>
        </Section>
      </div>

      <Card className="mt-4">
        <Collapsible open={batchOpen} onOpenChange={setBatchOpen}>
          <CollapsibleTrigger className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left">
            <span className="flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-md bg-muted">
                <Layers className="h-4 w-4" />
              </span>
              <span>
                <span className="block text-sm font-semibold">Upload all components together</span>
                <span className="block text-[12px] text-muted-foreground">One JSON bundle sends a separate request to each of the five model endpoints.</span>
              </span>
            </span>
            <Badge variant="muted">{batchOpen ? "Hide" : "Show"}</Badge>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="space-y-3 border-t border-border px-5 py-4">
              <p className="text-[12px] text-ink-2">
                Use one top-level JSON object with the keys {BATCH_COMPONENT_KEYS.join(", ")}. Each key contains the same request object you would upload for that
                subsystem by itself.
              </p>
              <UnitGuidance components={MODEL_SYSTEMS} />
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={downloadBatchTemplate} disabled={batchTemplateLoading || batchRunning}>
                  {batchTemplateLoading ? <Loader2 className="animate-spin" /> : <Download />}
                  {batchTemplateLoading ? "Preparing example…" : "Download all-components example"}
                </Button>
                <FileButton label="Choose bundle JSON" accept=".json,application/json" disabled={batchRunning} onFile={importBatchFile} />
                <Button
                  size="sm"
                  onClick={() => runBatch(false)}
                  disabled={!batchPayload || !batchAcknowledged || batchRunning || apiStatus !== "online" || (batchFingerprintMatches && !batchQuality?.schemaValid)}
                >
                  {batchRunning ? <Loader2 className="animate-spin" /> : <Sparkles />}
                  {batchRunning ? "Checking / running…" : "Check data & run five models"}
                </Button>
                {batchPayload && !batchRunning ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setBatchPayload(null);
                      setBatchFileName("");
                      setBatchResults(null);
                      setBatchError("");
                      setBatchQuality(null);
                      setBatchAcknowledged(false);
                    }}
                  >
                    Clear bundle
                  </Button>
                ) : null}
              </div>
              {batchFileName ? (
                <Notice kind="success">
                  Bundle ready: <strong>{batchFileName}</strong>. Each component request will be checked before any predictions run.
                </Notice>
              ) : null}
              {batchPayload ? (
                <label className="flex items-start gap-2.5 rounded-lg border border-border p-3 text-[12px] text-ink-2">
                  <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[var(--ink)]" checked={batchAcknowledged} onChange={(e) => setBatchAcknowledged(e.target.checked)} />
                  <span>
                    I checked that all five requests use the expected fields, sequence, and units. The app cannot verify physical units or whether these readings describe
                    a real aircraft condition.
                  </span>
                </label>
              ) : null}
              {batchError ? (
                <ErrorBox title="All-components check needs attention">
                  <p>{batchError}</p>
                </ErrorBox>
              ) : null}
              {batchFingerprintMatches && batchQuality ? (
                <section aria-label="All-components quality checks" className="space-y-2">
                  <div className="text-[13px] font-semibold">Pre-prediction data checks</div>
                  <p className="text-[12px] text-muted-foreground">
                    Each subsystem was checked separately; range warnings use the saved model&apos;s observed training support, not aircraft safety limits.
                  </p>
                  <div className="grid gap-3 lg:grid-cols-2">
                    {MODEL_SYSTEMS.map(({ key, title }) => {
                      const check = batchQuality.checks[key];
                      return (
                        <article key={key} className="space-y-2">
                          <div className="text-[12px] font-semibold">{title}</div>
                          {check.ok ? <InputQualityReport report={check.report} /> : <p className="text-[12px] text-destructive">Schema check failed: {check.error}</p>}
                        </article>
                      );
                    })}
                  </div>
                  {batchQuality.schemaValid && batchQuality.reviewRequired && !batchRunning && !batchResults ? (
                    <Button variant="outline" size="sm" onClick={() => runBatch(true)}>
                      I reviewed the warnings — continue to five predictions
                    </Button>
                  ) : null}
                </section>
              ) : null}
              {batchResults ? (
                <div className="grid gap-3 lg:grid-cols-2" aria-live="polite">
                  {MODEL_SYSTEMS.map(({ key, title }) => {
                    const outcome = batchResults[key];
                    return (
                      <article key={key} className="space-y-2 rounded-lg border border-border p-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[13px] font-semibold">{title}</span>
                          <Badge variant={outcome.ok ? "muted" : "danger"}>{outcome.ok ? "Response received" : "Request failed"}</Badge>
                        </div>
                        {outcome.ok ? (
                          <>
                            <p className="text-[12px] text-ink-2">{batchSummary(key, outcome.data)}</p>
                            <ResultMeaning component={key} />
                            <Disclosure summary={`Full ${title.toLowerCase()} response`}>
                              <pre className="max-h-64 overflow-auto whitespace-pre-wrap font-mono text-[11px]">{JSON.stringify(outcome.data, null, 2)}</pre>
                            </Disclosure>
                          </>
                        ) : (
                          <p className="text-[12px] text-destructive">{outcome.error}</p>
                        )}
                      </article>
                    );
                  })}
                </div>
              ) : null}
              {historySaveNotice && batchResults ? <Notice kind={historySaveNotice.kind}>{historySaveNotice.text}</Notice> : null}
              {batchResults ? (
                <Button variant="outline" size="sm" onClick={downloadBatchReport}>
                  <Download /> Download all-components report (.json)
                </Button>
              ) : null}
              <p className="text-[11px] text-muted-foreground">
                A convenience workflow, not one combined aircraft-level model. Each subsystem runs independently; fuel remains experimental and all results are
                research-only.
              </p>
            </div>
          </CollapsibleContent>
        </Collapsible>
      </Card>
    </PageBody>
  );
}
