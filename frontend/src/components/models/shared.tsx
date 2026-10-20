"use client";

import type { ReactNode } from "react";
import { AlertTriangle, BatteryCharging, CheckCircle2, ChevronDown, Droplets, Fuel, Gauge, Info, Plane, type LucideIcon } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { IntervalBar, ScoreBars } from "@/components/charts/gauges";
import { getInputUnitGuidance } from "@/lib/models/input-guidance";
import { getResultGuidance } from "@/lib/models/result-guidance";
import { formatNumber, labelOf } from "@/lib/models/catalog";
import type { ComponentKey, PredictionResponse, PredictionValue, PreflightReport } from "@/lib/models/types";
import { cn } from "@/lib/utils";

export const SYSTEM_ICONS: Record<ComponentKey, LucideIcon> = {
  engine: Gauge,
  battery: BatteryCharging,
  hydraulic: Droplets,
  "landing-gear": Plane,
  "fuel-system": Fuel,
};

/** Native <details> styled as a quiet disclosure row. */
export function Disclosure({ summary, children, className, defaultOpen }: { summary: ReactNode; children: ReactNode; className?: string; defaultOpen?: boolean }) {
  return (
    <details className={cn("disclosure group rounded-lg border border-border bg-background", className)} open={defaultOpen}>
      <summary className="flex items-center justify-between gap-2 px-3 py-2.5 text-[13px] font-medium text-foreground">
        <span className="flex items-center gap-2">{summary}</span>
        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-t border-border px-3 py-3 text-[13px]">{children}</div>
    </details>
  );
}

export function ConnectionDot({ status }: { status: "checking" | "online" | "offline" }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-block h-2 w-2 shrink-0 rounded-full",
        status === "online" ? "bg-up" : status === "offline" ? "bg-destructive" : "animate-pulse bg-ink-4",
      )}
    />
  );
}

