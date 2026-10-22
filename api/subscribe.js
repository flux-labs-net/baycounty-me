// POST /api/subscribe {email, govs:[...]} or {email, rule: {type, params}} -> sends a confirmation link (double opt-in).
// Guards: same-origin Origin (or Referer) required; honeypot + fill time; 5 sign-ups/hour per connection (per instance);
// at most one confirmation email per address every 10 minutes (database-backed, see _alerts.claimConfirmSend).
const {GOVS, FROM, SITE, makeToken, resend, sameOrigin, claimConfirmSend} = require('./_alerts');
const {ipOf} = require('./_gate');
const hits = new Map();
module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'GET') return res.status(200).json({ready: !!(process.env.ALERTS_SECRET && process.env.RESEND_FULL_KEY)});
  if (req.method !== 'POST') return res.status(405).json({ok: false, error: 'Method not allowed'});
  if (!sameOrigin(req)) return res.status(403).json({ok: false, error: 'Forbidden'});
  const ip = ipOf(req), now = Date.now();
  const recent = (hits.get(ip) || []).filter(t => now - t < 3600e3);
  if (recent.length >= 5) return res.status(429).json({ok: false, error: 'Too many sign-ups from this connection. Try again later.'});
  let b = req.body; if (typeof b === 'string') { try { b = JSON.parse(b); } catch (e) { b = {}; } } b = b || {};
  if (b.website || !b.t || now - Number(b.t) < 2000) return res.status(200).json({ok: true});
  const email = String(b.email || '').trim().toLowerCase().slice(0, 200);
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return res.status(400).json({ok: false, error: 'Please enter a valid email address.'});
  // Two kinds of sign-up: weekly digests ({govs}) or one rule alert ({rule: {type, params}}, see _rules.js).
  let tok, what;
  if (b.rule) {
    const {validate, describe} = require('./_rules');
    const v = validate(b.rule.type, b.rule.params || {});
    if (!v.ok) return res.status(400).json({ok: false, error: v.error});
    if (!require('./_db').hasDb()) return res.status(500).json({ok: false, error: 'Alerts aren’t set up yet. Please try again soon.'});
    tok = () => makeToken(email, [], {kind: 'rule', r: v.type, p: v.params});
    what = describe(v.type, v.params);
  } else {
    const govs = [...new Set((Array.isArray(b.govs) ? b.govs : []).filter(g => GOVS[g]))];
    if (!govs.length) return res.status(400).json({ok: false, error: 'Pick at least one government to follow.'});
    tok = () => makeToken(email, govs);
    what = 'weekly BayCounty.me updates for ' + govs.map(g => GOVS[g][0]).join(', ');
  }
  if (!(process.env.RESEND_FULL_KEY || process.env.RESEND_API_KEY) || !process.env.ALERTS_SECRET) return res.status(500).json({ok: false, error: 'Alerts aren’t set up yet. Please try again soon.'});
  // Cooldown: answer the same way whether or not an email goes out, so the form can't be used to probe addresses.
  if (!(await claimConfirmSend(email))) { recent.push(now); hits.set(ip, recent); return res.status(200).json({ok: true}); }
  const link = `${SITE}/api/confirm?t=${tok()}`;
  const {subject, html, text} = require('./_emails').confirmEmail({what, isRule: !!b.rule, link});
  const r = await resend('/emails', 'POST', {from: FROM, to: [email], subject, html, text}, (process.env.RESEND_FULL_KEY || process.env.RESEND_API_KEY));
  if (!r.ok) { console.error('confirm send', r.status, JSON.stringify(r.body)); return res.status(502).json({ok: false, error: 'We couldn’t send the confirmation email. Please try again.'}); }
  recent.push(now); hits.set(ip, recent);
  return res.status(200).json({ok: true});
};
