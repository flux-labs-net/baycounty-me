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
