// What's happening near one place: GET /api/v1/nearby, the MCP tool whats_happening_near, the signed-in "My home" page
// (/account) and the apps' My home screen, and the Monday "Your home this week" email (api/_account.js).
//
// assemble() is pure: it takes rows from public datasets plus the place (point, city, ZIP, evacuation zone) and returns
// sections of short items, each linking to its public record. feed() reads the datasets and the live layers
// (emergency notices, trash day, agenda items placed on the map) and calls it. Nothing about the place is stored or
// logged here; the API drops address, lat and lon from its request log for this endpoint.
const GOVS = require('../places/fl-bay/place.json').governments || [];
const GOV_NAME = Object.fromEntries(GOVS.map(g => [g.key, g.short || g.name]));
const GOV_SLUG = Object.fromEntries(GOVS.map(g => [g.key, g.slug]));
const CITY_GOV = {'Panama City': 'pc', 'Panama City Beach': 'pcb', 'Lynn Haven': 'lh', 'Callaway': 'cw', 'Springfield': 'sp', 'Parker': 'parker', 'Mexico Beach': 'mb'};
const SITE = 'https://baycounty.me';
const TZ = 'America/Chicago';
const RADII = [0.25, 0.5, 1, 2, 5];
// What a person can switch on or off on their My home page (account.prefs.topics). Alerts and "today" always show.
const TOPICS = {meetings: 'Public meetings', events: 'Things to do', projects: 'Building and road work near me', notices: 'Public notices',
  food: 'Restaurant inspections in my ZIP', business: 'New businesses in my ZIP'};
const ALL_TOPICS = Object.keys(TOPICS);
const bad = (msg, status = 400) => Object.assign(new Error(msg), {status, expose: true});

