// Records submission (Send records, in the government workspace /staff): a government's own staff send the files
// their systems already make and we take them in two steps. Used by api/gov.js (staff and admin actions) and api/v1.js
// (/records-sent, the public scorecard). Tables: migrations 0091-0093.
//  1. Confirm: staff see a report of what the file says (totals by month and department, biggest payees, first and
//     last check number) and press "Yes, this is the right file". Until then nothing is imported, so a wrong file
//     never needs cleaning up. Staff can't publish.
//  2. Check: we never take the file's word for it. api/_records_verify.js checks it against records we collect on our
//     own (approvals and votes, adopted budgets, the state's yearly figures, published pay, check-number gaps). A file
//     that passes every check publishes on its own; anything else waits for the BayCounty.me admin (review-file).
//
// Kinds of record:
//  * checkbook: a check register or payments export -> the finance importer (shape 'disbursements') -> checkbook_payments
//  * budget:    a budget-vs-actual report           -> the finance importer (shape 'budget')        -> budget_actuals
//  * contracts: a list of contracts awarded          -> read here, kept in gov.submissions            -> contracts (origin 'gov')
//  * payroll, appointments, fees (Phase 2)           -> api/_record_lists.js, gov.submissions         -> salary_positions,
//    board_appointments, fee_changes (origin 'gov'). Files only: nothing is typed in by hand.
// Each government also sees the sources we already read for it automatically (data_sources) and can agree to them
// (gov.feed_agreements), so a scraper becomes a feed the government knows about.
// The finance importer already detects columns, saves the mapping for next month, ties rows to the file's printed
// total and withholds the names of private individuals when it publishes (api/_finance/publish.js). Contract lists
// get the same treatment here. Nothing published is edited: a corrected file is sent again and the old one withdrawn.
const crypto = require('crypto');
const {readGrid} = require('./_finance/parse');
const {mapColumns, normHeader} = require('./_finance/detect');
const {money, date: toDate, fiscalYear} = require('./_finance/normalize');
const {sha256, safeName} = require('./_finance/pipeline');
const {isOrganization} = require('./_finance/publish');
const cutoff = require('./_cutoff');
const L = require('./_record_lists');
const V = require('./_records_verify');
const {confirmReport} = require('./_records_report');

const bad = (msg, status = 400) => Object.assign(new Error(msg), {status});
const MAX_INLINE = 3 * 1024 * 1024;

const KINDS = {
  checkbook: {label: 'Checkbook (every payment)', shape: 'disbursements', every: 'month',
    hint: 'The check register or payments report from your accounting system, for one or more whole months. Excel or CSV.'},
  budget: {label: 'Budget vs. actual', shape: 'budget', every: 'quarter',
    hint: 'The budget-vs-actual (or revenue and expenditure) report, as of a month end. Excel or CSV.'},
  contracts: {label: 'Contracts awarded', every: 'month',
    hint: 'A list of contracts, purchase orders over your bid limit or awards approved: vendor, amount and award date at least. Excel or CSV.'},
  ...Object.fromEntries(Object.entries(L.LISTS).map(([k, v]) => [k, {label: v.label, every: v.every, hint: v.hint}])),
};
// Kinds kept in gov.submissions (everything the finance importer doesn't read).
const SUB_KINDS = ['contracts', ...Object.keys(L.LISTS)];
const SHAPE_KIND = {disbursements: 'checkbook', budget: 'budget'};

// Template columns staff can download (also the columns a contract list is matched against).
const TEMPLATES = {
  checkbook: ['Check Date', 'Check Number', 'Vendor', 'Amount', 'Invoice Number', 'Fund', 'Account', 'Description', 'Status'],
  budget: ['Fund', 'Department', 'Account', 'Description', 'Original Budget', 'Amended Budget', 'YTD Actual', 'Encumbered'],
  contracts: ['Title', 'Vendor', 'Amount', 'Award Date', 'Method', 'Solicitation Number', 'Start Date', 'End Date', 'Approving Meeting', 'Document Link'],
  ...Object.fromEntries(Object.entries(L.LISTS).map(([k, v]) => [k, v.template])),
};

