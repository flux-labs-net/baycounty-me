// Public mail viewer (/correspondence, GET /api/v1/mail and /api/v1/mail/{id}): every email between BayCounty.me and
// officials or governments, read-only, start to finish. Four folders:
//   letters   letters to officials and their replies (corr.threads)
//   requests  public records requests and the answers (corr.threads linked from corr.records_requests)
//   sent_in   records a government emailed to its intake address (gov.intake_emails, with what happened to each file)
//   other     other mail to hello@baycounty.me from a government address that isn't part of a conversation yet
// Never included: sign-in codes and links, alerts and digests to residents, mail from outside senders to an intake
// address (dropped unread), and anything not from or to a government. Residents' details are hidden (api/_redact.js);
// officials and staff stay named. Conversations are public by default (migration 0094); one the admin takes down is
// listed with the reason and no messages.
const {redact, shownAddress} = require('./_redact');
const {stripQuoted} = require('./_correspondence');

const err = (msg, status = 400) => Object.assign(new Error(msg), {status, expose: true});
const FREE_MAIL = new Set(['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'aol.com', 'icloud.com', 'me.com', 'live.com', 'msn.com', 'comcast.net',
  'att.net', 'bellsouth.net', 'protonmail.com', 'proton.me', 'mail.com', 'ymail.com', 'gmx.com', 'knology.net', 'mchsi.com']);
const FOLDERS = {letters: 'Letters to officials', requests: 'Records requests', sent_in: 'Records sent in', other: 'Other mail from governments'};
const US = 'BayCounty.me';
const domainOf = a => String(a || '').toLowerCase().split('@')[1] || '';
const addrOf = s => { const m = String(s || '').match(/<([^>]+)>/); return (m ? m[1] : String(s || '')).trim().toLowerCase(); };
const nameOf = s => { const m = String(s || '').match(/^\s*"?([^"<]+?)"?\s*</); return m ? m[1].trim() : null; };

// Government domains (addresses on them stay visible) and which government each belongs to.
async function context(q) {
  const safe = p => p.catch(() => []);
  const src = await safe(q(`select lower(s.gov_domain) d, w.name from ingest.sources s left join gov.workspaces w on w.id = s.finance_workspace_id where s.gov_domain is not null`));
  const contacts = await safe(q(`select distinct lower(split_part(email, '@', 2)) d, government name from corr.contacts where email like '%@%'`));
  const rr = await safe(q(`select distinct lower(split_part(recipient_email, '@', 2)) d, government name from corr.records_requests where recipient_email like '%@%'`));
  const govOf = new Map();
  for (const r of [...src, ...contacts, ...rr]) if (r.d && !FREE_MAIL.has(r.d) && !govOf.has(r.d)) govOf.set(r.d, r.name || null);
  const govDomains = new Set([...govOf.keys(), 'baycounty.me']);
  const phrases = await safe(q('select thread_key, phrase from corr.redactions'));
  return {govDomains, govOf, phrases};
}
const phrasesFor = (ctx, keys) => ctx.phrases.filter(p => !p.thread_key || keys.includes(p.thread_key)).map(p => p.phrase);
const isGov = (ctx, addr) => Boolean(shownAddress(addr, ctx.govDomains)) && domainOf(addr) !== 'baycounty.me';
const govFor = (ctx, addr) => { const d = domainOf(addr); for (const [k, v] of ctx.govOf) if (d === k || d.endsWith('.' + k)) return v; return null; };

