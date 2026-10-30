// Send records (api/_records.js): reading contract lists, what's due, and the whole path from a file staff send to
// rows on the public tables, through /api/gov. The pure tests always run. The end-to-end tests run against a real
// Postgres when FINANCE_TEST_DATABASE_URL is set (CI has one); they use their own database (recordstest), so they
// never touch the gov and finance schemas the other test files rebuild in parallel.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const {readContracts, contractRows, dueList, parseId} = require('../_records');
const {parseCsv} = require('../_finance/parse');

test('contract lists: columns found under a title, people withheld, totals and old rows left out', () => {
  const grid = parseCsv([
    'City of Parker,,,,,',
    'Contracts awarded FY2026,,,,,',
    'Bid No,Project,Awarded To,Contract Amount,Date Approved,Procurement Method,Link',
    'ITB 2026-01,Water line replacement,Royal American Construction Company Inc,"$7,026,540.00",02/18/2026,Invitation to bid,https://example.gov/c1.pdf',
    'RFQ 2026-02,Engineering services,Anchor CEI LLC,"125,000",3/4/2026,CCNA,',
    ',Lawn care at City Hall,Jane Doe,"4,800",03/10/2026,Quotes,https://example.gov/jane.pdf',
    ',Old paving job,Gulf Asphalt Co,"90,000",05/01/2015,Bid,',
    ',Missing amount,Acme Supply,,03/12/2026,,',
    ',,Total,"7,156,340",,,',
  ].join('\n'));
  const c = readContracts(grid);
  assert.equal(c.ok, true, JSON.stringify(c.missing));
  assert.equal(c.mapping.vendor, 'Awarded To');
  assert.equal(c.mapping.award_date, 'Date Approved');
  assert.equal(c.rows.length, 3);
  const [water, eng, lawn] = c.rows;
  assert.equal(water.amount, 7026540);
  assert.equal(water.date, '2026-02-18');
  assert.equal(water.method, 'Competitive sealed bid (invitation to bid)');
  assert.equal(water.purpose, 'ITB 2026-01: Water line replacement');
  assert.equal(water.source_url, 'https://example.gov/c1.pdf');
  assert.equal(eng.method, 'Request for qualifications');
  assert.equal(lawn.vendor, 'Individual (name withheld)');
  assert.equal(lawn.source_url, null, 'a document naming a private person is not linked');
  assert.ok(!JSON.stringify(c.rows).includes('Jane'));
  assert.deepEqual(c.reasons, {'before 2016': 1, 'no amount': 1});
  assert.equal(c.skipped, 2);
});

test('contract lists: a file without vendor, amount and date says what is missing', () => {
  const c = readContracts(parseCsv('Name,Phone\nA,1\n'));
  assert.equal(c.ok, false);
  assert.ok(c.missing.length);
});

test('contract rows carry the government, who sent them and a per-file record hash', () => {
  const rows = contractRows({id: 9, original_name: 'awards.xlsx', submitted_at: '2026-10-30T15:00:00Z', rows: [{vendor: 'Anchor CEI LLC', amount: 125000, date: '2026-03-04', purpose: 'Engineering', method: null, notes: null}]},
    {id: 'parker', name: 'City of Parker'});
  assert.equal(rows[0].government, 'City of Parker');
  assert.equal(rows[0].source_title, 'Sent by City of Parker on 2026-10-30 (awards.xlsx)');
  assert.match(rows[0].record_hash, /^gov:9:[0-9a-f]{40}$/);
});

test('what is due: last month for payments, last quarter for budgets, the last month for contracts', () => {
  const today = new Date('2026-10-30T12:00:00Z');
  const none = dueList({}, today);
  assert.deepEqual(none.map(d => [d.kind, d.want, d.current]), [['checkbook', '2026-09-30', false], ['budget', '2026-09-30', false], ['contracts', '2026-09-29', false]]);
  assert.equal(none[0].text, 'Payments through September 2026');
  const some = dueList({checkbook: '2026-09-30', budget: '2026-06-30', contracts: '2026-10-15'}, today);
  assert.deepEqual(some.map(d => d.current), [true, false, true]);
  assert.equal(dueList({}, new Date('2026-01-05T00:00:00Z'))[1].want, '2025-12-31');
});

