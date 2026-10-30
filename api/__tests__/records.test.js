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
  intake_method text not null, inbound_address text unique, allowed_senders text[] not null default '{}', active boolean not null default true, auto_normalize boolean not null default false,
  created_at timestamptz not null default now());
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
create table votes (date date, headline text, summary text, amount numeric, agenda_item text, source_url text, government_key text);
insert into votes values ('2026-10-14', 'Award ITB 26-09 to Panhandle Paving LLC', 'Resurface 5th Street', 84500, '7.a', 'https://cityofparker.com/minutes/2026-10-14.pdf', 'parker');
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
  for (const f of ['0088_gov_workspace.sql', '0090_area_maps.sql', '0091_records_submission.sql', '0092_records_phase2.sql', '0093_records_verify_audit.sql', '0097_official_dashboard.sql']) await pool.query(fs.readFileSync(path.join(__dirname, '../../db/migrations', f), 'utf8'));
  await q(`insert into gov.members (workspace_id, email, role) values ('parker', 'finance@parker.test', 'records'), ('parker', 'mayor@parker.test', 'viewer'),
    ('parker', 'clerk@parker.test', 'publisher'), ('parker', 'owner@parker.test', 'owner')`);
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
  const [src0] = await q(`select allowed_senders, gov_domain from ingest.sources where inbound_address = 'parker@ingest.baycounty.me'`);
  assert.ok(src0.allowed_senders.every(a => !a.startsWith('@')), 'no whole domains on an allowed list');
  assert.equal(src0.gov_domain, 'cityofparker.com');
  await assert.rejects(q(`update ingest.sources set allowed_senders = '{"@cityofparker.com"}' where inbound_address = 'parker@ingest.baycounty.me'`), /sources_exact_senders/);
});

test('email security: only exact allowed addresses; the government domain gets a notice; everyone else is outside', opts, async () => {
  await q(`update ingest.sources set allowed_senders = '{"finance@cityofparker.com"}' where inbound_address = 'parker@ingest.baycounty.me'`);
  const chk = async from => (await q('select * from public.ingest_sender_check($1, $2)', ['Parker@ingest.baycounty.me', from]))[0];
  assert.equal((await chk('FINANCE@cityofparker.com')).status, 'authorized');
  const same = await chk('mayor@cityofparker.com');
  assert.equal(same.status, 'same_domain');
  assert.deepEqual(same.authorized, ['finance@cityofparker.com']);
  assert.equal((await chk('finance@cityofparker.com.evil.test')).status, 'outside');
  assert.equal((await chk('someone@gmail.com')).status, 'outside');
  assert.equal((await q('select * from public.ingest_sender_check($1, $2)', ['nobody@ingest.baycounty.me', 'a@b.com'])).length, 0);
  assert.equal((await q('select public.ingest_notice_sent_recently($1) r', ['mayor@cityofparker.com']))[0].r, false);
  await q(`select public.ingest_audit('system', 'intake_notice_sent', 'parker', 'mayor@cityofparker.com', null, '{}')`);
  assert.equal((await q('select public.ingest_notice_sent_recently($1) r', ['mayor@cityofparker.com']))[0].r, true, 'one notice a day');
  // An owner keeps the list, exact addresses only, and every change is logged.
  as = {email: 'clerk@parker.test', via: 'session'};
  assert.equal((await post('intake-senders', {senders: ['x@cityofparker.com']})).status, 403, 'publishers cannot change who may send');
  as = {email: 'owner@parker.test', via: 'session'};
  const bad = await post('intake-senders', {senders: ['@cityofparker.com']});
  assert.equal(bad.status, 400);
  const ok = await post('intake-senders', {senders: ['finance@cityofparker.com', 'Clerk@CityOfParker.com']});
  assert.equal(ok.status, 200, JSON.stringify(ok.body));
  assert.deepEqual((await get('intake-senders')).body.senders, ['finance@cityofparker.com', 'clerk@cityofparker.com']);
  const [a] = await q(`select detail from gov.activity where action = 'intake_senders_changed' order by id desc limit 1`);
  assert.deepEqual(a.detail.added, ['clerk@cityofparker.com']);
});

