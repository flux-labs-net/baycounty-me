// Tests for placing road closure posts on a map from the streets they name (api/_road_map.js). No network: the county
// street layer is a small made-up grid. Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const R = require('../_road_map');
const {mapOf} = require('../_emergency_feed');

test('stretches reads the street names out of city road posts', () => {
  const s = n => R.stretches(n).map(x => [x.main, x.from, x.to].map(t => t && [t.dir, t.name, t.type].filter(Boolean).join(' ')));
  assert.deepEqual(s({title: 'Road Closure Notice: 10th Street just west of W. Caroline Boulevard to Lisenby Avenue'}), [['10TH ST', 'W CAROLINE BLVD', 'LISENBY AVE']]);
  assert.deepEqual(s({title: 'Road Closure Notice: Michigan Ave. between W 22nd St. and W 20th Ct.'}), [['MICHIGAN AVE', 'W 22ND ST', 'W 20TH CT']]);
  // A title that names one corner gives way to the stretches listed in the text.
  assert.deepEqual(s({title: 'Florida Avenue & W. 7th Street Closure', summary: 'Beginning Monday, October 5, the following sections will be closed to vehicle traffic: - Florida Avenue: W. 7th Street to W. 8th Street - W. 7th Street: Ohio Avenue to Florida Avenue Detour signs will be in place'}),
    [['FLORIDA AVE', 'W 7TH ST', 'W 8TH ST'], ['W 7TH ST', 'OHIO AVE', 'FLORIDA AVE']]);
  assert.deepEqual(s({title: 'Road Closure: Thomas Drive at Front Beach Road'}), [['THOMAS DR', 'FRONT BEACH RD', null]]);
  assert.deepEqual(s({title: 'US 98 closed from SR 77 to Airport Rd'}), [['98', '77', 'AIRPORT RD']]);
  assert.deepEqual(s({title: 'Hurricane Isaias Emergency Information'}), []);
});

// Michigan Ave runs north-south at -85.70; 22nd St and 20th Ct cross it east-west. The same names in another city are
// far away, and only the posting city's are used.
const V = (lng, a, b) => Array.from({length: 11}, (_, i) => [lng, a + (b - a) * i / 10]);
const H = (lat, a, b) => [[a, lat], [b, lat]];
const LAYER = {
  MICHIGAN: [{attributes: {POSTTYPE: 'AVE', LCOMM: 'PANAMA CITY', RCOMM: 'PANAMA CITY'}, geometry: {paths: [V(-85.70, 30.18, 30.19), V(-85.70, 30.19, 30.20)]}},
    {attributes: {POSTTYPE: 'AVE', LCOMM: 'LYNN HAVEN', RCOMM: 'LYNN HAVEN'}, geometry: {paths: [V(-85.65, 30.24, 30.26)]}}],
  '22ND': [{attributes: {POSTTYPE: 'ST', LCOMM: 'PANAMA CITY', RCOMM: 'PANAMA CITY'}, geometry: {paths: [H(30.184, -85.71, -85.69)]}},
    {attributes: {POSTTYPE: 'CT', LCOMM: 'PANAMA CITY', RCOMM: 'PANAMA CITY'}, geometry: {paths: [H(30.199, -85.71, -85.69)]}}],
  '20TH': [{attributes: {POSTTYPE: 'CT', LCOMM: 'PANAMA CITY', RCOMM: 'PANAMA CITY'}, geometry: {paths: [H(30.193, -85.71, -85.69)]}}],
};
const cfg = {roads: {layer: 'https://gis.example/roads', communities: {pc: 'PANAMA CITY'}}};
const fakeGet = async url => {
  const name = /NAME = '([^']+)'/.exec(decodeURIComponent(url))[1];
  return {features: LAYER[name] || []};
};

test('streetMap draws the closed street between its cross streets', async () => {
  const g = JSON.parse(await R.streetMap({gov_id: 'pc', title: 'Road Closure Notice: Michigan Ave. between W 22nd St. and W 20th Ct.'}, cfg, fakeGet));
  assert.equal(g.features.length, 1);
  const f = g.features[0];
  assert.equal(f.geometry.type, 'LineString');
  assert.equal(f.properties.placed, 'street-names');
  const lats = f.geometry.coordinates.map(c => c[1]);
  assert.ok(Math.abs(Math.min(...lats) - 30.184) < 0.0005 && Math.abs(Math.max(...lats) - 30.193) < 0.0005, lats.join());
  assert.ok(f.geometry.coordinates.every(c => Math.abs(c[0] + 85.70) < 1e-6), 'stays on Michigan Ave');
});

test('streetMap gives a pin for a corner and the empty map when it cannot place a post', async () => {
  const pin = JSON.parse(await R.streetMap({gov_id: 'pc', title: 'Michigan Ave & W 22nd St Closure'}, cfg, fakeGet));
  assert.deepEqual(pin.features[0].geometry, {type: 'Point', coordinates: [-85.7, 30.184]});
  assert.equal(pin.features[0].properties.radius_m, 60);
  assert.equal(await R.streetMap({gov_id: 'pc', title: 'Road Closure Notice: Nowhere St between A St and B St'}, cfg, fakeGet), R.NONE);
  assert.equal(await R.streetMap({gov_id: 'pc', title: 'Parade Saturday'}, cfg, fakeGet), R.NONE);
  // The street layer down: no map yet, so the next check tries again.
  assert.equal(await R.streetMap({gov_id: 'pc', title: 'Michigan Ave between W 22nd St and W 20th Ct'}, cfg, async () => { throw new Error('down'); }), null);
});

test('FL511 closures get their start and end pins', () => {
  const g = JSON.parse(R.fl511Map([[30.2, -85.6], [30.21, -85.61]]));
  assert.deepEqual(g.features.map(f => f.geometry.coordinates), [[-85.6, 30.2], [-85.61, 30.21]]);
  assert.ok(g.features.every(f => f.properties.placed === 'fl511'));
  assert.equal(JSON.parse(R.fl511Map([[30.2, -85.6], null])).features.length, 1);
  assert.equal(R.fl511Map(undefined), null);
});

test('readers never get the empty "looked, found none" map', () => {
  assert.equal(mapOf(R.NONE), null);
  assert.equal(mapOf(null), null);
  const g = R.fl511Map([[30.2, -85.6], null]);
  assert.equal(mapOf(g), g);
});
