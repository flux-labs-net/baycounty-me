(() => {
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const big = n => n == null ? '' : n >= 1e6 ? '$' + (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? '$' + Math.round(n / 1e3) + 'K' : '$' + Math.round(n);
const ST = {completed: ['Completed', '#1F7A4D'], in_progress: ['In progress', 'var(--blue)'], not_started: ['Not started', 'var(--faint)'], unknown: ['Unknown', 'var(--faint)']};
let P = [], G = null, cur = [];
const W = 400, H = 300, k = Math.cos(30.2 * Math.PI / 180);
let view = {x: -85.66, y: 30.25, span: 0.62};
function proj([x, y]) { const sx = view.span * W / H / k; return [(x - (view.x - sx / 2)) / sx * W, ((view.y + view.span / 2) - y) / view.span * H]; }
function draw() {
  const svg = $('stMap'); const path = mp => mp.map(poly => poly.map(ring => 'M' + ring.map(p => proj(p).map(v => v.toFixed(1)).join(',')).join('L') + 'Z').join('')).join('');
  let s = `<rect width="${W}" height="${H}" fill="var(--water)"/>`;
  if (G) { s += `<path d="${path(G.land)}" fill="var(--land)" stroke="var(--landline)" stroke-width=".8"/>`; Object.values(G.cities).forEach(g => s += `<path d="${path(g)}" fill="var(--city)" stroke="var(--cityline)" stroke-width=".6"/>`); }
  const r = Math.max(2.2, Math.min(5, 1.6 / view.span));
  ['not_started', 'unknown', 'in_progress', 'completed'].forEach(st => cur.filter(p => p.s === st).forEach(p => { const [x, y] = proj([p.x, p.yy]); if (x < -5 || x > W + 5 || y < -5 || y > H + 5) return; s += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r}" fill="${ST[p.s]?.[1] || 'var(--faint)'}" stroke="var(--surface)" stroke-width=".8" data-i="${P.indexOf(p)}" tabindex="-1"/>`; }));
  svg.innerHTML = s;
}
function filt() {
  const q = $('stQ').value.trim().toLowerCase(), g = $('stG').value, c = $('stC').value, st = $('stS').value;
  cur = P.filter(p => (!g || p.g === g) && (!c || p.c === c) && (!st || p.s === st) && (!q || (p.n + ' ' + p.d).toLowerCase().includes(q)));
  const n = s => cur.filter(p => p.s === s).length;
  $('stCount').textContent = `${cur.length.toLocaleString()} projects · ${n('completed')} completed, ${n('in_progress')} in progress, ${n('not_started')} not started`;
  $('stList').innerHTML = cur.slice(0, 200).map(p => `<li data-i="${P.indexOf(p)}"><span class="st-dot" style="background:${ST[p.s]?.[1]}"></span><div><b>${esc(p.n)}</b><span class="muted small">${esc(p.g)} · ${esc(p.c)} · ${esc(ST[p.s]?.[0] || p.s)}${p.p != null && p.s === 'in_progress' ? ` (${p.p}%)` : ''}${p.k ? ' · ' + big(p.k) : ''}</span></div></li>`).join('') + (cur.length > 200 ? `<li class="muted small">Showing 200 of ${cur.length}. Narrow the filters to see more.</li>` : '');
  if (g) { const pts = cur.length ? cur : P.filter(p => p.g === g); const xs = pts.map(p => p.x), ys = pts.map(p => p.yy);
    view = {x: (Math.min(...xs) + Math.max(...xs)) / 2, y: (Math.min(...ys) + Math.max(...ys)) / 2, span: Math.max(0.04, (Math.max(...ys) - Math.min(...ys)) * 1.3, (Math.max(...xs) - Math.min(...xs)) * k * H / W * 1.3)}; }
  else view = {x: -85.66, y: 30.25, span: 0.62};
  draw();
}
const tt = $('tt');
$('stMap').addEventListener('pointermove', e => { const c = e.target.closest('circle[data-i]'); if (!c) { tt.hidden = true; return; } const p = P[+c.dataset.i];
  tt.innerHTML = `<b>${esc(p.n)}</b><br>${esc(p.g)} · ${esc(p.c)}<br>${esc(ST[p.s]?.[0])}${p.k ? ' · ' + big(p.k) : ''}`; tt.hidden = false; tt.style.left = Math.min(e.clientX + 14, innerWidth - 290) + 'px'; tt.style.top = (e.clientY + 14) + 'px'; });
$('stMap').addEventListener('pointerleave', () => tt.hidden = true);
$('stList').addEventListener('click', e => { const li = e.target.closest('li[data-i]'); if (!li) return; const p = P[+li.dataset.i]; view = {x: p.x, y: p.yy, span: 0.03}; draw();
  li.classList.toggle('open'); if (li.classList.contains('open') && !li.querySelector('.st-d') && p.d) li.querySelector('div').insertAdjacentHTML('beforeend', `<p class="st-d small">${esc(p.d)}</p>`); });
['stQ', 'stG', 'stC', 'stS'].forEach(id => $(id).addEventListener('input', filt));
$('stLeg').innerHTML = ['completed', 'in_progress', 'not_started'].map(s => `<li><i style="background:${ST[s][1]};border-radius:50%"></i><span>${ST[s][0]}</span></li>`).join('');
Promise.all([fetch('/data/surtax-projects.json').then(r => r.json()), fetch('/data/cra-geo.json').then(r => r.json()).catch(() => null)]).then(([p, g]) => {
  P = p; G = g;
  [...new Set(P.map(x => x.g))].sort().forEach(v => $('stG').insertAdjacentHTML('beforeend', `<option>${esc(v)}</option>`));
  [...new Set(P.map(x => x.c))].sort().forEach(v => $('stC').insertAdjacentHTML('beforeend', `<option>${esc(v)}</option>`));
  filt();
});
})();
