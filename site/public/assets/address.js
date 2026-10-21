(() => {
const D = {"taxdist":{"2":"Callaway","02":"Callaway","6":"Lynn Haven","06":"Lynn Haven","8":"Mexico Beach","08":"Mexico Beach","10":"Parker","13":"Panama City Beach","16":"Panama City","20":"Springfield","31":"Panama City - Downtown DIB","55":"unincorporated","56":"unincorporated - beach area"},"craAgency":{"Downtown Extension CRA":"Panama City CRA","Downtown N Extension CRA":"Panama City CRA","Downtown North CRA":"Panama City CRA","St. Andrews CRA":"Panama City CRA","St Andrews CRA - West Expansion Area":"Panama City CRA","St Andrews CRA - East Expansion Area":"Panama City CRA","Millville CRA":"Panama City CRA","Downtown CRA / DIB":"Panama City CRA","Front Beach Road CRA":"Panama City Beach CRA","Pier Park CRA":"Panama City Beach CRA","Lynn Haven CRA":"Lynn Haven CRA","Callaway CRA":"Callaway CRA","Springfield CRA":"Springfield CRA","Parker CRA":"Parker CRA"},"cra":{"Panama City CRA":{"spent":14042979,"n":73},"Lynn Haven CRA":{"spent":1800964,"n":30},"Panama City Beach CRA":{"spent":80404359,"n":47},"Callaway CRA":{"spent":648087,"n":7},"Springfield CRA":{"spent":60017,"n":9},"Parker CRA":{"spent":148377,"n":2}},"districts":{"Panama City":{"label":"Panama City","stack":["bay_county_general","county_mosquito_control","school_rle","school_discretionary","school_capital_outlay","nwfwmd","city_panama_city"],"total":15.7938},"Panama City - Downtown DIB":{"label":"Panama City, downtown improvement district","stack":["bay_county_general","county_mosquito_control","school_rle","school_discretionary","school_capital_outlay","nwfwmd","city_panama_city","pc_downtown_improvement_board"],"total":18.7938},"Panama City Beach":{"label":"Panama City Beach","stack":["bay_county_general","beach_mosquito","school_rle","school_discretionary","school_capital_outlay","nwfwmd"],"total":10.9139},"Lynn Haven":{"label":"Lynn Haven","stack":["bay_county_general","county_mosquito_control","school_rle","school_discretionary","school_capital_outlay","nwfwmd","city_lynn_haven"],"total":15.0439},"Callaway":{"label":"Callaway","stack":["bay_county_general","county_mosquito_control","school_rle","school_discretionary","school_capital_outlay","nwfwmd","city_callaway"],"total":13.6939},"Springfield":{"label":"Springfield","stack":["bay_county_general","county_mosquito_control","school_rle","school_discretionary","school_capital_outlay","nwfwmd","city_springfield"],"total":15.8589},"Parker":{"label":"Parker","stack":["bay_county_general","county_mosquito_control","school_rle","school_discretionary","school_capital_outlay","nwfwmd","city_parker"],"total":13.9939},"Mexico Beach":{"label":"Mexico Beach","stack":["bay_county_general","county_mosquito_control","school_rle","school_discretionary","school_capital_outlay","nwfwmd","city_mexico_beach"],"total":16.2439},"unincorporated":{"label":"Unincorporated Bay County (not in a city)","stack":["bay_county_general","county_fire_mstu","county_mosquito_control","school_rle","school_discretionary","school_capital_outlay","nwfwmd"],"total":12.3739},"unincorporated - beach area":{"label":"Unincorporated beach area (outside PCB city limits)","stack":["bay_county_general","county_fire_mstu","beach_mosquito","school_rle","school_discretionary","school_capital_outlay","nwfwmd"],"total":12.2939}},"auth":{"bay_county_general":{"n":"Bay County Commission","g":"county","school":false,"m":5.4362},"county_fire_mstu":{"n":"County fire service (outside cities)","g":"countysvc","school":false,"m":1.38},"county_mosquito_control":{"n":"County mosquito control","g":"countysvc","school":false,"m":0.2},"school_rle":{"n":"Schools: state-required rate","g":"school","school":true,"m":3.089},"school_discretionary":{"n":"Schools: local operating","g":"school","school":true,"m":0.748},"school_capital_outlay":{"n":"Schools: buildings and buses","g":"school","school":true,"m":1.5},"nwfwmd":{"n":"NW Florida Water Management District","g":"other","school":false,"m":0.0207},"beach_mosquito":{"n":"Beach Mosquito Control District","g":"other","school":false,"m":0.12},"pc_downtown_improvement_board":{"n":"Downtown Improvement Board","g":"other","school":false,"m":3.0},"city_callaway":{"n":"City of Callaway","g":"city","school":false,"m":2.7},"city_lynn_haven":{"n":"City of Lynn Haven","g":"city","school":false,"m":4.05},"city_mexico_beach":{"n":"City of Mexico Beach","g":"city","school":false,"m":5.25},"city_panama_city":{"n":"City of Panama City","g":"city","school":false,"m":4.7999},"city_parker":{"n":"City of Parker","g":"city","school":false,"m":3.0},"city_springfield":{"n":"City of Springfield","g":"city","school":false,"m":4.865}},"groups":[["school","Schools"],["county","Bay County"],["city","Your city"],["countysvc","County fire & mosquito"],["other","Special districts"]],"fy":"FY2026","second2026":26411};
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

/* ---------- autocomplete ---------- */
const inp = $('q'), list = $('acList');
let timer, items = [], active = -1, seq = 0;
function clean(s) { return s.toUpperCase().replace(/['"%_\\]/g, '').replace(/\s+/g, ' ').trim(); }
inp.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(suggest, 220); });
async function suggest() {
  const s = clean(inp.value);
  if (s.length < 3 || !/^\d/.test(s)) { hideList(); return; }
  const my = ++seq;
  try {
    const f = await q('Admin_A12/MapServer/3', {where: `ADDRESS LIKE '${s}%'`, outFields: 'ADDRESS,UNIT,CMNTY,ZIP,RENUM', returnGeometry: 'true', outSR: 4326, resultRecordCount: 10, orderByFields: 'ADDRESS'});
    if (my !== seq) return;
    items = f; active = -1;
    if (!f.length) { list.innerHTML = '<li class="ac-empty">No matching address. Try just the number and street name.</li>'; showList(); return; }
    list.innerHTML = f.map((x, i) => `<li role="option" id="ac${i}" data-i="${i}">${esc(title(x.attributes.ADDRESS))}${x.attributes.UNIT ? ' #' + esc(x.attributes.UNIT) : ''}<span>${esc(x.attributes.CMNTY || '')} ${esc(x.attributes.ZIP || '')}</span></li>`).join('');
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
    atPoint('Admin_A12/MapServer/34', pt), atPoint('Admin_A12/MapServer/51', pt), atPoint('Admin_A12/MapServer/80', pt), atPoint('Admin_A12/MapServer/84', pt),
    atPoint('ElectionAdministration/MapServer/2', pt), atPoint('ElectionAdministration/MapServer/3', pt), atPoint('ElectionAdministration/MapServer/4', pt), atPoint('ElectionAdministration/MapServer/5', pt),
    atPoint('SchoolAttendanceZones/MapServer/0', pt), atPoint('SchoolAttendanceZones/MapServer/1', pt), atPoint('SchoolAttendanceZones/MapServer/2', pt),
    near(42), near(39), near(41)]);
  const cityName = (city || []).map(c => c.NAME).find(n => n && !/unincorp/i.test(n)) || null;
  $('aSub').textContent = `${cityName ? 'City of ' + cityName : 'Unincorporated Bay County'} · ZIP ${a.ZIP || '—'}${parcel ? ' · Parcel ' + parcel.A1RENUM : ''}`;
  const pa = $('paLink');
  if (parcel?.PLINK) { pa.href = parcel.PLINK; pa.hidden = false; } else pa.hidden = true;
  renderTax(parcel, cityName);
  renderProp(parcel);
  renderReps(comm, local, sb, house, senate, ush, cityName);
  renderSchools(es, ms, hs);
  renderCra(cra);
  renderSafe(flood, evac, mosq, tdc, fire, lib, park);
  drawMap(pt, cityName, cra?.[0]?.CRA);
}
function miles(a, b) { if (!b) return 1e9; const R = 3958.8, t = Math.PI / 180, dLat = (b.y - a.y) * t, dLon = (b.x - a.x) * t; const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.y * t) * Math.cos(b.y * t) * Math.sin(dLon / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); }
const kv = rows => rows.filter(Boolean).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('');

function distFor(parcel, cityName) {
  const code = String(parcel?.DTAXDIST || '').trim();
  let id = D.taxdist[code];
  if (!id) id = cityName && D.districts[cityName] ? cityName : 'unincorporated';
  return {id, d: D.districts[id], exact: !!D.taxdist[code]};
}
function taxParts(p) {
  const hx = /\bHX\b/.test(p.DEXEMPTS || ''), assessed = +p.VASTOTAL || 0, just = +p.VASJUST || 0, exempt = +p.VASEXEMPT || 0, taxable = +p.VASTAXABLE || 0;
  const second = hx ? Math.min(Math.max(assessed - 50000, 0), D.second2026) : 0;
  const other = hx ? Math.max(0, exempt - Math.min(assessed, 25000) - second) : exempt;
  return {hx, assessed, just, exempt, taxable, second, other, school: hx ? Math.max(0, taxable + second) : Math.max(0, just - exempt), non: taxable};
}
function renderTax(p, cityName) {
  const el = $('taxBody');
  if (!p) { el.innerHTML = `<p class="muted">No parcel record came back for this address, so there's no value to estimate from. <a href="/public-money/tax-dollars">Use the calculator →</a></p>`; return; }
  const {id, d, exact} = distFor(p, cityName), t = taxParts(p);
  const rows = d.stack.map(aid => { const a = D.auth[aid]; return {n: a.n, g: a.g, m: a.m, amt: (a.school ? t.school : t.non) / 1000 * a.m}; }).filter(r => r.m > 0);
  const tot = rows.reduce((s, r) => s + r.amt, 0);
  const byG = D.groups.map(([g]) => [g, rows.filter(r => r.g === g).reduce((s, r) => s + r.amt, 0)]).filter(x => x[1] > 0.5);
  el.innerHTML = `<div class="bill-hd"><span class="bill-v sm">${usd(tot)}<small> / year</small></span><span class="muted small">${esc(d.label)} · ${String(+d.total.toFixed(4))} mills${exact ? '' : ' (area inferred from the map)'}</span></div>
    <div class="stackbar">${byG.map(([g, v]) => `<span class="seg" style="flex:${v} 1 0;background:var(--s${GI[g]})" title="${esc(GN[g])}: ${usd(v)}"></span>`).join('')}</div>
    <ul class="leg mini2">${byG.map(([g, v]) => `<li><i style="background:var(--s${GI[g]})"></i><span>${esc(g === 'city' ? (rows.find(r => r.g === 'city')?.n || 'City') : GN[g])}</span><b>${usd(v)}</b></li>`).join('')}</ul>
    <p class="muted small">2026 values × ${D.fy} rates. Property tax only; fees not included. <a href="/public-money/tax-dollars">Where it goes →</a></p>`;
}
function renderProp(p) {
  const el = $('propBody');
  if (!p) { el.innerHTML = '<dd class="muted">No parcel record found for this address.</dd>'; return; }
  const t = taxParts(p), codes = String(p.DEXEMPTS || '').trim().split(/\s+/).filter(Boolean);
  el.innerHTML = kv([
    ['Use', esc(title(p.DORAPPDESC))],
    p.S1YRBLTACT ? ['Built', esc(p.S1YRBLTACT) + (p.S1AREAHEAT ? ` · ${Math.round(p.S1AREAHEAT).toLocaleString()} heated sq ft` : '')] : null,
    ['Market (just) value', usd(t.just)],
    ['<span class="term" data-term="assessed-value">Assessed value</span>', usd(t.assessed) + (t.assessed < t.just ? ` <span class="muted small">(capped ${usd(t.just - t.assessed)} below market)</span>` : '')],
    ['Exemptions', t.exempt ? usd(t.exempt) + ` <span class="muted small">(${t.hx ? 'homestead' : 'codes'}${codes.filter(c => c !== 'HX').length ? (t.hx ? ' + ' : ' ') + esc(codes.filter(c => c !== 'HX').join(', ')) : ''})</span>` : 'None'],
    ['<span class="term" data-term="taxable-value">Taxable value</span>', usd(t.non) + (t.hx ? ` <span class="muted small">(${usd(t.school)} for school taxes)</span>` : '')],
  ]);
}
function renderReps(comm, local, sb, house, senate, ush, cityName) {
  const r = (x, pre) => x?.[0] ? `${x[0].DISTRICTURL ? `<a href="${esc(x[0].DISTRICTURL)}" target="_blank" rel="noopener">${esc(x[0].REPNAME || '—')}</a>` : esc(x[0].REPNAME || '—')} <span class="muted small">${esc(pre || x[0].NAME || '')}</span>` : '<span class="muted">—</span>';
  $('repBody').innerHTML = kv([
    ['County Commission', r(comm)],
    cityName ? ['City', `City of ${esc(cityName)}${local?.[0] ? ' · ' + r(local) : ''}`] : ['City', '<span class="muted">None (unincorporated). The County Commission is your local government.</span>'],
    ['School Board', r(sb)],
    ['Florida House', r(house)],
    ['Florida Senate', r(senate)],
    ['U.S. House', r(ush)],
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
  const ag = D.craAgency[c.CRA], s = ag && D.cra[ag];
  el.innerHTML = `<p>This address is inside the <b>${esc(c.CRA)}</b> district${c.EST_YEAR ? ` (created ${esc(c.EST_YEAR)})` : ''}. The city and county taxes on growth in this area since then go to the ${esc(ag || 'CRA')}'s fund and must be spent inside its districts.</p>
    ${s ? `<p class="small">${esc(ag)}: <b>${big(s.spent)}</b> in documented spending and awards across ${s.n} records on this site.</p>` : ''}
    <p class="small"><a href="/public-money/cra-spending">See what it pays for →</a></p>`;
}
function renderSafe(flood, evac, mosq, tdc, fire, lib, park) {
  const f = flood?.[0];
  const floodTxt = flood === null ? '<span class="muted">Couldn\'t check</span>'
    : f ? `<b>Zone ${esc(f.FLD_ZONE)}${f.ZONE_SUBTY && f.ZONE_SUBTY.trim() ? ' (' + esc(title(f.ZONE_SUBTY)) + ')' : ''}</b> · FEMA high-risk area${f.STATIC_BFE > 0 ? ` · base flood elevation ${esc(f.STATIC_BFE)} ft` : ''}`
    : 'Outside FEMA\'s mapped high-risk flood areas';
  const nearTxt = (x, nm) => x ? `${esc(x.NAME || nm)} <span class="muted small">${x.d.toFixed(1)} mi${x.FULLADDR || x.ADDRESS ? ' · ' + esc(x.FULLADDR || x.ADDRESS) : ''}</span>` : '<span class="muted">None within 10 miles</span>';
  $('safeBody').innerHTML = kv([
    ['Flood zone', floodTxt],
    ['Evacuation zone', evac?.[0]?.EZONE ? `<b>Zone ${esc(evac[0].EZONE)}</b> <span class="muted small">Know your zone before a storm</span>` : '<span class="muted">Not in a mapped zone</span>'],
    ['Nearest fire station', nearTxt(fire, 'Fire station')],
    ['Nearest library', nearTxt(lib, 'Library')],
    ['Nearest park', nearTxt(park, 'Park')],
    mosq?.[0] ? ['Mosquito control', esc(mosq[0].DISTRICT) + (mosq[0].ADMINISTRATION === 'BC' ? ' <span class="muted small">(Bay County)</span>' : '')] : null,
    tdc?.[0] ? ['Tourist tax area', esc(tdc[0].ID)] : null,
  ]) + '<dd class="span muted small">Flood zones are FEMA\'s effective map as published by Bay County. Lenders and insurers use the official FEMA map; check <a href="https://msc.fema.gov/portal/search" target="_blank" rel="noopener">FEMA\'s Map Service Center</a>.</dd>';
}

/* Amendment 3 card, filled from the same parcel */
const _renderTax = renderTax;
renderTax = function (p, cityName) { // eslint-disable-line no-func-assign
  _renderTax(p, cityName);
  const el = $('a3Body');
  if (!p) { el.innerHTML = '<p class="muted">No parcel record to estimate from. <a href="/public-money/amendment-3">Try the calculator →</a></p>'; return; }
  const {d} = distFor(p, cityName), t = taxParts(p);
  const nonM = d.stack.filter(a => !D.auth[a].school).reduce((s, a) => s + D.auth[a].m, 0);
  if (!t.hx) {
    el.innerHTML = `<p>This property has no homestead exemption, so Amendment 3 wouldn't lower its tax bill directly. It would limit how fast its taxed value can rise to <b>5% a year instead of 10%</b> for non-school taxes.${t.assessed < t.just ? ` Its value is already capped ${usd(t.just - t.assessed)} below market.` : ''}</p><p class="small"><a href="/public-money/amendment-3">What Amendment 3 does →</a></p>`;
    return;
  }
  const after = Math.max(0, t.assessed - 250000 - t.other), save = (t.non - after) / 1000 * nonM;
  el.innerHTML = `<p>With the full $250,000 homestead exemption on today's value and rates, this home's county, city and district taxes would drop by about <b>${usd(save)} a year</b>${after === 0 ? ', to zero; it would still pay school tax' : ''}.</p>
    <p class="muted small">Assumes rates stay the same and the owner was a Florida resident before 2027. Local governments here would collect less; see the state's estimates. <a href="/public-money/amendment-3">Amendment 3 →</a></p>`;
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
