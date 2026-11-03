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
const MIN_GAP = 18 * 1000;      // the SOE stamp is read at most every ~20 s (the full page only when it moved)
const STATE_GAP = 60 * 1000;    // the state's statewide file, at most once a minute

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

// --- statewide totals (Florida Division of Elections) ---------------------------------------------------------------
// The state posts every county's count as one tab-separated file (the same numbers the counties upload, a few minutes
// behind them): flelectionfiles.floridados.gov/enightfilespublic/<YYYYMMDD>_ElecResultsFL.txt. We add the counties
// up for the races Bay County voters share with the rest of the state or district.
const STATE_FILE = d => `https://flelectionfiles.floridados.gov/enightfilespublic/${d.replace(/-/g, '')}_ElecResultsFL.txt`;
async function statewideOf(e) {
  const t = await get(STATE_FILE(e.date), 20000);
  const lines = t.split(/\r?\n/), head = lines.shift().split('\t');
  const ix = k => head.indexOf(k);
  const [RC, RN, CO, J1, PR, PRR, LN, FN, VO] = ['RaceCode', 'RaceName', 'CountyCode', 'Juris1num', 'Precincts', 'PrecinctsReporting', 'CanNameLast', 'CanNameFirst', 'CanVotes'].map(ix);
  const races = {};
  for (const ln of lines) {
    const f = ln.split('\t'); if (f.length < head.length) continue;
    const key = `${f[RC].trim()}|${f[J1].trim()}|${f[RN].trim()}`;
    const r = races[key] || (races[key] = {code: f[RC].trim(), district: f[J1].trim().replace(/^0+/, ''), name: f[RN].trim(), counties: {}, choices: {}});
    r.counties[f[CO]] = [+f[PR] || 0, +f[PRR] || 0];
    const who = f[RC].trim() === 'GOV' ? `${f[FN].trim()} and ${f[LN].trim()}` : [f[FN].trim(), f[LN].trim()].filter(Boolean).join(' '); // governor rows: First = governor, Last = lieutenant
    r.choices[who] = (r.choices[who] || 0) + (+f[VO] || 0);
  }
  const keep = /^(USS|USR|GOV|ATG|CFO|AGR|STS|STR|AMD|SCJ|DCA)$/;
  return Object.values(races).filter(r => keep.test(r.code)).map(r => {
    const c = Object.values(r.counties);
    return {code: r.code, district: r.district || null, name: r.name, counties: c.length, precincts_total: c.reduce((a, x) => a + x[0], 0),
      precincts_reporting: c.reduce((a, x) => a + x[1], 0), choices: r.choices};
  });
}
const fold = s => String(s).normalize('NFD').replace(/[\u0300-\u036f]/g, '');
const lastName = s => fold(s).toLowerCase().replace(/"[^"]*"/g, ' ').split(' and ')[0].replace(/\b(jr|sr|ii|iii)\b\.?/g, '').replace(/[^a-z ]/g, ' ').trim().split(/\s+/).pop();
// The statewide race that matches one SOE contest, as {precincts_reporting, precincts_total, counties, choices:[{choice, votes, pct}]}.
function statewideFor(c, all) {
  if (!all || !all.length) return null;
  const t = c.contest, dist = (t.match(/District\s+(\d+)/i) || [])[1];
  const norm = s => fold(s).toLowerCase().replace(/[^a-z]/g, '');
  let r = null;
  if (/United States Senator/i.test(t)) r = all.find(x => x.code === 'USS');
  else if (/Congress/i.test(t)) r = all.find(x => x.code === 'USR' && x.district === dist);
  else if (/^Governor/i.test(t)) r = all.find(x => x.code === 'GOV');
  else if (/Attorney General/i.test(t)) r = all.find(x => x.code === 'ATG');
  else if (/Chief Financial/i.test(t)) r = all.find(x => x.code === 'CFO');
  else if (/Agriculture/i.test(t)) r = all.find(x => x.code === 'AGR');
  else if (/State Senator/i.test(t)) r = all.find(x => x.code === 'STS' && x.district === dist);
  else if (/State Representative/i.test(t)) r = all.find(x => x.code === 'STR' && x.district === dist);
  else if (/Constitutional Amendment/i.test(t)) {
    const words = t.replace(/^.*Amendment\s*/i, '').toLowerCase().split(/\W+/).filter(w => w.length > 4);
    r = all.filter(x => x.code === 'AMD').map(x => [words.filter(w => x.name.toLowerCase().includes(w.slice(0, 6))).length, x]).sort((a, b) => b[0] - a[0]).filter(x => x[0] > 0).map(x => x[1])[0] || null;
  } else if (/Retention/i.test(t)) {
    const who = norm(lastName(t.replace(/^.*(Judge|Court)\s+/i, '')));
    r = all.find(x => (x.code === 'SCJ' || x.code === 'DCA') && norm(x.name).includes(who));
  }
  if (!r) return null;
  const tot = Object.values(r.choices).reduce((a, v) => a + v, 0);
  const choices = c.choices.map(ch => {
    const k = Object.keys(r.choices).find(n => /^(yes|no)$/i.test(ch.choice) ? norm(n).startsWith(norm(ch.choice)) : lastName(n) === lastName(ch.choice));
    const v = k ? r.choices[k] : null;
    return {choice: ch.choice, votes: v, pct: v != null && tot ? Math.round(10000 * v / tot) / 100 : null};
  });
  return {name: r.name, counties: r.counties, precincts_reporting: r.precincts_reporting, precincts_total: r.precincts_total, total_votes: tot, choices,
    needs: r.code === 'AMD' ? '60% yes statewide to pass' : null};
}

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
    reported, contests: contests.map(c => ({...c, statewide: statewideFor(c, row.statewide)})), statewide_checked_at: row.statewide_at || null, reading_live: live(e),
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
    let sw = m && m.row.statewide, swAt = m && m.row.statewide_at;
    if (!swAt || Date.now() - new Date(swAt).getTime() >= STATE_GAP) { try { sw = await statewideOf(e); swAt = new Date().toISOString(); } catch (err) { console.error('statewide', err.message); } }
    memo[e.id] = {at: Date.now(), row: {...row, statewide: sw, statewide_at: swAt, changed_at: row.same ? m.row.changed_at : row.checked_at}};
    return shape(e, memo[e.id].row);
  }
  await q(`insert into election_live (election_id, name, election_date, source_url) values ($1, $2, $3, $4) on conflict (election_id) do nothing`,
    [e.id, e.name, e.date, `${ENR}/${e.id}/Summary/`]);
  let [row] = await q('select * from election_live where election_id = $1', [e.id]);
  const stale = !row.checked_at || Date.now() - new Date(row.checked_at).getTime() >= MIN_GAP;
  if ((stale || force) && live(e)) {
    const claimed = await q(`update election_live set claim_at = now() where election_id = $1 and (claim_at is null or claim_at < now() - interval '15 seconds') returning election_id`, [e.id]);
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
      if (!row.statewide_at || Date.now() - new Date(row.statewide_at).getTime() >= STATE_GAP) {
        try {
          const sw = await statewideOf(e);
          const [r2] = await q('update election_live set statewide = $2, statewide_at = now() where election_id = $1 returning *', [e.id, JSON.stringify(sw)]);
          if (r2) row = r2;
        } catch (err) { console.error('statewide', err.message); } // column not added yet, or the state file is slow: Bay numbers still go out
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
