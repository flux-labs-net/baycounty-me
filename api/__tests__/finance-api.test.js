// End-to-end tests for /api/finance against a real Postgres: migration 0015 is applied to a scratch database, then
// files go through the handler (preview, commit, hold, duplicate, saved mapping, flags, review, permissions).
// Runs when FINANCE_TEST_DATABASE_URL is set (CI provides a Postgres service); skipped otherwise.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const URL_ = process.env.FINANCE_TEST_DATABASE_URL;
const opts = {skip: URL_ ? false : 'FINANCE_TEST_DATABASE_URL not set'};

let pool, q, handler;
const files = new Map();
const fakeStorage = {configured: () => true, put: async (p, b) => { files.set(p, b); }, get: async p => files.get(p),
  signedUpload: async p => ({url: 'https://storage.test/' + p, token: 't'}), signedDownload: async p => 'https://storage.test/dl/' + p};
let as = {email: 'jeremy@fluxlabs.net', userId: null, via: 'cookie'};

function call(action, {method = 'GET', query = {}, body} = {}) {
  return new Promise((resolve, reject) => {
    const res = {code: 200, headers: {}, setHeader(k, v) { this.headers[k] = v; }, status(c) { this.code = c; return this; },
      json(o) { resolve({status: this.code, body: o}); return this; }};
    handler({method, query: {action, ...query}, headers: {}, body}, res).catch(reject);
  });
}
const post = (action, body) => call(action, {method: 'POST', body: {workspace: 'lh', ...body}});
const get = (action, query = {}) => call(action, {query: {workspace: 'lh', ...query}});
const b64 = s => Buffer.from(s).toString('base64');

test.before(async () => {
  if (!URL_) return;
  const {Pool} = require('pg');
  pool = new Pool({connectionString: URL_});
  q = async (t, p = []) => (await pool.query(t, p)).rows;
  await q('drop schema if exists finance cascade');
  for (const f of ['0015_finance.sql', '0016_finance_signin.sql']) await pool.query(fs.readFileSync(path.join(__dirname, '../../db/migrations', f), 'utf8'));
  await q(`insert into finance.members (workspace_id, email, role) values ('lh', 'viewer@city.test', 'viewer')`);
  const {createHandler} = require('../finance');
  handler = createHandler({q, hasDb: () => true, storage: fakeStorage, caller: async () => as});
});
test.after(async () => { if (pool) await pool.end(); });

const REGISTER = `Check Date,Check No,Vendor Name,Invoice No,Amount
10/02/2025,50101,Gulf Power Company,INV-1,"12,500.00"
10/09/2025,50103,ACME Paving Inc.,A-77,"30,000.00"
10/15/2025,50104,ACME Paving Inc.,A-78,"29,000.00"
10/20/2025,50105,Office Depot,OD-1,"212.40"
11/01/2025,50106,Office Depot,OD-1,"212.40"
,,,Grand Total,"71,924.80"
`;

test('workspaces lists the seeded Lynn Haven workspace for its owner', opts, async () => {
  const r = await call('workspaces');
  assert.equal(r.status, 200);
  assert.deepEqual(r.body.workspaces.map(w => [w.id, w.role]), [['lh', 'owner']]);
});

test('preview does not store rows; commit stores them, ties out and raises flags', opts, async () => {
  const pv = await post('ingest', {filename: 'oct-register.csv', content: b64(REGISTER)});
  assert.equal(pv.status, 200, JSON.stringify(pv.body));
  assert.equal(pv.body.committed, false);
  assert.equal(pv.body.shape, 'disbursements');
  assert.equal(pv.body.tie.status, 'ties');
  assert.equal(pv.body.sample.length, 5);
  assert.equal((await q('select count(*)::int n from finance.disbursements'))[0].n, 0);

  const c = await post('ingest', {upload_id: pv.body.upload_id, commit: true, source_system: 'Tyler Incode'});
  assert.equal(c.status, 200, JSON.stringify(c.body));
  assert.equal(c.body.committed, true);
  assert.equal((await q('select count(*)::int n from finance.disbursements'))[0].n, 5);
  const flags = (await get('flags')).body.flags.map(f => f.rule);
  assert.ok(flags.includes('split_purchase'), flags.join());
  assert.ok(flags.includes('duplicate_payment'), flags.join());
  assert.ok(flags.includes('audit_repeat'), 'seeded audit finding is flagged');
});

test('the same file cannot be committed twice', opts, async () => {
  const r = await post('ingest', {filename: 'again.csv', content: b64(REGISTER), commit: true});
  assert.equal(r.status, 409);
});

