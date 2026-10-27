// BayCounty.me contact form -> email via Resend.
// Env: RESEND_FULL_KEY or RESEND_API_KEY (a key that can send from baycounty.me), CONTACT_TO (default hello@fluxlabs.net), CONTACT_FROM.
const TOPICS = { correction: 'Correction', record: 'Record or tip', question: 'Question', other: 'Something else' };
const {ipOf} = require('./_gate');
const ALLOWED = /^https:\/\/((www\.)?baycounty\.me|[a-z0-9-]+\.vercel\.app)$/;
const hits = new Map(); // best-effort per-instance rate limit

const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const clip = (s, n) => String(s ?? '').trim().slice(0, n);
const ui = require('./_email_ui');
const TONE = { Correction: 'salmon', 'Record or tip': 'teal', Question: 'blue', 'Something else': 'amber' };

// The notice in hello@fluxlabs.net's inbox. Reply-To is the sender, so replying answers them directly.
function contactEmail({topic, name, email, page, message}) {
  const who = name || email || 'someone';
  const pageUrl = /^https?:\/\//.test(page) ? page : '';
  return ui.layout({title: `Contact form: ${topic}`, preheader: `${who}: ${message.slice(0, 120)}`, kicker: 'Contact form',
    hero: {tone: TONE[topic] || 'blue', icon: 'chat', eyebrow: `Contact form · ${esc(topic)}`, title: `New message from ${esc(who)}`},
    body: ui.facts([['Topic', ui.pill(TONE[topic] || 'blue', esc(topic))], ['Name', esc(name || '(not given)')],
        ['Email', email ? ui.a('mailto:' + email, esc(email)) : '(not given)'], ['Page', pageUrl ? ui.a(pageUrl, esc(page.replace(/^https?:\/\/[^/]+/, '') || page)) : esc(page || '(not given)')]]) +
      ui.quote(message) + ui.small(email ? `Reply to this email to answer ${esc(name || email)} directly.` : 'No email address was given, so there’s no way to reply.'),
    footer: ui.adminFooter('Sent from the contact form on BayCounty.me.')});
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return res.status(405).json({ ok: false, error: 'Method not allowed' });
  const origin = req.headers.origin || '';
  if (origin && !ALLOWED.test(origin)) return res.status(403).json({ ok: false, error: 'Forbidden' });

  const ip = ipOf(req);
  const now = Date.now(), recent = (hits.get(ip) || []).filter(t => now - t < 3600e3);
  if (recent.length >= 5) return res.status(429).json({ ok: false, error: 'Too many messages from this connection. Please try again later or email hello@fluxlabs.net.' });

  let b = req.body;
  if (typeof b === 'string') { try { b = JSON.parse(b); } catch { b = {}; } }
  b = b || {};
  // Spam traps: hidden field must be empty; form must have been open at least 3 seconds.
  if (b.website || !b.t || now - Number(b.t) < 3000) return res.status(200).json({ ok: true });

  const name = clip(b.name, 120), email = clip(b.email, 200), page = clip(b.page, 300), message = clip(b.message, 5000);
  const topic = TOPICS[b.topic] || TOPICS.other;
  if (message.length < 10) return res.status(400).json({ ok: false, error: 'Please write a little more in your message.' });
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return res.status(400).json({ ok: false, error: 'That email address doesn’t look right.' });
  if (!(process.env.RESEND_FULL_KEY || process.env.RESEND_API_KEY)) return res.status(500).json({ ok: false, error: 'The form isn’t configured yet. Please email hello@fluxlabs.net.' });

  const rows = [['Topic', topic], ['Name', name || '(not given)'], ['Email', email || '(not given)'], ['Page', page || '(not given)']];
  const html = contactEmail({topic, name, email, page, message});
  const text = rows.map(([k, v]) => `${k}: ${v}`).join('\n') + '\n\n' + message;

  const r = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${process.env.RESEND_FULL_KEY || process.env.RESEND_API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from: process.env.CONTACT_FROM || 'BayCounty.me <hello@baycounty.me>',
      to: [process.env.CONTACT_TO || 'hello@fluxlabs.net'],
      reply_to: email || undefined,
      subject: `[BayCounty.me] ${topic}${page ? ' · ' + page.replace(/^https?:\/\/[^/]+/, '') : ''}`,
      html, text,
    }),
  });
  if (!r.ok) { console.error('resend', r.status, await r.text()); return res.status(502).json({ ok: false, error: 'Your message couldn’t be sent just now. Please try again or email hello@fluxlabs.net.' }); }
  recent.push(now); hits.set(ip, recent);
  return res.status(200).json({ ok: true });
};
module.exports.contactEmail = contactEmail;
