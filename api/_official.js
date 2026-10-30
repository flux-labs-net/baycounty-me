// Elected officials' dashboard in the government workspace (/staff, migration 0096). A commissioner or council member
// signs in like staff and sees, for their own government: upcoming meetings and what is on each agenda, their own
// voting record, and the numbers (budget by year, spending against the budget, the checkbook, recent contracts).
// Everything here is public record read from the site's own tables; nothing can be changed. Used by api/gov.js
// (?action=official). The shaping functions are pure so the tests run without a database.
const B = require('./_budget');
const OB = require('./_openbooks');

const bad = (msg, status = 400) => Object.assign(new Error(msg), {status});
const DAY = 864e5;
const iso = d => d.toISOString().slice(0, 10);
const day = v => (v ? String(v).slice(0, 10) : null);
const num = v => (v === null || v === undefined || v === '' ? null : Number(v));

// Board names for the meetings dataset's board ids (data/meetings/meetings.json "boards").
const BOARDS = {county: 'Board of County Commissioners', 'county-planning': 'Planning Commission', schools: 'School Board',
  pc: 'City Commission', 'pc-cra': 'CRA Board', pcb: 'City Council', lh: 'City Commission', 'lh-cra': 'CRA Board',
  cw: 'City Commission', 'cw-cra': 'CRA Board', sp: 'City Commission', parker: 'City Council', mb: 'City Council'};
// The PDF reports on the dashboard (site/staff.js), named in the activity log when one is downloaded.
const REPORTS = {briefing: 'Full briefing', agendas: 'Upcoming agendas', votes: 'Voting record', numbers: 'Budget, spending and contracts'};
const boardOf = (gov, id) => id === gov || String(id || '').startsWith(gov + '-');

// The seats on a government's board on a date, from officeholder-terms.
function seats(terms, today) {
  return terms.filter(t => !t.vacant && t.person_id && day(t.start_date) <= today && (!t.end_date || day(t.end_date) >= today))
    .sort((a, b) => (a.seat_order ?? 99) - (b.seat_order ?? 99))
    .map(t => ({person_id: t.person_id, name: t.person_name, seat: t.seat, body: t.body, since: day(t.start_date), appointed: Boolean(t.appointed),
      how: t.how || null, source_url: t.source_url || null}));
}

// Every term one person has held on this government, oldest first.
function career(terms, personId) {
  return terms.filter(t => t.person_id === personId).sort((a, b) => String(a.start_date).localeCompare(String(b.start_date)))
    .map(t => ({seat: t.seat, body: t.body, start: day(t.start_date), end: day(t.end_date), how: t.how || null}));
}

// Meetings of this government's boards: what's coming (today on), then the last few that happened.
function meetings(rows, gov, today, {ahead = 90, recent = 6} = {}) {
  const until = iso(new Date(Date.parse(today + 'T00:00:00Z') + ahead * DAY));
  const mine = rows.filter(m => boardOf(gov, m.board)).map(m => {
    const items = (Array.isArray(m.agenda_items) && m.agenda_items.length ? m.agenda_items : Array.isArray(m.items) ? m.items : [])
      .map(i => (typeof i === 'string' ? {title: i} : {title: i.title || i.item || '', amount: i.amount || null})).filter(i => i.title);
    const money = items.filter(i => i.amount);
    return {board: m.board, board_name: BOARDS[m.board] || m.board, title: m.title, date: day(m.start), start: m.start, location: m.location || null,
      agenda_url: m.agenda_url || null, packet_url: m.packet_url || null, minutes_url: m.minutes_url || null,
      status: m.cancelled ? 'cancelled' : m.expected ? 'expected' : m.status || null, items, money_items: money.length,
      money_total: money.reduce((s, i) => s + (Number(String(i.amount).replace(/[^0-9.]/g, '')) || 0), 0)};
  }).sort((a, b) => String(a.start).localeCompare(String(b.start)));
  return {upcoming: mine.filter(m => m.date >= today && m.date <= until),
    recent: mine.filter(m => m.date < today).slice(-recent).reverse()};
}

const VOTE = {yes: 'yes', aye: 'yes', y: 'yes', no: 'no', nay: 'no', n: 'no', absent: 'absent', abstain: 'abstain', abstained: 'abstain', recused: 'abstain'};

