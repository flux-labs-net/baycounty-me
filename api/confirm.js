// Confirms an email alert sign-up (double opt-in).
//   GET  /api/confirm?t=...  shows a page with a "Confirm" button. Nothing changes on GET, because email security
//                            scanners (Microsoft Defender Safe Links and others) open links before people do.
//   POST /api/confirm (t)    does the work, then redirects to /alerts with a status.
// Token kinds: weekly digest sign-ups (no kind, from subscribe.js) and rule alerts (kind 'rule', see _rules.js).
const {GOVS, ALL_SEGMENT, readToken, resend, esc} = require('./_alerts');

function page(title, body) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>${esc(title)} · BayCounty.me</title><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600&display=swap"><link rel="stylesheet" href="/assets/site.css">
<style>body{display:block}.b{max-width:440px;margin:14vh auto 0;padding:24px;background:var(--surface);border:1px solid var(--line);border-radius:12px}h1{font:600 1.2rem var(--f-display);margin:0 0 8px}p{color:var(--muted);margin:0 0 16px}button,a.btn{display:inline-flex;min-height:40px;align-items:center;padding:0 18px;border-radius:8px;border:0;background:var(--navy);color:#fff;font:500 .95rem var(--f-body);cursor:pointer;text-decoration:none}</style></head>
<body><div class="b">${body}</div></body></html>`;
}

async function confirmDigest(p, key) {
  const segs = [ALL_SEGMENT, ...p.g.filter(g => GOVS[g]).map(g => GOVS[g][1])];
  let r = await resend('/contacts', 'POST', {email: p.e, unsubscribed: false, segments: segs.map(id => ({id}))}, key);
  if (!r.ok) { // already a contact: re-subscribe and add to each list
    await resend(`/contacts/${encodeURIComponent(p.e)}`, 'PATCH', {unsubscribed: false}, key);
    const adds = await Promise.all(segs.map(id => resend(`/contacts/${encodeURIComponent(p.e)}/segments/${id}`, 'POST', null, key)));
    r = {ok: adds.some(a => a.ok) || adds.every(a => a.status === 409 || a.status === 422)};
    if (!r.ok) console.error('confirm add', adds.map(a => a.status + ' ' + JSON.stringify(a.body)).join(' | '));
  }
  return r.ok ? `/alerts?status=confirmed&g=${p.g.join(',')}` : '/alerts?status=error';
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('X-Robots-Tag', 'noindex');
  if (req.method === 'GET') {
    const raw = (req.query && (req.query.t || req.query['amp;t'])) || '';
    const p = readToken(raw);
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    if (!p) return res.status(200).send(page('Link expired', `<h1>This link has expired</h1><p>Confirmation links last 7 days. Sign up again and we'll send a new one.</p><a class="btn" href="/alerts">Back to alerts</a>`));
    const tokAttr = String(raw).replace(/[^A-Za-z0-9._-]/g, '');
    const what = p.kind === 'rule' ? 'this alert' : `weekly updates for ${esc(p.g.filter(g => GOVS[g]).map(g => GOVS[g][0]).join(', '))}`;
    return res.status(200).send(page('Confirm your alerts', `<h1>Confirm your BayCounty.me alerts</h1><p>Press the button to start getting ${what} at ${esc(p.e)}.</p>
<form method="post" action="/api/confirm"><input type="hidden" name="t" value="${tokAttr}"><button type="submit" autofocus>Confirm</button></form>`));
  }
  if (req.method !== 'POST') return res.status(405).json({ok: false, error: 'Method not allowed'});
  const b = typeof req.body === 'string' ? Object.fromEntries(new URLSearchParams(req.body)) : req.body || {};
  const go = loc => { res.setHeader('Location', loc); return res.status(303).end(); };
  const p = readToken(b.t);
  if (!p) return go('/alerts?status=expired');
  if (p.kind === 'rule') {
    try { return go(await require('./_rules').confirmRule(p)); }
    catch (e) { console.error('confirm rule', e.message); return go('/alerts?status=error'); }
  }
  const key = process.env.RESEND_FULL_KEY;
  if (!key) return go('/alerts?status=error');
  return go(await confirmDigest(p, key));
};
