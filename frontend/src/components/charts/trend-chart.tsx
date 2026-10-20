"use client";

import { useId, useMemo, useRef, useState, type MouseEvent } from "react";
import { motion } from "framer-motion";
import { DOWN, FILL_OPACITY, GRID_STRONG, SERIES, UP, compact, nf, niceScale, smoothPath } from "@/lib/viz";
import { cn } from "@/lib/utils";

export type TrendDatum = { x: string | number; value: number; volume?: number };

/**
 * Stock-app style line chart.
 *
 *  - Headline value with a coloured change pill; hovering moves the headline
 *    to the hovered point, exactly like a trading app.
 *  - The line takes the colour of its direction over the window (mint when it
 *    moved the "good" way, soft red when it moved the bad way) and has a flat
 *    translucent fill - never a gradient.
 *  - A dotted baseline marks the value at the start of the window ("previous
 *    close"), a dashed crosshair with a dot and a label follows the pointer,
 *    and the last point pulses to signal a live series.
 *  - Optional volume bars under the line, and pill range tabs below.
 *
 * Axis text and markers are HTML over the plot because the SVG stretches with
 * preserveAspectRatio="none" (circles and glyphs inside it would distort).
 */
export function TrendChart({
  data,
  label,
  unit,
  height = 260,
  ranges = null,
  rangeSuffix = "",
  headline = "last",
  goodDirection = "up",
  valueFormat = (v: number) => nf.format(Math.round(v * 10) / 10),
  xFormat = (x: string | number) => String(x),
  domain,
  zeroBased = false,
  volumeLabel,
  emptyLabel = "No data yet",
  className,
}: {
  data: TrendDatum[];
  label: string;
  unit?: string;
  height?: number;
  ranges?: number[] | null;
  rangeSuffix?: string;
  headline?: "last" | "none";
  /** Which direction counts as good; "neutral" draws in the calm series hue. */
  goodDirection?: "up" | "down" | "neutral";
  valueFormat?: (v: number) => string;
  xFormat?: (x: string | number) => string;
  domain?: [number, number];
  zeroBased?: boolean;
  volumeLabel?: string;
  emptyLabel?: string;
  className?: string;
}) {
  const clipId = `clip-${useId().replace(/:/g, "")}`;
  const allRange = data.length;
  const [range, setRange] = useState<number>(allRange);
  const [hover, setHover] = useState<number | null>(null);
  const plotRef = useRef<HTMLDivElement>(null);

  const view = useMemo(() => (ranges && range < data.length ? data.slice(-range) : data), [data, range, ranges]);
  const hasVolume = volumeLabel != null && view.some((d) => d.volume != null);

  const g = useMemo(() => {
    const W = 100;
    const H = 100;
    const values = view.map((d) => d.value);
    const lo = Math.min(...values);
    const hi = Math.max(...values);
    let bottom: number;
    let top: number;
    if (domain) [bottom, top] = domain;
    else if (zeroBased) {
      const s = niceScale(Math.max(hi, 1), 0);
      bottom = 0;
      top = s.top;
    } else {
      const pad = (hi - lo || Math.abs(hi) || 1) * 0.12;
      bottom = lo - pad;
      top = hi + pad;
    }
    const span = top - bottom || 1;
    const x = (i: number) => (view.length <= 1 ? 0 : (i / (view.length - 1)) * W);
    const y = (v: number) => H - ((v - bottom) / span) * H;
    const path = smoothPath(view.map((d, i) => [x(i), y(d.value)] as [number, number]));
    const maxVol = Math.max(1, ...view.map((d) => d.volume ?? 0));
    return { W, H, top, bottom, span, x, y, path, area: `${path} L${W},${H} L0,${H} Z`, maxVol };
  }, [view, domain, zeroBased]);

  if (data.length < 2) {
    return (
      <div className="flex items-center justify-center text-[13px] text-muted-foreground" style={{ height }}>
        {emptyLabel}
      </div>
    );
  }

  const first = view[0].value;
  const lastIndex = view.length - 1;
  const shownIndex = hover ?? lastIndex;
  const shown = view[shownIndex];
  const delta = shown.value - first;
  const pct = first !== 0 ? (delta / Math.abs(first)) * 100 : null;
  const windowDelta = view[lastIndex].value - first;
  const good = goodDirection === "neutral" ? null : goodDirection === "up" ? windowDelta >= 0 : windowDelta <= 0;
  const lineColor = good == null ? SERIES : good ? UP : DOWN;
  const deltaGood = goodDirection === "neutral" ? null : goodDirection === "up" ? delta >= 0 : delta <= 0;
  const pillColor = deltaGood == null ? SERIES : deltaGood ? UP : DOWN;

  const headerH = headline === "none" ? 0 : 64;
  const tabsH = ranges ? 40 : 0;
  const volumeH = hasVolume ? 46 : 0;
  const plotH = Math.max(80, height - headerH - tabsH - volumeH - 22);
  const yTicks = [g.top, g.bottom + g.span / 2, g.bottom];

  function onMove(e: MouseEvent<HTMLDivElement>) {
    const box = plotRef.current?.getBoundingClientRect();
    if (!box || box.width === 0) return;
    const frac = Math.min(1, Math.max(0, (e.clientX - box.left) / box.width));
    setHover(Math.round(frac * lastIndex));
  }

  const leftPct = (i: number) => (lastIndex === 0 ? 0 : (i / lastIndex) * 100);
  const topPct = (v: number) => (1 - (v - g.bottom) / g.span) * 100;

  return (
    <div className={className}>
      {headline !== "none" ? (
        <div className="mb-3" aria-live="polite">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="font-display text-[28px] font-semibold leading-none tracking-tight">{valueFormat(shown.value)}</span>
            {unit ? <span className="text-[12px] text-muted-foreground">{unit}</span> : null}
            <span
              className="rounded-full px-2 py-0.5 text-[12px] font-semibold"
              style={{ color: pillColor, background: `color-mix(in oklab, ${pillColor} 14%, transparent)` }}
            >
              {delta >= 0 ? "▲" : "▼"} {valueFormat(Math.abs(delta))}
              {pct != null ? ` (${Math.abs(pct).toFixed(1)}%)` : ""}
            </span>
          </div>
          <div className="mt-1.5 text-[11px] text-muted-foreground">
            {label} · {hover != null ? xFormat(shown.x) : `latest of ${view.length} points`} · change since {xFormat(view[0].x)}
          </div>
        </div>
      ) : null}

      <div className="flex" style={{ height: plotH }}>
        <div ref={plotRef} className="relative min-w-0 flex-1 cursor-crosshair" onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
          <svg viewBox={`0 0 ${g.W} ${g.H}`} preserveAspectRatio="none" className="h-full w-full overflow-visible" role="img" aria-label={label}>
            <defs>
              <clipPath id={clipId}>
                <motion.rect
                  key={`${range}-${view.length}`}
                  x="0"
                  y="-10"
                  height={g.H + 20}
                  initial={{ width: 0 }}
                  animate={{ width: g.W }}
                  transition={{ duration: 0.9, ease: [0.22, 0.61, 0.36, 1] }}
                />
              </clipPath>
            </defs>
            {/* "Previous close": the value at the start of the window. */}
            <line
              x1="0"
              x2={g.W}
              y1={g.y(first)}
              y2={g.y(first)}
              style={{ stroke: GRID_STRONG }}
              strokeWidth="1"
              strokeDasharray="2 4"
              vectorEffect="non-scaling-stroke"
            />
            <g clipPath={`url(#${clipId})`}>
              <path d={g.area} style={{ fill: lineColor, fillOpacity: FILL_OPACITY }} />
              <path
                d={g.path}
                fill="none"
                style={{ stroke: lineColor }}
                strokeWidth="2.25"
                strokeLinecap="round"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
              />
            </g>
            {hover != null ? (
              <line
                x1={g.x(hover)}
                x2={g.x(hover)}
                y1="0"
                y2={g.H}
                style={{ stroke: GRID_STRONG }}
                strokeWidth="1"
                strokeDasharray="3 3"
                vectorEffect="non-scaling-stroke"
              />
            ) : null}
          </svg>

          {hover == null ? (
            <span
              className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2"
              style={{ left: `${leftPct(lastIndex)}%`, top: `${topPct(view[lastIndex].value)}%` }}
            >
              <span className="absolute inset-0 rounded-full motion-safe:animate-ping" style={{ background: lineColor, opacity: 0.45 }} />
              <span className="relative block h-2.5 w-2.5 rounded-full ring-2 ring-card" style={{ background: lineColor }} />
            </span>
          ) : (
            <>
              <span
                className="pointer-events-none absolute block h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-[3px] ring-card"
                style={{ left: `${leftPct(hover)}%`, top: `${topPct(shown.value)}%`, background: lineColor }}
              />
              <span
                className="pointer-events-none absolute top-0 z-10 -translate-y-full whitespace-nowrap rounded-md border border-border bg-popover px-2 py-0.5 text-[11px] font-medium shadow-sm"
                style={{
                  left: `${leftPct(hover)}%`,
                  transform: `translate(${hover === 0 ? "0" : hover === lastIndex ? "-100%" : "-50%"}, -110%)`,
                }}
              >
                {xFormat(shown.x)} · {valueFormat(shown.value)}
                {unit ? ` ${unit}` : ""}
              </span>
            </>
          )}
        </div>
        <div className="relative w-11 shrink-0" aria-hidden>
          {yTicks.map((t, i) => (
            <span key={i} className="absolute left-2 -translate-y-1/2 text-[10px] tabular-nums text-muted-foreground" style={{ top: `${topPct(t)}%` }}>
              {compact(Math.round(t * 10) / 10)}
            </span>
          ))}
        </div>
      </div>

      {hasVolume ? (
        <div className="mt-2 pr-11">
          <div className="flex h-9 items-end gap-[2px]" aria-label={volumeLabel}>
            {view.map((d, i) => (
              <motion.div
                key={`${range}-${i}`}
                className="flex-1 rounded-t-[2px]"
                initial={{ height: 0 }}
                animate={{ height: `${Math.max(4, ((d.volume ?? 0) / g.maxVol) * 100)}%` }}
                transition={{ duration: 0.5, delay: i * 0.015 }}
                style={{ background: hover === i ? lineColor : "var(--chart-6)", opacity: hover == null || hover === i ? 0.55 : 0.3 }}
                title={`${xFormat(d.x)} · ${volumeLabel}: ${d.volume ?? 0}`}
              />
            ))}
          </div>
          <div className="mt-1 text-[10px] text-muted-foreground">
            {volumeLabel}
            {hover != null ? ` · ${view[hover].volume ?? 0}` : ""}
          </div>
        </div>
      ) : null}

      <div className="mt-1.5 flex justify-between pr-11 text-[10px] text-muted-foreground">
        <span>{xFormat(view[0].x)}</span>
        <span>{xFormat(view[Math.floor(lastIndex / 2)].x)}</span>
        <span>{xFormat(view[lastIndex].x)}</span>
      </div>

      {ranges ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {[...ranges.filter((r) => r < data.length), allRange].map((r) => {
            const active = range === r;
            return (
              <button
                key={r}
                type="button"
                onClick={() => {
                  setRange(r);
                  setHover(null);
                }}
                aria-pressed={active}
                className={cn(
                  "rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors",
                  active ? "border-transparent" : "border-border text-muted-foreground hover:bg-muted",
                )}
                style={active ? { color: lineColor, background: `color-mix(in oklab, ${lineColor} 14%, transparent)` } : undefined}
              >
                {r === allRange ? "ALL" : `${r}${rangeSuffix}`}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
