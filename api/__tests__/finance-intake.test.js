// Email intake -> /finance (api/_finance/intake.js) against a real Postgres. Creates its own scratch database on the
// FINANCE_TEST_DATABASE_URL server (so it can run alongside finance-api.test.js), applies the finance and ingest
// migrations, and sends emailed files through the real /finance importer. Skipped when the variable isn't set.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const URL_ = process.env.FINANCE_TEST_DATABASE_URL;
const opts = {skip: URL_ ? false : 'FINANCE_TEST_DATABASE_URL not set'};
const DB = `intake_test_${process.pid}`;
let admin, pool, q, intake;

const files = new Map();
const storage = {configured: () => true, put: async (p, b) => { files.set(p, b); }, get: async p => files.get(p)};
const raw = new Map();
const deps = () => ({q, storage, readRaw: async p => raw.get(p), ingest: require('../finance').ingest});

const REGISTER = `Check Date,Check No,Vendor Name,Invoice No,Amount
10/02/2025,50101,Gulf Power Company,INV-1,"12,500.00"
10/09/2025,50103,ACME Paving Inc.,A-77,"30,000.00"
,,,Grand Total,"42,500.00"
`;
const BUDGET = `Budget vs Actual - Period ending 03/31/2026
Department,Account,Description,Amended Budget,YTD Actual,Encumbrances
Fleet,001-0590-552.10,Fuel,"80,000.00","70,000.00","15,000.00"
Police,001-0521-512.12,Salaries,"1,200,000.00","600,000.00",0
`;

async function addRaw(inbound, name, text) {
  const p = `src/${name}`; raw.set(p, Buffer.from(text));
  const [r] = await q(`insert into ingest.raw (source_id, intake_method, sender, file_name, file_hash, storage_path)
      select id, 'email', 'clerk@city.gov', $2, md5($3), $4 from ingest.sources where inbound_address = $1 returning id`, [inbound, name, text, p]);
  return r.id;
}

test.before(async () => {
  if (!URL_) return;
  const {Pool} = require('pg');
  admin = new Pool({connectionString: URL_});
  await admin.query(`drop database if exists ${DB}`);
  await admin.query(`create database ${DB}`);
  const u = new URL(URL_); u.pathname = '/' + DB;
  pool = new Pool({connectionString: u.toString()});
  q = async (t, p = []) => (await pool.query(t, p)).rows;
  await pool.query(`do $$ begin
    if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
    if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
    if not exists (select 1 from pg_roles where rolname = 'service_role') then create role service_role nologin; end if;
  end $$`);
  for (const f of ['0015_finance.sql', '0016_finance_signin.sql', '0022_ledger_ingest.sql', '0023_finance_intake.sql']) {
    await pool.query(fs.readFileSync(path.join(__dirname, '../../db/migrations', f), 'utf8'));
  }
  intake = require('../_finance/intake');
});
test.after(async () => {
  if (pool) await pool.end();
  if (admin) { await admin.query(`drop database if exists ${DB}`); await admin.end(); }
});

test('every intake source is linked to a finance workspace', opts, async () => {
  const rows = await q(`select inbound_address, finance_workspace_id from ingest.sources order by inbound_address`);
  assert.deepEqual(rows.map(r => [r.inbound_address.split('@')[0], r.finance_workspace_id]), [['lynnhaven', 'lh'], ['panamacity', 'pc'], ['springfield', 'sp']]);
});

test('an emailed check register lands in /finance as an unreviewed import, once', opts, async () => {
  const id = await addRaw('springfield@ingest.baycounty.me', 'oct-register.csv', REGISTER);
  const r = await intake.fromRaw(id, {}, deps());
  assert.equal(r.workspace, 'sp', JSON.stringify(r));
  assert.equal(r.shape, 'disbursements');
  assert.equal(r.ok, true);
  assert.equal(r.finance_only, false);
  const [u] = await q(`select status, uploaded_by, source_system, storage_path, row_count from finance.uploads where id = $1`, [r.upload_id]);
  assert.equal(u.status, 'preview', 'not committed: staff review it first');
  assert.equal(u.uploaded_by, 'email: clerk@city.gov');
  assert.equal(u.source_system, 'Springbrook');
  assert.match(u.storage_path, /^sp\/[0-9a-f]{16}\/oct-register\.csv$/);
  assert.ok(files.has(u.storage_path), 'copied into the finance bucket');
  const [d] = await q(`select count(*)::int n from finance.disbursements`);
  assert.equal(d.n, 0, 'no rows used until it is added');
  const [x] = await q(`select status, finance_status, finance_upload_id from ingest.raw where id = $1`, [id]);
  assert.deepEqual([x.status, x.finance_status, Number(x.finance_upload_id)], ['received', 'imported', Number(r.upload_id)], 'still goes to the public-ledger queue');
  assert.equal((await intake.fromRaw(id, {}, deps())).skipped, true, 'a second call does nothing');
  assert.equal((await intake.fromRaw(id, {retry: true}, deps())).skipped, true, 'nor does a retry once imported');
});

