// Live overlaps for /connections/overlaps (GET /api/v1/overlaps). The rest of that page is built from datasets the site
// build writes (site/correlations.py: vote-mentions, donor-votes, agenda-parties, development-companies, bid-trail,
// shared-owner-vendors, chamber-overlaps, emergency-purchase-donors, campaign-results). These joins are done here
// because their rows reach the database only after an admin confirms a match or publishes a file:
//   official_business_votes  an official's own registered business (official-businesses, hand-checked) named in a vote
//                            they cast (vote-mentions), with what local governments paid it (entity-connections)
//   nonprofit_board_money    a nonprofit with an official on its board (nonprofit-officials, hand-checked): payments
//                            from that official's government (nonprofit-payments) and the official's votes naming it
//   checkbook_donors         payees in the city checkbooks (checkbook-payments) that gave to a local campaign, or whose
//                            owners did (entity-connections gift and runs links)
//   split_purchases          two or more payments to one payee within 30 days, each just under a common purchasing
//                            threshold (checkbook-payments)
//   school_spending_grades   each school's per-student spending next to its grade for the same year
// A row is a fact in public records side by side with another, not a finding of wrongdoing. Individual donors are never
// named: gifts come only from entity-connections, which holds organizations and business owners (owner-gifts).
const {rest} = require('./_data');

const THRESHOLDS = [5000, 10000, 25000, 35000, 50000];
const UNDER = 0.9;  // "just under": at least 90% of the threshold
// agencies whose officials are the parent government's (a tourist development council is the county's)
const PARENT = {sheriff: 'county', clerk: 'county', property_appraiser: 'county', tax_collector: 'county', soe: 'county', port: 'pc',
  visit_pcb: 'county', destination_pc: 'county', mb_cdc: 'county'};
const SECTIONS = ['official_business_votes', 'nonprofit_board_money', 'checkbook_donors', 'split_purchases', 'school_spending_grades'];
const TTL = 300e3;
let cached = null;

const enc = s => encodeURIComponent(String(s));
const inList = xs => `in.(${xs.map(x => '"' + String(x).replace(/["\\]/g, '') + '"').join(',')})`;
const words = s => String(s || '').toLowerCase().replace(/&/g, ' and ').replace(/[^a-z0-9]+/g, ' ').trim()
  .split(' ').filter(w => w && !['inc', 'llc', 'co', 'corp', 'corporation', 'company', 'the', 'pa', 'pllc', 'lp', 'ltd', 'incorporated'].includes(w)).join(' ');
// payGov is one of the governments in govs (a Set of gov ids), or an agency of one
const own = (payGov, govs) => !!payGov && !!govs && (govs.has(payGov) || govs.has(PARENT[payGov]));

// person id (no prefix) -> Set of the governments they serve, served or ran for (entity-connections). The confirmed-match
// tables don't carry the official's government, so it comes from their profile.
async function govsOf(pids) {
  const rs = await rowsIn('entity_connections', 'from_id,to_id', 'from_id', [...new Set(pids)].map(p => 'person:' + p), '&relation=in.(serves,served,candidate)');
  const out = new Map();
  for (const r of rs) {
    const k = r.from_id.replace(/^person:/, '');
    if (!out.has(k)) out.set(k, new Set());
    out.get(k).add(String(r.to_id).replace(/^gov:/, ''));
  }
  return out;
}
const round = x => Math.round((x || 0) * 100) / 100;

// Every row of a table (paged), with a PostgREST query string.
async function rows(table, query) {
  const out = [];
  for (let off = 0; off < 200000; off += 1000) {
    const r = (await rest(`${table}?${query}&limit=1000&offset=${off}`)).rows;
    out.push(...r);
    if (r.length < 1000) break;
  }
  return out;
}

// Chunked "in" filter, so a long list never makes a URL too long.
async function rowsIn(table, select, col, values, extra = '') {
  const out = [], vs = [...new Set(values.filter(Boolean))];
  for (let i = 0; i < vs.length; i += 60) out.push(...await rows(table, `select=${select}&${col}=${enc(inList(vs.slice(i, i + 60)))}${extra}`));
  return out;
}

