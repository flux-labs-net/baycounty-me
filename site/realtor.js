/* Realtor console (/realtor): an agent signs in, saves their branding, runs any address and downloads a branded PDF.
   The report comes from GET /api/v1/address-report (api/_address_report.js); accounts, branding and history from
   /api/realtor (api/_realtor.js). Sections the API marks "pending" (data not published yet) are listed as coming soon
   on screen and left out of the PDF, so new sections appear here as soon as the API returns them. */
(() => {
const GIS = 'https://gis.baycountyfl.gov/arcgis/rest/services/Admin_A12/MapServer/3/query';
const PDFMAKE = 'https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.10/pdfmake.min.js';
const VFS = 'https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.10/vfs_fonts.min.js';
const DEF = {primary: '#1e3a76', accent: '#e5564a'};
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const usd = n => n == null ? '' : '$' + Math.round(n).toLocaleString('en-US');
const usd2 = n => n == null ? '' : '$' + Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
const title = s => String(s || '').toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase()).replace(/\b(Ne|Nw|Se|Sw|Us|Cr|Sr)\b/g, m => m.toUpperCase());
const mi = m => m == null ? '' : (m < 0.1 ? 'under 0.1 mi' : m.toFixed(1) + ' mi');
const day = s => { if (!s) return ''; const d = new Date(String(s).length === 10 ? s + 'T12:00:00' : s); return isNaN(d) ? '' : d.toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'}); };
const month = s => { if (!s) return ''; const d = new Date(String(s).length === 10 ? s + 'T12:00:00' : s); return isNaN(d) ? '' : d.toLocaleDateString('en-US', {month: 'short', year: 'numeric'}); };
const COLOR = /^#[0-9a-f]{6}$/i;
const color = (v, d) => COLOR.test(v || '') ? v : d;
function lum(hex) { const c = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(v => v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; }
const onColor = hex => lum(hex) > 0.45 ? '#161B24' : '#FFFFFF';
const nameLink = (id, text, url) => id && window.BC && BC.href && BC.href(id) ? BC.a(id, text) : url && url.startsWith('/') ? `<a href="${esc(url)}">${esc(text)}</a>` : url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(text)}</a>` : esc(text);

let ME = null, REPORT = null, PICK = null;

/* ---------- API ---------- */
async function api(action, body) {
  const r = await fetch(`/api/realtor?action=${action}`, body === undefined ? {credentials: 'same-origin'}
    : {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-BCM-Agent': '1'}, body: JSON.stringify(body)});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(j.error || 'Something went wrong.'), {status: r.status});
  return j;
}

/* ---------- views ---------- */
function show(view) {
  $('rcOut').hidden = view !== 'out'; $('rcIn').hidden = view !== 'in';
  document.querySelectorAll('[data-signed-in]').forEach(el => { el.hidden = view !== 'in'; });
}
function tab(name) {
  document.querySelectorAll('.rc-tab').forEach(b => b.setAttribute('aria-selected', b.dataset.tab === name));
  document.querySelectorAll('.rc-panel').forEach(p => { p.hidden = p.id !== 'p-' + name; });
  try { sessionStorage.setItem('rc-tab', name); } catch (e) { /* private window */ }
}
document.querySelectorAll('.rc-tab').forEach(b => b.addEventListener('click', () => tab(b.dataset.tab)));

async function start() {
  const u = new URL(location.href);
  if (u.searchParams.get('signin') === 'expired') { $('signMsg').className = 'rc-msg err'; $('signMsg').textContent = 'That sign-in link expired or was already used. Send yourself a new one.'; }
  try { ME = await api('me'); }
  catch (e) { show('out'); if (e.status !== 401) { $('signMsg').className = 'rc-msg err'; $('signMsg').textContent = e.status === 503 ? 'The realtor console is being set up. Please check back soon.' : e.message; } return; }
  show('in');
  $('who').textContent = ME.agent.email;
  fillBrand(ME.brand || {});
  renderHistory();
  let t = 'run'; try { t = sessionStorage.getItem('rc-tab') || (ME.brand ? 'run' : 'brand'); } catch (e) { t = ME.brand ? 'run' : 'brand'; }
  tab(t);
  const a = u.searchParams.get('lat') && u.searchParams.get('lon') ? {lat: +u.searchParams.get('lat'), lon: +u.searchParams.get('lon'), address: u.searchParams.get('a') || '', city: u.searchParams.get('c') || '', zip: u.searchParams.get('z') || '', parcel_id: u.searchParams.get('p') || ''} : null;
  if (a) { PICK = a; $('q').value = a.address; run(); }
}

/* ---------- sign in ---------- */
$('signForm').addEventListener('submit', async e => {
  e.preventDefault();
  const btn = $('signBtn'), msg = $('signMsg');
  btn.disabled = true; msg.className = 'rc-msg'; msg.textContent = 'Sending…';
  try {
    const r = await fetch('/api/realtor?action=login', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email: $('email').value})});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || 'Couldn’t send the link. Try again.');
    msg.className = 'rc-msg ok'; msg.textContent = j.message;
  } catch (err) { msg.className = 'rc-msg err'; msg.textContent = err.message; }
  btn.disabled = false;
});
$('signOut').addEventListener('click', async () => { await api('logout', {}).catch(() => {}); location.href = '/realtor'; });

/* ---------- branding ---------- */
const BF = ['agent_name', 'title', 'brokerage', 'license_no', 'phone', 'email', 'website', 'office_address', 'tagline', 'disclaimer'];
let IMG = {logo: null, photo: null};
function fillBrand(b) {
  BF.forEach(k => { $('b_' + k).value = b[k] || ''; });
  $('b_color_primary').value = color(b.color_primary, DEF.primary); $('b_color_accent').value = color(b.color_accent, DEF.accent);
  IMG = {logo: b.logo || null, photo: b.photo || null};
  imgPreview(); brandPreview();
}
function brandNow() {
  const b = {}; BF.forEach(k => { b[k] = $('b_' + k).value.trim(); });
  b.color_primary = $('b_color_primary').value; b.color_accent = $('b_color_accent').value; b.logo = IMG.logo; b.photo = IMG.photo;
  return b;
}
function imgPreview() {
  ['logo', 'photo'].forEach(k => {
    const el = $('prev_' + k);
    el.innerHTML = IMG[k] ? `<img src="${esc(IMG[k])}" alt="">` : `<span>${k === 'logo' ? 'No logo yet' : 'No photo yet'}</span>`;
    $('rm_' + k).hidden = !IMG[k];
  });
}
// Shrinks an upload in the browser and re-encodes it as PNG (logos, keeps transparency) or JPEG (photos), the two
// formats the PDF maker can draw. SVG and other formats are drawn onto a canvas first, so only pixels are saved.
function readImage(file, kind) {
  return new Promise((res, rej) => {
    if (!/^image\//.test(file.type)) return rej(new Error('Choose an image file (PNG, JPEG, WebP or SVG).'));
    const url = URL.createObjectURL(file), im = new Image();
    im.onload = () => {
      const max = kind === 'logo' ? 720 : 360, s = Math.min(1, max / Math.max(im.naturalWidth || max, im.naturalHeight || max));
      let w = Math.max(1, Math.round((im.naturalWidth || max) * s)), h = Math.max(1, Math.round((im.naturalHeight || max) * s));
      const cv = document.createElement('canvas'), cx = cv.getContext('2d');
      if (kind === 'photo') { const side = Math.min(w, h); cv.width = cv.height = side; cx.drawImage(im, (im.naturalWidth - side / s) / 2, (im.naturalHeight - side / s) / 2, side / s, side / s, 0, 0, side, side); }
      else { cv.width = w; cv.height = h; cx.drawImage(im, 0, 0, w, h); }
      URL.revokeObjectURL(url);
      let out = kind === 'logo' ? cv.toDataURL('image/png') : cv.toDataURL('image/jpeg', 0.86);
      if (kind === 'logo' && out.length > 380000) out = cv.toDataURL('image/jpeg', 0.9);
      if (out.length > (kind === 'logo' ? 400000 : 300000)) return rej(new Error('That image is too detailed. Try a smaller file.'));
      res(out);
    };
    im.onerror = () => { URL.revokeObjectURL(url); rej(new Error('That image couldn’t be read.')); };
    im.src = url;
  });
}
// The PDF cover photo: cropped in the browser to the two frames the covers use and kept only in memory, never sent.
let COVER = null;
function cropTo(im, aspect, w) {
  const W = im.naturalWidth, H = im.naturalHeight, cv = document.createElement('canvas'); let sx = 0, sy = 0, sw = W, sh = H;
  if (W / H > aspect) { sw = H * aspect; sx = (W - sw) / 2; } else { sh = W / aspect; sy = (H - sh) / 2; }
  cv.width = Math.min(w, Math.round(sw)); cv.height = Math.round(cv.width / aspect); cv.getContext('2d').drawImage(im, sx, sy, sw, sh, 0, 0, cv.width, cv.height);
  return cv.toDataURL('image/jpeg', 0.85);
}
$('coverPhoto').addEventListener('change', e => {
  const f = e.target.files && e.target.files[0], note = $('coverNote');
  if (!f) { COVER = null; return; }
  const url = URL.createObjectURL(f), im = new Image();
  im.onload = () => { COVER = {full: cropTo(im, 612 / 330, 1600), band: cropTo(im, 532 / 220, 1600)}; URL.revokeObjectURL(url); note.textContent = 'Photo added to the PDF cover. It stays in this browser.'; };
  im.onerror = () => { COVER = null; URL.revokeObjectURL(url); note.textContent = 'That photo couldn’t be read. Try a JPEG or PNG.'; };
  im.src = url;
});
['logo', 'photo'].forEach(k => {
  $('f_' + k).addEventListener('change', async e => {
    const f = e.target.files[0]; if (!f) return;
    try { IMG[k] = await readImage(f, k); imgPreview(); brandPreview(); } catch (err) { $('brandMsg').className = 'rc-msg err'; $('brandMsg').textContent = err.message; }
    e.target.value = '';
  });
  $('rm_' + k).addEventListener('click', () => { IMG[k] = null; imgPreview(); brandPreview(); });
});
$('brandForm').addEventListener('input', brandPreview);
$('brandForm').addEventListener('submit', async e => {
  e.preventDefault();
  const msg = $('brandMsg'), btn = $('brandBtn');
  btn.disabled = true; msg.className = 'rc-msg'; msg.textContent = 'Saving…';
  try { ME = await api('brand', brandNow()); fillBrand(ME.brand || {}); msg.className = 'rc-msg ok'; msg.textContent = 'Saved. Your next report uses this look.'; if (REPORT) renderReport(); }
  catch (err) { msg.className = 'rc-msg err'; msg.textContent = err.message; }
  btn.disabled = false;
});
$('resetColors').addEventListener('click', () => { $('b_color_primary').value = DEF.primary; $('b_color_accent').value = DEF.accent; brandPreview(); });

// The branded header used on screen (brand preview and report) and copied into the PDF.
function brandHead(b) {
  const p = color(b.color_primary, DEF.primary), fg = onColor(p);
  const lines = [b.title, b.phone, b.email, b.website ? b.website.replace(/^https?:\/\//, '') : '', b.license_no ? 'License ' + b.license_no : ''].filter(Boolean);
  return `<div class="rc-band" style="--b1:${p};--b1fg:${fg};--b2:${color(b.color_accent, DEF.accent)}">
    <div class="rc-band-logo">${b.logo ? `<img src="${esc(b.logo)}" alt="${esc(b.brokerage || 'Logo')}">` : `<b>${esc(b.brokerage || 'Your brokerage')}</b>`}</div>
    <div class="rc-band-who"><b>${esc(b.agent_name || 'Your name')}</b>${b.brokerage && b.logo ? `<span>${esc(b.brokerage)}</span>` : ''}${lines.map(l => `<span>${esc(l)}</span>`).join('')}</div>
    ${b.photo ? `<img class="rc-band-photo" src="${esc(b.photo)}" alt="">` : ''}
  </div>`;
}
function brandPreview() { const b = brandNow(); $('brandPrev').style.setProperty('--b2', color(b.color_accent, DEF.accent)); $('brandPrev').innerHTML = brandHead(b) + `<div class="rc-prev-body"><span class="rc-eyebrow">Property report</span><b>825 Ohio Ave</b><small>Lynn Haven, FL 32444</small>${$('b_tagline').value ? `<em>${esc($('b_tagline').value)}</em>` : ''}</div>`; }

/* ---------- address search (Bay County's address points; CORS is open) ---------- */
const inp = $('q'), list = $('acList');
let timer, items = [], active = -1, seq = 0;
const SKIP = new Set(['ST', 'STREET', 'AVE', 'AVENUE', 'RD', 'ROAD', 'DR', 'DRIVE', 'BLVD', 'LN', 'LANE', 'CT', 'CIR', 'PL', 'WAY', 'FL', 'FLORIDA', 'PANAMA', 'CITY', 'BEACH', 'LYNN', 'HAVEN', 'CALLAWAY', 'SPRINGFIELD', 'PARKER', 'MEXICO', 'SOUTHPORT', 'YOUNGSTOWN', 'FOUNTAIN']);
inp.addEventListener('input', () => { PICK = null; clearTimeout(timer); timer = setTimeout(suggest, 220); });
async function suggest() {
  const s = inp.value.toUpperCase().replace(/[^A-Z0-9 ]/g, ' ').replace(/\b\d{5}\s*$/, ' ').replace(/\s+/g, ' ').trim();
  const m = /^(\d+)\s+(.+)$/.exec(s);
  if (!m) { list.hidden = true; return; }
  const words = m[2].replace(/\bHWY\b/g, 'HIGHWAY').split(' ').filter(w => w.length > 1 && !SKIP.has(w)).slice(0, 3);
  if (!words.length) { list.hidden = true; return; }
  const where = [`ADDRESS LIKE '${m[1]} %'`, ...words.map(w => `ADDRESS LIKE '% ${w.replace(/'/g, "''")}%'`)].join(' AND ');
  const my = ++seq;
  try {
    const r = await fetch(GIS + '?' + new URLSearchParams({where, outFields: 'ADDRESS,UNIT,CMNTY,ZIP,RENUM', returnGeometry: 'true', outSR: 4326, resultRecordCount: 10, orderByFields: 'ADDRESS', f: 'json'}));
    const j = await r.json(); if (my !== seq) return;
    items = (j.features || []).filter(f => f.geometry).map(f => ({address: title(f.attributes.ADDRESS) + (f.attributes.UNIT && f.attributes.UNIT.trim() ? ' #' + f.attributes.UNIT.trim() : ''),
      city: title(f.attributes.CMNTY), zip: f.attributes.ZIP ? String(f.attributes.ZIP) : '', parcel_id: f.attributes.RENUM || '', lat: f.geometry.y, lon: f.geometry.x}));
    active = -1;
    list.innerHTML = items.length ? items.map((x, i) => `<li role="option" id="ac${i}" data-i="${i}">${esc(x.address)}<span>${esc(x.city)} ${esc(x.zip)}</span></li>`).join('')
      : '<li class="ac-empty">No matching address. Try the house number and street name, like "825 Ohio".</li>';
    list.hidden = false;
  } catch (e) { if (my === seq) { list.innerHTML = '<li class="ac-empty">Bay County’s map server didn’t answer. Try again in a moment.</li>'; list.hidden = false; } }
}
function pick(x) { PICK = x; inp.value = x.address; list.hidden = true; }
inp.addEventListener('keydown', e => {
  if (list.hidden || !items.length) return;
  if (e.key === 'ArrowDown') { e.preventDefault(); active = Math.min(items.length - 1, active + 1); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); active = Math.max(0, active - 1); }
  else if (e.key === 'Enter') { e.preventDefault(); pick(items[Math.max(0, active)]); return; }
  else if (e.key === 'Escape') { list.hidden = true; return; }
  list.querySelectorAll('li[role=option]').forEach((li, i) => li.setAttribute('aria-selected', i === active));
});
list.addEventListener('mousedown', e => { const li = e.target.closest('li[data-i]'); if (li) { e.preventDefault(); pick(items[+li.dataset.i]); } });
document.addEventListener('click', e => { if (!e.target.closest('.rc-ac')) list.hidden = true; });

