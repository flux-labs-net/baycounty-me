/* CRA network (/public-money/cra-network). Data is built by site/cra_network.py and inlined below.
   Views: force-directed network (d3), SVG map on /data/cra-geo.json, payee table, business gifts to CRA board members. */
(function () {
const D = __CRN__;
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const money = v => v == null ? 'Amount not stated' : v >= 1e6 ? '$' + (v / 1e6).toFixed(v >= 1e7 ? 1 : 2) + 'M' : v >= 1e3 ? '$' + Math.round(v / 1e3).toLocaleString() + 'K' : '$' + Math.round(v).toLocaleString();
const full = v => v == null ? '—' : '$' + Math.round(v).toLocaleString();
const STATUS = ['Spent', 'Committed', 'Budgeted', 'Proposed', 'Incoming', 'Not CRA-funded'];
const KIND = { biz: 'Business or nonprofit', gov: 'Government or bondholders', prop: 'Property owner', unnamed: 'Payee not named', grants: 'Grant recipients, not named', official: 'Elected official', cra: 'Agency' };
const COL = { cra: 'var(--navy)', biz: 'var(--blue)', gov: 'var(--muted)', prop: 'var(--amber)', unnamed: 'var(--surface)', grants: 'var(--surface)', official: 'var(--salmon)' };
const SCOL = { Spent: 'var(--blue)', Committed: 'var(--amber)', Budgeted: 'var(--navy)' };
const st = { cra: new Set(Object.keys(D.cras)), status: new Set(['Spent', 'Committed', 'Budgeted']), don: 'payees', board: 'all', sel: null, view: 'network' };
const ent = id => D.ents[id] || (id.startsWith('d:') ? { n: id.slice(2), k: 'biz' } : id.startsWith('o:') ? { n: id.slice(2), k: 'official' } : { n: id, k: 'biz' });
const craName = c => D.cras[c] ? D.cras[c].n : c;
const visible = () => D.recs.filter(r => st.cra.has(r.c) && st.status.has(r.s));
const donShown = () => st.don === 'off' ? [] : D.don.filter(d => st.don === 'payees' ? !!d.e : (d.e || (d.b && st.cra.has(d.b))));
const offId = d => 'o:' + d.o;

function chip(label, pressed, onclick, id) {
  const b = document.createElement('button'); b.type = 'button'; b.className = 'crn-chip'; b.textContent = label; if (id) b.id = id;
  b.setAttribute('aria-pressed', pressed); b.onclick = () => onclick(b); return b;
}
function radio(groupId, opts, cur, set) {
  const g = $(groupId);
  opts.forEach(([k, l]) => g.appendChild(chip(l, cur === k, b => { set(k); g.querySelectorAll('.crn-chip').forEach(x => x.setAttribute('aria-pressed', x === b)); }, groupId + '-' + k)));
}
function controls() {
  document.querySelectorAll('[data-cra]').forEach(b => b.onclick = () => { const k = b.dataset.cra; st.cra.has(k) ? st.cra.delete(k) : st.cra.add(k); b.setAttribute('aria-pressed', st.cra.has(k)); render(); });
  STATUS.forEach(k => $('crnStatus').appendChild(chip(k, st.status.has(k), b => { st.status.has(k) ? st.status.delete(k) : st.status.add(k); b.setAttribute('aria-pressed', st.status.has(k)); render(); })));
  radio('crnDon', [['payees', 'Donors who were paid'], ['all', 'All business donors'], ['off', 'Hide']], st.don, k => { st.don = k; render(); });
  radio('crnBoards', [['all', 'All'], ...['PC', 'PCB', 'LH', 'CW'].filter(k => D.cras[k]).map(k => [k, craName(k).replace(' CRA', '')]), ['none', 'Not on a CRA board']], st.board, k => { st.board = k; donTable(); });
  document.querySelectorAll('.crn-tab').forEach(b => b.onclick = () => setView(b.dataset.v));
}

function kpis(rows) {
  const sum = f => rows.filter(f).reduce((a, r) => a + (r.a || 0), 0);
  const counted = sum(r => r.k), unnamed = sum(r => r.k && r.e.startsWith('u:'));
  const named = new Set(rows.filter(r => /^[vb]:/.test(r.e)).map(r => r.e));
  const paidDon = new Set(D.don.filter(d => d.e && named.has(d.e)).map(d => d.e));
  $('crnKpis').innerHTML = [
    ['Spent', money(sum(r => r.k && r.s === 'Spent')), 'counted once, current filters'],
    ['Committed or budgeted', money(sum(r => r.k && (r.s === 'Committed' || r.s === 'Budgeted'))), 'not yet paid'],
    ['Named payees', named.size, `${counted ? Math.round(unnamed / counted * 100) : 0}% of counted dollars have no named payee`],
    ['Paid and gave', paidDon.size, 'businesses paid by a CRA that gave to a campaign'],
  ].map(([l, v, s]) => `<div class="kpi"><span class="eyebrow">${l}</span><span class="v">${v}</span><span class="s">${s}</span></div>`).join('');
}

let sim, hl, graphZoom;
function focusNode(id) {
  const svg = d3.select('#crnGraph'), n = svg.selectAll('.crn-node').filter(d => d.id === id).datum && svg.selectAll('.crn-node').filter(d => d.id === id);
  if (!n || n.empty() || !graphZoom) return;
  const d = n.datum(), r = svg.node().getBoundingClientRect(), vb = svg.node().viewBox.baseVal, sx = vb.width / r.width;
  const phone = innerWidth < 700, cx = phone ? vb.width / 2 : (vb.width - 380 * sx) / 2, cy = phone ? vb.height * 0.25 : vb.height / 2;
  const t = d3.zoomTransform(svg.node()), k = Math.max(t.k, 1.2);
  svg.transition().duration(400).call(graphZoom.transform, d3.zoomIdentity.translate(cx - d.x * k, cy - d.y * k).scale(k));
}
function graphBtn(f) { const svg = d3.select('#crnGraph'); if (!graphZoom) return; if (f === 0) svg.transition().duration(250).call(graphZoom.transform, d3.zoomIdentity); else svg.transition().duration(250).call(graphZoom.scaleBy, f); }
function graph(rows) {
  const svg = d3.select('#crnGraph'), W = svg.node().clientWidth || 800, H = svg.node().clientHeight || 620;
  svg.attr('viewBox', `0 0 ${W} ${H}`).selectAll('*').remove();
  if (sim) sim.stop();
  const nodes = new Map(), links = new Map();
  const add = (id, o) => { if (!nodes.has(id)) nodes.set(id, { id, total: 0, ...o }); return nodes.get(id); };
  rows.forEach(r => {
    add('c:' + r.c, { n: craName(r.c), k: 'cra' });
    const e = ent(r.e); add(r.e, { n: e.n, k: e.k }).total += r.a || 0;
    const key = 'c:' + r.c + '|' + r.e, l = links.get(key) || { source: 'c:' + r.c, target: r.e, type: 'paid', amt: 0 };
    l.amt += r.a || 0; links.set(key, l);
  });
  D.rel.forEach(x => {
    const sub = id => D.ents[id] && D.ents[id].sub;
    if ((nodes.has(x.a) || sub(x.a)) && (nodes.has(x.b) || sub(x.b)) && (nodes.has(x.a) || nodes.has(x.b))) {
      [x.a, x.b].forEach(id => { if (!nodes.has(id)) add(id, { n: ent(id).n, k: 'biz' }); });
      links.set(x.a + '~' + x.b, { source: x.a, target: x.b, type: 'rel' });
    }
  });
  donShown().forEach(d => {
    const o = add(offId(d), { n: d.o, k: 'official' });
    const donor = d.e || 'd:' + d.dn;
    if (!nodes.has(donor)) add(donor, { n: d.e ? ent(d.e).n : d.dn, k: 'biz' });
    const key = donor + '>' + o.id, l = links.get(key) || { source: donor, target: o.id, type: 'don', amt: 0 }; l.amt += d.a; links.set(key, l);
    if (d.b && nodes.has('c:' + d.b)) links.set(o.id + '@' + d.b, { source: o.id, target: 'c:' + d.b, type: 'board' });
  });
  const N = [...nodes.values()], L = [...links.values()];
  const rS = d3.scaleSqrt().domain([0, d3.max(N, d => d.total) || 1]).range([4, 30]);
  const wS = d3.scaleSqrt().domain([0, d3.max(L.filter(l => l.type === 'paid'), d => d.amt) || 1]).range([0.8, 7]);
  N.forEach(n => n.r = n.k === 'cra' ? 17 : n.k === 'official' ? 8 : Math.max(5, rS(n.total)));
  const connected = new Set(L.filter(l => l.type !== 'paid').flatMap(l => [l.source, l.target]));
  const g = svg.append('g');
  graphZoom = d3.zoom().scaleExtent([0.3, 5]).on('zoom', e => g.attr('transform', e.transform));
  svg.call(graphZoom);
  const link = g.append('g').selectAll('line').data(L).join('line')
    .attr('stroke', d => d.type === 'rel' ? 'var(--amber)' : d.type === 'paid' ? 'var(--faint)' : 'var(--salmon)')
    .attr('stroke-opacity', d => d.type === 'paid' ? 0.55 : 0.95)
    .attr('stroke-width', d => d.type === 'paid' ? wS(d.amt) : d.type === 'don' ? 2 : 1.5)
    .attr('stroke-dasharray', d => d.type === 'rel' ? '5 4' : d.type === 'board' ? '2 3' : null);
  const node = g.append('g').selectAll('g').data(N).join('g').attr('class', 'crn-node')
    .call(d3.drag().on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.2).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; }).on('end', (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));
  node.append('circle').attr('r', d => d.r).attr('fill', d => COL[d.k] || COL.biz)
    .attr('stroke', d => d.k === 'unnamed' || d.k === 'grants' ? 'var(--faint)' : d.k === 'cra' ? 'var(--ink)' : 'var(--surface)')
    .attr('stroke-width', d => d.k === 'unnamed' || d.k === 'grants' ? 1.5 : d.k === 'cra' ? 2 : 1.2)
    .attr('stroke-dasharray', d => d.k === 'grants' ? '3 2' : null)
    .attr('tabindex', 0).attr('role', 'button').attr('aria-label', d => d.n)
    .on('click', (e, d) => select(d.id)).on('keydown', (e, d) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(d.id); } })
    .on('mousemove', (e, d) => tip(e, `<b>${esc(d.n)}</b><br>${KIND[d.k]}${d.total ? ' · ' + money(d.total) : ''}`, 'crnTip')).on('mouseleave', () => hideTip('crnTip'));
  node.append('text').attr('dy', d => d.r + 12).attr('text-anchor', 'middle')
    .text(d => d.k === 'cra' ? d.n.replace(' CRA', '') : (d.r > 10 || connected.has(d.id) || d.k === 'official') ? (d.n.length > 30 ? d.n.slice(0, 29) + '…' : d.n) : '');
  sim = d3.forceSimulation(N)
    .force('link', d3.forceLink(L).id(d => d.id).distance(d => d.type === 'rel' ? 60 : d.type === 'board' ? 60 : 95).strength(d => d.type === 'paid' ? 0.5 : 0.8))
    .force('charge', d3.forceManyBody().strength(d => d.k === 'cra' ? -700 : -90))
    .force('collide', d3.forceCollide(d => d.r + 4))
    .force('x', d3.forceX(W / 2).strength(0.05)).force('y', d3.forceY(H / 2).strength(0.07))
    .on('tick', () => { link.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y); node.attr('transform', d => `translate(${d.x},${d.y})`); });
  for (let i = 0; i < 240; i++) sim.tick();
  if (fsOn) {  // full screen: start with the whole network in view
    const xs = N.map(n => n.x), ys = N.map(n => n.y), bx0 = Math.min(...xs) - 30, bx1 = Math.max(...xs) + 30, by0 = Math.min(...ys) - 30, by1 = Math.max(...ys) + 40;
    const k = Math.min(1.4, W / (bx1 - bx0), H / (by1 - by0));
    svg.call(graphZoom.transform, d3.zoomIdentity.translate(W / 2 - k * (bx0 + bx1) / 2, H / 2 - k * (by0 + by1) / 2).scale(k));
  }
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) sim.stop(); else sim.alpha(0.05).restart();
  hl = () => {
    const s = st.sel;
    if (!s) { node.classed('dim', false); link.classed('dim', false); return; }
    const nb = new Set([s]); L.forEach(l => { if (l.source.id === s) nb.add(l.target.id); if (l.target.id === s) nb.add(l.source.id); });
    node.classed('dim', d => !nb.has(d.id)); link.classed('dim', l => l.source.id !== s && l.target.id !== s);
  };
  hl();
}

