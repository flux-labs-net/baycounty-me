// Builders for the emails people get from BayCounty.me. Each returns {subject, html, text} and sends nothing,
// so the routes that send them and the /admin email previews use exactly the same content.
// The rule-alert email is built by compose() in alerts-run.js. Files starting with _ are not routes.
const {SITE, esc, PREFS_LINK_TEMPLATE, WEEKLY} = require('./_alerts');
const WEEKLY_NAME = WEEKLY[0];
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
  const weeklyOnly = !isRule && names && names.length === 1 && names[0] === WEEKLY_NAME;
  const subject = isRule ? 'Confirm your BayCounty.me alert' : weeklyOnly ? `Confirm your ${WEEKLY_NAME} email` : names && names.length === 1 ? `Confirm your ${names[0]} weekly updates` : 'Confirm your BayCounty.me weekly updates';
  const tail = ui.small('The link works for 7 days. If you didn’t ask for this, ignore this email and nothing will be sent.');
  const body = isRule
    ? ui.p('Please confirm you want this alert. We check every morning and email you only when something new matches.') +
      ui.facts([['Alert', `<b>${esc(what)}</b>`], ['How often', 'Only when something new matches']]) + ui.button(link, 'Confirm my alert') + tail
    : weeklyOnly ? ui.p(`You asked for <b>${WEEKLY_NAME}</b>. Each Monday morning you’ll get one short email with:`) +
      ui.list([['salmon', 'Events', 'What’s happening around the county that week'], ['blue', 'Meetings', 'Public meetings, with agendas'], ['teal', 'Votes', 'New votes, split votes and failed motions first'], ['amber', 'Contracts', 'New contracts and change orders, biggest first']]) +
      ui.button(link, 'Confirm my email') + tail
    : ui.p(`You asked for weekly BayCounty.me updates for <b>${esc(names ? names.join(', ') : what.replace(/^.*\bfor\s+/, ''))}</b>. Each Monday you’ll get:`) +
      ui.list([['teal', 'New', 'Votes, data and pages added that week'], ['blue', 'Meetings', 'Meetings coming up, with agendas'], ['amber', 'Fixes', 'Corrections to anything we published']]) +
      ui.button(link, 'Confirm my updates') + tail;
  const html = ui.layout({title: subject, preheader: isRule ? `${what}. Tap to start it.` : 'One tap and you’re set. The link works for 7 days.',
    kicker: 'Email alerts', hero: {tone: isRule ? 'teal' : 'blue', icon: 'bell', eyebrow: 'One more step', title: isRule ? 'Confirm your alert' : weeklyOnly ? 'Confirm your weekly email' : 'Confirm your weekly updates'}, body});
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

function realtorSignInEmail(link, minutes = 20) {
  const subject = 'Your BayCounty.me realtor console sign-in link';
  return {subject,
    text: `Sign in to the BayCounty.me realtor console:\n\n${link}\n\nThe link works once and expires in ${minutes} minutes. If you didn't ask for it, ignore this email.`,
    html: ui.layout({title: subject, preheader: `Your sign-in link. It works once and expires in ${minutes} minutes.`, kicker: 'Realtor console',
      hero: {tone: 'blue', icon: 'key', eyebrow: 'Realtor console', title: 'Sign in to run address reports'},
      body: ui.p(`Use this button to sign in. It works once and expires in ${minutes} minutes.`) + ui.button(link, 'Sign in') +
        ui.note('Didn’t ask for this? Ignore this email. Nobody can sign in without the link.'),
      footer: 'You’re getting this because someone asked to sign in to the BayCounty.me realtor console with this address.'})};
}

