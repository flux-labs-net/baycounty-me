// Database reads and writes for the finance workspace (schema "finance", migration 0015).
// Every function takes q (api/_db.js q, or a test double) so the API can be exercised against any Postgres.
const {runRules, isRevenue} = require('./rules');

const COLUMNS = {
  budget: {table: 'budget_lines', cols: ['fiscal_year', 'as_of', 'fund', 'department', 'account', 'description', 'original_budget', 'amended_budget', 'actual_ytd', 'encumbered', 'source_row']},
  disbursements: {table: 'disbursements', cols: ['paid_on', 'doc_no', 'method', 'payee', 'payee_key', 'amount', 'invoice_no', 'fund', 'account', 'description', 'is_void', 'source_row']},
  bank_transactions: {table: 'bank_transactions', cols: ['account_label', 'account_hash', 'posted_on', 'amount', 'check_no', 'description', 'source_row']},
  bank_recs: {table: 'bank_recs', cols: ['account_label', 'account_hash', 'period_end', 'statement_balance', 'book_balance', 'outstanding_checks', 'deposits_in_transit', 'other_adjustments', 'reconciled_on', 'prepared_by', 'approved_by', 'source_row']},
};
const ROW_TABLES = ['budget_lines', 'disbursements', 'bank_transactions', 'bank_recs'];
const num = v => (v === null || v === undefined ? null : Number(v));
const day = v => (v instanceof Date ? v.toISOString().slice(0, 10) : v ?? null);

async function workspace(q, id) {
  const [w] = await q('select id, government_key, name, fy_start_month, settings from finance.workspaces where id = $1', [id]);
  return w || null;
}

async function workspacesFor(q, who) {
  return q(`select w.id, w.name, w.government_key, m.role from finance.members m join finance.workspaces w on w.id = m.workspace_id
            where lower(m.email) = $1 or ($2::uuid is not null and m.user_id = $2::uuid) order by w.name`, [who.email, who.userId || null]);
}

async function log(q, ws, actor, action, detail) {
  await q('insert into finance.activity (workspace_id, actor, action, detail) values ($1, $2, $3, $4)', [ws, actor, action, detail ? JSON.stringify(detail) : null]).catch(() => {});
}

const UPLOAD_FIELDS = ['shape', 'source_system', 'original_name', 'storage_path', 'sha256', 'bytes', 'uploaded_by', 'period_start', 'period_end', 'row_count',
  'parsed_total', 'printed_total', 'tie_status', 'tie_difference', 'status', 'mapping', 'warnings', 'error'];
async function saveUpload(q, ws, fields, id) {
  const f = Object.fromEntries(Object.entries(fields).filter(([k]) => UPLOAD_FIELDS.includes(k)).map(([k, v]) => [k, (k === 'mapping' || k === 'warnings') && v !== null ? JSON.stringify(v) : v]));
  const keys = Object.keys(f);
  if (id) {
    const [u] = await q(`update finance.uploads set ${keys.map((k, i) => `${k} = $${i + 3}`).join(', ')} where id = $1 and workspace_id = $2 returning id`, [id, ws, ...keys.map(k => f[k])]);
    if (!u) throw Object.assign(new Error('Upload not found.'), {status: 404});
    return u.id;
  }
  const [u] = await q(`insert into finance.uploads (workspace_id, ${keys.join(', ')}) values ($1, ${keys.map((k, i) => `$${i + 2}`).join(', ')}) returning id`, [ws, ...keys.map(k => f[k])]);
  return u.id;
}

async function getUpload(q, ws, id) {
  const [u] = await q('select * from finance.uploads where id = $1 and workspace_id = $2', [id, ws]);
  if (!u) throw Object.assign(new Error('Upload not found.'), {status: 404});
  return u;
}

// Multi-row inserts, 400 rows a statement.
async function insertRows(q, ws, uploadId, shape, records) {
  const {table, cols} = COLUMNS[shape], all = ['upload_id', 'workspace_id', ...cols];
  for (let i = 0; i < records.length; i += 400) {
    const chunk = records.slice(i, i + 400), params = [], tuples = [];
    for (const r of chunk) {
      const vals = [uploadId, ws, ...cols.map(c => (r[c] === undefined ? null : r[c]))];
      tuples.push('(' + vals.map(v => { params.push(v); return '$' + params.length; }).join(', ') + ')');
    }
    await q(`insert into finance.${table} (${all.join(', ')}) values ${tuples.join(', ')}`, params);
  }
}

