// BayCounty.me admin: API keys, throttles, request logs and analytics. Used by /admin.
// Sign-in is by emailed link to an address listed in ADMIN_EMAILS (comma-separated, set in Vercel).
// The session is a signed, HttpOnly, SameSite=Strict cookie; changes also need the X-BCM-Admin header.
const crypto = require('crypto');
const {q, hasDb} = require('./_db');
const {sha256, derive, ipOf} = require('./_gate');
const {FROM, resend} = require('./_alerts');

const SITE = 'https://baycounty.me';
const COOKIE = 'bcm_admin';
const SESSION_HOURS = 12;
const b64 = s => Buffer.from(s).toString('base64url');
const sign = s => crypto.createHmac('sha256', derive('bcm-admin-v1')).update(s).digest('base64url');
const admins = () => String(process.env.ADMIN_EMAILS || '').toLowerCase().split(/[\s,]+/).filter(Boolean);

function makeToken(obj) { const body = b64(JSON.stringify(obj)); return body + '.' + sign(body); }
function readToken(tok) {
  const [body, sig] = String(tok || '').split('.');
  if (!body || !sig || !process.env.ALERTS_SECRET) return null;
  const want = sign(body);
  if (want.length !== sig.length || !crypto.timingSafeEqual(Buffer.from(want), Buffer.from(sig))) return null;
  try { const p = JSON.parse(Buffer.from(body, 'base64url').toString()); return p.exp > Date.now() ? p : null; } catch (e) { return null; }
}
function cookies(req) {
  return Object.fromEntries(String(req.headers.cookie || '').split(';').map(c => c.trim().split('=')).filter(x => x[0]).map(([k, ...v]) => [k, decodeURIComponent(v.join('='))]));
}
function session(req) {
  const s = readToken(cookies(req)[COOKIE]);
  return s && s.kind === 'session' && admins().includes(s.e) ? s : null;
}
const setCookie = (res, val, maxAge) => res.setHeader('Set-Cookie', `${COOKIE}=${val}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=${maxAge}`);

const loginHits = new Map();
const audit = (admin, action, keyId, detail) => q('insert into apiadmin.audit (admin, action, key_id, detail) values ($1, $2, $3, $4)', [admin, action, keyId || null, detail ? JSON.stringify(detail) : null]);

function newKey() {
  const key = 'bcm_' + crypto.randomBytes(24).toString('base64url');
  return {key, prefix: key.slice(0, 10), hash: sha256(key)};
}
const intOrNull = v => (v === '' || v === null || v === undefined) ? null : Math.max(0, parseInt(v, 10) || 0);
const txt = (v, n = 300) => (v === undefined ? undefined : (String(v ?? '').trim().slice(0, n) || null));
const EDITABLE = ['name', 'owner_name', 'owner_email', 'organization', 'notes', 'per_minute', 'per_day', 'status', 'expires_at'];

function clean(body) {
  const out = {};
  for (const f of EDITABLE) {
    if (!(f in body)) continue;
    if (f === 'per_minute' || f === 'per_day') out[f] = intOrNull(body[f]);
    else if (f === 'status') { if (['active', 'disabled', 'revoked'].includes(body[f])) out[f] = body[f]; }
    else if (f === 'expires_at') out[f] = body[f] ? new Date(body[f]).toISOString() : null;
    else out[f] = txt(body[f], f === 'notes' ? 2000 : 300);
  }
  return out;
}

// Which requests a stats/logs query covers: one key, keyless traffic, or everything.
function scope(k, params) {
  if (!k || k === 'all') return () => '';
  if (k === 'anon') return a => ` and ${a}key_id is null`;
  params.push(k); const n = params.length;
  return a => ` and ${a}key_id = $${n}`;
}

