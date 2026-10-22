// MCP tool tests against the built site files (site/public). Skipped when the site hasn't been built. Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs'), path = require('path');
const PUB = path.join(__dirname, '..', '..', 'site', 'public');
const built = fs.existsSync(path.join(PUB, 'downloads', 'index.json'));
process.env.API_SOURCE = 'files';
// Serve published files from disk instead of the network.
global.fetch = async url => {
  const p = path.join(PUB, new URL(url).pathname);
  if (!fs.existsSync(p)) return {ok: false, status: 404, json: async () => ({})};
  return {ok: true, status: 200, json: async () => JSON.parse(fs.readFileSync(p, 'utf8'))};
};
const mcp = require('../mcp');

test('normVendor and vendorMatch', () => {
  assert.equal(mcp.normVendor('Roberts & Roberts, Inc.'), 'roberts and roberts');
  assert.ok(mcp.vendorMatch('GAC Contractors, Inc.', mcp.normVendor('gac contractors')));
  assert.ok(!mcp.vendorMatch('Coastal Co', mcp.normVendor('co')), 'very short names do not match everything');
  assert.ok(!mcp.vendorMatch('ABC Paving', mcp.normVendor('abc')));
});

test('tools/list and resources/list', {skip: !built}, async () => {
  const t = await mcp.handle({}, {jsonrpc: '2.0', id: 1, method: 'tools/list'});
  const names = t.result.tools.map(x => x.name);
  for (const n of ['upcoming_meetings', 'member_voting_record', 'vendor_profile']) assert.ok(names.includes(n), n);
  const r = await mcp.handle({}, {jsonrpc: '2.0', id: 2, method: 'resources/list'});
  assert.ok(r.result.resources.some(x => x.uri === 'baycounty://datasets/contracts'));
  const rd = await mcp.handle({}, {jsonrpc: '2.0', id: 3, method: 'resources/read', params: {uri: 'baycounty://datasets/debt'}});
  const body = JSON.parse(rd.result.contents[0].text);
  assert.equal(body.dataset, 'debt'); assert.ok(body.rows.length > 0);
  const bad = await mcp.handle({}, {jsonrpc: '2.0', id: 4, method: 'resources/read', params: {uri: 'baycounty://datasets/nope'}});
  assert.ok(bad.error);
});

test('member_voting_record and upcoming_meetings', {skip: !built}, async () => {
  const req = {};
  const v = await mcp.call(req, 'member_voting_record', {member: 'Clair Pease', limit: 3});
  assert.equal(v.member, 'Clair Pease'); assert.ok(v.votes > 0); assert.ok(v.latest.length <= 3);
  await assert.rejects(mcp.call(req, 'member_voting_record', {member: 'zzzz nobody'}), /No recorded votes/);
  const m = await mcp.call(req, 'upcoming_meetings', {days: 120});
  assert.ok(Array.isArray(m.meetings));
  for (let i = 1; i < m.meetings.length; i++) assert.ok(Date.parse(m.meetings[i - 1].start.length === 10 ? m.meetings[i - 1].start + 'T12:00:00Z' : m.meetings[i - 1].start) <= Date.parse(m.meetings[i].start.length === 10 ? m.meetings[i].start + 'T23:59:00Z' : m.meetings[i].start));
});

test('vendor_profile pulls every section and never individual donors', {skip: !built}, async () => {
  const p = await mcp.call({}, 'vendor_profile', {vendor: 'ECSC'});
  for (const k of ['contracts', 'change_orders', 'vendor_payments', 'cra_payments', 'campaign_contributions']) assert.ok(k in p, k);
  assert.ok(p.contracts.count + p.change_orders.count + p.vendor_payments.count > 0);
  assert.equal(p.campaign_contributions.available, true);
  assert.match(p.note, /does not show why/);
});
