// Posts that are the same thing listed twice: a notice re-posted with a small update ("Reuse System Offline Due to
// Repair" seven minutes after "Reuse System Temporarily Out of Service"), a legal notice published again next week, one
// event on two calendars. The same rules as data/dupes.py, so the live API, the static pages and the data build merge the
// same posts; api/__tests__/dupes.test.js checks the two agree on data/dupes_cases.json.
//
// Two posts are compared only when they share a group (the same government's alert center, the same agency, the same day
// for events) and were posted within the feed's window:
//   title    shared title words, ignoring filler ("notice", "temporarily", "due to"): |A and B| / |A or B|
//   body     shared 3-word runs of the text over the shorter text's runs (so "the old text plus a few words" scores 1)
//   numbers  every number in the shorter post is in the longer one (an update adds to a post; it doesn't change it)
// Verdicts: 'same' (merged), 'maybe' (listed on /admin > Name matches for a person to decide) or null. A reviewer's call
// beats the score either way. Files starting with _ are not routes.

const FILLER = new Set(('a an the and or of for to in on at by as is are was be will been from with into until through thru due ' +
  'notice notices update updated updates alert alerts advisory reminder important please note attention ' +
  'temporarily temporary currently now new today city county residents customers').split(' '));
const BODY_SAME = 0.8, TITLE_SAME = 0.85, BODY_MAYBE = 0.5, TITLE_MAYBE = 0.6, MIN_BODY_WORDS = 8;