let GEO = null, mapT = null, mapZoom = null;
function zoomMap(svg) {
  const g = d3.select('#crnMapG');
  if (!mapZoom) mapZoom = d3.zoom().scaleExtent([1, 12]).on('zoom', e => {
    mapT = e.transform; const k = mapT.k, G = d3.select('#crnMapG').attr('transform', mapT);
    G.selectAll('circle').attr('r', function () { return (+this.dataset.r) / Math.sqrt(k); }).attr('stroke-width', function () { return (+this.dataset.sw || 1) / k; });
    G.selectAll('text').style('font-size', (13 / k) + 'px').style('stroke-width', (4 / k) + 'px');
  });
  d3.select(svg).call(mapZoom);
  g.selectAll('circle').each(function () { this.dataset.sw = this.getAttribute('stroke-width'); this.dataset.r = this.getAttribute('r'); });
  g.selectAll('path').attr('vector-effect', 'non-scaling-stroke');
  if (mapT) d3.select(svg).call(mapZoom.transform, mapT);
}
function focusMap(id) {
  const svg = $('crnMap'); if (!mapZoom) return;
  const cs = [...svg.querySelectorAll('circle[data-i]')].filter(c => { const r = D.recs.find(x => x.i === +c.dataset.i); return r && r.e === id; });
  if (!cs.length) return;
  const vb = svg.viewBox.baseVal, xs = cs.map(c => +c.getAttribute('cx')), ys = cs.map(c => +c.getAttribute('cy'));
  const bx0 = Math.min(...xs) - 40, bx1 = Math.max(...xs) + 40, by0 = Math.min(...ys) - 40, by1 = Math.max(...ys) + 40;
  const phone = innerWidth < 700, sx = vb.width / svg.getBoundingClientRect().width;
  const aw = phone ? vb.width : vb.width - 390 * sx, ah = phone ? vb.height * 0.42 : vb.height;  // the part the details panel leaves open
  const k = Math.max(1, Math.min(8, aw / (bx1 - bx0), ah / (by1 - by0)));
  const t = d3.zoomIdentity.translate(aw / 2 - k * (bx0 + bx1) / 2, ah / 2 - k * (by0 + by1) / 2).scale(k);
  d3.select(svg).transition().duration(450).call(mapZoom.transform, t);
}
function mapBtn(f) { const svg = d3.select('#crnMap'); if (!mapZoom) return; if (f === 0) svg.transition().duration(250).call(mapZoom.transform, d3.zoomIdentity); else svg.transition().duration(250).call(mapZoom.scaleBy, f); }
function map(rows) {
  const svg = $('crnMap');
  if (!GEO) { svg.innerHTML = '<text x="20" y="30" fill="var(--muted)" font-size="13">Loading the map…</text>'; return; }
  const pts = rows.filter(r => r.a && r.lat != null);
  const xs = pts.map(r => r.lng), ys = pts.map(r => r.lat);
  const pad = 0.012, k = Math.cos(30.2 * Math.PI / 180);
  let x0 = Math.min(...xs) - pad, x1 = Math.max(...xs) + pad, y0 = Math.min(...ys) - pad, y1 = Math.max(...ys) + pad;
  let W = 1200, H = Math.round(W * (y1 - y0) / ((x1 - x0) * k));
  const box = svg.getBoundingClientRect();
  if (fsOn && box.width > 50 && box.height > 50) {  // fill the screen: widen whichever side is short
    W = Math.round(box.width); H = Math.round(box.height);
    const want = W / H, have = (x1 - x0) * k / (y1 - y0);
    if (have < want) { const d = ((y1 - y0) * want / k - (x1 - x0)) / 2; x0 -= d; x1 += d; }
    else { const d = ((x1 - x0) * k / want - (y1 - y0)) / 2; y0 -= d; y1 += d; }
  }
  const P = ([x, y]) => [(x - x0) / (x1 - x0) * W, (y1 - y) / (y1 - y0) * H];
  const path = mp => mp.map(poly => poly.map(ring => 'M' + ring.map(p => P(p).map(v => v.toFixed(1)).join(',')).join('L') + 'Z').join('')).join('');
  const rS = d3.scaleSqrt().domain([0, d3.max(pts, r => r.a) || 1]).range([3, 30]);
  const col = s => SCOL[s] || 'var(--faint)';
  let s = `<rect width="${W}" height="${H}" fill="var(--water)"/>`;
  s += `<path d="${path(GEO.land)}" fill="var(--land)" stroke="var(--landline)" stroke-width=".8"/>`;
  s += Object.values(GEO.cities).map(m => `<path d="${path(m)}" fill="var(--city)" stroke="var(--cityline)" stroke-width=".7"/>`).join('');
  s += GEO.districts.map(d => `<path d="${path(d.geom)}" fill="var(--navy)" fill-opacity=".07" stroke="var(--navy)" stroke-opacity=".4" stroke-width=".8"/>`).join('');
  pts.sort((a, b) => b.a - a.a).forEach(r => {
    const [cx, cy] = P([r.lng, r.lat]), on = !st.sel || r.e === st.sel;
    s += `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${rS(r.a).toFixed(1)}" fill="${col(r.s)}" fill-opacity="${on ? 0.42 : 0.06}" stroke="${col(r.s)}" stroke-width="${st.sel && r.e === st.sel ? 2.5 : 1}" stroke-opacity="${on ? 1 : 0.25}" data-i="${r.i}" tabindex="0" role="button" aria-label="${esc(ent(r.e).n)}, ${full(r.a)}"/>`;
  });
  [['Panama City', -85.66, 30.159], ['Lynn Haven', -85.648, 30.245], ['Panama City Beach', -85.83, 30.197], ['Callaway', -85.57, 30.153], ['Springfield', -85.611, 30.163], ['Parker', -85.602, 30.13]]
    .forEach(([n, x, y]) => { const [a, b] = P([x, y]); if (a > 0 && a < W && b > 0 && b < H) s += `<text x="${a.toFixed(0)}" y="${(b - 20).toFixed(0)}" text-anchor="middle" class="crn-town">${n}</text>`; });
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.innerHTML = `<g id="crnMapG">${s}</g>`;
  zoomMap(svg);
  const byI = new Map(rows.map(r => [r.i, r]));
  svg.querySelectorAll('circle[data-i]').forEach(c => {
    const r = byI.get(+c.dataset.i);
    c.onclick = () => select(r.e); c.onkeydown = e => { if (e.key === 'Enter') select(r.e); };
    c.onmousemove = e => tip(e, `<b>${esc(ent(r.e).n)}</b><br>${esc(r.w)}<br>${full(r.a)} · ${esc(r.s)} · ${esc(r.when)}`, 'crnTip2');
    c.onmouseleave = () => hideTip('crnTip2');
  });
  $('crnMapLegend').innerHTML = ['Spent', 'Committed', 'Budgeted'].map(k => `<span><i style="background:${SCOL[k]}"></i>${k}</span>`).join('') + '<span><i style="background:var(--faint)"></i>Other</span><span><i class="sq"></i>CRA district</span>';
}

