// Tests for the /admin Sent mail tab (api/_sent.js). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const {shape, domainOf} = require('../_sent');

const now = new Date('2026-10-22T21:00:00Z');
const ago = d => new Date(now - d * 864e5).toISOString();
const emails = [
  {id: '1', from: 'BayCounty.me <hello@baycounty.me>', to: ['a@x.com'], subject: 'Your alerts', created_at: ago(0.1), last_event: 'delivered'},
  {id: '2', from: 'hello@baycounty.me', to: ['b@x.com'], subject: 'Digest', created_at: ago(1), last_event: 'bounced'},
  {id: '3', from: 'hello@baycounty.me', to: ['c@x.com'], subject: 'Sign in', created_at: ago(2), last_event: 'delivery_delayed'},
  {id: '4', from: 'Jeremy <jeremy@fluxlabs.net>', to: ['d@x.com'], subject: 'Hi', created_at: ago(1), last_event: 'opened'},
  {id: '5', from: 'hello@baycounty.me', to: ['e@x.com'], subject: 'Old', created_at: ago(20), last_event: 'delivered'},
];

test('counts the default domain and window', () => {
  const s = shape(emails, {now});
  assert.equal(s.counts.total, 3);
  assert.equal(s.counts.reached, 1);
  assert.equal(s.counts.problems, 2);
  assert.deepEqual(s.counts.by, {delivered: 1, bounced: 1, delivery_delayed: 1});
  assert.deepEqual(s.domains, ['baycounty.me', 'fluxlabs.net']);
});

test('filters: all domains, longer window, problems only, status, search', () => {
  assert.equal(shape(emails, {now, domain: ''}).counts.total, 4);
  assert.equal(shape(emails, {now, days: 30}).counts.total, 4);
  assert.deepEqual(shape(emails, {now, status: 'problems'}).rows.map(r => r.id), ['2', '3']);
  assert.deepEqual(shape(emails, {now, status: 'bounced'}).rows.map(r => r.id), ['2']);
  assert.deepEqual(shape(emails, {now, q: 'c@x'}).rows.map(r => r.id), ['3']);
  assert.equal(domainOf('X <Hi@BayCounty.me>'), 'baycounty.me');
});