test('file ids', () => {
  assert.deepEqual(parseId('f12'), {type: 'f', id: 12});
  assert.deepEqual(parseId('c3'), {type: 'c', id: 3});
  assert.throws(() => parseId('x1'));
  assert.throws(() => parseId('f1; drop'));
});

/* ---------- end to end ---------- */
const BASE = process.env.FINANCE_TEST_DATABASE_URL;
const opts = {skip: BASE ? false : 'FINANCE_TEST_DATABASE_URL not set'};
let admin, pool, q, handler;
let as = null;
const stored = new Map();
const storage = {configured: () => true, put: async (p, b) => { stored.set(p, b); }, get: async p => stored.get(p),
  signedUpload: async p => ({url: 'https://storage.test/' + p, token: 't'})};
const call = (action, {method = 'GET', query = {}, body} = {}) => new Promise((resolve, reject) => {
  const res = {code: 200, headers: {}, setHeader(k, v) { this.headers[k] = v; }, status(c) { this.code = c; return this; },
    json(o) { resolve({status: this.code, body: o}); return this; }, send(o) { resolve({status: this.code, body: o, headers: this.headers}); return this; }};
  handler({method, query: {action, ...query}, headers: {}, body}, res).catch(reject);
});
const post = (action, body, ws = 'parker') => call(action, {method: 'POST', body: {workspace: ws, ...body}});
const get = (action, query = {}, ws = 'parker') => call(action, {query: {workspace: ws, ...query}});
const b64 = s => Buffer.from(s).toString('base64');

const STUBS = `
create table governments (key text primary key);
insert into governments values ('county'), ('parker'), ('lh');
create table contracts (id bigint generated always as identity primary key, government text, vendor text, amount numeric, purpose text, date date, method text,
  source_title text, source_url text, notes text, government_key text references governments(key), origin text not null default 'manual', record_hash text not null,
  unique (origin, record_hash));
insert into contracts (government, vendor, amount, purpose, date, origin, record_hash, government_key) values
  ('City of Parker', 'Anchor CEI LLC', 125000, 'From the minutes', '2026-03-04', 'site_build', 'm1', 'parker');
create table checkbook_payments (id bigint generated always as identity primary key, government text, fiscal_year bigint, paid_on date, payee text, payee_kind text,
  payee_entity_id text, amount numeric, method text, doc_no text, invoice_no text, fund text, account text, description text, source_file text, upload_id bigint,
  published_at timestamptz, source_url text, gov_id text, government_key text, origin text not null default 'finance', record_hash text not null, unique (origin, record_hash));
create table budget_actuals (id bigint generated always as identity primary key, government text, fiscal_year bigint, as_of date, line_type text, fund text, department text,
  account text, description text, original_budget numeric, amended_budget numeric, actual_ytd numeric, encumbered numeric, source_file text, upload_id bigint,
  published_at timestamptz, source_url text, gov_id text, government_key text, origin text not null default 'finance', record_hash text not null, unique (origin, record_hash));
create table public_notices (id bigint generated always as identity primary key, gov_id text, title text, origin text not null default 'manual', record_hash text);
create table emergency_live (notice_id text primary key);
create schema ingest;
create table ingest.sources (id uuid primary key default gen_random_uuid(), entity_name text not null, entity_type text not null, erp_system text not null,
  intake_method text not null, inbound_address text unique, allowed_senders text[] not null default '{}', active boolean not null default true, created_at timestamptz not null default now());
alter table ingest.sources add column finance_workspace_id text;
insert into ingest.sources (entity_name, entity_type, erp_system, intake_method, inbound_address) values ('City of Lynn Haven', 'city', 'other', 'email', 'lynnhaven@ingest.baycounty.me');
`;

