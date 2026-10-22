// Tests for the Resend inbound webhook (api/agenda-inbound.js). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('crypto');
const {verify, forInbox} = require('../agenda-inbound');

const secret = 'whsec_' + Buffer.from('0123456789abcdef0123456789abcdef').toString('base64');
const sign = (id, ts, body, s = secret) => 'v1,' + crypto.createHmac('sha256', Buffer.from(s.slice(6), 'base64')).update(`${id}.${ts}.${body}`).digest('base64');
const now = 1792700000000, ts = String(now / 1000);
const body = JSON.stringify({type: 'email.received', data: {email_id: 'e1', to: ['ingest@baycounty.me']}});

test('accepts a correctly signed, fresh webhook (also among several signatures)', () => {
  assert.ok(verify(secret, {'svix-id': 'msg_1', 'svix-timestamp': ts, 'svix-signature': sign('msg_1', ts, body)}, body, now));
  assert.ok(verify(secret, {'svix-id': 'msg_1', 'svix-timestamp': ts, 'svix-signature': 'v1,AAAA ' + sign('msg_1', ts, body)}, body, now));
});

test('rejects tampered body, wrong secret, old timestamp and missing headers', () => {
  const h = {'svix-id': 'msg_1', 'svix-timestamp': ts, 'svix-signature': sign('msg_1', ts, body)};
  assert.ok(!verify(secret, h, body.replace('e1', 'e2'), now));
  assert.ok(!verify('whsec_' + Buffer.from('another-secret-another-secret!!').toString('base64'), h, body, now));
  assert.ok(!verify(secret, h, body, now + 6 * 60 * 1000));
  assert.ok(!verify(secret, {'svix-id': 'msg_1'}, body, now));
  assert.ok(!verify('', h, body, now));
});

test('only mail to the agenda inbox counts', () => {
  assert.ok(forInbox({to: ['Agendas <ingest@baycounty.me>']}));
  assert.ok(forInbox({to: ['x@y.com'], received_for: ['INGEST@baycounty.me']}));
  assert.ok(!forInbox({to: ['hello@baycounty.me']}));
});
