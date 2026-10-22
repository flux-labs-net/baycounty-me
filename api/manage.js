// Manage email alerts: /alerts/manage?t=<signed prefs token> (vercel.json rewrites it here).
//   GET  shows what the address follows (weekly digests and rule alerts) with forms. Nothing changes on GET,
//        because email security scanners open links before people do.
//   POST (form) does one action: save (governments to follow), unsubscribe (everything), remove_rule, or
//        send_link (email a fresh manage link; used when a link has no token, e.g. an older digest).
// The token is signed with ALERTS_SECRET and tied to the address (_alerts.prefsToken). It doesn't expire, so the
// link in every email keeps working; changing ALERTS_SECRET invalidates all of them.
const {GOVS, ALL_SEGMENT, FROM, resend, esc, emailShell, button, sameOrigin, claimConfirmSend, readPrefsToken, prefsUrl, setPrefsProperty, page} = require('./_alerts');

const KEY = () => process.env.RESEND_FULL_KEY;
const segToGov = Object.fromEntries(Object.entries(GOVS).map(([k, [, id]]) => [id, k]));
const enc = encodeURIComponent;

async function following(email, key) {
  const r = await resend(`/contacts/${enc(email)}/segments`, 'GET', null, key);
  if (r.status === 404) return {exists: false, govs: [], unsubscribed: true};
  if (!r.ok) throw new Error(`Resend ${r.status}`);
  const c = await resend(`/contacts/${enc(email)}`, 'GET', null, key);
  const govs = ((r.body && r.body.data) || []).map(s => segToGov[s.id]).filter(Boolean);
  return {exists: true, govs, unsubscribed: !!(c.body && c.body.unsubscribed)};
}

// Rule alerts for this address (migration 0008). Empty if the database or migration isn't there.
async function rules(email) {
  try {
    const db = require('./_db');
    if (!db.hasDb()) return [];
    return await db.q(`select id, rule_type, params, confirmed from alerts.subscriptions where email = $1 and unsubscribed_at is null order by created_at`, [email]);
  } catch (e) { console.error('manage: rules', e.message); return []; }
}
const describeRule = r => require('./_rules').describe(r.rule_type, r.params || {});

async function setGovs(email, want, key) {
  const now = await following(email, key);
  const add = want.filter(g => !now.govs.includes(g)), drop = now.govs.filter(g => !want.includes(g));
  if (!now.exists) {
    const r = await resend('/contacts', 'POST', {email, unsubscribed: false, segments: [ALL_SEGMENT, ...want.map(g => GOVS[g][1])].map(id => ({id}))}, key);
    if (!r.ok) throw new Error(`Resend ${r.status}`);
  } else {
    if (want.length && now.unsubscribed) await resend(`/contacts/${enc(email)}`, 'PATCH', {unsubscribed: false}, key);
    const res = await Promise.all([
      ...add.map(g => resend(`/contacts/${enc(email)}/segments/${GOVS[g][1]}`, 'POST', null, key)),
      ...drop.map(g => resend(`/contacts/${enc(email)}/segments/${GOVS[g][1]}`, 'DELETE', null, key)),
      ...(want.length ? [resend(`/contacts/${enc(email)}/segments/${ALL_SEGMENT}`, 'POST', null, key)] : [resend(`/contacts/${enc(email)}/segments/${ALL_SEGMENT}`, 'DELETE', null, key)]),
    ]);
    const bad = res.filter(r => !r.ok && ![404, 409, 422].includes(r.status));
    if (bad.length) throw new Error('Resend ' + bad.map(r => r.status).join(','));
  }
  if (want.length) await setPrefsProperty(email, key);
}

async function unsubscribeAll(email, key) {
  const now = await following(email, key);
  if (now.exists) {
    await resend(`/contacts/${enc(email)}`, 'PATCH', {unsubscribed: true}, key);
    await Promise.all([...now.govs.map(g => GOVS[g][1]), ALL_SEGMENT].map(id => resend(`/contacts/${enc(email)}/segments/${id}`, 'DELETE', null, key)));
  }
  try { const db = require('./_db'); if (db.hasDb()) await db.q('update alerts.subscriptions set unsubscribed_at = now() where email = $1 and unsubscribed_at is null', [email]); }
  catch (e) { console.error('manage: unsubscribe rules', e.message); }
}

const MSG = {saved: 'Saved. You’ll get weekly updates for the governments checked below.', stopped: 'You’re unsubscribed from every BayCounty.me email. You can sign up again any time.',
  removed: 'That alert is turned off.', error: 'Something went wrong. Please try again.', sent: 'If that address gets BayCounty.me email, a link to manage it is on its way.'};

function linkForm(note) {
  return page('Manage your alerts', `<h1>Manage your BayCounty.me emails</h1>${note ? `<p class="note">${esc(note)}</p>` : ''}<p>Enter your email address and we’ll send you a link to change what you follow or unsubscribe.</p>
<form method="post" action="/api/manage"><input type="hidden" name="action" value="send_link"><input type="email" name="email" required maxlength="200" autocomplete="email" placeholder="you@example.com"><button type="submit">Email me a link</button></form>
<p style="margin-top:16px">Every email also has a one-click unsubscribe link at the bottom.</p>`);
}

