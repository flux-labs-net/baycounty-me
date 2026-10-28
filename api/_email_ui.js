// The one layout every BayCounty.me email uses: the wordmark on the blue-grey ground, a white card with a colored icon
// badge, navy buttons, and a footer under the card. Same colors and type as the site (site/tokens.css).
// Email-safe on purpose: table layout, inline styles, a bulletproof button. Dark mode comes from a small <style> block
// (Apple Mail, iOS Mail and the Outlook apps honor it; Gmail applies its own dark tint and ignores it).
// site/email_ui.py is the Python twin for the agenda watcher and the workflow alerts; api/__tests__/email-ui.test.js
// checks the two give the same HTML. Files starting with _ are not routes.
const SITE = 'https://baycounty.me'; // emails always link to (and load icons from) the live site
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

const F = "Poppins,'Segoe UI',Arial,Helvetica,sans-serif";
const MONO = "'IBM Plex Mono',Consolas,'Courier New',monospace";
// Light values go inline; the class names carry the dark values (see DARK below).
const C = {bg: '#EEF3FA', card: '#FFFFFF', sunken: '#F4F8FC', ink: '#161B24', muted: '#5A6372', faint: '#8A93A1', line: '#DCE4EE',
  link: '#1E3A76', btn: '#1E3A76', btnTx: '#FFFFFF', salmon: '#E5564A', accent: '#B23A2F'};
const TONES = {blue: ['#E6EEF8', '#1E3A76'], teal: ['#E9F5F2', '#1F8A7A'], amber: ['#FDF5E6', '#9A6512'], salmon: ['#FFF1EE', '#B23A2F']};
const TONES_DARK = {blue: ['#1C2A40', '#9DB8EA'], teal: ['#132723', '#4CC2B2'], amber: ['#2A2215', '#FFC36B'], salmon: ['#2A1B1D', '#FF8C82']};
const ICONS = ['alert', 'bell', 'calendar', 'chat', 'check', 'dollar', 'file', 'key', 'lock', 'mail', 'megaphone', 'reply', 'search', 'spark', 'vote'];

// [class, property, dark value]. Background classes also get the Outlook.com [data-ogsb] rule, text ones [data-ogsc].
const DARK = [
  ['bc-bg', 'background-color', '#0E131B'], ['bc-card', 'background-color', '#151C27'], ['bc-sk', 'background-color', '#1B2431'],
  ['bc-btn', 'background-color', '#9DB8EA'], ['bc-ln', 'border-color', '#263142'],
  ['bc-ink', 'color', '#E7ECF3'], ['bc-mu', 'color', '#A1AABA'], ['bc-fa', 'color', '#768092'], ['bc-lk', 'color', '#9DB8EA'],
  ['bc-btx', 'color', '#0E131B'], ['bc-sal', 'color', '#FF8C82'], ['bc-acc', 'color', '#FF8C82'],
  ...Object.entries(TONES_DARK).flatMap(([t, [bg, fg]]) => [[`bc-tb-${t}`, 'background-color', bg], [`bc-tf-${t}`, 'color', fg]]),
];
const darkCss = () => {
  const rules = DARK.map(([c, p, v]) => `.${c}{${p}:${v}!important}`).join('');
  const ogs = DARK.map(([c, p, v]) => `[data-${p === 'color' ? 'ogsc' : 'ogsb'}] .${c}{${p}:${v}!important}`).join('');
  return `@media (prefers-color-scheme:dark){${rules}.bc-l{display:none!important}.bc-d{display:block!important;max-height:none!important;overflow:visible!important}}${ogs}`;
};
const HEAD_CSS = `body{margin:0;padding:0;-webkit-text-size-adjust:100%}a{text-decoration:none}table{border-collapse:separate}` +
  `@media (max-width:620px){.bc-px{padding-left:20px!important;padding-right:20px!important}.bc-h1{font-size:21px!important;line-height:28px!important}.bc-out{padding-left:8px!important;padding-right:8px!important}}` + darkCss();

