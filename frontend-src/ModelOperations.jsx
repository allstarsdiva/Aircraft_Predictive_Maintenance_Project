import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, ClipboardList, Download, Loader2, RefreshCw, ShieldAlert, Plane, Activity, CircleHelp } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { createSectionResultsFile } from './sectionResults.js';

const SYSTEMS = [
  { key: 'engine', title: 'Engine', endpoint: '/api/v2/predict/engine' },
  { key: 'battery', title: 'Electrical / Battery', endpoint: '/api/v2/predict/battery' },
  { key: 'hydraulic', title: 'Hydraulic', endpoint: '/api/v2/predict/hydraulic' },
  { key: 'landing-gear', title: 'Landing gear', endpoint: '/api/v2/predict/landing-gear' },
  { key: 'fuel-system', title: 'Fuel system', endpoint: '/api/predict/fuel-system' },
];
const number = value => typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 3 }) : String(value ?? 'Unavailable');

async function getJson(path, options = {}) {
  const response = await fetch(path, options);
  let body;
  try { body = await response.json(); } catch { throw new Error('The backend returned a non-JSON response.'); }
  if (!response.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : 'The backend could not complete this model request.');
  return body;
}

function outputSummary(key, data) {
  if (key === 'engine') return `Estimated remaining useful life: ${number(data.rul?.value)} ${data.rul?.unit || 'cycles'}`;
  if (key === 'battery') return `Estimated SOH: ${number(data.soh?.value)}%; RUL: ${number(data.rul?.value)} ${data.rul?.unit || 'cycles'}`;
  if (key === 'hydraulic') return Object.entries(data.predictions || {}).map(([name, result]) => `${name.replaceAll('_', ' ')}: ${result.label ?? result.value}`).join(' / ');
  if (key === 'landing-gear') return `Fault model output: ${data.fault?.label ?? data.fault?.value}; RUL estimate: ${number(data.rul?.value)} ${data.rul?.unit || 'percent'}`;
  return `${data.latest_is_abnormal ? 'Latest sample flagged' : 'No alert on latest sample'}; ${data.flagged_samples} of ${data.input_samples} samples flagged`;
}

function acceptance(data) {
  if (data.soh && typeof data.soh.accepted === 'boolean') return data.soh.accepted && data.rul?.accepted !== false;
  if (data.fault && typeof data.fault.accepted === 'boolean') return data.fault.accepted && data.rul?.accepted !== false;
  if (data.rul && typeof data.rul.accepted === 'boolean') return data.rul.accepted;
  const checks = Object.values(data.predictions || {}).filter(item => typeof item.accepted === 'boolean');
  return checks.length ? checks.every(item => item.accepted) : null;
}

function modelName(data) { return data.model || data.rul_model || data.fault_model || data.soh_model || 'Saved subsystem model'; }

function IntervalGraphic({ title, result }) {
  if (!result || typeof result.value !== 'number') return null;
  const low = typeof result.lower === 'number' ? result.lower : result.value;
  const high = typeof result.upper === 'number' ? result.upper : result.value;
  const scale = Math.max(Math.abs(low), Math.abs(high), Math.abs(result.value), 1) * 1.08;
  const left = Math.max(0, Math.min(100, (Math.min(low, high) / scale) * 100));
  const width = Math.max(1, Math.min(100 - left, (Math.abs(high - low) / scale) * 100));
  const point = Math.max(0, Math.min(100, (result.value / scale) * 100));
  return <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
    <div className="flex items-baseline justify-between gap-2"><span className="text-[11px] font-semibold text-slate-300">{title}</span><span className="text-xs font-bold text-cyan-200">{number(result.value)} {result.unit}</span></div>
    <div className="relative mt-3 h-3 rounded-full bg-slate-800" aria-label={`${title}: ${number(result.value)} ${result.unit}; interval ${number(low)} to ${number(high)}`}>
      <div className="absolute top-0 h-3 rounded-full bg-cyan-400/50" style={{ left: `${left}%`, width: `${width}%` }} />
      <span className="absolute -top-1 h-5 w-1 rounded bg-white" style={{ left: `calc(${point}% - 2px)` }} />
    </div>
    <div className="mt-2 flex justify-between text-[9px] text-slate-500"><span>Lower {number(low)}</span><span>Upper {number(high)} {result.unit}</span></div>
  </div>;
}

