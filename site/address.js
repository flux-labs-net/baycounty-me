(() => {
const D = __ADDR__;
const X = __ADDR_TXT__;
const fmt = (s, o) => s.replace(/\{(\w+)\}/g, (m, k) => o[k] ?? m);
const GIS = 'https://gis.baycountyfl.gov/arcgis/rest/services';
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const usd = n => '$' + Math.round(n).toLocaleString('en-US');
const big = n => n >= 1e6 ? '$' + (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? '$' + Math.round(n / 1e3) + 'K' : usd(n);
const title = s => String(s || '').toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase()).replace(/\b(Ne|Nw|Se|Sw|Us|Cr|Sr)\b/g, m => m.toUpperCase());
const GI = Object.fromEntries(D.groups.map(([g], i) => [g, i + 1]));
const GN = Object.fromEntries(D.groups);

async function q(path, params) {
  const u = new URL(`${GIS}/${path}/query`);
  Object.entries({f: 'json', returnGeometry: 'false', outFields: '*', ...params}).forEach(([k, v]) => u.searchParams.set(k, v));
  const r = await fetch(u, {mode: 'cors'});
  if (!r.ok) throw new Error('GIS ' + r.status);
  const j = await r.json();
  if (j.error) throw new Error(j.error.message || 'GIS error');
  return j.features || [];
}
const atPoint = (path, pt, extra = {}) => q(path, {geometry: JSON.stringify({x: pt.x, y: pt.y, spatialReference: {wkid: 4326}}), geometryType: 'esriGeometryPoint', inSR: 4326, spatialRel: 'esriSpatialRelIntersects', ...extra}).then(f => f.map(x => x.attributes)).catch(() => null);

/* FEMA National Flood Hazard Layer: the official, current flood map. The county's copy (Admin_A12/51) is older. */
const NFHL = 'https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer';
async function femaAt(layer, pt, fields) {
  const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), 15000);
  try {
    const r = await fetch(`${NFHL}/${layer}/query?` + new URLSearchParams({geometry: JSON.stringify({x: pt.x, y: pt.y, spatialReference: {wkid: 4326}}), geometryType: 'esriGeometryPoint', inSR: 4326, spatialRel: 'esriSpatialRelIntersects', outFields: fields, returnGeometry: 'false', f: 'json'}), {mode: 'cors', signal: ctl.signal});
    const j = await r.json(); if (j.error) throw new Error(j.error.message);
    return (j.features || []).map(f => f.attributes);
  } finally { clearTimeout(t); }
}
async function floodAt(pt) {
  try {
    const [zones, panels, lomr] = await Promise.all([
      femaAt(28, pt, 'FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE,V_DATUM,DEPTH').catch(() => femaAt(28, pt, 'FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE,V_DATUM,DEPTH')),
      femaAt(3, pt, 'FIRM_PAN,EFF_DATE').catch(() => []),
      femaAt(1, pt, 'CASE_NO,EFF_DATE').catch(() => [])]);
    const rank = z => (z.SFHA_TF === 'T' ? 1000 : 0) + (/^V/.test(z.FLD_ZONE) ? 500 : 0) + (z.STATIC_BFE > 0 ? z.STATIC_BFE : 0) + (/0\.2/.test(z.ZONE_SUBTY || '') ? 100 : 0);
    zones.sort((a, b) => rank(b) - rank(a));
    return {src: 'fema', zone: zones[0] || null, panel: panels[0] || null, lomr: lomr[0] || null};
  } catch (e) {
    const c = await atPoint('Admin_A12/MapServer/51', pt);
    return c === null ? null : {src: 'county', zone: c[0] || null, panel: null, lomr: null};
  }
}

/* Zoning and development near an address. Layers from Bay County GIS and the cities' ArcGIS Online
   services (see data/nearby/layers.json). Explicit field lists only: some layers carry owner names. */
