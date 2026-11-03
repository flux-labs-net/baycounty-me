// Correspondence with officials. Used by /api/admin (compose, threads, contacts, publishing), by the Resend inbound
// webhook (/api/agenda-inbound, for mail to hello@baycounty.me) and by /api/v1/correspondence (published threads only).
//
// Each recipient gets their own email and their own thread. One email to a whole board would let members reply-all
// to each other, which can become a meeting outside the public eye under Florida's Sunshine Law.
// Replies are matched to a thread by, in order: the In-Reply-To/References headers (our Message-ID carries the
// thread token), the "Ref: BCM-..." line quoted back in the reply, then the sender's address. Anything left over is
// kept as unmatched so it can be assigned by hand. Every conversation is public on /correspondence by default (migration 0094).
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const {q} = require('./_db');
const {FROM, SITE, resend, esc} = require('./_alerts');
const ui = require('./_email_ui');
const {admins} = require('./_session');

const INBOX = String(process.env.CORR_INBOX || 'hello@baycounty.me').toLowerCase();
const CONTACTS_FILE = path.join(__dirname, '..', 'data', 'civic', 'official_contacts.json');
const MAX_RECIPIENTS = 75;
const err = (msg, status = 400) => Object.assign(new Error(msg), {status});
const key = () => process.env.RESEND_FULL_KEY || process.env.RESEND_API_KEY;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const addrOf = s => { const m = String(s || '').match(/<([^>]+)>/); return (m ? m[1] : String(s || '')).trim().toLowerCase(); };
const EMAIL = /^[^\s@<>]+@[^\s@<>]+\.[a-z]{2,}$/i;

// ---------- pure helpers (tested) ----------

const newToken = () => crypto.randomBytes(6).toString('base64url').replace(/[-_]/g, 'x').toUpperCase().slice(0, 8);
const messageIdFor = (token, n = 0) => `<bcm-${token.toLowerCase()}-${n}@baycounty.me>`;

// The thread token from a reply's In-Reply-To/References, or from a "Ref: BCM-XXXXXXXX" line quoted in its body.
function tokenFrom({inReplyTo = '', references = '', text = '', subject = ''} = {}) {
  const h = String(inReplyTo) + ' ' + String(references);
  const m = h.match(/<bcm-([a-z0-9]{8})-\d+@baycounty\.me>/i);
  if (m) return {token: m[1].toUpperCase(), by: 'header'};
  const r = (String(text) + '\n' + String(subject)).match(/\bBCM-([A-Z0-9]{8})\b/i);
  if (r) return {token: r[1].toUpperCase(), by: 'token'};
  return null;
}

// The new part of a reply: drops quoted history ("On ... wrote:", "-----Original Message-----", Outlook "From:" blocks,
// lines starting with ">") and our own footer. Returns {text, quoted} where quoted says whether anything was cut.
function stripQuoted(text) {
  const lines = String(text || '').replace(/\r\n?/g, '\n').split('\n');
  let cut = lines.length;
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i].trim(), next = (lines[i + 1] || '').trim();
    const wrote = /^On .{4,200}wrote:$/i.test(l) || (/^On .{4,200}$/i.test(l) && /wrote:$/i.test(next) && l.length + next.length < 260);
    const outlook = /^-{2,}\s*Original Message\s*-{2,}$/i.test(l) || /^_{8,}$/.test(l) ||
      (/^From:\s/i.test(l) && lines.slice(i + 1, i + 5).some(x => /^(Sent|Date|To|Subject):\s/i.test(x.trim())));
    if (wrote || outlook || /^>/.test(l)) { cut = i; break; }
  }
  const kept = lines.slice(0, cut).join('\n').replace(/\n*Sent from BayCounty\.me[\s\S]*$/i, '').trim();
  return {text: kept, quoted: cut < lines.length};
}

