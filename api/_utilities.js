// Utilities and trash pickup at one address (GET /api/v1/utilities and the MCP tool utilities_at_address).
// Reads the utility-providers, trash-pickup, trash-holidays and utility-rates datasets (site/page_datasets.py, from
// data/utilities/<county>/utilities.json). Which city an address is in, its pickup route and whether an electric
// co-op maps it come live from public map layers; everything else is in the datasets. Nothing about the search is stored.
const bad = (msg, status = 400) => Object.assign(new Error(msg), {status, expose: true});

// Per place: the address points, the city boundary layer (its NAME -> area key) and the electric co-op territory layer.
const PLACES = {
  'fl-bay': {
    addresses: 'https://gis.baycountyfl.gov/arcgis/rest/services/Admin_A12/MapServer/3',
    boundary: 'https://gis.baycountyfl.gov/arcgis/rest/services/BayView/BayView/MapServer/6',
    names: {'Panama City': 'pc', 'Panama City Beach': 'pcb', 'Lynn Haven': 'lh', Callaway: 'cw', Springfield: 'sp', Parker: 'parker', 'Mexico Beach': 'mb',
      Unincorporated: 'county', 'Tyndall Air Force Base': 'county', 'Naval Support Activity Center': 'county'},
    coop: {layer: 'https://eedgis.pnnl.gov/arcgis/rest/services/Hosted/Electric_Service_Territories/FeatureServer/0', field: 'name',
      match: /GULF COAST ELECTRIC/i, provider: 'Gulf Coast Electric Cooperative'},
    bbox: [-86.1, 29.85, -85.2, 30.6],
  },
};
const ORDER = ['water', 'sewer', 'electric', 'gas', 'garbage', 'yard_waste', 'bulk', 'recycling', 'internet'];
const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

// "THURSDAY" -> "Thursday", "Monday, Thursday" stays, "Monday Only" -> "Monday".
function normDays(v) {
  if (v == null) return null;
  const s = String(v).trim();
  if (!s) return null;
  const found = DAYS.filter(d => new RegExp(`\\b${d}\\b`, 'i').test(s));
  return found.length ? found.join(', ') : s;
}

async function arcgis(url, params, fetchImpl = fetch, ms = 8000) {
  const u = `${url}/query?` + new URLSearchParams({f: 'json', returnGeometry: 'false', ...params});
  const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), ms);
  try {
    const r = await fetchImpl(u, {signal: ctl.signal});
    if (!r.ok) throw new Error('map server ' + r.status);
    const j = await r.json();
    if (j.error) throw new Error(j.error.message || 'map server error');
    return j.features || [];
  } finally { clearTimeout(t); }
}
const atPoint = (url, lat, lon, outFields, fetchImpl) => arcgis(url, {geometry: `${lon},${lat}`, geometryType: 'esriGeometryPoint', inSR: '4326',
  spatialRel: 'esriSpatialRelIntersects', outFields}, fetchImpl).then(f => f.map(x => x.attributes));

// A street address -> matching address points (house number plus street words, the way Bay County stores them).
async function findAddress(q, place = 'fl-bay', fetchImpl = fetch) {
  const P = PLACES[place];
  const s = String(q || '').toUpperCase().replace(/[^A-Z0-9 ]/g, ' ').replace(/\b(FL|FLORIDA|\d{5})\s*$/g, ' ').replace(/\s+/g, ' ').trim();
  const m = /^(\d+)\s+(.+)$/.exec(s);
  if (!m) throw bad('address must start with a house number, e.g. 825 Ohio Ave.');
  const words = m[2].split(' ').filter(w => w.length > 1 && !/^(ST|AVE|RD|DR|LN|CT|BLVD|WAY|CIR|PL|PANAMA|CITY|BEACH|LYNN|HAVEN|CALLAWAY|SPRINGFIELD|PARKER|MEXICO)$/.test(w)).slice(0, 4);
  // whole words first; then let the last word be the start of a word ("825 Ohio Av")
  const whole = w => `(ADDRESS LIKE '% ${w} %' OR ADDRESS LIKE '% ${w}')`;
  const opts = {outFields: 'ADDRESS,UNIT,CMNTY,ZIP', returnGeometry: 'true', outSR: '4326', resultRecordCount: '8', orderByFields: 'ADDRESS'};
  let f = await arcgis(P.addresses, {where: [`ADDRESS LIKE '${m[1]} %'`, ...words.map(whole)].join(' AND '), ...opts}, fetchImpl);
  if (!f.length && words.length) f = await arcgis(P.addresses, {where: [`ADDRESS LIKE '${m[1]} %'`, ...words.slice(0, -1).map(whole), `ADDRESS LIKE '% ${words[words.length - 1]}%'`].join(' AND '), ...opts}, fetchImpl);
  return f.filter(x => x.geometry).map(x => ({address: x.attributes.ADDRESS, unit: (x.attributes.UNIT || '').trim() || null, community: x.attributes.CMNTY, zip: x.attributes.ZIP,
    lat: +x.geometry.y.toFixed(6), lon: +x.geometry.x.toFixed(6)}));
}

const pick = (r, keys) => Object.fromEntries(keys.map(k => [k, r[k] ?? null]));
const PROV_KEYS = ['provider', 'entity_id', 'provider_kind', 'coverage', 'phone', 'website', 'outage_url', 'notes', 'source_url'];

