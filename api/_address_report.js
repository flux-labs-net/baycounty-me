// Address report: everything BayCounty.me has for one address, in one answer (GET /api/v1/address-report, the MCP tool
// address_report, and the realtor console at /realtor, which prints it as a branded PDF).
//
// The report is a list of sections. Each section is a small plug-in: it says which datasets (and, optionally, which
// api/_*.js module) it needs, and a run(ctx) that returns its data. A section whose data isn't published yet comes back
// with status "pending" instead of failing, so a new section (or a dataset that lands later, like utilities or parks)
// switches on without touching the console or the PDF. Live lookups go to Bay County's public GIS server and FEMA's flood
// map at the address point. Explicit field lists only: the parcel layer also carries owner names, mailing addresses and
// sale grantor/grantee names, which are never requested.
const PLACES = {
  'fl-bay': {
    name: 'Bay County', state: 'FL',
    gis: 'https://gis.baycountyfl.gov/arcgis/rest/services',
    bbox: [-86.0, 29.9, -85.3, 30.6],
  },
};
const NFHL = 'https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer';
const FIRST_YEAR = 2016; // site-wide cutoff: nothing dated before 2016
const bad = (msg, status = 400) => Object.assign(new Error(msg), {status, expose: true});

// Parcel fields we read. Never A2OWNAME, A3..A9 (mailing), SALEnGRNTR / SALEnGRTEE (names) or LEGALINEn.
const PARCEL_FIELDS = ['A1RENUM', 'PLINK', 'DTAXDIST', 'DORAPPCODE', 'DORAPPDESC', 'DTAXACRES', 'S1AREAHEAT', 'S1AREATTL', 'S1BATHRMS', 'S1BEDRMS',
  'S1STORIES', 'S1UNITS', 'S1YRBLTACT', 'S1YRBLTEFF', 'VASJUST', 'VASTOTAL', 'VASEXEMPT', 'VASTAXABLE', 'VAPBLDG', 'VAPLNDMRK', 'DEXEMPTS',
  'SubdivName', 'SubdivBlk', 'SubdivLot', 'Zoning', 'FLU', 'Surge', 'Evac',
  'SALE1DATE', 'SALE1PRADJ', 'SALE1QU_VI', 'SALE2DATE', 'SALE2PRADJ', 'SALE2QU_VI', 'SALE3DATE', 'SALE3PRADJ', 'SALE3QU_VI'];

/* ---------- small helpers ---------- */
const num = v => (v == null || v === '' || !Number.isFinite(Number(v)) ? null : Number(v));
const titleCase = s => String(s || '').toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase()).replace(/\b(Ne|Nw|Se|Sw|Us|Cr|Sr)\b/g, m => m.toUpperCase());
function miles(a, b) {
  if (!a || !b || b.lat == null || b.lon == null) return null;
  const R = 3958.8, t = Math.PI / 180, dLat = (b.lat - a.lat) * t, dLon = (b.lon - a.lon) * t;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * t) * Math.cos(b.lat * t) * Math.sin(dLon / 2) ** 2;
  return Math.round(2 * R * Math.asin(Math.sqrt(h)) * 100) / 100;
}
// Rows of any dataset that carries a point (lat/lng or latitude/longitude), nearest first, within a radius.
function nearRows(rows, pt, radius, limit = 5) {
  return (rows || []).map(r => {
    const lat = num(r.lat ?? r.latitude), lon = num(r.lng ?? r.lon ?? r.longitude);
    return lat == null || lon == null ? null : {r, mi: miles(pt, {lat, lon})};
  }).filter(x => x && x.mi <= radius).sort((a, b) => a.mi - b.mi).slice(0, limit);
}
// Same FNV-1a hash as site/addr_page.py shard_key and address.js shardOf, for the per-parcel files.
function shardOf(pid, n) {
  let h = 0x811c9dc5;
  for (const c of Buffer.from(String(pid))) h = Math.imul(h ^ c, 0x01000193) >>> 0;
  return 'h' + (h % n);
}
const isoDay = v => {
  if (v == null || v === '' || String(v).trim() === '') return null;
  const d = typeof v === 'number' ? new Date(v) : new Date(String(v).length === 10 ? v + 'T12:00:00Z' : v);
  return isNaN(d) ? null : d.toISOString().slice(0, 10);
};

/* ---------- GIS ---------- */
async function arc(url, params, fetchImpl = fetch, ms = 12000) {
  const u = `${url}/query?` + new URLSearchParams({f: 'json', returnGeometry: 'false', ...params});
  const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), ms);
  try {
    const r = await fetchImpl(u, {signal: ctl.signal});
    const j = await r.json();
    if (j.error) throw new Error(j.error.message || 'GIS error');
    return (j.features || []).map(f => ({...f.attributes, _g: f.geometry || null}));
  } finally { clearTimeout(t); }
}
const pointParams = pt => ({geometry: JSON.stringify({x: pt.lon, y: pt.lat, spatialReference: {wkid: 4326}}), geometryType: 'esriGeometryPoint', inSR: 4326, spatialRel: 'esriSpatialRelIntersects'});

