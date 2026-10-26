// Filters for the /admin "Votes from minutes" review queue (api/_minutes.js). No database needed. Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const {where, cleanIds, CHECKS} = require('../_minutes');

test('default queue is unreviewed flagged motions', () => {
  const w = where();
  assert.match(w.sql, /check_status = 'flagged'/);
  assert.deepEqual(w.params, ['unreviewed']);
});

test('filters become numbered params, never inline text', () => {
  const w = where({queue: 'sample', board: 'pc-cra', year: '2018', status: 'approved', q: "Pro Force'; drop"});
  assert.match(w.sql, /m\.sampled/);
  assert.deepEqual(w.params, ['approved', 'pc-cra', 2018, "%pro force'; drop%"]);
  assert.ok(!w.sql.includes('drop'));
  assert.equal(where({queue: 'all', status: ''}).sql, 'true');
});

test('bad filters are refused', () => {
  assert.throws(() => where({queue: 'x'}), /queue/);
  assert.throws(() => where({board: 'PC; drop'}), /board/);
  assert.throws(() => where({year: '2015'}), /year/);
  assert.throws(() => where({status: 'done'}), /status/);
});

test('ids are checked', () => {
  assert.deepEqual(cleanIds({items: [{id: 3}, {id: '4'}]}).map(x => x.id), [3, 4]);
  assert.throws(() => cleanIds({items: [{id: 'x'}]}), /motion/);
});

test('every check code match.py writes has a label', () => {
  const py = require('fs').readFileSync(require('path').join(__dirname, '..', '..', 'data', 'minutes', 'match.py'), 'utf8');
  const codes = new Set([...py.matchAll(/(?:out\.append\(|"checks": \[)"([a-z_]+)"/g)].map(m => m[1]));
  assert.ok(codes.size >= 8);
  for (const code of codes) {
    assert.ok(CHECKS[code], code);
  }
});
