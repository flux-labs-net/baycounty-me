"""Public schools (/schools): which schools serve an address, the district calendar, every school's grades, spending
and enrollment, and schools that closed since 2016.

Built from the schools, school-grades, school-spending, school-enrollment, school-calendar and school-zones datasets
(site/page_datasets.py _school_rows(), from data/schools/<county>/). The zone finder looks addresses up in the county's
address points and checks them against the school-zones shapes in the browser, the same test /api/v1/schools runs.
"""
import datetime as dt
import re
import html

from entity_links import a as link, build
from place import PLACE, governments

e = lambda s: html.escape(str(s if s is not None else ''))

CSS = r"""
.sc-find{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:16px;align-items:start}
.sc-box{padding:20px 22px;border-radius:24px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.sc-box h3{margin:0 0 6px;font-size:1.05rem;font-weight:600}
.sc-box p{margin:0 0 12px;font-size:.9rem;line-height:1.5}
.sc-ac{position:relative}
.sc-ac input{width:100%;box-sizing:border-box;font:inherit;font-size:1rem;padding:12px 14px;border-radius:14px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
.sc-ac ul{position:absolute;z-index:20;left:0;right:0;top:calc(100% + 4px);margin:0;padding:6px;list-style:none;border-radius:14px;background:var(--surface);box-shadow:var(--ui-shadow);max-height:300px;overflow:auto}
.sc-ac li{padding:9px 10px;border-radius:10px;cursor:pointer;font-size:.92rem}
.sc-ac li span{color:var(--muted);font-size:.8rem;margin-left:6px}
.sc-ac li:hover,.sc-ac li[aria-selected=true]{background:var(--sunken)}
.sc-ac li.sc-empty{cursor:default;color:var(--muted)}
.sc-res{display:flex;flex-direction:column;gap:10px}
.sc-res[hidden]{display:none}
.sc-z{display:flex;gap:12px;align-items:center;padding:12px 14px;border-radius:18px;background:var(--sunken);min-width:0}
.sc-z .lv{flex:none;width:86px;font-size:.78rem;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.sc-z b{display:block;font-size:.95rem;font-weight:600;overflow-wrap:anywhere}
.sc-z b a{color:inherit;text-decoration:none}
.sc-z b a:hover{color:var(--blue);text-decoration:underline}
.sc-z small{display:block;font-size:.8rem;color:var(--muted)}
.sc-z .gr{margin-left:auto}
.sc-g{display:inline-flex;align-items:center;justify-content:center;min-width:30px;height:30px;padding:0 6px;border-radius:9px;font:700 .95rem var(--f-body);background:var(--sunken);color:var(--muted);flex:none}
.sc-g.g-A{background:color-mix(in srgb,var(--teal) 22%,transparent);color:var(--teal)}
.sc-g.g-B{background:color-mix(in srgb,var(--blue) 18%,transparent);color:var(--blue)}
.sc-g.g-C{background:color-mix(in srgb,var(--amber,#C98A1B) 22%,transparent);color:var(--amber,#9A6A10)}
.sc-g.g-D,.sc-g.g-F{background:color-mix(in srgb,var(--salmon) 22%,transparent);color:var(--salmon)}
.sc-g.sm{min-width:24px;height:24px;font-size:.8rem;border-radius:7px}
.sc-cal{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.sc-cal [hidden]{display:none!important}
.sc-pill{display:inline-block;margin-top:6px;font-size:.72rem;font-weight:600;padding:2px 9px;border-radius:999px;background:var(--sunken);color:var(--muted)}
.sc-pill.k-no-school,.sc-pill.k-break{background:color-mix(in srgb,var(--salmon) 16%,transparent);color:var(--salmon)}
.sc-pill.k-board-meeting{background:color-mix(in srgb,var(--blue) 14%,transparent);color:var(--blue)}
.sc-pill.k-early-release{background:color-mix(in srgb,var(--amber,#C98A1B) 18%,transparent);color:var(--amber,#9A6A10)}
.sc-pill.k-graduation,.sc-pill.k-first-day,.sc-pill.k-last-day{background:color-mix(in srgb,var(--teal) 16%,transparent);color:var(--teal)}
.sc-ctl{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center}
.sc-ctl input[type=search]{font:inherit;font-size:.92rem;padding:9px 12px;border-radius:12px;border:1px solid var(--line);background:var(--bg);color:var(--ink);min-width:200px;flex:1;max-width:320px}
.sc-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px;align-items:start}
.sc-list [hidden]{display:none!important}
.sc-s{border-radius:20px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0;scroll-margin-top:90px}
.sc-s:target{outline:2px solid var(--blue);outline-offset:2px}
.sc-s summary{list-style:none;display:flex;gap:12px;align-items:center;padding:14px 16px;cursor:pointer}
.sc-s summary::-webkit-details-marker{display:none}
.sc-s summary .nm{min-width:0;flex:1}
.sc-s summary b{display:block;font-size:.95rem;font-weight:600;overflow-wrap:anywhere}
.sc-s summary small{display:block;font-size:.8rem;color:var(--muted);margin-top:2px}
.sc-s .bd{padding:0 16px 16px;display:flex;flex-direction:column;gap:12px;font-size:.88rem}
.sc-facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0}
.sc-facts div{padding:9px 11px;border-radius:12px;background:var(--sunken);min-width:0}
.sc-facts dt{font-size:.74rem;color:var(--muted)}
.sc-facts dd{margin:2px 0 0;font:600 1rem var(--f-body);font-variant-numeric:tabular-nums}
.sc-hist{display:flex;flex-wrap:wrap;gap:6px}
.sc-hrs{margin:0;font-size:.88rem}.sc-hrs b{font-weight:600;margin-right:4px}
.sc-map{height:480px;border-radius:24px;box-shadow:var(--ui-shadow);overflow:hidden;background:var(--sunken);z-index:0;margin-top:10px}
:root[data-theme="dark"] .sc-map .leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) brightness(.9) contrast(.9)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .sc-map .leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) brightness(.9) contrast(.9)}}
.sc-map .leaflet-popup-content{font:.85rem/1.5 var(--f-body);margin:10px 12px}
.sc-map .leaflet-popup-content > b:first-child{display:block;font-size:.95rem;margin-bottom:2px}
.sc-zsel{display:inline-flex;align-items:center;gap:8px;font-size:.85rem;color:var(--muted)}
.sc-zsel select{min-height:36px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--ink);padding:0 12px;font:inherit}
.sc-mkey{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:10px;font-size:.8rem;color:var(--muted)}
.sc-mkey span{display:inline-flex;align-items:center;gap:6px}
.sc-mkey i{width:12px;height:12px;border-radius:50%;background:#8a94a3;border:1.5px solid #fff}
.sc-mkey i.g-A{background:var(--teal)}.sc-mkey i.g-B{background:var(--blue)}.sc-mkey i.g-C{background:var(--amber,#C98A1B)}.sc-mkey i.g-D{background:var(--salmon)}
.sc-mkey i.ch{background:transparent;border:2.5px solid var(--ink)}
@media (max-width:760px){.sc-map{height:380px;border-radius:18px}}
.sc-cps{display:grid;gap:7px}
.sc-cp{display:grid;grid-template-columns:minmax(0,11.5em) minmax(60px,1fr) 3em 2.6em;align-items:center;gap:8px;font-size:.82rem}
.sc-cp .lb{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sc-cp .tr{position:relative;height:10px;border-radius:5px;background:var(--sunken)}
.sc-cp .tr i{position:absolute;inset:0 auto 0 0;border-radius:5px;background:var(--blue)}
.sc-cp .tr b{position:absolute;top:-3px;bottom:-3px;width:2px;margin-left:-1px;background:var(--ink);border-radius:1px}
.sc-cp .v{font-weight:600;text-align:right;font-variant-numeric:tabular-nums}
.sc-cp .ch{font-size:.72rem;color:var(--muted);font-variant-numeric:tabular-nums}
.sc-cp .ch.up{color:#15803d}.sc-cp .ch.dn{color:#b91c1c}
.sc-key{display:flex;flex-wrap:wrap;gap:4px 14px;margin-top:8px;font-size:.72rem;color:var(--muted)}
.sc-key span{display:inline-flex;align-items:center;gap:5px}
.sc-key i{width:14px;height:8px;border-radius:4px;background:var(--blue)}
.sc-key b{width:2px;height:12px;background:var(--ink)}
.sc-mixes{display:grid;gap:8px;margin:4px 0 16px}
.sc-mix{display:grid;grid-template-columns:9.5em 1fr;align-items:center;gap:10px;font-size:.85rem}
.sc-mix .lb{font-weight:600}.sc-mix .lb small{display:block;font-weight:400;color:var(--muted);font-size:.72rem}
.sc-mix .tr{display:flex;height:26px;border-radius:8px;overflow:hidden;background:var(--sunken)}
.sc-mix .tr i.g-A{background:color-mix(in srgb,var(--teal) 30%,transparent);color:var(--teal)}
.sc-mix .tr i.g-B{background:color-mix(in srgb,var(--blue) 24%,transparent);color:var(--blue)}
.sc-mix .tr i.g-C{background:color-mix(in srgb,var(--amber,#C98A1B) 28%,transparent);color:var(--amber,#9A6A10)}
.sc-mix .tr i.g-D,.sc-mix .tr i.g-F{background:color-mix(in srgb,var(--salmon) 30%,transparent);color:var(--salmon)}
.sc-mix .tr i{display:flex;align-items:center;justify-content:center;font:600 .72rem var(--f-body);font-style:normal;white-space:nowrap;overflow:hidden}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]) .sc-cp .ch.up{color:#4ade80}:root:not([data-theme=light]) .sc-cp .ch.dn{color:#f87171}}
:root[data-theme=dark] .sc-cp .ch.up{color:#4ade80}:root[data-theme=dark] .sc-cp .ch.dn{color:#f87171}
.sc-hist span{display:inline-flex;flex-direction:column;align-items:center;gap:2px;font-size:.68rem;color:var(--muted)}
.sc-spark{width:100%;height:46px;display:block}
.sc-spark path{fill:none;stroke:var(--blue);stroke-width:2}
.sc-spark circle{fill:var(--blue)}
.sc-mx td,.sc-mx th{text-align:center;padding:6px 4px}
.sc-mx td:first-child,.sc-mx th:first-child{text-align:left;min-width:180px;position:sticky;left:0;z-index:1;background:var(--surface)}
@media (max-width:640px){.sc-mx td:first-child,.sc-mx th:first-child{min-width:132px;max-width:132px;font-size:.8rem}}
.sc-mx td.na{color:var(--muted);font-size:.78rem}
.sc-bars{display:flex;flex-direction:column;gap:6px}
.sc-bar{display:grid;grid-template-columns:minmax(150px,240px) 1fr 80px;gap:10px;align-items:center;font-size:.85rem}
.sc-bar .tr{height:12px;border-radius:6px;background:var(--sunken);overflow:hidden}
.sc-bar .tr i{display:block;height:100%;border-radius:6px;background:var(--blue)}
.sc-bar .v{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
.sc-bar a{color:inherit;text-decoration:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sc-bar a:hover{color:var(--blue)}
.sc-enr{display:flex;align-items:flex-end;gap:6px;height:170px;padding-top:10px}
.sc-enr div{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:4px;height:100%;min-width:0}
.sc-enr i{display:block;width:100%;max-width:44px;border-radius:8px 8px 3px 3px;background:var(--blue)}
.sc-enr i.low{background:var(--salmon)}
.sc-enr b{font-size:.72rem;font-variant-numeric:tabular-nums;font-weight:600}
.sc-enr small{font-size:.7rem;color:var(--muted);white-space:nowrap}
.sc-pend{padding:16px 18px;border-radius:18px;background:var(--sunken);font-size:.9rem;line-height:1.5}
@media (max-width:760px){.sc-find{grid-template-columns:1fr}.sc-box{padding:16px}.sc-list{grid-template-columns:1fr}
  .sc-z .lv{width:70px}.sc-bar{grid-template-columns:minmax(0,1fr) 90px;grid-template-areas:"n v" "t t";row-gap:4px}.sc-bar a{grid-area:n}.sc-bar .tr{grid-area:t}.sc-bar .v{grid-area:v}
  .sc-cp{grid-template-columns:minmax(0,9.5em) minmax(50px,1fr) 2.7em 2.3em;gap:6px;font-size:.78rem}.sc-mix{grid-template-columns:6.5em 1fr}
  .sc-enr small{font-size:.62rem}.sc-enr b{font-size:.62rem}.sc-facts dd{font-size:.92rem}}
"""

