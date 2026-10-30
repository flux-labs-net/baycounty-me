// What /api/v1/emergency and /api/v1/evacuation-zone answer (also used by the MCP tools).
// Live notices come from emergency_live and the shelter status from emergency_state (public read, written by the
// poller every few minutes). When the last check is old (or the database can't be read), the sources are read directly.
const E = require('./_emergency');
const {datasetRows, rest} = require('./_data');
const SITE = 'https://baycounty.me';
const STALE_MS = 10 * 60e3;

const LIVE_COLS = 'notice_id,kind,source,source_type,gov_id,title,summary,instruction,severity,event,area,zones,issued,starts,ends,updated,status,full_closure,roadway,url,source_url,first_seen,last_seen';
const KIND_LABEL = {evacuation: 'Evacuation orders', weather: 'Weather alerts', shelter: 'Shelters open', 'boil-water': 'Boil-water notices', road: 'Road closures', utility: 'Water and utility outages', storm: 'Storm updates', safety: 'Public safety alerts'};

async function meta(req, catalog, id) {
  const m = catalog.datasets.find(d => d.id === id);
  return m ? (await datasetRows(req, m)).rows : [];
}

async function readLive(place) {
  const [n, s] = await Promise.all([
    rest(`emergency_live?select=${LIVE_COLS}&place_id=eq.${encodeURIComponent(place)}&active=is.true&order=last_seen.desc&limit=500`),
    rest(`emergency_state?select=checked_at,shelters,sources_ok,errors,push_ready&place_id=eq.${encodeURIComponent(place)}`),
  ]);
  return {notices: n.rows, state: s.rows[0] || null};
}

// Shelters from the dataset (address, map point, zone) with the newest status the poller saw.
function mergeShelters(rows, live) {
  const st = new Map((live || []).map(s => [s.shelter_id, s]));
  return rows.map(r => {
    const l = st.get(r.shelter_id);
    return {shelter_id: r.shelter_id, name: r.name, address: r.address, type: r.shelter_type, group: r.group_name, note: r.note || null,
      status: l ? l.status : r.status, status_as_of: l ? l.status_as_of : r.status_as_of, lat: r.lat, lng: r.lng, evacuation_zone: r.evacuation_zone, source_url: r.source_url};
  });
}

async function liveFeed(req, catalog, {place = 'fl-bay', refresh = true} = {}) {
  E.placeConfig(place);
  let live = null, source = 'database';
  try { live = await readLive(place); } catch (e) { live = null; }
  const age = live && live.state && live.state.checked_at ? Date.now() - Date.parse(live.state.checked_at) : Infinity;
  if (refresh && age > STALE_MS && require('./_db').hasDb()) {
    // The scheduled check is late; run one now (throttled, so many callers still make one check).
    try { await require('./_emergency_run').run(place); live = await readLive(place); } catch (e) { console.error('emergency refresh', e.message); }
  }
  let notices, state = live && live.state;
  if (!live || !state || !state.checked_at || Date.now() - Date.parse(state.checked_at) > 3 * STALE_MS) {
    // No recent stored check: read the sources directly.
    const r = await E.readAll(place);
    notices = r.notices.filter(n => n.status === 'active');
    state = {checked_at: new Date().toISOString(), shelters: r.shelters, sources_ok: r.ok, errors: r.errors, push_ready: null};
    source = 'sources';
  } else notices = live.notices;
  // A notice posted twice (re-posted with an update) is one card: the newest version, with first_posted and versions.
  notices = require('./_dupes').mergeNotices(notices, await require('./_dupes').decisions());
  notices = notices.slice().sort(E.byUrgency).map(n => ({...n, page: `${SITE}/emergency#n-${encodeURIComponent(n.notice_id)}`}));
  const [shelterRows, zoneRows] = await Promise.all([meta(req, catalog, 'emergency-shelters'), meta(req, catalog, 'evacuation-zones')]);
  const shelters = mergeShelters(shelterRows, state.shelters);
  const count = k => notices.filter(n => n.kind === k).length;
  const evac = notices.filter(n => n.kind === 'evacuation');
  const warnings = notices.filter(n => n.kind === 'weather' && /Warning|Emergency/.test(n.event || ''));
  const open = shelters.filter(s => s.status === 'open');
  const headline = evac.length ? `Evacuation order in effect${evac[0].zones ? ' for Zone' + (evac[0].zones.includes(',') ? 's ' : ' ') + evac[0].zones : ''}.`
    : warnings.length ? `${warnings[0].event} in effect.`
      : count('weather') ? `${count('weather')} weather ${count('weather') === 1 ? 'advisory or watch' : 'advisories and watches'} in effect.`
        : 'No weather warnings or evacuation orders right now.';
  return {
    place, checked_at: state.checked_at, data_source: source, headline,
    counts: Object.fromEntries(Object.keys(KIND_LABEL).map(k => [k, count(k)])), shelters_open: open.length,
    labels: KIND_LABEL, notices, shelters,
    zones: zoneRows.map(z => ({zone: z.zone, where_it_is: z.where_it_is, when_ordered: z.when_ordered, plain: z.plain, color: z.color, ordered: evac.some(n => (n.zones || '').split(', ').includes(z.zone))})),
    sources_ok: state.sources_ok || [], source_errors: (state.errors || []).map(e => e.source),
    links: {page: `${SITE}/emergency`, zone_lookup: `${SITE}/api/v1/evacuation-zone?address=`, archive: `${SITE}/api/v1/datasets/emergency-notices`, timeline: `${SITE}/api/v1/emergency-timeline`, push_signup: `${SITE}/api/push`},
    note: 'Notices come from the National Weather Service, FEMA IPAWS (emergency alerts), Bay County and city alert centers and news, FL511 and the county shelter page, checked every 5 minutes. Always follow instructions from emergency officials.',
  };
}


