// Tests for rule-alert validation, matching and email grouping (api/_rules.js, api/alerts-run.js). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
process.env.ALERTS_SECRET = 'test-secret';
const {validate, match, describe} = require('../_rules');
const {plan, compose} = require('../alerts-run');

test('validate normalizes and rejects bad rules', () => {
  assert.deepEqual(validate('contract', {gov: 'lh', min: '$250,000'}), {ok: true, type: 'contract', params: {gov: 'lh', min: 250000}});
  assert.equal(validate('contract', {gov: 'nope', min: 1}).ok, false);
  assert.equal(validate('contract', {gov: 'lh', min: 'lots'}).ok, false);
  assert.equal(validate('keyword', {keyword: 'ab'}).ok, false);
  assert.deepEqual(validate('keyword', {keyword: ' Ohio  Ave ', gov: ''}).params, {keyword: 'Ohio Ave'});
  assert.equal(validate('bogus', {}).ok, false);
  assert.match(describe('contract', {gov: 'lh', min: 100000}), /\$100,000 for Lynn Haven/);
});

test('contract rule matches amount and government, including change orders', () => {
  const rule = {id: 1, email: 'a@x.org', rule_type: 'contract', params: {gov: 'lh', min: 100000}};
  const big = {dataset: 'contracts', record_hash: 'h1', government_key: 'lh', record: {vendor: 'ACME', amount: 250000, source_url: 'https://s'}};
  assert.ok(match(rule, big));
  assert.equal(match(rule, {...big, government_key: 'pc'}), null);
  assert.equal(match(rule, {...big, record: {amount: 5000}}), null);
  assert.equal(match(rule, {...big, record: {amount: null}}), null, 'missing amount never matches');
  assert.ok(match(rule, {dataset: 'change-orders', record_hash: 'h2', government_key: 'lh', record: {vendor: 'ACME', change_amount: -150000}}));
});

test('vote, keyword and campaign rules', () => {
  const vote = {id: 2, rule_type: 'vote', params: {member: 'Clair Pease'}};
  assert.ok(match(vote, {dataset: 'member-votes', record_hash: 'v', record: {member: 'clair  pease', vote: 'yes', headline: 'Budget'}}));
  assert.equal(match(vote, {dataset: 'member-votes', record_hash: 'v', record: {member: 'Doug Crosby'}}), null);
  const kw = {id: 3, rule_type: 'keyword', params: {keyword: 'Ohio Ave', gov: 'lh'}};
  const meet = {dataset: 'meetings', record_hash: 'm', record: {board: 'lh-cra', title: 'CRA Board', start: '2026-10-13T17:15:00-05:00', agenda_items: ['Approval of new drive-through facility at 1615a Ohio Ave. Dutch Bros.']}};
  const m = match(kw, meet);
  assert.ok(m); assert.match(m.detail, /Dutch Bros/);
  assert.equal(match(kw, {...meet, record: {...meet.record, board: 'pc'}}), null, 'other government');
  assert.equal(match(kw, {...meet, record: {...meet.record, past: true}}), null, 'past meetings skipped');
  const camp = {id: 4, rule_type: 'campaign', params: {candidate: 'Chris Moore'}};
  assert.ok(match(camp, {dataset: 'candidates-2026', record_hash: 'c', record: {candidate: 'Chris Moore', reports_through: '2026-10-10', total_raised: 1200}}));
});

test('plan groups one email per subscriber and skips delivered matches', () => {
  const rules = [{id: 1, email: 'a@x.org', rule_type: 'contract', params: {gov: 'lh', min: 1}}, {id: 2, email: 'a@x.org', rule_type: 'vote', params: {member: 'Clair Pease'}},
    {id: 3, email: 'b@x.org', rule_type: 'contract', params: {gov: 'pc', min: 1}}];
  const events = [{dataset: 'contracts', record_hash: 'h1', government_key: 'lh', record: {vendor: 'V', amount: 10}},
    {dataset: 'contracts', record_hash: 'h1', government_key: 'lh', record: {vendor: 'V', amount: 10}},
    {dataset: 'member-votes', record_hash: 'v1', record: {member: 'Clair Pease', vote: 'no', headline: 'X'}}];
  const p = plan(rules, events);
  assert.deepEqual([...p.keys()], ['a@x.org']);
  assert.equal(p.get('a@x.org').length, 2);
  assert.equal(p.get('a@x.org')[0].hits.length, 1, 'duplicate event de-duplicated');
  const again = plan(rules, events, new Set(['1|c:h1', '2|v:v1']));
  assert.equal(again.size, 0);
  const mail = compose('a@x.org', p.get('a@x.org'));
  assert.match(mail.subject, /2 new matches/);
  assert.match(mail.text, /alerts\/manage\?t=/);
  assert.match(mail.html, /does not|not why/);
});