// Everything for one area, given what the map layers said. Pure, so tests can check it without the network.
// hits: {layerUrl: [{attributes}]}; coop: true/false/null (null = the co-op layer didn't answer).
function assemble(D, area, {hits = {}, coop = null, place = 'fl-bay'} = {}) {
  const P = PLACES[place] || {};
  const inArea = r => (r.place_id || place) === place && (r.area === area || r.area === 'all');
  const services = [];
  for (const svc of ORDER) {
    let ps = D.providers.filter(r => inArea(r) && r.service === svc);
    if (svc === 'electric' && P.coop) {
      const co = r => P.coop.match.test(r.provider);
      // The co-op shows only where its mapped territory covers the address; then it is listed first.
      ps = coop ? [...ps.filter(co), ...ps.filter(r => !co(r))] : ps.filter(r => !co(r));
    }
    // a city's own row replaces the countywide "all" row for the same service (e.g. recycling stays countywide)
    if (ps.some(r => r.area === area) && svc !== 'electric' && svc !== 'gas') ps = ps.filter(r => r.area === area);
    if (ps.length) services.push({service: svc, service_label: ps[0].service_label, providers: ps.map(r => pick(r, PROV_KEYS))});
  }
  const pickup = [];
  const groups = new Map();
  for (const r of D.trash.filter(inArea)) {
    const k = r.service + '|' + (r.lookup_layer || '') + '|' + r.provider;
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(r);
  }
  for (const rows of groups.values()) {
    const r0 = rows[0], base = {service: r0.service, service_label: r0.service_label, provider: r0.provider, notes: r0.notes, source_url: r0.source_url};
    if (r0.lookup_layer) {
      const h = hits[r0.lookup_layer];
      const a = h && h[0];
      if (a) {
        const zone = a[r0.zone_field] == null ? null : String(a[r0.zone_field]).trim();
        const row = rows.find(x => String(x.zone) === zone);
        pickup.push({...base, zone, zone_label: /route/i.test(r0.zone_field || '') ? 'route' : 'zone', days: normDays(a[r0.day_field]) || (row && row.pickup_days) || null, zone_area: null, rule: r0.rule, from_map: true});
      } else {
        pickup.push({...base, zone: null, days: null, zone_area: null, from_map: false,
          rule: h ? 'This address isn\'t on the city\'s route map. Call the number below for your day.' : 'The city\'s route map didn\'t answer just now. Try again, or call the number below.'});
      }
    } else {
      for (const r of rows) pickup.push({...base, zone: r.zone, days: r.pickup_days, zone_area: r.zone_area, rule: r.rule, from_map: false});
    }
  }
  pickup.sort((x, y) => ORDER.indexOf(x.service) - ORDER.indexOf(y.service));
  const holidays = D.holidays.filter(inArea).map(r => pick(r, ['provider', 'holiday', 'when_observed', 'garbage', 'yard_waste', 'source_url']));
  const rates = D.rates.filter(inArea).map(r => pick(r, ['provider', 'service', 'service_label', 'charge', 'amount', 'unit', 'applies_to', 'effective', 'notes', 'source_url']));
  const name = (D.providers.find(r => r.area === area) || D.trash.find(r => r.area === area) || {}).area_name || area;
  return {place_id: place, area, area_name: name, gov_id: area, services, pickup, holidays, rates,
    note: 'Providers and rules come from each city\'s and the county\'s own pages; pickup routes are read live from the city\'s route map. Electric co-op and FPL lines can run through the same neighborhood, so the name on your bill is the sure answer. Rates: utility-rates dataset.'};
}

// The full lookup: city at the point, then each route map and the co-op layer, then assemble().
async function lookup(D, q, fetchImpl = fetch) {
  const place = String(q.place || 'fl-bay');
  const P = PLACES[place];
  if (!P) throw bad(`Unknown place "${place}".`);
  let lat = Number(q.lat), lon = Number(q.lon ?? q.lng);
  let matched = null, others = [];
  if (q.address && !(Number.isFinite(lat) && Number.isFinite(lon))) {
    const found = await findAddress(q.address, place, fetchImpl);
    if (!found.length) throw bad(`No address found for "${String(q.address).slice(0, 80)}". Start with the house number and street name.`, 404);
    [matched, ...others] = found;
    ({lat, lon} = matched);
  }
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) throw bad('Add ?lat=&lon= (decimal degrees) or ?address=.');
  const [x0, y0, x1, y1] = P.bbox;
  if (lon < x0 || lon > x1 || lat < y0 || lat > y1) throw bad('That point is outside the county.', 404);
  const city = await atPoint(P.boundary, lat, lon, 'NAME', fetchImpl).catch(() => null);
  if (!city) throw Object.assign(new Error('The county map server didn\'t answer. Try again shortly.'), {status: 502, expose: true});
  const names = city.map(c => c.NAME);
  const area = names.map(n => P.names[n]).find(k => k && k !== 'county') || 'county';
  const layers = [...new Set(D.trash.filter(r => r.area === area && r.lookup_layer).map(r => r.lookup_layer))];
  const fieldsOf = u => [...new Set(D.trash.filter(r => r.lookup_layer === u).flatMap(r => [r.zone_field, r.day_field]))].join(',');
  const [hitList, coop] = await Promise.all([
    Promise.all(layers.map(u => atPoint(u, lat, lon, fieldsOf(u), fetchImpl).catch(() => null))),
    P.coop ? atPoint(P.coop.layer, lat, lon, P.coop.field, fetchImpl).then(f => f.some(a => P.coop.match.test(a[P.coop.field] || ''))).catch(() => null) : null,
  ]);
  const hits = Object.fromEntries(layers.map((u, i) => [u, hitList[i]]));
  return {point: {lat, lon}, address: matched, other_matches: others.length ? others : undefined, boundary: names, ...assemble(D, area, {hits, coop, place})};
}

module.exports = {PLACES, ORDER, normDays, assemble, lookup, findAddress};
