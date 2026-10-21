(() => {
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const big = n => n == null ? '' : n >= 1e6 ? '$' + (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? '$' + Math.round(n / 1e3) + 'K' : '$' + Math.round(n);
const ST = {completed: ['Completed', '#1F7A4D'], in_progress: ['In progress', 'var(--blue)'], not_started: ['Not started', 'var(--faint)'], unknown: ['Unknown', 'var(--faint)']};
let P = [], G = null, cur = [], sel = null, base = null;
const U0 = new URLSearchParams(location.search); // read before anything rewrites the link
const W = 400, H = 300, k = Math.cos(30.2 * Math.PI / 180);
const HOME = {x: -85.66, y: 30.25, span: 0.62}, NEAR = 0.16;   // NEAR ~ 11 miles tall: keeps coastline and towns in view
let view = {...HOME};
// Water labels for orientation (approximate centers)
// [name, lng, lat, show when the view is at most this tall]
const WATER = [['Gulf of Mexico', -85.80, 30.06, 9], ['West Bay', -85.86, 30.285, 9], ['East Bay', -85.50, 30.075, 9], ['St. Andrew Bay', -85.70, 30.135, 0.35], ['North Bay', -85.655, 30.215, 0.35], ['Deer Point Lake', -85.61, 30.30, 0.35]];
const MAJOR = new Set(['Panama City', 'Panama City Beach', 'Lynn Haven', 'Mexico Beach']);
function proj([x, y]) { const sx = view.span * W / H / k; return [(x - (view.x - sx / 2)) / sx * W, ((view.y + view.span / 2) - y) / view.span * H]; }
const inView = ([x, y], m = 0) => x > -m && x < W + m && y > -m && y < H + m;
function centroid(mp) { // center of the largest polygon's bounding box
  let best = null, area = -1;
  mp.forEach(poly => { const r = poly[0]; const xs = r.map(p => p[0]), ys = r.map(p => p[1]); const a = (Math.max(...xs) - Math.min(...xs)) * (Math.max(...ys) - Math.min(...ys)); if (a > area) { area = a; best = [(Math.max(...xs) + Math.min(...xs)) / 2, (Math.max(...ys) + Math.min(...ys)) / 2]; } });
  return best;
}
const GIS = 'https://services1.arcgis.com/QB0VWfqR9MD4lF0F/arcgis/rest/services/Surtax_Projects/FeatureServer/';
const recURL = p => !p.r ? 'https://bayhalfcent.com/' : GIS + p.r[0] + '/query?where=' + (p.r[0] === 0 ? 'OBJECTID%3D' + p.r[1][0] : 'OBJECTID+IN+(' + p.r[1].join(',') + ')') + '&outFields=*&outSR=4326&f=json';
const dotA = p => `tabindex="0" role="button" aria-label="${esc(p.n)}, ${esc(p.g)}, ${esc(ST[p.s]?.[0] || p.s)}${p.k ? ', ' + big(p.k) : ''}"`;
let refocus = null; // keep keyboard focus on a dot after the map redraws
let fs = 1; // text scale so labels stay readable when the map is drawn small (phones)
const label = (t, x, y, cls) => `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" class="${cls}" text-anchor="middle" style="font-size:${(cls === 'st-wl' ? 9 : 8.5) * fs}px">${esc(t)}</text>`;
function draw() {
  const svg = $('stMap'); fs = Math.min(1.7, Math.max(1, 420 / (svg.clientWidth || 420))); const path = mp => mp.map(poly => poly.map(ring => 'M' + ring.map(p => proj(p).map(v => v.toFixed(1)).join(',')).join('L') + 'Z').join('')).join('');
  const sw = Math.max(.5, Math.min(1.4, .3 / view.span));
  let s = `<rect width="${W}" height="${H}" fill="var(--water)"/>`;
  if (G) {
    s += `<path d="${path(G.land)}" fill="var(--land)" stroke="var(--landline)" stroke-width="${sw}"/>`;
    Object.values(G.cities).forEach(g => s += `<path d="${path(g)}" fill="var(--city)" stroke="var(--cityline)" stroke-width="${sw * .8}"/>`);
  }
  // water + city labels, drawn above the dots
  let L = '';
  WATER.forEach(([t, x, y, minSpan]) => { const p = proj([x, y]); if (view.span <= minSpan && inView(p, -10)) L += label(t, p[0], p[1], 'st-wl'); });
  if (G) Object.entries(G.cities).forEach(([n, g]) => { if (view.span > 0.35 && !MAJOR.has(n)) return; const c = centroid(g); if (!c) return; const p = proj(c); if (inView(p, -12)) L += label(n, p[0], p[1], 'st-cl'); });
  const r = Math.max(2.2, Math.min(4.5, 1.4 / view.span)), on = sel != null;
  ['not_started', 'unknown', 'in_progress', 'completed'].forEach(st => cur.filter(p => p.s === st && p !== sel).forEach(p => { const [x, y] = proj([p.x, p.yy]); if (!inView([x, y], 5)) return;
    s += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r}" fill="${ST[p.s]?.[1] || 'var(--faint)'}" stroke="var(--surface)" stroke-width=".8" data-i="${p._i}" opacity="${on ? .35 : 1}" ${dotA(p)}/>`; }));
  s += L;
  if (on) { // selected project: halo, ring, label with backing
    const [x, y] = proj([sel.x, sel.yy]), col = ST[sel.s]?.[1] || 'var(--faint)';
    const cw = 6.9 * fs, fit = n => sel.n.length <= n ? sel.n : sel.n.slice(0, Math.max(8, n - 1)).trimEnd() + '…';
    const roomR = W - x - 21, roomL = x - 21, right = roomR >= roomL || roomR >= sel.n.length * cw;
    const t = fit(Math.floor((right ? roomR : roomL) / cw));
    s += `<circle cx="${x}" cy="${y}" r="16" fill="${col}" opacity=".18"/><circle cx="${x}" cy="${y}" r="7.5" fill="${col}" stroke="var(--surface)" stroke-width="2.2" data-i="${sel._i}" ${dotA(sel)} aria-pressed="true"/><circle cx="${x}" cy="${y}" r="10.5" fill="none" stroke="var(--ink)" stroke-width="1.2"/>`;
    s += `<text x="${(right ? x + 15 : x - 15).toFixed(1)}" y="${(y + 4).toFixed(1)}" class="st-sl" text-anchor="${right ? 'start' : 'end'}" style="font-size:${10 * fs}px">${esc(t)}</text>`;
  }
  const hadFocus = svg.contains(document.activeElement) ? document.activeElement.dataset.i : null;
  svg.innerHTML = s;
  const fi = refocus != null ? refocus : hadFocus; refocus = null;
  if (fi != null) { const c = svg.querySelector(`circle[data-i="${fi}"][tabindex]`); if (c) c.focus({preventScroll: true}); }
  $('stAll').hidden = view.span === base?.span && view.x === base?.x && view.y === base?.y && !sel;
}
function fitView() {
  const g = $('stG').value;
  if (g) { const pts = cur.length ? cur : P.filter(p => p.g === g); const xs = pts.map(p => p.x), ys = pts.map(p => p.yy);
    return {x: (Math.min(...xs) + Math.max(...xs)) / 2, y: (Math.min(...ys) + Math.max(...ys)) / 2, span: Math.max(NEAR, (Math.max(...ys) - Math.min(...ys)) * 1.3, (Math.max(...xs) - Math.min(...xs)) * k * H / W * 1.3)}; }
  return {...HOME};
}
function filt() {
  const q = $('stQ').value.trim().toLowerCase(), g = $('stG').value, c = $('stC').value, st = $('stS').value;
  cur = P.filter(p => (!g || p.g === g) && (!c || p.c === c) && (!st || p.s === st) && (!q || (p.n + ' ' + p.d).toLowerCase().includes(q)));
  const n = s => cur.filter(p => p.s === s).length;
  $('stCount').textContent = `${cur.length.toLocaleString()} projects · ${n('completed')} completed, ${n('in_progress')} in progress, ${n('not_started')} not started`;
  $('stList').innerHTML = cur.slice(0, 200).map(p => `<li data-i="${p._i}" tabindex="0" role="button"${p === sel ? ' class="on" aria-current="true"' : ''}><span class="st-dot" style="background:${ST[p.s]?.[1]}"></span><div><b>${esc(p.n)}</b><span class="muted small">${esc(p.g)} · ${esc(p.c)} · ${esc(ST[p.s]?.[0] || p.s)}${p.p != null && p.s === 'in_progress' ? ` (${p.p}%)` : ''}${p.k ? ' · ' + big(p.k) : ''}</span></div></li>`).join('') + (cur.length > 200 ? `<li class="muted small">Showing 200 of ${cur.length}. Narrow the filters to see more.</li>` : '');
  if (sel && !cur.includes(sel)) clearSel(false);
  base = fitView(); if (!sel) view = {...base};
  draw();
}
function select(p, from) {
  sel = p; view = {x: p.x, y: p.yy, span: Math.min(NEAR, view.span < NEAR ? NEAR : NEAR)};
  if (window.BCM && p.id) BCM.urlState.set({p: p.id});
  const st = ST[p.s] || ['Unknown', 'var(--faint)'];
  $('stSel').hidden = false;
  $('stSel').innerHTML = `<div class="st-sel-hd"><span class="st-dot" style="background:${st[1]}"></span><div><b>${esc(p.n)}</b><span class="muted small">${esc(p.g)} · ${esc(p.c)}${p.y ? ' · ' + esc(p.y) : ''}</span></div><button type="button" class="st-x print-hide" aria-label="Close project details">×</button></div>
    <p class="st-meta"><span class="badge ${p.s === 'completed' ? 'ok' : ''}">${esc(st[0])}${p.p != null && p.s !== 'completed' ? ' · ' + p.p + '%' : ''}</span>${p.k ? ` <span class="small">Cost <b>${big(p.k)}</b></span>` : ''}</p>
    ${p.d ? `<p class="small">${esc(p.d.trim())}${/[.!?]$/.test(p.d.trim()) ? '' : '…'}</p>` : ''}
    <p class="small">Source: <a class="src" href="${esc(recURL(p))}" target="_blank" rel="noopener">county GIS record</a>${p.w ? ` · <a class="src" href="${esc(p.w)}" target="_blank" rel="noopener" title="The web page or document the county's map links for this project">county's linked document</a>` : ''}</p>
    <p class="small"><a href="https://www.google.com/maps/search/?api=1&query=${p.yy},${p.x}" target="_blank" rel="noopener">See the location in Google Maps</a>${/road|street|blvd|avenue|ave\b|drive|dr\b|highway|hwy|sidewalk|trail|bridge|paving|resurfac/i.test(p.n + ' ' + p.c) ? ' <span class="muted">· road projects are pinned at the middle of the segment</span>' : ''}</p>`;
  document.querySelectorAll('#stList li.on').forEach(x => { x.classList.remove('on'); x.removeAttribute('aria-current'); });
  const li = document.querySelector(`#stList li[data-i="${p._i}"]`);
  if (li) { li.classList.add('on'); li.setAttribute('aria-current', 'true'); if (from === 'map') li.scrollIntoView({block: 'nearest'}); }
  draw();
  if (from === 'list' && matchMedia('(max-width:900px)').matches) document.querySelector('.st-mapbox').scrollIntoView({behavior: 'smooth', block: 'start'});
}
function clearSel(redraw = true) {
  sel = null; $('stSel').hidden = true; $('stSel').innerHTML = '';
  if (window.BCM) BCM.urlState.set({p: ''});
  document.querySelectorAll('#stList li.on').forEach(x => { x.classList.remove('on'); x.removeAttribute('aria-current'); });
  if (redraw) { view = {...base}; draw(); }
}
const zoom = f => { view = {...view, span: Math.min(HOME.span * 1.2, Math.max(0.02, view.span * f))}; draw(); };
$('stIn').addEventListener('click', () => zoom(0.6));
$('stOut').addEventListener('click', () => zoom(1.6));
$('stAll').addEventListener('click', () => clearSel());
$('stSel').addEventListener('click', e => { if (e.target.closest('.st-x')) clearSel(); });
const tt = $('tt');
$('stMap').addEventListener('pointermove', e => { const c = e.target.closest('circle[data-i]'); if (!c || e.pointerType !== 'mouse') { tt.hidden = true; return; } const p = P[+c.dataset.i];
  tt.innerHTML = `<b>${esc(p.n)}</b><br>${esc(p.g)} · ${esc(p.c)}<br>${esc(ST[p.s]?.[0])}${p.k ? ' · ' + big(p.k) : ''}<br><span class="muted">Click for details</span>`; tt.hidden = false; tt.style.left = Math.min(e.clientX + 14, innerWidth - 290) + 'px'; tt.style.top = (e.clientY + 14) + 'px'; });
$('stMap').addEventListener('pointerleave', () => tt.hidden = true);
$('stMap').addEventListener('click', e => { const c = e.target.closest('circle[data-i]'); if (c) { tt.hidden = true; select(P[+c.dataset.i], 'map'); } });
$('stMap').addEventListener('keydown', e => { const c = e.target.closest && e.target.closest('circle[data-i]'); if (!c || (e.key !== 'Enter' && e.key !== ' ')) return;
  e.preventDefault(); const p = P[+c.dataset.i]; refocus = p._i; if (p === sel) clearSel(); else select(p, 'map'); });
const pick = e => { const li = e.target.closest('li[data-i]'); if (!li) return; const p = P[+li.dataset.i]; if (p === sel) clearSel(); else select(p, 'list'); };
$('stList').addEventListener('click', pick);
$('stList').addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(e); } });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && sel) clearSel(); });
['stQ', 'stG', 'stC', 'stS'].forEach(id => $(id).addEventListener('input', () => { clearSel(false); filt(); }));
$('stLeg').innerHTML = ['completed', 'in_progress', 'not_started'].map(s => `<li><i style="background:${ST[s][1]};border-radius:50%"></i><span>${ST[s][0]}</span></li>`).join('');
addEventListener('resize', () => { if (P.length) draw(); });
Promise.all([fetch('/data/surtax-projects.json').then(r => r.json()), fetch('/data/cra-geo.json').then(r => r.json()).catch(() => null)]).then(([p, g]) => {
  P = p; G = g; P.forEach((x, i) => x._i = i);
  [...new Set(P.map(x => x.g))].sort().forEach(v => $('stG').insertAdjacentHTML('beforeend', `<option>${esc(v)}</option>`));
  [...new Set(P.map(x => x.c))].sort().forEach(v => $('stC').insertAdjacentHTML('beforeend', `<option>${esc(v)}</option>`));
  // filters from the link (?gov=&type=&status=&q=) are set before the first draw; the shared helper keeps them in the link
  const U = U0;
  [['stG', 'gov'], ['stC', 'type'], ['stS', 'status'], ['stQ', 'q']].forEach(([id, k]) => { const v = U.get(k); if (!v) return; const el = $(id);
    if (el.tagName === 'SELECT') { const o = window.BCM ? BCM.findOption(el, v) : [...el.options].find(o => o.value === v); if (o) el.value = o.value; } else el.value = v; });
  filt();
  const want = U.get('p'), hit = want && P.find(x => x.id === want);
  if (hit) { if (!cur.includes(hit)) { ['stQ', 'stG', 'stC', 'stS'].forEach(id => $(id).value = ''); filt(); } select(hit, 'map'); $('map-h').scrollIntoView(); }
});
})();