// The outgoing email for one official. body is plain text written in /admin. kind: 'records' for a records request.
// Letters stay plain on purpose (no badge or big button): they go to government inboxes and should read like mail.
function composeEmail({subject, body, name, token, kind}) {
  const paras = String(body).trim().split(/\n{2,}/).map(p => ui.p(esc(p).replace(/\n/g, '<br>'))).join('');
  const footerText = `Sent from BayCounty.me, an independent public-records site for Bay County, Florida. Replies come to ${INBOX} and may be published at ${SITE}/correspondence as public records (Chapter 119, Florida Statutes). Ref: BCM-${token}`;
  const first = String(body).trim().split(/\n/)[0] || '';
  const html = ui.layout({title: subject, preheader: (name ? greeting(name) + ', ' : '') + first.slice(0, 120),
    kicker: kind === 'records' ? 'Public records request' : 'Public correspondence',
    body: (name ? ui.p(`${esc(greeting(name))},`) : '') + paras,
    letter: `${esc(footerText.replace(` Ref: BCM-${token}`, ''))}<br><span class="bc-fa" style="font-family:${ui.MONO};font-size:12px;color:${ui.C.faint}">Ref: BCM-${esc(token)}</span>`});
  const text = (name ? greeting(name) + ',\n\n' : '') + String(body).trim() + '\n\n--\n' + footerText + '\n';
  return {subject, html, text};
}
function greeting(name) {
  const clean = String(name || '').replace(/\s*\(.*?\)\s*/g, ' ').trim();
  return clean ? 'Dear ' + clean : 'Hello';
}

// ---------- contacts ----------

function fileContacts() {
  try { return JSON.parse(fs.readFileSync(CONTACTS_FILE, 'utf8')); } catch (e) { return null; }
}

// Adds new people from the file and refreshes file-origin rows. Rows edited in /admin (origin = 'manual') are left alone.
// File-origin rows no longer in the file (someone left the seat) are turned off, not deleted, so their threads keep a name.
async function seed() {
  const f = fileContacts();
  if (!f) return {added: 0, updated: 0, retired: 0, note: 'data/civic/official_contacts.json wasn’t found in this deployment.'};
  let added = 0, updated = 0;
  const keep = [];
  for (const g of f.governments || []) {
    for (const s of g.seats || []) {
      const email = s.email && EMAIL.test(s.email) ? s.email.trim() : null;
      const name = s.holder || null;
      keep.push([g.government, s.seat, name || ''].join('\u0001'));
      const r = await q(`insert into corr.contacts (government, government_key, seat, name, email, source_url, elected, notes)
          values ($1, $2, $3, $4, $5, $6, $7, $8)
          on conflict (government, seat, coalesce(name, '')) do update set government_key = excluded.government_key, email = excluded.email,
            source_url = excluded.source_url, elected = excluded.elected, notes = excluded.notes, active = true, updated_at = now()
          where corr.contacts.origin = 'file' and (corr.contacts.email, corr.contacts.source_url, corr.contacts.notes, corr.contacts.active)
            is distinct from (excluded.email, excluded.source_url, excluded.notes, true)
          returning (xmax = 0) inserted`,
        [g.government, g.key || null, s.seat, name, email, s.source_url || null, s.elected !== false, s.notes || null]);
      if (r.length) r[0].inserted ? added++ : updated++;
    }
  }
  const gone = await q(`update corr.contacts set active = false, updated_at = now()
      where origin = 'file' and active and not (government || chr(1) || seat || chr(1) || coalesce(name, '') = any($1::text[])) returning id`, [keep]);
  return {added, updated, retired: gone.length};
}

async function contacts() {
  let rows = await q('select * from corr.contacts order by government, id');
  if (!rows.length) { await seed(); rows = await q('select * from corr.contacts order by government, id'); }
  const f = fileContacts();
  return {contacts: rows, shared: (f && f.governments || []).filter(g => g.shared_email || g.contact_form)
    .map(g => ({government: g.government, shared_email: g.shared_email || null, contact_form: g.contact_form || null}))};
}

