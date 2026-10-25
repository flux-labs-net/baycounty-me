// Savings ideas (on each government page, built by site/savings_page.py): every figure is computed from records, never typed in. Run: npm test
// Needs a site build (python3 site/build_site.py).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const PUB = path.join(ROOT, 'site', 'public');
const read = f => JSON.parse(fs.readFileSync(f, 'utf8'));

test('opportunities.json holds no dollar figures, only rates, unit counts and expected record counts', () => {
  const cfg = read(path.join(ROOT, 'data', 'savings', 'opportunities.json'));
  const allowed = new Set(['low', 'high', 'units', 'expect']);
  const walk = (v, key, where) => {
    if (typeof v === 'number') assert.ok(allowed.has(key), `${where}: number under "${key}" (${v}); dollar figures must come from the records`);
    else if (Array.isArray(v)) v.forEach((x, i) => walk(x, key, `${where}[${i}]`));
    else if (v && typeof v === 'object') for (const [k, x] of Object.entries(v)) walk(x, k, `${where}.${k}`);
    else if (typeof v === 'string') assert.ok(!/\$\s?\d/.test(v), `${where}: text "${v.slice(0, 60)}…" states a dollar figure; show it from the records instead`);
  };
  walk(cfg, '', 'opportunities.json');
  for (const o of cfg.opportunities) if (o.rate) for (const k of ['low', 'high']) assert.ok(o.rate[k] >= 0 && o.rate[k] <= 1, `${o.id}: rate.${k} must be a share between 0 and 1`);
});

test('each opportunity adds up from its own evidence rows', () => {
  const D = read(path.join(PUB, 'data', 'savings.json'));
  const cfg = Object.fromEntries(read(path.join(ROOT, 'data', 'savings', 'opportunities.json')).opportunities.map(o => [o.id, o]));
  assert.ok(D.opportunities.length > 0);
  for (const o of D.opportunities) {
    const c = cfg[o.id];
    assert.ok(c, `${o.id} is not in opportunities.json`);
    assert.ok(D.evidence.some(r => r.opportunity_id === o.id), `${o.id} has no evidence rows`);
    if (!c.in_play) { assert.equal(o.in_play, null); continue; }
    const rows = D.evidence.filter(r => r.opportunity_id === o.id && r.group_id === c.in_play.group);
    const sum = rows.reduce((a, r) => a + (r[c.in_play.field] || 0), 0);
    assert.ok(Math.abs(sum - o.in_play) < 0.01, `${o.id}: in_play ${o.in_play} is not the sum of its evidence (${sum})`);
    if (c.rate) {
      assert.ok(Math.abs(o.savings_low - o.in_play * c.rate.low) < 0.01, `${o.id}: low estimate is not in_play × rate.low`);
      assert.ok(Math.abs(o.savings_high - o.in_play * c.rate.high) < 0.01, `${o.id}: high estimate is not in_play × rate.high`);
    } else assert.equal(o.savings_high, null, `${o.id}: no rate, so no estimate`);
  }
  const tot = k => D.opportunities.reduce((a, o) => a + (o[k] || 0), 0);
  for (const k of ['in_play', 'savings_low', 'savings_high']) assert.ok(Math.abs(tot(k) - D.stats[k]) < 0.01, `stats.${k} is not the sum of the opportunities`);
});

test('the page and its script carry no figures of their own', () => {
  const js = fs.readFileSync(path.join(ROOT, 'site', 'savings.js'), 'utf8');
  assert.ok(!/\$\s?\d/.test(js.replace(/\$\{/g, '')), 'savings.js contains a dollar literal');
  assert.ok(js.includes("fetch('/data/savings.json')"), 'savings.js should read the built data');
  const dl = read(path.join(PUB, 'downloads', 'index.json')).datasets.map(d => d.id);
  for (const id of ['savings-opportunities', 'savings-evidence']) assert.ok(dl.includes(id), `${id} is not in the open-data catalog`);
});