LEAFLET = ('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">'
           '<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js" defer></script>')

MAP_JS = r"""
window.addEventListener('load', () => {
  const el = document.getElementById('scMap'); if (!el || !window.L) return;
  const S = __SCHOOLS__;
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const col = g => ({A: css('--teal') || '#1a8f7a', B: css('--blue') || '#2b5fb4', C: css('--amber') || '#C98A1B', D: css('--salmon') || '#d65a4a', F: css('--salmon') || '#d65a4a'})[g] || '#8a94a3';
  const m = L.map(el, {scrollWheelZoom: false});
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(m);
  const pts = [], all = [];
  for (const [id, s] of Object.entries(S)) {
    if (s.lat == null || s.lon == null || s.ty === 'Virtual' || /virtual/i.test(s.name)) continue;
    const mk = L.circleMarker([s.lat, s.lon], {radius: 8, color: s.ch ? css('--ink') || '#111' : '#fff', weight: s.ch ? 2.5 : 1.5, fillColor: col(s.gr), fillOpacity: .95});
    const dir = `https://www.google.com/maps/dir/?api=1&destination=${s.lat},${s.lon}`;
    mk.bindPopup(`<b>${esc(s.name)}</b>${s.gr ? `State grade <b class="g">${esc(s.gr)}</b> (${s.gy - 1}-${String(s.gy).slice(2)})<br>` : ''}${esc(s.lv)}${s.g ? ' · grades ' + esc(s.g) : ''}${s.ch ? ' · charter' : ''}${s.n ? ` · ${Number(s.n).toLocaleString()} students` : ''}`
      + (s.hrs ? `<br>School day: ${esc(s.hrs)}` : '') + `<br><a href="#s-${esc(id)}" data-open="${esc(id)}">Details</a> · <a href="${dir}" target="_blank" rel="noopener">Directions</a>`);
    mk.addTo(m); pts.push({mk, s}); all.push([s.lat, s.lon]);
  }
  if (all.length) m.fitBounds(all, {padding: [24, 24]});
  el.addEventListener('click', ev => { const a = ev.target.closest('[data-open]'); if (!a) return; const d = document.getElementById('s-' + a.dataset.open); if (d) d.open = true; });
  const lvBox = document.getElementById('scMapLv');
  lvBox.addEventListener('click', ev => {
    const b = ev.target.closest('button'); if (!b) return;
    lvBox.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b));
    const v = b.dataset.v;
    for (const {mk, s} of pts) {
      const on = !v || (v === 'charter' ? s.ch : s.lv === v || (s.lv === 'Combined' && v !== 'charter'));
      on ? mk.addTo(m) : mk.remove();
    }
  });
  let zl = null, zones = null;
  document.getElementById('scMapZ').addEventListener('change', async ev => {
    const v = ev.target.value; if (zl) { zl.remove(); zl = null; } if (!v) return;
    try { zones = zones || await (await fetch('/downloads/school-zones.json')).json(); } catch (e) { return; }
    const line = css('--blue') || '#2b5fb4';
    zl = L.layerGroup(zones.filter(z => z.level === v && !z.mou_area).map(z => L.geoJSON(JSON.parse(z.geometry), {style: {color: line, weight: 1.5, fillColor: line, fillOpacity: .07}})
      .bindTooltip(esc(z.school || z.zone_name), {sticky: true}))).addTo(m);
    pts.forEach(({mk}) => mk.bringToFront && mk.bringToFront());
  });
});
"""

