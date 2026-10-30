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
  assert.equal(sourceKey({source_type: 'status-page', gov_id: 'sp'}), 'page:sp');
});

test('miles is a great-circle distance', () => {
  const d = miles({lat: 30.1588, lng: -85.6602}, {lat: 30.2159, lng: -85.8555});
  assert.ok(d > 12 && d < 13, String(d));
});

test('phone sign-up needs an account: /api/push refuses a sign-up and only removes phones', async () => {
  const push = require('../push');
  const call = async (method, body) => {
    const res = {code: 0, body: null, headers: {}, setHeader(k, v) { this.headers[k] = v; }, status(c) { this.code = c; return this; }, json(b) { this.body = b; return this; }};
    await push({method, body, headers: {}, socket: {}}, res);
    return res;
  };
  const r = await call('POST', {token: 'a'.repeat(64), platform: 'ios', topics: ['weather']});
  assert.equal(r.code, 401);
  assert.equal(r.body.signed_out, true);
  assert.equal((await call('GET')).code, 200);
});

test('a status page is a notice only when it says one is in effect', () => {
  const page = {gov: 'sp', name: 'City of Springfield', kind: 'boil-water', page: 'https://example.gov/pbwn', none: '\\b(currently|presently) no\\b[^.]*\\b(PBWN|boil)'};
  const html = t => `<nav><div class="field--name-body"><p>menu</p></div></nav><article class="node node--type-page"><div class="field field--name-body">${t}</div>
    <div class="print__wrapper">View PDF</div></article>`;
  assert.equal(E.statusPageText(html('<p>There is currently no PBWN in the City of Springfield.</p>')), 'There is currently no PBWN in the City of Springfield.');
  assert.deepEqual(E.statusPageNotice('There is currently no PBWN in the City of Springfield.', page, 'fl-bay'), []);
  const [n] = E.statusPageNotice(E.statusPageText(html('<p>Precautionary Boil Water Notice for Oak Ave</p><p>Boil water before drinking until further notice.</p>')), page, 'fl-bay');
  assert.equal(n.kind, 'boil-water');
  assert.equal(n.status, 'active');
  assert.equal(n.gov_id, 'sp');
  assert.equal(n.title, 'Precautionary Boil Water Notice for Oak Ave');
  assert.match(n.notice_id, /^page:sp:[0-9a-f]{10}$/);
  assert.equal(E.pushTopic(n), 'water');
});

test('two boil notices with the same title from one feed are both kept', () => {
  const feed = {gov: 'cw', name: 'City of Callaway'};
  const items = E.parseRss(`<item><title>PRECAUTIONARY BOIL WATER NOTICE</title><link>https://x.gov/CivicAlerts.aspx?AID=2157</link><description>Olokee St.</description></item>
    <item><title>PRECAUTIONARY BOIL WATER NOTICE</title><link>https://x.gov/CivicAlerts.aspx?AID=2156</link><description>Nelle Street. The post X appeared first on Y.</description></item>`);
  const ns = E.rssNotices(items, feed, 'fl-bay', 'news');
  assert.deepEqual(ns.map(n => n.notice_id), ['news:cw:2157', 'news:cw:2156']);
  assert.equal(ns[1].summary, 'Nelle Street.');
});

test('CivicPlus feed times are local clock times', () => {
  assert.equal(E.localTime('Wed, 28 Oct 2026 13:48:00 -0600', 'America/Chicago'), '2026-10-28T18:48:00.000Z'); // daylight time
  assert.equal(E.localTime('Mon, 07 Dec 2026 09:00:00 -0600', 'America/Chicago'), '2026-12-07T15:00:00.000Z'); // standard time
  const [n] = E.rssNotices(E.parseRss('<item><title>Boil water notice</title><link>https://x.gov/CivicAlerts.aspx?AID=1</link><pubDate>Wed, 28 Oct 2026 13:48:00 -0600</pubDate></item>'),
    {gov: 'cw', name: 'Callaway', url: 'https://x.gov/RSSFeed.aspx?ModID=1'}, 'fl-bay', 'news');
  assert.equal(n.issued, '2026-10-28T18:48:00.000Z');
});

test('Apple failure reasons are read from the answer body', () => {
  assert.equal(P.apnsReason({status: 400, data: '{"reason":"BadDeviceToken"}'}), 'BadDeviceToken');
  assert.equal(P.apnsReason({status: 0}), null);
  assert.equal(P.apnsReason({status: 500, data: 'oops'}), null);
});

test('push send reports Apple and Google reasons without crashing', async () => {
  const r = await P.send([], {title: 't', body: 'b', topic: 'test', notice_id: 'test', url: 'https://baycounty.me'});
  assert.deepEqual(r, {delivered: 0, failed: 0, skipped: 0, dead: [], reasons: []});
});

