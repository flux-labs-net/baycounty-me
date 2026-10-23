// /api/finance: the budget anomaly dashboard's backend (Phase 1). Private: every call needs a signed-in member of the
// workspace (see api/_finance/auth.js). Actions, all JSON:
//   POST ?action=login   {email}                    emails a 6-digit code to a workspace member
//   POST ?action=verify  {email, code, client}      starts a session: a cookie for the web, {token} for client "app"
//   POST ?action=logout                             ends this session
//   GET  ?action=workspaces                         workspaces you can see, with your role
//   GET  ?action=overview&workspace=lh              budget by department, payments by month, bank accounts, open flags
//   GET  ?action=uploads&workspace=lh               uploaded files, newest first
//   POST ?action=upload-url  {workspace, filename}  a one-time URL to PUT a large file into storage
//   POST ?action=ingest      {workspace, ...}       preview or commit a file (see ingest below)
//   POST ?action=replace     {workspace, upload_id} withdraw a committed file and its rows
//   GET  ?action=file&workspace=lh&upload_id=1      a 5-minute download link for the original file
//   GET  ?action=flags&workspace=lh[&status=open&rule=&severity=&limit=&offset=]
//   GET  ?action=flag&workspace=lh&id=1             one flag, the rows behind it, review notes
//   POST ?action=flag-status {workspace, id, status, note}   open | explained | follow_up | referred
//   POST ?action=run-rules   {workspace}
//   GET  ?action=members&workspace=lh  /  POST ?action=members {workspace, email, role}   (owners)
const db = require('./_db');
const storage = require('./_finance/storage');
const store = require('./_finance/store');
const {caller, requireRole, startLogin, finishLogin, logout, ROLES} = require('./_finance/auth');
const {FROM, resend} = require('./_alerts');
const {prepare, sha256, safeName} = require('./_finance/pipeline');

const MAX_INLINE = 3 * 1024 * 1024; // base64 uploads through the function (Vercel caps bodies at 4.5 MB); bigger files go to storage first
const bad = (msg, status = 400) => Object.assign(new Error(msg), {status});
const body = req => {
  if (req.method === 'GET') return {};
  try { return typeof req.body === 'string' ? JSON.parse(req.body || '{}') : req.body || {}; }
  catch (e) { throw bad('The request body isn’t valid JSON.'); }
};