function voteOf(roll, name) {
  for (const part of String(roll || '').split('; ')) {
    const i = part.lastIndexOf(': ');
    if (i > 0 && part.slice(0, i).trim().split(' ').pop().toLowerCase() === String(name || '').trim().split(' ').pop().toLowerCase()) return part.slice(i + 2);
  }
  return null;
}

// person id -> vote-mentions rows that list them among the members. The table is small (one row per vote and organization
// named), so it is read whole once; without it (not synced yet) there are no votes, and payments still show.
async function mentionsFor(pids) {
  const want = new Set(pids), out = new Map([...want].map(p => [p, []]));
  let rs = [];
  try { rs = await rows('vote_mentions', 'select=vote_id,date,gov_id,board,entity_id,entity_name,entity_url,headline,amount,outcome,tally,consent_agenda,roll_call,member_ids,source_type,source_url'); }
  catch (e) { console.error('overlaps: vote_mentions', e.message); }
  for (const r of rs) for (const p of String(r.member_ids || '').split('; ')) if (want.has(p)) out.get(p).push(r);
  return out;
}

async function officialBusinessVotes() {
  const obs = await rows('official_businesses', 'select=person_id,official,business,sunbiz_doc_number,gov_id');
  if (!obs.length) return [];
  // the profile each filing belongs to (a business filing can be the same organization as a company)
  const bids = obs.map(o => 'business:' + String(o.sunbiz_doc_number || '').toLowerCase());
  const prof = await rowsIn('entity_profiles', 'entity_id,page_url', 'entity_id', bids);
  const target = new Map(prof.map(p => {
    const m = String(p.page_url || '').match(/^\/public-money\/vendors\/(.+)$|^\/profile\/(\w+)\/(.+)$/);
    return [p.entity_id, m ? (m[1] ? 'vendor:' + m[1] : `${m[2]}:${m[3]}`) : p.entity_id];
  }));
  const pidOf = o => String(o.person_id || '').replace(/^person:/, '');
  const [ments, govs] = await Promise.all([mentionsFor(obs.map(pidOf)), govsOf(obs.map(pidOf))]);
  const ids = [...new Set(bids.map(b => target.get(b) || b))];
  const paid = await rowsIn('entity_connections', 'from_id,to_id,amount', 'to_id', ids, '&relation=eq.paid');
  const out = [];
  for (const o of obs) {
    const bid = 'business:' + String(o.sunbiz_doc_number || '').toLowerCase(), eid = target.get(bid) || bid, bw = words(o.business);
    const pay = paid.filter(p => p.to_id === eid);
    const mine = govs.get(pidOf(o)) || new Set(o.gov_id ? [o.gov_id] : []);
    const paidOwn = round(pay.filter(p => own(String(p.from_id).replace(/^gov:/, ''), mine)).reduce((a, p) => a + (+p.amount || 0), 0));
    for (const m of ments.get(pidOf(o)) || []) {
      if (m.entity_id !== eid && m.entity_id !== bid && words(m.entity_name) !== bw) continue;
      out.push({official: o.official, person_id: 'person:' + pidOf(o), business: o.business, sunbiz_doc_number: o.sunbiz_doc_number, business_id: eid,
        vote_id: m.vote_id, date: m.date, gov_id: m.gov_id, board: m.board, headline: m.headline, official_vote: voteOf(m.roll_call, o.official),
        outcome: m.outcome, tally: m.tally, consent_agenda: m.consent_agenda, paid_by_own_government: paidOwn || null, source_url: m.source_url});
    }
  }
  return out.sort((a, b) => String(b.date).localeCompare(String(a.date)));
}

