// Government workspace (/staff): sign-in, roles and everything staff can do. Used by api/gov.js; tables in
// migration 0088 (schema gov). Files starting with _ are not routes.
//
// What staff can and can't change (Jeremy, 2026-10-30: "I don't want them editing numbers that were pulled from records"):
//  * Their own posts (notices, events, jobs): written into the public tables with origin = 'gov'. Only rows with
//    origin = 'gov' and their own gov_id can be edited or withdrawn; every update and delete says so in its WHERE.
//  * Emergency alerts: written to gov.alerts, sent through the emergency hub's own push and email path.
//  * Record data (budgets, officials, rates, projects, anything the site read from a public record): read-only.
//    The only action is a flag (gov.flags), which BayCounty.me checks against the source and answers in /admin.
const crypto = require('crypto');
const {session: adminSession, admins} = require('./_session');

// records: a finance or clerk contact who sends records (Send records tab) and reads everything else, nothing more.
// official: an elected commissioner or council member (migration 0096). Reads only, like a viewer, and opens on their
// own dashboard (api/_official.js): agendas, their votes and the numbers. Tied to their seat by person_id.
const ROLES = {viewer: 1, auditor: 1, records: 1, official: 1, publisher: 2, alert_sender: 3, owner: 4};
const CAN = {read: 1, submit: 2, publish: 2, alert: 3, manage: 4};
const ROLE_LABEL = {owner: 'Owner', alert_sender: 'Alert sender', publisher: 'Publisher', records: 'Records sender', viewer: 'Viewer', auditor: 'Auditor', official: 'Elected official'};
// Sending records: the records role, or publisher and up.
const allowed = (role, need) => (ROLES[role] || 0) >= CAN[need] || (need === 'submit' && role === 'records');
const COOKIE = 'bcm_gov';
const SESSION_DAYS = 14;
const CODE_MINUTES = 10;
const MAX_ATTEMPTS = 5;
const COUNTYWIDE = 'All of Bay County';

