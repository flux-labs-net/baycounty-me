// /api/gov: the government workspace (/staff) for city and county staff. Private: every call but login/verify needs a
// signed-in member of the workspace (or the BayCounty.me admin). Logic and rules live in api/_gov.js. Actions, all JSON:
//   POST ?action=login   {email}                 emails a 6-digit code to a workspace member
//   POST ?action=verify  {email, code}           starts a session (cookie bcm_gov)
//   POST ?action=logout
//   GET  ?action=me                              your email and the workspaces you can open, with your role
//   GET  ?action=home&workspace=lh               counts and the latest activity for the workspace home
//   GET  ?action=posts&workspace=lh&kind=notice  your posts of a kind (notice | event | job), plus the ones read from records
//   POST ?action=post        {workspace, kind, id?, ...fields}   add or change one of your posts (publisher)
//   POST ?action=withdraw    {workspace, kind, id}               take one of your posts down (publisher)
//   GET  ?action=alerts&workspace=lh             this workspace's alerts, newest first
//   GET  ?action=reach&workspace=lh&kind=boil-water[&countywide=1]   phones and emails an alert would reach now
//   POST ?action=alert       {workspace, kind, title, message, instruction?, severity?, countywide?, hours?}   (alert sender)
//   POST ?action=alert-confirm {workspace, id}   second person confirms a countywide alert (alert sender)
//   POST ?action=alert-end     {workspace, id}   end a live alert or cancel a waiting one (alert sender)
//   GET  ?action=records&workspace=lh&dataset=budget-years      read-only record data
//   POST ?action=flag        {workspace, dataset, record_key?, record_label?, field?, shown_value?, correct_value?, evidence_url?, note?}
//   GET  ?action=flags&workspace=lh              flags sent from this workspace and our answers
//   GET  ?action=activity&workspace=lh           who did what (owners and auditors)
//   GET  ?action=members&workspace=lh  /  POST ?action=members {workspace, email, role | "remove"}   (owners)
const db = require('./_db');
const G = require('./_gov');
const {FROM, resend} = require('./_alerts');

const bad = (msg, status = 400) => Object.assign(new Error(msg), {status});
const body = req => {
  if (req.method === 'GET') return {};
  try { return typeof req.body === 'string' ? JSON.parse(req.body || '{}') : req.body || {}; }
  catch (e) { throw bad('The request body isn’t valid JSON.'); }
};

const NEED = {home: 'read', posts: 'read', post: 'publish', withdraw: 'publish', alerts: 'read', reach: 'alert', alert: 'alert',
  'alert-confirm': 'alert', 'alert-end': 'alert', records: 'read', flag: 'read', flags: 'read', activity: 'read', members: 'read'};
const POSTS = new Set(['post', 'withdraw', 'alert', 'alert-confirm', 'alert-end', 'flag']);