async function committedDuplicate(q, ws, sha) {
  const [u] = await q(`select id, original_name, uploaded_at from finance.uploads where workspace_id = $1 and sha256 = $2 and status = 'committed'`, [ws, sha]);
  return u || null;
}

async function savedMapping(q, ws, signature) {
  const [m] = await q('select shape, mapping from finance.mappings where workspace_id = $1 and signature = $2 order by updated_at desc limit 1', [ws, signature]);
  return m || null;
}
async function saveMapping(q, ws, shape, signature, mapping, headers, sourceSystem) {
  await q(`insert into finance.mappings (workspace_id, shape, signature, mapping, headers, source_system) values ($1, $2, $3, $4, $5, $6)
           on conflict (workspace_id, shape, signature) do update set mapping = excluded.mapping, headers = excluded.headers,
           source_system = coalesce(excluded.source_system, finance.mappings.source_system), updated_at = now()`,
    [ws, shape, signature, JSON.stringify(mapping), JSON.stringify(headers), sourceSystem || null]);
}

async function replaceUpload(q, ws, id) {
  await getUpload(q, ws, id);
  for (const t of ROW_TABLES) await q(`delete from finance.${t} where upload_id = $1 and workspace_id = $2`, [id, ws]);
  await q(`update finance.uploads set status = 'replaced' where id = $1 and workspace_id = $2`, [id, ws]);
}

// Everything the rules read, with numerics as numbers and dates as 'YYYY-MM-DD'.
async function loadAll(q, ws) {
  const [w, uploads, budget, disb, txns, recs, findings] = await Promise.all([
    workspace(q, ws),
    q(`select id, original_name, shape, status, tie_status, tie_difference, parsed_total, printed_total from finance.uploads where workspace_id = $1 and status <> 'replaced'`, [ws]),
    q(`select id, fiscal_year, as_of::text as_of, fund, department, account, description, original_budget, amended_budget, actual_ytd, encumbered from finance.budget_lines where workspace_id = $1`, [ws]),
    q(`select id, paid_on::text paid_on, doc_no, method, payee, payee_key, amount, invoice_no, is_void from finance.disbursements where workspace_id = $1`, [ws]),
    q(`select id, account_label, account_hash, posted_on::text posted_on, amount, check_no from finance.bank_transactions where workspace_id = $1`, [ws]),
    q(`select id, account_label, account_hash, period_end::text period_end, statement_balance, book_balance, outstanding_checks, deposits_in_transit, other_adjustments, reconciled_on::text reconciled_on, approved_by from finance.bank_recs where workspace_id = $1`, [ws]),
    q(`select id, fiscal_year, finding_id, title, topic, repeat, mgmt_response, source_url from finance.audit_findings where workspace_id = $1`, [ws]),
  ]);
  const N = (rows, nums, days) => rows.map(r => { for (const k of nums) r[k] = num(r[k]); for (const k of days) r[k] = day(r[k]); return r; });
  return {
    workspace: w,
    uploads: N(uploads, ['tie_difference', 'parsed_total', 'printed_total'], []),
    budget: N(budget, ['original_budget', 'amended_budget', 'actual_ytd', 'encumbered'], ['as_of']),
    disbursements: N(disb, ['amount'], ['paid_on']),
    bankTxns: N(txns, ['amount'], ['posted_on']),
    bankRecs: N(recs, ['statement_balance', 'book_balance', 'outstanding_checks', 'deposits_in_transit', 'other_adjustments'], ['period_end', 'reconciled_on']),
    findings,
  };
}

// Runs every rule and stores the result. New flags are inserted; known ones are refreshed but keep their review
// status; open flags that no longer fire are marked cleared (and reopen if they fire again).
async function refreshFlags(q, ws, today) {
  const data = await loadAll(q, ws);
  const flags = runRules({...data, today});
  const payload = JSON.stringify(flags.map(f => ({rule: f.rule, fingerprint: f.fingerprint, severity: f.severity, title: f.title, detail: f.detail,
    amount_at_risk: f.amount_at_risk, score: f.score, refs: f.refs, facts: f.facts})));
  await q(`insert into finance.flags (workspace_id, rule, fingerprint, severity, title, detail, amount_at_risk, score, refs, facts)
           select $1, x.rule, x.fingerprint, x.severity, x.title, x.detail, x.amount_at_risk, x.score, coalesce(x.refs, '[]'), coalesce(x.facts, '{}')
           from jsonb_to_recordset($2::jsonb) as x(rule text, fingerprint text, severity text, title text, detail text, amount_at_risk numeric, score numeric, refs jsonb, facts jsonb)
           on conflict (workspace_id, fingerprint) do update set severity = excluded.severity, title = excluded.title, detail = excluded.detail,
             amount_at_risk = excluded.amount_at_risk, score = excluded.score, refs = excluded.refs, facts = excluded.facts, last_seen_at = now(),
             status = case when finance.flags.status = 'cleared' then 'open' else finance.flags.status end`, [ws, payload]);
  const cleared = await q(`update finance.flags set status = 'cleared' where workspace_id = $1 and status = 'open'
           and not (fingerprint = any($2::text[])) returning id`, [ws, flags.map(f => f.fingerprint)]);
  return {flags: flags.length, cleared: cleared.length};
}

