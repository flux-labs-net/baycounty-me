// Open books: publishing finance files to the public tables (api/_finance/publish.js) and the totals the checkbook and
// budget tracker pages show (api/_openbooks.js). Pure functions, no database. Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const {checkbookRows, budgetRows, isOrganization, entityIndex, orgKey} = require('../_finance/publish');
const {checkbook, budgetActual, elapsed} = require('../_openbooks');

const upload = {id: 7, original_name: 'checks-oct.csv'};
const workspace = {government_key: 'lh', name: 'Lynn Haven', fy_start_month: 10};

test('organizations are named, people are not', () => {
  assert.ok(isOrganization('Gulf Power Company'));
  assert.ok(isOrganization('GRAINGER'));
  assert.ok(isOrganization('Smith & Sons'));
  assert.ok(isOrganization('A1 Lawn'));
  assert.ok(isOrganization('Coastal Fleet Parts'));
  assert.equal(isOrganization('Jane Doe'), false);
  assert.equal(isOrganization('John Q Public'), false);
  assert.ok(isOrganization('Jane Doe', 'vendor:jane-doe'), 'a known profile counts');
  assert.ok(isOrganization('Jane Doe', null, true), 'paid again and again against invoices counts');
  assert.equal(isOrganization(''), false);
});

test('entity index matches names without company suffixes', () => {
  const idx = entityIndex([{entity_id: 'vendor:gulf-power', kind: 'vendor', name: 'Gulf Power Co.'}, {entity_id: 'business:gp', kind: 'business', name: 'Gulf Power Company'}]);
  assert.equal(idx.get(orgKey('GULF POWER COMPANY')), 'vendor:gulf-power', 'vendor profiles win over business ones');
});

test('check register rows: voids left out, individuals withheld', () => {
  const disb = [
    {id: 1, paid_on: '2025-10-03', payee: 'Gulf Power Company', amount: 1200.5, doc_no: '1001', invoice_no: 'INV-9', description: 'Electric', fund: 'General'},
    {id: 2, paid_on: '2025-10-04', payee: 'Jane Doe', amount: 45, doc_no: '1002', invoice_no: 'R-1', description: 'Utility deposit refund 123 Main St'},
    {id: 3, paid_on: '2025-10-05', payee: 'Acme Supply', amount: 300, doc_no: '1003', is_void: true},
    {id: 4, paid_on: '2025-10-06', payee: 'Acme Supply', amount: 80, doc_no: '1004'},
    {id: 5, paid_on: '2025-10-07', payee: 'Acme Supply', amount: -80, doc_no: '1004'},
    {id: 6, paid_on: '2025-09-30', payee: 'Bay Tire', amount: 99, doc_no: '0999'},
  ];
  const rows = checkbookRows(disb, {upload, workspace, index: new Map([[orgKey('Gulf Power'), 'vendor:gulf-power']])});
  assert.deepEqual(rows.map(r => r.doc_no), ['1001', '1002', '0999'], 'void and reversed checks are left out');
  const [gp, person, tire] = rows;
  assert.equal(gp.payee_entity_id, 'vendor:gulf-power');
  assert.equal(gp.government, 'Lynn Haven');
  assert.equal(gp.fiscal_year, 2026);
  assert.equal(tire.fiscal_year, 2025);
  assert.equal(person.payee, 'Individual (name withheld)');
  assert.equal(person.payee_kind, 'individual');
  assert.equal(person.invoice_no, null);
  assert.equal(person.description, 'Refund to an individual');
  assert.ok(!JSON.stringify(rows).includes('Main St') && !JSON.stringify(rows).includes('Jane'));
  assert.equal(new Set(rows.map(r => r.record_hash)).size, rows.length);
});

test('budget report rows: revenue and expense lines', () => {
  const rows = budgetRows([
    {id: 1, fiscal_year: 2026, as_of: '2026-01-31', account: '001-311-100', description: 'Property taxes', original_budget: 1000, actual_ytd: 600},
    {id: 2, fiscal_year: 2026, as_of: '2026-01-31', account: '001-521-120', department: 'Police', description: 'Salaries', original_budget: 500, amended_budget: 550, actual_ytd: 200, encumbered: 10},
  ], {upload, workspace});
  assert.deepEqual(rows.map(r => r.line_type), ['revenue', 'expense']);
  assert.equal(rows[1].amended_budget, 550);
  assert.equal(rows[0].gov_id, 'lh');
});

