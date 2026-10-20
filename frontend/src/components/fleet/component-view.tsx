"use client";

import { Progress } from "@chakra-ui/react";
import { Thermometer, Wrench } from "lucide-react";
import { Card } from "@/components/ui/card";
import { TrendChart } from "@/components/charts/trend-chart";
import { Stagger, StaggerItem } from "@/components/motion";
import { EmptyState, Metric, PageBody, Section } from "@/components/shell/page-parts";
import { COMPONENT_ICONS, RiskBadge } from "@/components/fleet/status";
import { BackLink } from "@/components/fleet/aircraft-view";
import { useFleet } from "@/lib/fleet/fleet-provider";
import { cn } from "@/lib/utils";

export function ComponentView({ id, slug }: { id: string; slug: string }) {
  const { fleet } = useFleet();
  const aircraft = fleet.find((a) => a.id === id);
  const component = aircraft?.components.find((c) => c.slug === slug);

  if (!aircraft || !component) {
    return (
      <PageBody>
        <BackLink href={aircraft ? `/aircraft/${aircraft.id}` : "/"}>{aircraft ? aircraft.tail : "Fleet overview"}</BackLink>
        <Card>
          <EmptyState icon={Wrench} title="Component not found">
            This simulated component is not part of the current fleet.
          </EmptyState>
        </Card>
      </PageBody>
    );
  }

  const Icon = COMPONENT_ICONS[component.type];
  const high = component.risk === "High";

  return (
    <PageBody>
      <BackLink href={`/aircraft/${aircraft.id}`}>{aircraft.tail}</BackLink>

      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className={cn("flex h-11 w-11 items-center justify-center rounded-lg", high ? "bg-destructive/10 text-destructive" : "bg-muted")}>
              <Icon className="h-5 w-5" />
            </span>
            <div>
              <h1 className="font-display text-xl font-semibold tracking-tight">{component.type}</h1>
              <p className="text-xs text-muted-foreground">
                <span className="font-mono">{aircraft.tail}</span> · {aircraft.model} · simulated
              </p>
            </div>
          </div>
          <div className={cn("rounded-lg border px-3 py-2 text-right", high ? "border-destructive/30 bg-destructive/5" : "border-border bg-muted/50")}>
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Recommendation</div>
            <div className={cn("text-sm font-semibold", high && "text-destructive")}>{component.recommendation}</div>
          </div>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Metric label="Health score" value={<span className={component.health < 45 ? "text-destructive" : undefined}>{component.health}</span>} />
          <Metric label="RUL (cycles)" value={<span className={high ? "text-destructive" : undefined}>{component.rul}</span>} />
          <Metric label="Failure probability" value={`${component.failureProbability}%`} />
          <div>
            <div className="text-[11px] text-muted-foreground">Risk / priority</div>
            <div className="mt-1.5 flex gap-1.5">
              <RiskBadge risk={component.risk} />
              <RiskBadge risk={component.priority} />
            </div>
          </div>
        </div>
      </Card>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Section title="Health trend" description="Health score per recorded cycle">
          <TrendChart
            data={component.healthTrend.map((p) => ({ x: `C${p.cycle + 1}`, value: p.value }))}
            label="Health"
            unit="%"
            domain={[0, 100]}
            ranges={[5, 10, 20]}
            rangeSuffix="C"
          />
        </Section>
        <Section title="RUL trend" description="Cycles remaining per recorded cycle">
          <TrendChart
            data={component.rulTrend.map((p) => ({ x: `C${p.cycle + 1}`, value: p.value }))}
            label="RUL"
            unit="cycles"
            ranges={[5, 10, 20]}
            rangeSuffix="C"
          />
        </Section>
      </div>

      <div className="mb-2 mt-6 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Sensors</div>
      <Stagger className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {component.sensors.map((sensor) => {
          const pct = ((sensor.value - sensor.range[0]) / (sensor.range[1] - sensor.range[0])) * 100;
          return (
            <StaggerItem key={sensor.key}>
              <Card className="p-4">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-sm font-semibold">
                    <Thermometer className="h-3.5 w-3.5 text-ink-3" /> {sensor.label}
                  </span>
                  <span className="font-display text-sm font-semibold tabular-nums">
                    {sensor.value} <span className="font-sans text-xs font-normal text-muted-foreground">{sensor.unit}</span>
                  </span>
                </div>
                <Progress.Root value={Math.max(0, Math.min(100, pct))} size="xs" colorPalette="gray" mt="3">
                  <Progress.Track style={{ background: "var(--track)" }}>
                    <Progress.Range style={{ background: "var(--chart-1)" }} />
                  </Progress.Track>
                </Progress.Root>
                <div className="mb-3 mt-1 flex justify-between text-[10px] text-muted-foreground">
                  <span>
                    {sensor.range[0]} {sensor.unit}
                  </span>
                  <span>expected range</span>
                  <span>
                    {sensor.range[1]} {sensor.unit}
                  </span>
                </div>
                <TrendChart
                  data={sensor.trend.map((p) => ({ x: `C${p.cycle + 1}`, value: p.value }))}
                  label="Normalised reading (0–100)"
                  headline="none"
                  goodDirection="neutral"
                  domain={[0, 100]}
                  height={130}
                />
              </Card>
            </StaggerItem>
          );
        })}
      </Stagger>
    </PageBody>
  );
}
