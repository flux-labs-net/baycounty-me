// Weekly digest (Vercel cron, Mondays). Builds one email per government from /data/digest.json.
// Default: saves each as a Resend broadcast DRAFT and emails the editor to review. DIGEST_AUTOSEND=1 sends them.
const {GOVS, FROM, SITE, resend, esc, emailShell, button} = require('./_alerts');
const day = 864e5;
const nice = d => new Date(d + (d.length === 10 ? 'T12:00:00Z' : '')).toLocaleDateString('en-US', {month: 'short', day: 'numeric', timeZone: 'America/Chicago'});
const when = d => d.length > 10 ? new Date(d).toLocaleString('en-US', {weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago'}) : nice(d);
const P = 'margin:0 0 10px 0;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:22px;color:#161B24';
const H = 'margin:18px 0 8px 0;font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:22px;color:#1E3A76;font-weight:bold';
module.exports = async (req, res) => {
  if ((req.headers.authorization || '') !== `Bearer ${process.env.CRON_SECRET}` || !process.env.CRON_SECRET) return res.status(401).json({ok: false});
  const key = process.env.RESEND_FULL_KEY;
  if (!key) return res.status(500).json({ok: false, error: 'RESEND_FULL_KEY missing'});
  const dg = await (await fetch(`${SITE}/data/digest.json?ts=${Date.now()}`)).json();
  const now = Date.now(), since = now - 7 * day, until = now + 8 * day, autosend = process.env.DIGEST_AUTOSEND === '1';
  const done = [];
  for (const g of dg.govs) {
    if (!GOVS[g.key]) continue;
    const changes = (g.changes || []).filter(c => Date.parse(c.date + 'T23:59:59-05:00') >= since);
    const meets = (g.meetings || []).filter(m => { const t = Date.parse(m.start); return t >= now - day / 2 && t <= until; });
    if (!changes.length && !meets.length) continue;
    const page = `${SITE}/governments/${g.slug}`;
    let inner = `<p style="${P}">Here's what's new on BayCounty.me for <b>${esc(g.name)}</b> this week.</p>`, text = `What's new on BayCounty.me for ${g.name} this week.\n`;
    if (changes.length) {
      inner += `<p style="${H}">New and updated</p>` + changes.map(c => `<p style="${P}"><b><a href="${esc(c.url)}" style="color:#1E3A76">${esc(c.title)}</a></b> <span style="color:#5A6372;font-size:13px">${esc(nice(c.date))}</span><br>${esc(c.text)}</p>`).join('');
      text += '\nNEW AND UPDATED\n' + changes.map(c => `- ${c.title} (${nice(c.date)}): ${c.text} ${c.url}`).join('\n') + '\n';
    }
    if (meets.length) {
      inner += `<p style="${H}">Coming up</p>` + meets.map(m => `<p style="${P}"><b>${esc(when(m.start))}</b> · ${esc(m.title)}${m.agenda_url ? ` · <a href="${esc(m.agenda_url)}" style="color:#1E3A76">Agenda</a>` : m.expected ? ' <span style="color:#5A6372;font-size:13px">(regular schedule; agenda not posted yet)</span>' : ''}</p>`).join('');
      text += '\nCOMING UP\n' + meets.map(m => `- ${when(m.start)}: ${m.title}${m.agenda_url ? ' ' + m.agenda_url : ''}`).join('\n') + '\n';
    }
    inner += button(page, `See ${g.name} on BayCounty.me`);
    const footer = `You're getting this because you signed up for ${esc(g.name)} alerts on BayCounty.me. <a href="{{{RESEND_UNSUBSCRIBE_URL}}}" style="color:#5A6372">Unsubscribe</a> · <a href="${SITE}/alerts" style="color:#5A6372">Change what you follow</a>`;
    text += `\n${page}\n\nUnsubscribe: {{{RESEND_UNSUBSCRIBE_URL}}}`;
    const subject = `${g.name} this week on BayCounty.me`;
    const r = await resend('/broadcasts', 'POST', {segment_id: GOVS[g.key][1], from: FROM, reply_to: 'hello@fluxlabs.net', subject, name: `${subject} (${new Date().toISOString().slice(0, 10)})`, html: emailShell(subject, inner, footer), text, send: autosend}, key);
    done.push({gov: g.name, ok: r.ok, id: r.body && r.body.id, error: r.ok ? undefined : r.body});
  }
  if (done.length && !autosend) {
    await resend('/emails', 'POST', {from: FROM, to: [process.env.DIGEST_REVIEWER || 'hello@fluxlabs.net'], subject: `BayCounty.me: ${done.length} weekly digest${done.length > 1 ? 's' : ''} ready to review`,
      text: `These weekly digests were saved as drafts in Resend (Broadcasts). Review and send them there:\n\n${done.map(d => `- ${d.gov}${d.ok ? '' : ' (failed: ' + JSON.stringify(d.error) + ')'}`).join('\n')}\n\nhttps://resend.com/broadcasts`}, key);
  }
  return res.status(200).json({ok: true, autosend, digests: done});
};
