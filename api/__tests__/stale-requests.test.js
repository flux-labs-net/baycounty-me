// Records requests drafted when an official source goes stale (data/civic/scripts/stale_requests.py -> api/_records_requests.js
// seedStale). Letters always run. The queue tests run against a real Postgres when FINANCE_TEST_DATABASE_URL is set
// (CI has one) in their own database (staletest), so they never touch the corr schema other test files rebuild.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const {execFileSync} = require('child_process');
const {compose} = require('../_stale_requests');

const gap = (site, last, extra = {}) => ({gap_id: `beach-water:${site}:${last}`, location: site === 'Bay11' ? 'Earl Gilbert Park' : 'PCB Beach Access 41',
  listed_as: site === 'Bay11' ? 'Dupont Bridge' : null, site_id: site, epa_beach_id: 'FL131708', last_record: last, expected_every_days: 14,
  last_result: 'rated Poor (990 enterococci per 100 mL)', source_url: `https://www.floridahealth.gov/beach-detail/?SPLocation=${site}`, ...extra});
const draft = gaps => ({key: 'stale-beach-water-fdoh', kind: 'stale', check: 'beach-water', check_title: 'Beach water quality samples', page: '/beaches#water',
  government: 'Florida Department of Health', government_key: 'fdoh', recipient_name: 'Public Records Coordinator, Florida Department of Health',
  recipient_email: 'PublicRecordsRequest@FLHealth.gov', contact_url: 'https://www.floridahealth.gov/public-records/', gaps});

test('beach water letter: cites Chapter 119, the last sample, where we looked, and never names an AI', () => {
  const m = compose('beach-water', 'Beach water quality samples', [gap('Bay11', '2025-05-05')]);
  assert.equal(m.subject, 'Public records request: Healthy Beaches water samples for Earl Gilbert Park');
  assert.match(m.body, /Chapter 119, Florida Statutes/);
  assert.match(m.body, /Earl Gilbert Park, listed by the state as Dupont Bridge \(EPA beach ID FL131708\): the newest sample shown is from May 5, 2025/);
  assert.match(m.body, /We were unable to locate any newer results for this site on that official source/);
  assert.match(m.body, /Where we looked: https:\/\/www\.floridahealth\.gov\/beach-detail\/\?SPLocation=Bay11/);
  assert.doesNotMatch(m.body + m.subject, /\b(AI|Claude|Anthropic|GPT|automated reader|artificial)\b/i);
  const two = compose('beach-water', 'x', [gap('Bay11', '2025-05-05'), gap('Bay5', '2025-10-27')]);
  assert.match(two.subject, /Earl Gilbert Park and PCB Beach Access 41$/);
  assert.match(two.body, /For each site, please send/);
});

test('a check without its own letter gets the plain one', () => {
  const m = compose('new-check', 'Inspection reports', [gap('Bay5', '2026-01-02')]);
  assert.equal(m.subject, 'Public records request: Inspection reports');
  assert.match(m.body, /newest record published is from January 2, 2026/);
});

