// Exercise the actual React application in the installed headless Edge browser.
// Uses Node's built-in WebSocket/CDP support; no downloaded browser dependency.
import { spawn } from 'node:child_process';
import { mkdtemp, readFile, writeFile, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const baseURL = process.argv[2] || 'http://127.0.0.1:4173';
const profile = await mkdtemp(join(tmpdir(), 'aircraft-browser-check-'));
const browser = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'],
  { windowsHide: true, stdio: 'ignore' });
let startupError;
browser.on('error', error => { startupError = error; });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(action, description, timeout = 25000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    if (startupError) throw startupError;
    const result = await action();
    if (result) return result;
    await pause(150);
  }
  throw new Error(`Timed out: ${description}`);
}
let socket;
const checks = [];
const errors = [];
try {
  const port = await until(async () => {
    try { return (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; }
    catch { return null; }
  }, 'browser startup');
  const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const target = pages.find(page => page.type === 'page');
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let sequence = 0;
  const pending = new Map();
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
    if (message.id) {
      const request = pending.get(message.id);
      if (request) { pending.delete(message.id); message.error ? request.reject(message.error) : request.resolve(message.result); }
    }
  };
  const call = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++sequence; pending.set(id, { resolve, reject }); socket.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async expression => {
    const response = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (response.exceptionDetails) throw new Error(JSON.stringify(response.exceptionDetails));
    return response.result.value;
  };
  const body = () => evaluate('document.body.innerText');
  await call('Runtime.enable'); await call('Page.enable');
  await call('Page.navigate', { url: baseURL });
  await until(async () => (await body()).includes('Prediction service connected'), 'backend evidence');
  await until(async () => (await body()).includes('Important model limitations'), 'visible model-limitations summary');
  const limitationText = (await body()).toLowerCase();
  if (!limitationText.includes('intervals') || !limitationText.includes('hydraulic valve') || !limitationText.includes('fuel anomaly')) {
    throw new Error('The evidence summary is missing component-specific limitations');
  }
  checks.push('AI Predictions: saved-audit caveats for external validation, battery intervals, hydraulic valve, and fuel are visible before input');
  for (const component of ['Engine', 'Battery', 'Hydraulic', 'Landing gear', 'Fuel system']) {
    await evaluate(`Array.from(document.querySelectorAll('.component-tabs button')).find(b => b.querySelector('strong').textContent === ${JSON.stringify(component)}).click()`);
    await until(() => evaluate("Boolean(document.querySelector('textarea')?.value) && !document.querySelector('.workspace-grid button.primary').disabled"), `${component} sample`);
    await evaluate("document.querySelector('.workspace-grid .input-acknowledgement input').click()");
    await evaluate("document.querySelector('.workspace-grid button.primary').click()");
    await until(() => evaluate("Boolean(document.querySelector('.workspace-grid .result-panel .result-card') || document.querySelector('.workspace .input-quality-report'))"), `${component} preflight or result`);
    if (await evaluate("Boolean(document.querySelector('.workspace .quality-continue'))")) await evaluate("document.querySelector('.workspace .quality-continue').click()");
    await until(() => evaluate("Boolean(document.querySelector('.result-card'))"), `${component} prediction`);
    if (await evaluate("Boolean(document.querySelector('[role=alert]'))")) throw new Error(`${component} returned a UI error`);
    checks.push(`${component}: sample -> backend -> result rendered`);
  }
  await evaluate("(async()=>{const keys=['engine','battery','hydraulic','landing-gear','fuel-system'];const rows=await Promise.all(keys.map(async key=>[key,(await (await fetch('/api/workspace/examples/'+key+'?variant=normal')).json()).payload]));const input=document.querySelector('.bulk-actions input[type=file]');const transfer=new DataTransfer();transfer.items.add(new File([JSON.stringify(Object.fromEntries(rows))],'preflight-bundle.json',{type:'application/json'}));input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));return true})()");
  await until(() => evaluate("document.body.innerText.includes('preflight-bundle.json')"), 'all-components file import');
  await evaluate("document.querySelector('.all-components-panel .input-acknowledgement input').click()");
  await evaluate("document.querySelector('.bulk-actions button.primary').click()");
  await until(() => evaluate("document.querySelectorAll('.batch-quality-grid .input-quality-report').length === 5"), 'all-components quality checks');
  await until(() => evaluate("Boolean(document.querySelector('.batch-quality .quality-continue'))"), 'all-components review confirmation');
  await evaluate("document.querySelector('.batch-quality .quality-continue').click()");
  await until(() => evaluate("document.querySelectorAll('.bulk-results .bulk-result').length === 5"), 'all-components predictions');
  if (await evaluate("document.querySelectorAll('.bulk-results .bulk-result.success').length !== 5")) throw new Error('All-components predictions did not all complete after preflight');
  checks.push('All-components upload: five schema/support checks, explicit review, then five predictions');
  await evaluate("Array.from(document.querySelectorAll('.component-tabs button')).find(b => b.querySelector('strong').textContent === 'Hydraulic').click()");
  await until(() => evaluate("Boolean(document.querySelector('textarea')?.value) && !document.querySelector('.workspace-grid button.primary').disabled"), 'hydraulic sample');
  await evaluate("const s=document.querySelector('select'); s.value='challenge'; s.dispatchEvent(new Event('change',{bubbles:true}))");
  await until(() => evaluate("document.querySelector('textarea')?.value.includes('\"operating_condition_stable\": false')"), 'unstable sample');
  await evaluate("document.querySelector('.workspace-grid .input-acknowledgement input').click()");
  await evaluate("document.querySelector('.workspace-grid button.primary').click()");
  await until(() => evaluate("Boolean(document.querySelector('.workspace .quality-continue') || document.querySelectorAll('.result-card .review').length === 4)"), 'hydraulic preflight review');
  if (await evaluate("Boolean(document.querySelector('.workspace .quality-continue'))")) await evaluate("document.querySelector('.workspace .quality-continue').click()");
  await until(() => evaluate("document.querySelectorAll('.result-card .review').length === 4"), 'all unstable outputs rejected');
  checks.push('Unstable hydraulic: all four outputs require review');
  await evaluate("const t=document.querySelector('textarea'); Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(t,'{ invalid'); t.dispatchEvent(new Event('input',{bubbles:true}))");
  if (!await evaluate("document.querySelector('.workspace-grid button.primary').disabled")) throw new Error('Prediction button should remain disabled until the edited request is acknowledged');
  if (await evaluate("Boolean(document.querySelector('.result-card'))")) throw new Error('Stale prediction visible after editing input');
  checks.push('Invalid JSON: useful error and stale result cleared');
  await evaluate("Array.from(document.querySelectorAll('nav button')).find(b => b.textContent.trim() === 'Fleet').click()");
  await until(async () => { const text = await body(); return text.includes('Fleet health overview') && text.includes('5 / 5'); }, 'Fleet health snapshot');
  if (await evaluate("/AC-1000|N[0-9]{3}(AA|DL|UA)/.test(document.body.innerText)")) throw new Error('Generated aircraft identifiers remain visible in Fleet');
  await until(() => evaluate("document.querySelectorAll('svg.recharts-surface').length >= 1"), 'Fleet model-check chart');
  const fleetText = await body();
  if (!fleetText.toLowerCase().includes('aircraft connected') || !fleetText.toLowerCase().includes('not available')) throw new Error('Fleet health summary is missing its explicit no-aircraft status');
  checks.push('Fleet: distinct fleet-health summary, honest no-aircraft status, and model-check chart');
  await evaluate("Array.from(document.querySelectorAll('nav button')).find(b => b.textContent.trim() === 'Maintenance').click()");
  await until(async () => (await body()).includes('Component attention levels'), 'component maintenance triage');
  await until(() => evaluate("document.querySelectorAll('.model-output-graphic').length === 5 && document.querySelectorAll('svg.recharts-surface').length >= 4"), 'all maintenance graphs');
  if (await evaluate("document.querySelectorAll('.model-output-graphic').length !== 5 || document.querySelectorAll('svg.recharts-surface').length < 4")) throw new Error('Maintenance view is missing one or more subsystem graphs');
  if (await evaluate("!document.body.innerText.includes('Critical') || !document.body.innerText.includes('Caution')")) throw new Error('Maintenance critical/caution groups are not rendered');
  await until(() => evaluate("document.querySelectorAll('details.model-input-details').length === 5"), 'component input detail panels');
  await evaluate("document.querySelectorAll('details.model-input-details').forEach(d => d.open = true)");
  if (await evaluate("document.querySelectorAll('details.model-input-details[open]').length !== 5 || !document.body.innerText.toLowerCase().includes('data sent to the model') || !document.body.innerText.toLowerCase().includes('model features and sub-models')")) throw new Error('Maintenance component inputs/features did not expand');
  checks.push('Maintenance: Critical/Caution/Monitor sections, five graphs, and expandable real input/model-feature details');
  await evaluate("Array.from(document.querySelectorAll('nav button')).find(b => b.textContent.trim() === 'AI Predictions').click()");
  await evaluate("Array.from(document.querySelectorAll('.component-tabs button')).find(b => b.querySelector('strong').textContent === 'Landing gear').click()");
  await until(() => evaluate("Boolean(document.querySelector('textarea')?.value) && !document.querySelector('.workspace-grid button.primary').disabled"), 'final example');
  await evaluate("document.querySelector('.workspace-grid .input-acknowledgement input').click()");
  await evaluate("document.querySelector('.workspace-grid button.primary').click()");
  await until(() => evaluate("document.querySelectorAll('.result-card').length === 2"), 'final result');
  await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  const screenshot = await call('Page.captureScreenshot', { format: 'png' });
  await mkdir('reports/figures', { recursive: true });
  await writeFile('reports/figures/model-workspace-20260930.png', Buffer.from(screenshot.data, 'base64'));
  await call('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  const overflow = await evaluate('document.documentElement.scrollWidth > innerWidth + 1');
  if (overflow) throw new Error('Mobile layout overflows viewport');
  checks.push('390px mobile layout: no horizontal overflow');
  await call('Network.enable');
  await call('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0 });
  await evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Check connection')).click()");
  await until(() => evaluate("Boolean(document.querySelector('[role=alert]'))"), 'offline error');
  if (await evaluate("Boolean(document.querySelector('.result-card'))")) throw new Error('Stale prediction visible after disconnect');
  checks.push('Backend unavailable: error shown and previous prediction cleared');
  if (errors.length) throw new Error(`Browser runtime errors: ${errors.join('; ')}`);
  await mkdir('reports/metrics', { recursive: true });
  const result = { passed: true, checks, runtime_errors: errors, browser: 'Installed Microsoft Edge (headless)' };
  await writeFile('reports/metrics/workspace_browser_check_20260930.json', JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
} finally {
  socket?.close();
  browser.kill();
}