async function stats(key, days) {
  const p = [days], sc = scope(key, p), W = (a = '') => `${a}at > now() - make_interval(days => $1)` + sc(a), w = W();
  const [tot] = await q(`select count(*)::int requests, count(*) filter (where status >= 400 and status <> 429)::int errors,
      count(*) filter (where status = 429)::int throttled, round(avg(ms))::int avg_ms,
      percentile_disc(0.95) within group (order by ms) p95_ms, count(distinct ip_hash)::int connections,
      coalesce(sum(rows_returned), 0)::bigint rows_returned, max(at) last_request from apiadmin.requests where ${w}`, p);
  const daily = await q(`with d as (select generate_series((now() at time zone 'America/Chicago')::date - ($1::int - 1), (now() at time zone 'America/Chicago')::date, interval '1 day')::date as day)
      select to_char(d.day, 'YYYY-MM-DD') as day, count(r.id)::int requests, count(r.id) filter (where r.status >= 400)::int errors
      from d left join apiadmin.requests r on (r.at at time zone 'America/Chicago')::date = d.day and ${W('r.')}
      group by d.day order by d.day`, p);
  const group = col => q(`select coalesce(${col}::text, '(none)') label, count(*)::int n from apiadmin.requests where ${w} group by 1 order by 2 desc limit 10`, p);
  const [endpoints, datasets, statuses, surfaces, ips] = await Promise.all([group('endpoint'), group('dataset'), group('status'), group('surface'), group('host(ip)')]);
  return {days, totals: tot, daily, endpoints, datasets, statuses, surfaces, ips: ips.filter(x => x.label !== '(none)')};
}

