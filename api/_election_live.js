// Live election night results: GET /api/v1/election-live and /api/v1/election-live/history (/elections/live).
// Source: the Supervisor of Elections' results site (enr.electionsfl.org/BAY/<id>/Summary/, run by VR Systems for the
// SOE). It has no JSON feed: the Summary page is server-drawn HTML, and /BAY/<id>/stampedtime.js returns a number that
// changes whenever new results post. We read the stamp first and the Summary page only when the stamp moved.
//
// Storage (migration 0104): election_live holds the latest count; election_live_snapshots adds one row per SOE update
// (totals per choice) so the page can show how races moved. The SOE site is read at most once per MIN_GAP across all
// servers: a request claims the read in the database, everyone else gets the stored count. Without a database (local
// runs) it reads live with a per-server cache.
const ENR = 'https://enr.electionsfl.org/BAY';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36 BayCounty.me results reader';
const MIN_GAP = 45 * 1000;

// Elections we read live. Add a line before each election night (the SOE id is in the results site's address).
// `until` is the last day we keep reading (canvass and certification run a few days past Election Day).
const ELECTIONS = [
  {id: 4078, name: 'General Election', date: '2026-11-03', until: '2026-11-20'},
];

const current = () => ELECTIONS.slice().sort((a, b) => (a.date < b.date ? 1 : -1))[0];
const live = (e, now = new Date()) => {
  const d = new Date(now.getTime() - 6 * 3600 * 1000).toISOString().slice(0, 10); // Central-ish date
  return d >= addDays(e.date, -1) && d <= e.until;
};
function addDays(s, n) { const t = new Date(s + 'T12:00:00Z'); t.setUTCDate(t.getUTCDate() + n); return t.toISOString().slice(0, 10); }

