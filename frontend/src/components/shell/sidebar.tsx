"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { ChevronDown, Pause, Plane, Play, RadioTower } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { StatusDot } from "@/components/fleet/status";
import { useFleet } from "@/lib/fleet/fleet-provider";
import { NAV, WORKSPACES, isNavActive, workspaceForPath, type NavItem, type Workspace } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "./theme-toggle";

/** The active marker is a 2px left rail that glides between rows. */
function Rail() {
  return (
    <motion.span
      layoutId="sidebar-rail"
      className="absolute inset-y-0 left-0 w-[2px] bg-primary"
      transition={{ type: "spring", stiffness: 500, damping: 40 }}
    />
  );
}

function NavRow({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "relative flex items-center gap-3 py-2 pl-4 pr-3 text-[13px] transition-colors",
        active ? "bg-sidebar-active font-medium text-sidebar-active-foreground" : "text-sidebar-foreground/85 hover:bg-muted hover:text-sidebar-foreground",
      )}
    >
      {active ? <Rail /> : null}
      <Icon className="h-[18px] w-[18px]" />
      <span className="truncate">{item.label}</span>
    </Link>
  );
}

function AircraftSection({ pathname }: { pathname: string }) {
  const { fleet } = useFleet();
  const [open, setOpen] = useState(true);
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="pt-3">
      <CollapsibleTrigger className="flex w-full items-center justify-between px-4 py-1 text-[11px] font-medium uppercase tracking-wide text-sidebar-muted transition-colors hover:text-sidebar-foreground focus-visible:outline-none">
        <span>Aircraft ({fleet.length})</span>
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform duration-150", open ? "" : "-rotate-90")} />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-0.5 flex flex-col gap-0.5">
          {fleet.map((ac) => {
            const href = `/aircraft/${ac.id}`;
            const active = isNavActive(pathname, href);
            return (
              <Link
                key={ac.id}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative flex items-center gap-3 py-1.5 pl-4 pr-3 text-[13px] transition-colors",
                  active ? "bg-sidebar-active font-medium" : "text-sidebar-foreground/85 hover:bg-muted",
                )}
              >
                {active ? <Rail /> : null}
                <StatusDot status={ac.status} />
                <span className="truncate font-mono text-[12px]">{ac.tail}</span>
                <span className="ml-auto text-[11px] tabular-nums text-muted-foreground">{ac.overallHealth}%</span>
              </Link>
            );
          })}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

function TelemetryFooter() {
  const { connected, lastSync, toggleConnected } = useFleet();
  const [time, setTime] = useState("");
  useEffect(() => {
    setTime(lastSync ? lastSync.toLocaleTimeString() : "");
  }, [lastSync]);
  return (
    <div className="sticky bottom-0 border-t border-border bg-sidebar p-2">
      <div className="flex w-full items-center gap-3 rounded-md px-3 py-2">
        <span aria-hidden className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground ring-1 ring-border">
          <RadioTower className="h-[17px] w-[17px]" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] text-foreground">Simulated telemetry</span>
          <span className="block truncate text-[11px] text-sidebar-muted">
            {connected ? `Live · ${time || "syncing"}` : "Paused"}
          </span>
        </span>
        <button
          type="button"
          onClick={toggleConnected}
          aria-label={connected ? "Pause simulated telemetry" : "Resume simulated telemetry"}
          className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          {connected ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
        </button>
      </div>
    </div>
  );
}

export function Sidebar() {
  const pathname = usePathname() ?? "/";
  const [workspace, setWorkspace] = useState<Workspace>(() => workspaceForPath(pathname));
  useEffect(() => setWorkspace(workspaceForPath(pathname)), [pathname]);

  return (
    <nav
      aria-label="Primary"
      className="sticky top-0 hidden h-screen w-[var(--sidebar-width)] flex-none flex-col overflow-y-auto overflow-x-hidden border-r border-border bg-sidebar md:flex"
    >
      <div className="flex items-center gap-3 border-b border-border px-4 py-4">
        <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Plane className="h-4 w-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block font-display text-[15px] font-semibold leading-tight tracking-tight">AeroPredict</span>
          <span className="block text-[11px] leading-tight text-muted-foreground">Predictive maintenance</span>
        </span>
        <ThemeToggle />
      </div>

      <div className="flex border-b border-border">
        {WORKSPACES.map((w) => (
          <Link
            key={w.key}
            href={w.href}
            onClick={() => setWorkspace(w.key)}
            aria-pressed={workspace === w.key}
            className={cn(
              "flex-1 border-b-2 px-3 py-2.5 text-center text-[13px] font-medium transition-colors",
              workspace === w.key ? "border-b-primary text-primary" : "border-b-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {w.label}
          </Link>
        ))}
      </div>

      <div className="flex-1 pb-4">
        {NAV[workspace].map((group) => (
          <div key={group.label} className="pt-4">
            <div className="px-4 pb-1 text-[11px] font-medium uppercase tracking-wide text-sidebar-muted">{group.label}</div>
            <div className="mt-0.5 flex flex-col gap-0.5">
              {group.items.map((item) => (
                <NavRow key={item.href} item={item} active={isNavActive(pathname, item.href)} />
              ))}
            </div>
          </div>
        ))}
        {workspace === "monitor" ? <AircraftSection pathname={pathname} /> : null}
      </div>

      <TelemetryFooter />
    </nav>
  );
}

/** Compact navigation for narrow screens, where the sidebar is hidden. */
export function MobileNav() {
  const pathname = usePathname() ?? "/";
  const items = [...NAV.monitor, ...NAV.models].flatMap((g) => g.items);
  return (
    <div className="sticky top-0 z-20 border-b border-border bg-background md:hidden">
      <div className="flex items-center gap-2 px-4 py-3">
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Plane className="h-3.5 w-3.5" />
        </span>
        <span className="flex-1 font-display text-[15px] font-semibold">AeroPredict</span>
        <ThemeToggle />
      </div>
      <div className="flex gap-1 overflow-x-auto px-3 pb-2">
        {items.map((item) => {
          const active = isNavActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "whitespace-nowrap rounded-md px-2.5 py-1.5 text-xs font-medium",
                active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted",
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