async function nonprofitBoardMoney() {
  const nos = await rows('nonprofit_officials', 'select=official_id,person_id,official,nonprofit_id,nonprofit,titles,first_year,last_year,current,gov_id');
  if (!nos.length) return [];
  const pays = await rowsIn('nonprofit_payments', 'nonprofit_id,payer,gov_id,amount,date,record_type,source_url', 'nonprofit_id', nos.map(n => n.nonprofit_id));
  const pidOf = n => String(n.official_id || n.person_id || '').replace(/^person:/, '');
  const [ments, govs] = await Promise.all([mentionsFor(nos.map(pidOf)), govsOf(nos.map(pidOf))]);
  const out = [];
  for (const n of nos) {
    const g = govs.get(pidOf(n)) || new Set(n.gov_id ? [n.gov_id] : []);
    const mine = pays.filter(p => p.nonprofit_id === n.nonprofit_id && own(p.gov_id, g));
    const votes = (ments.get(pidOf(n)) || []).filter(m => m.entity_id === 'nonprofit:' + n.nonprofit_id);
    if (!mine.length && !votes.length) continue;
    out.push({official: n.official, person_id: 'person:' + pidOf(n), nonprofit: n.nonprofit, nonprofit_id: 'nonprofit:' + n.nonprofit_id, titles: n.titles,
      board_years: [n.first_year, n.last_year].filter(Boolean).join('–') || null, current: n.current, gov_id: n.gov_id || [...g][0] || null,
      paid_by_own_government: round(mine.reduce((a, p) => a + (+p.amount || 0), 0)) || null, payment_records: mine.length,
      payers: [...new Set(mine.map(p => p.payer))].join('; ') || null,
      votes: votes.map(m => ({vote_id: m.vote_id, date: m.date, headline: m.headline, official_vote: voteOf(m.roll_call, n.official), outcome: m.outcome, source_url: m.source_url}))});
  }
  return out.sort((a, b) => (b.paid_by_own_government || 0) - (a.paid_by_own_government || 0));
}

async function checkbook() {
  return rows('checkbook_payments', 'select=gov_id,government,fiscal_year,paid_on,payee,payee_kind,payee_entity_id,amount,doc_no,description,source_url&or=(payee_kind.is.null,payee_kind.neq.individual)');
}

async function checkbookDonors(cb) {
  const by = new Map();
  for (const p of cb) {
    if (!p.payee_entity_id) continue;
    const k = p.gov_id + '|' + p.payee_entity_id;
    const x = by.get(k) || {gov_id: p.gov_id, government: p.government, payee: p.payee, payee_id: p.payee_entity_id, paid: 0, payments: 0, years: new Set()};
    x.paid += +p.amount || 0; x.payments++; if (p.fiscal_year) x.years.add(p.fiscal_year);
    by.set(k, x);
  }
  if (!by.size) return [];
  const payees = [...new Set([...by.values()].map(x => x.payee_id))];
  const owners = await rowsIn('entity_connections', 'from_id,to_id', 'to_id', payees, '&relation=eq.runs&from_id=like.owner%3A*');
  const donors = [...new Set([...payees, ...owners.map(o => o.from_id)])];
  const gifts = await rowsIn('entity_connections', 'from_id,from_name,to_id,to_name,amount', 'from_id', donors, '&relation=eq.gift');
  const serve = await rowsIn('entity_connections', 'from_id,to_id', 'from_id', [...new Set(gifts.map(g => g.to_id))], '&relation=in.(serves,served)');
  const out = [];
  for (const x of by.values()) {
    const ds = new Set([x.payee_id, ...owners.filter(o => o.to_id === x.payee_id).map(o => o.from_id)]);
    const gs = gifts.filter(g => ds.has(g.from_id));
    if (!gs.length) continue;
    const here = gs.filter(g => serve.some(s => s.from_id === g.to_id && own(x.gov_id, new Set([String(s.to_id).replace(/^gov:/, '')]))));
    out.push({gov_id: x.gov_id, government: x.government, payee: x.payee, payee_id: x.payee_id, paid: round(x.paid), payments: x.payments,
      fiscal_years: [...x.years].sort().join(', '), gave_to_campaigns: round(gs.reduce((a, g) => a + (+g.amount || 0), 0)),
      gave_to_officials_here: round(here.reduce((a, g) => a + (+g.amount || 0), 0)) || null,
      gave_to: [...new Set(gs.map(g => g.to_name))].join('; '), through_owner: gs.some(g => g.from_id !== x.payee_id)});
  }
  return out.sort((a, b) => b.paid - a.paid);
}