/* ---------- run a report ---------- */
$('runForm').addEventListener('submit', e => { e.preventDefault(); run(); });
async function run() {
  const err = $('runErr'); err.hidden = true;
  if (!PICK && items.length && !list.hidden) pick(items[0]);
  const qs = PICK ? new URLSearchParams({lat: PICK.lat, lon: PICK.lon, label: PICK.address, parcel: PICK.parcel_id || ''}) : new URLSearchParams({address: inp.value});
  if (!PICK && !inp.value.trim()) { err.textContent = 'Type an address first.'; err.hidden = false; return; }
  $('runBtn').disabled = true; $('mailForm').hidden = true; $('mailBtn').setAttribute('aria-expanded', 'false'); $('report').innerHTML = '<div class="rc-loading"><span class="rc-spin" aria-hidden="true"></span>Gathering records for this address…</div>'; $('reportActs').hidden = true;
  try {
    const r = await fetch('/api/v1/address-report?' + qs);
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || 'The report couldn’t be made right now.');
    REPORT = j.data;
    if (PICK) { REPORT.address = PICK.address; REPORT.zip = REPORT.zip || PICK.zip; REPORT.parcel_id = PICK.parcel_id || REPORT.parcel_id; }
    REPORT.prepared_for = $('prepFor').value.trim();
    renderReport();
    const u = new URL(location.href); u.search = new URLSearchParams({lat: REPORT.lat, lon: REPORT.lon, a: REPORT.address || '', c: REPORT.city || '', z: REPORT.zip || '', p: REPORT.parcel_id || ''}); history.replaceState(null, '', u);
    api('report', {address: REPORT.address, city: REPORT.city, zip: REPORT.zip, parcel_id: REPORT.parcel_id, lat: REPORT.lat, lon: REPORT.lon, prepared_for: REPORT.prepared_for})
      .then(x => { if (x && x.id && REPORT) REPORT.saved_id = x.id; return api('me'); }).then(m => { ME = m; renderHistory(); }).catch(() => {});
  } catch (e2) { $('report').innerHTML = ''; err.textContent = e2.message; err.hidden = false; }
  $('runBtn').disabled = false;
}