/* ---------- the list ---------- */
async function allThreads(q, ctx) {
  const safe = p => p.catch(() => []);
  const corr = await safe(q(`select t.id, t.subject, t.official_name, t.official_seat, t.government, t.status, t.created_at, t.last_at, t.published, t.hidden_reason,
      rr.status rr_status,
      (select count(*)::int from corr.messages m where m.thread_id = t.id) n,
      (select count(*)::int from corr.messages m where m.thread_id = t.id and m.direction = 'in') replies,
      (select m.body_text from corr.messages m where m.thread_id = t.id order by m.at desc limit 1) last_text,
      (select m.direction from corr.messages m where m.thread_id = t.id order by m.at desc limit 1) last_dir,
      (select coalesce(sum(jsonb_array_length(m.attachments)), 0)::int from corr.messages m where m.thread_id = t.id) files
    from corr.threads t left join corr.records_requests rr on rr.thread_id = t.id
    where t.published or t.hidden_reason is not null`));
  const intake = await safe(q(`select e.id, e.email_id, e.sender, e.subject, e.body_text, e.decision, e.notice_sent, e.logged_at, e.received_at, e.finished_at,
      jsonb_array_length(e.attachments)::int files, w.name government
    from gov.intake_emails e left join gov.workspaces w on w.id = e.workspace_id where e.decision in ('accepted', 'refused')`));
  const loose = (await safe(q(`select id, from_addr, subject, body_text, at, jsonb_array_length(attachments)::int files from corr.messages
      where thread_id is null and direction = 'in' order by at desc limit 500`))).filter(m => isGov(ctx, addrOf(m.from_addr)));

  const snip = (t, keys) => redact(stripQuoted(t || '').text, {govDomains: ctx.govDomains, phrases: phrasesFor(ctx, keys)}).replace(/\s+/g, ' ').trim().slice(0, 160);
  return [
    ...corr.map(t => {
      const k = 'c' + t.id, hidden = !t.published;
      return {id: k, folder: t.rr_status ? 'requests' : 'letters', subject: t.subject, government: t.government,
        with: [t.official_name, t.official_seat].filter(Boolean).join(', ') || t.government, started_at: t.created_at, last_at: t.last_at,
        messages: hidden ? 0 : t.n, replies: t.replies, files: hidden ? 0 : t.files, status: t.rr_status || t.status, hidden_reason: hidden ? t.hidden_reason : null,
        last_from: t.last_dir === 'in' ? (t.official_name || 'Reply') : US, snippet: hidden ? '' : snip(t.last_text, [k])};
    }),
    ...intake.map(e => {
      const k = 'e' + e.id;
      return {id: k, folder: 'sent_in', subject: e.decision === 'accepted' ? (e.subject || '(no subject)') : 'Not accepted: sender isn’t on the allowed list',
        government: e.government, with: e.government ? `Staff, ${e.government}` : e.sender, started_at: e.received_at || e.logged_at, last_at: e.finished_at || e.logged_at,
        messages: 1 + (e.notice_sent ? 1 : 0), replies: 0, files: e.decision === 'accepted' ? e.files : 0, status: e.decision, hidden_reason: null,
        last_from: e.notice_sent ? US : (e.government ? `Staff, ${e.government}` : 'Staff'), snippet: e.decision === 'accepted' ? snip(e.body_text, [k]) : 'Not opened.'};
    }),
    ...loose.map(m => {
      const k = 'm' + m.id, g = govFor(ctx, addrOf(m.from_addr));
      return {id: k, folder: 'other', subject: m.subject || '(no subject)', government: g, with: nameOf(m.from_addr) || addrOf(m.from_addr), started_at: m.at, last_at: m.at,
        messages: 1, replies: 0, files: m.files, status: null, hidden_reason: null, last_from: nameOf(m.from_addr) || addrOf(m.from_addr), snippet: snip(m.body_text, [k])};
    }),
  ].sort((a, b) => new Date(b.last_at) - new Date(a.last_at));
}

async function list(q, {folder = '', government = '', q: needle = '', page = 1} = {}) {
  const ctx = await context(q);
  const all = await allThreads(q, ctx);
  const counts = Object.fromEntries(Object.keys(FOLDERS).map(f => [f, all.filter(t => t.folder === f).length]));
  const governments = [...new Set(all.map(t => t.government).filter(Boolean))].sort();
  const n = String(needle || '').toLowerCase().trim();
  let rows = all.filter(t => (!folder || t.folder === folder) && (!government || t.government === government));
  if (n) rows = rows.filter(t => [t.subject, t.with, t.government, t.snippet].join(' ').toLowerCase().includes(n));
  const size = 50, p = Math.max(1, parseInt(page, 10) || 1);
  return {folders: Object.entries(FOLDERS).map(([id, label]) => ({id, label, count: counts[id]})), total: all.length, governments,
    matched: rows.length, page: p, pages: Math.max(1, Math.ceil(rows.length / size)), threads: rows.slice((p - 1) * size, p * size),
    note: 'Every email between BayCounty.me and officials or governments, read-only. Residents’ email addresses, phone numbers and street addresses are hidden; officials and government staff are named. Sign-in codes and links are never included.'};
}

