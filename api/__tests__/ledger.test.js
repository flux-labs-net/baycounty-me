// Tests for accounting-system files on /admin (api/_ledger.js). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const dbPath = path.join(__dirname, '..', '_db.js');
const calls = [];
let reply = () => [];
require.cache[dbPath] = {id: dbPath, filename: dbPath, loaded: true, exports: {q: async (sql, p) => { calls.push({sql, p}); return reply(sql, p); }, hasDb: () => true}};
const L = require('../_ledger');

const A = '11111111-1111-4111-8111-111111111111', B = '22222222-2222-4222-8222-222222222222';

test('allowed senders: exact addresses only, lowercased and deduped; a whole domain is refused', () => {
  assert.deepEqual(L.cleanSenders('JMcSpadden@Springfield.FL.gov; jmcspadden@springfield.fl.gov, clerk@springfield.fl.gov'),
    ['jmcspadden@springfield.fl.gov', 'clerk@springfield.fl.gov']);
  assert.deepEqual(L.cleanSenders(''), []);
  assert.throws(() => L.cleanSenders('not an email'), /isn’t a full email/);
  assert.throws(() => L.cleanSenders('@springfield.fl.gov'), /not a whole domain/);
});

test('row ids must be uuids', () => {
  assert.deepEqual(L.cleanIds([A, A, B]), [A, B]);
  assert.throws(() => L.cleanIds(['1; drop table x']), /Unknown row id/);
  assert.deepEqual(L.cleanIds(undefined), []);
});

test('review: rejecting needs a note; approving a file reviews its pending rows', async () => {
  await assert.rejects(L.review('rejected', {ids: [A]}, 'a@x.com'), /reason/);
  await assert.rejects(L.review('maybe', {ids: [A]}, 'a@x.com'), /Unknown decision/);
  await assert.rejects(L.review('approved', {}, 'a@x.com'), /No rows/);
  calls.length = 0;
  reply = sql => sql.includes('from ingest.staging where raw_id') ? [{id: A}, {id: B}] : [{n: 2}];
  const r = await L.review('approved', {raw_id: B}, 'admin@baycounty.me');
  assert.deepEqual(r, {decision: 'approved', requested: 2, changed: 2});
  const call = calls.find(c => c.sql.includes('review_staging'));
  assert.deepEqual(call.p, [[A, B], 'approved', 'admin@baycounty.me', null]);
});

test('updateSource only sets what was sent', async () => {
  calls.length = 0;
  reply = () => [{id: A, entity_name: 'City of Springfield', auto_normalize: true, active: true, allowed_senders: []}];
  await L.updateSource({id: A, auto_normalize: true});
  assert.match(calls[0].sql, /set auto_normalize = \$2 where/);
  assert.deepEqual(calls[0].p, [A, true]);
  await assert.rejects(L.updateSource({id: A}), /Nothing to change/);
  await assert.rejects(L.updateSource({id: 'x', active: true}), /Unknown source/);
});

test('normalize calls the edge function with the service key, server side', async () => {
  process.env.SUPABASE_URL = 'https://proj.supabase.co/';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'svc';
  let seen;
  const fake = async (url, opts) => { seen = {url, opts}; return {ok: true, json: async () => ({processed: 1, results: [{ok: true}]})}; };
  const r = await L.normalize({raw_id: A}, fake);
  assert.equal(r.processed, 1);
  assert.equal(seen.url, 'https://proj.supabase.co/functions/v1/ingest-normalize');
  assert.equal(seen.opts.headers.Authorization, 'Bearer svc');
  assert.deepEqual(JSON.parse(seen.opts.body), {raw_id: A});
  await assert.rejects(L.normalize({}, fake), /Pick a file/);
  const failing = async () => ({ok: false, status: 401, json: async () => ({error: 'service role required'})});
  await assert.rejects(L.normalize({all: true}, failing), /service role required/);
});
