// End-to-end tests for /api/gov (the government workspace) against a real Postgres: migration 0088 plus small
// stand-ins for the public tables staff post into. Runs when FINANCE_TEST_DATABASE_URL is set (CI has a Postgres
// service); skipped otherwise. Also 0090 (maps on alerts and notices). The rule under test above all: staff never change record data, only flag it.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const URL_ = process.env.FINANCE_TEST_DATABASE_URL;
const opts = {skip: URL_ ? false : 'FINANCE_TEST_DATABASE_URL not set'};

let pool, q, handler, G;
let as = null;
const sent = [], runs = [];

function call(action, {method = 'GET', query = {}, body, headers = {}, caller} = {}) {
  return new Promise((resolve, reject) => {
    const res = {code: 200, headers: {}, setHeader(k, v) { this.headers[k] = v; }, status(c) { this.code = c; return this; },
      json(o) { resolve({status: this.code, body: o, headers: this.headers}); return this; }};
    (caller || handler)({method, query: {action, ...query}, headers, body}, res).catch(reject);
  });
}
const post = (action, body, ws = 'lh') => call(action, {method: 'POST', body: {workspace: ws, ...body}});
const get = (action, query = {}, ws = 'lh') => call(action, {query: {workspace: ws, ...query}});
const who = email => ({email, via: 'session'});

const STUBS = `
create schema govtest;
set search_path = govtest, public;
create table governments (key text primary key);
insert into governments values ('county'), ('lh'), ('pc');
create table public_notices (id bigint generated always as identity primary key, place_id text, notice_id text, published text, agency text, kind text, kind_label text,
  title text, event_date text, notice_type text, text text, pdf_url text, source_url text, gov_id text, government_key text, origin text not null default 'manual',
  record_hash text not null, created_at timestamptz default now(), updated_at timestamptz default now(), unique (origin, record_hash));
create table community_events (id bigint generated always as identity primary key, place_id text, event_id text, source_id text, source text, gov text, town text, title text,
  starts text, ends text, all_day boolean, venue text, category text, recurring boolean, cost text, url text, source_url text, gov_id text, government_key text,
  origin text not null default 'manual', record_hash text not null, created_at timestamptz default now(), updated_at timestamptz default now(), unique (origin, record_hash));
create table job_openings (id bigint generated always as identity primary key, place_id text, job_id text, board text, employer text, title text, department text, job_type text,
  pay text, posted text, closes text, url text, first_seen text, source_url text, gov_id text, government_key text, origin text not null default 'manual', record_hash text not null,
  created_at timestamptz default now(), updated_at timestamptz default now(), unique (origin, record_hash));
create table budget_years (id bigint generated always as identity primary key, gov_id text, fiscal_year integer, name text, amount numeric, source_url text,
  government_key text, origin text not null default 'manual', record_hash text not null, created_at timestamptz default now(), updated_at timestamptz default now());
create table emergency_live (notice_id text primary key);
insert into public_notices (place_id, notice_id, published, gov_id, title, text, origin, record_hash) values ('fl-bay', 'pn:1', '2026-10-01', 'lh', 'From the notice site', 'Read from records', 'site_build', 'h1');
insert into budget_years (gov_id, fiscal_year, name, amount, source_url, origin, record_hash) values ('lh', 2026, 'General Fund', 21500000, 'https://example.gov/budget.pdf', 'site_build', 'b1');
`;

test.before(async () => {
  if (!URL_) return;
  const {Pool} = require('pg');
  pool = new Pool({connectionString: URL_, max: 1});
  q = async (t, p = []) => (await pool.query(t, p)).rows;
  await q('drop schema if exists gov cascade');
  await q('drop schema if exists govtest cascade');
  await pool.query(STUBS);
  await pool.query(fs.readFileSync(path.join(__dirname, '../../db/migrations/0088_gov_workspace.sql'), 'utf8'));
  await pool.query(fs.readFileSync(path.join(__dirname, '../../db/migrations/0090_area_maps.sql'), 'utf8'));
  await q(`insert into gov.members (workspace_id, email, role) values ('lh', 'clerk@lh.test', 'publisher'), ('lh', 'chief@lh.test', 'alert_sender'),
    ('lh', 'mayor@lh.test', 'viewer'), ('lh', 'manager@lh.test', 'owner'), ('county', 'em1@county.test', 'alert_sender'), ('county', 'em2@county.test', 'alert_sender')`);
  G = require('../_gov');
  const {createHandler} = require('../gov');
  handler = createHandler({q, hasDb: () => true, caller: async () => as, sendEmail: async (to, m) => { sent.push({to, m}); },
    sendNow: async place => { runs.push(place); return {pushed: []}; }});
});
test.after(async () => { if (pool) { await q('drop schema if exists govtest cascade'); await pool.end(); } });