/* ---------- one conversation ---------- */
function attachmentsOf(list) {
  return (list || []).map(a => ({name: a.filename || a.name || 'file', size: a.size ?? null, type: a.content_type || null, sha256: a.sha256 || null,
    note: a.skipped || (a.duplicate ? 'Already received earlier (same fingerprint)' : null)}));
}

const ACTION_TEXT = {
  file_received: 'File received', file_preview: 'File read, waiting for staff to confirm it', file_committed: 'Staff confirmed it’s the right file; imported',
  file_received_status: 'Staff confirmed it’s the right file', file_held: 'Held for review', file_published: 'Published on BayCounty.me', file_unpublished: 'Taken off the site',
  file_withdrawn: 'Withdrawn by the government', file_replaced: 'Replaced by a newer file', review_publish: 'Published after review', review_hold: 'Kept off the site after review',
};
function eventText(a) {
  if (a.action === 'file_checked') {
    const c = (a.detail && a.detail.counts) || {};
    const st = a.detail && a.detail.status;
    return `Checked against our own records: ${c.match || 0} matched, ${(c.mismatch || 0) + (c.missing || 0)} didn’t match or missing, ${c.unconfirmed || 0} couldn’t be confirmed` +
      (st === 'verified' ? '. Everything matched.' : '. Waiting for review.');
  }
  if (a.action === 'file_received' && a.detail && a.detail.status) return ACTION_TEXT.file_received_status;
  return ACTION_TEXT[a.action] || null;
}

