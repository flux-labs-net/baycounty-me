// Utilities lookup (api/_utilities.js): day names, and assembling one area's answer from what the map layers said.
const test = require('node:test');
const assert = require('node:assert');
const U = require('../_utilities');

const LH = 'https://example/lh/garbage';
const D = {
  providers: [
    {area: 'all', service: 'electric', service_label: 'Electricity', provider: 'Florida Power & Light (FPL)', entity_id: 'vendor:fpl'},
    {area: 'all', service: 'electric', service_label: 'Electricity', provider: 'Gulf Coast Electric Cooperative', entity_id: 'vendor:gulf-coast-electric-cooperative'},
    {area: 'all', service: 'garbage', service_label: 'Garbage', provider: 'A private hauler'},
    {area: 'lh', area_name: 'Lynn Haven', service: 'water', service_label: 'Water', provider: 'City of Lynn Haven', entity_id: 'gov:lh'},
    {area: 'lh', area_name: 'Lynn Haven', service: 'garbage', service_label: 'Garbage', provider: 'City of Lynn Haven', entity_id: 'gov:lh'},
  ],
  trash: [
    {area: 'lh', area_name: 'Lynn Haven', service: 'garbage', service_label: 'Garbage', provider: 'City of Lynn Haven', lookup_layer: LH, zone_field: 'Route', day_field: 'Day', zone: 'ROUTE-A', pickup_days: 'Monday'},
    {area: 'lh', area_name: 'Lynn Haven', service: 'garbage', service_label: 'Garbage', provider: 'City of Lynn Haven', lookup_layer: LH, zone_field: 'Route', day_field: 'Day', zone: 'ROUTE-E', pickup_days: 'Friday'},
    {area: 'mb', area_name: 'Mexico Beach', service: 'garbage', service_label: 'Garbage', provider: 'City of Mexico Beach', zone: 'West side', pickup_days: 'Monday, Thursday'},
    {area: 'mb', area_name: 'Mexico Beach', service: 'garbage', service_label: 'Garbage', provider: 'City of Mexico Beach', zone: 'East side', pickup_days: 'Tuesday, Friday'},
  ],
  holidays: [{area: 'lh', provider: 'City of Lynn Haven', holiday: 'Christmas Day', when_observed: 'December 25', garbage: 'No pickup', yard_waste: 'No pickup'}],
  rates: [{area: 'lh', provider: 'City of Lynn Haven', service: 'bill', charge: 'Typical monthly bill', amount: 129.76}],
};

test('normDays: map-layer day text to plain weekday names', () => {
  assert.equal(U.normDays('THURSDAY'), 'Thursday');
  assert.equal(U.normDays('Monday Only'), 'Monday');
  assert.equal(U.normDays('Monday, Thursday'), 'Monday, Thursday');
  assert.equal(U.normDays(''), null);
  assert.equal(U.normDays(null), null);
});

test('assemble: city rows replace countywide ones, route day comes from the map hit', () => {
  const r = U.assemble(D, 'lh', {hits: {[LH]: [{Route: 'ROUTE-E', Day: 'FRIDAY'}]}, coop: false});
  assert.equal(r.area_name, 'Lynn Haven');
  const garbage = r.services.find(s => s.service === 'garbage');
  assert.deepEqual(garbage.providers.map(p => p.provider), ['City of Lynn Haven']);
  const elec = r.services.find(s => s.service === 'electric');
  assert.deepEqual(elec.providers.map(p => p.provider), ['Florida Power & Light (FPL)'], 'co-op hidden when its territory does not cover the point');
  assert.equal(r.pickup.length, 1);
  assert.equal(r.pickup[0].zone, 'ROUTE-E');
  assert.equal(r.pickup[0].days, 'Friday');
  assert.equal(r.pickup[0].from_map, true);
  assert.equal(r.holidays.length, 1);
  assert.equal(r.rates[0].amount, 129.76);
});

test('assemble: co-op listed first where it maps the point; missing map answers say so', () => {
  const r = U.assemble(D, 'lh', {hits: {[LH]: null}, coop: true});
  assert.equal(r.services.find(s => s.service === 'electric').providers[0].provider, 'Gulf Coast Electric Cooperative');
  assert.equal(r.pickup[0].days, null);
  assert.match(r.pickup[0].rule, /didn't answer/);
  const off = U.assemble(D, 'lh', {hits: {[LH]: []}});
  assert.match(off.pickup[0].rule, /isn't on the city's route map/);
});

test('assemble: areas without a route map list every zone', () => {
  const r = U.assemble(D, 'mb', {});
  assert.deepEqual(r.pickup.map(p => [p.zone, p.days]), [['West side', 'Monday, Thursday'], ['East side', 'Tuesday, Friday']]);
  assert.deepEqual(r.services.find(s => s.service === 'garbage').providers.map(p => p.provider), ['A private hauler']);
});

test('lookup: rejects points outside the county before any map call', async () => {
  let called = false;
  const f = async () => { called = true; throw new Error('no'); };
  await assert.rejects(U.lookup(D, {lat: '40', lon: '-75'}, f), e => e.status === 404);
  await assert.rejects(U.lookup(D, {}, f), e => e.status === 400);
  assert.equal(called, false);
});

test('lookup: city from the boundary layer, route from the route layer', async () => {
  const f = async url => {
    const u = String(url);
    const feats = u.includes('BayView') ? [{attributes: {NAME: 'Lynn Haven'}}] : u.startsWith(LH) ? [{attributes: {Route: 'ROUTE-A', Day: 'MONDAY'}}] : [];
    return {ok: true, json: async () => ({features: feats})};
  };
  const r = await U.lookup(D, {lat: '30.245', lon: '-85.648'}, f);
  assert.equal(r.area, 'lh');
  assert.equal(r.pickup[0].days, 'Monday');
  assert.deepEqual(r.point, {lat: 30.245, lon: -85.648});
});
