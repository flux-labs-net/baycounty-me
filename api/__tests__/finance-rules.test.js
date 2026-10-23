// Tests for the finance flag rules (api/_finance/rules.js).
const test = require('node:test');
const assert = require('node:assert/strict');
const {runRules, isRevenue, holidays} = require('../_finance/rules');

const ws = {id: 'lh', fy_start_month: 10, settings: {bid_threshold: 35000, manager_threshold: 3500}};
let nextId = 1;
const pay = (paid_on, payee, amount, extra = {}) => ({id: nextId++, paid_on, payee, payee_key: payee.toUpperCase(), amount, doc_no: String(50000 + nextId), method: 'check', is_void: false, ...extra});
const only = (flags, rule) => flags.filter(f => f.rule === rule);
const run = d => runRules({workspace: ws, today: '2026-06-15', ...d});

test('rule 1: a held upload that does not tie is urgent with the difference at risk', () => {
  const f = only(run({uploads: [{id: 9, original_name: 'oct.csv', tie_status: 'mismatch', tie_difference: -100, parsed_total: 900, printed_total: 1000, status: 'held'}]}), 'file_tie');
  assert.equal(f.length, 1);
  assert.equal(f[0].severity, 'urgent');
  assert.equal(f[0].amount_at_risk, 100);
});

test('rule 2: months with bank activity and no rec are flagged once per account; late recs are flagged', () => {
  const txns = [
    {id: 1, account_hash: 'A', account_label: '…4455', posted_on: '2026-01-10', amount: -500},
    {id: 2, account_hash: 'A', account_label: '…4455', posted_on: '2026-02-10', amount: 2000},
    {id: 3, account_hash: 'A', account_label: '…4455', posted_on: '2026-03-10', amount: -300},
  ];
  const recs = [{id: 10, account_hash: 'A', period_end: '2026-01-31', statement_balance: 100, book_balance: 100, reconciled_on: '2026-04-15', approved_by: 'K'}];
  const f = only(run({bankTxns: txns, bankRecs: recs}), 'rec_overdue');
  const missing = f.find(x => x.facts.months);
  assert.deepEqual(missing.facts.months, ['2026-02', '2026-03', '2026-04']);
  assert.equal(missing.amount_at_risk, 2300);
  const late = f.find(x => x.facts.month === '2026-01');
  assert.ok(late.title.includes('days late'));
  assert.equal(f.find(x => /no reviewer/.test(x.title)), undefined);
});

test('rule 2: May is not due yet on June 15 (30-day window)', () => {
  const txns = [{id: 1, account_hash: 'A', posted_on: '2026-05-10', amount: -5}];
  assert.equal(only(run({bankTxns: txns}), 'rec_overdue').length, 0);
});

test('rule 3: unreconciled difference; a balanced rec is not flagged', () => {
  const recs = [
    {id: 1, account_hash: 'A', period_end: '2026-04-30', statement_balance: 510000, outstanding_checks: 40000, deposits_in_transit: 5000, book_balance: 475000, reconciled_on: '2026-05-10', approved_by: 'x'},
    {id: 2, account_hash: 'A', period_end: '2026-03-31', statement_balance: 500000, outstanding_checks: 30000, deposits_in_transit: 0, book_balance: 468000, reconciled_on: '2026-04-10', approved_by: 'x'},
  ];
  const f = only(run({bankRecs: recs}), 'rec_difference');
  assert.equal(f.length, 1);
  assert.equal(f[0].amount_at_risk, 2000);
  assert.equal(f[0].severity, 'urgent');
});

