// Tests for the /admin Agendas tab summary (api/_agendas.js). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const {summarize} = require('../_agendas');

const now = new Date('2026-10-22T18:00:00Z');
const ago = h => new Date(now - h * 3600e3).toISOString();

test('quiet when the latest inbox run is recent and nothing is open', () => {
  const runs = [{status: 'ok', started_at: ago(0.4), finished_at: ago(0.3), notes: 'mode: inbox'}];
  const s = summarize({runs, counts: {}, now});
  assert.deepEqual(s.problems, []);
  assert.equal(s.last_inbox, runs[0]);
});

test('never run, failed, stale, sweeps only, open errors, unmatched mail', () => {
  assert.match(summarize({runs: [], now}).problems[0].text, /never run/);
  const p = summarize({runs: [{status: 'failed', notes: 'FAILED: boom', started_at: ago(30)}], counts: {unmatched: 2}, openErrors: 3, now}).problems.map(x => x.text);
  assert.equal(p.length, 5);
  assert.match(p[0], /last run failed: FAILED: boom/);
  assert.match(p[1], /No agenda run in 30 hours/);
  assert.match(p[2], /No inbox check/);
  assert.match(p[3], /3 unresolved/);
  assert.match(p[4], /2 emails/);
});
