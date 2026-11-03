// Resident accounts (api/_account.js) and the nearby feed they show (api/_nearby.js). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
process.env.ALERTS_SECRET = process.env.ALERTS_SECRET || 'test-secret';
const A = require('../_account');
const N = require('../_nearby');
const E = require('../_emails');

const HOME = {lat: 30.245, lon: -85.648, city: 'Lynn Haven', zip: '32444', gov_id: 'lh', zone: 'B'};
const TODAY = '2026-10-28';
const D = {
  notices: [
    {notice_id: 'evac-b', kind: 'evacuation', zones: 'A, B', title: 'Evacuation order for zones A and B', status: 'active'},
    {notice_id: 'evac-c', kind: 'evacuation', zones: 'C', title: 'Evacuation order for zone C', status: 'active'},
    {notice_id: 'bw-pc', kind: 'boil-water', gov_id: 'pc', title: 'Boil water: Panama City, Harrison Ave', status: 'active'},
    {notice_id: 'bw-lh', kind: 'boil-water', gov_id: 'lh', title: 'Boil water: Lynn Haven, Ohio Ave', status: 'active'},
    {notice_id: 'wx', kind: 'weather', event: 'Wind Advisory', area: 'Coastal Bay', title: 'Wind Advisory', status: 'active'},
    {notice_id: 'old', kind: 'weather', event: 'Heat Advisory', status: 'ended'},
  ],
  meetings: [
    {board: 'lh', gov_id: 'lh', title: 'Regular Meeting', start: '2026-11-03T18:00:00', agenda_url: 'https://lh.example/agenda'},
    {board: 'pc', gov_id: 'pc', title: 'Regular Meeting', start: '2026-11-04'},
    {board: 'schools', gov_id: 'schools', title: 'School Board', start: '2026-11-05'},
    {board: 'county', gov_id: 'county', title: 'Commission', start: '2026-10-20'},
    {board: 'county', gov_id: 'county', title: 'Commission', start: '2026-12-30'},
  ],
  events: [
    {title: 'Weekly market', town: 'Panama City', starts: '2026-10-31T09:00:00', recurring: true},
    {title: 'Fall festival', town: 'Lynn Haven', starts: '2026-11-01T10:00:00', venue: 'Sharon Park'},
    {title: 'Past show', town: 'Lynn Haven', starts: '2026-10-01T10:00:00'},
  ],
  development: [{name: 'New homes', status: 'Approved', lat: 30.246, lng: -85.648, approved_date: '2026-10-01'}, {name: 'Far away', status: 'Approved', lat: 30.4, lng: -85.9}],
  salesTax: [{name: 'Ohio Ave drainage', status: 'in_progress', pct_complete: 40, lat: 30.2455, lng: -85.6485}, {name: 'Done job', status: 'completed', lat: 30.245, lng: -85.648}],
  roads: [{description: 'US 231 widening', status: 'Under way', agency: 'Florida Department of Transportation', lat: 30.25, lng: -85.65, vendor_id: 'abc'}],
  agenda: [{board: 'lh', title: 'Rezoning at 900 Ohio Ave', lat: 30.2452, lng: -85.6482, meeting_date: '2026-11-03'}],
  publicNotices: [{gov_id: 'lh', title: 'Budget hearing', published: '2026-10-20', kind_label: 'Hearing'}, {gov_id: 'mb', title: 'Other town', published: '2026-10-25'}],
  restaurants: [{license_number: '1', zip: '32444'}, {license_number: '2', zip: '32405'}],
  inspections: [
    {license_number: '1', business_name: 'GOOD DINER', date: '2026-10-25', result: 'Met standards', result_level: 'meets'},
    {license_number: '1', business_name: 'GOOD DINER', date: '2026-10-26', result: 'Closed', result_level: 'closed', high_priority: 3},
    {license_number: '2', business_name: 'OTHER ZIP', date: '2026-10-26', result_level: 'closed'},
  ],
  businesses: [{name: 'Ohio Ave Bakery LLC', zip: '32444', filed_date: '2026-10-10', entity_id: 'business:l1'}, {name: 'Old LLC', zip: '32444', filed_date: '2026-01-01'}],
  beachConditions: [{flag_color: 'Yellow', rip_current_risk: 'Moderate'}],
  beachAccess: [{latitude: 30.18, longitude: -85.8}],
  trash: [{service: 'Garbage', days: 'Tuesday'}],
};

