// Who held each elected seat in a year (api/_officials.js, GET /api/v1/officials). Run: npm test
// Reads the published officeholder-terms rows, so it needs a site build (python3 site/build_site.py).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const O = require('../_officials');

const rows = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', 'site', 'public', 'downloads', 'officeholder-terms.json'), 'utf8'));
const names = (r, seat) => r.seats.find(s => s.seat === seat).holders.map(h => h.person_name);

test('fiscal years run Oct to Sep, schools Jul to Jun', () => {
  assert.deepEqual(O.fyWindow('lh', 2026), {from: '2025-10-01', to: '2026-09-30'});
  assert.deepEqual(O.fyWindow('schools', 2020), {from: '2019-07-01', to: '2020-06-30'});
});

test('a year shows that year\'s commission, not today\'s', () => {
  const r = O.inOffice(rows, {gov: 'lh', year: 2016});
  assert.deepEqual(names(r, 'Mayor'), ['Margo Anderson']);
  assert.deepEqual(names(r, 'Seat 4'), ['Joseph Ashbrook']);
});

test('a seat that changed hands lists everyone, and a gap stays unconfirmed', () => {
  const r = O.inOffice(rows, {gov: 'lh', year: 2021});
  assert.deepEqual(names(r, 'Mayor'), [null, 'Jesse Nelson']);
  assert.equal(r.seats.find(s => s.seat === 'Mayor').holders[0].vacant, true);
  const sd = O.inOffice(rows, {gov: 'schools', year: 2020}).seats.find(s => s.seat === 'District 2').holders;
  assert.equal(sd[1].confirmed, false);
  assert.ok(r.seats.find(s => s.seat === 'Mayor').holders.every(h => h.part_of_period));
});

test('a date picks one holder per seat, and the term ends the day the next begins', () => {
  assert.deepEqual(names(O.inOffice(rows, {gov: 'lh', date: '2019-04-16'}), 'Seat 1'), ['Brandon Aldridge']);
  assert.deepEqual(names(O.inOffice(rows, {gov: 'lh', date: '2019-04-15'}), 'Seat 1'), ['Rodney Friend']);
});

test('every term is in order within its seat, and every name has a profile id', () => {
  const by = {};
  for (const r of rows) (by[r.gov_id + '|' + r.seat] ||= []).push(r);
  for (const [k, ts] of Object.entries(by)) {
    ts.sort((a, b) => a.term_order - b.term_order);
    ts.slice(1).forEach((t, i) => assert.ok(ts[i].end_date && t.start_date >= ts[i].end_date, k));
  }
  assert.ok(rows.filter(r => r.person_name).every(r => r.person_id), 'a named holder without a person_id');
  assert.ok(new Set(rows.map(r => r.gov_id)).size >= 9);
});

test('bad input gets a clear error', () => {
  assert.throws(() => O.inOffice(rows, {}), /gov=/);
  assert.throws(() => O.inOffice(rows, {gov: 'nowhere'}), e => e.status === 404);
  assert.throws(() => O.inOffice(rows, {gov: 'lh', date: '2019'}), /YYYY-MM-DD/);
});
