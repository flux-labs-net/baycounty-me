// Public records requests drafted in /admin ("Records requests" tab). Two kinds of drafts:
//   budget: from data/civic/records_requests.json (data/civic/scripts/records_requests.py, the budget years we're missing).
//   stale:  from data/civic/stale_requests.json (data/civic/scripts/stale_requests.py), places where an official source's
//           newest record is older than its usual schedule. One open draft per check and custodian; a gap already in a
//           sent or dismissed request is never drafted again. Letters are in _stale_requests.js.
// Nothing is sent until an admin presses Send (or dismisses the draft with a reason). Every action goes in the locked,
// hash-chained corr.records_request_log (migration 0098). A sent request becomes a corr.threads conversation with its own token,
// so the reply is matched and shows up under Correspondence like any other.
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const {q} = require('./_db');
const {FROM, resend} = require('./_alerts');
const {INBOX, composeEmail, messageIdFor, newToken} = require('./_correspondence');

const {compose} = require('./_stale_requests');

const FILE = path.join(__dirname, '..', 'data', 'civic', 'records_requests.json');
const STALE_FILE = path.join(__dirname, '..', 'data', 'civic', 'stale_requests.json');
const EMAIL = /^[^\s@<>]+@[^\s@<>]+\.[a-z]{2,}$/i;
const STATUSES = ['draft', 'sent', 'received', 'closed', 'dismissed'];
const sha = s => crypto.createHash('sha256').update(String(s)).digest('hex');

// One row in the request's locked history. actor is the admin's email or 'system'.
const log = (id, actor, action, detail = {}) => q(`insert into corr.records_request_log (request_id, actor, action, detail, prev_hash, hash) values ($1, $2, $3, $4, '', '')`,
  [id, actor || 'system', action, JSON.stringify(detail)]);
const err = (msg, status = 400) => Object.assign(new Error(msg), {status});
const key = () => process.env.RESEND_FULL_KEY || process.env.RESEND_API_KEY;

// "Lynne Fasone, City Clerk" -> "Lynne Fasone"; an office ("City Clerk", "Office of Communications") -> "Records Custodian".
function greetName(recipient) {
  const s = String(recipient || '').trim();
  const person = s.includes(',') ? s.split(',')[0].trim() : '';
  return person && !/office|clerk|records|department/i.test(person) ? person : 'Records Custodian';
}

function fileDrafts(file = FILE) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')).requests || []; } catch (e) { return null; }
}

// Adds drafts from the file and refreshes ones nobody has edited or sent. Edited (origin = 'manual') or sent rows stay as they are.
async function seed() {
  const stale = await seedStale().catch(e => { console.error('stale records requests', e.message); return {added: [], error: e.message}; });
  const f = fileDrafts();
  if (!f) return {added: 0, updated: 0, stale, note: 'data/civic/records_requests.json wasn’t found in this deployment.'};
  let added = 0, updated = 0;
  for (const d of f) {
    const r = await q(`insert into corr.records_requests (key, government, government_key, recipient_name, recipient_email, contact_url, subject, body, gaps, notes)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        on conflict (key) do update set government = excluded.government, government_key = excluded.government_key, recipient_name = excluded.recipient_name,
          recipient_email = excluded.recipient_email, contact_url = excluded.contact_url, subject = excluded.subject, body = excluded.body,
          gaps = excluded.gaps, notes = excluded.notes, updated_at = now()
        where corr.records_requests.origin = 'file' and corr.records_requests.status = 'draft'
          and (corr.records_requests.subject, corr.records_requests.body, corr.records_requests.recipient_email, corr.records_requests.gaps::text, corr.records_requests.notes)
            is distinct from (excluded.subject, excluded.body, excluded.recipient_email, excluded.gaps::text, excluded.notes)
        returning id, (xmax = 0) inserted`,
      [d.key, d.government, d.government_key || null, d.recipient_name || null, d.recipient_email && EMAIL.test(d.recipient_email) ? d.recipient_email : null,
       d.contact_url || null, d.subject, d.body, JSON.stringify(d.gaps || []), d.notes || null]);
    if (r.length) {
      r[0].inserted ? added++ : updated++;
      await log(r[0].id, 'system', r[0].inserted ? 'drafted' : 'refreshed', {gaps: (d.gaps || []).length, source: 'records_requests.json'});
    }
  }
  return {added, updated, stale};
}

