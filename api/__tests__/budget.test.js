// Tests for api/_budget.js (GET /api/v1/budget-compare). Run: npm test
// The second group reads the built budget-years dataset (python3 site/build_site.py) and checks Lynn Haven's figures
// against its adopted budget documents.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const {compare, coverage} = require('../_budget');

const row = (fy, section, line_key, name, amount, extra = {}) => ({gov_id: 'x', government: 'City of X', fiscal_year: fy, fy: `FY${fy}`, basis: 'adopted', section, line_key, name, amount, in_total: true, status: 'adopted', ...extra});
const ROWS = [
  row(2025, 'total', 'total', 'Total budget', 1000), row(2026, 'total', 'total', 'Total budget', 1200), row(2024, 'total', 'total', 'Total budget', 900),
  row(2025, 'department', 'd:police', 'Police', 300, {service: 'Police / law enforcement'}), row(2026, 'department', 'd:police', 'Police Department', 330, {service: 'Police / law enforcement'}),
  row(2025, 'department', 'd:parks', 'Parks', 100, {service: 'Parks & recreation'}),
  row(2026, 'department', 'd:it', 'IT', 50, {service: 'Administration & support'}),
  row(2025, 'fund', 'f:general', 'General Fund', 600), row(2026, 'fund', 'f:general', 'General Fund', 500),
];

test('compares two years line by line, with change, percent and status', () => {
  const r = compare(ROWS, {gov: 'x', from: 2025, to: 2026});
  assert.equal(r.from, 2025); assert.equal(r.to, 2026);
  const t = r.totals.find(l => l.key === 'total');
  assert.deepEqual([t.from, t.to, t.change, t.pct], [1000, 1200, 200, 20]);
  const d = Object.fromEntries(r.sections.department.map(l => [l.key, l]));
  assert.equal(d['d:police'].pct, 10); assert.equal(d['d:police'].name, 'Police Department', 'the later year names the line');
  assert.equal(d['d:parks'].status, 'removed'); assert.equal(d['d:it'].status, 'added');
  assert.equal(r.sections.fund[0].change, -100);
  assert.equal(r.biggest_increase.key, 'd:police'); assert.equal(r.biggest_decrease, null, 'a line in only one year is not a cut');
  assert.equal(r.sections.service.length, 3);
  assert.deepEqual(r.history.map(h => [h.fiscal_year, h.total, h.detail]), [[2024, 900, false], [2025, 1000, true], [2026, 1200, true]]);
});

test('defaults to the latest detail year and the one before; rejects years not on record', () => {
  const r = compare(ROWS, {gov: 'X'});
  assert.deepEqual([r.from, r.to], [2025, 2026]);
  assert.match(compare(ROWS, {gov: 'x', from: 2024, to: 2026}).notes.join(' '), /FY2024 has only a total/);
  assert.throws(() => compare(ROWS, {gov: 'x', from: 2019, to: 2026}), e => e.status === 400 && /2024, 2025, 2026/.test(e.message));
  assert.throws(() => compare(ROWS, {gov: 'nope'}), e => e.status === 404);
  assert.throws(() => compare(ROWS, {}), e => e.status === 400);
  assert.throws(() => compare(ROWS, {gov: 'x', from: 2026, to: 2026}), e => e.status === 400);
  assert.deepEqual(coverage(ROWS)[0].adopted_detail, [2025, 2026]);
});

const built = path.join(__dirname, '..', '..', 'site', 'public', 'downloads', 'budget-years.json');
test('Lynn Haven: FY2025 vs FY2026 and FY2022 vs FY2026 match the budget documents', {skip: !fs.existsSync(built)}, () => {
  const rows = JSON.parse(fs.readFileSync(built, 'utf8'));
  const cov = coverage(rows).find(g => g.gov_id === 'lh');
  assert.deepEqual(cov.adopted_detail, [2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027]);
  const a = compare(rows, {gov: 'lh', from: 2025, to: 2026});
  const t = Object.fromEntries(a.totals.map(l => [l.key, l]));
  assert.equal(t.total.from, 52229518); assert.equal(t.total.to, 61858708);
  assert.equal(t.general_fund.from, 19809284); assert.equal(t.general_fund.to, 24353606);
  const fire = a.sections.department.find(l => l.key === 'd522');
  assert.deepEqual([fire.name, fire.from, fire.to], ['Fire', 2743653, 5343217]);
  // every year: departments add up to the General Fund, funds to the total (within rounding)
  for (const y of cov.adopted_detail) {
    const ys = rows.filter(r => r.gov_id === 'lh' && r.fiscal_year === y && r.basis === 'adopted');
    const sum = s => ys.filter(r => r.section === s).reduce((a, r) => a + r.amount, 0);
    const tot = k => ys.find(r => r.line_key === k).amount;
    assert.ok(Math.abs(sum('department') - tot('general_fund')) <= 3, `FY${y} departments`);
    assert.ok(Math.abs(sum('fund') - tot('total')) <= 3, `FY${y} funds`);
  }
  const b = compare(rows, {gov: 'lh', from: 2022, to: 2026});
  assert.equal(b.totals.find(l => l.key === 'total').from, 57108949);
  assert.equal(compare(rows, {gov: 'lh', basis: 'actual'}).to, 2024);
});

test('Bay County: adopted budgets by fund from FY2016 (the site\'s first year), each adding up to the printed total', {skip: !fs.existsSync(built)}, () => {
  const rows = JSON.parse(fs.readFileSync(built, 'utf8'));
  const cov = coverage(rows).find(g => g.gov_id === 'county');
  for (let y = 2016; y <= 2027; y++) assert.ok(cov.adopted_detail.includes(y), `FY${y}`);
  for (let y = 2016; y <= 2024; y++) assert.ok(cov.actual.includes(y), `actuals FY${y}`);
  assert.ok(!cov.adopted_detail.includes(2015) && !cov.actual.includes(2015), 'nothing before FY2016');
  for (const y of cov.adopted_detail) {
    const ys = rows.filter(r => r.gov_id === 'county' && r.fiscal_year === y && r.basis === 'adopted');
    const funds = ys.filter(r => r.section === 'fund').reduce((a, r) => a + r.amount, 0);
    assert.equal(funds, ys.find(r => r.line_key === 'total').amount, `FY${y}`);
  }
  const c = compare(rows, {gov: 'county', from: 2016, to: 2026});
  const t = Object.fromEntries(c.totals.map(l => [l.key, l]));
  assert.deepEqual([t.total.from, t.general_fund.from, t.general_fund.to], [281572075, 106557010, 281737981]);
  assert.equal(c.sections.fund.find(l => l.key === 'f101').name, '101 Transportation');
});
