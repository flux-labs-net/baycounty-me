
(() => {
const GIS = 'https://gis.baycountyfl.gov/arcgis/rest/services/Admin_A12/MapServer/3';
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const title = s => String(s || '').toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase()).replace(/\b(Ne|Nw|Se|Sw|Us|Cr|Sr)\b/g, m => m.toUpperCase());
const name = (id, text) => id && window.BC && BC.a ? BC.a(id, text) : esc(text);
const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const inp = $('utQ'), list = $('utList');
let items = [], active = -1, seq = 0, timer;

/* Holiday rules as the cities write them ("3rd Monday in January", "Friday after Thanksgiving") -> a date in a year. */
function easter(y) { const a = y % 19, b = Math.floor(y / 100), c = y % 100, d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25), g = Math.floor((b - f + 1) / 3),
  h = (19 * a + b - d - g + 15) % 30, i = Math.floor(c / 4), k = c % 4, l = (32 + 2 * e + 2 * i - h - k) % 7, m = Math.floor((a + 11 * h + 22 * l) / 451);
  return new Date(y, Math.floor((h + l - 7 * m + 114) / 31) - 1, ((h + l - 7 * m + 114) % 31) + 1); }
function nth(y, mo, dow, n) { if (n < 0) { const d = new Date(y, mo + 1, 0); while (d.getDay() !== dow) d.setDate(d.getDate() - 1); return d; }
  const d = new Date(y, mo, 1); while (d.getDay() !== dow) d.setDate(d.getDate() + 1); d.setDate(d.getDate() + 7 * (n - 1)); return d; }
function holidayDate(when, y) {
  let m = /^(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2})$/.exec(when);
  if (m) return new Date(y, MONTHS.indexOf(m[1]), +m[2]);
  m = /^(1st|2nd|3rd|4th|Last) (\w+day) in (\w+)$/.exec(when);
  if (m) return nth(y, MONTHS.indexOf(m[3]), DAYS.indexOf(m[2]), m[1] === 'Last' ? -1 : parseInt(m[1]));
  if (when === 'Friday before Easter') { const d = easter(y); d.setDate(d.getDate() - 2); return d; }
  if (when === 'Friday after Thanksgiving') { const d = nth(y, 10, 4, 4); d.setDate(d.getDate() + 1); return d; }
  return null;
}
const same = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
const fmtDate = d => `${DAYS[d.getDay()]}, ${MONTHS[d.getMonth()]} ${d.getDate()}`;
/* The next date one of these weekdays comes up (today counts), and any holiday on it that stops this kind of pickup. */
function nextPickup(days, svc, holidays) {
  const want = DAYS.filter(d => new RegExp('\\b' + d + '\\b').test(days || ''));
  if (!want.length) return null;
  const d = new Date(); d.setHours(0, 0, 0, 0);
  for (let i = 0; i < 8; i++, d.setDate(d.getDate() + 1)) {
    if (!want.includes(DAYS[d.getDay()])) continue;
    const key = svc === 'yard_waste' ? 'yard_waste' : 'garbage';
    const h = holidays.find(x => { const hd = holidayDate(x.when_observed, d.getFullYear()); return hd && same(hd, d) && /^No pickup/.test(x[key] || ''); });
    return {date: new Date(d), holiday: h};
  }
  return null;
}