function inputTrace(item) {
  const payload = item.example?.payload || {};
  if (item.system.key === 'engine' && Array.isArray(payload.records)) {
    return { title: 'Engine input trace - sensor_2', xLabel: 'Cycle', leftLabel: 'sensor_2', rows: payload.records.map((row, i) => ({ step: Number(row.cycle ?? i + 1), a: Number(row.sensor_2) })).filter(row => Number.isFinite(row.a)), leftName: 'sensor_2' };
  }
  if (item.system.key === 'battery' && Array.isArray(payload.samples)) {
    return { title: 'Battery sample input trace', xLabel: 'Sample time', leftLabel: 'Voltage (V)', rightLabel: 'Temperature', rows: payload.samples.map((row, i) => ({ step: Number(row.time ?? i), a: Number(row.voltage_measured), b: Number(row.temperature_measured) })).filter(row => Number.isFinite(row.a) && Number.isFinite(row.b)), leftName: 'Voltage', rightName: 'Temperature' };
  }
  if (item.system.key === 'fuel-system' && Array.isArray(payload.samples)) {
    const source = payload.samples;
    const stride = Math.max(1, Math.ceil(source.length / 180));
    const rows = source.flatMap((row, index) => index % stride === 0 || index === source.length - 1 ? [{ step: index, a: Number(row.FTL), b: Number(row.FTF) }] : []).filter(row => Number.isFinite(row.a) && Number.isFinite(row.b));
    return { title: `Fuel input trace - FTL and FTF (display ${rows.length} of ${source.length} samples)`, xLabel: 'Sample index', leftLabel: 'FTL', rightLabel: 'FTF', rows, leftName: 'FTL', rightName: 'FTF' };
  }
  return null;
}

function InputTrace({ item }) {
  const trace = inputTrace(item);
  if (!trace?.rows.length) return null;
  return <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
    <div className="mb-2 flex flex-wrap items-center justify-between gap-2"><span className="text-[11px] font-semibold text-slate-300">{trace.title}</span><span className="text-[9px] text-slate-500">Dataset input, not a live sensor stream</span></div>
    <div className="h-40 w-full">
      <ResponsiveContainer width="100%" height="100%"><LineChart data={trace.rows} margin={{ top: 5, right: 4, bottom: 0, left: -18 }}>
        <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="step" tick={{ fill: '#64748b', fontSize: 9 }} tickLine={false} axisLine={{ stroke: '#334155' }} label={{ value: trace.xLabel, position: 'insideBottomRight', offset: -2, fill: '#64748b', fontSize: 9 }} />
        <YAxis yAxisId="left" tick={{ fill: '#64748b', fontSize: 9 }} tickLine={false} axisLine={false} width={38} />
        {trace.rightName && <YAxis yAxisId="right" orientation="right" tick={{ fill: '#64748b', fontSize: 9 }} tickLine={false} axisLine={false} width={36} />}
        <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 10 }} labelFormatter={value => `${trace.xLabel}: ${value}`} />
        <Line yAxisId="left" type="monotone" dataKey="a" name={trace.leftName} stroke="#22d3ee" strokeWidth={2} dot={false} isAnimationActive={false} />
        {trace.rightName && <Line yAxisId="right" type="monotone" dataKey="b" name={trace.rightName} stroke="#a78bfa" strokeWidth={2} dot={false} isAnimationActive={false} />}
      </LineChart></ResponsiveContainer>
    </div>
    <div className="mt-1 flex gap-4 text-[9px] text-slate-500"><span className="text-cyan-300">{trace.leftLabel}</span>{trace.rightLabel && <span className="text-violet-300">{trace.rightLabel}</span>}</div>
  </div>;
}

function ConfidenceGraphic({ title, rows, note }) {
  const valid = rows.filter(row => typeof row.confidence === 'number');
  if (!valid.length) return null;
  return <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
    <div className="text-[11px] font-semibold text-slate-300">{title}</div>
    <div className="mt-3 space-y-3">{valid.map(row => <div key={row.name}>
      <div className="mb-1 flex items-center justify-between gap-2 text-[10px]"><span className="capitalize text-slate-400">{row.name.replaceAll('_', ' ')}: {row.label}</span><span className="text-slate-300">{number(row.confidence * 100)}%</span></div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-800"><div className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-violet-400" style={{ width: `${Math.max(0, Math.min(100, row.confidence * 100))}%` }} /></div>
    </div>)}</div>
    <p className="mt-3 text-[9px] leading-4 text-slate-500">{note}</p>
  </div>;
}

