// Who is calling /api/finance, and what they may do in a workspace.
// Two ways in:
//  * the BayCounty.me admin cookie (signed-in by emailed link; addresses in ADMIN_EMAILS). Browser POSTs must also send
//    X-BCM-Admin: 1, as on /admin, so another site can't make a signed-in browser change anything.
//  * a Supabase Auth access token (Authorization: Bearer <jwt>) for the mobile app, checked against Supabase's
//    /auth/v1/user. Off until SUPABASE_URL and SUPABASE_ANON_KEY are set.
// Either way, the caller must be listed in finance.members for the workspace.
const crypto = require('crypto');
const {session} = require('../_session');

const ROLES = {viewer: 1, auditor: 1, uploader: 2, reviewer: 3, owner: 4};
const CAN = {read: 1, upload: 2, review: 3, manage: 4};

const cache = new Map();
async function bearerUser(token) {
  const base = String(process.env.SUPABASE_URL || '').replace(/\/$/, ''), anon = process.env.SUPABASE_ANON_KEY;
  if (!base || !anon) return null;
  const h = crypto.createHash('sha256').update(token).digest('hex'), hit = cache.get(h);
  if (hit && hit.until > Date.now()) return hit.user;
  const r = await fetch(`${base}/auth/v1/user`, {headers: {Authorization: `Bearer ${token}`, apikey: anon}}).catch(() => null);
  const j = r && r.ok ? await r.json().catch(() => null) : null;
  const user = j && j.id && j.email ? {email: String(j.email).toLowerCase(), userId: j.id, via: 'app'} : null;
  cache.set(h, {user, until: Date.now() + 60e3});
  if (cache.size > 500) cache.delete(cache.keys().next().value);
  return user;
}

// Returns {email, userId, via} or null.
async function caller(req) {
  const auth = String((req.headers || {}).authorization || '');
  if (/^Bearer\s+\S+/i.test(auth)) return bearerUser(auth.replace(/^Bearer\s+/i, '').trim());
  const s = session(req);
  if (!s) return null;
  if (req.method !== 'GET' && req.headers['x-bcm-admin'] !== '1') return {email: s.e, userId: null, via: 'cookie', csrf: true};
  return {email: s.e, userId: null, via: 'cookie'};
}

// The caller's role in a workspace, or a thrown 401/403/404. Links an app user's id to their membership on first use.
async function requireRole(q, who, workspace, need) {
  if (!who) throw Object.assign(new Error('Sign in first.'), {status: 401});
  if (who.csrf) throw Object.assign(new Error('Missing admin header.'), {status: 403});
  if (!/^[a-z0-9_-]{1,40}$/.test(String(workspace || ''))) throw Object.assign(new Error('Choose a workspace.'), {status: 400});
  const rows = await q(`select m.id, m.role, m.user_id from finance.members m where m.workspace_id = $1 and (lower(m.email) = $2 or ($3::uuid is not null and m.user_id = $3::uuid)) limit 1`,
    [workspace, who.email, who.userId || null]);
  if (!rows.length) throw Object.assign(new Error('You don’t have access to this workspace.'), {status: 404});
  const m = rows[0];
  if (who.userId && !m.user_id) await q('update finance.members set user_id = $1 where id = $2', [who.userId, m.id]).catch(() => {});
  if ((ROLES[m.role] || 0) < CAN[need]) throw Object.assign(new Error(`This needs ${Object.keys(ROLES).find(r => ROLES[r] === CAN[need])} access.`), {status: 403});
  return m.role;
}

module.exports = {caller, requireRole, ROLES, CAN};