function payees(rows) {
  const m = new Map();
  rows.forEach(r => { const o = m.get(r.e) || { e: r.e, tot: 0, n: 0, c: new Set(), unk: 0 }; o.tot += r.a || 0; o.n++; o.c.add(r.c); if (r.a == null) o.unk++; m.set(r.e, o); });
  const list = [...m.values()].sort((a, b) => b.tot - a.tot);
  $('crnPayCount').textContent = `${list.length} payees · tap a row for its records`;
  const gave = new Set(D.don.filter(d => d.e).map(d => d.e));
  $('crnPay').innerHTML = `<thead><tr><th>Payee</th><th>Type</th><th>Agency</th><th class="num">Records</th><th class="num">Dollars in records</th></tr></thead><tbody>` +
    list.map(o => { const e = ent(o.e); return `<tr class="crn-row" tabindex="0" data-e="${esc(o.e)}"><td><b>${esc(e.n)}</b>${gave.has(o.e) ? ' <span class="crn-flag red">gave</span>' : ''}${e.k === 'unnamed' || e.k === 'grants' ? ` <span class="crn-flag">${esc([...o.c].join(', '))}</span>` : ''}</td><td>${KIND[e.k]}</td><td>${[...o.c].map(craName).map(s => s.replace(' CRA', '')).join(', ')}</td><td class="num">${o.n}${o.unk ? ` <span class="crn-flag">${o.unk} no $</span>` : ''}</td><td class="num">${full(o.tot)}</td></tr>`; }).join('') + '</tbody>';
  $('crnPay').querySelectorAll('tr.crn-row').forEach(t => { t.onclick = () => select(t.dataset.e); t.onkeydown = e => { if (e.key === 'Enter') select(t.dataset.e); }; });
}

