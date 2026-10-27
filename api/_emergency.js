// Emergency hub sources: National Weather Service alerts, each government's alert center and news feed (boil-water
// notices, road closures, storm updates), FL511 road closures, Bay County's shelter page and the evacuation zone map.
// Every reader returns notices in one shape (see notice()), so the live poller (_emergency_run.js), the daily archive
// (data/emergency/fetch_emergency.js) and the API all agree. Which feeds to read comes from data/emergency/sources.json,
// keyed by place id, so another county only needs its own entry there.
const SOURCES = require('../data/emergency/sources.json');
const UA = 'BayCounty.me emergency hub (hello@baycounty.me)';
const TIMEOUT = 9000;

const placeConfig = (place = 'fl-bay') => {
  const c = SOURCES[place];
  if (!c) throw Object.assign(new Error(`Unknown place "${place}".`), {status: 400, expose: true});
  return c;
};

async function get(url, {json = false, timeout = TIMEOUT, headers = {}} = {}) {
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), timeout);
  try {
    const r = await fetch(url, {signal: ctl.signal, headers: {'User-Agent': UA, Accept: json ? 'application/geo+json, application/json' : '*/*', ...headers}});
    if (!r.ok) throw new Error(`${new URL(url).hostname} answered ${r.status}`);
    return json ? r.json() : r.text();
  } finally { clearTimeout(timer); }
}

// ---------- text helpers ----------
const ENT = {amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', ndash: '–', mdash: '—', rsquo: '’', lsquo: '‘', rdquo: '”', ldquo: '“', hellip: '…'};
function decode(s) {
  return String(s || '').replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e) => {
    if (e[0] === '#') { const n = e[1].toLowerCase() === 'x' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10); return Number.isFinite(n) ? String.fromCodePoint(n) : m; }
    return ENT[e.toLowerCase()] ?? m;
  });
}
// HTML (possibly entity-encoded, as in RSS descriptions) -> plain text on one line per paragraph.
function plain(s) {
  let t = String(s || '').replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1');
  if (/&lt;\w/.test(t)) t = decode(t);
  t = t.replace(/<(script|style)[\s\S]*?<\/\1>/gi, ' ').replace(/<br\s*\/?>/gi, '\n').replace(/<\/(p|div|li|h\d)>/gi, '\n').replace(/<[^>]+>/g, ' ');
  return decode(t).replace(/[ \t ]+/g, ' ').replace(/ *\n */g, '\n').replace(/\n{2,}/g, '\n').trim();
}
const clip = (s, n) => { s = String(s || '').replace(/\s+/g, ' ').trim(); return s.length > n ? s.slice(0, n - 1).replace(/\s+\S*$/, '') + '…' : s; };
const iso = d => { const t = Date.parse(d); return Number.isFinite(t) ? new Date(t).toISOString() : null; };

