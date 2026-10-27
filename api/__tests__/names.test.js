// Name casing (api/_names.js) must match the build's (data/entities/ids.py biz_case / person_case), so a name reads the
// same on a static page, in the API and in a page script. Run: npm test (needs python3 site/build_site.py).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const {execFileSync} = require('child_process');
const {bizCase, personCase, nameCase} = require('../_names');

const ROOT = path.join(__dirname, '..', '..');
const PUB = path.join(ROOT, 'site', 'public');

test('all-caps names read as names', () => {
  const cases = {
    'PANAMA CITY COMMUNITY DEVELOPMENT COUNCIL, INC.': 'Panama City Community Development Council, Inc.',
    'HARRISON & LUVERNE, LLC': 'Harrison & Luverne, LLC',
    'ST. ANDREWS AND ST. JOSEPH BAYS ESTUARY PROGRAM': 'St. Andrews and St. Joseph Bays Estuary Program',
    'DOWNTOWN PC RENAISSANCE LLC': 'Downtown PC Renaissance LLC',
    'MCKENZIE BROTHERS 1ST STREET LLC': 'McKenzie Brothers 1st Street LLC',
    'YMCA OF NORTHWEST FLORIDA': 'YMCA of Northwest Florida',
    'Mixed Case Stays, Inc': 'Mixed Case Stays, Inc',
  };
  for (const [raw, want] of Object.entries(cases)) assert.equal(bizCase(raw), want);
  assert.equal(personCase('JOHN A MCDANIEL III'), 'John A McDaniel III');
  assert.equal(nameCase('BARRY S WILSON', 'member'), 'Barry S Wilson');
  assert.equal(nameCase('GAC, LLC', 'business'), 'GAC, LLC');
  assert.equal(bizCase(null), null);
});

test('the API and the build case every published name the same way', t => {
  try { execFileSync('python3', ['--version']); } catch { return t.skip('python3 not installed'); }
  const f = path.join(PUB, 'downloads', 'entity-profiles.json');
  if (!fs.existsSync(f)) return t.skip('needs a site build');
  const names = new Set();
  for (const p of JSON.parse(fs.readFileSync(f, 'utf8'))) {
    if (!p.name) continue;
    names.add(p.name); names.add(p.name.toUpperCase()); names.add(p.name.toLowerCase());
  }
  const list = [...names];
  const py = `import json, sys; sys.path.insert(0, 'data/entities'); import ids
names = json.load(sys.stdin)
json.dump([[ids.biz_case(n), ids.person_case(n)] for n in names], sys.stdout)`;
  const out = JSON.parse(execFileSync('python3', ['-c', py], {cwd: ROOT, input: JSON.stringify(list), maxBuffer: 1 << 28}).toString());
  const bad = [];
  list.forEach((n, i) => {
    if (bizCase(n) !== out[i][0]) bad.push(`biz ${JSON.stringify(n)}: js ${JSON.stringify(bizCase(n))} py ${JSON.stringify(out[i][0])}`);
    if (personCase(n) !== out[i][1]) bad.push(`person ${JSON.stringify(n)}: js ${JSON.stringify(personCase(n))} py ${JSON.stringify(out[i][1])}`);
  });
  assert.ok(list.length > 10000);
  assert.deepEqual(bad.slice(0, 20), []);
});
