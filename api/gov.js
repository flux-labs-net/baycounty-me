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
//   GET  ?action=members&workspace=lh  /  POST ?action=members {workspace, email, role | "remove", person_id? (role official)}   (owners)
// Elected officials (role official, migration 0096; api/_official.js). Read-only, like everything else here:
//   GET  ?action=official&workspace=lh[&person=jane-doe][&only=agendas|votes|numbers]   the dashboard: the official's seat
//        and board, upcoming meetings and agenda items, their voting record, and the budget, spending, checkbook and
//        contracts. An official sees their own seat unless they pick a colleague; staff pick any member of the board.
//   POST ?action=report-log  {workspace, report, person?}   records that a PDF report was downloaded (activity log)
// Send records (records sender, publisher and up; api/_records.js):
//   GET  ?action=submissions&workspace=lh        what's due, the intake email address, every file sent and its state
//   GET  ?action=template&workspace=lh&kind=contracts   a CSV with the template's column names
//   POST ?action=submit-url     {workspace, filename}   a one-time link to PUT a big file into storage
//   POST ?action=submit-preview {workspace, kind, filename, content (base64) | path, as_of?, printed_total?, mapping?}   read it, save it as waiting
//   POST ?action=submit-confirm {workspace, id}  "yes, this is the right file" for one that was previewed (or emailed in). It's
//        imported, then checked against our own records: if every check matches it publishes, otherwise it waits for review.
//        (submit-publish is the old name, kept for older app builds; it does the same thing.)
//   POST ?action=submit-withdraw {workspace, id} take a file's records off the public pages
//   POST ?action=feed-agree     {workspace, url, agree}    say yes (or no) to a source we read automatically for this government
//   GET  ?action=intake-senders&workspace=lh  /  POST {workspace, senders: [exact addresses]}   who may email files in (owners change it)
// BayCounty.me admins only (the site owner, in the staff app or with the admin cookie):
//   GET  ?action=overview                        every workspace with live/waiting alerts, open flags, members; recent activity
//   GET  ?action=review-flags&status=open        flags from every workspace (open | fixed | not_changed | all)
//   POST ?action=review-flag {id, status, reply?}   answer a flag (fixed | not_changed | open)
//   GET  ?action=review-files&status=open        sent files that didn't pass every check (open | decided)
//   POST ?action=review-file {file_id, decision: publish | hold, note}   publish a held file or keep it off the site (final)
const db = require('./_db');
const G = require('./_gov');
const R = require('./_records');
const O = require('./_official');
const {FROM, resend} = require('./_alerts');

const bad = (msg, status = 400) => Object.assign(new Error(msg), {status});
const body = req => {
  if (req.method === 'GET') return {};
  try { return typeof req.body === 'string' ? JSON.parse(req.body || '{}') : req.body || {}; }
  catch (e) { throw bad('The request body isn’t valid JSON.'); }
};

const NEED = {home: 'read', posts: 'read', post: 'publish', withdraw: 'publish', alerts: 'read', reach: 'alert', alert: 'alert',
  'alert-confirm': 'alert', 'alert-end': 'alert', records: 'read', flag: 'read', flags: 'read', activity: 'read', members: 'read',
  submissions: 'read', template: 'read', official: 'read', 'report-log': 'read', 'submit-url': 'submit', 'submit-preview': 'submit', 'submit-publish': 'submit', 'submit-confirm': 'submit',
  'submit-withdraw': 'submit', 'feed-agree': 'submit', 'intake-senders': 'read'};