// One member's voting record. rows: member_votes for this person; meta: the votes rows they belong to (by vote_id).
function voteRecord(rows, meta = [], {list = 250} = {}) {
  const byId = new Map(meta.map(v => [v.vote_id, v]));
  const count = {votes: 0, yes: 0, no: 0, absent: 0, abstain: 0, split: 0, on_losing_side: 0};
  const years = new Map();
  const out = rows.map(r => {
    const v = VOTE[String(r.vote || '').toLowerCase()] || 'other', m = byId.get(r.vote_id) || {};
    const outcome = String(m.outcome || '').toLowerCase();
    const losing = Boolean(m.split) && ((v === 'no' && /pass|approv|adopt/.test(outcome)) || (v === 'yes' && /fail|den|reject/.test(outcome)));
    count.votes++; if (count[v] !== undefined) count[v]++; if (m.split) count.split++; if (losing) count.on_losing_side++;
    const y = String(r.date || '').slice(0, 4);
    if (y) { const c = years.get(y) || {year: Number(y), votes: 0, yes: 0, no: 0, absent: 0, abstain: 0}; c.votes++; if (c[v] !== undefined) c[v]++; years.set(y, c); }
    return {date: day(r.date), board: r.board || null, vote: v, headline: r.headline || m.headline || null, outcome: m.outcome || null, tally: m.tally || null,
      split: Boolean(m.split), on_losing_side: losing, amount: num(m.amount), category: m.category || null, vote_id: r.vote_id || null, source_url: r.source_url || m.source_url || null};
  }).sort((a, b) => String(b.date).localeCompare(String(a.date)));
  return {count, by_year: [...years.values()].sort((a, b) => b.year - a.year),
    present_rate: count.votes ? Math.round((count.votes - count.absent) / count.votes * 1000) / 10 : null,
    split_votes: out.filter(v => v.split).slice(0, 60), recent: out.slice(0, list),
    first: out.length ? out[out.length - 1].date : null, last: out.length ? out[0].date : null};
}

// Budget by year (adopted totals) plus the latest two years compared, from budget-years.
function budget(rows, gov) {
  if (!rows.length) return null;
  let cmp = null;
  try { cmp = B.compare(rows, {gov}); } catch (e) { cmp = null; }
  const history = [...new Set(rows.filter(r => r.basis === 'adopted').map(r => Number(r.fiscal_year)))].sort((a, b) => a - b).map(y => {
    const o = {fiscal_year: y};
    for (const r of rows.filter(r => r.basis === 'adopted' && Number(r.fiscal_year) === y && r.section === 'total')) o[r.line_key] = num(r.amount);
    return o;
  }).filter(h => h.total || h.general_fund);
  // Departments when both years break the budget down by department; otherwise funds (a new year often has only its
  // fund totals in, and comparing departments then would read as every department cut to zero).
  const has = (y, s) => rows.some(r => r.basis === 'adopted' && Number(r.fiscal_year) === y && r.section === s);
  const byDept = cmp && has(cmp.from, 'department') && has(cmp.to, 'department');
  const lines = cmp ? (byDept ? cmp.sections.department || [] : [...(cmp.sections.fund || [])].sort((a, b) => Math.abs(b.change || 0) - Math.abs(a.change || 0))) : [];
  return {history, compare: cmp && {from: cmp.from, to: cmp.to, totals: cmp.totals, by: byDept ? 'department' : 'fund',
    label: byDept ? 'General Fund departments' : 'Funds, largest changes', departments: lines.slice(0, 12),
    biggest_increase: cmp.biggest_increase, biggest_decrease: cmp.biggest_decrease, notes: cmp.notes, sources: cmp.sources}};
}

function contracts(rows, today, days = 365) {
  const from = iso(new Date(Date.parse(today + 'T00:00:00Z') - days * DAY));
  const list = rows.filter(c => day(c.date) && day(c.date) >= from).sort((a, b) => String(b.date).localeCompare(String(a.date)))
    .map(c => ({date: day(c.date), vendor: c.vendor, vendor_id: c.vendor_id || null, amount: num(c.amount), purpose: c.purpose || null, method: c.method || null, source_url: c.source_url || null}));
  return {from, rows: list, total: list.reduce((s, c) => s + (c.amount || 0), 0), count: list.length};
}

// A table that isn't created yet (a new deployment) reads as empty.
const safe = async (q, sql, p) => { try { return await q(sql, p); } catch (e) { if (e.code === '42P01') return []; throw e; } };