test('elapsed: share of a Florida fiscal year gone', () => {
  assert.equal(elapsed(2026, '2026-09-30'), 1);
  assert.equal(elapsed(2026, '2025-09-15'), 0);
  assert.ok(Math.abs(elapsed(2026, '2026-03-31') - 0.5) < 0.01);
  assert.equal(elapsed(2026, null), null);
});

const pay = (paid_on, payee, amount, extra = {}) => ({gov_id: 'lh', government: 'Lynn Haven', fiscal_year: paid_on > '2025-09-30' ? 2026 : 2025, paid_on, payee, amount, payee_kind: 'organization', fund: 'General', method: 'check', ...extra});

test('checkbook totals', () => {
  const rows = [pay('2025-10-03', 'Gulf Power', 100, {payee_entity_id: 'vendor:gulf-power'}), pay('2025-10-20', 'Gulf Power', 50, {payee_entity_id: 'vendor:gulf-power'}),
    pay('2025-11-02', 'Acme', 70), pay('2025-11-03', 'Individual (name withheld)', 20, {payee_kind: 'individual'}), pay('2025-09-01', 'Acme', 999)];
  const d = checkbook(rows, {gov: 'lh'});
  assert.equal(d.fiscal_year, 2026);
  assert.deepEqual(d.fiscal_years, [2025, 2026]);
  assert.equal(d.total, 240);
  assert.equal(d.payments, 4);
  assert.equal(d.payees, 2);
  assert.deepEqual(d.individuals, {total: 20, payments: 1});
  assert.equal(d.top_payees[0].payee_entity_id, 'vendor:gulf-power');
  assert.deepEqual(d.by_month.map(m => m.month), ['2025-10', '2025-11']);
  assert.ok(d.largest.every(r => r.payee !== 'Individual (name withheld)'));
  assert.equal(checkbook(rows, {gov: 'lh', fy: 'FY2025'}).total, 999);
  assert.throws(() => checkbook(rows, {gov: 'pc'}), e => e.status === 404 && e.extra.governments[0] === 'lh');
  assert.throws(() => checkbook(rows, {gov: 'lh', fy: 2020}), e => e.status === 400);
});

test('checkbook and budget tracker with nothing published', () => {
  assert.equal(checkbook([]).government, null);
  assert.equal(budgetActual([]).government, null);
});

const line = (as_of, department, budget, actual, extra = {}) => ({gov_id: 'lh', government: 'Lynn Haven', fiscal_year: 2026, as_of, line_type: 'expense', department,
  original_budget: budget, actual_ytd: actual, encumbered: 0, ...extra});

test('budget vs actual by department', () => {
  const rows = [line('2026-01-31', 'Police', 100000, 30000), line('2026-01-31', 'Parks', 20000, 15000), line('2026-01-31', 'Fire', 10000, 9000, {encumbered: 2000}),
    line('2026-01-31', 'Debt service', 50000, 50000), line('2026-01-31', null, 1000, 500, {line_type: 'revenue', description: 'Property taxes'}),
    line('2025-12-31', 'Police', 100000, 20000)];
  const d = budgetActual(rows, {gov: 'lh'});
  assert.equal(d.as_of, '2026-01-31');
  assert.deepEqual(d.as_ofs, ['2025-12-31', '2026-01-31']);
  assert.deepEqual(d.over_budget, ['Fire']);
  assert.deepEqual(d.running_ahead, ['Parks'], 'debt payments and over-budget departments are not "ahead"');
  assert.equal(d.totals.budget, 180000);
  assert.equal(d.totals.spent, 106000);
  assert.equal(d.revenue.collected, 500);
  assert.equal(d.months.length, 2);
  assert.equal(budgetActual(rows, {gov: 'lh', as_of: '2025-12-31'}).totals.actual, 20000);
  assert.throws(() => budgetActual(rows, {gov: 'lh', as_of: '2026-05-31'}), e => e.status === 400 && e.extra.as_ofs.length === 2);
});
