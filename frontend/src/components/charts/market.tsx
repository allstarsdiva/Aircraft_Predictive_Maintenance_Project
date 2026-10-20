"use client";

import { useMemo, useRef, useState, type MouseEvent, type ReactNode } from "react";
import { motion } from "framer-motion";
import { DOWN, GRID, UP, compact, healthColor, nf } from "@/lib/viz";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ candles */

export type Candle = { x: string; open: number; high: number; low: number; close: number };

/**
 * Candlestick chart. Body spans open -> close (mint when it closed higher,
 * soft red when lower); the wick spans low -> high. Flat fills only.
 */
export function CandlestickChart({
  data,
  height = 260,
  valueFormat = (v: number) => nf.format(Math.round(v * 10) / 10),
  caption,
  bounds,
}: {
  data: Candle[];
  height?: number;
  valueFormat?: (v: number) => string;
  caption?: ReactNode;
  /** Hard limits for the axis, e.g. [0, 100] for a health score. */
  bounds?: [number, number];
}) {
  const [hover, setHover] = useState<number | null>(null);
  const plotRef = useRef<HTMLDivElement>(null);
  const scale = useMemo(() => {
    const lo = Math.min(...data.map((d) => d.low));
    const hi = Math.max(...data.map((d) => d.high));
    const pad = (hi - lo || 1) * 0.1;
    const bottom = lo - pad;
    const top = hi + pad;
    return bounds ? { bottom: Math.max(bounds[0], bottom), top: Math.min(bounds[1], top) } : { bottom, top };
  }, [data, bounds]);
  if (!data.length) return null;

  const span = scale.top - scale.bottom || 1;
  const yPct = (v: number) => (1 - (v - scale.bottom) / span) * 100;
  const active = data[hover ?? data.length - 1];
  const up = active.close >= active.open;
  const ticks = [scale.top, scale.bottom + span / 2, scale.bottom];

  function onMove(e: MouseEvent<HTMLDivElement>) {
    const box = plotRef.current?.getBoundingClientRect();
    if (!box) return;
    const frac = Math.min(0.9999, Math.max(0, (e.clientX - box.left) / box.width));
    setHover(Math.floor(frac * data.length));
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px]">
        <span className="font-medium">{active.x}</span>
        {(["open", "high", "low", "close"] as const).map((k) => (
          <span key={k} className="text-muted-foreground">
            {k[0].toUpperCase()} <span className="font-semibold tabular-nums text-foreground">{valueFormat(active[k])}</span>
          </span>
        ))}
        <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold" style={{ color: up ? UP : DOWN, background: `color-mix(in oklab, ${up ? UP : DOWN} 14%, transparent)` }}>
          {up ? "▲" : "▼"} {valueFormat(Math.abs(active.close - active.open))}
        </span>
      </div>
      <div className="flex" style={{ height: height - 60 }}>
        <div ref={plotRef} className="relative flex min-w-0 flex-1 cursor-crosshair items-stretch gap-[3px]" onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
          {ticks.map((t, i) => (
            <div key={i} className="pointer-events-none absolute inset-x-0 border-t border-dashed" style={{ top: `${yPct(t)}%`, borderColor: GRID }} />
          ))}
          {data.map((d, i) => {
            const isUp = d.close >= d.open;
            const color = isUp ? UP : DOWN;
            const bodyTop = yPct(Math.max(d.open, d.close));
            const bodyH = Math.max(0.8, Math.abs(yPct(d.open) - yPct(d.close)));
            return (
              <div key={d.x} className="relative flex-1" style={{ opacity: hover == null || hover === i ? 1 : 0.45 }}>
                <motion.div
                  className="absolute left-1/2 w-px -translate-x-1/2"
                  style={{ top: `${yPct(d.high)}%`, height: `${yPct(d.low) - yPct(d.high)}%`, background: color, transformOrigin: "bottom" }}
                  initial={{ scaleY: 0 }}
                  animate={{ scaleY: 1 }}
                  transition={{ duration: 0.4, delay: i * 0.03 }}
                />
                <motion.div
                  className="absolute inset-x-[22%] rounded-[3px]"
                  style={{ top: `${bodyTop}%`, height: `${bodyH}%`, background: color, transformOrigin: "bottom" }}
                  initial={{ scaleY: 0 }}
                  animate={{ scaleY: 1 }}
                  transition={{ duration: 0.45, delay: i * 0.03 + 0.1 }}
                />
              </div>
            );
          })}
        </div>
        <div className="relative w-11 shrink-0" aria-hidden>
          {ticks.map((t, i) => (
            <span key={i} className="absolute left-2 -translate-y-1/2 text-[10px] tabular-nums text-muted-foreground" style={{ top: `${yPct(t)}%` }}>
              {compact(Math.round(t * 10) / 10)}
            </span>
          ))}
        </div>
      </div>
      <div className="mt-1.5 flex gap-[3px] pr-11 text-[10px] text-muted-foreground">
        {data.map((d) => (
          <span key={d.x} className="flex-1 truncate text-center font-mono">
            {d.x}
          </span>
        ))}
      </div>
      {caption ? <p className="mt-2 text-[11px] text-muted-foreground">{caption}</p> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ heatmap */

/**
 * Market-style heatmap: one flat tile per cell, coloured on a soft
 * red -> gold -> mint scale by value (0-100), with the value printed.
 */
export function Heatmap({
  rows,
  columns,
  value,
  rowHref,
  onCell,
  format = (v: number) => `${v}`,
}: {
  rows: { key: string; label: ReactNode }[];
  columns: { key: string; label: string }[];
  value: (row: string, col: string) => number;
  rowHref?: (row: string) => string;
  onCell?: (row: string, col: string) => void;
  format?: (v: number) => string;
}) {
  const [hover, setHover] = useState<string | null>(null);
  return (
    <div className="overflow-x-auto">
      <div className="grid min-w-[560px] gap-1.5" style={{ gridTemplateColumns: `minmax(90px, 1.1fr) repeat(${columns.length}, minmax(70px, 1fr))` }}>
        <div />
        {columns.map((c) => (
          <div key={c.key} className="truncate pb-1 text-center text-[11px] font-medium text-muted-foreground">
            {c.label}
          </div>
        ))}
        {rows.map((r, ri) => (
          <div key={r.key} className="contents">
            <div className="flex items-center truncate pr-2 text-[12px]">
              {rowHref ? (
                <a href={rowHref(r.key)} className="truncate hover:underline">
                  {r.label}
                </a>
              ) : (
                r.label
              )}
            </div>
            {columns.map((c, ci) => {
              const v = value(r.key, c.key);
              const id = `${r.key}:${c.key}`;
              return (
                <motion.button
                  key={id}
                  type="button"
                  onClick={() => onCell?.(r.key, c.key)}
                  onMouseEnter={() => setHover(id)}
                  onMouseLeave={() => setHover(null)}
                  initial={{ opacity: 0, scale: 0.85 }}
                  animate={{ opacity: hover == null || hover === id ? 1 : 0.55, scale: hover === id ? 1.06 : 1 }}
                  transition={{ duration: 0.25, delay: hover == null ? (ri * columns.length + ci) * 0.008 : 0 }}
                  className={cn("rounded-md py-2.5 text-center text-[12px] font-semibold tabular-nums text-[#14181f]", onCell && "cursor-pointer")}
                  style={{ background: healthColor(v) }}
                  title={`${typeof r.label === "string" ? r.label : r.key} · ${c.label}: ${format(v)}`}
                >
                  {format(v)}
                </motion.button>
              );
            })}
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-2 text-[10px] text-muted-foreground">
        <span>0</span>
        {[10, 30, 50, 70, 90].map((v) => (
          <span key={v} className="h-2.5 w-7 rounded-sm" style={{ background: healthColor(v) }} />
        ))}
        <span>100 health</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ ticker */

export type TickerItem = { key: string; label: string; value: string; change: number; href?: string };

/** Scrolling ticker tape (pauses on hover); arrows and colour show direction. */
export function TickerTape({ items, speed = 38 }: { items: TickerItem[]; speed?: number }) {
  const [paused, setPaused] = useState(false);
  const loop = [...items, ...items];
  return (
    <div
      className="relative overflow-hidden rounded-xl border border-border bg-card"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      aria-label="Fleet ticker"
    >
      <motion.div
        className="flex w-max gap-8 py-2.5 pl-4"
        animate={paused ? undefined : { x: ["0%", "-50%"] }}
        transition={{ duration: speed, ease: "linear", repeat: Infinity }}
      >
        {loop.map((item, i) => {
          const up = item.change >= 0;
          const Comp = item.href ? "a" : "span";
          return (
            <Comp key={`${item.key}-${i}`} href={item.href} className="flex items-center gap-2 whitespace-nowrap text-[12px]">
              <span className="font-mono font-medium">{item.label}</span>
              <span className="tabular-nums text-ink-2">{item.value}</span>
              <span className="font-semibold tabular-nums" style={{ color: up ? UP : DOWN }}>
                {up ? "▲" : "▼"} {Math.abs(item.change).toFixed(1)}
              </span>
            </Comp>
          );
        })}
      </motion.div>
    </div>
  );
}