// Drafts for stale sources. For each check and custodian in the file:
//  - gaps already in a sent, received, closed or dismissed request are left out (never asked twice);
//  - an open draft nobody has edited follows the file (gaps added or gone); an edited one is left as it is, and new gaps
//    wait for a new draft once it is sent or dismissed;
//  - with no open draft and gaps left, a new draft is made.
// An open draft whose gaps have all closed (newer records showed up at the source) is dismissed by the system.
async function seedStale(drafts = fileDrafts(STALE_FILE)) {
  if (!drafts) return {added: [], updated: 0, resolved: 0, note: 'data/civic/stale_requests.json wasn’t found in this deployment.'};
  const added = [];
  let updated = 0, resolved = 0;
  const current = new Set();
  for (const d of drafts) {
    const all = (d.gaps || []).filter(g => g && g.gap_id);
    all.forEach(g => current.add(g.gap_id));
    const done = new Set((await q(`select distinct unnest(gap_ids) g from corr.records_requests where status <> 'draft' and gap_ids && $1::text[]`,
      [all.map(g => g.gap_id)])).map(r => r.g));
    const gaps = all.filter(g => !done.has(g.gap_id));
    const [open] = await q(`select * from corr.records_requests where group_key = $1 and status = 'draft' order by id limit 1`, [d.key]);
    if (!gaps.length) continue;                                     // all requested already; an open draft is handled below
    const ids = gaps.map(g => g.gap_id).sort();
    const {subject, body} = compose(d.check, d.check_title, gaps);
    const email = d.recipient_email && EMAIL.test(d.recipient_email) ? d.recipient_email : null;
    if (open) {
      if (open.origin !== 'file') continue;
      const before = [...(open.gap_ids || [])].sort();
      if (before.join() === ids.join() && open.body === body && open.subject === subject) continue;
      await q(`update corr.records_requests set subject = $2, body = $3, gaps = $4, gap_ids = $5, recipient_name = $6, recipient_email = $7, contact_url = $8,
          notes = $9, check_title = $10, page = $11, updated_at = now() where id = $1`,
        [open.id, subject, body, JSON.stringify(gaps), ids, d.recipient_name || null, email, d.contact_url || null, d.notes || null, d.check_title || null, d.page || null]);
      await log(open.id, 'system', 'refreshed', {added: ids.filter(x => !before.includes(x)), removed: before.filter(x => !ids.includes(x))});
      updated++;
      continue;
    }
    const key = `${d.key}-${sha(ids.join('|')).slice(0, 10)}`;
    const [row] = await q(`insert into corr.records_requests (key, kind, group_key, gap_ids, check_title, page, government, government_key, recipient_name, recipient_email,
        contact_url, subject, body, gaps, notes) values ($1, 'stale', $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        on conflict (key) do nothing returning id`,
      [key, d.key, ids, d.check_title || null, d.page || null, d.government, d.government_key || null, d.recipient_name || null, email, d.contact_url || null,
       subject, body, JSON.stringify(gaps), d.notes || null]);
    if (!row) continue;                                             // same gaps drafted before and since dismissed or sent
    await log(row.id, 'system', 'drafted', {check: d.check, gaps: ids, to: email});
    added.push({id: row.id, government: d.government, subject, gaps: gaps.length});
  }
  // Open drafts whose gaps are all gone from the file: the source caught up.
  const open = await q(`select id, gap_ids from corr.records_requests where kind = 'stale' and status = 'draft'`);
  for (const o of open) {
    if ((o.gap_ids || []).some(g => current.has(g))) continue;
    await q(`update corr.records_requests set status = 'dismissed', dismissed_at = now(), dismissed_by = 'system',
        dismissed_reason = $2, updated_at = now() where id = $1`, [o.id, 'Newer records showed up at the official source, so this request isn’t needed.']);
    await log(o.id, 'system', 'resolved', {gaps: o.gap_ids});
    resolved++;
  }
  return {added, updated, resolved};
}

