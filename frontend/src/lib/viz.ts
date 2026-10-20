/**
 * One palette and one form rule for every chart.
 *
 * Colours are CSS variables so every chart follows the light / true-black
 * theme automatically. The palette is soft (stock-app style) and validated:
 * mint = up / good, soft red = down / critical, gold = caution, and five calm
 * identity hues in a fixed, never-cycled order. Fills are flat - no gradients.
 * Every chart prints its values, which relieves the pastel contrast warning.
 */
export const SERIES = "var(--chart-1)";
export const SERIES_2 = "var(--chart-3)";
export const UP = "var(--chart-up)";
export const DOWN = "var(--chart-down)";
export const GOOD = "var(--chart-up)";
export const WARN = "var(--chart-warn)";
export const DANGER = "var(--chart-down)";
export const NEUTRAL = "var(--chart-6)";
export const GRID = "var(--hairline)";
export const GRID_STRONG = "var(--hairline-strong)";
export const TRACK = "var(--track)";
export const INK = "var(--ink)";
export const FILL_OPACITY = "var(--chart-fill-opacity)";

/** Identity hues, fixed order. A sixth+ series folds into "Other" (neutral). */
export const RAMP = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"] as const;

export function ramp(i: number): string {
  return RAMP[i] ?? NEUTRAL;
}

/**
 * Flat colour for a 0-100 health value on a soft red -> gold -> mint scale.
 * Each cell is ONE flat colour (color-mix), not a gradient.
 */
export function healthColor(value: number): string {
  const v = Math.max(0, Math.min(100, value));
  if (v <= 50) return `color-mix(in oklch, var(--chart-warn) ${Math.round((v / 50) * 100)}%, var(--chart-down))`;
  return `color-mix(in oklch, var(--chart-up) ${Math.round(((v - 50) / 50) * 100)}%, var(--chart-warn))`;
}

export const nf = new Intl.NumberFormat("en-IN");

/** `some_label-here` -> `Some Label Here`. */
export function humanise(label: string): string {
  return label
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

/** Round an axis top up to a 1/2/5 x 10^n step so ticks read as round numbers. */
export function niceScale(peak: number, floor = 0): { top: number; bottom: number; ticks: number[] } {
  const span = Math.max(peak - floor, 1e-9);
  const raw = span / 4;
  const mag = 10 ** Math.floor(Math.log10(Math.max(raw, 1e-9)));
  const norm = raw / mag;
  const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * mag;
  const bottom = Math.floor(floor / step) * step;
  const top = Math.ceil(peak / step) * step || step;
  const ticks: number[] = [];
  for (let t = bottom; t <= top + step * 1e-6; t += step) ticks.push(Number(t.toFixed(10)));
  return { top, bottom, ticks };
}

export function compact(n: number): string {
  const a = Math.abs(n);
  if (a >= 1e9) return `${(n / 1e9).toFixed(a % 1e9 === 0 ? 0 : 1)}B`;
  if (a >= 1e6) return `${(n / 1e6).toFixed(a % 1e6 === 0 ? 0 : 1)}M`;
  if (a >= 1e3) return `${(n / 1e3).toFixed(a % 1e3 === 0 ? 0 : 1)}k`;
  if (a > 0 && a < 1) return n.toFixed(2);
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

/** Linear-interpolated percentile (p in 0..1) of an unsorted list. */
export function percentile(values: number[], p: number): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = (sorted.length - 1) * p;
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

export const mean = (values: number[]): number => values.reduce((a, v) => a + v, 0) / Math.max(values.length, 1);

/**
 * Monotone cubic path through the points (same rule as d3's curveMonotoneX):
 * smooth, but it never overshoots and so never invents a peak.
 */
export function smoothPath(pts: [number, number][]): string {
  if (pts.length === 0) return "";
  if (pts.length < 3) return pts.map((p, i) => `${i === 0 ? "M" : "L"}${p[0]},${p[1]}`).join(" ");
  const n = pts.length;
  const dx: number[] = [];
  const slope: number[] = [];
  for (let i = 0; i < n - 1; i++) {
    const h = pts[i + 1][0] - pts[i][0];
    dx.push(h);
    slope.push(h === 0 ? 0 : (pts[i + 1][1] - pts[i][1]) / h);
  }
  const m: number[] = [slope[0] ?? 0];
  for (let i = 1; i < n - 1; i++) {
    const a = slope[i - 1];
    const b = slope[i];
    m.push(a * b <= 0 ? 0 : (a + b) / 2);
  }
  m.push(slope[n - 2] ?? 0);
  for (let i = 0; i < n - 1; i++) {
    if (slope[i] === 0) {
      m[i] = 0;
      m[i + 1] = 0;
      continue;
    }
    const a = m[i] / slope[i];
    const b = m[i + 1] / slope[i];
    const t = Math.hypot(a, b);
    if (t > 3) {
      m[i] = (3 / t) * a * slope[i];
      m[i + 1] = (3 / t) * b * slope[i];
    }
  }
  let d = `M${pts[0][0].toFixed(2)},${pts[0][1].toFixed(2)}`;
  for (let i = 0; i < n - 1; i++) {
    const h = dx[i];
    const c1x = pts[i][0] + h / 3;
    const c1y = pts[i][1] + (m[i] * h) / 3;
    const c2x = pts[i + 1][0] - h / 3;
    const c2y = pts[i + 1][1] - (m[i + 1] * h) / 3;
    d += ` C${c1x.toFixed(2)},${c1y.toFixed(2)} ${c2x.toFixed(2)},${c2y.toFixed(2)} ${pts[i + 1][0].toFixed(2)},${pts[i + 1][1].toFixed(2)}`;
  }
  return d;
}

/** Inline polyline for a sparkline. */
export function sparklinePath(values: number[], w: number, h: number, pad = 2): string {
  if (values.length < 2) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const rng = max - min || 1;
  return values
    .map((v, i) => {
      const x = pad + (i / (values.length - 1)) * (w - pad * 2);
      const y = h - pad - ((v - min) / rng) * (h - pad * 2);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
}

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

/** Signed change between the first and last value of a series. */
export function changeOf(values: number[]): { abs: number; pct: number | null; up: boolean } {
  const first = values[0] ?? 0;
  const last = values[values.length - 1] ?? 0;
  const abs = last - first;
  return { abs, pct: first !== 0 ? (abs / Math.abs(first)) * 100 : null, up: abs >= 0 };
}