test('alerts reach the home only when they apply to its zone or city', () => {
  const f = N.assemble(D, HOME, {today: TODAY});
  const ids = f.sections.find(s => s.id === 'alerts').items.map(i => i.id);
  assert.deepEqual(ids.sort(), ['bw-lh', 'evac-b', 'wx']);
  const noZone = N.assemble(D, {...HOME, zone: null}, {today: TODAY}).sections[0].items.map(i => i.id);
  assert.ok(!noZone.includes('evac-b'), 'an order naming zones never reaches a home outside every zone');
});

test('meetings are the home\'s county, school board and city, in the next two weeks', () => {
  const m = N.assemble(D, HOME, {today: TODAY}).sections.find(s => s.id === 'meetings').items;
  assert.deepEqual(m.map(x => x.gov_id), ['lh', 'schools']);
  assert.match(m[0].title, /^Lynn Haven City Commission/);
});

test('events: own town first, past events dropped', () => {
  const ev = N.assemble(D, HOME, {today: TODAY}).sections.find(s => s.id === 'events').items;
  assert.deepEqual(ev.map(x => x.title), ['Fall festival', 'Weekly market']);
  assert.equal(ev[0].in_town, true);
});

test('work nearby is within the radius, nearest first, finished work left out', () => {
  const p = N.assemble(D, HOME, {today: TODAY, radius_mi: 1}).sections.find(s => s.id === 'projects').items;
  assert.deepEqual(p.map(x => x.kind).sort(), ['agenda', 'development', 'road', 'sales-tax']);
  assert.ok(p.every((x, i) => i === 0 || p[i - 1].miles <= x.miles));
  assert.ok(!p.some(x => x.title === 'Far away' || x.title === 'Done job'));
  assert.equal(p.find(x => x.kind === 'road').entity_id, 'vendor:abc');
});

test('ZIP sections: closures first, other ZIPs and old filings left out; businesses link to profiles', () => {
  const f = N.assemble(D, HOME, {today: TODAY});
  const food = f.sections.find(s => s.id === 'food').items;
  assert.deepEqual(food.map(x => x.level), ['closed', 'meets']);
  assert.equal(food[0].title, 'Good Diner');
  const biz = f.sections.find(s => s.id === 'business');
  assert.equal(biz.count, 1);
  assert.equal(biz.items[0].url, 'https://baycounty.me/profile/business/l1');
});

test('topics turn sections off; alerts always show; beach flag only near a beach', () => {
  const f = N.assemble(D, HOME, {today: TODAY, topics: ['events']});
  assert.deepEqual(f.sections.map(s => s.id), ['alerts', 'events']);
  assert.equal(f.today_card.beach, null);
  const beachHome = N.assemble(D, {...HOME, lat: 30.185, lon: -85.8}, {today: TODAY, topics: []});
  assert.equal(beachHome.today_card.beach.flag, 'Yellow');
  assert.equal(f.local_government, 'City of Lynn Haven');
  assert.deepEqual(f.governments.map(g => g.gov_id), ['county', 'schools', 'lh']);
});

test('preferences are cleaned to known values', () => {
  const p = A.cleanPrefs({weekly_email: 'on', alert_email: ['evacuation', 'nukes'], push_topics: 'weather,agenda,spam', topics: ['events', 'x'], radius_mi: '2', is_admin: true});
  assert.deepEqual(p, {weekly_email: true, alert_email: ['evacuation'], push_topics: ['weather', 'agenda'], topics: ['events'], radius_mi: 2});
  assert.throws(() => A.cleanPrefs({radius_mi: 3}), /distances/);
  assert.deepEqual(A.cleanPrefs({}, {weekly_email: false}), {weekly_email: false});
});

test('tokens are signed; codes and sessions are only kept as hashes', () => {
  const t = A.makeToken({kind: 'link', e: 'a@b.example', n: 'x', exp: Date.now() + 60e3});
  assert.equal(A.readToken(t).e, 'a@b.example');
  assert.equal(A.readToken(t.slice(0, -2) + 'xx'), null);
  assert.equal(A.readToken(A.makeToken({kind: 'link', exp: Date.now() - 1})), null);
  assert.notEqual(A.hashCode('a@b.example', '123456'), A.hashCode('c@d.example', '123456'));
  assert.equal(A.hashSession('abc').length, 64);
  assert.match(A.manageUrl('u1'), /^https:\/\/baycounty\.me\/api\/account\?action=emails&t=/);
});