async function gis(params) {
  const u = GIS + '/query?' + new URLSearchParams({f: 'json', returnGeometry: 'true', outSR: '4326', outFields: 'ADDRESS,UNIT,CMNTY,ZIP', resultRecordCount: '10', orderByFields: 'ADDRESS', ...params});
  const r = await fetch(u, {mode: 'cors'}); const j = await r.json(); if (j.error) throw new Error(j.error.message); return j.features || [];
}
const sq = s => s.replace(/'/g, "''");
async function suggest() {
  const s = inp.value.toUpperCase().replace(/[^A-Z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
  const m = /^(\d+)\s+(.+)$/.exec(s);
  if (!m) { hide(); return; }
  const words = m[2].split(' ').filter(w => w.length > 1 && !/^(ST|AVE|RD|DR|LN|CT|BLVD|WAY|CIR|PL|FL|PANAMA|CITY|BEACH|LYNN|HAVEN)$/.test(w)).slice(0, 4);
  if (!words.length) { hide(); return; }
  const my = ++seq;
  const where = [`ADDRESS LIKE '${m[1]} %'`, ...words.slice(0, -1).map(w => `(ADDRESS LIKE '% ${sq(w)} %' OR ADDRESS LIKE '% ${sq(w)}')`), `ADDRESS LIKE '% ${sq(words[words.length - 1])}%'`].join(' AND ');
  try {
    const f = await gis({where});
    if (my !== seq) return;
    items = f; active = -1;
    list.innerHTML = f.length ? f.map((x, i) => `<li role="option" id="ut${i}" data-i="${i}">${esc(title(x.attributes.ADDRESS))}${(x.attributes.UNIT || '').trim() ? ' #' + esc(x.attributes.UNIT) : ''}<span>${esc(x.attributes.CMNTY || '')} ${esc(x.attributes.ZIP || '')}</span></li>`).join('')
      : '<li class="ut-empty">No matching address. Try just the house number and street name.</li>';
    show();
  } catch (e) { if (my === seq) { list.innerHTML = '<li class="ut-empty">Bay County\'s map server didn\'t answer. Try again in a moment.</li>'; show(); } }
}
function show() { list.hidden = false; inp.setAttribute('aria-expanded', 'true'); }
function hide() { list.hidden = true; inp.setAttribute('aria-expanded', 'false'); }
function mark() { list.querySelectorAll('li[role=option]').forEach((li, i) => li.setAttribute('aria-selected', i === active)); if (active >= 0) inp.setAttribute('aria-activedescendant', 'ut' + active); }
function pick(f) {
  hide();
  const a = f.attributes;
  inp.value = title(a.ADDRESS) + ((a.UNIT || '').trim() ? ' #' + a.UNIT : '');
  const u = new URL(location.href); u.searchParams.set('a', a.ADDRESS); history.replaceState(null, '', u);
  run(f.geometry.y, f.geometry.x, inp.value + (a.CMNTY ? ', ' + title(a.CMNTY) : ''));
}

const link = (u, t) => u ? `<a href="${esc(u)}" rel="noopener" target="_blank">${esc(t)}</a>` : '';
const tel = p => p ? `<a href="tel:${esc(p.replace(/[^0-9+]/g, ''))}">${esc(p)}</a>` : '';

/* Render one lookup from /api/v1/utilities into box (this page and the /my-address card share it). */
function render(box, r, opts = {}) {
  const pick = r.pickup.map(p => {
    const sv = ((r.services.find(s => s.service === p.service) || {}).providers || [])[0];
    const nx = p.days && r.holidays ? nextPickup(p.days, p.service, r.holidays) : null;
    const zone = p.zone && p.zone !== p.days ? ` <span class="muted">(${/^\d+$/.test(p.zone) ? (p.zone_label || 'zone') + ' ' : ''}${esc(p.zone)})</span>` : '';
    return `<div class="ut-card ut-pick"><span class="eyebrow">${esc(p.service_label)}</span>
      ${p.days ? `<div class="ut-day">${esc(p.days)}${zone}</div>` : ''}${p.zone_area ? `<p class="muted">${esc(p.zone && !p.days ? p.zone + ': ' : '')}${esc(p.zone_area)}</p>` : ''}
      ${nx ? `<div class="ut-next">Next: ${fmtDate(nx.date)}</div>` : ''}
      ${nx && nx.holiday ? `<div class="ut-warn">${esc(nx.holiday.holiday)}: no pickup that day. Check the holiday changes below.</div>` : ''}
      ${p.rule ? `<p>${esc(p.rule)}</p>` : ''}${p.notes ? `<p>${esc(p.notes)}</p>` : ''}
      ${sv ? `<b style="font-size:.92rem">${name(sv.entity_id, sv.provider)}</b>${sv.notes ? `<p class="muted">${esc(sv.notes)}</p>` : ''}<div class="ut-acts">${tel(sv.phone)}${link(sv.website, 'Website')}</div>` : `<p class="muted">${esc(p.provider)}</p>`}</div>`;
  }).join('');
  // garbage, yard waste and bulk providers show on their trash-day card, not twice
  const svc = r.services.filter(s => !r.pickup.some(p => p.service === s.service)).map(s => s.providers.map((p, i) =>
    `<div class="ut-card"><span class="eyebrow">${esc(s.service_label)}${s.providers.length > 1 ? (i === 0 ? ' · most likely' : ' · or') : ''}</span>
      <b>${name(p.entity_id, p.provider)}</b>${p.notes ? `<p>${esc(p.notes)}</p>` : ''}
      <div class="ut-acts">${tel(p.phone)}${link(p.website, 'Website')}${p.outage_url && p.outage_url !== p.website ? link(p.outage_url, 'Outage map') : ''}</div></div>`).join('')).join('');
  const hol = (r.holidays || []).length ? `<details class="tbl-toggle"><summary>Holiday changes (${r.holidays.length})</summary><div class="tablewrap"><table class="tx-table ut-tbl" data-tt="off"><thead><tr><th>Holiday</th><th>When</th><th>Garbage</th><th>Yard waste</th></tr></thead><tbody>${r.holidays.map(h => `<tr><td>${esc(h.holiday)}</td><td>${esc(h.when_observed)}</td><td>${esc(h.garbage)}</td><td>${esc(h.yard_waste)}</td></tr>`).join('')}</tbody></table></div></details>` : '';
  const bill = (r.rates || []).find(x => x.service === 'bill');
  box.innerHTML = `<div class="ut-hd">${opts.heading === false ? '' : `<h2>${esc(opts.label || '')}</h2>`}<p class="muted">${r.area === 'county' ? 'Unincorporated Bay County' : 'City of ' + esc(r.area_name)}${bill ? ` · typical water and sewer bill $${Number(bill.amount).toFixed(2)} a month at 5,000 gallons` : ''}</p></div>
    ${pick ? `<h3 class="ch-grp" style="margin-top:14px">Trash day</h3><div class="ut-grid">${pick}</div>` : ''}
    <h3 class="ch-grp" style="margin-top:18px">Who provides what</h3><div class="ut-grid">${svc}</div>${hol}
    <p class="note">${esc(r.note)}</p>`;
}
window.BCUtil = {render, nextPickup, holidayDate,
  async card(el, {lat, lon}) {
    el.innerHTML = '<p class="muted small">Loading…</p>';
    try { const j = await (await fetch(`/api/v1/utilities?lat=${lat}&lon=${lon}`)).json(); if (j.error) throw new Error(j.error); render(el, j.data, {heading: false}); }
    catch (e) { el.innerHTML = '<p class="muted small">Utility lookup didn\'t answer. <a href="/utilities">Try the utilities page</a>.</p>'; }
  }};

async function run(lat, lon, label) {
  const out = $('utOut'), err = $('utErr');
  err.hidden = true; out.hidden = false; out.innerHTML = '<p class="muted">Looking up…</p>';
  try {
    const res = await fetch(`/api/v1/utilities?lat=${lat}&lon=${lon}`); const j = await res.json();
    if (j.error) throw new Error(j.error);
    render(out, j.data, {label});
  } catch (e) { out.hidden = true; err.textContent = e.message || 'The lookup didn\'t answer. Try again in a moment.'; err.hidden = false; }
}
if (!inp) return;
inp.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(suggest, 220); });
inp.addEventListener('keydown', ev => {
  if (list.hidden || !items.length) { if (ev.key === 'Enter') { ev.preventDefault(); suggest(); } return; }
  if (ev.key === 'ArrowDown') { ev.preventDefault(); active = Math.min(items.length - 1, active + 1); mark(); }
  else if (ev.key === 'ArrowUp') { ev.preventDefault(); active = Math.max(0, active - 1); mark(); }
  else if (ev.key === 'Enter') { ev.preventDefault(); pick(items[Math.max(0, active)]); }
  else if (ev.key === 'Escape') hide();
});
list.addEventListener('mousedown', ev => { const li = ev.target.closest('li[data-i]'); if (li) { ev.preventDefault(); pick(items[+li.dataset.i]); } });
document.addEventListener('click', ev => { if (!ev.target.closest('.ac')) hide(); });

const qa = new URLSearchParams(location.search).get('a');
if (qa) gis({where: `ADDRESS = '${sq(qa.toUpperCase())}'`, resultRecordCount: '1'}).then(f => f[0] && pick(f[0])).catch(() => {});
// Signed in: the saved home's trash day shows without typing (kept out of the address bar).
else if (window.BCUseHome) BCUseHome(inp, h => run(h.lat, h.lon, inp.value + (h.city ? ', ' + title(h.city) : '')), inp.closest('.ac'));
})();