const GISB = 'https://gis.baycountyfl.gov/arcgis/rest/services';
async function arcq(url, pt, opts) {
  const p = new URLSearchParams({geometry: `${pt.x},${pt.y}`, geometryType: 'esriGeometryPoint', inSR: 4326, outSR: 4326, spatialRel: 'esriSpatialRelIntersects', returnGeometry: 'false', f: 'json', ...opts});
  const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), 15000);
  try { const r = await fetch(url + '/query?' + p, {mode: 'cors', signal: ctl.signal}); const j = await r.json(); if (j.error) throw new Error(j.error.message); return (j.features || []).map(f => ({...f.attributes, _g: f.geometry})); }
  finally { clearTimeout(t); }
}
const safe = pr => pr.catch(() => null);
const JUR = {BC: 'county code', LH: 'Lynn Haven code', PC: 'Panama City code', PCB: 'Panama City Beach code', CW: 'Callaway code', SF: 'Springfield code', SP: 'Springfield code', PK: 'Parker code', MB: 'Mexico Beach code'};
const bare = v => code(v).replace(/ \([^)]*code\)$/, '');
const code = v => String(v || '').replace(/^v\s+/i, '').replace(/\s*\(([A-Z]+)\)\s*$/, (m, j) => JUR[j] ? ` (${JUR[j]})` : m).trim();
const dstr = v => { if (v == null || v === '') return ''; const d = typeof v === 'number' ? new Date(v) : new Date(String(v).length === 10 ? v + 'T12:00:00' : v); return isNaN(d) || d.getFullYear() < 1990 ? '' : d.toLocaleDateString('en-US', {month: 'short', year: 'numeric'}); };
const dnum = v => { const d = typeof v === 'number' ? new Date(v) : new Date(v); return isNaN(d) ? 0 : d.getTime(); };
const milesTo = (a, g) => { if (!g || g.x == null) return null; const R = 3958.8, toR = x => x * Math.PI / 180, dy = toR(g.y - a.y), dx = toR(g.x - a.x) * Math.cos(toR(a.y)); return R * Math.sqrt(dx * dx + dy * dy); };
async function loadDev(pt, cityName) {
  const el = $('devBody'); if (!el) return;
  el.innerHTML = '<p class="muted small">Loading…</p>';
  const half = {distance: 0.5, units: 'esriSRUnit_StatuteMile'}, since = new Date(Date.now() - 5 * 365.25 * 864e5).toISOString().slice(0, 10);
  const PC = 'https://services3.arcgis.com/RfAh242jlP6Nb5vP/arcgis/rest/services', AGO = 'https://services1.arcgis.com/QB0VWfqR9MD4lF0F/arcgis/rest/services';
  const inPC = cityName === 'Panama City', inPCB = cityName === 'Panama City Beach';
  const [zon, flu, pcz, pcf, pcbf, dos, lhd, pcbd, rez, pcr, cond] = await Promise.all([
    safe(arcq(`${GISB}/LandUsePlanning/MapServer/1`, pt, {outFields: 'ZONING,Label,ORD_NUM,ORD_DATE'})),
    safe(arcq(`${GISB}/LandUsePlanning/MapServer/2`, pt, {outFields: 'FLU_CODE,Label,ORD_NUM,ORD_DATE'})),
    inPC ? safe(arcq(`${PC}/Zoning_CPC/FeatureServer/0`, pt, {outFields: 'LABEL,ZONE_TYPE,ordinance,ordinancedate'})) : null,
    inPC ? safe(arcq(`${PC}/FutureLandUse_CPC/FeatureServer/0`, pt, {outFields: 'LANDUSE'})) : null,
    inPCB ? safe(arcq(`${GISB}/PanamaCityBeach/PanamaCityBeachPublic/MapServer/8`, pt, {outFields: 'FLU_CODE,Label'})) : null,
    safe(arcq(`${GISB}/Departmental/Planning/MapServer/18`, pt, {...half, outFields: 'NAME,NUMBER,DESCRIPTION,SIZE,LOCATION,APPLICATION_RECEIVED,DO_ISSUED,TYPE', returnGeometry: 'true'})),
    safe(arcq(`${AGO}/LH_Development_Planning_Projects/FeatureServer/0`, pt, {...half, outFields: 'Project,Number_of_Units,Acres,Address,DO_Status,City_Commission_Approval_Date,DO_Expires', returnGeometry: 'true'})),
    safe(arcq(`${AGO}/PCB_Planning_Projects_Editing/FeatureServer/0`, pt, {...half, outFields: 'TYPE,Name,SIZE,DEVTYPE,DateApplied,DateIssued', returnGeometry: 'true'})),
    safe(arcq(`${GISB}/LandUsePlanning/MapServer/1`, pt, {...half, where: `ORD_DATE >= DATE '${since}'`, outFields: 'ZONING,Label,ORD_NUM,ORD_DATE,COMMENTS', orderByFields: 'ORD_DATE DESC'})),
    inPC ? safe(arcq(`${PC}/Zoning_CPC/FeatureServer/0`, pt, {...half, where: `ordinancedate >= DATE '${since}'`, outFields: 'LABEL,ZONE_TYPE,ordinance,ordinancedate,previouszone'})) : null,
    safe(arcq(`${GISB}/Departmental/Planning/MapServer/17`, pt, {distance: 0.25, units: 'esriSRUnit_StatuteMile', outFields: 'REF__NUM,TYPE,CONDITION,CONDITION2,CONDITION3', returnGeometry: 'true'})),
  ]);
  const z = pcz?.[0] ? `${pcz[0].LABEL}${pcz[0].ZONE_TYPE ? ' (' + pcz[0].ZONE_TYPE + ')' : ''}` : zon?.[0] ? (zon[0].ZONING === 'See FLU' ? 'Set by the future land use map' : code(zon[0].Label || zon[0].ZONING)) : null;
  const fl = pcf?.[0]?.LANDUSE || code(pcbf?.[0]?.Label || flu?.[0]?.Label || flu?.[0]?.FLU_CODE) || null;
  // projects: merge county, Lynn Haven and PCB layers
  const proj = [];
  (dos || []).forEach(d => proj.push({n: d.NAME, d: d.DESCRIPTION, s: d.TYPE, a: d.LOCATION, t: dnum(d.DO_ISSUED || d.APPLICATION_RECEIVED), when: d.DO_ISSUED ? 'issued ' + dstr(d.DO_ISSUED) : d.APPLICATION_RECEIVED ? 'applied ' + dstr(d.APPLICATION_RECEIVED) : '', mi: milesTo(pt, d._g), src: 'Bay County'}));
  (lhd || []).forEach(d => proj.push({n: (d.Project || '').trim(), d: [d.Number_of_Units && d.Number_of_Units !== 'N/A' ? d.Number_of_Units + ' units' : '', d.Acres ? d.Acres + ' acres' : ''].filter(Boolean).join(', '), s: d.DO_Status, a: d.Address, t: dnum(d.City_Commission_Approval_Date), when: d.City_Commission_Approval_Date ? 'approved ' + dstr(d.City_Commission_Approval_Date) : '', mi: milesTo(pt, d._g), src: 'Lynn Haven'}));
  (pcbd || []).forEach(d => proj.push({n: d.Name, d: d.TYPE, s: d.DEVTYPE, a: '', t: dnum(d.DateIssued || d.DateApplied), when: d.DateIssued ? 'issued ' + dstr(d.DateIssued) : d.DateApplied ? 'applied ' + dstr(d.DateApplied) : '', mi: milesTo(pt, d._g), src: 'Panama City Beach'}));
  const recent = proj.filter(p => !p.t || p.t >= Date.now() - 5 * 365.25 * 864e5).sort((a, b) => b.t - a.t).slice(0, 8);
  const rz = [...(rez || []).map(r => ({z: bare(r.Label || r.ZONING), o: r.ORD_NUM, t: dnum(r.ORD_DATE), prev: bare((r.COMMENTS || '').replace(/^pre\.?\s*/i, ''))})),
              ...(pcr || []).map(r => ({z: bare(r.LABEL), zc: bare(r.LABEL), o: r.ordinance, t: dnum(r.ordinancedate), prev: bare(r.previouszone || '')}))]
    .filter(r => r.t && r.t <= Date.now() + 864e5 && (!r.prev || r.prev.split(' (')[0] !== (r.zc || r.z).split(' (')[0]));
  const byOrd = new Map();
  rz.forEach(r => { const k = String(r.o); if (!byOrd.has(k)) byOrd.set(k, {o: r.o, t: r.t, ch: []}); const g = byOrd.get(k); const c = (r.prev ? r.prev + ' \u2192 ' : 'to ') + r.z; if (!g.ch.includes(c)) g.ch.push(c); });
  const uniq = [...byOrd.values()].sort((a, b) => b.t - a.t).slice(0, 5);
  const cu = (cond || []).filter(c => c.TYPE).slice(0, 4);
  const fail = [zon, flu, dos].every(x => x === null);
  if (fail) { el.innerHTML = '<p class="muted">Bay County\'s planning maps didn\'t answer. Try again in a moment.</p>'; return; }
  el.innerHTML = `<dl class="kv">${kv([['Zoning', z ? `<b>${esc(z)}</b>` : '<span class="muted">Not mapped</span>'], ['Future land use', fl ? `<b>${esc(fl)}</b> <span class="muted small">what the long-range plan allows</span>` : '<span class="muted">Not mapped</span>']])}</dl>
    <h4 class="dev-h">Development projects within half a mile <span class="muted small">last 5 years</span></h4>
    ${recent.length ? `<ul class="dev-list">${recent.map(p => `<li><b>${esc(p.n || 'Project')}</b>${p.d ? ` · ${esc(p.d)}` : ''}<br><span class="muted small">${[p.s, p.when, p.a, p.mi != null ? p.mi.toFixed(1) + ' mi away' : '', p.src].filter(Boolean).map(esc).join(' · ')}</span></li>`).join('')}</ul>` : '<p class="small muted">None on file nearby.</p>'}
    <h4 class="dev-h">Rezonings within half a mile <span class="muted small">last 5 years, adopted</span></h4>
    ${uniq.length ? `<ul class="dev-list">${uniq.map(g => `<li><b>Ordinance ${esc(g.o)}</b> <span class="muted small">${esc(dstr(g.t))}</span><br>${g.ch.slice(0, 4).map(esc).join('; ')}${g.ch.length > 4 ? ` and ${g.ch.length - 4} more` : ''}</li>`).join('')}</ul>` : '<p class="small muted">None nearby.</p>'}
    ${cu.length ? `<h4 class="dev-h">Conditional uses within a quarter mile</h4><ul class="dev-list">${cu.map(c => `<li><b>${esc(c.TYPE)}</b> ${esc([c.CONDITION, c.CONDITION2, c.CONDITION3].filter(Boolean).join(' '))}<br><span class="muted small">${esc(c.REF__NUM || '')}</span></li>`).join('')}</ul>` : ''}
    <p class="small muted">Building permits aren't published as open data. Search them on <a href="https://portal.baycountyfl.gov/Permit/Locator" target="_blank" rel="noopener">Bay County's permit portal</a>${inPCB ? ' or <a href="https://panamacitybeach.portal.iworq.net/PANAMACITYBEACH/permits/602" target="_blank" rel="noopener">Panama City Beach\'s</a>' : ''}. Zoning and projects come from Bay County, Panama City, Lynn Haven and Panama City Beach planning maps; pending rezoning applications aren't mapped.</p>`;
}

