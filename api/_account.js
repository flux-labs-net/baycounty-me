// Citizen accounts: sign in with a code sent by email, save a home address, choose what to hear about, and see
// what's happening near home. The website (/account) and both apps use it. Served at /api/account?action=... (vercel.json
// rewrites it to api/manage.js, which hands the request here; that keeps the deployment's function count where it is).
//
//   POST start {email, next?}             email a 6-digit code and a one-tap link (always answers the same, so it can't
//                                         be used to find out who has an account). next '/realtor' sends the one-tap
//                                         link back to the realtor console instead of My home
//   POST verify {email, code, client}     check the code; create the account the first time; start a session. client 'web'
//                                         sets the session cookie; 'ios' / 'android' get {token} for an Authorization header
//   GET  link?t=                          the one-tap link's confirm page; only its button (a POST) signs in, because email
//   POST link {t}                         scanners open links before people do
//   GET  me                               the person, their home, their choices and the topic lists
//   POST profile {first_name}
//   POST home {address} | {lat, lon, label}   save the home (looked up in the county's address points)
//   POST home_delete
//   POST prefs {weekly_email, alert_email[], push_topics[], radius_mi, topics[]}
//   GET  feed                             what's happening near the saved home (api/_nearby.js, the same as /api/v1/nearby)
//   POST device {token, platform, app_version}   this phone gets notifications for the account's home and choices
//   POST device {token, platform, off: true}      this phone stops getting them
//   POST logout {token?}                  ends this session; with this phone's push token, the phone stops getting alerts
//   POST delete_account                   deletes the person, their home, choices, sessions and send log
//   GET/POST emails?t=                    the "change or stop these emails" page linked from every email, and RFC 8058
//                                         one-click unsubscribe (signed token, no sign-in needed)
// Signed-in POSTs from a browser need the X-BCM-Account: 1 header and a same-site Origin; the apps send
// Authorization: Bearer <token> instead. Sessions are stored as hashes, so signing out ends them everywhere.
const crypto = require('crypto');
const {q, hasDb} = require('./_db');
const {derive, ipOf} = require('./_gate');
const {FROM, resend, sameOrigin} = require('./_alerts');
const N = require('./_nearby');

const SITE = 'https://baycounty.me';
const COOKIE = 'bcm_user', FLAG = 'bcm_in';
const SESSION_DAYS = {web: 60, ios: 365, android: 365};
const CODE_MIN = 15, CODE_TRIES = 5;
const PUSH_TOPICS = ['weather', 'evacuation', 'shelters', 'water', 'roads', 'agenda'];
const ALERT_EMAIL = ['evacuation', 'water', 'weather', 'shelters'];
const bad = (msg, status = 400) => Object.assign(new Error(msg), {status, expose: true});
const key = () => process.env.RESEND_FULL_KEY || process.env.RESEND_API_KEY;

/* ---------- tokens ---------- */
const b64 = s => Buffer.from(s).toString('base64url');
const sign = s => crypto.createHmac('sha256', derive('bcm-account-v1')).update(s).digest('base64url');
function makeToken(obj) { const body = b64(JSON.stringify(obj)); return body + '.' + sign(body); }
function readToken(tok) {
  const [body, sig] = String(tok || '').split('.');
  if (!body || !sig || !process.env.ALERTS_SECRET) return null;
  const want = sign(body);
  if (want.length !== sig.length || !crypto.timingSafeEqual(Buffer.from(want), Buffer.from(sig))) return null;
  try { const p = JSON.parse(Buffer.from(body, 'base64url').toString()); return !p.exp || p.exp > Date.now() ? p : null; } catch (e) { return null; }
}
const hashCode = (email, code) => crypto.createHmac('sha256', derive('bcm-account-code-v1')).update(`${email}|${code}`).digest('hex');
const hashSession = t => crypto.createHash('sha256').update(String(t)).digest('hex');
const newCode = () => String(crypto.randomInt(0, 1e6)).padStart(6, '0');
// The "change or stop these emails" link in every account email. It doesn't expire; it only reaches the email settings.
const manageUrl = userId => `${SITE}/api/account?action=emails&t=${encodeURIComponent(makeToken({kind: 'emails', u: userId}))}`;