test.before(async () => {
  if (!BASE) return;
  const {Pool} = require('pg');
  admin = new Pool({connectionString: BASE, max: 1});
  await admin.query('drop database if exists recordstest');
  await admin.query('create database recordstest');
  const u = new URL(BASE); u.pathname = '/recordstest';
  pool = new Pool({connectionString: u.toString(), max: 1});
  q = async (t, p = []) => (await pool.query(t, p)).rows;
  await pool.query(STUBS);
  for (const f of ['0015_finance.sql', '0016_finance_signin.sql', '0048_finance_publish.sql']) await pool.query(fs.readFileSync(path.join(__dirname, '../../db/migrations', f), 'utf8'));
  // 0023 needs the whole ingest schema; the one column 0091 reads is stubbed above.
  for (const f of ['0088_gov_workspace.sql', '0090_area_maps.sql', '0091_records_submission.sql']) await pool.query(fs.readFileSync(path.join(__dirname, '../../db/migrations', f), 'utf8'));
  await q(`insert into gov.members (workspace_id, email, role) values ('parker', 'finance@parker.test', 'records'), ('parker', 'mayor@parker.test', 'viewer'),
    ('parker', 'clerk@parker.test', 'publisher')`);
  const {createHandler} = require('../gov');
  handler = createHandler({q, hasDb: () => true, caller: async () => as, storage, sendEmail: async () => {}, sendNow: async () => ({})});
});
test.after(async () => {
  if (pool) await pool.end();
  if (admin) { await admin.query('drop database if exists recordstest'); await admin.end(); }
});

test('migration: every government has a finance workspace and an intake address', opts, async () => {
  const ws = await q('select id from finance.workspaces order by id');
  for (const id of ['county', 'pc', 'pcb', 'lh', 'cw', 'sp', 'parker', 'mb']) assert.ok(ws.some(w => w.id === id), id);
  const src = await q('select inbound_address, finance_workspace_id from ingest.sources order by inbound_address');
  assert.ok(src.some(s => s.inbound_address === 'parker@ingest.baycounty.me' && s.finance_workspace_id === 'parker'));
  assert.ok(src.some(s => s.inbound_address === 'lynnhaven@ingest.baycounty.me' && s.finance_workspace_id === 'lh'));
  const [s] = await q(`select id from ingest.sources where inbound_address = 'parker@ingest.baycounty.me'`);
  const ok = await q('select public.ingest_sender_is_staff($1, $2) ok', [s.id, 'FINANCE@parker.test']);
  const no = await q('select public.ingest_sender_is_staff($1, $2) ok', [s.id, 'mayor@parker.test']);
  assert.equal(ok[0].ok, true, 'a records sender may email files in');
  assert.equal(no[0].ok, false, 'a viewer may not');
});

test('roles: viewers see the tab but cannot send; the records role can', opts, async () => {
  as = {email: 'mayor@parker.test', via: 'session'};
  const seen = await get('submissions');
  assert.equal(seen.status, 200);
  assert.equal(seen.body.address, 'parker@ingest.baycounty.me');
  assert.equal(seen.body.due.length, 3);
  const r = await post('submit-preview', {kind: 'contracts', filename: 'a.csv', content: b64('Vendor,Amount,Award Date\nAcme Paving Inc,100,2026-10-01\n')});
  assert.equal(r.status, 403);
  as = {email: 'finance@parker.test', via: 'session'};
  const notice = await post('post', {kind: 'notice', title: 'x', text: 'y'});
  assert.equal(notice.status, 403, 'a records sender cannot post notices');
});

