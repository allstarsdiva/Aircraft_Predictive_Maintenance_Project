import React, { Suspense, lazy, useEffect, useRef, useState } from 'react';
import './workspace.css';

const SimulatedDashboard = lazy(() => import('../aircraft-maintenance-dashboard-enhanced.jsx'));
const COMPONENTS = [
  ['engine', 'Engine', 'RUL in cycles'], ['battery', 'Battery', 'SOH & remaining cycles'],
  ['hydraulic', 'Hydraulic', 'Four condition classifiers'],
  ['landing-gear', 'Landing gear', 'Fault & remaining life'],
  ['fuel-system', 'Fuel system', 'Experimental anomaly alerts'],
];
const ENDPOINTS = Object.fromEntries(COMPONENTS.map(([key]) => [key,
  key === 'fuel-system' ? '/api/predict/fuel-system' : `/api/v2/predict/${key}`]));
const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const format = value => typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 3 }) : String(value);
const label = text => text.replaceAll('_', ' ');

async function request(path, options = {}) {
  const response = await fetch(BASE + path, options);
  const text = await response.text();
  let body;
  try { body = JSON.parse(text); } catch { throw new Error('Backend returned a non-JSON response. Check the API address.'); }
  if (!response.ok) throw new Error(`${response.status}: ${typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || body)}`);
  return body;
}

function Prediction({ name, result }) {
  return <article className="result-card">
    <div className="card-heading"><span>{label(name)}</span><span className={`badge ${result.accepted ? 'accepted' : 'review'}`}>
      {result.accepted ? 'Passes model rule' : 'Engineering review required'}</span></div>
    <p className="prediction-value">{format(result.value)} <small>{result.unit || result.label || 'class'}</small></p>
    {result.lower !== undefined && <p>Estimated interval: {format(result.lower)} to {format(result.upper)} {result.unit}
      <span className="muted"> · nominal {format(result.interval_level * 100)}%; observed coverage may be lower</span></p>}
    {result.calibrated_confidence !== undefined && <p>Development confidence estimate: {format(result.calibrated_confidence * 100)}%</p>}
    {result.input_support?.hard_range_violations?.length > 0 && <p className="alert-text">Outside training range: {result.input_support.hard_range_violations.join(', ')}</p>}
    {result.input_support?.tail_range_warnings?.length > 0 && <details><summary>Unusual input values</summary>{result.input_support.tail_range_warnings.join(', ')}</details>}
  </article>;
}