function donTable() {
  const rows = D.don.filter(d => st.board === 'all' || (st.board === 'none' ? !d.b : d.b === st.board));
  $('crnDonCount').textContent = `${rows.length} donor and official pairs · ${money(rows.reduce((a, d) => a + d.a, 0))}`;
  $('crnDonT').innerHTML = `<thead><tr><th>Business donor</th><th>Official</th><th>Office</th><th class="num">Amount</th><th>Date</th><th>Also paid by a CRA</th></tr></thead><tbody>` +
    rows.map((d, i) => `<tr><td>${esc(d.dn)}${d.ty === 'pac' ? ' <span class="crn-flag">PAC</span>' : ''}</td><td><button type="button" class="crn-link" data-off="${i}">${esc(d.o)}</button></td><td>${esc(d.off)}</td><td class="num">${full(d.a)}${d.n > 1 ? ` <span class="crn-flag">${d.n} gifts</span>` : ''}</td><td class="num">${esc(d.date)}</td><td>${d.e ? `<button type="button" class="crn-link" data-ent="${esc(d.e)}">${esc(ent(d.e).n)}</button>${d.cf === 'likely' ? ' <span class="crn-flag">likely</span>' : ''}` : '—'}</td></tr>`).join('') + '</tbody>';
  $('crnDonT').querySelectorAll('[data-ent]').forEach(b => b.onclick = () => { setView('network'); select(b.dataset.ent); });
  $('crnDonT').querySelectorAll('[data-off]').forEach(b => b.onclick = () => {
    const d = rows[+b.dataset.off];
    if (st.don !== 'all') { st.don = 'all'; document.querySelectorAll('#crnDon .crn-chip').forEach(x => x.setAttribute('aria-pressed', x.id === 'crnDon-all')); }
    setView('network'); select(offId(d));
  });
}

