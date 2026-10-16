const encoder = new TextEncoder();

export async function sha256Text(value) {
  if (!globalThis.crypto?.subtle) throw new Error('This browser does not support secure report hashing.');
  const bytes = await globalThis.crypto.subtle.digest('SHA-256', encoder.encode(value));
  return [...new Uint8Array(bytes)].map(byte => byte.toString(16).padStart(2, '0')).join('');
}

export async function makePredictionReport({ component, title, releaseId, requestText, inputSummary, source, preflight, prediction }) {
  return {
    report_schema: 'aircraft-predictive-maintenance-prediction-report/v1',
    created_at_utc: new Date().toISOString(),
    component,
    component_title: title,
    model_release: releaseId || 'unavailable',
    model: prediction?.model || prediction?.rul_model || prediction?.fault_model || prediction?.soh_model || 'not reported by API',
    input: {
      source: source || 'user supplied',
      summary: inputSummary || 'Request summary unavailable',
      sha256: await sha256Text(requestText),
      raw_sensor_values_included: false,
    },
    preflight,
    prediction,
    limitations: [
      'Research prototype output only; not approved for aircraft maintenance decisions.',
      'The input digest identifies the exact request text but cannot reconstruct it.',
      'A report export is an audit convenience, not independent model validation.',
    ],
  };
}
