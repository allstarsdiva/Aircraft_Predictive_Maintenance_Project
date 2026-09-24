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
  await until(async () => (await body()).includes('Backend connected'), 'backend evidence');
  for (const component of ['Engine', 'Battery', 'Hydraulic', 'Landing gear', 'Fuel system']) {
    await evaluate(`Array.from(document.querySelectorAll('nav button')).find(b => b.querySelector('strong').textContent === ${JSON.stringify(component)}).click()`);
    await until(() => evaluate("Boolean(document.querySelector('textarea')?.value) && !document.querySelector('button.primary').disabled"), `${component} sample`);
    await evaluate("document.querySelector('button.primary').click()");
    await until(() => evaluate("Boolean(document.querySelector('.result-card'))"), `${component} prediction`);
    if (await evaluate("Boolean(document.querySelector('[role=alert]'))")) throw new Error(`${component} returned a UI error`);
    checks.push(`${component}: sample -> backend -> result rendered`);
  }
  await evaluate("Array.from(document.querySelectorAll('nav button')).find(b => b.querySelector('strong').textContent === 'Hydraulic').click()");
  await until(() => evaluate("Boolean(document.querySelector('textarea')?.value) && !document.querySelector('button.primary').disabled"), 'hydraulic sample');
  await evaluate("const s=document.querySelector('select'); s.value='challenge'; s.dispatchEvent(new Event('change',{bubbles:true}))");
  await until(() => evaluate("document.querySelector('textarea')?.value.includes('\"operating_condition_stable\": false')"), 'unstable sample');
  await evaluate("document.querySelector('button.primary').click()");
  await until(() => evaluate("document.querySelectorAll('.result-card .review').length === 4"), 'all unstable outputs rejected');
  checks.push('Unstable hydraulic: all four outputs require review');
  await evaluate("const t=document.querySelector('textarea'); Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(t,'{ invalid'); t.dispatchEvent(new Event('input',{bubbles:true}))");
  await evaluate("document.querySelector('button.primary').click()");
  await until(() => evaluate("Boolean(document.querySelector('[role=alert]'))"), 'invalid JSON error');
  if (await evaluate("Boolean(document.querySelector('.result-card'))")) throw new Error('Stale prediction visible after editing input');
  checks.push('Invalid JSON: useful error and stale result cleared');
  await evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Open simulated visual demo').click()");
  await until(async () => (await body()).includes('SIMULATED VISUAL DEMO'), 'simulation label');
  checks.push('Legacy visual dashboard explicitly labeled simulated');
  await evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Back to backend predictions').click()");
  await evaluate("Array.from(document.querySelectorAll('nav button')).find(b => b.querySelector('strong').textContent === 'Landing gear').click()");
  await until(() => evaluate("Boolean(document.querySelector('textarea')?.value) && !document.querySelector('button.primary').disabled"), 'final example');
  await evaluate("document.querySelector('button.primary').click()");
  await until(() => evaluate("document.querySelectorAll('.result-card').length === 2"), 'final result');
  await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  const screenshot = await call('Page.captureScreenshot', { format: 'png' });
  await mkdir('reports/figures', { recursive: true });
  await writeFile('reports/figures/model-workspace.png', Buffer.from(screenshot.data, 'base64'));
  await call('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  const overflow = await evaluate('document.documentElement.scrollWidth > innerWidth + 1');
  if (overflow) throw new Error('Mobile layout overflows viewport');
  checks.push('390px mobile layout: no horizontal overflow');
  await call('Network.enable');
  await call('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0 });
  await evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Reconnect / reload').click()");
  await until(() => evaluate("Boolean(document.querySelector('[role=alert]'))"), 'offline error');
  if (await evaluate("Boolean(document.querySelector('.result-card'))")) throw new Error('Stale prediction visible after disconnect');
  checks.push('Backend unavailable: error shown and previous prediction cleared');
  if (errors.length) throw new Error(`Browser runtime errors: ${errors.join('; ')}`);
  await mkdir('reports/metrics', { recursive: true });
  const result = { passed: true, checks, runtime_errors: errors, browser: 'Installed Microsoft Edge (headless)' };
  await writeFile('reports/metrics/workspace_browser_check.json', JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
} finally {
  socket?.close();
  browser.kill();
}
