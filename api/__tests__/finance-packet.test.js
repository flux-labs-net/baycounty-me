// The board packet takes every name it prints from the place config, so another county's build brands its own packet.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const {execFileSync} = require('child_process');

const root = path.join(__dirname, '..', '..');

test('packet code has no hard-coded site, operator or city names', () => {
  const js = fs.readFileSync(path.join(root, 'site', 'finance.js'), 'utf8');
  const packet = js.slice(js.indexOf('// ---------- board packet ----------'), js.indexOf("$('#print')"));
  assert.ok(packet.length > 1000, 'found the packet code');
  for (const name of ['BayCounty', 'Flux Labs', 'Lynn Haven', 'baycounty.me']) assert.ok(!packet.includes(name), `packet code mentions ${name}`);
});

test('finance page carries the brand from places/<id>/place.json', () => {
  const out = execFileSync('python3', ['-c', 'import json, finance_page; print(json.dumps(finance_page.brand()))'], {cwd: path.join(root, 'site')}).toString();
  const brand = JSON.parse(out);
  const placeCfg = JSON.parse(fs.readFileSync(path.join(root, 'places', 'fl-bay', 'place.json'), 'utf8'));
  assert.equal(brand.site, placeCfg.site_name);
  assert.equal(brand.operator, placeCfg.operator.name);
  assert.equal(brand.governments.lh, placeCfg.governments.find(g => g.key === 'lh').name);
  const html = fs.readFileSync(path.join(root, 'site', 'public', 'finance', 'index.html'), 'utf8');
  assert.match(html, /<script type="application\/json" id="brand">/);
});
