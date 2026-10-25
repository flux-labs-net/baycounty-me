// Who held each elected seat in a fiscal year or on a date (GET /api/v1/officials and the MCP tool officials_in_office).
// Reads the officeholder-terms dataset (site/page_datasets.py officeholder_terms()). Pure functions, so the tests, the
// API and the MCP tool give the same answer the government pages show (site/gov.js does the same pick in the browser).
const cutoff = require('./_cutoff');
const bad = (msg, status = 400) => Object.assign(new Error(msg), {status, expose: true});
const FY_START = {schools: 7};  // fiscal years start in October; the school district's in July
const pad = n => String(n).padStart(2, '0');

// The fiscal year's first and last day: FY2026 = 2025-10-01 to 2026-09-30 (schools 2025-07-01 to 2026-06-30).
function fyWindow(gov, year) {
  const m = FY_START[gov] || 10;
  const end = new Date(Date.UTC(year, m - 1, 0));
  return {from: `${year - 1}-${pad(m)}-01`, to: `${year}-${pad(end.getUTCMonth() + 1)}-${pad(end.getUTCDate())}`};
}

// Terms that overlap [from, to]. A term ends on the day its successor starts, so an end date equal to from is out.
const overlaps = (t, from, to) => (!t.start_date || t.start_date <= to) && (!t.end_date || t.end_date > from);

function governments(rows) {
  const by = new Map();
  for (const r of rows) {
    if (!by.has(r.gov_id)) by.set(r.gov_id, {gov_id: r.gov_id, government: r.government, body: r.body, place_id: r.place_id, seats: new Set(), unconfirmed: 0});
    const g = by.get(r.gov_id);
    g.seats.add(r.seat);
    if (r.confirmed === false) g.unconfirmed++;
  }
  return [...by.values()].map(g => ({...g, seats: [...g.seats]}));
}

function inOffice(all, q = {}, today = new Date().toISOString().slice(0, 10)) {
  const gov = String(q.gov || q.government || q.gov_id || '').trim().toLowerCase();
  if (!gov) throw bad('Add ?gov= with a government id, e.g. ?gov=lh. GET /officials with no gov lists them.');
  const rows = all.filter(r => r.gov_id === gov && (!q.place || r.place_id === q.place));
  if (!rows.length) throw bad(`No officeholder terms for "${gov}". Valid ids: ${[...new Set(all.map(r => r.gov_id))].join(', ')}`, 404);
  let from, to, year = null;
  if (q.date) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(q.date))) throw bad('date must be YYYY-MM-DD.');
    if (!cutoff.keep(q.date)) throw bad(`The site starts in ${cutoff.FIRST_YEAR}: pick a date in ${cutoff.FIRST_YEAR} or later.`);
    from = to = String(q.date);
  } else if (q.year) {
    year = Number(q.year);
    if (!Number.isInteger(year) || year < 1900 || year > 2100) throw bad('year must be a fiscal year such as 2019 (the year it ends).');
    if (year < cutoff.FIRST_YEAR) throw bad(`The site starts at FY${cutoff.FIRST_YEAR}: pick ${cutoff.FIRST_YEAR} or later.`);
    ({from, to} = fyWindow(gov, year));
  } else from = to = today;
  const seats = new Map();
  for (const r of rows.slice().sort((a, b) => a.seat_order - b.seat_order || a.term_order - b.term_order)) {
    if (!seats.has(r.seat)) seats.set(r.seat, {seat: r.seat, appointed: !!r.appointed, holders: []});
    if (!overlaps(r, from, to)) continue;
    // a term that began or ended inside the window: someone else held the seat for part of it
    const part = !!((r.start_date && r.start_date > from) || (r.end_date && r.end_date <= to));
    seats.get(r.seat).holders.push({person_name: r.person_name, person_id: r.person_id, vacant: !!r.vacant, confirmed: r.confirmed !== false, start_date: r.start_date, end_date: r.end_date,
      start_approx: !!r.start_approx, end_approx: !!r.end_approx, how: r.how, part_of_period: part, note: r.note, source_title: r.source_title, source_url: r.source_url});
  }
  const first = rows[0];
  return {gov_id: gov, government: first.government, body: first.body, place_id: first.place_id, fiscal_year: year, from, to, seats: [...seats.values()],
    note: 'One entry per person who held the seat during the period; part_of_period marks someone who joined or left during it. vacant = nobody held the seat; confirmed false = a stretch nobody could confirm from the records found. Elected seats, plus the appointed manager or administrator (appointed true).'};
}

module.exports = {fyWindow, overlaps, inOffice, governments};