// ---------- alert timeline (/api/v1/emergency-timeline, the timeline on /emergency) ----------
// Every notice that was live in the last `days` days, newest first: when it started and ended, and how many people
// each channel reached (emergency_reach, counts only). gov keeps one government's notices plus the countywide ones
// (weather, IPAWS, shelters) that reach it too.
const GOV_NAMES = {county: 'Bay County', pc: 'Panama City', pcb: 'Panama City Beach', lh: 'Lynn Haven', cw: 'Callaway', sp: 'Springfield', parker: 'Parker', mb: 'Mexico Beach'};
function buildTimeline(notices, reach, {days = 30, kind = '', gov = ''} = {}) {
  const per = new Map();
  for (const r of reach) {
    const o = per.get(r.notice_id) || {push: 0, email: 0, sms: 0};
    o[r.channel] = (o[r.channel] || 0) + (Number(r.people) || 0);
    per.set(r.notice_id, o);
  }
  const items = notices
    .filter(n => (!kind || n.kind === kind) && (!gov || !n.gov_id || n.gov_id === gov))
    .map(n => {
      const ids = [...new Set([n.notice_id, ...(n.versions || []).map(v => v.notice_id)])];
      const rr = ids.reduce((a, id) => { const o = per.get(id); if (o) for (const k of Object.keys(a)) a[k] += o[k] || 0; return a; }, {push: 0, email: 0, sms: 0});
      const started = n.first_posted || n.issued || n.first_seen || null;
      return {notice_id: n.notice_id, kind: n.kind, label: KIND_LABEL[n.kind] || 'Notice', title: n.title, event: n.event || null, severity: n.severity,
        source: n.source, source_type: n.source_type, gov_id: n.gov_id || null, zones: n.zones || null, area: n.area || null,
        started, ended: n.active ? null : (n.last_seen || null), active: !!n.active, status: n.active ? 'active' : n.status === 'lifted' ? 'lifted' : 'ended',
        reach: rr, people: rr.push + rr.email + rr.sms, url: n.url || null, page: `${SITE}/emergency#n-${encodeURIComponent(n.notice_id)}`};
    })
    .sort((a, b) => String(b.started || '').localeCompare(String(a.started || '')));
  const counts = {};
  for (const i of items) counts[i.kind] = (counts[i.kind] || 0) + 1;
  return {days, kind: kind || null, gov: gov || null, total: items.length, counts, labels: KIND_LABEL, governments: GOV_NAMES,
    reached: items.reduce((a, i) => a + i.people, 0), items};
}

