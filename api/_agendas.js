// Agenda watcher data for the /admin "Agendas" tab (tables from db/migrations/0012_agenda_inbox.sql, written by
// data/agendas/watch_agendas.py). Admin-only; files starting with _ are not routes.
const db = require('./_db');

const BUCKET = 'agendas';
const missing = e => e && (e.code === '42P01' || e.code === '3F000'); // table / schema not created yet

// Pure: headline numbers and problems from the query results. Kept separate so it can be tested without a database.
function summarize({runs = [], counts = {}, openErrors = 0, now = new Date(), inboxConfigured = true}) {
  const hrs = t => (now - new Date(t)) / 3600e3;
  const last = runs[0] || null;
  const lastInbox = runs.find(r => /inbox/.test(r.notes || '')) || null;
  const problems = [];
  if (!last) problems.push({level: 'warn', text: 'The agenda watcher has never run. Add the secrets and run the "Watch agendas" workflow.'});
  else {
    if (last.status === 'failed') problems.push({level: 'error', text: `The last run failed: ${last.notes || 'no details'}`});
    if (hrs(last.finished_at || last.started_at) > 26) problems.push({level: 'error', text: `No agenda run in ${Math.round(hrs(last.finished_at || last.started_at))} hours (the workflow may be off).`});
  }
  if (inboxConfigured && last && !lastInbox) problems.push({level: 'warn', text: 'No inbox check on record yet (sweeps only). Check RESEND_FULL_KEY (or the POP_* secrets) in GitHub.'});
  if (openErrors) problems.push({level: 'warn', text: `${openErrors} unresolved ingestion error${openErrors === 1 ? '' : 's'} in the last 7 days.`});
  if (counts.unmatched) problems.push({level: 'warn', text: `${counts.unmatched} email${counts.unmatched === 1 ? '' : 's'} in the last 7 days didn’t match any government. Check the sender below.`});
  return {last_run: last, last_inbox: lastInbox, problems};
}

async function safe(sql, params) { try { return await db.q(sql, params); } catch (e) { if (missing(e)) return null; throw e; } }

async function report({days = 14, board = '', status = ''} = {}) {
  const runs = await safe(`select id, status, started_at, finished_at, rows_in, notes from ingest_runs
      where origin = 'scraper:agendas' order by id desc limit 40`);
  if (runs === null) return {installed: false, problems: [{level: 'warn', text: 'The agendas tables don’t exist yet. The next database sync applies migration 0012.'}]};
  const [c] = await db.q(`select
      (select count(*) from agendas.notices where pulled_at > now() - interval '7 days')::int notices_7d,
      (select count(*) from agendas.notices where pulled_at > now() - interval '7 days' and status = 'unmatched')::int unmatched,
      (select count(*) from agendas.documents where first_seen_at > now() - interval '7 days')::int new_7d,
      (select count(*) from agendas.versions v join agendas.documents d on d.id = v.document_id
         where v.fetched_at > now() - interval '7 days' and v.fetched_at > d.first_seen_at + interval '1 minute')::int updated_7d,
      (select count(*) from agendas.documents)::int documents,
      (select count(*) from agendas.documents where status = 'failed')::int failing,
      (select count(*) from agendas.errors where resolved_at is null and at > now() - interval '7 days')::int open_errors`);
  const params = [Math.min(Math.max(days, 1), 120)];
  let where = `coalesce(d.last_changed_at, d.first_seen_at) > now() - make_interval(days => $1)`;
  if (board) { params.push(board); where += ` and (d.board = $${params.length} or d.source_key = $${params.length})`; }
  if (status) { params.push(status); where += ` and d.status = $${params.length}`; }
  const documents = await db.q(`select d.id, d.url, d.source_key, d.board, d.kind, d.title, d.meeting_date, d.first_seen_at, d.last_checked_at,
      d.last_changed_at, d.version_count, d.status, d.error, d.bytes, d.content_type, d.notice_id,
      coalesce((select json_agg(json_build_object('id', v.id, 'sha256', v.sha256, 'bytes', v.bytes, 'fetched_at', v.fetched_at, 'stored', v.storage_path is not null)
        order by v.fetched_at desc) from agendas.versions v where v.document_id = d.id), '[]') versions
      from agendas.documents d where ${where} order by coalesce(d.last_changed_at, d.first_seen_at) desc limit 300`, params);
  const notices = await db.q(`select id, received_at, pulled_at, from_addr, subject, left(body_text, 4000) body_text, links, attachments, sources, status, error
      from agendas.notices order by id desc limit 60`);
  const errors = await db.q(`select id, at, stage, source_key, url, message, notice_id, document_id, resolved_at
      from agendas.errors where at > now() - interval '14 days' order by (resolved_at is null) desc, id desc limit 150`);
  const boards = await db.q(`select coalesce(board, source_key) board, count(*)::int n, max(coalesce(last_changed_at, first_seen_at)) latest
      from agendas.documents group by 1 order by 1`);
  const s = summarize({runs, counts: c, openErrors: c.open_errors, inboxConfigured: true});
  return {installed: true, checked_at: new Date().toISOString(), counts: c, runs, documents, notices, errors, boards, ...s};
}