const cookies = req => Object.fromEntries(String(req.headers.cookie || '').split(';').map(c => c.trim().split('=')).filter(x => x[0]).map(([k, ...v]) => [k, decodeURIComponent(v.join('='))]));
// bcm_in is readable by page scripts so the header can say "My home" without asking the server; it holds no secret.
function sessionCookies(token, days = SESSION_DAYS.web) {
  const age = token ? days * 86400 : 0;
  return [`${COOKIE}=${token || ''}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${age}`, `${FLAG}=${token ? 1 : ''}; Path=/; Secure; SameSite=Lax; Max-Age=${age}`];
}
function setSession(res, token, days) { res.setHeader('Set-Cookie', sessionCookies(token, days)); }
// Pages a one-tap sign-in link may return to. The realtor console uses this same sign-in (one account for both).
const NEXT = ['/account', '/realtor'];
const nextOf = v => (NEXT.includes(v) ? v : '/account');

/* ---------- validation ---------- */
const EMAIL = /^[^\s@<>"]{1,64}@[^\s@<>"]{1,190}\.[a-z]{2,24}$/i;
const text = (v, n) => { const s = String(v ?? '').replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim(); return s ? s.slice(0, n) : null; };
const pickList = (v, allowed) => [...new Set((Array.isArray(v) ? v : String(v || '').split(',')).map(x => String(x).trim()).filter(x => allowed.includes(x)))];
function cleanPrefs(b, cur = {}) {
  const out = {};
  if (b.weekly_email !== undefined) out.weekly_email = b.weekly_email === true || b.weekly_email === 'true' || b.weekly_email === 1 || b.weekly_email === '1' || b.weekly_email === 'on';
  if (b.alert_email !== undefined) out.alert_email = pickList(b.alert_email, ALERT_EMAIL);
  if (b.push_topics !== undefined) out.push_topics = pickList(b.push_topics, PUSH_TOPICS);
  if (b.topics !== undefined) out.topics = pickList(b.topics, N.ALL_TOPICS);
  if (b.radius_mi !== undefined) { const r = Number(b.radius_mi); if (!N.RADII.includes(r)) throw bad('Pick one of the distances on the list.'); out.radius_mi = r; }
  return {...cur, ...out};
}

