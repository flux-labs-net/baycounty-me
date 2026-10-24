/* Public money map (/public-money/map): CRA payments, sales tax projects, CRA districts and city limits on one SVG map.
   Same projection and look as the Sales Tax Projects map (surtax.js); data from /data/cra-*.json and /data/surtax-projects.json. */
(() => {
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const big = n => n == null ? '' : (n < 0 ? '−' : '') + (Math.abs(n) >= 1e6 ? '$' + (Math.abs(n) / 1e6).toFixed(1) + 'M' : Math.abs(n) >= 1e3 ? '$' + Math.round(Math.abs(n) / 1e3) + 'K' : '$' + Math.round(Math.abs(n)));
const W = 400, H = 300, k = Math.cos(30.2 * Math.PI / 180);
const HOME = {x: -85.66, y: 30.25, span: 0.62}, NEAR = 0.05;
let view = {...HOME}, G = null, ITEMS = [], cur = [], sel = null, SLUG = {};
// statuses: CRA ledger statuses and sales-tax project statuses mapped onto one filter
const ST = {done: ['Spent / completed', '#1F7A4D'], active: ['Committed / in progress', 'var(--blue)'], plan: ['Budgeted, proposed or not started', 'var(--faint)'], other: ['Other', 'var(--faint)']};
const craSt = s => s === 'Spent' ? 'done' : s === 'Committed' ? 'active' : (s === 'Budgeted' || s === 'Proposed') ? 'plan' : 'other';
const taxSt = s => s === 'completed' ? 'done' : s === 'in_progress' ? 'active' : s === 'not_started' ? 'plan' : 'other';
const CRA_N = {pc: 'Panama City CRA', pcb: 'Panama City Beach CRA', lh: 'Lynn Haven CRA', cw: 'Callaway CRA', sf: 'Springfield CRA', pk: 'Parker CRA'};
function proj([x, y]) { const sx = view.span * W / H / k; return [(x - (view.x - sx / 2)) / sx * W, ((view.y + view.span / 2) - y) / view.span * H]; }
const inView = ([x, y], m = 0) => x > -m && x < W + m && y > -m && y < H + m;
const path = mp => mp.map(poly => poly.map(ring => 'M' + ring.map(p => proj(p).map(v => v.toFixed(1)).join(',')).join('L') + 'Z').join('')).join('');
const on = id => $(id).checked;
function draw() {
  const svg = $('pmMap'), sw = Math.max(.5, Math.min(1.4, .3 / view.span));
  let s = `<rect width="${W}" height="${H}" fill="var(--water)"/>`;
  if (G) {
    s += `<path d="${path(G.land)}" fill="var(--land)" stroke="var(--landline)" stroke-width="${sw}"/>`;
    if (on('pmLCity')) Object.values(G.cities).forEach(g => s += `<path d="${path(g)}" fill="var(--city)" stroke="var(--cityline)" stroke-width="${sw * .8}"/>`);
    if (on('pmLDist')) G.districts.filter(d => BCM.city.has(BCM.city.get(), d.cra)).forEach(d => s += `<path d="${path(d.geom)}" fill="var(--c-${d.cra})" fill-opacity=".16" stroke="var(--c-${d.cra})" stroke-width="${sw}"><title>${esc(d.name)} (est. ${d.est})</title></path>`);
  }
  const r = Math.max(2.2, Math.min(4.5, 1.4 / view.span));
  cur.forEach(p => { if (p === sel) return; const [x, y] = proj([p.x, p.y]); if (!inView([x, y], 5)) return;
    const col = ST[p.st][1], fade = sel ? .35 : 1;
    s += p.t === 'cra'
      ? `<rect x="${(x - r).toFixed(1)}" y="${(y - r).toFixed(1)}" width="${(2 * r).toFixed(1)}" height="${(2 * r).toFixed(1)}" transform="rotate(45 ${x.toFixed(1)} ${y.toFixed(1)})" fill="${col}" stroke="var(--surface)" stroke-width=".8" data-i="${p.i}" opacity="${fade}"/>`
      : `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r}" fill="${col}" stroke="var(--surface)" stroke-width=".8" data-i="${p.i}" opacity="${fade}"/>`; });
  if (sel) { const [x, y] = proj([sel.x, sel.y]); s += `<circle cx="${x}" cy="${y}" r="15" fill="${ST[sel.st][1]}" opacity=".18"/><circle cx="${x}" cy="${y}" r="7" fill="${ST[sel.st][1]}" stroke="var(--surface)" stroke-width="2" data-i="${sel.i}"/><circle cx="${x}" cy="${y}" r="10" fill="none" stroke="var(--ink)" stroke-width="1.2"/>`; }
  svg.innerHTML = s;
}
function filt() {
  const q = $('pmQ').value.trim().toLowerCase(), st = $('pmS').value, cra = on('pmLCra'), tax = on('pmLTax');
  const ck = BCM.city.get();
  cur = ITEMS.filter(p => ((p.t === 'cra' && cra) || (p.t === 'tax' && tax)) && (!ck || p.g === ck) && (!st || p.st === st) && (!q || p.q.includes(q)));
  const n = t => cur.filter(p => p.t === t).length;
  $('pmCount').textContent = `${n('cra').toLocaleString()} CRA records · ${n('tax').toLocaleString()} sales tax projects`;
  if (sel && !cur.includes(sel)) clear(false);
  draw();
}
function vendorLink(name) {
  const id = SLUG[(name || '').trim().toLowerCase()];
  return id ? `<a href="/public-money/vendors/${esc(id)}">${esc(name)}</a>` : esc(name);
}
function select(p) {
  sel = p; view = {x: p.x, y: p.y, span: Math.min(view.span, 0.16)};
  const st = ST[p.st], el = $('pmSel');
  el.hidden = false;
  el.innerHTML = p.t === 'cra'
    ? `<div class="st-sel-hd"><span class="st-dot" style="background:${st[1]}"></span><div><b>${esc(p.r.purpose)}</b><span class="muted small">${esc(CRA_N[p.r.cra] || '')} · ${esc(p.r.district || '')} · ${esc(p.r.when || '')}</span></div><button type="button" class="st-x" aria-label="Close">×</button></div>
       <p class="st-meta"><span class="badge">${esc(p.r.status)}</span>${p.r.amount != null ? ` <b>${big(p.r.amount)}</b>` : ' <span class="muted small">amount not stated</span>'}${p.r.count ? '' : ' <span class="muted small">not in CRA totals</span>'}</p>
       <p class="small">Paid to: ${vendorLink(p.r.payee)}</p>
       <p class="small muted">${esc(p.r.loc || p.r.addr || '')}${p.r.placed === 'district' ? ' · pinned at the district center' : p.r.prec === 'approximate' ? ' · approximate location' : ''}</p>
       <p class="small"><a href="/public-money/cra-spending">Open in the CRA ledger</a>${p.r.url ? ` · <a class="src" href="${esc(p.r.url)}" target="_blank" rel="noopener">Source</a>` : ''}</p>`
    : `<div class="st-sel-hd"><span class="st-dot" style="background:${st[1]}"></span><div><b>${esc(p.r.n)}</b><span class="muted small">${esc(p.r.g)} · ${esc(p.r.c)}${p.r.y ? ' · ' + esc(p.r.y) : ''}</span></div><button type="button" class="st-x" aria-label="Close">×</button></div>
       <p class="st-meta"><span class="badge">${esc(p.r.s.replace('_', ' '))}${p.r.p != null && p.r.s === 'in_progress' ? ' · ' + p.r.p + '%' : ''}</span>${p.r.k ? ` <span class="small">GIS cost <b>${big(p.r.k)}</b></span>` : ''}${p.r.sp != null ? ` <span class="small">County schedule <b>${big(p.r.sp)}</b> programmed</span>` : ''}</p>
       ${p.r.d ? `<p class="small">${esc(p.r.d.trim())}${/[.!?]$/.test(p.r.d.trim()) ? '' : '…'}</p>` : ''}
       <p class="small"><a href="/public-money/sales-tax-projects">Open in Sales Tax Projects</a>${p.r.su ? ` · <a class="src" href="${esc(p.r.su)}" target="_blank" rel="noopener">Schedule source</a>` : ''}</p>`;
  draw();
}
function clear(redraw = true) { sel = null; $('pmSel').hidden = true; if (redraw) draw(); }
const zoom = f => { view = {...view, span: Math.min(HOME.span * 1.2, Math.max(0.02, view.span * f))}; draw(); };
$('pmIn').addEventListener('click', () => zoom(0.6));
$('pmOut').addEventListener('click', () => zoom(1.6));
$('pmAll').addEventListener('click', () => { clear(false); view = {...HOME}; draw(); });
/* the city bar: show only that government's marks and fit the map to its city limits and marks */
function fitCity(ck) {
  if (!ck) { view = {...HOME}; return; }
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  const add = (x, y) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); };
  const lim = G && G.cities && G.cities[BCM.city.label(ck)];
  if (lim) lim.forEach(poly => poly.forEach(ring => ring.forEach(([x, y]) => add(x, y))));
  ITEMS.forEach(p => { if (p.g === ck) add(p.x, p.y); });
  if (!isFinite(x0)) { view = {...HOME}; return; }
  const span = Math.min(HOME.span, Math.max(0.04, (y1 - y0) * 1.15, (x1 - x0) * k * H / W * 1.15));
  view = {x: (x0 + x1) / 2, y: (y0 + y1) / 2, span};
}
$('pmSel').addEventListener('click', ev => { if (ev.target.closest('.st-x')) clear(); });
$('pmMap').addEventListener('click', ev => { const c = ev.target.closest('[data-i]'); if (c) select(ITEMS[+c.dataset.i]); });
const tt = $('tt');
$('pmMap').addEventListener('pointermove', ev => { const c = ev.target.closest('[data-i]'); if (!c || ev.pointerType !== 'mouse') { tt.hidden = true; return; } const p = ITEMS[+c.dataset.i];
  tt.innerHTML = p.t === 'cra' ? `<b>${p.r.amount != null ? big(p.r.amount) : 'Amount not stated'}</b> · ${esc(p.r.status)}<br>${esc(p.r.payee)}<br><span class="muted">${esc((p.r.purpose || '').slice(0, 100))}</span>` : `<b>${esc(p.r.n)}</b><br>${esc(p.r.g)} · ${esc(ST[p.st][0])}`;
  tt.hidden = false; tt.style.left = Math.min(ev.clientX + 14, innerWidth - 290) + 'px'; tt.style.top = (ev.clientY + 14) + 'px'; });
