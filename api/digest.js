// Weekly digest (Vercel cron, Mondays). Builds one email per government from /data/digest.json.
// Default: saves each as a Resend broadcast DRAFT and emails the editor to review. DIGEST_AUTOSEND=1 sends them.
// The email itself is built by digestEmail() in _emails.js (shared with the /admin previews).
const {GOVS, FROM, resend, ensurePrefsProperty} = require('./_alerts');
const {digestEmail} = require('./_emails');
const {SITE_URL} = require('./_data');
const ui = require('./_email_ui');

// Notes to the reviewer. kind: 'nodata' (digest.json missing), 'failed' (some sends failed), 'ready' (drafts saved).
function reviewEmail(kind, {why, done = []} = {}) {
  const esc = ui.esc;
  if (kind === 'nodata') return ui.adminNotice({subject: 'BayCounty.me: weekly digest FAILED (no digest data)', kicker: 'Weekly digest', tone: 'salmon', icon: 'alert',
    text: `The weekly digest did not run because ${SITE_URL}/data/digest.json could not be loaded: ${why}.\n\nNo emails were drafted or sent. Check the latest deploy, then re-run the cron from Vercel (Settings > Cron Jobs) or call /api/digest with the CRON_SECRET.`,
    eyebrow: 'Weekly digest', title: 'The digest didn’t run', preheader: 'digest.json could not be loaded. No emails were drafted or sent.',
    body: ui.p(`The weekly digest couldn’t load <b>/data/digest.json</b>: ${esc(why)}. No emails were drafted or sent.`) +
      ui.p('Check the latest deploy, then re-run the cron from Vercel (Settings, Cron Jobs) or call /api/digest with the CRON_SECRET.', {size: 14, lh: 21})});
  const failed = done.filter(d => !d.ok), n = kind === 'failed' ? failed.length : done.length, s = n > 1 ? 's' : '';
  if (kind === 'failed') return ui.adminNotice({subject: `BayCounty.me: ${n} weekly digest${s} failed`, kicker: 'Weekly digest', tone: 'salmon', icon: 'alert',
    text: failed.map(d => `- ${d.gov}: ${JSON.stringify(d.error)}`).join('\n'), eyebrow: 'Weekly digest', title: `${n} digest${s} didn’t send`,
    preheader: failed.map(d => d.gov).join(', '),
    body: ui.list(failed.map(d => ['salmon', 'Failed', `<b>${esc(d.gov)}</b><br><span style="font-size:13px">${esc(JSON.stringify(d.error))}</span>`])) + ui.button('https://resend.com/broadcasts', 'Open Resend broadcasts')});
  return ui.adminNotice({subject: `BayCounty.me: ${n} weekly digest${s} ready to review`, kicker: 'Review queue', tone: 'amber', icon: 'check',
    text: `These weekly digests were saved as drafts in Resend (Broadcasts). Review and send them there:\n\n${done.map(d => `- ${d.gov}${d.ok ? '' : ' (failed: ' + JSON.stringify(d.error) + ')'}`).join('\n')}\n\nhttps://resend.com/broadcasts`,
    eyebrow: 'Weekly digest', title: `${n} digest${s} ready to review`, preheader: done.map(d => d.gov).join(', '),
    body: ui.p('These weekly digests were saved as drafts in Resend. Nothing has gone to subscribers yet.') +
      ui.list(done.map(d => d.ok ? ['teal', 'Draft', esc(d.gov)] : ['salmon', 'Failed', `<b>${esc(d.gov)}</b> · ${esc(JSON.stringify(d.error))}`])) + ui.button('https://resend.com/broadcasts', 'Review in Resend')});
}

module.exports = async (req, res) => {
  if ((req.headers.authorization || '') !== `Bearer ${process.env.CRON_SECRET}` || !process.env.CRON_SECRET) return res.status(401).json({ok: false});
  const key = process.env.RESEND_FULL_KEY;
  if (!key) return res.status(500).json({ok: false, error: 'RESEND_FULL_KEY missing'});
  const reviewer = process.env.DIGEST_REVIEWER || 'hello@fluxlabs.net';
  let dg;
  try {
    const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 15000);
    let r;
    try { r = await fetch(`${SITE_URL}/data/digest.json?ts=${Date.now()}`, {signal: ctl.signal}); } finally { clearTimeout(timer); }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    dg = await r.json();
    if (!dg || !Array.isArray(dg.govs)) throw new Error('digest.json has no "govs" list');
  } catch (e) {
    const why = e.name === 'AbortError' ? 'timed out after 15 seconds' : e.message;
    console.error('digest: could not load digest.json', why);
    await resend('/emails', 'POST', {from: FROM, to: [reviewer], ...reviewEmail('nodata', {why})}, key).catch(() => {});
    return res.status(502).json({ok: false, error: 'digest.json unavailable', detail: why});
  }
  const now = Date.now(), autosend = process.env.DIGEST_AUTOSEND === '1';
  const done = [];
  // The manage link uses the prefs_token contact property (see _alerts.js); make sure it exists before drafting.
  await ensurePrefsProperty(key).catch(e => console.error('digest: prefs property', e.message));
  for (const g of dg.govs) {
    try {
    if (!GOVS[g.key]) continue;
    const m = digestEmail(g, {now});
    if (!m) continue;
    const {subject, html, text} = m;
    const r = await resend('/broadcasts', 'POST', {segment_id: GOVS[g.key][1], from: FROM, reply_to: 'hello@fluxlabs.net', subject, name: `${subject} (${new Date().toISOString().slice(0, 10)})`, html, text, send: autosend}, key);
    done.push({gov: g.name, ok: r.ok, id: r.body && r.body.id, error: r.ok ? undefined : r.body});
    } catch (e) { console.error('digest', g && g.name, e); done.push({gov: (g && g.name) || '?', ok: false, error: e.message}); }
  }
  const failed = done.filter(d => !d.ok);
  if (failed.length && autosend) {
    await resend('/emails', 'POST', {from: FROM, to: [reviewer], ...reviewEmail('failed', {done})}, key).catch(() => {});
  }
  if (done.length && !autosend) {
    await resend('/emails', 'POST', {from: FROM, to: [reviewer], ...reviewEmail('ready', {done})}, key);
  }
  return res.status(200).json({ok: true, autosend, digests: done});
};
module.exports.reviewEmail = reviewEmail;
