(() => {
const D = __BT__;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const big = n => n == null ? '—' : n >= 1e6 ? '$' + (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? '$' + Math.round(n / 1e3) + 'K' : '$' + Math.round(n);
const col = i => `var(--s${i + 1})`;
const tt = $('tt');
function tip(e, h) { tt.innerHTML = h; tt.hidden = false; const w = tt.offsetWidth, hh = tt.offsetHeight; let x = e.clientX + 14, y = e.clientY + 14; if (x + w > innerWidth - 8) x = e.clientX - w - 14; if (y + hh > innerHeight - 8) y = e.clientY - hh - 14; tt.style.left = x + 'px'; tt.style.top = y + 'px'; }

/* stacked collections: every zone, or only the zone the city bar at the top picks */
const el = $('btBars');
const C = window.BCM && BCM.city;
const zoneOf = k => k && k !== 'county' ? D.zones.find(z => C.key(z) === k) : null;
function bars(k) {
  const one = zoneOf(k), Z = one ? [one] : D.zones;
  const tots = D.years.map(y => Z.reduce((a, z) => a + (D.col[y][z] || 0), 0)), max = Math.max(...tots) || 1;
  el.style.gridTemplateColumns = `repeat(${D.years.length},minmax(0,1fr))`;
  el.innerHTML = D.years.map((y, i) => `<div class="vb" tabindex="0" data-i="${i}"><span class="vb-v">${big(tots[i])}</span><span class="vb-stack" style="height:${tots[i] / max * 100}%">${Z.slice().reverse().map(z => `<span style="flex:${D.col[y][z] || 0} 1 0;background:${col(D.zones.indexOf(z))}"></span>`).join('')}</span><span class="vb-x">FY${String(y).slice(2)}</span></div>`).join('');
  el.querySelectorAll('.vb').forEach(v => { const i = +v.dataset.i, y = D.years[i];
    const h = `<b>FY${y}</b> · ${big(tots[i])}` + Z.map(z => `<span class="tt-row"><i style="background:${col(D.zones.indexOf(z))}"></i>${esc(z)} <b>${big(D.col[y][z])}</b></span>`).join('');
    v.addEventListener('pointermove', e => tip(e, h)); v.addEventListener('pointerleave', () => tt.hidden = true); });
  $('btLeg').innerHTML = Z.map(z => `<li><i style="background:${col(D.zones.indexOf(z))}"></i><span>${esc(z)} zone</span><b>${big(D.col[D.years[D.years.length - 1]][z])}</b><em>FY${D.years[D.years.length - 1]}</em></li>`).join('');
  const m = $('tdcMap'); if (m) m.querySelectorAll('path[data-z]').forEach(p => p.setAttribute('fill-opacity', !one || p.dataset.z === one ? '.55' : '.12'));
}
bars(C ? C.get() : '');
if (C) C.on(bars);

/* CVB departments */
const dm = D.depts[0][1];
$('cvbBars').innerHTML = D.depts.map(([n, v]) => `<div class="hb"><span class="hb-n">${esc(n)}</span><span class="hb-track"><span class="hb-bar" style="width:${Math.max(.5, v / dm * 100)}%"></span></span><span class="hb-v">${big(v)} <em>${(v / D.total26 * 100).toFixed(v / D.total26 < .1 ? 1 : 0)}%</em></span></div>`).join('');

/* zone map */
fetch('/data/cra-geo.json').then(r => r.json()).then(G => {
  const svg = $('tdcMap'), W = 400, H = 260, k = Math.cos(30.2 * Math.PI / 180), c = {x: -85.6, y: 30.06}, spanY = 0.36, spanX = spanY * W / H / k;
  const x0 = c.x - spanX / 2, y0 = c.y + spanY / 2;
  const P = ([x, y]) => `${((x - x0) / spanX * W).toFixed(1)},${((y0 - y) / spanY * H).toFixed(1)}`;
  const path = mp => mp.map(poly => poly.map(ring => 'M' + ring.map(P).join('L') + 'Z').join('')).join('');
  let s = `<rect width="${W}" height="${H}" fill="var(--water)"/><path d="${path(G.land)}" fill="var(--land)" stroke="var(--landline)" stroke-width=".8"/>`;
  D.zones.forEach((z, i) => { const g = D.geo[z]; if (g) s += `<path d="${g.map(rings => rings.map(r => 'M' + r.map(P).join('L') + 'Z').join('')).join('')}" data-z="${esc(z)}" fill="${col(i)}" fill-opacity=".55" stroke="${col(i)}" stroke-width="1"><title>${esc(z)} zone</title></path>`; });
  const lab = [['Panama City Beach', -85.83, 30.19], ['Panama City', -85.64, 30.21], ['Mexico Beach', -85.42, 29.98]];
  lab.forEach(([n, x, y]) => { const [lx, ly] = P([x, y]).split(','); s += `<text x="${lx}" y="${ly}" font-size="11" font-weight="500" text-anchor="middle" fill="var(--ink)" style="paint-order:stroke;stroke:var(--land);stroke-width:3px">${n}</text>`; });
  svg.innerHTML = s;
  bars(C ? C.get() : '');
}).catch(() => {});
})();
