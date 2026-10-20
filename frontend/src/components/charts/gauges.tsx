"use client";

import { motion } from "framer-motion";
import { FILL_OPACITY, INK, SERIES, TRACK, healthColor, sparklinePath } from "@/lib/viz";
import { cn } from "@/lib/utils";

/** Inline sparkline with an optional flat translucent fill (no gradient). */
export function Sparkline({
  values,
  width = 84,
  height = 26,
  color = SERIES,
  strokeWidth = 1.75,
  fill = false,
}: {
  values: number[];
  width?: number;
  height?: number;
  color?: string;
  strokeWidth?: number;
  fill?: boolean;
}) {
  const d = sparklinePath(values, width, height);
  if (!d) return null;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true" style={{ flex: "none" }}>
      {fill ? <path d={`${d} L${width - 2} ${height} L2 ${height} Z`} style={{ fill: color, fillOpacity: FILL_OPACITY }} /> : null}
      <path d={d} fill="none" style={{ stroke: color }} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** 0-100 ring gauge on a soft red -> gold -> mint scale. */
export function RadialGauge({ value, size = 88, label = "health" }: { value: number; size?: number; label?: string }) {
  const R = 42;
  const C = 2 * Math.PI * R;
  const pct = Math.max(0, Math.min(100, value)) / 100;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90" aria-hidden>
        <circle cx="50" cy="50" r={R} fill="none" style={{ stroke: TRACK }} strokeWidth="9" />
        <motion.circle
          cx="50"
          cy="50"
          r={R}
          fill="none"
          strokeWidth="9"
          strokeLinecap="round"
          style={{ stroke: healthColor(value) }}
          initial={{ strokeDasharray: `0 ${C}` }}
          animate={{ strokeDasharray: `${pct * C} ${C}` }}
          transition={{ duration: 0.9, ease: [0.3, 0.8, 0.35, 1] }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn("font-display font-semibold leading-none tabular-nums", size >= 80 ? "text-lg" : "text-sm")}>{value}</span>
        {size >= 64 ? <span className="mt-0.5 text-[9px] uppercase tracking-wider text-muted-foreground">{label}</span> : null}
      </div>
    </div>
  );
}

/** Equal-width segments, one per part, for a compact profile strip. */
export function SegmentedBar({ segments, height = 8 }: { segments: { key: string; color: string; title: string }[]; height?: number }) {
  return (
    <div className="flex gap-[3px] overflow-hidden rounded-full" style={{ height }}>
      {segments.map((s, i) => (
        <motion.div
          key={s.key}
          title={s.title}
          className="flex-1"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 0.4, delay: i * 0.06 }}
          style={{ background: s.color, transformOrigin: "left" }}
        />
      ))}
    </div>
  );
}

/** Estimate with its interval on a shared scale (model outputs). */
export function IntervalBar({
  title,
  value,
  lower,
  upper,
  unit,
  format,
}: {
  title: string;
  value: number;
  lower?: number;
  upper?: number;
  unit?: string;
  format: (v: number) => string;
}) {
  const low = typeof lower === "number" ? lower : value;
  const high = typeof upper === "number" ? upper : value;
  const scale = Math.max(Math.abs(low), Math.abs(high), Math.abs(value), 1) * 1.08;
  const left = Math.max(0, Math.min(100, (Math.min(low, high) / scale) * 100));
  const width = Math.max(1, Math.min(100 - left, (Math.abs(high - low) / scale) * 100));
  const point = Math.max(0, Math.min(100, (value / scale) * 100));
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[12px] font-medium text-foreground">{title}</span>
        <span className="font-display text-sm font-semibold tabular-nums">
          {format(value)} {unit}
        </span>
      </div>
      <div className="relative mt-3 h-2.5 rounded-full" style={{ background: TRACK }} aria-label={`${title}: ${format(value)} ${unit ?? ""}; interval ${format(low)} to ${format(high)}`}>
        <div className="absolute top-0 h-2.5 rounded-full" style={{ left: `${left}%`, width: `${width}%`, background: SERIES, opacity: 0.45 }} />
        <span className="absolute -top-1 h-[18px] w-[3px] rounded" style={{ left: `calc(${point}% - 1.5px)`, background: INK }} />
      </div>
      <div className="mt-2 flex justify-between text-[10px] text-muted-foreground">
        <span>Lower {format(low)}</span>
        <span>
          Upper {format(high)} {unit}
        </span>
      </div>
    </div>
  );
}

/** Thin horizontal bars for 0-100 scores (confidence, importance). */
export function ScoreBars({
  rows,
  suffix = "%",
  format,
  color = SERIES,
}: {
  rows: { key: string; label: string; value: number }[];
  suffix?: string;
  format: (v: number) => string;
  color?: string;
}) {
  return (
    <ul className="space-y-2.5">
      {rows.map((row, i) => (
        <li key={row.key}>
          <div className="mb-1 flex items-center justify-between gap-2 text-[11px]">
            <span className="truncate text-muted-foreground" title={row.label}>
              {row.label}
            </span>
            <span className="shrink-0 font-semibold tabular-nums">
              {format(row.value)}
              {suffix}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full" style={{ background: TRACK }}>
            <motion.div
              className="h-full rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${Math.max(2, Math.min(100, row.value))}%` }}
              transition={{ duration: 0.6, delay: i * 0.04 }}
              style={{ background: color }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