// ---------- what a notice is about ----------
// Order matters: the first match wins. Lifted/rescinded boil-water notices are still boil-water notices (status lifted).
const KINDS = [
  ['evacuation', /\bevacuat(e|ion|ions)\b.*\b(order|ordered|mandatory|voluntary)\b|\b(mandatory|voluntary) evacuation/i],
  ['boil-water', /\bboil[- ]water\b|\bboil (your )?water\b|\bPBWN\b/i],
  ['shelter', /\bshelters?\b.*\b(open|opening|opened)\b|\b(open|opening|opened)\b.*\bshelters?\b/i],
  ['road', /\b(road|street|st\.?|avenue|ave\.?|lane|bridge|ramp|highway|hwy|blvd|drive|dr\.?) (closure|closed|closing)\b|\bclosures?\b|\bdetour\b|\blane (closure|closed)\b|\bclosed to traffic\b/i],
  ['utility', /\bwater (main|service|outage|interruption|line)\b|\bwater (is|will be) (off|shut)\b|\breuse (system|water)\b|\bsewer (spill|overflow)\b|\bpower outage\b/i],
  ['storm', /\b(hurricane|tropical storm|tropical depression|storm surge|sandbags?|sand available|debris|curfew|state of (local )?emergency|emergency operations center|re-?entry|damage assessment|evacuation zone)\b/i],
];
function classify(title, text = '') {
  // The title decides when it can; otherwise the first lines of the text.
  for (const [k, re] of KINDS) if (re.test(title)) return k;
  const t = `${title} ${String(text).slice(0, 400)}`;
  for (const [k, re] of KINDS) if (re.test(t)) return k;
  return null;
}
const LIFTED = /\b(rescind(ed)?|lifted|cancel(l)?ed|no longer in effect|has been lifted|reopen(ed|s)?|all clear)\b/i;
// Evacuation zones a notice names: "Zones A and B", "Zone A, B & C", "evacuation zone C".
function zonesIn(text) {
  const out = new Set();
  const re = /\bzones?\s+([A-E](?:\s*(?:,|and|&|or|\/)\s*(?:zone\s+)?[A-E]\b)*)/gi;
  let m;
  while ((m = re.exec(String(text || '')))) for (const z of m[1].match(/\b[A-E]\b/gi) || []) out.add(z.toUpperCase());
  return [...out].sort();
}

// One notice. Every reader fills what it knows; the rest stays null.
function notice(o) {
  return {
    notice_id: o.notice_id, place_id: o.place_id, kind: o.kind, source: o.source, source_type: o.source_type, gov_id: o.gov_id || null,
    title: clip(o.title, 240), summary: clip(o.summary, 900) || null, instruction: clip(o.instruction, 900) || null,
    severity: o.severity || 'info', event: o.event || null, area: clip(o.area, 400) || null, zones: (o.zones || []).join(', ') || null,
    issued: o.issued || null, starts: o.starts || null, ends: o.ends || null, updated: o.updated || null,
    status: o.status || 'active', full_closure: o.full_closure ?? null, roadway: o.roadway || null,
    url: o.url || null, source_url: o.source_url || o.url || null,
  };
}

