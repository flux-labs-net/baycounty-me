// This week in Bay County: the countywide weekly email (Vercel cron, Mondays). Built from /data/weekly.json
// (site/weekly.py, rebuilt every morning) by weeklyEmail() in _emails.js, the same content as /this-week.
// Default: saves it as a Resend broadcast DRAFT to the weekly list and emails the reviewer. WEEKLY_AUTOSEND=1 sends it.
//   GET /api/weekly with Authorization: Bearer CRON_SECRET          the Monday run
//   ...?test=1                                                      sends one copy to the reviewer only (no draft)
// The edition must be this week's (week_of = this Monday); a stale build stops the run and tells the reviewer.
const {WEEKLY, FROM, resend, ensurePrefsProperty, prefsUrl} = require('./_alerts');
const {weeklyEmail} = require('./_emails');
const {SITE_URL} = require('./_data');
const ui = require('./_email_ui');

// Monday of this week, in Bay County time, as YYYY-MM-DD.
function thisMonday(now = Date.now()) {
  const local = new Date(new Date(now).toLocaleString('en-US', {timeZone: 'America/Chicago'}));
  local.setDate(local.getDate() - ((local.getDay() + 6) % 7));
  return `${local.getFullYear()}-${String(local.getMonth() + 1).padStart(2, '0')}-${String(local.getDate()).padStart(2, '0')}`;
}

function reviewEmail(kind, {why, id, subject, counts} = {}) {
  const esc = ui.esc;
  if (kind === 'failed') return ui.adminNotice({subject: 'BayCounty.me: This week in Bay County FAILED', kicker: 'Weekly email', tone: 'salmon', icon: 'alert',
    text: `The weekly email did not go out: ${why}.\n\nNothing was sent to subscribers. Check the latest deploy, then re-run /api/weekly with the CRON_SECRET.`,
    eyebrow: 'Weekly email', title: 'The weekly email didn’t run', preheader: why,
    body: ui.p(`This week in Bay County didn’t go out: ${esc(why)}. Nothing was sent to subscribers.`) +
      ui.p('Check the latest deploy, then re-run /api/weekly with the CRON_SECRET.', {size: 14, lh: 21})});
  const c = counts || {};
  return ui.adminNotice({subject: `BayCounty.me: This week in Bay County ready to review`, kicker: 'Review queue', tone: 'amber', icon: 'check',
    text: `This week's email was saved as a draft in Resend (Broadcasts): "${subject}". Review and send it there:\n\nhttps://resend.com/broadcasts${id ? '/' + id : ''}`,
    eyebrow: 'Weekly email', title: 'This week’s email is ready to review', preheader: subject,
    body: ui.p('This week’s email was saved as a draft in Resend. Nothing has gone to subscribers yet.') +
      ui.facts([['Subject', esc(subject)], ['Events', String(c.ev || 0)], ['Meetings', String(c.mt || 0)], ['New votes', String(c.vt || 0)], ['New contracts', String(c.ct || 0)]]) +
      ui.button(`https://resend.com/broadcasts${id ? '/' + id : ''}`, 'Review in Resend') + ui.small(`The same list is on ${ui.link('https://baycounty.me/this-week', 'baycounty.me/this-week')}.`)});
}

async function loadEdition() {
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 15000);
  try {
    const r = await fetch(`${SITE_URL}/data/weekly.json?ts=${Date.now()}`, {signal: ctl.signal});
    if (!r.ok) throw new Error(`weekly.json: HTTP ${r.status}`);
    const ed = await r.json();
    if (!ed || !Array.isArray(ed.rows)) throw new Error('weekly.json has no "rows" list');
    return ed;
  } catch (e) { throw e.name === 'AbortError' ? new Error('weekly.json timed out after 15 seconds') : e; } finally { clearTimeout(timer); }
}

module.exports = async (req, res) => {
  if ((req.headers.authorization || '') !== `Bearer ${process.env.CRON_SECRET}` || !process.env.CRON_SECRET) return res.status(401).json({ok: false});
  const key = process.env.RESEND_FULL_KEY;
  if (!key) return res.status(500).json({ok: false, error: 'RESEND_FULL_KEY missing'});
  const reviewer = process.env.DIGEST_REVIEWER || 'hello@fluxlabs.net';
  const test = req.query && req.query.test === '1';
  const fail = async (code, why) => {
    console.error('weekly:', why);
    if (!test) await resend('/emails', 'POST', {from: FROM, to: [reviewer], ...reviewEmail('failed', {why})}, key).catch(() => {});
    return res.status(code).json({ok: false, error: why});
  };
  let ed;
  try { ed = await loadEdition(); } catch (e) { return fail(502, e.message); }
  const monday = thisMonday();
  if (ed.week_of !== monday && !test) return fail(409, `the site's weekly list is for the week of ${ed.week_of}, not ${monday} (the morning rebuild may not have deployed)`);
  const m = weeklyEmail(ed);
  if (!m) return res.status(200).json({ok: true, skipped: 'nothing this week'});
  if (test) { // one copy to the reviewer, with their own manage link in place of the broadcast placeholders
    const fill = s => s.split('{{{contact.prefs_token|none}}}').join(prefsUrl(reviewer).split('?t=')[1]).split('{{{RESEND_UNSUBSCRIBE_URL}}}').join(prefsUrl(reviewer));
    const r = await resend('/emails', 'POST', {from: FROM, to: [reviewer], reply_to: 'hello@fluxlabs.net', subject: `[Test] ${m.subject}`, html: fill(m.html), text: fill(m.text)}, key);
    return res.status(r.ok ? 200 : 502).json({ok: r.ok, test: true, to: reviewer, id: r.body && r.body.id, error: r.ok ? undefined : r.body});
  }
  const autosend = process.env.WEEKLY_AUTOSEND === '1';
  await ensurePrefsProperty(key).catch(e => console.error('weekly: prefs property', e.message));
  const r = await resend('/broadcasts', 'POST', {segment_id: WEEKLY[1], from: FROM, reply_to: 'hello@fluxlabs.net', subject: m.subject,
    name: `${m.subject} (${monday})`, html: m.html, text: m.text, send: autosend}, key);
  if (!r.ok) return fail(502, `Resend refused the broadcast: ${JSON.stringify(r.body)}`);
  const id = r.body && r.body.id;
  if (!autosend) await resend('/emails', 'POST', {from: FROM, to: [reviewer], ...reviewEmail('ready', {id, subject: m.subject, counts: m.counts})}, key).catch(e => console.error('weekly: review note', e.message));
  return res.status(200).json({ok: true, autosend, id, subject: m.subject, counts: m.counts});
};
module.exports.thisMonday = thisMonday;
module.exports.reviewEmail = reviewEmail;
