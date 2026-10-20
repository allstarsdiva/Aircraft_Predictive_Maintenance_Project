"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertTriangle, CheckCircle2, Database, GaugeCircle, Pause, Play, RefreshCw, ShieldAlert, ShieldCheck, Timer, TrendingDown, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TrendChart } from "@/components/charts/trend-chart";
import { DonutChart } from "@/components/charts/donut-chart";
import { RadialGauge, Sparkline } from "@/components/charts/gauges";
import { Heatmap, TickerTape } from "@/components/charts/market";
import { Stagger, StaggerItem } from "@/components/motion";
import { MiniBar, PageBody, PageHeader, Section, StatCard } from "@/components/shell/page-parts";
import { ChangePill, StatusBadge } from "@/components/fleet/status";
import { useFleet } from "@/lib/fleet/fleet-provider";
import { aircraftHealthSeries, fleetHealthSeries, fleetRulSeries, movers, type Mover } from "@/lib/fleet/analytics";
import { COMPONENT_TYPES, slugOf } from "@/lib/fleet/generate";
import { DANGER, DOWN, GOOD, UP, WARN, healthColor } from "@/lib/viz";

export function FleetActions() {
  const { connected, toggleConnected, resync } = useFleet();
  return (
    <>
      <Button variant="outline" size="sm" onClick={toggleConnected}>
        {connected ? <Pause /> : <Play />}
        {connected ? "Pause telemetry" : "Resume telemetry"}
      </Button>
      <Button size="sm" onClick={resync}>
        <RefreshCw />
        Resync fleet
      </Button>
    </>
  );
}