/* ---------- contract lists ---------- */
const CONTRACT_FIELDS = {
  vendor: ['vendor', 'vendor name', 'contractor', 'awarded to', 'company', 'supplier', 'firm', 'consultant', 'payee'],
  amount: ['amount', 'contract amount', 'award amount', 'contract value', 'value', 'not to exceed', 'nte', 'total', 'price', 'cost'],
  award_date: ['award date', 'date awarded', 'approval date', 'date approved', 'approved', 'execution date', 'date executed', 'board date', 'meeting date', 'date'],
  title: ['title', 'contract title', 'purpose', 'description', 'project', 'project name', 'scope', 'scope of work', 'contract name', 'subject'],
  method: ['method', 'procurement method', 'award method', 'how awarded', 'solicitation type', 'bid type', 'type'],
  solicitation: ['solicitation number', 'solicitation', 'bid number', 'bid no', 'rfp', 'itb', 'rfq', 'rfp no', 'itb no'],
  start: ['start date', 'term start', 'effective date', 'begin date', 'start'],
  end: ['end date', 'term end', 'expiration date', 'expiration', 'expires', 'end'],
  meeting: ['approving meeting', 'meeting', 'agenda item', 'resolution', 'resolution number', 'item'],
  link: ['document link', 'link', 'url', 'document', 'contract link', 'pdf'],
};
const CONTRACT_REQUIRED = [['vendor'], ['amount'], ['award_date']];
const METHODS = [
  [/\bitb\b|invitation to bid|sealed bid|competitive bid|low bid/i, 'Competitive sealed bid (invitation to bid)'],
  [/\brfp\b|request for proposals?/i, 'Request for proposals'],
  [/\brfq\b|request for qualifications|ccna/i, 'Request for qualifications'],
  [/piggy|cooperative|co-op|state contract|sourcewell|gsa\b/i, 'Cooperative purchasing (piggyback)'],
  [/sole source|single source/i, 'Sole source'],
  [/emergency/i, 'Emergency purchase'],
  [/quote/i, 'Quotes'],
];
const methodLabel = v => { const s = String(v || '').trim(); if (!s) return null; const m = METHODS.find(([re]) => re.test(s)); return m ? m[1] : s.slice(0, 120); };
const clean = (v, n = 300) => { if (v === null || v === undefined) return null; const s = (v instanceof Date ? v.toISOString().slice(0, 10) : String(v)).replace(/\s+/g, ' ').trim(); return s ? s.slice(0, n) : null; };
const https = v => { const s = clean(v, 500); return s && /^https:\/\/[^\s<>"]+$/i.test(s) ? s : null; };

// Pure: a grid of cells -> {ok, missing, headers, mapping, rows, skipped, reasons}. rows are publishable contracts.
function readContracts(grid) {
  let best = null;
  grid.slice(0, 40).forEach((row, idx) => {
    if (row.filter(v => typeof v === 'string' && /[a-z]/i.test(v)).length < 2) return;
    const headers = row.map(v => (typeof v === 'string' ? v : v instanceof Date ? '' : String(v ?? '')));
    const m = mapColumns(headers, CONTRACT_FIELDS), ok = CONTRACT_REQUIRED.every(a => a.some(f => m[f] !== undefined));
    const score = (ok ? 100 : 0) + Object.keys(m).length;
    if (!best || score > best.score) best = {score, idx, headers, m, ok};
  });
  if (!best) return {ok: false, missing: ['a header row'], headers: [], mapping: {}, rows: [], skipped: 0, reasons: {}};
  const missing = CONTRACT_REQUIRED.filter(a => !a.some(f => best.m[f] !== undefined)).map(a => a.join(' or ').replace('award_date', 'award date'));
  const mapping = Object.fromEntries(Object.entries(best.m).map(([f, i]) => [f, best.headers[i]]));
  if (missing.length) return {ok: false, missing, headers: best.headers, mapping, rows: [], skipped: 0, reasons: {}};
  const pick = (r, f) => (best.m[f] === undefined ? undefined : r[best.m[f]]);
  const rows = [], reasons = {};
  const skip = why => { reasons[why] = (reasons[why] || 0) + 1; };
  for (const r of grid.slice(best.idx + 1)) {
    const vendor = clean(pick(r, 'vendor'), 200), amount = money(pick(r, 'amount')), d = toDate(pick(r, 'award_date'));
    if (!vendor && amount === null) continue;                        // blank line
    if (vendor && /^(grand )?totals?\b/i.test(vendor)) continue;     // a total row
    if (!vendor) { skip('no vendor'); continue; }
    if (!(amount > 0)) { skip('no amount'); continue; }
    if (!d) { skip('no award date'); continue; }
    if (!cutoff.keep(fiscalYear(d, 10))) { skip('before 2016'); continue; }
    const org = isOrganization(vendor);
    const sol = clean(pick(r, 'solicitation'), 60), title = clean(pick(r, 'title'), 400);
    const start = toDate(pick(r, 'start')), end = toDate(pick(r, 'end')), meeting = clean(pick(r, 'meeting'), 200);
    rows.push({vendor: org ? vendor : 'Individual (name withheld)', vendor_kind: org ? 'organization' : 'individual', amount, date: d,
      purpose: [sol, org ? title : (title ? 'Contract with an individual' : null)].filter(Boolean).join(': ') || null,
      method: methodLabel(pick(r, 'method')),
      notes: [start || end ? `Term ${start || '?'} to ${end || '?'}` : null, meeting ? `Approved at ${meeting}` : null].filter(Boolean).join('. ') || null,
      source_url: org ? https(pick(r, 'link')) : null});
  }
  return {ok: true, missing: [], headers: best.headers, mapping, rows, skipped: Object.values(reasons).reduce((a, n) => a + n, 0), reasons};
}

const hash = (...p) => crypto.createHash('sha1').update(p.map(x => String(x ?? '')).join('|')).digest('hex');

// Pure: one submission's rows -> rows for the public contracts table.
function contractRows(sub, ws) {
  const sent = String(sub.submitted_at instanceof Date ? sub.submitted_at.toISOString() : sub.submitted_at || '').slice(0, 10);
  return (sub.rows || []).map(r => ({government: ws.name, vendor: r.vendor, amount: r.amount, purpose: r.purpose, date: r.date, method: r.method,
    source_title: `Sent by ${ws.name} on ${sent} (${sub.original_name})`, source_url: r.source_url || null, notes: r.notes,
    gov_id: ws.id, record_hash: `gov:${sub.id}:${hash(r.vendor, r.amount, r.date, r.purpose)}`}));
}

/* ---------- what's due ---------- */
const MONTH = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const ymd = d => d.toISOString().slice(0, 10);
const monthName = s => `${MONTH[Number(s.slice(5, 7)) - 1]} ${s.slice(0, 4)}`;
const dayOf = v => (v instanceof Date ? ymd(v) : v ? String(v).slice(0, 10) : null);

// Pure. latest: {checkbook, budget, contracts} = the newest period end published for each kind (contracts: the newest
// send). Returns one line per kind: what we'd expect by today and whether it's in.
function dueList(latest, today = new Date()) {
  const t = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), 1));
  const lastMonthEnd = ymd(new Date(t - 864e5));
  const q = Math.floor(today.getUTCMonth() / 3) * 3;                     // first month of this quarter
  const lastQuarterEnd = ymd(new Date(Date.UTC(today.getUTCFullYear(), q, 0)));
  const monthAgo = ymd(new Date(today - 31 * 864e5));
  const fy = L.fiscalYearOf(today), fyStart = `${fy - 1}-10-01`;
  const line = (kind, want, have, text) => ({kind, label: KINDS[kind].label, want, have: have || null, current: Boolean(have && have >= want), text});
  return [
    line('checkbook', lastMonthEnd, latest.checkbook, `Payments through ${monthName(lastMonthEnd)}`),
    line('budget', lastQuarterEnd, latest.budget, `Budget vs. actual as of ${monthName(lastQuarterEnd)}`),
    line('contracts', monthAgo, latest.contracts, 'Contracts awarded in the last month'),
    line('payroll', fyStart, latest.payroll, `Pay by job title for FY${fy}`),
  ];
}

