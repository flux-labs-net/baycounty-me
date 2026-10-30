// Records submission (Send records, in the government workspace /staff): a government's own staff send the files
// their systems already make, we read them, staff check a preview, and the records are published. Used by
// api/gov.js (staff actions) and api/v1.js (/records-sent, the public scorecard). Tables: migration 0091.
//
// Three kinds of record in Phase 1:
//  * checkbook: a check register or payments export -> the finance importer (shape 'disbursements') -> checkbook_payments
//  * budget:    a budget-vs-actual report           -> the finance importer (shape 'budget')        -> budget_actuals
//  * contracts: a list of contracts awarded          -> read here, kept in gov.submissions            -> contracts (origin 'gov')
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

const bad = (msg, status = 400) => Object.assign(new Error(msg), {status});
const MAX_INLINE = 3 * 1024 * 1024;

const KINDS = {
  checkbook: {label: 'Checkbook (every payment)', shape: 'disbursements', every: 'month',
    hint: 'The check register or payments report from your accounting system, for one or more whole months. Excel or CSV.'},
  budget: {label: 'Budget vs. actual', shape: 'budget', every: 'quarter',
    hint: 'The budget-vs-actual (or revenue and expenditure) report, as of a month end. Excel or CSV.'},
  contracts: {label: 'Contracts awarded', every: 'month',
    hint: 'A list of contracts, purchase orders over your bid limit or awards approved: vendor, amount and award date at least. Excel or CSV.'},
};
const SHAPE_KIND = {disbursements: 'checkbook', budget: 'budget'};

// Template columns staff can download (also the columns a contract list is matched against).
const TEMPLATES = {
  checkbook: ['Check Date', 'Check Number', 'Vendor', 'Amount', 'Invoice Number', 'Fund', 'Account', 'Description', 'Status'],
  budget: ['Fund', 'Department', 'Account', 'Description', 'Original Budget', 'Amended Budget', 'YTD Actual', 'Encumbered'],
  contracts: ['Title', 'Vendor', 'Amount', 'Award Date', 'Method', 'Solicitation Number', 'Start Date', 'End Date', 'Approving Meeting', 'Document Link'],
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
  const line = (kind, want, have, text) => ({kind, label: KINDS[kind].label, want, have: have || null, current: Boolean(have && have >= want), text});
  return [
    line('checkbook', lastMonthEnd, latest.checkbook, `Payments through ${monthName(lastMonthEnd)}`),
    line('budget', lastQuarterEnd, latest.budget, `Budget vs. actual as of ${monthName(lastQuarterEnd)}`),
    line('contracts', monthAgo, latest.contracts, 'Contracts awarded in the last month'),
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
  const [c] = await q(`select max(published_at) latest from gov.submissions where workspace_id = $1 and status = 'published'`, [wsId]);
  const out = {checkbook: null, budget: null, contracts: c && c.latest ? dayOf(c.latest) : null};
  for (const r of f) out[SHAPE_KIND[r.shape]] = r.latest;
  return out;
}

const fileStatus = u => (u.status === 'held' ? 'held' : u.status === 'preview' ? 'waiting' : u.published_at ? 'published' : 'not_public');

// Everything the Send records tab shows.
async function overview(q, ws, today = new Date()) {
  const files = await q(`select id, shape, original_name, status, uploaded_by, uploaded_at, period_start::text period_start, period_end::text period_end,
      row_count, tie_status, tie_difference, error, published_at, published_by from finance.uploads
      where workspace_id = $1 and shape in ('disbursements', 'budget') and status in ('preview', 'committed', 'held') order by uploaded_at desc limit 60`, [ws.id]);
  const subs = await q(`select id, kind, original_name, status, submitted_by, submitted_at, period_start::text period_start, period_end::text period_end,
      row_count, skipped, published_at, published_by, withdrawn_at from gov.submissions where workspace_id = $1 order by submitted_at desc limit 60`, [ws.id]);
  const list = [
    ...files.map(u => ({id: 'f' + u.id, kind: SHAPE_KIND[u.shape], name: u.original_name, status: fileStatus(u), via: /^email:/.test(u.uploaded_by || '') ? 'email' : 'upload',
      sent_by: String(u.uploaded_by || '').replace(/^email:\s*/, ''), sent_at: u.uploaded_at, period_start: u.period_start, period_end: u.period_end, rows: u.row_count,
      tie: u.tie_status, difference: u.tie_difference, problem: u.error, published_at: u.published_at, published_by: u.published_by})),
    ...subs.map(s => ({id: 'c' + s.id, kind: s.kind, name: s.original_name, status: s.status === 'preview' ? 'waiting' : s.status, via: 'upload', sent_by: s.submitted_by,
      sent_at: s.submitted_at, period_start: s.period_start, period_end: s.period_end, rows: s.row_count, skipped: s.skipped, published_at: s.published_at, published_by: s.published_by})),
  ].sort((a, b) => new Date(b.sent_at) - new Date(a.sent_at));
  return {address: await inboundAddress(q, ws.id), kinds: KINDS, templates: TEMPLATES, due: dueList(await latestByKind(q, ws.id), today), files: list};
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
  if (kind !== 'contracts') {
    const r = await deps.ingest(deps, ws.id, {filename: b.filename, content: b.content, path: b.path, upload_id: b.upload_id, shape: KINDS[kind].shape, mapping: b.mapping,
      printed_total: b.printed_total, as_of: b.as_of, fiscal_year: b.fiscal_year, commit: false, source_system: b.source_system}, {email: who.email});
    return {id: 'f' + r.upload_id, kind, ok: r.ok, missing: r.missing, label: r.label, headers: r.headers, mapping: r.mapping, row_count: r.row_count,
      parsed_total: r.parsed_total, printed_total: r.printed_total, tie: r.tie, warnings: r.warnings, period: r.period, fiscal_year: r.fiscal_year, sample: r.sample,
      used_saved_mapping: r.used_saved_mapping, already_added: r.already_added};
  }
  const {buffer, path: given, filename} = await readBuffer(deps, ws, b);
  const grid = await readGrid(filename, buffer);
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
    parsed_total: Math.round(rows.reduce((a, r) => a + r.amount, 0) * 100) / 100, sample: rows.slice(0, 15)};
}

