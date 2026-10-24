// Tests for the private business registry on /admin (api/_registry.js). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const dbPath = path.join(__dirname, '..', '_db.js');
const calls = [];
let reply = () => [];
require.cache[dbPath] = {id: dbPath, filename: dbPath, loaded: true, exports: {q: async (sql, p) => { calls.push({sql, p}); return reply(sql, p); }, hasDb: () => true}};
const R = require('../_registry');

test('county keys are checked, default bay', () => {
  assert.equal(R.cleanCounty('Bay'), 'bay');
  assert.equal(R.cleanCounty('okaloosa'), 'okaloosa');
  assert.equal(R.cleanCounty("bay'; drop"), 'bay');
  assert.equal(R.cleanCounty(undefined), 'bay');
});

test('search text: document numbers vs names', () => {
  assert.deepEqual(R.cleanQuery('l12000012345'), {kind: 'doc', term: 'L12000012345'});
  assert.deepEqual(R.cleanQuery("  O'Brien,  pat "), {kind: 'name', term: 'O BRIEN PAT', words: ['O', 'BRIEN', 'PAT']});
  assert.throws(() => R.cleanQuery('ab'), /at least 3/);
  assert.throws(() => R.cleanQuery('%%%'), /name or a Sunbiz/);
});

test('search runs parameterized queries in both name orders', async () => {
  calls.length = 0;
  reply = () => [];
  await R.search('bay', 'john smith');
  const people = calls.find(c => c.sql.includes('from registry.people'));
  assert.deepEqual(people.p, ['bay', 'JOHN SMITH%', 'SMITH JOHN%']);
});

test('review: only known statuses and group ids', async () => {
  await assert.rejects(R.review({group_id: 'g_0123456789', status: 'published'}, 'a@x'), /Unknown review status/);
  await assert.rejects(R.review({group_id: 'x', status: 'confirmed'}, 'a@x'), /Unknown group/);
  reply = () => [{group_id: 'g_0123456789', candidate: 'A', review_status: 'confirmed'}];
  calls.length = 0;
  const r = await R.review({group_id: 'g_0123456789', candidate: 'A', status: 'confirmed'}, 'a@x');
  assert.equal(r.updated, 1);
  // every review rewrites the public rows for that group (published if confirmed, removed otherwise)
  const pub = calls.find(c => c.sql.includes('registry.publish_group'));
  assert.deepEqual(pub.p, ['bay', 'g_0123456789', 'A']);
});

test('person and entity lookups reject malformed ids before touching the database', async () => {
  calls.length = 0;
  await assert.rejects(R.person('bay', 'p_123'), /Unknown person/);
  await assert.rejects(R.entity('bay', 'bad doc!'), /Unknown document/);
  assert.equal(calls.length, 0);
});