// A CAP 1.2 alert as IPAWS serves it (trimmed). Bay County shelter-in-place sent through Everbridge.
const cap = ({sender = 'everbridge@baycountyfl.gov', code = 'SPW', same = '012005', status = 'Actual', msgType = 'Alert', sev = 'Severe'} = {}) => `<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2"><identifier>EVB-12005-0001</identifier><sender>${sender}</sender><sent>2026-10-30T09:15:00-05:00</sent>
<status>${status}</status><msgType>${msgType}</msgType><scope>Public</scope>
<info><language>en-US</language><category>Safety</category><event>Shelter in Place Warning</event><urgency>Immediate</urgency><severity>${sev}</severity><certainty>Observed</certainty>
<eventCode><valueName>SAME</valueName><value>${code}</value></eventCode><effective>2026-10-30T09:15:00-05:00</effective><expires>2026-10-30T12:15:00-05:00</expires>
<senderName>Bay County Emergency Management</senderName><headline>Shelter in place near Highway 231 &amp; Transmitter Rd</headline>
<description>A chemical leak was reported near Highway 231.</description><instruction>Stay indoors and close windows.</instruction>
<area><areaDesc>Bay, FL</areaDesc><geocode><valueName>SAME</valueName><value>${same}</value></geocode></area></info></alert>`;

test('IPAWS alerts for Bay County become notices; tests, NWS and other counties do not', () => {
  const cfg = E.placeConfig('fl-bay');
  const p = E.parseCap(cap());
  assert.equal(p.identifier, 'EVB-12005-0001');
  assert.equal(p.info[0].eventCode, 'SPW');
  assert.deepEqual(p.info[0].areas[0].same, ['012005']);
  const n = E.ipawsNotice(p, 'fl-bay', cfg);
  assert.equal(n.notice_id, 'ipaws:EVB-12005-0001');
  assert.equal(n.kind, 'safety');
  assert.equal(n.gov_id, 'county');
  assert.equal(n.severity, 'severe');
  assert.equal(n.title, 'Shelter in place near Highway 231 & Transmitter Rd');
  assert.equal(n.issued, '2026-10-30T14:15:00.000Z');
  assert.equal(n.status, 'active');
  assert.equal(E.pushTopic(n), 'safety');
  assert.equal(sourceKey(n), 'ipaws');
  assert.equal(E.ipawsNotice(E.parseCap(cap({code: 'EVI'})), 'fl-bay', cfg).kind, 'evacuation');
  assert.equal(E.ipawsNotice(E.parseCap(cap({same: '012000'})), 'fl-bay', cfg).kind, 'safety', 'statewide alerts (AMBER) count');
  assert.equal(E.ipawsNotice(E.parseCap(cap({same: '012133'})), 'fl-bay', cfg), null, 'Washington County only');
  assert.equal(E.ipawsNotice(E.parseCap(cap({code: 'RWT'})), 'fl-bay', cfg), null, 'weekly test');
  assert.equal(E.ipawsNotice(E.parseCap(cap({status: 'Exercise'})), 'fl-bay', cfg), null);
  assert.equal(E.ipawsNotice(E.parseCap(cap({sender: 'w-nws.webmaster@noaa.gov'})), 'fl-bay', cfg), null, 'the NWS reader has these');
  assert.equal(E.ipawsNotice(E.parseCap(cap({msgType: 'Cancel'})), 'fl-bay', cfg).status, 'lifted');
});

test('the alert timeline sums reach per notice (admin only), filters by government and sorts newest first', () => {
  const F = require('../_emergency_feed');
  const notices = [
    {notice_id: 'a', kind: 'boil-water', title: 'Boil notice', gov_id: 'lh', issued: '2026-10-28T10:00:00Z', active: false, last_seen: '2026-10-29T10:00:00Z', status: 'lifted',
      versions: [{notice_id: 'a'}, {notice_id: 'a2'}]},
    {notice_id: 'b', kind: 'weather', title: 'Flood Advisory', gov_id: null, issued: '2026-10-29T10:00:00Z', active: true, status: 'active'},
    {notice_id: 'c', kind: 'road', title: 'PCB road closed', gov_id: 'pcb', issued: '2026-10-27T10:00:00Z', active: false, last_seen: '2026-10-27T12:00:00Z', status: 'active'},
  ];
  const reach = [{notice_id: 'a', channel: 'push', people: 5}, {notice_id: 'a2', channel: 'email', people: 7}, {notice_id: 'b', channel: 'push', people: 3}];
  const pub = F.buildTimeline(notices, reach, {days: 30});
  assert.equal(pub.reached, undefined, 'public timeline has no send counts');
  assert.ok(pub.items.every(i => !('reach' in i) && !('people' in i)), 'nor do its items');
  const g = '{"type":"FeatureCollection","features":[]}';
  assert.equal(F.buildTimeline([{...notices[0], geometry: g}], [], {}).items[0].geometry, g, 'the staff-drawn map comes along');
  const t = F.buildTimeline(notices, reach, {days: 30, admin: true});
  assert.deepEqual(t.items.map(i => i.notice_id), ['b', 'a', 'c']);
  assert.deepEqual(t.items[1].reach, {push: 5, email: 7, sms: 0}, 'reach of earlier versions counts');
  assert.equal(t.items[1].status, 'lifted');
  assert.equal(t.items[1].ended, '2026-10-29T10:00:00Z');
  assert.equal(t.items[0].ended, null);
  assert.equal(t.items[2].status, 'ended');
  assert.equal(t.reached, 15);
  assert.deepEqual(F.buildTimeline(notices, reach, {gov: 'lh'}).items.map(i => i.notice_id), ['b', 'a'], 'Lynn Haven plus countywide');
  assert.deepEqual(F.buildTimeline(notices, reach, {kind: 'road'}).items.map(i => i.notice_id), ['c']);
});

