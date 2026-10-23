// Who is calling /api/finance, and what they may do in a workspace.
//
// Ways in, checked in this order:
//  1. A finance session token: "Authorization: Bearer bcmf_..." (the mobile app) or the bcm_fin cookie (the
//     /finance page). Sessions start with a 6-digit code emailed to a workspace member (login + verify below).
//  2. A Supabase Auth access token (Bearer <jwt>), for a future Sign in with Apple in the app. Needs SUPABASE_ANON_KEY.
//  3. The BayCounty.me admin cookie (/admin sign-in).
// Cookie requests that change anything must also send X-BCM-Finance: 1 (or X-BCM-Admin: 1), so another site can't
// make a signed-in browser act. Whoever it is must be listed in finance.members for the workspace.
const crypto = require('crypto');
const {session: adminSession} = require('../_session');

const ROLES = {viewer: 1, auditor: 1, uploader: 2, reviewer: 3, owner: 4};
const CAN = {read: 1, upload: 2, review: 3, manage: 4};
const COOKIE = 'bcm_fin';
const SESSION_DAYS = 14;
const CODE_MINUTES = 10;
const MAX_ATTEMPTS = 5;

const sha = s => crypto.createHash('sha256').update(s).digest('hex');
const secret = () => process.env.FINANCE_HASH_SECRET || process.env.ALERTS_SECRET || 'baycounty.me-finance';
const codeHash = (email, code) => crypto.createHmac('sha256', secret()).update(`login|${email}|${code}`).digest('hex');
const normEmail = e => String(e || '').trim().toLowerCase();
const validEmail = e => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e) && e.length <= 254;

function cookieValue(req, name) {
  for (const part of String((req.headers || {}).cookie || '').split(';')) {
    const [k, ...v] = part.trim().split('=');
    if (k === name) return decodeURIComponent(v.join('='));
  }
  return null;
}
const setCookie = (res, val, maxAge) => res.setHeader('Set-Cookie', `${COOKIE}=${val}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`);

// ---- Supabase Auth (optional) ----
const supaCache = new Map();
async function supabaseUser(token) {
  const base = String(process.env.SUPABASE_URL || '').replace(/\/$/, ''), anon = process.env.SUPABASE_ANON_KEY;
  if (!base || !anon) return null;
  const h = sha(token), hit = supaCache.get(h);
  if (hit && hit.until > Date.now()) return hit.user;
  const r = await fetch(`${base}/auth/v1/user`, {headers: {Authorization: `Bearer ${token}`, apikey: anon}}).catch(() => null);
  const j = r && r.ok ? await r.json().catch(() => null) : null;
  const user = j && j.id && j.email ? {email: normEmail(j.email), userId: j.id, via: 'supabase'} : null;
  supaCache.set(h, {user, until: Date.now() + 60e3});
  if (supaCache.size > 500) supaCache.delete(supaCache.keys().next().value);
  return user;
}

async function sessionUser(q, token) {
  const rows = await q(`update finance.sessions set last_seen_at = now() where token_hash = $1 and revoked_at is null and expires_at > now()
                        returning email, client`, [sha(token)]);
  return rows.length ? {email: normEmail(rows[0].email), userId: null, via: rows[0].client === 'app' ? 'app' : 'web', token} : null;
}

// Returns {email, userId, via, csrf?} or null.
async function caller(req, q) {
  const h = req.headers || {}, auth = String(h.authorization || '');
  const unsafe = req.method !== 'GET' && req.method !== 'HEAD';
  if (/^Bearer\s+\S+/i.test(auth)) {
    const tok = auth.replace(/^Bearer\s+/i, '').trim();
    return tok.startsWith('bcmf_') ? sessionUser(q, tok) : supabaseUser(tok);
  }
  const csrf = unsafe && h['x-bcm-finance'] !== '1' && h['x-bcm-admin'] !== '1';
  const fin = cookieValue(req, COOKIE);
  if (fin && fin.startsWith('bcmf_')) {
    const u = await sessionUser(q, fin);
    if (u) return csrf ? {...u, csrf: true} : u;
  }
  const s = adminSession(req);
  if (!s) return null;
  return {email: normEmail(s.e), userId: null, via: 'admin', ...(csrf ? {csrf: true} : {})};
}

// The caller's role in a workspace, or a thrown 401/403/404. Links a Supabase user's id to their membership on first use.
async function requireRole(q, who, workspace, need) {
  if (!who) throw Object.assign(new Error('Sign in first.'), {status: 401});
  if (who.csrf) throw Object.assign(new Error('Missing X-BCM-Finance header.'), {status: 403});
  if (!/^[a-z0-9_-]{1,40}$/.test(String(workspace || ''))) throw Object.assign(new Error('Choose a workspace.'), {status: 400});
  const rows = await q(`select m.id, m.role, m.user_id from finance.members m where m.workspace_id = $1 and (lower(m.email) = $2 or ($3::uuid is not null and m.user_id = $3::uuid)) limit 1`,
    [workspace, who.email, who.userId || null]);
  if (!rows.length) throw Object.assign(new Error('You don’t have access to this workspace.'), {status: 404});
  const m = rows[0];
  if (who.userId && !m.user_id) await q('update finance.members set user_id = $1 where id = $2', [who.userId, m.id]).catch(() => {});
  if ((ROLES[m.role] || 0) < CAN[need]) throw Object.assign(new Error(`This needs ${Object.keys(ROLES).find(r => ROLES[r] === CAN[need])} access.`), {status: 403});
  return m.role;
}