test('a file that does not tie is held: no rows, an urgent flag', opts, async () => {
  const bad = REGISTER.replace('71,924.80', '71,000.00').replace('Office Depot,OD-1,"212.40"\n11/01', 'Office Depot,OD-2,"212.40"\n11/01');
  const r = await post('ingest', {filename: 'nov-register.csv', content: b64(bad), commit: true});
  assert.equal(r.status, 200);
  assert.equal(r.body.held, true);
  const [{n}] = await q(`select count(*)::int n from finance.disbursements d join finance.uploads u on u.id = d.upload_id where u.original_name = 'nov-register.csv'`);
  assert.equal(n, 0);
  const tie = (await get('flags', {rule: 'file_tie'})).body.flags;
  assert.equal(tie.length, 1);
  assert.equal(tie[0].severity, 'urgent');
});

test('a saved mapping is reused for the next file with the same columns', opts, async () => {
  const odd = 'When,Who,How much\n12/01/2025,Gulf Power,100\n';
  const first = await post('ingest', {filename: 'odd.csv', content: b64(odd), shape: 'disbursements', mapping: {paid_on: 'When', payee: 'Who', amount: 'How much'}, commit: true});
  assert.equal(first.body.committed, true, JSON.stringify(first.body));
  const second = await post('ingest', {filename: 'odd2.csv', content: b64('When,Who,How much\n12/02/2025,Gulf Power,101\n')});
  assert.equal(second.body.used_saved_mapping, true);
  assert.equal(second.body.ok, true);
});

test('budget upload takes its as-of date from the title line and feeds the overview', opts, async () => {
  const budget = `Budget vs Actual - Period ending 03/31/2026
Department,Account,Description,Amended Budget,YTD Actual,Encumbrances
Fleet,001-0590-552.10,Fuel,"80,000.00","70,000.00","15,000.00"
Police,001-0521-512.12,Salaries,"1,200,000.00","600,000.00",0
Revenue,001-0000-311.10,Ad valorem,"5,000,000.00","4,900,000.00",0
,,Grand Total,,"5,570,000.00",
`;
  const r = await post('ingest', {filename: 'bva-mar.csv', content: b64(budget), commit: true});
  assert.equal(r.body.committed, true, JSON.stringify(r.body));
  assert.equal(r.body.fiscal_year, 2026);
  const o = await get('overview');
  assert.equal(o.body.budget.as_of, '2026-03-31');
  assert.equal(o.body.budget.total_budget, 1280000, 'revenue line left out');
  assert.ok(o.body.payments.top_vendors.length > 0);
  const over = (await get('flags', {rule: 'over_budget'})).body.flags;
  assert.equal(over.length, 1);
  assert.equal(over[0].amount_at_risk, 5000);
});

test('explaining a flag needs a note, keeps it explained across re-runs, and records who', opts, async () => {
  const dup = (await get('flags', {rule: 'duplicate_payment'})).body.flags[0];
  assert.equal((await post('flag-status', {id: dup.id, status: 'explained'})).status, 400);
  assert.equal((await post('flag-status', {id: dup.id, status: 'explained', note: 'Two separate orders, confirmed with Purchasing.'})).status, 200);
  await post('run-rules', {});
  const d = (await get('flag', {id: dup.id})).body;
  assert.equal(d.status, 'explained');
  assert.equal(d.notes[0].author, 'jeremy@fluxlabs.net');
  assert.ok(d.rows.disbursements.length === 2);
});

test('replacing an upload removes its rows and clears flags that depended on them', opts, async () => {
  const [u] = await q(`select id from finance.uploads where original_name = 'oct-register.csv' and status = 'committed'`);
  const r = await post('replace', {upload_id: u.id});
  assert.equal(r.status, 200);
  const split = (await get('flags', {rule: 'split_purchase', status: 'all'})).body.flags;
  assert.ok(split.every(f => f.status === 'cleared'));
});

test('permissions: viewers read but cannot upload; strangers see nothing; cookie POSTs need the admin header', opts, async () => {
  as = {email: 'viewer@city.test', userId: null, via: 'cookie'};
  assert.equal((await get('overview')).status, 200);
  assert.equal((await post('ingest', {filename: 'x.csv', content: b64(REGISTER)})).status, 403);
  as = {email: 'someone@else.test', userId: null, via: 'cookie'};
  assert.equal((await get('overview')).status, 404);
  as = null;
  assert.equal((await get('overview')).status, 401);
  as = {email: 'jeremy@fluxlabs.net', via: 'cookie', csrf: true};
  assert.equal((await post('run-rules', {})).status, 403);
  as = {email: 'jeremy@fluxlabs.net', userId: null, via: 'cookie'};
});

test('owners manage members; app users get linked to their membership by id', opts, async () => {
  assert.equal((await post('members', {email: 'Finance@LynnHaven.test', role: 'uploader'})).status, 200);
  as = {email: 'finance@lynnhaven.test', userId: '11111111-1111-4111-8111-111111111111', via: 'app'};
  assert.equal((await get('uploads')).status, 200);
  const [m] = await q(`select user_id from finance.members where email = 'finance@lynnhaven.test'`);
  assert.equal(m.user_id, '11111111-1111-4111-8111-111111111111');
  assert.equal((await post('members', {email: 'x@y.test', role: 'owner'})).status, 403);
  as = {email: 'jeremy@fluxlabs.net', userId: null, via: 'cookie'};
});