function MoverList({ title, icon: Icon, rows, empty }: { title: string; icon: typeof TrendingUp; rows: Mover[]; empty: string }) {
  return (
    <Section title={<span className="flex items-center gap-2"><Icon className="h-4 w-4" /> {title}</span>} description="Change in mean health over the window">
      {rows.length === 0 ? <p className="py-6 text-center text-[13px] text-muted-foreground">{empty}</p> : null}
      <ul className="space-y-1">
        {rows.map(({ aircraft, series, change }) => (
          <li key={aircraft.id}>
            <Link href={`/aircraft/${aircraft.id}`} className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-hover">
              <span className="min-w-0 flex-1">
                <span className="block font-mono text-[13px] font-medium">{aircraft.tail}</span>
                <span className="block truncate text-[11px] text-muted-foreground">{aircraft.model}</span>
              </span>
              <Sparkline values={series} width={80} height={28} color={change >= 0 ? UP : DOWN} fill />
              <span className="w-[72px] text-right">
                <span className="block text-[13px] font-semibold tabular-nums">{aircraft.overallHealth}%</span>
                <ChangePill value={change} />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Section>
  );
}

export function OverviewView() {
  const { fleet } = useFleet();
  const router = useRouter();

  const stats = useMemo(() => {
    const healthy = fleet.filter((a) => a.status === "Healthy").length;
    const warning = fleet.filter((a) => a.status === "Warning").length;
    const critical = fleet.filter((a) => a.status === "Critical").length;
    const components = fleet.flatMap((a) => a.components);
    return {
      healthy,
      warning,
      critical,
      total: fleet.length,
      avgHealth: Math.round(fleet.reduce((s, a) => s + a.overallHealth, 0) / Math.max(fleet.length, 1)),
      avgRul: Math.round(components.reduce((s, c) => s + c.rul, 0) / Math.max(components.length, 1)),
      highRisk: components.filter((c) => c.risk === "High").length,
      readiness: Math.round(((healthy + warning * 0.65) / Math.max(fleet.length, 1)) * 100),
      sensors: components.reduce((s, c) => s + c.sensors.length, 0),
    };
  }, [fleet]);

  const health = useMemo(() => fleetHealthSeries(fleet), [fleet]);
  const rul = useMemo(() => fleetRulSeries(fleet), [fleet]);
  const { gainers, losers } = useMemo(() => movers(fleet), [fleet]);
  const ticker = useMemo(
    () =>
      fleet.map((ac) => {
        const s = aircraftHealthSeries(ac);
        return { key: ac.id, label: ac.tail, value: `${ac.overallHealth}%`, change: (s[s.length - 1] ?? 0) - (s[0] ?? 0), href: `/aircraft/${ac.id}` };
      }),
    [fleet],
  );
  const priority = useMemo(() => [...fleet].sort((a, b) => a.overallHealth - b.overallHealth).slice(0, 5), [fleet]);
  const alerts = useMemo(
    () =>
      fleet
        .flatMap((ac) => ac.components.filter((c) => c.risk === "High").map((c) => ({ ac, c })))
        .sort((a, b) => a.c.rul - b.c.rul)
        .slice(0, 5),
    [fleet],
  );

  return (
    <PageBody>
      <PageHeader
        eyebrow="Simulated fleet · not live aircraft data"
        title="Fleet overview"
        description="Component health, remaining useful life and maintenance priority across a simulated fleet of nine aircraft."
        actions={<FleetActions />}
      />

      <TickerTape items={ticker} />

      <Stagger className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StaggerItem>
          <StatCard
            label="Fleet readiness"
            value={`${stats.readiness}%`}
            sub={`${stats.healthy} of ${stats.total} fully healthy`}
            icon={ShieldCheck}
            hint="Healthy aircraft count fully; aircraft with only medium-risk components count at 65%."
            footer={<MiniBar value={stats.readiness} color={healthColor(stats.readiness)} />}
          />
        </StaggerItem>
        <StaggerItem>
          <StatCard
            label="Average health"
            value={`${stats.avgHealth}%`}
            sub="across all aircraft"
            icon={GaugeCircle}
            footer={<Sparkline values={health.map((p) => p.value)} width={200} height={30} color={UP} fill />}
          />
        </StaggerItem>
        <StaggerItem>
          <StatCard
            label="Average RUL"
            value={stats.avgRul}
            sub="cycles remaining per component"
            icon={Timer}
            footer={<Sparkline values={rul.map((p) => p.value)} width={200} height={30} color={DOWN} fill />}
          />
        </StaggerItem>
        <StaggerItem>
          <StatCard
            label="High-risk components"
            value={<span style={stats.highRisk ? { color: DANGER } : undefined}>{stats.highRisk}</span>}
            sub="RUL of 30 cycles or less"
            icon={ShieldAlert}
            footer={<MiniBar value={(stats.highRisk / Math.max(1, stats.total * 5)) * 100} danger />}
          />
        </StaggerItem>
      </Stagger>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Section className="xl:col-span-2" title="Fleet health" description="Mean component health per recorded cycle, like a price chart. Hover to scrub.">
          <TrendChart
            data={health}
            label="Fleet average health"
            unit="%"
            ranges={[5, 10]}
            rangeSuffix="C"
            height={372}
            volumeLabel="Components below 45% health"
          />
        </Section>
        <Section title="Fleet status" description="Aircraft by their worst component">
          <DonutChart
            sort={false}
            centerLabel="aircraft"
            data={[
              { label: "Healthy", value: stats.healthy, color: GOOD },
              { label: "Warning", value: stats.warning, color: WARN },
              { label: "Critical", value: stats.critical, color: DANGER },
            ]}
          />
          <div className="mt-5 space-y-2">
            {priority.slice(0, 3).map((ac, i) => (
              <Link key={ac.id} href={`/aircraft/${ac.id}`} className="flex items-center gap-3 rounded-lg border border-border px-3 py-2 transition-colors hover:bg-hover">
                <span className="w-5 font-mono text-[11px] text-muted-foreground">0{i + 1}</span>
                <span className="min-w-0 flex-1 truncate font-mono text-[13px]">{ac.tail}</span>
                <span className="text-[13px] font-semibold tabular-nums" style={{ color: `color-mix(in oklab, ${healthColor(ac.overallHealth)} 70%, var(--ink))` }}>
                  {ac.overallHealth}%
                </span>
              </Link>
            ))}
            <p className="text-[11px] text-muted-foreground">Lowest health first.</p>
          </div>
        </Section>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <MoverList title="Top gainers" icon={TrendingUp} rows={gainers} empty="No aircraft improved over this window." />
        <MoverList title="Top losers" icon={TrendingDown} rows={losers} empty="No aircraft lost health over this window." />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Section className="xl:col-span-2" title="Fleet health heatmap" description="Every component's health. Click a tile to open that component.">
          <Heatmap
            rows={fleet.map((a) => ({ key: a.id, label: <span className="font-mono">{a.tail}</span> }))}
            columns={COMPONENT_TYPES.map((t) => ({ key: t, label: t }))}
            value={(row, col) => fleet.find((a) => a.id === row)?.components.find((c) => c.type === col)?.health ?? 0}
            onCell={(row, col) => router.push(`/aircraft/${row}/${slugOf(col as (typeof COMPONENT_TYPES)[number])}`)}
            format={(v) => `${v}`}
          />
        </Section>

        <div className="space-y-4">
          <Section title="Critical alerts" description="High-risk components, shortest RUL first">
            {alerts.length === 0 ? (
              <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
                <CheckCircle2 className="h-4 w-4" /> No active high-risk alerts.
              </div>
            ) : (
              <ul className="space-y-2.5">
                {alerts.map(({ ac, c }) => (
                  <li key={`${ac.id}-${c.type}`}>
                    <Link href={`/aircraft/${ac.id}/${c.slug}`} className="flex items-start gap-2.5 rounded-md transition-colors hover:bg-hover">
                      <span className="mt-0.5 rounded-md p-1" style={{ color: DANGER, background: `color-mix(in oklab, ${DANGER} 14%, transparent)` }}>
                        <AlertTriangle className="h-3 w-3" />
                      </span>
                      <span className="text-[12px] text-ink-2">
                        <span className="font-mono font-medium text-foreground">{ac.tail}</span> · {c.type}
                        <span className="block">
                          <span className="font-semibold" style={{ color: DANGER }}>
                            {c.rul}
                          </span>{" "}
                          cycles RUL · inspect
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title={<span className="flex items-center gap-2"><Database className="h-3.5 w-3.5" /> System telemetry</span>}>
            <div className="grid grid-cols-2 gap-3 text-[13px]">
              <div>
                <div className="text-[11px] text-muted-foreground">Sensors</div>
                <div className="font-medium tabular-nums">{stats.sensors}</div>
              </div>
              <div>
                <div className="text-[11px] text-muted-foreground">Update rate</div>
                <div className="font-medium">2.5 s</div>
              </div>
              <div>
                <div className="text-[11px] text-muted-foreground">Data source</div>
                <div className="font-medium">Simulated</div>
              </div>
              <div>
                <div className="text-[11px] text-muted-foreground">Trained models</div>
                <Link href="/models/predict" className="font-medium underline-offset-4 hover:underline">
                  Models workspace
                </Link>
              </div>
            </div>
          </Section>
        </div>
      </div>

      <Section className="mt-4" title="Watchlist" description="All aircraft, like a stock watchlist: trend, health and change" bodyClassName="px-0 pb-1">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-[13px]">
            <thead>
              <tr className="border-b border-border text-left text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                <th className="px-5 py-2 font-medium">Aircraft</th>
                <th className="px-3 py-2 font-medium">Trend</th>
                <th className="px-3 py-2 text-right font-medium">Health</th>
                <th className="px-3 py-2 text-right font-medium">Change</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-5 py-2 text-right font-medium">Lowest RUL</th>
              </tr>
            </thead>
            <tbody>
              {fleet.map((ac) => {
                const s = aircraftHealthSeries(ac);
                const change = (s[s.length - 1] ?? 0) - (s[0] ?? 0);
                const lowest = Math.min(...ac.components.map((c) => c.rul));
                return (
                  <tr key={ac.id} className="cursor-pointer border-b border-rowline transition-colors last:border-0 hover:bg-hover" onClick={() => router.push(`/aircraft/${ac.id}`)}>
                    <td className="px-5 py-2.5">
                      <div className="flex items-center gap-3">
                        <RadialGauge value={ac.overallHealth} size={36} />
                        <span>
                          <span className="block font-mono font-medium">{ac.tail}</span>
                          <span className="block text-[11px] text-muted-foreground">{ac.model}</span>
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <Sparkline values={s} width={110} height={30} color={change >= 0 ? UP : DOWN} fill />
                    </td>
                    <td className="px-3 py-2.5 text-right font-semibold tabular-nums">{ac.overallHealth}%</td>
                    <td className="px-3 py-2.5 text-right">
                      <ChangePill value={change} />
                    </td>
                    <td className="px-3 py-2.5">
                      <StatusBadge status={ac.status} />
                    </td>
                    <td className="px-5 py-2.5 text-right tabular-nums" style={lowest <= 30 ? { color: DANGER } : undefined}>
                      {lowest} cyc
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>
    </PageBody>
  );
}
