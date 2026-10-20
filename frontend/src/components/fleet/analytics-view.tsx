"use client";

import { useMemo } from "react";
import { Table } from "@chakra-ui/react";
import { Activity, Layers3, Percent } from "lucide-react";
import { BarChart } from "@/components/charts/bar-chart";
import { DonutChart } from "@/components/charts/donut-chart";
import { TrendChart } from "@/components/charts/trend-chart";
import { CandlestickChart } from "@/components/charts/market";
import { Sparkline } from "@/components/charts/gauges";
import { Stagger, StaggerItem } from "@/components/motion";
import { MiniBar, PageBody, PageHeader, Section, StatCard } from "@/components/shell/page-parts";
import { COMPONENT_ICONS, ChangePill } from "@/components/fleet/status";
import { FleetActions } from "@/components/fleet/overview-view";
import { useFleet } from "@/lib/fleet/fleet-provider";
import { aircraftCandles, fleetRulSeries } from "@/lib/fleet/analytics";
import { COMPONENT_TYPES, meanTrend } from "@/lib/fleet/generate";
import { DANGER, DOWN, GOOD, UP, WARN, healthColor } from "@/lib/viz";

const mean = (values: number[]) => Math.round(values.reduce((a, v) => a + v, 0) / Math.max(values.length, 1));

export function AnalyticsView() {
  const { fleet } = useFleet();
  const components = useMemo(() => fleet.flatMap((a) => a.components), [fleet]);

  const bySubsystem = useMemo(
    () =>
      COMPONENT_TYPES.map((type) => {
        const list = components.filter((c) => c.type === type);
        const trend = meanTrend(list.map((c) => c.healthTrend)).map((p) => p.value);
        return {
          type,
          health: mean(list.map((c) => c.health)),
          rul: mean(list.map((c) => c.rul)),
          high: list.filter((c) => c.risk === "High").length,
          failure: mean(list.map((c) => c.failureProbability)),
          trend,
          change: (trend[trend.length - 1] ?? 0) - (trend[0] ?? 0),
        };
      }),
    [components],
  );

  const riskMix = useMemo(
    () => [
      { label: "Low", value: components.filter((c) => c.risk === "Low").length, color: GOOD },
      { label: "Medium", value: components.filter((c) => c.risk === "Medium").length, color: WARN },
      { label: "High", value: components.filter((c) => c.risk === "High").length, color: DANGER },
    ],
    [components],
  );

  const candles = useMemo(() => aircraftCandles(fleet), [fleet]);
  const rulTrend = useMemo(() => fleetRulSeries(fleet), [fleet]);

  return (
    <PageBody>
      <PageHeader
        eyebrow="Simulated fleet · not live aircraft data"
        title="Fleet analytics"
        description="How health, remaining life and risk are distributed across subsystems and aircraft."
        actions={<FleetActions />}
      />

      <Stagger className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StaggerItem>
          <StatCard label="Components tracked" value={components.length} sub={`${fleet.length} aircraft × 5 subsystems`} icon={Layers3} />
        </StaggerItem>
        <StaggerItem>
          <StatCard
            label="Mean failure probability"
            value={`${mean(components.map((c) => c.failureProbability))}%`}
            sub="simulated estimate"
            icon={Percent}
            footer={<MiniBar value={mean(components.map((c) => c.failureProbability))} danger />}
          />
        </StaggerItem>
        <StaggerItem>
          <StatCard
            label="Mean component health"
            value={`${mean(components.map((c) => c.health))}%`}
            sub="0 = failed, 100 = new"
            icon={Activity}
            footer={<MiniBar value={mean(components.map((c) => c.health))} color={healthColor(mean(components.map((c) => c.health)))} />}
          />
        </StaggerItem>
      </Stagger>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Section
          className="xl:col-span-2"
          title="Aircraft health candles"
          description="One candle per aircraft over the recorded window: body = health at the first cycle (open) to the latest (close), wick = highest and lowest health in between."
        >
          <CandlestickChart
            data={candles}
            height={320}
            bounds={[0, 100]}
            valueFormat={(v) => v.toFixed(1)}
            caption="Mint means health ended higher than it started, red means it ended lower. Hover a candle for its values."
          />
        </Section>
        <Section title="Component risk mix" description="All components by risk band">
          <DonutChart data={riskMix} sort={false} centerLabel="components" />
        </Section>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Section title="Fleet RUL trend" description="Mean remaining useful life per cycle; bars count components at 30 cycles or less">
          <TrendChart data={rulTrend} label="Average RUL" unit="cycles" ranges={[5, 10]} rangeSuffix="C" height={330} volumeLabel="High-risk components (RUL ≤ 30)" />
        </Section>
        <Section title="Average RUL by subsystem" description="Cycles remaining, mean across the fleet">
          <BarChart data={bySubsystem.map((s) => ({ label: s.type, value: s.rul, note: `${s.high} high-risk` }))} height={330} />
        </Section>
      </div>

      <Section className="mt-4" title="Health by aircraft" description="Mean component health; colour follows the health scale">
        <BarChart
          data={fleet.map((a) => ({ label: a.tail, value: a.overallHealth, color: healthColor(a.overallHealth) }))}
          valueFormat={(v) => `${v}%`}
          height={240}
        />
      </Section>

      <Section className="mt-4" title="Subsystem summary" description="Fleet-wide averages per subsystem, with each subsystem's health trend" bodyClassName="px-0 pb-2">
        <Table.Root size="sm" interactive>
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader ps="5">Subsystem</Table.ColumnHeader>
              <Table.ColumnHeader>Health trend</Table.ColumnHeader>
              <Table.ColumnHeader textAlign="end">Avg health</Table.ColumnHeader>
              <Table.ColumnHeader textAlign="end">Change</Table.ColumnHeader>
              <Table.ColumnHeader textAlign="end">Avg RUL</Table.ColumnHeader>
              <Table.ColumnHeader textAlign="end">High-risk</Table.ColumnHeader>
              <Table.ColumnHeader textAlign="end" pe="5">
                Avg failure probability
              </Table.ColumnHeader>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {bySubsystem.map((s) => {
              const Icon = COMPONENT_ICONS[s.type];
              return (
                <Table.Row key={s.type}>
                  <Table.Cell ps="5">
                    <span className="flex items-center gap-2 font-medium">
                      <Icon className="h-3.5 w-3.5 text-ink-3" /> {s.type}
                    </span>
                  </Table.Cell>
                  <Table.Cell>
                    <Sparkline values={s.trend} width={96} height={26} color={s.change >= 0 ? UP : DOWN} fill />
                  </Table.Cell>
                  <Table.Cell textAlign="end" className="tabular-nums">
                    {s.health}%
                  </Table.Cell>
                  <Table.Cell textAlign="end">
                    <ChangePill value={s.change} />
                  </Table.Cell>
                  <Table.Cell textAlign="end" className="tabular-nums">
                    {s.rul} cyc
                  </Table.Cell>
                  <Table.Cell textAlign="end" className="tabular-nums" style={s.high ? { color: DANGER } : undefined}>
                    {s.high}
                  </Table.Cell>
                  <Table.Cell textAlign="end" pe="5" className="tabular-nums">
                    {s.failure}%
                  </Table.Cell>
                </Table.Row>
              );
            })}
          </Table.Body>
        </Table.Root>
      </Section>
    </PageBody>
  );
}
