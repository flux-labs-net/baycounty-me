// Tests for the finance import engine: parsing, shape detection, column mapping, normalization and tie-out.
const test = require('node:test');
const assert = require('node:assert/strict');
const {parseCsv, readGrid} = require('../_finance/parse');
const {detect} = require('../_finance/detect');
const {money, date, payeeKey, maskAccount, normalize, fiscalYear} = require('../_finance/normalize');

const run = (csv, opts = {}) => {
  const rows = parseCsv(csv), det = detect(rows, opts);
  return {det, ...normalize(det.shape, rows, det, opts)};
};

test('money handles the formats accounting exports use', () => {
  assert.equal(money('$1,234.56'), 1234.56);
  assert.equal(money('(1,234.56)'), -1234.56);
  assert.equal(money('1,234.56-'), -1234.56);
  assert.equal(money('-$20.00'), -20);
  assert.equal(money('-'), null);
  assert.equal(money(''), null);
  assert.equal(money('n/a'), null);
  assert.equal(money(19.999), 20);
});

test('dates: US, ISO, Excel serial, month names, impossible dates', () => {
  assert.equal(date('9/30/2026'), '2026-09-30');
  assert.equal(date('09/30/26'), '2026-09-30');
  assert.equal(date('2026-10-01'), '2026-10-01');
  assert.equal(date(46295), '2026-09-30');
  assert.equal(date('Sep 30, 2026'), '2026-09-30');
  assert.equal(date('September 2026'), '2026-09-30');
  assert.equal(date('2/30/2026'), null);
  assert.equal(date(new Date(Date.UTC(2026, 0, 5))), '2026-01-05');
});

test('fiscal year starts in October', () => {
  assert.equal(fiscalYear('2025-10-01'), 2026);
  assert.equal(fiscalYear('2026-09-30'), 2026);
});

test('payee keys merge spelling variants', () => {
  assert.equal(payeeKey('Roberts & Roberts, Inc.'), payeeKey('ROBERTS AND ROBERTS INC'));
  assert.equal(payeeKey('Gulf Power Company'), 'GULF POWER');
});

test('bank account numbers are masked and hashed, never kept', () => {
  const a = maskAccount('000123456789'), b = maskAccount('0001-2345-6789');
  assert.equal(a.label, '…6789');
  assert.equal(a.hash, b.hash);
  assert.ok(!JSON.stringify(a).includes('123456'));
});

test('CSV parser: quotes, embedded commas and newlines, BOM, tabs', () => {
  assert.deepEqual(parseCsv('﻿a,b\n"x, y","he said ""hi"""\n'), [['a', 'b'], ['x, y', 'he said "hi"']]);
  assert.deepEqual(parseCsv('a\tb\n1\t2'), [['a', 'b'], ['1', '2']]);
  assert.deepEqual(parseCsv('a,b\n"line1\nline2",2\n\n'), [['a', 'b'], ['line1\nline2', '2']]);
});

const REGISTER = `City of Lynn Haven
Check Register 10/01/2025 - 10/31/2025
Check Date,Check #,Vendor Name,Invoice No,Amount,Status
10/02/2025,50101,Gulf Power Company,INV-1,"$12,500.00",
10/03/2025,50102,Total Pest Control LLC,TP-9,350.00,
10/09/2025,50103,ACME Paving Inc.,A-77,"$34,000.00",
10/10/2025,50104,ACME Paving Inc.,A-78,"$33,500.00",Voided
,,,Report Total:,"$80,350.00",
`;

test('check register: header found under title lines, vendor named Total is a payment, ties to report total', () => {
  const r = run(REGISTER);
  assert.equal(r.det.shape, 'disbursements');
  assert.equal(r.det.headerIndex, 2);
  assert.equal(r.records.length, 4);
  assert.equal(r.records[1].payee, 'Total Pest Control LLC');
  assert.equal(r.records[3].is_void, true);
  assert.equal(r.records[0].method, 'check');
  assert.equal(r.printedTotal, 80350);
  assert.equal(r.tie.status, 'ties');
  assert.equal(r.periodStart, '2025-10-02');
  assert.equal(r.periodEnd, '2025-10-10');
});

test('register whose total does not match is a mismatch with the difference', () => {
  const r = run(REGISTER.replace('$80,350.00', '$80,450.00'));
  assert.equal(r.tie.status, 'mismatch');
  assert.equal(r.tie.difference, -100);
});

test('a control total from the user overrides the file', () => {
  const r = run(REGISTER.replace(/,,,Report Total.*\n/, ''), {printedTotal: '80,350.00'});
  assert.equal(r.tie.status, 'ties');
  const n = run(REGISTER.replace(/,,,Report Total.*\n/, ''));
  assert.equal(n.tie.status, 'no_total');
});