const POSTS = new Set(['post', 'withdraw', 'alert', 'alert-confirm', 'alert-end', 'flag', 'submit-url', 'submit-preview', 'submit-publish', 'submit-confirm', 'submit-withdraw', 'feed-agree', 'report-log']);

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
      alert_kinds: G.ALERT_KINDS, notice_kinds: G.NOTICE_KINDS, job_types: G.JOB_TYPES, records: G.RECORDS, record_kinds: R.KINDS};
  }
  if (action === 'overview' || action === 'review-flags' || action === 'review-flag' || action === 'review-files' || action === 'review-file') {
    if (!who) throw bad('Sign in first.', 401);
    if (who.csrf) throw bad('Missing X-BCM-Gov header.', 403);
    if (!who.admin) throw bad('Only the BayCounty.me owner can see every government.', 403);
    if (action === 'overview') return G.ownerOverview(q);
    if (action === 'review-flags') return G.adminFlags(q, String(Q.status || 'open'));
    if (action === 'review-files') return R.reviewList(q, {status: String(Q.status || 'open')});
    if (req.method !== 'POST') throw bad('Use POST.', 405);
    if (action === 'review-file') return R.review(recordDeps(deps), b, who.email);
    return G.adminFlagReview(q, b, who.email);
  }
  const need = (action === 'members' || action === 'intake-senders') && req.method !== 'GET' ? 'manage' : NEED[action];
  if (!need) throw bad('Unknown action.', 404);
  if (POSTS.has(action) && req.method !== 'POST') throw bad('Use POST.', 405);
  const {role, workspace: w, person_id: seat} = await G.requireRole(q, who, String(b.workspace || Q.workspace || ''), need);
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
    // sent: how many phones, inboxes and texts it went to (counts only; shown to staff and in /admin, not on public pages).
    case 'alerts': return {countywide: w.countywide, alerts: await q(`select a.id, a.kind, a.title, a.message, a.instruction, a.severity, a.countywide, a.geometry, a.status, a.created_by, a.created_at,
        a.confirmed_by, a.sent_at, a.ends_at, a.ended_by, a.ended_at, (a.status = 'sent' and (a.ends_at is null or a.ends_at > now())) live,
        (select coalesce(jsonb_object_agg(r.channel, r.people), '{}') from emergency_reach r where r.notice_id = 'staff:' || a.id) sent
        from gov.alerts a where a.workspace_id = $1 order by a.created_at desc limit 100`, [w.id])};
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
    case 'official': {
      const person = /^[a-z0-9-]{1,120}$/.test(String(Q.person || '')) ? String(Q.person) : seat;
      const only = ['agendas', 'votes', 'numbers'].includes(Q.only) ? Q.only : null;
      return {role, own_person_id: seat, ...(await O.dashboard(q, w, person, {only}))};
    }
    case 'report-log': {
      const report = String(b.report || '');
      if (!O.REPORTS[report]) throw bad('Unknown report.');
      await G.log(q, w.id, email, 'report_downloaded', {report, title: O.REPORTS[report], ...(b.person ? {person_id: String(b.person).slice(0, 120)} : {})});
      return {ok: true};
    }
    case 'flag': return G.addFlag(q, w, b, email);
    case 'flags': return {flags: await q(`select id, email, dataset, record_label, field, shown_value, correct_value, evidence_url, note, status, reply, reviewed_at, created_at
        from gov.flags where workspace_id = $1 order by created_at desc limit 200`, [w.id])};
    case 'activity': {
      if (!['owner', 'auditor'].includes(role)) throw bad('Only owners and auditors can see the full activity log.', 403);
      return {activity: await q('select email, action, detail, at from gov.activity where workspace_id = $1 order by at desc limit 300', [w.id])};
    }
    case 'submissions': return R.overview(q, w);
    case 'template': {
      res.setHeader('Content-Type', 'text/csv; charset=utf-8');
      res.setHeader('Content-Disposition', `attachment; filename="${String(Q.kind).replace(/[^a-z]/g, '')}-template.csv"`);
      res.status(200).send(R.templateCsv(String(Q.kind || '')));
      return undefined;
    }
    case 'submit-url': return R.uploadUrl(recordDeps(deps), w, b);
    case 'submit-preview': return R.preview(recordDeps(deps), w, b, who);
    case 'submit-publish': case 'submit-confirm': return R.confirm(recordDeps(deps), w, b, who);
    case 'intake-senders': {
      if (req.method === 'GET') return R.intakeSenders(q, w);
      return R.setIntakeSenders(recordDeps(deps), w, b, who);
    }
    case 'submit-withdraw': return R.withdraw(recordDeps(deps), w, b, who);
    case 'feed-agree': return R.feedAgree(recordDeps(deps), w, b, who);
    case 'members': {
      if (req.method === 'GET') return {officials: await G.seatsNow(q, w.id), members: await q(`select m.email, m.role, m.person_id, ${G.PERSON_NAME} person_name, m.added_by, m.created_at from gov.members m where m.workspace_id = $1 order by m.role, m.email`, [w.id])};
      return G.setMember(q, w.id, b, email);
    }
  }
}

// The finance importer and publisher behind Send records. Tests pass their own storage (and may pass the rest).
const recordDeps = deps => ({q: deps.q, storage: deps.storage || require('./_finance/storage'), ingest: deps.ingest || require('./finance').ingest,
  publisher: deps.publisher || require('./_finance/publish'), log: G.log});

function createHandler(deps) {
  return async (req, res) => {
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Robots-Tag', 'noindex');
    if (!deps.hasDb()) return res.status(500).json({error: 'The government workspace isn’t configured on this deployment.'});
    const action = String((req.query || {}).action || '');
    try {
      const out = await route(deps, req, res, action);
      if (out === undefined) return undefined;  // already sent (a CSV template)
      return res.status(200).json(out);
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
module.exports.config = {api: {bodyParser: {sizeLimit: '4.5mb'}}};  // Send records: files up to 3 MB come inline as base64
