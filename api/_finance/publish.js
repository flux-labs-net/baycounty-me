// Publish a finance file to the public open-books tables (migration 0047): a check register's payments to
// checkbook_payments (/public-money/checkbook) and a budget-vs-actual report's lines to budget_actuals
// (/public-money/budget-tracker). Only an owner publishes, only a committed file that ties to its printed total, never
// the sample workspace. Unpublishing (or withdrawing the file) deletes its public rows.
//
// Privacy: a payee that isn't recognizably an organization is treated as a private individual (a utility refund, an
// employee reimbursement) and published without a name, its description replaced by a category. Organizations are
// named and linked to their profile (entity_id) when the site knows them. Voided checks are left out.
const crypto = require('crypto');
const {isRevenue} = require('./rules');
const {fiscalYear} = require('./normalize');

const bad = (msg, status = 400) => Object.assign(new Error(msg), {status});
const PUBLISHABLE = ['disbursements', 'budget'];
const GOV_NAME = {county: 'Bay County', schools: 'Bay District Schools', pc: 'Panama City', pcb: 'Panama City Beach', lh: 'Lynn Haven', cw: 'Callaway',
  sp: 'Springfield', parker: 'Parker', mb: 'Mexico Beach'};

// Words that mark a payee as an organization rather than a person.
const ORG = new RegExp('\\b(' + ['inc', 'incorporated', 'llc', 'l l c', 'llp', 'lp', 'ltd', 'pllc', 'pa', 'plc', 'corp', 'corporation', 'co', 'company', 'companies',
  'group', 'services?', 'svcs?', 'associates', 'assoc', 'partners', 'enterprises?', 'industries', 'solutions', 'systems', 'supply', 'supplies', 'construction',
  'contractors?', 'contracting', 'engineering', 'engineers', 'consulting', 'consultants?', 'bank', 'trust', 'insurance', 'authority', 'department', 'dept',
  'city', 'county', 'state', 'florida', 'usa', 'united states', 'district', 'board', 'commission', 'agency', 'association', 'foundation', 'church',
  'school', 'schools', 'university', 'college', 'club', 'league', 'society', 'council', 'center', 'centre', 'clinic', 'hospital', 'utilities',
  'utility', 'electric', 'power', 'energy', 'gas', 'water', 'telecom', 'communications', 'wireless', 'media', 'news', 'publishing', 'printing',
  'office', 'depot', 'store', 'stores', 'market', 'motors', 'auto', 'automotive', 'tire', 'tires', 'equipment', 'rental', 'rentals', 'holdings',
  'international', 'national', 'america', 'american', 'technologies', 'technology', 'tech', 'software', 'labs?', 'laboratories', 'medical',
  'health', 'healthcare', 'pharmacy', 'sales', 'distributors?', 'distribution', 'wholesale', 'fund', 'plan', 'retirement', 'pension', 'treasury',
  'treasurer', 'postmaster', 'usps', 'fedex', 'ups', 'amazon', 'walmart', 'lowes', 'verizon', 'comcast', 'att', 'at t', 'clerk', 'sheriff',
  'tax collector', 'property appraiser', 'irs', 'internal revenue', 'chamber', 'institute', 'academy', 'ministries', 'ministry', 'lab',
  'landscaping', 'lawn', 'pest', 'plumbing', 'roofing', 'paving', 'asphalt', 'concrete', 'electrical', 'mechanical', 'hvac', 'signs?', 'uniforms?',
  'fuel', 'oil', 'petroleum', 'chemicals?', 'materials', 'aggregates', 'graphics', 'design', 'architects?', 'surveying', 'testing', 'security',
  'alarm', 'janitorial', 'cleaning', 'waste', 'recycling', 'disposal', 'towing', 'marine', 'aviation', 'farms?', 'nursery', 'productions?',
  'studios?', 'events?', 'rentals?', 'properties', 'property', 'realty', 'management', 'mgmt', 'law', 'attorneys?', 'legal', 'cpas?', 'accounting',
  'parts', 'fleet', 'trucking', 'transport', 'transportation', 'logistics', 'freight', 'sports', 'youth', 'coastal', 'gulf', 'bay', 'panhandle',
  'emerald', 'southern', 'southeast', 'northwest', 'beach', 'harbor', 'island', 'tractor', 'hardware', 'lumber', 'glass', 'steel', 'metal',
  'machine', 'tools?', 'repair', 'welding', 'fence', 'fencing', 'pool', 'golf', 'fitness', 'library', 'museum', 'theatre', 'theater', 'press',
  'post', 'times', 'herald', 'radio', 'tv', 'cable', 'internet', 'cloud', 'data', 'digital', 'online', 'express', 'direct', 'pro', 'unlimited'].join('|') + ')\\b', 'i');