test('the gap finder flags only active sites past 45 days, with the date in the gap id', () => {
  const tmp = path.join(require('os').tmpdir(), `stale-${process.pid}.json`);
  execFileSync('python3', [path.join(__dirname, '../../data/civic/scripts/stale_requests.py'), '--today', '2026-10-30', '--out', tmp], {encoding: 'utf8'});
  const f = JSON.parse(fs.readFileSync(tmp, 'utf8'));
  fs.unlinkSync(tmp);
  for (const r of f.requests) for (const g of r.gaps) {
    assert.match(g.gap_id, /^[a-z-]+:[^:]+:\d{4}-\d{2}-\d{2}$/);
    assert.ok((new Date('2026-10-30') - new Date(g.last_record)) / 864e5 > 45, g.gap_id);
    assert.match(g.source_url, /^https:\/\//);
  }
});

/* ---------- the queue, against Postgres ---------- */
const BASE = process.env.FINANCE_TEST_DATABASE_URL;
const opts = {skip: BASE ? false : 'FINANCE_TEST_DATABASE_URL not set'};
let pool, q, R;
const sent = [];

test.before(async () => {
  if (!BASE) return;
  const {Pool} = require('pg');
  const admin = new Pool({connectionString: BASE});
  await admin.query('drop database if exists staletest with (force)').catch(() => admin.query('drop database if exists staletest'));
  await admin.query('create database staletest');
  await admin.end();
  const url = BASE.replace(/\/[^/?]+(\?|$)/, '/staletest$1');
  process.env.DATABASE_URL = url;
  process.env.RESEND_FULL_KEY = 're_test';
  global.fetch = async (u, o = {}) => {
    if (String(u).endsWith('/emails') && o.method === 'POST') { sent.push(JSON.parse(o.body)); return {ok: true, status: 200, json: async () => ({id: 'out_' + sent.length})}; }
    return {ok: false, status: 404, json: async () => ({})};
  };
  pool = new Pool({connectionString: url});
  q = async (t, p = []) => (await pool.query(t, p)).rows;
  for (const f of ['0020_correspondence.sql', '0046_records_requests.sql', '0098_stale_records_requests.sql'])
    await pool.query(fs.readFileSync(path.join(__dirname, '../../db/migrations', f), 'utf8'));
  R = require('../_records_requests');
});
test.after(async () => { if (pool) await pool.end(); });

const drafts = async () => q(`select * from corr.records_requests where kind = 'stale' order by id`);

test('stale gaps become one draft, are never drafted twice, and every step is in the locked history', opts, async () => {
  let r = await R.seedStale([draft([gap('Bay11', '2025-05-05')])]);
  assert.equal(r.added.length, 1);
  let [d] = await drafts();
  assert.equal(d.status, 'draft');
  assert.deepEqual(d.gap_ids, ['beach-water:Bay11:2025-05-05']);
  assert.equal(d.recipient_email, 'PublicRecordsRequest@FLHealth.gov');

  // the same check again: nothing new
  r = await R.seedStale([draft([gap('Bay11', '2025-05-05')])]);
  assert.equal(r.added.length, 0);
  assert.equal((await drafts()).length, 1);

  // a second site goes stale: the untouched draft takes it in
  r = await R.seedStale([draft([gap('Bay11', '2025-05-05'), gap('Bay5', '2025-10-27')])]);
  assert.equal(r.updated, 1);
  [d] = await drafts();
  assert.equal(d.gap_ids.length, 2);
  assert.match(d.subject, /Earl Gilbert Park and PCB Beach Access 41/);

  // approve and send: goes to the custodian once, with a reference
  const s = await R.send({id: d.id}, 'jeremy@fluxlabs.net');
  assert.equal(s.ok, true);
  assert.deepEqual(sent.at(-1).to, ['PublicRecordsRequest@FLHealth.gov']);
  assert.match(sent.at(-1).text, /Dear Records Custodian,/);
  assert.match(sent.at(-1).text, /Ref: BCM-/);

  // the same gaps after sending: never drafted again
  r = await R.seedStale([draft([gap('Bay11', '2025-05-05'), gap('Bay5', '2025-10-27')])]);
  assert.equal(r.added.length, 0);
  assert.equal((await drafts()).length, 1);

  // a new gap (Bay5 got samples, then stopped again later) gets a new draft with just that site
  r = await R.seedStale([draft([gap('Bay11', '2025-05-05'), gap('Bay5', '2026-08-01')])]);
  assert.equal(r.added.length, 1);
  const both = await drafts();
  assert.equal(both.length, 2);
  assert.deepEqual(both[1].gap_ids, ['beach-water:Bay5:2026-08-01']);
  assert.doesNotMatch(both[1].body, /Earl Gilbert/);

  // dismiss needs a reason; dismissed gaps aren't drafted again
  await assert.rejects(R.dismiss({id: both[1].id, reason: ''}, 'jeremy@fluxlabs.net'), /why/);
  await R.dismiss({id: both[1].id, reason: 'Found the results on the county site'}, 'jeremy@fluxlabs.net');
  r = await R.seedStale([draft([gap('Bay11', '2025-05-05'), gap('Bay5', '2026-08-01')])]);
  assert.equal(r.added.length, 0);
  await assert.rejects(R.send({id: both[1].id}, 'jeremy@fluxlabs.net'), /already sent/);

  const hist = await q(`select request_id, actor, action, detail from corr.records_request_log order by id`);
  assert.deepEqual(hist.map(h => h.action), ['drafted', 'refreshed', 'sent', 'drafted', 'dismissed']);
  assert.equal(hist[2].actor, 'jeremy@fluxlabs.net');
  assert.equal(hist[2].detail.to, 'PublicRecordsRequest@FLHealth.gov');
  assert.equal(hist[4].detail.reason, 'Found the results on the county site');
  assert.equal((await q('select count(*)::int n from corr.rr_log_breaks()'))[0].n, 0);
  await assert.rejects(q(`update corr.records_request_log set actor = 'x'`), /locked/);
  await assert.rejects(q('delete from corr.records_request_log'), /locked/);
});

test('an open draft closes itself when the source catches up; an edited one keeps its words', opts, async () => {
  await q(`delete from corr.records_requests`);
  await R.seedStale([draft([gap('Bay11', '2026-07-01')])]);
  let [d] = await q(`select * from corr.records_requests where status = 'draft'`);
  await R.save({id: d.id, body: 'My own wording of the request, edited by hand.'}, 'jeremy@fluxlabs.net');
  await R.seedStale([draft([gap('Bay11', '2026-07-01'), gap('Bay5', '2026-07-02')])]);
  [d] = await q(`select * from corr.records_requests where id = $1`, [d.id]);
  assert.equal(d.body, 'My own wording of the request, edited by hand.');
  assert.equal(d.gap_ids.length, 1, 'edited drafts are left as they are');
  const r = await R.seedStale([draft([])]);
  assert.equal(r.resolved, 1);
  [d] = await q(`select * from corr.records_requests where id = $1`, [d.id]);
  assert.equal(d.status, 'dismissed');
  assert.equal(d.dismissed_by, 'system');
  const notice = R.newDraftsNotice([{government: 'Florida Department of Health', subject: 'Public records request: Healthy Beaches water samples', gaps: 1}]);
  assert.equal(notice.subject, '1 records request drafted for stale data');
  assert.match(notice.html, /admin#records/);
});
