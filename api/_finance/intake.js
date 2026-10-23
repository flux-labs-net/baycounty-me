// Emailed accounting files -> /finance. A file accepted by the ingest-email edge function (ingest.raw) whose source
// names a finance workspace (ingest.sources.finance_workspace_id) is copied into that workspace's storage and run
// through the same importer as a staff upload, saved as an unreviewed import (status 'preview', uploaded_by
// 'email: <sender>'). Staff open it under "Emailed in" on /finance, check it, and add it. Nothing is committed here.
//
// Triggered three ways: ingest-email right after a file arrives (POST /api/finance?action=intake), the daily
// alerts run (sweep), and the Retry button in /admin. Each file is claimed before work starts, so repeats are harmless.
const db = require('../_db');
const store = require('./store');
const financeStorage = require('./storage');
const {sha256, safeName} = require('./pipeline');

const ERP = {new_world: 'Tyler New World', bsa: 'BS&A', springbrook: 'Springbrook'};
const NOT_PUBLIC = ['budget', 'bank_transactions', 'bank_recs']; // never sent to the public-ledger normalizer
const base = () => String(process.env.SUPABASE_URL || '').replace(/\/$/, '');
const key = () => process.env.SUPABASE_SERVICE_ROLE_KEY;

// The original file from the private ingest-raw bucket.
async function rawFile(path, fetchImpl = fetch) {
  if (!base() || !key()) throw new Error('SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY aren’t set.');
  const r = await fetchImpl(`${base()}/storage/v1/object/ingest-raw/${path.split('/').map(encodeURIComponent).join('/')}`,
    {headers: {Authorization: `Bearer ${key()}`, apikey: key()}});
  if (!r.ok) throw new Error(`The stored file couldn’t be read (${r.status}).`);
  return Buffer.from(await r.arrayBuffer());
}

// True only for a key that can run a service-role-only RPC on this project (legacy JWT or sb_secret_ key).
async function isServiceKey(presented, fetchImpl = fetch) {
  if (!presented || !base()) return false;
  try {
    const r = await fetchImpl(`${base()}/rest/v1/rpc/ingest_pending_raw`, {method: 'POST',
      headers: {apikey: presented, Authorization: `Bearer ${presented}`, 'Content-Type': 'application/json'}, body: JSON.stringify({p_limit: 1})});
    return r.ok;
  } catch (e) { return false; }
}

// deps: {q, storage (finance bucket: put/get/configured), readRaw(path) -> Buffer, ingest(deps, ws, body, who)}
async function fromRaw(rawId, {retry = false} = {}, deps = {}) {
  const q = deps.q || db.q;
  const readRaw = deps.readRaw || rawFile;
  const fstore = deps.storage || financeStorage;
  const ingest = deps.ingest || require('../finance').ingest;
  // Claim: new files, a stuck claim (10+ minutes), or a failed one when retrying.
  const [c] = await q(`update ingest.raw r set finance_status = 'importing', finance_error = null, finance_at = now()
      from ingest.sources s where r.id = $1 and s.id = r.source_id and r.storage_path is not null and r.finance_upload_id is null
        and (r.finance_status is null or (r.finance_status = 'importing' and r.finance_at < now() - interval '10 minutes')
             or ($2 and r.finance_status in ('failed', 'not_linked')))
      returning r.id, r.storage_path, r.file_name, r.sender, r.status, s.finance_workspace_id ws, s.erp_system, s.entity_name`, [rawId, retry]);
  if (!c) return {raw_id: rawId, skipped: true};
  if (!c.ws) {
    await q(`update ingest.raw set finance_status = 'not_linked' where id = $1`, [rawId]);
    return {raw_id: rawId, skipped: true, reason: 'source has no finance workspace'};
  }
  try {
    const buffer = await readRaw(c.storage_path);
    const filename = safeName(c.file_name);
    const path = `${c.ws}/${sha256(buffer).slice(0, 16)}/${filename}`;
    await fstore.put(path, buffer);
    const who = {email: `email: ${c.sender || 'unknown sender'}`};
    const r = await ingest({q, storage: fstore}, c.ws, {path, filename, commit: false, source_system: ERP[c.erp_system] || null}, who);
    const notPublic = NOT_PUBLIC.includes(r.shape);
    await q(`update ingest.raw set finance_upload_id = $2, finance_status = 'imported', finance_shape = $3, finance_at = now(),
        status = case when $4 and status in ('received', 'failed') then 'finance_only' else status end where id = $1`,
      [rawId, r.upload_id, r.shape || null, notPublic]);
    await store.log(q, c.ws, who.email, 'upload_emailed', {upload_id: r.upload_id, raw_id: rawId, shape: r.shape, rows: r.row_count, ready: r.ok});
    return {raw_id: rawId, workspace: c.ws, upload_id: r.upload_id, shape: r.shape, ok: r.ok, rows: r.row_count, finance_only: notPublic};
  } catch (e) {
    await q(`update ingest.raw set finance_status = 'failed', finance_error = $2 where id = $1`, [rawId, String(e.message || e).slice(0, 500)]);
    return {raw_id: rawId, error: e.message || String(e)};
  }
}

// Files from linked sources that were never sent (or whose claim died). Run daily.
async function sweep(limit = 20, deps = {}) {
  const q = deps.q || db.q;
  const ids = await q(`select r.id from ingest.raw r join ingest.sources s on s.id = r.source_id
      where s.finance_workspace_id is not null and r.storage_path is not null and r.finance_upload_id is null
        and (r.finance_status is null or (r.finance_status = 'importing' and r.finance_at < now() - interval '10 minutes'))
        and r.received_at > now() - interval '30 days' order by r.received_at limit $1`, [limit]);
  const out = [];
  for (const {id} of ids) out.push(await fromRaw(id, {}, deps));
  return out;
}

module.exports = {fromRaw, sweep, isServiceKey, rawFile, NOT_PUBLIC};
