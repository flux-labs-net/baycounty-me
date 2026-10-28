// "Name matches" on /admin: business names that look alike ("Emeral Coast Striping" / "Emerald Coast Striping", "GAC
// Contractor" / "GAC Contractors") and may be one company. The pairs come from the data build
// (data/entities/build_entities.py writes them to vendor_review.json look_alike_names); an admin's call is stored in
// name_match_reviews (migration 0059): confirmed = one company, rejected = keep apart. The daily refresh exports the calls
// (data/entities/export_name_decisions.py) and the next build joins or separates the names everywhere: vendor pages,
// campaign gifts, the money map and the apps. Spacing, punctuation and legal suffixes never need review; those names
// already share one key. Files starting with _ are not routes.
//
// kind 'repeat' (migration 0079): posts that may be the same thing listed twice (an alert re-posted with a changed date, a
// notice, event or job that looks alike but not enough to merge on its own; data/dupes.py and api/_dupes.js). Candidates come
// from the last build (data/dupes/review.json) plus the live alerts right now; confirmed = one post, rejected = keep apart.
const fs = require('fs');
const path = require('path');
const db = require('./_db');
const bulk = require('./_bulk');

const bad = (msg, status = 400) => Object.assign(new Error(msg), {status});
const STATUS = ['confirmed', 'rejected', 'unreviewed'];
const KEY = /^[a-z0-9]{3,120}$/;
const POST_KEY = /^[A-Za-z0-9][\w:.?=&\/%+-]{2,200}$/;  // a post id: alert:lh:145, pn:9c26a1d21bf3, pcb-chamber:27622, job:…
const KINDS = ['name', 'repeat'];
const REASONS = {spelling: 'One or two letters apart', plural: 'Plural', shortened: 'One name is the start of the other'};
const FEEDS = {alerts: 'Alert', notices: 'Public notice', events: 'Event', jobs: 'Job opening'};
const pct = x => (x == null ? null : Math.round(x * 100) + '%');

// The look-alike pairs from the last build (bundled with the function; see vercel.json includeFiles).
function candidates(read = () => fs.readFileSync(path.join(__dirname, '..', 'data', 'entities', 'vendor_review.json'), 'utf8')) {
  try { return JSON.parse(read()).look_alike_names || []; } catch (e) { return []; }
}

// Possible repeated posts: the last build's (data/dupes/review.json) plus the alerts live right now (emergency_live, last
// week), so a re-post seen minutes ago can be decided before the next build. Each pair as {a, b, reason: <feed>, why}.
function repeatCandidates(read = () => fs.readFileSync(path.join(__dirname, '..', 'data', 'dupes', 'review.json'), 'utf8')) {
  try { return JSON.parse(read()).pairs || []; } catch (e) { return []; }
}
async function liveRepeats() {
  const D = require('./_dupes');
  let rows = [];
  try {
    rows = await db.q(`select notice_id, source, source_type, gov_id, title, summary, issued, updated, first_seen::text as first_seen, url from emergency_live
      where last_seen > now() - interval '7 days'`);
  } catch (e) { return []; }
  const by = new Map(rows.map(n => [n.notice_id, n]));
  const issued = v => (v instanceof Date ? v.toISOString() : v);
  const items = rows.filter(n => !D.NOTICE_SKIP.has(n.source_type)).map(n => D.noticeItem({...n, issued: issued(n.issued), updated: issued(n.updated)}));
  const side = id => { const n = by.get(id); return {key: id, names: [n.title], source: n.source, posted: issued(n.issued), url: n.url, text: (n.summary || '').slice(0, 280) || null}; };
  return D.find(items, {windowHours: 72, decisions: {}}).maybe.map(m => ({a: side(m.a), b: side(m.b), title: m.title, body: m.body, feed: 'alerts'}));
}
function repeatPairs(pairs) {
  const seen = new Set(), out = [];
  for (const p of pairs) {
    const k = pairKey(p.a.key, p.b.key).join('|');
    if (seen.has(k)) continue;
    seen.add(k);
    const why = p.body != null ? `${pct(p.body)} same text, ${pct(p.title)} title` : `${pct(p.title)} same title`;
    out.push({a: p.a, b: p.b, reason: p.feed, reason_label: `${FEEDS[p.feed] || 'Post'}: ${why}`});
  }
  return out;
}

// Pure: the pair key (keys in sorted order) so a call holds whichever way round the pair was listed.
const pairKey = (a, b) => (a < b ? [a, b] : [b, a]);

// Pure: candidate pairs + stored calls -> rows for the table, filtered.
function merge(pairs, calls, {status = 'unreviewed', reason = '', q = ''} = {}) {
  const byPair = new Map(calls.map(c => [c.a_key + '|' + c.b_key, c]));
  const seen = new Set(), rows = [];
  for (const p of pairs) {
    const [a, b] = pairKey(p.a.key, p.b.key);
    const k = a + '|' + b;
    seen.add(k);
    const c = byPair.get(k);
    rows.push({a_key: a, b_key: b, a: p.a.key === a ? p.a : p.b, b: p.a.key === a ? p.b : p.a, reason: p.reason, reason_label: p.reason_label || REASONS[p.reason] || p.reason,
      review_status: c ? c.status : 'unreviewed', reviewed_by: c ? c.reviewed_by : null, reviewed_at: c ? c.reviewed_at : null});
  }
  // calls already applied by a build drop out of the candidate list; keep them visible under Confirmed / Rejected
  for (const c of calls) {
    if (seen.has(c.a_key + '|' + c.b_key)) continue;
    rows.push({a_key: c.a_key, b_key: c.b_key, a: {key: c.a_key, names: [c.a_name || c.a_key]}, b: {key: c.b_key, names: [c.b_name || c.b_key]}, reason: null,
      reason_label: 'Applied in the last build', review_status: c.status, reviewed_by: c.reviewed_by, reviewed_at: c.reviewed_at});
  }
  const ql = String(q || '').toLowerCase().trim();
  return rows.filter(r => (!status || r.review_status === status) && (!reason || r.reason === reason)
    && (!ql || [...(r.a.names || []), ...(r.b.names || [])].some(n => String(n).toLowerCase().includes(ql))));
}