test('rule 4: a check not cleared after 180 days; cleared ones and voids are not flagged', () => {
  const d = [pay('2025-10-05', 'Acme', 7000, {doc_no: '50101'}), pay('2025-10-06', 'Beta', 900, {doc_no: '50102'}),
             pay('2025-10-07', 'Gamma', 400, {doc_no: '50103', is_void: true}), pay('2025-10-08', 'Delta', 1234.56, {doc_no: '50104'})];
  const bank = [{id: 1, posted_on: '2025-10-01', amount: 10}, {id: 2, posted_on: '2025-10-20', amount: -900, check_no: '50102'},
                {id: 3, posted_on: '2025-10-21', amount: -1234.56}, {id: 4, posted_on: '2026-05-31', amount: 5}];
  const f = only(run({disbursements: d, bankTxns: bank}), 'stale_check');
  assert.deepEqual(f.map(x => x.facts.doc_no), ['50101']);
  assert.equal(f[0].severity, 'review');
});

test('rules 5 and 6 work per department: over budget, unbudgeted, burn rate; revenue lines ignored', () => {
  const b = (department, account, description, budget, actual, enc = 0) => ({id: nextId++, fiscal_year: 2026, as_of: '2026-03-31', department, account, description, amended_budget: budget, actual_ytd: actual, encumbered: enc});
  const f = run({budget: [
    b('Fleet', '001-0590-552.10', 'Fuel', 80000, 70000, 15000),          // department over by 5,000 with encumbrance
    b('Police', '001-0521-512.12', 'Salaries', 1200000, 600000),         // on pace
    b('IT', '001-0516-545.00', 'Licenses', 100000, 90000),               // 90% used at 50% of the year
    b('Grants', '001-0599-549.00', 'Misc', 0, 12000),                    // unbudgeted department
    b('Revenue', '001-0000-311.10', 'Ad valorem taxes', 5000000, 6000000), // revenue: collected more, not overspent
  ]});
  const over = only(f, 'over_budget');
  assert.deepEqual(over.map(x => x.amount_at_risk).sort((a, c) => a - c), [5000, 12000]);
  assert.ok(over.find(x => x.title.startsWith('Fleet')).detail.includes('Fuel ($5,000 over)'));
  const burn = only(f, 'burn_rate');
  assert.equal(burn.length, 1);
  assert.ok(burn[0].title.startsWith('IT:'));
});

test('a line over budget inside a department that is within budget is not flagged', () => {
  const b = (description, budget, actual) => ({id: nextId++, fiscal_year: 2026, as_of: '2026-03-31', department: 'Parks', account: '001-0572', description, amended_budget: budget, actual_ytd: actual});
  const f = run({budget: [b('Supplies', 10000, 14000), b('Salaries', 400000, 190000)]});
  assert.equal(only(f, 'over_budget').length, 0);
});

test('budget rules only read the latest snapshot of each fiscal year', () => {
  const l = (as_of, actual) => ({id: nextId++, fiscal_year: 2026, as_of, description: 'Fuel', account: '552', amended_budget: 1000, actual_ytd: actual});
  const f = only(run({budget: [l('2026-01-31', 5000), l('2026-03-31', 400)]}), 'over_budget');
  assert.equal(f.length, 0);
});

test('isRevenue uses type, then Florida UAS 3xx codes', () => {
  assert.equal(isRevenue({type: 'Revenue'}), true);
  assert.equal(isRevenue({account: '001-0000-311.10'}), true);
  assert.equal(isRevenue({account: '001-0521-552.10'}), false);
  assert.equal(isRevenue({account: '001-0310-512.12'}), false);
});

test('rule 7: same payee and amount within 30 days; same invoice twice is urgent; voided pair is not', () => {
  const f = only(run({disbursements: [
    pay('2026-01-05', 'Acme', 2500), pay('2026-01-20', 'Acme', 2500),
    pay('2026-02-01', 'Beta', 800, {invoice_no: 'B-1'}), pay('2026-02-20', 'Beta', 750, {invoice_no: 'b-1'}),
    pay('2026-03-01', 'Gamma', 600, {doc_no: '700'}), pay('2026-03-02', 'Gamma', 600, {doc_no: '701', is_void: true}),
    pay('2026-01-05', 'Delta', 2500), pay('2026-03-20', 'Delta', 2500),
  ]}), 'duplicate_payment');
  assert.equal(f.length, 2);
  assert.equal(f.find(x => x.facts.same_invoice).severity, 'urgent');
});