$('pmMap').addEventListener('pointerleave', () => tt.hidden = true);
document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && sel) clear(); });
['pmQ', 'pmS', 'pmLCra', 'pmLTax', 'pmLDist', 'pmLCity'].forEach(id => $(id).addEventListener('input', () => filt()));
$('pmLeg').innerHTML = Object.entries(ST).filter(([kk]) => kk !== 'other').map(([, v]) => `<li><i style="background:${v[1]};border-radius:50%"></i><span>${v[0]}</span></li>`).join('') +
  '<li><i style="background:var(--muted);transform:rotate(45deg);border-radius:1px"></i><span>Diamond: CRA record</span></li><li><i style="background:var(--muted);border-radius:50%"></i><span>Dot: sales tax project</span></li>';
addEventListener('resize', () => { if (ITEMS.length) draw(); });
Promise.all(['/data/cra-geo.json', '/data/cra-pay-1.json', '/data/cra-pay-2.json', '/data/surtax-projects.json', '/data/vendor-slugs.json'].map(u => fetch(u).then(r => r.json()).catch(() => null)))
  .then(([geo, p1, p2, tax, slugs]) => {
    G = geo; SLUG = (slugs && slugs.names) || {};
    (p1 || []).concat(p2 || []).forEach(r => { if (r.lat == null) return; ITEMS.push({t: 'cra', x: r.lng, y: r.lat, st: craSt(r.status), r, g: BCM.city.key(r.cra), q: (r.payee + ' ' + r.purpose + ' ' + r.loc + ' ' + (CRA_N[r.cra] || '')).toLowerCase()}); });
    (tax || []).forEach(r => ITEMS.push({t: 'tax', x: r.x, y: r.yy, st: taxSt(r.s), r, g: BCM.city.key(r.g), q: (r.n + ' ' + r.g + ' ' + r.c + ' ' + (r.d || '')).toLowerCase()}));
    ITEMS.forEach((p, i) => p.i = i);
    BCM.city.on(ck => { clear(false); fitCity(ck); filt(); });
  });
})();