/* ---------- reads ---------- */
async function inboundAddress(q, wsId) {
  const [s] = await q('select inbound_address from ingest.sources where finance_workspace_id = $1 and active order by created_at limit 1', [wsId]).catch(() => []);
  return s ? s.inbound_address : null;
}

async function latestByKind(q, wsId) {
  const f = await q(`select shape, max(period_end)::text latest from finance.uploads where workspace_id = $1 and published_at is not null
                     and shape in ('disbursements', 'budget') group by shape`, [wsId]);
  const c = await q(`select kind, max(published_at) latest from gov.submissions where workspace_id = $1 and status = 'published' group by kind`, [wsId]);
  const out = {checkbook: null, budget: null, contracts: null, payroll: null};
  for (const r of c) out[r.kind] = dayOf(r.latest);
  for (const r of f) out[SHAPE_KIND[r.shape]] = r.latest;
  return out;
}

// What staff see for each file: waiting (for their OK), held (doesn't add up to its own total), checking, in_review
// (a check didn't pass; the admin decides), published, not_published (the admin held it after review), withdrawn.
function fileStatus(base, v) {
  if (base === 'preview') return 'waiting';
  if (base === 'held_total') return 'held';
  if (base === 'published' || base === 'withdrawn') return base;
  if (!v) return 'checking';
  return v.decision === 'hold' ? 'not_published' : v.decision === 'publish' ? 'published' : 'in_review';
}
const verdict = v => (v ? {status: v.status, counts: v.counts, checked_at: v.checked_at, decision: v.decision, decided_at: v.decided_at, note: v.note,
  findings: (v.checks || []).filter(c => c.status !== 'match').slice(0, 40), matched: (v.checks || []).filter(c => c.status === 'match').length} : null);

// Everything the Send records tab shows.
async function overview(q, ws, today = new Date()) {
  const files = await q(`select id, shape, original_name, status, uploaded_by, uploaded_at, period_start::text period_start, period_end::text period_end,
      row_count, tie_status, tie_difference, error, published_at, published_by, sha256 from finance.uploads
      where workspace_id = $1 and shape in ('disbursements', 'budget') and status in ('preview', 'committed', 'held') order by uploaded_at desc limit 60`, [ws.id]);
  const subs = await q(`select id, kind, original_name, status, submitted_by, submitted_at, sent_by, sent_at, period_start::text period_start, period_end::text period_end,
      row_count, skipped, published_at, published_by, withdrawn_at, sha256 from gov.submissions where workspace_id = $1 order by submitted_at desc limit 60`, [ws.id]);
  const checks = new Map((await q('select * from gov.verifications where workspace_id = $1', [ws.id]).catch(() => [])).map(v => [v.file_id, v]));
  const list = [
    ...files.map(u => { const v = checks.get('f' + u.id); return {id: 'f' + u.id, kind: SHAPE_KIND[u.shape], name: u.original_name, sha256: u.sha256,
      status: fileStatus(u.status === 'held' ? 'held_total' : u.status === 'preview' ? 'preview' : u.published_at ? 'published' : 'confirmed', v),
      via: /^email:/.test(u.uploaded_by || '') ? 'email' : 'upload', sent_by: String(u.uploaded_by || '').replace(/^email:\s*/, ''), sent_at: u.uploaded_at,
      period_start: u.period_start, period_end: u.period_end, rows: u.row_count, tie: u.tie_status, difference: u.tie_difference, problem: u.error,
      published_at: u.published_at, published_by: u.published_by, check: verdict(v)}; }),
    ...subs.map(s => { const v = checks.get('c' + s.id); return {id: 'c' + s.id, kind: s.kind, name: s.original_name, sha256: s.sha256,
      status: fileStatus(s.status === 'preview' ? 'preview' : s.status === 'published' || s.status === 'withdrawn' ? s.status : 'confirmed', v),
      via: 'upload', sent_by: s.submitted_by, sent_at: s.submitted_at, confirmed_by: s.sent_by, confirmed_at: s.sent_at, period_start: s.period_start,
      period_end: s.period_end, rows: s.row_count, skipped: s.skipped, published_at: s.published_at, published_by: s.published_by, check: verdict(v)}; }),
  ].sort((a, b) => new Date(b.sent_at) - new Date(a.sent_at));
  const [src] = await q('select allowed_senders, gov_domain from ingest.sources where finance_workspace_id = $1 and active order by created_at limit 1', [ws.id]).catch(() => []);
  return {address: await inboundAddress(q, ws.id), senders: src ? src.allowed_senders || [] : [], gov_domain: src ? src.gov_domain || null : null,
    kinds: KINDS, templates: TEMPLATES, due: dueList(await latestByKind(q, ws.id), today), files: list, feeds: await feeds(q, ws)};
}