// --- reading the Summary page ---------------------------------------------------------------------------------------
const ENT = {amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', '#37': '%', '#39': "'"};
const unesc = s => String(s).replace(/&(#?\w+);/g, (m, k) => ENT[k] ?? (k[0] === '#' ? String.fromCharCode(k[1] === 'x' ? parseInt(k.slice(2), 16) : +k.slice(1)) : m));
const txt = s => unesc(String(s || '').replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim();
function num(s) {
  const t = txt(s).replace(/[,%]/g, '');
  if (t === '' || t === '-') return null; // a dash: 1 to 29 votes in a vote-type column, withheld by law (s. 98.0981(3)(a))
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}
const COL = {'Election Day': 'election_day', 'Early Votes': 'early_voting', 'Early Voting': 'early_voting', 'Vote By Mail': 'vote_by_mail', 'Provisional': 'provisional', 'Total Votes': 'votes', 'Percentage': 'pct'};

function parseSummary(html) {
  let t = String(html).replace(/src="data:[^"]*"/g, '').replace(/<(script|style|svg)[^>]*>[\s\S]*?<\/\1>/g, '');
  const cut = t.indexOf('showFavorites');
  const head = txt(cut > 0 ? t.slice(0, cut) : t.slice(0, 20000));
  const stat = label => { const m = head.match(new RegExp(label + ':\\s*([\\d,./%]+(?:\\s*/\\s*[\\d,]+)?)')); return m ? m[1] : null; };
  const pr = (stat('Precincts Reporting') || '').match(/(\d+)\s*\/\s*(\d+)/);
  const rep = label => { const m = head.match(new RegExp(label + ':\\s*(Not Reported|Partially Reported|Completely Reported|Reported|In Progress)', 'i')); return m ? m[1] : null; };
  const upd = head.match(/last updated at:\s*([\d/]+ [\d:]+ [ap]m)/i);
  const title = head.match(/Consider changing your browser\.\s*Learn More\s*(.*?)\s*Election Date:/);
  const info = {
    title: title ? title[1] : null,
    registered_voters: num(stat('Registered Voters') || ''), ballots_cast: num(stat('Ballots Cast') || stat('Ballots Counted') || ''),
    turnout_pct: num(stat('Voter Turnout') || ''), precincts_reporting: pr ? +pr[1] : null, precincts_total: pr ? +pr[2] : null,
    reported: {election_day: rep('Election Day'), early_voting: rep('Early Votes') || rep('Early Voting'), vote_by_mail: rep('Vote By Mail')},
    soe_updated: upd ? upd[1] : null,
  };
  const contests = [];
  const parts = t.split(/<div id="(\d+)" class="Race row">/);
  for (let i = 1; i < parts.length; i += 2) {
    const cid = +parts[i], b = parts[i + 1];
    const nm = b.match(/<label>([^<]+)<\/label>/);
    if (!nm) continue;
    const stats = {};
    for (const m of b.matchAll(/RaceStatsLabel[^>]*>((?:(?!<div)[\s\S])*?)<\/div>\s*<div class="RaceStatsValue[^>]*>([\s\S]*?)<\/div>/g)) {
      const k = txt(m[1]).replace(/:$/, '').toLowerCase().replace(/\s+/g, '_');
      if (k) stats[k] = /\d/.test(txt(m[2])) && !/\//.test(txt(m[2])) ? num(m[2]) : txt(m[2]);
    }
    const cols = [...b.matchAll(/<th class="DetailResultsHeader[^"]*">([\s\S]*?)<\/th>/g)].map(m => txt(m[1]));
    const tbody = b.match(/<table class="DetailResults"[\s\S]*?<tbody>([\s\S]*?)<\/tbody>/);
    const choices = [];
    const split = label => { const pm = label.match(/^(.*?)\s*\(([A-Z]{2,4})\)$/); return {choice: pm ? pm[1] : label, party: pm ? pm[2] : null}; };
    for (const row of tbody ? tbody[1].matchAll(/<tr>([\s\S]*?)<\/tr>/g) : []) {
      const cm = row[1].match(/<td class="ChoiceColumn">([\s\S]*?)<div/);
      if (!cm) continue;
      const cells = [...row[1].matchAll(/<td class="DetailResultsColumn[^"]*">([\s\S]*?)<\/td>/g)].map(m => num(m[1]));
      const label = txt(cm[1]);
      if (/^(OVER|UNDER) VOTES$/i.test(label)) continue;
      const ch = split(label);
      cols.forEach((c, j) => { ch[COL[c] || c.toLowerCase().replace(/\s+/g, '_')] = cells[j] ?? null; });
      choices.push(ch);
    }
    if (!choices.length) { // the simple view only: choice, bar, percent, votes
      for (const seg of b.split('<div class="row ResultsRow">').slice(1)) {
        const row = seg.split('<div class="row">')[0];
        const cm = row.match(/<div class="ChoiceColumn[^"]*">([\s\S]*?)<\/div>/);
        const vals = [...row.matchAll(/<div class="ResultsColumn[^"]*"[^>]*>([\s\S]*?)<\/div>/g)].map(m => num(m[1]));
        if (!cm || !vals.length) continue;
        const label = txt(cm[1]);
        if (/^(OVER|UNDER) VOTES$/i.test(label)) continue;
        choices.push({...split(label), votes: vals[vals.length - 1], pct: vals.length > 1 ? vals[0] : null});
      }
    }
    contests.push({contest_id: cid, contest: txt(nm[1]), over_votes: stats.overvotes ?? null, under_votes: stats.undervotes ?? null, stats, choices});
  }
  return {info, contests};
}

// --- fetching -------------------------------------------------------------------------------------------------------
async function get(url, ms = 15000) {
  const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), ms);
  try {
    const r = await fetch(url, {headers: {'User-Agent': UA, Accept: 'text/html,*/*'}, signal: ctl.signal});
    if (!r.ok) throw new Error(`SOE site answered HTTP ${r.status}`);
    return await r.text();
  } finally { clearTimeout(t); }
}
const stampOf = async id => (await get(`${ENR}/${id}/stampedtime.js?random=${Date.now()}`, 8000)).trim().slice(0, 40);
const summaryOf = async id => parseSummary(await get(`${ENR}/${id}/Summary/`));
const totalsOf = contests => Object.fromEntries(contests.map(c => [c.contest_id, Object.fromEntries(c.choices.map(x => [x.choice, x.votes]))]));

// --- the stored count -----------------------------------------------------------------------------------------------
function shape(e, row) {
  const contests = row.contests || [];
  const reported = row.reported || {};
  const complete = row.precincts_total > 0 && row.precincts_reporting === row.precincts_total && Object.values(reported).every(v => !v || /complete/i.test(v));
  const anyVotes = contests.some(c => c.choices.some(x => x.votes > 0));
  return {
    election_id: e.id, name: row.name || e.name, date: e.date, source_url: `${ENR}/${e.id}/Summary/`,
    status: complete && anyVotes ? 'complete' : anyVotes ? 'counting' : 'waiting',
    soe_updated: row.soe_updated || null, checked_at: row.checked_at || null, changed_at: row.changed_at || null,
    registered_voters: row.registered_voters == null ? null : +row.registered_voters, ballots_cast: row.ballots_cast == null ? null : +row.ballots_cast,
    turnout_pct: row.turnout_pct == null ? null : +row.turnout_pct, precincts_reporting: row.precincts_reporting, precincts_total: row.precincts_total,
    reported, contests, reading_live: live(e),
  };
}

let memo = {}; // no-database fallback: {id: {at, row}}
async function readNow(e, prev) {
  const stamp = await stampOf(e.id).catch(() => null);
  if (prev && stamp && prev.stamp === stamp && (prev.contests || []).length) return {...prev, checked_at: new Date().toISOString(), same: true};
  const {info, contests} = await summaryOf(e.id);
  if (!contests.length) throw new Error('No contests on the SOE page');
  return {name: e.name, stamp, ...info, contests, checked_at: new Date().toISOString()};
}

async function latest(e, {q, hasDb, force = false} = {}) {
  if (!hasDb) {
    const m = memo[e.id];
    if (m && !force && Date.now() - m.at < MIN_GAP) return shape(e, m.row);
    if (!live(e) && m) return shape(e, m.row);
    const row = await readNow(e, m && m.row);
    memo[e.id] = {at: Date.now(), row: {...row, changed_at: row.same ? m.row.changed_at : row.checked_at}};
    return shape(e, memo[e.id].row);
  }
  await q(`insert into election_live (election_id, name, election_date, source_url) values ($1, $2, $3, $4) on conflict (election_id) do nothing`,
    [e.id, e.name, e.date, `${ENR}/${e.id}/Summary/`]);
  let [row] = await q('select * from election_live where election_id = $1', [e.id]);
  const stale = !row.checked_at || Date.now() - new Date(row.checked_at).getTime() >= MIN_GAP;
  if ((stale || force) && live(e)) {
    const claimed = await q(`update election_live set claim_at = now() where election_id = $1 and (claim_at is null or claim_at < now() - interval '40 seconds') returning election_id`, [e.id]);
    if (claimed.length) {
      try {
        const r = await readNow(e, row);
        if (r.same) {
          [row] = await q('update election_live set checked_at = now(), error = null where election_id = $1 returning *', [e.id]);
        } else {
          const changed = JSON.stringify(totalsOf(r.contests)) !== JSON.stringify(totalsOf(row.contests || [])) || r.soe_updated !== row.soe_updated;
          [row] = await q(`update election_live set stamp = $2, soe_updated = $3, registered_voters = $4, ballots_cast = $5, turnout_pct = $6, precincts_reporting = $7,
              precincts_total = $8, reported = $9, contests = $10, checked_at = now(), changed_at = case when $11 then now() else changed_at end, error = null
              where election_id = $1 returning *`,
          [e.id, r.stamp, r.soe_updated, r.registered_voters, r.ballots_cast, r.turnout_pct, r.precincts_reporting, r.precincts_total,
            JSON.stringify(r.reported), JSON.stringify(r.contests), changed]);
          if (changed) {
            await q(`insert into election_live_snapshots (election_id, soe_updated, ballots_cast, precincts_reporting, precincts_total, totals) values ($1, $2, $3, $4, $5, $6)`,
              [e.id, r.soe_updated, r.ballots_cast, r.precincts_reporting, r.precincts_total, JSON.stringify(totalsOf(r.contests))]);
          }
        }
      } catch (err) {
        console.error('election-live read', err.message);
        await q('update election_live set checked_at = now(), error = $2 where election_id = $1', [e.id, String(err.message).slice(0, 300)]).catch(() => {});
      }
    }
  }
  return shape(e, row);
}

async function history(e, {q, hasDb}) {
  if (!hasDb) return [];
  const rows = await q('select taken_at, soe_updated, ballots_cast, precincts_reporting, precincts_total, totals from election_live_snapshots where election_id = $1 order by taken_at', [e.id]).catch(() => []);
  return rows.map(r => ({taken_at: r.taken_at, soe_updated: r.soe_updated, ballots_cast: r.ballots_cast == null ? null : +r.ballots_cast,
    precincts_reporting: r.precincts_reporting, precincts_total: r.precincts_total, totals: r.totals}));
}

function pick(query) {
  const want = parseInt(query.election || query.id || '', 10);
  const e = want ? ELECTIONS.find(x => x.id === want) : current();
  if (!e) { const err = new Error(`Election ${want} is not read live. Live elections: ${ELECTIONS.map(x => x.id).join(', ')}. Past results: /api/v1/datasets/election-results`); err.status = 404; err.expose = true; throw err; }
  return e;
}

// Flat rows (one per choice), for ?format=rows and the MCP tool.
const rows = d => d.contests.flatMap(c => c.choices.map(x => ({election_id: d.election_id, contest_id: c.contest_id, contest: c.contest, choice: x.choice, party: x.party,
  votes: x.votes, pct: x.pct, election_day: x.election_day ?? null, early_voting: x.early_voting ?? null, vote_by_mail: x.vote_by_mail ?? null, provisional: x.provisional ?? null})));

async function forRequest(query, db) {
  const e = pick(query);
  let d;
  try { d = await latest(e, {...db, force: false}); }
  catch (err) { // database down or migration not applied yet: read the SOE directly (per-server cache)
    console.error('election-live db', err.message);
    d = await latest(e, {hasDb: false});
  }
  if (query.contest) { const s = String(query.contest).toLowerCase(); d.contests = d.contests.filter(c => String(c.contest_id) === s || c.contest.toLowerCase().includes(s)); }
  return d;
}

module.exports = {ELECTIONS, parseSummary, forRequest, history: async (query, db) => history(pick(query), db), pick, rows, live, current};
