// Tests for the ingestion health check (api/_health.js) and the /admin email previews (api/_previews.js). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
process.env.ALERTS_SECRET = 'test-secret';
const {assess} = require('../_health');
const {preview, PREVIEWS} = require('../_previews');
const {confirmEmail, digestEmail} = require('../_emails');

const now = new Date('2026-10-22T14:00:00Z');
const hoursAgo = h => new Date(now - h * 3600e3).toISOString();

test('healthy when every latest load is ok and the last sync is recent', () => {
  const latest = [{dataset: 'votes', status: 'ok', started_at: hoursAgo(8)}, {dataset: 'contracts', status: 'ok', started_at: hoursAgo(8)}];
  assert.deepEqual(assess({latest, lastOk: hoursAgo(8), now}), []);
});

test('flags failed, stuck and stale loads', () => {
  const latest = [{dataset: 'votes', status: 'failed', notes: 'column "x" does not exist', started_at: hoursAgo(8)},
    {dataset: 'meetings', status: 'running', started_at: hoursAgo(5)}];
  const p = assess({latest, lastOk: hoursAgo(50), now});
  assert.equal(p.length, 3);
  assert.match(p[0].text, /No successful database sync in 50 hours/);
  assert.match(p[1].text, /votes failed to load: column "x"/);
  assert.match(p[2].text, /meetings has been "running" for 5 hours/);
  assert.match(assess({latest: [], lastOk: null, now})[0].text, /No successful database sync/);
});

test('flags alert email failures and an unprocessed backlog', () => {
  const p = assess({latest: [], lastOk: hoursAgo(1), now, outboxFailed: 2, eventsBacklog: 1});
  assert.equal(p.length, 2);
  assert.match(p[0].text, /2 rule-alert emails failed/);
  assert.match(p[1].text, /1 new record older than 2 days/);
});

test('digestEmail skips quiet weeks and widens on request', () => {
  const g = {key: 'lh', name: 'Lynn Haven', slug: 'lynn-haven', changes: [{date: '2026-09-20', title: 'Votes', text: 'New votes', url: 'https://baycounty.me/x'}], meetings: []};
  assert.equal(digestEmail(g, {now: now.getTime()}), null);
  const m = digestEmail(g, {now: now.getTime(), days: 60});
  assert.equal(m.subject, 'Lynn Haven this week on BayCounty.me');
  assert.match(m.html, /\{\{\{RESEND_UNSUBSCRIBE_URL\}\}\}/, 'live digest keeps the broadcast placeholder');
});

test('previews match the live builders and have inert links', async () => {
  const live = confirmEmail({what: 'weekly BayCounty.me updates for Lynn Haven', isRule: false, link: 'https://baycounty.me/api/confirm?t=preview-only'});
  const pv = await preview('confirm_digest', {gov: 'lh'});
  assert.equal(pv.html, live.html);
  for (const t of PREVIEWS.filter(x => x.id !== 'digest')) {
    const m = await preview(t.id, {gov: 'pcb'});
    assert.ok(m.subject, t.id);
    assert.doesNotMatch(m.html + m.text, /example\.com|RESEND_UNSUBSCRIBE_URL|contact\.prefs_token/, `${t.id} has a live or placeholder link`);
  }
  await assert.rejects(preview('nope'), /Unknown email/);
});