/* ---------- data ---------- */
const PREF_COLS = ['weekly_email', 'alert_email', 'push_topics', 'radius_mi', 'topics'];
const HOME_COLS = ['label', 'address', 'city', 'zip', 'parcel_id', 'lat', 'lon', 'gov_id', 'zone', 'updated_at'];
async function session(req) {
  const auth = String(req.headers.authorization || '');
  const bearer = /^Bearer\s+([A-Za-z0-9_-]{30,100})$/.exec(auth);
  const tok = bearer ? bearer[1] : cookies(req)[COOKIE];
  if (!tok || !/^[A-Za-z0-9_-]{30,100}$/.test(tok)) return null;
  const [r] = await q(`update account.sessions s set last_seen = now() from account.users u
      where s.token_hash = $1 and s.expires_at > now() and u.id = s.user_id and u.status = 'active' returning u.*, s.client, s.token_hash`, [hashSession(tok)]);
  return r ? {...r, via: bearer ? 'bearer' : 'cookie'} : null;
}
async function startSession(userId, client) {
  const tok = crypto.randomBytes(32).toString('base64url');
  await q(`insert into account.sessions (token_hash, user_id, client, expires_at) values ($1, $2, $3, now() + make_interval(days => $4))`, [hashSession(tok), userId, client, SESSION_DAYS[client]]);
  await q('update account.users set last_login_at = now(), login_count = login_count + 1 where id = $1', [userId]);
  return tok;
}
async function signInUser(email) {
  const [u] = await q(`insert into account.users (email) values ($1) on conflict (email) do update set email = excluded.email returning *`, [email]);
  if (u.status !== 'active') throw bad('This account is paused. Write to hello@baycounty.me.', 403);
  await q('insert into account.prefs (user_id) values ($1) on conflict (user_id) do nothing', [u.id]);
  return u;
}
async function me(u) {
  const [home] = await q(`select ${HOME_COLS.join(', ')} from account.homes where user_id = $1`, [u.id]);
  const [prefs] = await q(`select ${PREF_COLS.join(', ')} from account.prefs where user_id = $1`, [u.id]);
  const [{devices}] = await q('select count(*)::int as devices from push.devices where user_id = $1 and disabled_at is null', [u.id]);
  // The same email on the realtor console's agent list (api/_realtor.js): one sign-in opens both.
  const realtor = await q('select status from realtor.agents where email = $1', [u.email]).then(r => (r[0] ? r[0].status : null), () => null);
  return {user: {email: u.email, first_name: u.first_name, created_at: u.created_at, place_id: u.place_id}, realtor,
    home: home ? {...home, lat: +home.lat, lon: +home.lon} : null, prefs: prefs ? {...prefs, radius_mi: +prefs.radius_mi} : null, devices,
    choices: {topics: N.TOPICS, radius_mi: N.RADII, push_topics: require('./_emergency').TOPICS, alert_email: Object.fromEntries(ALERT_EMAIL.map(k => [k, require('./_emergency').TOPICS[k]]))}};
}
// Signed-in phones follow the account: its home point (rounded to about 100 m, as /api/push stores it), zone and choices.
async function syncDevices(userId) {
  await q(`update push.devices d set topics = p.push_topics, radius_mi = p.radius_mi,
      lat = round(h.lat::numeric, 3), lng = round(h.lon::numeric, 3), zone = h.zone,
      govs = case when h.gov_id is null then '{}'::text[] else array['county', h.gov_id] end
    from account.prefs p left join account.homes h on h.user_id = p.user_id
    where d.user_id = $1 and p.user_id = $1`, [userId]);
}

/* ---------- the feed for the saved home ---------- */
async function homeFeed(req, home, prefs) {
  const {loadFile, datasetRows} = require('./_data');
  const catalog = await loadFile(req, '/downloads/index.json');
  const rowsOf = async id => { const m = catalog.datasets.find(d => d.id === id); return m ? (await datasetRows(req, m)).rows : null; };
  const loc = {place_id: home.place_id || 'fl-bay', place: home.place_id || 'fl-bay', lat: +home.lat, lon: +home.lon, city: home.city, zip: home.zip, gov_id: home.gov_id, zone: home.zone};
  const f = await N.feed(loc, {radius_mi: prefs ? +prefs.radius_mi : 1, topics: prefs ? prefs.topics : N.ALL_TOPICS}, {catalog, rowsOf, live: N.liveSources(req, catalog, loc)});
  return {...f, home: {label: home.label, address: home.address, city: home.city, zip: home.zip, zone: home.zone, gov_id: home.gov_id}};
}