// ---------- National Weather Service ----------
// Push-worthy events: warnings that call for action now, plus hurricane and tropical storm watches.
const NWS_PUSH = /^(Hurricane|Tropical Storm|Storm Surge|Extreme Wind|Tornado|Flash Flood|Tsunami) (Warning|Watch)$|^(Evacuation Immediate|Civil Emergency Message|Shelter In Place Warning|Law Enforcement Warning|Severe Thunderstorm Warning|Hurricane Local Statement)$/;
const NWS_SEV = {Extreme: 'extreme', Severe: 'severe', Moderate: 'moderate', Minor: 'minor', Unknown: 'info'};
function nwsNotice(f, place, cfg) {
  const p = f.properties || {};
  const text = `${p.headline || ''} ${p.description || ''} ${p.instruction || ''}`;
  const evac = p.event === 'Evacuation Immediate' || (/Hurricane Local Statement|Civil Emergency/.test(p.event) && /\bevacuat/i.test(text) && zonesIn(text).length);
  return notice({
    notice_id: 'nws:' + String(p.id || f.id || '').replace(/^.*\//, ''), place_id: place, kind: evac ? 'evacuation' : 'weather',
    source: cfg.nws.office_name || 'National Weather Service', source_type: 'nws', gov_id: null,
    title: p.headline || p.event, summary: p.description, instruction: p.instruction, severity: NWS_SEV[p.severity] || 'info',
    event: p.event, area: p.areaDesc, zones: evac ? zonesIn(text) : [], issued: iso(p.sent), starts: iso(p.onset || p.effective), ends: iso(p.ends || p.expires),
    updated: iso(p.sent), status: p.messageType === 'Cancel' ? 'lifted' : 'active',
    url: `https://alerts.weather.gov/search?id=${encodeURIComponent(String(p.id || '').replace(/^.*\//, ''))}`, source_url: cfg.nws.url,
  });
}
async function nws(place = 'fl-bay') {
  const cfg = placeConfig(place);
  const d = await get(`https://api.weather.gov/alerts/active?zone=${cfg.nws.zones.join(',')}`, {json: true});
  return (d.features || []).filter(f => (f.properties || {}).status === 'Actual').map(f => nwsNotice(f, place, cfg));
}
// The last week of alerts (active or not), for the archive.
async function nwsRecent(place = 'fl-bay') {
  const cfg = placeConfig(place);
  const d = await get(`https://api.weather.gov/alerts?zone=${cfg.nws.zones.join(',')}&limit=500`, {json: true});
  return (d.features || []).filter(f => (f.properties || {}).status === 'Actual').map(f => ({...nwsNotice(f, place, cfg), status: 'archived'}));
}

// ---------- government alert centers and news feeds (CivicPlus RSS) ----------
function parseRss(xml) {
  const tag = (it, t) => { const m = new RegExp(`<${t}[^>]*>([\\s\\S]*?)</${t}>`, 'i').exec(it); return m ? m[1].replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1').trim() : ''; };
  return [...String(xml || '').matchAll(/<item>([\s\S]*?)<\/item>/gi)].map(m => ({
    title: decode(tag(m[1], 'title')).replace(/\s+/g, ' ').trim(), link: decode(tag(m[1], 'link')), pubDate: tag(m[1], 'pubDate'),
    description: plain(tag(m[1], 'description')), category: decode(tag(m[1], 'category')),
  })).filter(i => i.title);
}
const SEV_OF = {evacuation: 'extreme', shelter: 'severe', 'boil-water': 'moderate', storm: 'moderate', road: 'minor', utility: 'minor'};
function rssNotices(items, feed, place, sourceType) {
  const out = [];
  for (const it of items) {
    // Alert center items are all alerts; news items count only when they're about an emergency topic.
    const kind = sourceType === 'alert-center' ? classify(it.title, it.description) || 'storm' : classify(it.title);
    if (!kind) continue;
    const id = (/[?&](AID|ARC)=(\d+)/i.exec(it.link) || [])[2] || require('crypto').createHash('sha1').update(it.link || it.title).digest('hex').slice(0, 10);
    const text = `${it.title} ${it.description}`;
    out.push(notice({
      notice_id: `${sourceType === 'alert-center' ? 'alert' : 'news'}:${feed.gov}:${id}`, place_id: place, kind, source: feed.name, source_type: sourceType,
      gov_id: feed.gov, title: it.title, summary: it.description, severity: SEV_OF[kind] || 'info', zones: kind === 'evacuation' ? zonesIn(text) : [],
      issued: iso(it.pubDate), updated: iso(it.pubDate), status: (kind === 'boil-water' || kind === 'road' || kind === 'evacuation') && LIFTED.test(it.title) ? 'lifted' : 'active',
      url: it.link, source_url: feed.page || it.link,
    }));
  }
  return out;
}
async function alertCenters(place = 'fl-bay') {
  const cfg = placeConfig(place);
  return settle(cfg.alert_centers.map(f => async () => rssNotices(parseRss(await get(f.url)), f, place, 'alert-center')), cfg.alert_centers.map(f => 'alert:' + f.gov));
}
// News posts stay on the hub for NEWS_DAYS after they're posted (a news post has no end date).
const NEWS_DAYS = 10;
async function newsFeeds(place = 'fl-bay', now = Date.now()) {
  const cfg = placeConfig(place);
  const r = await settle(cfg.news_feeds.map(f => async () => rssNotices(parseRss(await get(f.url)), f, place, 'news')), cfg.news_feeds.map(f => 'news:' + f.gov));
  r.notices = r.notices.map(n => {
    const age = (now - Date.parse(n.issued || 0)) / 864e5;
    return {...n, ends: n.issued ? new Date(Date.parse(n.issued) + NEWS_DAYS * 864e5).toISOString() : null, status: n.status === 'active' && age > NEWS_DAYS ? 'expired' : n.status};
  });
  return r;
}

// ---------- FL511 (state roads) ----------
// FL511 times read like "10/26/26, 8:27 AM", in the Florida 511 map's local time; kept as local ISO without an offset.
function fl511Time(s) {
  const m = /^(\d{1,2})\/(\d{1,2})\/(\d{2}),\s*(\d{1,2}):(\d{2})\s*(AM|PM)$/i.exec(String(s || '').trim());
  if (!m) return null;
  let h = +m[4] % 12; if (/pm/i.test(m[6])) h += 12;
  const p = n => String(n).padStart(2, '0');
  return `20${m[3]}-${p(m[1])}-${p(m[2])}T${p(h)}:${m[5]}`;
}
function fl511Notices(rows, layer, place, cfg) {
  return rows.filter(r => String(r.county || '').toLowerCase() === cfg.fl511.county.toLowerCase())
    // Construction zones only when the road is fully closed; lane work alone is too common to be news.
    .filter(r => layer !== 'Construction' || r.isFullClosure === true || r.isFullClosure === 'True')
    .map(r => {
      const full = r.isFullClosure === true || r.isFullClosure === 'True';
      const desc = plain(r.description);
      return notice({
        notice_id: `fl511:${r.id}`, place_id: place, kind: 'road', source: 'FL511 (Florida Department of Transportation)', source_type: 'fl511', gov_id: null,
        title: `${r.roadwayName || 'Road'}: ${layer === 'Incidents' ? (r.eventSubType && !/^\d+$/.test(r.eventSubType) ? r.eventSubType : 'incident') : full ? 'closed' : 'lane closure'}${r.direction && r.direction !== 'None' ? ' (' + r.direction + ')' : ''}`,
        summary: desc, instruction: r.detourDescription && r.detourDescription !== 'None' ? 'Detour: ' + plain(r.detourDescription) : null,
        severity: full || r.severity === 'Major' ? 'moderate' : 'minor', event: layer === 'Incidents' ? 'Incident' : layer === 'Closures' ? 'Closure' : 'Construction',
        area: [r.locationDescription, r.laneDescription].filter(x => x && x !== 'None').join(' · '), issued: fl511Time(r.startDate), starts: fl511Time(r.startDate),
        ends: fl511Time(r.endDate), updated: fl511Time(r.lastUpdated), full_closure: full, roadway: r.roadwayName || null,
        url: cfg.fl511.url, source_url: cfg.fl511.url,
      });
    });
}
async function fl511(place = 'fl-bay') {
  const cfg = placeConfig(place);
  const q = encodeURIComponent(JSON.stringify({columns: [], start: 0, length: 1000}));
  return settle(cfg.fl511.layers.map(l => async () => fl511Notices((await get(`https://fl511.com/List/GetData/${l}?query=${q}&lang=en`, {json: true})).data || [], l, place, cfg)),
    cfg.fl511.layers.map(l => 'fl511:' + l));
}

// ---------- shelters (Bay County's Emergency Shelters page) ----------
// The page lists shelter groups, each "<Group> - OPEN|CLOSED (current as of <date>)", a sentence about the group, then
// each shelter's name and street address. Returns [{group, status, as_of, about, shelters: [{name, address, note}]}].
function parseShelters(html) {
  const body = (/id="moduleContent"([\s\S]*?)<footer/i.exec(html) || /<main([\s\S]*?)<\/main>/i.exec(html) || [null, html])[1];
  const lines = plain(body).split('\n').map(s => s.trim()).filter(Boolean);
  const groups = [];
  let g = null;
  for (let i = 0; i < lines.length; i++) {
    const L = lines[i];
    const head = /^(.*?(?:Shelters?|Locations?))\s*-\s*(OPEN|CLOSED|ON STANDBY|STANDBY)?\s*(\(current as of ([^)]+)\))?\s*$/i.exec(L);
    if (head) {
      let status = head[2] || '', asText = head[4] || '';
      if (!status && /^(OPEN|CLOSED|ON STANDBY|STANDBY)$/i.test(lines[i + 1] || '')) status = lines[++i];
      const am = !asText && /^\(?current as of ([^)]+)\)?$/i.exec(lines[i + 1] || '');
      if (am) { asText = am[1]; i++; }
      const asOf = asText ? iso(asText.replace('.', '')) : null;
      g = {group: head[1].trim(), status: status.toUpperCase() || 'UNKNOWN', as_of: asOf ? asOf.slice(0, 10) : null, about: '', shelters: []};
      groups.push(g);
      continue;
    }
    if (!g) continue;
    if (/,\s*FL\s+\d{5}/.test(L) && g.shelters.length && !g.shelters[g.shelters.length - 1].address) { g.shelters[g.shelters.length - 1].address = L; continue; }
    if (/^Note:/i.test(L) && g.shelters.length) { g.shelters[g.shelters.length - 1].note = L.replace(/^Note:\s*/i, ''); continue; }
    if (/,\s*FL\s+\d{5}/.test(lines[i + 1] || '')) { g.shelters.push({name: L.replace(/\s+/g, ' '), address: null, note: null}); continue; }
    if (!g.shelters.length && !g.about && L.length > 40) g.about = L;
    if (/^(Activation Information|Disaster Preparedness)$/.test(L)) break; // the side menu starts
  }
  return groups.filter(x => x.shelters.length);
}
const GROUP_TYPE = [[/special needs/i, 'special-needs'], [/general population/i, 'general'], [/mass care/i, 'mass-care'], [/recovery/i, 'recovery'], [/extreme weather|alternate/i, 'extreme-weather'], [/pet/i, 'pet-friendly']];
const groupType = g => (GROUP_TYPE.find(([re]) => re.test(g)) || [null, 'other'])[1];
async function shelters(place = 'fl-bay') {
  const cfg = placeConfig(place);
  const groups = parseShelters(await get(cfg.shelters.page));
  if (!groups.length) throw new Error('shelter page: no shelters found (the page layout may have changed)');
  return groups.flatMap(g => g.shelters.map(s => ({
    shelter_id: slug(s.name), place_id: place, name: s.name, address: s.address, shelter_type: groupType(g.group), group_name: g.group,
    group_about: g.about || null, note: s.note, status: g.status === 'OPEN' ? 'open' : g.status === 'CLOSED' ? 'closed' : g.status.toLowerCase(),
    status_as_of: g.as_of, operator: cfg.shelters.name, source_url: cfg.shelters.page,
  })));
}
// Shelter status changes become notices: an open shelter group is news (and a push).
function shelterNotices(rows, place) {
  const open = rows.filter(r => r.status === 'open');
  const byGroup = new Map();
  for (const r of open) { if (!byGroup.has(r.group_name)) byGroup.set(r.group_name, []); byGroup.get(r.group_name).push(r); }
  return [...byGroup].map(([group, rs]) => notice({
    notice_id: `shelter:${slug(group)}:${rs[0].status_as_of || 'open'}`, place_id: place, kind: 'shelter', source: rs[0].operator, source_type: 'shelters', gov_id: 'county',
    title: `${group} open`, summary: rs.map(r => `${r.name}, ${r.address}`).join('; '), severity: 'severe', issued: rs[0].status_as_of, updated: rs[0].status_as_of,
    status: 'active', url: rs[0].source_url,
  }));
}
const slug = s => String(s || '').toLowerCase().replace(/&/g, ' and ').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 80);

