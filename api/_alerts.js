// Shared helpers for BayCounty.me email alerts (files starting with _ are not routes).
const crypto = require('crypto');
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
const FROM = process.env.ALERTS_FROM || 'BayCounty.me <hello@baycounty.me>';
const SITE = 'https://baycounty.me';
const b64 = s => Buffer.from(s).toString('base64url');
const sign = s => crypto.createHmac('sha256', process.env.ALERTS_SECRET || '').update(s).digest('base64url');
function makeToken(email, govs) { const body = b64(JSON.stringify({e: email, g: govs, t: Date.now()})); return body + '.' + sign(body); }
function readToken(tok) {
  const [body, sig] = String(tok || '').split('.');
  if (!body || !sig || !process.env.ALERTS_SECRET) return null;
  const want = sign(body);
  if (want.length !== sig.length || !crypto.timingSafeEqual(Buffer.from(want), Buffer.from(sig))) return null;
  try { const p = JSON.parse(Buffer.from(body, 'base64url').toString()); return Date.now() - p.t < 7 * 864e5 ? p : null; } catch (e) { return null; }
}
async function resend(path, method, body, key) {
  const r = await fetch('https://api.resend.com' + path, {method, headers: {Authorization: `Bearer ${key}`, 'Content-Type': 'application/json'}, body: body ? JSON.stringify(body) : undefined});
  let j = null; try { j = await r.json(); } catch (e) {}
  return {ok: r.ok, status: r.status, body: j};
}
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
function emailShell(title, inner, footer) {
  return `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta http-equiv="X-UA-Compatible" content="IE=edge"><title>${esc(title)}</title></head>
<body style="margin:0;padding:0;background-color:#F6F8FB"><table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#F6F8FB" style="background-color:#F6F8FB"><tr><td align="center" style="padding-top:24px;padding-bottom:24px;padding-left:12px;padding-right:12px">
<table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;background-color:#FFFFFF;border:1px solid #E1E6ED" bgcolor="#FFFFFF">
<tr><td style="padding-top:20px;padding-bottom:16px;padding-left:24px;padding-right:24px;border-bottom:1px solid #E1E6ED;font-family:Arial,Helvetica,sans-serif;font-size:20px;line-height:24px;color:#161B24;font-weight:bold">BayCounty<span style="color:#E5564A">.me</span></td></tr>
<tr><td style="padding-top:20px;padding-bottom:8px;padding-left:24px;padding-right:24px;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:22px;color:#161B24">${inner}</td></tr>
<tr><td style="padding-top:16px;padding-bottom:20px;padding-left:24px;padding-right:24px;border-top:1px solid #E1E6ED;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:18px;color:#5A6372">${footer}</td></tr>
</table></td></tr></table></body></html>`;
}
const button = (href, label) => `<table cellpadding="0" cellspacing="0" border="0" style="margin-top:8px;margin-bottom:16px"><tr><td bgcolor="#1E3A76" style="background-color:#1E3A76;border-radius:6px;padding-top:12px;padding-bottom:12px;padding-left:20px;padding-right:20px"><a href="${esc(href)}" style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:18px;color:#FFFFFF;text-decoration:none;font-weight:bold">${esc(label)}</a></td></tr></table>`;
module.exports = {GOVS, ALL_SEGMENT, FROM, SITE, makeToken, readToken, resend, esc, emailShell, button};
