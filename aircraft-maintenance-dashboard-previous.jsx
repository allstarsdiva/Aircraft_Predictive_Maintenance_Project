import React, { useState, useMemo, useEffect, useCallback } from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  RadialBarChart, RadialBar, PolarAngleAxis,
} from "recharts";
import {
  Plane, Gauge, AlertTriangle, CheckCircle2, Activity, Thermometer, Wind,
  Zap, Fuel, Wrench, ChevronRight, ChevronLeft, RefreshCw, Wifi,
  WifiOff, LayoutGrid, ClipboardList, Circle, ArrowUpRight, ArrowDownRight,
  Minus, Bell, Search, ShieldCheck, Clock3, BrainCircuit, Sparkles, Target, ChevronUp, ChevronDown, Crosshair, GaugeCircle, PlaneTakeoff, Database, RadioTower, CircleDot, Timer, Cpu, ActivitySquare, Layers3, Route, ShieldAlert, ZapIcon, BarChart3, SlidersHorizontal, Eye, EyeOff, Maximize2, X,
} from "lucide-react";

/* ============================================================================
   DATA LAYER
   In production this whole block is replaced by calls into the FastAPI
   backend shown in the architecture diagram:
     GET  /api/fleet                 -> fleet summary + aircraft list
     GET  /api/aircraft/:id          -> single aircraft, components, sensors
     GET  /api/component/:id/history -> trend series for charts
     WS   /ws/telemetry              -> live sensor + RUL push updates
   generateFleet() below stands in for that REST layer, and useLiveTelemetry()
   stands in for the WebSocket subscription (jittering values on an interval).
============================================================================ */

const COMPONENT_DEFS = {
  Engine: {
    icon: Gauge,
    sensors: [
      { key: "temperature", label: "Temperature", unit: "\u00b0C", range: [550, 950] },
      { key: "vibration", label: "Vibration", unit: "mm/s", range: [0.5, 12] },
      { key: "pressure", label: "Pressure", unit: "psi", range: [180, 420] },
      { key: "rpm", label: "RPM", unit: "rpm", range: [8000, 15000] },
    ],
  },
  "Landing Gear": {
    icon: Circle,
    sensors: [
      { key: "strutPressure", label: "Strut Pressure", unit: "psi", range: [800, 1600] },
      { key: "brakeTemp", label: "Brake Temp", unit: "\u00b0C", range: [80, 400] },
      { key: "tirePressure", label: "Tire Pressure", unit: "psi", range: [180, 220] },
      { key: "shockAbsorb", label: "Shock Absorption", unit: "%", range: [60, 100] },
    ],
  },
  Hydraulic: {
    icon: Wind,
    sensors: [
      { key: "fluidPressure", label: "Fluid Pressure", unit: "psi", range: [2800, 3200] },
      { key: "fluidTemp", label: "Fluid Temp", unit: "\u00b0C", range: [40, 110] },
      { key: "flowRate", label: "Flow Rate", unit: "L/min", range: [10, 45] },
      { key: "contamination", label: "Contamination", unit: "ppm", range: [0, 25] },
    ],
  },
  Electrical: {
    icon: Zap,
    sensors: [
      { key: "voltage", label: "Voltage", unit: "V", range: [110, 130] },
      { key: "current", label: "Current", unit: "A", range: [5, 60] },
      { key: "batteryHealth", label: "Battery Health", unit: "%", range: [40, 100] },
      { key: "load", label: "System Load", unit: "%", range: [10, 95] },
    ],
  },
  Fuel: {
    icon: Fuel,
    sensors: [
      { key: "flowRate", label: "Flow Rate", unit: "L/h", range: [800, 2600] },
      { key: "tankPressure", label: "Tank Pressure", unit: "psi", range: [12, 30] },
      { key: "temperature", label: "Temperature", unit: "\u00b0C", range: [-10, 45] },
      { key: "contamination", label: "Contamination", unit: "ppm", range: [0, 20] },
    ],
  },
};

const COMPONENT_TYPES = Object.keys(COMPONENT_DEFS);
const AIRCRAFT_TYPES = [
  "Boeing 737-800", "Airbus A320neo", "Boeing 777-300ER",
  "Airbus A350-900", "Boeing 787-9", "Embraer E190",
];
const AIRLINE_CODES = ["AA", "DL", "UA", "SW", "BA", "LH", "EK", "QF", "AF"];

function rand(min, max) { return Math.random() * (max - min) + min; }
function randInt(min, max) { return Math.floor(rand(min, max + 1)); }
function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }

function riskFromRUL(rul) {
  if (rul <= 30) return "High";
  if (rul <= 150) return "Medium";
  return "Low";
}
const RECOMMENDATION = {
  High: "Inspect Immediately",
  Medium: "Monitor Closely",
  Low: "No Action Required",
};

function healthForRisk(risk) {
  if (risk === "High") return randInt(12, 42);
  if (risk === "Medium") return randInt(45, 76);
  return randInt(80, 99);
}