// ---- Email-code sign-in ----
const hits = new Map();
function ipLimited(req) {
  const ip = String((req.headers || {})['x-real-ip'] || (req.headers || {})['x-forwarded-for'] || 'unknown').split(',')[0].trim();
  const now = Date.now(), recent = (hits.get(ip) || []).filter(t => now - t < 600e3);
  recent.push(now); hits.set(ip, recent);
  if (hits.size > 5000) hits.delete(hits.keys().next().value);
  return {limited: recent.length > 10, ipHash: sha('ip|' + ip).slice(0, 24)};
}

function codeEmail(code, appName = 'BayCounty.me Finance') {
  const text = `Your ${appName} sign-in code is ${code}\n\nIt works once and expires in ${CODE_MINUTES} minutes. If you didn't ask for it, ignore this email.`;
  const html = `<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:22px;color:#161B24">
<p>Your ${appName} sign-in code:</p>
<p style="font-size:30px;letter-spacing:6px;font-weight:bold;margin:12px 0;font-family:'Courier New',monospace">${code}</p>
<p style="color:#5A6372;font-size:13px">It works once and expires in ${CODE_MINUTES} minutes. If you didn't ask for it, ignore this email.</p></div>`;
  return {subject: `${code} is your BayCounty.me sign-in code`, text, html};
}

// Sends a code if the address belongs to a workspace member. Always answers the same way, so the form can't be used
// to find out who has access.
async function startLogin(q, req, body, sendEmail) {
  const email = normEmail(body.email), same = {ok: true, message: 'If that address has access, a 6-digit code is on its way.'};
  if (!validEmail(email)) throw Object.assign(new Error('Enter your email address.'), {status: 400});
  const {limited, ipHash} = ipLimited(req);
  if (limited) throw Object.assign(new Error('Too many sign-in attempts. Try again in a few minutes.'), {status: 429});
  const [m] = await q('select 1 from finance.members where lower(email) = $1 limit 1', [email]);
  if (!m) return same;
  const [{n}] = await q(`select count(*)::int n from finance.login_codes where lower(email) = $1 and created_at > now() - interval '15 minutes'`, [email]);
  if (n >= 3) return same;
  const code = String(crypto.randomInt(0, 1e6)).padStart(6, '0');
  await q(`insert into finance.login_codes (email, code_hash, expires_at, ip_hash) values ($1, $2, now() + make_interval(mins => $3), $4)`,
    [email, codeHash(email, code), CODE_MINUTES, ipHash]);
  await q(`delete from finance.login_codes where created_at < now() - interval '1 day'`).catch(() => {});
  await sendEmail(email, codeEmail(code));
  return same;
}

// Checks the newest unused code. A wrong guess counts against it; five wrong guesses use it up.
async function finishLogin(q, req, res, body) {
  const email = normEmail(body.email), code = String(body.code || '').replace(/\D/g, '');
  const fail = msg => Object.assign(new Error(msg || 'That code isn’t right. Check the newest email, or ask for a new code.'), {status: 400});
  if (!validEmail(email) || code.length !== 6) throw fail('Enter the 6-digit code from the email.');
  const {limited} = ipLimited(req);
  if (limited) throw Object.assign(new Error('Too many sign-in attempts. Try again in a few minutes.'), {status: 429});
  const [c] = await q(`select id, code_hash, attempts from finance.login_codes where lower(email) = $1 and used_at is null and expires_at > now()
                       order by created_at desc limit 1`, [email]);
  if (!c || c.attempts >= MAX_ATTEMPTS) throw fail('That code has expired. Ask for a new one.');
  const want = Buffer.from(c.code_hash), got = Buffer.from(codeHash(email, code));
  if (want.length !== got.length || !crypto.timingSafeEqual(want, got)) {
    await q('update finance.login_codes set attempts = attempts + 1 where id = $1', [c.id]);
    throw fail();
  }
  const used = await q('update finance.login_codes set used_at = now() where id = $1 and used_at is null returning id', [c.id]);
  if (!used.length) throw fail('That code has already been used. Ask for a new one.');
  const client = body.client === 'app' ? 'app' : 'web';
  const token = 'bcmf_' + crypto.randomBytes(32).toString('base64url');
  await q(`insert into finance.sessions (email, token_hash, client, user_agent, expires_at) values ($1, $2, $3, $4, now() + make_interval(days => $5))`,
    [email, sha(token), client, String((req.headers || {})['user-agent'] || '').slice(0, 200) || null, SESSION_DAYS]);
  await q(`delete from finance.sessions where expires_at < now() - interval '30 days'`).catch(() => {});
  if (client === 'web') setCookie(res, token, SESSION_DAYS * 86400);
  return {ok: true, email, expires_in_days: SESSION_DAYS, ...(client === 'app' ? {token} : {})};
}

async function logout(q, req, res, who) {
  if (who && who.token) await q('update finance.sessions set revoked_at = now() where token_hash = $1', [sha(who.token)]);
  setCookie(res, '', 0);
  return {ok: true};
}

module.exports = {caller, requireRole, startLogin, finishLogin, logout, codeEmail, ROLES, CAN, COOKIE};