async function route(deps, req, res, action) {
  const {q} = deps, Q = req.query || {}, b = body(req);
  if (action === 'login' || action === 'verify') {
    if (req.method !== 'POST') throw bad('Use POST.', 405);
    return action === 'login' ? G.startLogin(q, req, b, deps.sendEmail) : G.finishLogin(q, req, res, b);
  }
  const who = await deps.caller(req, q);
  if (action === 'logout') {
    if (req.method !== 'POST') throw bad('Use POST.', 405);
    return G.logout(q, res, who && !who.csrf ? who : null);
  }
  if (action === 'me') {
    if (!who) throw bad('Sign in first.', 401);
    return {email: who.email, admin: Boolean(who.admin), workspaces: await G.workspacesFor(q, who), roles: G.ROLE_LABEL,
      alert_kinds: G.ALERT_KINDS, notice_kinds: G.NOTICE_KINDS, job_types: G.JOB_TYPES, records: G.RECORDS};
  }
  const need = action === 'members' && req.method !== 'GET' ? 'manage' : NEED[action];
  if (!need) throw bad('Unknown action.', 404);
  if ((POSTS.has(action) || (action === 'members' && req.method !== 'GET')) && req.method !== 'POST') throw bad('Use POST.', 405);
  const {role, workspace: w} = await G.requireRole(q, who, String(b.workspace || Q.workspace || ''), need);
  const email = who.email;

  switch (action) {
    case 'home': {
      const [c] = await q(`select
          (select count(*)::int from public_notices where origin = 'gov' and gov_id = $1) notices,
          (select count(*)::int from community_events where origin = 'gov' and gov_id = $1 and starts >= to_char(now(), 'YYYY-MM-DD')) events,
          (select count(*)::int from job_openings where origin = 'gov' and gov_id = $1 and (closes is null or closes >= to_char(now(), 'YYYY-MM-DD'))) jobs,
          (select count(*)::int from gov.alerts where workspace_id = $1 and status = 'sent' and (ends_at is null or ends_at > now())) live_alerts,
          (select count(*)::int from gov.alerts where workspace_id = $1 and status = 'pending') waiting_alerts,
          (select count(*)::int from gov.flags where workspace_id = $1 and status = 'open') open_flags,
          (select count(*)::int from gov.members where workspace_id = $1) members`, [w.id]);
      const activity = await q('select email, action, detail, at from gov.activity where workspace_id = $1 order by at desc limit 12', [w.id]);
      return {workspace: w, role, counts: c, activity};
    }
    case 'posts': return G.listPosts(q, w, String(Q.kind || ''));
    case 'post': return G.savePost(q, w, String(b.kind || ''), b, email);
    case 'withdraw': return G.withdrawPost(q, w, String(b.kind || ''), b.id, email);
    case 'alerts': return {countywide: w.countywide, alerts: await q(`select id, kind, title, message, instruction, severity, countywide, status, created_by, created_at,
        confirmed_by, sent_at, ends_at, ended_by, ended_at, (status = 'sent' and (ends_at is null or ends_at > now())) live
        from gov.alerts where workspace_id = $1 order by created_at desc limit 100`, [w.id])};
    case 'reach': return G.reach(q, w, String(Q.kind || ''), Q.countywide === '1' && w.countywide);
    case 'alert': {
      const a = await G.createAlert(q, w, b, email, {admin: Boolean(who.admin)});
      const sent = a.status === 'sent' ? await deps.sendNow(w.place_id) : null;
      return {ok: true, alert: a, delivery: sent, message: a.status === 'pending' ? 'Saved. A second alert sender has to confirm a countywide alert before it goes out.' : 'Sent.'};
    }
    case 'alert-confirm': {
      const a = await G.confirmAlert(q, w, b.id, email);
      return {ok: true, alert: a, delivery: await deps.sendNow(w.place_id)};
    }
    case 'alert-end': {
      const a = await G.endAlert(q, w, b.id, email);
      if (a.status === 'ended') await deps.sendNow(w.place_id);
      return {ok: true, alert: a};
    }
    case 'records': return G.records(q, w, String(Q.dataset || ''));
    case 'flag': return G.addFlag(q, w, b, email);
    case 'flags': return {flags: await q(`select id, email, dataset, record_label, field, shown_value, correct_value, evidence_url, note, status, reply, reviewed_at, created_at
        from gov.flags where workspace_id = $1 order by created_at desc limit 200`, [w.id])};
    case 'activity': {
      if (!['owner', 'auditor'].includes(role)) throw bad('Only owners and auditors can see the full activity log.', 403);
      return {activity: await q('select email, action, detail, at from gov.activity where workspace_id = $1 order by at desc limit 300', [w.id])};
    }
    case 'members': {
      if (req.method === 'GET') return {members: await q('select email, role, added_by, created_at from gov.members where workspace_id = $1 order by role, email', [w.id])};
      return G.setMember(q, w.id, b, email);
    }
  }
}

function createHandler(deps) {
  return async (req, res) => {
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Robots-Tag', 'noindex');
    if (!deps.hasDb()) return res.status(500).json({error: 'The government workspace isn’t configured on this deployment.'});
    const action = String((req.query || {}).action || '');
    try {
      return res.status(200).json(await route(deps, req, res, action));
    } catch (e) {
      const status = e.status || 500;
      if (status >= 500) console.error('gov', action, e);
      return res.status(status).json({error: status >= 500 && !e.status ? 'Something went wrong. Try again.' : e.message});
    }
  };
}

async function sendEmail(to, m) {
  const key = process.env.RESEND_FULL_KEY || process.env.RESEND_API_KEY;
  if (!key) throw bad('Email isn’t configured on this deployment.', 500);
  const r = await resend('/emails', 'POST', {from: FROM, to: [to], subject: m.subject, text: m.text, html: m.html}, key);
  if (!r.ok) { console.error('gov sign-in email', r.status, JSON.stringify(r.body)); throw bad('The sign-in email didn’t send. Try again in a minute.', 502); }
}

// Runs an emergency check right away, so a sent alert reaches phones and inboxes in seconds instead of at the next
// 5-minute check. A failure here doesn't undo the alert: the next scheduled check sends it.
async function sendNow(place) {
  try {
    const r = await require('./_emergency_run').run(place, {force: true});
    const mine = (r.pushed || []).filter(p => String(p.notice_id).startsWith('staff:'));
    return {checked_at: r.checked_at, pushed: mine};
  } catch (e) {
    console.error('gov send now', e.message);
    return {error: 'Saved, but the immediate send didn’t run. The next emergency check (within 5 minutes) sends it.'};
  }
}

module.exports = createHandler({q: db.q, hasDb: db.hasDb, caller: G.caller, sendEmail, sendNow});
module.exports.createHandler = createHandler;