function OutputVisualization({ item }) {
  const { system, result } = item;
  if (!result) return null;
  if (system.key === 'engine') return <div className="mt-4 space-y-3"><IntervalGraphic title="Engine RUL estimate and interval" result={result.rul} /><InputTrace item={item} /></div>;
  if (system.key === 'battery') return <div className="mt-4 space-y-3"><IntervalGraphic title="Battery SOH estimate and interval" result={result.soh} /><IntervalGraphic title="Battery RUL estimate and interval" result={result.rul} /><InputTrace item={item} /></div>;
  if (system.key === 'hydraulic') return <div className="mt-4"><ConfidenceGraphic title="Hydraulic model confidence by output" rows={Object.entries(result.predictions || {}).map(([name, value]) => ({ name, label: value.label ?? `class ${value.value}`, confidence: value.calibrated_confidence }))} note="Bars show the returned confidence estimates; class codes are labels, not a severity scale. Unaccepted outputs require review." /></div>;
  if (system.key === 'landing-gear') return <div className="mt-4 space-y-3"><ConfidenceGraphic title="Landing-gear fault classification confidence" rows={[{ name: 'fault', label: result.fault?.label ?? `class ${result.fault?.value}`, confidence: result.fault?.calibrated_confidence }]} note="Confidence belongs to the dataset-trained classifier; it is not an aircraft safety probability." /><IntervalGraphic title="Landing-gear RUL estimate and interval" result={result.rul} /></div>;
  const flagged = Math.max(0, Math.min(result.input_samples, result.flagged_samples));
  const fuelBars = [{ name: 'Flagged', samples: flagged }, { name: 'Not flagged', samples: Math.max(0, result.input_samples - flagged) }];
  return <div className="mt-4 space-y-3">
    <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3"><div className="mb-2 text-[11px] font-semibold text-slate-300">Fuel detector output counts</div><div className="h-32"><ResponsiveContainer width="100%" height="100%"><BarChart data={fuelBars} margin={{ top: 4, right: 8, bottom: 0, left: -15 }}><CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 9 }} tickLine={false} axisLine={{ stroke: '#334155' }} /><YAxis allowDecimals={false} tick={{ fill: '#64748b', fontSize: 9 }} tickLine={false} axisLine={false} /><Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 10 }} /><Bar dataKey="samples" name="Samples" fill="#fb7185" radius={[5, 5, 0, 0]} isAnimationActive={false} /></BarChart></ResponsiveContainer></div><p className="mt-1 text-[9px] text-slate-500">Counts are from the detector response; the API does not return per-sample alert positions.</p></div>
    <InputTrace item={item} />
  </div>;
}

