// POST /api/subscribe {email, govs:[...]} -> sends a confirmation link (double opt-in).
const {GOVS, FROM, SITE, makeToken, resend, esc, emailShell, button} = require('./_alerts');
const ALLOWED = /^https:\/\/((www\.)?baycounty\.me|[a-z0-9-]+\.vercel\.app)$/;
const hits = new Map();
module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'GET') return res.status(200).json({ready: !!(process.env.ALERTS_SECRET && process.env.RESEND_FULL_KEY)});
  if (req.method !== 'POST') return res.status(405).json({ok: false, error: 'Method not allowed'});
  const origin = req.headers.origin || '';
  if (origin && !ALLOWED.test(origin)) return res.status(403).json({ok: false, error: 'Forbidden'});
  const ip = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim() || 'unknown', now = Date.now();
  const recent = (hits.get(ip) || []).filter(t => now - t < 3600e3);
  if (recent.length >= 5) return res.status(429).json({ok: false, error: 'Too many sign-ups from this connection. Try again later.'});
  let b = req.body; if (typeof b === 'string') { try { b = JSON.parse(b); } catch (e) { b = {}; } } b = b || {};
  if (b.website || !b.t || now - Number(b.t) < 2000) return res.status(200).json({ok: true});
  const email = String(b.email || '').trim().toLowerCase().slice(0, 200);
  const govs = [...new Set((Array.isArray(b.govs) ? b.govs : []).filter(g => GOVS[g]))];
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return res.status(400).json({ok: false, error: 'Please enter a valid email address.'});
  if (!govs.length) return res.status(400).json({ok: false, error: 'Pick at least one government to follow.'});
  if (!(process.env.RESEND_FULL_KEY || process.env.RESEND_API_KEY) || !process.env.ALERTS_SECRET) return res.status(500).json({ok: false, error: 'Alerts aren’t set up yet. Please try again soon.'});
  const link = `${SITE}/api/confirm?t=${makeToken(email, govs)}`;
  const names = govs.map(g => GOVS[g][0]).join(', ');
  const html = emailShell('Confirm your BayCounty.me alerts', `<p style="margin:0 0 12px 0;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:22px;color:#161B24">Please confirm you want weekly BayCounty.me updates for <b>${esc(names)}</b>: new votes, data and corrections, plus upcoming meetings.</p>${button(link, 'Confirm my alerts')}<p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:20px;color:#5A6372">The link works for 7 days. If you didn't ask for this, ignore this email and nothing will be sent.</p>`,
    'BayCounty.me puts Bay County, Florida public records in plain view. Built by Flux Labs, Panama City.');
  const text = `Please confirm you want weekly BayCounty.me updates for ${names}.\n\nConfirm: ${link}\n\nThe link works for 7 days. If you didn't ask for this, ignore this email.`;
  const r = await resend('/emails', 'POST', {from: FROM, to: [email], subject: 'Confirm your BayCounty.me alerts', html, text}, (process.env.RESEND_FULL_KEY || process.env.RESEND_API_KEY));
  if (!r.ok) { console.error('confirm send', r.status, JSON.stringify(r.body)); return res.status(502).json({ok: false, error: 'We couldn’t send the confirmation email. Please try again.'}); }
  recent.push(now); hits.set(ip, recent);
  return res.status(200).json({ok: true});
};