async function saveContact(b, me) {
  const id = parseInt(b.id, 10);
  if (!id) throw err('Which contact?');
  const f = {};
  if (b.email !== undefined) {
    const email = String(b.email || '').trim();
    if (email && !EMAIL.test(email)) throw err('That doesn’t look like an email address.');
    f.email = email || null;
  }
  if (b.name !== undefined) f.name = String(b.name || '').trim().slice(0, 200) || null;
  if (b.notes !== undefined) f.notes = String(b.notes || '').trim().slice(0, 1000) || null;
  if (b.source_url !== undefined) f.source_url = String(b.source_url || '').trim().slice(0, 500) || null;
  if (typeof b.active === 'boolean') f.active = b.active;
  const cols = Object.keys(f);
  if (!cols.length) throw err('Nothing to change.');
  const [row] = await q(`update corr.contacts set ${cols.map((c, i) => `${c} = $${i + 2}`).join(', ')}, origin = 'manual', updated_at = now() where id = $1 returning *`,
    [id, ...cols.map(c => f[c])]);
  if (!row) throw err('Contact not found.', 404);
  return {contact: row, by: me};
}

// ---------- sending ----------

async function send({subject, body, ids, test}, me) {
  subject = String(subject || '').trim().slice(0, 200);
  body = String(body || '').trim().slice(0, 20000);
  if (!subject) throw err('Add a subject.');
  if (body.length < 10) throw err('Write a message first.');
  if (!key()) throw err('RESEND_FULL_KEY isn’t set in Vercel.', 500);
  const want = [...new Set((ids || []).map(n => parseInt(n, 10)).filter(Boolean))];

  if (test) {
    // A preview to the signed-in admin only, using the first selected official's name. Nothing is stored.
    const [c] = want.length ? await q('select name from corr.contacts where id = $1', [want[0]]) : [{}];
    const m = composeEmail({subject, body, name: c && c.name, token: 'TEST0000'});
    const r = await resend('/emails', 'POST', {from: FROM, to: [me], reply_to: INBOX, subject: '[Test] ' + m.subject, html: m.html, text: m.text}, key());
    if (!r.ok) throw err('Resend didn’t accept the test (' + r.status + ').', 502);
    return {ok: true, test: true, to: me};
  }

  if (!want.length) throw err('Pick at least one official.');
  if (want.length > MAX_RECIPIENTS) throw err(`That’s more than ${MAX_RECIPIENTS} people in one send.`);
  const people = await q('select * from corr.contacts where id = any($1::bigint[]) and active and email is not null order by government, id', [want]);
  if (!people.length) throw err('None of the selected officials has an email address on file.');
  const govs = [...new Set(people.map(p => p.government))];
  const [batch] = await q(`insert into corr.batches (subject, body_text, government, recipient_count, created_by) values ($1, $2, $3, $4, $5) returning id`,
    [subject, body, govs.length === 1 ? govs[0] : null, people.length, me]);

  const results = [];
  for (const p of people) {
    const token = newToken();
    const msgId = messageIdFor(token, 0);
    const m = composeEmail({subject, body, name: p.name, token});
    const [t] = await q(`insert into corr.threads (token, batch_id, contact_id, official_name, official_seat, government, email, subject)
        values ($1, $2, $3, $4, $5, $6, $7, $8) returning id`, [token, batch.id, p.id, p.name, p.seat, p.government, p.email, subject]);
    // One recipient per email, never cc or bcc, so replies come only to us.
    const r = await resend('/emails', 'POST', {from: FROM, to: [p.email], reply_to: INBOX, subject: m.subject, html: m.html, text: m.text,
      headers: {'Message-ID': msgId}, tags: [{name: 'kind', value: 'correspondence'}]}, key());
    const status = r.ok ? 'sent' : 'failed';
    await q(`insert into corr.messages (thread_id, direction, from_addr, to_addr, subject, body_text, message_id, resend_id, status)
        values ($1, 'out', $2, $3, $4, $5, $6, $7, $8)`, [t.id, FROM, p.email, m.subject, body, msgId, r.ok && r.body ? r.body.id : null, status]);
    results.push({contact_id: p.id, name: p.name, seat: p.seat, government: p.government, ok: r.ok, error: r.ok ? null : ((r.body && r.body.message) || 'Resend error ' + r.status)});
    await sleep(250); // stays under Resend's default rate limit
  }
  const skipped = want.length - people.length;
  return {batch_id: batch.id, sent: results.filter(x => x.ok).length, failed: results.filter(x => !x.ok), skipped};
}

