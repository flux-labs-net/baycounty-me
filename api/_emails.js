// Builders for the emails people get from BayCounty.me. Each returns {subject, html, text} and sends nothing,
// so the routes that send them and the /admin email previews use exactly the same content.
// The rule-alert email is built by compose() in alerts-run.js. Files starting with _ are not routes.
const {SITE, esc, PREFS_LINK_TEMPLATE} = require('./_alerts');
const ui = require('./_email_ui');

const day = 864e5;
const TZ = 'America/Chicago';
const at = d => new Date(d + (d.length === 10 ? 'T12:00:00Z' : ''));
const nice = d => at(d).toLocaleDateString('en-US', {month: 'short', day: 'numeric', timeZone: TZ});
const when = d => d.length > 10 ? at(d).toLocaleString('en-US', {weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: TZ}) : at(d).toLocaleDateString('en-US', {weekday: 'short', month: 'short', day: 'numeric', timeZone: TZ});
const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
// Cuts long text at a sentence (or word) near n characters, so each update stays two or three lines.
function clip(s, n = 220) {
  s = String(s || '').trim();
  if (s.length <= n) return s;
  const cut = s.slice(0, n), dot = cut.lastIndexOf('. ');
  return dot > n * 0.5 ? cut.slice(0, dot + 1) : cut.replace(/\s+\S*$/, '') + '…';
}

// Double opt-in confirmation (subscribe.js). what: plain-text description; isRule: rule alert vs weekly digest.
// govs: government names for a digest sign-up (optional, for the subject line).
function confirmEmail({what, isRule, link, govs}) {
  const names = govs && govs.length ? govs : null;
  const subject = isRule ? 'Confirm your BayCounty.me alert' : names && names.length === 1 ? `Confirm your ${names[0]} weekly updates` : 'Confirm your BayCounty.me weekly updates';
  const tail = ui.small('The link works for 7 days. If you didn’t ask for this, ignore this email and nothing will be sent.');
  const body = isRule
    ? ui.p('Please confirm you want this alert. We check every morning and email you only when something new matches.') +
      ui.facts([['Alert', `<b>${esc(what)}</b>`], ['How often', 'Only when something new matches']]) + ui.button(link, 'Confirm my alert') + tail
    : ui.p(`You asked for weekly BayCounty.me updates for <b>${esc(names ? names.join(', ') : what.replace(/^.*\bfor\s+/, ''))}</b>. Each Monday you’ll get:`) +
      ui.list([['teal', 'New', 'Votes, data and pages added that week'], ['blue', 'Meetings', 'Meetings coming up, with agendas'], ['amber', 'Fixes', 'Corrections to anything we published']]) +
      ui.button(link, 'Confirm my updates') + tail;
  const html = ui.layout({title: subject, preheader: isRule ? `${what}. Tap to start it.` : 'One tap and you’re set. The link works for 7 days.',
    kicker: 'Email alerts', hero: {tone: isRule ? 'teal' : 'blue', icon: 'bell', eyebrow: 'One more step', title: isRule ? 'Confirm your alert' : 'Confirm your weekly updates'}, body});
  const text = `Please confirm you want ${isRule ? 'this BayCounty.me alert: ' : ''}${what}.\n\nConfirm: ${link}\n\nThe link works for 7 days. If you didn't ask for this, ignore this email.`;
  return {subject, html, text};
}

// "Email me a link" from the manage page (manage.js).
function manageLinkEmail(link) {
  const subject = 'Your link to manage BayCounty.me emails';
  return {subject,
    html: ui.layout({title: subject, preheader: 'Change what you follow or unsubscribe.', kicker: 'Email alerts',
      hero: {tone: 'blue', icon: 'mail', eyebrow: 'Your emails', title: 'Change what you follow'},
      body: ui.p('Here’s your link to pick which governments you follow, change your alerts, or unsubscribe from everything.') + ui.button(link, 'Manage my emails') +
        ui.small('If you didn’t ask for this, you can ignore it. Nothing changes until you use the link.')}),
    text: `Change what you follow or unsubscribe: ${link}\n\nIf you didn't ask for this, you can ignore it.`};
}

