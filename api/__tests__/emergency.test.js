// Tests for the emergency readers (api/_emergency.js), notifications (api/_push.js, api/_agenda_push.js) and which
// source a live notice belongs to (api/_emergency_run.js). No network or database. Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const E = require('../_emergency');
const P = require('../_push');
const A = require('../_agenda_push');
const {sourceKey} = require('../_emergency_run');
const {miles} = require('../_geo');

test('classify sorts notices by their title first', () => {
  assert.equal(E.classify('Precautionary Boil Water Notice - Manistee Dr'), 'boil-water');
  assert.equal(E.classify('Mandatory evacuation ordered for Zones A and B'), 'evacuation');
  assert.equal(E.classify('General population shelters opening at 2 p.m.'), 'shelter');
  assert.equal(E.classify('Road Closure: Thomas Drive at Front Beach Road'), 'road');
  assert.equal(E.classify('Water main break on 11th Street'), 'utility');
  assert.equal(E.classify('Sandbags available at three county sites'), 'storm');
  assert.equal(E.classify('City Commission meeting moved'), null);
  // the text decides only when the title doesn't
  assert.equal(E.classify('Update from Public Works', 'A precautionary boil water notice is in effect for...'), 'boil-water');
});

test('zonesIn reads every zone a notice names', () => {
  assert.deepEqual(E.zonesIn('Evacuation order for Zones A and B, and zone C mobile homes'), ['A', 'B', 'C']);
  assert.deepEqual(E.zonesIn('Zone A, B & D'), ['A', 'B', 'D']);
  assert.deepEqual(E.zonesIn('No zones mentioned'), []);
});

test('fl511Time turns FL511 times into local ISO times', () => {
  assert.equal(E.fl511Time('10/27/26, 1:05 PM'), '2026-10-27T13:05');
  assert.equal(E.fl511Time('1/2/26, 12:30 AM'), '2026-01-02T00:30');
  assert.equal(E.fl511Time('soon'), null);
});

test('parseShelters reads groups, status, date and each shelter', () => {
  const html = `<main><h2>Special Needs Shelters - CLOSED (current as of November 3, 2025)</h2>
    <p>Special needs shelters are for residents who registered ahead of time with the Florida Special Needs Registry.</p>
    <p>Breakfast Point Academy</p><p>601 N Richard Jackson Blvd, Panama City Beach, FL 32407</p>
    <h2>General Population Shelters -</h2><p>OPEN</p><p>(current as of October 9, 2026)</p>
    <p>Deane Bozeman School</p><p>13410 Highway 77, Panama City, FL 32409</p><p>Note: Pets in carriers only.</p></main>`;
  const g = E.parseShelters(html);
  assert.equal(g.length, 2);
  assert.equal(g[0].status, 'CLOSED');
  assert.equal(g[0].as_of, '2025-11-03');
  assert.equal(g[0].shelters[0].address, '601 N Richard Jackson Blvd, Panama City Beach, FL 32407');
  assert.ok(/registered ahead/.test(g[0].about));
  assert.equal(g[1].status, 'OPEN');
  assert.equal(g[1].as_of, '2026-10-09');
  assert.equal(g[1].shelters[0].note, 'Pets in carriers only.');
});

test('pushTopic sends only what is worth a notification', () => {
  assert.equal(E.pushTopic({status: 'active', kind: 'evacuation'}), 'evacuation');
  assert.equal(E.pushTopic({status: 'active', kind: 'boil-water'}), 'water');
  assert.equal(E.pushTopic({status: 'lifted', kind: 'boil-water'}), null);
  assert.equal(E.pushTopic({status: 'active', kind: 'road', full_closure: false}), null);
  assert.equal(E.pushTopic({status: 'active', kind: 'road', full_closure: true}), 'roads');
  assert.equal(E.pushTopic({status: 'active', kind: 'weather', event: 'Hurricane Warning'}), 'weather');
  assert.equal(E.pushTopic({status: 'active', kind: 'weather', event: 'Rip Current Statement'}), null);
});

test('notification text is short and links to the notice', () => {
  const m = P.message({notice_id: 'pcb:123', kind: 'boil-water', source: 'City of Panama City Beach', title: 'Precautionary Boil Water Notice - Manistee Dr'}, 'water');
  assert.equal(m.title, 'Boil-water notice · Panama City Beach');
  assert.equal(m.url, 'https://baycounty.me/emergency#n-pcb%3A123');
  assert.equal(m.critical, false);
  const w = P.message({notice_id: 'nws:1', kind: 'weather', event: 'Hurricane Warning', area: 'Coastal Bay; Inland Bay', severity: 'extreme', zones: 'A, B'}, 'weather');
  assert.equal(w.title, 'Hurricane Warning · Zones A, B');
  assert.equal(w.body, 'Hurricane Warning for Coastal Bay, Inland Bay');
  assert.equal(w.critical, true);
});

test('agenda notifications name the board and day, not an address line', () => {
  const m = A.message({record_hash: 'abc', board: 'pc', meeting_date: '2026-11-10', title: 'Site plan review', url: 'https://example.org/a.pdf'});
  assert.equal(m.notice_id, 'agenda:abc');
  assert.equal(m.topic, 'agenda');
  assert.equal(m.title, 'Near you: Panama City agenda, Nov 10');
  assert.ok(m.body.startsWith('Site plan review'));
  assert.ok(E.TOPICS.agenda);
});

test('a notice ends only when its own source answered without it', () => {
  assert.equal(sourceKey({source_type: 'nws'}), 'nws');
  assert.equal(sourceKey({source_type: 'alert-center', gov_id: 'pcb'}), 'alert:pcb');
  assert.equal(sourceKey({source_type: 'news', gov_id: 'county'}), 'news:county');
  assert.equal(sourceKey({source_type: 'fl511', event: 'Incident'}), 'fl511:Incidents');
});

test('miles is a great-circle distance', () => {
  const d = miles({lat: 30.1588, lng: -85.6602}, {lat: 30.2159, lng: -85.8555});
  assert.ok(d > 12 && d < 13, String(d));
});
