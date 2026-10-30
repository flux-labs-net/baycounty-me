// The email intake report for /admin ("Email intake" tab): every email that reached an intake address at
// ingest.baycounty.me, with its timestamps (sent, received by the mail service, webhook, logged, finished), sender,
// recipients, authentication result, decision and reason, every attachment's name, size and SHA-256, and the audit-log
// events about the email or its files with each event's chain hash. Downloads as CSV (one row per email) or as a
// printable report page (HTML, print to PDF). Admin-only. Reads gov.intake_report() and gov.audit_chain_breaks()
// (migration 0093).
const {esc} = require('./_alerts');

const err = (msg, status = 400) => Object.assign(new Error(msg), {status});
const DAY = 864e5;
const TZ = 'America/Chicago';

// {from, to} as Date objects from 'YYYY-MM-DD' strings (to is inclusive). Defaults to the last 30 days; at most 400 days.
function window({from = '', to = '', now = new Date()} = {}) {
  const day = s => (/^\d{4}-\d{2}-\d{2}$/.test(String(s)) ? new Date(s + 'T00:00:00Z') : null);
  const end = day(to) ? new Date(+day(to) + DAY) : new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()) + DAY);
  const start = day(from) || new Date(+end - 30 * DAY);
  if (start >= end) throw err('The start date has to be before the end date.');
  if (end - start > 400 * DAY) throw err('Pick 400 days or fewer.');
  return {from: start, to: end};
}

const DECISION = {accepted: 'Accepted', refused: 'Refused (government address not on the list)', dropped: 'Dropped (outside sender or unknown address)',
  unauthenticated: 'Refused (sender not authenticated)', failed: 'Failed', received: 'Received, not finished'};

async function report(q, {from, to, workspace = ''} = {}) {
  const w = window({from, to});
  const rows = await q('select * from gov.intake_report($1, $2, $3)', [w.from.toISOString(), w.to.toISOString(), workspace || null]);
  const breaks = await q('select id, problem from gov.audit_chain_breaks()');
  const [head] = await q('select count(*)::int events, max(id) last_id, (select hash from gov.audit_log order by id desc limit 1) last_hash from gov.audit_log');
  const counts = {};
  for (const r of rows) counts[r.decision] = (counts[r.decision] || 0) + 1;
  return {from: w.from.toISOString().slice(0, 10), to: new Date(+w.to - DAY).toISOString().slice(0, 10), workspace: workspace || null,
    generated_at: new Date().toISOString(), emails: rows, counts,
    chain: {intact: !breaks.length, breaks, events: head ? head.events : 0, last_id: head ? head.last_id : null, last_hash: head ? head.last_hash : null}};
}

