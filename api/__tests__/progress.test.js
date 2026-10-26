// Import progress (api/_progress.js): the numbers behind /data-sources#progress, /api/v1/import-progress and /admin.
const test = require('node:test');
const assert = require('node:assert/strict');
const {summarize} = require('../_progress');

const NOW = '2026-10-26T12:00:00Z';
const rows = [
  {board: 'pc', year: 2016, listed: 20, captured: 20, read: 20, motions: 300, passed: 280, flagged: 5, reviewed: 15, pages: 400, ocr_pages: 400},
  {board: 'pc', year: 2017, listed: 22, captured: 10, read: 4, reading: 2, motions: 50, passed: 50},
  {board: 'schools', year: 2016, listed: 0},
  {board: 'schools', year: 2024, listed: null, captured: 3},   // captured by the watcher, archive not counted
  {board: 'pc', year: 2015, listed: 9},                         // before the site's first year: ignored
];

test('totals, stages and the board-year grid', () => {
  const d = summarize(rows, [], {now: NOW});
  assert.equal(d.totals.found, 45);
  assert.equal(d.totals.captured, 33);
  assert.equal(d.totals.read, 24);
  assert.equal(d.totals.gaps, 1);
  assert.equal(d.phase.key, 'capturing');
  assert.deepEqual(d.stages.map(s => s.key), ['found', 'captured', 'read', 'checked']);
  assert.equal(d.stages[3].value, 280 + 50 + 15);
  const pc = d.boards.find(b => b.board === 'pc');
  assert.equal(pc.years[0].state, 'reviewing');
  assert.equal(pc.years[1].state, 'reading');
  const sb = d.boards.find(b => b.board === 'schools');
  assert.equal(sb.years.find(y => y.year === 2016).state, 'none_online');
  assert.equal(sb.years.find(y => y.year === 2024).state, 'captured');
  assert.equal(sb.years.find(y => y.year === 2020).state, 'not_listed');
  assert.equal(d.years[0], 2016);
  assert.equal(d.years.at(-1), 2026);
  assert.equal(d.cost, undefined);   // the public answer never carries costs
});

test('time left uses the last week’s pace once reads exist, the schedule before', () => {
  assert.equal(summarize(rows, [], {now: NOW}).eta.basis, 'schedule');
  const fast = summarize(rows.map(r => r.board === 'pc' && r.year === 2016 ? {...r, read_7d: 70} : r), [], {now: NOW});
  assert.equal(fast.eta.basis, 'pace');
  assert.equal(fast.eta.per_day, 10);
  assert.equal(fast.eta.days, Math.ceil(fast.eta.files_left / 10));
});

test('admin cost estimate', () => {
  const d = summarize(rows, [], {now: NOW, cost: {spent: 1.5, in_flight: 0.5, avg: 0, budget: 150}});
  assert.equal(d.cost.avg_basis, 'estimate');
  assert.equal(d.cost.left, Math.round((45 - 24 - 2) * 0.04 * 100) / 100);
  assert.equal(d.cost.total, Math.round((2 + d.cost.left) * 100) / 100);
});

test('runs: only minutes crawls and reads', () => {
  const runs = [{dataset: 'agenda_documents', notes: 'minutes backfill: 3 new', status: 'ok', started_at: NOW},
    {dataset: 'agenda_documents', notes: '1 notice(s); 0 new', status: 'ok', started_at: NOW},
    {dataset: 'minutes_votes', notes: 'model: x', status: 'running', started_at: NOW}];
  const d = summarize(rows, runs, {now: NOW});
  assert.deepEqual(d.runs.map(r => r.kind), ['crawl', 'read']);
  assert.ok(!('notes' in d.runs[0]));
});

test('nothing yet', () => {
  const d = summarize([], [], {now: NOW});
  assert.equal(d.phase.key, 'not_started');
  assert.equal(d.boards.length, 0);
});