export function UnitGuidance({ components }: { components: { key: ComponentKey; title: string }[] }) {
  return (
    <Disclosure summary={<><Info className="h-3.5 w-3.5 text-ink-3" /> Review expected fields and units</>}>
      <div className="space-y-3">
        {components.map(({ key, title }) => (
          <section key={key}>
            {components.length > 1 ? <div className="mb-1 font-medium">{title}</div> : null}
            <ul className="list-disc space-y-1 pl-5 text-[12px] text-ink-2">
              {getInputUnitGuidance(key).map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </section>
        ))}
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          These notes document expected units; the API receives numeric values without unit tags and cannot confirm which units your file actually uses. Do not
          convert or rename unknown-unit fields by guesswork.
        </p>
      </div>
    </Disclosure>
  );
}

export function InputQualityReport({ report }: { report: PreflightReport | null | undefined }) {
  if (!report) return null;
  const review = report.review_required;
  return (
    <section
      aria-label="Upload quality check"
      role="status"
      className={cn("rounded-lg border p-3", review ? "border-hairline-strong bg-muted/60" : "border-border bg-background")}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-[13px] font-semibold">
          {review ? <AlertTriangle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
          {review ? "Input check needs your review" : "Format and range checks passed"}
        </span>
        <Badge variant="muted">{report.schema_valid ? "Request structure valid" : "Structure check failed"}</Badge>
      </div>
      {report.checks ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {Object.entries(report.checks).map(([task, check]) => (
            <article key={task} className="rounded-md border border-border bg-background p-2.5">
              <div className="flex items-center justify-between gap-2">
                <strong className="text-[12px] capitalize">{labelOf(task)}</strong>
                <Badge variant={check.status === "within_training_range" ? "muted" : "outline"}>
                  {check.status === "within_training_range" ? "Within training range" : check.status === "not_assessed" ? "Range not assessed" : "Review required"}
                </Badge>
              </div>
              {check.detail ? <p className="mt-1 text-[11px] text-muted-foreground">{check.detail}</p> : null}
              {check.hard_range_violations?.length ? (
                <p className="mt-1 text-[11px] text-destructive">Outside observed training range: {check.hard_range_violations.join(", ")}</p>
              ) : null}
              {check.tail_range_warnings?.length ? (
                <p className="mt-1 text-[11px] text-ink-2">Near edge of training range: {check.tail_range_warnings.join(", ")}</p>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}
      {report.notes?.length ? (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-[12px] text-ink-2">
          {report.notes.map((note, index) => (
            <li key={index}>{note}</li>
          ))}
        </ul>
      ) : null}
      <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
        This checks request structure and available model training support only. Request files contain no unit metadata, so units cannot be verified here; this is
        not a physical-condition or safety check.
      </p>
    </section>
  );
}

export function ResultMeaning({ component }: { component: string }) {
  const guidance = getResultGuidance(component);
  if (!guidance) return null;
  return (
    <aside aria-label="How to interpret this result" className="rounded-lg border border-border bg-muted/50 p-3">
      <div className="text-[12px] font-semibold">What this means</div>
      <p className="mt-1 text-[12px] text-ink-2">{guidance.meaning}</p>
      <p className="mt-1 text-[11px] text-muted-foreground">{guidance.caveat}</p>
    </aside>
  );
}

/** One model output (RUL, SOH, fault class or a hydraulic target). */
export function PredictionCard({ name, result }: { name: string; result: PredictionValue }) {
  const numeric = typeof result.value === "number";
  return (
    <article className="rounded-lg border border-border bg-background p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[13px] font-semibold capitalize">{labelOf(name)}</span>
        {result.accepted ? (
          <Badge variant="muted">
            <CheckCircle2 className="h-3 w-3" /> Within model checks
          </Badge>
        ) : (
          <Badge variant="outline">
            <AlertTriangle className="h-3 w-3" /> Review required
          </Badge>
        )}
      </div>
      <p className="mt-3 font-display text-[28px] font-semibold leading-none tabular-nums">
        {formatNumber(result.value)} <small className="font-sans text-sm font-normal text-muted-foreground">{result.unit || result.label || "class"}</small>
      </p>
      {numeric && result.lower !== undefined ? (
        <div className="mt-3">
          <IntervalBar title="Estimate and interval" value={result.value as number} lower={result.lower} upper={result.upper} unit={result.unit} format={(v) => formatNumber(v)} />
          <p className="mt-1 text-[11px] text-muted-foreground">
            Nominal {formatNumber((result.interval_level ?? 0) * 100)}% interval; observed coverage may be lower.
          </p>
        </div>
      ) : null}
      {result.calibrated_confidence !== undefined ? (
        <p className="mt-2 text-[12px] text-ink-2">Development confidence estimate: {formatNumber(result.calibrated_confidence * 100)}%</p>
      ) : null}
      {result.input_support?.hard_range_violations?.length ? (
        <p className="mt-2 text-[12px] text-destructive">Outside training range: {result.input_support.hard_range_violations.join(", ")}</p>
      ) : null}
      {result.input_support?.tail_range_warnings?.length ? (
        <Disclosure className="mt-2" summary="Unusual input values">
          {result.input_support.tail_range_warnings.join(", ")}
        </Disclosure>
      ) : null}
      {result.top_model_features?.length ? (
        <Disclosure className="mt-2" summary="What features influence this model?">
          <p className="mb-2 text-[11px] text-muted-foreground">Global model importance, not a case-specific cause. Bars are relative to this model's strongest feature.</p>
          <ScoreBars
            rows={result.top_model_features.map((item) => ({ key: item.feature, label: labelOf(item.feature), value: item.relative_importance }))}
            format={(v) => formatNumber(v)}
          />
        </Disclosure>
      ) : null}
    </article>
  );
}

export function FuelResultCard({ result, metrics }: { result: PredictionResponse; metrics?: { abnormal_detection_rate: number; normal_false_alarm_rate: number } }) {
  return (
    <article className="rounded-lg border border-border bg-background p-4">
      <Badge variant="outline">Experimental — readiness gate failed</Badge>
      <p className={cn("mt-3 font-display text-[26px] font-semibold leading-none", result.latest_is_abnormal && "text-destructive")}>
        {result.latest_is_abnormal ? "Abnormal alert" : "No current alert"}
      </p>
      <p className="mt-2 text-[13px] text-ink-2">
        {result.flagged_samples} of {result.input_samples} samples flagged · latest anomaly margin {formatNumber(result.latest_anomaly_margin)}
      </p>
      {result.largest_normal_envelope_deviations?.length ? (
        <Disclosure className="mt-3" summary="Largest departures from the normal envelope">
          <p className="mb-2 text-[11px] text-muted-foreground">Scaled differences from this model's normal-data reference; not proof of a fault or its cause.</p>
          <ScoreBars
            suffix=" scale"
            rows={result.largest_normal_envelope_deviations.map((item) => ({ key: item.feature, label: labelOf(item.feature), value: Math.min(100, item.scaled_deviation * 20) }))}
            format={(v) => formatNumber(v / 20)}
          />
        </Disclosure>
      ) : null}
      <p className="mt-3 text-[11px] text-muted-foreground">
        A missing alert does not establish a healthy fuel system.
        {metrics
          ? ` Nested development detection: ${formatNumber(metrics.abnormal_detection_rate * 100)}%; false alarms: ${formatNumber(metrics.normal_false_alarm_rate * 100)}%.`
          : " Detection remains limited; independent mission validation is unresolved."}
      </p>
    </article>
  );
}

export function Notice({ kind, children }: { kind: "info" | "success" | "error"; children: ReactNode }) {
  return (
    <Alert variant={kind === "error" ? "destructive" : "muted"} role="status">
      {kind === "success" ? <CheckCircle2 /> : kind === "error" ? <AlertTriangle /> : <Info />}
      <AlertDescription>{children}</AlertDescription>
    </Alert>
  );
}

export function ErrorBox({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Alert variant="destructive">
      <AlertTriangle />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{children}</AlertDescription>
    </Alert>
  );
}
