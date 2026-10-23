// Tests for agenda-item alerts (api/_rules.js 'agenda-items' events, alerts-run plan()). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
process.env.ALERTS_SECRET = 'test-secret';
const {match, describe} = require('../_rules');
const {plan} = require('../alerts-run');

const item = (over = {}) => ({dataset: 'agenda-items', record_hash: 'x', government_key: 'county', record: {
  board: 'county', meeting_date: '2026-11-03', item_number: '12', title: 'Southport Water Treatment Plant Feasibility Study',
  summary: 'Task order for a feasibility study.', kind: 'contract', amount: 2458636, parties: ['Black & Veatch'],
  addresses: ['Southport'], agenda_url: 'https://baycountyfl.primegov.com/Portal/Meeting?meetingTemplateId=1950', ...over}});
const rule = (rule_type, params, id = 1) => ({id, email: 'a@x.com', rule_type, params});

test('keyword rules match agenda item titles, parties and addresses, and respect the government', () => {
  assert.ok(match(rule('keyword', {keyword: 'southport'}), item()));
  assert.ok(match(rule('keyword', {keyword: 'Black & Veatch'}), item()));
  const m = match(rule('keyword', {keyword: 'water treatment', gov: 'county'}), item());
  assert.match(m.title, /agenda, 2026-11-03: Southport Water Treatment/);
  assert.match(m.detail, /\$2,458,636/);
  assert.equal(m.url, item().record.agenda_url);
  assert.equal(match(rule('keyword', {keyword: 'water treatment', gov: 'lh'}), item()), null);
  assert.equal(match(rule('keyword', {keyword: 'sidewalk'}), item()), null);
});

test('contract rules match spending items over the amount for that government only', () => {
  const m = match(rule('contract', {gov: 'county', min: 1000000}), item());
  assert.ok(m);
  assert.match(m.detail, /not yet approved/);
  assert.equal(match(rule('contract', {gov: 'county', min: 5000000}), item()), null);
  assert.equal(match(rule('contract', {gov: 'lh', min: 0}), item()), null);
  assert.equal(match(rule('contract', {gov: 'county', min: 0}), item({kind: 'budget', amount: 9e8})), null);
  assert.equal(match(rule('contract', {gov: 'county', min: 0}), item({amount: null})), null);
  assert.match(describe('contract', {gov: 'county', min: 100000}), /upcoming agendas/);
});

test('an item already matched from the meetings feed is not sent twice', () => {
  const meeting = {dataset: 'meetings', record_hash: 'm', government_key: 'county', record: {board: 'county', start: '2026-11-03T09:00:00-06:00',
    title: 'BOCC Regular Meeting', agenda_items: ['Southport Water Treatment Plant Feasibility Study'], agenda_url: 'u'}};
  const out = plan([rule('keyword', {keyword: 'southport'})], [item(), meeting]);
  const hits = out.get('a@x.com')[0].hits;
  assert.equal(hits.length, 1);
  assert.match(hits[0].dedupe, /^k:/);
  // without the meeting, the agenda item alone is sent
  assert.equal(plan([rule('keyword', {keyword: 'southport'})], [item()]).get('a@x.com')[0].hits.length, 1);
});
