// Zoned schools (api/_schools.js): the point-in-zone test behind /api/v1/schools, the MCP tool and the /schools page.
// Uses the published school-zones and schools datasets, so it needs a site build (python3 site/build_site.py).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const S = require('../_schools');

const PUB = path.join(__dirname, '..', '..', 'site', 'public', 'downloads');
const read = f => JSON.parse(fs.readFileSync(path.join(PUB, f), 'utf8'));

test('inRings handles holes (even-odd)', () => {
  const outer = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]], hole = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]];
  assert.equal(S.inRings([outer, hole], 2, 2), true);
  assert.equal(S.inRings([outer, hole], 5, 5), false);
  assert.equal(S.inRings([outer], 11, 5), false);
});

test('Bay High School\'s own address is in the Bay High zone', () => {
  const zones = read('school-zones.json'), schools = read('schools.json');
  if (!zones.length) return;
  const r = S.zonedAt(zones, schools, 30.170673, -85.65866);
  assert.equal(r.inside_district, true);
  assert.equal(r.high.school.name, 'Bay High School');
  assert.ok(r.elementary && r.middle, 'every level has a zone in the middle of Panama City');
});

test('every zone points at a school in the schools dataset', () => {
  const zones = read('school-zones.json'), ids = new Set(read('schools.json').map(s => s.school_id));
  for (const z of zones) assert.ok(ids.has(z.school_id), `zone "${z.zone_name}" has no school (add it to data/schools/<county>/zone_schools.json)`);
});

test('a point far outside the county has no zones; a bad point is a 400', () => {
  const r = S.zonedAt(read('school-zones.json'), read('schools.json'), 25.77, -80.19);
  assert.equal(r.inside_district, false);
  assert.throws(() => S.zonedAt([], [], 'x', 1), e => e.status === 400);
});

test('geocode builds a county address query and needs a house number', async () => {
  let asked = '';
  const hits = await S.geocode('1200 Harrison Ave, Panama City FL 32401', async u => { asked = u; return {json: async () => ({features: [{attributes: {ADDRESS: '1200 HARRISON AVE', CMNTY: 'PANAMA CITY', ZIP: '32401'}, geometry: {x: -85.66, y: 30.17}}]})}; });
  assert.match(new URL(asked).searchParams.get('where'), /ADDRESS LIKE '1200 %' AND ADDRESS LIKE '% HARRISON%'/);
  assert.deepEqual(hits[0], {address: '1200 HARRISON AVE', city: 'PANAMA CITY', zip: '32401', lat: 30.17, lon: -85.66});
  await assert.rejects(S.geocode('Harrison Ave'), e => e.status === 400);
});