JS = r"""
(() => {
  const GIS = 'https://gis.baycountyfl.gov/arcgis/rest/services/Admin_A12/MapServer/3/query';
  const S = __SCHOOLS__;
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const title = s => String(s || '').toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase()).replace(/\b(Ne|Nw|Se|Sw|Us|Cr|Sr)\b/g, m => m.toUpperCase());

  /* ---------- zone finder: county address points, then the school-zones shapes ---------- */
  const inp = $('scAddr'), list = $('scList'), out = $('scOut');
  let zones = null, items = [], seq = 0, timer = 0, active = -1;
  const SKIP = new Set(['ST', 'STREET', 'AVE', 'AVENUE', 'RD', 'ROAD', 'DR', 'DRIVE', 'BLVD', 'LN', 'LANE', 'CT', 'CIR', 'PL', 'WAY', 'FL', 'FLORIDA', 'PANAMA', 'CITY', 'BEACH', 'LYNN', 'HAVEN', 'CALLAWAY', 'SPRINGFIELD', 'PARKER', 'MEXICO', 'SOUTHPORT', 'YOUNGSTOWN', 'FOUNTAIN']);
  function where(raw) {
    const s = raw.toUpperCase().replace(/[^A-Z0-9 ]/g, ' ').replace(/\b\d{5}\b/g, ' ').replace(/\s+/g, ' ').trim();
    const m = /^(\d+)\s*(.*)$/.exec(s); if (!m) return null;
    const w = m[2].split(' ').filter(x => x.length > 1 && !SKIP.has(x)).slice(0, 3);
    if (!w.length) return null;
    return [`ADDRESS LIKE '${m[1]} %'`, ...w.map((x, i) => i === w.length - 1 ? `ADDRESS LIKE '% ${x.replace(/'/g, "''")}%'` : `(ADDRESS LIKE '% ${x} %' OR ADDRESS LIKE '% ${x}')`)].join(' AND ');
  }
  async function suggest() {
    const w = where(inp.value); if (!w) { list.hidden = true; return; }
    const my = ++seq;
    try {
      const u = GIS + '?' + new URLSearchParams({where: w, outFields: 'ADDRESS,UNIT,CMNTY,ZIP', returnGeometry: 'true', outSR: '4326', resultRecordCount: '8', orderByFields: 'ADDRESS', f: 'json'});
      const j = await (await fetch(u)).json(); if (my !== seq) return;
      items = (j.features || []).filter((f, i, a) => a.findIndex(g => g.attributes.ADDRESS === f.attributes.ADDRESS) === i); active = -1;
      list.innerHTML = items.length ? items.map((f, i) => `<li role="option" data-i="${i}">${esc(title(f.attributes.ADDRESS))}<span>${esc(title(f.attributes.CMNTY || ''))} ${esc(f.attributes.ZIP || '')}</span></li>`).join('')
        : '<li class="sc-empty">No matching address. Try the house number and street name, like "1200 Harrison".</li>';
      list.hidden = false;
    } catch (e) { if (my === seq) { list.innerHTML = '<li class="sc-empty">The county\'s address service didn\'t answer. Try again in a moment.</li>'; list.hidden = false; } }
  }
  function inRings(rings, x, y) {
    let c = false;
    for (const r of rings) for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
      const [xi, yi] = r[i], [xj, yj] = r[j];
      if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c;
    }
    return c;
  }
  const rings = g => g.type === 'Polygon' ? g.coordinates : g.coordinates.flat();
  async function pick(f) {
    list.hidden = true;
    const a = f.attributes, pt = f.geometry;
    inp.value = title(a.ADDRESS);
    out.hidden = false; $('scHint').hidden = true; out.innerHTML = '<p class="muted small">Checking the zones…</p>';
    try { zones = zones || (await (await fetch('/downloads/school-zones.json')).json()).map(z => ({...z, r: rings(JSON.parse(z.geometry))})); }
    catch (e) { out.innerHTML = '<p class="muted">Couldn\'t load the zone map. Try again.</p>'; return; }
    const rows = ['Elementary', 'Middle', 'High'].map(lv => {
      const z = zones.filter(z => z.level === lv && inRings(z.r, pt.x, pt.y)).sort((p, q) => p.mou_area - q.mou_area)[0];
      const s = z && S[z.school_id];
      if (!z) return `<div class="sc-z"><span class="lv">${lv}</span><span class="nm"><b class="muted">No zone found</b><small>This spot may be outside the district's zones.</small></span></div>`;
      const sub = s ? [s.g ? `Grades ${s.g}` : '', s.n ? `${s.n.toLocaleString('en-US')} students` : ''].filter(Boolean).join(' · ') : '';
      return `<div class="sc-z"><span class="lv">${lv}</span><span class="nm"><b><a href="#s-${esc(z.school_id)}">${esc(s ? s.name : z.school || z.zone_name)}</a></b><small>${esc(sub)}${z.mou_area ? ' · MOU area: confirm with the district' : ''}</small></span>${s && s.gr ? `<span class="gr sc-g g-${esc(s.gr)}" title="State grade ${esc(s.gy)}">${esc(s.gr)}</span>` : ''}</div>`;
    });
    out.innerHTML = rows.join('') + `<p class="small muted" style="margin:4px 0 0">${esc(title(a.ADDRESS))}, ${esc(title(a.CMNTY || ''))}. <a href="/my-address?a=${encodeURIComponent(a.ADDRESS)}&z=${encodeURIComponent(a.ZIP || '')}${a.UNIT ? '&u=' + encodeURIComponent(a.UNIT) : ''}">Full report for this address →</a></p>`;
    const u = new URL(location.href); u.searchParams.set('a', a.ADDRESS); history.replaceState(null, '', u);
  }
  if (inp) {
    inp.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(suggest, 250); });
    inp.addEventListener('keydown', e => {
      const lis = [...list.querySelectorAll('li[data-i]')];
      if (e.key === 'ArrowDown' && lis.length) { e.preventDefault(); active = Math.min(lis.length - 1, active + 1); }
      else if (e.key === 'ArrowUp' && lis.length) { e.preventDefault(); active = Math.max(0, active - 1); }
      else if (e.key === 'Enter') { e.preventDefault(); if (items.length && !list.hidden) pick(items[Math.max(0, active)]); else suggest(); return; }
      else if (e.key === 'Escape') { list.hidden = true; return; } else return;
      lis.forEach((li, i) => li.setAttribute('aria-selected', i === active));
    });
    list.addEventListener('mousedown', e => { const li = e.target.closest('li[data-i]'); if (li) { e.preventDefault(); pick(items[+li.dataset.i]); } });
    document.addEventListener('click', e => { if (!e.target.closest('.sc-ac')) list.hidden = true; });
    const q = new URLSearchParams(location.search).get('a');
    if (q) { inp.value = title(q); (async () => { await suggest(); const f = items.find(f => f.attributes.ADDRESS === q.toUpperCase()) || (items.length === 1 && items[0]); if (f) pick(f); })(); }
  }

  /* ---------- calendar chips ---------- */
  const cal = $('scCal');
  if (cal) {
    const cards = [...cal.children], more = $('scCalMore'), N = matchMedia('(max-width:760px)').matches ? 6 : 9;
    let k = '', open = false;
    const ok = c => !k || c.dataset.k.split(' ').includes(k);
    function show() { let n = 0; for (const c of cards) { const y = ok(c); c.hidden = !y || (!open && n >= N); if (y) n++; } const left = cards.filter(ok).length - N; more.hidden = open || left <= 0; more.textContent = `Show ${left} more`; }
    $('scCalK').addEventListener('click', ev => { const b = ev.target.closest('button'); if (!b) return; $('scCalK').querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); k = b.dataset.v; show(); });
    more.addEventListener('click', () => { open = true; show(); });
    show();
  }

  /* ---------- school list filters ---------- */
  const box = $('scSchools');
  if (box) {
    const cards = [...box.querySelectorAll('.sc-s')], q = $('scQ');
    let lv = '';
    function show() {
      const t = q.value.trim().toLowerCase(); let n = 0;
      for (const c of cards) { const y = (!lv || c.dataset.f.split(' ').includes(lv)) && (!t || c.dataset.t.includes(t)); c.hidden = !y; if (y) n++; }
      $('scNone').hidden = n > 0;
    }
    $('scLv').addEventListener('click', ev => { const b = ev.target.closest('button'); if (!b) return; $('scLv').querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); lv = b.dataset.v; show(); });
    q.addEventListener('input', show);
    const open = () => { const d = location.hash.startsWith('#s-') && document.getElementById(location.hash.slice(1)); if (d && d.tagName === 'DETAILS') { d.hidden = false; d.open = true; } };
    window.addEventListener('hashchange', open); open();
  }
})();
"""

