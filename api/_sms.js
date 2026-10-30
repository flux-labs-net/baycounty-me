// Alert text messages from a Telnyx toll-free number (BayCounty.me alerts, phase 3; migration 0090).
//
// Settings (Vercel environment):
//   TELNYX_API_KEY       API key (Telnyx portal > Auth > API Keys)
//   TELNYX_FROM          the toll-free number in +1 format, e.g. +18885551234
//   TELNYX_PROFILE_ID    optional messaging profile id
//   SMS_SEGMENT_COST     optional estimate per message part in dollars (default 0.0095: Telnyx $0.0055 + carrier fee)
// Texts go only to numbers their owner confirmed with a code. Every text is logged (kind, parts, cost; never the number
// or the words) in account.sms_log, and nothing is sent once the month's spend reaches the cap in account.sms_settings
// (set on /admin > Alert texts). STOP, HELP and START replies come back to /api/sms (vercel.json rewrites it to
// api/manage.js?app=sms, which hands it to webhook() below); the URL carries a signed key so only Telnyx can use it.
const crypto = require('crypto');
const {q, hasDb} = require('./_db');
const {derive} = require('./_gate');

const API = 'https://api.telnyx.com/v2/messages';
const SITE = 'https://baycounty.me';
const PART_COST = () => Number(process.env.SMS_SEGMENT_COST) || 0.0095;
const ready = () => !!(process.env.TELNYX_API_KEY && process.env.TELNYX_FROM);

const STOP_WORDS = ['STOP', 'STOPALL', 'UNSUBSCRIBE', 'CANCEL', 'END', 'QUIT', 'REVOKE', 'OPTOUT'];
const START_WORDS = ['START', 'UNSTOP', 'YES', 'SUBSCRIBE'];
const HELP_WORDS = ['HELP', 'INFO'];
const HELP_TEXT = 'BayCounty.me alerts: emergency notices for Bay County, FL. Msg frequency varies. Msg & data rates may apply. ' +
  'Change or stop at baycounty.me/account. Reply STOP to end. hello@baycounty.me';

/* ---------- numbers and text ---------- */
// US numbers only: 10 digits, or 11 starting with 1. Returns +1XXXXXXXXXX or null.
function normPhone(s) {
  let d = String(s || '').replace(/\D/g, '');
  if (d.length === 11 && d[0] === '1') d = d.slice(1);
  return /^[2-9]\d{2}[2-9]\d{6}$/.test(d) ? '+1' + d : null;
}
const maskPhone = p => (p ? `(•••) •••-${p.slice(-4)}` : null);

// Keep texts in the plain character set so a part holds 160 characters, not 70.
const plain = s => String(s || '').replace(/[‘’]/g, "'").replace(/[“”]/g, '"').replace(/[–—]/g, '-').replace(/…/g, '...')
  .replace(/·/g, '-').replace(/\s+/g, ' ').trim();
