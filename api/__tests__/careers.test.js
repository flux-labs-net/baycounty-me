// Tests for officials' business ties on /admin (api/_careers.js). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const dbPath = path.join(__dirname, '..', '_db.js');
const calls = [];
let reply = () => [];
require.cache[dbPath] = {id: dbPath, filename: dbPath, loaded: true, exports: {q: async (sql, p) => { calls.push({sql, p}); return reply(sql, p); }, hasDb: () => true}};
const C = require('../_careers');

test('review pairs: one or many, ids checked', () => {
  assert.deepEqual(C.cleanPairs({person_id: 'allan-branch', person_key: 'p_0123456789ab'}), [{person_id: 'allan-branch', person_key: 'p_0123456789ab'}]);
  assert.equal(C.cleanPairs({pairs: [{person_id: 'a-b', person_key: 'p_0123456789ab'}, {person_id: 'c-d', person_key: 'p_ba9876543210'}]}).length, 2);
  assert.throws(() => C.cleanPairs({person_id: 'x', person_key: 'p_0123456789ab'}), /Unknown match/);
  assert.throws(() => C.cleanPairs({person_id: 'a-b', person_key: "p_1'; drop"}), /Unknown match/);
  assert.throws(() => C.cleanPairs({pairs: []}), /1 to 500/);
});

test('review: only known statuses; publishes after an update', async () => {
  await assert.rejects(C.review({person_id: 'a-b', person_key: 'p_0123456789ab', status: 'published'}, 'a@x'), /Unknown review status/);
  calls.length = 0;
  reply = sql => sql.includes('update careers.matches') ? [{person_id: 'a-b', person_key: 'p_0123456789ab', review_status: 'confirmed'}] : [{n: 3}];
  const r = await C.review({county: 'bay', person_id: 'a-b', person_key: 'p_0123456789ab', status: 'confirmed'}, 'a@x');
  assert.equal(r.updated, 1);
  assert.equal(r.published, 3);
  assert.ok(calls.some(c => c.sql.includes('careers.publish')));
  const upd = calls.find(c => c.sql.includes('update careers.matches'));
  assert.deepEqual(upd.p.slice(0, 3), ['confirmed', 'a@x', 'bay']);
});

test('review: nothing matched is a 404 and publishes nothing', async () => {
  calls.length = 0;
  reply = () => [];
  await assert.rejects(C.review({person_id: 'a-b', person_key: 'p_0123456789ab', status: 'rejected'}, 'a@x'), /Unknown match/);
  assert.ok(!calls.some(c => c.sql.includes('careers.publish')));
});

test('match list filters are parameterized', async () => {
  calls.length = 0;
  reply = () => [];
  await C.matches({county: 'bay', status: 'unreviewed', confidence: 'high', q: "O'Neal"});
  const m = calls.find(c => c.sql.includes('from careers.matches m'));
  assert.deepEqual(m.p, ['bay', 'unreviewed', 'high', "%o'neal%"]);
  calls.length = 0;
  await C.matches({county: 'bay', status: 'drop table', confidence: 'x'});
  assert.deepEqual(calls.find(c => c.sql.includes('from careers.matches m')).p, ['bay']);
});