/* ---------- report model: one shape for the screen and the PDF ----------
   A section becomes {title, kv: [[label, value, {html, bold}]], table: {cols, rows, align}, lists: [{h, items: [{t, html, sub}]}], note, sources}. */
const S = id => (REPORT.sections || []).find(s => s.id === id && (s.status === 'ok' || s.status === 'partial') && s.data);
function sectionModel(s) {
  const d = s.data, m = {id: s.id, title: s.title, kv: [], lists: [], note: s.note, sources: s.sources || []};
  const kv = (k, v, o = {}) => { if (v != null && v !== '' && v !== false) m.kv.push([k, String(v), o]); };
  switch (s.id) {
    case 'property': {
      kv('Parcel', d.parcel_id); kv('Use', d.use);
      kv('Year built', d.year_built ? d.year_built + (d.effective_year && d.effective_year !== d.year_built ? ` (effective ${d.effective_year})` : '') : null);
      kv('Heated area', d.heated_sqft ? d.heated_sqft.toLocaleString('en-US') + ' sq ft' + (d.total_sqft && d.total_sqft !== d.heated_sqft ? ` (${d.total_sqft.toLocaleString('en-US')} total)` : '') : null);
      kv('Bedrooms / baths', d.bedrooms || d.bathrooms ? `${d.bedrooms || '—'} / ${d.bathrooms || '—'}` : null);
      kv('Stories', d.stories); kv('Lot', d.acres ? d.acres.toLocaleString('en-US', {maximumFractionDigits: 2}) + ' acres' : null);
      kv('Subdivision', d.subdivision ? d.subdivision + (d.block ? `, block ${d.block}` : '') + (d.lot ? `, lot ${d.lot}` : '') : null);
      kv('Market value', usd(d.market_value), {bold: true}); kv('Assessed value', usd(d.assessed_value));
      kv('Land / building', d.land_value != null ? `${usd(d.land_value)} / ${usd(d.building_value)}` : null);
      kv('Homestead', d.homestead ? 'Yes, on the 2026 roll' : 'No');
      if (d.sales && d.sales.length) m.lists.push({h: 'Recent sales', items: d.sales.map(x => ({t: usd(x.price), sub: [month(x.date), x.qualified ? 'qualified sale' : 'not a qualified sale', x.vacant ? 'vacant land' : ''].filter(Boolean).join(' · ')}))});
      break;
    }
    case 'tax': {
      kv('Estimated yearly bill', usd(d.estimated_bill), {bold: true}); kv('Property tax', usd(d.property_tax)); kv('Flat fees', d.fees_total ? usd(d.fees_total) : 'None on the FY2026 bill');
      kv('Taxing district', `${d.district_label} · ${(+d.total_millage).toFixed(4)} mills${d.district_from_parcel ? '' : ' (from the map)'}`);
      kv('Taxable value', d.taxable_school !== d.taxable_other ? `${usd(d.taxable_other)} (${usd(d.taxable_school)} for school taxes)` : usd(d.taxable_other));
      kv('Homestead on the roll', d.homestead ? 'Yes. The buyer\'s bill resets without it.' : 'No');
      m.table = {cols: ['Who levies it', 'Mills', 'Amount'], align: ['left', 'right', 'right'],
        rows: [...d.lines.map(l => [l.authority, l.millage.toFixed(4), usd2(l.amount)]), ...d.fees.map(f => [f.fee, 'flat fee', usd2(f.amount)])]};
      m.note = d.note; break;
    }
    case 'hazards': {
      kv('Flood zone', d.flood_zone ? `Zone ${d.flood_zone}` : 'Not mapped', {bold: true}); kv('Flood risk', d.flood_risk);
      kv('Base flood elevation', d.base_flood_elevation_ft ? `${d.base_flood_elevation_ft} ft${d.vertical_datum ? ' (' + d.vertical_datum + ')' : ''}` : null);
      kv('FIRM panel', d.firm_panel ? d.firm_panel + (d.firm_effective ? `, effective ${day(d.firm_effective)}` : '') : null);
      kv('Map revision (LOMR)', d.map_revision ? `${d.map_revision.case}${d.map_revision.effective ? ', ' + day(d.map_revision.effective) : ''}` : null);
      kv('Evacuation zone', d.evacuation_zone ? `Zone ${d.evacuation_zone}` : 'Not in a mapped zone', {bold: !!d.evacuation_zone});
      kv('Storm surge', d.storm_surge);
      kv('Redevelopment district', d.cra_district ? `${d.cra_district}${d.cra_since ? ` (since ${d.cra_since})` : ''}` : 'Not in a CRA district');
      break;
    }
    case 'schools': (d.schools || []).forEach(x => kv(x.level, x.school + (x.state_grade ? ` · state grade ${x.state_grade}${x.state_grade_year ? ' (' + x.state_grade_year + ')' : ''}` : ''), {html: x.page_url ? `<a href="${esc(x.page_url)}">${esc(x.school)}</a>${x.state_grade ? ` <span class="muted">· state grade ${esc(x.state_grade)}</span>` : ''}` : null})); break;
    case 'utilities': {
      (d.services || []).forEach(x => kv(x.service_label || x.service, (x.providers || []).map(p => p.provider).join(', ') || 'Not listed'));
      if ((d.pickup || []).length) m.lists.push({h: 'Pickup days', items: d.pickup.map(p => ({t: `${p.service_label || p.service}: ${Array.isArray(p.days) ? p.days.join(', ') : p.days || p.rule || 'see the provider'}`, sub: [p.provider, p.zone].filter(Boolean).join(' · ')}))});
      break;
    }
    case 'zoning': {
      kv('Zoning', d.zoning || 'Not mapped'); kv('Future land use', d.future_land_use || 'Not mapped');
      m.lists.push({h: `Development within ${d.projects_radius_miles === 1 ? 'a mile' : 'half a mile'}`, empty: 'None on file nearby.',
        items: (d.projects || []).map(p => ({t: p.name || 'Project', sub: [p.description, p.status, p.date ? month(p.date) : '', mi(p.miles)].filter(Boolean).join(' · ')}))});
      break;
    }
    case 'roads': m.lists.push({h: 'Within a mile', empty: 'None on file nearby.', items: (d.projects || []).map(p => ({t: p.name,
      sub: [p.kind, p.status ? p.status[0].toUpperCase() + p.status.slice(1) + (p.pct_complete != null && p.status === 'in progress' ? ` (${p.pct_complete}%)` : '') : '', p.cost ? usd(p.cost) : '', p.completion ? 'done ' + month(p.completion) : '', mi(p.miles)].filter(Boolean).join(' · ')}))}); break;
    case 'outdoors': {
      m.lists.push({h: 'Parks', empty: 'None within five miles.', items: (d.parks || []).map(p => ({t: p.name, sub: [p.kind, p.acres ? p.acres + ' acres' : '', mi(p.miles)].filter(Boolean).join(' · ')}))});
      if (d.beaches) m.lists.push({h: 'Beach accesses', empty: 'None nearby.', items: d.beaches.map(b => ({t: b.name, sub: [b.address, b.parking ? 'parking' : '', b.restroom ? 'restrooms' : '', mi(b.miles)].filter(Boolean).join(' · ')}))});
      if (s.status === 'partial') m.note = null;
      break;
    }
    case 'services': (d.services || []).forEach(x => kv(x.kind, `${x.name} · ${mi(x.miles)}`)); kv('Mosquito control', d.mosquito_district); break;
    case 'officials': {
      kv('Local government', d.local_government, {bold: true});
      (d.seats || []).forEach(x => kv(x.office, x.name + (x.district ? ` (${x.district})` : ''), {html: nameLink(x.entity_id, x.name, x.page_url) + (x.district ? ` <span class="muted">${esc(x.district)}</span>` : '')}));
      if ((d.city_council || []).length) m.lists.push({h: d.local_government.replace(/^City of /, '') + ' commission and manager', cols: 2,
        items: d.city_council.map(x => ({t: x.name, html: nameLink(x.entity_id, x.name, x.page_url), sub: x.seat}))});
      break;
    }
    default: Object.entries(d).forEach(([k, v]) => { if (v == null || typeof v === 'object') return; kv(k.replace(/_/g, ' '), v); });
  }
  if (!m.kv.length && !m.table && !m.lists.some(l => l.items.length || l.empty)) return null;
  return m;
}
function tiles() {
  const tax = S('tax'), hz = S('hazards'), sch = S('schools'), pr = S('property');
  return [
    tax ? ['Estimated yearly tax', usd(tax.data.estimated_bill), 'tax + flat fees'] : null,
    hz ? ['Flood zone', hz.data.flood_zone ? hz.data.flood_zone : 'Not mapped', hz.data.high_risk ? 'high-risk area' : 'FEMA map'] : null,
    hz ? ['Evacuation zone', hz.data.evacuation_zone || 'None', 'county map'] : null,
    pr && pr.data.year_built ? ['Built', String(pr.data.year_built), pr.data.heated_sqft ? pr.data.heated_sqft.toLocaleString('en-US') + ' sq ft' : ''] : sch ? ['Schools', String(sch.data.schools.length), 'zoned'] : null,
  ].filter(Boolean);
}