/* ---------- feeds we already read (data_sources) and the government's OK for each ---------- */
async function feeds(q, ws) {
  const rows = await q(`select source_name, source_url, method, refresh, what_we_take, page from data_sources
      where gov_id = $1 and method like 'Automatic%' and coalesce(source_url, '') <> '' order by source_name`, [ws.id]).catch(() => []);
  const ok = await q('select source_url, agreed_by, agreed_at from gov.feed_agreements where workspace_id = $1', [ws.id]).catch(() => []);
  const seen = new Set();
  return rows.filter(r => !seen.has(r.source_url) && seen.add(r.source_url)).map(r => {
    const a = ok.find(x => x.source_url === r.source_url);
    return {name: r.source_name, url: r.source_url, how_often: r.refresh || r.method, takes: r.what_we_take, page: r.page,
      agreed: Boolean(a), agreed_by: a ? a.agreed_by : null, agreed_at: a ? a.agreed_at : null};
  });
}

// A government says yes (or takes it back) to a source we read automatically.
async function feedAgree(deps, ws, b, who) {
  const url = String(b.url || '');
  const [src] = await deps.q(`select source_url from data_sources where gov_id = $1 and source_url = $2 limit 1`, [ws.id, url]);
  if (!src) throw bad('That source isn’t one we read for your government.', 404);
  if (b.agree === false) await deps.q('delete from gov.feed_agreements where workspace_id = $1 and source_url = $2', [ws.id, url]);
  else await deps.q(`insert into gov.feed_agreements (workspace_id, source_url, agreed_by) values ($1, $2, $3)
      on conflict (workspace_id, source_url) do update set agreed_by = excluded.agreed_by, agreed_at = now()`, [ws.id, url, who.email]);
  await deps.log(deps.q, ws.id, who.email, b.agree === false ? 'feed_unagreed' : 'feed_agreed', {title: url});
  return {ok: true, agreed: b.agree !== false};
}

/* ---------- staff actions ---------- */
function parseId(v) {
  const m = String(v || '').match(/^([fc])(\d{1,12})$/);
  if (!m) throw bad('Choose a file.');
  return {type: m[1], id: Number(m[2])};
}

async function readBuffer(deps, ws, b) {
  let buffer, path = b.path ? String(b.path) : null;
  const filename = safeName(b.filename || (path && path.split('/').pop()));
  if (b.content) {
    buffer = Buffer.from(String(b.content), 'base64');
    if (buffer.length > MAX_INLINE) throw bad('That file is too big to send directly. Ask for an upload link first (submit-url).', 413);
  } else if (path) {
    if (!path.startsWith(ws.id + '/') || path.includes('..')) throw bad('That file path isn’t in this workspace.');
    buffer = await deps.storage.get(path);
  } else throw bad('Choose a file to send.');
  if (!buffer.length) throw bad('The file is empty.');
  return {buffer, path, filename};
}

async function uploadUrl(deps, ws, b) {
  const name = safeName(b.filename);
  const path = `${ws.id}/staff/${crypto.randomBytes(8).toString('hex')}/${name}`;
  return {path, ...(await deps.storage.signedUpload(path))};
}

// Reads a file and saves it as waiting for a check. Returns the preview staff confirm.
async function preview(deps, ws, b, who) {
  const kind = String(b.kind || '');
  if (!KINDS[kind]) throw bad('Choose what kind of record this is: checkbook, budget or contracts.');
  if (KINDS[kind].shape) {
    const r = await deps.ingest(deps, ws.id, {filename: b.filename, content: b.content, path: b.path, upload_id: b.upload_id, shape: KINDS[kind].shape, mapping: b.mapping,
      printed_total: b.printed_total, as_of: b.as_of, fiscal_year: b.fiscal_year, commit: false, source_system: b.source_system}, {email: who.email});
    return {id: 'f' + r.upload_id, kind, ok: r.ok, missing: r.missing, label: r.label, headers: r.headers, mapping: r.mapping, row_count: r.row_count,
      parsed_total: r.parsed_total, printed_total: r.printed_total, tie: r.tie, warnings: r.warnings, period: r.period, fiscal_year: r.fiscal_year, sample: r.sample,
      used_saved_mapping: r.used_saved_mapping, already_added: r.already_added, report: r.report || null};
  }
  const {buffer, path: given, filename} = await readBuffer(deps, ws, b);
  const grid = await readGrid(filename, buffer);
  if (L.LISTS[kind]) return previewList(deps, ws, kind, L.readList(kind, grid.rows), {buffer, path: given, filename}, who);
  const c = readContracts(grid.rows);
  const sha = sha256(buffer);
  let path = given;
  if (!path && deps.storage.configured()) { path = `${ws.id}/records/${sha.slice(0, 16)}/${filename}`; await deps.storage.put(path, buffer); }
  // Already on the site (from minutes or an earlier file): same government, vendor, amount and date.
  const dupes = c.rows.length ? await q_dupes(deps.q, ws, c.rows) : new Set();
  const rows = c.rows.filter((r, i) => !dupes.has(i));
  const dates = rows.map(r => r.date).sort();
  const [s] = await deps.q(`insert into gov.submissions (workspace_id, kind, original_name, storage_path, sha256, bytes, submitted_by, row_count, skipped, rows, period_start, period_end)
      values ($1, 'contracts', $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) returning id`,
    [ws.id, filename, path, sha, buffer.length, who.email, rows.length, c.skipped, JSON.stringify(rows), dates[0] || null, dates[dates.length - 1] || null]);
  return {id: 'c' + s.id, kind, ok: c.ok && rows.length > 0, missing: c.ok ? (rows.length ? [] : ['at least one new contract (every row was skipped or is already on the site)']) : c.missing,
    label: KINDS.contracts.label, headers: c.headers, mapping: c.mapping, row_count: rows.length, skipped: c.skipped, reasons: c.reasons, already_on_site: dupes.size,
    withheld: rows.filter(r => r.vendor_kind === 'individual').length, period: {start: dates[0] || null, end: dates[dates.length - 1] || null},
    parsed_total: Math.round(rows.reduce((a, r) => a + r.amount, 0) * 100) / 100, sample: rows.slice(0, 15), report: confirmReport('contracts', rows)};
}

