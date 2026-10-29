// Anonymous app check-ins (api/_app_usage.js, api/app-usage.js). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const U = require('../_app_usage');

test('a check-in is trimmed to platform, version, flags, opens and screen counts', () => {
  const p = U.parse({platform: 'ios', version: '1.4 (12)', new: true, month: true, week: false, opens: 3,
    screens: {today: 2, 'dataset/votes': 1, 'Restaurants': 4}, device_id: 'abc', email: 'x@y.example'});
  assert.deepEqual(p, {platform: 'ios', version: '1.4 (12)', isNew: true, month: true, week: false, opens: 3,
    screens: {today: 2, 'dataset/votes': 1, restaurants: 4}});
  assert.ok(!('device_id' in p) && !('email' in p));
});

test('unknown platforms are refused and odd values are dropped or capped', () => {
  assert.equal(U.parse({platform: 'web'}), null);
  assert.equal(U.parse(null), null);
  assert.equal(U.parse('ios'), null);
  const p = U.parse({platform: 'android', version: '<script>', new: 'yes', opens: 1e9,
    screens: {'person/john smith': 1, '825 ohio ave': 1, 'search?q=x': 2, ok: -4, events: 99999, good: '2'}});
  assert.equal(p.version, '');
  assert.equal(p.isNew, false);
  assert.equal(p.opens, 500);
  assert.deepEqual(p.screens, {events: 2000, good: 2});
});

test('screens is capped at 120 names', () => {
  const screens = Object.fromEntries(Array.from({length: 300}, (_, i) => ['s' + i, 1]));
  assert.equal(Object.keys(U.parse({platform: 'ios', screens}).screens).length, 120);
});

test('the endpoint answers 405, 400 and 202 without a database', async () => {
  delete process.env.DATABASE_URL; delete process.env.POSTGRES_URL;
  const handler = require('../app-usage');
  const call = async (method, body) => {
    const out = {};
    const res = {setHeader() {}, status(c) { out.status = c; return this; }, json(j) { out.body = j; return this; }};
    await handler({method, body, headers: {'x-forwarded-for': '203.0.113.9'}, socket: {}}, res);
    return out;
  };
  assert.equal((await call('GET')).status, 405);
  assert.equal((await call('POST', {platform: 'web'})).status, 400);
  assert.equal((await call('POST', JSON.stringify({platform: 'ios', opens: 1}))).status, 202);
});