/* ---------- on screen ---------- */
function renderReport() {
  const b = (ME && ME.brand) || {}, r = REPORT;
  const models = r.sections.map(s => (s.status === 'ok' || s.status === 'partial') && s.data ? sectionModel(s) : null).filter(Boolean);
  const pending = r.sections.filter(s => s.status === 'pending').map(s => s.title), failed = r.sections.filter(s => s.status === 'error').map(s => s.title);
  const sub = [r.jurisdiction, r.zip ? 'FL ' + r.zip : '', r.parcel_id ? 'Parcel ' + r.parcel_id : ''].filter(Boolean).join(' · ');
  const kvH = m => m.kv.length ? `<dl class="rc-kv">${m.kv.map(([k, v, o]) => `<dt>${esc(k)}</dt><dd${o.bold ? ' class="b"' : ''}>${o.html || esc(v)}</dd>`).join('')}</dl>` : '';
  const tbH = m => m.table ? `<div class="rc-tw"><table class="rc-tb" data-tt="off"><thead><tr>${m.table.cols.map((c, i) => `<th class="${m.table.align[i]}">${esc(c)}</th>`).join('')}</tr></thead><tbody>${m.table.rows.map(row => `<tr>${row.map((c, i) => `<td class="${m.table.align[i]}">${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : '';
  const lsH = m => m.lists.map(l => `<h4>${esc(l.h)}</h4>${l.items.length ? `<ul class="rc-list${l.cols === 2 ? ' two' : ''}">${l.items.map(i => `<li><b>${i.html || esc(i.t)}</b>${i.sub ? `<small>${esc(i.sub)}</small>` : ''}</li>`).join('')}</ul>` : `<p class="muted small">${esc(l.empty || 'None on file.')}</p>`}`).join('');
  const srcH = m => m.sources.length ? `<p class="rc-src">${m.sources.map(x => `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.label)} ↗</a>`).join(' ')}</p>` : '';
  $('report').innerHTML = `<article class="rc-sheet" style="--b1:${color(b.color_primary, DEF.primary)};--b2:${color(b.color_accent, DEF.accent)}">
    ${brandHead(b)}
    <header class="rc-title"><span class="rc-eyebrow">Property report</span><h2>${esc(r.address || 'This address')}</h2><p>${esc(sub)}</p>
      <p class="rc-meta">${r.prepared_for ? `Prepared for <b>${esc(r.prepared_for)}</b> · ` : ''}${esc(day(r.generated_at))}${b.agent_name ? ` · by ${esc(b.agent_name)}` : ''}</p>
      ${r.other_matches ? `<p class="rc-meta">Other matches: ${r.other_matches.map(esc).join('; ')}</p>` : ''}</header>
    <div class="rc-tiles">${tiles().map(([k, v, s]) => `<div><span>${esc(k)}</span><b>${esc(v)}</b><small>${esc(s)}</small></div>`).join('')}</div>
    <div class="rc-secs">${models.map(m => `<section class="rc-sec${m.table || m.id === 'officials' ? ' wide' : ''}" id="s-${esc(m.id)}"><h3>${esc(m.title)}</h3>${kvH(m)}${tbH(m)}${lsH(m)}${m.note ? `<p class="rc-note">${esc(m.note)}</p>` : ''}${srcH(m)}</section>`).join('')}</div>
    ${pending.length ? `<p class="rc-soon"><b>Coming soon to reports:</b> ${pending.map(esc).join(', ')}.</p>` : ''}
    ${failed.length ? `<p class="rc-soon err"><b>Couldn’t load right now:</b> ${failed.map(esc).join(', ')}. Run the report again in a minute.</p>` : ''}
    <footer class="rc-disc">${b.disclaimer ? `<p>${esc(b.disclaimer)}</p>` : ''}<p>${esc(DISCLAIMER)}</p></footer>
  </article>`;
  $('reportActs').hidden = false;
}
const DISCLAIMER = 'Compiled from public records by BayCounty.me on the date shown. It is not a survey, title search, appraisal, inspection or flood determination. Tax figures are estimates; the Tax Collector’s bill is the amount owed. School zones, utilities and districts can change: confirm anything a decision depends on with the agency named in each section. Owner names and other private details are never included.';

/* ---------- history ---------- */
function renderHistory() {
  const el = $('histList'), rs = (ME && ME.reports) || [];
  $('histCount').textContent = ME && ME.agent ? `${ME.agent.reports_run || 0} report${ME.agent.reports_run === 1 ? '' : 's'} run` : '';
  el.innerHTML = rs.length ? rs.map(r => `<li><div><b>${esc(r.address)}</b><small>${esc([r.city, r.zip, r.prepared_for ? 'for ' + r.prepared_for : '', day(r.created_at)].filter(Boolean).join(' · '))}</small></div>
    <span class="rc-hacts">${r.lat != null ? `<button type="button" class="rc-btn ghost" data-run="${r.id}">Run again</button>` : ''}<button type="button" class="rc-btn ghost" data-del="${r.id}" aria-label="Remove ${esc(r.address)} from history">Remove</button></span></li>`).join('')
    : '<li class="muted">Reports you run show up here.</li>';
}
$('histList').addEventListener('click', async e => {
  const run1 = e.target.closest('[data-run]'), del = e.target.closest('[data-del]');
  if (run1) { const r = ME.reports.find(x => String(x.id) === run1.dataset.run); PICK = {address: r.address, city: r.city, zip: r.zip, parcel_id: r.parcel_id, lat: r.lat, lon: r.lon}; inp.value = r.address; $('prepFor').value = r.prepared_for || ''; tab('run'); run(); }
  if (del) { await api('delete_report', {id: +del.dataset.del}).catch(() => {}); ME = await api('me'); renderHistory(); }
});
$('delAcct').addEventListener('click', async () => {
  const b = $('delAcct');
  if (b.dataset.sure !== '1') { b.dataset.sure = '1'; b.textContent = 'Press again to delete everything'; return; }
  await api('delete_account', {}).catch(() => {}); location.href = '/realtor';
});

/* ---------- branded PDF (pdfmake) ----------
   Letter, 40pt margins. Tables fit the page width with short cells on one line; only long text wraps. Each section is
   one unbreakable block, so a heading never sits alone at the bottom of a page. */
function load(src) { return new Promise((res, rej) => { const s = document.createElement('script'); s.src = src; s.onload = res; s.onerror = () => rej(new Error('load ' + src)); document.head.appendChild(s); }); }
async function pdfReady() { if (!window.pdfMake) await load(PDFMAKE); if (!window.pdfMake.vfs || !Object.keys(window.pdfMake.vfs).length) await load(VFS); }
const DEFAULT_COVER = 'type';
const RB = t => String(t ?? '').replace(/→/g, 'to').replace(/[←-⇿☀-➿]/g, '');
function buildDoc(opts = {}) {
  // Clean brochure layout: brand band, the address, six at-a-glance numbers, then numbered sections whose facts sit
  // in a two- or three-column grid. No links anywhere in the PDF: sources are named in plain text.
  const b = (ME && ME.brand) || {}, r = REPORT, P = color(b.color_primary, DEF.primary), A = color(b.color_accent, DEF.accent), FG = onColor(P);
  if (!(b.agent_name || b.brokerage || b.logo)) opts = {...opts, noDate: true};
  const ink = '#161B24', muted = '#5A6372', faint = '#8A93A1', line = '#E3E7EE', sunken = '#F4F6F9', W = 532;
  const none = {hLineWidth: () => 0, vLineWidth: () => 0, paddingLeft: () => 0, paddingRight: () => 0, paddingTop: () => 0, paddingBottom: () => 0};
  const cap = (t, o = {}) => ({text: String(t).toUpperCase(), fontSize: 6.5, bold: true, color: faint, characterSpacing: 0.7, ...o});
  const contact = [b.phone, b.email, b.website ? b.website.replace(/^https?:\/\//, '').replace(/\/$/, '') : ''].filter(Boolean);

  // Brand band: logo (on a white tile so it reads on any color) or brokerage name, then the agent.
  const who = [{text: b.agent_name || '', bold: true, fontSize: 11.5, color: FG}, b.title ? {text: b.title, fontSize: 8, color: FG, opacity: 0.9} : null,
    contact.length ? {text: contact.join('   '), fontSize: 8, color: FG, margin: [0, 3, 0, 0]} : null,
    b.license_no ? {text: 'License ' + b.license_no, fontSize: 7, color: FG, opacity: 0.8, margin: [0, 1, 0, 0]} : null].filter(Boolean);
  const cells = [b.logo ? {table: {body: [[{image: b.logo, fit: [140, 40]}]]}, layout: {...none, fillColor: () => '#FFFFFF', paddingLeft: () => 7, paddingRight: () => 7, paddingTop: () => 5, paddingBottom: () => 5}}
    : {text: b.brokerage || 'Property report', color: FG, bold: true, fontSize: 15, margin: [0, 8, 0, 0]}, {stack: who, alignment: 'right', margin: [0, 2, 0, 0]}];
  const widths = [b.logo ? 'auto' : '*', '*'];
  if (b.photo) { cells.push({image: b.photo, width: 50, height: 50}); widths.push(50); }
  const band = {table: {widths, body: [cells]}, layout: {...none, fillColor: () => P, paddingLeft: i => (i === 0 ? 16 : 10), paddingRight: i => (i === cells.length - 1 ? 16 : 0), paddingTop: () => 14, paddingBottom: () => 14}};

  const sub = [r.jurisdiction, r.zip ? 'FL ' + r.zip : '', r.parcel_id ? 'Parcel ' + r.parcel_id : ''].filter(Boolean).join('   ·   ');
  const title = {margin: [0, 22, 0, 0], stack: [
    {text: 'PROPERTY REPORT', fontSize: 7.5, bold: true, color: A, characterSpacing: 1.4},
    {text: RB(r.address || ''), fontSize: 26, bold: true, color: ink, margin: [0, 4, 0, 3]},
    {text: sub, fontSize: 9, color: muted},
    {columns: [r.prepared_for ? {width: 'auto', stack: [cap('Prepared for'), {text: RB(r.prepared_for), fontSize: 9.5, bold: true, color: ink, margin: [0, 2, 0, 0]}]} : null,
      opts.noDate ? null : {width: 'auto', stack: [cap('Date'), {text: day(r.generated_at), fontSize: 9.5, bold: true, color: ink, margin: [0, 2, 0, 0]}]},
      b.agent_name ? {width: 'auto', stack: [cap('Prepared by'), {text: RB(b.agent_name + (b.brokerage ? ', ' + b.brokerage : '')), fontSize: 9.5, bold: true, color: ink, margin: [0, 2, 0, 0]}]} : null].filter(Boolean),
     columnGap: 28, margin: [0, 12, 0, 0]},
    b.tagline ? {text: RB(b.tagline), fontSize: 9.5, italics: true, color: P, margin: [0, 12, 0, 0]} : null].filter(Boolean)};

  // At a glance: up to six numbers, three to a row.
  const tax = S('tax'), hz = S('hazards'), pr = S('property'), sch = S('schools');
  const G = [tax ? ['Estimated yearly tax', usd(tax.data.estimated_bill), 'property tax + flat fees'] : null,
    pr && pr.data.market_value ? ['Market value', usd(pr.data.market_value), '2026 Property Appraiser roll'] : null,
    hz ? ['Flood zone', hz.data.flood_zone || 'Not mapped', hz.data.high_risk ? 'high-risk flood area' : 'FEMA flood map'] : null,
    hz ? ['Evacuation zone', hz.data.evacuation_zone || 'None', 'county evacuation map'] : null,
    pr && pr.data.year_built ? ['Year built', String(pr.data.year_built), pr.data.effective_year && pr.data.effective_year !== pr.data.year_built ? 'effective ' + pr.data.effective_year : 'Property Appraiser'] : null,
    pr && pr.data.heated_sqft ? ['Heated area', pr.data.heated_sqft.toLocaleString('en-US') + ' sq ft', pr.data.acres ? pr.data.acres.toLocaleString('en-US', {maximumFractionDigits: 2}) + '-acre lot' : ''] :
      sch && sch.data.schools ? ['Zoned schools', String(sch.data.schools.length), 'elementary to high'] : null].filter(Boolean);
  const glance = (cols = 3, big = 17) => { const rows = []; for (let i = 0; i < G.length; i += cols) rows.push(Array.from({length: cols}, (_, j) => G[i + j]
      ? {stack: [cap(G[i + j][0], {color: muted}), {text: RB(G[i + j][1]), fontSize: big, bold: true, color: ink, margin: [0, 4, 0, 2]}, {text: G[i + j][2], fontSize: 7.5, color: muted}]} : {text: ''}));
    return rows.length ? {table: {widths: Array(cols).fill('*'), body: rows},
      layout: {fillColor: () => sunken, hLineWidth: (i, n) => (i === 0 ? 2.5 : i < n.table.body.length ? 6 : 0), hLineColor: i => (i === 0 ? A : '#FFFFFF'),
        vLineWidth: i => (i > 0 && i < cols ? 6 : 0), vLineColor: () => '#FFFFFF', paddingLeft: () => 12, paddingRight: () => 10, paddingTop: () => 11, paddingBottom: () => 11}} : null; };

  // Cover. Agents with branding get their band; everyone else gets a clean default led by the place name.
  // opts.photo / opts.bandPhoto: the agent's listing photo for this report, already cropped to its frame (pdfmake can't
  // crop). With a photo the cover is 'photo'; without one it is 'type'.
  const branded = !!(b.agent_name || b.brokerage || b.logo);
  const city = /^City of /.test(r.jurisdiction || '') ? r.jurisdiction.replace(/^City of /, '') : 'Bay County';
  const cityLine = city === 'Bay County' ? 'Florida' : 'Bay County, Florida';
  const addr = (top = 22, size = 26, fg = null) => ({margin: [0, top, 0, 0], stack: title.stack.slice(1).map((x, i) => (i === 0 ? {...x, fontSize: size, margin: [0, 0, 0, 3]} : x)).map(x => (fg && x.text != null && !x.columns ? {...x, color: fg} : x))});
  const kicker = (t, c = A) => ({text: t.toUpperCase(), fontSize: 7.5, bold: true, color: c, characterSpacing: 1.4});
  const bleed = (node, y, h) => ({...node, absolutePosition: {x: 0, y}, width: 612, height: h});
  const spacer = h => ({text: '', margin: [0, h, 0, 0]});
  const style = branded ? 'branded' : opts.photo ? 'photo' : (opts.style || DEFAULT_COVER);
  let cover;
  if (style === 'branded') {
    cover = [band, {canvas: [{type: 'rect', x: 0, y: 0, w: W, h: 3, color: A}]}, opts.bandPhoto || opts.photo ? {image: opts.bandPhoto || opts.photo, width: W, height: 220, margin: [0, 14, 0, 0]} : null, title, glance() && {...glance(), margin: [0, 18, 0, 0]}];
  } else if (style === 'photo') { // the agent's listing photo, edge to edge, then the address on white
    const H = 330;
    cover = [opts.photo ? bleed({image: opts.photo}, 0, H) : {canvas: [{type: 'rect', x: 0, y: 0, w: 612, h: H, color: sunken}], absolutePosition: {x: 0, y: 0}},
      {canvas: [{type: 'rect', x: 0, y: 0, w: 612, h: 4, color: A}], absolutePosition: {x: 0, y: H}},
      spacer(H - 44 + 14), {columns: [kicker(city + ', Florida'), {text: 'PROPERTY REPORT   ·   ' + day(r.generated_at).toUpperCase(), fontSize: 7.5, bold: true, color: faint, characterSpacing: 1.2, alignment: 'right'}]},
      addr(8, 28), {...glance(), margin: [0, 18, 0, 0]}];
  } else { // type: no photo, a solid color block carrying the address and the key numbers
    const H = 470, inv = [];
    for (let i = 0; i < G.length; i += 3) inv.push([0, 1, 2].map(j => G[i + j] ? {stack: [{text: G[i + j][0].toUpperCase(), fontSize: 6.5, bold: true, color: FG, opacity: 0.7, characterSpacing: 0.7},
      {text: RB(G[i + j][1]), fontSize: 17, bold: true, color: FG, margin: [0, 3, 0, 1]}, {text: G[i + j][2], fontSize: 7.5, color: FG, opacity: 0.7}]} : {text: ''}));
    cover = [{canvas: [{type: 'rect', x: 0, y: 0, w: 612, h: H, color: P}, {type: 'rect', x: 40, y: H - 4, w: 64, h: 4, color: A}], absolutePosition: {x: 0, y: 0}},
      {columns: [{text: city.toUpperCase(), fontSize: 9, bold: true, color: FG, characterSpacing: 2.2}, {text: 'PROPERTY REPORT   ·   ' + day(r.generated_at).toUpperCase(), fontSize: 7.5, bold: true, color: FG, opacity: 0.75, characterSpacing: 1.2, alignment: 'right'}], margin: [0, 0, 0, 0]},
      {text: cityLine, fontSize: 8, color: FG, opacity: 0.7, margin: [0, 2, 0, 0]},
      {text: RB(r.address || ''), fontSize: 42, bold: true, color: FG, margin: [0, 92, 0, 6], lineHeight: 1.0},
      {text: [r.jurisdiction, r.zip ? 'FL ' + r.zip : '', r.parcel_id ? 'Parcel ' + r.parcel_id : ''].filter(Boolean).join('   ·   '), fontSize: 9.5, color: FG, opacity: 0.8},
      inv.length ? {margin: [0, 48, 0, 0], table: {widths: ['*', '*', '*'], body: inv}, layout: {...none, hLineWidth: (i, n) => (i > 0 && i < n.table.body.length ? 0.5 : 0), hLineColor: () => FG, paddingTop: () => 10, paddingBottom: () => 10, paddingRight: () => 10}} : null,
      spacer(64)];
  }

  // Sections.
  const models = r.sections.map(s => (s.status === 'ok' || s.status === 'partial') && s.data ? sectionModel(s) : null).filter(Boolean);
  const grid = m => {
    if (!m.kv.length) return null;
    const n = m.kv.every(([, v]) => v.length <= 26) && m.kv.length > 2 ? 3 : 2, rows = [];
    for (let i = 0; i < m.kv.length; i += n) rows.push(Array.from({length: n}, (_, j) => { const c = m.kv[i + j];
      return c ? {stack: [cap(c[0]), {text: RB(c[1]), fontSize: 9.5, bold: !!c[2].bold, color: ink, margin: [0, 2.5, 0, 0]}]} : {text: ''}; }));
    return {table: {widths: Array(n).fill('*'), body: rows}, layout: {...none, hLineWidth: (i, nd) => (i > 0 && i < nd.table.body.length ? 0.5 : 0), hLineColor: () => line, paddingRight: () => 12, paddingTop: () => 7, paddingBottom: () => 7}};
  };
  const dataTable = m => m.table ? {margin: [0, 10, 0, 0], table: {headerRows: 1, widths: ['*', 56, 72], body: [m.table.cols.map((c, i) => cap(c, {alignment: m.table.align[i], color: muted, noWrap: true})),
    ...m.table.rows.map(row => row.map((c, i) => ({text: RB(c), fontSize: 8.5, color: ink, alignment: m.table.align[i], noWrap: i > 0})))]},
    layout: {...none, fillColor: (i) => (i > 0 && i % 2 === 0 ? sunken : null), hLineWidth: i => (i === 1 ? 0.8 : 0), hLineColor: () => muted, paddingLeft: () => 6, paddingRight: () => 6, paddingTop: () => 4, paddingBottom: () => 4}} : null;
  const listBlock = l => {
    const it = l.items.map(i => ({stack: [{text: RB(i.t), fontSize: 9, bold: true, color: ink}, i.sub ? {text: RB(i.sub), fontSize: 7.5, color: muted, margin: [0, 1.5, 0, 0]} : null].filter(Boolean), margin: [0, 0, 10, 7]}));
    const body = !it.length ? [{text: l.empty || 'None on file.', fontSize: 8.5, color: muted}]
      : it.length > 3 || l.cols === 2 ? [{columns: [{stack: it.filter((_, i) => i % 2 === 0)}, {stack: it.filter((_, i) => i % 2 === 1)}], columnGap: 16}] : it;
    return [cap(l.h, {color: P, margin: [0, 12, 0, 6]}), ...body];
  };
  const sections = models.map((m, k) => ({unbreakable: true, margin: [0, 24, 0, 0], stack: [
    {columns: [{width: 26, text: String(k + 1).padStart(2, '0'), fontSize: 10, bold: true, color: A, margin: [0, 2.5, 0, 0]}, {text: m.title, fontSize: 13.5, bold: true, color: P}], margin: [0, 0, 0, 5]},
    {canvas: [{type: 'line', x1: 0, y1: 0, x2: W, y2: 0, lineWidth: 0.75, lineColor: line}], margin: [0, 0, 0, 2]},
    grid(m), dataTable(m), ...m.lists.flatMap(listBlock),
    m.note ? {text: RB(m.note), fontSize: 7.5, color: muted, margin: [0, 9, 0, 0]} : null,
    m.sources.length ? {text: [{text: 'Source: ', bold: true}, m.sources.map(x => x.label).join(', ')], fontSize: 7, color: faint, margin: [0, 4, 0, 0]} : null,
  ].filter(Boolean)}));

  // Closing: the agent card, then the fine print.
  const card = b.agent_name || b.brokerage ? {unbreakable: true, margin: [0, 28, 0, 0], table: {widths: b.photo ? [56, '*'] : ['*'], body: [[
    ...(b.photo ? [{image: b.photo, width: 56, height: 56}] : []),
    {stack: [cap('Questions about this home?', {color: A}), {text: b.agent_name || b.brokerage, fontSize: 12, bold: true, color: ink, margin: [0, 3, 0, 1]},
      {text: [b.title, b.agent_name ? b.brokerage : ''].filter(Boolean).join(', '), fontSize: 8.5, color: muted},
      contact.length ? {text: contact.join('   ·   '), fontSize: 8.5, color: ink, margin: [0, 4, 0, 0]} : null,
      b.office_address ? {text: RB(b.office_address), fontSize: 8, color: muted, margin: [0, 2, 0, 0]} : null].filter(Boolean)}]]},
    layout: {...none, fillColor: () => sunken, vLineWidth: i => (i === 0 ? 3 : 0), vLineColor: () => P, paddingLeft: i => (i === 0 ? 14 : 12), paddingRight: () => 12, paddingTop: () => 12, paddingBottom: () => 12}} : null;
  const disc = {unbreakable: true, margin: [0, 18, 0, 0], stack: [
    b.disclaimer ? {text: RB(b.disclaimer), fontSize: 7.5, color: muted, margin: [0, 0, 0, 6]} : null,
    {text: DISCLAIMER, fontSize: 7, color: faint}].filter(Boolean)};

  // Contents fills the rest of the cover; the sections start on page 2.
  if (sections.length && !branded) { // a branded band leaves no room for it
    const names = models.map((m, k) => ({columns: [{width: 18, text: String(k + 1).padStart(2, '0'), fontSize: 8, bold: true, color: A}, {text: m.title, fontSize: 8.5, color: ink}], margin: [0, 0, 0, 5]}));
    const per = Math.ceil(names.length / 3);
    cover.push({unbreakable: true, margin: [0, 24, 0, 0], stack: [cap('In this report', {color: muted, margin: [0, 0, 0, 8]}), {columns: [0, 1, 2].map(i => ({stack: names.slice(i * per, i * per + per)})), columnGap: 14}]});
    sections[0].pageBreak = 'before';
  }
  const footLine = [b.agent_name, b.brokerage, b.phone].filter(Boolean).join('   ·   ');
  return {
    pageSize: 'LETTER', pageMargins: [40, 44, 40, 48],
    info: {title: `Property report: ${r.address || ''}`, author: b.agent_name || b.brokerage || 'BayCounty.me', subject: 'Address report', creator: 'BayCounty.me realtor console'},
    defaultStyle: {font: 'Roboto', fontSize: 9, color: ink, lineHeight: 1.18},
    header: page => page > 1 ? {margin: [40, 18, 40, 0], stack: [
      {columns: [{text: RB(r.address || ''), fontSize: 7.5, bold: true, color: ink}, {text: b.brokerage || 'Property report', fontSize: 7.5, color: muted, alignment: 'right'}]},
      {canvas: [{type: 'rect', x: 0, y: 5, w: 24, h: 2, color: A}]}]} : null,
    footer: (page, count) => ({margin: [40, 16, 40, 0], columns: [{text: footLine || RB(r.address || 'Property report'), fontSize: 7, color: faint, noWrap: true},
      {text: [{text: 'Public records compiled by ', color: faint}, {text: 'BayCounty.me', bold: true, color: muted}, {text: `     ${page} / ${count}`, color: faint}], fontSize: 7, alignment: 'right', width: 'auto'}]}),
    content: [...cover.filter(Boolean), ...sections, card, disc].filter(Boolean),
  };
}
const pdfName = () => `property-report-${String(REPORT.address || 'address').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}.pdf`;
async function makePdf() { await pdfReady(); return pdfMake.createPdf(buildDoc(COVER ? {photo: COVER.full, bandPhoto: COVER.band} : {})); }
$('pdfBtn').addEventListener('click', async () => {
  const btn = $('pdfBtn'); btn.disabled = true; const label = btn.innerHTML; btn.textContent = 'Making PDF…';
  try { (await makePdf()).download(pdfName()); }
  catch (e) { $('runErr').textContent = 'The PDF couldn’t be made. Check your connection and try again.'; $('runErr').hidden = false; }
  btn.disabled = false; btn.innerHTML = label;
});

/* ---------- email the report ----------
   The PDF is made here, as for the download, and posted once to /api/realtor?action=email. It goes out from
   hello@baycounty.me under the agent's name with replies going to the agent; nothing about it is kept but a count. */
function openMail() {
  const b = (ME && ME.brand) || {}, name = b.agent_name || '', reply = b.email || (ME && ME.agent.email) || '';
  $('mailFrom').innerHTML = `Sent from hello@baycounty.me as <b>${esc(name ? name + ' via BayCounty.me' : 'BayCounty.me')}</b>, with the PDF attached. Replies go to <b>${esc(reply)}</b>.` +
    (name ? '' : ' Add your name under Your branding so clients know it’s from you.');
  $('m_subject').value = `Property report: ${REPORT.address || ''}`;
  const first = (REPORT.prepared_for || '').split(/\s+/)[0];
  $('m_message').value = `${first ? `Hi ${first},\n\n` : ''}Here’s the property report for ${REPORT.address || 'the address we talked about'}. Let me know if you have any questions.${name ? `\n\n${name}` : ''}`;
  $('mailMsg').textContent = ''; $('mailMsg').className = 'rc-msg small';
  $('mailForm').hidden = false; $('mailBtn').setAttribute('aria-expanded', 'true'); $('m_to').focus();
}
function closeMail() { $('mailForm').hidden = true; $('mailBtn').setAttribute('aria-expanded', 'false'); }
$('mailBtn').addEventListener('click', () => ($('mailForm').hidden ? openMail() : closeMail()));
$('mailCancel').addEventListener('click', closeMail);
$('mailForm').addEventListener('submit', async e => {
  e.preventDefault();
  const msg = $('mailMsg'), btn = $('mailSend'), to = $('m_to').value.split(/[\s,;]+/).filter(Boolean);
  msg.className = 'rc-msg small';
  if (!to.length) { msg.className = 'rc-msg small err'; msg.textContent = 'Add at least one email address.'; return; }
  btn.disabled = true; msg.textContent = 'Making the PDF…';
  try {
    const doc = await makePdf(), pdf = await new Promise(res => doc.getBase64(res));
    msg.textContent = 'Sending…';
    const r = await api('email', {to, subject: $('m_subject').value, message: $('m_message').value, cc_me: $('m_cc').checked, pdf, filename: pdfName(),
      address: REPORT.address, prepared_for: REPORT.prepared_for, report_id: REPORT.saved_id || null});
    msg.className = 'rc-msg small ok'; msg.textContent = `Sent to ${r.sent_to.join(', ')}. Replies go to ${r.reply_to}.`; $('m_to').value = '';
  } catch (err) { msg.className = 'rc-msg small err'; msg.textContent = err.message || 'The email couldn’t be sent.'; }
  btn.disabled = false;
});
$('printBtn').addEventListener('click', () => window.print());
window.BCRealtor = {buildDoc: o => buildDoc(o), report: () => REPORT, pdfReady};

start();
})();
