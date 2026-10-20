"use client";

import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { BarChart } from "@/components/charts/bar-chart";
import { TrendChart } from "@/components/charts/trend-chart";
import { IntervalBar, ScoreBars } from "@/components/charts/gauges";
import { Disclosure, SYSTEM_ICONS } from "@/components/models/shared";
import { formatNumber, labelOf } from "@/lib/models/catalog";
import { acceptance, importanceGroups, inputTrace, modelInputGroups, modelName, outputSummary, type ModelRun } from "@/lib/models/triage";
import { createSectionResultsFile } from "@/lib/models/section-results";
import { triage } from "@/lib/models/triage";
import type { PredictionValue } from "@/lib/models/types";
import { downloadJson } from "@/lib/download";
import { DANGER, GOOD } from "@/lib/viz";

function Interval({ title, result }: { title: string; result?: PredictionValue }) {
  if (!result || typeof result.value !== "number") return null;
  return <IntervalBar title={title} value={result.value} lower={result.lower} upper={result.upper} unit={result.unit} format={(v) => formatNumber(v)} />;
}

function Confidence({ title, rows, note }: { title: string; rows: { name: string; label: string; confidence?: number }[]; note: string }) {
  const valid = rows.filter((row) => typeof row.confidence === "number");
  if (!valid.length) return null;
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <div className="mb-2.5 text-[12px] font-medium">{title}</div>
      <ScoreBars rows={valid.map((r) => ({ key: r.name, label: `${labelOf(r.name)}: ${r.label}`, value: (r.confidence ?? 0) * 100 }))} format={(v) => formatNumber(v)} />
      <p className="mt-2.5 text-[10px] leading-4 text-muted-foreground">{note}</p>
    </div>
  );
}