test('rule 8: payments under the bid threshold that add up past it within 14 days', () => {
  const f = only(run({disbursements: [pay('2026-02-02', 'Paving Co', 30000), pay('2026-02-09', 'Paving Co', 29000), pay('2026-04-01', 'Paving Co', 20000)]}), 'split_purchase');
  const bid = f.find(x => x.facts.threshold === 35000);
  assert.equal(bid.facts.count, 2);
  assert.equal(bid.amount_at_risk, 59000);
  assert.equal(bid.severity, 'review');
});

test('rule 9: round amounts and weekend or holiday dates', () => {
  const f = only(run({disbursements: [pay('2026-03-04', 'A', 10000), pay('2026-03-07', 'B', 1500.25), pay('2026-07-03', 'C', 2000.5), pay('2026-03-04', 'D', 1234.5)]}), 'round_or_weekend');
  assert.equal(f.length, 3);
  assert.ok(f.some(x => /Saturday/.test(x.title)));
  assert.ok(f.some(x => /holiday/.test(x.title)), 'July 3, 2026 is the observed Independence Day');
});

test('federal holidays include observed dates', () => {
  const h = holidays(2026);
  assert.ok(h.has('2026-07-03'));
  assert.ok(h.has('2026-11-26'));
  assert.ok(h.has('2026-01-19'));
});

test('rule 10: a vendor month 3x its median; a large first payment is info', () => {
  const d = [];
  for (const m of ['2025-10', '2025-11', '2025-12', '2026-01', '2026-02', '2026-03']) d.push(pay(`${m}-15`, 'Water Co', 2000));
  d.push(pay('2026-04-15', 'Water Co', 9000));
  d.push(pay('2026-04-20', 'New Vendor LLC', 30000.01));
  const f = only(run({disbursements: d}), 'payee_spike');
  assert.equal(f.find(x => x.facts.payee === 'Water Co').amount_at_risk, 7000);
  assert.equal(f.find(x => x.facts.payee === 'New Vendor LLC').severity, 'info');
});

test('rule 16: repeat reconciliation finding is review until three clean months of recs', () => {
  const findings = [{id: 1, topic: 'reconciliation', fiscal_year: 2025, finding_id: '2025-001', title: 'Reconciliation', repeat: true},
                    {id: 2, topic: 'reconciliation', fiscal_year: 2024, finding_id: '2024-001', title: 'Reconciliation', repeat: true}];
  const open = only(run({findings}), 'audit_repeat');
  assert.equal(open.length, 1);
  assert.equal(open[0].severity, 'review');
  assert.deepEqual(open[0].facts.years, [2024, 2025]);
  const rec = (pe, on) => ({id: nextId++, account_hash: 'A', period_end: pe, statement_balance: 1, book_balance: 1, reconciled_on: on, approved_by: 'K'});
  const clean = only(run({findings, bankRecs: [rec('2026-03-31', '2026-04-10'), rec('2026-04-30', '2026-05-12'), rec('2026-05-31', '2026-06-10')]}), 'audit_repeat');
  assert.equal(clean[0].severity, 'info');
});

test('flags are ranked by dollars times severity and fingerprints are stable', () => {
  const data = {disbursements: [pay('2026-01-05', 'Acme', 2500, {id: 1, doc_no: '1'}), pay('2026-01-20', 'Acme', 2500, {id: 2, doc_no: '2'})],
                uploads: [{id: 3, original_name: 'x', tie_status: 'mismatch', tie_difference: 50000, status: 'held'}]};
  const a = run(data), b = run(data);
  assert.equal(a[0].rule, 'file_tie');
  assert.deepEqual(a.map(f => f.fingerprint), b.map(f => f.fingerprint));
});
