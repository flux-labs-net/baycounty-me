// What /api/v1/emergency and /api/v1/evacuation-zone answer (also used by the MCP tools).
// Live notices come from emergency_live and the shelter status from emergency_state (public read, written by the
// poller every few minutes). When the last check is old (or the database can't be read), the sources are read directly.
const E = require('./_emergency');
const {datasetRows, rest} = require('./_data');
const SITE = 'https://baycounty.me';
const STALE_MS = 10 * 60e3;

const LIVE_COLS = 'notice_id,kind,source,source_type,gov_id,title,summary,instruction,severity,event,area,zones,issued,starts,ends,updated,status,full_closure,roadway,url,source_url,first_seen,last_seen';
const KIND_LABEL = {evacuation: 'Evacuation orders', weather: 'Weather alerts', shelter: 'Shelters open', 'boil-water': 'Boil-water notices', road: 'Road closures', utility: 'Water and utility outages', storm: 'Storm updates'};

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
    links: {page: `${SITE}/emergency`, zone_lookup: `${SITE}/api/v1/evacuation-zone?address=`, archive: `${SITE}/api/v1/datasets/emergency-notices`, push_signup: `${SITE}/api/push`},
    note: 'Notices come from the National Weather Service, Bay County and city alert centers and news, FL511 and the county shelter page, checked every 5 minutes. Always follow instructions from emergency officials.',
  };
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

module.exports = {liveFeed, zoneLookup, KIND_LABEL, miles};
