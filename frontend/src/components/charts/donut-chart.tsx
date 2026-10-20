"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { TRACK, humanise, nf, prefersReducedMotion, ramp } from "@/lib/viz";

export type DonutDatum = { label: string; value: number; color?: string };

/**
 * Part-to-whole ring. Use only when the slices genuinely sum to one whole.
 * Slices are ordered largest-first, the legend prints value and share, and
 * long tails fold into "Other".
 */
export function DonutChart({
  data,
  size = 168,
  thickness = 22,
  maxSlices = 6,
  centerLabel = "total",
  emptyLabel = "No data yet",
  sort = true,
}: {
  data: DonutDatum[];
  size?: number;
  thickness?: number;
  maxSlices?: number;
  centerLabel?: string;
  emptyLabel?: string;
  sort?: boolean;
}) {
  const [drawn, setDrawn] = useState(false);
  const [hover, setHover] = useState<number | null>(null);
  const reduced = useRef(false);

  useEffect(() => {
    reduced.current = prefersReducedMotion();
    const id = requestAnimationFrame(() => requestAnimationFrame(() => setDrawn(true)));
    return () => cancelAnimationFrame(id);
  }, []);

  const slices = useMemo(() => {
    const clean = data.filter((d) => d.value > 0);
    if (sort) clean.sort((a, b) => b.value - a.value);
    if (clean.length <= maxSlices) return clean;
    const head = clean.slice(0, maxSlices - 1);
    const tail = clean.slice(maxSlices - 1);
    return [...head, { label: "Other", value: tail.reduce((s, d) => s + d.value, 0) }];
  }, [data, maxSlices, sort]);

  const total = slices.reduce((s, d) => s + d.value, 0);
  if (!total) {
    return (
      <div className="flex items-center justify-center text-[13px] text-muted-foreground" style={{ height: size }}>
        {emptyLabel}
      </div>
    );
  }

  const R = 50 - thickness / 4;
  const C = 2 * Math.PI * R;
  const active = hover != null ? slices[hover] : undefined;
  let offset = 0;
  const arcs = slices.map((d, i) => {
    const frac = d.value / total;
    const arc = { d, i, dash: Math.max(0, frac * C - 1.2), offset, color: d.color ?? ramp(i) };
    offset += frac * C;
    return arc;
  });

  return (
    <div className="flex flex-wrap items-center gap-5">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
          <circle cx="50" cy="50" r={R} fill="none" style={{ stroke: TRACK }} strokeWidth={thickness / 2} />
          {arcs.map((a) => {
            const on = hover === a.i;
            return (
              <circle
                key={a.d.label}
                cx="50"
                cy="50"
                r={R}
                fill="none"
                strokeWidth={on ? thickness / 2 + 2.5 : thickness / 2}
                strokeDasharray={`${drawn || reduced.current ? a.dash : 0} ${C}`}
                strokeDashoffset={-a.offset}
                onMouseEnter={() => setHover(a.i)}
                onMouseLeave={() => setHover(null)}
                style={{
                  stroke: a.color,
                  opacity: hover == null || on ? 1 : 0.4,
                  transition: reduced.current
                    ? "opacity .15s linear, stroke-width .15s ease"
                    : `stroke-dasharray .7s cubic-bezier(.3,.8,.35,1) ${a.i * 70}ms, opacity .15s linear, stroke-width .15s ease`,
                }}
              />
            );
          })}
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-[20px] font-semibold leading-none tabular-nums">
            {active ? `${Math.round((active.value / total) * 100)}%` : nf.format(total)}
          </span>
          <span className="mt-1 max-w-[80%] truncate text-[10px] text-muted-foreground">{active ? humanise(active.label) : centerLabel}</span>
        </div>
      </div>

      <ul className="min-w-[160px] flex-1 space-y-1.5">
        {arcs.map((a) => (
          <li
            key={a.d.label}
            className="flex items-center gap-2 text-[12px]"
            onMouseEnter={() => setHover(a.i)}
            onMouseLeave={() => setHover(null)}
            style={{ opacity: hover == null || hover === a.i ? 1 : 0.5 }}
          >
            <span className="h-2.5 w-2.5 shrink-0 rounded-[3px]" style={{ background: a.color }} />
            <span className="truncate text-muted-foreground">{humanise(a.d.label)}</span>
            <span className="ml-auto shrink-0 font-medium tabular-nums">{nf.format(a.d.value)}</span>
            <span className="w-9 shrink-0 text-right tabular-nums text-muted-foreground">{Math.round((a.d.value / total) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