const GSM = /^[A-Za-z0-9 @£$¥èéùìòÇØøÅå_ÆæßÉ!"#%&'()*+,\-./:;<=>?¡ÄÖÑÜ§¿äöñüà\n\r]*$/;
function segments(text) {
  const t = String(text || '');
  if (GSM.test(t)) return t.length <= 160 ? 1 : Math.ceil(t.length / 153);
  return t.length <= 70 ? 1 : Math.ceil(t.length / 67);
}

// The alert text: who it's from, what it is, the instruction when there is one, the link and how to stop. Two parts at most.
function alertText(n, topic) {
  const P = require('./_push');
  const m = P.message(n, topic);
  const tail = ` ${SITE.replace('https://', '')}/emergency Reply STOP to end.`;
  let body = plain(`BayCounty.me: ${m.title}. ${m.body}`);
  const extra = plain(n.instruction || '');
  if (extra && !body.includes(extra)) body += ' ' + extra;
  const room = 306 - tail.length;
  if (body.length > room) body = body.slice(0, room - 3).replace(/\s+\S*$/, '') + '...';
  return body + tail;
}

/* ---------- spend ---------- */
const monthKey = (now = Date.now()) => new Date(now).toLocaleDateString('en-CA', {timeZone: 'America/Chicago'}).slice(0, 7);
async function settings() {
  const [s] = await q('select monthly_cap, paused, cap_hit_month, updated_by, updated_at from account.sms_settings where id');
  return s ? {...s, monthly_cap: +s.monthly_cap} : {monthly_cap: 150, paused: false};
}
// This month's spend (Central time), in dollars.
async function monthSpend(now = Date.now()) {
  const [r] = await q(`select coalesce(sum(cost), 0)::float as spent, count(*)::int as texts, coalesce(sum(segments), 0)::int as parts from account.sms_log
      where ok and to_char(sent_at at time zone 'America/Chicago', 'YYYY-MM') = $1`, [monthKey(now)]);
  return r;
}

/* ---------- sending ---------- */
async function sendOne(to, text) {
  if (!ready()) return {ok: false, error: 'not-configured'};
  const body = {from: process.env.TELNYX_FROM, to, text};
  if (process.env.TELNYX_PROFILE_ID) body.messaging_profile_id = process.env.TELNYX_PROFILE_ID;
  try {
    const r = await fetch(API, {method: 'POST', headers: {Authorization: `Bearer ${process.env.TELNYX_API_KEY}`, 'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) return {ok: false, error: ((j.errors || [])[0] || {}).detail || `Telnyx ${r.status}`, code: ((j.errors || [])[0] || {}).code};
    const d = j.data || {};
    const parts = d.parts || segments(text);
    const cost = d.cost && d.cost.amount != null ? Number(d.cost.amount) : parts * PART_COST();
    return {ok: true, id: d.id, parts, cost};
  } catch (e) { return {ok: false, error: e.message}; }
}
async function log(userId, kind, r, noticeId = null) {
  await q(`insert into account.sms_log (user_id, kind, notice_id, segments, cost, provider_id, ok) values ($1, $2, $3, $4, $5, $6, $7)
      on conflict do nothing`, [userId, kind, noticeId, r.parts || 1, r.ok ? r.cost || 0 : 0, r.id || null, !!r.ok]);
}
// A one-off text to one account (codes, HELP and START replies, tests). Counts toward the cap but is never blocked by it,
// so people can always confirm a number or get help.
async function sendTo(userId, to, text, kind) {
  const r = await sendOne(to, text);
  await log(userId, kind, r).catch(e => console.error('sms log', e.message));
  return r;
}

// An emergency notice was just pushed (api/_emergency_run.js): text the confirmed numbers whose owners asked for that
// type by text and whose areas or home it reaches. Overnight, people with quiet hours get only urgent ones.
// Stops when the month's spend reaches the cap.
async function noticeTexts(place, n, topic, nowMs = Date.now()) {
  const E = require('./_emergency');
  const out = {people: 0, sent: 0, capped: false};
  if (!hasDb() || !ready() || !E.ALERT_TYPES.some(t => t.key === topic && t.channels.includes('sms'))) return out;
  const s = await settings();
  if (s.paused) return out;
  const rows = await q(`select u.id, m.phone, h.address, h.zone, h.gov_id, p.alert_areas, p.quiet_hours from account.users u
      join account.prefs p on p.user_id = u.id join account.sms m on m.user_id = u.id and m.status = 'active'
      left join account.homes h on h.user_id = u.id
      where u.status = 'active' and coalesce(h.place_id, u.place_id, 'fl-bay') = $1 and p.alert_sms && $2::text[]`, [place, E.topicsFor(topic)]);
  const hush = E.quietNow(nowMs) && !E.isUrgent(n, topic);
  const want = rows.filter(r => !(hush && r.quiet_hours) && E.reaches({...n, status: 'active'}, {areas: r.alert_areas || [], home: r.address ? {gov_id: r.gov_id, zone: r.zone} : null}));
  if (!want.length) return out;
  const text = alertText(n, topic);
  const each = segments(text) * PART_COST();
  let {spent} = await monthSpend(nowMs);
  for (const r of want) {
    if (spent + each > s.monthly_cap) { out.capped = true; break; }
    // Claim first, so overlapping runs never text a person twice for one notice.
    const claimed = await q(`insert into account.sms_log (user_id, kind, notice_id, segments, cost, ok) values ($1, 'alert', $2, $3, 0, false)
        on conflict do nothing returning id`, [r.id, n.notice_id, segments(text)]);
    if (!claimed.length) continue;
    out.people++;
    const res = await sendOne(r.phone, text);
    await q('update account.sms_log set ok = $2, cost = $3, segments = $4, provider_id = $5 where id = $1',
      [claimed[0].id, !!res.ok, res.ok ? res.cost : 0, res.parts || segments(text), res.id || null]);
    if (res.ok) { out.sent++; spent += res.cost; }
    else if (res.code === '40300') await q(`update account.sms set status = 'stopped', stopped_at = now() where user_id = $1`, [r.id]); // the number opted out with the carrier
  }
  if (out.capped) {
    const mk = monthKey(nowMs);
    const first = await q(`update account.sms_settings set cap_hit_month = $1 where id and cap_hit_month is distinct from $1 returning id`, [mk]);
    if (first.length) console.error(`sms: monthly cap of $${s.monthly_cap} reached for ${mk}; texts paused until next month or a higher cap`);
  }
  return out;
}

/* ---------- STOP / HELP / START (Telnyx webhook) ---------- */
const hookKey = () => crypto.createHmac('sha256', derive('bcm-sms-hook-v1')).update('telnyx').digest('hex').slice(0, 32);
const webhookUrl = () => `${SITE}/api/sms?k=${hookKey()}`;
function keyword(text) {
  const w = String(text || '').trim().toUpperCase().replace(/[^A-Z]/g, '');
  if (STOP_WORDS.includes(w)) return 'stop';
  if (START_WORDS.includes(w)) return 'start';
  if (HELP_WORDS.includes(w)) return 'help';
  return null;
}
async function webhook(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return res.status(405).json({ok: false});
  const k = String((req.query || {}).k || '');
  const want = hookKey();
  if (k.length !== want.length || !crypto.timingSafeEqual(Buffer.from(k), Buffer.from(want))) return res.status(403).json({ok: false});
  if (!hasDb()) return res.status(503).json({ok: false});
  let b = req.body; if (typeof b === 'string') { try { b = JSON.parse(b); } catch (e) { b = {}; } }
  const d = (b && b.data) || {};
  if (d.event_type !== 'message.received') return res.status(200).json({ok: true, ignored: d.event_type || null});
  const p = d.payload || {};
  const from = normPhone(p.from && p.from.phone_number);
  const kw = keyword(p.text);
  if (!from || !kw) return res.status(200).json({ok: true});
  try {
    const rows = await q('select user_id, status from account.sms where phone = $1', [from]);
    if (kw === 'stop') {
      // The carrier confirms the opt-out on toll-free numbers; we only record it.
      await q(`update account.sms set status = 'stopped', stopped_at = now(), updated_at = now() where phone = $1 and status <> 'stopped'`, [from]);
    } else if (kw === 'start') {
      const was = rows.find(r => r.status === 'stopped' && r.user_id);
      const taken = rows.find(r => r.status === 'active');
      if (was && !taken) {
        await q(`update account.sms set status = 'active', stopped_at = null, updated_at = now() where user_id = $1`, [was.user_id]);
        await sendTo(was.user_id, from, 'BayCounty.me alerts are back on. Msg frequency varies. Msg & data rates may apply. Reply HELP for help, STOP to end.', 'start');
      }
    } else if (kw === 'help') {
      await sendTo(rows[0] ? rows[0].user_id : null, from, HELP_TEXT, 'help');
    }
  } catch (e) { console.error('sms webhook', e.message); }
  return res.status(200).json({ok: true});
}

/* ---------- admin ---------- */
async function adminReport() {
  const s = await settings();
  const m = await monthSpend();
  const [c] = await q(`select count(*) filter (where status = 'active')::int as active, count(*) filter (where status = 'pending')::int as pending,
      count(*) filter (where status = 'stopped')::int as stopped from account.sms`);
  const byKind = await q(`select kind, count(*)::int as texts, coalesce(sum(segments), 0)::int as parts, coalesce(sum(cost), 0)::float as cost from account.sms_log
      where ok and to_char(sent_at at time zone 'America/Chicago', 'YYYY-MM') = $1 group by kind order by cost desc`, [monthKey()]);
  const months = await q(`select to_char(sent_at at time zone 'America/Chicago', 'YYYY-MM') as month, count(*)::int as texts, coalesce(sum(cost), 0)::float as cost
      from account.sms_log where ok and sent_at > now() - interval '13 months' group by 1 order by 1 desc`);
  const f = normPhone(process.env.TELNYX_FROM);
  return {ready: ready(), from: f ? `(${f.slice(2, 5)}) ${f.slice(5, 8)}-${f.slice(8)}` : null,
    settings: s, month: monthKey(), spent: m.spent, texts: m.texts, parts: m.parts, part_cost: PART_COST(), phones: c, by_kind: byKind, months, webhook_url: webhookUrl()};
}
async function setSettings({monthly_cap, paused}, admin) {
  const cap = monthly_cap === undefined ? null : Number(monthly_cap);
  if (cap !== null && !(cap >= 0 && cap <= 10000)) throw Object.assign(new Error('The cap must be between $0 and $10,000.'), {status: 400, expose: true});
  await q(`update account.sms_settings set monthly_cap = coalesce($1, monthly_cap), paused = coalesce($2, paused), updated_by = $3, updated_at = now() where id`,
    [cap, typeof paused === 'boolean' ? paused : null, admin]);
  return adminReport();
}

module.exports = {ready, normPhone, maskPhone, plain, segments, alertText, monthKey, settings, monthSpend, sendOne, sendTo, noticeTexts,
  keyword, webhook, webhookUrl, hookKey, adminReport, setSettings, HELP_TEXT};
