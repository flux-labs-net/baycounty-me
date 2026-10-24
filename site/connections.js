/* Connections (/connections). Data is built by site/connections.py and inlined below.
   Views: force-directed network (d3), payee table, business gifts to officials. Covers every government and agency
   with payment records; a CRA is one payer among the rest. */
(function () {
const D = __CN__;
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const money = v => v == null ? 'Amount not stated' : v >= 1e6 ? '$' + (v / 1e6).toFixed(v >= 1e7 ? 1 : 2) + 'M' : v >= 1e3 ? '$' + Math.round(v / 1e3).toLocaleString() + 'K' : '$' + Math.round(v).toLocaleString();
const full = v => v == null ? '—' : '$' + Math.round(v).toLocaleString();
const url = i => i == null ? null : D.urls[i];
const KIND = { biz: 'Business or nonprofit', gov: 'Public body, fund or bondholders', prop: 'Property owner', unnamed: 'Payee not named', grants: 'Grant recipients, not named', official: 'Elected official', candidate: '2026 candidate', payer: 'Government or agency' };
const PKIND = { gov: 'Government', cra: 'Redevelopment agency (CRA)', tourism: 'Tourism agency' };
const COL = { payer: 'var(--navy)', biz: 'var(--blue)', gov: 'var(--muted)', prop: 'var(--amber)', unnamed: 'var(--surface)', grants: 'var(--surface)', official: 'var(--salmon)', candidate: 'var(--salmon)' };
const TOP = 40;  // payees shown by dollars in the "key payees" view, besides every donor and linked payee
const st = { pay: new Set(Object.keys(D.payers)), types: new Set(Object.keys(D.types)), scope: 'focus', focus: new Set(), don: 'payees', sel: null, view: 'trail', city: '' };
const ent = id => id.startsWith('m:') ? { n: (D.off[id] || {}).n || id.slice(2), k: (D.off[id] || {}).cand ? 'candidate' : 'official' }
  : id.startsWith('p:') ? { n: D.payers[id.slice(2)].n, k: 'payer' } : D.ents[id] || (id.startsWith('d:') ? { n: id.slice(2), k: 'biz' } : { n: id, k: 'biz' });
const payerName = p => D.payers[p] ? D.payers[p].n : p;
const visible = () => D.recs.filter(r => st.pay.has(r.p) && st.types.has(r.t));
const gaveSet = new Set(D.don.filter(d => d.e).map(d => d.e));
const linked = new Set(D.rel.flatMap(x => [x.a, x.b]));
const offShown = o => !st.city || o.g === st.city;
const donShown = () => st.don === 'off' ? [] : D.don.filter(d => (st.don === 'payees' ? !!d.e : true) && offShown(D.off[d.o] || {}));

function chip(label, pressed, onclick, id) {
  const b = document.createElement('button'); b.type = 'button'; b.className = 'cn-chip'; b.textContent = label; if (id) b.id = id;
  b.setAttribute('aria-pressed', pressed); b.onclick = () => onclick(b); return b;
}
function radio(groupId, opts, cur, set) {
  const g = $(groupId);
  opts.forEach(([k, l]) => g.appendChild(chip(l, cur === k, b => { set(k); g.querySelectorAll('.cn-chip').forEach(x => x.setAttribute('aria-pressed', x === b)); }, groupId + '-' + k)));
}
function controls() {
  document.querySelectorAll('[data-payer]').forEach(b => b.onclick = () => { const k = b.dataset.payer; st.pay.has(k) ? st.pay.delete(k) : st.pay.add(k); b.setAttribute('aria-pressed', st.pay.has(k)); render(); });
  Object.entries(D.types).forEach(([k, l]) => $('cnTypes').appendChild(chip(l, st.types.has(k), b => { st.types.has(k) ? st.types.delete(k) : st.types.add(k); b.setAttribute('aria-pressed', st.types.has(k)); render(); })));
  radio('cnScope', [['focus', 'Start from a name'], ['key', 'Donors and top payees'], ['all', 'Every payee']], st.scope, k => { st.scope = k; render(); });
  radio('cnDon', [['payees', 'Donors who were paid'], ['all', 'All business donors'], ['off', 'Hide']], st.don, k => { st.don = k; render(); });
  document.querySelectorAll('.cn-tab').forEach(b => b.onclick = () => setView(b.dataset.v));
}

/* The government picker at the top narrows the payers to one city's government, its CRA and nothing else
   (Bay County also keeps the tourism agencies, which the county runs). Clearing it turns every payer back on. */
function cityToPayers(k) {
  st.city = k || '';
  st.pay = new Set(Object.keys(D.payers).filter(p => !k || D.payers[p].g === k));
  document.querySelectorAll('[data-payer]').forEach(b => b.setAttribute('aria-pressed', st.pay.has(b.dataset.payer)));
}

function payeeTotals(rows) {
  const m = new Map();
  rows.forEach(r => { const o = m.get(r.e) || { e: r.e, tot: 0, n: 0, p: new Set(), t: new Set(), unk: 0 }; o.tot += r.a || 0; o.n++; o.p.add(r.p); o.t.add(r.t); if (r.a == null) o.unk++; m.set(r.e, o); });
  return m;
}
function shownPayees(rows) {
  const m = payeeTotals(rows);
  if (st.scope === 'all') return new Set(m.keys());
  const keep = new Set([...m.values()].sort((a, b) => b.tot - a.tot).slice(0, TOP).map(o => o.e));
  m.forEach((o, e) => { if (gaveSet.has(e) || linked.has(e)) keep.add(e); });
  if (st.sel && m.has(st.sel)) keep.add(st.sel);
  return keep;
}

function kpis(rows) {
  const m = payeeTotals(rows), named = [...m.keys()].filter(e => /^[vb]:/.test(e));
  const paidDon = named.filter(e => gaveSet.has(e));
  const gifts = D.don.filter(d => offShown(D.off[d.o] || {}));
  const paidGifts = gifts.filter(d => d.e && m.has(d.e));
  $('cnKpis').innerHTML = [
    ['Named payees', named.length.toLocaleString(), `paid by ${new Set(rows.map(r => r.p)).size} governments and agencies in the current filters`],
    ['Paid and gave', paidDon.length, 'businesses paid in these records that gave to a campaign'],
    ['Their gifts', money(paidGifts.reduce((a, d) => a + d.a, 0)), `${paidGifts.length} donor and official pair${paidGifts.length === 1 ? '' : 's'}`],
    ['All business gifts', money(gifts.reduce((a, d) => a + d.a, 0)), `to ${new Set(gifts.map(d => d.o)).size} officials and candidates in the gift records`],
  ].map(([l, v, s]) => `<div class="kpi"><span class="eyebrow">${l}</span><span class="v">${v}</span><span class="s">${s}</span></div>`).join('');
}

let sim, hl, graphZoom;
function focusNode(id) {
  const svg = d3.select('#cnGraph'), n = svg.selectAll('.cn-node').filter(d => d.id === id);
  if (!n || n.empty() || !graphZoom) return;
  const d = n.datum(), r = svg.node().getBoundingClientRect(), vb = svg.node().viewBox.baseVal, sx = vb.width / r.width;
  const phone = innerWidth < 700, cx = phone ? vb.width / 2 : (vb.width - 380 * sx) / 2, cy = phone ? vb.height * 0.25 : vb.height / 2;
  const t = d3.zoomTransform(svg.node()), k = Math.max(t.k, 1.2);
  svg.transition().duration(400).call(graphZoom.transform, d3.zoomIdentity.translate(cx - d.x * k, cy - d.y * k).scale(k));
}
function graphBtn(f) { const svg = d3.select('#cnGraph'); if (!graphZoom) return; if (f === 0) svg.transition().duration(250).call(graphZoom.transform, d3.zoomIdentity); else svg.transition().duration(250).call(graphZoom.scaleBy, f); }
function graph(rows) {
  const svg = d3.select('#cnGraph'), W = svg.node().clientWidth || 800, H = svg.node().clientHeight || 620;
  svg.attr('viewBox', `0 0 ${W} ${H}`).selectAll('*').remove();
  if (sim) sim.stop();
  const keep = st.scope === 'focus' ? new Set(rows.map(r => r.e)) : shownPayees(rows);
  const nodes = new Map(), links = new Map();
  const add = (id, o) => { if (!nodes.has(id)) nodes.set(id, { id, total: 0, ...o }); return nodes.get(id); };
  rows.forEach(r => {
    if (!keep.has(r.e)) return;
    add('p:' + r.p, { n: payerName(r.p), k: 'payer' });
    const e = ent(r.e); add(r.e, { n: e.n, k: e.k }).total += r.a || 0;
    const key = 'p:' + r.p + '|' + r.e, l = links.get(key) || { source: 'p:' + r.p, target: r.e, type: 'paid', amt: 0 };
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
    if (d.e && !nodes.has(d.e) && st.don === 'payees') return;  // a paid donor whose payments are filtered out
    const o = add(d.o, { n: ent(d.o).n, k: ent(d.o).k });
    const donor = d.e || 'd:' + d.dn;
    if (!nodes.has(donor)) add(donor, { n: d.e ? ent(d.e).n : d.dn, k: 'biz' });
    const key = donor + '>' + o.id, l = links.get(key) || { source: donor, target: o.id, type: 'don', amt: 0 }; l.amt += d.a; links.set(key, l);
    ((D.off[d.o] || {}).gp || []).forEach(p => { if (nodes.has('p:' + p)) links.set(o.id + '@' + p, { source: o.id, target: 'p:' + p, type: 'board' }); });
  });
  let N = [...nodes.values()], L = [...links.values()];
  if (st.scope === 'focus') {
    if (!st.focus.size) { graphPrompt(svg, W, H); hl = null; return; }
    // the picked names and their direct connections; a government or agency brings its donors, linked payees and largest payees
    const keepN = new Set(st.focus), nbr = new Map();
    L.forEach(l => [[l.source, l.target], [l.target, l.source]].forEach(([a, b]) => { if (st.focus.has(a)) { if (!nbr.has(a)) nbr.set(a, []); nbr.get(a).push([b, l]); } }));
    nbr.forEach((list, a) => {
      if (a.startsWith('p:') && list.length > 18) {
        const key = list.filter(([b, l]) => l.type !== 'paid' || gaveSet.has(b) || linked.has(b));
        const big = list.filter(([, l]) => l.type === 'paid').sort((x, y) => y[1].amt - x[1].amt).slice(0, 12);
        list = [...new Set([...key, ...big])];
      }
      list.forEach(([b]) => keepN.add(b));
    });
    N = N.filter(n => keepN.has(n.id));
    L = L.filter(l => keepN.has(l.source) && keepN.has(l.target) && (st.focus.has(l.source) || st.focus.has(l.target) || l.type !== 'paid'));
  }
  if (!N.length) { svg.append('text').attr('x', 20).attr('y', 30).attr('fill', 'var(--muted)').attr('font-size', 13).text('Nothing matches these filters.'); hl = null; return; }
  const rS = d3.scaleSqrt().domain([0, d3.max(N.filter(n => n.k !== 'payer'), d => d.total) || 1]).range([4, 22]);
  const wS = d3.scaleSqrt().domain([0, d3.max(L.filter(l => l.type === 'paid'), d => d.amt) || 1]).range([0.8, 7]);
  N.forEach(n => n.r = n.k === 'payer' ? 17 : n.k === 'official' || n.k === 'candidate' ? 8 : Math.max(5, rS(n.total)));
  const connected = new Set(L.filter(l => l.type !== 'paid').flatMap(l => [l.source, l.target]));  // labelled when the graph is small
  const g = svg.append('g');
  // labels keep the same on-screen size at every zoom level
  graphZoom = d3.zoom().scaleExtent([0.2, 5]).on('zoom', e => {
    const k = e.transform.k; g.attr('transform', e.transform);
    g.selectAll('.cn-node text').style('font-size', d => (d.k === 'payer' ? 12 : 10.5) / k + 'px').style('stroke-width', 3 / k + 'px').attr('dy', d => d.r + 11 / k);
  });
  svg.call(graphZoom);
  const link = g.append('g').selectAll('line').data(L).join('line')
    .attr('stroke', d => d.type === 'rel' ? 'var(--amber)' : d.type === 'paid' ? 'var(--faint)' : d.type === 'board' ? 'var(--navy)' : 'var(--salmon)')
    .attr('stroke-opacity', d => d.type === 'paid' ? 0.5 : d.type === 'board' ? 0.5 : 0.95)
    .attr('stroke-width', d => d.type === 'paid' ? wS(d.amt) : d.type === 'don' ? 2 : 1.5)
    .attr('stroke-dasharray', d => d.type === 'rel' ? '5 4' : d.type === 'board' ? '2 3' : null);
  const node = g.append('g').selectAll('g').data(N).join('g').attr('class', 'cn-node')
    .call(d3.drag().on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.2).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; }).on('end', (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));
  node.append('circle').attr('r', d => d.r).attr('fill', d => COL[d.k] || COL.biz)
    .attr('stroke', d => d.k === 'unnamed' || d.k === 'grants' ? 'var(--faint)' : d.k === 'payer' ? 'var(--ink)' : 'var(--surface)')
    .attr('stroke-width', d => d.k === 'unnamed' || d.k === 'grants' ? 1.5 : d.k === 'payer' ? 2 : 1.2)
    .attr('stroke-dasharray', d => d.k === 'grants' || d.k === 'candidate' ? '3 2' : null)
    .classed('cn-focus', d => st.focus.has(d.id))
    .attr('tabindex', 0).attr('role', 'button').attr('aria-label', d => d.n)
    .on('click', (e, d) => select(d.id)).on('keydown', (e, d) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(d.id); } })
    .on('mousemove', (e, d) => tip(e, `<b>${esc(d.n)}</b><br>${d.k === 'payer' ? PKIND[D.payers[d.id.slice(2)].k] : KIND[d.k]}${d.total ? ' · ' + money(d.total) + ' in records' : ''}`, 'cnTip')).on('mouseleave', () => hideTip('cnTip'));
  node.append('text').attr('dy', d => d.r + 12).attr('text-anchor', 'middle')
    .text(d => d.k === 'payer' ? d.n : (d.r > 13 || N.length < 60 || (N.length < 90 && (connected.has(d.id) || d.k === 'official'))) ? (d.n.length > 30 ? d.n.slice(0, 29) + '…' : d.n) : '')
    .attr('class', d => d.k === 'payer' ? 'cn-pl' : null);
  sim = d3.forceSimulation(N)
    .force('link', d3.forceLink(L).id(d => d.id).distance(d => (N.length < 60 ? 1.7 : 1) * (d.type === 'rel' ? 60 : d.type === 'board' ? 90 : 95)).strength(d => d.type === 'paid' ? 0.5 : d.type === 'board' ? 0.15 : 0.8))
    .force('charge', d3.forceManyBody().strength(d => d.k === 'payer' ? -700 : N.length < 60 ? -260 : -90))
    .force('collide', d3.forceCollide(d => d.r + 4))
    .force('x', d3.forceX(W / 2).strength(0.05)).force('y', d3.forceY(H / 2).strength(0.07))
    .on('tick', () => { link.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y); node.attr('transform', d => `translate(${d.x},${d.y})`); });
  for (let i = 0; i < 260; i++) sim.tick();
  {  // start with the whole network in view
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

function graphPrompt(svg, W, H) {
  const g = svg.append('g').attr('class', 'cn-prompt');
  g.append('text').attr('x', W / 2).attr('y', H / 2 - 14).attr('text-anchor', 'middle').text('Search for a business, official or government above,');
  g.append('text').attr('x', W / 2).attr('y', H / 2 + 10).attr('text-anchor', 'middle').text('or tap a name in Money trail or Payees. Tap any circle to expand it.');
}
function searchBox() {
  const opts = new Map();
  Object.entries(D.payers).forEach(([k, p]) => opts.set(p.n, 'p:' + k));
  Object.entries(D.off).forEach(([k, o]) => opts.set(o.n + (o.cand ? ' (2026 candidate)' : ''), k));
  const has = new Set(D.recs.map(r => r.e));
  Object.entries(D.ents).forEach(([k, e]) => { if (has.has(k) && /^[vb]:/.test(k)) opts.set(e.n, k); });
  $('cnFind').innerHTML = [...opts.keys()].sort().map(n => `<option value="${esc(n)}">`).join('');
  const go = () => {
    const id = opts.get($('cnQ').value.trim()); if (!id) return; $('cnQ').value = '';
    if (st.scope !== 'focus') { st.scope = 'focus'; document.querySelectorAll('#cnScope .cn-chip').forEach(x => x.setAttribute('aria-pressed', x.id === 'cnScope-focus')); }
    if (st.view !== 'network') setView('network');
    select(id);
  };
  $('cnQ').addEventListener('change', go);
  $('cnQ').addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
  $('cnClear').onclick = () => { st.focus.clear(); select(null); if (st.view === 'network') graph(visible()); };
}

/* Money trail: who paid a business (left), the business (middle), and the officials it gave to (right).
   Only businesses that were both paid in the current filters and gave to a campaign. */
let trailHl = () => {};
function trail(rows) {
  const svg = d3.select('#cnTrail'); svg.selectAll('*').remove();
  const paid = new Map();  // business -> payer -> dollars in records
  rows.forEach(r => { if (!gaveSet.has(r.e)) return; const m = paid.get(r.e) || new Map(); m.set(r.p, (m.get(r.p) || 0) + (r.a || 0)); paid.set(r.e, m); });
  const gifts = new Map();  // business -> official -> dollars
  D.don.forEach(d => { if (!d.e || !paid.has(d.e) || !offShown(D.off[d.o] || {})) return; const m = gifts.get(d.e) || new Map(); m.set(d.o, (m.get(d.o) || 0) + d.a); gifts.set(d.e, m); });
  const biz = [...gifts.keys()];
  $('cnTrailCount').textContent = `${biz.length} businesses paid and gave · tap a name for its records`;
  if (!biz.length) { svg.attr('viewBox', '0 0 800 80').attr('width', 800).attr('height', 80); svg.append('text').attr('x', 20).attr('y', 40).attr('class', 'cn-tl').text('No business in these filters was both paid and a campaign donor.'); trailHl = () => {}; return; }
  const payerOrder = Object.keys(D.payers);
  const pays = payerOrder.filter(p => biz.some(b => paid.get(b).has(p)));
  // businesses sit next to the government that paid them most; payers and officials next to their businesses
  const main = b => payerOrder.indexOf([...paid.get(b).entries()].sort((a, c) => c[1] - a[1])[0][0]);
  biz.sort((a, b) => main(a) - main(b) || ent(a).n.localeCompare(ent(b).n));
  const bi = new Map(biz.map((b, i) => [b, i]));
  const mean = xs => xs.reduce((a, x) => a + x, 0) / xs.length;
  const offs = [...new Set(biz.flatMap(b => [...gifts.get(b).keys()]))];
  const ob = new Map(offs.map(o => [o, mean(biz.filter(b => gifts.get(b).has(o)).map(b => bi.get(b)))]));
  offs.sort((a, b) => ob.get(a) - ob.get(b));
  const pb = new Map(pays.map(p => [p, mean(biz.filter(b => paid.get(b).has(p)).map(b => bi.get(b)))]));
  pays.sort((a, b) => pb.get(a) - pb.get(b));
  // phones get two columns (business, official) with who paid it written under each business
  const avail = svg.node().parentElement.clientWidth || 900, phone = avail < 640;
  const W = phone ? avail : Math.max(760, avail), row = phone ? 40 : 30, top = 40;
  const H = top + Math.max(biz.length, offs.length, phone ? 0 : pays.length) * row + 16;
  svg.attr('viewBox', `0 0 ${W} ${H}`).attr('width', W).attr('height', H);
  const colW = phone ? W * 0.44 : Math.min(250, W * 0.26), xL = colW, xM0 = phone ? 0 : W / 2 - colW / 2, xM1 = phone ? W * 0.45 : W / 2 + colW / 2, xR = phone ? W * 0.64 : W - colW;
  const fit = (t, w) => { const n = Math.max(8, Math.floor(w / 6.8)); return t.length > n ? t.slice(0, n - 1) + '…' : t; };
  const yOf = (n, i) => top + (H - top - 16) * (i + 0.5) / n;
  const Y = new Map();
  pays.forEach((p, i) => Y.set('p:' + p, yOf(pays.length, i)));
  biz.forEach((b, i) => Y.set(b, yOf(biz.length, i)));
  offs.forEach((o, i) => Y.set(o, yOf(offs.length, i)));
  const hd = svg.append('g').attr('class', 'cn-th');
  (phone ? [[12, 'start', 'Business paid, and a donor'], [xR, 'start', 'Gave to']] : [[xL, 'end', 'Paid by'], [W / 2, 'middle', 'Business paid, and a donor'], [xR, 'start', 'Gave to']]).forEach(([x, a, t]) => hd.append('text').attr('x', x).attr('y', 18).attr('text-anchor', a).text(t));
  const L = [], maxP = d3.max(biz.flatMap(b => [...paid.get(b).values()])) || 1, maxG = d3.max(biz.flatMap(b => [...gifts.get(b).values()])) || 1;
  const wP = d3.scaleSqrt().domain([0, maxP]).range([1, 9]), wG = d3.scaleSqrt().domain([0, maxG]).range([1.2, 7]);
  biz.forEach(b => {
    if (!phone) paid.get(b).forEach((v, p) => L.push({ a: 'p:' + p, b, x0: xL + 8, x1: xM0 - 6, w: wP(v), c: 'var(--faint)', t: `${esc(payerName(p))} paid ${esc(ent(b).n)} ${money(v)} in records` }));
    gifts.get(b).forEach((v, o) => L.push({ a: b, b: o, x0: xM1 + 6, x1: xR - 8, w: wG(v), c: 'var(--salmon)', t: `${esc(ent(b).n)} gave ${esc(ent(o).n)} ${full(v)}` }));
  });
  const path = l => { const y0 = Y.get(l.a), y1 = Y.get(l.b), m = (l.x0 + l.x1) / 2; return `M${l.x0},${y0}C${m},${y0} ${m},${y1} ${l.x1},${y1}`; };
  const lk = svg.append('g').attr('fill', 'none').selectAll('path').data(L).join('path').attr('d', path).attr('stroke', d => d.c).attr('stroke-width', d => d.w).attr('stroke-opacity', 0.55)
    .on('mousemove', (e, d) => tip(e, d.t, 'cnTip3')).on('mouseleave', () => hideTip('cnTip3'));
  const label = (id, x, anchor, txt, cls, sub) => {
    const g = svg.append('g').attr('class', 'cn-tn ' + cls).attr('data-id', id).attr('tabindex', 0).attr('role', 'button').attr('aria-label', txt)
      .on('click', () => select(id)).on('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(id); } });
    const w = anchor === 'middle' ? colW - 24 : phone ? (anchor === 'start' && x > 20 ? W - x - 4 : colW - 22) : colW - 10;
    g.append('text').attr('x', x).attr('y', Y.get(id) - (sub ? 7 : 0)).attr('dy', '0.35em').attr('text-anchor', anchor).text(fit(txt, w)).append('title').text(txt);
    if (sub) g.append('text').attr('class', 'cn-ts').attr('x', x).attr('y', Y.get(id) + 9).attr('dy', '0.35em').attr('text-anchor', anchor).text(fit(sub, w));
  };
  if (!phone) pays.forEach(p => label('p:' + p, xL, 'end', payerName(p), 'cn-tp'));
  biz.forEach(b => phone ? label(b, 12, 'start', ent(b).n, 'cn-tb', 'Paid by ' + [...paid.get(b).keys()].map(payerName).join(', ')) : label(b, W / 2, 'middle', ent(b).n, 'cn-tb'));
  offs.forEach(o => { const O = D.off[o] || {}; label(o, xR, 'start', O.n + (O.cand ? ' (candidate)' : ''), 'cn-to'); });
  svg.append('g').selectAll('circle').data([...(phone ? [] : pays.map(p => ['p:' + p, xL + 5, 'var(--navy)'])), ...biz.flatMap(b => phone ? [[b, xM1 + 3, 'var(--blue)']] : [[b, xM0 - 3, 'var(--blue)'], [b, xM1 + 3, 'var(--blue)']]), ...offs.map(o => [o, xR - 5, 'var(--salmon)'])])
    .join('circle').attr('cx', d => d[1]).attr('cy', d => Y.get(d[0])).attr('r', 3.5).attr('fill', d => d[2]);
  trailHl = () => {
    const s = st.sel;
    if (!s || !Y.has(s)) { lk.classed('dim', false); svg.selectAll('.cn-tn').classed('dim', false).classed('on', false); return; }
    // a business: its own lines. A payer or official: the businesses it touches, with their lines on the other side too.
    const isBiz = bi.has(s);
    const bs = new Set(isBiz ? [s] : L.filter(l => l.a === s || l.b === s).map(l => l.a === s ? l.b : l.a));
    const keep = new Set(L.filter(l => (bs.has(l.a) || bs.has(l.b)) && (isBiz || l.a === s || l.b === s || (s.startsWith('p:') ? l.b.startsWith('m:') : l.a.startsWith('p:')))));
    const on = new Set([s, ...[...keep].flatMap(l => [l.a, l.b])]);
    lk.classed('dim', l => !keep.has(l));
    svg.selectAll('.cn-tn').classed('dim', function () { return !on.has(this.dataset.id); }).classed('on', function () { return this.dataset.id === s; });
  };
  trailHl();
}

function payees(rows) {
  const list = [...payeeTotals(rows).values()].sort((a, b) => b.tot - a.tot);
  $('cnPayCount').textContent = `${list.length} payees · tap a row for its records`;
  $('cnPay').innerHTML = `<thead><tr><th>Payee</th><th>Type</th><th>Paid by</th><th>Records</th><th class="num">Count</th><th class="num">Dollars in records</th></tr></thead><tbody>` +
    list.map(o => { const e = ent(o.e); return `<tr class="cn-row" tabindex="0" data-e="${esc(o.e)}"><td><b>${esc(e.n)}</b>${gaveSet.has(o.e) ? ' <span class="cn-flag red">gave</span>' : ''}</td><td>${KIND[e.k]}</td><td>${[...o.p].map(payerName).map(esc).join(', ')}</td><td>${[...o.t].map(t => esc(D.types[t])).join(', ')}</td><td class="num">${o.n}${o.unk ? ` <span class="cn-flag">${o.unk} no $</span>` : ''}</td><td class="num">${full(o.tot)}</td></tr>`; }).join('') + '</tbody>';
  $('cnPay').querySelectorAll('tr.cn-row').forEach(t => { t.onclick = () => select(t.dataset.e); t.onkeydown = e => { if (e.key === 'Enter') select(t.dataset.e); }; });
}

function donTable() {
  const rows = D.don.filter(d => offShown(D.off[d.o] || {}));
  $('cnDonCount').textContent = `${rows.length} donor and official pairs · ${money(rows.reduce((a, d) => a + d.a, 0))}`;
  $('cnDonT').innerHTML = `<thead><tr><th>Business or group</th><th>Official</th><th>Office</th><th class="num">Amount</th><th>Date</th><th>Also paid by a government</th></tr></thead><tbody>` +
    rows.map((d, i) => { const o = D.off[d.o] || {}; return `<tr><td>${esc(d.dn)}${d.ty === 'pac' || d.ty === 'committee' ? ` <span class="cn-flag">${d.ty.toUpperCase() === 'PAC' ? 'PAC' : 'committee'}</span>` : ''}</td><td><button type="button" class="cn-link" data-off="${i}">${esc(o.n)}</button>${o.cand ? ' <span class="cn-flag">2026 candidate</span>' : ''}</td><td>${esc(o.off)}</td><td class="num">${full(d.a)}${d.n > 1 ? ` <span class="cn-flag">${d.n} gifts</span>` : ''}</td><td class="num">${esc(d.date)}</td><td>${d.e ? `<button type="button" class="cn-link" data-ent="${esc(d.e)}">${esc(ent(d.e).n)}</button>${d.cf === 'likely' ? ' <span class="cn-flag">likely</span>' : ''}` : '—'}</td></tr>`; }).join('') + '</tbody>';
  $('cnDonT').querySelectorAll('[data-ent]').forEach(b => b.onclick = () => { setView('network'); select(b.dataset.ent); });
  $('cnDonT').querySelectorAll('[data-off]').forEach(b => b.onclick = () => {
    const d = rows[+b.dataset.off];
    if (st.don !== 'all') { st.don = 'all'; document.querySelectorAll('#cnDon .cn-chip').forEach(x => x.setAttribute('aria-pressed', x.id === 'cnDon-all')); }
    setView('network'); select(d.o);
  });
}

const src = u => u ? ` · <a href="${esc(u)}" target="_blank" rel="noopener">Source</a>` : '';
function recList(rs) {
  return `<div class="cn-recs">${rs.map(r => `<div class="cn-rec"><span>${esc(r.w || D.types[r.t])}</span><span class="num">${full(r.a)}</span><span class="cn-meta"><span class="cn-pill">${esc(D.types[r.t])}</span>${r.s ? `<span>${esc(r.s)}</span>` : ''}<span>${esc(r.when)}</span><span>${esc(payerName(r.p))}</span>${r.x ? '<span class="cn-flag">inside a project total</span>' : ''}${url(r.u) ? `<a href="${esc(url(r.u))}" target="_blank" rel="noopener">Source</a>` : ''}</span></div>`).join('')}</div>`;
}
function byType(rs) {
  const m = {}; rs.forEach(r => { m[r.t] = (m[r.t] || 0) + (r.a || 0); });
  return Object.keys(D.types).filter(t => t in m).map(t => `<div class="cn-rec"><span>${esc(D.types[t])}</span><span class="num">${full(m[t])}</span></div>`).join('');
}
function profile() {
  const p = $('cnProfile'), id = st.sel;
  const close = '<button type="button" class="cn-x" data-clear aria-label="Close details">×</button>', clear = '<button type="button" class="cn-btn" data-clear>Clear selection</button>';
  if (!id) {
    const starts = [...gaveSet].filter(e => D.ents[e]).slice(0, 5);
    p.innerHTML = `<h3 class="eyebrow">Start here</h3><p>Tap any circle or table row to see its full record. These businesses were paid by a local government and also gave to a campaign:</p>
      <div class="cn-starts">${starts.map(k => `<button type="button" class="cn-link" data-sel="${k}">${esc(ent(k).n)}</button>`).join('')}</div>
      <p class="cn-note">A line is a documented connection, not evidence of wrongdoing. Contracts are usually bid, and spending is approved by the full board.</p>`;
  } else if (id.startsWith('p:')) {
    const k = id.slice(2), P = D.payers[k], rows = visible().filter(r => r.p === k), named = new Set(rows.filter(r => /^[vb]:/.test(r.e)).map(r => r.e));
    const offs = Object.entries(D.off).filter(([, o]) => (o.gp || []).includes(k));
    p.innerHTML = `${close}<div><span class="eyebrow">${PKIND[P.k]}</span><h2>${esc(P.n)}</h2></div>
      <div><span class="cn-note">${rows.length} records in the current filters, ${named.size} named payees. Contract awards and check register payments can describe the same money, so the types are not added together.</span></div>
      <div class="cn-recs">${byType(rows)}</div>
      ${offs.length ? `<div class="cn-rel"><h3 class="eyebrow">Elected board</h3>${offs.map(([oid, o]) => `<div><button type="button" class="cn-link" data-sel="${esc(oid)}">${esc(o.n)}</button> <span class="cn-note">${esc(o.off)}</span></div>`).join('')}</div>` : ''}
      ${P.k === 'cra' ? '<p><a href="/public-money/cra-spending">Open the full CRA ledger</a></p>' : P.k === 'tourism' ? '<p><a href="/public-money/who-gets-paid">Every tourism agency payment</a></p>' : '<p><a href="/public-money/contracts">Contracts and awards</a></p>'}${clear}`;
  } else if (id.startsWith('m:')) {
    const o = D.off[id] || {}, ds = D.don.filter(d => d.o === id);
    p.innerHTML = `${close}<div><span class="eyebrow">${o.cand ? '2026 candidate' : 'Elected official'}</span><h2>${esc(o.n)}</h2><p class="cn-note">${esc(o.off)}</p></div>
      <div><div class="cn-big">${money(ds.reduce((a, d) => a + d.a, 0))}</div><span class="cn-note">from businesses, PACs and committees. Gifts from individual people are never named.</span></div>
      ${(o.gp || []).length ? `<p class="cn-note">Sits on: ${o.gp.map(k => `<button type="button" class="cn-link" data-sel="p:${esc(k)}">${esc(payerName(k))}</button>`).join(', ')}</p>` : ''}
      <div class="cn-recs">${ds.map(d => `<div class="cn-rec"><span>${d.e ? `<button type="button" class="cn-link" data-sel="${esc(d.e)}">${esc(d.dn)}</button> <span class="cn-flag red">paid by a government</span>` : esc(d.dn)}</span><span class="num">${full(d.a)}</span><span class="cn-meta">${esc(d.date)}${url(d.u) ? ` · <a href="${esc(url(d.u))}" target="_blank" rel="noopener">Campaign report</a>` : ''}</span></div>`).join('')}</div>${clear}`;
  } else {
    const e = ent(id), all = D.recs.filter(r => r.e === id), shown = all.filter(r => st.pay.has(r.p) && st.types.has(r.t));
    const rel = D.rel.filter(x => x.a === id || x.b === id).map(x => { const o = x.a === id ? x.b : x.a; return `<div><button type="button" class="cn-link" data-sel="${esc(o)}">${esc(ent(o).n)}</button><div class="cn-note">${esc(x.t)}${src(x.u)}</div></div>`; });
    const dons = D.don.filter(d => d.e === id || 'd:' + d.dn === id);
    const by = [...new Set(all.map(r => payerName(r.p)))];
    p.innerHTML = `${close}<div><span class="eyebrow">${KIND[e.k] || ''}</span><h2>${esc(e.n)}</h2>${by.length ? `<p class="cn-note">Paid by ${esc(by.join(' · '))}</p>` : ''}${e.vp ? `<p><a href="/public-money/vendors/${esc(e.vp)}">Vendor profile: every contract, payment and vote</a></p>` : ''}</div>
      ${all.length ? `<div><span class="cn-note">${all.length} record${all.length === 1 ? '' : 's'}${shown.length < all.length ? `, ${shown.length} in the current filters` : ''}. An award and the payments on it can both appear, so the types are not added together.</span><div class="cn-recs">${byType(all)}</div></div>` : ''}
      ${rel.length ? `<div class="cn-rel"><h3 class="eyebrow">Connected payees</h3>${rel.join('')}</div>` : ''}
      ${e.k === 'biz' ? `<div class="cn-rel"><h3 class="eyebrow">Campaign gifts</h3>${dons.length ? dons.map(d => { const o = D.off[d.o] || {}; return `<div>${full(d.a)} to <button type="button" class="cn-link" data-sel="${esc(d.o)}">${esc(o.n)}</button>, ${esc(o.off)}${o.cand ? ' (2026 candidate)' : ''} · ${esc(d.date)}${url(d.u) ? ` · <a href="${esc(url(d.u))}" target="_blank" rel="noopener">Report</a>` : ''}${d.cf === 'likely' ? ' <span class="cn-flag">likely match</span>' : ''}</div>`; }).join('') : '<div class="cn-note">None in the campaign data.</div>'}</div>` : ''}
      ${all.length ? `<div><h3 class="eyebrow">Records</h3>${recList(all)}</div>` : ''}${clear}`;
  }
  p.querySelectorAll('[data-sel]').forEach(b => b.onclick = () => select(b.dataset.sel));
  p.querySelectorAll('[data-clear]').forEach(c => c.onclick = () => select(null));
}

function tip(e, h, id) { const t = $(id), b = t.parentElement.getBoundingClientRect(); t.innerHTML = h; t.hidden = false; let lx = e.clientX - b.left + 12; if (lx > b.width - 250) lx = e.clientX - b.left - 252; t.style.left = Math.max(4, lx) + 'px'; t.style.top = (e.clientY - b.top + 12) + 'px'; }
function hideTip(id) { $(id).hidden = true; }

function select(id) {
  st.sel = id; document.querySelector('.cn-main').classList.toggle('has-sel', !!id); profile();
  if (st.view === 'network') {
    // a payee outside the "key payees" set joins the graph when picked
    if (id && st.scope === 'focus') { if (!st.focus.has(id)) { st.focus.add(id); graph(visible()); } }
    else if (id && D.ents[id] && !d3.select('#cnGraph').selectAll('.cn-node').filter(d => d.id === id).size()) graph(visible());
    if (hl) hl();
    if (fsOn && id) focusNode(id);
  }
  if (st.view === 'trail') trailHl();
  if (id && !fsOn && (innerWidth <= 900 || (st.view === 'network' && innerWidth < 1100))) $('cnProfile').scrollIntoView({ behavior: 'smooth', block: 'start' });
}
let fsOn = false;
function setFull(on) {
  const m = document.querySelector('.cn-main');
  fsOn = on; m.classList.toggle('fs', on); document.documentElement.classList.toggle('cn-locked', on);
  document.querySelectorAll('.cn-fs').forEach(b => { b.textContent = on ? 'Exit full screen' : 'Full screen'; b.setAttribute('aria-pressed', on); });
  try {
    if (on && m.requestFullscreen && !document.fullscreenElement) m.requestFullscreen().catch(() => {});
    if (!on && document.fullscreenElement) document.exitFullscreen().catch(() => {});
  } catch (e) {}
  requestAnimationFrame(() => { if (st.view === 'network') graph(visible()); });
}
const VIEWS = ['trail', 'network', 'payees', 'gifts'];
function setView(v) {
  if (fsOn && v !== 'network') setFull(false);
  st.view = v;
  document.querySelector('.cn-main').classList.toggle('wide', v === 'network');
  VIEWS.forEach(k => { $('v-' + k).hidden = k !== v; $('t-' + k).setAttribute('aria-selected', k === v); });
  if (location.hash.slice(1) !== v) history.replaceState(null, '', location.pathname + location.search + '#' + v);
  render();
}
function render() {
  const rows = visible(); kpis(rows);
  if (st.view === 'trail') trail(rows); else if (st.view === 'network') graph(rows); else if (st.view === 'payees') payees(rows); else donTable();
  profile();
}

function start() {
  controls();
  searchBox();
  document.querySelectorAll('.cn-fs').forEach(b => b.onclick = () => setFull(!fsOn));
  addEventListener('keydown', e => { if (e.key === 'Escape' && fsOn) { if (st.sel) select(null); else setFull(false); } });
  document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement && fsOn) setFull(false); });
  [['cnGin', 1.5], ['cnGout', 1 / 1.5], ['cnGreset', 0]].forEach(([id, f]) => { const b = $(id); if (b) b.onclick = () => graphBtn(f); });
  BCM.city.on((k, d) => { cityToPayers(k); if (d.why !== 'now') { if (st.sel && !st.sel.startsWith('m:') && !st.sel.startsWith('p:') && !visible().some(r => r.e === st.sel)) st.sel = null; render(); } });
  const h = location.hash.slice(1);
  setView(VIEWS.includes(h) ? h : h === 'donations' ? 'gifts' : 'trail');
  let rt; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { if (st.view === 'network') graph(visible()); else if (st.view === 'trail') trail(visible()); }, 250); });
}
if (window.d3) start(); else addEventListener('load', start);
})();