async function thread(q, id) {
  const m = String(id || '').match(/^([cem])(\d{1,12})$/);
  if (!m) throw err('Unknown conversation.', 404);
  const ctx = await context(q);
  const key = m[1] + m[2], n = Number(m[2]);
  const R = (t, extra = []) => redact(t, {govDomains: ctx.govDomains, phrases: phrasesFor(ctx, [key, ...extra])});
  let out;

  if (m[1] === 'c') {
    const [t] = await q(`select t.*, rr.status rr_status, rr.subject rr_subject from corr.threads t left join corr.records_requests rr on rr.thread_id = t.id where t.id = $1`, [n]);
    if (!t || (!t.published && !t.hidden_reason)) throw err('Unknown conversation.', 404);
    const official = {name: t.official_name || null, role: [t.official_seat, t.government].filter(Boolean).join(', ') || null};
    const head = {id: key, folder: t.rr_status ? 'requests' : 'letters', subject: t.subject, government: t.government, status: t.rr_status || t.status,
      participants: [{name: US, role: 'Independent public-records site'}, official], started_at: t.created_at, last_at: t.last_at};
    if (!t.published) return {...head, hidden_reason: t.hidden_reason, items: []};
    const msgs = await q(`select id, direction, from_addr, to_addr, cc, subject, body_text, message_id, in_reply_to, status, attachments, at from corr.messages where thread_id = $1 order by at, id`, [n]);
    const officialAddr = String(t.email || '').toLowerCase();
    out = {...head, items: msgs.map(x => {
      const mk = 'm' + x.id;
      const from = x.direction === 'out' ? {name: US, role: null}
        : addrOf(x.from_addr) === officialAddr ? official
        : {name: nameOf(x.from_addr) && isGov(ctx, addrOf(x.from_addr)) ? nameOf(x.from_addr) : null, address: shownAddress(addrOf(x.from_addr), ctx.govDomains),
          role: govFor(ctx, addrOf(x.from_addr)) || (isGov(ctx, addrOf(x.from_addr)) ? null : 'Someone else (address hidden)')};
      const shown = x.direction === 'in' ? stripQuoted(x.body_text || '') : {text: x.body_text || '', quoted: false};
      return {type: 'message', id: mk, direction: x.direction, from, to: x.direction === 'out' ? [official] : [{name: US}], at: x.at, subject: x.subject,
        text: R(shown.text, [mk]), quoted: shown.quoted ? R(String(x.body_text || '').slice(shown.text.length).trim(), [mk]) : null,
        attachments: attachmentsOf(x.attachments), delivery: x.direction === 'out' ? x.status : null, message_id: x.message_id || null, in_reply_to: x.in_reply_to || null};
    })};
  } else if (m[1] === 'e') {
    const [e] = await q(`select e.*, w.name government from gov.intake_emails e left join gov.workspaces w on w.id = e.workspace_id where e.id = $1 and e.decision in ('accepted', 'refused')`, [n]);
    if (!e) throw err('Unknown conversation.', 404);
    const staff = {name: e.government ? `Staff, ${e.government}` : 'Government staff', address: shownAddress(e.sender, ctx.govDomains), role: e.government};
    const intake = {name: `${US} records intake`, address: e.intake_address || (e.recipients || [])[0] || null};
    const ok = e.decision === 'accepted';
    const files = attachmentsOf(ok ? e.attachments : []);
    const items = [{type: 'message', id: 'e' + e.id, direction: 'in', from: staff, to: [intake], at: e.received_at || e.logged_at, sent_at: e.sent_at,
      subject: ok ? e.subject || '(no subject)' : null, text: ok ? R(e.body_text || '') : null,
      not_opened: ok ? null : 'Not opened: this address isn’t on the government’s list of who may send records, so nothing in the email was read or kept.',
      attachments: files, message_id: e.message_id || null, logged_at: e.logged_at}];
    if (e.notice_sent && e.notice_text) items.push({type: 'message', id: 'e' + e.id + 'r', direction: 'out', from: {name: US}, to: [staff], at: e.finished_at,
      subject: `Not accepted: records for ${e.government || 'your government'}`, text: R(e.notice_text), attachments: []});
    const shas = files.map(f => f.sha256).filter(Boolean);
    const trail = shas.length ? await q(`select id, at, action, detail, hash from gov.audit_log where file_sha256 = any($1::text[]) and action not in ('email_logged', 'email_finished') order by id`, [shas]).catch(() => []) : [];
    const seen = new Set();
    for (const a of trail) {
      const text = eventText(a);
      const k = text + '|' + (a.detail && a.detail.name || '');
      if (!text || seen.has(k)) continue;
      seen.add(k);
      items.push({type: 'event', at: a.at, text, file: (a.detail && a.detail.name) || null, hash: a.hash});
    }
    out = {id: key, folder: 'sent_in', subject: items[0].subject || 'Not accepted: sender isn’t on the allowed list', government: e.government, status: e.decision,
      participants: [staff, intake], started_at: items[0].at, last_at: e.finished_at || e.logged_at, items: items.sort((a, b) => new Date(a.at) - new Date(b.at))};
  } else {
    const [x] = await q(`select id, from_addr, to_addr, subject, body_text, message_id, attachments, at from corr.messages where id = $1 and thread_id is null and direction = 'in'`, [n]);
    if (!x || !isGov(ctx, addrOf(x.from_addr))) throw err('Unknown conversation.', 404);
    const g = govFor(ctx, addrOf(x.from_addr));
    const from = {name: nameOf(x.from_addr), address: addrOf(x.from_addr), role: g};
    const shown = stripQuoted(x.body_text || '');
    out = {id: key, folder: 'other', subject: x.subject || '(no subject)', government: g, status: null, participants: [from, {name: US}], started_at: x.at, last_at: x.at,
      items: [{type: 'message', id: key, direction: 'in', from, to: [{name: US}], at: x.at, subject: x.subject, text: R(shown.text), quoted: shown.quoted ? R(String(x.body_text || '').slice(shown.text.length).trim()) : null,
        attachments: attachmentsOf(x.attachments), message_id: x.message_id || null}]};
  }
  // Neighbours in the full list, for next and previous.
  const all = await allThreads(q, ctx);
  const i = all.findIndex(t => t.id === key);
  return {...out, newer: i > 0 ? all[i - 1].id : null, older: i >= 0 && i < all.length - 1 ? all[i + 1].id : null};
}

module.exports = {list, thread, FOLDERS, eventText};
