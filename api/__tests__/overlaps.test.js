// api/_overlaps.js: the live overlap joins (pure parts).
const test = require('node:test');
const assert = require('node:assert');
const O = require('../_overlaps');

test('payments just under a threshold within 30 days are grouped', () => {
  const p = (d, amt, payee = 'ACME PAVING') => ({gov_id: 'lh', government: 'Lynn Haven', payee, payee_entity_id: null, amount: amt, paid_on: d, doc_no: d});
  const rows = O.splitPurchases([p('2026-01-02', 24500), p('2026-01-20', 23990), p('2026-03-30', 24800), p('2026-01-05', 26000), p('2026-01-06', 9500, 'OTHER CO')]);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].threshold, 25000);
  assert.equal(rows[0].payments, 2);
  assert.equal(rows[0].total, 48490);
  assert.deepEqual(rows[0].items.map(i => i.paid_on), ['2026-01-02', '2026-01-20']);
});

test('one payment under a threshold is not a run', () => {
  assert.equal(O.splitPurchases([{gov_id: 'pc', payee: 'X', amount: 49999, paid_on: '2026-02-01'}]).length, 0);
});

test('a member vote is read from the roll call by last name', () => {
  const roll = 'Paul Casto: yes; Mary Coburn: no; Ethan Register: absent';
  assert.equal(O.voteOf(roll, 'Mary Coburn'), 'no');
  assert.equal(O.voteOf(roll, 'Ethan Register'), 'absent');
  assert.equal(O.voteOf(roll, 'Somebody Else'), null);
});

test('company names compare without legal endings', () => {
  assert.equal(O.words('Panhandle Engineering, Inc.'), O.words('PANHANDLE ENGINEERING'));
  assert.notEqual(O.words('Panhandle Engineering'), O.words('Panhandle Paving'));
});

test('an unknown section is a 400', async () => {
  await assert.rejects(O.overlaps({section: 'nope'}).catch(e => { throw e; }), e => e.status === 400 || /Unknown section/.test(e.message));
});