test('email intake log: one locked row per email with its timestamps, files and audit events; the report shows it', opts, async () => {
  const p = {email_id: 'em_1', message_id: '<a1@cityofparker.com>', sent_at: '2026-10-30T13:00:00Z', received_at: '2026-10-30T13:00:05Z',
    webhook_at: '2026-10-30T13:00:06Z', sender: 'Finance@CityOfParker.com', recipients: ['parker@ingest.baycounty.me'], payload_sha256: 'ab'.repeat(32)};
  const [first] = await q('select * from public.ingest_email_log($1)', [p]);
  assert.equal(first.existing, false);
  const [retry] = await q('select * from public.ingest_email_log($1)', [p]);
  assert.equal(retry.existing, true, 'a retried webhook is not handled twice');
  assert.equal(retry.id, first.id);
  await q('select public.ingest_email_finish($1, $2)', [first.id, {decision: 'accepted', reason: 'on the allowed list and authenticated', intake_address: 'parker@ingest.baycounty.me',
    workspace_id: 'parker', subject: 'September checks', body_text: 'Attached.', attachments: [{name: 'checks.csv', size: 120, sha256: 'cd'.repeat(32), raw_id: null}]}]);
  const [e] = await q('select * from gov.intake_emails where id = $1', [first.id]);
  assert.equal(e.sender, 'finance@cityofparker.com');
  assert.equal(e.subject, 'September checks');
  assert.ok(e.finished_at);
  await assert.rejects(q(`update gov.intake_emails set reason = 'changed' where id = $1`, [first.id]), /locked/);
  await assert.rejects(q('delete from gov.intake_emails where id = $1', [first.id]), /locked/);
  // A refused email keeps the envelope only.
  const [r2] = await q('select * from public.ingest_email_log($1)', [{...p, email_id: 'em_2', sender: 'someone@gmail.com', payload_sha256: 'ef'.repeat(32)}]);
  await q('select public.ingest_email_finish($1, $2)', [r2.id, {decision: 'dropped', reason: 'outside sender', subject: 'Free money', body_text: 'spam'}]);
  const [d] = await q('select subject, body_text from gov.intake_emails where id = $1', [r2.id]);
  assert.equal(d.subject, null);
  assert.equal(d.body_text, null);
  const IR = require('../_intake_report');
  const rep = await IR.report(q, {from: '2020-01-01', to: '2100-01-01'}).catch(() => null)
    || await IR.report(q, {from: new Date(Date.now() - 864e5).toISOString().slice(0, 10), to: new Date().toISOString().slice(0, 10)});
  const em = rep.emails.find(x => x.email_id === 'em_1');
  assert.ok(em, 'the email is in the report');
  assert.deepEqual(em.events.map(a => a.action), ['email_logged', 'email_finished']);
  assert.equal(rep.chain.intact, true);
  assert.equal(rep.counts.accepted, 1);
  const csv = IR.toCsv(rep);
  assert.match(csv.split('\r\n')[0], /^email_id,message_id,sent_at,received_at,webhook_at,logged_at/);
  assert.match(csv, /em_1,<a1@cityofparker\.com>,2026-10-30T13:00:00\.000Z/);
  const html = IR.toHtml(rep);
  assert.match(html, /Audit trail checked/);
  assert.ok(!html.includes('Free money'), 'nothing from a dropped email');
  // The public mail viewer shows the accepted email with its file fingerprint; the dropped one never appears.
  const M = require('../_mail');
  const l = await M.list(q, {folder: 'sent_in'});
  assert.deepEqual(l.threads.map(t => t.subject), ['September checks']);
  const t = await M.thread(q, l.threads[0].id);
  assert.equal(t.items[0].from.address, 'finance@cityofparker.com');
  assert.equal(t.items[0].attachments[0].sha256, 'cd'.repeat(32));
  assert.equal(t.items[0].text, 'Attached.');
  await assert.rejects(M.thread(q, 'e' + r2.id), /Unknown/);
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
  assert.equal(p.body.report.rows, 2, 'the confirm report covers the rows that will be taken in');
  assert.equal(p.body.report.total, 486000);
  assert.deepEqual(p.body.report.by_month.map(m => m.key), ['2026-09']);
  const conf = await post('submit-confirm', {id: p.body.id});
  assert.equal(conf.status, 200, JSON.stringify(conf.body));
  assert.equal(conf.body.status, 'in_review', 'no approval on record for these contracts, so they wait');
  assert.equal(conf.body.check.status, 'unverified');
  assert.equal((await q(`select count(*)::int n from contracts where origin = 'gov'`))[0].n, 0, 'nothing public before review');
  assert.equal((await get('submissions')).body.files.find(f => f.id === p.body.id).status, 'in_review');
  const twice = await post('submit-confirm', {id: p.body.id});
  assert.equal(twice.status, 409);
  // Staff can't publish; only the admin's review can.
  assert.equal((await call('review-file', {method: 'POST', body: {file_id: p.body.id, decision: 'publish'}})).status, 403);
  as = {email: 'owner@baycounty.me', admin: true, via: 'session'};
  const open = await call('review-files');
  assert.ok(open.body.files.some(f => f.file_id === p.body.id && f.name === 'awards.csv'));
  const noNote = await call('review-file', {method: 'POST', body: {file_id: p.body.id, decision: 'hold'}});
  assert.equal(noNote.status, 400, 'holding needs a reason');
  const pub = await call('review-file', {method: 'POST', body: {file_id: p.body.id, decision: 'publish', note: 'Checked with the clerk'}});
  assert.equal(pub.status, 200, JSON.stringify(pub.body));
  assert.equal(pub.body.published.rows, 2);
  const again = await call('review-file', {method: 'POST', body: {file_id: p.body.id, decision: 'hold', note: 'changed my mind'}});
  assert.equal(again.status, 409, 'a decision is final');
  await assert.rejects(q(`update gov.verifications set decision = 'hold' where file_id = $1`, [p.body.id]), /locked/);
  as = {email: 'finance@parker.test', via: 'session'};
  const rows = await q(`select vendor, amount::float, government, government_key, source_title from contracts where origin = 'gov' order by amount desc`);
  assert.deepEqual(rows.map(r => r.vendor), ['Gulf Asphalt Co', 'Individual (name withheld)']);
  assert.equal(rows[0].government, 'City of Parker');
  assert.equal(rows[0].government_key, 'parker');
  assert.match(rows[0].source_title, /^Sent by City of Parker on \d{4}-\d{2}-\d{2} \(awards\.csv\)$/);

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
  assert.deepEqual(act.map(a => a.action).filter(a => a.startsWith('records_')), ['records_confirmed', 'records_review_published', 'records_published', 'records_withdrawn']);
  // The audit trail holds all of it, chained and locked.
  const trail = await q(`select action, file_sha256 from gov.audit_log where subject = $1 order by id`, [p.body.id]);
  assert.ok(trail.some(t => t.action === 'file_checked'));
  assert.ok(trail.some(t => t.action === 'review_publish'));
  assert.equal((await q('select count(*)::int n from gov.audit_chain_breaks()'))[0].n, 0);
  await assert.rejects(q(`update gov.audit_log set actor = 'x' where id = (select min(id) from gov.audit_log)`), /append-only|locked|can/);
  await assert.rejects(q('delete from gov.audit_log'), /append-only|locked|can/);
  await assert.rejects(q(`update gov.submissions set sha256 = 'x' where id = $1`, [Number(p.body.id.slice(1))]), /locked/);
  await assert.rejects(q(`delete from gov.submissions where id = $1`, [Number(p.body.id.slice(1))]), /locked/);
});