// A follow-up in an existing thread, sent as a reply so it threads in the official's mail client.
async function reply({thread_id, body}, me) {
  body = String(body || '').trim().slice(0, 20000);
  if (body.length < 2) throw err('Write a reply first.');
  const [t] = await q('select * from corr.threads where id = $1', [parseInt(thread_id, 10) || 0]);
  if (!t) throw err('Thread not found.', 404);
  if (!t.email) throw err('This thread has no address to reply to.');
  const prev = await q(`select message_id from corr.messages where thread_id = $1 and message_id is not null order by at`, [t.id]);
  const n = prev.length;
  const msgId = messageIdFor(t.token, n);
  const subj = /^re:/i.test(t.subject) ? t.subject : 'Re: ' + t.subject;
  const m = composeEmail({subject: subj, body, name: t.official_name, token: t.token});
  const refs = prev.map(x => x.message_id).join(' ');
  const r = await resend('/emails', 'POST', {from: FROM, to: [t.email], reply_to: INBOX, subject: subj, html: m.html, text: m.text,
    headers: {'Message-ID': msgId, ...(refs ? {'In-Reply-To': prev[n - 1].message_id, References: refs} : {})}, tags: [{name: 'kind', value: 'correspondence'}]}, key());
  if (!r.ok) throw err('Resend didn’t accept the reply (' + r.status + ').', 502);
  await q(`insert into corr.messages (thread_id, direction, from_addr, to_addr, subject, body_text, message_id, in_reply_to, resend_id, status)
      values ($1, 'out', $2, $3, $4, $5, $6, $7, $8, 'sent')`, [t.id, FROM, t.email, subj, body, msgId, n ? prev[n - 1].message_id : null, r.body.id]);
  await q(`update corr.threads set last_at = now(), status = case when status = 'closed' then 'awaiting' else status end where id = $1`, [t.id]);
  return {ok: true, by: me};
}

// ---------- inbound ----------

const forInbox = data => [].concat(data.to || [], data.cc || [], data.bcc || [], data.received_for || []).some(a => addrOf(a) === INBOX || String(a).toLowerCase().includes(INBOX));

function header(h, name) {
  if (!h) return '';
  if (Array.isArray(h)) { const x = h.find(e => String(e.name || e.key || '').toLowerCase() === name); return x ? String(x.value || '') : ''; }
  const k = Object.keys(h).find(k => k.toLowerCase() === name);
  return k ? String(Array.isArray(h[k]) ? h[k].join(' ') : h[k]) : '';
}

// Called by the inbound webhook with a Resend received-email id. Safe to call twice for the same email.
async function inbound(emailId) {
  const [dup] = await q('select id from corr.messages where resend_id = $1', [emailId]);
  if (dup) return {ok: true, duplicate: true};
  const r = await resend('/emails/receiving/' + encodeURIComponent(emailId), 'GET', null, key());
  if (!r.ok) throw err('Couldn’t read the received email (' + r.status + ').', 502);
  const d = r.body || {};
  const h = d.headers || {};
  const from = addrOf(d.from || header(h, 'from'));
  const info = {inReplyTo: header(h, 'in-reply-to') || d.in_reply_to || '', references: header(h, 'references') || '', text: d.text || '', subject: d.subject || ''};

  let thread = null, by = null;
  const tk = tokenFrom(info);
  if (tk) { [thread] = await q('select * from corr.threads where token = $1', [tk.token]); if (thread) by = tk.by; }
  if (!thread && from) {
    [thread] = await q(`select * from corr.threads where lower(email) = $1 order by last_at desc limit 1`, [from]);
    if (thread) by = 'address';
  }
  const atts = (d.attachments || []).map(a => ({filename: a.filename, content_type: a.content_type, size: a.size || null}));
  const msgId = d.message_id || header(h, 'message-id') || null;
  const [row] = await q(`insert into corr.messages (thread_id, direction, from_addr, to_addr, cc, subject, body_text, body_html, message_id, in_reply_to, resend_id, status, attachments, matched_by, at)
      values ($1, 'in', $2, $3, $4, $5, $6, $7, $8, $9, $10, 'received', $11, $12, coalesce($13::timestamptz, now()))
      on conflict do nothing returning id`,
    [thread ? thread.id : null, d.from || from, [].concat(d.to || []).join(', '), JSON.stringify(d.cc || []), d.subject || '', String(d.text || '').slice(0, 50000),
     String(d.html || '').slice(0, 200000), msgId, info.inReplyTo || null, emailId, JSON.stringify(atts), by, d.created_at || null]);
  if (!row) return {ok: true, duplicate: true};
  if (thread) await q(`update corr.threads set status = 'replied', last_at = now() where id = $1`, [thread.id]);
  await notifyAdmins(thread, d, from, by).catch(e => console.error('corr notify', e.message));
  return {ok: true, matched: !!thread, by};
}

