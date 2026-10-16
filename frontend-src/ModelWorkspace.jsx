import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Activity, ArrowRight, BatteryCharging, CheckCircle2, CircleDot, Cpu, Download, Droplets, FileJson2, Fuel, Gauge, Loader2, Plane, Sparkles, Upload } from 'lucide-react';
import { csvToPayload, payloadToCsv } from './requestFiles.js';
import { makeComponentBundle, parseComponentBundle } from './batchRequests.js';
import { makePredictionReport, sha256Text } from './predictionReport.js';
import { getInputUnitGuidance } from './inputGuidance.js';
import { friendlyApiError, parseJsonObject } from './uploadValidation.js';
import { getResultGuidance } from './resultGuidance.js';
import { predictionNeedsReview, summarizeHistoryPrediction } from './predictionHistory.js';
import './workspace.css';


const COMPONENTS = [
  { key: 'engine', title: 'Engine', subtitle: 'Remaining useful life', metric: 'RUL', icon: Gauge, accent: 'cyan' },
  { key: 'battery', title: 'Battery', subtitle: 'Health & remaining life', metric: 'SOH + RUL', icon: BatteryCharging, accent: 'violet' },
  { key: 'hydraulic', title: 'Hydraulic', subtitle: 'Four condition checks', metric: '4 outputs', icon: Droplets, accent: 'blue' },
  { key: 'landing-gear', title: 'Landing gear', subtitle: 'Fault & remaining life', metric: 'FAULT + RUL', icon: Plane, accent: 'amber' },
  { key: 'fuel-system', title: 'Fuel system', subtitle: 'Anomaly screening', metric: 'EXPERIMENTAL', icon: Fuel, accent: 'rose' },
];
const ENDPOINTS = Object.fromEntries(COMPONENTS.map(({ key }) => [key,
  key === 'fuel-system' ? '/api/predict/fuel-system' : `/api/v2/predict/${key}`]));
const PREFLIGHT_ENDPOINTS = Object.fromEntries(COMPONENTS.map(({ key }) => [key, `/api/v2/preflight/${key}`]));
const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const format = value => typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 3 }) : String(value);
const label = text => text.replaceAll('_', ' ');

function summarizeRequest(component, input) {
  if (!input.trim()) return { state: 'empty', title: 'No request data loaded', detail: 'Choose an example or import a JSON file to get started.' };
  let payload;
  try { payload = JSON.parse(input); }
  catch { return { state: 'invalid', title: 'JSON needs attention', detail: 'Open the full JSON editor and fix the formatting, or import a valid JSON file.' }; }
  if (!payload || Array.isArray(payload) || typeof payload !== 'object') {
    return { state: 'invalid', title: 'Request must be one JSON object', detail: 'Open the full JSON editor to review the request structure.' };
  }
  const collectionName = component === 'engine' ? 'records' : ['battery', 'fuel-system'].includes(component) ? 'samples' : null;
  const collection = collectionName && Array.isArray(payload[collectionName]) ? payload[collectionName] : null;
  const itemCount = collection ? collection.length : 1;
  const fieldCount = component === 'hydraulic'
    ? Object.keys(payload.features || {}).length
    : collection?.length && collection[0] && typeof collection[0] === 'object'
      ? Object.keys(collection[0]).length
      : Object.keys(payload).length;
  const subject = component === 'engine' ? (itemCount === 1 ? 'engine cycle' : 'engine cycles')
    : component === 'battery' ? (itemCount === 1 ? 'battery reading' : 'battery readings')
      : component === 'fuel-system' ? (itemCount === 1 ? 'fuel-system reading' : 'fuel-system readings')
        : component === 'hydraulic' ? 'hydraulic cycle'
          : 'landing event';
  const countText = `${itemCount.toLocaleString()} ${subject}`;
  const fieldsText = fieldCount ? ` | ${fieldCount} input fields per reading` : '';
  return { state: 'ready', title: 'JSON format valid', detail: `${countText}${fieldsText}. The API checks the request schema and available model training support before prediction.` };
}

function InputQualityReport({ report }) {
  if (!report) return null;
  const review = report.review_required;
  return <section className={`input-quality-report ${review ? 'review' : 'supported'}`} aria-label="Upload quality check" role="status">
    <div className="input-quality-heading"><strong>{review ? 'Input check needs your review' : 'Format and range checks passed'}</strong><span>{report.schema_valid ? 'Request structure valid' : 'Structure check failed'}</span></div>
    {report.checks && <div className="input-quality-tasks">{Object.entries(report.checks).map(([task, check]) => <article key={task}>
      <strong>{label(task)}</strong><span className={check.status === 'within_training_range' ? 'quality-ok' : 'quality-review'}>{check.status === 'within_training_range' ? 'Within observed training range' : check.status === 'not_assessed' ? 'Range not assessed' : 'Review required'}</span>
      <small>{check.detail}</small>
      {check.hard_range_violations?.length > 0 && <small className="quality-review">Outside observed training range: {check.hard_range_violations.join(', ')}</small>}
      {check.tail_range_warnings?.length > 0 && <small className="quality-review">Near edge of training range: {check.tail_range_warnings.join(', ')}</small>}
    </article>)}</div>}
    {report.notes?.length > 0 && <ul className="input-quality-notes">{report.notes.map((note, index) => <li key={index}>{note}</li>)}</ul>}
    <p className="input-quality-footnote">This checks request structure and available model training support only. Request files contain no unit metadata, so units cannot be verified here; this is not a physical-condition or safety check.</p>
  </section>;
}