test('a budget report is marked finance-only so it never reaches the public ledger', opts, async () => {
  const id = await addRaw('panamacity@ingest.baycounty.me', 'bva-mar.csv', BUDGET);
  const r = await intake.fromRaw(id, {}, deps());
  assert.equal(r.workspace, 'pc', JSON.stringify(r));
  assert.equal(r.shape, 'budget');
  assert.equal(r.finance_only, true);
  const [x] = await q(`select status from ingest.raw where id = $1`, [id]);
  assert.equal(x.status, 'finance_only');
  const [ctx] = await q(`select public.ingest_pending_raw(20) id`);
  assert.notEqual(ctx && ctx.id, id, 'not offered to the normalizer');
});

test('a failure is recorded and can be retried; the sweep skips failed files', opts, async () => {
  const id = await addRaw('springfield@ingest.baycounty.me', 'nov.csv', REGISTER.replace('10/02', '11/02'));
  const broken = {...deps(), readRaw: async () => { throw new Error('storage down'); }};
  const r = await intake.fromRaw(id, {}, broken);
  assert.equal(r.error, 'storage down');
  const [x] = await q(`select finance_status, finance_error from ingest.raw where id = $1`, [id]);
  assert.deepEqual([x.finance_status, x.finance_error], ['failed', 'storage down']);
  assert.deepEqual(await intake.sweep(20, deps()), [], 'the daily sweep leaves failed files for a person to retry');
  const again = await intake.fromRaw(id, {retry: true}, deps());
  assert.equal(again.ok, true, JSON.stringify(again));
});

test('the sweep sends files that were never sent; unlinked sources are marked', opts, async () => {
  const id = await addRaw('springfield@ingest.baycounty.me', 'dec.csv', REGISTER.replace('10/02', '12/02'));
  const out = await intake.sweep(20, deps());
  assert.deepEqual(out.map(o => o.raw_id), [id]);
  await q(`update ingest.sources set finance_workspace_id = null where inbound_address = 'lynnhaven@ingest.baycounty.me'`);
  const lid = await addRaw('lynnhaven@ingest.baycounty.me', 'jan.csv', REGISTER);
  assert.equal((await intake.fromRaw(lid, {}, deps())).skipped, true);
  const [x] = await q(`select finance_status from ingest.raw where id = $1`, [lid]);
  assert.equal(x.finance_status, 'not_linked');
});

test('the intake endpoint only answers to a service-role key', opts, async () => {
  const {createHandler} = require('../finance');
  const seen = [];
  const fake = {isServiceKey: async k => k === 'svc', fromRaw: async id => { seen.push(id); return {raw_id: id}; }};
  const h = createHandler({q, hasDb: () => true, storage, caller: async () => null, intake: fake});
  const call = (auth, body) => new Promise((resolve, reject) => {
    const res = {code: 200, setHeader() {}, status(c) { this.code = c; return this; }, json(o) { resolve({status: this.code, body: o}); return this; }};
    h({method: 'POST', query: {action: 'intake'}, headers: auth ? {authorization: `Bearer ${auth}`} : {}, body}, res).catch(reject);
  });
  const id = '11111111-1111-4111-8111-111111111111';
  assert.equal((await call(null, {raw_id: id})).status, 401);
  assert.equal((await call('anon-key', {raw_id: id})).status, 401);
  const ok = await call('svc', {raw_ids: [id, 'not-a-uuid']});
  assert.equal(ok.status, 200);
  assert.deepEqual(seen, [id]);
});

test('isServiceKey probes the service-role-only RPC', async () => {
  process.env.SUPABASE_URL = 'https://proj.supabase.co';
  const {isServiceKey} = require('../_finance/intake');
  let hit;
  const fetchOk = async (url, o) => { hit = {url, o}; return {ok: o.headers.apikey === 'svc'}; };
  assert.equal(await isServiceKey('svc', fetchOk), true);
  assert.equal(hit.url, 'https://proj.supabase.co/rest/v1/rpc/ingest_pending_raw');
  assert.equal(await isServiceKey('anon', fetchOk), false);
  assert.equal(await isServiceKey('', fetchOk), false);
});
