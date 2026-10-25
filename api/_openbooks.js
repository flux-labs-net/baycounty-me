// Open books: each government's own accounting, published from its finance files (api/_finance/publish.js).
//   GET /api/v1/checkbook?gov=&fy=         totals for one government's payments in one fiscal year (checkbook-payments)
//   GET /api/v1/budget-actual?gov=&fy=&as_of=   spending and revenue against the budget, by department (budget-actuals)
// Pure functions over the dataset rows, so the pages, the MCP tools and the tests share one calculation.
const bad = (msg, status = 400, extra = {}) => Object.assign(new Error(msg), {status, expose: true, extra});
const r2 = n => Math.round((n || 0) * 100) / 100;
const uniq = a => [...new Set(a)].sort((x, y) => (x > y ? 1 : x < y ? -1 : 0));
const n = v => (v === null || v === undefined || v === '' ? 0 : Number(v));
const day = v => (v ? String(v).slice(0, 10) : null);

// Which governments have published data, with their fiscal years and the latest date.
function coverage(rows, dateCol) {
  const by = new Map();
  for (const r of rows) {
    if (!by.has(r.gov_id)) by.set(r.gov_id, {gov_id: r.gov_id, government: r.government, fiscal_years: new Set(), through: null});
    const g = by.get(r.gov_id), d = day(r[dateCol]);
    g.fiscal_years.add(Number(r.fiscal_year));
    if (d && (!g.through || d > g.through)) g.through = d;
  }
  return [...by.values()].map(g => ({...g, fiscal_years: uniq([...g.fiscal_years])})).sort((a, b) => String(a.government).localeCompare(String(b.government)));
}

// The government and fiscal year asked for, defaulting to the latest year of the one asked for (or the first one).
function pick(rows, q, dateCol) {
  const govs = coverage(rows, dateCol);
  if (!govs.length) return {govs, gov: null};
  const want = String(q.gov || q.government || '').trim().toLowerCase();
  const gov = want ? govs.find(g => g.gov_id === want) : govs[0];
  if (!gov) throw bad(`Nothing published yet for "${want}".`, 404, {governments: govs.map(g => g.gov_id)});
  const fyQ = q.fy || q.fiscal_year ? parseInt(String(q.fy || q.fiscal_year).replace(/^FY/i, ''), 10) : null;
  const fy = fyQ ?? gov.fiscal_years[gov.fiscal_years.length - 1];
  if (!gov.fiscal_years.includes(fy)) throw bad(`${gov.government} has no published FY${fy}. Years published: ${gov.fiscal_years.map(y => 'FY' + y).join(', ')}.`, 400, {fiscal_years: gov.fiscal_years});
  return {govs, gov, fy};
}

function checkbook(all, q = {}) {
  const {govs, gov, fy} = pick(all, q, 'paid_on');
  if (!gov) return {governments: [], government: null, note: 'No government has published its check register yet.'};
  const rows = all.filter(r => r.gov_id === gov.gov_id && Number(r.fiscal_year) === fy);
  const months = new Map(), payees = new Map(), funds = new Map(), methods = new Map();
  let total = 0, indiv = {total: 0, payments: 0};
  for (const r of rows) {
    const a = n(r.amount), m = day(r.paid_on).slice(0, 7);
    total += a;
    const mm = months.get(m) || {month: m, total: 0, payments: 0}; mm.total += a; mm.payments++; months.set(m, mm);
    if (r.payee_kind === 'individual') { indiv.total += a; indiv.payments++; }
    else {
      const k = r.payee_entity_id || r.payee;
      const p = payees.get(k) || {payee: r.payee, payee_entity_id: r.payee_entity_id || null, total: 0, payments: 0, first: day(r.paid_on), last: day(r.paid_on)};
      p.total += a; p.payments++; if (day(r.paid_on) < p.first) p.first = day(r.paid_on); if (day(r.paid_on) > p.last) p.last = day(r.paid_on);
      payees.set(k, p);
    }
    const f = r.fund || 'Not given'; funds.set(f, (funds.get(f) || 0) + a);
    const me = r.method || 'other'; methods.set(me, (methods.get(me) || 0) + a);
  }
  const dates = rows.map(r => day(r.paid_on)).sort();
  return {government: gov.government, gov_id: gov.gov_id, fiscal_year: fy, fiscal_years: gov.fiscal_years, governments: govs,
    from: dates[0] || null, through: dates[dates.length - 1] || null, total: r2(total), payments: rows.length, payees: payees.size,
    by_month: [...months.values()].sort((a, b) => a.month.localeCompare(b.month)).map(m => ({...m, total: r2(m.total)})),
    top_payees: [...payees.values()].sort((a, b) => b.total - a.total).slice(0, 25).map(p => ({...p, total: r2(p.total)})),
    by_fund: [...funds].map(([fund, t]) => ({fund, total: r2(t)})).sort((a, b) => b.total - a.total),
    by_method: [...methods].map(([method, t]) => ({method, total: r2(t)})).sort((a, b) => b.total - a.total),
    individuals: {total: r2(indiv.total), payments: indiv.payments},
    largest: rows.filter(r => r.payee_kind !== 'individual').sort((a, b) => n(b.amount) - n(a.amount)).slice(0, 10)
      .map(r => ({paid_on: day(r.paid_on), payee: r.payee, payee_entity_id: r.payee_entity_id || null, amount: n(r.amount), description: r.description || null, fund: r.fund || null})),
    source_files: uniq(rows.map(r => r.source_file).filter(Boolean)),
    note: 'From the government\'s own check register. Voided checks are left out. Payments to private individuals (refunds, reimbursements) are counted but not named.'};
}