const words = s => String(s == null ? '' : s).toLowerCase().replace(/’/g, "'").replace(/'/g, '').match(/[a-z0-9]+/g) || [];
const stem = w => (w.length > 3 && w.endsWith('s') && !w.endsWith('ss') ? w.slice(0, -1) : w);
const titleWords = s => new Set(words(s).filter(w => !FILLER.has(w)).map(stem));
const inter = (a, b) => { let n = 0; for (const x of a) if (b.has(x)) n++; return n; };
function jaccard(a, b) {
  if (!a.size || !b.size) return 0;
  const i = inter(a, b);
  return i / (a.size + b.size - i);
}
function shingles(ws, n = 3) {
  const out = new Set();
  for (let i = 0; i + n <= ws.length; i++) out.add(ws.slice(i, i + n).join(' '));
  return out;
}
// Shared 3-word runs over the shorter text's runs; null when either text is too short to judge.
function containment(a, b) {
  const wa = words(a), wb = words(b);
  if (Math.min(wa.length, wb.length) < MIN_BODY_WORDS) return null;
  const sa = shingles(wa), sb = shingles(wb);
  return inter(sa, sb) / Math.min(sa.size, sb.size);
}
const nums = s => (String(s).match(/\d+/g) || []).map(x => x.replace(/^0+/, '') || '0');
// Every number in the shorter post (title + body) is also in the longer one.
function numbersFit(a, b) {
  const [short, long] = words(a).length <= words(b).length ? [nums(a), nums(b)] : [nums(b), nums(a)];
  const L = new Set(long);
  return short.every(x => L.has(x));
}

// a, b: {title, body?, place?, ref?}. strictNumbers: numbers that disagree mean two posts (legal notices).
function compare(a, b, strictNumbers = false) {
  const t = jaccard(titleWords(a.title), titleWords(b.title));
  const body = containment(a.body, b.body);
  const numbers = numbersFit(`${a.title || ''} ${a.body || ''}`, `${b.title || ''} ${b.body || ''}`);
  const out = {title: t, body, numbers, verdict: null};
  if (a.place && b.place && String(a.place).toLowerCase() !== String(b.place).toLowerCase()) return out; // one title in two towns
  if (a.ref && b.ref && a.ref !== b.ref) return out; // two job requisitions
  if (numbers && ((body != null && body >= BODY_SAME) || (t >= TITLE_SAME && (body == null || body >= BODY_MAYBE)))) out.verdict = 'same';
  else if (strictNumbers && !numbers) { /* different posts */ }
  else if ((body != null && (body >= BODY_SAME || (body >= BODY_MAYBE && t >= TITLE_MAYBE))) || (body == null && t >= TITLE_MAYBE)) out.verdict = 'maybe';
  return out;
}

function ts(v) {
  if (!v) return null;
  let s = String(v);
  if (!/[T ]/.test(s)) s += 'T00:00:00Z';
  else if (!/(Z|[+-]\d\d:?\d\d)$/.test(s)) s = s.replace(' ', 'T') + 'Z';
  const t = Date.parse(s);
  return Number.isFinite(t) ? t / 1000 : null;
}
const r2 = x => Math.floor(x * 100 + 0.5) / 100;
const pairKey = (a, b) => (a < b ? [a, b] : [b, a]);
const cmpStr = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

// Reviewer calls: {confirmed: [{a_key, b_key}], rejected: [...]} (the shape data/dupes/decisions.json and the database use).
function decisionSets(d = {}) {
  const set = xs => new Set((xs || []).map(x => pairKey(x.a_key, x.b_key).join('|')));
  return {same: set(d.confirmed), apart: set(d.rejected)};
}

// items: [{id, group, when, title, body?, place?, ref?, rank?}] (lower rank is kept first, then the newest).
// Returns {groups: [[id, ...] kept post first], maybe: [{a, b, title, body}], same_as: {id: kept id}}.
function find(items, {windowHours = 72, decisions = null, strictNumbers = false} = {}) {
  const dec = decisions && decisions.same instanceof Set ? decisions : decisionSets(decisions || {});
  const by = new Map();
  for (const it of items) { const g = String(it.group == null ? '' : it.group); if (!by.has(g)) by.set(g, []); by.get(g).push(it); }
  const parent = new Map(items.map(it => [it.id, it.id]));
  const root = x => { while (parent.get(x) !== x) { parent.set(x, parent.get(parent.get(x))); x = parent.get(x); } return x; };
  const maybe = [], win = windowHours * 3600;
  for (const g of [...by.keys()].sort(cmpStr)) {
    const rows = by.get(g).slice().sort((a, b) => ((ts(a.when) || 0) - (ts(b.when) || 0)) || cmpStr(a.id, b.id));
    rows.forEach((a, i) => {
      const ta = ts(a.when);
      for (const b of rows.slice(i + 1)) {
        const tb = ts(b.when);
        if (ta != null && tb != null && tb - ta > win) break;
        const k = pairKey(a.id, b.id), kk = k.join('|');
        if (dec.apart.has(kk)) continue;
        const c = compare(a, b, strictNumbers);
        if (dec.same.has(kk) || c.verdict === 'same') parent.set(root(a.id), root(b.id));
        else if (c.verdict === 'maybe') maybe.push({a: k[0], b: k[1], title: r2(c.title), body: c.body == null ? null : r2(c.body)});
      }
    });
  }
  const clusters = new Map();
  for (const it of items) { const r = root(it.id); if (!clusters.has(r)) clusters.set(r, []); clusters.get(r).push(it); }
  const groups = [], same_as = {};
  for (const members of clusters.values()) {
    if (members.length < 2) continue;
    members.sort((a, b) => ((a.rank || 0) - (b.rank || 0)) || ((ts(b.when) || 0) - (ts(a.when) || 0)) || cmpStr(b.id, a.id));
    groups.push(members.map(m => m.id));
    for (const m of members.slice(1)) same_as[m.id] = members[0].id;
  }
  const kept = id => same_as[id] || id;
  groups.sort((x, y) => { for (let i = 0; i < Math.min(x.length, y.length); i++) { const c = cmpStr(x[i], y[i]); if (c) return c; } return x.length - y.length; });
  return {groups, maybe: maybe.filter(m => kept(m.a) !== kept(m.b)), same_as};
}

// Emergency notices: one government's alert center or news feed, posted within 3 days. Weather alerts, FL511 and shelter
// notices keep their own ids for one event, so they aren't compared.
const NOTICE_SKIP = new Set(['nws', 'fl511', 'shelters']);
const noticeItem = n => ({id: n.notice_id, group: `${n.gov_id || n.source}`, when: n.issued || n.updated || n.first_seen, title: n.title, body: n.summary});
function noticeGroups(notices, decisions) {
  return find(notices.filter(n => !NOTICE_SKIP.has(n.source_type)).map(noticeItem), {windowHours: 72, decisions});
}

// Live notices -> one card per post: the newest version, with `first_posted` (the earliest version's time) and `versions`
// (every version, newest first: notice_id, title, issued, url) when it was posted more than once.
function mergeNotices(notices, decisions) {
  const r = noticeGroups(notices, decisions);
  if (!r.groups.length) return notices;
  const by = new Map(notices.map(n => [n.notice_id, n]));
  const extra = new Map();
  for (const g of r.groups) {
    const vs = g.map(id => by.get(id)).sort((a, b) => String(b.issued || '').localeCompare(String(a.issued || '')));
    extra.set(g[0], {first_posted: vs.map(v => v.issued).filter(Boolean).sort()[0] || null,
      versions: vs.map(v => ({notice_id: v.notice_id, title: v.title, issued: v.issued, url: v.url}))});
  }
  return notices.filter(n => !r.same_as[n.notice_id]).map(n => (extra.has(n.notice_id) ? {...n, ...extra.get(n.notice_id)} : n));
}

// Reviewer calls on repeated posts, from the database (name_match_reviews, kind 'repeat') when it is connected, else the
// copy the daily refresh exports (data/dupes/decisions.json). Cached for 5 minutes.
let cache = {at: 0, d: null};
async function decisions({now = Date.now()} = {}) {
  if (cache.d && now - cache.at < 5 * 60e3) return cache.d;
  let d = null;
  try {
    const db = require('./_db');
    if (db.hasDb()) {
      const rows = await db.q(`select a_key, b_key, status from name_match_reviews where kind = 'repeat'`);
      d = {confirmed: rows.filter(r => r.status === 'confirmed'), rejected: rows.filter(r => r.status === 'rejected')};
    }
  } catch (e) { d = null; }
  if (!d) { try { d = require('../data/dupes/decisions.json'); } catch (e) { d = {}; } }
  cache = {at: now, d};
  return d;
}

module.exports = {decisions, words, titleWords, jaccard, containment, numbersFit, compare, find, decisionSets, pairKey, noticeGroups, mergeNotices, noticeItem, NOTICE_SKIP,
  BODY_SAME, TITLE_SAME, BODY_MAYBE, TITLE_MAYBE};