const iconUrl = (name, tone, dark) => `${SITE}/assets/email/${name}-${tone}${dark ? '-d' : ''}.png`;
// The light icon shows everywhere; dark-mode clients swap in the dark one. Outlook for Windows never sees the dark copy.
function icon(name, tone, size) {
  if (!ICONS.includes(name)) name = 'spark';
  const img = (dark, cls, style) => `<img class="${cls}" src="${iconUrl(name, tone, dark)}" width="${size}" height="${size}" alt="" style="${style}border:0;outline:none;width:${size}px;height:${size}px">`;
  return img(false, 'bc-l', 'display:block;') + `<!--[if !mso]><!-->${img(true, 'bc-d', 'display:none;max-height:0;overflow:hidden;')}<!--<![endif]-->`;
}
const tone = t => (TONES[t] ? t : 'blue');

function p(html, o = {}) {
  return `<p class="${o.muted ? 'bc-mu' : 'bc-ink'}" style="margin:0 0 ${o.mb ?? 14}px 0;font-family:${F};font-size:${o.size || 15}px;line-height:${o.lh || 24}px;color:${o.muted ? C.muted : C.ink}">${html}</p>`;
}
const small = (html, mb = 0) => p(html, {size: 13, lh: 20, muted: true, mb});

function badge(t, ic, size = 48) {
  t = tone(t);
  return `<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td class="bc-tb-${t}" width="${size}" height="${size}" align="center" valign="middle" bgcolor="${TONES[t][0]}" style="width:${size}px;height:${size}px;background-color:${TONES[t][0]};border-radius:${Math.round(size * 0.3)}px">${icon(ic, t, Math.round(size * 0.46))}</td></tr></table>`;
}

function hero({tone: t, icon: ic, eyebrow, title}) {
  return `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>` +
    `<td width="48" valign="top" style="padding:2px 16px 0 0">${badge(t, ic)}</td>` +
    `<td valign="middle">${eyebrow ? `<div class="bc-mu" style="font-family:${F};font-size:11px;line-height:16px;letter-spacing:1px;text-transform:uppercase;font-weight:600;color:${C.muted}">${eyebrow}</div>` : ''}` +
    `<div class="bc-h1 bc-ink" style="font-family:${F};font-size:24px;line-height:31px;font-weight:600;color:${C.ink};margin-top:3px">${title}</div></td></tr></table>`;
}

function section(t, ic, title, count) {
  return `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:10px 0 4px 0"><tr>` +
    `<td width="30" valign="middle" style="padding:0 10px 0 0">${badge(t, ic, 30)}</td>` +
    `<td class="bc-lk" valign="middle" style="font-family:${F};font-size:16px;line-height:22px;font-weight:600;color:${C.link}">${title}${count != null ? ` <span class="bc-fa" style="font-weight:500;color:${C.faint}">${count}</span>` : ''}</td></tr></table>`;
}

const a = (href, label, style = '') => `<a class="bc-lk" href="${esc(href)}" style="color:${C.link};text-decoration:none;${style}">${label}</a>`;
const link = (href, label) => `<a class="bc-lk" href="${esc(href)}" style="color:${C.link};text-decoration:underline">${label}</a>`;
const footLink = (href, label) => `<a class="bc-mu" href="${esc(href)}" style="color:${C.muted};text-decoration:underline">${label}</a>`;

// One record or update: linked title, small meta line, a few lines of text and an optional "→" link.
function item({title, url, meta, text, more, moreUrl}) {
  return `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td class="bc-ln" style="padding:14px 0;border-bottom:1px solid ${C.line}">` +
    `<div style="font-family:${F};font-size:15px;line-height:22px;font-weight:600">${url ? a(url, title) : `<span class="bc-ink" style="color:${C.ink}">${title}</span>`}</div>` +
    (meta ? `<div class="bc-fa" style="font-family:${F};font-size:12px;line-height:18px;color:${C.faint};margin-top:2px">${meta}</div>` : '') +
    (text ? `<div class="bc-mu" style="font-family:${F};font-size:14px;line-height:21px;color:${C.muted};margin-top:6px">${text}</div>` : '') +
    (more && (moreUrl || url) ? `<div style="font-family:${F};font-size:13px;line-height:18px;font-weight:600;margin-top:8px">${a(moreUrl || url, `${more} &rarr;`)}</div>` : '') +
    `</td></tr></table>`;
}

function pill(t, text) {
  t = tone(t);
  return `<span class="bc-tb-${t} bc-tf-${t}" style="display:inline-block;font-family:${F};font-size:12px;line-height:16px;font-weight:600;padding:4px 10px;border-radius:999px;background-color:${TONES[t][0]};color:${TONES[t][1]};white-space:nowrap">${text}</span>`;
}

