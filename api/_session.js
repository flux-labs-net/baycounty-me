// Admin sign-in session shared by /api/admin and /api/finance: a signed, HttpOnly, SameSite=Strict cookie
// issued after an emailed link to an address in ADMIN_EMAILS (see api/admin.js).
const crypto = require('crypto');
const {derive} = require('./_gate');

const COOKIE = 'bcm_admin';
const SESSION_HOURS = 12;
const b64 = s => Buffer.from(s).toString('base64url');
const sign = s => crypto.createHmac('sha256', derive('bcm-admin-v1')).update(s).digest('base64url');
const admins = () => String(process.env.ADMIN_EMAILS || '').toLowerCase().split(/[\s,]+/).filter(Boolean);

function makeToken(obj) { const body = b64(JSON.stringify(obj)); return body + '.' + sign(body); }
function readToken(tok) {
  const [body, sig] = String(tok || '').split('.');
  if (!body || !sig || !process.env.ALERTS_SECRET) return null;
  const want = sign(body);
  if (want.length !== sig.length || !crypto.timingSafeEqual(Buffer.from(want), Buffer.from(sig))) return null;
  try { const p = JSON.parse(Buffer.from(body, 'base64url').toString()); return p.exp > Date.now() ? p : null; } catch (e) { return null; }
}
function cookies(req) {
  return Object.fromEntries(String(req.headers.cookie || '').split(';').map(c => c.trim().split('=')).filter(x => x[0]).map(([k, ...v]) => [k, decodeURIComponent(v.join('='))]));
}
function session(req) {
  const s = readToken(cookies(req)[COOKIE]);
  return s && s.kind === 'session' && admins().includes(s.e) ? s : null;
}
const setCookie = (res, val, maxAge) => res.setHeader('Set-Cookie', `${COOKIE}=${val}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=${maxAge}`);


module.exports = {COOKIE, SESSION_HOURS, b64, sign, admins, makeToken, readToken, cookies, session, setCookie};
