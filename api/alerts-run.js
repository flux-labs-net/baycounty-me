// Daily rule-alerts run (Vercel cron). Matches new records (alerts.events, written by db/scripts/load.py) to
// confirmed rules (alerts.subscriptions) and builds ONE email per subscriber listing everything that matched.
// Default (ALERTS_AUTOSEND unset): emails are saved as drafts in alerts.outbox and the reviewer
// (DIGEST_REVIEWER) gets a summary. Nothing goes to subscribers. After review, set ALERTS_AUTOSEND=1 and call
// GET /api/alerts-run?send=drafts with the CRON_SECRET to send the waiting drafts.
// With ALERTS_AUTOSEND=1, each run's emails are sent right away.
// Auth: Authorization: Bearer <CRON_SECRET> (Vercel sends it on cron calls).
// Each run first does the ingestion health check (_health.js) and emails ADMIN_EMAILS if it finds problems.
const {FROM, SITE, resend, esc, prefsUrl} = require('./_alerts');
const ui = require('./_email_ui');
const {match, describe} = require('./_rules');
const db = require('./_db');

// Each kind of rule gets its own colored heading in the email.
const LOOK = {contract: ['teal', 'dollar'], keyword: ['blue', 'search'], vote: ['amber', 'vote'], campaign: ['salmon', 'megaphone']};
// MAX_EVENTS caps one run. It was 5000, and a vote backfill of ~50,000 rows then took weeks to clear.
const MAX_EVENTS = 50000, MAX_PER_EMAIL = 40;

// Pure: group matches per subscriber. rules: [{id, email, rule_type, params}], events: [{dataset, record_hash, government_key, record}],
// seen: Set of `${subscription_id}|${dedupe}` already delivered. Returns Map email -> [{rule, hits: [match...]}].
function plan(rules, events, seen = new Set()) {
  const out = new Map();
  // Meetings first: an item already listed from a meeting's agenda isn't sent again from the agenda reader.
  const ordered = [...events].sort((a, b) => (a.dataset === 'agenda-items') - (b.dataset === 'agenda-items'));
  for (const rule of rules) {
    const hits = [], keys = new Set(), items = new Set();
    for (const ev of ordered) {
      const m = match(rule, ev);
      if (!m || keys.has(m.dedupe) || seen.has(`${rule.id}|${m.dedupe}`)) continue;
      if (ev.dataset === 'agenda-items' && (m.itemKeys || []).every(k => items.has(k))) continue;
      keys.add(m.dedupe); (m.itemKeys || []).forEach(k => items.add(k)); hits.push(m);
    }
    if (!hits.length) continue;
    if (!out.has(rule.email)) out.set(rule.email, []);
    out.get(rule.email).push({rule, hits});
  }
  return out;
}

function compose(email, groups) {
  let n = 0, body = '', text = 'New on BayCounty.me that matches your alerts.\n';
  groups.forEach(({rule, hits}, gi) => {
    const shown = hits.slice(0, Math.max(1, MAX_PER_EMAIL - n));
    n += shown.length;
    const head = describe(rule.rule_type, rule.params);
    const [tone, icon] = LOOK[rule.rule_type] || ['blue', 'bell'];
    body += (gi ? ui.spacer(18) : '') + ui.section(tone, icon, esc(head), hits.length) +
      shown.map(m => ui.item({title: esc(m.title), url: m.url, text: m.detail ? esc(m.detail) : '', more: m.url ? 'See the record' : ''})).join('');
    text += `\n${head.toUpperCase()}\n` + shown.map(m => `- ${m.title}${m.detail ? ': ' + m.detail : ''}${m.url ? ' ' + m.url : ''}`).join('\n') + '\n';
    if (hits.length > shown.length) { body += ui.p(`…and ${hits.length - shown.length} more.`, {muted: true, mb: 0, size: 14}); text += `...and ${hits.length - shown.length} more.\n`; }
  });
  body += ui.spacer(16) + ui.note('Each item links to its public record. A match only shows that a record mentions what you asked about, not why anything happened.') +
    ui.button(`${SITE}/meetings`, 'See it on BayCounty.me');
  const manage = prefsUrl(email);
  const footer = `You’re getting this because you set up these alerts on BayCounty.me. ${ui.footLink(manage, 'Change or stop your alerts')}<br><br>${ui.ABOUT}`;
  text += `\nChange or stop your alerts: ${manage}\n`;
  const total = groups.reduce((a, g) => a + g.hits.length, 0);
  const first = groups[0] && groups[0].hits[0];
  const subject = `${total} new match${total === 1 ? '' : 'es'} for your BayCounty.me alerts`;
  const today = new Date().toLocaleDateString('en-US', {month: 'short', day: 'numeric', timeZone: 'America/Chicago'});
  const html = ui.layout({title: subject, preheader: first ? `${first.title}${total > 1 ? `, and ${total - 1} more` : ''}.` : '', kicker: `Your alerts · ${today}`,
    hero: {tone: 'teal', icon: 'bell', eyebrow: 'New this morning', title: `${total} new match${total === 1 ? '' : 'es'} for your alerts`}, body, footer});
  return {subject, html, text, matches: total};
}