// A property report an agent emails from the realtor console (_realtor.js action=email). It goes out from
// hello@baycounty.me under the agent's name with Reply-To set to the agent; the PDF is attached by the caller.
// agent: {name, title, brokerage, phone, email}; message: the agent's own note (plain text), optional.
function realtorReportEmail({agent, address, message, preparedFor}) {
  const who = agent.name || agent.email;
  const subject = `Property report: ${address}`;
  const facts = [['Prepared by', esc(who) + (agent.title ? `, ${esc(agent.title)}` : '')], agent.brokerage && ['Brokerage', esc(agent.brokerage)],
    agent.phone && ['Phone', esc(agent.phone)], ['Email', esc(agent.email)], preparedFor && ['Prepared for', esc(preparedFor)]].filter(Boolean);
  const intro = message ? ui.quote(message) : ui.p(`${esc(who)} sent you a property report for <b>${esc(address)}</b>.`);
  const html = ui.layout({title: subject, preheader: `${who} sent you a property report for ${address}. The PDF is attached.`, kicker: 'Property report',
    hero: {tone: 'blue', icon: 'file', eyebrow: agent.brokerage ? `${who} · ${agent.brokerage}` : who, title: address},
    body: intro + ui.facts(facts) + ui.note(`The full report is attached as a PDF. Reply to this email to reach ${esc(who)}.`),
    footer: `${esc(who)} sent this report from the BayCounty.me realtor console. BayCounty.me compiles Bay County public records and isn’t part of any sale. Replies go to ${esc(who)}, not to BayCounty.me.`});
  const text = [message || `${who} sent you a property report for ${address}.`, '',
    ...facts.map(([k, v]) => `${k}: ${v.replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>')}`), '',
    `The full report is attached as a PDF. Reply to this email to reach ${who}.`, '',
    `${who} sent this report from the BayCounty.me realtor console. BayCounty.me compiles Bay County public records and isn't part of any sale.`].join('\n');
  return {subject, html, text};
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

// This week in Bay County (weekly.js), from /data/weekly.json (site/weekly.py; the same rows as the weekly-roundup
// dataset and /this-week). Shows the featured rows of each section: events this week, public meetings this week, and
// votes and contracts first seen on the site last week. Returns null when the edition has nothing in it.
// The footer keeps Resend's broadcast placeholders, like the per-government digest.
const money = n => { const a = Math.abs(n); return (n < 0 ? '-' : '') + (a >= 1e6 ? `$${(a / 1e6).toFixed(1).replace(/\.0$/, '')} million` : `$${Math.round(a).toLocaleString('en-US')}`); };
// event times without an offset are local (Central); October to early November is CDT, the rest of the year CST
const local = s => new Date(/[zZ]|[+-]\d\d:\d\d$/.test(s) ? s : s + (isCdt(s) ? '-05:00' : '-06:00'));
function isCdt(s) { // US daylight time: second Sunday of March to first Sunday of November
  const d = new Date(s.slice(0, 10) + 'T12:00:00Z'), y = d.getUTCFullYear();
  const nth = (m, k) => { const f = new Date(Date.UTC(y, m, 1)); return new Date(Date.UTC(y, m, 1 + ((7 - f.getUTCDay()) % 7) + 7 * (k - 1))); };
  return d >= nth(2, 2) && d < nth(10, 1);
}
function weeklyEmail(ed) {
  const rows = (ed && ed.rows) || [];
  const all = s => rows.filter(r => s.includes(r.section)), feat = s => all(s).filter(r => r.featured);
  const byStart = (a, b) => local(a.starts) - local(b.starts);
  const ev = feat(['event']).sort(byStart), mt = feat(['meeting']), vt = feat(['vote']), ct = feat(['contract', 'change_order']);
  const n = {ev: all(['event']).length, mt: all(['meeting']).length, vt: all(['vote']).length, ct: all(['contract', 'change_order']).length};
  if (!ev.length && !mt.length && !vt.length && !ct.length) return null;
  const weekOf = at(ed.week_of).toLocaleDateString('en-US', {month: 'long', day: 'numeric', timeZone: TZ});
  const page = `${SITE}/this-week`;
  const tile = (r, o) => { const d = local(r.starts); return ui.meeting({mon: d.toLocaleDateString('en-US', {month: 'short', timeZone: TZ}).toUpperCase(), day: d.toLocaleDateString('en-US', {day: 'numeric', timeZone: TZ}), ...o}); };
  const time = r => r.all_day ? local(r.starts).toLocaleDateString('en-US', {weekday: 'short', timeZone: TZ}) + ' · All day'
    : local(r.starts).toLocaleString('en-US', {weekday: 'short', hour: 'numeric', minute: '2-digit', timeZone: TZ}).replace(':00', '');
  const more = (shown, total, href, label) => total > shown ? ui.p(ui.a(href, `${label} (${total}) &rarr;`), {size: 13, lh: 18, mb: 6}) : '';
  const place = v => v && v.includes('; ') ? v.split('; ').pop() : v; // "Venue not stated...; City offices: ..." -> the address
  const nameLink = (url, name) => url ? ui.a(url, esc(name)) : esc(name);
  let body = '', text = `${WEEKLY_NAME}, week of ${weekOf}.\n`;
  const sec = (tone, icon, title, count) => (body ? ui.spacer(18) : '') + ui.section(tone, icon, title, count);
  if (ev.length) {
    body += sec('salmon', 'calendar', 'Happening this week', n.ev) + ev.map(r => tile(r, {title: esc(r.title), time: esc([time(r), r.venue, r.town].filter(Boolean).join(' · ')), agendaUrl: r.url, linkLabel: 'Details'})).join('') +
      more(ev.length, n.ev, `${SITE}/events`, 'Every event this week');
    text += '\nHAPPENING THIS WEEK\n' + ev.map(r => `- ${time(r)}: ${r.title}${r.venue ? ', ' + r.venue : ''}${r.town ? ', ' + r.town : ''} ${r.url || ''}`).join('\n') + '\n';
  }
  if (mt.length) {
    body += sec('blue', 'megaphone', 'Public meetings', n.mt) + mt.map(r => tile(r, {title: esc(r.title), time: esc([time(r), place(r.venue)].filter(Boolean).join(' · ')), agendaUrl: r.agenda_posted ? r.url : '', pending: r.agenda_posted ? '' : 'Agenda not posted yet'})).join('') +
      more(mt.length, n.mt, `${SITE}/meetings`, 'All meetings');
    text += '\nPUBLIC MEETINGS\n' + mt.map(r => `- ${time(r)}: ${r.title}${r.agenda_posted ? ' ' + r.url : ' (agenda not posted yet)'}`).join('\n') + '\n';
  }
  if (vt.length) {
    body += sec('teal', 'vote', 'New votes', n.vt) + vt.map(r => {
      const result = [r.outcome && !/not yet|unclear/.test(r.outcome) && r.outcome[0].toUpperCase() + r.outcome.slice(1), r.tally && r.tally !== 'not found' ? r.tally : ''].filter(Boolean).join(' ');
      const no = (r.people || []).length ? `${r.summary ? '<br>' : ''}<span style="font-size:13px">Voted no: ${r.people.map(p => nameLink(p.url, p.name)).join(', ')}</span>` : '';
      const sum = r.summary && r.summary !== r.title ? esc(clip(r.summary, 180)) : '';
      return ui.item({title: esc(r.title), url: r.url, meta: esc([r.government || r.board, nice(r.date), result].filter(Boolean).join(' · ')), text: sum + no});
    }).join('') + more(vt.length, n.vt, page + '#votes', 'All new votes');
    text += '\nNEW VOTES\n' + vt.map(r => `- ${r.title} (${r.government || r.board}, ${nice(r.date)}${r.tally && r.tally !== 'not found' ? ', ' + r.tally : ''})${r.voted_no ? ' Voted no: ' + r.voted_no + '.' : ''} ${r.url}`).join('\n') + '\n';
  }
  if (ct.length) {
    body += sec('amber', 'dollar', 'New contracts', n.ct) + ct.map(r => {
      const kind = r.section === 'change_order' ? 'Change order' : 'Contract';
      return ui.item({title: `${money(r.amount || 0)} · ${esc(r.title || 'Vendor not named')}`, url: r.vendor_url || r.url,
        meta: esc([kind, r.government, nice(r.date)].filter(Boolean).join(' · ')), text: esc(clip(r.summary || '', 180)), more: r.source_url ? 'Source' : '', moreUrl: r.source_url});
    }).join('') + more(ct.length, n.ct, page + '#contracts', 'All new contracts');
    text += '\nNEW CONTRACTS\n' + ct.map(r => `- ${money(r.amount || 0)} ${r.title || 'Vendor not named'} (${r.section === 'change_order' ? 'change order, ' : ''}${r.government}, ${nice(r.date)}): ${r.summary || ''} ${r.vendor_url || r.url}`).join('\n') + '\n';
  }
  body += ui.button(page, 'See the whole week on BayCounty.me', {mt: 22});
  const footer = `You’re getting this because you signed up for ${WEEKLY_NAME} on BayCounty.me. ${ui.footLink(PREFS_LINK_TEMPLATE, 'Change what you get')} · ${ui.footLink('{{{RESEND_UNSUBSCRIBE_URL}}}', 'Unsubscribe')}<br><br>${ui.ABOUT}`;
  text += `\n${page}\n\nChange what you get: ${PREFS_LINK_TEMPLATE}\nUnsubscribe: {{{RESEND_UNSUBSCRIBE_URL}}}`;
  const counts = [n.ev && plural(n.ev, 'event'), n.vt && plural(n.vt, 'new vote'), n.ct && plural(n.ct, 'new contract')].filter(Boolean);
  const subject = `${WEEKLY_NAME}: ${counts.join(', ') || plural(n.mt, 'public meeting')}`;
  const pre = [vt[0] && vt[0].title, ct[0] && `${money(ct[0].amount || 0)} ${ct[0].title}`, ev[0] && ev[0].title].filter(Boolean).join(' · ');
  const html = ui.layout({title: subject, preheader: pre, kicker: `Weekly email · ${nice(ed.week_of)}`,
    hero: {tone: 'blue', icon: 'calendar', eyebrow: `Week of ${weekOf}`, title: WEEKLY_NAME}, body, footer});
  return {subject, html, text, counts: n};
}

module.exports = {confirmEmail, manageLinkEmail, adminSignInEmail, realtorSignInEmail, realtorReportEmail, digestEmail, weeklyEmail, clip};