/* ---------- pages ---------- */
const escH = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
function page(title, inner) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>${escH(title)} · BayCounty.me</title><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600&display=swap"><link rel="stylesheet" href="/assets/site.css">
<style>body{display:block}.b{max-width:440px;margin:12vh auto 0;padding:24px;background:var(--surface);border:1px solid var(--line);border-radius:16px}h1{font:600 1.2rem var(--f-display);margin:0 0 8px}p{color:var(--muted);margin:0 0 16px}
label{display:flex;gap:10px;align-items:center;margin:0 0 10px}form{margin:0 0 12px}button,a.btn{display:inline-flex;min-height:44px;align-items:center;padding:0 20px;border-radius:10px;border:0;background:var(--navy);color:#fff;font:500 .95rem var(--f-body);cursor:pointer;text-decoration:none}button.plain{background:none;color:var(--ink);border:1px solid var(--line)}.note{background:var(--surface-2,#eef3fa);padding:10px 12px;border-radius:10px;color:var(--ink)}</style></head>
<body><div class="b">${inner}</div></body></html>`;
}
function linkPage(ok, email, tok, next = '/account') {
  return page('Sign in', ok ? `<h1>Sign in to BayCounty.me</h1><p>Signing in as ${escH(email)}.</p>
<form method="post" action="/api/account?action=link"><input type="hidden" name="t" value="${escH(tok)}"><button type="submit" autofocus>Sign in</button></form>`
    : `<h1>This link has expired</h1><p>Sign-in links last ${CODE_MIN} minutes and work once.</p><a class="btn" href="${escH(nextOf(next))}">Get a new code</a>`);
}
function emailsPage(tok, u, p, msg) {
  if (!u) return page('Your emails', '<h1>That link isn’t valid any more</h1><p>Sign in to change your emails.</p><a class="btn" href="/account">Sign in</a>');
  const t = escH(tok);
  return page('Your emails', `<h1>Your BayCounty.me emails</h1><p>For ${escH(u.email)}</p>${msg ? `<p class="note">${escH(msg)}</p>` : ''}
<form method="post" action="/api/account?action=emails"><input type="hidden" name="t" value="${t}"><input type="hidden" name="do" value="save">
<label><input type="checkbox" name="weekly_email" value="on"${p && p.weekly_email ? ' checked' : ''}> Monday email about my home</label>
<label><input type="checkbox" name="alerts" value="on"${p && p.alert_email && p.alert_email.length ? ' checked' : ''}> Emails when an emergency affects my home</label>
<button type="submit">Save</button></form>
<form method="post" action="/api/account?action=emails"><input type="hidden" name="t" value="${t}"><input type="hidden" name="do" value="stop"><button type="submit" class="plain">Stop all account emails</button></form>
<p style="margin-top:16px"><a href="/account">Open My home</a> to change your home or phone notifications.</p>`);
}

/* ---------- handler ---------- */
const hits = new Map();
function limit(k, n, ms) { const now = Date.now(); const r = (hits.get(k) || []).filter(t => now - t < ms); r.push(now); hits.set(k, r); if (hits.size > 5000) hits.clear(); return r.length > n; }
const body = req => (typeof req.body === 'string' ? (() => { try { return JSON.parse(req.body || '{}'); } catch (e) { return Object.fromEntries(new URLSearchParams(req.body)); } })() : req.body || {});

async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('X-Robots-Tag', 'noindex');
  const action = String((req.query || {}).action || '');
  const html = (code, s) => { res.setHeader('Content-Type', 'text/html; charset=utf-8'); res.setHeader('Referrer-Policy', 'no-referrer'); return res.status(code).send(s); };
  if (!process.env.ALERTS_SECRET || !hasDb()) return res.status(503).json({error: 'Accounts aren’t set up on this deployment yet.'});
  try {
    if (action === 'start' && req.method === 'POST') {
      const b = body(req);
      if (!b.client || b.client === 'web') { if (!sameOrigin(req)) throw bad('Sign in from baycounty.me.', 403); }
      if (limit('ip:' + ipOf(req), 8, 600e3)) throw bad('Too many tries. Wait a few minutes and try again.', 429);
      const email = String(b.email || '').trim().toLowerCase();
      if (!EMAIL.test(email)) throw bad('Enter a valid email address.');
      const [{n}] = await q(`select count(*)::int as n from account.codes where email = $1 and created_at > now() - interval '10 minutes'`, [email]);
      if (n < 3) {
        const code = newCode(), nonce = crypto.randomBytes(9).toString('base64url');
        await q(`insert into account.codes (email, code_hash, nonce, expires_at) values ($1, $2, $3, now() + make_interval(mins => $4))`, [email, hashCode(email, code), nonce, CODE_MIN]);
        const next = nextOf(b.next);
        const link = `${SITE}/api/account?action=link&t=${encodeURIComponent(makeToken({kind: 'link', e: email, n: nonce, exp: Date.now() + CODE_MIN * 60e3, ...(next === '/account' ? {} : {r: next})}))}`;
        const m = require('./_emails').accountCodeEmail(code, link, CODE_MIN);
        const r = await resend('/emails', 'POST', {from: FROM, to: [email], subject: m.subject, text: m.text, html: m.html}, key());
        if (!r.ok) console.error('account code email', r.status);
      }
      return res.status(200).json({ok: true, message: `We sent a 6-digit code to ${email}. It works for ${CODE_MIN} minutes.`});
    }
    if (action === 'verify' && req.method === 'POST') {
      const b = body(req);
      const client = ['ios', 'android'].includes(b.client) ? b.client : 'web';
      if (client === 'web' && !sameOrigin(req)) throw bad('Sign in from baycounty.me.', 403);
      if (limit('v:' + ipOf(req), 20, 600e3)) throw bad('Too many tries. Wait a few minutes and try again.', 429);
      const email = String(b.email || '').trim().toLowerCase(), code = String(b.code || '').replace(/\D/g, '');
      if (!EMAIL.test(email) || code.length !== 6) throw bad('Enter the 6-digit code from the email.');
      const [c] = await q(`update account.codes set attempts = attempts + 1 where id = (select id from account.codes where email = $1 and used_at is null and expires_at > now()
          order by created_at desc limit 1) and attempts < $2 returning id, code_hash`, [email, CODE_TRIES]);
      const want = c ? Buffer.from(c.code_hash) : null, got = Buffer.from(hashCode(email, code));
      if (!c || want.length !== got.length || !crypto.timingSafeEqual(want, got)) throw bad('That code didn’t match, or it has expired. Check the newest email, or send a new code.');
      const used = await q('update account.codes set used_at = now() where id = $1 and used_at is null returning id', [c.id]);
      if (!used.length) throw bad('That code was already used. Send a new code.');
      const u = await signInUser(email);
      const tok = await startSession(u.id, client);
      if (client === 'web') setSession(res, tok, SESSION_DAYS.web);
      return res.status(200).json({ok: true, ...(client === 'web' ? {} : {token: tok}), ...(await me(u))});
    }
    if (action === 'link' && req.method === 'GET') {
      if (!req.query.t && req.query['amp;t']) req.query.t = req.query['amp;t'];
      const t = readToken(req.query.t);
      return html(200, linkPage(!!(t && t.kind === 'link'), t && t.e, String(req.query.t || '').replace(/[^A-Za-z0-9._-]/g, ''), t && t.r));
    }
    if (action === 'link' && req.method === 'POST') {
      const t = readToken(body(req).t);
      const next = nextOf(t && t.r);
      const fail = () => { res.setHeader('Location', next + '?signin=expired'); return res.status(303).end(); };
      if (!t || t.kind !== 'link') return fail();
      const used = await q('update account.codes set used_at = now() where nonce = $1 and email = $2 and used_at is null and expires_at > now() returning id', [t.n, t.e]);
      if (!used.length) return fail();
      const u = await signInUser(t.e);
      setSession(res, await startSession(u.id, 'web'), SESSION_DAYS.web);
      res.setHeader('Location', next); return res.status(303).end();
    }
    if (action === 'emails') {
      // From the footer of an account email: signed token, no sign-in. One-click unsubscribe (RFC 8058) stops both kinds.
      const b = req.method === 'POST' ? body(req) : {};
      const t = readToken(req.query.t || b.t);
      const u = t && t.kind === 'emails' ? (await q('select * from account.users where id = $1', [t.u]))[0] : null;
      if (req.method === 'POST' && b['List-Unsubscribe'] === 'One-Click') {
        if (!u) return res.status(400).json({ok: false});
        await q(`update account.prefs set weekly_email = false, alert_email = '{}', updated_at = now() where user_id = $1`, [u.id]);
        return res.status(200).json({ok: true, unsubscribed: true});
      }
      let msg = null;
      if (req.method === 'POST' && u) {
        if (!sameOrigin(req)) return html(403, page('Not allowed', '<h1>Not allowed</h1><p>Please use the form on BayCounty.me.</p>'));
        if (b.do === 'stop') { await q(`update account.prefs set weekly_email = false, alert_email = '{}', updated_at = now() where user_id = $1`, [u.id]); msg = 'Done. Your account won’t send you any more emails. Sign-in codes still come when you ask for one.'; }
        else { await q(`update account.prefs set weekly_email = $2, alert_email = case when $3 then array['evacuation', 'water'] else '{}'::text[] end, updated_at = now() where user_id = $1`, [u.id, b.weekly_email === 'on', b.alerts === 'on']); msg = 'Saved.'; }
      }
      const [p] = u ? await q('select weekly_email, alert_email from account.prefs where user_id = $1', [u.id]) : [];
      return html(200, emailsPage(String(req.query.t || b.t || '').replace(/[^A-Za-z0-9._-]/g, ''), u, p, msg));
    }
    if (action === 'logout') {
      const u = await session(req);
      if (u) await q('delete from account.sessions where token_hash = $1', [u.token_hash]);
      // Alerts need a signed-in phone, so signing out turns this phone's alerts off.
      const token = String(body(req).token || '').trim();
      if (u && token) await q('delete from push.devices where token = $1 and user_id = $2', [token, u.id]);
      setSession(res, '', 0);
      return res.status(200).json({ok: true});
    }

    const u = await session(req);
    if (!u) { if (cookies(req)[FLAG]) setSession(res, '', 0); return res.status(401).json({error: 'Sign in first.'}); }
    if (req.method === 'GET' && action === 'me') return res.status(200).json(await me(u));
    if (req.method === 'GET' && action === 'feed') {
      const [home] = await q('select * from account.homes where user_id = $1', [u.id]);
      if (!home) return res.status(200).json({home: null, note: 'Save your home address first.'});
      const [prefs] = await q(`select ${PREF_COLS.join(', ')} from account.prefs where user_id = $1`, [u.id]);
      return res.status(200).json(await homeFeed(req, home, prefs));
    }
    if (req.method !== 'POST') throw bad('Use POST.', 405);
    if (u.via === 'cookie' && (req.headers['x-bcm-account'] !== '1' || !sameOrigin(req))) throw bad('That request didn’t come from BayCounty.me.', 403);
    const b = body(req);
    if (action === 'profile') {
      await q('update account.users set first_name = $2 where id = $1', [u.id, text(b.first_name, 60)]);
      return res.status(200).json(await me({...u, first_name: text(b.first_name, 60)}));
    }
    if (action === 'home') {
      if (limit('h:' + u.id, 20, 3600e3)) throw bad('Too many changes. Try again in a while.', 429);
      const hasPt = b.lat != null && b.lon != null && b.lat !== '' && b.lon !== '';
      if (!hasPt && !text(b.address, 160)) throw bad('Type your street address, like 825 Ohio Ave.');
      const loc = await N.resolve(hasPt ? {lat: Number(b.lat), lon: Number(b.lon), label: text(b.address, 160), parcel: text(b.parcel_id, 30)} : {address: text(b.address, 160)});
      const address = loc.address || text(b.address, 160);
      if (!address) throw bad('Type your street address, like 825 Ohio Ave.');
      await q(`insert into account.homes (user_id, place_id, label, address, city, zip, parcel_id, lat, lon, gov_id, zone, updated_at) values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, now())
          on conflict (user_id) do update set place_id = excluded.place_id, label = excluded.label, address = excluded.address, city = excluded.city, zip = excluded.zip,
            parcel_id = excluded.parcel_id, lat = excluded.lat, lon = excluded.lon, gov_id = excluded.gov_id, zone = excluded.zone, updated_at = now()`,
      [u.id, loc.place || 'fl-bay', text(b.label, 40) || 'Home', address, loc.city || text(b.city, 80), loc.zip || text(b.zip, 10), loc.parcel_id || null, loc.lat, loc.lon, loc.gov_id || 'county', loc.zone || null]);
      await syncDevices(u.id);
      return res.status(200).json({...(await me(u)), other_matches: loc.other_matches || []});
    }
    if (action === 'home_delete') { await q('delete from account.homes where user_id = $1', [u.id]); await q(`update push.devices set lat = null, lng = null, zone = null where user_id = $1`, [u.id]); return res.status(200).json(await me(u)); }
    if (action === 'prefs') {
      const [cur] = await q(`select ${PREF_COLS.join(', ')} from account.prefs where user_id = $1`, [u.id]);
      const p = cleanPrefs(b, cur || {});
      await q(`insert into account.prefs (user_id, weekly_email, alert_email, push_topics, radius_mi, topics, updated_at) values ($1, $2, $3, $4, $5, $6, now())
          on conflict (user_id) do update set weekly_email = excluded.weekly_email, alert_email = excluded.alert_email, push_topics = excluded.push_topics,
            radius_mi = excluded.radius_mi, topics = excluded.topics, updated_at = now()`,
      [u.id, p.weekly_email ?? true, p.alert_email || [], p.push_topics || [], p.radius_mi || 1, p.topics || N.ALL_TOPICS]);
      await syncDevices(u.id);
      return res.status(200).json(await me(u));
    }
    if (action === 'test_push') {
      // A test notification to this account's own phones only, so a person can check alerts reach them.
      if (limit('tp:' + u.id, 5, 3600e3)) throw bad('That’s enough tests for now. Try again in an hour.', 429);
      const P = require('./_push');
      const devices = await q('select token, platform from push.devices where user_id = $1 and disabled_at is null', [u.id]);
      if (!devices.length) throw bad('No phones are signed in yet. Sign in to the BayCounty.me app and turn on alerts in My home settings.');
      const r = await P.send(devices, {title: 'Test alert · BayCounty.me', body: 'This is a test. Real alerts for your home will look like this.', topic: 'test',
        notice_id: 'test', url: 'https://baycounty.me/account', critical: false});
      if (r.dead.length) await q('update push.devices set disabled_at = now() where token = any($1::text[])', [r.dead]);
      if (r.failed) console.error('test push', JSON.stringify(r.reasons));
      return res.status(200).json({ok: r.delivered > 0, phones: devices.length, delivered: r.delivered, failed: r.failed, skipped: r.skipped, reasons: [...new Set(r.reasons)]});
    }
    if (action === 'device') {
      const platform = b.platform === 'android' ? 'android' : b.platform === 'ios' ? 'ios' : null;
      const token = String(b.token || '').trim();
      if (!platform || !({ios: /^[0-9a-f]{64,200}$/i, android: /^[\w:.-]{100,400}$/})[platform].test(token)) throw bad('A valid device token and platform are required.');
      if (b.off === true) {
        await q('delete from push.devices where token = $1 and user_id = $2', [token, u.id]);
        return res.status(200).json({ok: true, removed: true});
      }
      await q(`insert into push.devices (token, platform, place_id, app_version, user_id) values ($1, $2, $3, $4, $5)
          on conflict (token) do update set platform = excluded.platform, app_version = excluded.app_version, user_id = excluded.user_id, last_seen = now(), failures = 0, disabled_at = null`,
      [token, platform, u.place_id || 'fl-bay', text(b.app_version, 40), u.id]);
      await syncDevices(u.id);
      return res.status(200).json({ok: true, sending: require('./_push').ready()[platform]});
    }
    if (action === 'delete_account') {
      await q('delete from push.devices where user_id = $1', [u.id]);
      await q('delete from account.codes where email = $1', [u.email]);
      await q('delete from account.users where id = $1', [u.id]);
      setSession(res, '', 0);
      return res.status(200).json({ok: true, deleted: true});
    }
    throw bad('Unknown action.', 404);
  } catch (e) {
    if (!e.expose) console.error('account', action, e);
    return res.status(e.status || 500).json({error: e.expose ? e.message : 'Something went wrong. Please try again.'});
  }
}

/* ---------- emails sent by the scheduled runs ---------- */
// Monday: one "Your home this week" email per account with weekly_email on and a saved home. Each week is sent once
// (account.sends). opts.only: an email address, to send a single test copy. Returns counts only.
async function weeklyRun(req, {only = null, now = new Date(), dry = false, budgetMs = 50e3} = {}) {
  const t0 = Date.now();
  if (!hasDb()) return {skipped: 'no database'};
  const week = N.localDay(now);
  const rows = await q(`select u.id, u.email, u.first_name, h.*, p.radius_mi, p.topics from account.users u join account.homes h on h.user_id = u.id join account.prefs p on p.user_id = u.id
      where u.status = 'active' and ${only ? 'u.email = $1' : `p.weekly_email and not exists (select 1 from account.sends s where s.user_id = u.id and s.kind = 'weekly' and s.dedupe_key = $1)`}
      order by u.created_at limit 2000`, [only || week]);
  const out = {week, accounts: rows.length, sent: 0, empty: 0, failed: 0, left: 0};
  for (const [i, r] of rows.entries()) {
    // Stop before the function's time limit; the second Monday run (an hour later) picks up whoever is left.
    if (Date.now() - t0 > budgetMs) { out.left = rows.length - i; break; }
    try {
      const f = await homeFeed(req, r, r);
      const m = require('./_emails').homeWeeklyEmail(f, {home: r, name: r.first_name, manage: manageUrl(r.id)});
      if (!m) { out.empty++; continue; }
      if (dry) { out.sent++; continue; }
      if (!only) {
        const claimed = await q(`insert into account.sends (user_id, kind, dedupe_key, items) values ($1, 'weekly', $2, $3) on conflict do nothing returning id`, [r.id, week, m.items]);
        if (!claimed.length) continue;
      }
      const s = await resend('/emails', 'POST', {from: FROM, to: [r.email], subject: m.subject, html: m.html, text: m.text,
        headers: {'List-Unsubscribe': `<${manageUrl(r.id)}>`, 'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'}}, key());
      if (s.ok) { out.sent++; if (!only) await q(`update account.sends set resend_id = $3 where user_id = $1 and kind = 'weekly' and dedupe_key = $2`, [r.id, week, s.body && s.body.id]); }
      else out.failed++;
    } catch (e) { out.failed++; console.error('account weekly', e.message); }
  }
  return out;
}

// An emergency notice was just pushed (api/_emergency_run.js): email the accounts whose home it reaches and who asked
// for that topic by email. Same matching as the My home alerts list.
async function emailNotice(place, n, topic) {
  if (!hasDb() || !ALERT_EMAIL.includes(topic)) return {sent: 0};
  const rows = await q(`select u.id, u.email, h.address, h.zone, h.gov_id, h.label from account.users u join account.homes h on h.user_id = u.id join account.prefs p on p.user_id = u.id
      where u.status = 'active' and h.place_id = $1 and $2 = any(p.alert_email)`, [place, topic]);
  let sent = 0;
  for (const r of rows) {
    if (!N.assemble({notices: [{...n, status: 'active'}]}, {lat: 30.2, lon: -85.6, gov_id: r.gov_id, zone: r.zone}, {topics: []}).sections[0].items.length) continue;
    const claimed = await q(`insert into account.sends (user_id, kind, dedupe_key) values ($1, 'alert', $2) on conflict do nothing returning id`, [r.id, n.notice_id]);
    if (!claimed.length) continue;
    const m = require('./_emails').homeAlertEmail({...n, topic}, {home: r, manage: manageUrl(r.id)});
    const s = await resend('/emails', 'POST', {from: FROM, to: [r.email], subject: m.subject, html: m.html, text: m.text,
      headers: {'List-Unsubscribe': `<${manageUrl(r.id)}>`, 'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'}}, key()).catch(() => ({ok: false}));
    if (s.ok) sent++;
  }
  return {sent};
}

/* ---------- admin (counts only) ---------- */
async function adminSummary() {
  const [c] = await q(`select (select count(*)::int from account.users) as accounts, (select count(*)::int from account.homes) as homes,
      (select count(*)::int from account.prefs where weekly_email) as weekly, (select count(*)::int from push.devices where user_id is not null and disabled_at is null) as phones,
      (select count(*)::int from account.users where created_at > now() - interval '7 days') as new_7d`);
  const byGov = await q('select coalesce(gov_id, \'county\') as gov_id, count(*)::int as homes from account.homes group by 1 order by 2 desc');
  return {...c, homes_by_government: byGov};
}

module.exports = handler;
Object.assign(module.exports, {session, signInUser, startSession, sessionCookies, nextOf, SESSION_DAYS, makeToken, readToken, hashCode, hashSession, cleanPrefs, manageUrl, weeklyRun, emailNotice, adminSummary, homeFeed, COOKIE, PUSH_TOPICS, ALERT_EMAIL});
