// Sent mail for the /admin "Sent mail" tab: emails sent through Resend and each one's latest delivery status.
// Resend's API returns only the latest event per email (no history). Uses RESEND_FULL_KEY. Admin-only.
const {resend} = require('./_alerts');

const PAGE = 100, MAX_PAGES = 5;           // up to 500 most recent sends per load
const CACHE_MS = 60 * 1000;
let cache = null;                          // {at, emails}

// Plain-English labels, and which statuses need attention.
const STATUS = {
  queued: 'Queued', scheduled: 'Scheduled', sent: 'Sent', delivered: 'Delivered', delivery_delayed: 'Delayed',
  opened: 'Opened', clicked: 'Clicked', bounced: 'Bounced', complained: 'Marked as spam', failed: 'Failed',
  canceled: 'Canceled', suppressed: 'Suppressed',
};
const PROBLEM = new Set(['bounced', 'complained', 'failed', 'suppressed', 'delivery_delayed']);
const REACHED = new Set(['delivered', 'opened', 'clicked', 'complained']); // got to the inbox

const domainOf = from => { const m = String(from || '').match(/@([^>\s]+)/); return m ? m[1].toLowerCase() : ''; };

async function fetchAll(key) {
  if (cache && Date.now() - cache.at < CACHE_MS) return cache.emails;
  const out = [];
  let after = null;
  for (let i = 0; i < MAX_PAGES; i++) {
    const r = await resend(`/emails?limit=${PAGE}${after ? '&after=' + encodeURIComponent(after) : ''}`, 'GET', null, key);
    if (!r.ok) throw Object.assign(new Error(`Resend said ${r.status}: ${(r.body && r.body.message) || 'no details'}`), {status: 502});
    const data = (r.body && r.body.data) || [];
    out.push(...data);
    if (!r.body.has_more || !data.length) break;
    after = data[data.length - 1].id;
  }
  cache = {at: Date.now(), emails: out};
  return out;
}

// Pure: filter and count. emails: Resend list items; opts: {days, domain ('' = all), status, q, now}.
function shape(emails, {days = 7, domain = 'baycounty.me', status = '', q = '', now = new Date()} = {}) {
  const since = now - days * 864e5;
  const needle = String(q || '').toLowerCase().trim();
  const inWindow = emails.filter(e => new Date(e.created_at) >= since && (!domain || domainOf(e.from) === domain));
  const counts = {total: inWindow.length, reached: 0, problems: 0, by: {}};
  for (const e of inWindow) {
    const s = e.last_event || 'sent';
    counts.by[s] = (counts.by[s] || 0) + 1;
    if (REACHED.has(s)) counts.reached++;
    if (PROBLEM.has(s)) counts.problems++;
  }
  const rows = inWindow.filter(e => (!status || (status === 'problems' ? PROBLEM.has(e.last_event) : (e.last_event || 'sent') === status))
    && (!needle || [e.subject, e.from, ...(e.to || [])].join(' ').toLowerCase().includes(needle)))
    .map(e => ({id: e.id, created_at: e.created_at, scheduled_at: e.scheduled_at || null, from: e.from, to: e.to || [],
      subject: e.subject, status: e.last_event || 'sent', problem: PROBLEM.has(e.last_event)}));
  const domains = [...new Set(emails.map(e => domainOf(e.from)).filter(Boolean))].sort();
  return {counts, rows, domains};
}

async function list(opts) {
  const key = process.env.RESEND_FULL_KEY;
  if (!key) throw Object.assign(new Error('RESEND_FULL_KEY isn’t set in Vercel.'), {status: 500});
  const emails = await fetchAll(key);
  const s = shape(emails, opts);
  const oldest = emails.length ? emails[emails.length - 1].created_at : null;
  return {...s, labels: STATUS, fetched: emails.length, oldest_fetched: oldest, capped: emails.length >= PAGE * MAX_PAGES, checked_at: new Date().toISOString()};
}

async function detail(id) {
  if (!/^[0-9a-f-]{36}$/i.test(String(id))) throw Object.assign(new Error('Bad email id.'), {status: 400});
  const r = await resend(`/emails/${id}`, 'GET', null, process.env.RESEND_FULL_KEY);
  if (!r.ok) throw Object.assign(new Error(`Resend said ${r.status}`), {status: r.status === 404 ? 404 : 502});
  const e = r.body || {};
  return {id: e.id, created_at: e.created_at, from: e.from, to: e.to, cc: e.cc, bcc: e.bcc, reply_to: e.reply_to, subject: e.subject,
    status: e.last_event || 'sent', html: e.html || null, text: e.text || null, tags: e.tags || []};
}

module.exports = {shape, list, detail, STATUS, domainOf};
