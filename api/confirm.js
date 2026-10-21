// GET /api/confirm?t=... -> adds the contact to the chosen governments' lists, then shows /alerts.
const {GOVS, ALL_SEGMENT, readToken, resend} = require('./_alerts');
module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  const p = readToken(req.query && req.query.t);
  if (!p) { res.writeHead(302, {Location: '/alerts?status=expired'}); return res.end(); }
  const key = process.env.RESEND_FULL_KEY;
  if (!key) { res.writeHead(302, {Location: '/alerts?status=error'}); return res.end(); }
  const segs = [ALL_SEGMENT, ...p.g.filter(g => GOVS[g]).map(g => GOVS[g][1])];
  let r = await resend('/contacts', 'POST', {email: p.e, unsubscribed: false, segments: segs.map(id => ({id}))}, key);
  if (!r.ok) { // already a contact: re-subscribe and add to each list
    await resend(`/contacts/${encodeURIComponent(p.e)}`, 'PATCH', {unsubscribed: false}, key);
    const adds = await Promise.all(segs.map(id => resend(`/contacts/${encodeURIComponent(p.e)}/segments/${id}`, 'POST', null, key)));
    r = {ok: adds.some(a => a.ok) || adds.every(a => a.status === 409 || a.status === 422)};
    if (!r.ok) console.error('confirm add', adds.map(a => a.status + ' ' + JSON.stringify(a.body)).join(' | '));
  }
  res.writeHead(302, {Location: r.ok ? `/alerts?status=confirmed&g=${p.g.join(',')}` : '/alerts?status=error'}); res.end();
};
