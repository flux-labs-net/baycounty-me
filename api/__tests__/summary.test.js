// Tests for the /admin To do counts (api/_summary.js). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const {summary, COUNTS} = require('../_summary');

test('returns one count per queue, null where a query fails', async () => {
  const q = async sql => {
    if (sql.includes('agendas.errors')) throw Object.assign(new Error('relation does not exist'), {code: '42P01'});
    if (sql.includes('limit_cases')) return [{n: 3}];
    if (sql.includes('corr.threads')) return [{n: '2'}];
    return [{n: 0}];
  };
  const r = await summary(q);
  assert.deepEqual(Object.keys(r.counts).sort(), Object.keys(COUNTS).sort());
  assert.equal(r.counts.limits, 3);
  assert.equal(r.counts.replies, 2);
  assert.equal(r.counts.owners, 0);
  assert.equal(r.counts.agendas, null);
});

test('every count key has a menu item or To do card in the admin page', () => {
  const fs = require('fs'), path = require('path');
  const js = fs.readFileSync(path.join(__dirname, '../../site/admin.js'), 'utf8');
  for (const k of Object.keys(COUNTS)) assert.match(js, new RegExp(`\\['${k}',`), `TODO card for ${k}`);
});
