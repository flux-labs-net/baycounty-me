// Daily rule-alerts run (Vercel cron). Matches new records (alerts.events, written by db/scripts/load.py) to
// confirmed rules (alerts.subscriptions) and builds ONE email per subscriber listing everything that matched.
// Default (ALERTS_AUTOSEND unset): emails are saved as drafts in alerts.outbox and the reviewer
// (DIGEST_REVIEWER) gets a summary. Nothing goes to subscribers. After review, set ALERTS_AUTOSEND=1 and call
// GET /api/alerts-run?send=drafts with the CRON_SECRET to send the waiting drafts.
// With ALERTS_AUTOSEND=1, each run's emails are sent right away.
// Auth: Authorization: Bearer <CRON_SECRET> (Vercel sends it on cron calls).
const {FROM, SITE, resend, esc, emailShell, button, prefsUrl} = require('./_alerts');
const {match, describe} = require('./_rules');
const db = require('./_db');

const P = 'margin:0 0 10px 0;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:22px;color:#161B24';
const H = 'margin:18px 0 8px 0;font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:22px;color:#1E3A76;font-weight:bold';
const MAX_EVENTS = 5000, MAX_PER_EMAIL = 40;

// Pure: group matches per subscriber. rules: [{id, email, rule_type, params}], events: [{dataset, record_hash, government_key, record}],
// seen: Set of `${subscription_id}|${dedupe}` already delivered. Returns Map email -> [{rule, hits: [match...]}].
function plan(rules, events, seen = new Set()) {
  const out = new Map();
  for (const rule of rules) {
    const hits = [], keys = new Set();
    for (const ev of events) {
      const m = match(rule, ev);
      if (!m || keys.has(m.dedupe) || seen.has(`${rule.id}|${m.dedupe}`)) continue;
      keys.add(m.dedupe); hits.push(m);
    }
    if (!hits.length) continue;
    if (!out.has(rule.email)) out.set(rule.email, []);
    out.get(rule.email).push({rule, hits});
  }
  return out;
}

function compose(email, groups) {
  let n = 0, inner = `<p style="${P}">Here’s what’s new on BayCounty.me that matches your alerts.</p>`, text = 'New on BayCounty.me that matches your alerts.\n';
  for (const {rule, hits} of groups) {
    const shown = hits.slice(0, Math.max(1, MAX_PER_EMAIL - n));
    n += shown.length;
    const head = describe(rule.rule_type, rule.params);
    inner += `<p style="${H}">${esc(head)}</p>` + shown.map(m => `<p style="${P}"><b>${m.url ? `<a href="${esc(m.url)}" style="color:#1E3A76">${esc(m.title)}</a>` : esc(m.title)}</b>${m.detail ? `<br>${esc(m.detail)}` : ''}</p>`).join('');
    text += `\n${head.toUpperCase()}\n` + shown.map(m => `- ${m.title}${m.detail ? ': ' + m.detail : ''}${m.url ? ' ' + m.url : ''}`).join('\n') + '\n';
    if (hits.length > shown.length) { inner += `<p style="${P}">…and ${hits.length - shown.length} more.</p>`; text += `...and ${hits.length - shown.length} more.\n`; }
  }
  inner += `<p style="${P};font-size:13px;color:#5A6372">Each item links to its public record. A match only shows that a record mentions what you asked about, not why anything happened.</p>` + button(`${SITE}/meetings`, 'See it on BayCounty.me');
  const manage = prefsUrl(email);
  const footer = `You’re getting this because you set up these alerts on BayCounty.me. <a href="${esc(manage)}" style="color:#5A6372">Change or stop your alerts</a>`;
  text += `\nChange or stop your alerts: ${manage}\n`;
  const total = groups.reduce((a, g) => a + g.hits.length, 0);
  const subject = `BayCounty.me: ${total} new match${total === 1 ? '' : 'es'} for your alerts`;
  return {subject, html: emailShell(subject, inner, footer), text, matches: total};
}

async function sendOne(key, o) {
  const r = await resend('/emails', 'POST', {from: FROM, to: [o.email], reply_to: 'hello@fluxlabs.net', subject: o.subject, html: o.html, text: o.text,
    headers: {'List-Unsubscribe': `<${prefsUrl(o.email)}>`}}, key);
  await db.q(`update alerts.outbox set status = $2, sent_at = case when $2 = 'sent' then now() end, error = $3 where id = $1`,
    [o.id, r.ok ? 'sent' : 'failed', r.ok ? null : JSON.stringify(r.body).slice(0, 500)]);
  return r.ok;
}