function buildTrend(endValue, points, volatility) {
  const drift = rand(-volatility, volatility);
  const start = clamp(endValue - drift * points, 0, 100);
  const out = [];
  for (let i = 0; i < points; i++) {
    const t = i / (points - 1);
    const base = start + (endValue - start) * t;
    out.push({ cycle: i, value: Math.round(clamp(base + rand(-volatility, volatility), 0, 100)) });
  }
  out[out.length - 1].value = Math.round(endValue);
  return out;
}

function buildRULTrend(endRUL, points) {
  const start = endRUL + randInt(20, 80);
  const out = [];
  for (let i = 0; i < points; i++) {
    const t = i / (points - 1);
    const val = start + (endRUL - start) * t + rand(-4, 4);
    out.push({ cycle: i, value: Math.max(0, Math.round(val)) });
  }
  out[out.length - 1].value = endRUL;
  return out;
}

function makeComponent(type) {
  const rul = randInt(4, 300);
  const risk = riskFromRUL(rul);
  const health = healthForRisk(risk);
  const failureProbability = risk === "High" ? randInt(55, 92) : risk === "Medium" ? randInt(18, 48) : randInt(1, 15);
  const def = COMPONENT_DEFS[type];
  const volatility = risk === "High" ? 9 : risk === "Medium" ? 5 : 2;

  const sensors = def.sensors.map((s) => {
    const [lo, hi] = s.range;
    const span = hi - lo;
    const skew = risk === "High" ? rand(0.7, 1.15) : risk === "Medium" ? rand(0.4, 0.85) : rand(0.15, 0.55);
    const value = lo + span * clamp(skew, 0, 1.15);
    return {
      ...s,
      value: Math.round(value * 10) / 10,
      trend: buildTrend(clamp(skew * 100, 0, 100), 16, volatility),
    };
  });

  return {
    type,
    icon: def.icon,
    health,
    rul,
    risk,
    priority: risk,
    recommendation: RECOMMENDATION[risk],
    failureProbability,
    healthTrend: buildTrend(health, 20, volatility),
    rulTrend: buildRULTrend(rul, 20),
    sensors,
  };
}

function aircraftStatus(components) {
  if (components.some((c) => c.risk === "High")) return "Critical";
  if (components.some((c) => c.risk === "Medium")) return "Warning";
  return "Healthy";
}

function generateFleet(count = 9) {
  return Array.from({ length: count }, (_, i) => {
    const components = COMPONENT_TYPES.map(makeComponent);
    const status = aircraftStatus(components);
    const overallHealth = Math.round(components.reduce((a, c) => a + c.health, 0) / components.length);
    return {
      id: `AC-${1000 + i}`,
      tail: `N${randInt(100, 999)}${AIRLINE_CODES[randInt(0, AIRLINE_CODES.length - 1)]}`,
      model: AIRCRAFT_TYPES[randInt(0, AIRCRAFT_TYPES.length - 1)],
      status,
      overallHealth,
      flightHours: randInt(1200, 48000),
      components,
    };
  });
}

/* ---- live "WebSocket" simulation: jitters values on an interval -------- */
function useLiveTelemetry(setFleet, enabled) {
  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => {
      setFleet((prev) =>
        prev.map((ac) => {
          const components = ac.components.map((c) => {
            const jitter = c.risk === "High" ? 3 : c.risk === "Medium" ? 1.5 : 0.5;
            const health = Math.round(clamp(c.health + rand(-jitter, jitter * 0.6), 3, 99));
            const rul = Math.max(0, Math.round(c.rul - rand(0, 0.4)));
            const risk = riskFromRUL(rul);
            return {
              ...c,
              health,
              rul,
              risk,
              priority: risk,
              recommendation: RECOMMENDATION[risk],
              sensors: c.sensors.map((s) => ({
                ...s,
                value: Math.round((s.value + rand(-1, 1) * (s.range[1] - s.range[0]) * 0.01) * 10) / 10,
              })),
            };
          });
          return { ...ac, components, status: aircraftStatus(components), overallHealth: Math.round(components.reduce((a, c) => a + c.health, 0) / components.length) };
        })
      );
    }, 2500);
    return () => clearInterval(id);
  }, [enabled, setFleet]);
}

/* ============================================================================
   UI PRIMITIVES
============================================================================ */

const STATUS_STYLES = {
  Healthy: { text: "text-emerald-400", bg: "bg-emerald-400/10", ring: "ring-emerald-400/30", dot: "bg-emerald-400" },
  Warning: { text: "text-amber-400", bg: "bg-amber-400/10", ring: "ring-amber-400/30", dot: "bg-amber-400" },
  Critical: { text: "text-red-400", bg: "bg-red-400/10", ring: "ring-red-400/30", dot: "bg-red-400" },
};
const RISK_STYLES = {
  Low: { text: "text-emerald-400", bg: "bg-emerald-400/10", border: "border-emerald-400/30" },
  Medium: { text: "text-amber-400", bg: "bg-amber-400/10", border: "border-amber-400/30" },
  High: { text: "text-red-400", bg: "bg-red-400/10", border: "border-red-400/30" },
};