async function timeline(req, catalog, q = {}, {place = 'fl-bay'} = {}) {
  E.placeConfig(place);
  const days = Math.min(90, Math.max(1, parseInt(q.days, 10) || 30));
  const kind = KIND_LABEL[String(q.kind || '')] ? String(q.kind) : '';
  const gov = GOV_NAMES[String(q.gov || '')] ? String(q.gov) : '';
  const since = new Date(Date.now() - days * 864e5).toISOString();
  const P = encodeURIComponent(place);
  const [n, r] = await Promise.all([
    rest(`emergency_live?select=${LIVE_COLS},active&place_id=eq.${P}&last_seen=gte.${since}&order=first_seen.desc&limit=2000`),
    rest(`emergency_reach?select=notice_id,channel,people&place_id=eq.${P}&sent_at=gte.${new Date(Date.now() - (days + 7) * 864e5).toISOString()}&limit=5000`).catch(() => ({rows: []})),
  ]);
  const D = require('./_dupes');
  const notices = D.mergeNotices(n.rows, await D.decisions());
  return {place, ...buildTimeline(notices, r.rows, {days, kind, gov}),
    note: 'Every notice live in this window, newest first. people counts phones and inboxes each channel sent it to (counts only). Older notices: the emergency-notices dataset.'};
}

const {miles} = require('./_geo');

async function zoneLookup(req, catalog, q, {place = 'fl-bay'} = {}) {
  let pt = null, match = null;
  if (q.lat != null && q.lng != null && q.lat !== '' && q.lng !== '') pt = {lat: Number(q.lat), lng: Number(q.lng)};
  else if (q.address || q.q) {
    match = await E.geocode(String(q.address || q.q).slice(0, 200), place);
    if (!match) return {query: String(q.address || q.q), found: false, message: 'No Bay County address matched. Try the house number and street, like 825 Ohio Ave.'};
    pt = {lat: match.lat, lng: match.lng};
  } else throw Object.assign(new Error('Add ?address=<street address> or ?lat=&lng=.'), {status: 400, expose: true});
  const zone = await E.zoneAt(pt.lat, pt.lng, place);
  const zones = await meta(req, catalog, 'evacuation-zones');
  const info = zones.find(z => z.zone === zone) || null;
  let orders = [];
  try { orders = (await rest(`emergency_live?select=notice_id,title,zones,issued,source,url&place_id=eq.${place}&active=is.true&kind=eq.evacuation`)).rows; } catch (e) { orders = []; }
  const shelters = (await meta(req, catalog, 'emergency-shelters')).filter(s => s.lat && s.lng && ['general', 'special-needs', 'extreme-weather', 'pet-friendly'].includes(s.shelter_type))
    .map(s => ({name: s.name, address: s.address, type: s.shelter_type, status: s.status, evacuation_zone: s.evacuation_zone, miles: +miles(pt, {lat: s.lat, lng: s.lng}).toFixed(1)}))
    .sort((a, b) => a.miles - b.miles).slice(0, 3);
  const Z = await meta(req, catalog, 'evacuation-zones');
  return {
    query: q.address || q.q || `${pt.lat},${pt.lng}`, found: true, address: match, point: pt, zone,
    in_zone: !!zone, zone_info: info ? {where_it_is: info.where_it_is, when_ordered: info.when_ordered, plain: info.plain} : null,
    what_to_do: zone ? `You're in evacuation Zone ${zone}. ${info ? info.when_ordered : ''} Leave when an evacuation order names Zone ${zone}.`.replace(/\s+/g, ' ')
      : 'This address is outside the four evacuation zones. Bay County recommends sheltering in place unless an order covers your area. Some orders also cover mobile and manufactured homes in every zone, so read each order.',
    orders_now: orders.map(o => ({...o, includes_you: !o.zones || (zone && o.zones.split(', ').includes(zone))})),
    nearest_shelters: shelters, map: (Z[0] || {}).map_url || null,
    source_url: (Z[0] || {}).source_url || null, note: 'Zone from Bay County\'s evacuation zone map. Confirm with the county map or 850-248-6040 before a storm.',
  };
}

module.exports = {liveFeed, zoneLookup, timeline, buildTimeline, KIND_LABEL, GOV_NAMES, miles};
