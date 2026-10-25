// Entity profiles API (api/_entities.js) against the built downloads. Run: npm test (needs python3 site/build_site.py).
// The database is "down" here (fetch to it fails), so every read takes the published-file fallback.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const PUB = path.join(__dirname, '..', '..', 'site', 'public');
const realFetch = global.fetch;
test.before(() => {
  global.fetch = async url => {
    const u = new URL(url);
    if (!u.hostname.includes('baycounty.me')) throw new Error('database unreachable in tests');
    const f = path.join(PUB, u.pathname);
    if (!fs.existsSync(f)) return {ok: false, status: 404};
    return {ok: true, status: 200, json: async () => JSON.parse(fs.readFileSync(f, 'utf8'))};
  };
});
test.after(() => { global.fetch = realFetch; });

const catalog = () => JSON.parse(fs.readFileSync(path.join(PUB, 'downloads', 'index.json'), 'utf8'));
const E = () => require('../_entities');

test('every connection points at entities that have a profile', () => {
  const profiles = JSON.parse(fs.readFileSync(path.join(PUB, 'downloads', 'entity-profiles.json'), 'utf8'));
  const links = JSON.parse(fs.readFileSync(path.join(PUB, 'downloads', 'entity-connections.json'), 'utf8'));
  const ids = new Set(profiles.map(p => p.entity_id));
  assert.ok(profiles.length > 1000 && links.length > 1000);
  for (const l of links) {
    assert.ok(ids.has(l.from_id) && ids.has(l.to_id), `connection ${l.link_id} names an entity with no profile`);
    assert.ok(E().ID_RE.test(l.from_id) && E().ID_RE.test(l.to_id), `bad id in ${l.link_id}`);
  }
  for (const p of profiles) assert.ok(p.page_url && p.page_url.startsWith('/'), `${p.entity_id} has no page`);
});

test('individual donors appear only when they run a business', () => {
  const links = JSON.parse(fs.readFileSync(path.join(PUB, 'downloads', 'entity-connections.json'), 'utf8'));
  const runs = new Set(links.filter(x => x.relation === 'runs' && x.from_kind === 'owner').map(x => x.from_id));
  const gifts = links.filter(x => x.relation === 'gift');
  for (const l of gifts) assert.ok(['vendor', 'business', 'committee', 'nonprofit', 'gov', 'owner'].includes(l.from_kind), `gift from a ${l.from_kind}: ${l.from_name}`);
  for (const l of gifts.filter(x => x.from_kind === 'owner')) assert.ok(runs.has(l.from_id), `${l.from_id} gave but runs no business`);
  const rows = JSON.parse(fs.readFileSync(path.join(PUB, 'downloads', 'owner-gifts.json'), 'utf8'));
  for (const r of rows) {
    assert.ok(r.businesses && r.business_doc_numbers, `${r.donor_id} has no business`);
    // keyed ids only: the Sunbiz person key (p_...) is a hash of name + ZIP + street and can be traced to an address
    assert.match(r.donor_id, /^owner:o_[0-9a-f]{16}$/, `${r.donor_id} is not a keyed owner id`);
    for (const k of Object.keys(r)) assert.ok(!/address|occupation|zip|street/i.test(k), `owner-gifts must not publish ${k}`);
  }
});

test('getEntity returns a profile and its connections from either side', async () => {
  const links = JSON.parse(fs.readFileSync(path.join(PUB, 'downloads', 'entity-connections.json'), 'utf8'));
  const gift = links.find(l => l.relation === 'gift' && l.to_kind === 'person');
  const d = await E().getEntity({}, catalog(), gift.to_id);
  assert.equal(d.entity.entity_id, gift.to_id);
  const c = d.connections.find(x => x.other.entity_id === gift.from_id && x.relation === 'gift');
  assert.ok(c, 'the gift shows on the official\'s profile');
  assert.equal(c.direction, 'in');
  assert.equal(c.label, 'got campaign gifts from');
  await assert.rejects(E().getEntity({}, catalog(), 'person:nobody-at-all'), e => e.status === 404);
  await assert.rejects(E().getEntity({}, catalog(), 'drop table'), e => e.status === 400);
});

test('searchEntities finds by name', async () => {
  const rows = await E().searchEntities({}, catalog(), {q: 'dewberry'});
  assert.ok(rows.some(r => r.entity_id === 'vendor:dewberry'));
});

test('a board member or business officer confirmed as an official shows once, as the official', () => {
  const {mergeConfirmed} = E();
  const links = [
    {from_id: 'member:b_1', from_name: 'Allan Branch', from_kind: 'member', to_id: 'nonprofit:np-1', relation: 'board', amount: 500, first_date: '2025', detail: 'Director · current'},
    {from_id: 'member:b_2', from_name: 'Jane Doe', from_kind: 'member', to_id: 'nonprofit:np-1', relation: 'board'},
    {from_id: 'member:b_3', from_name: 'Brian Q. Rust', from_kind: 'member', to_id: 'business:l1', relation: 'runs'},
    {from_id: 'owner:o_4', from_name: 'Pat Smith', from_kind: 'owner', to_id: 'business:l1', relation: 'runs'},
  ];
  const live = [
    {from_id: 'person:allan-branch', from_name: 'Allan Branch', from_kind: 'person', to_id: 'nonprofit:np-1', relation: 'board', detail: 'Director · current', same_as: 'member:b_1', checked_by_hand: true},
    {from_id: 'person:brian-rust', from_name: 'Brian Rust', from_kind: 'person', to_id: 'business:l1', relation: 'runs', checked_by_hand: true},
  ];
  const all = mergeConfirmed(links, live);
  assert.deepEqual(all.map(r => r.from_id).sort(), ['member:b_2', 'owner:o_4', 'person:allan-branch', 'person:brian-rust']);
  const allan = all.find(r => r.from_id === 'person:allan-branch');
  assert.equal(allan.merged_from, 'member:b_1');
  assert.equal(allan.amount, 500, 'keeps the pay from the filing');
  assert.equal(allan.first_date, '2025');
});

test('each person has one row per government, with every role folded in', async () => {
  const links = JSON.parse(fs.readFileSync(path.join(PUB, 'downloads', 'entity-connections.json'), 'utf8'));
  const seen = new Map();
  for (const l of links.filter(x => ['serves', 'served', 'candidate'].includes(x.relation))) {
    const k = l.from_id + '|' + l.to_id;
    assert.ok(!seen.has(k), `${l.from_name} is listed twice for ${l.to_name}: "${seen.get(k)}" and "${l.detail}"`);
    seen.set(k, l.detail);
  }
  const hamre = links.find(l => l.from_id === 'person:cindy-hamre' && l.to_id === 'gov:sp');
  if (hamre) {
    assert.equal(hamre.relation, 'serves');
    assert.match(hamre.detail, /Ward 4 \(2022–now\)/);
    assert.match(hamre.detail, /Running again in 2026/);
    assert.doesNotMatch(hamre.detail, /springfield/);  // no lowercased place names
  }
  const r = await E().getEntity({}, catalog(), 'gov:sp');
  const people = r.connections.filter(c => c.other.kind === 'person');
  assert.ok(people.length && people.every(c => c.other.kind_label && c.other.kind_label !== 'Official or candidate'), 'people on a government page say what they are');
});