// Saves a list kind (payroll, appointments, fees) as waiting and returns its preview.
async function previewList(deps, ws, kind, r, file, who) {
  let path = file.path, sha = file.buffer ? sha256(file.buffer) : crypto.randomBytes(16).toString('hex');
  if (file.buffer && !path && deps.storage.configured()) { path = `${ws.id}/records/${sha.slice(0, 16)}/${file.filename}`; await deps.storage.put(path, file.buffer); }
  const dates = r.rows.map(x => x.term_start || x.effective_date).filter(Boolean).sort();
  const [s] = await deps.q(`insert into gov.submissions (workspace_id, kind, original_name, storage_path, sha256, bytes, submitted_by, row_count, skipped, rows, period_start, period_end)
      values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12) returning id`,
    [ws.id, kind, file.filename, path || null, sha, file.buffer ? file.buffer.length : 0, who.email, r.rows.length, r.skipped, JSON.stringify(r.rows),
      dates[0] || null, dates[dates.length - 1] || null]);
  const spec = L.LISTS[kind];
  return {id: 'c' + s.id, kind, ok: r.ok && r.rows.length > 0, missing: r.ok ? (r.rows.length ? [] : ['at least one row to publish']) : r.missing,
    label: spec.label, headers: r.headers, mapping: r.mapping, row_count: r.rows.length, skipped: r.skipped, reasons: r.reasons,
    names_removed: kind === 'payroll' ? r.rows.reduce((a, x) => a + x.names_removed, 0) : undefined,
    period: {start: dates[0] || null, end: dates[dates.length - 1] || null}, parsed_total: spec.total ? Math.round(spec.total(r.rows)) : null,
    report: confirmReport(kind, r.rows),
    sample: r.rows.slice(0, 15).map(x => (kind === 'payroll' ? {...x, salaries: undefined, people: x.salaries.length,
      typical: x.salaries.length ? x.salaries[Math.floor(x.salaries.length / 2)] : null} : x))};
}

async function q_dupes(q, ws, rows) {
  const have = await q(`select lower(vendor) v, amount::numeric a, date::text d from contracts where government_key = $1 or government = $2`, [ws.id, ws.name]).catch(() => []);
  const keys = new Set(have.map(h => `${h.v}|${Number(h.a)}|${h.d}`));
  const out = new Set();
  rows.forEach((r, i) => { if (keys.has(`${r.vendor.toLowerCase()}|${Number(r.amount)}|${r.date}`)) out.add(i); });
  return out;
}

// Step one: staff say this is the right file. A finance file is imported (and must add up to its own printed total);
// a list is marked received. Nothing is public yet. Then step two runs straight away.
async function confirm(deps, ws, b, who) {
  const {type, id} = parseId(b.id);
  const {q} = deps;
  const [done] = await q('select file_id from gov.verifications where file_id = $1', [type + id]);
  if (done) throw bad('This file was already confirmed and checked.', 409);
  if (type === 'f') {
    const [u] = await q('select id, status, shape from finance.uploads where id = $1 and workspace_id = $2', [id, ws.id]);
    if (!u || !SHAPE_KIND[u.shape]) throw bad('File not found.', 404);
    if (u.status === 'held') throw bad('This file doesn’t add up to its own printed total, so it can’t be taken in. Send a corrected file.');
    if (u.status === 'preview') {
      const r = await deps.ingest(deps, ws.id, {upload_id: id, commit: true, shape: u.shape, printed_total: b.printed_total, as_of: b.as_of, fiscal_year: b.fiscal_year, mapping: b.mapping},
        {email: who.email});
      if (!r.committed) {
        if (r.held) return {ok: false, held: true, message: r.message};
        throw bad(r.missing && r.missing.length ? `This file can’t be taken in yet. Missing: ${r.missing.join('; ')}.` : 'This file can’t be taken in yet.');
      }
    } else if (u.status !== 'committed') throw bad('This file was replaced or withdrawn. Send it again.');
    await deps.log(q, ws.id, who.email, 'records_confirmed', {kind: SHAPE_KIND[u.shape], file: id});
  } else {
    const [s] = await q('select id, kind, status, row_count from gov.submissions where id = $1 and workspace_id = $2', [id, ws.id]);
    if (!s) throw bad('File not found.', 404);
    if (s.status === 'withdrawn') throw bad('This file was withdrawn. Send it again.');
    if (s.status !== 'preview') throw bad('This file was already confirmed.', 409);
    if (!s.row_count) throw bad('There’s nothing new in this file.');
    await q(`update gov.submissions set status = 'received', sent_at = now(), sent_by = $3 where id = $1 and workspace_id = $2`, [s.id, ws.id, who.email]);
    await deps.log(q, ws.id, who.email, 'records_confirmed', {kind: s.kind, file: s.id});
  }
  return check(deps, ws, type + id);
}