// Admin sign-in link (admin.js).
function adminSignInEmail(link) {
  const subject = 'Sign in to BayCounty.me admin';
  return {subject,
    text: `Sign in to the BayCounty.me admin:\n\n${link}\n\nThe link works once and expires in 15 minutes. If you didn't ask for it, ignore this email.`,
    html: ui.layout({title: subject, preheader: 'Your sign-in link. It works once and expires in 15 minutes.', kicker: 'Admin',
      hero: {tone: 'blue', icon: 'key', eyebrow: 'Admin', title: 'Sign in to BayCounty.me'},
      body: ui.p('Use this button to sign in to the admin. It works once and expires in 15 minutes.') + ui.button(link, 'Sign in') +
        ui.note('Didn’t ask for this? Ignore this email. Nobody can sign in without the link.'),
      footer: 'You’re getting this because someone asked to sign in to the BayCounty.me admin with this address.'})};
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
  const counts = [changes.length && plural(changes.length, 'update'), meets.length && plural(meets.length, 'meeting')].filter(Boolean);
  const weekOf = new Date(now - 6 * day).toLocaleDateString('en-US', {month: 'short', day: 'numeric', timeZone: TZ});
  let body = '', text = `What's new on BayCounty.me for ${g.name} this week.\n`;
  if (changes.length) {
    body += ui.section('teal', 'spark', 'New and updated', changes.length) +
      changes.map(c => { const t = clip(c.text); return ui.item({title: esc(c.title), url: c.url, meta: esc(nice(c.date)), text: esc(t), more: t !== String(c.text || '').trim() ? 'Read more' : ''}); }).join('');
    text += '\nNEW AND UPDATED\n' + changes.map(c => `- ${c.title} (${nice(c.date)}): ${c.text} ${c.url}`).join('\n') + '\n';
  }
  if (meets.length) {
    body += (changes.length ? ui.spacer(18) : '') + ui.section('salmon', 'calendar', 'Coming up', meets.length) + meets.map(m => {
      const d = at(m.start);
      return ui.meeting({mon: d.toLocaleDateString('en-US', {month: 'short', timeZone: TZ}).toUpperCase(), day: d.toLocaleDateString('en-US', {day: 'numeric', timeZone: TZ}),
        title: esc(m.title), time: esc([when(m.start), m.location].filter(Boolean).join(' · ')), agendaUrl: m.agenda_url, pending: m.agenda_url ? '' : 'Agenda not posted yet'});
    }).join('');
    text += '\nCOMING UP\n' + meets.map(m => `- ${when(m.start)}: ${m.title}${m.agenda_url ? ' ' + m.agenda_url : ''}`).join('\n') + '\n';
  }
  body += ui.button(page, `See ${g.name} on BayCounty.me`, {mt: 22});
  const footer = `You’re getting this because you signed up for ${esc(g.name)} updates on BayCounty.me. ${ui.footLink(PREFS_LINK_TEMPLATE, 'Change what you follow')} · ${ui.footLink('{{{RESEND_UNSUBSCRIBE_URL}}}', 'Unsubscribe')}<br><br>${ui.ABOUT}`;
  text += `\n${page}\n\nChange what you follow: ${PREFS_LINK_TEMPLATE}\nUnsubscribe: {{{RESEND_UNSUBSCRIBE_URL}}}`;
  const subject = `${g.name} this week: ${counts.join(', ')}`;
  const pre = [...changes.slice(0, 2).map(c => c.title), meets[0] && `${meets[0].title} ${nice(meets[0].start)}`].filter(Boolean).join(' · ');
  const html = ui.layout({title: subject, preheader: pre, kicker: `Weekly update · ${nice(new Date(now).toISOString())}`,
    hero: {tone: 'blue', icon: 'calendar', eyebrow: `${esc(g.name)} · Week of ${weekOf}`, title: `${counts.join(' and ').replace(/^./, c => c.toUpperCase())} this week`}, body, footer});
  return {subject, html, text, changes: changes.length, meetings: meets.length};
}

module.exports = {confirmEmail, manageLinkEmail, adminSignInEmail, digestEmail, clip};