// Address search in the county's address points: house number first, then the street words in any order.
const STREET_SKIP = new Set(['ST', 'STREET', 'AVE', 'AVENUE', 'RD', 'ROAD', 'DR', 'DRIVE', 'BLVD', 'LN', 'LANE', 'CT', 'CIR', 'PL', 'WAY', 'FL', 'FLORIDA',
  'PANAMA', 'CITY', 'BEACH', 'LYNN', 'HAVEN', 'CALLAWAY', 'SPRINGFIELD', 'PARKER', 'MEXICO', 'SOUTHPORT', 'YOUNGSTOWN', 'FOUNTAIN']);
function parseAddress(text) {
  let s = String(text || '').toUpperCase().replace(/[^A-Z0-9# ]/g, ' ').replace(/\b\d{5}(\s+\d{4})?\s*$/, ' ').replace(/\s+/g, ' ').trim();
  let unit = '';
  const um = /\s(?:#\s*|(?:APT|UNIT|STE|SUITE|LOT|BLDG)\s+#?\s*)([A-Z0-9-]+)$/.exec(s);
  if (um) { unit = um[1]; s = s.slice(0, um.index).trim(); }
  const m = /^(\d+)\s+(.+)$/.exec(s);
  if (!m) throw bad('Give a street address with a house number, e.g. 825 Ohio Ave.');
  const words = m[2].replace(/\bHWY\b/g, 'HIGHWAY').split(' ').filter(w => w.length > 1 && !STREET_SKIP.has(w)).slice(0, 3);
  if (!words.length) throw bad('Add the street name.');
  return {house: m[1], words, unit};
}
async function geocode(text, {place = 'fl-bay', zip = null, fetchImpl = fetch} = {}) {
  const P = PLACES[place]; if (!P) throw bad(`Unknown place "${place}".`);
  const a = parseAddress(text), sq = s => s.replace(/'/g, "''");
  const where = [`ADDRESS LIKE '${a.house} %'`, ...a.words.map(w => `ADDRESS LIKE '% ${sq(w)}%'`),
    ...(a.unit ? [`UNIT = '${sq(a.unit)}'`] : []), ...(zip && /^\d{5}$/.test(String(zip)) ? [`ZIP = ${Number(zip)}`] : [])].join(' AND ');
  let feats;
  try { feats = await arc(`${P.gis}/Admin_A12/MapServer/3`, {where, outFields: 'ADDRESS,UNIT,CMNTY,ZIP,RENUM', returnGeometry: 'true', outSR: 4326, resultRecordCount: 10, orderByFields: 'ADDRESS'}, fetchImpl, 9000); }
  catch (e) { throw bad("The county's address service didn't answer. Try again in a moment.", 502); }
  return feats.filter(f => f._g).map(f => ({address: titleCase(f.ADDRESS) + (f.UNIT && f.UNIT.trim() ? ' #' + f.UNIT.trim() : ''), street: f.ADDRESS, unit: (f.UNIT || '').trim() || null,
    city: titleCase(f.CMNTY), zip: f.ZIP ? String(f.ZIP) : null, parcel_id: f.RENUM || null, lat: f._g.y, lon: f._g.x}));
}

async function floodAt(pt, fetchImpl) {
  const fema = (layer, fields) => arc(`${NFHL}/${layer}`, {...pointParams(pt), outFields: fields}, fetchImpl, 15000);
  const [zones, panels, lomr] = await Promise.all([
    fema(28, 'FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE,V_DATUM,DEPTH'), fema(3, 'FIRM_PAN,EFF_DATE').catch(() => []), fema(1, 'CASE_NO,EFF_DATE').catch(() => [])]);
  const rank = z => (z.SFHA_TF === 'T' ? 1000 : 0) + (/^V/.test(z.FLD_ZONE) ? 500 : 0) + (z.STATIC_BFE > 0 ? z.STATIC_BFE : 0) + (/0\.2/.test(z.ZONE_SUBTY || '') ? 100 : 0);
  zones.sort((a, b) => rank(b) - rank(a));
  return {zone: zones[0] || null, panel: panels[0] || null, lomr: lomr[0] || null};
}
function floodText(z) {
  if (!z) return {zone: null, risk: 'Not on FEMA\'s flood map at this point'};
  const high = z.SFHA_TF === 'T' || /^(A|V)/.test(z.FLD_ZONE || '');
  if (high) return {zone: z.FLD_ZONE, risk: `FEMA high-risk area${/^V/.test(z.FLD_ZONE) ? ' with coastal waves' : ''}. Lenders require flood insurance with a federally backed mortgage.`, high: true};
  if (z.FLD_ZONE === 'X' && /0\.2/.test(z.ZONE_SUBTY || '')) return {zone: 'X (shaded)', risk: 'Moderate risk, outside the high-risk area (0.2% annual chance flood)'};
  if (z.FLD_ZONE === 'X') return {zone: 'X', risk: 'Minimal flood hazard on FEMA\'s map'};
  if (z.FLD_ZONE === 'D') return {zone: 'D', risk: 'Flood risk not determined'};
  return {zone: z.FLD_ZONE, risk: ''};
}

/* ---------- tax ---------- */
// Same arithmetic as the My Address page (site/address.js taxParts and renderTax).
function taxParts(p, ex, second2026) {
  if (ex) {
    const [tsd, tnsd, h1, h2, oth] = ex, assessed = +p.VASTOTAL || 0, just = +p.VASJUST || 0, exempt = h1 + h2 + oth;
    return {homestead: h1 > 0, assessed, just, exempt, school: tsd, non: tnsd, roll: true};
  }
  const hx = /\bHX\b/.test(p.DEXEMPTS || ''), assessed = +p.VASTOTAL || 0, just = +p.VASJUST || 0, exempt = +p.VASEXEMPT || 0, taxable = +p.VASTAXABLE || 0;
  const second = hx ? Math.min(Math.max(assessed - 50000, 0), second2026) : 0;
  const fullEx = taxable === 0 && /\b(13|14|VT|96)\b/.test(p.DEXEMPTS || '');
  return {homestead: hx, assessed, just, exempt, school: fullEx ? 0 : hx ? Math.max(0, taxable + second) : Math.max(0, just - exempt), non: taxable, roll: false};
}
function taxEstimate(D, parcel, cityName, ex, nav) {
  const code = String(parcel.DTAXDIST || '').trim();
  let id = D.taxdist[code];
  const exact = !!id;
  if (!id) id = cityName && D.districts[cityName] ? cityName : 'unincorporated';
  const d = D.districts[id];
  if (!d) return null;
  const t = taxParts(parcel, ex, D.second2026 || 0);
  const lines = d.stack.map(aid => {
    const a = D.auth[aid];
    return a && a.m > 0 ? {authority_id: aid, authority: a.n, group: a.g, school: !!a.school, millage: a.m, amount: Math.round((a.school ? t.school : t.non) / 1000 * a.m * 100) / 100} : null;
  }).filter(Boolean);
  const tax = lines.reduce((s, r) => s + r.amount, 0);
  const fees = (nav || []).map(([c, a]) => ({code: c, fee: (D.navLabel || {})[c] || `Other charge (${c})`, amount: Number(a)}));
  const feeTotal = fees.reduce((s, f) => s + f.amount, 0);
  return {district: id, district_label: d.label, district_from_parcel: exact, total_millage: d.total, fiscal_year: D.fy,
    homestead: t.homestead, market_value: t.just, assessed_value: t.assessed, exemptions: t.exempt, taxable_school: t.school, taxable_other: t.non,
    lines, property_tax: Math.round(tax), fees, fees_total: Math.round(feeTotal), estimated_bill: Math.round(tax + feeTotal),
    note: `Estimate: 2026 values × the ${D.fy} rates, plus the flat fees on the FY2026 bill. The Tax Collector's bill is the amount owed. A sale removes the seller's homestead, so a buyer's bill is often higher.`};
}

/* ---------- officials ---------- */
const normName = s => String(s || '').toLowerCase().replace(/[.,]/g, ' ').split(/\s+/).filter(w => w.length > 1 && !/^(jr|sr|ii|iii|iv)$/.test(w));
// A GIS representative name -> one person in people-directory for that government (last name + first name prefix), or null.
function matchPerson(people, name, gov) {
  const a = normName(name); if (a.length < 2) return null;
  const hits = (people || []).filter(p => (!gov || (p.gov_ids || []).includes(gov))).filter(p => {
    const b = normName(p.name); return b.length > 1 && b[b.length - 1] === a[a.length - 1] && (b[0].startsWith(a[0]) || a[0].startsWith(b[0]));
  });
  return hits.length === 1 ? hits[0] : null;
}
const CITY_GOV = {'Panama City': 'pc', 'Panama City Beach': 'pcb', 'Lynn Haven': 'lh', 'Callaway': 'cw', 'Springfield': 'sp', 'Parker': 'parker', 'Mexico Beach': 'mb'};

/* ---------- the sections ---------- */
// needs: datasets that must be in the catalog for the section to run (otherwise status "pending").
// module: an api/_*.js file the section uses when present (it may arrive with another pull request).
const SECTIONS = [
  {id: 'property', title: 'The property', async run(c) {
    const p = await c.parcel();
    if (!p) return {status: 'none', note: 'No parcel record came back for this address.'};
    const sales = [1, 2, 3].map(i => ({date: isoDay(p[`SALE${i}DATE`]), price: num(p[`SALE${i}PRADJ`]), kind: String(p[`SALE${i}QU_VI`] || '').trim()}))
      .filter(s => s.date && s.price > 0 && Number(s.date.slice(0, 4)) >= FIRST_YEAR)
      .map(s => ({date: s.date, price: s.price, qualified: /^Q/.test(s.kind), vacant: /V$/.test(s.kind)}));
    return {data: {parcel_id: p.A1RENUM, use: titleCase(p.DORAPPDESC), use_code: String(p.DORAPPCODE || '').trim() || null,
      year_built: num(p.S1YRBLTACT) || null, effective_year: num(p.S1YRBLTEFF) || null, heated_sqft: num(p.S1AREAHEAT) || null, total_sqft: num(p.S1AREATTL) || null,
      bedrooms: num(p.S1BEDRMS) || null, bathrooms: num(p.S1BATHRMS) || null, stories: num(p.S1STORIES) || null, units: num(p.S1UNITS) || null, acres: num(p.DTAXACRES),
      subdivision: p.SubdivName ? titleCase(p.SubdivName) : null, block: p.SubdivBlk || null, lot: p.SubdivLot || null,
      market_value: num(p.VASJUST), assessed_value: num(p.VASTOTAL), building_value: num(p.VAPBLDG), land_value: num(p.VAPLNDMRK),
      homestead: /\bHX\b/.test(p.DEXEMPTS || ''), sales, appraiser_url: p.PLINK || null},
      note: 'From the Property Appraiser\'s parcel data on the county GIS server (2026 roll). Owner names are not shown; they are public on the Property Appraiser\'s site. Sales before 2016 are left out.',
      sources: [{label: 'Bay County Property Appraiser', url: p.PLINK || 'https://www.baypa.net/'}]};
  }},
  {id: 'tax', title: 'Property tax estimate', needs: ['tax-districts', 'property-tax-rates'], async run(c) {
    const p = await c.parcel();
    if (!p) return {status: 'none', note: 'No parcel record, so there is no value to estimate from.'};
    const D = await c.file('/data/app/address.json');
    const [ex, nav] = await Promise.all([c.shard('ex', p.A1RENUM, D), c.shard('nav', p.A1RENUM, D)]);
    const est = taxEstimate(D, p, await c.cityName(), ex, nav);
    return est ? {data: est, sources: [{label: 'Florida Department of Revenue tax rates', url: 'https://floridarevenue.com/property/Pages/DataPortal.aspx'}, {label: 'Bay County Tax Collector', url: 'https://www.baycountytaxcollector.com/'}]}
      : {status: 'none', note: 'This tax district isn\'t in the rate tables.'};
  }},
  {id: 'hazards', title: 'Flood, storm and evacuation', async run(c) {
    const [fl, evac, cra, p] = await Promise.all([floodAt(c.pt, c.fetch).catch(() => null), c.layer('Admin_A12/MapServer/80', 'EZONE'), c.layer('Admin_A12/MapServer/27', 'CRA,EST_YEAR'), c.parcel()]);
    if (!fl && evac == null) return {status: 'error', note: 'FEMA\'s and the county\'s map servers didn\'t answer.'};
    const f = fl ? floodText(fl.zone) : null, eff = ms => (ms ? new Date(ms).toISOString().slice(0, 10) : null);
    return {data: {flood_zone: f ? f.zone : null, flood_risk: f ? f.risk : 'Couldn\'t reach FEMA\'s flood map', high_risk: !!(f && f.high),
      base_flood_elevation_ft: fl && fl.zone && fl.zone.STATIC_BFE > 0 ? fl.zone.STATIC_BFE : null, vertical_datum: fl && fl.zone ? fl.zone.V_DATUM || null : null,
      firm_panel: fl && fl.panel ? fl.panel.FIRM_PAN : null, firm_effective: fl && fl.panel ? eff(fl.panel.EFF_DATE) : null,
      map_revision: fl && fl.lomr && fl.lomr.CASE_NO ? {case: fl.lomr.CASE_NO, effective: eff(fl.lomr.EFF_DATE)} : null,
      evacuation_zone: evac && evac[0] && evac[0].EZONE ? evac[0].EZONE : null, storm_surge: p && p.Surge ? p.Surge : null,
      cra_district: cra && cra[0] ? cra[0].CRA : null, cra_since: cra && cra[0] ? cra[0].EST_YEAR || null : null},
      note: 'Flood zone is read live from FEMA\'s National Flood Hazard Layer at the address point. The lender\'s flood determination or an elevation certificate decides a building\'s zone.',
      sources: [{label: 'FEMA Flood Map Service Center', url: `https://msc.fema.gov/portal/search?AddressQuery=${encodeURIComponent(c.addressLine)}`}, {label: 'Bay County Emergency Services: know your zone', url: 'https://www.baycountyfl.gov/176/Emergency-Services'}]};
  }},
  {id: 'schools', title: 'Zoned public schools', async run(c) {
    const S = c.mod('_schools'), zones = S && await c.rows('school-zones'), schools = S && await c.rows('schools');
    if (S && zones && schools) {
      const z = S.zonedAt(zones, schools, c.pt.lat, c.pt.lon);
      const one = (lvl, x) => x ? {level: lvl, school: x.school ? x.school.name : x.zone, grades: x.school ? x.school.grades : null, state_grade: x.school ? x.school.latest_grade : null,
        state_grade_year: x.school ? x.school.latest_grade_year : null, enrollment: x.school ? x.school.enrollment : null, phone: x.school ? x.school.phone : null, page_url: x.school ? x.school.page_url : null} : null;
      return {data: {schools: [one('Elementary', z.elementary), one('Middle', z.middle), one('High', z.high)].filter(Boolean)}, note: z.note,
        sources: [{label: 'Bay District Schools', url: 'https://www.bay.k12.fl.us/'}]};
    }
    const lv = await Promise.all([0, 1, 2].map(i => c.layer(`SchoolAttendanceZones/MapServer/${i}`, 'NAME')));
    if (lv.every(x => x == null)) return {status: 'error', note: 'The county\'s school zone map didn\'t answer.'};
    const list = ['Elementary', 'Middle', 'High'].map((level, i) => lv[i] && lv[i][0] ? {level, school: titleCase(lv[i][0].NAME)} : null).filter(Boolean);
    return {data: {schools: list}, note: 'Attendance zones from Bay District Schools via the county GIS server. Choice, magnet, charter and virtual schools take students from outside their zone; confirm with the district before you rely on it.',
      sources: [{label: 'Bay District Schools', url: 'https://www.bay.k12.fl.us/'}]};
  }},
  {id: 'utilities', title: 'Utilities and trash day', module: '_utilities', needs: ['utility-providers', 'trash-pickup', 'trash-holidays', 'utility-rates'], async run(c) {
    const U = c.mod('_utilities');
    const [providers, trash, holidays, rates] = await Promise.all(['utility-providers', 'trash-pickup', 'trash-holidays', 'utility-rates'].map(id => c.rows(id)));
    const r = await U.lookup({providers, trash, holidays, rates}, {lat: c.pt.lat, lon: c.pt.lon, place: c.place}, c.fetch);
    return {data: {services: r.services, pickup: r.pickup, holidays: (r.holidays || []).slice(0, 6), rates: (r.rates || []).slice(0, 12)}, note: r.note};
  }},
  {id: 'zoning', title: 'Zoning and development nearby', async run(c) {
    const G = 'LandUsePlanning/MapServer';
    const [zon, flu, dos, dev] = await Promise.all([c.layer(`${G}/1`, 'ZONING,Label'), c.layer(`${G}/2`, 'FLU_CODE,Label'),
      c.layer('Departmental/Planning/MapServer/18', 'NAME,NUMBER,DESCRIPTION,TYPE,DO_ISSUED,APPLICATION_RECEIVED', {distance: 0.5, units: 'esriSRUnit_StatuteMile', returnGeometry: 'true', outSR: 4326}),
      c.rows('development-projects')]);
    if (zon == null && flu == null && dos == null && !dev) return {status: 'error', note: 'The county\'s planning maps didn\'t answer.'};
    const cut = Date.now() - 5 * 365.25 * 864e5;
    let projects;
    if (dev) {
      projects = nearRows(dev, c.pt, 1, 8).map(({r, mi}) => ({name: r.name, description: r.description || r.size || null, status: r.status || null,
        date: r.permit_date || r.approved_date || r.applied_date || null, government: r.government || null, miles: mi, source_url: r.source_url || null}));
    } else {
      projects = (dos || []).map(d => ({name: d.NAME, description: d.DESCRIPTION || null, status: d.TYPE || null, date: isoDay(d.DO_ISSUED || d.APPLICATION_RECEIVED),
        government: 'Bay County', miles: d._g ? miles(c.pt, {lat: d._g.y, lon: d._g.x}) : null, source_url: null}))
        .filter(d => !d.date || Date.parse(d.date) >= cut).sort((a, b) => (a.miles ?? 9) - (b.miles ?? 9)).slice(0, 8);
    }
    const z = zon && zon[0] ? (zon[0].ZONING === 'See FLU' ? 'Set by the future land use map' : zon[0].Label || zon[0].ZONING) : null;
    return {data: {zoning: z, future_land_use: flu && flu[0] ? flu[0].Label || flu[0].FLU_CODE : null, projects, projects_radius_miles: dev ? 1 : 0.5},
      note: 'Zoning from the county\'s land use map (cities keep their own maps; confirm with the city\'s planning office inside city limits). Building permits are searched on the county\'s permit portal.',
      sources: [{label: 'Bay County permit portal', url: 'https://portal.baycountyfl.gov/Permit/Locator'}]};
  }},
  {id: 'roads', title: 'Road and public works projects nearby', needs: ['sales-tax-projects'], async run(c) {
    const [st, rc] = await Promise.all([c.rows('sales-tax-projects'), c.rows('road-contracts')]);
    const projects = nearRows(st, c.pt, 1, 6).map(({r, mi}) => ({name: r.name, kind: 'Half-cent sales tax', status: String(r.status || '').replace(/_/g, ' ') || null,
      pct_complete: r.pct_complete ?? null, cost: r.actual_cost || r.programmed_cost || r.promised_cost || null, government: r.government || null, miles: mi, source_url: r.source_url || null}));
    const roads = rc ? nearRows(rc.filter(r => !r.final_acceptance_date && !r.ended_date), c.pt, 2, 5).map(({r, mi}) => ({name: r.description || r.roads, kind: `${r.agency || 'Road'} contract`,
      status: r.status || null, cost: num(r.amount), completion: r.estimated_completion_date || null, contractor: r.contractor || null, contractor_id: r.vendor_id ? `vendor:${r.vendor_id}` : null, miles: mi, source_url: r.source_url || null})) : [];
    return {data: {projects: [...roads, ...projects]}, note: 'Half-cent sales tax projects within a mile' + (rc ? ' and open road contracts within two miles' : '') + ', measured from the address point.'};
  }},
  {id: 'outdoors', title: 'Parks and beaches nearby', async run(c) {
    const [parks, beach] = await Promise.all([c.rows('parks'), c.rows('beach-access')]);
    let list;
    if (parks) list = nearRows(parks, c.pt, 5, 5).map(({r, mi}) => ({name: r.name, kind: r.kind || 'Park', address: r.address || null, facilities: r.facilities || null, miles: mi}));
    else {
      const g = await c.layer('Admin_A12/MapServer/41', 'NAME,ADDRESS,CLASSIFICA,SIZE_AC', {distance: 5, units: 'esriSRUnit_StatuteMile', returnGeometry: 'true', outSR: 4326});
      list = (g || []).map(x => ({name: titleCase(x.NAME), kind: x.CLASSIFICA ? titleCase(x.CLASSIFICA) : 'Park', address: x.ADDRESS ? titleCase(x.ADDRESS) : null, acres: num(x.SIZE_AC), miles: x._g ? miles(c.pt, {lat: x._g.y, lon: x._g.x}) : null}))
        .filter(x => x.miles != null).sort((a, b) => a.miles - b.miles).slice(0, 5);
    }
    const beaches = beach ? nearRows(beach, c.pt, 15, 3).map(({r, mi}) => ({name: r.name, address: r.address || null, parking: r.parking ?? null, restroom: r.restroom ?? null, miles: mi})) : null;
    return {data: {parks: list, beaches}, status: beaches === null ? 'partial' : 'ok', note: beaches === null ? 'Beach accesses will appear here once the beaches data is published.' : 'Straight-line distances from the address point.'};
  }},
  {id: 'services', title: 'Nearby services', async run(c) {
    const near = (layer, fields) => c.layer(layer, fields, {distance: 10, units: 'esriSRUnit_StatuteMile', returnGeometry: 'true', outSR: 4326})
      .then(fs => (fs || []).map(x => ({...x, mi: x._g ? miles(c.pt, {lat: x._g.y, lon: x._g.x}) : 99})).sort((a, b) => a.mi - b.mi)[0] || null);
    const [fire, lib, mosq] = await Promise.all([near('Admin_A12/MapServer/42', 'NAME,FULLADDR'), near('Admin_A12/MapServer/39', 'NAME,ADDRESS,PHONE'), c.layer('Admin_A12/MapServer/34', 'DISTRICT,ADMINISTRATION')]);
    const item = (kind, x, addr) => x ? {kind, name: titleCase(x.NAME), address: x[addr] ? titleCase(x[addr]) : null, miles: x.mi} : null;
    return {data: {services: [item('Fire station', fire, 'FULLADDR'), item('Library', lib, 'ADDRESS')].filter(Boolean), mosquito_district: mosq && mosq[0] ? mosq[0].DISTRICT : null}};
  }},
  {id: 'officials', title: 'Who represents this address', needs: ['people-directory'], async run(c) {
    const cityName = await c.cityName(), people = await c.rows('people-directory');
    const L = (path, f) => c.layer(path, f || 'NAME,REPNAME,DISTRICTURL');
    const [comm, local, sb, house, senate, ush] = await Promise.all([L('Admin_A12/MapServer/28'), L('Admin_A12/MapServer/30', 'CITY,NAME,REPNAME,DISTRICTURL'),
      L('ElectionAdministration/MapServer/2'), L('ElectionAdministration/MapServer/3'), L('ElectionAdministration/MapServer/4'), L('ElectionAdministration/MapServer/5')]);
    const cityGov = CITY_GOV[cityName] || null;
    const seat = (office, x, gov) => {
      const a = x && x[0]; if (!a || !a.REPNAME) return null;
      const p = gov ? matchPerson(people, a.REPNAME, gov) : null;
      return {office, district: a.NAME || null, name: p ? p.name : titleCase(a.REPNAME), entity_id: p ? `person:${p.person_id}` : null, page_url: p ? `/people/${p.person_id}` : (a.DISTRICTURL || null)};
    };
    const seats = [seat('County Commission', comm, 'county'), cityGov ? seat(`${cityName} commission`, local, cityGov) : null, seat('School Board', sb, 'schools'),
      seat('Florida House', house), seat('Florida Senate', senate), seat('U.S. House', ush)].filter(Boolean);
    // The city's whole elected body (and its manager) from officeholder-terms: several cities elect at large, so the
    // county's local district layer has no district for them.
    let council = [];
    const terms = cityGov ? await c.rows('officeholder-terms') : null;
    if (terms) {
      try {
        council = require('./_officials').inOffice(terms, {gov: cityGov, place: c.place}).seats.flatMap(st => st.holders.filter(h => !h.vacant && h.person_name)
          .map(h => ({seat: st.seat, appointed: st.appointed, name: h.person_name, entity_id: h.person_id ? `person:${h.person_id}` : null, page_url: h.person_id ? `/people/${h.person_id}` : null})));
      } catch (e) { if (!e.expose) throw e; }
    }
    return {data: {local_government: cityName ? `City of ${cityName}` : `Unincorporated ${PLACES[c.place].name}`, gov_id: cityGov || 'county', seats, city_council: council},
      note: 'Districts and names from the county GIS server, which can lag an election by a few weeks.'};
  }},
  {id: 'events', title: 'Coming up nearby', async run(c) {
    const [community, meetings] = await Promise.all([c.rows('community-events'), c.rows('meetings')]);
    const cityName = await c.cityName(), gov = CITY_GOV[cityName] || 'county', today = new Date().toISOString().slice(0, 10);
    const town = s => String(s || '').toLowerCase();
    const ev = (community || []).filter(e => e.starts && String(e.starts).slice(0, 10) >= today && (!cityName || !e.town || town(e.town) === town(cityName) || e.gov === gov))
      .sort((a, b) => String(a.starts).localeCompare(String(b.starts))).slice(0, 6)
      .map(e => ({title: e.title, starts: e.starts, venue: e.venue || null, town: e.town || null, url: e.url || e.source_url || null}));
    const mt = (meetings || []).filter(m => !m.past && m.start >= today && [gov, 'county', 'schools'].includes(m.gov_id))
      .sort((a, b) => String(a.start).localeCompare(String(b.start))).slice(0, 5)
      .map(m => ({title: m.title, board: m.board, starts: m.start, location: m.location || null, url: m.agenda_url || null, gov_id: m.gov_id}));
    return {data: {events: ev, meetings: mt}, status: community ? 'ok' : 'partial', note: community ? null : 'Community events will appear here once the events calendar is published.'};
  }},
];

/* ---------- the report ---------- */
// deps: {fetchImpl, catalog, rows(id) -> rows | null, file(path) -> json, mod(name) -> module | null}
async function build(loc, deps) {
  const place = loc.place || 'fl-bay', P = PLACES[place];
  if (!P) throw bad(`Unknown place "${place}".`);
  const pt = {lat: Number(loc.lat), lon: Number(loc.lon)};
  const [x0, y0, x1, y1] = P.bbox;
  if (!Number.isFinite(pt.lat) || !Number.isFinite(pt.lon)) throw bad('Give an address, or lat and lon in decimal degrees.');
  if (pt.lon < x0 || pt.lon > x1 || pt.lat < y0 || pt.lat > y1) throw bad(`That point is outside ${P.name}.`, 404);
  const fetchImpl = deps.fetchImpl || fetch, memo = new Map();
  const once = (k, f) => { if (!memo.has(k)) memo.set(k, f()); return memo.get(k); };
  const has = id => !!(deps.catalog || []).find(d => d.id === id);
  const c = {
    place, pt, fetch: fetchImpl,
    addressLine: [loc.address, loc.city, P.state, loc.zip].filter(Boolean).join(', '),
    layer: (path, fields, extra = {}) => once(`L:${path}:${fields}:${JSON.stringify(extra)}`, () => arc(`${P.gis}/${path}`, {...pointParams(pt), outFields: fields, ...extra}, fetchImpl).catch(() => null)),
    parcel: () => once('parcel', async () => {
      const pf = PARCEL_FIELDS.join(',');
      if (loc.parcel_id) {
        const r = await arc(`${P.gis}/Admin_A12/MapServer/6`, {where: `A1RENUM='${String(loc.parcel_id).replace(/[^0-9A-Za-z-]/g, '')}'`, outFields: pf}, fetchImpl).catch(() => null);
        if (r && r[0]) return r[0];
      }
      const r = await arc(`${P.gis}/Admin_A12/MapServer/6`, {...pointParams(pt), outFields: pf}, fetchImpl).catch(() => null);
      return r && r[0] ? r[0] : null;
    }),
    cityName: () => once('city', async () => { const r = await c.layer('Admin_A12/MapServer/26', 'NAME'); return (r || []).map(x => x.NAME).find(n => n && !/unincorp/i.test(n)) || null; }),
    rows: id => once(`R:${id}`, async () => (has(id) ? deps.rows(id) : null)),
    file: path => once(`F:${path}`, () => deps.file(path)),
    shard: (kind, pid, D) => once(`S:${kind}:${pid}`, async () => {
      if (!pid || !D.shards || !D.shards[kind]) return null;
      try { const s = await deps.file(`/data/${kind}/${shardOf(pid, D.shards[kind])}.json`); return s ? s[pid] || null : null; } catch (e) { return null; }
    }),
    mod: name => (deps.mod ? deps.mod(name) : null),
  };
  const out = await Promise.all(SECTIONS.map(async s => {
    const base = {id: s.id, title: s.title};
    if ((s.module && !c.mod(s.module)) || (s.needs || []).some(id => !has(id))) return {...base, status: 'pending', note: 'This part of the report is coming soon.'};
    try {
      const r = await s.run(c);
      return {...base, status: r.status || 'ok', data: r.data || null, note: r.note || null, sources: r.sources || []};
    } catch (e) {
      if (!e.expose) console.error('address-report', s.id, e.message);
      return {...base, status: 'error', note: 'Couldn\'t load this part right now.'};
    }
  }));
  const cityName = await c.cityName();
  return {place_id: place, address: loc.address || null, city: cityName || loc.city || null, zip: loc.zip || null, lat: pt.lat, lon: pt.lon,
    jurisdiction: cityName ? `City of ${cityName}` : `Unincorporated ${P.name}`, generated_at: new Date().toISOString(), sections: out,
    note: 'Compiled from public records. Check anything a decision depends on with the agency named in each section. Owner names and private details are never included.'};
}

// Resolve ?address= / ?lat=&lon= into a location for build().
async function locate(q, fetchImpl = fetch) {
  const place = String(q.place || 'fl-bay');
  if (q.lat != null && q.lon != null && q.lat !== '' && q.lon !== '') return {place, lat: Number(q.lat), lon: Number(q.lon), address: q.label ? String(q.label).slice(0, 120) : null, parcel_id: q.parcel || null};
  if (!q.address) throw bad('Add ?address= (house number and street) or ?lat=&lon=.');
  const hits = await geocode(q.address, {place, zip: q.zip, fetchImpl});
  if (!hits.length) throw bad(`No address in the county matches "${String(q.address).slice(0, 80)}". Start with the house number and street name.`, 404);
  const h = hits[0];
  return {place, lat: h.lat, lon: h.lon, address: h.address, city: h.city, zip: h.zip, parcel_id: h.parcel_id, other_matches: hits.slice(1, 5).map(x => `${x.address}, ${x.city} ${x.zip || ''}`.trim())};
}

// Modules that arrive with other pull requests. Written as plain require() calls so Vercel bundles them once they exist;
// until then the require fails and the section that needs one reports "pending".
const OPTIONAL = {_schools: () => require('./_schools'), _utilities: () => require('./_utilities')};
function optional(name) {
  try { return OPTIONAL[name] ? OPTIONAL[name]() : null; }
  catch (e) { if (e.code !== 'MODULE_NOT_FOUND') console.error('address-report: module', name, e.message); return null; }
}

// One report for an API request. rowsOf(id) reads a dataset (database first, then the published file); file(path) reads
// a published file from the site.
async function forRequest(q, {catalog, rowsOf, file, fetchImpl = fetch, mod = optional}) {
  const loc = await locate(q, fetchImpl);
  const r = await build(loc, {fetchImpl, catalog: catalog.datasets || catalog, rows: rowsOf, file, mod});
  if (loc.other_matches && loc.other_matches.length) r.other_matches = loc.other_matches;
  if (loc.parcel_id) r.parcel_id = loc.parcel_id;
  return r;
}

module.exports = {forRequest, optional, PLACES, SECTIONS, PARCEL_FIELDS, build, locate, geocode, parseAddress, taxEstimate, taxParts, floodText, matchPerson, nearRows, shardOf, miles};