module.exports = async (req, res) => {
  if (!process.env.CRON_SECRET || (req.headers.authorization || '') !== `Bearer ${process.env.CRON_SECRET}`) return res.status(401).json({ok: false});
  const key = process.env.RESEND_FULL_KEY;
  if (!key) return res.status(500).json({ok: false, error: 'RESEND_FULL_KEY missing'});
  if (!db.hasDb()) return res.status(500).json({ok: false, error: 'DATABASE_URL missing'});
  const autosend = process.env.ALERTS_AUTOSEND === '1';
  const reviewer = process.env.DIGEST_REVIEWER || 'hello@fluxlabs.net';
  try {
    // Send drafts on request (after review), only when autosend is on: the owner flips ALERTS_AUTOSEND=1 to approve.
    if ((req.query || {}).send === 'drafts') {
      if (!autosend) return res.status(409).json({ok: false, error: 'Set ALERTS_AUTOSEND=1 to send drafts.'});
      const drafts = await db.q(`select id, email, subject, html, text from alerts.outbox where status = 'draft' order by id limit 200`);
      let sent = 0; for (const o of drafts) if (await sendOne(key, o)) sent++;
      return res.status(200).json({ok: true, sent, drafts: drafts.length});
    }
    const events = await db.q(`select id, dataset, record_hash, government_key, record from alerts.events where processed_at is null order by id limit ${MAX_EVENTS}`);
    if (!events.length) return res.status(200).json({ok: true, events: 0, emails: 0});
    const rules = await db.q(`select id, email, rule_type, params from alerts.subscriptions where confirmed and unsubscribed_at is null`);
    const seen = new Set((rules.length ? await db.q(`select subscription_id, dedupe_key from alerts.deliveries where subscription_id = any($1)`, [rules.map(r => r.id)]) : [])
      .map(d => `${d.subscription_id}|${d.dedupe_key}`));
    const byEmail = plan(rules, events, seen);
    const made = [];
    for (const [email, groups] of byEmail) {
      const m = compose(email, groups);
      const [o] = await db.q(`insert into alerts.outbox (email, subject, html, text, matches) values ($1,$2,$3,$4,$5) returning id`, [email, m.subject, m.html, m.text, m.matches]);
      for (const {rule, hits} of groups) for (const h of hits)
        await db.q(`insert into alerts.deliveries (subscription_id, dedupe_key, outbox_id) values ($1,$2,$3) on conflict do nothing`, [rule.id, h.dedupe, o.id]);
      made.push({id: o.id, email, subject: m.subject, html: m.html, text: m.text, matches: m.matches});
    }
    await db.q(`update alerts.events set processed_at = now() where id = any($1)`, [events.map(e => e.id)]);
    let sent = 0;
    if (autosend) for (const o of made) if (await sendOne(key, o)) sent++;
    if (made.length && !autosend) {
      await resend('/emails', 'POST', {from: FROM, to: [reviewer], subject: `BayCounty.me: ${made.length} rule alert email${made.length > 1 ? 's' : ''} ready to review`,
        text: `The daily alerts run matched ${events.length} new record(s) and drafted ${made.length} email(s) (saved in alerts.outbox, status 'draft'):\n\n${made.map(o => `- #${o.id}: ${o.matches} match(es): ${o.subject}`).join('\n')}\n\nTo send drafts: set ALERTS_AUTOSEND=1 in Vercel, then POST ${SITE}/api/alerts-run?send=drafts with the CRON_SECRET (or wait for the next run, which sends new matches directly).\nAddresses aren't listed here; see alerts.outbox in Supabase.`}, key).catch(() => {});
    }
    return res.status(200).json({ok: true, autosend, events: events.length, rules: rules.length, emails: made.length, sent});
  } catch (e) {
    console.error('alerts-run', e);
    if (e.code === '42P01') return res.status(200).json({ok: false, error: 'Migration 0008 not applied yet.'});
    return res.status(500).json({ok: false, error: e.message});
  }
};
module.exports.plan = plan;
module.exports.compose = compose;
