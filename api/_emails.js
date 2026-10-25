// Builders for the emails people get from BayCounty.me. Each returns {subject, html, text} and sends nothing,
// so the routes that send them and the /admin email previews use exactly the same content.
// The rule-alert email is built by compose() in alerts-run.js. Files starting with _ are not routes.
const {SITE, esc, emailShell, button, PREFS_LINK_TEMPLATE} = require('./_alerts');

const P = 'margin:0 0 10px 0;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:22px;color:#161B24';
const H = 'margin:18px 0 8px 0;font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:22px;color:#1E3A76;font-weight:bold';
const day = 864e5;
const nice = d => new Date(d + (d.length === 10 ? 'T12:00:00Z' : '')).toLocaleDateString('en-US', {month: 'short', day: 'numeric', timeZone: 'America/Chicago'});
const when = d => d.length > 10 ? new Date(d).toLocaleString('en-US', {weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago'}) : nice(d);

// Double opt-in confirmation (subscribe.js). what: plain-text description; isRule: rule alert vs weekly digest.
function confirmEmail({what, isRule, link}) {
  const subject = 'Confirm your BayCounty.me alerts';
  const lead = isRule ? `Please confirm you want this BayCounty.me email alert: <b>${esc(what)}</b>. We check every morning and email you only when something new matches.` : `Please confirm you want ${esc(what).replace(/for (.*)$/, 'for <b>$1</b>')}: new votes, data and corrections, plus upcoming meetings.`;
  const html = emailShell(subject, `<p style="margin:0 0 12px 0;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:22px;color:#161B24">${lead}</p>${button(link, 'Confirm my alerts')}<p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:20px;color:#5A6372">The link works for 7 days. If you didn't ask for this, ignore this email and nothing will be sent.</p>`,
    'BayCounty.me puts Bay County, Florida public records in plain view. Built by Flux Labs, Panama City.');
  const text = `Please confirm you want ${isRule ? 'this BayCounty.me alert: ' : ''}${what}.\n\nConfirm: ${link}\n\nThe link works for 7 days. If you didn't ask for this, ignore this email.`;
  return {subject, html, text};
}

// "Email me a link" from the manage page (manage.js).
function manageLinkEmail(link) {
  const subject = 'Manage your BayCounty.me emails';
  return {subject,
    html: emailShell(subject, `<p style="margin:0 0 12px 0;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:22px;color:#161B24">Here’s your link to change what you follow or unsubscribe.</p>${button(link, 'Manage my emails')}`, 'If you didn’t ask for this, you can ignore it.'),
    text: `Change what you follow or unsubscribe: ${link}`};
}

// Admin sign-in link (admin.js).
function adminSignInEmail(link) {
  const subject = 'Sign in to BayCounty.me admin';
  return {subject,
    text: `Sign in to the BayCounty.me admin:\n\n${link}\n\nThe link works once and expires in 15 minutes. If you didn't ask for it, ignore this email.`,
    html: emailShell(subject, `<p style="${P}">Sign in to the BayCounty.me admin:</p>${button(link, 'Sign in')}<p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:20px;color:#5A6372">The link works once and expires in 15 minutes. If you didn't ask for it, ignore this email.</p>`,
      'You’re getting this because someone asked to sign in to the BayCounty.me admin with this address.')};
}

// Weekly digest for one government (digest.js), from one entry of /data/digest.json. Returns null when there's
// nothing new in the last `days` days and no meeting in the next 8, which means no email that week.
// The footer keeps Resend's broadcast placeholders ({{{RESEND_UNSUBSCRIBE_URL}}}, the prefs_token property).
function digestEmail(g, {now = Date.now(), days = 7} = {}) {
  const since = now - days * day, until = now + 8 * day;
  const changes = (g.changes || []).filter(c => Date.parse(c.date + 'T23:59:59-05:00') >= since);
  const meets = (g.meetings || []).filter(m => { const t = Date.parse(m.start); return t >= now - day / 2 && t <= until; });
  if (!changes.length && !meets.length) return null;
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
  const footer = `You're getting this because you signed up for ${esc(g.name)} alerts on BayCounty.me. <a href="{{{RESEND_UNSUBSCRIBE_URL}}}" style="color:#5A6372">Unsubscribe</a> · <a href="${PREFS_LINK_TEMPLATE}" style="color:#5A6372">Change what you follow</a>`;
  text += `\n${page}\n\nChange what you follow: ${PREFS_LINK_TEMPLATE}\nUnsubscribe: {{{RESEND_UNSUBSCRIBE_URL}}}`;
  const subject = `${g.name} this week on BayCounty.me`;
  return {subject, html: emailShell(subject, inner, footer), text, changes: changes.length, meetings: meets.length};
}

module.exports = {confirmEmail, manageLinkEmail, adminSignInEmail, digestEmail};
