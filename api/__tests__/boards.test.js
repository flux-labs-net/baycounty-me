// Tests for the private nonprofit board research on /admin (api/_boards.js). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const dbPath = path.join(__dirname, '..', '_db.js');
const calls = [];
let reply = () => [];
require.cache[dbPath] = {id: dbPath, filename: dbPath, loaded: true, exports: {q: async (sql, p) => { calls.push({sql, p}); return reply(sql, p); }, hasDb: () => true}};
const B = require('../_boards');

test('review: only known statuses, board keys and official ids; every review republishes the county', async () => {
  await assert.rejects(B.review({board_key: 'b_0123456789ab', official_id: 'jane-doe', status: 'public'}, 'a@x'), /Unknown review status/);
  await assert.rejects(B.review({board_key: 'p_0123456789ab', official_id: 'jane-doe', status: 'confirmed'}, 'a@x'), /Unknown person/);
  await assert.rejects(B.review({board_key: 'b_0123456789ab', official_id: "x'; drop", status: 'confirmed'}, 'a@x'), /Unknown official/);
  reply = sql => sql.includes('publish_board_officials') ? [{n: 2}] : [{board_key: 'b_0123456789ab', official_id: 'jane-doe', review_status: 'confirmed'}];
  calls.length = 0;
  const r = await B.review({board_key: 'b_0123456789ab', official_id: 'jane-doe', status: 'confirmed'}, 'a@x');
  assert.equal(r.updated, 1);
  assert.equal(r.published, 2);
  const upd = calls.find(c => c.sql.includes('update registry.board_official_matches'));
  assert.deepEqual(upd.p, ['confirmed', 'a@x', 'bay', 'b_0123456789ab', 'jane-doe']);
  assert.deepEqual(calls.find(c => c.sql.includes('publish_board_officials')).p, ['bay']);
});

test('lookups reject malformed ids before touching the database', async () => {
  calls.length = 0;
  await assert.rejects(B.person('bay', 'b_123'), /Unknown person/);
  await assert.rejects(B.nonprofit('bay', 'np-12'), /Unknown nonprofit/);
  await assert.rejects(B.nonprofit('bay', 'np-sb-../x'), /Unknown nonprofit/);
  assert.equal(calls.length, 0);
});

test('search: EINs look up nonprofits, names search people in both orders', async () => {
  reply = () => [];
  calls.length = 0;
  await B.search('bay', '59-1234567');
  assert.ok(calls[0].sql.includes('from registry.board_seats'));
  assert.deepEqual(calls[0].p.slice(0, 2), ['bay', '591234567']);
  calls.length = 0;
  await B.search('bay', 'jane doe');
  const people = calls.find(c => c.sql.includes('from registry.board_people'));
  assert.deepEqual(people.p, ['bay', 'JANE DOE%', 'DOE JANE%', '%JANE DOE%']);
});

test('interlocks clamp the minimum board count', async () => {
  calls.length = 0;
  await B.interlocks('bay', '999');
  assert.deepEqual(calls[0].p, ['bay', 20]);
  await B.interlocks('Bay', 'x');
  assert.deepEqual(calls[1].p, ['bay', 2]);
});
