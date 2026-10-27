// Tests for look-alike business names on /admin (api/_name_matches.js). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const dbPath = path.join(__dirname, '..', '_db.js');
const calls = [];
let reply = () => [];
require.cache[dbPath] = {id: dbPath, filename: dbPath, loaded: true, exports: {q: async (sql, p) => { calls.push({sql, p}); return reply(sql, p); }, hasDb: () => true}};
const N = require('../_name_matches');

const PAIRS = [
  {a: {key: 'emeraldcoaststriping', names: ['Emerald Coast Striping']}, b: {key: 'emeralcoaststriping', names: ['Emeral Coast Striping LLC'], gifts: 1, given: 500}, reason: 'spelling'},
  {a: {key: 'gaccontractor', names: ['GAC Contractor']}, b: {key: 'gaccontractors', names: ['GAC Contractors'], vendor_id: 'gac-contractors'}, reason: 'plural'},
];

test('pairs are stored in sorted key order, one or many, keys checked', () => {
  assert.deepEqual(N.cleanPairs({a_key: 'zeta1', b_key: 'alpha1', a_name: 'Zeta', b_name: 'Alpha'}), [{a_key: 'alpha1', b_key: 'zeta1', a_name: 'Alpha', b_name: 'Zeta'}]);
  assert.equal(N.cleanPairs({items: [{a_key: 'abc', b_key: 'abd'}, {a_key: 'abd', b_key: 'abc'}]}).length, 1);
  assert.throws(() => N.cleanPairs({a_key: 'abc', b_key: 'abc'}), /Unknown name pair/);
  assert.throws(() => N.cleanPairs({a_key: "a'; drop", b_key: 'abc'}), /Unknown name pair/);
  assert.throws(() => N.cleanPairs({items: []}), /1 to 500/);
});

test('merge: calls attach to candidate pairs either way round; filters work', () => {
  const calls = [{a_key: 'emeralcoaststriping', b_key: 'emeraldcoaststriping', status: 'confirmed', reviewed_by: 'x@y'}];
  const all = N.merge(PAIRS, calls, {status: ''});
  assert.equal(all.length, 2);
  assert.equal(all[0].a_key, 'emeralcoaststriping');
  assert.equal(all[0].a.names[0], 'Emeral Coast Striping LLC');
  assert.equal(all[0].review_status, 'confirmed');
  assert.equal(N.merge(PAIRS, calls).length, 1);  // unreviewed by default
  assert.equal(N.merge(PAIRS, calls, {status: '', reason: 'plural'}).length, 1);
  assert.equal(N.merge(PAIRS, calls, {status: '', q: 'gac'}).length, 1);
});

test('merge: a call already applied by a build stays listed', () => {
  const rows = N.merge([], [{a_key: 'aaa', b_key: 'bbb', a_name: 'A', b_name: 'B', status: 'rejected'}], {status: 'rejected'});
  assert.equal(rows.length, 1);
  assert.equal(rows[0].a.names[0], 'A');
});

test('review: unknown status refused; confirm upserts; unreviewed deletes', async () => {
  await assert.rejects(N.review({status: 'maybe', a_key: 'abc', b_key: 'abd'}, 'me'), /Unknown review status/);
  calls.length = 0; reply = () => [{a_key: 'abc', b_key: 'abd', status: 'confirmed'}];
  const r = await N.review({status: 'confirmed', a_key: 'abd', b_key: 'abc'}, 'me@x');
  assert.equal(r.updated, 1);
  assert.match(calls[0].sql, /insert into name_match_reviews/);
  assert.deepEqual(JSON.parse(calls[0].p[0])[0].a_key, 'abc');
  calls.length = 0; reply = () => [];
  await N.review({status: 'unreviewed', a_key: 'abc', b_key: 'abd'}, 'me@x');
  assert.match(calls[0].sql, /delete from name_match_reviews/);
});

test('candidates: read from the build file; a missing file gives none', () => {
  assert.deepEqual(N.candidates(() => JSON.stringify({look_alike_names: PAIRS})).length, 2);
  assert.deepEqual(N.candidates(() => { throw new Error('ENOENT'); }), []);
  assert.ok(Array.isArray(N.candidates()));
});