async function route(req, res, action, me) {
  const body = req.method === 'POST' ? (typeof req.body === 'string' ? JSON.parse(req.body || '{}') : req.body || {}) : {};
  const Q = req.query || {};
  switch (action) {
    case 'me': return {email: me.e, expires: me.exp};
    case 'keys': {
      const rows = await q(`select k.id, k.name, k.owner_name, k.owner_email, k.organization, k.notes, k.prefix, k.per_minute, k.per_day, k.status,
          k.expires_at, k.created_by, k.created_at, k.updated_at, k.rotated_at, k.last_used_at,
          (select count(*)::int from apiadmin.requests r where r.key_id = k.id and r.at > now() - interval '24 hours') req_24h,
          (select count(*)::int from apiadmin.requests r where r.key_id = k.id and r.at > now() - interval '30 days') req_30d
        from apiadmin.keys k order by (k.status = 'revoked'), k.created_at desc`);
      const [anon] = await q(`select count(*) filter (where at > now() - interval '24 hours')::int req_24h, count(*)::int req_30d from apiadmin.requests where key_id is null and at > now() - interval '30 days'`);
      return {keys: rows, anonymous: anon};
    }
    case 'create': {
      const f = clean(body);
      if (!f.name) throw Object.assign(new Error('Give the key a name.'), {status: 400});
      const [s] = await q('select default_per_minute, default_per_day from apiadmin.settings where id');
      const k = newKey();
      const [row] = await q(`insert into apiadmin.keys (name, owner_name, owner_email, organization, notes, per_minute, per_day, status, expires_at, prefix, key_hash, created_by)
          values ($1, $2, $3, $4, $5, $6, $7, coalesce($8, 'active'), $9, $10, $11, $12) returning id, name, prefix, per_minute, per_day, status`,
        [f.name, f.owner_name, f.owner_email, f.organization, f.notes, 'per_minute' in f ? f.per_minute : s.default_per_minute, 'per_day' in f ? f.per_day : s.default_per_day,
         f.status || null, f.expires_at || null, k.prefix, k.hash, me.e]);
      await audit(me.e, 'create_key', row.id, {name: f.name});
      return {key: k.key, record: row};
    }
    case 'update': {
      const f = clean(body), cols = Object.keys(f);
      if (!body.id || !cols.length) throw Object.assign(new Error('Nothing to change.'), {status: 400});
      if ('name' in f && !f.name) throw Object.assign(new Error('A key needs a name.'), {status: 400});
      const sets = cols.map((c, i) => `${c} = $${i + 2}`).join(', ');
      const [row] = await q(`update apiadmin.keys set ${sets}, updated_at = now() where id = $1 returning id, name, status, per_minute, per_day`, [body.id, ...cols.map(c => f[c])]);
      if (!row) throw Object.assign(new Error('Key not found.'), {status: 404});
      await audit(me.e, 'update_key', row.id, f);
      return {record: row};
    }
    case 'rotate': {
      const k = newKey();
      const [row] = await q(`update apiadmin.keys set prefix = $2, key_hash = $3, rotated_at = now(), updated_at = now() where id = $1 and status <> 'revoked' returning id, name, prefix`, [body.id, k.prefix, k.hash]);
      if (!row) throw Object.assign(new Error('Key not found or revoked.'), {status: 404});
      await audit(me.e, 'rotate_key', row.id, null);
      return {key: k.key, record: row};
    }
    case 'settings': {
      if (req.method === 'POST') {
        const vals = {anon_per_minute: intOrNull(body.anon_per_minute), anon_per_day: intOrNull(body.anon_per_day), require_key: !!body.require_key,
          default_per_minute: intOrNull(body.default_per_minute), default_per_day: intOrNull(body.default_per_day)};
        await q(`update apiadmin.settings set anon_per_minute = $1, anon_per_day = $2, require_key = $3, default_per_minute = $4, default_per_day = $5, updated_at = now() where id`,
          [vals.anon_per_minute, vals.anon_per_day, vals.require_key, vals.default_per_minute, vals.default_per_day]);
        await audit(me.e, 'update_settings', null, vals);
      }
      const [s] = await q('select anon_per_minute, anon_per_day, require_key, default_per_minute, default_per_day, updated_at from apiadmin.settings where id');
      return {settings: s};
    }
    case 'stats': return stats(Q.key || 'all', Math.min(Math.max(parseInt(Q.days || '30', 10) || 30, 1), 90));
    case 'logs': {
      const p = [], lim = Math.min(parseInt(Q.limit || '100', 10) || 100, 500);
      let w = 'true' + scope(Q.key, p)('r.');
      if (Q.before) { p.push(parseInt(Q.before, 10)); w += ` and r.id < $${p.length}`; }
      if (Q.status === 'errors') w += ' and r.status >= 400';
      if (Q.ip) { p.push(String(Q.ip).trim()); w += ` and r.ip <<= $${p.length}::inet`; }
      const rows = await q(`select r.id, r.at, r.key_id, k.name key_name, k.prefix, r.surface, r.endpoint, r.dataset, r.query, r.status, r.rows_returned, r.ms, r.ip_hash, host(r.ip) ip, r.user_agent
          from apiadmin.requests r left join apiadmin.keys k on k.id = r.key_id where ${w} order by r.id desc limit ${lim}`, p);
      return {logs: rows, next_before: rows.length === lim ? rows[rows.length - 1].id : null};
    }
    case 'blocks': {
      if (req.method === 'POST') {
        const net = String(body.network || '').trim();
        if (!/^[0-9a-fA-F:.]+(\/\d{1,3})?$/.test(net)) throw Object.assign(new Error('Enter an IP address or range, e.g. 203.0.113.7 or 203.0.113.0/24.'), {status: 400});
        let row;
        try {
          [row] = await q(`insert into apiadmin.blocks (network, reason, expires_at, created_by) values ($1::cidr, $2, $3, $4)
              on conflict (network) do update set reason = excluded.reason, expires_at = excluded.expires_at returning id, network::text network`,
            [net, txt(body.reason, 300) || null, body.expires_at ? new Date(body.expires_at).toISOString() : null, me.e]);
        } catch (e) { if (e.code === '22P02' || e.code === '22023') throw Object.assign(new Error('That isn\u2019t a valid IP address or range.'), {status: 400}); throw e; }
        await audit(me.e, 'block_ip', null, {network: row.network, reason: txt(body.reason, 300) || null});
      }
      return {blocks: await q(`select b.id, b.network::text network, b.reason, b.expires_at, b.created_by, b.created_at,
          (select count(*)::int from apiadmin.requests r where r.ip <<= b.network and r.status = 403 and r.at > now() - interval '30 days') blocked_30d
          from apiadmin.blocks b order by b.created_at desc`)};
    }
    case 'unblock': {
      const [row] = await q('delete from apiadmin.blocks where id = $1 returning network::text network', [body.id]);
      if (!row) throw Object.assign(new Error('Block not found.'), {status: 404});
      await audit(me.e, 'unblock_ip', null, {network: row.network});
      return {ok: true};
    }
    case 'audit': return {audit: await q('select at, admin, action, key_id, detail from apiadmin.audit order by id desc limit 100')};
    default: throw Object.assign(new Error('Unknown action.'), {status: 404});
  }
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('X-Robots-Tag', 'noindex');
  const action = String((req.query || {}).action || '');
  if (!process.env.ALERTS_SECRET || !hasDb()) return res.status(500).json({error: 'Admin isn’t configured on this deployment.'});

  if (action === 'login' && req.method === 'POST') {
    const ip = ipOf(req), now = Date.now();
    const recent = (loginHits.get(ip) || []).filter(t => now - t < 600e3); recent.push(now); loginHits.set(ip, recent);
    if (recent.length > 5) return res.status(429).json({error: 'Too many sign-in attempts. Try again in a few minutes.'});
    const b = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : req.body || {};
    const email = String(b.email || '').trim().toLowerCase();
    if (admins().includes(email)) {
      const tok = makeToken({kind: 'login', e: email, n: crypto.randomBytes(9).toString('base64url'), exp: now + 15 * 60e3});
      const link = `${SITE}/api/admin?action=verify&t=${encodeURIComponent(tok)}`;
      const key = process.env.RESEND_FULL_KEY || process.env.RESEND_API_KEY;
      const r = await resend('/emails', 'POST', {from: FROM, to: [email], subject: 'Sign in to BayCounty.me admin',
        text: `Sign in to the BayCounty.me admin:\n\n${link}\n\nThe link works once and expires in 15 minutes. If you didn't ask for it, ignore this email.`,
        html: `<p>Sign in to the BayCounty.me admin:</p><p><a href="${link}" style="display:inline-block;padding:10px 18px;background:#1E3A76;color:#fff;border-radius:8px;text-decoration:none">Sign in</a></p><p style="color:#5A6372;font-size:13px">The link works once and expires in 15 minutes. If you didn't ask for it, ignore this email.</p>`}, key);
      if (!r.ok) console.error('admin login email', r.status, JSON.stringify(r.body));
      await audit(email, 'login_requested', null, {ok: r.ok}).catch(() => {});
    }
    return res.status(200).json({ok: true, message: 'If that address can sign in, a link is on its way.'});
  }
  // The emailed link opens a confirm page; only pressing its button (a POST) signs in. Email security scanners
  // (Microsoft Defender Safe Links and others) open links before you do, and would otherwise use up the one-time link.
  if (action === 'verify' && req.method === 'GET') {
    if (!req.query.t && req.query['amp;t']) req.query.t = req.query['amp;t']; // link copied from an HTML view with &amp;
    const t = readToken(req.query.t);
    const ok = t && t.kind === 'login' && admins().includes(t.e);
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.setHeader('Referrer-Policy', 'no-referrer');
    const tokAttr = String(req.query.t || '').replace(/[^A-Za-z0-9._-]/g, '');
    return res.status(200).send(`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>Sign in · BayCounty.me admin</title><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600&display=swap"><link rel="stylesheet" href="/assets/site.css">
<style>body{display:block}.b{max-width:420px;margin:14vh auto 0;padding:24px;background:var(--surface);border:1px solid var(--line);border-radius:12px}h1{font:600 1.2rem var(--f-display);margin:0 0 8px}p{color:var(--muted);margin:0 0 16px}button,a.btn{display:inline-flex;min-height:40px;align-items:center;padding:0 18px;border-radius:8px;border:0;background:var(--navy);color:#fff;font:500 .95rem var(--f-body);cursor:pointer;text-decoration:none}</style></head>
<body><div class="b">${ok ? `<h1>Sign in to BayCounty.me admin</h1><p>Signing in as ${t.e.replace(/[<>&"]/g, '')}.</p>
<form method="post" action="/api/admin?action=verify"><input type="hidden" name="t" value="${tokAttr}"><button type="submit" autofocus>Sign in</button></form>`
      : `<h1>This link has expired</h1><p>Sign-in links last 15 minutes and work once.</p><a class="btn" href="/admin">Get a new link</a>`}</div></body></html>`);
  }
  if (action === 'verify' && req.method === 'POST') {
    const b = typeof req.body === 'string' ? Object.fromEntries(new URLSearchParams(req.body)) : req.body || {};
    const t = readToken(b.t);
    const fail = () => { res.setHeader('Location', '/admin?signin=expired'); return res.status(303).end(); };
    if (!t || t.kind !== 'login' || !admins().includes(t.e)) return fail();
    const used = await q(`select 1 from apiadmin.audit where action = 'login' and detail->>'nonce' = $1`, [t.n]);
    if (used.length) return fail();
    await audit(t.e, 'login', null, {nonce: t.n});
    setCookie(res, makeToken({kind: 'session', e: t.e, exp: Date.now() + SESSION_HOURS * 3600e3}), SESSION_HOURS * 3600);
    res.setHeader('Location', '/admin'); return res.status(303).end();
  }
  if (action === 'logout') { setCookie(res, '', 0); return res.status(200).json({ok: true}); }

  const me = session(req);
  if (!me) return res.status(401).json({error: 'Sign in first.'});
  if (req.method === 'POST' && req.headers['x-bcm-admin'] !== '1') return res.status(403).json({error: 'Missing admin header.'});
  try {
    return res.status(200).json(await route(req, res, action, me));
  } catch (e) {
    if (!e.status) console.error('admin', action, e);
    return res.status(e.status || 500).json({error: e.status ? e.message : 'Something went wrong.'});
  }
};
