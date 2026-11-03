// Maps for road notices that come without one. City and county road closure posts only name streets ("10th Street
// just west of W. Caroline Boulevard to Lisenby Avenue"), so the closed stretch is found on the county's street
// centerline layer: where the cross streets meet the closed street, and the street between them. FL511 (state roads)
// gives each closure's start and end point on its map. The result is the same GeoJSON FeatureCollection staff draw
// (api/_gov.js areaShape), with properties.placed = 'street-names' or 'fl511' so pages can say it was placed, not drawn.

const DIR = {NORTH: 'N', SOUTH: 'S', EAST: 'E', WEST: 'W', N: 'N', S: 'S', E: 'E', W: 'W'};
const TYPE = {STREET: 'ST', ST: 'ST', AVENUE: 'AVE', AVE: 'AVE', AV: 'AVE', ROAD: 'RD', RD: 'RD', DRIVE: 'DR', DR: 'DR', BOULEVARD: 'BLVD', BLVD: 'BLVD',
  LANE: 'LN', LN: 'LN', COURT: 'CT', CT: 'CT', CIRCLE: 'CIR', CIR: 'CIR', PLACE: 'PL', PL: 'PL', PARKWAY: 'PKWY', PKWY: 'PKWY', TRAIL: 'TRL', TRL: 'TRL',
  TERRACE: 'TER', TER: 'TER', WAY: 'WAY', HIGHWAY: 'HWY', HWY: 'HWY'};

