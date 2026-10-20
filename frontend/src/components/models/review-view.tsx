"use client";

import { AlertTriangle, Download, Loader2, RefreshCw, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Stagger, StaggerItem } from "@/components/motion";
import { EmptyState, PageBody, PageHeader, StatCard } from "@/components/shell/page-parts";
import { RunCard, downloadSectionResults } from "@/components/models/run-card";
import { useModelRuns } from "@/hooks/use-model-runs";
import { ATTENTION_ORDER, triage, type AttentionLevel } from "@/lib/models/triage";
import { cn } from "@/lib/utils";

const LEVEL_NOTE: Record<AttentionLevel, string> = {
  Critical: "Positive fault/anomaly output on an example",
  Caution: "Abstention or input-support warning",
  Monitor: "No model alert for the example; not clearance",
  Unavailable: "Model endpoint returned an error",
};

export function ReviewView() {
  const { runs, loading, refresh } = useModelRuns("challenge");
  const groups = ATTENTION_ORDER.map((level) => ({ level, rows: runs.filter((r) => triage(r).level === level) }));

  return (
    <PageBody>
      <PageHeader
        eyebrow="Trained models · challenge examples"
        title="Model review"
        description="Per-component outputs grouped by model evidence. Critical means a model produced a positive fault/anomaly result; caution means a gate or input-support warning requires review."
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => downloadSectionResults("maintenance", "challenge", runs)} disabled={loading || runs.length === 0}>
              <Download /> Download results (.json)
            </Button>
            <Button size="sm" onClick={refresh} disabled={loading}>
              <RefreshCw className={loading ? "animate-spin" : undefined} /> Recheck components
            </Button>
          </>
        }
      />

      <Alert variant="muted" className="mb-4">
        <ShieldAlert />
        <AlertDescription>
          These are challenge examples from research datasets, not aircraft work orders or maintenance diagnoses. Review levels do not schedule work; fuel anomaly output
          is experimental.
        </AlertDescription>
      </Alert>

      <Stagger className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {groups.map(({ level, rows }) => (
          <StaggerItem key={level}>
            <StatCard
              label={level === "Critical" ? "Critical model flags" : level === "Caution" ? "Caution / review" : level}
              value={loading ? "—" : <span className={level === "Critical" && rows.length ? "text-destructive" : undefined}>{rows.length}</span>}
              sub={LEVEL_NOTE[level]}
            />
          </StaggerItem>
        ))}
      </Stagger>

      {loading ? (
        <div className="mt-4 flex items-center gap-3 rounded-xl border border-border bg-card p-4 text-[13px]">
          <Loader2 className="h-4 w-4 animate-spin" /> Running challenge examples through the five model endpoints…
        </div>
      ) : runs.length === 0 ? (
        <div className="mt-4 rounded-xl border border-border bg-card">
          <EmptyState icon={AlertTriangle} title="No model responses">
            Start the FastAPI backend and recheck.
          </EmptyState>
        </div>
      ) : (
        groups.map(({ level, rows }) => (
          <section key={level} className="mt-6" aria-label={`${level} component reviews`}>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2">
              <h2 className={cn("flex items-center gap-2 font-sans text-sm font-semibold tracking-normal", level === "Critical" && "text-destructive")}>
                {level} <Badge variant="muted">{rows.length}</Badge>
              </h2>
              <span className="text-[11px] text-muted-foreground">{LEVEL_NOTE[level]}</span>
            </div>
            {rows.length === 0 ? (
              <p className="text-[12px] text-muted-foreground">No components in this group for the current challenge examples.</p>
            ) : (
              <div className="grid gap-4 lg:grid-cols-2">
                {rows.map((run) => (
                  <div key={run.system.key} className="space-y-2">
                    <div
                      className={cn(
                        "rounded-lg border px-3 py-2 text-[12px] leading-5",
                        level === "Critical" ? "border-destructive/30 bg-destructive/5 text-destructive" : "border-border bg-muted/50 text-ink-2",
                      )}
                    >
                      <strong>
                        {run.system.title} — {level}:
                      </strong>{" "}
                      {triage(run).reason}
                    </div>
                    <RunCard run={run} detailed />
                  </div>
                ))}
              </div>
            )}
          </section>
        ))
      )}

      <p className="mt-6 text-[11px] leading-5 text-muted-foreground">
        No maintenance thresholds have been approved for operational use. Engine and battery RUL are shown with their estimate and interval; this screen does not
        invent a critical-cycle cutoff. Fuel predictions remain experimental.
      </p>
    </PageBody>
  );
}
