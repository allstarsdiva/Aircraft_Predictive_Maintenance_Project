"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { Progress } from "@chakra-ui/react";
import { ArrowDownRight, ArrowUpRight, ChevronLeft, Minus, PlaneTakeoff } from "lucide-react";
import { Card } from "@/components/ui/card";
import { RadialGauge, SegmentedBar, Sparkline } from "@/components/charts/gauges";
import { HoverLift, Stagger, StaggerItem } from "@/components/motion";
import { EmptyState, Metric, PageBody, Section } from "@/components/shell/page-parts";
import { COMPONENT_ICONS, RISK_COLOR, RiskBadge, StatusBadge } from "@/components/fleet/status";
import { useFleet } from "@/lib/fleet/fleet-provider";
import type { TrendPoint } from "@/lib/fleet/types";
import { DOWN, UP } from "@/lib/viz";

function TrendArrow({ data }: { data: TrendPoint[] }) {
  const delta = data.length > 1 ? data[data.length - 1].value - data[0].value : 0;
  if (Math.abs(delta) < 2) return <Minus className="h-3.5 w-3.5 text-ink-4" aria-label="steady" />;
  return delta > 0 ? <ArrowUpRight className="h-3.5 w-3.5 text-ink-2" aria-label="rising" /> : <ArrowDownRight className="h-3.5 w-3.5 text-ink-2" aria-label="falling" />;
}

export function BackLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="mb-4 inline-flex items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground">
      <ChevronLeft className="h-3.5 w-3.5" /> {children}
    </Link>
  );
}

export function AircraftView({ id }: { id: string }) {
  const { fleet } = useFleet();
  const aircraft = fleet.find((a) => a.id === id);

  if (!aircraft) {
    return (
      <PageBody>
        <BackLink href="/">Fleet overview</BackLink>
        <Card>
          <EmptyState icon={PlaneTakeoff} title="Aircraft not found">
            This simulated aircraft is not in the current fleet. Resyncing the fleet generates new aircraft.
          </EmptyState>
        </Card>
      </PageBody>
    );
  }

  const worstFailure = Math.max(...aircraft.components.map((c) => c.failureProbability));
  const lowestRul = Math.min(...aircraft.components.map((c) => c.rul));

  return (
    <PageBody>
      <BackLink href="/">Fleet overview</BackLink>

      <Card className="p-5">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
          <RadialGauge value={aircraft.overallHealth} size={96} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-mono text-2xl font-semibold tracking-tight">{aircraft.tail}</h1>
              <StatusBadge status={aircraft.status} />
            </div>
            <p className="mt-1 text-[13px] text-muted-foreground">
              {aircraft.model} · {aircraft.flightHours.toLocaleString("en-IN")} flight hours · simulated
            </p>
          </div>
          <div className="grid grid-cols-2 gap-6 sm:gap-10">
            <Metric label="Worst failure probability" value={`${worstFailure}%`} />
            <Metric label="Lowest RUL" value={<span className={lowestRul <= 30 ? "text-destructive" : undefined}>{lowestRul} <span className="text-xs font-normal text-muted-foreground">cyc</span></span>} />
          </div>
        </div>
      </Card>

      <Section className="mt-4" title="Component risk profile" description={`${aircraft.components.length} subsystems`}>
        <SegmentedBar segments={aircraft.components.map((c) => ({ key: c.type, color: RISK_COLOR[c.risk], title: `${c.type}: ${c.risk}` }))} />
        <div className="mt-2.5 flex flex-wrap gap-4 text-[11px] text-muted-foreground">
          {(["High", "Medium", "Low"] as const).map((r) => (
            <span key={r} className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: RISK_COLOR[r] }} />
              {r}
            </span>
          ))}
        </div>
      </Section>

      <div className="mb-2 mt-6 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Components</div>
      <Stagger className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {aircraft.components.map((c) => {
          const Icon = COMPONENT_ICONS[c.type];
          return (
            <StaggerItem key={c.type}>
              <HoverLift>
                <Link href={`/aircraft/${aircraft.id}/${c.slug}`} className="group block">
                  <Card className="p-4 transition-colors group-hover:border-hairline-strong">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-muted">
                          <Icon className="h-4 w-4" />
                        </span>
                        <span className="text-sm font-semibold">{c.type}</span>
                      </span>
                      <RiskBadge risk={c.risk} />
                    </div>
                    <div className="mt-3 flex items-end justify-between">
                      <div>
                        <div className="text-[11px] text-muted-foreground">RUL</div>
                        <div className={`font-display text-lg font-semibold tabular-nums ${c.risk === "High" ? "text-destructive" : ""}`}>
                          {c.rul} <span className="text-xs font-normal text-muted-foreground">cycles</span>
                        </div>
                      </div>
                      <Sparkline values={c.healthTrend.map((p) => p.value)} color={(c.healthTrend.at(-1)?.value ?? 0) >= (c.healthTrend[0]?.value ?? 0) ? UP : DOWN} width={92} height={30} fill />
                    </div>
                  </Card>
                </Link>
              </HoverLift>
            </StaggerItem>
          );
        })}
      </Stagger>

      <Section className="mt-6" title="Sensor snapshot" description="First sensor of each subsystem, positioned within its expected range">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {aircraft.components.map((c) => {
            const s = c.sensors[0];
            const pct = ((s.value - s.range[0]) / (s.range[1] - s.range[0])) * 100;
            return (
              <div key={c.type + s.key} className="rounded-lg border border-border p-3">
                <div className="truncate text-[11px] text-muted-foreground">
                  {c.type} · {s.label}
                </div>
                <div className="mt-1 flex items-baseline gap-1">
                  <span className="font-display text-lg font-semibold tabular-nums">{s.value}</span>
                  <span className="text-xs text-muted-foreground">{s.unit}</span>
                  <span className="ml-auto">
                    <TrendArrow data={s.trend} />
                  </span>
                </div>
                <Progress.Root value={Math.max(0, Math.min(100, pct))} size="xs" colorPalette="gray" mt="2">
                  <Progress.Track style={{ background: "var(--track)" }}>
                    <Progress.Range style={{ background: "var(--chart-1)" }} />
                  </Progress.Track>
                </Progress.Root>
                <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
                  <span>{s.range[0]}</span>
                  <span>{s.range[1]}</span>
                </div>
              </div>
            );
          })}
        </div>
      </Section>
    </PageBody>
  );
}