// A short-lived link to a stored version (Supabase Storage), or the public source URL when it wasn't stored.
async function fileLink(versionId) {
  const [v] = await db.q(`select v.storage_path, d.url from agendas.versions v join agendas.documents d on d.id = v.document_id where v.id = $1`, [versionId]);
  if (!v) throw Object.assign(new Error('No such file version.'), {status: 404});
  const base = String(process.env.SUPABASE_URL || '').replace(/\/$/, ''), key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!v.storage_path || !base || !key) return {url: /^https?:/.test(v.url) ? v.url : null, stored: false};
  const r = await fetch(`${base}/storage/v1/object/sign/${BUCKET}/${v.storage_path.split('/').map(encodeURIComponent).join('/')}`, {
    method: 'POST', headers: {Authorization: `Bearer ${key}`, apikey: key, 'Content-Type': 'application/json'}, body: JSON.stringify({expiresIn: 300})});
  const j = await r.json().catch(() => ({}));
  if (!r.ok || !(j.signedURL || j.signedUrl)) throw Object.assign(new Error('Storage didn’t return a link: ' + (j.message || r.status)), {status: 502});
  return {url: `${base}/storage/v1${j.signedURL || j.signedUrl}`, stored: true};
}

async function resolveError(id, all) {
  if (all) return {resolved: (await db.q(`update agendas.errors set resolved_at = now() where resolved_at is null returning id`)).length};
  return {resolved: (await db.q(`update agendas.errors set resolved_at = now() where id = $1 and resolved_at is null returning id`, [id])).length};
}

// Ask GitHub to run the watcher now (needs GITHUB_DISPATCH_TOKEN in Vercel: a fine-grained token with Actions: write on the repo).
async function runNow(mode = 'both', only = '', emailId = '') {
  const tok = process.env.GITHUB_DISPATCH_TOKEN;
  if (!tok) throw Object.assign(new Error('Set GITHUB_DISPATCH_TOKEN in Vercel to run the watcher from here, or use the Workflow runs link.'), {status: 409});
  const r = await fetch('https://api.github.com/repos/jeremymcs/baycounty-me/actions/workflows/watch-agendas.yml/dispatches', {
    method: 'POST', headers: {Authorization: `Bearer ${tok}`, Accept: 'application/vnd.github+json', 'User-Agent': 'baycounty-me-admin'},
    body: JSON.stringify({ref: 'main', inputs: {mode: ['inbox', 'sweep', 'both'].includes(mode) ? mode : 'both', only: String(only).replace(/[^a-z,-]/g, ''),
      email_id: String(emailId || '').replace(/[^A-Za-z0-9-]/g, '').slice(0, 64)}})});
  if (r.status !== 204) throw Object.assign(new Error(`GitHub said ${r.status}: ${(await r.text()).slice(0, 200)}`), {status: 502});
  return {started: true};
}

module.exports = {summarize, report, fileLink, resolveError, runNow};