// repeat: the register pays this name again and again against invoice numbers, the way a vendor is paid.
function isOrganization(name, known, repeat = false) {
  const s = String(name || '').trim();
  if (!s) return false;
  if (known || repeat) return true;
  if (/[0-9&@/]/.test(s)) return true;                        // "A1 Lawn", "Smith & Sons", "dba"
  const words = s.toLowerCase().replace(/[.,'’]/g, '').split(/\s+/).filter(Boolean);
  if (words.length === 1) return true;                        // "AMAZON", "GRAINGER": a person's name has two parts
  return ORG.test(s.toLowerCase().replace(/[.,'’]/g, ' '));
}

function individualCategory(d) {
  const t = `${d.description || ''} ${d.account || ''}`.toLowerCase();
  if (/refund|overpay|deposit/.test(t)) return 'Refund to an individual';
  if (/reimb|mileage|travel|per diem/.test(t)) return 'Reimbursement to an individual';
  if (/settle|claim|damage/.test(t)) return 'Claim or settlement paid to an individual';
  return 'Payment to an individual';
}

// Organization names as one key, for matching to the site's profiles: lower case, no punctuation or company suffixes.
const SUFFIX = /\b(incorporated|inc|llc|l l c|llp|ltd|co|corp|corporation|company|pa|pllc|pc|the|of florida|of fl)\b/g;
const orgKey = s => String(s || '').toLowerCase().replace(/&/g, ' and ').replace(/[^a-z0-9 ]+/g, ' ').replace(SUFFIX, ' ').replace(/\s+/g, ' ').trim();

// profiles: [{entity_id, name, aliases}] (vendor, nonprofit, gov and business profiles). Returns name key -> entity_id.
function entityIndex(profiles) {
  const idx = new Map(), rank = {vendor: 0, gov: 1, nonprofit: 2, business: 3};
  const sorted = [...profiles].sort((a, b) => (rank[a.kind] ?? 9) - (rank[b.kind] ?? 9));
  for (const p of sorted) for (const n of [p.name, ...(Array.isArray(p.aliases) ? p.aliases : [])]) {
    const k = orgKey(n);
    if (k && k.length > 2 && !idx.has(k)) idx.set(k, p.entity_id);
  }
  return idx;
}

const hash = (...parts) => crypto.createHash('sha1').update(parts.map(p => String(p ?? '')).join('|')).digest('hex');
const day = v => (v instanceof Date ? v.toISOString().slice(0, 10) : v ? String(v).slice(0, 10) : null);
const num = v => (v === null || v === undefined ? null : Number(v));

// Pure: one check register's rows -> public checkbook rows.
function checkbookRows(disb, {upload, workspace, index = new Map()}) {
  const gov = workspace.government_key, fy = workspace.fy_start_month || 10;
  const voided = new Set(disb.filter(d => d.is_void || num(d.amount) < 0).map(d => d.doc_no).filter(Boolean));
  const invoiced = new Map();
  for (const d of disb) if (d.invoice_no && d.payee) invoiced.set(d.payee, (invoiced.get(d.payee) || 0) + 1);
  const out = [];
  for (const d of disb) {
    const amount = num(d.amount), paid = day(d.paid_on);
    if (d.is_void || !(amount > 0) || !paid || (d.doc_no && voided.has(d.doc_no))) continue;
    const entity = index.get(orgKey(d.payee)) || null;
    const org = isOrganization(d.payee, entity, (invoiced.get(d.payee) || 0) >= 3);
    out.push({government: GOV_NAME[gov] || workspace.name, fiscal_year: fiscalYear(paid, fy), paid_on: paid,
      payee: org ? d.payee : 'Individual (name withheld)', payee_kind: org ? 'organization' : 'individual', payee_entity_id: org ? entity : null,
      amount, method: d.method || null, doc_no: d.doc_no || null, invoice_no: org ? d.invoice_no || null : null, fund: d.fund || null,
      account: d.account || null, description: org ? d.description || null : individualCategory(d), source_file: upload.original_name,
      upload_id: upload.id, source_url: null, gov_id: gov, record_hash: hash(upload.id, d.id, paid, amount, d.doc_no, d.payee)});
  }
  return out;
}

// Pure: one budget-vs-actual report's lines -> public budget_actuals rows.
function budgetRows(lines, {upload, workspace}) {
  const gov = workspace.government_key;
  return lines.map(l => ({government: GOV_NAME[gov] || workspace.name, fiscal_year: l.fiscal_year, as_of: day(l.as_of), line_type: isRevenue(l) ? 'revenue' : 'expense',
    fund: l.fund || null, department: l.department || null, account: l.account || null, description: l.description || null,
    original_budget: num(l.original_budget), amended_budget: num(l.amended_budget), actual_ytd: num(l.actual_ytd), encumbered: num(l.encumbered),
    source_file: upload.original_name, upload_id: upload.id, source_url: null, gov_id: gov,
    record_hash: hash(upload.id, l.id, l.fiscal_year, day(l.as_of), l.account, l.description, l.actual_ytd)}));
}

const COLS = {
  checkbook_payments: ['government', 'fiscal_year', 'paid_on', 'payee', 'payee_kind', 'payee_entity_id', 'amount', 'method', 'doc_no', 'invoice_no', 'fund', 'account',
    'description', 'source_file', 'upload_id', 'source_url', 'gov_id'],
  budget_actuals: ['government', 'fiscal_year', 'as_of', 'line_type', 'fund', 'department', 'account', 'description', 'original_budget', 'amended_budget', 'actual_ytd',
    'encumbered', 'source_file', 'upload_id', 'source_url', 'gov_id'],
};
const TABLE = {disbursements: 'checkbook_payments', budget: 'budget_actuals'};

async function insertPublic(q, table, rows) {
  const cols = COLS[table];
  for (let i = 0; i < rows.length; i += 300) {
    const chunk = rows.slice(i, i + 300), params = [], tuples = [];
    for (const r of chunk) {
      const ph = [...cols.map(c => r[c] ?? null), r.record_hash].map(v => { params.push(v); return '$' + params.length; });
      const govParam = ph[cols.indexOf('gov_id')];
      tuples.push(`(${ph.join(', ')}, now(), (select key from governments where key = ${govParam}), 'finance')`);
    }
    await q(`insert into ${table} (${cols.join(', ')}, record_hash, published_at, government_key, origin) values ${tuples.join(', ')}
             on conflict (origin, record_hash) do nothing`, params);
  }
}

// The upload as it can be published, or a thrown reason it can't.
async function publishable(q, ws, uploadId) {
  if (/-sample$/.test(ws)) throw bad('The sample workspace holds made-up figures, so it can’t be published.');
  const [u] = await q(`select id, workspace_id, shape, original_name, status, tie_status, period_start::text period_start, period_end::text period_end, published_at
                       from finance.uploads where id = $1 and workspace_id = $2`, [uploadId, ws]);
  if (!u) throw bad('Upload not found.', 404);
  if (!PUBLISHABLE.includes(u.shape)) throw bad('Only check registers and budget-vs-actual reports are published. Bank statements and reconciliations stay private.');
  if (u.status !== 'committed') throw bad('Add the file first (it has to be checked and added before it can be published).');
  if (u.tie_status === 'mismatch') throw bad('This file doesn’t tie to its printed total, so it can’t be published.');
  return u;
}

// Publishes (or re-publishes) one upload. Refuses a file that would double-count rows already published.
async function publish(q, ws, uploadId, who) {
  const u = await publishable(q, ws, uploadId);
  const [w] = await q('select id, government_key, name, fy_start_month from finance.workspaces where id = $1', [ws]);
  const table = TABLE[u.shape];
  let rows;
  if (u.shape === 'disbursements') {
    const [o] = await q(`select id, original_name from finance.uploads where workspace_id = $1 and id <> $2 and shape = 'disbursements' and status = 'committed'
        and published_at is not null and period_start <= $4::date and period_end >= $3::date limit 1`, [ws, u.id, u.period_start, u.period_end]);
    if (o) throw bad(`These payments overlap ${o.original_name}, which is already published. Unpublish it first, so no payment is counted twice.`, 409);
    const disb = await q(`select id, paid_on::text paid_on, doc_no, method, payee, amount, invoice_no, fund, account, description, is_void
        from finance.disbursements where upload_id = $1 and workspace_id = $2 order by paid_on, id`, [u.id, ws]);
    const profiles = await q(`select entity_id, kind, name, aliases from entity_profiles where kind in ('vendor', 'gov', 'nonprofit', 'business')`).catch(() => []);
    rows = checkbookRows(disb, {upload: u, workspace: w, index: entityIndex(profiles)});
  } else {
    const lines = await q(`select id, fiscal_year, as_of::text as_of, fund, department, account, description, original_budget, amended_budget, actual_ytd, encumbered
        from finance.budget_lines where upload_id = $1 and workspace_id = $2 order by id`, [u.id, ws]);
    const asOf = lines[0] && lines[0].as_of, fy = lines[0] && lines[0].fiscal_year;
    const [o] = asOf ? await q(`select distinct u.original_name from budget_actuals b join finance.uploads u on u.id = b.upload_id
        where b.gov_id = $1 and b.fiscal_year = $2 and b.as_of = $3::date and b.upload_id <> $4 limit 1`, [w.government_key, fy, asOf, u.id]) : [];
    if (o) throw bad(`A report for FY${fy} as of ${asOf} (${o.original_name}) is already published. Unpublish it first.`, 409);
    rows = budgetRows(lines, {upload: u, workspace: w});
  }
  await q(`delete from ${table} where upload_id = $1`, [u.id]);
  await insertPublic(q, table, rows);
  await q(`update finance.uploads set published_at = now(), published_by = $3 where id = $1 and workspace_id = $2`, [u.id, ws, who]);
  const withheld = rows.filter(r => r.payee_kind === 'individual').length;
  return {ok: true, table, rows: rows.length, ...(u.shape === 'disbursements' ? {individuals_withheld: withheld, linked: rows.filter(r => r.payee_entity_id).length} : {}),
    page: u.shape === 'disbursements' ? `/public-money/checkbook?gov=${w.government_key}` : `/public-money/budget-tracker?gov=${w.government_key}`};
}

async function unpublish(q, ws, uploadId) {
  const [u] = await q('select id, shape from finance.uploads where id = $1 and workspace_id = $2', [uploadId, ws]);
  if (!u) throw bad('Upload not found.', 404);
  const table = TABLE[u.shape];
  let n = 0;
  if (table) n = (await q(`delete from ${table} where upload_id = $1 returning id`, [u.id])).length;
  await q('update finance.uploads set published_at = null, published_by = null where id = $1 and workspace_id = $2', [u.id, ws]);
  return {ok: true, removed: n};
}

module.exports = {publish, unpublish, checkbookRows, budgetRows, isOrganization, entityIndex, orgKey, individualCategory, PUBLISHABLE};