async function q_dupes(q, ws, rows) {
  const have = await q(`select lower(vendor) v, amount::numeric a, date::text d from contracts where government_key = $1 or government = $2`, [ws.id, ws.name]).catch(() => []);
  const keys = new Set(have.map(h => `${h.v}|${Number(h.a)}|${h.d}`));
  const out = new Set();
  rows.forEach((r, i) => { if (keys.has(`${r.vendor.toLowerCase()}|${Number(r.amount)}|${r.date}`)) out.add(i); });
  return out;
}

// Confirms a previewed file and publishes it.
async function publish(deps, ws, b, who) {
  const {type, id} = parseId(b.id);
  const {q} = deps;
  if (type === 'f') {
    const [u] = await q('select id, status, shape from finance.uploads where id = $1 and workspace_id = $2', [id, ws.id]);
    if (!u || !SHAPE_KIND[u.shape]) throw bad('File not found.', 404);
    if (u.status === 'preview') {
      const r = await deps.ingest(deps, ws.id, {upload_id: id, commit: true, shape: u.shape, printed_total: b.printed_total, as_of: b.as_of, fiscal_year: b.fiscal_year, mapping: b.mapping},
        {email: who.email});
      if (!r.committed) {
        if (r.held) return {ok: false, held: true, message: r.message};
        throw bad(r.missing && r.missing.length ? `This file can’t be published yet. Missing: ${r.missing.join('; ')}.` : 'This file can’t be published yet.');
      }
    } else if (u.status === 'held') throw bad('This file doesn’t add up to its own printed total, so it can’t be published. Send a corrected file.');
    const p = await deps.publisher.publish(q, ws.id, id, who.email);
    await deps.log(q, ws.id, who.email, 'records_published', {kind: SHAPE_KIND[u.shape], file: id, rows: p.rows});
    return {...p, kind: SHAPE_KIND[u.shape]};
  }
  const [s] = await q('select * from gov.submissions where id = $1 and workspace_id = $2', [id, ws.id]);
  if (!s) throw bad('File not found.', 404);
  if (s.status === 'withdrawn') throw bad('This file was withdrawn. Send it again to publish it.');
  if (!s.rows.length) throw bad('There’s nothing new to publish in this file.');
  const rows = contractRows(s, ws);
  await q(`delete from contracts where origin = 'gov' and record_hash like $1`, [`gov:${s.id}:%`]);
  const cols = ['government', 'vendor', 'amount', 'purpose', 'date', 'method', 'source_title', 'source_url', 'notes'];
  for (let i = 0; i < rows.length; i += 200) {
    const chunk = rows.slice(i, i + 200), params = [], tuples = [];
    for (const r of chunk) {
      const ph = [...cols.map(c => r[c] ?? null), r.record_hash, r.gov_id].map(v => { params.push(v); return '$' + params.length; });
      tuples.push(`(${ph.slice(0, cols.length + 1).join(', ')}, (select key from governments where key = ${ph[cols.length + 1]}), 'gov')`);
    }
    await q(`insert into contracts (${cols.join(', ')}, record_hash, government_key, origin) values ${tuples.join(', ')} on conflict (origin, record_hash) do nothing`, params);
  }
  await q(`update gov.submissions set status = 'published', published_at = now(), published_by = $3 where id = $1 and workspace_id = $2`, [s.id, ws.id, who.email]);
  await deps.log(q, ws.id, who.email, 'records_published', {kind: 'contracts', file: s.id, rows: rows.length});
  return {ok: true, kind: 'contracts', table: 'contracts', rows: rows.length, individuals_withheld: s.rows.filter(r => r.vendor_kind === 'individual').length, page: '/public-money/contracts#sent'};
}

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
    removed = (await q(`delete from contracts where origin = 'gov' and record_hash like $1 returning id`, [`gov:${s.id}:%`])).length;
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
  const c = await q(`select workspace_id, count(*)::int files, sum(row_count)::int rows, max(period_end)::text latest, max(published_at) last_sent
      from gov.submissions where status = 'published' group by workspace_id`);
  const governments = wss.map(w => {
    const kinds = {};
    for (const r of f.filter(x => x.workspace_id === w.id)) kinds[SHAPE_KIND[r.shape]] = {files: r.files, rows: r.rows || 0, latest: r.latest, last_sent: dayOf(r.last_sent)};
    const cr = c.find(x => x.workspace_id === w.id);
    if (cr) kinds.contracts = {files: cr.files, rows: cr.rows || 0, latest: cr.latest, last_sent: dayOf(cr.last_sent)};
    const due = dueList({checkbook: kinds.checkbook && kinds.checkbook.latest, budget: kinds.budget && kinds.budget.latest, contracts: kinds.contracts && kinds.contracts.last_sent}, today);
    const records = Object.fromEntries(Object.keys(KINDS).map(k => {
      const d = due.find(x => x.kind === k), have = kinds[k];
      return [k, {status: !have ? 'not_sent' : d.current ? 'current' : 'behind', files: have ? have.files : 0, rows: have ? have.rows : 0,
        latest: have ? have.latest : null, last_sent: have ? have.last_sent : null}];
    }));
    return {gov_id: w.id, government: w.name, sends: Object.values(records).some(r => r.files > 0), records};
  });
  const contracts = await q(`select government, vendor, amount, purpose, date::text date, method, source_title, source_url, notes, government_key gov_id
      from contracts where origin = 'gov' and ($1::text is null or government_key = $1) order by date desc, id desc limit 200`, [gov]);
  return {data: {governments, contracts: contracts.map(r => ({...r, amount: Number(r.amount)}))},
    note: 'Records each government sends to BayCounty.me directly from its own systems: check registers (checkbook-payments), budget-vs-actual reports (budget-actuals) and contract lists (contracts, origin gov). status: current = in for the latest period we expect (last month for payments, last quarter for budgets, the last month for contracts), behind = sent before but not the latest, not_sent = nothing yet. Payments to private individuals and contracts with individuals are listed without the person\'s name.'};
}

function templateCsv(kind) {
  if (!TEMPLATES[kind]) throw bad('Unknown template.', 404);
  return TEMPLATES[kind].join(',') + '\n';
}

module.exports = {KINDS, TEMPLATES, CONTRACT_FIELDS, readContracts, contractRows, dueList, overview, preview, publish, withdraw, uploadUrl, publicSent, templateCsv, parseId, normHeader};