function ResultCard({ item, maintenance = false }) {
  const { system, example, result, error } = item;
  const accepted = result ? acceptance(result) : null;
  const experimental = system.key === 'fuel-system';
  const needsReview = experimental || accepted === false;
  const status = error ? 'Model unavailable' : experimental ? 'Experimental - review required' : accepted === false ? 'Model requested review' : accepted === true ? 'Input passed model checks' : 'Review model output';
  return <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
    <div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-semibold text-slate-100">{system.title}</h3><p className="mt-1 text-[11px] text-slate-500">Dataset example: {example?.source || 'not available'}</p></div>
      <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold ${error || needsReview ? 'border-amber-400/30 bg-amber-400/10 text-amber-200' : 'border-cyan-400/25 bg-cyan-400/10 text-cyan-200'}`}>{status}</span></div>
    {error ? <p className="mt-3 text-xs text-amber-200">{error}</p> : result ? <>
      <p className="mt-3 text-sm leading-6 text-slate-200">{outputSummary(system.key, result)}</p>
      <div className="model-output-graphic"><OutputVisualization item={item} /></div>
      <p className="mt-2 break-words text-[10px] text-slate-500">Model: {modelName(result)}</p>
      {result.warnings?.length > 0 && <details className="mt-3 text-xs text-slate-400"><summary className="cursor-pointer">Model limitations and warnings</summary><ul className="mt-2 list-disc space-y-1 pl-5">{result.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></details>}
      {maintenance && <ModelInputDetails item={item} />}
    </> : <p className="mt-3 text-xs text-slate-500">Waiting for a backend response.</p>}
  </article>;
}

const displayName = value => String(value).replaceAll('_', ' ');
const displayValue = value => typeof value === 'number'
  ? value.toLocaleString(undefined, { maximumFractionDigits: 5 })
  : typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value ?? '—');

function modelInputGroups(item) {
  const payload = item.example?.payload || {};
  const key = item.system.key;
  if (key === 'engine') {
    const rows = payload.records || [];
    return [{ title: 'Engine cycle and sensor inputs', note: `${rows.length} ordered cycles · ${Object.keys(rows.at(-1) || {}).length} fields in the latest cycle`, values: rows.at(-1) || {} }];
  }
  if (key === 'battery') {
    const samples = payload.samples || [];
    return [
      { title: 'Battery and discharge context', values: { battery_id: payload.battery_id, discharge_cycle: payload.discharge_cycle, ambient_temperature: payload.ambient_temperature, samples_in_cycle: samples.length } },
      { title: 'Measured electrical/thermal signals · last sample', note: 'Full ordered sample sequence is sent to the model.', values: samples.at(-1) || {} },
    ];
  }
  if (key === 'hydraulic') return [
    { title: 'Cycle context', values: { cycle_id: payload.cycle_id, operating_condition_stable: payload.operating_condition_stable } },
    { title: 'Hydraulic sensor-derived model features', note: `${Object.keys(payload.features || {}).length} measured/engineered inputs`, values: payload.features || {} },
  ];
  if (key === 'landing-gear') return [{ title: 'Landing-event observable inputs', values: payload }];
  const samples = payload.samples || [];
  return [{ title: 'Fuel-system sensor features · last sample', note: `${samples.length} ordered samples · full trajectory is sent to the model.`, values: samples.at(-1) || {} }];
}

function importanceGroups(item) {
  const result = item.result || {};
  const key = item.system.key;
  if (key === 'engine') return [{ title: 'Engine RUL model · global feature importance', rows: result.rul?.top_model_features || [] }];
  if (key === 'battery') return [
    { title: 'Battery SOH model · global feature importance', rows: result.soh?.top_model_features || [] },
    { title: 'Battery RUL model · global feature importance', rows: result.rul?.top_model_features || [] },
  ];
  if (key === 'hydraulic') return Object.entries(result.predictions || {}).map(([target, prediction]) => ({ title: `${displayName(target)} model · global feature importance`, rows: prediction.top_model_features || [] }));
  if (key === 'landing-gear') return [
    { title: 'Landing-gear fault model · global feature importance', rows: result.fault?.top_model_features || [] },
    { title: 'Landing-gear RUL model · global feature importance', rows: result.rul?.top_model_features || [] },
  ];
  return [{ title: 'Fuel detector · largest deviations from its normal envelope', rows: (result.largest_normal_envelope_deviations || []).map(row => ({ feature: row.feature, relative_importance: row.scaled_deviation, value: row.scaled_deviation })) }];
}

function ModelInputDetails({ item }) {
  const inputs = modelInputGroups(item);
  const importance = importanceGroups(item).filter(group => group.rows.length);
  return <details className="model-input-details mt-4 overflow-hidden rounded-lg border border-slate-800 bg-slate-950/50 text-xs text-slate-300">
    <summary className="cursor-pointer list-none px-3 py-3 font-semibold text-cyan-100 marker:hidden">
      <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded bg-cyan-400/10 text-cyan-200">+</span>
      View component inputs, sub-parts & model features
    </summary>
    <div className="space-y-4 border-t border-slate-800 p-3">
      <div><h4 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">Data sent to the model</h4>
        <div className="grid gap-3 xl:grid-cols-2">{inputs.map(group => <section key={group.title} className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
          <h5 className="text-[11px] font-semibold capitalize text-slate-200">{group.title}</h5>{group.note && <p className="mt-1 text-[10px] text-slate-500">{group.note}</p>}
          <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-1.5 sm:grid-cols-2">{Object.entries(group.values).map(([name, value]) => <div key={name} className="flex min-w-0 items-baseline justify-between gap-2 border-b border-slate-800/70 py-1"><dt className="truncate text-[10px] capitalize text-slate-500" title={name}>{displayName(name)}</dt><dd className="break-all text-right font-mono text-[10px] text-slate-200">{displayValue(value)}</dd></div>)}</dl>
        </section>)}</div>
      </div>
      <div><h4 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">Model features and sub-models</h4>
        {importance.length ? <div className="grid gap-3 xl:grid-cols-2">{importance.map(group => <section key={group.title} className="rounded-lg border border-slate-800 bg-slate-900/70 p-3"><h5 className="text-[11px] font-semibold capitalize text-slate-200">{group.title}</h5><ul className="mt-2 space-y-2">{group.rows.map(row => <li key={row.feature} className="grid grid-cols-[minmax(0,1fr)_minmax(4rem,1fr)_3.5rem] items-center gap-2 text-[10px]"><span className="truncate capitalize text-slate-400" title={row.feature}>{displayName(row.feature)}</span><span className="h-1.5 overflow-hidden rounded-full bg-slate-800"><i className="block h-full rounded-full bg-gradient-to-r from-cyan-500 to-violet-400" style={{ width: `${Math.max(2, Math.min(100, Number(row.relative_importance) || 0))}%` }} /></span><strong className="text-right text-slate-300">{number(row.relative_importance)}{item.system.key === 'fuel-system' ? ' score' : '%'}</strong></li>)}</ul></section>)}</div>
          : <p className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-[10px] leading-5 text-slate-500">This endpoint does not return feature-importance values. The input fields above are the data provided to its detector; they are not ranked causes.</p>}
        <p className="mt-2 text-[10px] leading-4 text-slate-500">For the predictive models, importance is global model-level importance, not a case-specific explanation. Fuel scores are envelope deviations, not feature-importance percentages.</p>
      </div>
    </div>
  </details>;
}

function triage(item) {
  if (!item.result) return { level: 'Unavailable', reason: item.error || 'No model response.' };
  const data = item.result;
  if (item.system.key === 'fuel-system' && (data.latest_is_abnormal || data.flagged_samples > 0))
    return { level: 'Critical', reason: `${data.flagged_samples} of ${data.input_samples} example samples were flagged; this experimental detector needs engineering review.` };
  if (item.system.key === 'landing-gear' && data.fault?.value > 0)
    return { level: 'Critical', reason: `Model flagged ${data.fault.label || `fault class ${data.fault.value}`} in this synthetic landing-event example.` };
  const results = item.system.key === 'hydraulic' ? Object.values(data.predictions || {}) : [data.rul, data.soh, data.fault].filter(Boolean);
  if (results.some(result => result?.accepted === false || result?.input_support?.abstain))
    return { level: 'Caution', reason: 'At least one output was not accepted by its model gate; it is marked for review, not diagnosed as faulty.' };
  if (results.some(result => result?.input_support?.tail_range_warnings?.length))
    return { level: 'Caution', reason: 'Input includes values near/outside a model’s well-supported range; review the result.' };
  return { level: 'Monitor', reason: 'No model alert was returned for this example. This is not a maintenance clearance.' };
}

function downloadSectionResults(section, variant, items) {
  const report = createSectionResultsFile({
    section,
    variant,
    entries: items.map(item => {
      const status = triage(item);
      return {
        component: item.system.key,
        title: item.system.title,
        level: status.level,
        reason: status.reason,
        source: item.example?.source,
        model: item.result ? modelName(item.result) : null,
        summary: item.result ? outputSummary(item.system.key, item.result) : null,
        prediction: item.result || null,
        referenceLabels: item.example?.actual || null,
        error: item.error || null,
      };
    }),
  });
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = section + '-results-' + report.created_at_utc.slice(0, 10) + '.json';
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function SummaryTile({ label, value, note, tone = 'slate' }) {
  const palette = tone === 'amber' ? 'text-amber-200' : tone === 'rose' ? 'text-rose-200' : 'text-slate-100';
  return <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"><p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p><p className={`mt-1 text-2xl font-bold ${palette}`}>{value}</p><p className="mt-1 text-[10px] leading-4 text-slate-500">{note}</p></div>;
}

function FleetOverview({ items, loading, refresh, downloadResults, history, historyLoading, historyError, onOutcomeSaved }) {
  const [assetFilter, setAssetFilter] = useState('');
  const [savingOutcomeId, setSavingOutcomeId] = useState('');
  const [outcomeError, setOutcomeError] = useState('');
  const ready = items.filter(item => item.result).length;
  const filteredHistory = history.filter(entry => !assetFilter.trim()
    || (entry.asset_id || '').toLowerCase().includes(assetFilter.trim().toLowerCase()));
  const counts = ['Critical', 'Caution', 'Monitor', 'Unavailable'].map(level => ({
    name: level, systems: items.filter(item => triage(item).level === level).length,
  }));
  const downloadHistory = () => {
    const report = { schema: 'aircraft-prediction-history-export/v1', exported_at_utc: new Date().toISOString(), entries: history };
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = `prediction-history-${report.exported_at_utc.slice(0, 10)}.json`; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <div className="space-y-5">
    <header className="rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-900 to-cyan-950/30 p-5"><div className="flex flex-wrap items-start justify-between gap-4">
      <div><p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-300"><Plane size={14} /> Fleet health</p><h1 className="mt-2 text-2xl font-bold text-white">Fleet health overview</h1><p className="mt-2 max-w-3xl text-xs leading-5 text-slate-400">High-level status of the connected project services and subsystem model coverage. This project currently has no aircraft registry or live fleet telemetry feed connected.</p></div>
      <div className="flex flex-wrap gap-2"><button type="button" onClick={downloadResults} disabled={loading || items.length === 0} className="inline-flex items-center gap-2 rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-100 hover:border-cyan-300 disabled:opacity-50"><Download size={14} /> Download Fleet results (.json)</button>
      <button type="button" onClick={refresh} disabled={loading} className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-xs font-semibold text-slate-200 hover:border-cyan-400/50 disabled:opacity-50"><RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh snapshot</button></div>
    </div></header>
    <div role="note" className="flex items-start gap-2 rounded-xl border border-amber-400/25 bg-amber-400/5 px-4 py-3 text-xs leading-5 text-amber-100"><CircleHelp size={15} className="mt-0.5 shrink-0" /> Aircraft count and real fleet health are unavailable until aircraft records and telemetry are integrated. The subsystem counts below are backend model checks on labeled dataset examples, not aircraft counts.</div>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <SummaryTile label="Aircraft connected" value="0" note="No fleet/telemetry source integrated" />
      <SummaryTile label="Subsystem models responding" value={`${ready} / ${SYSTEMS.length}`} note="Live calls to saved model endpoints" />
      <SummaryTile label="Model checks for review" value={items.filter(item => ['Critical', 'Caution'].includes(triage(item).level)).length} note="Dataset examples only; see Maintenance" tone="amber" />
      <SummaryTile label="Fleet health status" value="Not available" note="No aircraft-level health records" />
    </div>
    <section className="grid gap-4 lg:grid-cols-[1.1fr_1.9fr]">
      <article className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"><div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-100"><Activity size={15} className="text-cyan-300" /> Model-check distribution</div><p className="mb-2 text-[10px] text-slate-500">Status grouping of the sample responses; not fleet condition.</p><div className="h-48"><ResponsiveContainer width="100%" height="100%"><BarChart data={counts} margin={{ top: 8, right: 4, bottom: 0, left: -20 }}><CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 9 }} tickLine={false} axisLine={{ stroke: '#334155' }} /><YAxis allowDecimals={false} tick={{ fill: '#64748b', fontSize: 9 }} tickLine={false} axisLine={false} /><Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 10 }} /><Bar dataKey="systems" name="Subsystem examples" fill="#22d3ee" radius={[5, 5, 0, 0]} isAnimationActive={false} /></BarChart></ResponsiveContainer></div></article>
      <article className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"><h2 className="text-sm font-semibold text-slate-100">Subsystem service coverage</h2><p className="mt-1 text-[10px] text-slate-500">One representative dataset example per available trained subsystem model.</p><div className="mt-3 divide-y divide-slate-800">{items.map(item => <div key={item.system.key} className="flex flex-wrap items-center justify-between gap-2 py-3"><div><p className="text-xs font-semibold text-slate-200">{item.system.title}</p><p className="mt-0.5 text-[10px] text-slate-500">{item.example?.source || (item.error ? 'Backend unavailable' : 'Loading source…')}</p></div><span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold ${item.result ? 'border-cyan-400/25 bg-cyan-400/10 text-cyan-200' : 'border-rose-400/25 bg-rose-400/10 text-rose-200'}`}>{item.result ? 'Model responding' : 'Unavailable'}</span></div>)}</div></article>
    </section>
    {loading && <div className="flex items-center gap-3 rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-4 text-sm text-cyan-100"><Loader2 size={18} className="animate-spin" /> Checking backend model coverage…</div>}
    <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4" aria-labelledby="prediction-history-title">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 id="prediction-history-title" className="text-sm font-semibold text-slate-100">Recent submitted prediction runs</h2><p className="mt-1 text-[10px] leading-4 text-slate-500">User-run results saved from AI Predictions. The example-based snapshot above is kept separate.</p></div>
        <div className="flex flex-wrap items-center gap-2"><input aria-label="Filter history by project asset ID" value={assetFilter} onChange={event => setAssetFilter(event.target.value)} placeholder="Filter project asset ID" className="rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-[11px] text-slate-200 placeholder:text-slate-600" />
          <button type="button" onClick={downloadHistory} disabled={!history.length || historyLoading} className="rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-[11px] font-semibold text-cyan-100 disabled:opacity-50">Download history (.json)</button></div></div>
      {historyLoading && <p className="mt-4 flex items-center gap-2 text-xs text-cyan-100"><Loader2 size={15} className="animate-spin" /> Loading saved prediction history…</p>}
      {historyError && <p className="mt-4 rounded-lg border border-amber-400/25 bg-amber-400/5 p-3 text-xs leading-5 text-amber-100" role="alert">{historyError}</p>}
      {!historyLoading && !historyError && history.length === 0 && <p className="mt-4 rounded-lg border border-slate-800 bg-slate-950/50 p-4 text-xs leading-5 text-slate-400">No submitted prediction runs saved yet. Run a prediction in AI Predictions to add it here. Example-based checks are not added to this history.</p>}
      {!historyLoading && !historyError && history.length > 0 && filteredHistory.length === 0 && <p className="mt-4 text-xs text-slate-500">No saved runs match that project asset ID.</p>}
      {!historyLoading && !historyError && filteredHistory.length > 0 && <div className="mt-4 space-y-2">{filteredHistory.map(entry => {
        const when = new Date(entry.created_at_utc);
        const dateText = Number.isNaN(when.getTime()) ? entry.created_at_utc : when.toLocaleString();
        const sourceText = entry.source === 'dataset_example' ? 'Dataset example' : entry.source === 'uploaded_file' ? 'Uploaded file' : entry.source === 'all_components_bundle' ? 'All-components bundle' : 'Edited request';
        return <article key={entry.id} className="grid gap-2 rounded-lg border border-slate-800 bg-slate-950/50 p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
          <div className="min-w-0"><div className="flex flex-wrap items-center gap-x-2 gap-y-1"><strong className="text-xs capitalize text-slate-100">{entry.component.replaceAll('-', ' ')}</strong><span className="text-[10px] text-slate-500">{dateText}</span></div>
            <p className="mt-1 text-xs text-slate-300">{entry.summary}</p><p className="mt-1 text-[10px] text-slate-500">{entry.asset_id ? `Asset ${entry.asset_id}` : 'Unassigned asset'} · {sourceText}</p></div>
          <div className="flex flex-col items-start gap-2 sm:items-end">
            <span className={`w-fit rounded-full border px-2.5 py-1 text-[10px] font-semibold ${entry.review_required ? 'border-amber-400/25 bg-amber-400/5 text-amber-200' : 'border-emerald-400/25 bg-emerald-400/5 text-emerald-200'}`}>{entry.review_required ? 'Review required' : 'Model checks passed'}</span>
            <label className="flex items-center gap-2 text-[10px] text-slate-500">
              <span>Inspection outcome</span>
              <select aria-label={`Inspection outcome for ${entry.component} prediction`} value={entry.outcome_status || 'unreviewed'} disabled={savingOutcomeId === entry.id}
                onChange={async event => {
                  const outcome_status = event.target.value;
                  setSavingOutcomeId(entry.id); setOutcomeError('');
                  try {
                    const updated = await getJson(`/api/prediction-history/${encodeURIComponent(entry.id)}/outcome`, {
                      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ outcome_status }),
                    });
                    onOutcomeSaved(updated);
                  } catch (error) { setOutcomeError(error.message || 'Could not save inspection outcome.'); }
                  finally { setSavingOutcomeId(''); }
                }}
                className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-[10px] text-slate-200 disabled:opacity-50">
                <option value="unreviewed" disabled>Not reviewed</option>
                <option value="confirmed_fault">Confirmed fault</option>
                <option value="no_fault_found">No fault found</option>
                <option value="inconclusive">Inconclusive</option>
              </select>
            </label>
          </div>
        </article>;
      })}</div>}
      {outcomeError && <p className="mt-3 rounded-lg border border-rose-400/25 bg-rose-400/5 p-3 text-xs text-rose-100" role="alert">{outcomeError}</p>}
      <p className="mt-3 text-[10px] leading-4 text-slate-600">History stores result summaries and an input digest only; it does not store raw sensor values. “Model checks passed” is not maintenance clearance.</p>
    </section>
    <p className="text-[11px] leading-5 text-slate-500">To show actual fleet health here, the next integration needs aircraft IDs, assigned component records, timestamped telemetry/predictions, and validated condition limits. Model output alone is not operational clearance.</p>
    <div className="flex justify-end border-t border-slate-800 pt-4"><button type="button" onClick={downloadResults} disabled={loading || items.length === 0} className="inline-flex items-center gap-2 rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-100 hover:border-cyan-300 disabled:opacity-50"><Download size={14} /> Download Fleet results (.json)</button></div>
  </div>;
}