async function manageView(tok, p, msg) {
  const key = KEY();
  let f;
  try { f = await following(p.e, key); } catch (e) { console.error('manage: following', e.message); return page('Manage your alerts', `<h1>Manage your alerts</h1><p>We couldn’t load your settings right now. Please try again in a few minutes.</p>`); }
  const rs = await rules(p.e);
  const t = String(tok).replace(/[^A-Za-z0-9._-]/g, '');
  const hidden = a => `<input type="hidden" name="t" value="${t}"><input type="hidden" name="action" value="${a}">`;
  const boxes = Object.entries(GOVS).map(([k, [name]]) => `<label><input type="checkbox" name="g" value="${k}"${f.govs.includes(k) && !f.unsubscribed ? ' checked' : ''}> ${esc(name)}</label>`).join('');
  const ruleList = rs.length ? `<h2>Alerts you set up</h2><ul class="r">${rs.map(r => `<li><span>${esc(describeRule(r))}${r.confirmed ? '' : ' <em>(not confirmed yet)</em>'}</span><form method="post" action="/api/manage">${hidden('remove_rule')}<input type="hidden" name="id" value="${Number(r.id)}"><button type="submit" class="plain">Turn off</button></form></li>`).join('')}</ul>` : '';
  return page('Manage your alerts', `<h1>Manage your BayCounty.me emails</h1><p>For ${esc(p.e)}</p>${msg && MSG[msg] ? `<p class="note">${esc(MSG[msg])}</p>` : ''}
<h2>Weekly updates</h2><form method="post" action="/api/manage">${hidden('save')}<div class="opts">${boxes}</div><button type="submit">Save</button></form>
${ruleList}<p style="margin-top:16px">Want an alert for a vote, a contract, a street name or a candidate? <a href="/alerts#rules">Set one up on the alerts page</a>.</p>
<h2>Stop everything</h2><form method="post" action="/api/manage">${hidden('unsubscribe')}<button type="submit" class="plain">Unsubscribe from all BayCounty.me emails</button></form>`);
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('X-Robots-Tag', 'noindex');
  const html = (code, body) => { res.setHeader('Content-Type', 'text/html; charset=utf-8'); return res.status(code).send(body); };
  if (!KEY() || !process.env.ALERTS_SECRET) return html(503, page('Alerts unavailable', '<h1>Email alerts aren’t set up yet</h1><p>Please try again soon.</p>'));
  if (req.method === 'GET') {
    const raw = (req.query && (req.query.t || req.query['amp;t'])) || '';
    const p = readPrefsToken(raw);
    if (!p) return html(200, linkForm(raw && raw !== 'none' ? 'That link isn’t valid any more.' : null));
    return html(200, await manageView(raw, p, req.query.m));
  }
  if (req.method !== 'POST') return res.status(405).json({ok: false, error: 'Method not allowed'});
  if (!sameOrigin(req)) return html(403, page('Not allowed', '<h1>Not allowed</h1><p>Please use the form on BayCounty.me.</p>'));
  const b = typeof req.body === 'string' ? Object.fromEntries(new URLSearchParams(req.body)) : req.body || {};
  const back = (t, m) => { res.setHeader('Location', `/alerts/manage?t=${enc(t)}&m=${m}`); return res.status(303).end(); };
  if (b.action === 'send_link') {
    const email = String(b.email || '').trim().toLowerCase().slice(0, 200);
    // Same answer whether or not the address is subscribed, so the form can't be used to probe addresses.
    if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && await claimConfirmSend('manage:' + email)) {
      let known = false;
      try { known = (await following(email, KEY())).exists || (await rules(email)).length > 0; } catch (e) {}
      if (known) {
        const link = prefsUrl(email);
        const m = require('./_emails').manageLinkEmail(link);
        await resend('/emails', 'POST', {from: FROM, to: [email], subject: m.subject, html: m.html, text: m.text}, KEY()).catch(e => console.error('manage: send link', e.message));
      }
    }
    return html(200, page('Check your email', `<h1>Check your email</h1><p>${esc(MSG.sent)}</p><a class="btn" href="/alerts">Back to alerts</a>`));
  }
  const p = readPrefsToken(b.t);
  if (!p) return html(200, linkForm('That link isn’t valid any more.'));
  try {
    if (b.action === 'save') {
      const g = [].concat(b.g || []).filter(x => GOVS[x]);
      await setGovs(p.e, [...new Set(g)], KEY());
      return back(b.t, 'saved');
    }
    if (b.action === 'unsubscribe') { await unsubscribeAll(p.e, KEY()); return back(b.t, 'stopped'); }
    if (b.action === 'remove_rule') {
      const db = require('./_db');
      await db.q('update alerts.subscriptions set unsubscribed_at = now() where id = $1 and email = $2', [parseInt(b.id, 10) || 0, p.e]);
      return back(b.t, 'removed');
    }
  } catch (e) { console.error('manage', b.action, e.message); return back(b.t, 'error'); }
  return back(b.t, 'error');
};
module.exports.setGovs = setGovs;
