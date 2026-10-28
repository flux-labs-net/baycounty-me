// Tests for repeated posts (api/_dupes.js and data/dupes.py). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const {execFileSync} = require('child_process');
const D = require('../_dupes');

const ROOT = path.join(__dirname, '..', '..');
const CASES = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'dupes_cases.json'), 'utf8')).cases;
const opts = o => ({windowHours: o.window_hours, strictNumbers: !!o.strict_numbers, decisions: o.decisions || null});

for (const c of CASES) {
  test(`case: ${c.name}`, () => {
    const r = D.find(c.items, opts(c.options));
    assert.deepEqual(r.groups, c.groups);
    if (c.maybe !== 'any') assert.deepEqual(r.maybe.map(m => [m.a, m.b]), c.maybe.map(m => [m.a, m.b]));
  });
}

test('scores: filler words are ignored, an added clause still reads as the same text', () => {
  assert.deepEqual([...D.titleWords('Reuse System Temporarily Out of Service Due to Repairs')].sort(), ['out', 'repair', 'reuse', 'service', 'system']);
  const c = D.compare({title: 'Reuse System Offline Due to Repair', body: CASES[0].items[1].body}, {title: 'Reuse System Temporarily Out of Service', body: CASES[0].items[0].body});
  assert.equal(c.verdict, 'same');
  assert.ok(c.body > 0.9);
  assert.equal(c.numbers, true);
  assert.equal(D.containment('too short', 'too short'), null);
});

test('mergeNotices: one card per post, newest kept, earliest time and every version attached', () => {
  const [old, upd] = CASES[0].items;
  const n = (it, extra = {}) => ({notice_id: it.id, gov_id: 'lh', source: 'City of Lynn Haven', source_type: 'alert-center', title: it.title, summary: it.body, issued: it.when, url: 'u/' + it.id, ...extra});
  const weather = {notice_id: 'nws:1', source_type: 'nws', gov_id: null, source: 'NWS', title: 'Small Craft Advisory', summary: 'x', issued: old.when};
  const out = D.mergeNotices([n(old), weather, n(upd)]);
  assert.equal(out.length, 2);
  const card = out.find(x => x.notice_id === 'alert:lh:145');
  assert.equal(card.first_posted, old.when);
  assert.deepEqual(card.versions.map(v => v.notice_id), ['alert:lh:145', 'alert:lh:144']);
  // a reviewer's "keep apart" leaves both
  assert.equal(D.mergeNotices([n(old), n(upd)], {rejected: [{a_key: 'alert:lh:145', b_key: 'alert:lh:144'}]}).length, 2);
});

test('the API and the build find the same repeats', t => {
  try { execFileSync('python3', ['--version']); } catch { return t.skip('python3 not installed'); }
  const sets = CASES.map(c => ({items: c.items, o: c.options}));
  const em = path.join(ROOT, 'data', 'emergency', 'bay', 'notices.json');
  if (fs.existsSync(em)) {
    const ns = JSON.parse(fs.readFileSync(em, 'utf8')).notices.filter(n => !D.NOTICE_SKIP.has(n.source_type));
    sets.push({items: ns.map(D.noticeItem), o: {window_hours: 72}});
  }
  const pn = path.join(ROOT, 'data', 'notices', 'bay', 'notices.json');
  if (fs.existsSync(pn)) {
    const ns = JSON.parse(fs.readFileSync(pn, 'utf8')).notices;
    sets.push({items: ns.map(n => ({id: n.notice_id, group: n.agency || n.gov_id, when: n.published, title: n.title, body: n.text})), o: {window_hours: 504, strict_numbers: true}});
  }
  const py = `import json, sys; sys.path.insert(0, 'data'); import dupes
out = []
for s in json.load(sys.stdin):
    o = s['o']
    out.append(dupes.find(s['items'], window_hours=o['window_hours'], decisions=o.get('decisions'), strict_numbers=o.get('strict_numbers', False)))
json.dump(out, sys.stdout)`;
  const got = JSON.parse(execFileSync('python3', ['-c', py], {cwd: ROOT, input: JSON.stringify(sets), maxBuffer: 1 << 28}).toString());
  sets.forEach((s, i) => {
    const js = D.find(s.items, opts(s.o));
    assert.deepEqual(js.groups, got[i].groups, `groups differ in set ${i}`);
    assert.deepEqual(js.maybe, got[i].maybe, `review pairs differ in set ${i}`);
    assert.deepEqual(js.same_as, got[i].same_as);
  });
});

test('two short posts under one stock title stay apart', () => {
  const a = {title: 'PRECAUTIONARY BOIL WATER NOTICE', body: 'Olokee St. between S. Comet and S. Jan Dr.'};
  const b = {title: 'PRECAUTIONARY BOIL WATER NOTICE', body: 'All of Nelle Street and Harvey Street.'};
  assert.equal(D.compare(a, b).verdict, null);
  assert.equal(D.compare(a, {...a, body: 'Olokee St. between S. Comet and S. Jan Dr'}).verdict, 'same');
});
