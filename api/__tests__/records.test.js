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
  assert.deepEqual(none.map(d => [d.kind, d.want, d.current]), [['checkbook', '2026-09-30', false], ['budget', '2026-09-30', false], ['contracts', '2026-09-29', false],
    ['payroll', '2026-10-01', false]]);
  assert.equal(none[3].text, 'Pay by job title for FY2027');
  assert.equal(none[0].text, 'Payments through September 2026');
  const some = dueList({checkbook: '2026-09-30', budget: '2026-06-30', contracts: '2026-10-15'}, today);
  assert.deepEqual(some.map(d => d.current), [true, false, true, false]);
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
alter table ingest.sources add constraint sources_entity_type_check check (entity_type in ('city','county','cra'));
create table datasets (id text primary key, table_name text, title text, description text, updated_at timestamptz);
create table ingest_runs (id bigint primary key);
create function touch_updated_at() returns trigger language plpgsql as $f$ begin new.updated_at = now(); return new; end $f$;
create table salary_positions (id bigint generated always as identity primary key, employer text, employer_id text, government text, fiscal_year text, title text,
  department text, category text, grade text, pay_min numeric, pay_mid numeric, pay_max numeric, pay_basis text, hourly_min numeric, hourly_max numeric,
  actual_salaries jsonb, budgeted_fte numeric, "union" text, source_url text, notes text, government_key text references governments(key),
  origin text not null default 'manual', record_hash text not null, unique (origin, record_hash));
create table data_sources (source_name text, source_url text, method text, refresh text, what_we_take text, page text, gov_id text);
insert into data_sources values ('Parker City Council agendas', 'https://cityofparker.com/agendas', 'Automatic, daily', 'Daily', 'Agendas and packets', '/meetings', 'parker'),
  ('Parker budget book', 'https://cityofparker.com/budget.pdf', 'Downloaded and read by hand', 'Yearly', 'Budget', '/governments/parker', 'parker');
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
  for (const f of ['0088_gov_workspace.sql', '0090_area_maps.sql', '0091_records_submission.sql', '0092_records_phase2.sql']) await pool.query(fs.readFileSync(path.join(__dirname, '../../db/migrations', f), 'utf8'));
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
  assert.equal(seen.body.due.length, 4);
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

/* ---------- Phase 2: payroll, appointments, fee changes, short forms, feeds ---------- */
const LISTS = require('../_record_lists');

test('payroll: one row per job title, names removed, pay kept as an unnamed list', () => {
  const grid = [['Employee Name', 'Job Title', 'Department', 'Annual Salary', 'Hourly Rate'],
    ['Smith, Ann', 'Police Officer', 'Police', '52,000', ''], ['Doe, Bob', 'Police Officer', 'Police', '', '26.00'],
    ['Lee, Cy', 'City Clerk', 'Administration', '71000', ''], ['', 'Total', '', '175000', '']];
  const r = LISTS.readList('payroll', grid);
  assert.equal(r.ok, true, JSON.stringify(r.missing));
  assert.equal(r.rows.length, 2);
  const po = r.rows.find(x => x.title === 'Police Officer');
  assert.deepEqual(po.salaries, [52000, 54080]);
  assert.equal(po.names_removed, 2);
  assert.equal(po.budgeted_fte, 2);
  assert.ok(!JSON.stringify(r.rows).includes('Smith'), 'no employee names in what gets published');
  const missing = LISTS.readList('payroll', [['Name', 'Department'], ['Ann', 'Police']]);
  assert.equal(missing.ok, false);
});

test('appointments and fee changes read from a sheet or one form', () => {
  const a = LISTS.readList('appointments', [['Board', 'Seat', 'Member', 'Appointed By', 'Term Start', 'Term End'],
    ['Planning Board', 'Seat 1', 'Jordan Rivers', 'City Commission', '2025-01-01', '2028-12-31'], ['Planning Board', 'Seat 2', 'Vacant', '', '', ''],
    ['Library Board', '', 'Pat Lane', 'Mayor', '2012-01-01', '2014-12-31']]);
  assert.equal(a.ok, true);
  assert.deepEqual(a.rows.map(r => r.person), ['Jordan Rivers']);
  assert.deepEqual(a.reasons, {'vacant seat': 1, 'term ended before 2016': 1});
  const f = LISTS.readForm('fees', {fee: 'Residential water base charge', old_amount: '18.50', new_amount: '$19.75', unit: 'per month', effective: '2026-10-01'});
  assert.equal(f.ok, true);
  assert.equal(f.rows[0].category, 'utility');
  assert.equal(f.rows[0].new_amount, 19.75);
  assert.equal(LISTS.readForm('fees', {fee: 'Pavilion rental'}).ok, false);
});