// Share of the fiscal year gone by a date. fy is the year the fiscal year ends; Florida cities start October 1.
function elapsed(fy, asOf, startMonth = 10) {
  if (!asOf) return null;
  const start = Date.UTC(startMonth > 1 ? fy - 1 : fy, startMonth - 1, 1), end = Date.UTC(startMonth > 1 ? fy : fy + 1, startMonth - 1, 1);
  const t = Date.parse(asOf + 'T00:00:00Z') + 864e5;  // through the end of that day
  return Math.round(Math.min(1, Math.max(0, (t - start) / (end - start))) * 1000) / 1000;
}

const budgetOf = l => (l.amended_budget === null || l.amended_budget === undefined || l.amended_budget === '' ? n(l.original_budget) : n(l.amended_budget));

function budgetActual(all, q = {}) {
  const {govs: g0, gov, fy} = pick(all, q, 'as_of');
  if (!gov) return {governments: [], government: null, note: 'No government has published a budget-vs-actual report yet.'};
  const mine = all.filter(r => r.gov_id === gov.gov_id && Number(r.fiscal_year) === fy);
  const asOfs = uniq(mine.map(r => day(r.as_of)).filter(Boolean));
  const asOf = q.as_of ? day(q.as_of) : asOfs[asOfs.length - 1];
  if (!asOfs.includes(asOf)) throw bad(`No report as of ${asOf}. Reports published for FY${fy}: ${asOfs.join(', ')}.`, 400, {as_ofs: asOfs});
  const rows = mine.filter(r => day(r.as_of) === asOf);
  const exp = rows.filter(r => r.line_type !== 'revenue'), rev = rows.filter(r => r.line_type === 'revenue');
  const el = elapsed(fy, asOf);
  const group = (lines, keyOf) => {
    const m = new Map();
    for (const l of lines) {
      const k = keyOf(l);
      const g = m.get(k) || {name: k, fund: l.fund || null, original: 0, budget: 0, actual: 0, encumbered: 0, lines: []};
      g.original += n(l.original_budget); g.budget += budgetOf(l); g.actual += n(l.actual_ytd); g.encumbered += n(l.encumbered);
      g.lines.push({account: l.account || null, description: l.description || null, original: n(l.original_budget), budget: budgetOf(l), actual: n(l.actual_ytd), encumbered: n(l.encumbered)});
      m.set(k, g);
    }
    return [...m.values()].map(g => {
      const spent = g.actual + g.encumbered;
      return {...g, original: r2(g.original), budget: r2(g.budget), actual: r2(g.actual), encumbered: r2(g.encumbered), spent: r2(spent),
        used: g.budget > 0 ? Math.round(spent / g.budget * 1000) / 1000 : null, amended: r2(g.budget - g.original),
        lines: g.lines.sort((a, b) => b.budget - a.budget)};
    }).sort((a, b) => b.budget - a.budget);
  };
  const departments = group(exp, l => l.department || l.fund || 'Other');
  const sources = group(rev, l => l.description || l.account || 'Other revenue').map(s => ({...s, collected: s.actual}));
  const sum = (xs, k) => r2(xs.reduce((s, x) => s + x[k], 0));
  const totals = {original: sum(departments, 'original'), budget: sum(departments, 'budget'), actual: sum(departments, 'actual'), encumbered: sum(departments, 'encumbered')};
  totals.spent = r2(totals.actual + totals.encumbered);
  totals.used = totals.budget > 0 ? Math.round(totals.spent / totals.budget * 1000) / 1000 : null;
  // the same totals for every report published this year, oldest first, for the month-by-month line
  const months = asOfs.map(d => {
    const ls = mine.filter(r => day(r.as_of) === d && r.line_type !== 'revenue'), rv = mine.filter(r => day(r.as_of) === d && r.line_type === 'revenue');
    const b = ls.reduce((s, l) => s + budgetOf(l), 0), sp = ls.reduce((s, l) => s + n(l.actual_ytd) + n(l.encumbered), 0);
    return {as_of: d, elapsed: elapsed(fy, d), budget: r2(b), spent: r2(sp), used: b > 0 ? Math.round(sp / b * 1000) / 1000 : null,
      revenue_budget: r2(rv.reduce((s, l) => s + budgetOf(l), 0)), revenue_collected: r2(rv.reduce((s, l) => s + n(l.actual_ytd), 0))};
  });
  const ahead = departments.filter(d => d.budget >= 10000 && d.used !== null && el !== null && d.used - el > 0.2 && d.spent <= d.budget && !/debt/i.test(d.name));
  const over = departments.filter(d => d.budget > 0 && d.spent > d.budget + 0.5);
  return {government: gov.government, gov_id: gov.gov_id, fiscal_year: fy, fiscal_years: gov.fiscal_years, governments: g0, as_of: asOf, as_ofs: asOfs, elapsed: el,
    totals, departments, over_budget: over.map(d => d.name), running_ahead: ahead.map(d => d.name),
    revenue: rev.length ? {budget: sum(sources, 'budget'), collected: sum(sources, 'actual'), sources} : null, months,
    source_files: uniq(rows.map(r => r.source_file).filter(Boolean)),
    note: 'From the government\'s own budget-vs-actual report. Spent includes open purchase orders (encumbered). The budget is the amended budget where the report gives one. Debt payments and once-a-year bills can run ahead of the calendar without a problem.'};
}

module.exports = {checkbook, budgetActual, coverage, elapsed};