// The reviewer's note when drafts are waiting (autosend off).
function reviewEmail(made, events) {
  const n = made.length, s = n > 1 ? 's' : '';
  const text = `The daily alerts run matched ${events} new record(s) and drafted ${n} email(s) (saved in alerts.outbox, status 'draft'):\n\n${made.map(o => `- #${o.id}: ${o.matches} match(es): ${o.subject}`).join('\n')}\n\nTo send drafts: set ALERTS_AUTOSEND=1 in Vercel, then POST ${SITE}/api/alerts-run?send=drafts with the CRON_SECRET (or wait for the next run, which sends new matches directly).\nAddresses aren't listed here; see alerts.outbox in Supabase.`;
  return ui.adminNotice({subject: `BayCounty.me: ${n} rule alert email${s} ready to review`, text, kicker: 'Review queue', tone: 'amber', icon: 'check',
    preheader: `The morning run matched ${events} new record${events === 1 ? '' : 's'} and drafted ${n} email${s}.`,
    eyebrow: 'Daily alerts run', title: `${n} alert email${s} ready to review`,
    body: ui.p(`The morning run matched ${events} new record${events === 1 ? '' : 's'} and drafted ${n} email${s}. Nothing has gone to subscribers yet.`) +
      ui.list(made.slice(0, 40).map(o => ['blue', `#${o.id}`, `${o.matches} match${o.matches === 1 ? '' : 'es'} · ${esc(o.subject)}`])) +
      ui.p(`To send them, set <b>ALERTS_AUTOSEND=1</b> in Vercel, then POST <span style="font-family:${ui.MONO};font-size:13px">/api/alerts-run?send=drafts</span> with the CRON_SECRET, or wait for the next run.`, {size: 14, lh: 21}) +
      ui.small('Addresses aren’t listed here. They stay in alerts.outbox in Supabase.')});
}

async function sendOne(key, o) {
  const r = await resend('/emails', 'POST', {from: FROM, to: [o.email], reply_to: 'hello@fluxlabs.net', subject: o.subject, html: o.html, text: o.text,
    headers: {'List-Unsubscribe': `<${prefsUrl(o.email)}>`, 'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'}}, key);
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
  // Emailed accounting files that never reached /finance (the edge function's call failed or was missed).
  await require('./_finance/intake').sweep().catch(e => console.error('finance intake sweep', e.message));
  // Ingestion health check (see _health.js): emails the admins (ADMIN_EMAILS) only when something is wrong.
  // Runs first and on its own, so a problem in the alerts run below can't hide it. ?health=1 runs only the check.
  let health = null;
  try { health = await require('./_health').checkAndNotify(key); }
  catch (e) { console.error('ingest health', e); health = {error: e.message}; }
  if ((req.query || {}).health) return res.status(200).json({ok: !health.error, health});
  try {
    // Send drafts on request (after review), only when autosend is on: the owner flips ALERTS_AUTOSEND=1 to approve.
    if ((req.query || {}).send === 'drafts') {
      if (!autosend) return res.status(409).json({ok: false, error: 'Set ALERTS_AUTOSEND=1 to send drafts.'});
      const drafts = await db.q(`select id, email, subject, html, text from alerts.outbox where status = 'draft' order by id limit 200`);
      let sent = 0; for (const o of drafts) if (await sendOne(key, o)) sent++;
      return res.status(200).json({ok: true, sent, drafts: drafts.length});
    }
    const problems = health && health.problems ? health.problems.length : null;
    const rules = await db.q(`select id, email, rule_type, params from alerts.subscriptions where confirmed and unsubscribed_at is null`);
    // No one has a rule: nothing can match, so mark the whole queue checked in one statement.
    if (!rules.length) {
      const [c] = await db.q(`with u as (update alerts.events set processed_at = now() where processed_at is null returning 1) select count(*)::int n from u`);
      return res.status(200).json({ok: true, events: c ? c.n : 0, rules: 0, emails: 0, ingest_problems: problems});
    }
    const events = await db.q(`select id, dataset, record_hash, government_key, record from alerts.events where processed_at is null order by id limit ${MAX_EVENTS}`);
    if (!events.length) return res.status(200).json({ok: true, events: 0, emails: 0, ingest_problems: problems});
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
      await resend('/emails', 'POST', {from: FROM, to: [reviewer], ...reviewEmail(made, events.length)}, key).catch(() => {});
    }
    return res.status(200).json({ok: true, autosend, events: events.length, rules: rules.length, emails: made.length, sent, ingest_problems: problems});
  } catch (e) {
    console.error('alerts-run', e);
    if (e.code === '42P01') return res.status(200).json({ok: false, error: 'Migration 0008 not applied yet.'});
    return res.status(500).json({ok: false, error: e.message});
  }
};
module.exports.plan = plan;
module.exports.compose = compose;
module.exports.reviewEmail = reviewEmail;