test('payroll file: preview, publish to salary positions without names, withdraw', opts, async () => {
  as = {email: 'finance@parker.test', via: 'session'};
  const csv = 'Name,Position,Department,Annual Salary\nAnn Smith,Public Works Laborer,Public Works,38000\nBob Doe,Public Works Laborer,Public Works,41000\n';
  const p = await post('submit-preview', {kind: 'payroll', filename: 'payroll.csv', content: b64(csv)});
  assert.equal(p.status, 200, JSON.stringify(p.body));
  assert.equal(p.body.ok, true, JSON.stringify(p.body.missing));
  assert.equal(p.body.row_count, 1);
  assert.equal(p.body.names_removed, 2);
  assert.ok(!JSON.stringify(p.body).includes('Ann Smith'));
  const pub = await post('submit-publish', {id: p.body.id});
  assert.equal(pub.status, 200, JSON.stringify(pub.body));
  const rows = await q(`select employer, employer_id, title, actual_salaries, budgeted_fte, government_key from salary_positions where origin = 'gov'`);
  assert.equal(rows.length, 1);
  assert.deepEqual(rows[0].actual_salaries, [38000, 41000]);
  assert.equal(Number(rows[0].budgeted_fte), 2);
  assert.equal(rows[0].government_key, 'parker');
  const due = (await get('submissions')).body.due.find(d => d.kind === 'payroll');
  assert.equal(due.current, true);
  await post('submit-withdraw', {id: p.body.id});
  assert.equal((await q(`select count(*)::int n from salary_positions where origin = 'gov'`))[0].n, 0);
});

test('short forms publish one appointment, fee change or contract at once', opts, async () => {
  as = {email: 'clerk@parker.test', via: 'session'};
  const a = await post('submit-form', {kind: 'appointments', fields: {board: 'Code Enforcement Board', seat: 'Alternate', person: 'Sam Ortiz', appointed_by: 'City Council', term_start: '2026-10-01'}});
  assert.equal(a.status, 200, JSON.stringify(a.body));
  assert.equal(a.body.rows, 1);
  const fee = await post('submit-form', {kind: 'fees', fields: {fee: 'Garbage pickup', old_amount: '21', new_amount: '23.50', unit: 'per month', effective: '2026-11-01'}});
  assert.equal(fee.status, 200, JSON.stringify(fee.body));
  const c = await post('submit-form', {kind: 'contracts', fields: {vendor: 'Panhandle Paving LLC', amount: '84,500', award_date: '2026-10-20', title: 'Resurface 5th Street', method: 'ITB'}});
  assert.equal(c.status, 200, JSON.stringify(c.body));
  const bad = await post('submit-form', {kind: 'fees', fields: {fee: 'Missing amount'}});
  assert.equal(bad.status, 400);
  const payrollForm = await post('submit-form', {kind: 'payroll', fields: {title: 'x'}});
  assert.equal(payrollForm.status, 400, 'payroll is a file, not a form');
  assert.equal((await q(`select person from board_appointments where gov_id = 'parker'`))[0].person, 'Sam Ortiz');
  assert.equal((await q(`select category from fee_changes where gov_id = 'parker'`))[0].category, 'trash');
  const R = require('../_records');
  const sent = await R.publicSent(q, {gov: 'parker'}, new Date('2026-10-30T12:00:00Z'));
  assert.equal(sent.data.appointments.length, 1);
  assert.equal(sent.data.fees[0].new_amount, 23.5);
  const parker = sent.data.governments[0];
  assert.equal(parker.records.appointments.status, 'current');
  assert.equal(parker.records.fees.status, 'current');
  assert.ok(sent.data.contracts.some(x => x.vendor === 'Panhandle Paving LLC'));
});

test('feeds: a government sees what we read automatically and can agree to it', opts, async () => {
  as = {email: 'clerk@parker.test', via: 'session'};
  const s = await get('submissions');
  assert.deepEqual(s.body.feeds.map(f => f.url), ['https://cityofparker.com/agendas'], 'only automatic sources');
  assert.equal(s.body.feeds[0].agreed, false);
  const ok = await post('feed-agree', {url: 'https://cityofparker.com/agendas'});
  assert.equal(ok.status, 200, JSON.stringify(ok.body));
  assert.equal((await get('submissions')).body.feeds[0].agreed, true);
  const other = await post('feed-agree', {url: 'https://example.com/not-ours'});
  assert.equal(other.status, 404);
  as = {email: 'mayor@parker.test', via: 'session'};
  assert.equal((await post('feed-agree', {url: 'https://cityofparker.com/agendas', agree: false})).status, 403, 'viewers cannot change agreements');
  const R = require('../_records');
  const sent = await R.publicSent(q, {gov: 'parker'});
  assert.equal(sent.data.governments[0].feeds_agreed, 1);
});

test('migration 0092 adds the School Board and the five county officers with intake addresses', opts, async () => {
  const ws = (await q(`select id from gov.workspaces order by id`)).map(r => r.id);
  for (const id of ['schools', 'sheriff', 'clerk', 'property_appraiser', 'tax_collector', 'soe']) assert.ok(ws.includes(id), id);
  const src = await q(`select inbound_address, finance_workspace_id, allowed_senders from ingest.sources where finance_workspace_id = 'schools'`);
  assert.equal(src[0].inbound_address, 'schools@ingest.baycounty.me');
  assert.deepEqual(src[0].allowed_senders, ['@bay.k12.fl.us']);
  assert.equal((await q(`select count(*)::int n from finance.workspaces where id in ('sheriff', 'soe')`))[0].n, 2);
});