// Seeds on every open (a handful of rows), so drafts nobody has touched follow the latest file.
async function list() {
  await seed();
  const rows = await q(`select r.*, t.status thread_status, t.last_at thread_last_at from corr.records_requests r left join corr.threads t on t.id = r.thread_id
      order by (r.status = 'draft') desc, (r.kind = 'stale') desc, r.id desc`);
  const hist = await q(`select request_id, at, actor, action, detail from corr.records_request_log order by id`);
  const by = {};
  for (const h of hist) (by[h.request_id] = by[h.request_id] || []).push(h);
  rows.forEach(r => { r.history = by[r.id] || []; });
  return {requests: rows};
}

async function save(b, me) {
  const id = parseInt(b.id, 10);
  if (!id) throw err('Which request?');
  const f = {};
  if (b.recipient_email !== undefined) {
    const e = String(b.recipient_email || '').trim();
    if (e && !EMAIL.test(e)) throw err('That doesn’t look like an email address.');
    f.recipient_email = e || null;
  }
  if (b.recipient_name !== undefined) f.recipient_name = String(b.recipient_name || '').trim().slice(0, 200) || null;
  if (b.subject !== undefined) { f.subject = String(b.subject || '').trim().slice(0, 200); if (!f.subject) throw err('Add a subject.'); }
  if (b.body !== undefined) { f.body = String(b.body || '').trim().slice(0, 20000); if (f.body.length < 10) throw err('Write the request first.'); }
  if (b.notes !== undefined) f.notes = String(b.notes || '').trim().slice(0, 2000) || null;
  if (b.status !== undefined) {
    if (!STATUSES.includes(b.status)) throw err('Unknown status.');
    if (b.status === 'dismissed') throw err('Use Dismiss, with a reason.');
    f.status = b.status;
    if (b.status === 'draft') Object.assign(f, {dismissed_at: null, dismissed_by: null, dismissed_reason: null});
    if (b.status === 'sent') f.sent_at = new Date().toISOString(); // marked sent by hand (e.g. through a contact form)
  }
  const cols = Object.keys(f);
  if (!cols.length) throw err('Nothing to change.');
  const content = cols.some(c => ['recipient_email', 'recipient_name', 'subject', 'body', 'notes'].includes(c));
  const [row] = await q(`update corr.records_requests set ${cols.map((c, i) => `${c} = $${i + 2}`).join(', ')}${content ? ", origin = 'manual'" : ''}, updated_at = now()
      where id = $1 returning *`, [id, ...cols.map(c => f[c])]);
  if (!row) throw err('Request not found.', 404);
  const changed = cols.filter(c => !c.startsWith('dismissed_'));
  await log(row.id, me, b.status !== undefined ? 'status' : 'edited', {fields: changed, status: f.status, body_sha256: f.body ? sha(f.body) : undefined});
  return {request: row};
}

// Not sending a draft: needs a reason, kept in the history. Its gaps are never drafted again.
async function dismiss({id, reason}, me) {
  const why = String(reason || '').trim().slice(0, 500);
  if (why.length < 3) throw err('Say why you’re dismissing it.');
  const [row] = await q(`update corr.records_requests set status = 'dismissed', dismissed_at = now(), dismissed_by = $2, dismissed_reason = $3, updated_at = now()
      where id = $1 and status = 'draft' returning *`, [parseInt(id, 10) || 0, me, why]);
  if (!row) throw err('Only a draft can be dismissed.', 409);
  await log(row.id, me, 'dismissed', {reason: why, gaps: row.gap_ids});
  return {request: row};
}