const BUDGET = `Budget vs Actual - Period ending 03/31/2026
Fund,Department,Account,Description,Original Budget,Amended Budget,YTD Actual,Encumbrances
General,Police,001-0521-512.12,Regular Salaries,"1,200,000.00","1,200,000.00","610,000.00",0
General,Police,001-0521-552.10,Fuel,"80,000.00","80,000.00","70,000.00","5,000.00"
General,Police,,Total Police,"1,280,000.00","1,280,000.00","680,000.00","5,000.00"
General,Parks,001-0572-546.30,Repairs,"40,000.00","40,000.00","45,000.00",0
General,Parks,,Total Parks,"40,000.00","40,000.00","45,000.00",0
,,,Grand Total,"1,320,000.00","1,320,000.00","725,000.00","5,000.00"
`;

test('budget vs actual: subtotal lines dropped, grand total ties on the actual column', () => {
  const r = run(BUDGET);
  assert.equal(r.det.shape, 'budget');
  assert.equal(r.records.length, 3);
  assert.equal(r.records[1].encumbered, 5000);
  assert.equal(r.printedTotal, 725000);
  assert.equal(r.tie.status, 'ties');
});

test('budget with only subtotals and a miss is reported as untied, not held', () => {
  const r = run(BUDGET.replace(/,,,Grand Total.*\n/, '').replace('"45,000.00",0\nGeneral,Parks,,Total', '"45,000.00",0\nGeneral,Parks,,Total'), {});
  assert.notEqual(r.tie.status, 'mismatch');
});

const BANK = `Account,Posting Date,Description,Debit,Credit,Check Number
000123456789,10/03/2025,CHECK 50101,12500.00,,50101
000123456789,10/05/2025,DEPOSIT,,"20,000.00",
000123456789,10/12/2025,ACH GULF COAST UTILITIES,1200.00,,
`;

test('bank statement: debit/credit columns become a signed amount; account is masked', () => {
  const r = run(BANK);
  assert.equal(r.det.shape, 'bank_transactions');
  assert.deepEqual(r.records.map(x => x.amount), [-12500, 20000, -1200]);
  assert.equal(r.records[0].check_no, '50101');
  assert.equal(r.records[0].account_label, '…6789');
  assert.ok(!JSON.stringify(r.records).includes('000123456789'));
});

const RECS = `Bank Account,Statement Date,Statement Balance,Outstanding Checks,Deposits in Transit,Book Balance,Date Reconciled,Prepared By,Reviewed By
Operating 4455,10/31/2025,"510,000.00","40,000.00","5,000.00","475,000.00",11/20/2025,J. Smith,K. Lee
Operating 4455,11/30/2025,"500,000.00","30,000.00",0,"468,000.00",,J. Smith,
`;

test('bank rec summary maps balances and dates', () => {
  const r = run(RECS);
  assert.equal(r.det.shape, 'bank_recs');
  assert.equal(r.records.length, 2);
  assert.equal(r.records[0].reconciled_on, '2025-11-20');
  assert.equal(r.records[1].reconciled_on, null);
  assert.equal(r.records[0].approved_by, 'K. Lee');
});

test('a forced shape and a manual column mapping win over detection', () => {
  const rows = parseCsv('When,Who,How much\n10/1/2025,Acme,100\n');
  const auto = detect(rows);
  assert.equal(auto.ok, false);
  const det = detect(rows, {shape: 'disbursements', mapping: {paid_on: 'When', payee: 'Who', amount: 'How much'}});
  assert.equal(det.ok, true);
  const out = normalize('disbursements', rows, det);
  assert.equal(out.records[0].amount, 100);
});

test('Excel workbook round trip with real dates and numbers', async () => {
  const ExcelJS = require('exceljs');
  const wb = new ExcelJS.Workbook(), ws = wb.addWorksheet('Register');
  ws.addRow(['Lynn Haven check register']);
  ws.addRow(['Check Date', 'Check No', 'Payee', 'Amount']);
  ws.addRow([new Date(Date.UTC(2025, 9, 2)), 50101, 'Gulf Power', 12500]);
  ws.addRow([new Date(Date.UTC(2025, 9, 3)), 50102, 'Acme', {formula: '100+250', result: 350}]);
  ws.addRow(['', '', 'Grand Total', 12850]);
  const buf = Buffer.from(await wb.xlsx.writeBuffer());
  const grid = await readGrid('register.xlsx', buf);
  const det = detect(grid.rows), out = normalize(det.shape, grid.rows, det);
  assert.equal(det.shape, 'disbursements');
  assert.equal(out.records[0].paid_on, '2025-10-02');
  assert.equal(out.records[0].doc_no, '50101');
  assert.equal(out.records[1].amount, 350);
  assert.equal(out.tie.status, 'ties');
});

test('PDF and old .xls get a clear message', async () => {
  await assert.rejects(readGrid('x.pdf', Buffer.from('%PDF-1.4')), /PDF uploads/);
  await assert.rejects(readGrid('x.xls', Buffer.from([0xd0, 0xcf, 0x11])), /save as \.xlsx/);
});