KIND_LABEL = {'no-school': 'No school', 'break': 'Break', 'board-meeting': 'School Board', 'early-release': 'Early release', 'grading': 'Grading period',
              'graduation': 'Graduation', 'first-day': 'First day', 'last-day': 'Last day', 'other': 'District event'}
LEVEL_ORDER = ['Elementary', 'Middle', 'High', 'Combined', 'Other']


def _money(n):
    return '—' if n is None else f'${round(n):,}'


def _d(s):
    try:
        return dt.date.fromisoformat((s or '')[:10])
    except ValueError:
        return None


def _tile(d):
    return f'<span class="ui-date" aria-hidden="true"><span class="mo">{d.strftime("%b").upper()}</span><span class="d">{d.day}</span><span class="wd">{d.strftime("%a")}</span></span>'


def _venue(ev):
    import re
    return re.sub(r',?\s*(United States|USA)\s*$', '', ev.get('venue') or '').strip(' ,')


def _when(ev):
    s, en = _d(ev['starts']), _d(ev.get('ends'))
    if ev.get('all_day'):
        if en and s and en > s:
            return f"{s.strftime('%a, %b %-d')} to {en.strftime('%a, %b %-d')}"
        return s.strftime('%A, %B %-d') if s else ''
    try:
        t = dt.datetime.fromisoformat(ev['starts'])
        return t.strftime('%a, %b %-d') + ' · ' + t.strftime('%-I:%M %p').replace(':00 ', ' ').lower().replace('am', 'a.m.').replace('pm', 'p.m.')
    except ValueError:
        return ev['starts']


def _g(grade, small=False, title=''):
    if not grade:
        return ''
    return f'<span class="sc-g{" sm" if small else ""} g-{e(grade)}"{f" title={chr(34)}{e(title)}{chr(34)}" if title else ""}>{e(grade)}</span>'


def _spark(points):
    """A small enrollment line: [(year, n)]."""
    if len(points) < 2:
        return ''
    lo, hi = min(n for _, n in points), max(n for _, n in points)
    span = (hi - lo) or 1
    w, h, pad = 300, 46, 5
    xy = [(pad + i * (w - 2 * pad) / (len(points) - 1), h - pad - (n - lo) / span * (h - 2 * pad)) for i, (_, n) in enumerate(points)]
    d = 'M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in xy)
    return (f'<svg class="sc-spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none" role="img" aria-label="Enrollment {points[0][0]} to {points[-1][0]}: '
            f'{points[0][1]:,} to {points[-1][1]:,}"><path d="{d}" vector-effect="non-scaling-stroke"/><circle cx="{xy[-1][0]:.1f}" cy="{xy[-1][1]:.1f}" r="3"/></svg>')