const bad = (msg, status = 400) => Object.assign(new Error(msg), {status});
const sha = s => crypto.createHash('sha256').update(s).digest('hex');
const secret = () => process.env.GOV_HASH_SECRET || process.env.ALERTS_SECRET || 'baycounty.me-gov';
const codeHash = (email, code) => crypto.createHmac('sha256', secret()).update(`gov-login|${email}|${code}`).digest('hex');
const normEmail = e => String(e || '').trim().toLowerCase();
const validEmail = e => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e) && e.length <= 254;
const txt = (v, n = 300) => { const s = String(v ?? '').replace(/\r\n/g, '\n').trim(); return s ? s.slice(0, n) : null; };
const day = v => { const s = String(v || '').slice(0, 10); return /^\d{4}-\d{2}-\d{2}$/.test(s) && !isNaN(Date.parse(s)) ? s : null; };
const stamp = v => { const s = String(v || '').slice(0, 16); return /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?$/.test(s) && !isNaN(Date.parse(s.length === 10 ? s : s + ':00Z')) ? s : null; };
const link = v => { const s = txt(v, 500); if (!s) return null; if (!/^https:\/\/[^\s<>"]+$/i.test(s)) throw bad('Links must start with https://'); return s; };

// A map of where an alert or notice applies: pins with a radius, street or pipe lines, and drawn areas, as a GeoJSON
// FeatureCollection. Points must be in or near Bay County. Returns compact JSON text, or null for no map.
const BOX = {w: -86.2, e: -84.9, s: 29.6, n: 30.7};
const SHAPES = {Point: 'pin', LineString: 'line', Polygon: 'area'};
function areaShape(v) {
  if (v == null || v === '') return null;
  let g = v;
  if (typeof g === 'string') { if (g.length > 200000) throw bad('That map is too detailed. Use fewer points.'); try { g = JSON.parse(g); } catch (e) { throw bad('The map could not be read. Clear it and draw it again.'); } }
  if (!g || g.type !== 'FeatureCollection' || !Array.isArray(g.features)) throw bad('The map could not be read. Clear it and draw it again.');
  if (!g.features.length) return null;
  if (g.features.length > 20) throw bad('A map can hold up to 20 pins, lines and areas.');
  const pt = c => {
    if (!Array.isArray(c) || c.length < 2) throw bad('The map could not be read. Clear it and draw it again.');
    const [x, y] = c.map(Number);
    if (!(x >= BOX.w && x <= BOX.e && y >= BOX.s && y <= BOX.n)) throw bad('Every point on the map has to be in Bay County.');
    return [Math.round(x * 1e6) / 1e6, Math.round(y * 1e6) / 1e6];
  };
  const features = g.features.map(f => {
    const geo = f && f.geometry, kind = geo && SHAPES[geo.type];
    if (!kind) throw bad('Maps can have pins, lines and areas only.');
    if (kind === 'pin') {
      const r = Math.round(Number(f.properties && f.properties.radius_m) || 0);
      return {type: 'Feature', properties: r ? {radius_m: Math.min(Math.max(r, 25), 8000)} : {}, geometry: {type: 'Point', coordinates: pt(geo.coordinates)}};
    }
    if (kind === 'line') {
      const c = (geo.coordinates || []).map(pt);
      if (c.length < 2 || c.length > 500) throw bad('A line needs between 2 and 500 points.');
      return {type: 'Feature', properties: {}, geometry: {type: 'LineString', coordinates: c}};
    }
    const ring = ((geo.coordinates || [])[0] || []).map(pt);
    if (ring.length >= 3 && (ring[0][0] !== ring[ring.length - 1][0] || ring[0][1] !== ring[ring.length - 1][1])) ring.push(ring[0]);
    if (ring.length < 4 || ring.length > 501) throw bad('An area needs at least 3 corners (and no more than 500).');
    return {type: 'Feature', properties: {}, geometry: {type: 'Polygon', coordinates: [ring]}};
  });
  return JSON.stringify({type: 'FeatureCollection', features});
}

function cookieValue(req, name) {
  for (const part of String((req.headers || {}).cookie || '').split(';')) {
    const [k, ...v] = part.trim().split('=');
    if (k === name) return decodeURIComponent(v.join('='));
  }
  return null;
}
const setCookie = (res, val, maxAge) => res.setHeader('Set-Cookie', `${COOKIE}=${val}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`);

/* ---------- who is calling ---------- */
// A workspace session (cookie bcm_gov, or "Bearer bcmg_..." for an app) or the BayCounty.me admin cookie. Cookie
// requests that change anything must send X-BCM-Gov: 1 (or X-BCM-Admin: 1), so another site can't act for a browser.
async function caller(req, q) {
  const h = req.headers || {}, auth = String(h.authorization || '');
  const unsafe = req.method !== 'GET' && req.method !== 'HEAD';
  const fromToken = async tok => {
    const rows = await q(`update gov.sessions set last_seen_at = now() where token_hash = $1 and revoked_at is null and expires_at > now() returning email`, [sha(tok)]);
    if (!rows.length) return null;
    const email = normEmail(rows[0].email);
    // A BayCounty.me admin (ADMIN_EMAILS) signed in with an emailed code, e.g. in the staff app: owner everywhere.
    return {email, via: 'session', token: tok, ...(admins().includes(email) ? {admin: true} : {})};
  };
  if (/^Bearer\s+bcmg_\S+/i.test(auth)) return fromToken(auth.replace(/^Bearer\s+/i, '').trim());
  const csrf = unsafe && h['x-bcm-gov'] !== '1' && h['x-bcm-admin'] !== '1';
  const c = cookieValue(req, COOKIE);
  if (c && c.startsWith('bcmg_')) {
    const u = await fromToken(c);
    if (u) return csrf ? {...u, csrf: true} : u;
  }
  const s = adminSession(req);
  if (!s) return null;
  return {email: normEmail(s.e), via: 'admin', admin: true, ...(csrf ? {csrf: true} : {})};
}

// The workspaces a caller can open. A BayCounty.me admin sees every one, as owner.
async function workspacesFor(q, who) {
  if (who.admin) return (await q('select id, name, modules, countywide from gov.workspaces order by countywide desc, name')).map(w => ({...w, role: 'owner', person_id: null}));
  return q(`select w.id, w.name, w.modules, w.countywide, m.role, m.person_id from gov.members m join gov.workspaces w on w.id = m.workspace_id
            where lower(m.email) = $1 order by w.countywide desc, w.name`, [who.email]);
}

// The caller's role in a workspace, or a thrown 401/403/404.
async function requireRole(q, who, ws, need) {
  if (!who) throw bad('Sign in first.', 401);
  if (who.csrf) throw bad('Missing X-BCM-Gov header.', 403);
  if (!/^[a-z0-9_-]{1,40}$/.test(String(ws || ''))) throw bad('Choose a workspace.');
  const [w] = await q('select id, name, place_id, modules, countywide from gov.workspaces where id = $1', [ws]);
  if (!w) throw bad('There’s no workspace for that government.', 404);
  let role = 'owner', personId = null;
  if (!who.admin) {
    const [m] = await q('select role, person_id from gov.members where workspace_id = $1 and lower(email) = $2', [ws, who.email]);
    if (!m) throw bad('You don’t have access to this workspace.', 404);
    role = m.role; personId = m.person_id || null;
  }
  if (!allowed(role, need)) {
    const want = {publish: 'publisher', submit: 'records sender', alert: 'alert sender', manage: 'owner'}[need] || 'viewer';
    throw bad(`This needs ${want} access. Ask your workspace owner.`, 403);
  }
  return {role, workspace: w, person_id: personId};
}

const log = (q, ws, email, action, detail = {}) =>
  q('insert into gov.activity (workspace_id, email, action, detail) values ($1, $2, $3, $4)', [ws, email, action, JSON.stringify(detail)]).catch(e => console.error('gov log', e.message));

/* ---------- email-code sign-in ---------- */
const hits = new Map();
function ipLimited(req) {
  const ip = String((req.headers || {})['x-real-ip'] || (req.headers || {})['x-forwarded-for'] || 'unknown').split(',')[0].trim();
  const now = Date.now(), recent = (hits.get(ip) || []).filter(t => now - t < 600e3);
  recent.push(now); hits.set(ip, recent);
  if (hits.size > 5000) hits.delete(hits.keys().next().value);
  return {limited: recent.length > 10, ipHash: sha('ip|' + ip).slice(0, 24)};
}

function codeEmail(code) {
  const ui = require('./_email_ui');
  const subject = `${code} is your BayCounty.me sign-in code`;
  const text = `Your BayCounty.me government workspace sign-in code is ${code}\n\nIt works once and expires in ${CODE_MINUTES} minutes. If you didn't ask for it, ignore this email.`;
  const html = ui.layout({title: subject, preheader: `It works once and expires in ${CODE_MINUTES} minutes.`, kicker: 'Government workspace',
    hero: {tone: 'teal', icon: 'lock', eyebrow: 'Government workspace', title: 'Your sign-in code'},
    body: ui.p('Enter this code on the sign-in page:') + ui.code(code) +
      ui.small(`It works once and expires in ${CODE_MINUTES} minutes. If you didn’t ask for it, ignore this email.`),
    footer: 'You’re getting this because someone asked to sign in to the BayCounty.me government workspace with this address.'});
  return {subject, text, html};
}

// Always answers the same way, so the form can't be used to find out who has access.
async function startLogin(q, req, body, sendEmail) {
  const email = normEmail(body.email), same = {ok: true, message: 'If that address has access, a 6-digit code is on its way.'};
  if (!validEmail(email)) throw bad('Enter your email address.');
  const {limited, ipHash} = ipLimited(req);
  if (limited) throw bad('Too many sign-in attempts. Try again in a few minutes.', 429);
  const [m] = await q('select 1 from gov.members where lower(email) = $1 limit 1', [email]);
  if (!m && !admins().includes(email)) return same;
  const [{n}] = await q(`select count(*)::int n from gov.login_codes where lower(email) = $1 and created_at > now() - interval '15 minutes'`, [email]);
  if (n >= 3) return same;
  const code = String(crypto.randomInt(0, 1e6)).padStart(6, '0');
  await q(`insert into gov.login_codes (email, code_hash, expires_at, ip_hash) values ($1, $2, now() + make_interval(mins => $3), $4)`,
    [email, codeHash(email, code), CODE_MINUTES, ipHash]);
  await q(`delete from gov.login_codes where created_at < now() - interval '1 day'`).catch(() => {});
  await sendEmail(email, codeEmail(code));
  return same;
}

async function finishLogin(q, req, res, body) {
  const email = normEmail(body.email), code = String(body.code || '').replace(/\D/g, '');
  const fail = msg => bad(msg || 'That code isn’t right. Check the newest email, or ask for a new code.');
  if (!validEmail(email) || code.length !== 6) throw fail('Enter the 6-digit code from the email.');
  if (ipLimited(req).limited) throw bad('Too many sign-in attempts. Try again in a few minutes.', 429);
  const [c] = await q(`select id, code_hash, attempts from gov.login_codes where lower(email) = $1 and used_at is null and expires_at > now()
                       order by created_at desc limit 1`, [email]);
  if (!c || c.attempts >= MAX_ATTEMPTS) throw fail('That code was already used or has expired. Send a new code.');
  const want = Buffer.from(c.code_hash), got = Buffer.from(codeHash(email, code));
  if (want.length !== got.length || !crypto.timingSafeEqual(want, got)) {
    await q('update gov.login_codes set attempts = attempts + 1 where id = $1', [c.id]);
    throw fail();
  }
  const used = await q('update gov.login_codes set used_at = now() where id = $1 and used_at is null returning id', [c.id]);
  if (!used.length) throw fail('That code has already been used. Ask for a new one.');
  const token = 'bcmg_' + crypto.randomBytes(32).toString('base64url');
  await q(`insert into gov.sessions (email, token_hash, user_agent, expires_at) values ($1, $2, $3, now() + make_interval(days => $4))`,
    [email, sha(token), String((req.headers || {})['user-agent'] || '').slice(0, 200) || null, SESSION_DAYS]);
  await q(`delete from gov.sessions where expires_at < now() - interval '30 days'`).catch(() => {});
  setCookie(res, token, SESSION_DAYS * 86400);
  for (const w of await q('select workspace_id from gov.members where lower(email) = $1', [email])) await log(q, w.workspace_id, email, 'signed_in');
  return {ok: true, email, expires_in_days: SESSION_DAYS, ...(body.client === 'app' ? {token} : {})};
}

async function logout(q, res, who) {
  if (who && who.token) await q('update gov.sessions set revoked_at = now() where token_hash = $1', [sha(who.token)]);
  setCookie(res, '', 0);
  return {ok: true};
}

/* ---------- posts: notices, events, jobs ---------- */
// Each kind is a public table the site already shows. fields: what staff fill in; row(): the table's columns.
const NOTICE_KINDS = {meeting: 'Public meeting', hearing: 'Public hearing or ordinance', bid: 'Bid or proposal request', utility: 'Water, sewer or utility work', road: 'Road or street work', other: 'Other notice'};
const JOB_TYPES = ['Full time', 'Part time', 'Seasonal', 'Temporary', 'Volunteer'];
const POSTS = {
  notice: {table: 'public_notices', id: 'notice_id', order: 'published desc nulls last', dateCol: 'published',
    clean: b => {
      // The request's own `kind` names the post kind ("notice"), so the notice type comes as notice_kind.
      const nk = b.notice_kind != null ? b.notice_kind : b.kind;
      const kind = NOTICE_KINDS[nk] ? nk : 'other';
      const title = txt(b.title, 200), text = txt(b.text, 20000);
      if (!title) throw bad('Give the notice a title.');
      if (!text) throw bad('Paste the notice text.');
      return {kind, kind_label: NOTICE_KINDS[kind], title, text, event_date: day(b.event_date), published: day(b.published) || new Date().toISOString().slice(0, 10),
        pdf_url: link(b.pdf_url), notice_type: 'Posted by government staff', geometry: areaShape(b.geometry)};
    },
    row: (c, w) => ({...c, agency: w.name, source_url: c.pdf_url || null}),
    show: ['title', 'kind', 'kind_label', 'published', 'event_date', 'text', 'pdf_url', 'geometry']},
  event: {table: 'community_events', id: 'event_id', order: 'starts desc nulls last', dateCol: 'starts',
    clean: b => {
      const title = txt(b.title, 200), starts = stamp(b.starts);
      if (!title) throw bad('Give the event a name.');
      if (!starts) throw bad('Pick the date the event starts.');
      const ends = stamp(b.ends);
      if (ends && ends < starts) throw bad('The event can’t end before it starts.');
      return {title, starts, ends, all_day: starts.length === 10, venue: txt(b.venue, 200), cost: txt(b.cost, 80), url: link(b.url),
        category: b.category === 'Public meeting' ? 'Public meeting' : 'Community'};
    },
    row: (c, w) => ({...c, source: w.name, source_id: 'gov-' + w.id, gov: w.id, town: w.name.replace(/^City of /, ''), recurring: false, source_url: c.url || null}),
    show: ['title', 'starts', 'ends', 'venue', 'category', 'cost', 'url']},
  job: {table: 'job_openings', id: 'job_id', order: 'posted desc nulls last', dateCol: 'posted',
    clean: b => {
      const title = txt(b.title, 200), url = link(b.url);
      if (!title) throw bad('Give the job a title.');
      if (!url) throw bad('Add the link where people apply.');
      return {title, url, department: txt(b.department, 200), job_type: JOB_TYPES.includes(b.job_type) ? b.job_type : null, pay: txt(b.pay, 120),
        posted: day(b.posted) || new Date().toISOString().slice(0, 10), closes: day(b.closes)};
    },
    row: (c, w) => ({...c, board: w.id, employer: w.name, first_seen: c.posted, source_url: c.url}),
    show: ['title', 'department', 'job_type', 'pay', 'posted', 'closes', 'url']},
};
const postKind = k => { const p = POSTS[k]; if (!p) throw bad('Post kind must be notice, event or job.'); return p; };

async function listPosts(q, w, kind) {
  const p = postKind(kind);
  const cols = ['id', p.id, ...p.show, 'created_at', 'updated_at'].map(c => `"${c}"`).join(', ');
  // Ours: editable. Theirs from records: shown so staff can see what's already on the site, never editable.
  const mine = await q(`select ${cols} from ${p.table} where origin = 'gov' and gov_id = $1 order by ${p.order} limit 200`, [w.id]);
  const read = await q(`select ${cols} from ${p.table} where origin <> 'gov' and gov_id = $1 order by ${p.order} limit 50`, [w.id]).catch(() => []);
  return {kind, posts: mine.map(r => ({...r, editable: true})), from_records: read.map(r => ({...r, editable: false}))};
}

async function savePost(q, w, kind, b, email) {
  const p = postKind(kind), clean = p.clean(b || {});
  const id = b && b.id != null ? Number(b.id) : null;
  if (id) {
    const row = p.row(clean, w), cols = Object.keys(row);
    const r = await q(`update ${p.table} set ${cols.map((c, i) => `"${c}" = $${i + 3}`).join(', ')}, updated_at = now()
                       where id = $1 and origin = 'gov' and gov_id = $2 returning id`, [id, w.id, ...cols.map(c => row[c])]);
    if (!r.length) throw bad('Only posts made in this workspace can be changed. Data from public records can only be flagged.', 403);
    await log(q, w.id, email, `${kind}_edited`, {id, title: clean.title});
    return {ok: true, id};
  }
  const key = `gov-${w.id}-${crypto.randomBytes(6).toString('hex')}`;
  const row = {...p.row(clean, w), [p.id]: key, place_id: w.place_id};
  const cols = Object.keys(row);
  const [gk] = await q('select key from governments where key = $1', [w.id]).catch(() => []);
  const r = await q(`insert into ${p.table} (${cols.map(c => `"${c}"`).join(', ')}, gov_id, government_key, origin, record_hash)
                     values (${cols.map((_, i) => `$${i + 1}`).join(', ')}, $${cols.length + 1}, $${cols.length + 2}, 'gov', $${cols.length + 3}) returning id`,
  [...cols.map(c => row[c]), w.id, gk ? gk.key : null, key]);
  await log(q, w.id, email, `${kind}_posted`, {id: r[0].id, title: clean.title});
  return {ok: true, id: r[0].id};
}

async function withdrawPost(q, w, kind, id, email) {
  const p = postKind(kind);
  const r = await q(`delete from ${p.table} where id = $1 and origin = 'gov' and gov_id = $2 returning title`, [Number(id), w.id]);
  if (!r.length) throw bad('Only posts made in this workspace can be withdrawn.', 403);
  await log(q, w.id, email, `${kind}_withdrawn`, {id: Number(id), title: r[0].title});
  return {ok: true};
}

/* ---------- emergency alerts ---------- */
const ALERT_KINDS = {
  evacuation: 'Evacuation order', shelter: 'Shelter open', 'boil-water': 'Boil-water notice', road: 'Road fully closed',
  safety: 'Public safety (police, fire, hazmat)', general: 'General update (closures, sandbags, debris)',
};
const SEVERITIES = ['extreme', 'severe', 'moderate', 'minor', 'info'];
const ALERT_COLS = `id, workspace_id, kind, title, message, instruction, severity, countywide, geometry, status, created_by, created_at, confirmed_by, sent_at, ends_at, ended_by, ended_at`;

// Countywide alerts need a second person (another alert sender or owner of a countywide workspace, or a BayCounty.me
// admin). Alerts for one city go out at once.
async function createAlert(q, w, b, email, {admin = false} = {}) {
  const kind = ALERT_KINDS[b.kind] ? b.kind : null;
  if (!kind) throw bad('Pick what kind of alert this is.');
  const title = txt(b.title, 140), message = txt(b.message, 900);
  if (!title) throw bad('Give the alert a short headline.');
  if (!message) throw bad('Write what is happening.');
  const countywide = Boolean(b.countywide);
  if (countywide && !w.countywide) throw bad('This workspace can only send alerts to its own city.', 403);
  const hours = Math.min(Math.max(Number(b.hours) || 24, 1), 24 * 14);
  const needsConfirm = countywide && !admin;
  const geometry = areaShape(b.geometry);
  const [a] = await q(`insert into gov.alerts (workspace_id, place_id, kind, title, message, instruction, severity, countywide, status, created_by, sent_at, ends_at, geometry)
      values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, now() + make_interval(hours => $12), $13) returning ${ALERT_COLS}`,
  [w.id, w.place_id, kind, title, message, txt(b.instruction, 900), SEVERITIES.includes(b.severity) ? b.severity : 'severe', countywide,
    needsConfirm ? 'pending' : 'sent', email, needsConfirm ? null : new Date().toISOString(), hours, geometry]);
  await log(q, w.id, email, needsConfirm ? 'alert_drafted' : 'alert_sent', {id: a.id, title, countywide});
  return a;
}

async function confirmAlert(q, w, id, email) {
  const [a] = await q(`update gov.alerts set status = 'sent', confirmed_by = $3, sent_at = now(),
                         ends_at = now() + (ends_at - created_at)
                       where id = $1 and workspace_id = $2 and status = 'pending' and lower(created_by) <> $3 returning ${ALERT_COLS}`, [Number(id), w.id, email]);
  if (!a) {
    const [x] = await q('select status, created_by from gov.alerts where id = $1 and workspace_id = $2', [Number(id), w.id]);
    if (x && x.status === 'pending' && normEmail(x.created_by) === email) throw bad('A second person has to confirm a countywide alert.', 403);
    throw bad('That alert isn’t waiting for confirmation.', 409);
  }
  await log(q, w.id, email, 'alert_confirmed', {id: a.id, title: a.title});
  return a;
}

async function endAlert(q, w, id, email) {
  const [a] = await q(`update gov.alerts set status = case when status = 'pending' then 'cancelled' else 'ended' end, ended_by = $3, ended_at = now()
                       where id = $1 and workspace_id = $2 and status in ('pending', 'sent') returning ${ALERT_COLS}`, [Number(id), w.id, email]);
  if (!a) throw bad('That alert has already ended.', 409);
  await log(q, w.id, email, a.status === 'cancelled' ? 'alert_cancelled' : 'alert_ended', {id: a.id, title: a.title});
  return a;
}

// How many residents an alert could reach right now, by channel (phones with the topic on, accounts with alert email on).
const TOPIC_OF = {evacuation: 'evacuation', shelter: 'shelters', 'boil-water': 'water', road: 'roads', safety: 'safety', general: 'general'};
async function reach(q, w, kind, countywide) {
  const topic = TOPIC_OF[kind];
  if (!topic) return {topic: null, phones: 0, emails: 0, note: 'This kind of alert shows on the public alert timeline only.'};
  const gov = countywide ? null : w.id;
  const [p] = await q(`select count(*)::int n from push.devices where place_id = $1 and disabled_at is null and user_id is not null and topics && $2::text[]
      and ($3::text is null or cardinality(govs) = 0 or $3 = any(govs))`, [w.place_id, require('./_emergency').topicsFor(topic), gov]).catch(() => [{n: null}]);
  const [e] = await q(`select count(distinct u.id)::int n from account.users u join account.homes h on h.user_id = u.id join account.prefs p on p.user_id = u.id
      where u.status = 'active' and h.place_id = $1 and p.alert_email && $2::text[] and ($3::text is null or h.gov_id = $3)`, [w.place_id, require('./_emergency').topicsFor(topic), gov]).catch(() => [{n: null}]);
  return {topic, phones: p.n, emails: e.n};
}

// The live staff alerts as emergency-hub notices (api/_emergency.js readAll calls this every check). Every active one,
// every time, so the hub ends an alert as soon as it is ended here or runs out.
async function liveNotices(q, place) {
  const rows = await q(`select a.*, w.name gov_name from gov.alerts a left join gov.workspaces w on w.id = a.workspace_id
      where a.place_id = $1 and a.status = 'sent' and (a.ends_at is null or a.ends_at > now()) order by a.sent_at desc limit 50`, [place]);
  return rows.map(a => ({
    notice_id: 'staff:' + a.id, place_id: place, kind: a.kind, source: a.gov_name || 'BayCounty.me', source_type: 'staff', gov_id: a.workspace_id || null,
    title: a.title, summary: a.message, instruction: a.instruction, severity: a.severity, event: ALERT_KINDS[a.kind],
    area: a.countywide ? COUNTYWIDE : (a.gov_name || null), zones: [], issued: new Date(a.sent_at).toISOString(), starts: new Date(a.sent_at).toISOString(),
    ends: a.ends_at ? new Date(a.ends_at).toISOString() : null, updated: new Date(a.sent_at).toISOString(), status: 'active',
    full_closure: a.kind === 'road' ? true : null, roadway: null, url: 'https://baycounty.me/emergency', source_url: 'https://baycounty.me/emergency',
    geometry: a.geometry || null,
  }));
}

/* ---------- record data: read-only, flag only ---------- */
// Datasets that hold a government's own record data. Staff see their rows; they can't change them.
const RECORDS = {
  'budget-years': 'Budget by year', 'officeholder-terms': 'Who held each seat', 'people-directory': 'Officials and staff',
  'utility-rates': 'Utility rates', 'trash-pickup': 'Trash and recycling pickup', 'parks': 'Parks', 'development-projects': 'Development projects',
  'public-notices': 'Public notices (from the notice website)', 'job-openings': 'Job openings (from your job board)', 'community-events': 'Events (from your calendar)',
};
const HIDDEN = ['government_key', 'origin', 'ingest_run_id', 'record_hash', 'created_at', 'updated_at', 'place_id', 'same_as', 'first_posted'];

async function records(q, w, dataset) {
  if (!RECORDS[dataset]) throw bad('Pick one of your record datasets.');
  const table = dataset.replace(/-/g, '_');
  const rows = await q(`select to_jsonb(t) - $2::text[] as r from ${table} t where t.gov_id = $1 and t.origin <> 'gov' order by t.id limit 500`, [w.id, HIDDEN]).catch(() => []);
  return {dataset, title: RECORDS[dataset], read_only: true, rows: rows.map(x => x.r),
    note: 'These come from public records, so they can’t be changed here. If something is wrong, flag it with the right value and where it comes from; we check it against the source.'};
}

async function addFlag(q, w, b, email) {
  if (!RECORDS[b.dataset] && b.dataset !== 'other') throw bad('Say which data the flag is about.');
  const correct = txt(b.correct_value, 500), note = txt(b.note, 2000);
  if (!correct && !note) throw bad('Say what the right value is, or what’s wrong.');
  const [f] = await q(`insert into gov.flags (workspace_id, email, dataset, record_key, record_label, field, shown_value, correct_value, evidence_url, note)
      values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) returning id, status, created_at`,
  [w.id, email, b.dataset, txt(b.record_key, 120), txt(b.record_label, 300), txt(b.field, 80), txt(b.shown_value, 500), correct, link(b.evidence_url), note]);
  await log(q, w.id, email, 'data_flagged', {id: f.id, dataset: b.dataset, field: txt(b.field, 80)});
  return {ok: true, ...f};
}

/* ---------- public: what staff posted (GET /api/v1/government-posts) ---------- */
// Public rows (they are in the public tables); the notices, events and jobs pages add these to what they read from
// records, so a post shows on the site as soon as it is saved, not at the next build.
async function publicPosts(q, query = {}) {
  const gov = /^[a-z0-9_-]{1,40}$/.test(String(query.gov || '')) ? String(query.gov) : null;
  const kinds = String(query.kind || 'notice,event,job').split(',').filter(k => POSTS[k]);
  if (!kinds.length) throw Object.assign(new Error('kind must be notice, event or job (comma list).'), {status: 400, expose: true});
  const today = new Date().toISOString().slice(0, 10), out = {};
  for (const k of kinds) {
    const p = POSTS[k];
    const cols = ['id', p.id, 'gov_id', ...p.show, 'updated_at'].map(c => `"${c}"`).join(', ');
    const when = k === 'event' ? `and coalesce(ends, starts) >= $2` : k === 'job' ? `and (closes is null or closes >= $2)` : `and coalesce(event_date, published) >= to_char(($2::date - 30), 'YYYY-MM-DD')`;
    out[k === 'notice' ? 'notices' : k + 's'] = await q(`select ${cols}, (select name from gov.workspaces w where w.id = t.gov_id) posted_by from ${p.table} t
        where origin = 'gov' and ($1::text is null or gov_id = $1) ${when} order by ${p.order} limit 100`, [gov, today]);
  }
  return {data: out, note: 'Posted by city and county staff in the BayCounty.me government workspace. Rows also appear in the public-notices, community-events and job-openings datasets (origin gov).'};
}

// An official member's name from their seat on record (SQL, for member lists aliased m).
const PERSON_NAME = `(select t.person_name from officeholder_terms t where t.person_id = m.person_id and t.gov_id = m.workspace_id limit 1)`;

// Who holds a seat now (officeholder-terms), to pick from when giving an official access. One government, or all.
async function seatsNow(q, ws = null) {
  return q(`select gov_id, person_id, person_name, seat, body from officeholder_terms
      where person_id is not null and not coalesce(vacant, false) and (end_date is null or end_date >= to_char(now(), 'YYYY-MM-DD'))
        and ($1::text is null or gov_id = $1) order by gov_id, seat_order, person_name`, [ws]).catch(e => { if (e.code === '42P01') return []; throw e; });
}

/* ---------- admin side (api/admin.js) ---------- */
async function adminOverview(q) {
  const workspaces = await q(`select w.id, w.name, w.modules, w.countywide,
      (select count(*)::int from gov.members m where m.workspace_id = w.id) members,
      (select max(at) from gov.activity a where a.workspace_id = w.id) last_activity,
      (select count(*)::int from gov.alerts a where a.workspace_id = w.id and a.status = 'sent' and (a.ends_at is null or a.ends_at > now())) live_alerts
    from gov.workspaces w order by w.countywide desc, w.name`);
  const members = await q(`select m.workspace_id, m.email, m.role, m.person_id, ${PERSON_NAME} person_name, m.added_by, m.created_at from gov.members m order by m.workspace_id, m.role, m.email`);
  return {workspaces, members, roles: ROLE_LABEL, officials: await seatsNow(q)};
}

// The owner's home in the staff app: every workspace with what needs attention, plus totals.
async function ownerOverview(q) {
  const workspaces = await q(`select w.id, w.name, w.countywide,
      (select count(*)::int from gov.members m where m.workspace_id = w.id) members,
      (select max(at) from gov.activity a where a.workspace_id = w.id) last_activity,
      (select count(*)::int from gov.alerts a where a.workspace_id = w.id and a.status = 'sent' and (a.ends_at is null or a.ends_at > now())) live_alerts,
      (select count(*)::int from gov.alerts a where a.workspace_id = w.id and a.status = 'pending') waiting_alerts,
      (select count(*)::int from gov.flags f where f.workspace_id = w.id and f.status = 'open') open_flags,
      (select count(*)::int from public_notices n where n.origin = 'gov' and n.gov_id = w.id) notices
    from gov.workspaces w order by w.countywide desc, w.name`);
  const sum = k => workspaces.reduce((n, w) => n + (w[k] || 0), 0);
  const activity = await q(`select a.workspace_id, w.name gov_name, a.email, a.action, a.detail, a.at from gov.activity a
      join gov.workspaces w on w.id = a.workspace_id order by a.at desc limit 25`);
  return {totals: {workspaces: workspaces.length, members: sum('members'), live_alerts: sum('live_alerts'), waiting_alerts: sum('waiting_alerts'),
    open_flags: sum('open_flags'), notices: sum('notices')}, workspaces, activity};
}

async function adminFlags(q, status = 'open') {
  const st = ['open', 'fixed', 'not_changed', 'all'].includes(status) ? status : 'open';
  return {flags: await q(`select f.*, w.name gov_name from gov.flags f join gov.workspaces w on w.id = f.workspace_id
      where ($1 = 'all' or f.status = $1) order by f.created_at desc limit 300`, [st])};
}

async function adminFlagReview(q, b, email) {
  if (!['fixed', 'not_changed', 'open'].includes(b.status)) throw bad('Status must be fixed, not_changed or open.');
  const [f] = await q(`update gov.flags set status = $2, reply = $3, reviewed_by = $4, reviewed_at = now() where id = $1 returning id, workspace_id, status`,
    [Number(b.id), b.status, txt(b.reply, 2000), email]);
  if (!f) throw bad('No such flag.', 404);
  await log(q, f.workspace_id, email, 'flag_answered', {id: f.id, status: f.status});
  return {ok: true};
}

async function setMember(q, ws, b, by) {
  const email = normEmail(b.email), role = String(b.role || '');
  if (!validEmail(email)) throw bad('Enter an email address.');
  if (role === 'remove') {
    await q('delete from gov.members where workspace_id = $1 and lower(email) = $2 and lower(email) <> $3', [ws, email, by]);
    await log(q, ws, by, 'member_removed', {email});
    return {ok: true};
  }
  if (!(role in ROLES)) throw bad(`Role must be one of ${Object.keys(ROLES).join(', ')}, or remove.`);
  // An official is tied to their seat on record, so their dashboard shows their own votes.
  let person = null;
  if (role === 'official') {
    person = txt(b.person_id, 120);
    if (!person) throw bad('Pick which official this is.');
    const [t] = await q('select person_name from officeholder_terms where gov_id = $1 and person_id = $2 limit 1', [ws, person]).catch(() => []);
    if (!t) throw bad('That person doesn’t hold a seat on this government on record.');
  }
  await q(`insert into gov.members (workspace_id, email, role, person_id, added_by) values ($1, $2, $3, $4, $5)
           on conflict (workspace_id, email) do update set role = excluded.role, person_id = excluded.person_id`, [ws, email, role, person, by]);
  await log(q, ws, by, 'member_set', {email, role, ...(person ? {person_id: person} : {})});
  return {ok: true};
}

module.exports = {ROLES, CAN, ROLE_LABEL, COOKIE, COUNTYWIDE, NOTICE_KINDS, JOB_TYPES, ALERT_KINDS, RECORDS, POSTS, TOPIC_OF,
  caller, workspacesFor, requireRole, log, startLogin, finishLogin, logout, codeEmail,
  areaShape, listPosts, savePost, withdrawPost, createAlert, confirmAlert, endAlert, reach, liveNotices, records, addFlag, publicPosts,
  adminOverview, ownerOverview, adminFlags, adminFlagReview, setMember, PERSON_NAME, seatsNow};