async function notifyAdmins(thread, d, from, by) {
  const to = admins();
  if (!to.length || !key()) return;
  await resend('/emails', 'POST', {from: FROM, to, ...replyNotice(thread, d, from, by)}, key());
}

// The admin notice for an inbound email: {subject, html, text}. thread is null when it matched nothing.
function replyNotice(thread, d, from, by) {
  const who = thread ? `${thread.official_name || from} (${thread.official_seat}, ${thread.government})` : from;
  const subject = thread ? `Reply from ${thread.official_name || from}: ${thread.subject}` : `Unmatched email to ${INBOX}: ${d.subject || '(no subject)'}`;
  const snippet = stripQuoted(d.text || '').text.slice(0, 600);
  const atts = (d.attachments || []).length;
  const html = ui.layout({title: subject, preheader: `“${snippet.slice(0, 120)}”`, kicker: 'Correspondence',
    hero: thread ? {tone: 'teal', icon: 'reply', eyebrow: by === 'address' ? 'New reply · Matched by sender' : 'New reply · Matched to a thread', title: `${esc(thread.official_name || from)} replied`}
                 : {tone: 'amber', icon: 'mail', eyebrow: 'New email · Not matched yet', title: `Email to ${esc(INBOX)}`},
    body: ui.facts([['From', esc(who)], ['Subject', esc(d.subject || '(no subject)')], ...(thread ? [['Thread', esc(thread.subject)]] : []), ...(atts ? [['Attachments', `${atts} file${atts === 1 ? '' : 's'}`]] : [])]) +
      ui.quote(snippet || '(no text)') + ui.button(`${SITE}/admin#correspondence`, thread ? 'Open in Correspondence' : 'Match it to a thread') +
      ui.small('Conversations with officials and governments are public on /correspondence automatically. Residents’ addresses and phone numbers are hidden; hide a name in Conversations if needed.'),
    footer: ui.adminFooter()});
  return {subject, html, text: `${who} wrote:\n\n${snippet}\n\n${SITE}/admin#correspondence`};
}

// ---------- admin views ----------

