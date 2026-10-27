// Ingestion health: reads ingest_runs (written by db/scripts/load.py and scrapers) and the alerts tables, and
// lists problems an admin should know about. Used by the daily alerts run (emails admins when there are problems)
// and by the Ingestion tab on /admin. Files starting with _ are not routes.
const db = require('./_db');
const {FROM, SITE, resend, esc} = require('./_alerts');
const ui = require('./_email_ui');

const STALE_HOURS = Number(process.env.INGEST_STALE_HOURS) || 36; // the database normally syncs every morning
const STUCK_HOURS = 2;

// Pure: turn query results into a list of problems. Kept separate so it can be tested without a database.
// latest: newest run per dataset; lastOk: newest successful run overall (Date or null); now: Date.
function assess({latest = [], lastOk = null, now = new Date(), outboxFailed = 0, eventsBacklog = 0, staleHours = STALE_HOURS}) {
  const problems = [];
  const hrs = t => (now - new Date(t)) / 3600e3;
  if (!lastOk) problems.push({level: 'error', text: 'No successful database sync is on record.'});
  else if (hrs(lastOk) > staleHours) problems.push({level: 'error', text: `No successful database sync in ${Math.round(hrs(lastOk))} hours (the daily sync may not be running).`});
  for (const r of latest) {
    if (r.status === 'failed') problems.push({level: 'error', dataset: r.dataset, text: `${r.dataset} failed to load${r.notes ? ': ' + r.notes : ''}`});
    else if (r.status === 'running' && hrs(r.started_at) > STUCK_HOURS) problems.push({level: 'warn', dataset: r.dataset, text: `${r.dataset} has been "running" for ${Math.round(hrs(r.started_at))} hours (the load probably died).`});
  }
  if (outboxFailed) problems.push({level: 'warn', text: `${outboxFailed} rule-alert email${outboxFailed === 1 ? '' : 's'} failed to send in the last day (alerts.outbox).`});
  if (eventsBacklog) problems.push({level: 'warn', text: `${eventsBacklog} new record${eventsBacklog === 1 ? '' : 's'} older than 2 days haven't been checked against alert rules (the daily alerts run may be failing).`});
  return problems;
}

async function safe(sql, params) { try { return await db.q(sql, params); } catch (e) { if (e.code === '42P01' || e.code === '3F000') return []; throw e; } }

async function report() {
  const latest = await db.q(`select distinct on (dataset) dataset, origin, status, started_at, finished_at, rows_in, rows_added, rows_deleted, notes, git_sha
      from ingest_runs where dataset is not null and started_at > now() - interval '60 days' order by dataset, id desc`);
  const lastOkRows = await db.q(`select dataset, max(coalesce(finished_at, started_at)) last_ok from ingest_runs where status = 'ok' group by dataset`);
  const okBy = Object.fromEntries(lastOkRows.map(r => [r.dataset, r.last_ok]));
  const lastOk = lastOkRows.reduce((m, r) => (!m || new Date(r.last_ok) > new Date(m) ? r.last_ok : m), null);
  const failures = await db.q(`select id, dataset, origin, started_at, notes, git_sha from ingest_runs where status = 'failed' and started_at > now() - interval '14 days' order by id desc limit 30`);
  const [ob] = await safe(`select count(*) filter (where status = 'failed' and created_at > now() - interval '1 day')::int failed_24h,
      count(*) filter (where status = 'draft')::int drafts from alerts.outbox`);
  const [ev] = await safe(`select count(*) filter (where processed_at is null and detected_at < now() - interval '2 days')::int backlog,
      count(*) filter (where processed_at is null)::int pending from alerts.events`);
  const problems = assess({latest, lastOk, outboxFailed: ob ? ob.failed_24h : 0, eventsBacklog: ev ? ev.backlog : 0});
  return {checked_at: new Date().toISOString(), stale_hours: STALE_HOURS, last_sync: lastOk, problems,
    datasets: latest.map(r => ({...r, last_ok: okBy[r.dataset] || null})), failures,
    alerts: {drafts: ob ? ob.drafts : 0, failed_24h: ob ? ob.failed_24h : 0, events_pending: ev ? ev.pending : 0}};
}