// Sends one request. test: a preview to the signed-in admin only, nothing stored or changed.
async function send({id, test}, me) {
  const [r] = await q('select * from corr.records_requests where id = $1', [parseInt(id, 10) || 0]);
  if (!r) throw err('Request not found.', 404);
  if (!key()) throw err('RESEND_FULL_KEY isn’t set in Vercel.', 500);
  const name = greetName(r.recipient_name);
  if (test) {
    const m = composeEmail({subject: r.subject, body: r.body, name, token: 'TEST0000', kind: 'records'});
    const s = await resend('/emails', 'POST', {from: FROM, to: [me], reply_to: INBOX, subject: '[Test] ' + m.subject, html: m.html, text: m.text}, key());
    if (!s.ok) throw err('Resend didn’t accept the test (' + s.status + ').', 502);
    await log(r.id, me, 'test_sent', {to: me});
    return {ok: true, test: true, to: me};
  }
  if (r.status !== 'draft') throw err('This request was already sent.');
  if (!r.recipient_email) throw err('Add the recipient’s email address first.');
  const token = newToken(), msgId = messageIdFor(token, 0);
  const m = composeEmail({subject: r.subject, body: r.body, name, token, kind: 'records'});
  const [t] = await q(`insert into corr.threads (token, official_name, official_seat, government, email, subject)
      values ($1, $2, $3, $4, $5, $6) returning id`, [token, r.recipient_name, 'Records request', r.government, r.recipient_email, r.subject]);
  const s = await resend('/emails', 'POST', {from: FROM, to: [r.recipient_email], reply_to: INBOX, subject: m.subject, html: m.html, text: m.text,
    headers: {'Message-ID': msgId}, tags: [{name: 'kind', value: 'records-request'}]}, key());
  await q(`insert into corr.messages (thread_id, direction, from_addr, to_addr, subject, body_text, message_id, resend_id, status)
      values ($1, 'out', $2, $3, $4, $5, $6, $7, $8)`, [t.id, FROM, r.recipient_email, m.subject, r.body, msgId, s.ok && s.body ? s.body.id : null, s.ok ? 'sent' : 'failed']);
  if (!s.ok) {
    await q('delete from corr.threads where id = $1', [t.id]);
    await log(r.id, me, 'send_failed', {to: r.recipient_email, status: s.status});
    throw err('Resend didn’t accept the email (' + s.status + '). Nothing was marked sent.', 502);
  }
  const [row] = await q(`update corr.records_requests set status = 'sent', thread_id = $2, sent_at = now(), sent_by = $3, updated_at = now() where id = $1 returning *`, [r.id, t.id, me]);
  await log(r.id, me, 'sent', {to: r.recipient_email, subject: m.subject, body_sha256: sha(r.body), message_id: msgId, resend_id: s.body ? s.body.id : null, thread_id: t.id, gaps: r.gap_ids});
  return {ok: true, request: row, thread_id: t.id};
}

// The daily check (alerts-run): makes new drafts and tells the admins when there are new ones to review.
async function autoDraft(admins, sendMail) {
  const r = await seedStale();
  if (r.added && r.added.length && admins.length && sendMail) await sendMail(admins, newDraftsNotice(r.added));
  return r;
}

function newDraftsNotice(added) {
  const ui = require('./_email_ui');
  const n = added.length, s = n === 1 ? '' : 's';
  const subject = `${n} records request${s} drafted for stale data`;
  return ui.adminNotice({subject, kicker: 'Records requests', tone: 'amber', icon: 'mail', eyebrow: 'Waiting for your approval',
    title: `${n} new records request${s} to review`, preheader: added.map(a => a.government).join(', '),
    body: ui.list(added.map(a => ['amber', 'Draft', `<b>${ui.esc(a.government)}</b><br>${ui.esc(a.subject)}`])) +
      ui.button(`${ui.SITE}/admin#records`, 'Review in admin') +
      ui.small('An official source stopped publishing on its usual schedule. Nothing is sent until you approve it.'),
    text: added.map(a => `${a.government}: ${a.subject}`).join('\n') + `\n\nReview: ${ui.SITE}/admin#records`});
}

module.exports = {seed, seedStale, list, save, dismiss, send, greetName, autoDraft, newDraftsNotice, log};
