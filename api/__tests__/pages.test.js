// Every site page's data must be in the database and the API. Run: npm test
// Fails, naming the page, when a page in /data/app/pages.json has no entry in api/_pages.js, or an entry points at a
// dataset the open-data catalog (and so the database) doesn't have. Needs a site build (python3 site/build_site.py).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const {sourceFor} = require('../_pages');
const {openapi} = require('../v1');

const PUB = path.join(__dirname, '..', '..', 'site', 'public');
const read = f => JSON.parse(fs.readFileSync(path.join(PUB, f), 'utf8'));

test('every site page says where its data lives in the API', () => {
  const pages = read('data/app/pages.json').map(p => p.path || p.u);
  const ids = new Set(read('downloads/index.json').datasets.map(d => d.id));
  assert.ok(pages.length > 20);
  for (const p of pages) {
    const s = sourceFor(p);
    assert.ok(s, `${p} has no entry in api/_pages.js: add its datasets (and a migration for any new table), or "none" with a reason`);
    assert.ok((s.datasets || []).length || (s.endpoints || []).length || s.none, `${p}: list datasets, endpoints or "none"`);
    for (const id of s.datasets || []) assert.ok(ids.has(id), `${p} uses dataset "${id}", which is not in the open-data catalog`);
  }
});

test('every dataset has a database migration', () => {
  const sql = fs.readdirSync(path.join(__dirname, '..', '..', 'db', 'migrations')).map(f => fs.readFileSync(path.join(__dirname, '..', '..', 'db', 'migrations', f), 'utf8')).join('\n');
  for (const d of read('downloads/index.json').datasets) {
    const t = d.id.replace(/-/g, '_');
    assert.ok(new RegExp(`create table if not exists ${t}\\b`).test(sql), `dataset "${d.id}" has no "create table ${t}" migration`);
  }
});

test('OpenAPI documents every endpoint the API serves', () => {
  const spec = openapi(read('downloads/index.json'));
  for (const p of ['/datasets', '/datasets/{id}', '/governments', '/status', '/changes', '/meetings.ics', '/correspondence', '/pages', '/search', '/entities', '/entities/{id}', '/budget-compare', '/checkbook', '/budget-actual'])
    assert.ok(spec.paths[p], `OpenAPI is missing ${p}`);
});