function UnitGuidance({ components }) {
  return <details className="unit-guidance">
    <summary>Review expected fields and units</summary>
    {components.map(({ key, title }) => <section key={key}>
      {components.length > 1 && <strong>{title}</strong>}
      <ul>{getInputUnitGuidance(key).map((item, index) => <li key={index}>{item}</li>)}</ul>
    </section>)}
    <p>These notes document expected units; the API receives numeric values without unit tags and cannot confirm which units your file actually uses. Do not convert or rename unknown-unit fields by guesswork.</p>
  </details>;
}

function batchSummary(component, data) {
  if (component === 'engine') return `Estimated RUL: ${format(data.rul.value)} ${data.rul.unit}`;
  if (component === 'battery') return `SOH: ${format(data.soh.value)}%; estimated RUL: ${format(data.rul.value)} ${data.rul.unit}`;
  if (component === 'hydraulic') return Object.entries(data.predictions || {}).map(([name, result]) => `${label(name)}: ${result.label ?? result.value}`).join('; ');
  if (component === 'landing-gear') return `Fault: ${data.fault.label ?? data.fault.value}; estimated RUL: ${format(data.rul.value)} ${data.rul.unit}`;
  return `${data.latest_is_abnormal ? 'Latest sample flagged' : 'No alert on latest sample'}; ${data.flagged_samples} of ${data.input_samples} samples flagged`;
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(BASE + path, options);
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new Error('Cannot reach FastAPI. Start the backend and confirm it is listening on port 8000.');
  }
  const text = await response.text();
  let body;
  try { body = JSON.parse(text); } catch { throw new Error('Backend returned a non-JSON response. Check the API address.'); }
  if (!response.ok) throw new Error(friendlyApiError(response.status, body.detail));
  return body;
}

function Prediction({ name, result }) {
  return <article className="result-card">
    <div className="card-heading"><span>{label(name)}</span><span className={`badge ${result.accepted ? 'accepted' : 'review'}`}>
      {result.accepted ? 'Within model checks' : 'Review required'}</span></div>
    <p className="prediction-value">{format(result.value)} <small>{result.unit || result.label || 'class'}</small></p>
    {result.lower !== undefined && <p>Estimated interval: {format(result.lower)} to {format(result.upper)} {result.unit}
      <span className="muted"> | nominal {format(result.interval_level * 100)}%; observed coverage may be lower</span></p>}
    {result.calibrated_confidence !== undefined && <p>Development confidence estimate: {format(result.calibrated_confidence * 100)}%</p>}
    {result.input_support?.hard_range_violations?.length > 0 && <p className="alert-text">Outside training range: {result.input_support.hard_range_violations.join(', ')}</p>}
    {result.input_support?.tail_range_warnings?.length > 0 && <details><summary>Unusual input values</summary>{result.input_support.tail_range_warnings.join(', ')}</details>}
    {result.top_model_features?.length > 0 && <details className="model-explanation"><summary>What features influence this model?</summary>
      <p className="muted">Global model importance, not a case-specific cause. Bars are relative to this model's strongest feature.</p>
      <ul>{result.top_model_features.map(item => <li key={item.feature}><span>{label(item.feature)}</span><span className="importance-track"><i style={{ width: `${Math.max(2, item.relative_importance)}%` }} /></span><strong>{format(item.relative_importance)}%</strong></li>)}</ul>
    </details>}
  </article>;
}

function ResultMeaning({ component }) {
  const guidance = getResultGuidance(component);
  if (!guidance) return null;
  return <aside className="result-meaning" aria-label="How to interpret this result">
    <strong>What this means</strong>
    <p>{guidance.meaning}</p>
    <small>{guidance.caveat}</small>
  </aside>;
}