// The whole dashboard for one official of workspace w. personId: the signed-in official's seat; staff and the
// BayCounty.me owner may pass any current member of the board (all of it is public record).
async function dashboard(q, w, personId, {today = iso(new Date()), only = null} = {}) {
  const terms = await safe(q, `select person_id, person_name, seat, seat_order, body, start_date, end_date, appointed, vacant, how, source_url
      from officeholder_terms where gov_id = $1`, [w.id]);
  const board = seats(terms, today);
  const pid = personId || (board[0] && board[0].person_id) || null;
  const held = career(terms, pid);
  if (pid && !held.length) throw bad('That person doesn’t hold a seat on this government on record.', 404);
  const me = board.find(b => b.person_id === pid) || (held.length ? {person_id: pid, name: terms.find(t => t.person_id === pid).person_name, seat: held[held.length - 1].seat,
    body: held[held.length - 1].body, since: held[held.length - 1].start, former: true} : null);
  const want = k => !only || only === k;
  const out = {official: me ? {...me, terms: held} : null, board, government: w.name, gov_id: w.id, today};
  if (want('agendas')) out.meetings = meetings(await safe(q, `select board, title, start, location, agenda_url, packet_url, minutes_url, status, expected, cancelled, items, agenda_items
      from meetings where board = $1 or board like $2`, [w.id, w.id + '-%']), w.id, today);
  if (want('votes') && pid) {
    const rows = await safe(q, `select "date"::text as date, board, vote, headline, source_url, vote_id from member_votes where person_id = $1 and government_key = $2`, [pid, w.id]);
    const ids = [...new Set(rows.map(r => r.vote_id).filter(Boolean))];
    const meta = ids.length ? await safe(q, `select vote_id, headline, outcome, tally, split, amount, category, source_url from votes where vote_id = any($1)`, [ids]) : [];
    out.votes = voteRecord(rows, meta);
  }
  if (want('numbers')) {
    const by = await safe(q, `select government, gov_id, fiscal_year, basis, section, line_key, name, service, fund_type, amount, in_total, status, source_url
        from budget_years where gov_id = $1`, [w.id]);
    const ct = await safe(q, `select "date"::text as date, vendor, vendor_id, amount, purpose, method, source_url from contracts where government_key = $1 and "date" >= $2::date`,
      [w.id, iso(new Date(Date.parse(today + 'T00:00:00Z') - 365 * DAY))]);
    const [fy] = await safe(q, 'select max(fiscal_year)::int fy from checkbook_payments where gov_id = $1', [w.id]);
    const cb = fy && fy.fy ? await safe(q, `select gov_id, government, fiscal_year, paid_on::text as paid_on, payee, payee_kind, payee_entity_id, amount, fund, method, description, source_file
        from checkbook_payments where gov_id = $1 and fiscal_year = $2`, [w.id, fy.fy]) : [];
    const [bfy] = await safe(q, 'select max(fiscal_year)::int fy from budget_actuals where gov_id = $1', [w.id]);
    const ba = bfy && bfy.fy ? await safe(q, `select gov_id, government, fiscal_year, as_of::text as as_of, line_type, fund, department, account, description, original_budget, amended_budget, actual_ytd, encumbered, source_file
        from budget_actuals where gov_id = $1 and fiscal_year = $2`, [w.id, bfy.fy]) : [];
    const tryIt = f => { try { return f(); } catch (e) { return null; } };
    const book = cb.length ? tryIt(() => OB.checkbook(cb, {gov: w.id})) : null;
    const bva = ba.length ? tryIt(() => OB.budgetActual(ba, {gov: w.id})) : null;
    out.numbers = {budget: budget(by, w.id), contracts: contracts(ct, today),
      checkbook: book && {fiscal_year: book.fiscal_year, from: book.from, through: book.through, total: book.total, payments: book.payments, payees: book.payees,
        by_month: book.by_month, top_payees: book.top_payees.slice(0, 15), largest: book.largest},
      budget_actual: bva && {fiscal_year: bva.fiscal_year, as_of: bva.as_of, elapsed: bva.elapsed, totals: bva.totals,
        departments: bva.departments.map(d => ({name: d.name, budget: d.budget, spent: d.spent, used: d.used})), over_budget: bva.over_budget, running_ahead: bva.running_ahead,
        revenue: bva.revenue && {budget: bva.revenue.budget, collected: bva.revenue.collected}}};
  }
  return out;
}

module.exports = {BOARDS, REPORTS, boardOf, seats, career, meetings, voteRecord, budget, contracts, dashboard};