function profile() {
  const p = $('crnProfile'), id = st.sel;
  if (!id) {
    p.innerHTML = `<h3 class="eyebrow">Start here</h3><p>Tap any circle, map point or table row to see its full record.</p>
      <div class="crn-starts">${['v:dewberry', 'v:charlie-coram-s-place', 'v:mainline', 'v:bcl'].filter(k => D.ents[k]).map(k => `<button type="button" class="crn-link" data-sel="${k}">${esc(ent(k).n)}</button>`).join('')}</div>
      <p class="crn-note">A line is a documented connection, not evidence of wrongdoing. Contracts are usually bid, and CRA spending is approved by the full board.</p>`;
    p.querySelectorAll('[data-sel]').forEach(b => b.onclick = () => select(b.dataset.sel)); return;
  }
  if (id.startsWith('c:')) {
    const c = id.slice(2), rows = visible().filter(r => r.c === c), named = new Set(rows.filter(r => /^[vb]:/.test(r.e)).map(r => r.e));
    p.innerHTML = `<button type="button" class="crn-x" data-clear aria-label="Close details">×</button><div><span class="eyebrow">Agency</span><h2>${esc(craName(c))}</h2></div><div><div class="crn-big">${money(rows.filter(r => r.k).reduce((a, r) => a + (r.a || 0), 0))}</div><span class="crn-note">Counted dollars in the current filters, ${rows.length} records, ${named.size} named payees</span></div>
      <p><a href="/public-money/cra-spending">Open the full CRA ledger</a></p><button type="button" class="crn-btn" data-clear>Clear selection</button>`;
  } else if (id.startsWith('o:')) {
    const ds = D.don.filter(d => offId(d) === id);
    p.innerHTML = `<button type="button" class="crn-x" data-clear aria-label="Close details">×</button><div><span class="eyebrow">Elected official</span><h2>${esc(id.slice(2))}</h2><p class="crn-note">${esc(ds[0] ? ds[0].off : '')}</p></div>
      <div><div class="crn-big">${money(ds.reduce((a, d) => a + d.a, 0))}</div><span class="crn-note">from businesses and PACs on this page</span></div>
      <div class="crn-recs">${ds.map(d => `<div class="crn-rec"><span>${esc(d.dn)}${d.e ? ' <span class="crn-flag red">paid by a CRA</span>' : ''}</span><span class="num">${full(d.a)}</span><span class="crn-meta">${esc(d.date)}${d.u ? ` · <a href="${esc(d.u)}" target="_blank" rel="noopener">Campaign report</a>` : ''}</span></div>`).join('')}</div>
      <button type="button" class="crn-btn" data-clear>Clear selection</button>`;
  } else {
    const e = ent(id), all = D.recs.filter(r => r.e === id), shown = all.filter(r => st.cra.has(r.c) && st.status.has(r.s));
    const rel = D.rel.filter(x => x.a === id || x.b === id).map(x => { const o = x.a === id ? x.b : x.a; return `<div><button type="button" class="crn-link" data-sel="${esc(o)}">${esc(ent(o).n)}</button><div class="crn-note">${esc(x.t)} · <a href="${esc(x.u)}" target="_blank" rel="noopener">Source</a></div></div>`; });
    const dons = D.don.filter(d => d.e === id || 'd:' + d.dn === id);
    const cras = [...new Set(all.map(r => craName(r.c)))];
    p.innerHTML = `<button type="button" class="crn-x" data-clear aria-label="Close details">×</button><div><span class="eyebrow">${KIND[e.k] || ''}</span><h2>${esc(e.n)}</h2>${cras.length ? `<p class="crn-note">${esc(cras.join(' · '))}</p>` : ''}${e.vp ? `<p><a href="/public-money/vendors/${esc(e.vp)}">Vendor profile: every contract, payment and vote</a></p>` : ''}</div>
      ${all.length ? `<div><div class="crn-big">${money(all.reduce((a, r) => a + (r.a || 0), 0))}</div><span class="crn-note">across ${all.length} CRA record${all.length === 1 ? '' : 's'}${shown.length < all.length ? `, ${shown.length} in the current filters` : ''}. Contract records can sit inside a project total.</span></div>` : ''}
      ${rel.length ? `<div class="crn-rel"><h3 class="eyebrow">Connected payees</h3>${rel.join('')}</div>` : ''}
      ${e.k === 'biz' ? `<div class="crn-rel"><h3 class="eyebrow">Campaign gifts</h3>${dons.length ? dons.map(d => `<div>${full(d.a)} to ${esc(d.o)}, ${esc(d.off)} · ${esc(d.date)}${d.u ? ` · <a href="${esc(d.u)}" target="_blank" rel="noopener">Report</a>` : ''}${d.cf === 'likely' ? ' <span class="crn-flag">likely match</span>' : ''}</div>`).join('') : '<div class="crn-note">None in the campaign data.</div>'}</div>` : ''}
      ${all.length ? `<div><h3 class="eyebrow">CRA records</h3><div class="crn-recs">${all.map(r => `<div class="crn-rec"><span>${esc(r.w)}</span><span class="num">${full(r.a)}</span><span class="crn-meta"><span class="crn-pill" style="color:${SCOL[r.s] || 'var(--muted)'}">${esc(r.s)}</span><span>${esc(r.when)}</span><span>${esc(craName(r.c).replace(' CRA', ''))}</span>${r.k ? '' : '<span class="crn-flag">not in totals</span>'}${r.u ? `<a href="${esc(r.u)}" target="_blank" rel="noopener">Source</a>` : ''}</span>${r.nt ? `<span class="crn-meta">${esc(r.nt)}</span>` : ''}</div>`).join('')}</div></div>` : (e.k === 'biz' ? '<p class="crn-note">Not paid in the CRA ledger.</p>' : '')}
      <button type="button" class="crn-btn" data-clear>Clear selection</button>`;
  }
  p.querySelectorAll('[data-sel]').forEach(b => b.onclick = () => select(b.dataset.sel));
  p.querySelectorAll('[data-clear]').forEach(c => c.onclick = () => select(null));
}