test('a file that matches our own records publishes on its own', opts, async () => {
  as = {email: 'clerk@parker.test', via: 'session'};
  const p = await post('submit-preview', {kind: 'contracts', filename: 'oct-awards.csv', content: b64('Vendor,Amount,Award Date,Title\nPanhandle Paving LLC,"84,500",2026-10-20,Resurface 5th Street\n')});
  assert.equal(p.status, 200, JSON.stringify(p.body));
  const c = await post('submit-confirm', {id: p.body.id});
  assert.equal(c.status, 200, JSON.stringify(c.body));
  assert.equal(c.body.check.status, 'verified', JSON.stringify(c.body.check));
  assert.equal(c.body.status, 'published');
  const [v] = await q('select decision, decided_by from gov.verifications where file_id = $1', [p.body.id]);
  assert.deepEqual(v, {decision: 'publish', decided_by: 'BayCounty.me checks'});
  assert.equal((await get('submissions')).body.files.find(f => f.id === p.body.id).status, 'published');
  await post('submit-withdraw', {id: p.body.id});
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
  assert.deepEqual(p.body.report.checks, {first: 5001, last: 5003, count: 3});
  assert.equal(p.body.report.total, 1555.5);
  assert.equal(p.body.report.top_payees[0].key, 'Gulf Power Company');
  assert.equal((await q('select count(*)::int n from finance.disbursements'))[0].n, 0, 'nothing imported before staff confirm');
  const conf = await post('submit-confirm', {id: p.body.id});
  assert.equal(conf.status, 200, JSON.stringify(conf.body));
  assert.equal(conf.body.status, 'in_review', 'a part-year register can’t be fully checked, so it waits');
  assert.ok(conf.body.check.findings.some(f => f.check === 'Matches the check register we already have'));
  assert.equal((await q('select count(*)::int n from checkbook_payments'))[0].n, 0);
  as = {email: 'owner@baycounty.me', admin: true, via: 'session'};
  const rv = await call('review-file', {method: 'POST', body: {file_id: p.body.id, decision: 'publish', note: 'ok'}});
  assert.equal(rv.status, 200, JSON.stringify(rv.body));
  const pub = {body: rv.body.published};
  as = {email: 'finance@parker.test', via: 'session'};
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

test('appointments and fee changes read from a sheet', () => {
  const a = LISTS.readList('appointments', [['Board', 'Seat', 'Member', 'Appointed By', 'Term Start', 'Term End'],
    ['Planning Board', 'Seat 1', 'Jordan Rivers', 'City Commission', '2025-01-01', '2028-12-31'], ['Planning Board', 'Seat 2', 'Vacant', '', '', ''],
    ['Library Board', '', 'Pat Lane', 'Mayor', '2012-01-01', '2014-12-31']]);
  assert.equal(a.ok, true);
  assert.deepEqual(a.rows.map(r => r.person), ['Jordan Rivers']);
  assert.deepEqual(a.reasons, {'vacant seat': 1, 'term ended before 2016': 1});
  const f = LISTS.readList('fees', [['Fee', 'Old Amount', 'New Amount', 'Unit', 'Effective Date'], ['Residential water base charge', '18.50', '$19.75', 'per month', '2026-10-01'], ['Pavilion rental', '', '', '', '']]);
  assert.equal(f.ok, true);
  assert.equal(f.rows.length, 1);
  assert.equal(f.rows[0].category, 'utility');
  assert.equal(f.rows[0].new_amount, 19.75);
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
  assert.equal(p.body.report.people, 2);
  const pub = await post('submit-confirm', {id: p.body.id});
  assert.equal(pub.status, 200, JSON.stringify(pub.body));
  assert.equal(pub.body.status, 'in_review');
  as = {email: 'owner@baycounty.me', admin: true, via: 'session'};
  assert.equal((await call('review-file', {method: 'POST', body: {file_id: p.body.id, decision: 'publish', note: 'ok'}})).status, 200);
  as = {email: 'finance@parker.test', via: 'session'};
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

test('appointment, fee and contract lists publish from files; there is no typed entry', opts, async () => {
  as = {email: 'clerk@parker.test', via: 'session'};
  const send = async (kind, name, csv) => {
    const p = await post('submit-preview', {kind, filename: name, content: b64(csv)});
    assert.equal(p.status, 200, JSON.stringify(p.body));
    assert.equal(p.body.ok, true, JSON.stringify(p.body.missing));
    const pub = await post('submit-publish', {id: p.body.id});  // the old name still works for older app builds
    assert.equal(pub.status, 200, JSON.stringify(pub.body));
    if (pub.body.status === 'published') return pub.body.published;
    as = {email: 'owner@baycounty.me', admin: true, via: 'session'};
    const r = await call('review-file', {method: 'POST', body: {file_id: p.body.id, decision: 'publish', note: 'ok'}});
    as = {email: 'clerk@parker.test', via: 'session'};
    assert.equal(r.status, 200, JSON.stringify(r.body));
    return r.body.published;
  };
  assert.equal((await send('appointments', 'boards.csv', 'Board,Seat,Member,Appointed By,Term Start\nCode Enforcement Board,Alternate,Sam Ortiz,City Council,2026-10-01\n')).rows, 1);
  await send('fees', 'fees.csv', 'Fee,Old Amount,New Amount,Unit,Effective Date\nGarbage pickup,21,23.50,per month,2026-11-01\n');
  await send('contracts', 'contracts.csv', 'Vendor,Amount,Award Date,Title,Method\nPanhandle Paving LLC,"84,500",2026-10-20,Resurface 5th Street,ITB\n');
  const typed = await post('submit-form', {kind: 'fees', fields: {fee: 'x', new_amount: '1'}});
  assert.ok(typed.status >= 400, 'typed entry is gone');
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
  const src = await q(`select inbound_address, finance_workspace_id, allowed_senders, gov_domain from ingest.sources where finance_workspace_id = 'schools'`);
  assert.equal(src[0].inbound_address, 'schools@ingest.baycounty.me');
  assert.deepEqual(src[0].allowed_senders, []);
  assert.equal(src[0].gov_domain, 'bay.k12.fl.us');
  assert.equal((await q(`select count(*)::int n from finance.workspaces where id in ('sheriff', 'soe')`))[0].n, 2);
});