function splitPurchases(cb) {
  const by = new Map();
  for (const p of cb) {
    const a = +p.amount;
    const t = THRESHOLDS.find(t => a >= t * UNDER && a < t);
    if (!t || !p.paid_on) continue;
    const k = [p.gov_id, p.payee_entity_id || words(p.payee), t].join('|');
    if (!by.has(k)) by.set(k, []);
    by.get(k).push(p);
  }
  const out = [];
  for (const [k, ps] of by) {
    ps.sort((a, b) => String(a.paid_on).localeCompare(String(b.paid_on)));
    let run = [ps[0]];
    const flush = () => {
      if (run.length >= 2) out.push({gov_id: run[0].gov_id, government: run[0].government, payee: run[0].payee, payee_id: run[0].payee_entity_id || null,
        threshold: +k.split('|')[2], payments: run.length, total: round(run.reduce((a, p) => a + (+p.amount || 0), 0)),
        first_date: run[0].paid_on, last_date: run[run.length - 1].paid_on,
        items: run.map(p => ({paid_on: p.paid_on, amount: +p.amount, doc_no: p.doc_no, description: p.description, source_url: p.source_url}))});
    };
    for (const p of ps.slice(1)) {
      if ((Date.parse(p.paid_on) - Date.parse(run[run.length - 1].paid_on)) / 864e5 <= 30) run.push(p);
      else { flush(); run = [p]; }
    }
    flush();
  }
  return out.sort((a, b) => b.total - a.total);
}

async function schoolSpendingGrades() {
  const [sp, gr] = await Promise.all([rows('school_spending', 'select=school_id,school,year,total_per_student,enrollment,source_url'),
    rows('school_grades', 'select=school_id,year,grade,percent_of_points')]);
  const g = new Map(gr.map(r => [r.school_id + '|' + r.year, r]));
  return sp.filter(s => g.has(s.school_id + '|' + s.year)).map(s => {
    const x = g.get(s.school_id + '|' + s.year);
    return {school_id: s.school_id, school: s.school, year: s.year, per_student: s.total_per_student, enrollment: s.enrollment, grade: x.grade,
      percent_of_points: x.percent_of_points, source_url: s.source_url};
  }).sort((a, b) => (b.year - a.year) || String(a.school).localeCompare(String(b.school)));
}

async function safe(fn) {
  try { return {rows: await fn(), error: null}; }
  catch (e) { console.error('overlaps', e.message); return {rows: [], error: 'Could not read this part right now.'}; }
}

async function overlaps(query = {}) {
  const want = query.section ? String(query.section) : null;
  if (want && !SECTIONS.includes(want)) throw Object.assign(new Error(`Unknown section "${want.slice(0, 40)}". Sections: ${SECTIONS.join(', ')}.`), {status: 400, expose: true});
  if (!cached || Date.now() - cached.t > TTL) {
    const cb = await safe(checkbook);
    const [obv, nbm, csg] = await Promise.all([safe(officialBusinessVotes), safe(nonprofitBoardMoney), safe(schoolSpendingGrades)]);
    const cbd = cb.error ? cb : await safe(() => checkbookDonors(cb.rows));
    const sp = cb.error ? cb : await safe(async () => splitPurchases(cb.rows));
    cached = {t: Date.now(), v: {official_business_votes: obv, nonprofit_board_money: nbm, checkbook_donors: cbd, split_purchases: sp, school_spending_grades: csg}};
  }
  const gov = query.gov ? String(query.gov) : null;
  const data = {};
  for (const s of want ? [want] : SECTIONS) {
    const x = cached.v[s];
    data[s] = {rows: gov ? x.rows.filter(r => r.gov_id === gov || PARENT[r.gov_id] === gov) : x.rows, error: x.error};
  }
  return {data, thresholds: THRESHOLDS,
    note: 'Live joins of hand-confirmed matches and database-only rows. The other overlaps are datasets: vote-mentions, donor-votes, agenda-parties, development-companies, bid-trail, shared-owner-vendors, chamber-overlaps, emergency-purchase-donors and campaign-results. A row puts two public records side by side; it is not a finding of wrongdoing.'};
}

module.exports = {overlaps, splitPurchases, voteOf, words, SECTIONS, THRESHOLDS};