// A confirmed file as the checker reads it: {kind, sha256, rows, period_start, period_end, fiscal_year}.
async function loadFile(q, ws, fileId) {
  const {type, id} = parseId(fileId);
  if (type === 'f') {
    const [u] = await q('select id, shape, sha256, period_start::text period_start, period_end::text period_end from finance.uploads where id = $1 and workspace_id = $2', [id, ws.id]);
    if (!u) throw bad('File not found.', 404);
    const kind = SHAPE_KIND[u.shape];
    const rows = kind === 'checkbook'
      ? await q(`select paid_on::text paid_on, doc_no, method, payee, amount::float8 amount, invoice_no, fund, account, description, is_void from finance.disbursements where upload_id = $1 order by source_row`, [id])
      : await q(`select fiscal_year, as_of::text as_of, fund, department, account, description, original_budget::float8 original_budget, amended_budget::float8 amended_budget,
          actual_ytd::float8 actual_ytd, encumbered::float8 encumbered from finance.budget_lines where upload_id = $1 order by source_row`, [id]);
    const fy = kind === 'budget' ? Math.max(0, ...rows.map(r => Number(r.fiscal_year) || 0)) || null : null;
    return {kind, sha256: u.sha256, rows, period_start: u.period_start, period_end: u.period_end, fiscal_year: fy};
  }
  const [s] = await q('select id, kind, sha256, rows, period_start::text period_start, period_end::text period_end from gov.submissions where id = $1 and workspace_id = $2', [id, ws.id]);
  if (!s) throw bad('File not found.', 404);
  return {kind: s.kind, sha256: s.sha256, rows: s.rows || [], period_start: s.period_start, period_end: s.period_end, fiscal_year: null};
}

const CHECKER = 'BayCounty.me checks';

// Step two: check the file against our own records and keep the result. Verified files publish; the rest are held.
async function check(deps, ws, fileId) {
  const {q} = deps;
  const f = await loadFile(q, ws, fileId);
  const v = await V.verifyFile(q, ws, f);
  await q(`insert into gov.verifications (file_id, workspace_id, kind, file_sha256, status, checks, counts) values ($1, $2, $3, $4, $5, $6, $7)
      on conflict (file_id) do nothing`, [fileId, ws.id, f.kind, f.sha256, v.status, JSON.stringify(v.checks), JSON.stringify(v.counts)]);
  const out = {ok: true, id: fileId, kind: f.kind, check: {status: v.status, counts: v.counts, findings: v.checks.filter(c => c.status !== 'match').slice(0, 40),
    matched: v.checks.filter(c => c.status === 'match').length}};
  if (v.status === 'verified') {
    await q(`update gov.verifications set decision = 'publish', decided_by = $2, decided_at = now(), note = 'Every check matched' where file_id = $1 and decision is null`, [fileId, CHECKER]);
    const p = await release(deps, ws, fileId, {email: CHECKER});
    return {...out, status: 'published', published: p, message: `Every check matched our own records. Published ${p.rows} row${p.rows === 1 ? '' : 's'}.`};
  }
  if (fileId[0] === 'c') await q(`update gov.submissions set status = 'held' where id = $1 and workspace_id = $2 and status = 'received'`, [Number(fileId.slice(1)), ws.id]);
  return {...out, status: 'in_review',
    message: v.status === 'discrepancies' ? 'Some numbers didn’t match our own records, so this file waits for review before anything is public.'
      : 'We couldn’t confirm every record against our own sources yet, so this file waits for review before anything is public.'};
}

// Puts a confirmed and checked file's records on the public pages. Only check() (verified) and review() call it.
async function release(deps, ws, fileId, who) {
  const {type, id} = parseId(fileId);
  const {q} = deps;
  if (type === 'f') {
    const [u] = await q('select id, status, shape from finance.uploads where id = $1 and workspace_id = $2', [id, ws.id]);
    if (!u || u.status !== 'committed') throw bad('This file isn’t ready to publish.', 409);
    const p = await deps.publisher.publish(q, ws.id, id, who.email);
    await deps.log(q, ws.id, who.email, 'records_published', {kind: SHAPE_KIND[u.shape], file: id, rows: p.rows});
    return {...p, kind: SHAPE_KIND[u.shape]};
  }
  const [s] = await q('select * from gov.submissions where id = $1 and workspace_id = $2', [id, ws.id]);
  if (!s) throw bad('File not found.', 404);
  if (!['received', 'held'].includes(s.status)) throw bad('This file isn’t ready to publish.', 409);
  const t = TARGET[s.kind];
  const rows = t.rows(s, ws);
  await q(`delete from ${t.table} where origin = 'gov' and record_hash like $1`, [`gov:${s.id}:%`]);
  const cols = t.cols;
  for (let i = 0; i < rows.length; i += 200) {
    const chunk = rows.slice(i, i + 200), params = [], tuples = [];
    for (const r of chunk) {
      const ph = [...cols.map(c => r[c] ?? null), r.record_hash, r.gov_id].map(v => { params.push(v); return '$' + params.length; });
      tuples.push(`(${ph.slice(0, cols.length + 1).join(', ')}, (select key from governments where key = ${ph[cols.length + 1]}), 'gov')`);
    }
    await q(`insert into ${t.table} (${cols.join(', ')}, record_hash, government_key, origin) values ${tuples.join(', ')} on conflict (origin, record_hash) do nothing`, params);
  }
  await q(`update gov.submissions set status = 'published', published_at = now(), published_by = $3 where id = $1 and workspace_id = $2`, [s.id, ws.id, who.email]);
  await deps.log(q, ws.id, who.email, 'records_published', {kind: s.kind, file: s.id, rows: rows.length});
  return {ok: true, kind: s.kind, table: t.table, rows: rows.length, page: t.page,
    individuals_withheld: s.kind === 'contracts' ? s.rows.filter(r => r.vendor_kind === 'individual').length : 0,
    names_removed: s.kind === 'payroll' ? s.rows.reduce((a, r) => a + (r.names_removed || 0), 0) : 0};
}

/* ---------- who may email files in ---------- */
// Exact addresses only (migration 0093). A government owner keeps the list; every change goes in the activity log.
async function intakeSenders(q, ws) {
  const [s] = await q('select inbound_address, allowed_senders, gov_domain from ingest.sources where finance_workspace_id = $1 and active order by created_at limit 1', [ws.id]);
  if (!s) throw bad('This government has no intake address yet.', 404);
  return {address: s.inbound_address, senders: s.allowed_senders || [], gov_domain: s.gov_domain || null};
}