// ---- Sign-in with an emailed code, through the real caller() ----
const sent = [];
function realCall(action, {method = 'POST', body, headers = {}} = {}) {
  const {createHandler} = require('../finance');
  const {caller} = require('../_finance/auth');
  const h = createHandler({q, hasDb: () => true, storage: fakeStorage, caller, sendEmail: async (to, m) => { sent.push({to, m}); }});
  return new Promise((resolve, reject) => {
    const res = {code: 200, headers: {}, setHeader(k, v) { this.headers[k] = v; }, status(c) { this.code = c; return this; },
      json(o) { resolve({status: this.code, body: o, headers: this.headers}); return this; }};
    h({method, query: {action, ...(method === 'GET' ? body : {})}, headers: {'x-real-ip': '10.0.0.' + (sent.length + 1), ...headers}, body: method === 'GET' ? undefined : body}, res).catch(reject);
  });
}
const codeFrom = m => m.text.match(/\b(\d{6})\b/)[1];

test('sign-in: members get a code, strangers get the same answer and no email', opts, async () => {
  const a = await realCall('login', {body: {email: 'viewer@city.test'}});
  const b = await realCall('login', {body: {email: 'nobody@city.test'}});
  assert.equal(a.status, 200);
  assert.deepEqual(a.body, b.body);
  assert.equal(sent.length, 1);
  assert.equal(sent[0].to, 'viewer@city.test');
  assert.match(sent[0].m.subject, /^\d{6} is your/);
});

test('sign-in: wrong codes count, the right one opens a web session cookie, and it works only once', opts, async () => {
  const code = codeFrom(sent[0].m), wrong = code === '000000' ? '111111' : '000000';
  assert.equal((await realCall('verify', {body: {email: 'viewer@city.test', code: wrong}})).status, 400);
  const ok = await realCall('verify', {body: {email: 'Viewer@City.test', code}});
  assert.equal(ok.status, 200, JSON.stringify(ok.body));
  assert.equal(ok.body.token, undefined, 'web sign-in does not return the token in the body');
  const cookie = ok.headers['Set-Cookie'].split(';')[0];
  assert.match(cookie, /^bcm_fin=bcmf_/);
  assert.match(ok.headers['Set-Cookie'], /HttpOnly; Secure; SameSite=Lax/);
  assert.equal((await realCall('verify', {body: {email: 'viewer@city.test', code}})).status, 400, 'code is single-use');

  const ov = await realCall('overview', {method: 'GET', body: {workspace: 'lh'}, headers: {cookie}});
  assert.equal(ov.status, 200, JSON.stringify(ov.body));
  assert.equal(ov.body.role, 'viewer');
  const noHeader = await realCall('run-rules', {body: {workspace: 'lh'}, headers: {cookie}});
  assert.equal(noHeader.status, 403, 'cookie POST without X-BCM-Finance is refused');
  const viewerWrite = await realCall('flag-status', {body: {workspace: 'lh', id: 1, status: 'explained', note: 'x'}, headers: {cookie, 'x-bcm-finance': '1'}});
  assert.equal(viewerWrite.status, 403, 'viewers cannot review flags');

  const out = await realCall('logout', {body: {}, headers: {cookie, 'x-bcm-finance': '1'}});
  assert.equal(out.status, 200);
  assert.equal((await realCall('overview', {method: 'GET', body: {workspace: 'lh'}, headers: {cookie}})).status, 401, 'session revoked');
});

test('sign-in: the app gets a bearer token; five wrong guesses burn the code', opts, async () => {
  await realCall('login', {body: {email: 'jeremy@fluxlabs.net'}});
  const code = codeFrom(sent[sent.length - 1].m);
  const app = await realCall('verify', {body: {email: 'jeremy@fluxlabs.net', code, client: 'app'}});
  assert.match(app.body.token, /^bcmf_/);
  const ws = await realCall('workspaces', {method: 'GET', body: {}, headers: {authorization: 'Bearer ' + app.body.token}});
  assert.deepEqual(ws.body.workspaces.map(w => w.id), ['lh']);
  assert.equal(ws.body.via, 'app');
  const post = await realCall('run-rules', {body: {workspace: 'lh'}, headers: {authorization: 'Bearer ' + app.body.token}});
  assert.equal(post.status, 200, 'bearer requests need no CSRF header');

  await q('delete from finance.login_codes');
  await realCall('login', {body: {email: 'jeremy@fluxlabs.net'}});
  const fresh = codeFrom(sent[sent.length - 1].m), bad = fresh === '999999' ? '888888' : '999999';
  for (let i = 0; i < 5; i++) await realCall('verify', {body: {email: 'jeremy@fluxlabs.net', code: bad}});
  const late = await realCall('verify', {body: {email: 'jeremy@fluxlabs.net', code: fresh}});
  assert.equal(late.status, 400);
  assert.match(late.body.error, /expired/);
});