const FLAG_COLS = 'id, rule, severity, title, detail, amount_at_risk::float8 amount_at_risk, score::float8 score, status, first_seen_at, last_seen_at, facts';
async function listFlags(q, ws, {status = 'open', rule, severity, limit = 100, offset = 0} = {}) {
  const where = ['workspace_id = $1'], p = [ws];
  if (status && status !== 'all') { p.push(String(status).split(',')); where.push(`status = any($${p.length}::text[])`); }
  if (rule) { p.push(String(rule).split(',')); where.push(`rule = any($${p.length}::text[])`); }
  if (severity) { p.push(String(severity).split(',')); where.push(`severity = any($${p.length}::text[])`); }
  p.push(Math.min(500, Math.max(1, Number(limit) || 100)), Math.max(0, Number(offset) || 0));
  const rows = await q(`select ${FLAG_COLS} from finance.flags where ${where.join(' and ')} order by score desc, id limit $${p.length - 1} offset $${p.length}`, p);
  const [{n}] = await q(`select count(*)::int n from finance.flags where ${where.join(' and ')}`, p.slice(0, -2));
  return {total: n, flags: rows};
}

// One flag with the rows behind it and its review notes.
async function flagDetail(q, ws, id) {
  const [f] = await q(`select ${FLAG_COLS}, refs from finance.flags where id = $1 and workspace_id = $2`, [id, ws]);
  if (!f) throw Object.assign(new Error('Flag not found.'), {status: 404});
  const byTable = {};
  for (const r of f.refs || []) if (['uploads', 'audit_findings', ...ROW_TABLES].includes(r.table)) (byTable[r.table] = byTable[r.table] || []).push(Number(r.id));
  const rows = {};
  for (const [t, ids] of Object.entries(byTable)) {
    const cols = t === 'uploads' ? 'id, original_name, shape, uploaded_at, uploaded_by, parsed_total, printed_total, tie_status, tie_difference, status' : '*';
    rows[t] = await q(`select ${cols} from finance.${t} where workspace_id = $1 and id = any($2::bigint[]) order by id limit 200`, [ws, ids]);
  }
  const notes = await q('select id, author, status, note, created_at from finance.flag_notes where flag_id = $1 order by id', [id]);
  delete f.refs;
  return {...f, rows, notes};
}

async function setFlagStatus(q, ws, id, status, note, author) {
  if (!['open', 'explained', 'follow_up', 'referred'].includes(status)) throw Object.assign(new Error('Status must be open, explained, follow_up or referred.'), {status: 400});
  if (status === 'explained' && !String(note || '').trim()) throw Object.assign(new Error('Add a short note saying why.'), {status: 400});
  const [f] = await q('update finance.flags set status = $3 where id = $1 and workspace_id = $2 returning id', [id, ws, status]);
  if (!f) throw Object.assign(new Error('Flag not found.'), {status: 404});
  await q('insert into finance.flag_notes (flag_id, author, status, note) values ($1, $2, $3, $4)', [id, author, status, String(note || '').trim().slice(0, 4000) || null]);
}