COMPONENTS = [('grade3_ela_achievement', '3rd-grade reading', 'Third graders scoring on grade level or above in reading'),
              ('ela_achievement', 'Reading', 'Students scoring on grade level or above in English language arts'),
              ('ela_gains', 'Reading gains', 'Students who made a year of progress in reading'),
              ('ela_gains_low25', 'Reading, lowest 25%', 'Progress among the school\'s lowest-scoring quarter of readers'),
              ('math_achievement', 'Math', 'Students scoring on grade level or above in math'),
              ('math_gains', 'Math gains', 'Students who made a year of progress in math'),
              ('math_gains_low25', 'Math, lowest 25%', 'Progress among the school\'s lowest-scoring quarter in math'),
              ('science_achievement', 'Science', 'Students passing the state science test'),
              ('social_studies_achievement', 'Social studies', 'Students passing the civics or U.S. History exam'),
              ('middle_acceleration', 'Advanced courses', 'Middle schoolers passing high school courses or industry certifications'),
              ('graduation_rate', 'Graduation rate', 'Students graduating within four years (from the year before)'),
              ('college_career_acceleration', 'College credit', 'Graduates who passed AP, IB, dual enrollment or an industry certification (from the year before)')]


def _scores(g, prev, st):
    """The parts of one school's grade: a bar per component with a mark for the state average of that school type."""
    rows = ''
    for key, label, tip in COMPONENTS:
        v = g.get(key)
        if v is None:
            continue
        sv = (st or {}).get(key)
        pv = (prev or {}).get(key)
        ch = ''
        if pv is not None:
            d = round(v - pv)
            ch = f'<span class="ch {"up" if d > 0 else "dn" if d < 0 else ""}" title="Change from the year before">{"+" if d > 0 else ""}{d}</span>' if d else '<span class="ch" title="Same as the year before">±0</span>'
        mark = f'<b class="st" style="left:{min(100, sv):.0f}%" title="Florida average {sv:.0f}%"></b>' if sv is not None else ''
        rows += (f'<div class="sc-cp" title="{e(tip)}"><span class="lb">{e(label)}</span><span class="tr"><i style="width:{min(100, v):.0f}%"></i>{mark}</span>'
                 f'<span class="v">{v:.0f}%</span>{ch}</div>')
    if not rows:
        return ''
    pts = g.get('percent_of_points')
    head = f'Scores behind the {e(g["school_year"])} grade' + (f': {pts:.0f}% of possible points' if pts is not None else '')
    stl = f'{st["school_type"].lower()} school' if st and st['school_type'] != 'All' else 'school'
    return (f'<div><div class="muted small" style="margin-bottom:6px">{head}</div><div class="sc-cps">{rows}</div>'
            f'<div class="sc-key"><span><i></i>This school</span><span><b></b>Florida {e(stl)} average</span>'
            + ('<span>+/− change from the year before</span>' if prev else '') + '</div></div>')


def _t(hhmm):
    """'13:50' -> '1:50 p.m.'"""
    if not hhmm:
        return ''
    h, m = map(int, hhmm.split(':'))
    return f"{(h - 1) % 12 + 1}:{m:02d} {'a.m.' if h < 12 else 'p.m.'}"


def _hours(rows):
    """One school's day: '7:30 a.m. to 2:00 p.m.', or one line per grade band."""
    if not rows:
        return ''
    if len(rows) == 1 and not rows[0].get('part'):
        r = rows[0]
        return f"{_t(r['start_time'])} to {_t(r['end_time'])}" + (f" ({e(r['note'])})" if r.get('note') else '')
    return '; '.join(f"{e(r['part'] or '')}: {_t(r['start_time'])} to {_t(r['end_time'])}" + (f" ({e(r['note'])})" if r.get('note') else '') for r in rows)


def _where(s):
    """The school's address as a map link and its phone as a tap-to-call link."""
    import re, urllib.parse
    addr = ', '.join(x for x in (s.get('address'), s.get('city')) if x)
    out = []
    if addr:
        q = urllib.parse.quote(f"{s['name']}, {addr}, FL {s.get('zip') or ''}".strip())
        out.append(f'<a href="https://www.google.com/maps/search/?api=1&amp;query={q}" target="_blank" rel="noopener">{e(addr)}</a>')
    d = re.sub(r'\D', '', s.get('phone') or '')[-10:]
    if len(d) == 10:
        out.append(f'<a href="tel:+1{d}" style="white-space:nowrap">({d[:3]}) {d[3:6]}-{d[6:]}</a>')
    elif s.get('phone'):
        out.append(e(s['phone']))
    return ' · '.join(out)


def _mix(counts, label):
    n = sum(counts.values()) or 1
    segs = ''.join(f'<i class="g-{c}" style="width:{100 * counts.get(c, 0) / n:.2f}%" title="{c}: {counts.get(c, 0)} ({100 * counts.get(c, 0) / n:.0f}%)">{f"{c} {100 * counts.get(c, 0) / n:.0f}%" if counts.get(c, 0) / n >= .08 else ""}</i>'
                   for c in 'ABCDF')
    return f'<div class="sc-mix"><span class="lb">{label}</span><span class="tr">{segs}</span></div>'


