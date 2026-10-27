// Shared helpers for BayCounty.me email alerts (files starting with _ are not routes).
const crypto = require('crypto');
const ui = require('./_email_ui');
const GOVS = {
  county: ['Bay County', 'c9e0b24b-617a-40ee-842f-0c89112299e9'],
  schools: ['Bay District Schools', '29f40586-260f-45fa-9c47-5a703bc5bb75'],
  pc: ['Panama City', 'a117c7c0-6625-4f64-8898-ffaa4133b2d5'],
  pcb: ['Panama City Beach', '59d5eb2a-952c-4536-acc6-a7cb30f19495'],
  lh: ['Lynn Haven', 'e99d7465-3228-4765-8f35-1fe1da2147a0'],
  cw: ['Callaway', '5029df13-2ac4-4279-b997-b3ddb5e05b19'],
  sp: ['Springfield', '77e80d22-80a4-4beb-bc02-04be48a25c08'],
  parker: ['Parker', '43812535-2b28-4afc-b940-4caddd779cec'],
  mb: ['Mexico Beach', 'd629cd98-bffd-49f2-99bb-f519f70594e1'],
};
const ALL_SEGMENT = '1ae0dd54-dba8-4baa-93b2-fc1e1a04a9aa';
// The countywide weekly email ("This week in Bay County", api/weekly.js) has its own list beside the per-government ones.
// LISTS is everything a person can sign up for by key: 'week' plus each government.
const WEEKLY = ['This week in Bay County', process.env.WEEKLY_SEGMENT || 'b85149cc-3e1b-4e07-8df5-61a6ce10c7b1'];
const LISTS = {week: WEEKLY, ...GOVS};
const FROM = process.env.ALERTS_FROM || 'BayCounty.me <hello@baycounty.me>';
const SITE = 'https://baycounty.me';
const b64 = s => Buffer.from(s).toString('base64url');
const sign = s => crypto.createHmac('sha256', process.env.ALERTS_SECRET || '').update(s).digest('base64url');
function makeToken(email, govs, extra = {}) { const body = b64(JSON.stringify({...extra, e: email, g: govs, t: Date.now()})); return body + '.' + sign(body); }
function readToken(tok) {
  const [body, sig] = String(tok || '').split('.');
  if (!body || !sig || !process.env.ALERTS_SECRET) return null;
  const want = sign(body);
  if (want.length !== sig.length || !crypto.timingSafeEqual(Buffer.from(want), Buffer.from(sig))) return null;
  try { const p = JSON.parse(Buffer.from(body, 'base64url').toString()); return Date.now() - p.t < 7 * 864e5 ? p : null; } catch (e) { return null; }
}
async function resend(path, method, body, key) {
  if (path === '/emails' && method === 'POST' && body) body = finishEmail(body);
  const r = await fetch('https://api.resend.com' + path, {method, headers: {Authorization: `Bearer ${key}`, 'Content-Type': 'application/json'}, body: body ? JSON.stringify(body) : undefined});
  let j = null; try { j = await r.json(); } catch (e) {}
  return {ok: r.ok, status: r.status, body: j};
}
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
// Wraps a plain body in the shared email layout (api/_email_ui.js). Builders that want the badge/hero call ui.layout.
function emailShell(title, inner, footer) {
  return ui.layout({title, body: inner, footer: footer || DEFAULT_FOOTER});
}
// Every email leaves as a full HTML document with a plain-text part. Spam filters (Microsoft and Sophos most of all)
// score bare HTML fragments and HTML-only mail as spam-like, so a builder that passes a fragment gets the site shell
// and a footer, and one that passes no text gets text made from its HTML.
const DEFAULT_FOOTER = ui.ABOUT;
function htmlToText(html) {
  return String(html)
    .replace(/<(style|script|head)[^>]*>[\s\S]*?<\/\1>/gi, '')
    .replace(/<a\s[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/gi, (m, href, label) => { const l = label.replace(/<[^>]+>/g, '').trim(); return l && l !== href ? `${l} (${href})` : href; })
    .replace(/<br\s*\/?>/gi, '\n').replace(/<\/(p|div|tr|h[1-6]|li|table)>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;|&rsquo;|&lsquo;/g, "'").replace(/&amp;/g, '&')
    .replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
}
function finishEmail(body) {
  const out = {...body};
  if (out.html && !/<html[\s>]/i.test(out.html)) out.html = emailShell(out.subject || 'BayCounty.me', out.html, DEFAULT_FOOTER);
  if (!out.text && out.html) out.text = htmlToText(out.html);
  return out;
}
const button = (href, label) => ui.button(href, label);

// Sign-up forms must be posted from this site. Requires an Origin header from an allowed origin, or (for browsers
// that leave Origin off) a Referer on an allowed origin. A request with neither is refused.
const ALLOWED_ORIGIN = /^https:\/\/((www\.)?baycounty\.me|[a-z0-9-]+\.vercel\.app)$/;
function sameOrigin(req) {
  const h = req.headers || {};
  if (h.origin) return ALLOWED_ORIGIN.test(String(h.origin));
  try { return !!h.referer && ALLOWED_ORIGIN.test(new URL(String(h.referer)).origin); } catch (e) { return false; }
}

// Per-address cooldown for confirmation emails: at most one per address every 10 minutes.
// Uses the database (alerts.claim_confirm_send, migration 0007) so it holds across server instances. If the database
// isn't configured or the migration isn't applied, falls back to a per-instance memory map (best effort only:
// each Vercel instance keeps its own, and it resets when the instance is recycled).
const COOLDOWN_MIN = 10;
const emailHash = email => crypto.createHmac('sha256', 'bcm-email-v1:' + (process.env.ALERTS_SECRET || '')).update(String(email).toLowerCase()).digest('hex').slice(0, 32);
const memSends = new Map();
async function claimConfirmSend(email) {
  const h = emailHash(email);
  try {
    const db = require('./_db');
    if (db.hasDb()) return (await db.q('select alerts.claim_confirm_send($1, $2) as ok', [h, COOLDOWN_MIN]))[0].ok;
  } catch (e) { console.error('cooldown: database unavailable, using memory', e.message); }
  const now = Date.now(), last = memSends.get(h);
  if (last && now - last < COOLDOWN_MIN * 60e3) return false;
  memSends.set(h, now);
  return true;
}

// Signed link for managing preferences (no expiry, but tied to the address and the secret). Kind 'prefs'.
function prefsToken(email) { const body = b64(JSON.stringify({k: 'prefs', e: String(email).toLowerCase()})); return body + '.' + sign('prefs.' + body); }
function readPrefsToken(tok) {
  const [body, sig] = String(tok || '').split('.');
  if (!body || !sig || !process.env.ALERTS_SECRET) return null;
  const want = sign('prefs.' + body);
  if (want.length !== sig.length || !crypto.timingSafeEqual(Buffer.from(want), Buffer.from(sig))) return null;
  try { const p = JSON.parse(Buffer.from(body, 'base64url').toString()); return p.k === 'prefs' && p.e ? p : null; } catch (e) { return null; }
}
const prefsUrl = email => `${SITE}/alerts/manage?t=${prefsToken(email)}`;

// Digest broadcasts go to a whole segment, so the per-person manage link comes from a Resend contact property:
// prefs_token holds each contact's prefsToken, and the digest links to /alerts/manage?t={{{contact.prefs_token|none}}}.
// A contact without the property gets "none", which the manage page answers with an "email me a link" form.
const PREFS_PROP = 'prefs_token';
const PREFS_LINK_TEMPLATE = `${SITE}/alerts/manage?t={{{contact.${PREFS_PROP}|none}}}`;
let propReady = false;
async function ensurePrefsProperty(key) {
  if (propReady) return;
  const r = await resend('/contact-properties', 'POST', {key: PREFS_PROP, type: 'string', fallback_value: 'none'}, key);
  if (r.ok || r.status === 409 || r.status === 422) propReady = true; // created, or it already exists
}
// Best effort: a failure here never stops a sign-up (the manage page has the email-a-link fallback).
async function setPrefsProperty(email, key) {
  try {
    await ensurePrefsProperty(key);
    const r = await resend(`/contacts/${encodeURIComponent(email)}`, 'PATCH', {properties: {[PREFS_PROP]: prefsToken(email)}}, key);
    if (!r.ok) console.error('prefs property', r.status, JSON.stringify(r.body));
    return r.ok;
  } catch (e) { console.error('prefs property', e.message); return false; }
}

// Small HTML page in the site's style, for pages served by functions (confirm, manage).
function page(title, body) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>${esc(title)} · BayCounty.me</title><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600&display=swap"><link rel="stylesheet" href="/assets/site.css">
<style>body{display:block}.b{max-width:520px;margin:10vh auto 40px;padding:24px;background:var(--surface);border:1px solid var(--line);border-radius:12px}h1{font:600 1.2rem var(--f-display);margin:0 0 8px}h2{font:600 1rem var(--f-display);margin:22px 0 8px}p{color:var(--muted);margin:0 0 16px}button,a.btn{display:inline-flex;min-height:40px;align-items:center;padding:0 18px;border-radius:8px;border:0;background:var(--navy);color:var(--bg);font:500 .95rem var(--f-body);cursor:pointer;text-decoration:none}button.plain{background:none;color:var(--blue);padding:0;min-height:0;text-decoration:underline}.opts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:0 0 16px}.opts label{display:flex;gap:8px;align-items:center;padding:8px 10px;border:1px solid var(--line);border-radius:10px;font-size:.9rem}ul.r{list-style:none;padding:0;margin:0 0 16px}ul.r li{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--line);font-size:.92rem}input[type=email]{width:100%;min-height:40px;padding:0 10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);font:inherit;margin:0 0 12px;box-sizing:border-box}.note{padding:10px 12px;border:1px solid var(--line);border-radius:10px;margin:0 0 16px;color:var(--ink)}@media (max-width:480px){.opts{grid-template-columns:minmax(0,1fr)}.b{margin-top:24px}}</style></head>
<body><div class="b">${body}</div></body></html>`;
}

module.exports = {GOVS, WEEKLY, LISTS, ALL_SEGMENT, FROM, SITE, makeToken, readToken, resend, finishEmail, htmlToText, esc, emailShell, button,
  sameOrigin, claimConfirmSend, emailHash, prefsToken, readPrefsToken, prefsUrl, COOLDOWN_MIN,
  PREFS_PROP, PREFS_LINK_TEMPLATE, ensurePrefsProperty, setPrefsProperty, page};