// A meeting row with a month/day tile. mon/day are already formatted ("OCT", "28").
function meeting({mon, day, title, time, agendaUrl, pending, linkLabel = 'Read the agenda'}) {
  return `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td class="bc-ln" style="padding:12px 0;border-bottom:1px solid ${C.line}">` +
    `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>` +
    `<td width="52" valign="top" style="padding-right:14px"><table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td class="bc-sk" width="52" align="center" bgcolor="${C.sunken}" style="width:52px;background-color:${C.sunken};border-radius:12px;padding:7px 0 8px 0">` +
    `<div class="bc-acc" style="font-family:${F};font-size:11px;line-height:14px;font-weight:600;letter-spacing:1px;color:${C.accent}">${mon}</div>` +
    `<div class="bc-ink" style="font-family:${F};font-size:21px;line-height:24px;font-weight:600;color:${C.ink}">${day}</div></td></tr></table></td>` +
    `<td valign="top"><div class="bc-ink" style="font-family:${F};font-size:15px;line-height:22px;font-weight:600;color:${C.ink}">${title}</div>` +
    (time ? `<div class="bc-mu" style="font-family:${F};font-size:13px;line-height:19px;color:${C.muted};margin-top:2px">${time}</div>` : '') +
    (agendaUrl ? `<div style="margin-top:7px;font-family:${F};font-size:13px;line-height:18px;font-weight:600">${a(agendaUrl, `${linkLabel} &rarr;`)}</div>` : pending ? `<div style="margin-top:7px">${pill('amber', pending)}</div>` : '') +
    `</td></tr></table></td></tr></table>`;
}

function button(href, label, o = {}) {
  return `<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:${o.mt ?? 8}px 0 ${o.mb ?? 18}px 0"><tr><td class="bc-btn" bgcolor="${C.btn}" style="background-color:${C.btn};border-radius:12px;padding:14px 24px">` +
    `<a class="bc-btx" href="${esc(href)}" style="font-family:${F};font-size:15px;line-height:18px;font-weight:600;color:${C.btnTx};text-decoration:none;display:inline-block">${esc(label)}</a></td></tr></table>`;
}

const box = (inner, style) => `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:${style.m}"><tr><td class="bc-sk ${style.cls || ''}" ${style.align ? `align="${style.align}" ` : ''}bgcolor="${C.sunken}" style="background-color:${C.sunken};border-radius:${style.r || 12}px;${style.s}">${inner}</td></tr></table>`;
const note = html => box(html, {m: '6px 0 16px 0', cls: 'bc-mu', s: `padding:13px 16px;font-family:${F};font-size:13px;line-height:20px;color:${C.muted}`});
// Quoted text (a message, a request). Plain text in, escaped here, line breaks kept.
const quote = text => box(esc(text).replace(/\r?\n/g, '<br>'), {m: '2px 0 18px 0', cls: 'bc-ink', s: `padding:16px 18px;font-family:${F};font-size:14px;line-height:22px;color:${C.ink}`});
const code = c => box(esc(c), {m: '4px 0 18px 0', cls: 'bc-ink', align: 'center', r: 14, s: `padding:20px 12px;font-family:${MONO};font-size:34px;line-height:40px;letter-spacing:10px;font-weight:600;color:${C.ink}`});

// Label/value rows. Values are HTML (escape them first).
function facts(rows) {
  return `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:4px 0 16px 0">` + rows.map(([k, v], i) => {
    const top = i ? `border-top:1px solid ${C.line};` : '';
    return `<tr><td class="bc-mu bc-ln" width="110" valign="top" style="padding:9px 12px 9px 0;${top}font-family:${F};font-size:13px;line-height:20px;color:${C.muted}">${k}</td>` +
      `<td class="bc-ink bc-ln" valign="top" style="padding:9px 0;${top}font-family:${F};font-size:14px;line-height:20px;color:${C.ink};word-break:break-word">${v}</td></tr>`;
  }).join('') + `</table>`;
}

// Rows with a status pill: [[tone, label, html], ...].
function list(rows) {
  return `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 16px 0">` + rows.map(([t, label, html]) =>
    `<tr><td class="bc-ln" style="padding:10px 0;border-bottom:1px solid ${C.line}"><table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>` +
    `<td valign="top" style="padding:1px 10px 0 0;white-space:nowrap">${pill(t, label)}</td>` +
    `<td class="bc-ink" valign="top" style="font-family:${F};font-size:14px;line-height:21px;color:${C.ink};word-break:break-word">${html}</td></tr></table></td></tr>`).join('') + `</table>`;
}

