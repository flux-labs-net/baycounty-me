// Address report (api/_address_report.js): the pieces that don't need the live map servers, plus one full build
// against fake map servers. Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const A = require('../_address_report');

test('parcel fields never include owner, mailing, buyer/seller or legal description fields', () => {
  for (const f of A.PARCEL_FIELDS) assert.ok(!/OWN|MAIL|GRNTR|GRTEE|LEGAL/i.test(f), `${f} must not be requested`);
});

test('addresses parse to a house number and street words', () => {
  assert.deepEqual(A.parseAddress('825 Ohio Ave, Lynn Haven, FL 32444'), {house: '825', words: ['OHIO'], unit: ''});
  assert.deepEqual(A.parseAddress('100 W Hwy 98 Apt 4B'), {house: '100', words: ['HIGHWAY', '98'], unit: '4B'});
  assert.throws(() => A.parseAddress('Ohio Ave'), /house number/);
  assert.throws(() => A.parseAddress('12 Street'), /street name/);
});

test('parcel shards match site/addr_page.py shard_key', () => {
  assert.equal(A.shardOf('09611-010-000', 96), 'h27');
  assert.equal(A.shardOf('10481-000-000', 128), 'h123');
});

const D = {taxdist: {'06': 'Lynn Haven'}, districts: {'Lynn Haven': {label: 'Lynn Haven', stack: ['county', 'school', 'city'], total: 13}, unincorporated: {label: 'Unincorporated', stack: ['county', 'school'], total: 9}},
  auth: {county: {n: 'Bay County Commission', g: 'county', school: false, m: 5}, school: {n: 'Schools', g: 'school', school: true, m: 4}, city: {n: 'City of Lynn Haven', g: 'city', school: false, m: 4}},
  fy: 'FY2026', second2026: 26411, navLabel: {LN: 'Lynn Haven stormwater assessment'}, shards: {ex: 96, nav: 128}};

test('tax estimate: district from the parcel, school tax on the school value, flat fees added', () => {
  const p = {DTAXDIST: '06', VASJUST: 300000, VASTOTAL: 250000, VASEXEMPT: 50000, VASTAXABLE: 200000, DEXEMPTS: 'HX HB'};
  const t = A.taxEstimate(D, p, 'Lynn Haven', [225000, 200000, 25000, 25000, 0], [['LN', 120]]);
  assert.equal(t.district, 'Lynn Haven');
  assert.ok(t.district_from_parcel);
  assert.equal(t.property_tax, Math.round(200 * 5 + 225 * 4 + 200 * 4));
  assert.equal(t.fees_total, 120);
  assert.equal(t.estimated_bill, t.property_tax + 120);
  assert.equal(t.fees[0].fee, 'Lynn Haven stormwater assessment');
  const u = A.taxEstimate(D, {...p, DTAXDIST: '99'}, null, null, []);
  assert.equal(u.district, 'unincorporated');
  assert.equal(u.district_from_parcel, false);
});

test('officials match one person on the same government, or nobody', () => {
  const people = [{person_id: 'doug-moore', name: 'Douglas Moore', gov_ids: ['county']}, {person_id: 'ann-moore', name: 'Ann Moore', gov_ids: ['lh']}];
  assert.equal(A.matchPerson(people, 'DOUG MOORE', 'county').person_id, 'doug-moore');
  assert.equal(A.matchPerson(people, 'Doug Moore', 'schools'), null);
  assert.equal(A.matchPerson(people, 'Moore', 'county'), null);
});

test('nearby rows read lat/lng or latitude/longitude and sort by distance', () => {
  const pt = {lat: 30.2, lon: -85.6};
  const r = A.nearRows([{name: 'far', lat: 30.5, lng: -85.6}, {name: 'b', latitude: 30.205, longitude: -85.6}, {name: 'a', lat: 30.201, lng: -85.6}, {name: 'none'}], pt, 2);
  assert.deepEqual(r.map(x => x.r.name), ['a', 'b']);
});

test('flood zones read in plain words', () => {
  assert.ok(A.floodText({FLD_ZONE: 'AE', SFHA_TF: 'T'}).high);
  assert.equal(A.floodText({FLD_ZONE: 'X', ZONE_SUBTY: '0.2 PCT ANNUAL CHANCE FLOOD HAZARD'}).zone, 'X (shaded)');
  assert.equal(A.floodText(null).zone, null);
});

// A fake map server: answers by layer path.
function fakeFetch(answers) {
  return async url => {
    const key = Object.keys(answers).find(k => url.includes(k));
    const feats = key ? answers[key] : [];
    return {json: async () => ({features: feats.map(a => ({attributes: a, geometry: a._g}))})};
  };
}

test('a full report: sections run, missing datasets are pending, failures stay inside their section', async () => {
  const answers = {
    'Admin_A12/MapServer/6': [{A1RENUM: '1', DTAXDIST: '06', DORAPPDESC: 'SINGLE FAMILY', S1YRBLTACT: 1998, VASJUST: 300000, VASTOTAL: 250000, VASEXEMPT: 0, VASTAXABLE: 250000, DEXEMPTS: '',
      SALE1DATE: '2021-05-01', SALE1PRADJ: 280000, SALE1QU_VI: 'Q - I', SALE2DATE: '2010-01-01', SALE2PRADJ: 90000, SALE2QU_VI: 'Q - I'}],
    'Admin_A12/MapServer/26': [{NAME: 'Lynn Haven'}],
    'Admin_A12/MapServer/80': [{EZONE: 'C'}],
    'NFHL/MapServer/28': [{FLD_ZONE: 'AE', SFHA_TF: 'T', STATIC_BFE: 9}],
    'Admin_A12/MapServer/28': [{NAME: 'District 1', REPNAME: 'DOUG MOORE'}],
  };
  const catalog = [{id: 'tax-districts'}, {id: 'property-tax-rates'}, {id: 'people-directory'}];
  const rows = {'people-directory': [{person_id: 'doug-moore', name: 'Douglas Moore', gov_ids: ['county']}]};
  const r = await A.build({lat: 30.24, lon: -85.65, address: '1 Test St'}, {fetchImpl: fakeFetch(answers), catalog, rows: async id => rows[id] || [], file: async f => (f.startsWith('/data/app') ? D : {}), mod: () => null});
  const S = id => r.sections.find(s => s.id === id);
  assert.equal(r.jurisdiction, 'City of Lynn Haven');
  assert.equal(S('property').status, 'ok');
  assert.deepEqual(S('property').data.sales.map(s => s.date), ['2021-05-01'], 'sales before 2016 are left out');
  assert.equal(S('tax').data.district, 'Lynn Haven');
  assert.equal(S('hazards').data.flood_zone, 'AE');
  assert.equal(S('hazards').data.evacuation_zone, 'C');
  assert.equal(S('utilities').status, 'pending', 'no utilities module or datasets yet');
  assert.equal(S('roads').status, 'pending', 'no sales-tax-projects in this catalog');
  const comm = S('officials').data.seats.find(x => x.office === 'County Commission');
  assert.equal(comm.entity_id, 'person:doug-moore');
  assert.ok(!JSON.stringify(r).match(/OWNAME|MAILADDR|GRNTR/));
});

test('a point outside the county is refused', async () => {
  await assert.rejects(A.build({lat: 25.7, lon: -80.2}, {catalog: [], rows: async () => [], file: async () => ({})}), /outside Bay County/);
});
