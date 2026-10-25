// Compare one government's budget in two fiscal years, line by line (GET /api/v1/budget-compare).
// Reads the budget-years dataset (site/page_datasets.py budget_years()). Pure functions, so the tests and the MCP
// tool use the same comparison the page shows.
const SECTIONS = {adopted: ['department', 'fund'], actual: ['spending', 'revenue']};
const bad = (msg, status = 400, extra = {}) => Object.assign(new Error(msg), {status, expose: true, extra});
const uniq = a => [...new Set(a)].sort((x, y) => x - y);
const pct = (a, b) => (a ? Math.round((b - a) / Math.abs(a) * 1000) / 10 : null);

// Which years each government has, per basis: totals only, or line-by-line detail.
function coverage(rows) {
  const by = new Map();
  for (const r of rows) {
    if (!by.has(r.gov_id)) by.set(r.gov_id, {gov_id: r.gov_id, government: r.government, adopted_totals: [], adopted_detail: [], actual: []});
    const g = by.get(r.gov_id);
    if (r.basis === 'adopted') (r.section === 'total' ? g.adopted_totals : g.adopted_detail).push(r.fiscal_year);
    else g.actual.push(r.fiscal_year);
  }
  return [...by.values()].map(g => ({...g, adopted_totals: uniq([...g.adopted_totals, ...g.adopted_detail]), adopted_detail: uniq(g.adopted_detail), actual: uniq(g.actual)}));
}

function lines(rows, from, to, keyOf = r => r.line_key, nameOf = r => r.name) {
  const m = new Map();
  for (const r of rows) {
    if (r.fiscal_year !== from && r.fiscal_year !== to) continue;
    const k = keyOf(r);
    if (!m.has(k)) m.set(k, {key: k, name: null, from: null, to: null, in_total: r.in_total !== false});
    const l = m.get(k), side = r.fiscal_year === to ? 'to' : 'from';
    l[side] = (l[side] || 0) + Number(r.amount || 0);
    if (side === 'to' || !l.name) l.name = nameOf(r);
    if (r.fund_type && (side === 'to' || !l.fund_type)) l.fund_type = r.fund_type;
    if (r.service && (side === 'to' || !l.service)) l.service = r.service;
  }
  return [...m.values()].map(l => ({...l, change: (l.to || 0) - (l.from || 0), pct: l.from != null && l.to != null ? pct(l.from, l.to) : null,
    status: l.from == null ? 'added' : l.to == null ? 'removed' : 'both'}))
    .sort((a, b) => Math.abs(b.change) - Math.abs(a.change) || (b.to || 0) - (a.to || 0));
}

function compare(all, q = {}) {
  const gov = String(q.gov || q.government || '').trim().toLowerCase();
  if (!gov) throw bad('Add ?gov= with a government id, e.g. ?gov=lh. GET /budget-compare with no gov lists them.');
  const rows = all.filter(r => String(r.gov_id).toLowerCase() === gov);
  if (!rows.length) throw bad(`No budgets on record for "${gov}".`, 404, {governments: coverage(all).map(g => g.gov_id)});
  const basis = q.basis === 'actual' ? 'actual' : 'adopted';
  const mine = rows.filter(r => r.basis === basis);
  const years = uniq(mine.map(r => r.fiscal_year));
  const detail = uniq(mine.filter(r => r.section !== 'total').map(r => r.fiscal_year));
  if (years.length < 2) throw bad(`${rows[0].government} has ${years.length ? 'only FY' + years[0] : 'no'} ${basis === 'actual' ? 'audited actuals' : 'adopted budget'} on record, so there is nothing to compare yet.`, 404, {years});
  const num = v => (v == null || v === '' ? null : parseInt(String(v).replace(/^FY/i, ''), 10));
  // Default: the latest year with line-by-line detail, against the detail year before it (pages open on the latest year).
  const pool = detail.length >= 2 ? detail : years;
  let to = num(q.to) ?? pool[pool.length - 1];
  let from = num(q.from) ?? ([...pool].reverse().find(y => y < to) ?? years.filter(y => y < to).pop());
  for (const [k, y] of [['from', from], ['to', to]])
    if (!years.includes(y)) throw bad(`${rows[0].government} has no ${basis === 'actual' ? 'audited actuals' : 'adopted budget'} for ${k}=${y}. Years on record: ${years.join(', ')}.`, 400, {years});
  if (from === to) throw bad('Pick two different years.', 400, {years});
  const yr = mine.filter(r => r.fiscal_year === from || r.fiscal_year === to);
  const sec = s => yr.filter(r => r.section === s);
  const sections = {};
  for (const s of SECTIONS[basis]) sections[s] = lines(sec(s), from, to);
  if (basis === 'adopted') sections.service = lines(sec('department'), from, to, r => r.service || 'Other services', r => r.service || 'Other services');
  const ORDER = ['total', 'general_fund', 'revenue_total', 'spending_total'];
  const totals = lines(sec('total'), from, to).sort((a, b) => ORDER.indexOf(a.key) - ORDER.indexOf(b.key));
  const history = years.map(y => {
    const o = {fiscal_year: y, fy: `FY${y}`, detail: detail.includes(y)};
    for (const r of mine.filter(r => r.fiscal_year === y && r.section === 'total')) { o[r.line_key] = Number(r.amount); o.status = o.status || r.status; }
    return o;
  });
  // Plain notes about what the two years can and can't tell you
  const notes = [];
  const main = sections[SECTIONS[basis][0]];
  const has = y => main.some(l => l[y === from ? 'from' : 'to'] != null);
  for (const y of [from, to]) if (!has(y)) notes.push(`FY${y} has only a total on record, no ${basis === 'actual' ? 'breakdown' : 'fund or department lines'}.`);
  if (has(from) && has(to)) {
    const both = main.filter(l => l.status === 'both').length;
    if (both < main.length / 2) notes.push(`Most ${basis === 'actual' ? 'lines' : 'department names'} differ between the two documents, so compare by service or total.`);
  }
  const st = y => (history.find(h => h.fiscal_year === y) || {}).status;
  if (st(from) && st(to) && st(from) !== st(to)) notes.push(`FY${from} is ${st(from)} and FY${to} is ${st(to)}, so they aren't measured the same way.`);
  const src = y => [...new Set(yr.filter(r => r.fiscal_year === y && r.source_url).map(r => r.source_url))];
  const moved = main.filter(l => l.status === 'both' && l.in_total && l.from > 0 && l.to > 0);  // credits (negative lines) aren't spending
  return {government: rows[0].government, gov_id: rows[0].gov_id, basis, from, to, years, detail_years: detail,
    other_basis_years: uniq(rows.filter(r => r.basis !== basis).map(r => r.fiscal_year)),
    totals, sections, history,
    biggest_increase: moved.filter(l => l.change > 0)[0] || null, biggest_decrease: moved.filter(l => l.change < 0)[0] || null,
    notes, sources: {from: src(from), to: src(to)},
    about: basis === 'actual'
      ? 'Audited revenue and spending from the Annual Financial Reports each government files with the state (all operating funds). Transfers and borrowing are listed but left out of the totals (in_total false).'
      : 'Adopted budgets: what the commission approved for the year. Totals count money moved between funds in both funds, and department lines are the General Fund only.'};
}

module.exports = {compare, coverage, lines};
