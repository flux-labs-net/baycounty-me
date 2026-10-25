// The site's first year (2016): one number in Python, the API and the page scripts, and no published row before it.
// Run: npm test (the download checks need a site build: python3 site/build_site.py).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const C = require('../_cutoff');

const ROOT = path.join(__dirname, '..', '..');
const read = p => fs.readFileSync(path.join(ROOT, p), 'utf8');
const DL = path.join(ROOT, 'site', 'public', 'downloads');

test('Python, the API and the page scripts use the same first year', () => {
  assert.equal(C.FIRST_YEAR, 2016);
  assert.equal(Number(read('data/entities/cutoff.py').match(/^FIRST_YEAR = (\d{4})$/m)[1]), C.FIRST_YEAR);
  assert.equal(Number(read('site/tables.js').match(/const FIRST_YEAR = (\d{4});/)[1]), C.FIRST_YEAR);
});

test('yearOf reads fiscal years, dates and spans', () => {
  assert.equal(C.yearOf('FY2015'), 2015);
  assert.equal(C.yearOf('2015-09-30'), 2015);
  assert.equal(C.yearOf('Sep 2009 - Nov 2011'), 2011);
  assert.equal(C.yearOf('2008 purchase; final loan payment FY2022'), 2022);
  assert.equal(C.yearOf(null), null);
  assert.ok(!C.keep(2015) && C.keep(2016) && C.keep(null) && C.keep('no date'));
});

// the column that dates each row (site/opendata.py FIRST_YEAR_COL), plus date_end where a dataset has structured dates
const COLS = ['fiscal_year', 'tax_year', 'end_date', 'last_year', 'last_date', 'expiration_date', 'closed_year', 'sort_date', 'date_end'];
test('no published dataset has a row from before 2016', {skip: !fs.existsSync(path.join(DL, 'index.json'))}, () => {
  const idx = JSON.parse(fs.readFileSync(path.join(DL, 'index.json'), 'utf8'));
  const bad = [];
  for (const d of idx.datasets) {
    const rows = JSON.parse(fs.readFileSync(path.join(DL, d.id + '.json'), 'utf8'));
    for (const r of rows) for (const c of COLS) if (c in r && !C.keep(r[c])) { bad.push(`${d.id}.${c}=${r[c]}`); break; }
  }
  assert.deepEqual(bad.slice(0, 10), []);
});
