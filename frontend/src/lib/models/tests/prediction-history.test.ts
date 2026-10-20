// Ported from tests/frontend_prediction_history.test.mjs (TypeScript, run with `npm test`).
import test from 'node:test';
import assert from 'node:assert/strict';
import { predictionNeedsReview as needsReview, summarizeHistoryPrediction as summarize } from '../prediction-history.ts';
import type { PredictionResponse } from '../types.ts';

// Tests pass deliberately partial responses.
const summarizeHistoryPrediction = (component: string, data: object) => summarize(component, data as PredictionResponse);
const predictionNeedsReview = (component: string, data: object) => needsReview(component, data as PredictionResponse);

test('history summaries retain subsystem-specific units and useful results', () => {
  assert.match(summarizeHistoryPrediction('engine', { rul: { value: 12, unit: 'cycles' } }), /12 cycles/);
  assert.match(summarizeHistoryPrediction('battery', { soh: { value: 91 }, rul: { value: 8, unit: 'cycles' } }), /91%.*8 cycles/);
  assert.match(summarizeHistoryPrediction('hydraulic', { predictions: { cooler_condition_percent: { label: '100%' } } }), /cooler condition percent: 100%/);
  assert.match(summarizeHistoryPrediction('landing-gear', { fault: { label: 'normal' }, rul: { value: 75 } }), /normal.*75 percent/);
  assert.match(summarizeHistoryPrediction('fuel-system', { flagged_samples: 2, input_samples: 10, latest_is_abnormal: true }), /2 of 10 samples flagged/);
});

test('review state follows model acceptance and keeps experimental fuel under review', () => {
  assert.equal(predictionNeedsReview('engine', { rul: { accepted: true } }), false);
  assert.equal(predictionNeedsReview('engine', { rul: { accepted: false } }), true);
  assert.equal(predictionNeedsReview('battery', { soh: { accepted: true }, rul: { accepted: false } }), true);
  assert.equal(predictionNeedsReview('hydraulic', { predictions: { valve: { accepted: true }, pump: { accepted: false } } }), true);
  assert.equal(predictionNeedsReview('landing-gear', { fault: { accepted: true }, rul: { accepted: true } }), false);
  assert.equal(predictionNeedsReview('fuel-system', { latest_is_abnormal: false }), true);
});

test('history summaries reject unsupported subsystem names', () => {
  assert.throws(() => summarizeHistoryPrediction('avionics', {}), /Unknown prediction-history component/);
});
