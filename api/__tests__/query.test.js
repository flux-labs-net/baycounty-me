// Tests for api/_query.js (filters, operators, aggregation, CSV) and v1 helpers. Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const {filterRows, toCsv, csvCell, aggregate} = require('../_query');

const rows = [
  {id: 1, gov: 'Lynn Haven', vendor: 'ACME', amount: 500, date: '2026-01-05', note: 'paving'},
  {id: 2, gov: 'Lynn Haven', vendor: 'Beta', amount: null, date: '', note: null},
  {id: 3, gov: 'Panama City', vendor: 'ACME', amount: 1500, date: '2026-03-01', note: ''},
  {id: 4, gov: 'Callaway', vendor: 'Gamma', amount: '250', date: '2025-12-31', note: 'amount pending'},
];
const ids = q => filterRows(rows, q).map(r => r.id);

test('null and blank values never match ranges', () => {
  assert.deepEqual(ids({amount_min: '0'}), [1, 3, 4]);
  assert.deepEqual(ids({amount_max: '1000'}), [1, 4]);
  assert.deepEqual(ids({date_from: '2026-01-01'}), [1, 3]);
  assert.deepEqual(ids({date_to: '2026-12-31'}), [1, 3, 4]);
  assert.deepEqual(ids({amount_min: 'abc'}), [], 'non-numeric bound matches nothing');
});

test('equality, OR lists and contains', () => {
  assert.deepEqual(ids({gov: 'lynn haven'}), [1, 2]);
  assert.deepEqual(ids({gov: 'Callaway,Panama City'}), [3, 4]);
  assert.deepEqual(ids({vendor_contains: 'cm'}), [1, 3]);
  assert.deepEqual(ids({nope: 'x'}), [], 'unknown column matches nothing');
});

test('_ne excludes values; blanks count as not equal', () => {
  assert.deepEqual(ids({vendor_ne: 'acme'}), [2, 4]);
  assert.deepEqual(ids({gov_ne: 'Lynn Haven,Callaway'}), [3]);
  assert.deepEqual(ids({note_ne: 'paving'}), [2, 3, 4]);
});

test('_null=true/false', () => {
  assert.deepEqual(ids({amount_null: 'true'}), [2]);
  assert.deepEqual(ids({amount_null: 'false'}), [1, 3, 4]);
  assert.deepEqual(ids({note_null: 'true'}), [2, 3], 'empty string is blank');
  assert.deepEqual(ids({note_null: 'maybe'}), [1, 2, 3, 4], 'other values ignored');
});

test('a real column ending in an operator suffix is matched as a column', () => {
  const r = [{amount_min: 5, x: 1}, {amount_min: 6, x: 2}];
  assert.deepEqual(filterRows(r, {amount_min: '6'}).map(x => x.x), [2]);
});

test('q searches values, not keys; sort puts nulls last', () => {
  assert.deepEqual(ids({q: 'amount'}), [4]);
  assert.deepEqual(ids({sort: '-amount'}), [3, 1, 4, 2]);
  assert.equal(filterRows(rows, {sort: 'amount'}).pop().id, 2);
});

test('group_by with count and sum (non-numeric skipped)', () => {
  const g = aggregate(rows, 'gov', 'amount', Object.keys(rows[0]));
  assert.deepEqual(g[0], {gov: 'Lynn Haven', count: 2, sum_amount: 500, n_amount: 1});
  assert.deepEqual(g.find(x => x.gov === 'Callaway'), {gov: 'Callaway', count: 1, sum_amount: 250, n_amount: 1});
  const two = aggregate(rows, 'gov,vendor', '', Object.keys(rows[0]));
  assert.equal(two.length, 4);
  assert.ok(!('sum_' in two[0]));
  assert.throws(() => aggregate(rows, 'bogus', '', Object.keys(rows[0])), e => e.status === 400 && /bogus/.test(e.message));
  assert.throws(() => aggregate(rows, 'gov', 'bogus', Object.keys(rows[0])), e => e.status === 400);
  assert.deepEqual(aggregate([{a: 0.1, g: 'x'}, {a: 0.2, g: 'x'}], 'g', 'a', ['a', 'g'])[0].sum_a, 0.3, 'rounded to cents');
});

test('CSV escaping and formula guard', () => {
  assert.equal(csvCell('=SUM(A1)'), "'=SUM(A1)");
  assert.equal(csvCell('+1'), "'+1");
  assert.equal(csvCell('-x'), "'-x");
  assert.equal(csvCell('@cmd'), "'@cmd");
  assert.equal(csvCell('\tx'), "'\tx");
  assert.equal(csvCell(-5), '-5', 'real negative numbers are left alone');
  assert.equal(csvCell(NaN), '');
  assert.equal(csvCell(null), '');
  assert.equal(csvCell('a,b'), '"a,b"');
  assert.equal(csvCell('say "hi"'), '"say ""hi"""');
  assert.equal(csvCell('line\nbreak'), '"line\nbreak"');
  assert.equal(csvCell(['a', 'b']), 'a; b');
  assert.equal(csvCell({k: 1}), '"{""k"":1}"');
  const csv = toCsv([{a: 1, b: 'x'}, {a: 2, c: '=1'}]);
  assert.equal(csv, "a,b,c\n1,x,\n2,,'=1\n");
  assert.equal(toCsv([]), '');
});

test('v1 meetings.ics filters by government and folds long lines', () => {
  const v1 = require('../v1');
  const ics = v1.meetingsIcs([
    {board: 'lh', title: 'City Commission', start: '2026-11-10T17:30:00-06:00', location: '825 Ohio Ave., Lynn Haven', agenda_url: 'https://x/a'},
    {board: 'lh-cra', title: 'CRA', start: '2026-11-11'},
    {board: 'pc', title: 'Commission', start: '2026-11-12T08:00:00-06:00'},
    {board: 'lh', title: 'Old', start: '2026-10-01T17:30:00-05:00', past: true},
  ], 'lh');
  assert.equal((ics.match(/BEGIN:VEVENT/g) || []).length, 2);
  assert.match(ics, /DTSTART:20261110T233000Z/);
  assert.match(ics, /DTSTART;VALUE=DATE:20261111/);
  assert.match(ics, /SUMMARY:Lynn Haven: City Commission/);
  assert.match(ics, /825 Ohio Ave\.\\, Lynn Haven/);
  assert.ok(ics.split('\r\n').every(l => l.length <= 75));
  assert.equal((v1.meetingsIcs([{board: 'pc', title: 'x', start: '2026-11-12'}], 'lh-cra').match(/BEGIN:VEVENT/g) || []).length, 0);
});