test('alert areas: who a notice reaches', () => {
  const lhBoil = {kind: 'boil-water', gov_id: 'lh', status: 'active'};
  const evacA = {kind: 'evacuation', zones: 'A', status: 'active'};
  const home = {gov_id: 'pc', zone: 'B'};
  assert.equal(E.reaches(lhBoil, {home}), false, 'a Panama City home does not get Lynn Haven boil notices');
  assert.equal(E.reaches(lhBoil, {areas: ['lh'], home}), true, 'unless it follows Lynn Haven');
  assert.equal(E.reaches(lhBoil, {areas: ['all'], home}), true);
  assert.equal(E.reaches(lhBoil, {}), true, 'no home and no areas: everything');
  assert.equal(E.reaches({...lhBoil, gov_id: 'county'}, {areas: ['pcb']}), true, 'county notices always come');
  assert.equal(E.reaches(evacA, {home}), false, 'zone B home, zone A order');
  assert.equal(E.reaches(evacA, {home: {zone: 'A'}}), true);
  assert.equal(E.reaches(evacA, {areas: ['pc']}), true, 'no home: every order');
  assert.equal(E.reaches({kind: 'weather', status: 'active'}, {areas: ['mb'], home}), true);
  assert.equal(E.pushTopic({kind: 'utility', status: 'active'}), 'outages');
  assert.equal(E.pushTopic({kind: 'storm', status: 'active'}), 'general');
  assert.ok(E.isUrgent({severity: 'moderate'}, 'evacuation'));
  assert.ok(!E.isUrgent({severity: 'moderate'}, 'water'));
  assert.ok(E.isUrgent({severity: 'severe'}, 'safety'));
  assert.equal(E.quietNow(Date.parse('2026-10-30T04:00:00Z')), true, '11 PM Central');
  assert.equal(E.quietNow(Date.parse('2026-10-30T17:00:00Z')), false, 'noon Central');
  const quiet = JSON.parse(P.apnsPayload({title: 't', body: 'b', topic: 'water', notice_id: 'x', quiet: true}));
  assert.equal(quiet.aps.sound, undefined);
  assert.equal(quiet.aps['interruption-level'], 'passive');
  assert.equal(JSON.parse(P.apnsPayload({title: 't', body: 'b', topic: 'water', notice_id: 'x'})).aps.sound, 'default');
});

test('an admin removes a test alert: hidden everywhere, logged, staff alert marked removed', async () => {
  const G = require('../_gov');
  const calls = [];
  const q = async (sql, params) => {
    calls.push([sql.replace(/\s+/g, ' ').trim(), params]);
    if (/update emergency_live/.test(sql)) return [{notice_id: 'staff:1', title: 'Boil Water Notice (TEST)', gov_id: 'lh'}];
    if (/update gov.alerts/.test(sql)) return [{id: 1, workspace_id: 'lh'}];
    return [];
  };
  await assert.rejects(G.adminRemoveAlert(q, {notice_id: 'staff:1'}, 'a@b.c'), /why/, 'a reason is required');
  const r = await G.adminRemoveAlert(q, {notice_id: 'staff:1', note: 'test post'}, 'a@b.c');
  assert.deepEqual(r, {ok: true, notice_id: 'staff:1', removed: true});
  assert.ok(calls.some(([s, p]) => /set removed_at = now\(\)/.test(s) && p[1] === 'a@b.c' && p[2] === 'test post'));
  assert.ok(calls.some(([s]) => /set status = 'removed'/.test(s)));
  assert.ok(calls.some(([s, p]) => /insert into gov.activity/.test(s) && p.includes('alert_removed')), 'logged for the government');
  assert.ok(calls.some(([s]) => /delete from emergency_notices/.test(s)), 'off the archive table');
  assert.ok(!calls.some(([s]) => /delete from (emergency_live|gov\.alerts)/.test(s)), 'nothing in the record is deleted');
});
