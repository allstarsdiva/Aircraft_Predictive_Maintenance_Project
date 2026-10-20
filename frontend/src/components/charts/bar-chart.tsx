"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { GRID, SERIES, compact, humanise, nf, niceScale } from "@/lib/viz";

export type BarDatum = { label: string; value: number; color?: string; note?: string };

/**
 * Standing bar chart: soft single-hue bars that grow in (staggered), a
 * labelled y axis on round ticks with gridlines BEHIND the bars, printed
 * values, and hover focus. Pass `color` per datum only when it carries
 * meaning (mint = good, red = act).
 */
export function BarChart({
  data,
  height = 220,
  emptyLabel = "No data yet",
  valueFormat = (v: number) => nf.format(v),
}: {
  data: BarDatum[];
  height?: number;
  emptyLabel?: string;
  valueFormat?: (v: number) => string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const track = useRef<HTMLDivElement>(null);
  const [barPx, setBarPx] = useState<number | null>(null);

  useEffect(() => {
    const el = track.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w != null) setBarPx(data.length ? w / data.length : null);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [data.length]);

  if (!data.length) {
    return (
      <div className="flex items-center justify-center text-[13px] text-muted-foreground" style={{ height }}>
        {emptyLabel}
      </div>
    );
  }

  const showValues = barPx == null || barPx >= 38;
  const max = Math.max(...data.map((d) => d.value), 0) || 1;
  const total = data.reduce((a, d) => a + d.value, 0) || 1;
  const plot = height - 58;
  const { top, ticks } = niceScale(max);

  return (
    <div style={{ height }} className="flex gap-2">
      <div className="relative w-9 shrink-0" aria-hidden style={{ height: plot, marginTop: 20 }}>
        {ticks.map((t) => (
          <span key={t} className="absolute right-1.5 -translate-y-1/2 text-[10px] tabular-nums text-muted-foreground" style={{ top: `${(1 - t / top) * 100}%` }}>
            {compact(t)}
          </span>
        ))}
      </div>

      <div ref={track} className="relative flex min-w-0 flex-1 items-start gap-2">
        <div className="pointer-events-none absolute inset-x-0 z-0" style={{ height: plot, top: 20 }}>
          {ticks
            .filter((t) => t > 0 && t < top)
            .map((t) => (
              <div key={t} className="absolute inset-x-0 border-t border-dashed" style={{ top: `${(1 - t / top) * 100}%`, borderColor: GRID }} />
            ))}
        </div>
        {data.map((d, i) => {
          const on = hover === i;
          const color = d.color ?? SERIES;
          return (
            <div
              key={d.label}
              className="relative z-10 flex min-w-0 flex-1 cursor-default flex-col items-center"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              title={`${humanise(d.label)} · ${valueFormat(d.value)} · ${Math.round((d.value / total) * 100)}%${d.note ? ` · ${d.note}` : ""}`}
            >
              {showValues ? (
                <span className="mb-1 h-4 w-full truncate text-center text-[11px] font-semibold leading-4 tabular-nums transition-opacity" style={{ opacity: hover == null || on ? 1 : 0.45 }}>
                  {valueFormat(d.value)}
                </span>
              ) : (
                <span className="mb-1 h-4" aria-hidden />
              )}
              <div className="flex w-full items-end justify-center" style={{ height: plot }}>
                <motion.div
                  className="w-full max-w-[46px] rounded-t-[8px]"
                  initial={{ height: "0%" }}
                  animate={{ height: `${Math.max((d.value / top) * 100, 1.5)}%`, opacity: hover == null || on ? 1 : 0.4 }}
                  transition={{ height: { duration: 0.6, delay: i * 0.05, ease: [0.22, 0.8, 0.3, 1] }, opacity: { duration: 0.15 } }}
                  style={{ background: color }}
                />
              </div>
              <span className="mt-1.5 line-clamp-2 w-full break-words text-center text-[11px] leading-tight text-muted-foreground">{humanise(d.label)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