const recipients = () => String(process.env.ADMIN_EMAILS || process.env.DIGEST_REVIEWER || 'hello@fluxlabs.net').split(/[\s,;]+/).filter(Boolean);

const central = d => new Date(d).toLocaleString('en-US', {timeZone: 'America/Chicago', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'}) + ' Central';

// The admin email for a report with problems.
function problemsEmail(r) {
  const n = r.problems.length, s = n === 1 ? '' : 's';
  const errors = r.problems.filter(p => p.level === 'error');
  const text = `The daily BayCounty.me ingestion check found ${n} problem${s}:\n\n` +
    r.problems.map(p => `- ${p.level === 'error' ? '' : '(warning) '}${p.text}`).join('\n') +
    `\n\nLast successful database sync: ${r.last_sync ? new Date(r.last_sync).toLocaleString('en-US', {timeZone: 'America/Chicago'}) + ' Central' : 'never'}.\n` +
    `\nDetails: ${SITE}/admin#ingestion\nWorkflow runs: https://github.com/jeremymcs/baycounty-me/actions\n`;
  return ui.adminNotice({subject: `BayCounty.me ingestion check: ${n} problem${s}`, text, kicker: 'Data health',
    tone: errors.length ? 'salmon' : 'amber', icon: 'alert', eyebrow: 'Daily ingestion check', title: `${n} problem${s} need${s ? '' : 's'} a look`,
    preheader: (r.problems[0] || {}).text || '',
    body: ui.list(r.problems.map(p => p.level === 'error' ? ['salmon', 'Error', esc(p.text)] : ['amber', 'Warning', esc(p.text)])) +
      ui.facts([['Last good sync', r.last_sync ? central(r.last_sync) : 'Never'], ['Workflow runs', ui.a('https://github.com/jeremymcs/baycounty-me/actions', 'GitHub Actions')]]) +
      ui.button(`${SITE}/admin#ingestion`, 'Open data health') + ui.small('When a fetch fails, the site keeps the previous data. Nothing is deleted.')});
}

// The admin email when the check itself couldn't run.
function brokenEmail(message) {
  const text = `The daily ingestion check couldn't read the database: ${message}\n\nCheck Supabase and the DATABASE_URL setting in Vercel. Details: ${SITE}/admin#ingestion\n`;
  return ui.adminNotice({subject: 'BayCounty.me ingestion check could not run', text, kicker: 'Data health', tone: 'salmon', icon: 'alert',
    eyebrow: 'Daily ingestion check', title: 'The check couldn’t run', preheader: 'The daily check couldn’t read the database.',
    body: ui.p('The daily ingestion check couldn’t read the database:') + ui.quote(message) +
      ui.p('Check Supabase and the DATABASE_URL setting in Vercel.', {size: 14, lh: 21}) + ui.button(`${SITE}/admin#ingestion`, 'Open data health')});
}

// Daily: email the admins only when something is wrong. Returns the report.
async function checkAndNotify(key) {
  let r;
  try { r = await report(); }
  catch (e) { // the check itself couldn't run (e.g. the database is down): that's worth an email too
    if (key) await resend('/emails', 'POST', {from: FROM, to: recipients(), ...brokenEmail(e.message)}, key).catch(() => {});
    throw e;
  }
  if (r.problems.length && key) {
    const s = await resend('/emails', 'POST', {from: FROM, to: recipients(), ...problemsEmail(r)}, key);
    if (!s.ok) console.error('health email', s.status, JSON.stringify(s.body));
    r.emailed = s.ok;
  }
  return r;
}

module.exports = {assess, report, checkAndNotify, recipients, problemsEmail, brokenEmail, STALE_HOURS};
