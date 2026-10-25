// Public records requests drafted in /admin ("Records requests" tab). Drafts are seeded from
// data/civic/records_requests.json (made by data/civic/scripts/records_requests.py from the budget years we're missing).
// Nothing is sent until an admin presses Send. A sent request becomes a corr.threads conversation with its own token,
// so the reply is matched and shows up under Correspondence like any other.
const fs = require('fs');
const path = require('path');
const {q} = require('./_db');
const {FROM, resend} = require('./_alerts');
const {INBOX, composeEmail, messageIdFor, newToken} = require('./_correspondence');

const FILE = path.join(__dirname, '..', 'data', 'civic', 'records_requests.json');
const EMAIL = /^[^\s@<>]+@[^\s@<>]+\.[a-z]{2,}$/i;
const STATUSES = ['draft', 'sent', 'received', 'closed'];
const err = (msg, status = 400) => Object.assign(new Error(msg), {status});
const key = () => process.env.RESEND_FULL_KEY || process.env.RESEND_API_KEY;

// "Lynne Fasone, City Clerk" -> "Lynne Fasone"; an office ("City Clerk", "Office of Communications") -> "Records Custodian".
function greetName(recipient) {
  const s = String(recipient || '').trim();
  const person = s.includes(',') ? s.split(',')[0].trim() : '';
  return person && !/office|clerk|records|department/i.test(person) ? person : 'Records Custodian';
}

function fileDrafts() {
  try { return JSON.parse(fs.readFileSync(FILE, 'utf8')).requests || []; } catch (e) { return null; }
}

// Adds drafts from the file and refreshes ones nobody has edited or sent. Edited (origin = 'manual') or sent rows stay as they are.
async function seed() {
  const f = fileDrafts();
  if (!f) return {added: 0, updated: 0, note: 'data/civic/records_requests.json wasn’t found in this deployment.'};
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
        returning (xmax = 0) inserted`,
      [d.key, d.government, d.government_key || null, d.recipient_name || null, d.recipient_email && EMAIL.test(d.recipient_email) ? d.recipient_email : null,
       d.contact_url || null, d.subject, d.body, JSON.stringify(d.gaps || []), d.notes || null]);
    if (r.length) r[0].inserted ? added++ : updated++;
  }
  return {added, updated};
}

async function list() {
  let rows = await q(`select r.*, t.status thread_status, t.last_at thread_last_at from corr.records_requests r left join corr.threads t on t.id = r.thread_id order by r.id`);
  if (!rows.length) { await seed(); rows = await q(`select r.*, null thread_status, null thread_last_at from corr.records_requests r order by r.id`); }
  return {requests: rows};
}

async function save(b) {
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
    f.status = b.status;
    if (b.status === 'sent') f.sent_at = new Date().toISOString(); // marked sent by hand (e.g. through a contact form)
  }
  const cols = Object.keys(f);
  if (!cols.length) throw err('Nothing to change.');
  const content = cols.some(c => ['recipient_email', 'recipient_name', 'subject', 'body', 'notes'].includes(c));
  const [row] = await q(`update corr.records_requests set ${cols.map((c, i) => `${c} = $${i + 2}`).join(', ')}${content ? ", origin = 'manual'" : ''}, updated_at = now()
      where id = $1 returning *`, [id, ...cols.map(c => f[c])]);
  if (!row) throw err('Request not found.', 404);
  return {request: row};
}

// Sends one request. test: a preview to the signed-in admin only, nothing stored or changed.
async function send({id, test}, me) {
  const [r] = await q('select * from corr.records_requests where id = $1', [parseInt(id, 10) || 0]);
  if (!r) throw err('Request not found.', 404);
  if (!key()) throw err('RESEND_FULL_KEY isn’t set in Vercel.', 500);
  const name = greetName(r.recipient_name);
  if (test) {
    const m = composeEmail({subject: r.subject, body: r.body, name, token: 'TEST0000'});
    const s = await resend('/emails', 'POST', {from: FROM, to: [me], reply_to: INBOX, subject: '[Test] ' + m.subject, html: m.html, text: m.text}, key());
    if (!s.ok) throw err('Resend didn’t accept the test (' + s.status + ').', 502);
    return {ok: true, test: true, to: me};
  }
  if (r.status !== 'draft') throw err('This request was already sent.');
  if (!r.recipient_email) throw err('Add the recipient’s email address first.');
  const token = newToken(), msgId = messageIdFor(token, 0);
  const m = composeEmail({subject: r.subject, body: r.body, name, token});
  const [t] = await q(`insert into corr.threads (token, official_name, official_seat, government, email, subject)
      values ($1, $2, $3, $4, $5, $6) returning id`, [token, r.recipient_name, 'Records request', r.government, r.recipient_email, r.subject]);
  const s = await resend('/emails', 'POST', {from: FROM, to: [r.recipient_email], reply_to: INBOX, subject: m.subject, html: m.html, text: m.text,
    headers: {'Message-ID': msgId}, tags: [{name: 'kind', value: 'records-request'}]}, key());
  await q(`insert into corr.messages (thread_id, direction, from_addr, to_addr, subject, body_text, message_id, resend_id, status)
      values ($1, 'out', $2, $3, $4, $5, $6, $7, $8)`, [t.id, FROM, r.recipient_email, m.subject, r.body, msgId, s.ok && s.body ? s.body.id : null, s.ok ? 'sent' : 'failed']);
  if (!s.ok) {
    await q('delete from corr.threads where id = $1', [t.id]);
    throw err('Resend didn’t accept the email (' + s.status + '). Nothing was marked sent.', 502);
  }
  const [row] = await q(`update corr.records_requests set status = 'sent', thread_id = $2, sent_at = now(), sent_by = $3, updated_at = now() where id = $1 returning *`, [r.id, t.id, me]);
  return {ok: true, request: row, thread_id: t.id};
}

module.exports = {seed, list, save, send, greetName};
