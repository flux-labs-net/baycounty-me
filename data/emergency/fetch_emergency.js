#!/usr/bin/env node
// Daily emergency-hub refresh (run in refresh-meetings.yml, or by hand: node data/emergency/fetch_emergency.js [place]).
// Writes, under data/emergency/<county>/:
//   shelters.json   Bay County's shelter list and status, with each shelter's map point and evacuation zone
//   zones_geo.json  the evacuation zone shapes (simplified) from the county GIS layer
//   notices.json    the notice archive: every weather alert, boil-water notice, road closure and storm update seen,
//                   merged by notice_id (first_seen / last_seen). Adds the last week of weather alerts and whatever the
//                   live poller stored (emergency_live, public read) so short notices between daily runs are kept.
// One failing source keeps yesterday's file for that part and exits 0 after printing the error.
const fs = require('fs');
const path = require('path');
const E = require('../../api/_emergency');

const PLACE = process.argv[2] || process.env.PLACE_ID || 'fl-bay';
const DIR = path.join(__dirname, PLACE.split('-').slice(1).join('-'));
const FIRST_YEAR = 2016; // the site's first year (data/entities/cutoff.py)
const DB_URL = process.env.SUPABASE_URL || 'https://azdgwljijievtsrydxsp.supabase.co';
const DB_KEY = process.env.SUPABASE_PUBLISHABLE_KEY || 'sb_publishable_Z2KjpNqiFYGhcXEA0j-ODw_2fa9xopr';

const read = (f, d) => { try { return JSON.parse(fs.readFileSync(path.join(DIR, f), 'utf8')); } catch (e) { return d; } };
const write = (f, v, indent = 1) => fs.writeFileSync(path.join(DIR, f), JSON.stringify(v, null, indent) + '\n');
const today = () => new Date().toLocaleDateString('en-CA', {timeZone: E.placeConfig(PLACE).timezone});
const problems = [];

async function sheltersPart() {
  const old = read('shelters.json', {shelters: []});
  const prev = new Map(old.shelters.map(s => [s.shelter_id, s]));
  const rows = await E.shelters(PLACE);
  for (const r of rows) {
    const p = prev.get(r.shelter_id);
    if (p && p.address === r.address && p.lat) Object.assign(r, {lat: p.lat, lng: p.lng, evacuation_zone: p.evacuation_zone});
    else {
      const g = r.address ? await E.geocode(r.address, PLACE).catch(() => null) : null;
      r.lat = g ? +g.lat.toFixed(6) : null; r.lng = g ? +g.lng.toFixed(6) : null;
      r.evacuation_zone = g ? await E.zoneAt(g.lat, g.lng, PLACE).catch(() => null) : null;
    }
  }
  write('shelters.json', {_about: 'Written by data/emergency/fetch_emergency.js from Bay County\'s Emergency Shelters page. lat/lng from the county\'s address points; evacuation_zone from its zone map.',
    checked: today(), source_url: E.placeConfig(PLACE).shelters.page, shelters: rows});
  return rows.length;
}

async function zonesPart() {
  const z = await E.zoneGeometry(PLACE);
  if (!z.length) throw new Error('zone layer returned no shapes');
  write('zones_geo.json', {_about: 'Bay County evacuation zone shapes, simplified to about 300 m, from the county GIS layer. Written by fetch_emergency.js.',
    checked: today(), source_url: E.placeConfig(PLACE).zones.layer, zones: z}, 0);
  return z.length;
}

async function liveRows() {
  const cols = 'notice_id,place_id,kind,source,source_type,gov_id,title,summary,instruction,severity,event,area,zones,issued,starts,ends,updated,status,full_closure,roadway,url,source_url,first_seen,last_seen';
  const r = await fetch(`${DB_URL}/rest/v1/emergency_live?select=${cols}&place_id=eq.${PLACE}&order=last_seen.desc&limit=2000`, {headers: {apikey: DB_KEY}});
  if (!r.ok) throw new Error(`emergency_live ${r.status}`);
  return r.json();
}

async function noticesPart() {
  const old = read('notices.json', {notices: []});
  const by = new Map(old.notices.map(n => [n.notice_id, n]));
  const now = new Date().toISOString();
  const live = await E.readAll(PLACE);
  problems.push(...live.errors.map(e => `${e.source}: ${e.error}`));
  const recent = await E.nwsRecent(PLACE).catch(e => { problems.push('nws recent: ' + e.message); return []; });
  const stored = await liveRows().catch(e => { problems.push('emergency_live: ' + e.message); return []; });
  const activeNow = new Set(live.notices.filter(n => n.status === 'active').map(n => n.notice_id));
  const add = (n, seenAt) => {
    if (String(n.issued || n.updated || now).slice(0, 4) < String(FIRST_YEAR)) return;
    const p = by.get(n.notice_id);
    const {first_seen: fs0, last_seen: ls0, ...rest} = n;
    const first = [p && p.first_seen, fs0, seenAt].filter(Boolean).sort()[0];
    const last = [p && p.last_seen, ls0, seenAt].filter(Boolean).sort().pop();
    by.set(n.notice_id, {...(p || {}), ...rest, first_seen: first, last_seen: last});
  };
  for (const n of stored) add(n, null);
  for (const n of recent) add(n, null);
  for (const n of live.notices) add(n, now);
  // status in the archive: active only if it was live at this run; otherwise it has ended (or was lifted).
  const rows = [...by.values()].map(n => ({...n, status: activeNow.has(n.notice_id) ? 'active' : n.status === 'lifted' ? 'lifted' : 'ended'}))
    .sort((a, b) => String(b.issued || b.first_seen).localeCompare(String(a.issued || a.first_seen)));
  write('notices.json', {_about: 'Every emergency notice BayCounty.me has seen for this place: weather alerts, boil-water notices, road closures, utility and storm updates. Written by data/emergency/fetch_emergency.js; the live list is /api/v1/emergency.',
    checked: today(), notices: rows});
  return rows.length;
}

(async () => {
  fs.mkdirSync(DIR, {recursive: true});
  for (const [name, fn] of [['shelters', sheltersPart], ['zones', zonesPart], ['notices', noticesPart]]) {
    try { console.log(`${name}: ${await fn()}`); } catch (e) { problems.push(`${name}: ${e.message}`); }
  }
  if (problems.length) console.error('Problems (yesterday\'s data kept where a part failed):\n  ' + problems.join('\n  '));
})();
