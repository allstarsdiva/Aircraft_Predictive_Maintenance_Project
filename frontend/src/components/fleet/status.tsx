import { CircleDot, Droplets, Fuel, Gauge, Zap, type LucideIcon } from "lucide-react";
import type React from "react";
import { cn } from "@/lib/utils";
import { DANGER, GOOD, WARN } from "@/lib/viz";
import type { AircraftStatus, ComponentType, Risk } from "@/lib/fleet/types";

export const COMPONENT_ICONS: Record<ComponentType, LucideIcon> = {
  Engine: Gauge,
  "Landing Gear": CircleDot,
  Hydraulic: Droplets,
  Electrical: Zap,
  Fuel: Fuel,
};

/** Soft semantic colours: mint = fine, gold = watch, soft red = act. */
export const RISK_COLOR: Record<Risk, string> = { High: DANGER, Medium: WARN, Low: GOOD };
export const STATUS_COLOR: Record<AircraftStatus, string> = { Critical: DANGER, Warning: WARN, Healthy: GOOD };

/** Soft tinted pill (stock-app style): tinted background, readable text. */
export function SoftPill({ color, children, className }: { color: string; children: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold leading-4", className)}
      style={{ color: `color-mix(in oklab, ${color} 70%, var(--ink))`, background: `color-mix(in oklab, ${color} 15%, transparent)` }}
    >
      {children}
    </span>
  );
}

export function RiskBadge({ risk, className }: { risk: Risk; className?: string }) {
  return (
    <SoftPill color={RISK_COLOR[risk]} className={cn("rounded-md", className)}>
      {risk}
    </SoftPill>
  );
}

export function StatusBadge({ status, className }: { status: AircraftStatus; className?: string }) {
  return (
    <SoftPill color={STATUS_COLOR[status]} className={className}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: STATUS_COLOR[status] }} />
      {status}
    </SoftPill>
  );
}

/** Up/down change pill: mint when the move is good, soft red when it is bad. */
export function ChangePill({ value, goodWhenUp = true, suffix = "" }: { value: number; goodWhenUp?: boolean; suffix?: string }) {
  const good = goodWhenUp ? value >= 0 : value <= 0;
  return (
    <SoftPill color={good ? GOOD : DANGER}>
      {value >= 0 ? "▲" : "▼"} {Math.abs(value).toFixed(1)}
      {suffix}
    </SoftPill>
  );
}

export function StatusDot({ status }: { status: AircraftStatus }) {
  return <span aria-hidden className="h-2 w-2 shrink-0 rounded-full" style={{ background: STATUS_COLOR[status] }} />;
}