// ingest body: {workspace, filename, content (base64) | path (from upload-url), commit, upload_id?,
//   shape?, mapping? {field: "Column name"}, printed_total?, as_of?, fiscal_year?, account?, source_system?}
// Preview (commit false) returns the detected shape, the column mapping, the first 15 parsed rows and the tie-out.
// Commit stores the rows and re-runs the rules; a file that doesn't tie is held (no rows used) and flagged.
async function ingest(deps, ws, b, who) {
  const {q} = deps;
  const w = await store.workspace(q, ws);
  let buffer, path = b.path ? String(b.path) : null, filename = safeName(b.filename || (path && path.split('/').pop()));
  if (b.upload_id && !b.content && !path) {
    const u = await store.getUpload(q, ws, Number(b.upload_id));
    path = u.storage_path; filename = u.original_name;
  }
  if (b.content) {
    buffer = Buffer.from(String(b.content), 'base64');
    if (buffer.length > MAX_INLINE) throw bad('That file is too big to send directly. Use action=upload-url, then ingest with its path.', 413);
  } else if (path) {
    if (!path.startsWith(ws + '/') || path.includes('..')) throw bad('That file path isn’t in this workspace.');
    buffer = await deps.storage.get(path);
  } else throw bad('Send the file as base64 "content" with a "filename", or the "path" from upload-url.');
  if (!buffer.length) throw bad('The file is empty.');

  const hash = sha256(buffer);
  if (b.content && !path) {
    path = `${ws}/${hash.slice(0, 16)}/${filename}`;
    if (deps.storage.configured()) await deps.storage.put(path, buffer); else path = null;
  }
  const dup = await store.committedDuplicate(q, ws, hash);
  if (dup && b.commit) throw bad(`This exact file was already added on ${new Date(dup.uploaded_at).toISOString().slice(0, 10)} (${dup.original_name}).`, 409);

  // Saved mapping for this header layout, unless the caller is choosing columns now.
  let saved = null;
  const first = await prepare(buffer, filename, {shape: b.shape, mapping: b.mapping, printedTotal: b.printed_total, asOf: b.as_of,
    fiscalYear: b.fiscal_year, account: b.account, fyStartMonth: w.fy_start_month});
  let p = first;
  if (!b.mapping && first.signature) {
    saved = await store.savedMapping(q, ws, first.signature);
    if (saved && (!b.shape || b.shape === saved.shape)) {
      p = await prepare(buffer, filename, {shape: b.shape, printedTotal: b.printed_total, asOf: b.as_of, fiscalYear: b.fiscal_year,
        account: b.account, fyStartMonth: w.fy_start_month, saved});
    }
  }

  const fields = {shape: p.shape, source_system: b.source_system ? String(b.source_system).slice(0, 80) : null, original_name: filename,
    storage_path: path, sha256: hash, bytes: buffer.length, uploaded_by: who.email, period_start: p.periodStart || null, period_end: p.periodEnd || null,
    row_count: p.records.length, parsed_total: p.parsedTotal ?? null, printed_total: p.printedTotal ?? null, tie_status: p.tie ? p.tie.status : null,
    tie_difference: p.tie ? p.tie.difference : null, mapping: p.mapping, warnings: p.warnings || [], error: p.ok ? null : `Missing: ${p.missing.join('; ')}`};
  const preview = {shape: p.shape, label: p.label, sheet: p.sheet, header_row: p.headerRow, headers: p.headers, mapping: p.mapping,
    fields_available: p.available, used_saved_mapping: p.usedSavedMapping, ok: p.ok, missing: p.missing, row_count: p.records.length,
    parsed_total: p.parsedTotal ?? null, printed_total: p.printedTotal ?? null, tie: p.tie || null, warnings: p.warnings || [],
    period: {start: p.periodStart || null, end: p.periodEnd || null}, fiscal_year: p.fiscalYear || null, sample: p.records.slice(0, 15),
    already_added: dup ? {upload_id: dup.id, on: dup.uploaded_at} : null};

  if (!b.commit || !p.ok) {
    const id = await store.saveUpload(q, ws, {...fields, status: 'preview'}, b.upload_id ? Number(b.upload_id) : null);
    return {upload_id: id, committed: false, ...preview};
  }
  if (p.tie && p.tie.status === 'mismatch') {
    const id = await store.saveUpload(q, ws, {...fields, status: 'held'}, b.upload_id ? Number(b.upload_id) : null);
    await store.log(q, ws, who.email, 'upload_held', {upload_id: id, difference: p.tie.difference});
    const r = await store.refreshFlags(q, ws);
    return {upload_id: id, committed: false, held: true, message: `Held: the rows add up to ${p.parsedTotal}, but the file's total is ${p.printedTotal}. Nothing from this file is used until it ties.`, rules: r, ...preview};
  }
  const id = await store.saveUpload(q, ws, {...fields, status: 'preview'}, b.upload_id ? Number(b.upload_id) : null);
  await store.insertRows(q, ws, id, p.shape, p.records);
  await store.saveUpload(q, ws, {status: 'committed'}, id);
  if (p.signature) await store.saveMapping(q, ws, p.shape, p.signature, p.mapping, p.headers, fields.source_system);
  await store.log(q, ws, who.email, 'upload_committed', {upload_id: id, shape: p.shape, rows: p.records.length});
  const r = await store.refreshFlags(q, ws);
  return {upload_id: id, committed: true, rules: r, ...preview};
}

