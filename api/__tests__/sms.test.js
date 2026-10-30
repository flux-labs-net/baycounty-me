// Tests for alert text messages (api/_sms.js): numbers, message length, keywords and the webhook key.
// No network or database. Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const S = require('../_sms');
const E = require('../_emergency');

test('US mobile numbers are cleaned to +1 format', () => {
  assert.equal(S.normPhone('(850) 555-0123'), '+18505550123');
  assert.equal(S.normPhone('1-850-555-0123'), '+18505550123');
  assert.equal(S.normPhone('+1 850.555.0123'), '+18505550123');
  assert.equal(S.normPhone('555-0123'), null);
  assert.equal(S.normPhone('(050) 555-0123'), null);
  assert.equal(S.normPhone('+44 20 7946 0958'), null);
  assert.equal(S.maskPhone('+18505550123'), '(•••) •••-0123');
});

test('message parts: plain characters fit 160, others 70', () => {
  assert.equal(S.segments('a'.repeat(160)), 1);
  assert.equal(S.segments('a'.repeat(161)), 2);
  assert.equal(S.segments('a'.repeat(306)), 2);
  assert.equal(S.segments('“quoted”'), 1);
  assert.equal(S.segments('“'.repeat(71)), 2);
});

test('alert texts are plain, at most two parts, and say how to stop', () => {
  const n = {notice_id: 'ipaws:x', kind: 'evacuation', title: 'Mandatory evacuation ordered for Zones A and B — leave now',
    zones: 'A, B', instruction: 'Leave now. Go inland. Shelters are open at Deane Bozeman School and Mosley High School. ' + 'More detail. '.repeat(30)};
  const t = S.alertText(n, 'evacuation');
  assert.ok(t.startsWith('BayCounty.me: Evacuation order'), t);
  assert.ok(t.endsWith('baycounty.me/emergency Reply STOP to end.'), t);
  assert.ok(t.length <= 306, String(t.length));
  assert.equal(S.segments(t), 2);
  const short = S.alertText({notice_id: 'w', kind: 'boil-water', source: 'City of Lynn Haven', gov_id: 'lh', title: 'Boil water notice for Ohio Ave'}, 'water');
  assert.equal(S.segments(short), 1, short);
});

test('only urgent and important alert types can come by text', () => {
  const sms = E.ALERT_TYPES.filter(t => t.channels.includes('sms')).map(t => t.key);
  assert.deepEqual(sms, ['evacuation', 'weather', 'safety', 'shelters', 'water']);
});

test('STOP, START and HELP keywords', () => {
  assert.equal(S.keyword('stop'), 'stop');
  assert.equal(S.keyword(' Unsubscribe. '), 'stop');
  assert.equal(S.keyword('START'), 'start');
  assert.equal(S.keyword('help'), 'help');
  assert.equal(S.keyword('stop sending me these please'), null);
});

test('the reply webhook refuses requests without its key', async () => {
  const res = {code: 0, setHeader() {}, status(c) { this.code = c; return this; }, json() { return this; }};
  await S.webhook({method: 'POST', query: {k: 'nope'}, body: {}}, res);
  assert.equal(res.code, 403);
  assert.ok(S.webhookUrl().includes('/api/sms?k=' + S.hookKey()));
});