async function threads({status = '', government = '', published = '', q: needle = '', year = ''} = {}) {
  const p = [], w = ['true'];
  if (status) { p.push(status); w.push(`t.status = $${p.length}`); }
  if (government) { p.push(government); w.push(`t.government = $${p.length}`); }
  if (published === 'yes') w.push('t.published'); else if (published === 'no') w.push('not t.published');
  if (/^\d{4}$/.test(String(year))) { p.push(Number(year)); w.push(`extract(year from t.created_at at time zone 'America/Chicago') = $${p.length}`); }
  if (needle) { p.push('%' + String(needle).toLowerCase() + '%'); w.push(`(lower(t.subject) like $${p.length} or lower(coalesce(t.official_name, '')) like $${p.length} or lower(coalesce(t.email, '')) like $${p.length})`); }
  const rows = await q(`select t.id, t.batch_id, t.official_name, t.official_seat, t.government, t.email, t.subject, t.status, t.published, t.created_at, t.last_at,
      (select count(*)::int from corr.messages m where m.thread_id = t.id and m.direction = 'out') sent,
      (select count(*)::int from corr.messages m where m.thread_id = t.id and m.direction = 'in') received,
      (select m.status from corr.messages m where m.thread_id = t.id and m.direction = 'out' order by m.at desc limit 1) delivery
    from corr.threads t where ${w.join(' and ')} order by t.last_at desc limit 300`, p);
  const unmatched = await q(`select id, from_addr, subject, left(body_text, 300) snippet, at from corr.messages where thread_id is null order by at desc limit 50`);
  const [tot] = await q(`select count(*)::int threads, count(*) filter (where status = 'awaiting')::int awaiting, count(*) filter (where status = 'replied')::int replied,
      count(*) filter (where published)::int published from corr.threads`);
  const years = (await q(`select distinct extract(year from created_at at time zone 'America/Chicago')::int y from corr.threads order by 1 desc`)).map(r => r.y);
  const govs = (await q(`select distinct government from corr.threads where government is not null order by 1`)).map(r => r.government);
  return {threads: rows, unmatched, totals: tot, years, governments: govs};
}

const FINAL = new Set(['delivered', 'bounced', 'complained', 'failed', 'opened', 'clicked', 'suppressed', 'canceled']);
async function thread(id) {
  const [t] = await q('select * from corr.threads where id = $1', [parseInt(id, 10) || 0]);
  if (!t) throw err('Thread not found.', 404);
  const msgs = await q('select id, direction, from_addr, to_addr, cc, subject, body_text, status, attachments, matched_by, resend_id, at from corr.messages where thread_id = $1 order by at', [t.id]);
  // Refresh delivery status for sent emails that haven't settled yet.
  for (const m of msgs.filter(m => m.direction === 'out' && m.resend_id && !FINAL.has(m.status)).slice(0, 10)) {
    const r = await resend('/emails/' + encodeURIComponent(m.resend_id), 'GET', null, key()).catch(() => null);
    const s = r && r.ok && r.body && r.body.last_event;
    if (s && s !== m.status) { m.status = s; await q('update corr.messages set status = $2 where id = $1', [m.id, s]); }
  }
  return {thread: t, messages: msgs.map(m => ({...m, shown: m.direction === 'in' ? stripQuoted(m.body_text) : {text: m.body_text, quoted: false}}))};
}

// Conversations are public by default (migration 0094). Taking one down needs a reason, which the public page shows
// in its place; putting it back clears the reason.
async function publish({id, published, batch, reason}, me) {
  const on = !!published;
  const why = String(reason || '').trim().slice(0, 500);
  if (!on && why.length < 5) throw err('Say why this conversation comes down. The reason is shown on the public page in its place.');
  const set = `published = $2, published_at = case when $2 then coalesce(published_at, now()) end, published_by = case when $2 then $3 end, hidden_reason = case when $2 then null else $4 end`;
  const rows = batch
    ? await q(`update corr.threads set ${set} where batch_id = $1 returning id`, [parseInt(batch, 10) || 0, on, me, why || null])
    : await q(`update corr.threads set ${set} where id = $1 returning id`, [parseInt(id, 10) || 0, on, me, why || null]);
  if (!rows.length) throw err('Thread not found.', 404);
  return {ok: true, changed: rows.length, published: on};
}

// Words hidden on the public page (a resident's name, say), for one conversation or everywhere.
async function redactions({thread_key = ''} = {}) {
  return {redactions: await q(`select id, thread_key, phrase, reason, added_by, added_at from corr.redactions where $1 = '' or thread_key = $1 or thread_key is null order by added_at desc`, [String(thread_key)])};
}
async function redactSet({thread_key, phrase, reason, remove}, me) {
  if (remove) { await q('delete from corr.redactions where id = $1', [parseInt(remove, 10) || 0]); return {ok: true}; }
  const p = String(phrase || '').trim();
  if (p.length < 2) throw err('Type the words to hide.');
  const k = thread_key && /^[cem]\d{1,12}$/.test(thread_key) ? thread_key : null;
  await q(`insert into corr.redactions (thread_key, phrase, reason, added_by) values ($1, $2, $3, $4) on conflict do nothing`, [k, p.slice(0, 200), String(reason || '').slice(0, 300) || null, me]);
  return {ok: true};
}

