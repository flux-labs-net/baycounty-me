// BayCounty.me admin: API keys, throttles, request logs, analytics, ingestion health and email previews. Used by /admin.
// Sign-in is by emailed link to an address listed in ADMIN_EMAILS (comma-separated, set in Vercel).
// The session is a signed, HttpOnly, SameSite=Strict cookie; changes also need the X-BCM-Admin header.
const crypto = require('crypto');
const {q, hasDb} = require('./_db');
const {sha256, derive, ipOf} = require('./_gate');
const {FROM, GOVS, resend} = require('./_alerts');
const {adminSignInEmail} = require('./_emails');
const {preview, PREVIEWS} = require('./_previews');

const SITE = 'https://baycounty.me';
const {COOKIE, SESSION_HOURS, admins, makeToken, readToken, session, setCookie} = require('./_session');

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

// An IPv4/IPv6 address, optionally with a /prefix in range. Checked before Postgres sees it, so bad input is a 400, not a 500.
const net = require('net');
function validNet(s) {
  const m = String(s).match(/^([0-9a-fA-F:.]+)(?:\/(\d{1,3}))?$/);
  if (!m) return false;
  const v = net.isIP(m[1]);
  if (!v) return false;
  return m[2] === undefined || Number(m[2]) <= (v === 4 ? 32 : 128);
}
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Which requests a stats/logs query covers: one key, keyless traffic, or everything.
function scope(k, params) {
  if (!k || k === 'all') return () => '';
  if (k === 'anon') return a => ` and ${a}key_id is null`;
  if (!UUID.test(String(k))) throw Object.assign(new Error('Unknown key filter.'), {status: 400});
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
  let body = {};
  if (req.method === 'POST') {
    try { body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : req.body || {}; }
    catch (e) { throw Object.assign(new Error('The request body isn\u2019t valid JSON.'), {status: 400}); }
  }
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
      if (Q.before) {
        if (!/^\d{1,18}$/.test(String(Q.before))) throw Object.assign(new Error('"before" must be a log id (a whole number).'), {status: 400});
        p.push(String(Q.before)); w += ` and r.id < $${p.length}::bigint`;
      }
      if (Q.status === 'errors') w += ' and r.status >= 400';
      if (Q.ip) {
        const ip = String(Q.ip).trim();
        if (!validNet(ip)) throw Object.assign(new Error('Enter an IP address or range, e.g. 203.0.113.7 or 203.0.113.0/24.'), {status: 400});
        p.push(ip); w += ` and r.ip <<= $${p.length}::inet`;
      }
      const rows = await q(`select r.id, r.at, r.key_id, k.name key_name, k.prefix, r.surface, r.endpoint, r.dataset, r.query, r.status, r.rows_returned, r.ms, r.ip_hash, host(r.ip) ip, r.user_agent
          from apiadmin.requests r left join apiadmin.keys k on k.id = r.key_id where ${w} order by r.id desc limit ${lim}`, p);
      return {logs: rows, next_before: rows.length === lim ? rows[rows.length - 1].id : null};
    }
    case 'blocks': {
      if (req.method === 'POST') {
        const network = String(body.network || '').trim();
        if (!validNet(network)) throw Object.assign(new Error('Enter an IP address or range, e.g. 203.0.113.7 or 203.0.113.0/24.'), {status: 400});
        let row;
        try {
          [row] = await q(`insert into apiadmin.blocks (network, reason, expires_at, created_by) values ($1::cidr, $2, $3, $4)
              on conflict (network) do update set reason = excluded.reason, expires_at = excluded.expires_at returning id, network::text network`,
            [network, txt(body.reason, 300) || null, body.expires_at ? new Date(body.expires_at).toISOString() : null, me.e]);
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
    case 'summary': return require('./_summary').summary();
    case 'ingestion': return require('./_health').report();
    // ---------- accounting-system files (ingest schema) ----------
    case 'ledger': return require('./_ledger').report({status: String(Q.status || 'pending'), source: String(Q.source || ''), raw: String(Q.raw || '')});
    case 'ledger_normalize': case 'ledger_approve': case 'ledger_reject': case 'ledger_source': case 'ledger_finance': {
      if (req.method !== 'POST') throw Object.assign(new Error('Use POST.'), {status: 405});
      const L = require('./_ledger');
      const r = action === 'ledger_normalize' ? await L.normalize(body)
        : action === 'ledger_finance' ? await L.toFinance(body)
        : action === 'ledger_source' ? await L.updateSource(body)
        : await L.review(action === 'ledger_approve' ? 'approved' : 'rejected', body, me.e);
      await audit(me.e, action, null, action === 'ledger_normalize' ? {raw_id: body.raw_id || null, all: !!body.all, processed: r.processed}
        : action === 'ledger_finance' ? {raw_id: body.raw_id, workspace: r.workspace, upload_id: r.upload_id}
        : action === 'ledger_source' ? {source: body.id, auto_normalize: body.auto_normalize, active: body.active, senders: 'allowed_senders' in body ? r.allowed_senders.length : undefined}
        : {raw_id: body.raw_id || null, rows: r.changed, note: body.note || null}).catch(() => {});
      return r;
    }
    case 'agendas': return require('./_agendas').report({days: parseInt(Q.days || '14', 10) || 14, board: String(Q.board || '').slice(0, 40), status: String(Q.status || '').slice(0, 20)});
    case 'sent': return require('./_sent').list({days: Math.min(Math.max(parseInt(Q.days || '7', 10) || 7, 1), 90),
      domain: Q.domain === undefined ? 'baycounty.me' : String(Q.domain).slice(0, 100), status: String(Q.status || '').slice(0, 30), q: String(Q.q || '').slice(0, 100)});
    case 'sent_detail': return require('./_sent').detail(String(Q.id || ''));
    case 'agenda_items': return require('./_agendas').items(parseInt(Q.id, 10) || 0);
    case 'agenda_file': return require('./_agendas').fileLink(parseInt(Q.id, 10) || 0);
    case 'agenda_resolve': {
      if (req.method !== 'POST') throw Object.assign(new Error('Use POST.'), {status: 405});
      const r = await require('./_agendas').resolveError(parseInt(body.id, 10) || 0, !!body.all);
      await audit(me.e, 'agenda_resolve', null, {id: body.id || null, all: !!body.all, resolved: r.resolved});
      return r;
    }
    case 'agenda_run': {
      if (req.method !== 'POST') throw Object.assign(new Error('Use POST.'), {status: 405});
      const r = await require('./_agendas').runNow(String(body.mode || 'both'), String(body.only || ''));
      await audit(me.e, 'agenda_run', null, {mode: body.mode || 'both', only: body.only || ''});
      return r;
    }
    // ---------- correspondence with officials ----------
    case 'registry': return require('./_registry').groups({county: Q.county, status: String(Q.status || ''), candidate: String(Q.candidate || '')});
    case 'registry_limits': return require('./_registry').limits({county: Q.county, status: String(Q.status || '')});
    case 'registry_search': return require('./_registry').search(Q.county, Q.q);
    case 'registry_person': return require('./_registry').person(Q.county, Q.key);
    case 'registry_entity': return require('./_registry').entity(Q.county, Q.doc);
    case 'registry_review': {
      if (req.method !== 'POST') throw Object.assign(new Error('Use POST.'), {status: 405});
      const r = await require('./_registry').review(body, me.e);
      await audit(me.e, action, null, {status: body.status, n: r.updated, groups: r.rows.map(x => x.group_id + '|' + x.candidate)});
      return r;
    }
    case 'registry_limit_review': {
      if (req.method !== 'POST') throw Object.assign(new Error('Use POST.'), {status: 405});
      const r = await require('./_registry').reviewLimit(body, me.e);
      await audit(me.e, action, null, {status: body.status, resolution: body.resolution || null, n: r.updated, cases: r.rows.map(x => x.case_id)});
      return r;
    }
    case 'boards': return require('./_boards').officials({county: Q.county, status: String(Q.status || '')});
    case 'boards_interlocks': return require('./_boards').interlocks(Q.county, Q.min);
    case 'boards_donors': return require('./_boards').donors(Q.county);
    case 'boards_search': return require('./_boards').search(Q.county, Q.q);
    case 'boards_person': return require('./_boards').person(Q.county, Q.key);
    case 'boards_nonprofit': return require('./_boards').nonprofit(Q.county, Q.id);
    case 'boards_review': {
      if (req.method !== 'POST') throw Object.assign(new Error('Use POST.'), {status: 405});
      const r = await require('./_boards').review(body, me.e);
      await audit(me.e, action, null, {status: body.status, n: r.updated, matches: r.rows.map(x => x.board_key + '|' + x.official_id)});
      return r;
    }
    case 'minutes': return require('./_minutes').report({queue: String(Q.queue || 'flagged'), board: String(Q.board || ''), year: String(Q.year || ''),
      status: Q.status == null ? 'unreviewed' : String(Q.status), q: String(Q.q || '')});
    case 'import_progress': return require('./_minutes').progress();
    case 'minutes_review': {
      if (req.method !== 'POST') throw Object.assign(new Error('Use POST.'), {status: 405});
      const r = await require('./_minutes').review(body, me.e);
      await audit(me.e, action, null, {status: body.status, n: r.updated, motions: r.rows.map(x => x.id)});
      return r;
    }
    case 'realtors': return require('./_realtor').adminList();
    case 'realtor_set': {
      if (req.method !== 'POST') throw Object.assign(new Error('Use POST.'), {status: 405});
      const r = await require('./_realtor').adminSet(body);
      await audit(me.e, action, null, r);
      return r;
    }
    case 'names': return require('./_name_matches').list({status: Q.status == null ? 'unreviewed' : String(Q.status), reason: String(Q.reason || ''), q: String(Q.q || ''), kind: String(Q.kind || 'name')});
    case 'names_review': {
      if (req.method !== 'POST') throw Object.assign(new Error('Use POST.'), {status: 405});
      const r = await require('./_name_matches').review(body, me.e);
      await audit(me.e, action, null, {status: body.status, n: r.updated, pairs: r.rows.map(x => x.a_key + '|' + x.b_key)});
      return r;
    }
    case 'careers': return require('./_careers').matches({county: Q.county, status: String(Q.status || ''), confidence: String(Q.confidence || ''), q: String(Q.q || '')});
    case 'careers_review': {
      if (req.method !== 'POST') throw Object.assign(new Error('Use POST.'), {status: 405});
      const r = await require('./_careers').review(body, me.e);
      await audit(me.e, action, null, {status: body.status, n: r.updated, pairs: r.rows.map(x => x.person_id + '|' + x.person_key)});
      return r;
    }
    case 'corr_contacts': return require('./_correspondence').contacts();
    case 'corr_contact': case 'corr_seed': case 'corr_send': case 'corr_reply': case 'corr_publish': case 'corr_status': case 'corr_assign': case 'corr_dismiss': {
      if (req.method !== 'POST') throw Object.assign(new Error('Use POST.'), {status: 405});
      const C = require('./_correspondence');
      const fn = {corr_contact: C.saveContact, corr_seed: C.seed, corr_send: C.send, corr_reply: C.reply, corr_publish: C.publish,
        corr_status: C.setStatus, corr_assign: C.assign, corr_dismiss: C.dismiss}[action];
      const r = await fn(body, me.e);
      await audit(me.e, action, null, action === 'corr_send' ? {subject: body.subject, recipients: (body.ids || []).length, test: !!body.test, batch: r.batch_id || null}
        : {id: body.id || body.thread_id || body.message_id || body.batch || null}).catch(() => {});
      return r;
    }
    case 'corr_threads': return require('./_correspondence').threads({status: String(Q.status || '').slice(0, 20), government: String(Q.government || '').slice(0, 120),
      published: String(Q.published || ''), q: String(Q.q || '').slice(0, 100), year: String(Q.year || '')});
    case 'corr_thread': return require('./_correspondence').thread(Q.id);
    case 'rr_list': return require('./_records_requests').list();
    case 'rr_seed': case 'rr_save': case 'rr_send': {
      if (req.method !== 'POST') throw Object.assign(new Error('Use POST.'), {status: 405});
      const R = require('./_records_requests');
      const r = await {rr_seed: R.seed, rr_save: R.save, rr_send: R.send}[action](body, me.e);
      await audit(me.e, action, null, {id: body.id || null, test: !!body.test, status: body.status || null}).catch(() => {});
      return r;
    }
    case 'email_previews': return {templates: PREVIEWS, govs: Object.entries(GOVS).map(([key, [name]]) => ({key, name}))};
    case 'email_preview': return preview(String(Q.template || ''), {gov: Q.gov, source: Q.source});
    case 'email_test': {
      if (req.method !== 'POST') throw Object.assign(new Error('Use POST.'), {status: 405});
      // Sends the previewed email to the signed-in admin only, never to anyone else.
      const m = await preview(String(body.template || ''), {gov: body.gov, source: body.source});
      if (!m.html && !m.text) throw Object.assign(new Error(m.note || 'Nothing to send.'), {status: 400});
      const key = process.env.RESEND_FULL_KEY || process.env.RESEND_API_KEY;
      const r = await resend('/emails', 'POST', {from: FROM, to: [me.e], subject: '[Test] ' + m.subject, html: m.html, text: m.text}, key);
      if (!r.ok) throw Object.assign(new Error('Resend didn\u2019t accept the test email (' + r.status + ').'), {status: 502});
      await audit(me.e, 'email_test', null, {template: body.template}).catch(() => {});
      return {ok: true, to: me.e};
    }
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
      const m = adminSignInEmail(link);
      const r = await resend('/emails', 'POST', {from: FROM, to: [email], subject: m.subject, text: m.text, html: m.html}, key);
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