async function route(deps, req, res, action) {
  const {q} = deps, Q = req.query || {}, b = body(req);
  if (action === 'login' || action === 'verify') {
    if (req.method !== 'POST') throw bad('Use POST.', 405);
    return action === 'login' ? startLogin(q, req, b, deps.sendEmail) : finishLogin(q, req, res, b);
  }
  const who = await deps.caller(req, q);
  if (action === 'logout') {
    if (req.method !== 'POST') throw bad('Use POST.', 405);
    return logout(q, req, res, who && !who.csrf ? who : null);
  }
  if (action === 'workspaces') {
    if (!who) throw bad('Sign in first.', 401);
    return {email: who.email, via: who.via, workspaces: await store.workspacesFor(q, who)};
  }
  const ws = String(b.workspace || Q.workspace || '');
  const need = {overview: 'read', uploads: 'read', file: 'read', flags: 'read', flag: 'read', 'upload-url': 'upload', ingest: 'upload',
    replace: 'upload', 'flag-status': 'review', 'run-rules': 'upload', members: req.method === 'GET' ? 'read' : 'manage'}[action];
  if (!need) throw bad('Unknown action.', 404);
  const post = ['upload-url', 'ingest', 'replace', 'flag-status', 'run-rules'].includes(action) || (action === 'members' && req.method !== 'GET');
  if (post && req.method !== 'POST') throw bad('Use POST.', 405);
  const role = await requireRole(q, who, ws, need);

  switch (action) {
    case 'overview': return {role, ...(await store.overview(q, ws))};
    case 'uploads': return {uploads: await q(`select id, original_name, shape, source_system, uploaded_by, uploaded_at, period_start::text period_start, period_end::text period_end,
        row_count, parsed_total::float8 parsed_total, printed_total::float8 printed_total, tie_status, tie_difference::float8 tie_difference, status, warnings, error
        from finance.uploads where workspace_id = $1 order by uploaded_at desc limit 200`, [ws])};
    case 'upload-url': {
      if (!deps.storage.configured()) throw bad('File storage isn’t configured on this deployment; send the file as base64 "content" instead.', 501);
      const name = safeName(b.filename), stamp = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
      const path = `${ws}/incoming/${stamp}-${Math.random().toString(36).slice(2, 8)}/${name}`;
      return {path, ...(await deps.storage.signedUpload(path)), method: 'PUT', note: 'PUT the file bytes to url, then POST action=ingest with this path.'};
    }
    case 'ingest': return ingest(deps, ws, b, who);
    case 'replace': {
      await store.replaceUpload(q, ws, Number(b.upload_id));
      await store.log(q, ws, who.email, 'upload_replaced', {upload_id: Number(b.upload_id)});
      return {ok: true, rules: await store.refreshFlags(q, ws)};
    }
    case 'file': {
      const u = await store.getUpload(q, ws, Number(Q.upload_id));
      if (!u.storage_path) throw bad('The original file wasn’t stored.', 404);
      return {url: await deps.storage.signedDownload(u.storage_path), name: u.original_name};
    }
    case 'flags': return store.listFlags(q, ws, Q);
    case 'flag': return store.flagDetail(q, ws, Number(Q.id));
    case 'flag-status': {
      await store.setFlagStatus(q, ws, Number(b.id), String(b.status || ''), b.note, who.email);
      await store.log(q, ws, who.email, 'flag_status', {id: Number(b.id), status: b.status});
      return {ok: true};
    }
    case 'run-rules': return {ok: true, rules: await store.refreshFlags(q, ws)};
    case 'members': {
      if (req.method === 'GET') return {members: await q('select email, role, (user_id is not null) app_linked, created_at from finance.members where workspace_id = $1 order by role, email', [ws])};
      const email = String(b.email || '').trim().toLowerCase(), newRole = String(b.role || '');
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) throw bad('Enter an email address.');
      if (newRole === 'remove') { await q('delete from finance.members where workspace_id = $1 and lower(email) = $2 and lower(email) <> $3', [ws, email, who.email]); return {ok: true}; }
      if (!(newRole in ROLES)) throw bad(`Role must be one of ${Object.keys(ROLES).join(', ')}, or remove.`);
      await q(`insert into finance.members (workspace_id, email, role) values ($1, $2, $3) on conflict (workspace_id, email) do update set role = excluded.role`, [ws, email, newRole]);
      await store.log(q, ws, who.email, 'member_set', {email, role: newRole});
      return {ok: true};
    }
  }
}

function createHandler(deps) {
  return async (req, res) => {
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Robots-Tag', 'noindex');
    if (!deps.hasDb()) return res.status(500).json({error: 'The finance workspace isn’t configured on this deployment.'});
    const action = String((req.query || {}).action || '');
    try {
      return res.status(200).json(await route(deps, req, res, action));
    } catch (e) {
      const status = e.status || 500;
      if (status >= 500) console.error('finance', action, e);
      return res.status(status).json({error: status >= 500 && !e.status ? 'Something went wrong. Try again, or check the server log.' : e.message});
    }
  };
}

// Sign-in codes go out through Resend (the same sender as BayCounty.me alerts).
async function sendEmail(to, m) {
  const key = process.env.RESEND_FULL_KEY || process.env.RESEND_API_KEY;
  if (!key) throw bad('Email isn’t configured on this deployment.', 500);
  const r = await resend('/emails', 'POST', {from: FROM, to: [to], subject: m.subject, text: m.text, html: m.html}, key);
  if (!r.ok) { console.error('finance sign-in email', r.status, JSON.stringify(r.body)); throw bad('The sign-in email didn’t send. Try again in a minute.', 502); }
}

module.exports = createHandler({q: db.q, hasDb: db.hasDb, storage, caller, sendEmail});
module.exports.createHandler = createHandler;
module.exports.config = {api: {bodyParser: {sizeLimit: '4.5mb'}}};