export default function ModelWorkspace() {
  const [component, setComponent] = useState('engine');
  const [variant, setVariant] = useState('normal');
  const [sample, setSample] = useState(null);
  const [input, setInput] = useState('');
  const [fileName, setFileName] = useState('');
  const [inputQuality, setInputQuality] = useState(null);
  const [result, setResult] = useState(null);
  const [runRecord, setRunRecord] = useState(null);
  const [reportError, setReportError] = useState('');
  const [reportSaving, setReportSaving] = useState(false);
  const [historySaveNotice, setHistorySaveNotice] = useState(null);
  const [assetId, setAssetId] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [runStage, setRunStage] = useState('quality');
  const [apiStatus, setApiStatus] = useState('checking');
  const [evidence, setEvidence] = useState(null);
  const [evidenceError, setEvidenceError] = useState('');
  const [batchPayload, setBatchPayload] = useState(null);
  const [batchFileName, setBatchFileName] = useState('');
  const [batchTemplateLoading, setBatchTemplateLoading] = useState(false);
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchError, setBatchError] = useState('');
  const [batchResults, setBatchResults] = useState(null);
  const [batchQuality, setBatchQuality] = useState(null);
  const [batchAcknowledged, setBatchAcknowledged] = useState(false);
  const [inputAcknowledged, setInputAcknowledged] = useState(false);
  const [reload, setReload] = useState(0);
  const generation = useRef(0);
  const controller = useRef(null);
  const batchController = useRef(null);

  useEffect(() => () => batchController.current?.abort(), []);

  useEffect(() => {
    const abort = new AbortController();
    setApiStatus('checking');
    setEvidence(null); setEvidenceError('');
    request('/api/health', { signal: abort.signal }).then(() => setApiStatus('online')).catch(err => {
      if (err.name !== 'AbortError') {
        setApiStatus('offline');
        generation.current += 1;
        controller.current?.abort();
        setRunning(false); setResult(null);
      }
    });
    request('/api/workspace/evidence', { signal: abort.signal }).then(setEvidence).catch(err => {
      if (err.name !== 'AbortError') setEvidenceError(err.message);
    });
    return () => abort.abort();
  }, [reload]);

  useEffect(() => {
    generation.current += 1;
    controller.current?.abort();
    const abort = new AbortController();
    setLoading(true); setRunning(false); setSample(null); setInput(''); setFileName(''); setInputQuality(null); setInputAcknowledged(false); setResult(null); setRunRecord(null); setReportError(''); setError('');
    request(`/api/workspace/examples/${component}?variant=${variant}`, { signal: abort.signal })
      .then(data => { setSample(data); setInput(JSON.stringify(data.payload, null, 2)); })
      .catch(err => { if (err.name !== 'AbortError') setError(err.message); })
      .finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => { abort.abort(); controller.current?.abort(); };
  }, [component, variant]);

  function edit(value) {
    generation.current += 1; controller.current?.abort(); setRunning(false);
    setInput(value); setFileName(''); setInputQuality(null); setInputAcknowledged(false); setResult(null); setRunRecord(null); setReportError(''); setError('');
  }

  function resetToExample() {
    if (!sample) return;
    edit(JSON.stringify(sample.payload, null, 2));
  }

  function downloadExample() {
    if (!sample) return;
    const blob = new Blob([JSON.stringify(sample.payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${component}-request-example.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function downloadCsvTemplate() {
    if (!sample) return;
    const blob = new Blob([payloadToCsv(component, sample.payload)], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${component}-example-template.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function runPrediction(confirmReview) {
    if (!inputAcknowledged) return;
    setError(''); setResult(null); setRunRecord(null); setReportError(''); setHistorySaveNotice(null); setBatchResults(null);
    const current = ++generation.current;
    try {
      const payload = JSON.parse(input);
      if (!payload || Array.isArray(payload) || typeof payload !== 'object') throw new Error('Input must be a JSON object.');
      controller.current?.abort();
      controller.current = new AbortController(); setRunning(true); setRunStage('quality');
      let checked = inputQuality?.sourceText === input ? inputQuality.report : null;
      if (!checked) {
        checked = await request(PREFLIGHT_ENDPOINTS[component], { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload), signal: controller.current.signal });
        if (current !== generation.current) return;
        setInputQuality({ sourceText: input, report: checked });
      }
      if (checked.review_required && !confirmReview) return;
      setRunStage('prediction');
      const data = await request(ENDPOINTS[component], { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload), signal: controller.current.signal });
      if (current === generation.current) {
        setResult(data);
        const source = sample && input === JSON.stringify(sample.payload, null, 2) ? sample.source : fileName ? 'User-uploaded file' : 'User-edited request';
        setRunRecord({ requestText: input, preflight: checked, prediction: data,
          inputSummary: summarizeRequest(component, input).detail,
          source });
        setHistorySaveNotice({ kind: 'info', text: 'Saving this result to Fleet history…' });
        let inputDigest;
        try { inputDigest = await sha256Text(input); } catch { inputDigest = null; }
        try {
          await request('/api/prediction-history', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
            component, asset_id: assetId.trim() || null,
            source: sample && input === JSON.stringify(sample.payload, null, 2) ? 'dataset_example' : fileName ? 'uploaded_file' : 'edited_input',
            summary: summarizeHistoryPrediction(component, data),
            review_required: predictionNeedsReview(component, data),
            model_release: evidence?.release_id || null,
            input_digest: inputDigest,
          }) });
          if (current === generation.current) setHistorySaveNotice({ kind: 'success', text: 'Saved to Fleet history. Raw sensor values were not stored.' });
        } catch {
          if (current === generation.current) setHistorySaveNotice({ kind: 'error', text: 'Prediction completed, but could not be saved to Fleet history. Check the backend and try Refresh snapshot in Fleet.' });
        }
      }
    } catch (err) { if (current === generation.current && err.name !== 'AbortError') setError(err.message); }
    finally { if (current === generation.current) setRunning(false); }
  }

  async function downloadPredictionReport() {
    if (!runRecord || !result) return;
    setReportError(''); setReportSaving(true);
    try {
      const report = await makePredictionReport({
        component, title: COMPONENTS.find(item => item.key === component)?.title,
        releaseId: evidence?.release_id, ...runRecord,
      });
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url; anchor.download = `${component}-prediction-report-${report.created_at_utc.slice(0, 10)}.json`;
      anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { setReportError(err.message || 'Could not create the prediction report.'); }
    finally { setReportSaving(false); }
  }

  async function downloadBatchTemplate() {
    setBatchError(''); setBatchTemplateLoading(true);
    try {
      const examples = await Promise.all(COMPONENTS.map(async ({ key }) => [key,
        await request(`/api/workspace/examples/${key}?variant=normal`)]));
      const bundle = makeComponentBundle(Object.fromEntries(examples));
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url; anchor.download = 'all-aircraft-components-example.json'; anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) { setBatchError(err.message); }
    finally { setBatchTemplateLoading(false); }
  }

  async function runBatch(confirmReview = false) {
    if (!batchPayload || batchRunning || !batchAcknowledged) return;
    setBatchError(''); setBatchResults(null); setBatchRunning(true); setHistorySaveNotice(null);
    batchController.current?.abort();
    const activeController = new AbortController();
    batchController.current = activeController;
    try {
      const fingerprint = JSON.stringify(batchPayload);
      let quality = batchQuality?.fingerprint === fingerprint ? batchQuality : null;
      if (!quality) {
        const outcomes = await Promise.allSettled(COMPONENTS.map(({ key }) => request(PREFLIGHT_ENDPOINTS[key], {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(batchPayload[key]), signal: activeController.signal,
        })));
        const checks = Object.fromEntries(COMPONENTS.map(({ key }, index) => {
          const outcome = outcomes[index];
          return [key, outcome.status === 'fulfilled'
            ? { ok: true, report: outcome.value }
            : { ok: false, error: outcome.reason?.message || 'Quality check failed.' }];
        }));
        quality = {
          fingerprint,
          checks,
          schemaValid: Object.values(checks).every(check => check.ok),
          reviewRequired: Object.values(checks).some(check => check.ok && check.report.review_required),
        };
        setBatchQuality(quality);
      }
      if (!quality.schemaValid) {
        setBatchError('One or more component requests failed their schema check. Fix those sections in the JSON bundle, then upload it again. No predictions were run.');
        return;
      }
      if (quality.reviewRequired && !confirmReview) return;
      const outcomes = await Promise.allSettled(COMPONENTS.map(({ key }) => request(ENDPOINTS[key], {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(batchPayload[key]), signal: activeController.signal,
      })));
      const results = Object.fromEntries(COMPONENTS.map(({ key }, index) => {
        const outcome = outcomes[index];
        return [key, outcome.status === 'fulfilled'
          ? { ok: true, data: outcome.value }
          : { ok: false, error: outcome.reason?.message || 'Prediction request failed.' }];
      }));
      setBatchResults(results);
      setHistorySaveNotice({ kind: 'info', text: 'Saving successful subsystem results to Fleet history…' });
      const historySaves = COMPONENTS.flatMap(({ key }) => {
        const outcome = results[key];
        if (!outcome?.ok) return [];
        const requestText = JSON.stringify(batchPayload[key]);
        return [(async () => {
          let inputDigest;
          try { inputDigest = await sha256Text(requestText); } catch { inputDigest = null; }
          return request('/api/prediction-history', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
            component: key, asset_id: assetId.trim() || null,
            source: batchFileName ? 'uploaded_file' : 'all_components_bundle',
            summary: summarizeHistoryPrediction(key, outcome.data),
            review_required: predictionNeedsReview(key, outcome.data),
            model_release: evidence?.release_id || null,
            input_digest: inputDigest,
          }) });
        })()];
      });
      const saveOutcomes = await Promise.allSettled(historySaves);
      const savedCount = saveOutcomes.filter(outcome => outcome.status === 'fulfilled').length;
      setHistorySaveNotice(historySaves.length === 0
        ? { kind: 'error', text: 'No subsystem predictions were returned, so no results were saved to Fleet history.' }
        : savedCount === historySaves.length
        ? { kind: 'success', text: `Saved ${savedCount} subsystem results to Fleet history. Raw sensor values were not stored.` }
        : { kind: 'error', text: `Saved ${savedCount} of ${historySaves.length} subsystem results to Fleet history; some could not be saved. Check the backend and refresh Fleet.` });
    } finally { setBatchRunning(false); }
  }

  async function downloadBatchReport() {
    if (!batchResults || !batchPayload) return;
    setBatchError('');
    try {
      const reports = await Promise.all(COMPONENTS.map(async ({ key, title }) => {
        const outcome = batchResults[key];
        if (!outcome?.ok) return [key, { status: 'request_failed', error: outcome?.error || 'No result returned.' }];
        const check = batchQuality?.checks?.[key];
        const report = await makePredictionReport({
          component: key, title, releaseId: evidence?.release_id,
          requestText: JSON.stringify(batchPayload[key]),
          inputSummary: summarizeRequest(key, JSON.stringify(batchPayload[key])).detail,
          source: batchFileName ? 'User-uploaded all-components file' : 'User-supplied all-components request',
          preflight: check?.ok ? check.report : { status: 'not_available' },
          prediction: outcome.data,
        });
        return [key, report];
      }));
      const record = {
        report_schema: 'aircraft-predictive-maintenance-batch-report/v1',
        created_at_utc: new Date().toISOString(),
        model_release: evidence?.release_id || 'unavailable',
        reports: Object.fromEntries(reports),
        limitations: ['Independent subsystem predictions; this is not a combined aircraft-level model.', 'Research prototype output only; not approved for aircraft maintenance decisions.', 'Raw sensor values are excluded; each successful subsystem includes a request-text SHA-256 digest.'],
      };
      const blob = new Blob([JSON.stringify(record, null, 2)], { type: 'application/json;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url; anchor.download = 'all-components-prediction-report-' + record.created_at_utc.slice(0, 10) + '.json';
      anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { setBatchError(err.message || 'Could not create the all-components report.'); }
  }

  const matchesSample = sample && input === JSON.stringify(sample.payload, null, 2);
  const requestSummary = useMemo(() => summarizeRequest(component, input), [component, input]);
  const fuelMetrics = evidence?.fuel_evaluation?.metrics;
  const predictions = result?.predictions || Object.fromEntries(['rul', 'soh', 'fault'].filter(key => result?.[key]).map(key => [key, result[key]]));
  const engineRul = result?.component === 'Engine' ? result.rul?.value : null;
  const engineRisk = engineRul == null ? null : engineRul <= 30 ? 'High' : engineRul <= 60 ? 'Medium' : 'Low';
  return <div className="workspace">
    <header className="workspace-header"><div className="hero-copy"><div className="eyebrow"><Sparkles size={14} /> AIRCRAFT PREDICTIVE MAINTENANCE</div><h1>AI predictions</h1>
      <p className="muted">Choose an aircraft system, add its sensor data, and review a model-generated assessment.</p><p className="prototype-context">Research prototype — not approved for aircraft maintenance decisions.</p></div>
      <div className="hero-mark"><span><Plane size={21} /></span><div><strong>Predictive maintenance</strong><small>Research workspace</small></div></div>
    </header>
    <main>
      <ol className="steps" aria-label="Prediction steps">
        <li><span>01</span><div><strong>Choose a system</strong><small>Select the component to assess</small></div><ArrowRight size={15} /></li>
        <li><span>02</span><div><strong>Add sensor data</strong><small>Use a sample or your JSON file</small></div><ArrowRight size={15} /></li>
        <li><span>03</span><div><strong>Review the result</strong><small>Check estimates and warnings</small></div><CheckCircle2 size={15} /></li>
      </ol>
      <section className={`connection ${apiStatus}`} aria-live="polite"><span className={`dot ${apiStatus === 'online' ? 'online' : apiStatus === 'offline' ? 'offline' : ''}`} />
        <span className="connection-copy"><strong>{apiStatus === 'checking' ? 'Connecting to prediction service' : apiStatus === 'offline' ? 'Prediction service unavailable' : 'Prediction service connected'}</strong>
          <small>{apiStatus === 'checking' ? 'Checking FastAPI...' : apiStatus === 'offline' ? 'Start the backend, then retry.' : evidence ? `Active model release: ${evidence.release_id}` : 'Model release details unavailable'}</small></span>
        <button type="button" onClick={() => setReload(value => value + 1)}><CircleDot size={14} /> Check connection</button></section>
      {evidenceError && <div role="alert" className="error"><strong>Could not load model release details</strong><p>{evidenceError}</p>
        <p>Confirm the backend is running, then use Check connection to retry.</p></div>}
      <div className="section-intro"><div><span className="section-kicker">STEP 1</span><h2>Choose an aircraft system</h2></div><p>Select a model to see its data and prediction options.</p></div>
      <nav className="component-tabs" aria-label="Aircraft subsystem">{COMPONENTS.map(({ key, title, subtitle, metric, icon: Icon, accent }) =>
        <button key={key} aria-pressed={component === key} onClick={() => setComponent(key)}><span className={`system-icon ${accent}`}><Icon size={19} /></span><span className="system-copy"><strong>{title}</strong><small>{subtitle}</small><em>{metric}</em></span><ArrowRight className="system-arrow" size={15} /></button>)}</nav>
      <label className="history-asset-field" htmlFor="history-asset-id"><span><strong>Optional project asset ID</strong><small>Used to group saved prediction runs in Fleet. Use an internal ID, not a registration number or personal information.</small></span><input id="history-asset-id" maxLength={80} value={assetId} onChange={event => setAssetId(event.target.value)} placeholder="e.g. TEST-AIRCRAFT-01" /></label>
      <section className="panel all-components-panel" aria-labelledby="all-components-title">
        <div className="panel-heading"><span className="panel-icon result-icon"><Cpu size={18} /></span><div><span className="section-kicker">MULTI-SYSTEM</span><h2 id="all-components-title">Upload all components together</h2><p>One JSON bundle sends a separate request to each of the five model endpoints.</p></div></div>
        <div className="bulk-guidance"><strong>Bundle format</strong><span>Use one top-level JSON object with these five keys: engine, battery, hydraulic, landing-gear, and fuel-system. Each key contains the same request object you would upload for that subsystem by itself.</span></div>
        <UnitGuidance components={COMPONENTS} />
        <div className="input-actions bulk-actions">
          <button type="button" onClick={downloadBatchTemplate} disabled={batchTemplateLoading || batchRunning}>{batchTemplateLoading ? <><Loader2 className="spin" size={15} /> Preparing example...</> : 'Download all-components example'}</button>
          <label className="upload"><Upload size={15} /> Choose bundle JSON<input aria-label="Choose all-components JSON bundle" type="file" accept=".json,application/json" disabled={batchRunning} onChange={async event => {
            const file = event.target.files?.[0]; if (!file) return;
            setBatchError(''); setBatchResults(null); setBatchPayload(null); setBatchFileName(''); setBatchQuality(null); setBatchAcknowledged(false);
            try {
              if (file.size > 20_000_000) throw new Error('Choose an all-components JSON file smaller than 20 MB.');
              const parsed = parseComponentBundle(await file.text());
              setBatchPayload(parsed); setBatchFileName(file.name);
            } catch (err) { setBatchError(err instanceof SyntaxError ? 'This file is not valid JSON. Check its commas, quotes, and brackets.' : err.message); }
            event.target.value = '';
          }} /></label>
          <button type="button" className="primary" onClick={() => runBatch(false)} disabled={!batchPayload || !batchAcknowledged || batchRunning || apiStatus !== 'online' || (batchQuality?.fingerprint === JSON.stringify(batchPayload) && !batchQuality.schemaValid)}>{batchRunning ? <><Loader2 className="spin" size={15} /> Checking / running...</> : 'Check data & run five models'}</button>
          {batchPayload && !batchRunning && <button type="button" onClick={() => { setBatchPayload(null); setBatchFileName(''); setBatchResults(null); setBatchError(''); setBatchQuality(null); setBatchAcknowledged(false); }}>Clear bundle</button>}
        </div>
        {batchFileName && <p className="file-ready" role="status">Bundle ready: <strong>{batchFileName}</strong>. Each component request will be checked before any predictions run.</p>}
        {batchPayload && <label className="input-acknowledgement"><input type="checkbox" checked={batchAcknowledged} onChange={event => setBatchAcknowledged(event.target.checked)} /><span>I checked that all five requests use the expected fields, sequence, and units. The app cannot verify physical units or whether these readings describe a real aircraft condition.</span></label>}
        {batchError && <div className="error" role="alert"><strong>All-components check needs attention</strong><p>{batchError}</p></div>}
        {batchPayload && batchQuality && batchQuality.fingerprint === JSON.stringify(batchPayload) && <section className="batch-quality" aria-label="All-components quality checks">
          <h3>Pre-prediction data checks</h3><p className="muted">Each subsystem was checked separately; range warnings use the saved model's observed training support, not aircraft safety limits.</p>
          <div className="batch-quality-grid">{COMPONENTS.map(({ key, title }) => {
            const check = batchQuality.checks[key];
            return <article key={key}><strong>{title}</strong>{check.ok ? <InputQualityReport report={check.report} /> : <p className="alert-text">Schema check failed: {check.error}</p>}</article>;
          })}</div>
          {!batchQuality.schemaValid && <p className="alert-text">Correct the invalid component request(s) and upload the bundle again. Predictions are blocked until the request structures are valid.</p>}
          {batchQuality.schemaValid && batchQuality.reviewRequired && !batchRunning && !batchResults && <button type="button" className="quality-continue" onClick={() => runBatch(true)}>I reviewed the warnings - continue to five predictions</button>}
        </section>}
        {batchRunning && <div className="running-state"><Loader2 className="spin" size={20} /><span><strong>Checking inputs, then running models if suitable</strong><small>Any required review pauses the predictions; a schema error blocks the batch.</small></span></div>}
        {batchResults && <button type="button" onClick={downloadBatchReport} className="quality-continue">Download all-components report (.json)</button>}
        {batchResults && <div className="bulk-results" aria-live="polite">{COMPONENTS.map(({ key, title }) => {
          const outcome = batchResults[key];
          return <article key={key} className={`bulk-result ${outcome.ok ? 'success' : 'failure'}`}>
            <div className="card-heading"><span>{title}</span><span className={`badge ${outcome.ok ? 'accepted' : 'review'}`}>{outcome.ok ? 'Response received' : 'Request failed'}</span></div>
            {outcome.ok ? <><p>{batchSummary(key, outcome.data)}</p><ResultMeaning component={key} />{outcome.data.warnings?.length > 0 && <details><summary>Model warnings</summary><ul>{outcome.data.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></details>}<details><summary>Full {title.toLowerCase()} response</summary><pre>{JSON.stringify(outcome.data, null, 2)}</pre></details></> : <p className="alert-text">{outcome.error}</p>}
          </article>;
        })}</div>}
        {historySaveNotice && batchResults && <div className={`history-save-notice ${historySaveNotice.kind}`} role="status">{historySaveNotice.text}</div>}
        <p className="muted bulk-caution">This is a convenience workflow, not one combined aircraft-level model. Each subsystem runs independently; fuel remains experimental and all results are research-only.</p>
      </section>
      <div className="workspace-grid"><section className="panel">
        <div className="panel-heading"><span className="panel-icon input-icon"><FileJson2 size={18} /></span><div><span className="section-kicker">STEP 2</span><h2>Provide sensor data</h2><p>Start with a sample or load your own JSON.</p></div></div>
        <div className="sample-selector"><label htmlFor="sample-variant">Dataset example</label><select id="sample-variant" aria-label="Dataset example" value={variant} onChange={event => setVariant(event.target.value)}>
          <option value="normal">Normal example{component === 'hydraulic' ? ' (stable)' : ''}</option><option value="challenge">Challenge example{component === 'hydraulic' ? ' (unstable)' : ''}</option></select></div>
        <p className="muted">{loading ? 'Loading dataset example...' : matchesSample ? sample.source : 'Custom JSON - dataset reference labels do not apply'}</p>
        <p className="muted">Start with an example or import a JSON/CSV file. Use the selected system's CSV example for the required columns.</p>
        <UnitGuidance components={COMPONENTS.filter(item => item.key === component)} />
        <div className={`request-summary ${requestSummary.state}`} role="status" aria-live="polite">
          <span className="request-summary-icon">{requestSummary.state === 'ready' ? <CheckCircle2 size={17} /> : <FileJson2 size={17} />}</span>
          <span className="request-summary-copy"><strong>{requestSummary.title}</strong><small>{requestSummary.detail}</small></span>
          {requestSummary.state === 'ready' && <span className="request-summary-badge">JSON OK</span>}
        </div>
        {inputQuality?.sourceText === input && <InputQualityReport report={inputQuality.report} />}
        <p className="request-note">Detailed sensor values are hidden to keep this view simple. The complete request is still sent to the model.</p>
        <details className="advanced-json">
          <summary><span><FileJson2 size={15} /> View or edit full JSON</span><span className="advanced-label">ADVANCED</span></summary>
          <div className="advanced-json-body">
            <label className="input-label" htmlFor="model-input">Prediction request JSON <span>Required</span></label>
            <textarea id="model-input" aria-describedby="json-help" spellCheck="false" value={input} onChange={event => edit(event.target.value)} placeholder="Select an example or import a .json request file" />
            <p id="json-help" className="input-help">The complete request is sent to the model API. JSON files must contain one object, not a list.</p>
          </div>
        </details>
        <label className="input-acknowledgement"><input type="checkbox" checked={inputAcknowledged} onChange={event => setInputAcknowledged(event.target.checked)} /><span>I checked that this request uses the expected fields, sequence, and units. The app cannot verify physical units or whether these readings describe a real aircraft condition.</span></label>
        <div className="input-actions"><button className="primary" onClick={() => runPrediction(false)} disabled={loading || running || !input.trim() || !inputAcknowledged}>{running ? <><Loader2 className="spin" size={16} /> {runStage === 'quality' ? 'Checking input...' : 'Running model...'}</> : <><Sparkles size={16} /> Check data & predict</>}</button>
          {inputQuality?.sourceText === input && inputQuality.report.review_required && !running && !result && requestSummary.state === 'ready' && <button type="button" className="quality-continue" onClick={() => runPrediction(true)}>I reviewed the warnings - continue</button>}
          <label className="upload"><Upload size={15} /> Import JSON / CSV<input aria-label="Choose a JSON or CSV request file" type="file" accept=".json,.csv,application/json,text/csv" onChange={async event => {
            const file = event.target.files?.[0]; if (!file) return;
            const current = ++generation.current;
            controller.current?.abort(); setRunning(false); setResult(null); setError(''); setFileName(''); setInputQuality(null); setInputAcknowledged(false);
            try {
              if (file.size > 5_000_000) throw new Error('Choose a JSON file smaller than 5 MB.');
              const text = await file.text();
              const parsed = file.name.toLowerCase().endsWith('.csv')
                ? sample?.payload ? csvToPayload(component, text, sample.payload) : (() => { throw new Error('Wait for the selected system example to load before importing CSV.'); })()
                : parseJsonObject(text);
              if (current === generation.current) { setInput(JSON.stringify(parsed, null, 2)); setFileName(file.name); }
            }
            catch (err) { if (current === generation.current) setError(err instanceof SyntaxError ? 'This file is not valid JSON. Check commas, quotes, and brackets, then try again.' : err.message); }
            event.target.value = '';
          }} /></label></div>
        <div className="input-actions secondary-actions">
          <button type="button" onClick={resetToExample} disabled={!sample || loading || running}>Reset to selected example</button>
          <button type="button" onClick={downloadExample} disabled={!sample || loading}>Download selected example JSON</button>
          <button type="button" onClick={downloadCsvTemplate} disabled={!sample || loading}>Download CSV example</button>
        </div>
        {fileName && <p className="file-ready" role="status">File ready: <strong>{fileName}</strong>. Review the JSON, then run the prediction.</p>}
        {sample && <p className="muted">{sample.evaluation_note}</p>}
      </section><section className="panel result-panel" aria-live="polite"><div className="panel-heading"><span className="panel-icon result-icon"><Cpu size={18} /></span><div><span className="section-kicker">STEP 3</span><h2>Prediction results</h2><p>Model output and review guidance appear here.</p></div></div>
        {historySaveNotice && !batchResults && <div className={`history-save-notice ${historySaveNotice.kind}`} role="status">{historySaveNotice.text}</div>}
        {error && <div className="error" role="alert"><strong>Could not run prediction</strong><p>{error}</p></div>}
        {running && <div className="running-state"><Loader2 className="spin" size={20} /><span><strong>Running prediction</strong><small>Sending your request to the selected model...</small></span></div>}
        {!result && !running && !error && <div className="empty-results"><span className="empty-icon"><Activity size={23} /></span><h3>Ready when you are</h3><p>Choose a system, review its sample data, then run a prediction to see the model output here.</p><div><CheckCircle2 size={14} /> Results come from your FastAPI model service</div></div>}
        {engineRisk && <div className="risk-summary" role="status">
          <strong>Prototype maintenance-risk band: {engineRisk}</strong>
          <span>Based on the demonstration RUL thresholds (High: 30 cycles or less; Medium: 31-60; Low: above 60). This is not an approved maintenance limit.</span>
        </div>}
        {Object.entries(predictions).map(([name, prediction]) => <Prediction key={name} name={name} result={prediction} />)}
        {result?.component === 'Fuel System' && <article className="result-card"><span className="badge review">Experimental - readiness gate failed</span>
          <p className="prediction-value">{result.latest_is_abnormal ? 'Abnormal alert' : 'No current alert'}</p>
          <p>{result.flagged_samples} of {result.input_samples} samples flagged</p><p>Latest anomaly margin: {format(result.latest_anomaly_margin)}</p>
          {result.largest_normal_envelope_deviations?.length > 0 && <details className="model-explanation"><summary>Largest departures from the normal envelope</summary>
            <p className="muted">Scaled differences from this model's normal-data reference; these are not proof of a fault or its cause.</p>
            <ul>{result.largest_normal_envelope_deviations.map(item => <li key={item.feature}><span>{label(item.feature)}</span><span className="importance-track"><i style={{ width: `${Math.min(100, item.scaled_deviation * 20)}%` }} /></span><strong>{format(item.scaled_deviation)} scale</strong></li>)}</ul>
          </details>}
          <p className="muted">A missing alert does not establish a healthy fuel system.
            {fuelMetrics ? ` Nested development detection: ${format(fuelMetrics.abnormal_detection_rate * 100)}%; false alarms: ${format(fuelMetrics.normal_false_alarm_rate * 100)}%.` : ' Detection remains limited; independent mission validation is unresolved.'}</p></article>}
        {result?.warnings?.map((warning, index) => <p className="notice" key={index}>{warning}</p>)}
        {result && <ResultMeaning component={component} />}
        {result && <div className="input-actions report-actions"><button type="button" onClick={downloadPredictionReport} disabled={reportSaving || !runRecord}>{reportSaving ? 'Preparing report...' : 'Download prediction report (.json)'}</button><span className="muted">Includes model/check details and an input hash, not raw sensor values.</span></div>}
        {reportError && <p className="error" role="alert">{reportError}</p>}
        {matchesSample && <details><summary>Reference labels for this dataset example</summary><pre>{JSON.stringify(sample.actual, null, 2)}</pre></details>}
        {result && <details><summary>Complete backend response</summary><pre>{JSON.stringify(result, null, 2)}</pre></details>}
      </section></div>
      {(result || batchResults) && <section className="panel result-download-footer" aria-label="Download AI prediction results">
        <div className="panel-heading"><span className="panel-icon result-icon"><Download size={18} /></span><div><span className="section-kicker">DOWNLOAD</span><h2>Save these results</h2><p>Download the prediction report for the results currently shown above.</p></div></div>
        <div className="input-actions">{result && <button type="button" onClick={downloadPredictionReport} disabled={reportSaving || !runRecord}>{reportSaving ? 'Preparing report...' : 'Download prediction report (.json)'}</button>}
          {batchResults && <button type="button" className="quality-continue" onClick={downloadBatchReport}>Download all-components report (.json)</button>}</div>
      </section>}
    </main>
  </div>;
}