// Home screen numbers.
async function overview(q, ws, today = new Date().toISOString().slice(0, 10)) {
  const data = await loadAll(q, ws);
  const w = data.workspace, fyStart = w.fy_start_month || 10;
  // Budget: latest snapshot of the latest fiscal year, expense lines only, by department.
  let budget = null;
  if (data.budget.length) {
    const fy = Math.max(...data.budget.map(l => l.fiscal_year || 0));
    const asOf = data.budget.filter(l => l.fiscal_year === fy).map(l => l.as_of || '').sort().pop();
    const lines = data.budget.filter(l => l.fiscal_year === fy && (l.as_of || '') === asOf && !isRevenue(l));
    const depts = new Map();
    for (const l of lines) {
      const k = l.department || l.fund || 'Other', d = depts.get(k) || {department: k, budget: 0, actual: 0, encumbered: 0, over_lines: 0};
      const b = l.amended_budget ?? l.original_budget ?? 0;
      d.budget += b; d.actual += l.actual_ytd || 0; d.encumbered += l.encumbered || 0;
      if ((l.actual_ytd || 0) + (l.encumbered || 0) > b + 0.5) d.over_lines++;
      depts.set(k, d);
    }
    const r2 = n => Math.round(n * 100) / 100;
    const list = [...depts.values()].map(d => ({...d, budget: r2(d.budget), actual: r2(d.actual), encumbered: r2(d.encumbered)})).sort((a, b) => b.budget - a.budget);
    const start = `${fy - (fyStart > 1 ? 1 : 0)}-${String(fyStart).padStart(2, '0')}-01`;
    const elapsed = asOf ? Math.min(1, Math.max(0, (Date.parse(asOf) - Date.parse(start)) / 864e5 / 365)) : null;
    budget = {fiscal_year: fy, as_of: asOf, elapsed: elapsed === null ? null : Math.round(elapsed * 1000) / 1000,
      total_budget: r2(list.reduce((s, d) => s + d.budget, 0)), total_actual: r2(list.reduce((s, d) => s + d.actual, 0)),
      total_encumbered: r2(list.reduce((s, d) => s + d.encumbered, 0)), departments: list};
  }
  // Payments by month and top vendors over the latest 12 months of data.
  let payments = null;
  const live = data.disbursements.filter(d => !d.is_void && d.paid_on && d.amount);
  if (live.length) {
    const end = live.map(d => d.paid_on).sort().pop(), from = new Date(Date.parse(end) - 365 * 864e5).toISOString().slice(0, 10);
    const recent = live.filter(d => d.paid_on > from), months = new Map(), vendors = new Map();
    for (const d of recent) {
      const m = d.paid_on.slice(0, 7); months.set(m, (months.get(m) || 0) + d.amount);
      const v = vendors.get(d.payee_key) || {payee: d.payee, total: 0, payments: 0}; v.total += d.amount; v.payments++; vendors.set(d.payee_key, v);
    }
    payments = {through: end, total: Math.round(recent.reduce((s, d) => s + d.amount, 0) * 100) / 100,
      by_month: [...months].sort().map(([month, total]) => ({month, total: Math.round(total * 100) / 100})),
      top_vendors: [...vendors.values()].sort((a, b) => b.total - a.total).slice(0, 10).map(v => ({...v, total: Math.round(v.total * 100) / 100}))};
  }
  const accounts = new Map();
  for (const r of data.bankRecs) { const a = accounts.get(r.account_hash) || {account: r.account_label, last_rec: null, last_reconciled_on: null}; if (!a.last_rec || r.period_end > a.last_rec) { a.last_rec = r.period_end; a.last_reconciled_on = r.reconciled_on; } accounts.set(r.account_hash, a); }
  for (const t of data.bankTxns) if (!accounts.has(t.account_hash)) accounts.set(t.account_hash, {account: t.account_label, last_rec: null, last_reconciled_on: null});
  const [flagSum] = await q(`select count(*)::int open, coalesce(sum(amount_at_risk), 0)::float8 dollars,
      count(*) filter (where severity = 'urgent')::int urgent, count(*) filter (where severity = 'review')::int review, count(*) filter (where severity = 'info')::int info
      from finance.flags where workspace_id = $1 and status in ('open', 'follow_up')`, [ws]);
  const top = (await listFlags(q, ws, {status: 'open,follow_up', limit: 10})).flags;
  const sources = await q(`select shape, count(*)::int files, max(uploaded_at) last_upload, min(period_start)::text period_start, max(period_end)::text period_end,
      count(*) filter (where status = 'held')::int held from finance.uploads where workspace_id = $1 and status in ('committed', 'held') group by shape`, [ws]);
  return {workspace: {id: w.id, name: w.name}, as_of: today, budget, payments, bank_accounts: [...accounts.values()], flags: {...flagSum, top}, sources};
}

module.exports = {COLUMNS, workspace, workspacesFor, log, saveUpload, getUpload, insertRows, committedDuplicate, savedMapping, saveMapping,
  replaceUpload, loadAll, refreshFlags, listFlags, flagDetail, setFlagStatus, overview};