function MaintenanceReview({ items, loading, refresh, downloadResults }) {
  const order = ['Critical', 'Caution', 'Monitor', 'Unavailable'];
  const grouped = order.map(level => ({ level, rows: items.filter(item => triage(item).level === level) }));
  const summary = {
    Critical: grouped.find(group => group.level === 'Critical').rows.length,
    Caution: grouped.find(group => group.level === 'Caution').rows.length,
    Monitor: grouped.find(group => group.level === 'Monitor').rows.length,
    Unavailable: grouped.find(group => group.level === 'Unavailable').rows.length,
  };
  return <div className="space-y-5">
    <header className="rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-900 to-amber-950/20 p-5"><div className="flex flex-wrap items-start justify-between gap-4">
      <div><p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-amber-200"><ClipboardList size={14} /> Maintenance review</p><h1 className="mt-2 text-2xl font-bold text-white">Component attention levels</h1><p className="mt-2 max-w-3xl text-xs leading-5 text-slate-400">Review per-component outputs grouped by model evidence. Critical means a model produced a positive fault/anomaly result; caution means a model gate or input-support warning requires review.</p></div>
      <div className="flex flex-wrap gap-2"><button type="button" onClick={downloadResults} disabled={loading || items.length === 0} className="inline-flex items-center gap-2 rounded-lg border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-xs font-semibold text-amber-100 hover:border-amber-200 disabled:opacity-50"><Download size={14} /> Download Maintenance results (.json)</button>
      <button type="button" onClick={refresh} disabled={loading} className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-xs font-semibold text-slate-200 hover:border-amber-300/50 disabled:opacity-50"><RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Recheck components</button></div>
    </div></header>
    <div role="note" className="flex items-start gap-2 rounded-xl border border-amber-400/25 bg-amber-400/5 px-4 py-3 text-xs leading-5 text-amber-100"><ShieldAlert size={15} className="mt-0.5 shrink-0" /> These are challenge examples from research datasets, not aircraft work orders or maintenance diagnoses. Review levels do not schedule work. Hydraulic caution reflects model abstention; fuel anomaly output is experimental.</div>
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Component attention counts">
      <SummaryTile label="Critical model flags" value={loading ? '—' : summary.Critical} note="Positive fault/anomaly output on an example" tone="rose" />
      <SummaryTile label="Caution / review" value={loading ? '—' : summary.Caution} note="Abstention or model input-support warning" tone="amber" />
      <SummaryTile label="Monitor" value={loading ? '—' : summary.Monitor} note="No model alert for the example; not clearance" />
      <SummaryTile label="Unavailable" value={loading ? '—' : summary.Unavailable} note="Model endpoint returned an error" />
    </section>
    {loading && <div className="flex items-center gap-3 rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-4 text-sm text-cyan-100"><Loader2 size={18} className="animate-spin" /> Running challenge examples through the five model endpoints…</div>}
    {!loading && grouped.map(({ level, rows }) => <section key={level} className="space-y-3" aria-label={`${level} component reviews`}>
      <div className={`rounded-xl border px-4 py-3 ${level === 'Critical' ? 'border-rose-400/25 bg-rose-400/5' : level === 'Caution' ? 'border-amber-400/25 bg-amber-400/5' : level === 'Monitor' ? 'border-cyan-400/20 bg-cyan-400/5' : 'border-slate-700 bg-slate-900/50'}`}>
        <div className="flex flex-wrap items-center justify-between gap-2"><h2 className={`text-sm font-bold ${level === 'Critical' ? 'text-rose-200' : level === 'Caution' ? 'text-amber-200' : level === 'Monitor' ? 'text-cyan-200' : 'text-slate-300'}`}>{level} <span className="ml-1 rounded-full bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300">{rows.length}</span></h2><span className="text-[10px] text-slate-500">{level === 'Critical' ? 'Model-flagged example' : level === 'Caution' ? 'Requires model/engineering review' : level === 'Monitor' ? 'No alert in this example' : 'Could not evaluate'}</span></div>
        {rows.length === 0 ? <p className="mt-2 text-[11px] text-slate-500">No components in this group for the current challenge examples.</p> : <div className="mt-3 grid gap-3 lg:grid-cols-2">{rows.map(item => <div key={item.system.key} className="space-y-2"><div className={`rounded-lg border px-3 py-2 text-[11px] leading-5 ${level === 'Critical' ? 'border-rose-400/25 bg-rose-400/5 text-rose-100' : level === 'Caution' ? 'border-amber-400/25 bg-amber-400/5 text-amber-100' : level === 'Monitor' ? 'border-cyan-400/20 bg-cyan-400/5 text-cyan-100' : 'border-slate-700 bg-slate-950/50 text-slate-300'}`}><strong>{item.system.title} — {level}:</strong> {triage(item).reason}</div><ResultCard item={item} maintenance /></div>)}</div>}
      </div>
    </section>)}
    {!loading && items.length === 0 && <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300"><AlertTriangle className="mb-2 text-amber-300" size={18} />No model responses are available. Start the FastAPI backend and retry.</div>}
    <p className="text-[11px] leading-5 text-slate-500">No maintenance thresholds have been approved for operational use. Engine/battery RUL is shown with its estimate and interval; this screen does not invent a critical-cycle cutoff. Fuel predictions remain experimental.</p>
    <div className="flex justify-end border-t border-slate-800 pt-4"><button type="button" onClick={downloadResults} disabled={loading || items.length === 0} className="inline-flex items-center gap-2 rounded-lg border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-xs font-semibold text-amber-100 hover:border-amber-200 disabled:opacity-50"><Download size={14} /> Download Maintenance results (.json)</button></div>
  </div>;
}

export default function ModelOperationsView({ mode }) {
  const [refreshCount, setRefreshCount] = useState(0);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const isMaintenance = mode === 'maintenance';
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setItems([]);
    const variant = isMaintenance ? 'challenge' : 'normal';
    Promise.all(SYSTEMS.map(async system => {
      try {
        const example = await getJson(`/api/workspace/examples/${system.key}?variant=${variant}`, { signal: controller.signal });
        const result = await getJson(system.endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(example.payload), signal: controller.signal });
        return { system, example, result };
      } catch (error) {
        if (error.name === 'AbortError') throw error;
        return { system, error: error.message };
      }
    })).then(responses => { if (!controller.signal.aborted) setItems(responses); })
      .catch(error => { if (error.name !== 'AbortError') setItems(SYSTEMS.map(system => ({ system, error: error.message }))); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [refreshCount, isMaintenance]);

  useEffect(() => {
    if (isMaintenance) return undefined;
    const controller = new AbortController();
    setHistoryLoading(true); setHistoryError('');
    getJson('/api/prediction-history?limit=100', { signal: controller.signal })
      .then(records => { if (!controller.signal.aborted) setHistory(Array.isArray(records) ? records : []); })
      .catch(error => {
        if (!controller.signal.aborted) {
          setHistory([]);
          setHistoryError(error.message || 'Could not load saved prediction history.');
        }
      })
      .finally(() => { if (!controller.signal.aborted) setHistoryLoading(false); });
    return () => controller.abort();
  }, [refreshCount, isMaintenance]);
  const refresh = () => setRefreshCount(value => value + 1);
  const saveOutcome = updated => setHistory(records => records.map(record => record.id === updated.id ? updated : record));
  const downloadResults = () => downloadSectionResults(
    isMaintenance ? 'maintenance' : 'fleet',
    isMaintenance ? 'challenge' : 'normal',
    items,
  );
  return isMaintenance
    ? <MaintenanceReview items={items} loading={loading} refresh={refresh} downloadResults={downloadResults} />
    : <FleetOverview items={items} loading={loading} refresh={refresh} downloadResults={downloadResults}
      history={history} historyLoading={historyLoading} historyError={historyError} onOutcomeSaved={saveOutcome} />;
}