function healthColor(h) {
  if (h >= 75) return "#34d399";
  if (h >= 45) return "#fbbf24";
  return "#f87171";
}

function StatusPill({ status }) {
  const s = STATUS_STYLES[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${s.text} ${s.bg} ring-1 ${s.ring}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {status}
    </span>
  );
}

function RiskBadge({ risk }) {
  const s = RISK_STYLES[risk];
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold ${s.text} ${s.bg} ${s.border}`}>
      {risk}
    </span>
  );
}

function HealthGauge({ value, size = 88 }) {
  const color = healthColor(value);
  const data = [{ value }];
  return (
    <div style={{ width: size, height: size }} className="relative shrink-0">
      <ResponsiveContainer width="100%" height="100%">
        <RadialBarChart
          innerRadius="70%"
          outerRadius="100%"
          data={data}
          startAngle={90}
          endAngle={-270}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
          <RadialBar dataKey="value" cornerRadius={20} fill={color} background={{ fill: "#1e293b" }} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-lg font-bold text-slate-100">{value}</span>
        <span className="text-[9px] uppercase tracking-wider text-slate-500">health</span>
      </div>
    </div>
  );
}

function MiniTrend({ data, color, height = 40 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
        <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function TrendArrow({ data }) {
  if (data.length < 2) return <Minus className="h-3.5 w-3.5 text-slate-500" />;
  const delta = data[data.length - 1].value - data[0].value;
  if (Math.abs(delta) < 2) return <Minus className="h-3.5 w-3.5 text-slate-500" />;
  return delta > 0
    ? <ArrowUpRight className="h-3.5 w-3.5 text-emerald-400" />
    : <ArrowDownRight className="h-3.5 w-3.5 text-red-400" />;
}

function SectionLabel({ children, icon: Icon }) {
  return (
    <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-slate-500">
      {Icon && <Icon className="h-3.5 w-3.5" />}
      {children}
    </div>
  );
}

function Card({ children, className = "", onClick }) {
  return (
    <div
      onClick={onClick}
      className={`rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-sm ${onClick ? "cursor-pointer transition hover:border-slate-700 hover:bg-slate-900" : ""} ${className}`}
    >
      {children}
    </div>
  );
}


function MetricTile({ label, value, sub, icon: Icon, tone = "cyan", progress }) {
  const tones = {
    cyan: "text-cyan-300 bg-cyan-400/10 border-cyan-400/20",
    emerald: "text-emerald-300 bg-emerald-400/10 border-emerald-400/20",
    amber: "text-amber-300 bg-amber-400/10 border-amber-400/20",
    red: "text-red-300 bg-red-400/10 border-red-400/20",
    violet: "text-violet-300 bg-violet-400/10 border-violet-400/20",
  };
  return (
    <Card className="relative overflow-hidden">
      <div className={`absolute -right-6 -top-6 h-20 w-20 rounded-full blur-2xl opacity-20 ${tones[tone].split(" ")[1]}`} />
      <div className="relative flex items-start justify-between gap-3">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</div>
          <div className="mt-1 font-mono text-2xl font-bold text-slate-100">{value}</div>
          {sub && <div className="mt-1 text-[11px] text-slate-500">{sub}</div>}
        </div>
        <div className={`rounded-lg border p-2 ${tones[tone]}`}><Icon className="h-4 w-4" /></div>
      </div>
      {typeof progress === "number" && (
        <div className="relative mt-3 h-1 overflow-hidden rounded-full bg-slate-800">
          <div className={`h-full rounded-full ${tones[tone].split(" ")[1].replace("bg-", "bg-")}`} style={{ width: `${clamp(progress,0,100)}%` }} />
        </div>
      )}
    </Card>
  );
}

function FleetHealthMap({ fleet, onSelectAircraft }) {
  return (
    <Card className="overflow-hidden bg-gradient-to-br from-slate-900 via-slate-900 to-cyan-950/20">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-100">Fleet Health Matrix</div>
          <div className="text-[10px] uppercase tracking-wider text-slate-500">Live predictive state</div>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-slate-500"><CircleDot className="h-3 w-3 text-cyan-400" /> telemetry active</div>
      </div>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-3 xl:grid-cols-5">
        {fleet.map((ac) => {
          const tone = ac.status === "Critical" ? "border-red-400/40 bg-red-400/10" : ac.status === "Warning" ? "border-amber-400/40 bg-amber-400/10" : "border-emerald-400/30 bg-emerald-400/10";
          return (
            <button key={ac.id} onClick={() => onSelectAircraft(ac.id)}
              className={`group rounded-lg border p-2 text-left transition hover:-translate-y-0.5 hover:border-cyan-400/50 ${tone}`}>
              <div className="flex items-center justify-between">
                <PlaneTakeoff className="h-3.5 w-3.5 text-slate-400 group-hover:text-cyan-300" />
                <span className="font-mono text-[10px] text-slate-500">{ac.id}</span>
              </div>
              <div className="mt-2 truncate font-mono text-xs font-bold text-slate-100">{ac.tail}</div>
              <div className="mt-1 flex items-center justify-between">
                <span className="text-[9px] uppercase tracking-wider text-slate-500">{ac.status}</span>
                <span className="font-mono text-xs font-bold" style={{color: healthColor(ac.overallHealth)}}>{ac.overallHealth}%</span>
              </div>
            </button>
          );
        })}
      </div>
    </Card>
  );
}

function PredictiveInsight({ fleet }) {
  const critical = fleet.filter(a => a.status === "Critical");
  const lowest = [...fleet].sort((a,b) => a.overallHealth - b.overallHealth)[0];
  const worst = lowest?.components.reduce((a,b) => a.rul < b.rul ? a : b);
  const confidence = clamp(Math.round(88 - (critical.length * 3) + rand(-2,2)), 72, 96);
  return (
    <Card className="relative overflow-hidden border-cyan-400/20 bg-gradient-to-br from-cyan-400/[0.07] via-slate-900 to-violet-500/[0.05]">
      <div className="absolute right-0 top-0 h-28 w-28 rounded-full bg-cyan-400/10 blur-3xl" />
      <div className="relative flex items-start gap-3">
        <div className="rounded-xl border border-cyan-400/20 bg-cyan-400/10 p-2.5"><BrainCircuit className="h-5 w-5 text-cyan-300" /></div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-100">Predictive Intelligence</span>
            <span className="rounded-full bg-cyan-400/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-cyan-300">AI Insight</span>
          </div>
          <p className="mt-1.5 text-xs leading-5 text-slate-400">
            {worst ? <><span className="font-mono font-semibold text-slate-200">{lowest.tail}</span> is currently the fleet's weakest asset. <span className="text-slate-200">{worst.type}</span> has the shortest projected life at <span className="font-mono text-red-300">{worst.rul} cycles</span>.</> : "No immediate predictive concern detected."}
          </p>
        </div>
        <div className="hidden text-right sm:block">
          <div className="text-[9px] uppercase tracking-wider text-slate-500">Model confidence</div>
          <div className="font-mono text-lg font-bold text-cyan-300">{confidence}%</div>
        </div>
      </div>
      <div className="relative mt-4 grid grid-cols-3 gap-2 border-t border-slate-800/70 pt-3">
        <div><div className="text-[9px] uppercase text-slate-600">Risk signal</div><div className="mt-0.5 text-xs font-semibold text-slate-300">{critical.length ? "Escalated" : "Stable"}</div></div>
        <div><div className="text-[9px] uppercase text-slate-600">Action</div><div className="mt-0.5 text-xs font-semibold text-slate-300">{worst?.risk === "High" ? "Inspect" : "Monitor"}</div></div>
        <div><div className="text-[9px] uppercase text-slate-600">Next scan</div><div className="mt-0.5 text-xs font-semibold text-slate-300">2.5 sec</div></div>
      </div>
    </Card>
  );
}

/* ============================================================================
   VIEW: FLEET DASHBOARD
============================================================================ */

function FleetDashboard({ fleet, onSelectAircraft, connected }) {
  const counts = useMemo(() => ({
    total: fleet.length,
    healthy: fleet.filter((a) => a.status === "Healthy").length,
    warning: fleet.filter((a) => a.status === "Warning").length,
    critical: fleet.filter((a) => a.status === "Critical").length,
  }), [fleet]);

  const avgHealth = Math.round(fleet.reduce((sum, a) => sum + a.overallHealth, 0) / Math.max(fleet.length, 1));
  const allComponents = fleet.flatMap(a => a.components);
  const avgRul = Math.round(allComponents.reduce((sum, c) => sum + c.rul, 0) / Math.max(allComponents.length, 1));
  const highRiskComponents = allComponents.filter(c => c.risk === "High").length;
  const readiness = Math.round(((counts.healthy + counts.warning * 0.65) / Math.max(counts.total, 1)) * 100);

  const highestRisk = useMemo(() => [...fleet].sort((a, b) => a.overallHealth - b.overallHealth).slice(0, 5), [fleet]);
  const alerts = useMemo(() => {
    const list = [];
    fleet.forEach((ac) => ac.components.forEach((c) => {
      if (c.risk === "High") list.push({ aircraft: ac.tail, component: c.type, rul: c.rul, id: `${ac.id}-${c.type}` });
    }));
    return list.sort((a,b) => a.rul - b.rul).slice(0, 6);
  }, [fleet]);

  return (
    <div className="space-y-5">
      <div className="relative overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-900 via-slate-900 to-cyan-950/30 p-5">
        <div className="absolute -right-20 -top-24 h-56 w-56 rounded-full bg-cyan-400/10 blur-3xl" />
        <div className="relative flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
          <div>
            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.22em] text-cyan-300"><RadioTower className="h-3.5 w-3.5" /> Fleet Command · Predictive Operations</div>
            <h1 className="mt-2 text-2xl font-bold tracking-tight text-white sm:text-3xl">Aircraft Health Intelligence</h1>
            <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-400">A real-time command view for component health, remaining useful life, sensor anomalies and maintenance priority.</p>
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-slate-700/70 bg-slate-950/50 px-3 py-2">
            <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400 animate-pulse" : "bg-slate-600"}`} />
            <span className="text-[11px] font-semibold text-slate-300">{connected ? "LIVE TELEMETRY" : "TELEMETRY PAUSED"}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricTile label="Fleet Readiness" value={`${readiness}%`} sub={`${counts.healthy}/${counts.total} fully healthy`} icon={ShieldCheck} tone="emerald" progress={readiness} />
        <MetricTile label="Avg. Health" value={`${avgHealth}%`} sub="across all aircraft" icon={GaugeCircle} tone={avgHealth < 60 ? "red" : "cyan"} progress={avgHealth} />
        <MetricTile label="Avg. RUL" value={`${avgRul}`} sub="cycles remaining" icon={Timer} tone="violet" />
        <MetricTile label="High-Risk Signals" value={highRiskComponents} sub="components requiring attention" icon={ShieldAlert} tone={highRiskComponents ? "red" : "emerald"} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <FleetHealthMap fleet={fleet} onSelectAircraft={onSelectAircraft} />
          <PredictiveInsight fleet={fleet} />
          <div>
            <SectionLabel icon={LayoutGrid}>Aircraft Fleet</SectionLabel>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {fleet.map((ac) => (
                <Card key={ac.id} onClick={() => onSelectAircraft(ac.id)} className="group">
                  <div className="flex items-center gap-3">
                    <HealthGauge value={ac.overallHealth} size={64} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate font-mono text-sm font-semibold text-slate-100">{ac.tail}</span>
                        <StatusPill status={ac.status} />
                      </div>
                      <div className="mt-0.5 truncate text-xs text-slate-500">{ac.model}</div>
                      <div className="mt-2 flex items-center gap-3 text-[10px] text-slate-600">
                        <span>{ac.flightHours.toLocaleString()} hrs</span>
                        <span>•</span>
                        <span>{ac.components.filter(c=>c.risk==="High").length} high-risk</span>
                      </div>
                    </div>
                    <ChevronRight className="h-4 w-4 shrink-0 text-slate-600 transition group-hover:translate-x-0.5 group-hover:text-cyan-400" />
                  </div>
                </Card>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <SectionLabel icon={Target}>Priority Queue</SectionLabel>
            <Card>
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs text-slate-500">Lowest health first</span>
                <span className="font-mono text-[10px] text-cyan-400">{highestRisk.length} tracked</span>
              </div>
              <ul className="divide-y divide-slate-800">
                {highestRisk.map((ac, idx) => (
                  <li key={ac.id} onClick={() => onSelectAircraft(ac.id)} className="flex cursor-pointer items-center gap-3 py-3 first:pt-0 last:pb-0">
                    <span className="font-mono text-[10px] text-slate-700">0{idx+1}</span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-mono text-xs font-semibold text-slate-200">{ac.tail}</div>
                      <div className="mt-0.5 text-[10px] text-slate-500">{ac.model}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-sm font-bold" style={{color: healthColor(ac.overallHealth)}}>{ac.overallHealth}%</div>
                      <div className="text-[9px] uppercase text-slate-600">health</div>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          <div>
            <SectionLabel icon={Bell}>Critical Alerts</SectionLabel>
            <Card className={alerts.length ? "border-red-400/20" : ""}>
              {alerts.length === 0 ? (
                <div className="flex items-center gap-2 text-sm text-slate-500"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> No active high-risk alerts.</div>
              ) : (
                <ul className="space-y-3">
                  {alerts.map((a) => (
                    <li key={a.id} className="flex items-start gap-2.5">
                      <div className="mt-0.5 rounded-md bg-red-400/10 p-1"><AlertTriangle className="h-3 w-3 text-red-400" /></div>
                      <div className="text-xs text-slate-400">
                        <span className="font-mono font-semibold text-slate-100">{a.aircraft}</span>
                        <span className="text-slate-600"> · </span>{a.component}
                        <div className="mt-0.5"><span className="font-mono text-red-300">{a.rul}</span> cycles RUL · <span className="text-red-300">inspect</span></div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <Card className="bg-slate-900/40">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-300"><Database className="h-3.5 w-3.5 text-violet-400" /> System Telemetry</div>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div><div className="text-[9px] uppercase text-slate-600">Sensors</div><div className="font-mono text-sm text-slate-300">{allComponents.length * 4}</div></div>
              <div><div className="text-[9px] uppercase text-slate-600">Update rate</div><div className="font-mono text-sm text-slate-300">2.5s</div></div>
              <div><div className="text-[9px] uppercase text-slate-600">Prediction</div><div className="text-sm font-semibold text-emerald-300">Online</div></div>
              <div><div className="text-[9px] uppercase text-slate-600">Data mode</div><div className="text-sm font-semibold text-slate-300">Simulated</div></div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

/* ============================================================================
   VIEW: AIRCRAFT DETAIL
============================================================================ */

function AircraftDetail({ aircraft, onSelectComponent, onBack }) {
  const worstFailureProb = Math.max(...aircraft.components.map((c) => c.failureProbability));
  const worstRUL = Math.min(...aircraft.components.map((c) => c.rul));

  return (
    <div className="space-y-6">
      <button onClick={onBack} className="flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-300">
        <ChevronLeft className="h-3.5 w-3.5" /> Fleet Overview
      </button>

      <Card>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <HealthGauge value={aircraft.overallHealth} size={96} />
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-mono text-2xl font-bold text-slate-100">{aircraft.tail}</h2>
              <StatusPill status={aircraft.status} />
            </div>
            <p className="text-sm text-slate-500">{aircraft.model} &middot; {aircraft.flightHours.toLocaleString()} flight hours</p>
          </div>
          <div className="grid grid-cols-2 gap-4 sm:gap-8">
            <div>
              <div className="text-[11px] uppercase tracking-wide text-slate-500">Failure Probability</div>
              <div className="font-mono text-xl font-bold text-slate-100">{worstFailureProb}%</div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wide text-slate-500">Lowest RUL</div>
              <div className="font-mono text-xl font-bold text-slate-100">{worstRUL}<span className="text-xs text-slate-500"> cyc</span></div>
            </div>
          </div>
        </div>
      </Card>

      <Card className="border-slate-800/80 bg-slate-900/40">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Maintenance Readiness</div>
            <div className="mt-1 text-sm font-semibold text-slate-200">Component risk profile</div>
          </div>
          <div className="flex items-center gap-2 text-[10px] text-slate-500"><Layers3 className="h-3.5 w-3.5" /> {aircraft.components.length} subsystems</div>
        </div>
        <div className="mt-4 flex h-2 overflow-hidden rounded-full bg-slate-800">
          {aircraft.components.map(c => <div key={c.type} title={`${c.type}: ${c.risk}`} className={`${c.risk === "High" ? "bg-red-400" : c.risk === "Medium" ? "bg-amber-400" : "bg-emerald-400"} transition-all`} style={{width:`${100/aircraft.components.length}%`, opacity:0.9}} />)}
        </div>
        <div className="mt-2 flex flex-wrap gap-3 text-[10px] text-slate-500">
          <span><i className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-red-400" />High</span>
          <span><i className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-amber-400" />Medium</span>
          <span><i className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />Low</span>
        </div>
      </Card>

      <div>
        <SectionLabel icon={Wrench}>Component Status</SectionLabel>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {aircraft.components.map((c) => (
            <Card key={c.type} onClick={() => onSelectComponent(c.type)}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <c.icon className="h-4 w-4 text-slate-400" />
                  <span className="text-sm font-semibold text-slate-200">{c.type}</span>
                </div>
                <RiskBadge risk={c.risk} />
              </div>
              <div className="mt-3 flex items-end justify-between">
                <div>
                  <div className="text-[11px] text-slate-500">RUL</div>
                  <div className="font-mono text-lg font-bold text-slate-100">{c.rul} <span className="text-xs font-normal text-slate-500">cycles</span></div>
                </div>
                <div className="h-8 w-20"><MiniTrend data={c.healthTrend} color={healthColor(c.health)} height={32} /></div>
              </div>
            </Card>
          ))}
        </div>
      </div>

      <div>
        <SectionLabel icon={Activity}>Sensor Monitoring {"\u2014"} Snapshot</SectionLabel>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {aircraft.components.flatMap((c) =>
            c.sensors.slice(0, 1).map((s) => (
              <Card key={c.type + s.key}>
                <div className="text-[11px] text-slate-500">{c.type} {"\u00b7"} {s.label}</div>
                <div className="mt-1 flex items-baseline gap-1">
                  <span className="font-mono text-lg font-bold text-slate-100">{s.value}</span>
                  <span className="text-xs text-slate-500">{s.unit}</span>
                  <TrendArrow data={s.trend} />
                </div>
              </Card>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

/* ============================================================================
   VIEW: COMPONENT DETAIL (reused for every subsystem)
============================================================================ */

function ComponentDetail({ aircraft, component, onBack }) {
  const s = RISK_STYLES[component.risk];
  return (
    <div className="space-y-6">
      <button onClick={onBack} className="flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-300">
        <ChevronLeft className="h-3.5 w-3.5" /> {aircraft.tail}
      </button>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className={`flex h-11 w-11 items-center justify-center rounded-lg ${s.bg} ${s.border} border`}>
              <component.icon className={`h-5 w-5 ${s.text}`} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-100">{component.type}</h2>
              <p className="text-xs text-slate-500">{aircraft.tail} &middot; {aircraft.model}</p>
            </div>
          </div>
          <div className={`rounded-lg border px-3 py-2 text-right ${s.bg} ${s.border}`}>
            <div className="text-[10px] uppercase tracking-wide text-slate-500">Prediction Status</div>
            <div className={`text-sm font-bold ${s.text}`}>{component.recommendation}</div>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <div className="text-[11px] text-slate-500">Health Score</div>
            <div className="font-mono text-xl font-bold" style={{ color: healthColor(component.health) }}>{component.health}</div>
          </div>
          <div>
            <div className="text-[11px] text-slate-500">RUL (cycles)</div>
            <div className="font-mono text-xl font-bold text-slate-100">{component.rul}</div>
          </div>
          <div>
            <div className="text-[11px] text-slate-500">Failure Probability</div>
            <div className="font-mono text-xl font-bold text-slate-100">{component.failureProbability}%</div>
          </div>
          <div>
            <div className="text-[11px] text-slate-500">Risk / Priority</div>
            <RiskBadge risk={component.risk} />
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {component.sensors.map((sensor) => (
          <Card key={sensor.key}>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-sm font-semibold text-slate-200">
                <Thermometer className="h-3.5 w-3.5 text-slate-500" /> {sensor.label}
              </span>
              <span className="font-mono text-sm font-bold text-slate-100">{sensor.value} <span className="text-xs font-normal text-slate-500">{sensor.unit}</span></span>
            </div>
            <div className="mt-2 h-16">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={sensor.trend}>
                  <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="cycle" hide />
                  <YAxis hide domain={["dataMin - 5", "dataMax + 5"]} />
                  <Tooltip
                    contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 11 }}
                    labelFormatter={() => ""}
                  />
                  <Line type="monotone" dataKey="value" stroke="#22d3ee" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Card>
          <SectionLabel icon={Activity}>Health Trend</SectionLabel>
          <div className="h-36">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={component.healthTrend}>
                <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="cycle" tick={{ fontSize: 10, fill: "#64748b" }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#64748b" }} width={28} />
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 11 }} />
                <Line type="monotone" dataKey="value" stroke={healthColor(component.health)} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <SectionLabel icon={Gauge}>RUL Trend (cycles remaining)</SectionLabel>
          <div className="h-36">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={component.rulTrend}>
                <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="cycle" tick={{ fontSize: 10, fill: "#64748b" }} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} width={28} />
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 11 }} />
                <Line type="monotone" dataKey="value" stroke="#a78bfa" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </div>
  );
}

/* ============================================================================
   VIEW: MAINTENANCE CENTER
============================================================================ */

function MaintenanceCenter({ fleet, onSelectAircraft }) {
  const [filter, setFilter] = useState("All");
  const rows = useMemo(() => {
    const all = [];
    fleet.forEach((ac) => {
      ac.components.forEach((c) => {
        all.push({
          aircraftId: ac.id, tail: ac.tail, type: c.type, icon: c.icon,
          rul: c.rul, risk: c.risk, recommendation: c.recommendation, priority: c.priority,
        });
      });
    });
    const order = { High: 0, Medium: 1, Low: 2 };
    return all
      .filter((r) => filter === "All" || r.priority === filter)
      .sort((a, b) => order[a.priority] - order[b.priority] || a.rul - b.rul);
  }, [fleet, filter]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionLabel icon={ClipboardList}>Maintenance Center</SectionLabel>
        <div className="flex gap-1.5">
          {["All", "High", "Medium", "Low"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-md px-2.5 py-1 text-xs font-semibold transition ${
                filter === f ? "bg-cyan-400/15 text-cyan-300 ring-1 ring-cyan-400/40" : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-[11px] uppercase tracking-wide text-slate-500">
              <th className="px-4 py-3 font-medium">Aircraft</th>
              <th className="px-4 py-3 font-medium">Component</th>
              <th className="px-4 py-3 font-medium">RUL</th>
              <th className="px-4 py-3 font-medium">Risk</th>
              <th className="px-4 py-3 font-medium">Recommendation</th>
              <th className="px-4 py-3 font-medium">Priority</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr
                key={r.aircraftId + r.type}
                onClick={() => onSelectAircraft(r.aircraftId)}
                className={`cursor-pointer border-b border-slate-800/60 last:border-0 hover:bg-slate-800/40 ${i % 2 ? "bg-slate-900/30" : ""}`}
              >
                <td className="px-4 py-2.5 font-mono text-slate-300">{r.tail}</td>
                <td className="px-4 py-2.5">
                  <span className="flex items-center gap-1.5 text-slate-200">
                    <r.icon className="h-3.5 w-3.5 text-slate-500" /> {r.type}
                  </span>
                </td>
                <td className="px-4 py-2.5 font-mono text-slate-300">{r.rul} cyc</td>
                <td className="px-4 py-2.5"><RiskBadge risk={r.risk} /></td>
                <td className="px-4 py-2.5 text-slate-400">{r.recommendation}</td>
                <td className="px-4 py-2.5"><RiskBadge risk={r.priority} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

/* ============================================================================
   ROOT APP
============================================================================ */

export default function App() {
  const [fleet, setFleet] = useState(() => generateFleet());
  const [view, setView] = useState("fleet"); // fleet | aircraft | component | maintenance
  const [selectedAircraftId, setSelectedAircraftId] = useState(null);
  const [selectedComponentType, setSelectedComponentType] = useState(null);
  const [connected, setConnected] = useState(true);
  const [lastSync, setLastSync] = useState(new Date());

  useLiveTelemetry(setFleet, connected);
  useEffect(() => {
    if (!connected) return;
    const id = setInterval(() => setLastSync(new Date()), 2500);
    return () => clearInterval(id);
  }, [connected]);

  const selectedAircraft = useMemo(
    () => fleet.find((a) => a.id === selectedAircraftId) || null,
    [fleet, selectedAircraftId]
  );
  const selectedComponent = useMemo(
    () => selectedAircraft?.components.find((c) => c.type === selectedComponentType) || null,
    [selectedAircraft, selectedComponentType]
  );

  const goAircraft = useCallback((id) => { setSelectedAircraftId(id); setView("aircraft"); }, []);
  const goComponent = useCallback((type) => { setSelectedComponentType(type); setView("component"); }, []);

  const navItems = [
    { key: "fleet", label: "Fleet", icon: LayoutGrid },
    { key: "maintenance", label: "Maintenance", icon: ClipboardList },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans">
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/90 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-400/10 ring-1 ring-cyan-400/30">
              <Plane className="h-4 w-4 text-cyan-400" />
            </div>
            <div>
              <div className="text-sm font-bold leading-tight text-slate-100">AeroPredict</div>
              <div className="text-[10px] leading-tight text-slate-500">Predictive Maintenance Console</div>
            </div>
          </div>

          <nav className="hidden items-center gap-1 sm:flex">
            {navItems.map((n) => (
              <button
                key={n.key}
                onClick={() => { setView(n.key); }}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition ${
                  view === n.key || (n.key === "fleet" && (view === "aircraft" || view === "component"))
                    ? "bg-slate-800 text-slate-100"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                <n.icon className="h-3.5 w-3.5" /> {n.label}
              </button>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setConnected((v) => !v)}
              className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium text-slate-500 hover:text-slate-300"
              title="Toggle live telemetry (simulated WebSocket)"
            >
              {connected ? <Wifi className="h-3.5 w-3.5 text-emerald-400" /> : <WifiOff className="h-3.5 w-3.5 text-slate-600" />}
              <span className="hidden md:inline">{connected ? "Live" : "Paused"}</span>
            </button>
            <button
              onClick={() => setFleet(generateFleet())}
              className="flex items-center gap-1.5 rounded-md bg-slate-800 px-2.5 py-1.5 text-[11px] font-medium text-slate-300 hover:bg-slate-700"
              title="Re-fetch fleet (GET /api/fleet)"
            >
              <RefreshCw className="h-3.5 w-3.5" /> <span className="hidden md:inline">Sync</span>
            </button>
          </div>
        </div>
        <div className="flex sm:hidden border-t border-slate-800">
          {navItems.map((n) => (
            <button
              key={n.key}
              onClick={() => setView(n.key)}
              className={`flex flex-1 items-center justify-center gap-1.5 py-2 text-xs font-semibold ${
                view === n.key ? "text-cyan-400" : "text-slate-500"
              }`}
            >
              <n.icon className="h-3.5 w-3.5" /> {n.label}
            </button>
          ))}
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        {view === "fleet" && (
          <FleetDashboard fleet={fleet} onSelectAircraft={goAircraft} connected={connected} />
        )}
        {view === "aircraft" && selectedAircraft && (
          <AircraftDetail
            aircraft={selectedAircraft}
            onSelectComponent={goComponent}
            onBack={() => setView("fleet")}
          />
        )}
        {view === "component" && selectedAircraft && selectedComponent && (
          <ComponentDetail
            aircraft={selectedAircraft}
            component={selectedComponent}
            onBack={() => setView("aircraft")}
          />
        )}
        {view === "maintenance" && (
          <MaintenanceCenter fleet={fleet} onSelectAircraft={goAircraft} />
        )}
      </main>

      <footer className="mx-auto max-w-7xl px-4 pb-6 text-center text-[11px] text-slate-600 sm:px-6">
        AeroPredict simulation &middot; last sync {lastSync.toLocaleTimeString()} &middot; REST + WebSocket integration ready
      </footer>
    </div>
  );
}
