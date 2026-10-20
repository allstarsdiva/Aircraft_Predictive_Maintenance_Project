"use client";

import { useState } from "react";
import { Activity, CircleHelp, Download, Loader2, RefreshCw, Search, ServerCog } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { BarChart } from "@/components/charts/bar-chart";
import { Stagger, StaggerItem } from "@/components/motion";
import { EmptyState, PageBody, PageHeader, Section, StatCard } from "@/components/shell/page-parts";
import { ErrorBox, SYSTEM_ICONS } from "@/components/models/shared";
import { downloadSectionResults } from "@/components/models/run-card";
import { useModelRuns, usePredictionHistory } from "@/hooks/use-model-runs";
import { MODEL_SYSTEMS } from "@/lib/models/catalog";
import { ATTENTION_ORDER, triage } from "@/lib/models/triage";
import { downloadJson } from "@/lib/download";
import { DANGER } from "@/lib/viz";

const SOURCE_TEXT: Record<string, string> = {
  dataset_example: "Dataset example",
  uploaded_file: "Uploaded file",
  all_components_bundle: "All-components bundle",
};

export function CoverageView() {
  const { runs, loading, refresh, tick } = useModelRuns("normal");
  const history = usePredictionHistory(tick);
  const [assetFilter, setAssetFilter] = useState("");

  const ready = runs.filter((r) => r.result).length;
  const counts = ATTENTION_ORDER.map((level) => ({ level, count: runs.filter((r) => triage(r).level === level).length }));
  const review = counts.filter((c) => c.level === "Critical" || c.level === "Caution").reduce((a, c) => a + c.count, 0);
  const filtered = history.history.filter((e) => !assetFilter.trim() || (e.asset_id || "").toLowerCase().includes(assetFilter.trim().toLowerCase()));

  const actions = (
    <>
      <Button variant="outline" size="sm" onClick={() => downloadSectionResults("fleet", "normal", runs)} disabled={loading || runs.length === 0}>
        <Download /> Download results (.json)
      </Button>
      <Button size="sm" onClick={refresh} disabled={loading}>
        <RefreshCw className={loading ? "animate-spin" : undefined} /> Refresh snapshot
      </Button>
    </>
  );

  return (
    <PageBody>
      <PageHeader
        eyebrow="Trained models · dataset examples"
        title="Model coverage"
        description="Status of the connected backend and each subsystem model, checked on normal dataset examples."
        actions={actions}
      />

      <Alert variant="muted" className="mb-4">
        <CircleHelp />
        <AlertDescription>
          No aircraft registry or live telemetry is connected. The counts below are backend model checks on labelled dataset examples, not aircraft counts or fleet
          health.
        </AlertDescription>
      </Alert>

      <Stagger className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StaggerItem>
          <StatCard label="Aircraft connected" value="0" sub="No fleet or telemetry source" icon={ServerCog} />
        </StaggerItem>
        <StaggerItem>
          <StatCard label="Models responding" value={loading ? "—" : `${ready} / ${MODEL_SYSTEMS.length}`} sub="Live calls to saved endpoints" icon={Activity} />
        </StaggerItem>
        <StaggerItem>
          <StatCard label="Checks for review" value={loading ? "—" : review} sub="Dataset examples only" icon={CircleHelp} />
        </StaggerItem>
        <StaggerItem>
          <StatCard label="Fleet health" value="n/a" sub="No aircraft-level records" icon={ServerCog} />
        </StaggerItem>
      </Stagger>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[1.1fr_1.9fr]">
        <Section title="Model-check distribution" description="Grouping of the example responses; not fleet condition">
          {loading ? (
            <div className="flex h-[200px] items-center justify-center text-[13px] text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Checking models…
            </div>
          ) : (
            <BarChart height={220} data={counts.map((c) => ({ label: c.level, value: c.count, color: c.level === "Critical" ? DANGER : undefined }))} />
          )}
        </Section>
        <Section title="Subsystem service coverage" description="One representative dataset example per trained subsystem model">
          <ul className="divide-y divide-rowline">
            {(runs.length ? runs : MODEL_SYSTEMS.map((system) => ({ system }))).map((run) => {
              const Icon = SYSTEM_ICONS[run.system.key];
              const r = run as { result?: unknown; error?: string; example?: { source: string } };
              return (
                <li key={run.system.key} className="flex flex-wrap items-center justify-between gap-2 py-3">
                  <span className="flex items-center gap-3">
                    <span className="flex h-8 w-8 items-center justify-center rounded-md bg-muted">
                      <Icon className="h-4 w-4" />
                    </span>
                    <span>
                      <span className="block text-[13px] font-medium">{run.system.title}</span>
                      <span className="block text-[11px] text-muted-foreground">{r.example?.source || (r.error ? "Backend unavailable" : "Loading source…")}</span>
                    </span>
                  </span>
                  <Badge variant={r.result ? "muted" : loading ? "outline" : "danger"}>{r.result ? "Model responding" : loading ? "Checking" : "Unavailable"}</Badge>
                </li>
              );
            })}
          </ul>
        </Section>
      </div>

      <Section
        className="mt-4"
        title="Recent submitted prediction runs"
        description="Results saved from AI predictions. Example-based checks above are kept separate."
        actions={
          <>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-4" />
              <Input
                aria-label="Filter history by project asset ID"
                value={assetFilter}
                onChange={(e) => setAssetFilter(e.target.value)}
                placeholder="Filter asset ID"
                className="h-8 w-48 pl-8 text-[13px]"
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              disabled={!history.history.length || history.loading}
              onClick={() => {
                const exportedAt = new Date().toISOString();
                downloadJson({ schema: "aircraft-prediction-history-export/v1", exported_at_utc: exportedAt, entries: history.history }, `prediction-history-${exportedAt.slice(0, 10)}.json`);
              }}
            >
              <Download /> History (.json)
            </Button>
          </>
        }
      >
        {history.loading ? (
          <p className="flex items-center gap-2 text-[13px] text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading saved prediction history…
          </p>
        ) : history.error ? (
          <ErrorBox title="Could not load history">{history.error}</ErrorBox>
        ) : history.history.length === 0 ? (
          <EmptyState icon={Activity} title="No saved runs yet">
            Run a prediction in AI predictions to add it here. Example-based checks are not added to this history.
          </EmptyState>
        ) : filtered.length === 0 ? (
          <p className="text-[13px] text-muted-foreground">No saved runs match that asset ID.</p>
        ) : (
          <ul className="divide-y divide-rowline">
            {filtered.map((entry) => {
              const when = new Date(entry.created_at_utc);
              return (
                <li key={entry.id} className="grid gap-2 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-x-2">
                      <strong className="text-[13px] capitalize">{entry.component.replaceAll("-", " ")}</strong>
                      <span className="text-[11px] text-muted-foreground">{Number.isNaN(when.getTime()) ? entry.created_at_utc : when.toLocaleString()}</span>
                    </div>
                    <p className="mt-0.5 text-[12px] text-ink-2">{entry.summary}</p>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                      {entry.asset_id ? `Asset ${entry.asset_id}` : "Unassigned asset"} · {SOURCE_TEXT[entry.source] ?? "Edited request"}
                    </p>
                  </div>
                  <Badge variant={entry.review_required ? "outline" : "muted"}>{entry.review_required ? "Review required" : "Model checks passed"}</Badge>
                </li>
              );
            })}
          </ul>
        )}
        <p className="mt-3 text-[10px] leading-4 text-muted-foreground">
          History stores result summaries and an input digest only; it does not store raw sensor values. “Model checks passed” is not maintenance clearance.
        </p>
      </Section>
    </PageBody>
  );
}