const num = v => (v == null || v === '' || !Number.isFinite(Number(v)) ? null : Number(v));
function miles(a, b) {
  const R = 3958.8, t = Math.PI / 180, dLat = (b.lat - a.lat) * t, dLon = (b.lon - a.lon) * t;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * t) * Math.cos(b.lat * t) * Math.sin(dLon / 2) ** 2;
  return Math.round(2 * R * Math.asin(Math.sqrt(h)) * 100) / 100;
}
const ptOf = r => { const lat = num(r.lat ?? r.latitude), lon = num(r.lng ?? r.lon ?? r.longitude); return lat == null || lon == null ? null : {lat, lon}; };
// Today in Bay County, as YYYY-MM-DD (dates in the datasets are local).
const localDay = (d = new Date()) => new Intl.DateTimeFormat('en-CA', {timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit'}).format(d);
const addDays = (day, n) => { const d = new Date(day + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const day10 = v => (v ? String(v).slice(0, 10) : null);
const clip = (s, n) => { s = String(s || '').replace(/\s+/g, ' ').trim(); return s.length > n ? s.slice(0, n - 1).replace(/\s+\S*$/, '') + '…' : s; };
const titleCase = s => String(s || '').toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase());

function boardName(board, gov) {
  const g = GOV_NAME[gov] || GOV_NAME[String(board || '').split('-')[0]] || 'Local board';
  if (/-cra$/.test(board || '')) return `${g} CRA board`;
  if (board === 'county-planning') return 'Bay County Planning Commission';
  if (board === 'schools') return 'School Board';
  if (gov === 'county') return 'County Commission';
  return `${g} ${Object.values(CITY_GOV).includes(gov) ? 'City Commission' : 'board'}`;
}

// The governments that cover a place: the county, the school district and the city it is in (if any).
function govsFor(loc) { return ['county', 'schools', ...(loc.gov_id && loc.gov_id !== 'county' ? [loc.gov_id] : [])]; }

/* ---------- sections ---------- */
// Emergency notices that reach this home: an evacuation order naming its zone (or naming no zone), a boil-water,
// road or utility notice from its city or the county, and every weather warning or advisory for the county.
function alerts(notices, loc) {
  const govs = new Set(['county', loc.gov_id || 'county']);
  return (notices || []).filter(n => n.status == null || n.status === 'active').filter(n => {
    if (n.kind === 'evacuation') return !n.zones || (loc.zone && String(n.zones).split(/,\s*/).includes(loc.zone));
    if (n.kind === 'weather') return true;
    if (n.kind === 'shelter') return true;
    if (['boil-water', 'utility', 'road'].includes(n.kind)) return !n.gov_id || govs.has(n.gov_id);
    return false;
  }).slice(0, 6).map(n => ({kind: n.kind, title: clip(n.kind === 'weather' ? n.event || n.title : n.title, 120), detail: clip(n.kind === 'weather' ? n.area || n.summary : n.summary || n.source, 160),
    date: n.issued || n.updated || null, severity: n.severity || null, url: `${SITE}/emergency#n-${encodeURIComponent(n.notice_id)}`, id: n.notice_id}));
}

function meetings(rows, loc, today, days) {
  const govs = new Set(govsFor(loc)), end = addDays(today, days);
  return (rows || []).filter(r => govs.has(r.gov_id) && !r.cancelled && day10(r.start) >= today && day10(r.start) <= end)
    .sort((a, b) => String(a.start).localeCompare(String(b.start))).slice(0, 8)
    .map(r => ({kind: 'meeting', title: `${boardName(r.board, r.gov_id)}: ${clip(r.title || 'Meeting', 80)}`, date: String(r.start), gov_id: r.gov_id,
      detail: r.agenda_url ? 'Agenda posted' : 'Agenda not posted yet', url: r.agenda_url || r.detail_url || `${SITE}/meetings`}));
}

function events(rows, loc, today, days) {
  const end = addDays(today, days), town = loc.city || null;
  // Public meetings from city calendars are left out here: the meetings section lists them with their agendas.
  const soon = (rows || []).filter(r => r.category !== 'Public meeting' && !/cancel+ed/i.test(r.title || '')).filter(r => { const s = day10(r.starts), e = day10(r.ends) || s; return s && e >= today && s <= end; });
  // Events in the home's own town first, then the rest of the county; one-off events before weekly ones.
  const rank = r => (town && r.town === town ? 0 : 1) * 10 + (r.recurring ? 1 : 0);
  return soon.sort((a, b) => rank(a) - rank(b) || String(a.starts).localeCompare(String(b.starts))).slice(0, 8)
    .map(r => ({kind: 'event', title: clip(r.title, 100), date: r.starts, all_day: !!r.all_day, detail: [r.venue, r.town].filter(Boolean).join(' · ') || null,
      in_town: !!(town && r.town === town), url: r.url || r.source_url || `${SITE}/events`}));
}

// Building, development and road work within the radius, nearest first.
function projects(D, pt, radius) {
  const out = [];
  for (const r of D.development || []) {
    const p = ptOf(r); if (!p) continue;
    if (/withdrawn|denied|expired|closed|complete/i.test(r.status || '') && !r.applied_date) continue;
    const mi = miles(pt, p); if (mi > radius) continue;
    out.push({kind: 'development', title: clip(r.name || r.description || 'Development project', 100), detail: [r.status, r.size, r.location].filter(Boolean).join(' · '),
      date: r.approved_date || r.applied_date || null, miles: mi, gov_id: r.gov_id || null, url: r.plans_url || r.source_page || `${SITE}/development`});
  }
  for (const r of D.salesTax || []) {
    const p = ptOf(r); if (!p || !['in_progress', 'not_started'].includes(r.status)) continue;
    const mi = miles(pt, p); if (mi > radius) continue;
    out.push({kind: 'sales-tax', title: clip(r.name, 100), detail: `Sales tax project · ${r.status === 'in_progress' ? `In progress${r.pct_complete != null ? `, ${r.pct_complete}% done` : ''}` : 'Not started'}`,
      date: r.date_start || null, miles: mi, gov_id: r.gov_id || null, url: `${SITE}/public-money/sales-tax-projects`});
  }
  for (const r of D.roads || []) {
    const p = ptOf(r); if (!p || !/^(under way|active)$/i.test(String(r.status || '').trim())) continue;
    const mi = miles(pt, p); if (mi > Math.max(radius, 1)) continue;   // road jobs are long; their point is the middle
    out.push({kind: 'road', title: clip(r.description, 110), detail: [r.agency === 'Florida Department of Transportation' ? 'FDOT' : r.agency, r.status,
      r.estimated_completion_date ? `done ${r.estimated_completion_date.slice(0, 7)}` : null].filter(Boolean).join(' · '),
      date: r.work_began_date || null, miles: mi, entity_id: r.vendor_id ? `vendor:${r.vendor_id}` : null, url: `${SITE}/roads`});
  }
  for (const r of D.agenda || []) {
    const p = ptOf(r); if (!p) continue;
    const mi = miles(pt, p); if (mi > radius) continue;
    out.push({kind: 'agenda', title: clip(r.title, 120), detail: `On a ${GOV_NAME[String(r.board || '').split('-')[0]] || 'local'} agenda${r.meeting_date ? ' for ' + day10(r.meeting_date) : ''}`,
      date: day10(r.meeting_date), miles: mi, url: r.url || `${SITE}/meetings`});
  }
  // One row per project: a project mapped at several points shows once, at its nearest point.
  const seen = new Set();
  return out.sort((a, b) => a.miles - b.miles).filter(x => { const k = x.kind + '|' + x.title.toLowerCase(); if (seen.has(k)) return false; seen.add(k); return true; }).slice(0, 10);
}

function notices(rows, loc, today) {
  const govs = new Set(govsFor(loc)), since = addDays(today, -21);
  return (rows || []).filter(r => govs.has(r.gov_id) && day10(r.published) >= since)
    .sort((a, b) => String(b.published).localeCompare(String(a.published))).slice(0, 6)
    .map(r => ({kind: 'notice', title: clip(r.title, 120), detail: [r.kind_label, r.agency].filter(Boolean).join(' · '), date: day10(r.published),
      event_date: r.event_date || null, url: r.pdf_url || r.source_url || `${SITE}/notices`}));
}

// Restaurant inspections in the home's ZIP over the last two weeks: closures and warnings first.
function food(inspections, restaurants, loc, today) {
  if (!loc.zip) return [];
  const since = addDays(today, -14);
  const zipOf = new Map((restaurants || []).map(r => [String(r.license_number), String(r.zip || '').slice(0, 5)]));
  const LV = {closed: 0, warning: 1, 'meets-after': 2, meets: 3};
  return (inspections || []).filter(r => day10(r.date) >= since && zipOf.get(String(r.license_number)) === String(loc.zip).slice(0, 5))
    .sort((a, b) => (LV[a.result_level] ?? 4) - (LV[b.result_level] ?? 4) || String(b.date).localeCompare(String(a.date))).slice(0, 6)
    .map(r => ({kind: 'inspection', title: titleCase(r.business_name), detail: [r.result, r.high_priority ? `${r.high_priority} high-priority` : null].filter(Boolean).join(' · '),
      date: day10(r.date), level: r.result_level || null, url: `${SITE}/restaurants?q=${encodeURIComponent(r.business_name || '')}`}));
}

// Businesses filed with the state in the last 30 days with a mailing ZIP matching the home. Names only (never addresses).
function business(rows, loc, today) {
  if (!loc.zip) return {count: 0, items: []};
  const since = addDays(today, -30);
  const hits = (rows || []).filter(r => String(r.zip || '').slice(0, 5) === String(loc.zip).slice(0, 5) && day10(r.filed_date) >= since)
    .sort((a, b) => String(b.filed_date).localeCompare(String(a.filed_date)));
  return {count: hits.length, items: hits.slice(0, 6).map(r => ({kind: 'business', title: r.name, detail: r.filing_type || null, date: day10(r.filed_date),
    entity_id: r.entity_id || null, url: r.entity_id ? `${SITE}/profile/business/${String(r.entity_id).split(':')[1]}` : r.source_url}))};
}

// Today's beach flag, for homes within 2 miles of a public beach access.
function beach(conditions, access, pt) {
  const near = (access || []).map(a => { const p = ptOf(a); return p ? miles(pt, p) : null; }).filter(m => m != null).sort((a, b) => a - b)[0];
  if (near == null || near > 2) return null;
  const c = (conditions || []).filter(r => r.flag_color).sort((a, b) => (a.sort_order ?? 9) - (b.sort_order ?? 9))[0];
  return c ? {flag: c.flag_color, rip_current_risk: c.rip_current_risk || null, water_temperature: c.water_temperature || null, miles_to_beach: near, url: `${SITE}/beaches`} : null;
}

// Pure. D: {notices, meetings, events, development, salesTax, roads, agenda, publicNotices, inspections, restaurants,
// businesses, beachConditions, beachAccess, trash}. loc: {lat, lon, city, zip, gov_id, zone}. Returns sections.
function assemble(D, loc, {radius_mi = 1, days = 14, today = localDay(), topics = ALL_TOPICS} = {}) {
  const pt = {lat: Number(loc.lat), lon: Number(loc.lon)};
  const want = new Set(topics);
  const radius = RADII.includes(Number(radius_mi)) ? Number(radius_mi) : 1;
  const gov = loc.gov_id || CITY_GOV[loc.city] || 'county';
  const L = {...loc, gov_id: gov};
  const biz = want.has('business') ? business(D.businesses, L, today) : {count: 0, items: []};
  const sections = [
    {id: 'alerts', title: 'Alerts for your home', items: alerts(D.notices, L), empty: 'No warnings, evacuation orders or boil-water notices for your home right now.'},
    want.has('meetings') && {id: 'meetings', title: 'Public meetings coming up', items: meetings(D.meetings, L, today, days), empty: 'No meetings on the calendar in the next two weeks.'},
    want.has('events') && {id: 'events', title: 'Things to do', items: events(D.events, L, today, days), empty: 'No events listed for the next two weeks.'},
    want.has('projects') && {id: 'projects', title: `Within ${radius === 1 ? 'a mile' : radius + ' miles'} of home`, items: projects(D, pt, radius), empty: 'No building, development or road work on file near your home.'},
    want.has('notices') && {id: 'notices', title: 'Public notices', items: notices(D.publicNotices, L, today), empty: 'No public notices from your governments in the last three weeks.'},
    want.has('food') && {id: 'food', title: `Restaurant inspections in ${L.zip || 'your ZIP'}`, items: food(D.inspections, D.restaurants, L, today), empty: 'No inspections in your ZIP in the last two weeks.'},
    want.has('business') && {id: 'business', title: `New businesses in ${L.zip || 'your ZIP'}`, count: biz.count, items: biz.items, empty: 'No new filings in your ZIP in the last 30 days.'},
  ].filter(Boolean);
  const gpages = govsFor(L).map(k => ({gov_id: k, name: GOV_NAME[k] || k, url: `${SITE}/governments/${GOV_SLUG[k] || k}`}));
  return {
    place_id: loc.place_id || 'fl-bay', today, city: L.city || null, zip: L.zip || null, gov_id: gov, local_government: gov === 'county' ? 'Unincorporated Bay County' : `City of ${GOV_NAME[gov]}`,
    zone: L.zone || null, radius_mi: radius,
    today_card: {trash: D.trash || null, beach: beach(D.beachConditions, D.beachAccess, pt), alerts: sections[0].items.length},
    governments: gpages, sections,
    note: 'Everything here is public record from the datasets named in each section. Distances are from the address point.',
  };
}

/* ---------- reading the data ---------- */
const DATASETS = {meetings: 'meetings', events: 'community-events', development: 'development-projects', salesTax: 'sales-tax-projects', roads: 'road-contracts',
  publicNotices: 'public-notices', inspections: 'restaurant-inspections', restaurants: 'restaurants', businesses: 'new-businesses',
  beachConditions: 'beach-conditions', beachAccess: 'beach-access'};
const NEEDS = {meetings: ['meetings'], events: ['events'], projects: ['development', 'salesTax', 'roads'], notices: ['publicNotices'], food: ['inspections', 'restaurants'], business: ['businesses']};

// Fills in what a saved home or a lookup leaves out: the city (gov), ZIP and evacuation zone. loc may be {address} or {lat, lon}.
async function resolve(q, {fetchImpl = fetch} = {}) {
  const A = require('./_address_report');
  const loc = await A.locate(q, fetchImpl);
  const P = A.PLACES[loc.place || 'fl-bay'];
  if (!P) throw bad('Unknown place.');
  const [x0, y0, x1, y1] = P.bbox;
  if (!(loc.lon >= x0 && loc.lon <= x1 && loc.lat >= y0 && loc.lat <= y1)) throw bad(`That point is outside ${P.name}.`, 404);
  const pp = {geometry: JSON.stringify({x: loc.lon, y: loc.lat, spatialReference: {wkid: 4326}}), geometryType: 'esriGeometryPoint', inSR: 4326, spatialRel: 'esriSpatialRelIntersects', outFields: 'NAME', returnGeometry: 'false', f: 'json'};
  const cities = await fetchImpl(`${P.gis}/Admin_A12/MapServer/26/query?` + new URLSearchParams(pp)).then(r => r.json()).then(j => (j.features || []).map(f => f.attributes.NAME)).catch(() => []);
  const city = cities.find(n => n && !/unincorp/i.test(n) && CITY_GOV[n]) || null;
  let zone = q.zone && /^[A-E]$/.test(q.zone) ? q.zone : null;
  if (!zone) { try { zone = await require('./_emergency').zoneAt(loc.lat, loc.lon, loc.place || 'fl-bay'); } catch (e) { zone = null; } }
  return {...loc, city: city || loc.city || null, gov_id: city ? CITY_GOV[city] : 'county', zone: zone || null};
}

// deps: {catalog, rowsOf(id) -> rows|null, live: {notices()?, agenda()?, trash()?}}
async function feed(loc, opts, deps) {
  const topics = (opts.topics && opts.topics.length ? opts.topics : ALL_TOPICS).filter(t => TOPICS[t]);
  const keys = new Set(['beachConditions', 'beachAccess', ...topics.flatMap(t => NEEDS[t] || [])]);
  const D = {};
  // Rows with same_as are a post listed twice (data/dupes.py); the kept row stands for both.
  await Promise.all([...keys].map(async k => { try { D[k] = ((await deps.rowsOf(DATASETS[k])) || []).filter(r => !r.same_as); } catch (e) { D[k] = []; } }));
  const live = deps.live || {};
  const [notices, agenda, trash] = await Promise.all([
    live.notices ? live.notices().catch(() => []) : [],
    topics.includes('projects') && live.agenda ? live.agenda().catch(() => []) : [],
    live.trash ? live.trash().catch(() => null) : null,
  ]);
  Object.assign(D, {notices, agenda, trash});
  return assemble(D, loc, {...opts, topics});
}

// The trash and recycling days at a point, from the utilities lookup (live map layers). Short form for the card.
async function trashAt(req, catalog, loc) {
  const U = require('./_utilities');
  const {utilityData} = require('./v1');
  const r = await U.lookup(await utilityData(req, catalog), {lat: loc.lat, lon: loc.lon});
  return (r.pickup || []).filter(p => p.days).slice(0, 4).map(p => ({service: p.service_label || p.service, days: p.days, provider: p.provider || null}));
}

// Agenda items placed on the map in the last 30 days (push.agenda_points, from api/_agenda_push.js). Database only.
async function agendaPoints(place = 'fl-bay') {
  const db = require('./_db');
  if (!db.hasDb()) return [];
  return db.q(`select board, meeting_date, title, url, lat, lng from push.agenda_points where place_id = $1 and lat is not null
      and (meeting_date is null or meeting_date >= current_date - 30) order by placed_at desc limit 400`, [place]);
}

// One answer for a request with ?address= or ?lat=&lon= (the API endpoint and the MCP tool).
async function forRequest(req, catalog, q, {rowsOf}) {
  if (!q.address && (q.lat == null || q.lat === '')) throw bad('Add ?address= (house number and street) or ?lat=&lon=.');
  const loc = await resolve({...q, lon: q.lon ?? q.lng});
  const topics = q.topics ? String(q.topics).split(',').map(s => s.trim()).filter(t => TOPICS[t]) : ALL_TOPICS;
  const r = await feed(loc, {radius_mi: q.radius_mi, topics, days: Math.min(Math.max(parseInt(q.days || '14', 10) || 14, 1), 31)}, {catalog, rowsOf, live: liveSources(req, catalog, loc)});
  return {...r, address: q.address ? loc.address || null : null, lat: loc.lat, lon: loc.lon};
}

function liveSources(req, catalog, loc) {
  return {
    notices: async () => (await require('./_emergency_feed').liveFeed(req, catalog, {place: loc.place || 'fl-bay', refresh: false})).notices,
    agenda: () => agendaPoints(loc.place || 'fl-bay'),
    trash: () => trashAt(req, catalog, loc),
  };
}

module.exports = {assemble, feed, resolve, forRequest, liveSources, trashAt, agendaPoints, govsFor, boardName, localDay, addDays, miles, TOPICS, ALL_TOPICS, RADII, DATASETS, CITY_GOV, GOV_NAME};
