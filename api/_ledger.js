// Accounting-system files (city and county ERP exports) for the Ingestion tab on /admin.
// Files arrive by email at <city>@ingest.baycounty.me (Supabase edge function ingest-email) and land in ingest.raw.
// "Normalize" maps a file's rows into ingest.staging (edge function ingest-normalize); an admin then approves or
// rejects rows here, and only approved rows reach public.ledger_transactions. Files starting with _ are not routes.
const db = require('./_db');

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const bad = (msg, status = 400) => Object.assign(new Error(msg), {status});

// Pure: "a@x.gov, @springfield.fl.gov" -> ['a@x.gov', '@springfield.fl.gov']. Throws on anything else.
function cleanSenders(v) {
  const list = (Array.isArray(v) ? v : String(v ?? '').split(/[\s,;]+/)).map(s => String(s).trim().toLowerCase()).filter(Boolean);
  for (const s of list) {
    if (!/^([a-z0-9._%+'-]+)?@[a-z0-9.-]+\.[a-z]{2,}$/.test(s)) throw bad(`“${s}” isn’t an email address or @domain.`);
  }
  if (list.length > 50) throw bad('Up to 50 allowed senders per source.');
  return [...new Set(list)];
}

// Pure: a list of row ids from the request body, validated.
function cleanIds(v) {
  const ids = (Array.isArray(v) ? v : []).map(String);
  if (ids.some(id => !UUID.test(id))) throw bad('Unknown row id.');
  if (ids.length > 2000) throw bad('Up to 2,000 rows at a time.');
  return [...new Set(ids)];
}

const REVIEW = ['pending', 'approved', 'rejected', 'all'];

async function report({status = 'pending', source = '', raw = ''} = {}) {
  if (!REVIEW.includes(status)) status = 'pending';
  if (source && !UUID.test(source)) source = '';
  if (raw && !UUID.test(raw)) raw = '';
  const sources = await db.q(`select s.id, s.entity_name, s.entity_type, s.erp_system, s.intake_method, s.inbound_address, s.allowed_senders,
      s.auto_normalize, s.active, s.column_map is not null as has_map, s.finance_workspace_id, w.name finance_workspace,
      (select count(*) from ingest.raw r where r.source_id = s.id)::int files,
      (select max(received_at) from ingest.raw r where r.source_id = s.id) last_file,
      (select count(*) from ingest.staging t where t.source_id = s.id and t.review_status = 'pending')::int pending
    from ingest.sources s left join finance.workspaces w on w.id = s.finance_workspace_id order by s.entity_name`);
  const files = await db.q(`select r.id, r.source_id, s.entity_name, r.received_at, r.intake_method, r.sender, r.file_name, r.status,
      r.row_count, r.error_message, r.storage_path is not null as has_file, s.finance_workspace_id,
      r.finance_status, r.finance_shape, r.finance_error, r.finance_upload_id, fu.status finance_upload_status,
      (select count(*) from ingest.staging t where t.raw_id = r.id and t.review_status = 'pending')::int pending,
      (select count(*) from ingest.staging t where t.raw_id = r.id and t.review_status = 'approved')::int approved,
      (select count(*) from ingest.staging t where t.raw_id = r.id and t.review_status = 'rejected')::int rejected
    from ingest.raw r join ingest.sources s on s.id = r.source_id left join finance.uploads fu on fu.id = r.finance_upload_id
    where r.received_at > now() - interval '120 days' ${source ? 'and r.source_id = $1' : ''}
    order by r.received_at desc limit 100`, source ? [source] : []);
  const p = []; const w = [];
  if (status !== 'all') { p.push(status); w.push(`t.review_status = $${p.length}`); }
  if (source) { p.push(source); w.push(`t.source_id = $${p.length}`); }
  if (raw) { p.push(raw); w.push(`t.raw_id = $${p.length}`); }
  const rows = await db.q(`select t.id, t.raw_id, s.entity_name, to_char(t.txn_date, 'YYYY-MM-DD') txn_date, t.fiscal_year, t.fund_code,
      t.account_code, t.vendor_name, t.amount, t.description, t.check_number, t.review_status, t.reviewed_by_email, t.reviewed_at, t.review_note
    from ingest.staging t join ingest.sources s on s.id = t.source_id
    ${w.length ? 'where ' + w.join(' and ') : ''} order by t.txn_date desc nulls last, t.created_at desc limit 500`, p);
  const [tot] = await db.q(`select count(*) filter (where review_status = 'pending')::int pending,
      count(*) filter (where review_status = 'approved')::int approved, count(*) filter (where review_status = 'rejected')::int rejected,
      coalesce(sum(amount) filter (where review_status = 'pending'), 0)::float pending_amount
    from ingest.staging`);
  const [fx] = await db.q(`select count(*) filter (where status = 'received' and storage_path is not null)::int waiting,
      count(*) filter (where status = 'failed' and received_at > now() - interval '14 days')::int failed_14d from ingest.raw`);
  return {sources, files, rows, totals: {...tot, ...fx}, filter: {status, source, raw}};
}

// Calls the ingest-normalize edge function with the service-role key (server side only).
async function normalize({raw_id, all} = {}, fetchImpl = fetch) {
  const base = String(process.env.SUPABASE_URL || '').replace(/\/$/, ''), key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!base || !key) throw bad('Normalizing needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in Vercel.', 500);
  let payload;
  if (all) payload = {all: true};
  else if (raw_id && UUID.test(String(raw_id))) payload = {raw_id: String(raw_id)};
  else throw bad('Pick a file to normalize.');
  const r = await fetchImpl(`${base}/functions/v1/ingest-normalize`, {method: 'POST',
    headers: {'Content-Type': 'application/json', Authorization: `Bearer ${key}`, apikey: key}, body: JSON.stringify(payload)});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw bad(`Normalize failed: ${j.error || j.msg || r.status}`, 502);
  return j;
}

async function review(decision, body = {}, email) {
  if (!['approved', 'rejected'].includes(decision)) throw bad('Unknown decision.');
  let ids = cleanIds(body.ids);
  if (!ids.length && body.raw_id) {
    if (!UUID.test(String(body.raw_id))) throw bad('Unknown file.');
    ids = (await db.q(`select id from ingest.staging where raw_id = $1 and review_status = 'pending'`, [String(body.raw_id)])).map(r => r.id);
  }
  if (!ids.length) throw bad('No rows selected.');
  const note = body.note == null ? null : String(body.note).trim().slice(0, 500) || null;
  if (decision === 'rejected' && !note) throw bad('Add a short reason when rejecting rows.');
  const [r] = await db.q('select ingest.review_staging($1::uuid[], $2, $3, $4) n', [ids, decision, email, note]);
  return {decision, requested: ids.length, changed: r ? r.n : 0};
}

async function updateSource(body = {}) {
  const id = String(body.id || '');
  if (!UUID.test(id)) throw bad('Unknown source.');
  const sets = [], p = [id];
  if ('auto_normalize' in body) { p.push(!!body.auto_normalize); sets.push(`auto_normalize = $${p.length}`); }
  if ('active' in body) { p.push(!!body.active); sets.push(`active = $${p.length}`); }
  if ('allowed_senders' in body) { p.push(cleanSenders(body.allowed_senders)); sets.push(`allowed_senders = $${p.length}::text[]`); }
  if (!sets.length) throw bad('Nothing to change.');
  const rows = await db.q(`update ingest.sources set ${sets.join(', ')} where id = $1 returning id, entity_name, auto_normalize, active, allowed_senders`, p);
  if (!rows.length) throw bad('Unknown source.', 404);
  return rows[0];
}

// Send (or re-send) one file to its source's /finance workspace as an unreviewed import.
async function toFinance(body = {}) {
  if (!UUID.test(String(body.raw_id || ''))) throw bad('Pick a file.');
  const r = await require('./_finance/intake').fromRaw(String(body.raw_id), {retry: true});
  if (r.error) throw bad(`Couldn’t send it to /finance: ${r.error}`, 502);
  if (r.skipped) throw bad(r.reason ? `Not sent: ${r.reason}.` : 'Already sent to /finance, or no stored file.', 409);
  return r;
}

module.exports = {report, normalize, review, updateSource, toFinance, cleanSenders, cleanIds};