test('sign-in: codes only go to members, and a good code starts a session', opts, async () => {
  const real = require('../gov').createHandler({q, hasDb: () => true, caller: G.caller, sendEmail: async (to, m) => { sent.push({to, m}); }, sendNow: async () => ({})});
  const r1 = await call('login', {method: 'POST', body: {email: 'stranger@x.test'}, caller: real});
  assert.equal(r1.status, 200);
  assert.equal(sent.length, 0, 'no email for a non-member');
  await call('login', {method: 'POST', body: {email: 'clerk@lh.test'}, caller: real});
  assert.equal(sent.length, 1);
  const code = sent[0].m.text.match(/\d{6}/)[0];
  const bad = await call('verify', {method: 'POST', body: {email: 'clerk@lh.test', code: code === '000000' ? '111111' : '000000'}, caller: real});
  assert.equal(bad.status, 400);
  const ok = await call('verify', {method: 'POST', body: {email: 'clerk@lh.test', code}, caller: real});
  assert.equal(ok.status, 200, JSON.stringify(ok.body));
  const cookie = ok.headers['Set-Cookie'].split(';')[0];
  const me = await call('me', {headers: {cookie}, caller: real});
  assert.deepEqual(me.body.workspaces.map(w => [w.id, w.role]), [['lh', 'publisher']]);
  // A cookie request that changes something must carry the X-BCM-Gov header.
  const csrf = await call('post', {method: 'POST', headers: {cookie}, body: {workspace: 'lh', kind: 'notice', title: 'x', text: 'y'}, caller: real});
  assert.equal(csrf.status, 403);
  const withHdr = await call('post', {method: 'POST', headers: {cookie, 'x-bcm-gov': '1'}, body: {workspace: 'lh', kind: 'notice', title: 'Budget hearing', text: 'Hearing text'}, caller: real});
  assert.equal(withHdr.status, 200, JSON.stringify(withHdr.body));
  // Another government's workspace is not theirs.
  const other = await call('home', {query: {workspace: 'county'}, headers: {cookie}, caller: real});
  assert.equal(other.status, 404);
});

test('staff post, edit and withdraw their own notices; record rows are never editable', opts, async () => {
  as = who('clerk@lh.test');
  const p = await post('post', {kind: 'notice', title: 'Public hearing on Ordinance 1201', text: 'The City Commission will hold a hearing.', kind_: 'x', event_date: '2026-11-12'});
  assert.equal(p.status, 200, JSON.stringify(p.body));
  const [row] = await q(`select * from govtest.public_notices where id = $1`, [p.body.id]);
  assert.equal(row.origin, 'gov');
  assert.equal(row.gov_id, 'lh');
  assert.equal(row.government_key, 'lh');
  assert.equal(row.agency, 'City of Lynn Haven');
  const e = await post('post', {kind: 'notice', id: p.body.id, title: 'Public hearing on Ordinance 1201 (moved)', text: 'New date.'});
  assert.equal(e.status, 200);
  const [ingested] = await q(`select id from govtest.public_notices where origin = 'site_build'`);
  const e2 = await post('post', {kind: 'notice', id: ingested.id, title: 'Changed', text: 'Changed'});
  assert.equal(e2.status, 403, 'a row from records cannot be edited');
  const w2 = await post('withdraw', {kind: 'notice', id: ingested.id});
  assert.equal(w2.status, 403, 'a row from records cannot be withdrawn');
  assert.equal((await q(`select title from govtest.public_notices where id = $1`, [ingested.id]))[0].title, 'From the notice site');
  const list = await get('posts', {kind: 'notice'});
  assert.ok(list.body.posts.every(r => r.editable));
  assert.ok(list.body.from_records.every(r => !r.editable));
  const ev = await post('post', {kind: 'event', title: 'Fall Festival', starts: '2099-11-01T10:00', venue: 'Sheffield Park'});
  assert.equal(ev.status, 200, JSON.stringify(ev.body));
  const job = await post('post', {kind: 'job', title: 'Utility Worker I', url: 'http://not-https.test'});
  assert.equal(job.status, 400, 'links must be https');
  const pub = await G.publicPosts(q, {gov: 'lh'});
  assert.ok(pub.data.notices.some(n => n.title.includes('Ordinance 1201') && n.posted_by === 'City of Lynn Haven'));
  assert.ok(pub.data.events.some(n => n.title === 'Fall Festival'));
  const wd = await post('withdraw', {kind: 'event', id: ev.body.id});
  assert.equal(wd.status, 200);
});