function tip(e, h, id) { const t = $(id), b = t.parentElement.getBoundingClientRect(); t.innerHTML = h; t.hidden = false; let lx = e.clientX - b.left + 12; if (lx > b.width - 250) lx = e.clientX - b.left - 252; t.style.left = Math.max(4, lx) + 'px'; t.style.top = (e.clientY - b.top + 12) + 'px'; }
function hideTip(id) { $(id).hidden = true; }

function select(id) {
  st.sel = id; document.querySelector('.crn-main').classList.toggle('has-sel', !!id); profile();
  if (st.view === 'network' && hl) { hl(); if (fsOn && id) focusNode(id); } if (st.view === 'map') { map(visible()); if (fsOn && id) focusMap(id); }
  const wide = st.view === 'network' || st.view === 'map';
  if (id && !fsOn && (innerWidth <= 900 || (wide && innerWidth < 1100))) $('crnProfile').scrollIntoView({ behavior: 'smooth', block: 'start' });
}
let fsOn = false;
function setFull(on) {
  const m = document.querySelector('.crn-main');
  fsOn = on; m.classList.toggle('fs', on); document.documentElement.classList.toggle('crn-locked', on);
  document.querySelectorAll('.crn-fs').forEach(b => { b.textContent = on ? 'Exit full screen' : 'Full screen'; b.setAttribute('aria-pressed', on); });
  try {
    if (on && m.requestFullscreen && !document.fullscreenElement) m.requestFullscreen().catch(() => {});
    if (!on && document.fullscreenElement) document.exitFullscreen().catch(() => {});
  } catch (e) {}
  requestAnimationFrame(() => { if (st.view === 'network') graph(visible()); else if (st.view === 'map') map(visible()); });
}
function setView(v) {
  if (fsOn && v !== 'network' && v !== 'map') setFull(false);
  st.view = v;
  document.querySelector('.crn-main').classList.toggle('wide', v === 'map' || v === 'network');
  document.querySelectorAll('.crn-fsv').forEach(b => b.setAttribute('aria-pressed', b.dataset.v === v));
  ['network', 'map', 'payees', 'donations'].forEach(k => { $('v-' + k).hidden = k !== v; $('t-' + k).setAttribute('aria-selected', k === v); });
  if (location.hash.slice(1) !== v) history.replaceState(null, '', '#' + v);
  render();
}
function render() {
  const rows = visible(); kpis(rows);
  if (st.view === 'network') graph(rows); else if (st.view === 'map') map(rows); else if (st.view === 'payees') payees(rows); else donTable();
  profile();
}

