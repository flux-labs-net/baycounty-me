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

test('limit review: statuses, case ids, resolution and source link are checked', () => {
  assert.throws(() => R.cleanLimitReview({case_id: 'l_0123456789', status: 'published'}), /Unknown review status/);
  assert.throws(() => R.cleanLimitReview({case_id: 'g_0123456789', status: 'confirmed'}), /Unknown case/);
  assert.throws(() => R.cleanLimitReview({case_id: 'l_0123456789', status: 'resolved'}), /how it was resolved/);
  assert.throws(() => R.cleanLimitReview({case_id: 'l_0123456789', status: 'resolved', resolution: 'refunded', resolution_url: 'javascript:alert(1)'}), /http/);
  const ok = R.cleanLimitReview({case_id: 'l_0123456789', status: 'resolved', resolution: 'amended_report', resolution_note: ' SOE typo ', resolution_url: 'https://example.org/r.pdf'});
  assert.deepEqual(ok, {county: 'bay', status: 'resolved', id: 'l_0123456789', resolution: 'amended_report', note: 'SOE typo', url: 'https://example.org/r.pdf'});
  // a resolution is only stored with a resolved status
  assert.equal(R.cleanLimitReview({case_id: 'l_0123456789', status: 'confirmed', resolution: 'refunded'}).resolution, null);
});

test('limit review rewrites the public row for that case', async () => {
  reply = sql => sql.includes('update registry.limit_cases') ? [{case_id: 'l_0123456789', review_status: 'confirmed'}] : [{n: 1}];
  calls.length = 0;
  const r = await R.reviewLimit({case_id: 'l_0123456789', status: 'confirmed'}, 'a@x');
  assert.equal(r.published, 1);
  const pub = calls.find(c => c.sql.includes('registry.publish_limit_case'));
  assert.deepEqual(pub.p, ['bay', 'l_0123456789']);
});