test('roles: viewers read only, publishers cannot send alerts, owners manage people', opts, async () => {
  as = who('mayor@lh.test');
  assert.equal((await get('home')).status, 200);
  assert.equal((await post('post', {kind: 'notice', title: 'x', text: 'y'})).status, 403);
  as = who('clerk@lh.test');
  assert.equal((await post('alert', {kind: 'boil-water', title: 'x', message: 'y'})).status, 403);
  assert.equal((await post('members', {email: 'new@lh.test', role: 'viewer'})).status, 403);
  as = who('manager@lh.test');
  assert.equal((await post('members', {email: 'new@lh.test', role: 'viewer'})).status, 200);
  assert.equal((await get('activity')).status, 200);
});

test('alerts: a city alert goes out at once; countywide needs a second person', opts, async () => {
  as = who('chief@lh.test');
  const cw = await post('alert', {kind: 'evacuation', title: 'x', message: 'y', countywide: true});
  assert.equal(cw.status, 403, 'a city cannot send countywide');
  const a = await post('alert', {kind: 'boil-water', title: 'Boil-water notice for Highway 77', message: 'A main break on Highway 77.', instruction: 'Boil water for one minute.'});
  assert.equal(a.status, 200, JSON.stringify(a.body));
  assert.equal(a.body.alert.status, 'sent');
  assert.deepEqual(runs, ['fl-bay'], 'the emergency check ran right away');
  let live = await G.liveNotices(q, 'fl-bay');
  assert.equal(live.length, 1);
  assert.equal(live[0].notice_id, 'staff:' + a.body.alert.id);
  assert.equal(live[0].source_type, 'staff');
  assert.equal(live[0].gov_id, 'lh');
  const E = require('../_emergency');
  assert.equal(E.pushTopic(E.notice(live[0])), 'water');
  assert.equal(require('../_emergency_run').govFilter(live[0]), 'lh', 'a city alert goes only to phones following that city');

  as = who('em1@county.test');
  const c = await post('alert', {kind: 'evacuation', title: 'Evacuation order for Zone A', message: 'Leave now.', countywide: true}, 'county');
  assert.equal(c.body.alert.status, 'pending');
  assert.equal((await post('alert-confirm', {id: c.body.alert.id}, 'county')).status, 403, 'the same person cannot confirm');
  as = who('em2@county.test');
  const ok = await post('alert-confirm', {id: c.body.alert.id}, 'county');
  assert.equal(ok.status, 200, JSON.stringify(ok.body));
  live = await G.liveNotices(q, 'fl-bay');
  const county = live.find(n => n.notice_id === 'staff:' + c.body.alert.id);
  assert.equal(county.area, G.COUNTYWIDE);
  assert.equal(require('../_emergency_run').govFilter(county), null, 'countywide goes to every phone');

  as = who('chief@lh.test');
  const end = await post('alert-end', {id: a.body.alert.id});
  assert.equal(end.body.alert.status, 'ended');
  live = await G.liveNotices(q, 'fl-bay');
  assert.ok(!live.some(n => n.notice_id === 'staff:' + a.body.alert.id), 'an ended alert drops off the live list');
});

test('record data is read-only: staff flag it and BayCounty.me answers', opts, async () => {
  as = who('mayor@lh.test');
  const r = await get('records', {dataset: 'budget-years'});
  assert.equal(r.status, 200);
  assert.equal(r.body.read_only, true);
  assert.equal(r.body.rows.length, 1);
  assert.ok(!('record_hash' in r.body.rows[0]));
  const f = await post('flag', {dataset: 'budget-years', record_key: String(r.body.rows[0].id), field: 'amount', shown_value: '21500000', correct_value: '21,750,000',
    evidence_url: 'https://www.cityoflynnhaven.com/budget.pdf'});
  assert.equal(f.status, 200, JSON.stringify(f.body));
  assert.equal(Number((await q('select amount from govtest.budget_years'))[0].amount), 21500000, 'a flag never changes the record');
  const open = await G.adminFlags(q, 'open');
  assert.equal(open.flags.length, 1);
  await G.adminFlagReview(q, {id: open.flags[0].id, status: 'fixed', reply: 'The adopted budget was amended in March; updated.'}, 'jeremy@fluxlabs.net');
  const mine = await get('flags');
  assert.equal(mine.body.flags[0].status, 'fixed');
  assert.match(mine.body.flags[0].reply, /amended/);
  assert.equal((await get('records', {dataset: 'payroll'})).status, 400);
});