test('contracts: preview skips what is already on the site, publish adds rows, withdraw removes them', opts, async () => {
  as = {email: 'finance@parker.test', via: 'session'};
  const csv = 'Project,Vendor,Amount,Award Date,Method\nEngineering,Anchor CEI LLC,"125,000",03/04/2026,RFQ\nPaving on Tyndall Pkwy,Gulf Asphalt Co,"480,000",09/15/2026,ITB\nMowing,John Smith,"6,000",09/20/2026,Quotes\n';
  const p = await post('submit-preview', {kind: 'contracts', filename: 'awards.csv', content: b64(csv)});
  assert.equal(p.status, 200, JSON.stringify(p.body));
  assert.equal(p.body.ok, true);
  assert.equal(p.body.already_on_site, 1, 'Anchor CEI is already in the contracts table from the minutes');
  assert.equal(p.body.row_count, 2);
  assert.equal(p.body.withheld, 1);
  assert.match(p.body.id, /^c\d+$/);
  const pub = await post('submit-publish', {id: p.body.id});
  assert.equal(pub.status, 200, JSON.stringify(pub.body));
  assert.equal(pub.body.rows, 2);
  const rows = await q(`select vendor, amount::float, government, government_key, source_title from contracts where origin = 'gov' order by amount desc`);
  assert.deepEqual(rows.map(r => r.vendor), ['Gulf Asphalt Co', 'Individual (name withheld)']);
  assert.equal(rows[0].government, 'City of Parker');
  assert.equal(rows[0].government_key, 'parker');
  assert.match(rows[0].source_title, /^Sent by City of Parker on \d{4}-\d{2}-\d{2} \(awards\.csv\)$/);
  const again = await post('submit-publish', {id: p.body.id});
  assert.equal(again.body.rows, 2);
  assert.equal((await q(`select count(*)::int n from contracts where origin = 'gov'`))[0].n, 2, 'publishing twice does not double the rows');

  const pub2 = await call('records-sent', {});  // not a gov action
  assert.equal(pub2.status, 404);
  const R = require('../_records');
  const sent = await R.publicSent(q, {}, new Date());
  const parker = sent.data.governments.find(g => g.gov_id === 'parker');
  assert.equal(parker.records.contracts.status, 'current');
  assert.equal(parker.records.checkbook.status, 'not_sent');
  assert.equal(parker.sends, true);
  assert.equal(sent.data.contracts.length, 2);
  assert.ok(!JSON.stringify(sent).includes('finance@parker.test'), 'no staff email on the public scorecard');

  const w = await post('submit-withdraw', {id: p.body.id});
  assert.equal(w.body.removed, 2);
  assert.equal((await q(`select count(*)::int n from contracts where origin = 'gov'`))[0].n, 0);
  assert.equal((await q(`select count(*)::int n from contracts`))[0].n, 1, 'rows from the minutes are never touched');
  const list = await get('submissions');
  assert.equal(list.body.files[0].status, 'withdrawn');
  const act = await q(`select action from gov.activity where workspace_id = 'parker' order by id`);
  assert.deepEqual(act.map(a => a.action).filter(a => a.startsWith('records_')), ['records_published', 'records_published', 'records_withdrawn']);
});

test('checkbook: a check register goes through the finance importer and publishes with names of individuals withheld', opts, async () => {
  as = {email: 'finance@parker.test', via: 'session'};
  const csv = 'Check Date,Check Number,Vendor,Amount,Invoice Number,Description\n09/02/2026,5001,Gulf Power Company,1200.50,INV-1,Electric\n09/03/2026,5002,Mary Jones,45.00,R-1,Utility deposit refund\n09/15/2026,5003,Coastal Fleet Parts,310.00,INV-2,Brake pads\n';
  const p = await post('submit-preview', {kind: 'checkbook', filename: 'checks-sep.csv', content: b64(csv)});
  assert.equal(p.status, 200, JSON.stringify(p.body));
  assert.equal(p.body.ok, true, JSON.stringify(p.body.missing));
  assert.equal(p.body.row_count, 3);
  assert.match(p.body.id, /^f\d+$/);
  const waiting = await get('submissions');
  assert.equal(waiting.body.files.find(f => f.id === p.body.id).status, 'waiting');
  const pub = await post('submit-publish', {id: p.body.id});
  assert.equal(pub.status, 200, JSON.stringify(pub.body));
  assert.equal(pub.body.rows, 3);
  assert.equal(pub.body.individuals_withheld, 1);
  const rows = await q(`select payee, government from checkbook_payments order by paid_on`);
  assert.deepEqual(rows.map(r => r.payee), ['Gulf Power Company', 'Individual (name withheld)', 'Coastal Fleet Parts']);
  const list = await get('submissions');
  const f = list.body.files.find(x => x.id === p.body.id);
  assert.equal(f.status, 'published');
  assert.equal(f.period_end, '2026-09-15');
  const w = await post('submit-withdraw', {id: p.body.id});
  assert.equal(w.body.removed, 3);
  assert.equal((await q('select count(*)::int n from checkbook_payments'))[0].n, 0);
});

test('a CSV template downloads with its column names', opts, async () => {
  as = {email: 'mayor@parker.test', via: 'session'};
  const t = await get('template', {kind: 'contracts'});
  assert.equal(t.status, 200);
  assert.match(t.body, /^Title,Vendor,Amount,Award Date/);
});
