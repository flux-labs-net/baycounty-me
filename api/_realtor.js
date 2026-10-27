// Realtor console accounts (/realtor): sign-in by emailed link, a saved branding profile, and report history.
// Served at /api/realtor?action=... (vercel.json rewrites it to api/manage.js, which hands the request here; that keeps
// the deployment's function count where it is).
//
//   POST login {email}        email a one-time sign-in link (always answers the same, so it can't be used to probe)
//   GET  verify?t=            a confirm page; only its button (a POST) signs in, because email scanners open links first
//   POST verify               use the link once, create the account if sign-up is open, set the session cookie
//   GET  me                   the agent, their branding and their last 25 reports
//   POST brand {…}            save branding (names, contact, colors, logo and photo as small data: URLs)
//   POST report {address,…}   add a report to the agent's history (the report itself comes from /api/v1/address-report)
//   POST delete_report {id}   remove one report from history
//   POST delete_account       delete the agent, their branding and their history
//   POST logout
// Every POST except login/verify needs the X-BCM-Agent: 1 header and a same-site Origin. Sign-up: REALTOR_SIGNUP=open
// (default, anyone with an email address) or invite (new addresses are saved as pending until an admin turns them on).
const crypto = require('crypto');
const {q, hasDb} = require('./_db');
const {derive, ipOf} = require('./_gate');
const {FROM, resend, sameOrigin} = require('./_alerts');
const {realtorSignInEmail} = require('./_emails');
const {admins} = require('./_session');

const SITE = 'https://baycounty.me';
const COOKIE = 'bcm_agent';
const SESSION_DAYS = 30;
const LINK_MIN = 20;
const MAX_LOGO = 400000, MAX_PHOTO = 300000;
const bad = (msg, status = 400) => Object.assign(new Error(msg), {status, expose: true});

/* ---------- signed tokens (same shape as the admin session, its own key) ---------- */
const b64 = s => Buffer.from(s).toString('base64url');
const sign = s => crypto.createHmac('sha256', derive('bcm-agent-v1')).update(s).digest('base64url');
function makeToken(obj) { const body = b64(JSON.stringify(obj)); return body + '.' + sign(body); }
function readToken(tok) {
  const [body, sig] = String(tok || '').split('.');
  if (!body || !sig || !process.env.ALERTS_SECRET) return null;
  const want = sign(body);
  if (want.length !== sig.length || !crypto.timingSafeEqual(Buffer.from(want), Buffer.from(sig))) return null;
  try { const p = JSON.parse(Buffer.from(body, 'base64url').toString()); return p.exp > Date.now() ? p : null; } catch (e) { return null; }
}
const cookies = req => Object.fromEntries(String(req.headers.cookie || '').split(';').map(c => c.trim().split('=')).filter(x => x[0]).map(([k, ...v]) => [k, decodeURIComponent(v.join('='))]));
const setCookie = (res, val, maxAge) => res.setHeader('Set-Cookie', `${COOKIE}=${val}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`);

/* ---------- validation ---------- */
const EMAIL = /^[^\s@<>"]{1,64}@[^\s@<>"]{1,190}\.[a-z]{2,24}$/i;
const COLOR = /^#[0-9a-f]{6}$/i;
// Raster images only (SVG can carry script). The API checks the header bytes match the stated type.
const IMG = /^data:image\/(png|jpeg);base64,([A-Za-z0-9+/]+={0,2})$/;
const MAGIC = {png: [0x89, 0x50, 0x4e, 0x47], jpeg: [0xff, 0xd8, 0xff]};
function image(v, max, label) {
  if (v == null || v === '') return null;
  const m = IMG.exec(String(v));
  if (!m) throw bad(`${label} must be a PNG or JPEG image.`);
  if (String(v).length > max) throw bad(`${label} is too large. Use an image under ${Math.round(max * 0.75 / 1000)} KB.`);
  const head = Buffer.from(m[2].slice(0, 16), 'base64');
  if (!MAGIC[m[1]].every((b, i) => head[i] === b)) throw bad(`${label} doesn't look like a ${m[1].toUpperCase()} file.`);
  return String(v);
}
const text = (v, n) => { const s = String(v ?? '').replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim(); return s ? s.slice(0, n) : null; };
const longText = (v, n) => { const s = String(v ?? '').replace(/[\u0000-\u0009\u000b-\u001f\u007f]/g, '').trim(); return s ? s.slice(0, n) : null; };
function website(v) {
  const s = text(v, 200); if (!s) return null;
  const u = /^https?:\/\//i.test(s) ? s : 'https://' + s;
  try { const x = new URL(u); if (!/^https?:$/.test(x.protocol) || !x.hostname.includes('.')) throw 0; return x.toString().replace(/\/$/, ''); }
  catch (e) { throw bad('The website doesn’t look like a web address.'); }
}
// Turns a posted branding form into a clean row. Unknown fields are ignored.
function cleanBrand(b) {
  const email = text(b.email, 200);
  if (email && !EMAIL.test(email)) throw bad('The contact email doesn’t look right.');
  for (const k of ['color_primary', 'color_accent']) if (b[k] && !COLOR.test(String(b[k]))) throw bad('Colors must look like #1e3a76.');
  return {agent_name: text(b.agent_name, 120), title: text(b.title, 120), brokerage: text(b.brokerage, 160), license_no: text(b.license_no, 60),
    phone: text(b.phone, 40), email: email ? email.toLowerCase() : null, website: website(b.website), office_address: text(b.office_address, 200),
    tagline: text(b.tagline, 160), disclaimer: longText(b.disclaimer, 1200),
    color_primary: b.color_primary ? String(b.color_primary).toLowerCase() : null, color_accent: b.color_accent ? String(b.color_accent).toLowerCase() : null,
    logo: image(b.logo, MAX_LOGO, 'The logo'), photo: image(b.photo, MAX_PHOTO, 'The photo')};
}
const BRAND_COLS = ['agent_name', 'title', 'brokerage', 'license_no', 'phone', 'email', 'website', 'office_address', 'tagline', 'disclaimer', 'color_primary', 'color_accent', 'logo', 'photo'];