/* ---------- autocomplete ---------- */
const inp = $('q'), list = $('acList');
let timer, items = [], active = -1, seq = 0;
function clean(s) { return s.toUpperCase().replace(/['"%_\\]/g, '').replace(/\s+/g, ' ').trim(); }
inp.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(suggest, 220); });
/* Address parsing: the county stores USPS abbreviations (DR, AVE, N), spelled-out highways
   ("W HIGHWAY 98"), "SAINT" or "ST", and ordinals like "10TH". People type all sorts of variants,
   so we normalize what they type, match the words in any order, and relax if nothing matches. */
const TYPES = {DRIVE: 'DR', DRV: 'DR', DR: 'DR', STREET: 'ST', STR: 'ST', ST: 'ST', AVENUE: 'AVE', AV: 'AVE', AVN: 'AVE', AVE: 'AVE', ROAD: 'RD', RD: 'RD',
  BOULEVARD: 'BLVD', BLV: 'BLVD', BLVD: 'BLVD', LANE: 'LN', LN: 'LN', COURT: 'CT', CRT: 'CT', CT: 'CT', COURTS: 'CTS', CIRCLE: 'CIR', CIRC: 'CIR', CIR: 'CIR',
  PLACE: 'PL', PL: 'PL', TERRACE: 'TER', TERR: 'TER', TER: 'TER', TRAIL: 'TRL', TR: 'TRL', TRL: 'TRL', PARKWAY: 'PKWY', PKY: 'PKWY', PKWY: 'PKWY',
  PLAZA: 'PLZ', PLZ: 'PLZ', POINT: 'PT', PT: 'PT', COVE: ['COVE', 'CV'], CV: ['COVE', 'CV'], CROSSING: 'XING', XING: 'XING', LANDING: 'LNDG', LNDG: 'LNDG',
  MANOR: 'MNR', MNR: 'MNR', SQUARE: 'SQ', SQ: 'SQ', ALLEY: 'ALY', ALY: 'ALY', BEND: 'BND', BND: 'BND', GARDENS: 'GDNS', GDNS: 'GDNS', KNOLL: 'KNL', KNL: 'KNL',
  TRACE: 'TRCE', TRCE: 'TRCE', CORNER: 'COR', COR: 'COR', LOOP: 'LOOP', RUN: 'RUN', PATH: 'PATH', PASS: 'PASS', WAY: 'WAY', TURN: 'TURN', ISLE: 'ISLE'};
const DIRS = {NORTH: 'N', SOUTH: 'S', EAST: 'E', WEST: 'W', NORTHWEST: 'NW', N: 'N', S: 'S', E: 'E', W: 'W', NW: 'NW'};
const ORD = {FIRST: '1ST', SECOND: '2ND', THIRD: '3RD', FOURTH: '4TH', FIFTH: '5TH', SIXTH: '6TH', SEVENTH: '7TH', EIGHTH: '8TH', NINTH: '9TH', TENTH: '10TH',
  ELEVENTH: '11TH', TWELFTH: '12TH', THIRTEENTH: '13TH', FOURTEENTH: '14TH', FIFTEENTH: '15TH', SIXTEENTH: '16TH', SEVENTEENTH: '17TH', EIGHTEENTH: '18TH', NINETEENTH: '19TH', TWENTIETH: '20TH'};
const PLACES = ['PANAMA CITY BEACH', 'PANAMA CITY', 'LYNN HAVEN', 'CALLAWAY', 'SPRINGFIELD', 'PARKER', 'MEXICO BEACH', 'SOUTHPORT', 'FOUNTAIN', 'YOUNGSTOWN', 'TYNDALL AFB', 'BAYOU GEORGE', 'BAY COUNTY'];
function parseAddr(raw) {
  let s = raw.toUpperCase().replace(/[.,'"%_\\]/g, ' ').replace(/\s+/g, ' ').trim();
  s = s.replace(/\b(FL|FLORIDA)\b/g, ' ').replace(/\b\d{5}(-\d{4})?\s*$/, ' ').replace(/\s+/g, ' ').trim();
  let place = '';
  for (const p of PLACES) { const re = new RegExp(`\\s${p}$`); if (re.test(s)) { place = p; s = s.replace(re, '').trim(); break; } }
  let unit = '';
  const um = /\s(?:#\s*|(?:APT|APARTMENT|UNIT|STE|SUITE|BLDG|LOT|RM|SPC|TRLR)\s+#?\s*)([A-Z0-9-]+)\s*$/.exec(s);
  if (um) { unit = um[1]; s = s.slice(0, um.index).trim(); }
  const hm = /^(\d+)\s*([A-Z])?\s+(.*)$/.exec(s) || /^(\d+)$/.exec(s);
  if (!hm) return null;
  const house = hm[1], rest = (hm[3] || '').trim();
  let w = rest ? rest.split(' ') : [];
  // highway forms: HWY 98, US 98, US HWY 98, SR 77, STATE ROAD 77, CR 2321, COUNTY ROAD 2321 -> HIGHWAY n
  const joined = w.join(' ').replace(/\b(?:US|U S|SR|S R|STATE ROAD|STATE RD|CR|C R|COUNTY ROAD|COUNTY RD)\s*(?:HWY|HIGHWAY)?\s*(\d+[A-Z]?)\b/g, 'HIGHWAY $1')
    .replace(/\bHWY\b/g, 'HIGHWAY').replace(/\bMLK\b/g, 'MARTIN LUTHER KING JR').replace(/\bJUNIOR\b/g, 'JR').replace(/\bMOUNT\b/g, 'MT');
  w = joined ? joined.split(' ') : [];
  const toks = []; // {alts:[...], kind:'name'|'type'|'dir'}
  w.forEach((t, i) => {
    const last = i === w.length - 1;
    if (ORD[t]) { toks.push({alts: [ORD[t]], kind: 'name'}); return; }
    if (DIRS[t] && (i === 0 || last)) { toks.push({alts: [DIRS[t]], kind: 'dir'}); return; }
    if ((t === 'ST' || t === 'SAINT') && !last) { toks.push({alts: ['ST', 'SAINT'], kind: 'name', word: true}); return; }
    if (TYPES[t] && last && i > 0) { const v = TYPES[t]; toks.push({alts: Array.isArray(v) ? v : [v], kind: 'type'}); return; }
    toks.push({alts: [t], kind: 'name', partial: last});
  });
  return {house, unit, place, toks};
}
const sq = s => s.replace(/'/g, "''");
function whereFor(a, keep) {
  const parts = [`ADDRESS LIKE '${a.house} %'`];
  a.toks.filter(t => keep.includes(t.kind)).forEach(t => {
    const ors = t.alts.map(x => t.kind === 'name' && !t.word ? (t.partial ? `ADDRESS LIKE '% ${sq(x)}%'` : `(ADDRESS LIKE '% ${sq(x)} %' OR ADDRESS LIKE '% ${sq(x)}')`)
      : `(ADDRESS LIKE '% ${sq(x)} %' OR ADDRESS LIKE '% ${sq(x)}')`);
    parts.push('(' + ors.join(' OR ') + ')');
  });
  if (a.unit) parts.push(`(UNIT = '${sq(a.unit)}' OR UNIT LIKE '${sq(a.unit)}%')`);
  return parts.join(' AND ');
}
async function findAddr(a) {
  const opts = {outFields: 'ADDRESS,UNIT,CMNTY,ZIP,RENUM', returnGeometry: 'true', outSR: 4326, resultRecordCount: 25, orderByFields: 'ADDRESS'};
  // strict, then without direction/type (they're often typed differently), then without the unit
  const tries = [['name', 'type', 'dir'], ['name']];
  for (const keep of tries) {
    const f = await q('Admin_A12/MapServer/3', {where: whereFor(a, keep), ...opts});
    if (f.length) return {f, relaxed: keep.length === 1 && a.toks.some(t => t.kind !== 'name')};
  }
  if (a.unit) { const f = await q('Admin_A12/MapServer/3', {where: whereFor({...a, unit: ''}, ['name']), ...opts}); if (f.length) return {f, relaxed: true}; }
  return {f: [], relaxed: false};
}
async function suggest() {
  const a = parseAddr(inp.value);
  if (!a || (!a.toks.length && inp.value.trim().length < 3)) { hideList(); return; }
  if (!a.toks.length) { hideList(); return; }
  const my = ++seq;
  try {
    let {f, relaxed} = await findAddr(a);
    if (my !== seq) return;
    if (a.place) f.sort((x, y) => ((y.attributes.CMNTY || '').toUpperCase() === a.place) - ((x.attributes.CMNTY || '').toUpperCase() === a.place));
    f = f.slice(0, 10);
    items = f; active = -1;
    if (!f.length) { list.innerHTML = '<li class="ac-empty">No matching address. Check the house number, or try just the number and street name (for example "1614 Ohio").</li>'; showList(); return; }
    list.innerHTML = (relaxed ? '<li class="ac-empty ac-note">Closest matches:</li>' : '') + f.map((x, i) => `<li role="option" id="ac${i}" data-i="${i}">${esc(title(x.attributes.ADDRESS))}${x.attributes.UNIT && x.attributes.UNIT.trim() ? ' #' + esc(x.attributes.UNIT) : ''}<span>${esc(x.attributes.CMNTY || '')} ${esc(x.attributes.ZIP || '')}</span></li>`).join('');
    showList();
  } catch (e) { if (my === seq) { list.innerHTML = '<li class="ac-empty">Bay County\'s map server didn\'t answer. Try again in a moment.</li>'; showList(); } }
}
function showList() { list.hidden = false; inp.setAttribute('aria-expanded', 'true'); }
function hideList() { list.hidden = true; inp.setAttribute('aria-expanded', 'false'); inp.removeAttribute('aria-activedescendant'); }
function mark() { list.querySelectorAll('li[role=option]').forEach((li, i) => li.setAttribute('aria-selected', i === active)); if (active >= 0) inp.setAttribute('aria-activedescendant', 'ac' + active); }
inp.addEventListener('keydown', e => {
  if (list.hidden || !items.length) { if (e.key === 'Enter') { e.preventDefault(); suggest(); } return; }
  if (e.key === 'ArrowDown') { e.preventDefault(); active = Math.min(items.length - 1, active + 1); mark(); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); active = Math.max(0, active - 1); mark(); }
  else if (e.key === 'Enter') { e.preventDefault(); pick(items[Math.max(0, active)]); }
  else if (e.key === 'Escape') hideList();
});
list.addEventListener('mousedown', e => { const li = e.target.closest('li[data-i]'); if (li) { e.preventDefault(); pick(items[+li.dataset.i]); } });
document.addEventListener('click', e => { if (!e.target.closest('.ac')) hideList(); });

function pick(f) {
  hideList();
  const a = f.attributes;
  inp.value = title(a.ADDRESS) + (a.UNIT ? ' #' + a.UNIT : '');
  const u = new URL(location.href); u.searchParams.set('a', a.ADDRESS); if (a.UNIT) u.searchParams.set('u', a.UNIT); else u.searchParams.delete('u'); u.searchParams.set('z', a.ZIP || '');
  history.replaceState(null, '', u);
  load(f);
}

/* ---------- lookup ---------- */
async function load(f) {
  const a = f.attributes, pt = f.geometry;
  $('err').hidden = true; $('out').hidden = false;
  $('aTitle').textContent = title(a.ADDRESS) + (a.UNIT ? ' #' + a.UNIT : '');
  $('aSub').textContent = `${a.CMNTY || ''}, FL ${a.ZIP || ''} · Loading…`;
  document.querySelectorAll('.addr-grid .card > :not(h3)').forEach(el => { if (el.id !== 'map') el.innerHTML = '<p class="muted small">Loading…</p>'; });
  const parcelP = a.RENUM ? q('Admin_A12/MapServer/6', {where: `A1RENUM='${String(a.RENUM).replace(/'/g, '')}'`}).then(x => x[0]?.attributes || null).catch(() => null)
                          : atPoint('Admin_A12/MapServer/6', pt).then(x => x?.[0] || null);
  const near = (layer) => q(`Admin_A12/MapServer/${layer}`, {geometry: JSON.stringify({x: pt.x, y: pt.y, spatialReference: {wkid: 4326}}), geometryType: 'esriGeometryPoint', inSR: 4326, distance: 10, units: 'esriSRUnit_StatuteMile', returnGeometry: 'true', outSR: 4326})
    .then(fs => fs.map(x => ({...x.attributes, d: miles(pt, x.geometry)})).sort((p, r) => p.d - r.d)[0] || null).catch(() => null);
  const [parcel, city, cra, comm, local, mosq, flood, evac, tdc, sb, house, senate, ush, es, ms, hs, fire, lib, park] = await Promise.all([
    parcelP, atPoint('Admin_A12/MapServer/26', pt), atPoint('Admin_A12/MapServer/27', pt), atPoint('Admin_A12/MapServer/28', pt), atPoint('Admin_A12/MapServer/30', pt),
    atPoint('Admin_A12/MapServer/34', pt), floodAt(pt), atPoint('Admin_A12/MapServer/80', pt), atPoint('Admin_A12/MapServer/84', pt),
    atPoint('ElectionAdministration/MapServer/2', pt), atPoint('ElectionAdministration/MapServer/3', pt), atPoint('ElectionAdministration/MapServer/4', pt), atPoint('ElectionAdministration/MapServer/5', pt),
    atPoint('SchoolAttendanceZones/MapServer/0', pt), atPoint('SchoolAttendanceZones/MapServer/1', pt), atPoint('SchoolAttendanceZones/MapServer/2', pt),
    near(42), near(39), near(41)]);
  const cityName = (city || []).map(c => c.NAME).find(n => n && !/unincorp/i.test(n)) || null;
  $('aSub').dataset.city = cityName || '';
  $('aSub').textContent = `${cityName ? 'City of ' + cityName : 'Unincorporated Bay County'} · ZIP ${a.ZIP || '—'}${parcel ? ' · Parcel ' + parcel.A1RENUM : ''}`;
  const pa = $('paLink');
  if (parcel?.PLINK) { pa.href = parcel.PLINK; pa.hidden = false; } else pa.hidden = true;
  if (parcel) parcel._ex = await loadEx(parcel.A1RENUM);
  const govKey = cityKey(cityName);
  renderTax(parcel, cityName);
  renderProp(parcel);
  renderReps(comm, local, sb, house, senate, ush, cityName);
  renderSchools(es, ms, hs);
  renderCra(cra);
  renderSafe(flood, evac, mosq, tdc, fire, lib, park);
  renderGovLinks(govKey);
  loadDev(pt, cityName);
  loadNear(pt, govKey);
  drawMap(pt, cityName, cra?.[0]?.CRA);
}
/* The government that runs this address: its city, or the County Commission outside city limits. Keys match govs.py. */
const cityKey = cityName => (cityName && Object.keys(D.govs).find(k => D.govs[k].s === cityName)) || 'county';

/* GIS representative name -> the name used in recorded votes (same government only; one clear match or none).
   Matches last names and first names where one starts the other (Doug/Douglas), ignoring initials and Jr./Sr. */
function normName(s) { return String(s || '').toLowerCase().replace(/[.,]/g, ' ').split(/\s+/).filter(w => w.length > 1 && !/^(jr|sr|ii|iii|iv)$/.test(w)); }
function matchMember(rep, gov) {
  const a = normName(rep); if (a.length < 2) return null;
  const hits = (D.members[gov] || []).filter(([n]) => { const b = normName(n); return b.length > 1 && b[b.length - 1] === a[a.length - 1] && (b[0].startsWith(a[0]) || a[0].startsWith(b[0])); });
  return hits.length === 1 ? hits[0] : null;
}

/* Links to this government's records, filtered with the params each page already reads (see gov_pages.py). */
function govRecordLinks(k) {
  const g = D.govs[k]; if (!g) return '';
  const L = [[`/governments/${g.slug}`, X.l_page], g.c ? [`/public-money/contracts?gov=${encodeURIComponent(g.c)}#all`, X.l_contracts] : null, [`/meetings?gov=${k}`, X.l_meetings],
    g.b ? [`/public-money/budget-explorer?gov=${k}`, X.l_budget] : null, [`/alerts?gov=${k}`, X.l_alerts], [`/records-request?gov=${k}`, X.l_records],
    g.f ? [`/public-money/hurricane-michael?q=${encodeURIComponent(g.f)}`, X.l_michael] : null].filter(Boolean);
  return `<dt>${esc(g.s)}</dt><dd>${L.map(([h, t]) => `<a href="${esc(h)}">${esc(t)}</a>`).join(' · ')}</dd>`;
}
function renderGovLinks(k) {
  const keys = [...new Set([k, 'county', 'schools'])];
  $('govBody').innerHTML = `<dl class="kv">${keys.map(govRecordLinks).join('')}</dl><p class="muted small">${esc(X.govNote)}</p>`;
}

/* Public money near the address: CRA ledger rows within half a mile and sales tax projects within a mile.
   Fetched only after an address is chosen. */
let NEAR = null;
async function loadNear(pt, govKey) {
  const el = $('nearBody'); if (!el) return;
  el.innerHTML = '<p class="muted small">Loading…</p>';
  try {
    NEAR = NEAR || await Promise.all(['/data/cra-pay-1.json', '/data/cra-pay-2.json', '/data/surtax-projects.json'].map(u => fetch(u).then(r => { if (!r.ok) throw new Error(u); return r.json(); })))
      .then(([a, b, s]) => ({cra: a.concat(b), st: s}));
  } catch (e) { NEAR = null; el.innerHTML = `<p class="muted">${esc(X.fail)}</p>`; return; }
  el.innerHTML = nearHtml(pt, NEAR, govKey);
}
function nearCra(pt, pays) {
  // only rows counted in CRA totals and placed at a site (not just somewhere in a district)
  return pays.filter(p => p.count && p.placed === 'site' && p.lat != null && p.lng != null)
    .map(p => ({...p, mi: miles(pt, {x: p.lng, y: p.lat})})).filter(p => p.mi <= 0.5).sort((a, b) => a.mi - b.mi);
}
function nearSurtax(pt, projs) {
  return projs.filter(p => p.x != null && p.yy != null).map(p => ({...p, mi: miles(pt, {x: p.x, y: p.yy})})).filter(p => p.mi <= 1).sort((a, b) => a.mi - b.mi);
}
function nearHtml(pt, N, govKey) {
  const cr = nearCra(pt, N.cra), st = nearSurtax(pt, N.st), MAX = 5;
  const craAmt = cr.filter(p => p.status === 'Spent' || p.status === 'Committed').reduce((a, p) => a + (p.amount || 0), 0);
  const more = n => n > MAX ? `<li class="muted small">${esc(fmt(X.more, {n: n - MAX}))}</li>` : '';
  const craIds = [...new Set(cr.map(p => p.cra))], craName = id => (Object.entries(D.craId).find(([, v]) => v === id) || [id])[0];
  const stGov = st[0]?.g;
  return `<h4 class="dev-h">${esc(X.nearCraH)}${cr.length ? ` <span class="muted small">${esc(fmt(X.craTotal, {n: cr.length, amt: big(craAmt)}))}</span>` : ''}</h4>
    ${cr.length ? `<ul class="dev-list">${cr.slice(0, MAX).map(p => `<li><b>${p.amount ? usd(p.amount) : '—'}</b> · ${esc(p.purpose || p.payee || '')}<br><span class="muted small">${[X['cs_' + p.status] || p.status, p.when, p.mi.toFixed(1) + ' mi'].filter(Boolean).map(esc).join(' · ')}${p.url ? ` · <a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(X.source)}</a>` : ''}</span></li>`).join('')}${more(cr.length)}</ul>
      <p class="small">${craIds.map(id => `<a href="/public-money/cra-spending?cra=${esc(id)}">${esc(craIds.length > 1 ? craName(id) + ': ' : '')}${esc(X.seeCra)}</a>`).join(' · ')}</p>` : `<p class="small muted">${esc(X.nearNone)}</p>`}
    <h4 class="dev-h">${esc(X.nearStH)}${st.length ? ` <span class="muted small">${esc(fmt(X.stTotal, {n: st.length}))}</span>` : ''}</h4>
    ${st.length ? `<ul class="dev-list">${st.slice(0, MAX).map(p => `<li><b>${esc(p.n)}</b>${p.k ? ` · ${big(p.k)}` : ''}<br><span class="muted small">${[X['st_' + p.s] || X.st_unknown, p.p != null && p.s === 'in_progress' ? p.p + '%' : '', p.g, p.mi.toFixed(1) + ' mi'].filter(Boolean).map(esc).join(' · ')}</span></li>`).join('')}${more(st.length)}</ul>
      <p class="small"><a href="/public-money/sales-tax-projects?gov=${encodeURIComponent(stGov)}">${esc(X.seeSt)}</a></p>` : `<p class="small muted">${esc(X.nearNone)}</p>`}
    <p class="muted small">${esc(X.nearNote)}</p>`;
}

function miles(a, b) { if (!b) return 1e9; const R = 3958.8, t = Math.PI / 180, dLat = (b.y - a.y) * t, dLon = (b.x - a.x) * t; const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.y * t) * Math.cos(b.y * t) * Math.sin(dLon / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); }
const kv = rows => rows.filter(Boolean).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('');

function distFor(parcel, cityName) {
  const code = String(parcel?.DTAXDIST || '').trim();
  let id = D.taxdist[code];
  if (!id) id = cityName && D.districts[cityName] ? cityName : 'unincorporated';
  return {id, d: D.districts[id], exact: !!D.taxdist[code]};
}
/* Parcel lookups are split into small files by a hash of the parcel id (same FNV-1a as addr_page.shard_key). */
function shardOf(pid, n) {
  let h = 0x811c9dc5;
  for (const c of new TextEncoder().encode(pid)) h = Math.imul(h ^ c, 0x01000193) >>> 0;
  return 'h' + (h % n);
}
const shardCache = {};
async function shardGet(kind, pid) {
  if (!pid) return null;
  const url = `/data/${kind}/${shardOf(pid, D.shards[kind])}.json`;
  try {
    shardCache[url] = shardCache[url] || fetch(url).then(r => r.ok ? r.json() : {}).catch(() => { delete shardCache[url]; return null; });
    const s = await shardCache[url];
    return s ? s[pid] || null : undefined; // undefined = couldn't load
  } catch (e) { return undefined; }
}
const loadEx = pid => shardGet('ex', pid);
function taxParts(p) {
  if (p._ex) {
    // 2026 final tax roll: school and non-school taxable value as certified. Homestead amounts are shown by name;
    // every other exemption is one lumped amount, so no one's personal circumstances show up here.
    const [tsd, tnsd, h1, h2, oth] = p._ex, assessed = +p.VASTOTAL || 0, just = +p.VASJUST || 0, exempt = h1 + h2 + oth;
    return {hx: h1 > 0, assessed, just, exempt, taxable: tnsd, second: h2, other: oth, h1,
      school: tsd, non: tnsd, nonOther: null, roll: true, full: tsd === 0 && tnsd === 0 && exempt > 0};
  }
  const hx = /\bHX\b/.test(p.DEXEMPTS || ''), assessed = +p.VASTOTAL || 0, just = +p.VASJUST || 0, exempt = +p.VASEXEMPT || 0, taxable = +p.VASTAXABLE || 0;
  const second = hx ? Math.min(Math.max(assessed - 50000, 0), D.second2026) : 0;
  const other = hx ? Math.max(0, exempt - Math.min(assessed, 25000) - second) : exempt;
  // county codes for full exemptions (disabled veteran, totally disabled person, etc.): no school tax either
  const fullEx = taxable === 0 && /\b(13|14|VT|96)\b/.test(p.DEXEMPTS || '');
  return {hx, assessed, just, exempt, taxable, second, other, school: fullEx ? 0 : hx ? Math.max(0, taxable + second) : Math.max(0, just - exempt), non: taxable};
}
/* Link to a calculator with this parcel's numbers. Both calculators take the value before exemptions
   (assessed value) and apply the homestead themselves: v = assessed value, d = district id, h = 1/0 homestead. */
function whatIf(path, p, distId, t) {
  const u = new URLSearchParams({v: Math.round(t.assessed || 0), d: distId, h: t.hx ? '1' : '0'});
  if (path.endsWith('amendment-3')) { u.delete('h'); u.set('k', t.hx ? 'home' : 'non'); }
  return `${path}?${u}#calc`;
}
/* Florida DOR land-use codes where someone could live and claim a homestead: 01 single family, 02 mobile home,
   04 condominium, 05 co-op, 08 multi-family under 10 units. */
const isResidential = p => /^0[12458]/.test(String(p?.DORAPPCODE || '').trim());
function renderTax(p, cityName) {
  const el = $('taxBody');
  if (!p) { el.innerHTML = `<p class="muted">No parcel record came back for this address, so there's no value to estimate from. <a href="/public-money/tax-dollars">Use the calculator →</a></p>`; return; }
  const {id, d, exact} = distFor(p, cityName), t = taxParts(p);
  const rows = d.stack.map(aid => { const a = D.auth[aid]; return {n: a.n, g: a.g, m: a.m, amt: (a.school ? t.school : (a.g === 'county' || a.g === 'countysvc' || t.nonOther == null) ? t.non : t.nonOther) / 1000 * a.m}; }).filter(r => r.m > 0);
  const tot = rows.reduce((s, r) => s + r.amt, 0);
  const byG = D.groups.map(([g]) => [g, rows.filter(r => r.g === g).reduce((s, r) => s + r.amt, 0)]).filter(x => x[1] > 0.5);
  const gname = g => g === 'city' ? (rows.find(r => r.g === 'city')?.n || 'City') : GN[g];
  const barLabel = fmt(X.barLabel, {parts: byG.map(([g, v]) => `${gname(g)} ${usd(v)} (${tot ? Math.round(v / tot * 100) : 0}%)`).join(', ')});
  el.innerHTML = `<div class="bill-hd"><span class="bill-v sm">${usd(tot)}<small> / year</small></span><span class="muted small">${esc(d.label)} · ${String(+d.total.toFixed(4))} mills${exact ? '' : ' (area inferred from the map)'}</span></div>
    <div class="stackbar" role="img" aria-label="${esc(barLabel)}">${byG.map(([g, v]) => `<span class="seg" style="flex:${v} 1 0;background:var(--s${GI[g]})" title="${esc(GN[g])}: ${usd(v)}"></span>`).join('')}</div>
    <ul class="leg mini2">${byG.map(([g, v]) => `<li><i style="background:var(--s${GI[g]})"></i><span>${esc(gname(g))}</span><b>${usd(v)}</b></li>`).join('')}</ul>
    <div id="feeBody"><p class="muted small">Checking fees on the tax bill…</p></div>
    <p class="muted small">Property tax: 2026 values × ${D.fy} rates. Fees: the FY2026 tax roll. <a href="/public-money/tax-dollars">Where it goes →</a></p>
    <p class="small"><a href="${esc(whatIf('/public-money/tax-dollars', p, id, t))}">${esc(X.whatif)}</a></p>`;
  loadFees(p.A1RENUM, tot);
}
async function loadFees(pid, taxTot) {
  const el = $('feeBody'); if (!el || !pid) return;
  const got = await shardGet('nav', pid);
  if (got === undefined) { el.innerHTML = ''; return; }
  const items = got || [];
  const fees = items.reduce((a, x) => a + x[1], 0);
  el.innerHTML = items.length
    ? `<dl class="kv fees"><dt class="span">Flat fees on the tax bill</dt>${items.map(([c, a]) => `<dt>${esc(D.navLabel[c] || 'Other charge (' + c + ')')}</dt><dd>${usd(a)}</dd>`).join('')}<dt><b>Estimated total bill</b></dt><dd><b>${usd(taxTot + fees)}</b> <span class="muted small">tax + fees</span></dd></dl>`
    : '<p class="muted small">No flat fees (non-ad valorem assessments) were on this parcel\'s FY2026 tax bill.</p>';
}
const PA_URL = 'https://www.baypa.net/';
function exList(t) {
  const items = [t.h1 ? ['Homestead', t.h1] : null, t.second ? ['Additional homestead', t.second] : null, t.other ? ['Other exemptions', t.other] : null].filter(Boolean)
    .map(([n, v]) => `<li>${n} <span class="muted">${usd(v)}</span></li>`);
  return `${usd(t.exempt)}<ul class="plain small ex-list">${items.join('')}</ul>${t.other ? `<span class="muted small">The kinds of other exemptions aren't shown, to protect owners' privacy. Owners can see theirs on the <a href="${PA_URL}" target="_blank" rel="noopener">Property Appraiser's site</a>.</span> ` : ''}${t.full ? '<span class="small"><b>No property tax is owed on this home.</b></span> ' : ''}<a class="small" href="/public-money/exemptions">About exemptions →</a>`;
}
function renderProp(p) {
  const el = $('propBody');
  if (!p) { el.innerHTML = '<dd class="muted">No parcel record found for this address.</dd>'; return; }
  const t = taxParts(p);
  el.innerHTML = kv([
    ['Use', esc(title(p.DORAPPDESC))],
    p.S1YRBLTACT ? ['Built', esc(p.S1YRBLTACT) + (p.S1AREAHEAT ? ` · ${Math.round(p.S1AREAHEAT).toLocaleString()} heated sq ft` : '')] : null,
    ['Market (just) value', usd(t.just)],
    ['<span class="term" data-term="assessed-value">Assessed value</span>', usd(t.assessed) + (t.assessed < t.just ? ` <span class="muted small">(capped ${usd(t.just - t.assessed)} below market)</span>` : '')],
    ['Exemptions', t.roll ? exList(t) : t.exempt ? usd(t.exempt) + (t.hx ? ' <span class="muted small">(includes homestead)</span>' : '') : 'No exemptions'],
    ['<span class="term" data-term="taxable-value">Taxable value</span>', usd(t.non) + (t.school !== t.non ? ` <span class="muted small">(${usd(t.school)} for school taxes${t.nonOther != null && t.nonOther !== t.non ? `, ${usd(t.nonOther)} for city and district taxes` : ''})</span>` : '')],
  ]) + (!t.hx && isResidential(p) ? `<dt class="span">${esc(X.hsH)}</dt><dd class="span small">${fmt(esc(X.hs), {pa: `<a href="${PA_URL}" target="_blank" rel="noopener">${esc(X.pa)}</a>`})} <a href="/public-money/exemptions#apply">${esc(X.exLink)}</a></dd>` : '');
}
/* A local representative: name links to their recorded votes when they're in the votes data, with a yes/no tally,
   plus a link to campaign money for that government. State and federal seats link to their district site. */
function repLine(x, gov) {
  const a = x?.[0]; if (!a) return '<span class="muted">—</span>';
  const m = gov ? matchMember(a.REPNAME, gov) : null;
  const name = m ? `<a href="/public-money/votes?m=${encodeURIComponent(m[0])}#all">${esc(a.REPNAME)}</a>` : a.DISTRICTURL ? `<a href="${esc(a.DISTRICTURL)}" target="_blank" rel="noopener">${esc(a.REPNAME || '—')}</a>` : esc(a.REPNAME || '—');
  const site = m && a.DISTRICTURL ? ` <a class="small" href="${esc(a.DISTRICTURL)}" target="_blank" rel="noopener">${esc(X.website)}</a>` : '';
  const tal = m ? `<br><span class="muted small">${esc(fmt(X.tally, {y: m[1], n: m[2]}))}</span>` : '';
  const cm = gov ? ` <a class="small" href="/public-money/campaign-money?gov=${gov}">${esc(X.campaign)}</a>` : '';
  return `${name} <span class="muted small">${esc(a.NAME || '')}</span>${site}${tal}${gov ? (tal ? ' ·' : '<br>') + cm : ''}`;
}
function renderReps(comm, local, sb, house, senate, ush, cityName) {
  const ck = cityName ? cityKey(cityName) : null;
  const ballot = D.elections ? [...new Set([ck || 'county', 'county', 'schools'])].map(k => `<a href="/elections?gov=${k}">${esc(D.govs[k]?.s || k)}</a>`).join(' · ') : '';
  $('repBody').innerHTML = kv([
    ['County Commission', repLine(comm, 'county')],
    cityName ? ['City', `City of ${esc(cityName)}${local?.[0] ? ' · ' + repLine(local, ck !== 'county' ? ck : null) : ck !== 'county' ? ` <a class="small" href="/public-money/campaign-money?gov=${ck}">${esc(X.campaign)}</a>` : ''}`] : ['City', '<span class="muted">None (unincorporated). The County Commission is your local government.</span>'],
    ['School Board', repLine(sb, 'schools')],
    ['Florida House', repLine(house)],
    ['Florida Senate', repLine(senate)],
    ['U.S. House', repLine(ush)],
    ballot ? [esc(X.ballotH), `<span class="small">${esc(X.ballot)} ${ballot}</span>`] : null,
  ]) + '<dt class="span">Money decisions</dt><dd class="span"><a href="/public-money/tax-dollars#govs">See each government\'s budget →</a></dd>';
}
function renderSchools(es, ms, hs) {
  const n = x => x?.[0] ? esc(x[0].NAME) : '<span class="muted">—</span>';
  $('schBody').innerHTML = kv([['Elementary', n(es)], ['Middle', n(ms)], ['High', n(hs)]]) + '<dd class="span muted small">Attendance zones from Bay District Schools via county GIS. Choice and magnet options differ.</dd>';
}
function renderCra(cra) {
  const el = $('craBody'), c = cra?.[0];
  if (cra === null) { el.innerHTML = '<p class="muted">Couldn\'t check right now.</p>'; return; }
  if (!c) { el.innerHTML = '<p>This address is <b>not inside a CRA district</b>, so all of its city and county property tax goes to those governments\' regular budgets.</p><p class="small"><a href="/public-money/cra-spending">See Bay County\'s CRAs →</a></p>'; return; }
  const ag = D.craAgency[c.CRA], s = ag && D.cra[ag], cid = ag && D.craId[ag];
  el.innerHTML = `<p>This address is inside the <b>${esc(c.CRA)}</b> district${c.EST_YEAR ? ` (created ${esc(c.EST_YEAR)})` : ''}. The city and county taxes on growth in this area since then go to the ${esc(ag || 'CRA')}'s fund and must be spent inside its districts.</p>
    ${s ? `<p class="small">${esc(ag)}: <b>${big(s.spent)}</b> in documented spending and awards across ${s.n} records on this site.</p>` : ''}
    <p class="small"><a href="/public-money/cra-spending${cid ? '?cra=' + cid : ''}">See what it pays for →</a></p>`;
}
function renderSafe(flood, evac, mosq, tdc, fire, lib, park) {
  const f = flood?.zone, fdate = ms => ms ? new Date(ms).toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC'}) : '';
  const bfe = f && f.STATIC_BFE > 0 ? ` · base flood elevation <b>${esc(f.STATIC_BFE)} ft</b>${f.V_DATUM ? ' <span class="muted small">(' + esc(f.V_DATUM) + ')</span>' : ''}` : '';
  let floodTxt;
  if (flood === null) floodTxt = '<span class="muted">Couldn\'t check right now</span>';
  else if (!f) floodTxt = flood.src === 'county' ? 'Outside the high-risk areas on Bay County\'s copy of the flood map' : '<span class="muted">Not on FEMA\'s flood map here</span>';
  else if (f.SFHA_TF === 'T' || /^(A|V)/.test(f.FLD_ZONE)) floodTxt = `<b>Zone ${esc(f.FLD_ZONE)}</b> · FEMA high-risk area${/^V/.test(f.FLD_ZONE) ? ', coastal waves' : ''}${bfe}${f.DEPTH > 0 ? ` · flood depth ${esc(f.DEPTH)} ft` : ''}`;
  else if (f.FLD_ZONE === 'X' && /0\.2/.test(f.ZONE_SUBTY || '')) floodTxt = '<b>Zone X (shaded)</b> · moderate risk, outside the high-risk area (0.2% annual chance flood)';
  else if (f.FLD_ZONE === 'X') floodTxt = '<b>Zone X</b> · minimal flood hazard on FEMA\'s map';
  else if (f.FLD_ZONE === 'D') floodTxt = '<b>Zone D</b> · flood risk not determined';
  else floodTxt = `<b>Zone ${esc(f.FLD_ZONE)}</b>${bfe}`;
  if (flood?.panel?.FIRM_PAN) floodTxt += `<br><span class="muted small">FIRM panel ${esc(flood.panel.FIRM_PAN)}${flood.panel.EFF_DATE ? ', effective ' + fdate(flood.panel.EFF_DATE) : ''}${flood.lomr?.CASE_NO ? ` · map revision (LOMR) ${esc(flood.lomr.CASE_NO)}${flood.lomr.EFF_DATE ? ', ' + fdate(flood.lomr.EFF_DATE) : ''}` : ''}</span>`;
  if (flood?.src === 'county') floodTxt += '<br><span class="muted small">FEMA\'s live map didn\'t respond, so this is Bay County\'s older copy, which predates the October 2024 maps. Use the FEMA link below to confirm.</span>';
  const nearTxt = (x, nm) => x ? `${esc(x.NAME || nm)} <span class="muted small">${x.d.toFixed(1)} mi${x.FULLADDR || x.ADDRESS ? ' · ' + esc(x.FULLADDR || x.ADDRESS) : ''}</span>` : '<span class="muted">None within 10 miles</span>';
  $('safeBody').innerHTML = kv([
    ['Flood zone', floodTxt],
    ['Evacuation zone', evac?.[0]?.EZONE ? `<b>Zone ${esc(evac[0].EZONE)}</b> <span class="muted small">Know your zone before a storm</span>` : '<span class="muted">Not in a mapped zone</span>'],
    ['Nearest fire station', nearTxt(fire, 'Fire station')],
    ['Nearest library', nearTxt(lib, 'Library')],
    ['Nearest park', nearTxt(park, 'Park')],
    mosq?.[0] ? ['Mosquito control', esc(mosq[0].DISTRICT) + (mosq[0].ADMINISTRATION === 'BC' ? ' <span class="muted small">(Bay County)</span>' : '')] : null,
    tdc?.[0] ? ['Tourist tax area', esc(tdc[0].ID)] : null,
  ]) + `<dd class="span muted small">Flood zone is checked live against FEMA's National Flood Hazard Layer at the address point. A building's official zone comes from the flood map, your lender's flood determination or an elevation certificate. <a href="https://msc.fema.gov/portal/search?AddressQuery=${encodeURIComponent($('aTitle').textContent + ', ' + ($('aSub').dataset.city ? $('aSub').dataset.city + ', FL' : 'Bay County, FL'))}" target="_blank" rel="noopener">Check this address on FEMA's map</a>.</dd>`;
}

/* Amendment 3 card, filled from the same parcel */
const _renderTax = renderTax;
renderTax = function (p, cityName) { // eslint-disable-line no-func-assign
  _renderTax(p, cityName);
  const el = $('a3Body');
  if (!p) { el.innerHTML = '<p class="muted">No parcel record to estimate from. <a href="/public-money/amendment-3">Try the calculator →</a></p>'; return; }
  const {id, d} = distFor(p, cityName), t = taxParts(p);
  const nonM = d.stack.filter(a => !D.auth[a].school).reduce((s, a) => s + D.auth[a].m, 0);
  const try3 = `<p class="small"><a href="${esc(whatIf('/public-money/amendment-3', p, id, t))}">${esc(X.whatifA3)}</a></p>`;
  if (!t.hx) {
    el.innerHTML = `<p>This property has no homestead exemption, so Amendment 3 wouldn't lower its tax bill directly. It would limit how fast its taxed value can rise to <b>5% a year instead of 10%</b> for non-school taxes.${t.assessed < t.just ? ` Its value is already capped ${usd(t.just - t.assessed)} below market.` : ''}</p><p class="small"><a href="/public-money/amendment-3">What Amendment 3 does →</a></p>` + try3;
    return;
  }
  const after = Math.max(0, t.assessed - 250000 - t.other), save = (t.non - after) / 1000 * nonM;
  el.innerHTML = `<p>With the full $250,000 homestead exemption on today's value and rates, this home's county, city and district taxes would drop by about <b>${usd(save)} a year</b>${after === 0 ? ', to zero; it would still pay school tax' : ''}.</p>
    <p class="muted small">Assumes rates stay the same and the owner was a Florida resident before 2027. Local governments here would collect less; see the state's estimates. <a href="/public-money/amendment-3">Amendment 3 →</a></p>` + try3;
};

/* ---------- map ---------- */
let GEO = null;
async function drawMap(pt, cityName, craName) {
  const svg = $('map');
  try { GEO = GEO || await (await fetch('/data/cra-geo.json')).json(); } catch (e) { svg.innerHTML = ''; return; }
  const local = !!(cityName || craName), W = 400, H = 260, k = Math.cos(30.2 * Math.PI / 180);
  const c = local ? pt : {x: -85.69, y: 30.235}, spanY = local ? 0.045 : 0.72, spanX = spanY * W / H / k;
  const x0 = c.x - spanX / 2, y0 = c.y + spanY / 2;
  const P = ([lng, lat]) => `${((lng - x0) / spanX * W).toFixed(1)},${((y0 - lat) / spanY * H).toFixed(1)}`;
  const path = mp => mp.map(poly => poly.map(ring => 'M' + ring.map(P).join('L') + 'Z').join('')).join('');
  let s = `<rect width="${W}" height="${H}" fill="var(--water)"/>`;
  s += `<path d="${path(GEO.land)}" fill="var(--land)" stroke="var(--landline)" stroke-width=".8"/>`;
  Object.entries(GEO.cities).forEach(([n, g]) => { s += `<path d="${path(g)}" fill="${n === cityName ? 'color-mix(in srgb,var(--blue) 12%,var(--land))' : 'var(--city)'}" stroke="var(--cityline)" stroke-width="${n === cityName ? 1.4 : .8}"/>`; });
  GEO.districts.forEach(dd => { s += `<path d="${path(dd.geom)}" fill="color-mix(in srgb,var(--amber) ${dd.name === craName ? 35 : 15}%,transparent)" stroke="var(--amber)" stroke-width="${dd.name === craName ? 1.6 : .8}" stroke-dasharray="${dd.name === craName ? '' : '3 2'}"/>`; });
  const [mx0, my0] = P([pt.x, pt.y]).split(',').map(Number), placed = [];
  Object.entries(GEO.cities).forEach(([n, g]) => {
    let best = null, ba = 0; g.forEach(poly => { const r = poly[0]; let a = 0, cx = 0, cy = 0; r.forEach(([x, y], i) => { const [x2, y2] = r[(i + 1) % r.length]; const c = x * y2 - x2 * y; a += c; cx += (x + x2) * c; cy += (y + y2) * c; }); if (Math.abs(a) > ba) { ba = Math.abs(a); best = [cx / (3 * a), cy / (3 * a)]; } });
    if (!best) return; const [lx, ly] = P(best).split(',').map(Number);
    const wd = n.length * 6.2;
    if (placed.some(([px, py, pw]) => Math.abs(px - lx) < (pw + wd) / 2 + 4 && Math.abs(py - ly) < 13)) return;
    if (lx > 20 && lx < W - 20 && ly > 12 && ly < H - 12 && Math.hypot(lx - mx0, ly - my0) > 24) placed.push([lx, ly, wd]), s += `<text x="${lx}" y="${ly}" text-anchor="middle" font-size="11" font-weight="500" fill="var(--muted)" style="paint-order:stroke;stroke:var(--land);stroke-width:3px">${n}</text>`;
  });
  if (!local) s += `<path d="${path(GEO.county)}" fill="none" stroke="var(--muted)" stroke-width="1" stroke-dasharray="4 3"/>`;
  const [mx, my] = P([pt.x, pt.y]).split(',').map(Number);
  s += `<circle cx="${mx}" cy="${my}" r="12" fill="var(--salmon)" opacity=".18"/><circle cx="${mx}" cy="${my}" r="6" fill="var(--salmon)" stroke="var(--surface)" stroke-width="2"/>`;
  svg.innerHTML = s;
  $('mapCap').innerHTML = `<i class="sw city"></i> city limits <i class="sw cra"></i> CRA districts · ${local ? 'about 3 miles across' : 'all of Bay County <span class="sw cty"></span> county line'}`;
}

/* PDF report subtitle */
window.BCReportTitle = () => 'Address report: ' + $('aTitle').textContent;
window.BCReportMeta = () => `Address report: ${$('aTitle').textContent} · ${$('aSub').textContent}`;

/* restore from URL */
(async () => {
  const u = new URL(location.href), a = u.searchParams.get('a'), qq = u.searchParams.get('q');
  if (!a && qq) { inp.value = qq; inp.focus({preventScroll: true}); suggest(); return; }
  if (!a) { inp.focus({preventScroll: true}); return; }
  inp.value = title(a);
  try {
    const unit = u.searchParams.get('u'), z = u.searchParams.get('z');
    let where = `ADDRESS = '${clean(a)}'` + (z ? ` AND ZIP = ${parseInt(z, 10) || 0}` : '') + (unit ? ` AND UNIT = '${clean(unit)}'` : '');
    const f = await q('Admin_A12/MapServer/3', {where, outFields: 'ADDRESS,UNIT,CMNTY,ZIP,RENUM', returnGeometry: 'true', outSR: 4326, resultRecordCount: 1});
    if (f[0]) load(f[0]); else { $('err').textContent = 'That address wasn\'t found. Try searching again.'; $('err').hidden = false; }
  } catch (e) { $('err').textContent = 'Bay County\'s map server didn\'t answer. Try again in a moment.'; $('err').hidden = false; }
})();
})();