async function list({status = 'unreviewed', reason = '', q = '', kind = 'name'} = {}) {
  if (status && !STATUS.includes(status)) status = 'unreviewed';
  if (!KINDS.includes(kind)) kind = 'name';
  let calls;
  try { calls = await db.q(`select a_key, b_key, a_name, b_name, status, reviewed_by, reviewed_at from name_match_reviews where kind = $1`, [kind]); }
  catch (e) {
    if (kind !== 'name' || !/column .*kind/i.test(e.message)) throw e;
    calls = await db.q(`select a_key, b_key, a_name, b_name, status, reviewed_by, reviewed_at from name_match_reviews`);  // before migration 0079
  }
  const pairs = kind === 'repeat' ? repeatPairs([...repeatCandidates(), ...(await liveRepeats())]) : candidates();
  const all = merge(pairs, calls, {status: ''});
  const count = st => all.filter(r => r.review_status === st).length;
  const rows = merge(pairs, calls, {status, reason, q});
  return {kind, counts: {pairs: pairs.length, unreviewed: count('unreviewed'), confirmed: count('confirmed'), rejected: count('rejected')},
    reasons: kind === 'repeat' ? FEEDS : REASONS, rows: rows.slice(0, 500), total: rows.length};
}

// Pure: the pairs named in a review body (one, or `items` for a bulk change).
function cleanPairs(body, kind = 'name') {
  const re = kind === 'repeat' ? POST_KEY : KEY;
  return bulk.items(body, x => {
    const a = String(x.a_key || ''), b = String(x.b_key || '');
    if (!re.test(a) || !re.test(b) || a === b) throw bad('Unknown name pair.');
    const [ka, kb] = pairKey(a, b);
    const swap = ka !== a;
    const nm = v => (v == null ? null : String(v).replace(/\s+/g, ' ').trim().slice(0, 200) || null);
    return {a_key: ka, b_key: kb, a_name: nm(swap ? x.b_name : x.a_name), b_name: nm(swap ? x.a_name : x.b_name)};
  });
}

async function review(body, admin) {
  const status = String(body.status || '');
  if (!STATUS.includes(status)) throw bad('Unknown review status.');
  const kind = body.kind == null || body.kind === '' ? 'name' : String(body.kind);
  if (!KINDS.includes(kind)) throw bad('Unknown review kind.');
  const pairs = cleanPairs(body, kind);
  if (status === 'unreviewed') {
    const rows = await db.q(`delete from name_match_reviews r using jsonb_to_recordset($1::jsonb) as x(a_key text, b_key text)
      where r.a_key = x.a_key and r.b_key = x.b_key returning r.a_key, r.b_key`, [JSON.stringify(pairs)]);
    return {updated: rows.length || pairs.length, by: admin, rows: rows.length ? rows : pairs.map(p => ({a_key: p.a_key, b_key: p.b_key}))};
  }
  // Business names keep the insert they always had, so it works before migration 0079 too.
  const rows = await db.q(kind === 'name' ? `insert into name_match_reviews (a_key, b_key, a_name, b_name, status, reviewed_by, reviewed_at)
    select x.a_key, x.b_key, x.a_name, x.b_name, $2, $3, now() from jsonb_to_recordset($1::jsonb) as x(a_key text, b_key text, a_name text, b_name text)
    on conflict (a_key, b_key) do update set status = excluded.status, reviewed_by = excluded.reviewed_by, reviewed_at = now(),
      a_name = coalesce(excluded.a_name, name_match_reviews.a_name), b_name = coalesce(excluded.b_name, name_match_reviews.b_name)
    returning a_key, b_key, status` : `insert into name_match_reviews (a_key, b_key, a_name, b_name, status, reviewed_by, reviewed_at, kind)
    select x.a_key, x.b_key, x.a_name, x.b_name, $2, $3, now(), 'repeat' from jsonb_to_recordset($1::jsonb) as x(a_key text, b_key text, a_name text, b_name text)
    on conflict (a_key, b_key) do update set status = excluded.status, reviewed_by = excluded.reviewed_by, reviewed_at = now(), kind = 'repeat',
      a_name = coalesce(excluded.a_name, name_match_reviews.a_name), b_name = coalesce(excluded.b_name, name_match_reviews.b_name)
    returning a_key, b_key, status`, [JSON.stringify(pairs), status, admin || null]);
  return {updated: rows.length, by: admin, rows};
}

module.exports = {candidates, repeatCandidates, repeatPairs, liveRepeats, merge, pairKey, cleanPairs, list, review, REASONS, FEEDS};