const spacer = h => `<div style="height:${h}px;line-height:${h}px;font-size:1px">&nbsp;</div>`;

// Hidden inbox preview text, padded so the client doesn't pull body text in after it.
const preheader = text => text ? `<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;opacity:0">${esc(text)}${'&#8199;&#65279;&#847; '.repeat(40)}</div>` : '';

const ABOUT = 'BayCounty.me puts Bay County, Florida public records in plain view. Built by Flux Labs in Panama City.';

// The whole email. hero: {tone, icon, eyebrow, title} or null (letters). letter: HTML for the in-card footer used by
// correspondence. footer: HTML under the card. kicker: small label right of the wordmark.
function layout({title, preheader: pre, kicker = '', hero: h, body, letter, footer = ABOUT}) {
  const pad = 'padding-left:32px;padding-right:32px';
  return `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="X-UA-Compatible" content="IE=edge">` +
    `<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark"><title>${esc(title)}</title>` +
    `<!--[if !mso]><!--><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&amp;family=IBM+Plex+Mono:wght@600&amp;display=swap"><!--<![endif]-->` +
    `<!--[if mso]><style>*{font-family:'Segoe UI',Arial,sans-serif!important}</style><![endif]-->` +
    `<style>${HEAD_CSS}</style></head>\n` +
    `<body class="bc-bg" style="margin:0;padding:0;background-color:${C.bg}">${preheader(pre)}\n` +
    `<table class="bc-bg" role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="${C.bg}" style="background-color:${C.bg}"><tr><td class="bc-out" align="center" style="padding:28px 16px 32px 16px">\n` +
    `<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px">\n` +
    `<tr><td style="padding:0 6px 14px 6px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>` +
    `<td class="bc-ink" style="font-family:${F};font-size:21px;line-height:26px;font-weight:700;color:${C.ink};letter-spacing:-0.2px"><a class="bc-ink" href="${SITE}" style="color:${C.ink};text-decoration:none">BayCounty<span class="bc-sal" style="color:${C.salmon}">.me</span></a></td>` +
    `<td class="bc-mu" align="right" style="font-family:${F};font-size:12px;line-height:16px;font-weight:500;color:${C.muted}">${kicker}</td></tr></table></td></tr>\n` +
    `<tr><td class="bc-card bc-ln" bgcolor="${C.card}" style="background-color:${C.card};border:1px solid ${C.line};border-radius:20px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">\n` +
    (h ? `<tr><td class="bc-px" style="padding-top:30px;padding-bottom:18px;${pad}">${hero(h)}</td></tr>\n` : '') +
    `<tr><td class="bc-px" style="padding-top:${h ? 0 : 30}px;padding-bottom:${letter ? 14 : 18}px;${pad}">${body}</td></tr>\n` +
    (letter ? `<tr><td class="bc-px bc-ln bc-mu" style="padding-top:16px;padding-bottom:24px;${pad};border-top:1px solid ${C.line};font-family:${F};font-size:12px;line-height:19px;color:${C.muted}">${letter}</td></tr>\n` : '') +
    `</table></td></tr>\n` +
    `<tr><td class="bc-mu" style="padding:18px 6px 0 6px;font-family:${F};font-size:12px;line-height:19px;color:${C.muted}">${footer}</td></tr>\n` +
    `</table></td></tr></table></body></html>`;
}

// Admin notices share a footer.
const adminFooter = (why = 'Admin notice. Sent to BayCounty.me admins only.') => `${why} ${footLink(`${SITE}/admin`, 'Open admin')}`;

// An admin notice: {subject, html, text}. text is the plain-text part (kept as the old text-only emails had it).
function adminNotice({subject, preheader: pre, kicker, tone: t = 'blue', icon: ic = 'bell', eyebrow, title, body, text, footer}) {
  return {subject, text, html: layout({title: subject, preheader: pre, kicker, hero: {tone: t, icon: ic, eyebrow, title}, body, footer: footer || adminFooter()})};
}

module.exports = {adminNotice, SITE, esc, C, F, MONO, TONES, TONES_DARK, ICONS, ABOUT, layout, hero, badge, section, item, pill, meeting, button, note, quote, code,
  facts, list, p, small, a, link, footLink, spacer, preheader, adminFooter, iconUrl, darkCss};
