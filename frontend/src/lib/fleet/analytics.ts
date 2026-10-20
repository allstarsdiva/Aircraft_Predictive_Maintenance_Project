/**
 * Derived series for the stock-style charts. Everything is computed from the
 * simulated fleet's recorded trends; nothing here is new data.
 */
import { meanTrend } from "./generate.ts";
import type { Aircraft, FleetComponent } from "./types.ts";

const round1 = (v: number) => Math.round(v * 10) / 10;

function percentile(values: number[], p: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  const idx = (sorted.length - 1) * p;
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

/** Mean health of one aircraft's components per recorded cycle. */
export function aircraftHealthSeries(aircraft: Aircraft): number[] {
  return meanTrend(aircraft.components.map((c) => c.healthTrend)).map((p) => p.value);
}

/** Fleet-wide mean health per cycle, with how many components sat below the danger line. */
export function fleetHealthSeries(fleet: Aircraft[], danger = 45): { x: string; value: number; volume: number }[] {
  const components = fleet.flatMap((a) => a.components);
  return meanTrend(components.map((c) => c.healthTrend)).map((p, i) => ({
    x: `C${p.cycle + 1}`,
    value: p.value,
    volume: components.filter((c) => (c.healthTrend[i]?.value ?? 100) < danger).length,
  }));
}

/** Fleet-wide mean RUL per cycle, with how many components were at or below the high-risk line. */
export function fleetRulSeries(fleet: Aircraft[], highRisk = 30): { x: string; value: number; volume: number }[] {
  const components = fleet.flatMap((a) => a.components);
  return meanTrend(components.map((c) => c.rulTrend)).map((p, i) => ({
    x: `C${p.cycle + 1}`,
    value: p.value,
    volume: components.filter((c) => (c.rulTrend[i]?.value ?? Infinity) <= highRisk).length,
  }));
}

/**
 * One candle per aircraft over the recorded window, like a stock's candle for
 * a period: open = mean health at the first cycle, close = latest, wick =
 * highest and lowest mean health reached in between.
 */
export function aircraftCandles(fleet: Aircraft[]): { x: string; open: number; high: number; low: number; close: number }[] {
  return fleet.map((aircraft) => {
    const s = aircraftHealthSeries(aircraft);
    return {
      x: aircraft.tail,
      open: round1(s[0] ?? 0),
      close: round1(s[s.length - 1] ?? 0),
      high: round1(Math.max(...s)),
      low: round1(Math.min(...s)),
    };
  });
}

/**
 * Health candles per cycle: open = previous cycle's fleet mean, close = this
 * cycle's mean, wick = 10th to 90th percentile across all components.
 */
export function healthCandles(components: FleetComponent[]): { x: string; open: number; high: number; low: number; close: number }[] {
  if (!components.length) return [];
  const length = Math.min(...components.map((c) => c.healthTrend.length));
  const means = Array.from({ length }, (_, i) => components.reduce((a, c) => a + c.healthTrend[i].value, 0) / components.length);
  return means.map((close, i) => {
    const values = components.map((c) => c.healthTrend[i].value);
    const open = i === 0 ? close : means[i - 1];
    return {
      x: `C${i + 1}`,
      open: round1(open),
      close: round1(close),
      high: round1(Math.max(percentile(values, 0.9), open, close)),
      low: round1(Math.min(percentile(values, 0.1), open, close)),
    };
  });
}

export interface Mover {
  aircraft: Aircraft;
  series: number[];
  change: number;
}

/** Aircraft ranked by change in mean health over the recorded window. */
export function movers(fleet: Aircraft[]): { gainers: Mover[]; losers: Mover[] } {
  const all = fleet.map((aircraft) => {
    const series = aircraftHealthSeries(aircraft);
    return { aircraft, series, change: round1((series[series.length - 1] ?? 0) - (series[0] ?? 0)) };
  });
  const sorted = [...all].sort((a, b) => b.change - a.change);
  return {
    gainers: sorted.filter((m) => m.change > 0).slice(0, 3),
    losers: sorted.filter((m) => m.change < 0).reverse().slice(0, 3),
  };
}