// ---------- evacuation zones ----------
async function zoneAt(lat, lng, place = 'fl-bay') {
  const cfg = placeConfig(place);
  lat = Number(lat); lng = Number(lng);
  if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) throw Object.assign(new Error('lat and lng must be numbers.'), {status: 400, expose: true});
  const u = `${cfg.zones.layer}/query?geometry=${lng},${lat}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=${cfg.zones.field}&returnGeometry=false&f=json`;
  const d = await get(u, {json: true});
  const zones = (d.features || []).map(f => f.attributes[cfg.zones.field]).filter(Boolean).sort();
  return zones[0] || null; // zones don't overlap; the lowest letter is the first to leave if they ever touch
}
const ADDR_DROP = /\b(FL|FLORIDA|USA|PANAMA CITY BEACH|PANAMA CITY|LYNN HAVEN|CALLAWAY|SPRINGFIELD|PARKER|MEXICO BEACH|SOUTHPORT|YOUNGSTOWN|FOUNTAIN|WEST BAY|BAYOU GEORGE)\b/g;
const ADDR_DIR = {NORTH: 'N', SOUTH: 'S', EAST: 'E', WEST: 'W'};
const ADDR_TYPE = {STREET: 'ST', AVENUE: 'AVE', ROAD: 'RD', DRIVE: 'DR', BOULEVARD: 'BLVD', LANE: 'LN', COURT: 'CT', CIRCLE: 'CIR', PLACE: 'PL', PARKWAY: 'PKWY', TRAIL: 'TRL', TERRACE: 'TER'};
// A typed street address -> the first matching Bay County address point. Only the house number and street words are used.
async function geocode(address, place = 'fl-bay') {
  const cfg = placeConfig(place);
  let s = String(address || '').toUpperCase().replace(/[.,'"%_\\#]/g, ' ').replace(/\s\d{5}(-\d{4})?\s*$/, ' ').replace(ADDR_DROP, ' ').replace(/\s+/g, ' ').trim();
  // Bay County's address points write every numbered road as HIGHWAY n (US 98, SR 77, County Road 2321).
  s = s.replace(/\b(?:US|U S|SR|S R|STATE ROAD|STATE RD|CR|C R|COUNTY ROAD|COUNTY RD)\s*(?:HWY|HIGHWAY)?\s*(\d+[A-Z]?)\b/g, 'HIGHWAY $1').replace(/\bHWY\b/g, 'HIGHWAY');
  const m = /^(\d+)\s+(.+)$/.exec(s);
  if (!m) throw Object.assign(new Error('Type a street address with a house number, like 825 Ohio Ave.'), {status: 400, expose: true});
  const words = m[2].split(' ').map(w => ADDR_TYPE[w] || ADDR_DIR[w] || w).filter(w => /^[A-Z0-9]+$/.test(w)).slice(0, 5);
  const sq = x => x.replace(/'/g, "''");
  const tries = [words, words.filter(w => !Object.values(ADDR_TYPE).includes(w) && !/^[NSEW]$/.test(w))];
  for (const ws of tries) {
    if (!ws.length) continue;
    const where = [`ADDRESS LIKE '${m[1]} %'`, ...ws.map(w => `(ADDRESS LIKE '% ${sq(w)} %' OR ADDRESS LIKE '% ${sq(w)}')`)].join(' AND ');
    const d = await get(`${cfg.addresses.layer}/query?where=${encodeURIComponent(where)}&outFields=ADDRESS,CMNTY,ZIP&returnGeometry=true&outSR=4326&resultRecordCount=5&f=json`, {json: true});
    const f = (d.features || [])[0];
    if (f) return {address: f.attributes.ADDRESS, community: f.attributes.CMNTY || null, zip: f.attributes.ZIP || null, lat: f.geometry.y, lng: f.geometry.x};
  }
  return null;
}
async function zoneGeometry(place = 'fl-bay') {
  const cfg = placeConfig(place);
  const d = await get(`${cfg.zones.layer}/query?where=1%3D1&outFields=${cfg.zones.field},LAST_EDIT_DATE&returnGeometry=true&outSR=4326&maxAllowableOffset=0.003&geometryPrecision=4&f=geojson`, {json: true, timeout: 20000});
  return (d.features || []).map(f => ({zone: f.properties[cfg.zones.field], edited: f.properties.LAST_EDIT_DATE ? new Date(f.properties.LAST_EDIT_DATE).toISOString().slice(0, 10) : null, geometry: f.geometry}));
}

// Runs readers side by side; one failing feed never stops the others. Returns {notices, errors: [{source, error}], ok: [source]}.
async function settle(fns, names) {
  const rs = await Promise.allSettled(fns.map(f => f()));
  const out = {notices: [], errors: [], ok: []};
  rs.forEach((r, i) => {
    if (r.status === 'fulfilled') { out.notices.push(...(r.value.notices || r.value)); out.ok.push(names[i]); }
    else out.errors.push({source: names[i], error: String(r.reason && r.reason.message || r.reason).slice(0, 300)});
  });
  return out;
}

// Every live source for a place. Shelter rows come back too, so the caller can store their status.
async function readAll(place = 'fl-bay', now = Date.now()) {
  const parts = await Promise.allSettled([nws(place), alertCenters(place), newsFeeds(place, now), fl511(place), shelters(place)]);
  const out = {notices: [], errors: [], ok: [], shelters: null};
  const [w, ac, nf, rd, sh] = parts;
  if (w.status === 'fulfilled') { out.notices.push(...w.value); out.ok.push('nws'); } else out.errors.push({source: 'nws', error: String(w.reason.message || w.reason)});
  for (const p of [ac, nf, rd]) if (p.status === 'fulfilled') { out.notices.push(...p.value.notices); out.ok.push(...p.value.ok); out.errors.push(...p.value.errors); }
  if (sh.status === 'fulfilled') { out.shelters = sh.value; out.notices.push(...shelterNotices(sh.value, place)); out.ok.push('shelters'); }
  else out.errors.push({source: 'shelters', error: String(sh.reason.message || sh.reason)});
  // The same notice can show up in a government's alert center and its news feed; keep the alert center's.
  const seen = new Set(), keyOf = n => `${n.gov_id}|${n.title.toLowerCase()}`;
  out.notices.sort((a, b) => (a.source_type === 'news') - (b.source_type === 'news'));
  out.notices = out.notices.filter(n => { const k = keyOf(n); if (seen.has(k)) return false; seen.add(k); return true; });
  return out;
}

// Which notices go out as a phone notification, and to which topic. Road closures only when a road is fully closed.
function pushTopic(n) {
  if (n.status !== 'active') return null;
  if (n.kind === 'evacuation') return 'evacuation';
  if (n.kind === 'shelter') return 'shelters';
  if (n.kind === 'boil-water') return 'water';
  if (n.kind === 'weather') return NWS_PUSH.test(n.event || '') ? 'weather' : null;
  if (n.kind === 'road') return n.full_closure ? 'roads' : null;
  return null;
}
const TOPICS = {weather: 'Weather warnings', evacuation: 'Evacuation orders', shelters: 'Shelter openings', water: 'Boil-water notices', roads: 'Full road closures', agenda: 'Agenda items near my saved place'};
const DEFAULT_TOPICS = ['weather', 'evacuation', 'shelters', 'water'];

// Active notices first by how serious they are, then newest.
const SEV_RANK = {extreme: 0, severe: 1, moderate: 2, minor: 3, info: 4};
const byUrgency = (a, b) => (SEV_RANK[a.severity] ?? 5) - (SEV_RANK[b.severity] ?? 5) || String(b.updated || b.issued || '').localeCompare(String(a.updated || a.issued || ''));

module.exports = {SOURCES, placeConfig, plain, decode, clip, classify, zonesIn, parseRss, rssNotices, nwsNotice, nws, nwsRecent, alertCenters, newsFeeds,
  fl511, fl511Notices, fl511Time, parseShelters, shelters, shelterNotices, zoneAt, geocode, zoneGeometry, readAll, pushTopic, TOPICS, DEFAULT_TOPICS,
  byUrgency, NWS_PUSH, NEWS_DAYS, slug, notice};