def schools_page(out_dir):
    from page_datasets import schools, school_grades, school_grade_state, school_bell_times, school_spending, school_enrollment, school_calendar, school_zones
    S, G, SP, EN, CAL, Z = schools(), school_grades(), school_spending(), school_enrollment(), school_calendar(), school_zones()
    GS = {(r['year'], r['school_type']): r for r in school_grade_state()}
    BT = school_bell_times()
    bell_by = {}
    for r in BT:
        if r['kind'] == 'school day' and r['school_id']:
            bell_by.setdefault(r['school_id'], []).append(r)
    early = [r for r in BT if r['kind'] == 'early release']
    bell_year = next((r['school_year'] for r in BT), '')
    conf = PLACE.get('schools') or {}
    if not S:
        return '<div class="page"><h1>Public schools</h1><p>No school data for this place yet.</p></div>'
    gov = next((g for g in governments() if g['key'] == conf.get('district_gov')), None)
    district = conf.get('district_name') or (gov or {}).get('short') or 'the school district'
    gov_url = f"/governments/{gov['slug']}" if gov else '/governments'
    ents = build().ents
    open_s = [s for s in S if s['status'] == 'Open']
    closed = [s for s in S if s['status'] != 'Open']
    by_id = {s['school_id']: s for s in S}
    today = dt.date.today()
    year_label = open_s[0]['enrollment_year'] if open_s else ''
    students = sum(s['enrollment'] or 0 for s in open_s)
    n_charter = sum(1 for s in open_s if s['charter'])

    grades_by = {}
    for g in G:
        grades_by.setdefault(g['school_id'], {})[g['year']] = g
    grade_years = sorted({g['year'] for g in G})
    latest_gy = grade_years[-1] if grade_years else None
    spend_by = {}
    for x in SP:
        spend_by.setdefault(x['school_id'], {})[x['year']] = x
    spend_years = sorted({x['year'] for x in SP if x.get('total_per_student')})
    latest_sy = spend_years[-1] if spend_years else None
    enr_by = {}
    for r in EN:
        enr_by.setdefault(r['school_id'], []).append((r['year'], r['enrollment']))

    # --- KPIs
    upcoming = [c for c in CAL if (_d(c.get('ends')) or _d(c['starts']) or today) >= today]
    next_off = next((c for c in upcoming if c['kind'] in ('no-school', 'break') and _d(c['starts']) and _d(c['starts']) >= today), None)
    k = lambda lab, v, s: f'<div class="kpi"><span class="eyebrow">{lab}</span><span class="v">{v}</span><span class="s">{s}</span></div>'
    if latest_gy:
        gl = [grades_by[s['school_id']][latest_gy]['grade'] for s in open_s if latest_gy in grades_by.get(s['school_id'], {})]
        kpi_grade = k(f'A schools, {latest_gy - 1}-{str(latest_gy)[2:]}', sum(1 for x in gl if x == 'A'), f'of {len(gl)} graded. {sum(1 for x in gl if x == "B")} B, {sum(1 for x in gl if x == "C")} C, {sum(1 for x in gl if x in ("D", "F"))} D or F')
    else:
        kpi_grade = k('State school grades', '—', 'Being added from the Florida Department of Education')
    kpis = (k('Public schools', len(open_s), f'{len(open_s) - n_charter} run by the district, {n_charter} charter schools') +
            k(f'Students, {year_label}', f'{students:,}', 'Enrolled in the fall, from the federal school directory') +
            kpi_grade +
            k('Next day off', next_off['starts'] and _d(next_off['starts']).strftime('%b %-d') if next_off else '—', e(next_off['title']) if next_off else 'See the district calendar'))

    # --- calendar
    cal_cards = []
    for c in upcoming:
        d = _d(c['starts'])
        if not d:
            continue
        kk = c['kind'] + (' off' if c['kind'] in ('no-school', 'break') else ' milestones' if c['kind'] in ('grading', 'graduation', 'first-day', 'last-day', 'early-release') else '')
        cal_cards.append(f'<div class="ui-mc" data-k="{e(kk)}">{_tile(d)}<div style="min-width:0"><b>{e(c["title"])}</b><small>{e(_when(c))}</small>'
                         + (f'<small>{e(_venue(c))}</small>' if c.get('venue') else '') +
                         f'<span class="sc-pill k-{e(c["kind"])}">{e(KIND_LABEL.get(c["kind"], "District event"))}</span></div></div>')
    cal_err = ''

    # --- school cards
    cards = []
    for s in sorted(open_s, key=lambda s: (LEVEL_ORDER.index(s['level']) if s['level'] in LEVEL_ORDER else 9, s['name'])):
        sid = s['school_id']
        gh = grades_by.get(sid, {})
        last = gh.get(latest_gy) if latest_gy else None
        lg = last['grade'] if last else None
        sub = [x for x in [s['level'] if s['level'] != 'Other' else s['school_type'], f"grades {s['grades']}" if s.get('grades') else '', s.get('city')] if x]
        tags = [s['level'].lower()] + (['charter'] if s['charter'] else ['district']) + (['zoned'] if s.get('zoned_levels') else [])
        op = s.get('operator_entity_id')
        op_html = f'<p style="margin:0">Charter school run by {link(op, ents[op]["name"])}, a nonprofit. Authorized and overseen by {e(district)}.</p>' if op and op in ents else (
            f'<p style="margin:0">Charter school, authorized and overseen by {e(district)}.</p>' if s['charter'] else '')
        hist = ''.join(f'<span>{_g(gh[y]["grade"], True, f"{y - 1}-{str(y)[2:]}")}{y}</span>' for y in sorted(gh))
        sp = spend_by.get(sid, {})
        sp_last = sp.get(latest_sy) if latest_sy else None
        enr = sorted(enr_by.get(sid, []))
        facts = [('Students', f"{s['enrollment']:,}" if s.get('enrollment') else '—'),
                 ('Per teacher', s.get('students_per_teacher') or '—'),
                 (f"Spent per student{', ' + str(latest_sy - 1) + '-' + str(latest_sy)[2:] if sp_last else ''}", _money(sp_last['total_per_student']) if sp_last and sp_last.get('total_per_student') else '—')]
        zoned = f"Attendance zone for {s['zoned_levels'].lower()} school students." if s.get('zoned_levels') else ('Open to students across the county by application.' if s['charter'] or s['school_type'] != 'Regular' else '')
        cards.append(f'''<details class="sc-s" id="s-{e(sid)}" data-f="{e(" ".join(tags))}" data-t="{e((s["name"] + " " + (s.get("city") or "")).lower())}">
  <summary>{_g(lg, title=f"State grade {latest_gy - 1}-{str(latest_gy)[2:]}" if lg else "") or '<span class="sc-g" title="No grade on file">–</span>'}<span class="nm"><b>{e(s["name"])}</b><small>{e(" · ".join(sub))}{" · Charter" if s["charter"] else ""}</small></span></summary>
  <div class="bd">
    <dl class="sc-facts">{"".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in facts)}</dl>
    {f'<div><div class="muted small" style="margin-bottom:4px">State grades</div><div class="sc-hist">{hist}</div></div>' if hist else ''}
    {_scores(last, gh.get(latest_gy - 1), GS.get((latest_gy, last.get('school_type') or 'All')) or GS.get((latest_gy, 'All'))) if last else ''}
    {f'<div><div class="muted small">Enrollment, {enr[0][0] - 1}-{str(enr[0][0])[2:]} to {enr[-1][0] - 1}-{str(enr[-1][0])[2:]}: {enr[0][1]:,} to {enr[-1][1]:,}</div>{_spark(enr)}</div>' if len(enr) > 1 else ''}
    {op_html}
    {f'<p class="sc-hrs"><b>School day {e(bell_year)}</b> {_hours(bell_by[sid])}</p>' if bell_by.get(sid) else ''}
    <p style="margin:0">{_where(s)}{(" · " + e(zoned)) if zoned else ""}{f" · {s['free_reduced_lunch_pct']:.0f}% of students qualify for free or reduced-price lunch" if s.get("free_reduced_lunch_pct") else ""}</p>
  </div>
</details>''')
    lv_chips = ''.join(f'<button type="button" class="chip" data-v="{v}" aria-pressed="false">{t}</button>' for v, t in
                       [('elementary', 'Elementary'), ('middle', 'Middle'), ('high', 'High'), ('combined', 'K-8 and K-12'), ('charter', 'Charter'), ('other', 'Other programs')]
                       if v in ('charter',) or any(s['level'].lower() == v for s in open_s))

    # --- grades matrix
    if grade_years:
        show_years = [y for y in range(max(grade_years[0], 2016), latest_gy + 1)]
        mx_rows = ''
        for s in sorted((s for s in S if s['school_id'] in grades_by), key=lambda s: (s['status'] != 'Open', s['name'])):
            gh = grades_by[s['school_id']]
            cells = ''.join(f'<td>{_g(gh[y]["grade"], True)}</td>' if y in gh else '<td class="na">·</td>' for y in show_years)
            mx_rows += f'<tr><td><a href="#s-{e(s["school_id"])}">{e(s["name"])}</a>{" <span class=muted>(closed)</span>" if s["status"] != "Open" else ""}</td>{cells}</tr>'
        bay = {}
        for g in G:
            if g['year'] == latest_gy and g['grade'] in 'ABCDF':
                bay[g['grade']] = bay.get(g['grade'], 0) + 1
        fl = GS.get((latest_gy, 'All'))
        mix = ''
        if fl:
            flc = {c.upper(): fl[f'grade_{c}'] for c in 'abcdf'}
            pa, fa = 100 * bay.get('A', 0) / max(1, sum(bay.values())), 100 * flc['A'] / max(1, sum(flc.values()))
            mix = (f'<p>In {latest_gy - 1}-{str(latest_gy)[2:]}, <b>{pa:.0f}%</b> of {e(PLACE["name"])}\'s graded public schools earned an A, compared with <b>{fa:.0f}%</b> of schools statewide. '
                   'Open a school under Every school to see the test scores behind its grade next to the Florida average.</p>'
                   f'<div class="sc-mixes">{_mix(bay, e(PLACE["name"]) + f" <small>{sum(bay.values())} schools</small>")}{_mix(flc, f"Florida <small>{sum(flc.values()):,} schools</small>")}</div>')
        grades_html = mix + (f'<div class="tablewrap"><table class="tx-table sc-mx" data-tt="off" data-stack="off"><thead><tr><th>School</th>{"".join(f"<th>{y - 1}-{str(y)[2:]}</th>" for y in show_years)}</tr></thead><tbody>{mx_rows}</tbody></table></div>'
                       '<p class="note">No school grades were given for 2019-20, when state testing was canceled. For 2020-21, only schools that asked got a grade. 2022-23 grades were an informational baseline after the state changed its tests. A dot means no grade that year (the school was new, closed, or isn\'t graded, like virtual and alternative programs).</p>')
    else:
        grades_html = ('<div class="sc-pend">The Florida Department of Education publishes every school\'s grade each July. Its website turns away the automated readers this site uses, '
                       'so the grade files are being added by hand. Until then, each school\'s grades are on the state\'s <a href="https://edudata.fldoe.org/" rel="noopener" target="_blank">Know Your Schools</a> report cards.</div>')

    # --- spending
    if latest_sy:
        rows = sorted((x for x in SP if x['year'] == latest_sy and x.get('total_per_student') and by_id.get(x['school_id'], {}).get('status') == 'Open'), key=lambda x: -x['total_per_student'])
        top = rows[0]['total_per_student'] if rows else 1
        avg = sum(x['estimated_total'] or 0 for x in rows) / max(1, sum(x['enrollment'] or 0 for x in rows if x['estimated_total']))
        bars = ''.join(f'<div class="sc-bar"><a href="#s-{e(x["school_id"])}" title="{e(x["school"])}">{e(x["school"])}</a><span class="tr"><i style="width:{100 * x["total_per_student"] / top:.1f}%"></i></span><span class="v">{_money(x["total_per_student"])}</span></div>' for x in rows)
        spend_html = (f'<p>What each school spent per student in {latest_sy - 1}-{str(latest_sy)[2:]}, counting federal, state and local money. Across these schools the average was about <b>{_money(avg)}</b> per student. '
                      'Schools for students with disabilities, alternative schools and small schools cost more per student; schools with more students from low-income families get more federal money.</p>'
                      f'<div class="sc-bars">{bars}</div>')
    else:
        spend_html = ('<div class="sc-pend">Per-school spending comes from the Florida Department of Education\'s yearly per-pupil expenditure reports (required by the federal Every Student Succeeds Act). '
                      f'Like the grades, those files are being added by hand. The district\'s overall budget is on the <a href="{gov_url}">{e(district)} page</a>.</div>')

    # --- district enrollment by year
    tot = {}
    for r in EN:
        tot[r['year']] = tot.get(r['year'], 0) + r['enrollment']
    ys = sorted(tot)
    hi = max(tot.values()) if tot else 1
    enr_bars = ''.join(f'<div><b>{tot[y] / 1000:.1f}K</b><i class="{"low" if y in (2020, 2021) else ""}" style="height:{max(4, 130 * tot[y] / hi):.0f}px"></i><small>{y - 1}-{str(y)[2:]}</small></div>' for y in ys)
    drop = ''
    if 2019 in tot and 2020 in tot:
        drop = f' Enrollment fell by about {tot[2019] - tot[2020]:,} students in the school year after Hurricane Michael (October 2018), and several schools closed or merged.'

    # --- closed schools
    closed_rows = ''.join(f'<tr><td>{e(s["name"])}</td><td>{e(s.get("last_year_open") or "")}</td><td>{e(s.get("city") or "")}</td></tr>'
                          for s in sorted(closed, key=lambda s: (s.get('last_year_open') or '', s['name'])))

    # --- board meetings
    board = [c for c in upcoming if c['kind'] == 'board-meeting'][:3]
    board_html = ''.join(f'<li><b>{e(_when(c))}</b> · {e(c["title"])}{(" · " + e(_venue(c))) if c.get("venue") else ""}</li>' for c in board)
    zone_date = max((z['last_edited'] or '' for z in Z), default='')

    js_s = {s['school_id']: {'name': s['name'], 'g': s.get('grades'), 'n': s.get('enrollment'), 'gr': s.get('latest_grade'), 'gy': s.get('latest_grade_year'),
                             'lat': s.get('latitude'), 'lon': s.get('longitude'), 'lv': s['level'], 'ch': bool(s['charter']), 'ty': s['school_type'],
                             'city': s.get('city'), 'hrs': re.sub('<[^>]+>', '', _hours(bell_by.get(s['school_id'], [])))} for s in open_s}
    early_html = (f'<p class="note">Early release days ({e(bell_year)}): ' + ', '.join(f"{e(r['part'].lower())} let out at {_t(r['end_time'])}" for r in early) +
                  f'. Times are from the district\'s <a href="{e(BT[0]["source_url"])}" rel="noopener" target="_blank">start and end times chart</a>.</p>') if early else ''
    import json
    js = JS.replace('__SCHOOLS__', json.dumps(js_s, separators=(',', ':')))
    return f'''<style>{CSS}</style>{LEAFLET}
<div class="page tax sc">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Governments · {e(district)}</span><h1>Public schools</h1>
    <p class="lede">Find the schools zoned for your address, see what's coming up on the school calendar, and compare every public school in {e(PLACE["name"])}: grades, students, spending and how each has changed since 2016.</p></div>
    <div class="stamp"><a class="pill" href="{gov_url}">{e(district)}: budget, board and votes →</a><span>School list from the {e(year_label)} federal school directory</span></div></header>
  <div class="kpis">{kpis}</div>

  <section class="tx-sec"><div class="sec-hd"><h2 id="zoned" data-tile="Your schools">Which schools serve your address</h2><span class="muted">Attendance zones as of {e(zone_date)}</span></div>
    <div class="sc-find">
      <div class="sc-box"><h3>Type your street address</h3><p>We look it up in the county's address list and check it against {e(district)}' attendance zones.</p>
        <div class="sc-ac"><input id="scAddr" type="text" inputmode="text" autocomplete="off" placeholder="e.g. 1200 Harrison Ave" aria-label="Street address" aria-controls="scList" aria-autocomplete="list"><ul id="scList" role="listbox" hidden></ul></div>
        <p class="small muted" style="margin:10px 0 0">Choice, magnet, charter and virtual schools take students from anywhere in the county. Confirm with the district before you enroll.</p></div>
      <div class="sc-box"><h3>Zoned schools</h3><div class="sc-res" id="scOut" hidden></div><p class="muted small" id="scHint">Pick an address to see its elementary, middle and high school.</p></div>
    </div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="map" data-tile="Map">Map of every school</h2><span class="muted">Colored by the latest state grade</span></div>
    <div class="sc-ctl"><div class="chips" id="scMapLv" role="group" aria-label="Kind of school"><button type="button" class="chip" data-v="" aria-pressed="true">All</button><button type="button" class="chip" data-v="Elementary" aria-pressed="false">Elementary</button><button type="button" class="chip" data-v="Middle" aria-pressed="false">Middle</button><button type="button" class="chip" data-v="High" aria-pressed="false">High</button><button type="button" class="chip" data-v="charter" aria-pressed="false">Charter</button></div>
      <label class="sc-zsel">Zones <select id="scMapZ" aria-label="Show attendance zones"><option value="">Off</option><option value="Elementary">Elementary</option><option value="Middle">Middle</option><option value="High">High</option></select></label></div>
    <div class="sc-map" id="scMap" role="img" aria-label="Map of {len(open_s)} public schools in {e(PLACE["name"])}, colored by state grade"></div>
    <div class="sc-mkey"><span><i class="g-A"></i>A</span><span><i class="g-B"></i>B</span><span><i class="g-C"></i>C</span><span><i class="g-D"></i>D or F</span><span><i></i>No grade</span><span><i class="ch"></i>Ring = charter</span></div>
    <p class="note">Tap a dot for the school's grade, hours and details. Turn on zones to see which area each school serves. Virtual programs and schools without an address on file aren't shown.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="calendar" data-tile="Calendar">School calendar</h2><span class="muted">From the <a href="{e(conf.get("calendar_page") or "#")}" rel="noopener" target="_blank">district's calendar</a>, checked daily</span></div>
    <div class="sc-ctl"><div class="chips" id="scCalK" role="group" aria-label="Kind of date"><button type="button" class="chip" data-v="" aria-pressed="true">Everything</button><button type="button" class="chip" data-v="off" aria-pressed="false">Days off</button><button type="button" class="chip" data-v="milestones" aria-pressed="false">Grading and graduation</button><button type="button" class="chip" data-v="board-meeting" aria-pressed="false">School Board</button></div></div>
    <div class="sc-cal" id="scCal">{"".join(cal_cards) or '<p class="muted">No upcoming dates posted.</p>'}</div>
    <div><button type="button" class="ui-btn" id="scCalMore" hidden style="width:auto;border:0;cursor:pointer;font-family:inherit">Show more</button></div>{cal_err}</section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="schools" data-tile="Every school">Every public school</h2><span class="muted">{len(open_s)} schools · tap one for its details</span></div>
    <div class="sc-ctl"><div class="chips" id="scLv" role="group" aria-label="Kind of school"><button type="button" class="chip" data-v="" aria-pressed="true">All</button>{lv_chips}</div><input type="search" id="scQ" placeholder="Find a school or city" aria-label="Find a school"></div>
    <div class="sc-list" id="scSchools">{"".join(cards)}</div>
    <p class="note" id="scNone" hidden>No school matches.</p>
    <p class="note">The letter is the school's latest Florida school grade. Students and teachers are from the {e(year_label)} federal school directory; "per teacher" divides students by full-time teachers.</p>{early_html}</section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="grades" data-tile="Grades">School grades since 2016</h2><span class="muted">Florida Department of Education</span></div>
    {grades_html}</section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="spending" data-tile="Spending">Spending per school</h2><span class="muted">Per-pupil expenditure reports</span></div>
    {spend_html}</section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="enrollment" data-tile="Students">Students by year</h2><span class="muted">Every public school, fall enrollment</span></div>
    <div class="sc-enr" role="img" aria-label="District enrollment by school year">{enr_bars}</div>
    <p class="note">Total of every public school's fall enrollment, district and charter, from the federal school directory.{drop}</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="closed" data-tile="Closed">Schools closed since 2016</h2><span class="muted">{len(closed)} schools</span></div>
    <div class="tablewrap"><table class="tx-table" data-tt-year="off"><thead><tr><th>School</th><th>Last school year listed</th><th>City</th></tr></thead><tbody>{closed_rows or '<tr><td colspan="3" class="muted">None.</td></tr>'}</tbody></table></div>
    <p class="note">From the federal school directory: the last year each school appears. Some were merged into another school or renamed rather than closed.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="board" data-tile="School Board">Who runs the schools</h2></div>
    <p>{e(district)} is run by an elected five-member School Board and an elected superintendent. The board sets the school tax rate (most of it is set by the state), adopts the budget and approves contracts.</p>
    {f'<ul class="plain">{board_html}</ul>' if board_html else ''}
    <p><a href="{gov_url}">Budget, debt and audits →</a> · <a href="/people?gov=schools">Board members and leaders →</a> · <a href="/public-money/votes?gov=schools">How the board voted →</a> · <a href="/meetings?gov=schools">Meetings and agendas →</a></p></section>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>Schools, students and teachers</b>: the U.S. Department of Education's Common Core of Data school directory, read through the Urban Institute's Education Data API, every year since 2015-16. Updated weekly; the federal directory runs about a year behind.</li>
      <li><b>Attendance zones</b>: {e(district)}' zones as published on Bay County's GIS server, checked weekly. Shapes are simplified slightly, so an address right on a zone line can come out on the wrong side; the district has the final word.</li>
      <li><b>Calendar</b>: the events feed on the district's website, read every day. Past dates of the school year stay listed.</li>
      <li><b>Grades and spending</b>: the Florida Department of Education's school grades files and its per-pupil expenditure reports, read by hand when the state publishes them.</li>
      <li><b>Data:</b> {" · ".join(f'<a href="/api/v1/datasets/{d}">{d}</a> (<a href="/downloads/{d}.csv">CSV</a>)' for d in ("schools", "school-grades", "school-spending", "school-enrollment", "school-calendar", "school-zones"))} · zoned schools for any address: <a href="/api/v1/schools?address=1200%20Harrison%20Ave">/api/v1/schools</a>.</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>{js}</script><script>{MAP_JS.replace('__SCHOOLS__', json.dumps(js_s, separators=(',', ':')))}</script>'''