function InputTraceCharts({ run }: { run: ModelRun }) {
  const trace = inputTrace(run);
  if (!trace || !trace.series.some((s) => s.rows.length)) return null;
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span className="text-[12px] font-medium">{trace.title}</span>
        <span className="text-[10px] text-muted-foreground">Dataset input, not a live sensor stream</span>
      </div>
      <div className="space-y-3">
        {trace.series.map((s) => (
          <div key={s.name}>
            <div className="mb-1 text-[11px] text-muted-foreground">{s.name}</div>
            <TrendChart
              data={s.rows.map((r) => ({ x: r.step, value: r.value }))}
              label={s.name}
              headline="none"
              goodDirection="neutral"
              zeroBased={false}
              height={110}
              xFormat={(x) => `${trace.xLabel} ${typeof x === "number" ? formatNumber(x, 1) : x}`}
              valueFormat={(v) => formatNumber(v)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

function OutputVisualization({ run }: { run: ModelRun }) {
  const { system, result } = run;
  if (!result) return null;
  if (system.key === "engine")
    return (
      <div className="space-y-3">
        <Interval title="Engine RUL estimate and interval" result={result.rul} />
        <InputTraceCharts run={run} />
      </div>
    );
  if (system.key === "battery")
    return (
      <div className="space-y-3">
        <Interval title="Battery SOH estimate and interval" result={result.soh} />
        <Interval title="Battery RUL estimate and interval" result={result.rul} />
        <InputTraceCharts run={run} />
      </div>
    );
  if (system.key === "hydraulic")
    return (
      <Confidence
        title="Hydraulic model confidence by output"
        rows={Object.entries(result.predictions || {}).map(([name, value]) => ({ name, label: String(value.label ?? `class ${value.value}`), confidence: value.calibrated_confidence }))}
        note="Bars show the returned confidence estimates; class codes are labels, not a severity scale. Unaccepted outputs require review."
      />
    );
  if (system.key === "landing-gear")
    return (
      <div className="space-y-3">
        <Confidence
          title="Landing-gear fault classification confidence"
          rows={[{ name: "fault", label: String(result.fault?.label ?? `class ${result.fault?.value}`), confidence: result.fault?.calibrated_confidence }]}
          note="Confidence belongs to the dataset-trained classifier; it is not an aircraft safety probability."
        />
        <Interval title="Landing-gear RUL estimate and interval" result={result.rul} />
      </div>
    );
  const total = result.input_samples ?? 0;
  const flagged = Math.max(0, Math.min(total, result.flagged_samples ?? 0));
  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-border bg-background p-3">
        <div className="mb-1 text-[12px] font-medium">Fuel detector output counts</div>
        <BarChart
          height={180}
          data={[
            { label: "Flagged", value: flagged, color: DANGER },
            { label: "Not flagged", value: Math.max(0, total - flagged), color: GOOD },
          ]}
        />
        <p className="mt-1 text-[10px] text-muted-foreground">Counts come from the detector response; the API does not return per-sample alert positions.</p>
      </div>
      <InputTraceCharts run={run} />
    </div>
  );
}

const displayValue = (value: unknown) =>
  typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: 5 }) : typeof value === "boolean" ? (value ? "Yes" : "No") : String(value ?? "—");

function ModelInputDetails({ run }: { run: ModelRun }) {
  const inputs = modelInputGroups(run);
  const importance = importanceGroups(run).filter((g) => g.rows.length);
  return (
    <Disclosure summary="View component inputs, sub-parts and model features" className="mt-3">
      <div className="space-y-4">
        <div>
          <div className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Data sent to the model</div>
          <div className="grid gap-3 xl:grid-cols-2">
            {inputs.map((group) => (
              <section key={group.title} className="rounded-lg border border-border p-3">
                <div className="text-[12px] font-medium">{group.title}</div>
                {group.note ? <p className="mt-0.5 text-[11px] text-muted-foreground">{group.note}</p> : null}
                <dl className="mt-2 grid grid-cols-1 gap-x-4 sm:grid-cols-2">
                  {Object.entries(group.values).map(([name, value]) => (
                    <div key={name} className="flex min-w-0 items-baseline justify-between gap-2 border-b border-rowline py-1">
                      <dt className="truncate text-[11px] text-muted-foreground" title={name}>
                        {labelOf(name)}
                      </dt>
                      <dd className="break-all text-right font-mono text-[11px]">{displayValue(value)}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            ))}
          </div>
        </div>
        <div>
          <div className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Model features and sub-models</div>
          {importance.length ? (
            <div className="grid gap-3 xl:grid-cols-2">
              {importance.map((group) => (
                <section key={group.title} className="rounded-lg border border-border p-3">
                  <div className="mb-2.5 text-[12px] font-medium capitalize">{group.title}</div>
                  <ScoreBars
                    suffix={run.system.key === "fuel-system" ? " score" : "%"}
                    rows={group.rows.map((row) => ({ key: row.feature, label: labelOf(row.feature), value: Number(row.relative_importance) || 0 }))}
                    format={(v) => formatNumber(v)}
                  />
                </section>
              ))}
            </div>
          ) : (
            <p className="rounded-lg border border-border p-3 text-[11px] text-muted-foreground">
              This endpoint does not return feature-importance values. The input fields above are the data provided to its detector; they are not ranked causes.
            </p>
          )}
          <p className="mt-2 text-[10px] leading-4 text-muted-foreground">
            Importance is global model-level importance, not a case-specific explanation. Fuel scores are envelope deviations, not feature-importance percentages.
          </p>
        </div>
      </div>
    </Disclosure>
  );
}

export function RunCard({ run, detailed = false }: { run: ModelRun; detailed?: boolean }) {
  const { system, example, result, error } = run;
  const Icon = SYSTEM_ICONS[system.key];
  const accepted = result ? acceptance(result) : null;
  const experimental = system.key === "fuel-system";
  const needsReview = experimental || accepted === false;
  const status = error
    ? "Model unavailable"
    : experimental
      ? "Experimental — review required"
      : accepted === false
        ? "Model requested review"
        : accepted === true
          ? "Input passed model checks"
          : "Review model output";
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-center gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-muted">
            <Icon className="h-4 w-4" />
          </span>
          <div>
            <h3 className="font-sans text-sm font-semibold tracking-normal">{system.title}</h3>
            <p className="text-[11px] text-muted-foreground">Dataset example: {example?.source || "not available"}</p>
          </div>
        </div>
        <Badge variant={error ? "danger" : needsReview ? "outline" : "muted"}>
          {error || needsReview ? <AlertTriangle className="h-3 w-3" /> : <CheckCircle2 className="h-3 w-3" />}
          {status}
        </Badge>
      </div>
      {error ? (
        <p className="mt-3 text-[12px] text-destructive">{error}</p>
      ) : result ? (
        <>
          <p className="mt-3 text-[13px] leading-6">{outputSummary(system.key, result)}</p>
          <div className="mt-3">
            <OutputVisualization run={run} />
          </div>
          <p className="mt-2 break-words text-[10px] text-muted-foreground">Model: {modelName(result)}</p>
          {result.warnings?.length ? (
            <Disclosure className="mt-3" summary="Model limitations and warnings">
              <ul className="list-disc space-y-1 pl-5 text-[12px] text-ink-2">
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </Disclosure>
          ) : null}
          {detailed ? <ModelInputDetails run={run} /> : null}
        </>
      ) : (
        <p className="mt-3 text-[12px] text-muted-foreground">Waiting for a backend response.</p>
      )}
    </Card>
  );
}

export function downloadSectionResults(section: "fleet" | "maintenance", variant: string, runs: ModelRun[]) {
  const report = createSectionResultsFile({
    section,
    variant,
    entries: runs.map((run) => {
      const status = triage(run);
      return {
        component: run.system.key,
        title: run.system.title,
        level: status.level,
        reason: status.reason,
        source: run.example?.source,
        model: run.result ? modelName(run.result) : null,
        summary: run.result ? outputSummary(run.system.key, run.result) : null,
        prediction: run.result || null,
        referenceLabels: run.example?.actual || null,
        error: run.error || null,
      };
    }),
  });
  downloadJson(report, `${section}-results-${report.created_at_utc.slice(0, 10)}.json`);
}