function start() {
  controls();
  document.querySelectorAll('.crn-fs').forEach(b => b.onclick = () => setFull(!fsOn));
  document.querySelectorAll('.crn-fsv').forEach(b => b.onclick = () => setView(b.dataset.v));
  addEventListener('keydown', e => { if (e.key === 'Escape' && fsOn) { if (st.sel) select(null); else setFull(false); } });
  document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement && fsOn) setFull(false); });
  [['crnZin', 1.6], ['crnZout', 1 / 1.6], ['crnZreset', 0]].forEach(([id, f]) => { const b = $(id); if (b) b.onclick = () => mapBtn(f); });
  [['crnGin', 1.5], ['crnGout', 1 / 1.5], ['crnGreset', 0]].forEach(([id, f]) => { const b = $(id); if (b) b.onclick = () => graphBtn(f); });
  const h = location.hash.slice(1);
  setView(['network', 'map', 'payees', 'donations'].includes(h) ? h : 'network');
  fetch('/data/cra-geo.json').then(r => r.json()).then(g => { GEO = g; if (st.view === 'map') map(visible()); }).catch(() => { $('crnMap').innerHTML = '<text x="20" y="30" fill="var(--muted)" font-size="13">The map could not load. Try reloading the page.</text>'; });
  let rt; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { if (st.view === 'network') graph(visible()); }, 250); });
}
if (window.d3) start(); else addEventListener('load', start);
})();