test('maps: pins, lines and areas are checked, kept on alerts and notices, and reach the live feed', async () => {
  const G2 = require('../_gov');
  const fc = (...features) => ({type: 'FeatureCollection', features});
  const pin = (x, y, r) => ({type: 'Feature', properties: r ? {radius_m: r} : {}, geometry: {type: 'Point', coordinates: [x, y]}});
  assert.equal(G2.areaShape(''), null);
  assert.equal(G2.areaShape(fc()), null);
  const out = JSON.parse(G2.areaShape(JSON.stringify(fc(pin(-85.6602349, 30.1588, 76),
    {type: 'Feature', geometry: {type: 'LineString', coordinates: [[-85.66, 30.16], [-85.65, 30.17]]}},
    {type: 'Feature', geometry: {type: 'Polygon', coordinates: [[[-85.6, 30.2], [-85.59, 30.2], [-85.59, 30.21]]]}}))));
  assert.deepEqual(out.features[0], {type: 'Feature', properties: {radius_m: 76}, geometry: {type: 'Point', coordinates: [-85.660235, 30.1588]}});
  assert.equal(out.features[2].geometry.coordinates[0].length, 4, 'an area is closed');
  assert.throws(() => G2.areaShape(fc(pin(-80.1, 25.8))), /in Bay County/);
  assert.throws(() => G2.areaShape(fc({type: 'Feature', geometry: {type: 'LineString', coordinates: [[-85.66, 30.16]]}})), /between 2/);
  assert.throws(() => G2.areaShape(fc({type: 'Feature', geometry: {type: 'MultiPoint', coordinates: []}})), /pins, lines and areas/);
  assert.throws(() => G2.areaShape('{not json'), /could not be read/);
  assert.equal(JSON.parse(G2.areaShape(fc(pin(-85.66, 30.16, 99999)))).features[0].properties.radius_m, 8000);
});

test('maps: a staff alert and a staff notice keep their map', opts, async () => {
  const map = JSON.stringify({type: 'FeatureCollection', features: [{type: 'Feature', properties: {radius_m: 150}, geometry: {type: 'Point', coordinates: [-85.66, 30.24]}}]});
  as = who('chief@lh.test');
  const a = await post('alert', {kind: 'boil-water', title: 'Boil water on Ohio Ave', message: 'A main broke.', geometry: map});
  assert.equal(a.status, 200, JSON.stringify(a.body));
  const live = await G.liveNotices(q, 'fl-bay');
  const n = live.find(x => x.title === 'Boil water on Ohio Ave');
  assert.equal(JSON.parse(n.geometry).features[0].properties.radius_m, 150);
  const badMap = await post('alert', {kind: 'road', title: 'x', message: 'y', geometry: '{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[-81,28]}}]}'});
  assert.equal(badMap.status, 400);
  as = who('clerk@lh.test');
  const p = await post('post', {kind: 'notice', title: 'Water main work on 5th St', text: 'Crews replace a pipe.', geometry: map});
  assert.equal(p.status, 200, JSON.stringify(p.body));
  const pub = await G.publicPosts(q, {kind: 'notice'});
  const row = pub.data.notices.find(r => r.title === 'Water main work on 5th St');
  assert.ok(row.geometry && JSON.parse(row.geometry).features.length === 1);
  // Editing without a map clears it.
  await post('post', {kind: 'notice', id: p.body.id, title: 'Water main work on 5th St', text: 'Done.', geometry: ''});
  const [r2] = await q('select geometry from public_notices where id = $1', [p.body.id]);
  assert.equal(r2.geometry, null);
});

test('staff alerts reach their own city, and everyone when countywide; general updates push', async () => {
  const E = require('../_emergency');
  const city = {source_type: 'staff', kind: 'safety', gov_id: 'lh', area: 'City of Lynn Haven', status: 'active'};
  assert.equal(E.reaches(city, {home: {gov_id: 'lh'}}), true);
  assert.equal(E.reaches(city, {home: {gov_id: 'pc'}}), false, 'a Lynn Haven safety alert does not reach a Panama City home');
  assert.equal(E.reaches(city, {areas: ['all']}), true);
  assert.equal(E.reaches({...city, gov_id: 'county', area: 'All of Bay County'}, {home: {gov_id: 'pc'}}), true);
  assert.equal(E.pushTopic({...city, kind: 'general'}), 'general');
  assert.equal(require('../_emergency_run').govFilter(city), 'lh');
});
