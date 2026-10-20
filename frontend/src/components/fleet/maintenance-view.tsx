"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Table } from "@chakra-ui/react";
import { ClipboardList, Search, ShieldAlert, Wrench } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/tabs";
import { Stagger, StaggerItem } from "@/components/motion";
import { EmptyState, PageBody, PageHeader, Section, StatCard } from "@/components/shell/page-parts";
import { COMPONENT_ICONS, RiskBadge } from "@/components/fleet/status";
import { FleetActions } from "@/components/fleet/overview-view";
import { useFleet } from "@/lib/fleet/fleet-provider";
import type { Risk } from "@/lib/fleet/types";

const FILTERS = ["All", "High", "Medium", "Low"] as const;
type Filter = (typeof FILTERS)[number];
const ORDER: Record<Risk, number> = { High: 0, Medium: 1, Low: 2 };

export function MaintenanceView() {
  const { fleet } = useFleet();
  const router = useRouter();
  const [filter, setFilter] = useState<Filter>("All");
  const [query, setQuery] = useState("");

  const all = useMemo(
    () => fleet.flatMap((ac) => ac.components.map((c) => ({ ac, c }))).sort((a, b) => ORDER[a.c.priority] - ORDER[b.c.priority] || a.c.rul - b.c.rul),
    [fleet],
  );
  const rows = all.filter(
    ({ ac, c }) =>
      (filter === "All" || c.priority === filter) &&
      (!query.trim() || `${ac.tail} ${c.type}`.toLowerCase().includes(query.trim().toLowerCase())),
  );
  const count = (risk: Risk) => all.filter(({ c }) => c.priority === risk).length;

  return (
    <PageBody>
      <PageHeader
        eyebrow="Simulated fleet · not live aircraft data"
        title="Maintenance center"
        description="Every component with its remaining useful life, risk band, recommendation and priority."
        actions={<FleetActions />}
      />

      <Stagger className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StaggerItem>
          <StatCard label="High priority" value={<span className="text-destructive">{count("High")}</span>} sub="Inspect immediately" icon={ShieldAlert} />
        </StaggerItem>
        <StaggerItem>
          <StatCard label="Medium priority" value={count("Medium")} sub="Monitor closely" icon={Wrench} />
        </StaggerItem>
        <StaggerItem>
          <StatCard label="Low priority" value={count("Low")} sub="No action required" icon={ClipboardList} />
        </StaggerItem>
      </Stagger>

      <Section
        className="mt-4"
        title="Work queue"
        description={`${rows.length} of ${all.length} components · sorted by priority, then RUL`}
        actions={
          <>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-4" />
              <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search tail or subsystem" className="h-8 w-56 pl-8 text-[13px]" aria-label="Search work queue" />
            </div>
            <Segmented value={filter} options={FILTERS} onChange={setFilter} ariaLabel="Filter by priority" />
          </>
        }
        bodyClassName="px-0 pb-2"
      >
        {rows.length === 0 ? (
          <EmptyState icon={ClipboardList} title="Nothing matches">
            Clear the search or choose another priority filter.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <Table.Root size="sm" interactive minW="720px">
              <Table.Header>
                <Table.Row>
                  <Table.ColumnHeader ps="5">Aircraft</Table.ColumnHeader>
                  <Table.ColumnHeader>Component</Table.ColumnHeader>
                  <Table.ColumnHeader textAlign="end">RUL</Table.ColumnHeader>
                  <Table.ColumnHeader>Risk</Table.ColumnHeader>
                  <Table.ColumnHeader>Recommendation</Table.ColumnHeader>
                  <Table.ColumnHeader pe="5">Priority</Table.ColumnHeader>
                </Table.Row>
              </Table.Header>
              <Table.Body>
                {rows.map(({ ac, c }) => {
                  const Icon = COMPONENT_ICONS[c.type];
                  return (
                    <Table.Row key={`${ac.id}-${c.type}`} cursor="pointer" onClick={() => router.push(`/aircraft/${ac.id}/${c.slug}`)}>
                      <Table.Cell ps="5" className="font-mono">
                        {ac.tail}
                      </Table.Cell>
                      <Table.Cell>
                        <span className="flex items-center gap-1.5">
                          <Icon className="h-3.5 w-3.5 text-ink-3" /> {c.type}
                        </span>
                      </Table.Cell>
                      <Table.Cell textAlign="end" className={`tabular-nums ${c.risk === "High" ? "text-destructive" : ""}`}>
                        {c.rul} cyc
                      </Table.Cell>
                      <Table.Cell>
                        <RiskBadge risk={c.risk} />
                      </Table.Cell>
                      <Table.Cell className="text-ink-2">{c.recommendation}</Table.Cell>
                      <Table.Cell pe="5">
                        <RiskBadge risk={c.priority} />
                      </Table.Cell>
                    </Table.Row>
                  );
                })}
              </Table.Body>
            </Table.Root>
          </div>
        )}
      </Section>
    </PageBody>
  );
}