export default function ModelWorkspace() {
  const [component, setComponent] = useState('engine');
  const [variant, setVariant] = useState('normal');
  const [sample, setSample] = useState(null);
  const [input, setInput] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [evidence, setEvidence] = useState(null);
  const [evidenceError, setEvidenceError] = useState('');
  const [reload, setReload] = useState(0);
  const [mode, setMode] = useState('live');
  const generation = useRef(0);
  const controller = useRef(null);

  useEffect(() => {
    const abort = new AbortController();
    setEvidence(null); setEvidenceError('');
    request('/api/workspace/evidence', { signal: abort.signal }).then(setEvidence).catch(err => {
      if (err.name !== 'AbortError') setEvidenceError(err.message);
    });
    return () => abort.abort();
  }, [reload]);

  useEffect(() => {
    generation.current += 1;
    controller.current?.abort();
    const abort = new AbortController();
    setLoading(true); setRunning(false); setSample(null); setInput(''); setResult(null); setError('');
    request(`/api/workspace/examples/${component}?variant=${variant}`, { signal: abort.signal })
      .then(data => { setSample(data); setInput(JSON.stringify(data.payload, null, 2)); })
      .catch(err => { if (err.name !== 'AbortError') setError(err.message); })
      .finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => { abort.abort(); controller.current?.abort(); };
  }, [component, variant, reload]);

  function edit(value) {
    generation.current += 1; controller.current?.abort(); setRunning(false);
    setInput(value); setResult(null); setError('');
  }

  async function predict() {
    setError(''); setResult(null);
    const current = ++generation.current;
    try {
      const payload = JSON.parse(input);
      if (!payload || Array.isArray(payload) || typeof payload !== 'object') throw new Error('Input must be a JSON object.');
      controller.current = new AbortController(); setRunning(true);
      const data = await request(ENDPOINTS[component], { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload), signal: controller.current.signal });
      if (current === generation.current) setResult(data);
    } catch (err) { if (current === generation.current && err.name !== 'AbortError') setError(err.message); }
    finally { if (current === generation.current) setRunning(false); }
  }

  const matchesSample = sample && input === JSON.stringify(sample.payload, null, 2);
  const fuelMetrics = evidence?.fuel_evaluation?.metrics;
  const predictions = result?.predictions || Object.fromEntries(['rul', 'soh', 'fault'].filter(key => result?.[key]).map(key => [key, result[key]]));
  return <div className="workspace">
    <header className="workspace-header"><div><div className="eyebrow">AIRCRAFT PREDICTIVE MAINTENANCE</div><h1>Model workspace</h1></div>
      <button onClick={() => setMode(mode === 'live' ? 'simulation' : 'live')}>{mode === 'live' ? 'Open simulated visual demo' : 'Back to backend predictions'}</button></header>
    {mode === 'simulation' ? <><p className="notice">SIMULATED VISUAL DEMO · Aircraft, telemetry and predictions below are generated locally. Use the model workspace for backend results.</p>
      <Suspense fallback={<p>Loading visual demo...</p>}><SimulatedDashboard /></Suspense></> : <main>
      <div className="notice">Research candidate · Model acceptance is a development rule, not approval for maintenance use. Fuel remains experimental.</div>
      <section className="connection"><span className={`dot ${evidence ? 'online' : ''}`} />
        <span>{evidence ? `Backend connected · ${evidence.release_id}` : 'Backend evidence unavailable'}</span>
        <button onClick={() => setReload(value => value + 1)}>Reconnect / reload</button></section>
      {evidenceError && <div role="alert" className="error">{evidenceError}<p>Start the backend with: <code>.\.venv\Scripts\python.exe -m uvicorn src.api.app:app --reload</code></p></div>}
      <nav className="component-tabs" aria-label="Aircraft subsystem">{COMPONENTS.map(([key, title, subtitle]) =>
        <button key={key} aria-pressed={component === key} onClick={() => setComponent(key)}><strong>{title}</strong><small>{subtitle}</small></button>)}</nav>
      <div className="workspace-grid"><section className="panel">
        <div className="card-heading"><h2>Input data</h2><select aria-label="Dataset example" value={variant} onChange={event => setVariant(event.target.value)}>
          <option value="normal">Example A{component === 'hydraulic' ? ' (stable)' : ''}</option><option value="challenge">Example B{component === 'hydraulic' ? ' (unstable)' : ''}</option></select></div>
        <p className="muted">{loading ? 'Loading dataset example...' : matchesSample ? sample.source : 'Custom input - reference labels do not apply'}</p>
        <label className="input-label" htmlFor="model-input">Prediction request JSON</label>
        <textarea id="model-input" spellCheck="false" value={input} onChange={event => edit(event.target.value)} placeholder="Load an example or paste your request JSON" />
        <div className="input-actions"><button className="primary" onClick={predict} disabled={loading || running || !input.trim()}>{running ? 'Running model...' : 'Run prediction'}</button>
          <label className="upload">Import JSON<input aria-label="Import request JSON" type="file" accept=".json,application/json" onChange={async event => {
            const file = event.target.files?.[0]; if (!file) return;
            const current = generation.current;
            try { if (file.size > 5_000_000) throw new Error('Choose a JSON file smaller than 5 MB.'); const text = await file.text(); JSON.parse(text); if (current === generation.current) edit(text); }
            catch (err) { if (current === generation.current) setError(err.message); }
            event.target.value = '';
          }} /></label></div>
        {sample && <p className="muted">{sample.evaluation_note}</p>}
      </section><section className="panel" aria-live="polite"><h2>Prediction results</h2>
        {error && <div className="error" role="alert">{error}</div>}
        {!result && <p className="muted">{running ? 'Waiting for the backend model...' : 'Run a prediction to see model output, uncertainty and review decisions.'}</p>}
        {Object.entries(predictions).map(([name, prediction]) => <Prediction key={name} name={name} result={prediction} />)}
        {result?.component === 'Fuel System' && <article className="result-card"><span className="badge review">Experimental - readiness gate failed</span>
          <p className="prediction-value">{result.latest_is_abnormal ? 'Abnormal alert' : 'No current alert'}</p>
          <p>{result.flagged_samples} of {result.input_samples} samples flagged</p><p>Latest anomaly margin: {format(result.latest_anomaly_margin)}</p>
          <p className="muted">A missing alert does not establish a healthy fuel system.
            {fuelMetrics ? ` Nested development detection: ${format(fuelMetrics.abnormal_detection_rate * 100)}%; false alarms: ${format(fuelMetrics.normal_false_alarm_rate * 100)}%.` : ' Detection remains limited; independent mission validation is unresolved.'}</p></article>}
        {result?.warnings?.map((warning, index) => <p className="notice" key={index}>{warning}</p>)}
        {matchesSample && <details><summary>Reference labels for this dataset example</summary><pre>{JSON.stringify(sample.actual, null, 2)}</pre></details>}
        {result && <details><summary>Complete backend response</summary><pre>{JSON.stringify(result, null, 2)}</pre></details>}
      </section></div>
      {evidence && <section className="panel audit"><h2>Finalization audit</h2><p className="muted">{evidence.audit.scope}</p>
        <div className="table-scroll"><table><thead><tr><th>Task</th><th>Separate evaluation</th><th>Coverage / acceptance</th></tr></thead><tbody>
          {Object.entries(evidence.audit.tasks).map(([key, task]) => { const m = task.evaluation_metrics;
            if (key === 'fuel' && fuelMetrics) return <tr key={key}><td>fuel (nested development)</td>
              <td>Balanced accuracy {format(fuelMetrics.balanced_accuracy * 100)}%; detection {format(fuelMetrics.abnormal_detection_rate * 100)}%</td>
              <td>False alarms {format(fuelMetrics.normal_false_alarm_rate * 100)}%; readiness blocked</td></tr>;
            return <tr key={key}><td>{label(key)}</td>
            <td>{!m ? task.reason || task.status : m.mae !== undefined ? `MAE ${format(m.mae)}; RMSE ${format(m.rmse)}` : `Accuracy ${format(m.accuracy * 100)}%`}</td>
            <td>{!m ? 'Unresolved' : m.interval_coverage !== undefined ? `Interval coverage ${format(m.interval_coverage * 100)}% (nominal ${format(task.nominal_interval_level * 100)}%)` : `Accepted ${format(m.accepted_coverage * 100)}%; accuracy ${m.accepted_accuracy === null ? 'N/A (none accepted)' : format(m.accepted_accuracy * 100) + '%'}`}</td></tr>; })}
        </tbody></table></div><details><summary>Audit findings and limitations</summary><ul>{evidence.audit.findings.map(item => <li key={item}>{item}</li>)}</ul></details>
      </section>}
    </main>}
  </div>;
}
