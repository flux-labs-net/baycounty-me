// The confirm report staff see before a file is taken in (Send records, step one). It shows what the file says in a
// form someone who knows their own books can check at a glance: totals by month and by department or fund, the biggest
// payees, the first and last check number, and the date range. If the numbers don't look like theirs, it's the wrong
// file, and nothing has been imported yet. Pure: takes the rows the reader found.
const r2 = n => Math.round((Number(n) || 0) * 100) / 100;
const TOP = 10;

function group(rows, keyOf, valOf) {
  const m = new Map();
  for (const r of rows) {
    const k = keyOf(r) || '(none)';
    const g = m.get(k) || {key: k, total: 0, rows: 0};
    g.total += Number(valOf(r)) || 0; g.rows++;
    m.set(k, g);
  }
  return [...m.values()].map(g => ({...g, total: r2(g.total)}));
}
const byTotal = list => list.sort((a, b) => Math.abs(b.total) - Math.abs(a.total));
const byKey = list => list.sort((a, b) => String(a.key).localeCompare(String(b.key)));
const top = list => { const s = byTotal(list); return s.length > TOP ? [...s.slice(0, TOP), {key: `${s.length - TOP} more`, total: r2(s.slice(TOP).reduce((a, g) => a + g.total, 0)), rows: s.slice(TOP).reduce((a, g) => a + g.rows, 0), rest: true}] : s; };
const month = d => (d ? String(d).slice(0, 7) : null);
const range = ds => { const s = ds.filter(Boolean).map(String).sort(); return {first: s[0] || null, last: s[s.length - 1] || null}; };

function checkbook(rows) {
  const live = rows.filter(r => !r.is_void);
  const nums = live.map(r => String(r.doc_no || '').trim()).filter(s => /^\d{1,12}$/.test(s)).map(Number).sort((a, b) => a - b);
  return {
    kind: 'checkbook', rows: rows.length, voided: rows.length - live.length, total: r2(live.reduce((a, r) => a + (Number(r.amount) || 0), 0)),
    dates: range(live.map(r => r.paid_on)),
    checks: nums.length ? {first: nums[0], last: nums[nums.length - 1], count: nums.length} : null,
    by_month: byKey(group(live, r => month(r.paid_on), r => r.amount)),
    by_fund: top(group(live, r => r.fund, r => r.amount)),
    top_payees: top(group(live, r => r.payee, r => r.amount)),
    largest: live.slice().sort((a, b) => (Number(b.amount) || 0) - (Number(a.amount) || 0)).slice(0, 5)
      .map(r => ({payee: r.payee, amount: r2(r.amount), paid_on: r.paid_on || null, doc_no: r.doc_no || null})),
  };
}

function budget(rows) {
  const sum = f => r2(rows.reduce((a, r) => a + (Number(r[f]) || 0), 0));
  const dept = r => r.department || r.fund;
  const g = new Map();
  for (const r of rows) {
    const k = dept(r) || '(none)';
    const x = g.get(k) || {key: k, original: 0, amended: 0, actual: 0, rows: 0};
    x.original += Number(r.original_budget) || 0; x.amended += Number(r.amended_budget) || 0; x.actual += Number(r.actual_ytd) || 0; x.rows++;
    g.set(k, x);
  }
  const depts = [...g.values()].map(x => ({...x, original: r2(x.original), amended: r2(x.amended), actual: r2(x.actual), total: r2(x.amended || x.original)}));
  return {kind: 'budget', rows: rows.length, original: sum('original_budget'), amended: sum('amended_budget'), actual: sum('actual_ytd'), encumbered: sum('encumbered'),
    as_of: range(rows.map(r => r.as_of)).last, by_department: top(depts)};
}

function contracts(rows) {
  return {kind: 'contracts', rows: rows.length, total: r2(rows.reduce((a, r) => a + (Number(r.amount) || 0), 0)), dates: range(rows.map(r => r.date)),
    by_month: byKey(group(rows, r => month(r.date), r => r.amount)), top_payees: top(group(rows, r => r.vendor, r => r.amount))};
}

function payroll(rows) {
  const people = rows.reduce((a, r) => a + ((r.salaries || []).length || 0), 0);
  const total = r2(rows.reduce((a, r) => a + (r.salaries || []).reduce((x, s) => x + (Number(s) || 0), 0), 0));
  return {kind: 'payroll', rows: rows.length, people, total,
    by_department: top(group(rows.flatMap(r => (r.salaries || []).map(s => ({d: r.department, s}))), x => x.d, x => x.s))};
}

function counted(kind, rows, keyOf) {
  return {kind, rows: rows.length, by_group: top(group(rows, keyOf, () => 1)).map(g => ({key: g.key, rows: g.rows}))};
}

function confirmReport(kind, rows = []) {
  if (kind === 'checkbook' || kind === 'disbursements') return checkbook(rows);
  if (kind === 'budget') return budget(rows);
  if (kind === 'contracts') return contracts(rows);
  if (kind === 'payroll') return payroll(rows);
  if (kind === 'appointments') return counted('appointments', rows, r => r.board);
  if (kind === 'fees') return counted('fees', rows, r => r.category);
  return {kind, rows: rows.length};
}

module.exports = {confirmReport};