test('emails: sign-in code, weekly home email and emergency alert', () => {
  const c = E.accountCodeEmail('042137', 'https://baycounty.me/api/account?action=link&t=x');
  assert.match(c.subject, /^042137 /);
  assert.match(c.html, /042137/); assert.match(c.text, /15 minutes/);
  const f = N.assemble(D, HOME, {today: TODAY});
  const w = E.homeWeeklyEmail(f, {home: {address: '825 Ohio Ave', label: 'Home'}, name: 'Sam', manage: 'https://baycounty.me/m'});
  assert.match(w.subject, /^Your week near Lynn Haven: \d+ things to know$/);
  assert.match(w.html, /Hi Sam/); assert.match(w.html, /Fall festival/); assert.match(w.text, /https:\/\/baycounty\.me\/m/);
  assert.equal(E.homeWeeklyEmail({...f, sections: f.sections.map(s => ({...s, items: []}))}, {home: {address: 'x'}, manage: 'm'}), null);
  const a = E.homeAlertEmail({notice_id: 'evac-b', topic: 'evacuation', title: 'Evacuation order for zones A and B'}, {home: {address: '825 Ohio Ave', zone: 'B'}, manage: 'm'});
  assert.match(a.subject, /^Evacuation order for Zone B/);
  assert.match(a.html, /825 Ohio Ave/);
});

test('the nearby endpoint is documented, in the page map and never logs the address', () => {
  const v1 = require('../v1');
  assert.ok(v1.openapi({datasets: []}).paths['/nearby']);
  const P = require('../_pages');
  assert.deepEqual(P.PAGES['/account'].endpoints.includes('/nearby'), true);
  const src = require('fs').readFileSync(require.resolve('../v1'), 'utf8');
  assert.match(src, /parts\[0\] === 'address-report' \|\| parts\[0\] === 'nearby'/);
});

test('a new account gets one welcome email linking to the weekly email sign-up', async () => {
  const w = E.accountWelcomeEmail({weekly: 'https://baycounty.me/api/confirm?t=abc', manage: 'https://baycounty.me/m', name: 'Sam'});
  assert.equal(w.subject, 'Welcome to BayCounty.me');
  assert.match(w.html, /Hi Sam/); assert.match(w.html, /This week in Bay County/); assert.match(w.html, /api\/confirm\?t=abc/);
  assert.match(w.text, /api\/confirm\?t=abc/); assert.match(w.text, /https:\/\/baycounty\.me\/m/);

  // Fresh copy of _account with a stand-in database and Resend, to watch what sendWelcome does.
  const dbPath = require.resolve('../_db'), accPath = require.resolve('../_account');
  const realDb = require.cache[dbPath], realAcc = require.cache[accPath], realFetch = global.fetch, realKey = process.env.RESEND_API_KEY;
  const sends = new Set(), sql = [], mail = [];
  require.cache[dbPath] = {id: dbPath, filename: dbPath, loaded: true, exports: {hasDb: () => true, q: async (s, p) => {
    sql.push(s);
    if (/insert into account\.sends/.test(s)) { const k = p[0]; if (sends.has(k)) return []; sends.add(k); return [{id: 7}]; }
    return [];
  }}};
  delete require.cache[accPath];
  global.fetch = async (url, o) => { mail.push(JSON.parse(o.body)); return {ok: true, status: 200, json: async () => ({id: 're_1'})}; };
  process.env.RESEND_API_KEY = 'test';
  try {
    const A2 = require('../_account');
    const u = {id: 'u1', email: 'new@example.com', first_name: null};
    assert.equal(await A2.sendWelcome(u), true);
    assert.equal(await A2.sendWelcome(u), false, 'only once per account');
    assert.equal(mail.length, 1);
    assert.deepEqual(mail[0].to, ['new@example.com']);
    assert.match(mail[0].headers['List-Unsubscribe'], /action=emails/);
    const t = /api\/confirm\?t=([A-Za-z0-9._-]+)/.exec(mail[0].text)[1];
    const p = require('../_alerts').readToken(t);
    assert.deepEqual([p.e, p.g], ['new@example.com', ['week']], 'the link joins the countywide weekly list only after Confirm');
  } finally {
    if (realDb) require.cache[dbPath] = realDb; else delete require.cache[dbPath];
    if (realAcc) require.cache[accPath] = realAcc; else delete require.cache[accPath];
    global.fetch = realFetch;
    if (realKey === undefined) delete process.env.RESEND_API_KEY; else process.env.RESEND_API_KEY = realKey;
  }
  const src = require('fs').readFileSync(accPath, 'utf8');
  assert.equal((src.match(/if \(u\.created\) await sendWelcome\(u\);/g) || []).length, 2, 'code and one-tap sign-in both send it');
  assert.match(src, /\(xmax = 0\) as created/);
});