async function setStatus({id, status}) {
  if (!['awaiting', 'replied', 'closed'].includes(status)) throw err('Unknown status.');
  const [row] = await q('update corr.threads set status = $2 where id = $1 returning id', [parseInt(id, 10) || 0, status]);
  if (!row) throw err('Thread not found.', 404);
  return {ok: true};
}

async function assign({message_id, thread_id}) {
  const [t] = await q('select id from corr.threads where id = $1', [parseInt(thread_id, 10) || 0]);
  if (!t) throw err('Thread not found.', 404);
  const [m] = await q(`update corr.messages set thread_id = $2, matched_by = 'manual' where id = $1 and direction = 'in' returning id`, [parseInt(message_id, 10) || 0, t.id]);
  if (!m) throw err('Message not found.', 404);
  await q(`update corr.threads set status = 'replied', last_at = now() where id = $1`, [t.id]);
  return {ok: true};
}

async function dismiss({message_id}) {
  const [m] = await q('delete from corr.messages where id = $1 and thread_id is null returning id', [parseInt(message_id, 10) || 0]);
  if (!m) throw err('Only unmatched messages can be dismissed.', 404);
  return {ok: true};
}

// ---------- public ----------

// Published threads only, newest first, grouped by the message that started them. No email addresses are returned:
// officials are shown by name and seat, and BayCounty.me by name.
async function publicFeed({year = '', government = ''} = {}) {
  const p = [], w = ['t.published'];
  if (government) { p.push(String(government)); w.push(`t.government = $${p.length}`); }
  const all = await q(`select t.id, t.batch_id, t.official_name, t.official_seat, t.government, t.subject, t.status, t.created_at, t.published_at
    from corr.threads t where ${w.join(' and ')} order by t.created_at desc limit 1000`, p);
  const years = [...new Set(all.map(t => new Date(t.created_at).getFullYear()))].sort((a, b) => b - a);
  const y = year === 'all' ? null : (/^\d{4}$/.test(String(year)) ? Number(year) : years[0] || null);
  const list = y ? all.filter(t => new Date(t.created_at).getFullYear() === y) : all;
  const ids = list.map(t => t.id);
  const msgs = ids.length ? await q(`select thread_id, direction, body_text, at from corr.messages where thread_id = any($1::bigint[]) order by at`, [ids]) : [];
  const byThread = new Map();
  for (const m of msgs) {
    const shown = m.direction === 'in' ? stripQuoted(m.body_text).text : m.body_text;
    (byThread.get(m.thread_id) || byThread.set(m.thread_id, []).get(m.thread_id)).push({direction: m.direction, text: shown, at: m.at});
  }
  const batches = new Map();
  for (const t of list) {
    const k = t.batch_id || 't' + t.id;
    if (!batches.has(k)) batches.set(k, {subject: t.subject, sent_at: t.created_at, governments: new Set(), threads: []});
    const b = batches.get(k);
    b.governments.add(t.government);
    b.threads.push({id: t.id, official: t.official_name, seat: t.official_seat, government: t.government, status: t.status, messages: byThread.get(t.id) || []});
  }
  const out = [...batches.values()].map(b => ({...b, governments: [...b.governments],
    replies: b.threads.filter(t => t.messages.some(m => m.direction === 'in')).length}));
  const governments = [...new Set(all.map(t => t.government).filter(Boolean))].sort();
  return {year: y, years, governments, total: all.length, conversations: out};
}

module.exports = {INBOX, replyNotice, forInbox, inbound, seed, contacts, saveContact, send, reply, threads, thread, publish, redactions, redactSet, setStatus, assign, dismiss, publicFeed,
  tokenFrom, stripQuoted, composeEmail, messageIdFor, newToken};