async function setIntakeSenders(deps, ws, b, who) {
  const {cleanSenders} = require('./_ledger');
  const list = cleanSenders(b.senders);
  const [s] = await deps.q('select id, allowed_senders from ingest.sources where finance_workspace_id = $1 and active order by created_at limit 1', [ws.id]);
  if (!s) throw bad('This government has no intake address yet.', 404);
  await deps.q('update ingest.sources set allowed_senders = $2 where id = $1', [s.id, list]);
  const before = new Set(s.allowed_senders || []), after = new Set(list);
  await deps.log(deps.q, ws.id, who.email, 'intake_senders_changed', {added: list.filter(a => !before.has(a)), removed: [...before].filter(a => !after.has(a))});
  return {ok: true, senders: list};
}

/* ---------- admin review of files that didn't pass every check ---------- */
const fileName = async (q, fileId) => {
  const {type, id} = parseId(fileId);
  const [r] = type === 'f'
    ? await q(`select original_name name, uploaded_by sent_by, uploaded_at sent_at, period_start::text period_start, period_end::text period_end, row_count rows, storage_path from finance.uploads where id = $1`, [id])
    : await q(`select original_name name, coalesce(sent_by, submitted_by) sent_by, coalesce(sent_at, submitted_at) sent_at, period_start::text period_start, period_end::text period_end, row_count rows, storage_path from gov.submissions where id = $1`, [id]);
  return r || {};
};

async function reviewList(q, {status = 'open'} = {}) {
  const rows = await q(`select v.*, w.name government from gov.verifications v join gov.workspaces w on w.id = v.workspace_id
      where ${status === 'open' ? 'v.decision is null' : 'v.decided_at > now() - interval \'90 days\''} order by v.checked_at desc limit 200`);
  const out = [];
  for (const v of rows) out.push({file_id: v.file_id, workspace_id: v.workspace_id, government: v.government, kind: v.kind, sha256: v.file_sha256, status: v.status,
    counts: v.counts, checks: v.checks, checked_at: v.checked_at, decision: v.decision, decided_by: v.decided_by, decided_at: v.decided_at, note: v.note, ...(await fileName(q, v.file_id))});
  return {files: out};
}

// The admin publishes a held file (findings and all) or keeps it off the site. A decision is final (migration 0093).
async function review(deps, b, admin) {
  const fileId = String(b.file_id || '');
  parseId(fileId);
  const decision = String(b.decision || '');
  if (!['publish', 'hold'].includes(decision)) throw bad('Choose publish or hold.');
  const note = String(b.note || '').trim().slice(0, 1000);
  if (decision === 'hold' && note.length < 3) throw bad('Add a note saying why this file stays off the site.');
  const {q} = deps;
  const [v] = await q('select v.*, w.name from gov.verifications v join gov.workspaces w on w.id = v.workspace_id where v.file_id = $1', [fileId]);
  if (!v) throw bad('File not found.', 404);
  if (v.decision) throw bad(`This file was already ${v.decision === 'publish' ? 'published' : 'held'} on ${new Date(v.decided_at).toISOString().slice(0, 10)}.`, 409);
  const ws = {id: v.workspace_id, name: v.name};
  await q('update gov.verifications set decision = $2, decided_by = $3, decided_at = now(), note = $4 where file_id = $1 and decision is null', [fileId, decision, admin, note || null]);
  await deps.log(q, ws.id, admin, decision === 'publish' ? 'records_review_published' : 'records_review_held', {file: fileId, kind: v.kind, note});
  if (decision === 'hold') return {ok: true, decision};
  return {ok: true, decision, published: await release(deps, ws, fileId, {email: admin})};
}

// Where each gov.submissions kind is published.
const TARGET = {
  contracts: {table: 'contracts', cols: ['government', 'vendor', 'amount', 'purpose', 'date', 'method', 'source_title', 'source_url', 'notes'],
    rows: (s, ws) => contractRows(s, ws), page: '/public-money/contracts#sent'},
  payroll: {table: 'salary_positions', cols: L.LISTS.payroll.cols, rows: (s, ws) => L.listRows('payroll', s, ws), page: '/people#staff-pay'},
  appointments: {table: 'board_appointments', cols: L.LISTS.appointments.cols.filter(c => c !== 'gov_id').concat('gov_id'),
    rows: (s, ws) => L.listRows('appointments', s, ws), page: '/people#appointments'},
  fees: {table: 'fee_changes', cols: L.LISTS.fees.cols.filter(c => c !== 'gov_id').concat('gov_id'), rows: (s, ws) => L.listRows('fees', s, ws), page: '/public-money/fees-and-bills#changes'},
};

// Takes a published file's records off the public pages (the file stays on record here).
async function withdraw(deps, ws, b, who) {
  const {type, id} = parseId(b.id);
  const {q} = deps;
  let removed = 0, kind;
  if (type === 'f') {
    const [u] = await q('select id, status, shape from finance.uploads where id = $1 and workspace_id = $2', [id, ws.id]);
    if (!u || !SHAPE_KIND[u.shape]) throw bad('File not found.', 404);
    kind = SHAPE_KIND[u.shape];
    if (u.status === 'preview') await q(`update finance.uploads set status = 'replaced' where id = $1 and workspace_id = $2`, [id, ws.id]);
    else removed = (await deps.publisher.unpublish(q, ws.id, id)).removed;
  } else {
    const [s] = await q('select id, kind from gov.submissions where id = $1 and workspace_id = $2', [id, ws.id]);
    if (!s) throw bad('File not found.', 404);
    kind = s.kind;
    removed = (await q(`delete from ${TARGET[s.kind].table} where origin = 'gov' and record_hash like $1 returning id`, [`gov:${s.id}:%`])).length;
    await q(`update gov.submissions set status = 'withdrawn', withdrawn_at = now(), withdrawn_by = $3 where id = $1 and workspace_id = $2`, [s.id, ws.id, who.email]);
  }
  await deps.log(q, ws.id, who.email, 'records_withdrawn', {kind, file: id, removed});
  return {ok: true, removed};
}