// "W. Caroline Boulevard" -> {dir: 'W', name: 'CAROLINE', type: 'BLVD'}. Numbered highways read like the county layer
// writes them (NAME '98', '231', '2321'). null when nothing street-like is left.
function street(s) {
  let t = String(s || '').toUpperCase().replace(/[.,;()'"]/g, ' ').replace(/\s+/g, ' ').trim();
  t = t.replace(/^(THE|AND|OF)\s+/, '');
  const hwy = /\b(?:US|U S|SR|S R|STATE ROAD|STATE RD|CR|C R|COUNTY ROAD|COUNTY RD|HIGHWAY|HWY)\s*(\d+[A-Z]?)\b/.exec(t);
  if (hwy) return {dir: null, name: hwy[1], type: null};
  const w = t.split(' ').filter(Boolean);
  let dir = null, type = null;
  if (w.length > 1 && DIR[w[0]]) dir = DIR[w.shift()];
  if (w.length > 1 && TYPE[w[w.length - 1]]) type = TYPE[w.pop()];
  const name = w.join(' ');
  if (!name || name.length > 40 || !/^[A-Z0-9 ]+$/.test(name)) return null;
  return {dir, name, type};
}

const LEAD = /^(?:road|street|lane)\s+(?:closure|closing|work)s?(?:\s+notice)?\s*[:\-–—]\s*/i;
const SIDE = /\s+(?:just\s+|immediately\s+)?(?:west|east|north|south)\s+of\s+/i;

// The stretches a notice names: [{main, from, to}] (to null for one cross street) from the title, then the summary.
function stretches(n) {
  const out = [];
  const tryText = raw => {
    const text = String(raw || '').replace(LEAD, '').replace(/\s+/g, ' ').trim();
    // "Florida Avenue: W. 7th Street to W. 8th Street - W. 7th Street: Ohio Avenue to Florida Avenue"
    for (const m of text.matchAll(/(?:^|[-–—•]\s)([A-Za-z0-9. ]{2,40}?):\s*([A-Za-z0-9. ]{2,40}?)\s+to\s+([A-Za-z0-9. ]{2,40}?)(?=\s+[-–—•]\s|\s+Detour|[.;]|$)/g)) {
      out.push({main: m[1], from: m[2], to: m[3]});
    }
    if (out.length) return;
    let m = /^(.{2,40}?)\s+between\s+(.{2,40}?)\s+and\s+(.{2,40}?)(?:[.;,]|\s+(?:for|due|beginning|starting|from|on)\b|$)/i.exec(text);
    if (m) return out.push({main: m[1], from: m[2], to: m[3]});
    m = /^(.{2,40}?)\s+from\s+(.{2,40}?)\s+to\s+(.{2,40}?)(?:[.;,]|\s+(?:for|due|beginning|starting|on)\b|$)/i.exec(text);
    if (m) return out.push({main: m[1].split(SIDE)[0], from: m[2].split(SIDE).pop(), to: m[3]});
    m = new RegExp(`^(.{2,40}?)${SIDE.source}(.{2,40}?)\\s+to\\s+(.{2,40}?)(?:[.;,]|$)`, 'i').exec(text);
    if (m) return out.push({main: m[1], from: m[2], to: m[3]});
    m = /^(.{2,40}?)\s+(?:&|and|at)\s+(.{2,40}?)(?:\s+(?:intersection\s+)?(?:closure|closed|closing|road work)\b.*)?$/i.exec(text);
    if (m) return out.push({main: m[1], from: m[2], to: null});
  };
  tryText(n.title);
  // A title that names only a corner ("Florida Avenue & W. 7th Street Closure") gives way to stretches in the text.
  if (!out.length || out.every(s => !s.to)) {
    const first = out.splice(0);
    tryText(n.summary);
    if (!out.some(s => s.to)) { out.splice(0); out.push(...first); }
  }
  return out.map(s => ({main: street(s.main), from: street(s.from), to: s.to ? street(s.to) : null})).filter(s => s.main && s.from && (s.to || s.to === null));
}

// ---------- geometry on [lng, lat] points ----------
const M_LAT = 111320;
const meters = (a, b) => { const k = Math.cos(a[1] * Math.PI / 180); return Math.hypot((a[0] - b[0]) * M_LAT * k, (a[1] - b[1]) * M_LAT); };
// The closest point on segment p-q to x, and how far it is.
function nearestOnSeg(x, p, q) {
  const k = Math.cos(x[1] * Math.PI / 180);
  const dx = (q[0] - p[0]) * k, dy = q[1] - p[1];
  const len = dx * dx + dy * dy;
  let t = len ? (((x[0] - p[0]) * k) * dx + (x[1] - p[1]) * dy) / len : 0;
  t = Math.max(0, Math.min(1, t));
  const pt = [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t];
  return {pt, d: meters(x, pt)};
}
// Where two streets meet (within `tol` meters): one point per crossing, from the vertices of each near the other.
function crossings(pathsA, pathsB, tol = 15) {
  const hits = [];
  const near = (pts, paths) => {
    for (const x of pts) {
      for (const path of paths) for (let i = 1; i < path.length; i++) {
        const r = nearestOnSeg(x, path[i - 1], path[i]);
        if (r.d <= tol) hits.push(x);
      }
    }
  };
  near(pathsA.flat(), pathsB);
  near(pathsB.flat(), pathsA);
  // One point per crossing: group hits within 40 m.
  const out = [];
  for (const h of hits) if (!out.some(o => meters(o, h) < 40)) out.push(h);
  return out;
}
// The street between two points on it: the shortest way along its centerline pieces (vertices joined within 2 m).
function along(paths, a, b) {
  const key = p => `${p[0].toFixed(5)},${p[1].toFixed(5)}`;
  const nodes = new Map(), edges = new Map();
  const add = p => { const k = key(p); if (!nodes.has(k)) { nodes.set(k, p); edges.set(k, []); } return k; };
  for (const path of paths) for (let i = 1; i < path.length; i++) {
    const u = add(path[i - 1]), v = add(path[i]), w = meters(path[i - 1], path[i]);
    edges.get(u).push([v, w]); edges.get(v).push([u, w]);
  }
  const closest = x => { let best = null, bd = Infinity; for (const [k, p] of nodes) { const d = meters(x, p); if (d < bd) { bd = d; best = k; } } return bd < 40 ? best : null; };
  const s = closest(a), t = closest(b);
  if (!s || !t) return null;
  const dist = new Map([[s, 0]]), prev = new Map(), done = new Set();
  while (true) {
    let u = null, ud = Infinity;
    for (const [k, d] of dist) if (!done.has(k) && d < ud) { u = k; ud = d; }
    if (u === null || u === t) break;
    done.add(u);
    for (const [v, w] of edges.get(u)) if (!done.has(v) && ud + w < (dist.get(v) ?? Infinity)) { dist.set(v, ud + w); prev.set(v, u); }
  }
  if (!dist.has(t) || dist.get(t) > 8000) return null;
  const line = [];
  for (let k = t; k; k = prev.get(k)) { line.unshift(nodes.get(k)); if (k === s) break; }
  return line.length >= 2 ? line : null;
}

const r6 = v => Math.round(v * 1e6) / 1e6;
const pt = p => [r6(p[0]), r6(p[1])];
function collection(features, placed) {
  return JSON.stringify({type: 'FeatureCollection', features: features.map(f => ({...f, properties: {...(f.properties || {}), placed}}))});
}
// An empty collection: looked and found nothing, so the poller doesn't look again for this notice. Apps and pages draw
// no map for it (AlertArea.parse returns nil for no features).
const NONE = JSON.stringify({type: 'FeatureCollection', features: [], properties: {placed: 'none'}});

// ---------- the county street layer ----------
const sq = s => String(s).replace(/'/g, "''");
async function streetPaths(get, layer, s, cache, comm) {
  const where = [`NAME = '${sq(s.name)}'`];
  if (s.dir) where.push(`(PREDIR = '${s.dir}' OR PREDIR IS NULL OR PREDIR = ' ')`);
  const k = where.join(' AND ') + '|' + (s.type || '') + '|' + (comm || '');
  if (cache.has(k)) return cache.get(k);
  const u = `${layer}/query?where=${encodeURIComponent(where.join(' AND '))}&outFields=POSTTYPE,LCOMM,RCOMM&returnGeometry=true&outSR=4326&geometryPrecision=6&resultRecordCount=2000&f=json`;
  const d = await get(u, {json: true});
  let feats = d.features || [];
  // In the posting city when it has that street (Michigan Ave runs through Panama City and Lynn Haven).
  const inCity = comm ? feats.filter(f => [f.attributes.LCOMM, f.attributes.RCOMM].some(c => String(c || '').trim() === comm)) : [];
  if (inCity.length) feats = inCity;
  // The street type when the notice gives one (10th St, not 10th Ct), else every type of that name.
  const typed = s.type ? feats.filter(f => String(f.attributes.POSTTYPE || '').trim() === s.type) : feats;
  const paths = (typed.length ? typed : feats).flatMap(f => (f.geometry && f.geometry.paths) || []);
  cache.set(k, paths);
  return paths;
}

// The map for one stretch: a line along the closed street between its cross streets, or a pin where two meet.
async function stretchFeature(get, layer, s, cache, comm) {
  const main = await streetPaths(get, layer, s.main, cache, comm);
  if (!main.length) return null;
  const A = crossings(main, await streetPaths(get, layer, s.from, cache, comm));
  if (!A.length) return null;
  if (!s.to) return {type: 'Feature', properties: {radius_m: 60}, geometry: {type: 'Point', coordinates: pt(A[0])}};
  const B = crossings(main, await streetPaths(get, layer, s.to, cache, comm));
  if (!B.length) return {type: 'Feature', properties: {radius_m: 60}, geometry: {type: 'Point', coordinates: pt(A[0])}};
  // The pair of crossings closest together (a cross street can meet a long road more than once).
  let best = null;
  for (const a of A) for (const b of B) { const d = meters(a, b); if (d > 1 && (!best || d < best.d)) best = {a, b, d}; }
  if (!best || best.d > 8000) return null;
  const line = along(main, best.a, best.b) || [best.a, best.b];
  return {type: 'Feature', properties: {}, geometry: {type: 'LineString', coordinates: line.map(pt)}};
}

// A road notice's map from the street names it gives, or NONE. Never throws.
async function streetMap(n, cfg, get) {
  if (!cfg.roads || !cfg.roads.layer) return null;
  const list = stretches(n).slice(0, 4);
  if (!list.length) return NONE;
  const cache = new Map(), feats = [], comm = (cfg.roads.communities || {})[n.gov_id] || null;
  for (const s of list) {
    try { const f = await stretchFeature(get, cfg.roads.layer, s, cache, comm); if (f) feats.push(f); } catch (e) { return null; } // try again next check
  }
  return feats.length ? collection(feats, 'street-names') : NONE;
}

// FL511's map points (start, and end when it gives one) per closure id, from its map icon list.
async function fl511Points(get, layer) {
  const d = await get(`https://fl511.com/map/mapIcons/${layer}`, {json: true});
  const out = new Map();
  for (const i of (d && d.item2) || []) {
    const ok = p => Array.isArray(p) && p.length >= 2 && Number.isFinite(+p[0]) && Number.isFinite(+p[1]) && Math.abs(+p[0]) <= 90;
    if (ok(i.location)) out.set(String(i.itemId), [i.location, ok(i.secondarylocation) ? i.secondarylocation : null]);
  }
  return out;
}
function fl511Map(points) {
  if (!points) return null;
  const [a, b] = points;
  const P = p => ({type: 'Feature', properties: {}, geometry: {type: 'Point', coordinates: [r6(+p[1]), r6(+p[0])]}});
  const feats = [P(a)];
  // The end point as a second pin (a straight line between them could cut across land).
  if (b && meters([+a[1], +a[0]], [+b[1], +b[0]]) > 30) feats.push(P(b));
  return collection(feats, 'fl511');
}

module.exports = {street, stretches, crossings, along, streetMap, fl511Points, fl511Map, NONE};