/* ---------- data ---------- */
const signupMode = () => (String(process.env.REALTOR_SIGNUP || 'open').toLowerCase() === 'invite' ? 'invite' : 'open');
async function agentByEmail(email) { return (await q('select * from realtor.agents where email = $1', [email]))[0] || null; }
async function session(req) {
  const t = readToken(cookies(req)[COOKIE]);
  if (!t || t.kind !== 'agent') return null;
  const a = (await q('select * from realtor.agents where id = $1', [t.id]))[0];
  return a && a.status === 'active' ? a : null;
}
async function me(agent) {
  const [brand] = await q(`select ${BRAND_COLS.join(', ')}, updated_at from realtor.brands where agent_id = $1`, [agent.id]);
  const reports = await q('select id, address, city, zip, parcel_id, lat, lon, prepared_for, created_at from realtor.reports where agent_id = $1 order by created_at desc limit 25', [agent.id]);
  return {agent: {email: agent.email, status: agent.status, place_id: agent.place_id, created_at: agent.created_at, reports_run: agent.reports_run}, brand: brand || null, reports};
}

/* ---------- pages ---------- */
const escH = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
function confirmPage(ok, email, tok) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>Sign in · Realtor console</title><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600&display=swap"><link rel="stylesheet" href="/assets/site.css">
<style>body{display:block}.b{max-width:420px;margin:14vh auto 0;padding:24px;background:var(--surface);border:1px solid var(--line);border-radius:16px}h1{font:600 1.2rem var(--f-display);margin:0 0 8px}p{color:var(--muted);margin:0 0 16px}button,a.btn{display:inline-flex;min-height:44px;align-items:center;padding:0 20px;border-radius:10px;border:0;background:var(--navy);color:#fff;font:500 .95rem var(--f-body);cursor:pointer;text-decoration:none}</style></head>
<body><div class="b">${ok ? `<h1>Sign in to the realtor console</h1><p>Signing in as ${escH(email)}.</p>
<form method="post" action="/api/realtor?action=verify"><input type="hidden" name="t" value="${escH(tok)}"><button type="submit" autofocus>Sign in</button></form>`
    : `<h1>This link has expired</h1><p>Sign-in links last ${LINK_MIN} minutes and work once.</p><a class="btn" href="/realtor">Get a new link</a>`}</div></body></html>`;
}

/* ---------- handler ---------- */
const loginHits = new Map();
const body = req => (typeof req.body === 'string' ? (() => { try { return JSON.parse(req.body || '{}'); } catch (e) { return Object.fromEntries(new URLSearchParams(req.body)); } })() : req.body || {});

async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('X-Robots-Tag', 'noindex');
  const action = String((req.query || {}).action || '');
  if (!process.env.ALERTS_SECRET || !hasDb()) return res.status(503).json({error: 'The realtor console isn’t set up on this deployment yet.'});
  try {
    if (action === 'login' && req.method === 'POST') {
      if (!sameOrigin(req)) throw bad('Sign in from baycounty.me.', 403);
      const ip = ipOf(req), now = Date.now();
      const recent = (loginHits.get(ip) || []).filter(t => now - t < 600e3); recent.push(now); loginHits.set(ip, recent);
      if (recent.length > 5) throw bad('Too many sign-in attempts. Try again in a few minutes.', 429);
      const email = String(body(req).email || '').trim().toLowerCase();
      if (!EMAIL.test(email)) throw bad('Enter a valid email address.');
      const existing = await agentByEmail(email);
      const isAdmin = admins().includes(email);
      const send = existing ? existing.status === 'active' : (signupMode() === 'open' || isAdmin);
      if (!existing && !send) await q(`insert into realtor.agents (email, status) values ($1, 'pending') on conflict (email) do nothing`, [email]);
      if (send) {
        const tok = makeToken({kind: 'login', e: email, n: crypto.randomBytes(9).toString('base64url'), exp: now + LINK_MIN * 60e3});
        const m = realtorSignInEmail(`${SITE}/api/realtor?action=verify&t=${encodeURIComponent(tok)}`, LINK_MIN);
        const r = await resend('/emails', 'POST', {from: FROM, to: [email], subject: m.subject, text: m.text, html: m.html}, process.env.RESEND_FULL_KEY || process.env.RESEND_API_KEY);
        if (!r.ok) console.error('realtor login email', r.status);
      }
      return res.status(200).json({ok: true, message: signupMode() === 'invite'
        ? 'If that address has access, a sign-in link is on its way. New addresses are added once BayCounty.me turns them on.'
        : 'Check your email for a sign-in link. It works once and lasts 20 minutes.'});
    }
    if (action === 'verify' && req.method === 'GET') {
      if (!req.query.t && req.query['amp;t']) req.query.t = req.query['amp;t'];
      const t = readToken(req.query.t);
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.setHeader('Referrer-Policy', 'no-referrer');
      return res.status(200).send(confirmPage(!!(t && t.kind === 'login'), t && t.e, String(req.query.t || '').replace(/[^A-Za-z0-9._-]/g, '')));
    }
    if (action === 'verify' && req.method === 'POST') {
      const t = readToken(body(req).t);
      const fail = () => { res.setHeader('Location', '/realtor?signin=expired'); return res.status(303).end(); };
      if (!t || t.kind !== 'login') return fail();
      const used = await q('insert into realtor.logins (nonce, email) values ($1, $2) on conflict (nonce) do nothing returning nonce', [t.n, t.e]);
      if (!used.length) return fail();
      let a = await agentByEmail(t.e);
      if (!a && (signupMode() === 'open' || admins().includes(t.e))) a = (await q(`insert into realtor.agents (email) values ($1) on conflict (email) do update set email = excluded.email returning *`, [t.e]))[0];
      if (!a || a.status !== 'active') return fail();
      await q('update realtor.agents set last_login_at = now(), login_count = login_count + 1 where id = $1', [a.id]);
      setCookie(res, makeToken({kind: 'agent', id: a.id, exp: Date.now() + SESSION_DAYS * 864e5}), SESSION_DAYS * 86400);
      res.setHeader('Location', '/realtor'); return res.status(303).end();
    }
    if (action === 'logout') { setCookie(res, '', 0); return res.status(200).json({ok: true}); }

    const agent = await session(req);
    if (!agent) return res.status(401).json({error: 'Sign in first.', signup: signupMode()});
    if (action === 'me' && req.method === 'GET') return res.status(200).json(await me(agent));
    if (req.method !== 'POST') throw bad('Use POST.', 405);
    if (req.headers['x-bcm-agent'] !== '1' || !sameOrigin(req)) throw bad('That request didn’t come from the console.', 403);
    const b = body(req);
    if (action === 'brand') {
      const row = cleanBrand(b);
      await q(`insert into realtor.brands (agent_id, ${BRAND_COLS.join(', ')}, updated_at) values ($1, ${BRAND_COLS.map((_, i) => '$' + (i + 2)).join(', ')}, now())
               on conflict (agent_id) do update set ${BRAND_COLS.map(c => `${c} = excluded.${c}`).join(', ')}, updated_at = now()`, [agent.id, ...BRAND_COLS.map(c => row[c])]);
      return res.status(200).json(await me(agent));
    }
    if (action === 'report') {
      const address = text(b.address, 160);
      if (!address) throw bad('Missing the address.');
      const lat = Number(b.lat), lon = Number(b.lon);
      const [r] = await q(`insert into realtor.reports (agent_id, place_id, address, city, zip, parcel_id, lat, lon, prepared_for) values ($1, $2, $3, $4, $5, $6, $7, $8, $9) returning id, created_at`,
        [agent.id, agent.place_id, address, text(b.city, 80), text(b.zip, 10), text(b.parcel_id, 30), Number.isFinite(lat) ? lat : null, Number.isFinite(lon) ? lon : null, text(b.prepared_for, 120)]);
      await q('update realtor.agents set reports_run = reports_run + 1 where id = $1', [agent.id]);
      return res.status(200).json({ok: true, id: r.id, created_at: r.created_at});
    }
    if (action === 'delete_report') {
      await q('delete from realtor.reports where id = $1 and agent_id = $2', [Number(b.id) || 0, agent.id]);
      return res.status(200).json({ok: true});
    }
    if (action === 'delete_account') {
      await q('delete from realtor.agents where id = $1', [agent.id]);
      setCookie(res, '', 0);
      return res.status(200).json({ok: true});
    }
    throw bad('Unknown action.', 404);
  } catch (e) {
    if (!e.expose) console.error('realtor', action, e);
    return res.status(e.status || 500).json({error: e.expose ? e.message : 'Something went wrong. Please try again.'});
  }
}

module.exports = handler;
Object.assign(module.exports, {cleanBrand, image, website, makeToken, readToken, signupMode, COOKIE});