/* ---------- public: who sends what (scorecard) + contracts staff sent ---------- */
async function publicSent(q, query = {}, today = new Date()) {
  const gov = query.gov ? String(query.gov) : null;
  if (gov && !/^[a-z0-9_-]{1,40}$/.test(gov)) throw Object.assign(new Error('Unknown government.'), {status: 400, expose: true});
  const wss = await q(`select id, name from gov.workspaces where ($1::text is null or id = $1) order by countywide desc, name`, [gov]);
  const f = await q(`select workspace_id, shape, count(*)::int files, sum(row_count)::int rows, max(period_end)::text latest, max(published_at) last_sent
      from finance.uploads where published_at is not null and shape in ('disbursements', 'budget') group by workspace_id, shape`);
  const c = await q(`select workspace_id, kind, count(*)::int files, sum(row_count)::int rows, max(period_end)::text latest, max(published_at) last_sent
      from gov.submissions where status = 'published' group by workspace_id, kind`);
  const agreed = await q('select workspace_id, count(*)::int n from gov.feed_agreements group by workspace_id').catch(() => []);
  const governments = wss.map(w => {
    const kinds = {};
    for (const r of f.filter(x => x.workspace_id === w.id)) kinds[SHAPE_KIND[r.shape]] = {files: r.files, rows: r.rows || 0, latest: r.latest, last_sent: dayOf(r.last_sent)};
    for (const cr of c.filter(x => x.workspace_id === w.id)) kinds[cr.kind] = {files: cr.files, rows: cr.rows || 0, latest: cr.latest, last_sent: dayOf(cr.last_sent)};
    const last = k => kinds[k] && kinds[k].last_sent;
    const due = dueList({checkbook: kinds.checkbook && kinds.checkbook.latest, budget: kinds.budget && kinds.budget.latest, contracts: last('contracts'), payroll: last('payroll')}, today);
    const records = Object.fromEntries(Object.keys(KINDS).map(k => {
      const d = due.find(x => x.kind === k), have = kinds[k];
      return [k, {status: !have ? 'not_sent' : !d || d.current ? 'current' : 'behind', files: have ? have.files : 0, rows: have ? have.rows : 0,
        latest: have ? have.latest : null, last_sent: have ? have.last_sent : null}];
    }));
    const fa = agreed.find(x => x.workspace_id === w.id);
    return {gov_id: w.id, government: w.name, sends: Object.values(records).some(r => r.files > 0), feeds_agreed: fa ? fa.n : 0, records};
  });
  const contracts = await q(`select government, vendor, amount, purpose, date::text date, method, source_title, source_url, notes, government_key gov_id
      from contracts where origin = 'gov' and ($1::text is null or government_key = $1) order by date desc, id desc limit 200`, [gov]);
  const appointments = await q(`select government, board, seat, person, appointed_by, term_start::text term_start, term_end::text term_end, notes, source_url, source_title, gov_id
      from board_appointments where origin = 'gov' and ($1::text is null or gov_id = $1) order by government, board, seat nulls last, person limit 500`, [gov]).catch(() => []);
  const fees = await q(`select government, fee, category, old_amount, new_amount, unit, effective_date::text effective_date, adopted_by, source_url, source_title, gov_id
      from fee_changes where origin = 'gov' and ($1::text is null or gov_id = $1) order by effective_date desc nulls last, id desc limit 300`, [gov]).catch(() => []);
  const payroll = await q(`select employer government, employer_id gov_id, fiscal_year, title, department, grade, pay_min, pay_max, actual_salaries, budgeted_fte, notes
      from salary_positions where origin = 'gov' and ($1::text is null or employer_id = $1) order by employer, department nulls last, title limit 1000`, [gov]).catch(() => []);
  const num = v => (v === null || v === undefined ? null : Number(v));
  return {data: {governments, contracts: contracts.map(r => ({...r, amount: Number(r.amount)})), appointments,
    payroll: payroll.map(r => ({...r, pay_min: num(r.pay_min), pay_max: num(r.pay_max), budgeted_fte: num(r.budgeted_fte), actual_salaries: r.actual_salaries || []})),
    fees: fees.map(r => ({...r, old_amount: num(r.old_amount), new_amount: num(r.new_amount)}))},
    note: 'Records each government sends to BayCounty.me directly from its own systems: check registers (checkbook-payments), budget-vs-actual reports (budget-actuals), contract lists (contracts, origin gov), pay by job title (salary-positions, origin gov), board appointments (board-appointments) and fee or rate changes (fee-changes). status: current = in for the latest period we expect (last month for payments, last quarter for budgets, the last month for contracts, this fiscal year for payroll; appointments and fees whenever they change), behind = sent before but not the latest, not_sent = nothing yet. feeds_agreed = sources we read automatically that the government has said yes to. Payments to private individuals and contracts with individuals are listed without the person\'s name; payroll never names employees.'};
}

function templateCsv(kind) {
  if (!TEMPLATES[kind]) throw bad('Unknown template.', 404);
  return TEMPLATES[kind].join(',') + '\n';
}

module.exports = {KINDS, SUB_KINDS, TEMPLATES, CONTRACT_FIELDS, readContracts, contractRows, dueList, overview, preview, confirm, check, release, review, reviewList,
  loadFile, intakeSenders, setIntakeSenders, withdraw, feeds, feedAgree,
  uploadUrl, publicSent, templateCsv, parseId, normHeader};