const iso = v => (v ? new Date(v).toISOString() : '');
const cell = v => { const s = v == null ? '' : String(v); return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
const files = e => (e.attachments || []);

// One row per email. Times are UTC ISO 8601.
function toCsv(r) {
  const cols = ['email_id', 'message_id', 'sent_at', 'received_at', 'webhook_at', 'logged_at', 'finished_at', 'sender', 'recipients', 'intake_address',
    'workspace_id', 'decision', 'reason', 'notice_sent', 'subject', 'files', 'file_sha256', 'payload_sha256', 'events', 'last_event_hash'];
  const lines = [cols.join(',')];
  for (const e of r.emails) {
    const ev = e.events || [];
    lines.push([e.email_id, e.message_id, iso(e.sent_at), iso(e.received_at), iso(e.webhook_at), iso(e.logged_at), iso(e.finished_at), e.sender,
      (e.recipients || []).join(' '), e.intake_address, e.workspace_id, e.decision, e.reason, e.notice_sent ? 'yes' : 'no', e.subject,
      files(e).map(f => f.name).join(' | '), files(e).map(f => f.sha256 || '').join(' | '), e.payload_sha256, ev.length, ev.length ? ev[ev.length - 1].hash : '']
      .map(cell).join(','));
  }
  return lines.join('\r\n') + '\r\n';
}

const local = v => (v ? new Date(v).toLocaleString('en-US', {timeZone: TZ, year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit'}) + ' CT' : '–');
const size = n => (n == null ? '' : n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(1) + ' KB' : (n / 1048576).toFixed(1) + ' MB');

// A standalone, printable page (read-only). Print to PDF from the browser for a signed copy.
function toHtml(r) {
  const c = r.counts;
  const emails = r.emails.map(e => {
    const fl = files(e);
    const times = [['Sent (sender’s clock)', e.sent_at], ['Received by the mail service', e.received_at], ['Webhook signed', e.webhook_at], ['Logged', e.logged_at], ['Finished', e.finished_at]];
    return `<article class="em ${esc(e.decision)}">
  <h2>${esc(e.subject || (e.decision === 'accepted' ? '(no subject)' : '(not opened)'))}<span class="tag">${esc(DECISION[e.decision] || e.decision)}</span></h2>
  <dl><dt>From</dt><dd>${esc(e.sender)}</dd><dt>To</dt><dd>${esc((e.recipients || []).join(', '))}</dd>
    ${e.workspace_id ? `<dt>Government</dt><dd>${esc(e.workspace_id)}</dd>` : ''}<dt>Reason</dt><dd>${esc(e.reason || '–')}${e.notice_sent ? ' · “who may send” reply sent' : ''}</dd>
    <dt>Email id</dt><dd class="mono">${esc(e.email_id || '–')}</dd><dt>Message-ID</dt><dd class="mono">${esc(e.message_id || '–')}</dd>
    <dt>Webhook body SHA-256</dt><dd class="mono">${esc(e.payload_sha256)}</dd></dl>
  <table><thead><tr><th>Timestamp</th><th>When</th><th>UTC</th></tr></thead><tbody>${times.map(([k, v]) => `<tr><td>${k}</td><td>${local(v)}</td><td class="mono">${iso(v) || '–'}</td></tr>`).join('')}</tbody></table>
  ${fl.length ? `<table><thead><tr><th>File</th><th>Size</th><th>SHA-256</th><th>Result</th></tr></thead><tbody>${fl.map(f => `<tr><td>${esc(f.name)}</td><td>${size(f.size)}</td><td class="mono">${esc(f.sha256 || '–')}</td><td>${esc(f.error ? 'Error: ' + f.error : f.skipped || (f.duplicate ? 'Already received (same SHA-256)' : f.raw_id ? 'Stored and imported' : ''))}</td></tr>`).join('')}</tbody></table>` : ''}
  ${(e.events || []).length ? `<table><thead><tr><th>#</th><th>When</th><th>Who</th><th>What</th><th>Chain hash</th></tr></thead><tbody>${e.events.map(a => `<tr><td>${a.id}</td><td>${local(a.at)}</td><td>${esc(a.actor)}</td><td>${esc(a.action.replace(/_/g, ' '))}</td><td class="mono">${esc(String(a.hash).slice(0, 16))}…</td></tr>`).join('')}</tbody></table>` : ''}
</article>`;
  }).join('\n');
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Email intake report ${esc(r.from)} to ${esc(r.to)}</title>
<style>
:root{--ink:#14202b;--muted:#5b6876;--line:#d9dee4;--bg:#fff;--ok:#1f7a4d;--bad:#b3261e}
body{font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;color:var(--ink);background:var(--bg);margin:0;padding:24px 16px;max-width:980px;margin-inline:auto}
h1{font-size:1.4rem;margin:0 0 4px}h2{font-size:1.05rem;margin:0 0 8px;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.muted{color:var(--muted)}.mono{font-family:ui-monospace,Menlo,monospace;font-size:.78rem;word-break:break-all}
.sum{display:flex;gap:16px;flex-wrap:wrap;margin:14px 0;padding:12px 14px;border:1px solid var(--line);border-radius:10px}
.sum b{display:block;font-size:1.2rem}.chain{padding:10px 14px;border-radius:10px;margin:0 0 18px;border:1px solid}
.chain.ok{color:var(--ok);border-color:currentColor}.chain.bad{color:var(--bad);border-color:currentColor}
.em{border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:0 0 14px;break-inside:avoid}
.tag{font-size:.75rem;font-weight:500;border:1px solid var(--line);border-radius:999px;padding:1px 8px;color:var(--muted)}
.accepted .tag{color:var(--ok);border-color:currentColor}
dl{display:grid;grid-template-columns:max-content 1fr;gap:3px 14px;margin:0 0 10px}dt{color:var(--muted)}dd{margin:0}
table{width:100%;border-collapse:collapse;margin:8px 0 0;font-size:.85rem}th,td{text-align:left;padding:4px 6px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:500}.bar{display:flex;gap:8px;margin:0 0 12px}.bar button{font:inherit;padding:6px 12px;border:1px solid var(--line);border-radius:8px;background:none;cursor:pointer}
@media print{.bar{display:none}body{padding:0}}
@media (max-width:600px){dl{grid-template-columns:1fr}dt{margin-top:4px}}
</style></head><body>
<div class="bar"><button type="button" onclick="print()">Print or save as PDF</button></div>
<h1>Email intake report</h1>
<p class="muted">${esc(r.from)} to ${esc(r.to)}${r.workspace ? ' · ' + esc(r.workspace) : ' · all governments'} · generated ${local(r.generated_at)} (${esc(r.generated_at)})</p>
<div class="sum"><div><b>${r.emails.length}</b>emails</div>${Object.entries(c).map(([k, n]) => `<div><b>${n}</b>${esc((DECISION[k] || k).split(' (')[0].toLowerCase())}</div>`).join('')}</div>
<div class="chain ${r.chain.intact ? 'ok' : 'bad'}">${r.chain.intact
    ? `Audit trail checked: all ${r.chain.events} events link up. Latest event #${r.chain.last_id}, hash <span class="mono">${esc(r.chain.last_hash || '')}</span>.`
    : `Audit trail BROKEN at event${r.chain.breaks.length === 1 ? '' : 's'} ${r.chain.breaks.map(b => '#' + b.id + ' (' + esc(b.problem) + ')').join(', ')}.`}</div>
${emails || '<p class="muted">No email reached an intake address in this window.</p>'}
<p class="muted small">Refused and dropped emails are kept as envelope only (from, to, times, reason): nothing inside them was opened. Each file’s SHA-256 is the fingerprint of the exact bytes received; the chain hashes tie every event to the one before it.</p>
</body></html>`;
}

module.exports = {report, toCsv, toHtml, window, DECISION};
