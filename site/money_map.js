(() => {
const D = __MM__;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const M = n => { const a = Math.abs(n || 0); return a >= 1e6 ? '$' + (n/1e6).toFixed(1) + 'M' : a >= 1e4 ? '$' + Math.round(n/1e3) + 'K' : '$' + Math.round(n || 0).toLocaleString(); };
// Days between a gift and a vote, said plainly: "on Mar 4, 2024, 834 days before the vote" (same wording as money_map.gift_when_text).
const dayGap = (g, v, short) => {
  const n = Math.round((Date.parse(v.slice(0, 10) + 'T12:00:00Z') - Date.parse(g.slice(0, 10) + 'T12:00:00Z')) / 864e5);
  if (!n) return 'the same day as the vote';
  return `${Math.abs(n).toLocaleString('en-US')} day${Math.abs(n) === 1 ? '' : 's'} ${n > 0 ? 'before' : 'after'}${short ? '' : ' the vote'}`;
};
const giftWhen = (ds, vote) => {
  ds = [...new Set((ds || []).filter(Boolean))].sort();
  if (!ds.length || !vote) return '';
  if (ds.length === 1) return ` on ${fd(ds[0])}, ${dayGap(ds[0], vote)}`;
  const parts = ds.map((d, i) => `${fd(d)} (${dayGap(d, vote, i > 0)})`);
  return ` on ${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`;
};
const fd = s => s ? new Date(s + 'T12:00:00').toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'}) : '';
const NS = 'http://www.w3.org/2000/svg';
const OFF = D.officials, DON = D.donors, GIFTS = D.gifts, CON = D.contracts, GN = D.govs, VOTES = D.votes;
const GORDER = Object.keys(GN);
const qs = new URLSearchParams(location.search);
// the city bar at the top picks the government; county officers (sheriff, clerk...) count with Bay County
const CITY = g => g === 'constitutional' ? 'county' : g;
const GOV = () => (window.BCM && BCM.city ? BCM.city.get() : '') || '';
const inGov = (g, k = GOV()) => !k || CITY(g) === k;
if (qs.get('show')) $('mmShow').value = qs.get('show');
if (qs.get('q')) $('mmQ').value = qs.get('q');
let sel = null; // {t:'d'|'o'|'g', id}
{ const m = /^([dog])-(.+)$/.exec(qs.get('sel') || ''); if (m) sel = {t: m[1], id: m[1] === 'g' ? m[2] : +m[2]}; }
function writeURL(later) { // keep the view in the link: ?show=&q=&sel=d-12 (the city bar keeps ?gov=)
  const u = new URL(location.href), set = (k, v) => v ? u.searchParams.set(k, v) : u.searchParams.delete(k);
  set('show', $('mmShow').value !== 'same' ? $('mmShow').value : ''); set('q', $('mmQ').value.trim()); set('sel', sel ? sel.t + '-' + sel.id : '');
  clearTimeout(writeURL.t); const go = () => history.replaceState(history.state, '', u.pathname + u.search + u.hash);
  if (later) writeURL.t = setTimeout(go, 350); else go();
}
const conAmt = c => c.a || c.p;
const sameDon = new Set(GIFTS.filter(g => g.same).map(g => g.d));

function filtered() {
  const show = $('mmShow').value, q = $('mmQ').value.trim().toLowerCase();
  const offs = new Set(OFF.filter(o => inGov(o.g)).map(o => o.id));
  let gifts = GIFTS.filter(g => offs.has(g.o));
  let dset;
  if (show === 'same') dset = sameDon;
  else if (show === 'k') dset = new Set(DON.filter(d => d.k).map(d => d.id));
  else if (show === 'top') { const t = {}; gifts.forEach(g => t[g.d] = (t[g.d] || 0) + g.a); dset = new Set(Object.keys(t).sort((a, b) => t[b] - t[a]).slice(0, 40).map(Number)); }
  else dset = new Set(DON.map(d => d.id));
  if (q) {
    const hitD = new Set(DON.filter(d => d.n.toLowerCase().includes(q)).map(d => d.id)), hitO = new Set(OFF.filter(o => o.n.toLowerCase().includes(q)).map(o => o.id));
    gifts = gifts.filter(g => hitD.has(g.d) || hitO.has(g.o));
  }
  gifts = gifts.filter(g => dset.has(g.d));
  const usedD = new Set(gifts.map(g => g.d)), usedO = new Set(gifts.map(g => g.o));
  const cons = CON.filter(c => usedD.has(c.d));
  return {gifts, cons, usedD, usedO};
}

function render() {
  const {gifts, cons, usedD, usedO} = filtered();
  const svg = $('mmSvg'); svg.innerHTML = '';
  const W = Math.max(760, $('mmWrap').clientWidth), RH = 22, PAD = 34;
  const offs = OFF.filter(o => usedO.has(o.id));
  const oy = {}; offs.forEach((o, i) => oy[o.id] = i);
  const bary = {}; gifts.forEach(g => (bary[g.d] = bary[g.d] || []).push(oy[g.o]));
  const avg = a => a.reduce((s, x) => s + x, 0) / a.length;
  const dons = DON.filter(d => usedD.has(d.id)).sort((a, b) => avg(bary[a.id]) - avg(bary[b.id]) || b.tot - a.tot);
  const govs = GORDER.filter(g => cons.some(c => c.g === g));
  const rows = Math.max(dons.length, offs.length, govs.length, 1);
  const H = PAD + rows * RH + 10;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('width', W); svg.setAttribute('height', H);
  const meas = document.createElementNS(NS, 'text'); meas.setAttribute('class', 'mm-meas'); svg.appendChild(meas);
  let OW = 60; offs.forEach(o => { meas.textContent = o.n + '  ' + (GN[o.g] || ''); OW = Math.max(OW, meas.getComputedTextLength() + 18); });
  let HW = 40; dons.forEach(d => { meas.textContent = d.n.length > 34 ? d.n.slice(0, 33) + '…' : d.n; HW = Math.max(HW, meas.getComputedTextLength() / 2 + 14); }); meas.remove();
  const xO = Math.min(OW, W * 0.3), xG = W - Math.min(170, W * 0.2), xD = Math.max(xO + 70 + HW, Math.min(xG - 90 - HW, (xO + xG) / 2));
  const yOf = (n, i) => PAD + (rows - n) * RH / 2 + i * RH + RH / 2;
  const P = {d: {}, o: {}, g: {}};
  dons.forEach((d, i) => P.d[d.id] = yOf(dons.length, i));
  offs.forEach((o, i) => P.o[o.id] = yOf(offs.length, i));
  govs.forEach((g, i) => P.g[g] = yOf(govs.length, i));
  const head = (x, t, anchor) => { const e = document.createElementNS(NS, 'text'); e.setAttribute('x', x); e.setAttribute('y', 14); e.setAttribute('class', 'mm-h'); e.setAttribute('text-anchor', anchor); e.textContent = t; svg.appendChild(e); };
  head(xO, 'Officials', 'end'); head(xD, 'Donor organizations', 'middle'); head(xG - 6, 'Pays the donor', 'start');
  const gmax = Math.max(1, ...gifts.map(g => g.a)), cmax = Math.max(1, ...cons.map(conAmt));
  const links = document.createElementNS(NS, 'g'); svg.appendChild(links);
  const path = (x1, y1, x2, y2) => { const m = (x1 + x2) / 2; return `M${x1},${y1} C${m},${y1} ${m},${y2} ${x2},${y2}`; };
  const LK = [];
  gifts.forEach(g => { const p = document.createElementNS(NS, 'path'); p.setAttribute('d', path(xO + 6, P.o[g.o], xD - HW, P.d[g.d])); p.setAttribute('class', 'mm-l gift' + (g.same ? ' same' : '')); p.setAttribute('stroke-width', (1 + 6 * Math.sqrt(g.a / gmax)).toFixed(1)); p._k = {d: g.d, o: g.o}; links.appendChild(p); LK.push(p); });
  cons.forEach(c => { const p = document.createElementNS(NS, 'path'); p.setAttribute('d', path(xD + HW, P.d[c.d], xG - 6, P.g[c.g])); p.setAttribute('class', 'mm-l con'); p.setAttribute('stroke-width', (1 + 6 * Math.sqrt(conAmt(c) / cmax)).toFixed(1)); p._k = {d: c.d, g: c.g}; links.appendChild(p); LK.push(p); });
  const NODES = [];
  const node = (t, id, x, y, label, sub, anchor, cls) => {
    const g = document.createElementNS(NS, 'g'); g.setAttribute('class', 'mm-n ' + cls); g.setAttribute('tabindex', '0'); g.setAttribute('role', 'button'); g.setAttribute('aria-label', label + (sub ? ', ' + sub : ''));
    const tx = document.createElementNS(NS, 'text'); tx.setAttribute('x', x); tx.setAttribute('y', y + 4); tx.setAttribute('text-anchor', anchor);
    if (anchor === 'middle') {
      tx.textContent = label.length > 34 ? label.slice(0, 33) + '…' : label;
      const bg = document.createElementNS(NS, 'rect'); bg.setAttribute('x', x - HW); bg.setAttribute('y', y - 10); bg.setAttribute('width', HW * 2); bg.setAttribute('height', 20); bg.setAttribute('rx', 10); bg.setAttribute('class', 'mm-pill');
      const t2 = document.createElementNS(NS, 'title'); t2.textContent = label + (sub ? ' · ' + sub : ''); g.appendChild(t2); g.appendChild(bg); g.appendChild(tx);
    } else {
      tx.innerHTML = `${esc(label)}<tspan class="mm-sub" dx="6">${esc(sub)}</tspan>`;
      const dot = document.createElementNS(NS, 'circle'); dot.setAttribute('cx', anchor === 'end' ? x + 6 : x - 6); dot.setAttribute('cy', y); dot.setAttribute('r', 4);
      g.appendChild(dot); g.appendChild(tx);
    }
    g._k = {t, id}; svg.appendChild(g); NODES.push(g);
    const pick = () => { sel = sel && sel.t === t && sel.id === id ? null : {t, id}; highlight(); detail(); writeURL(); };
    g.addEventListener('click', pick); g.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } });
  };
  offs.forEach(o => node('o', o.id, xO, P.o[o.id], o.n, GN[o.g] || '', 'end', ''));
  dons.forEach(d => node('d', d.id, xD, P.d[d.id], d.n, M(gifts.filter(g => g.d === d.id).reduce((s, g) => s + g.a, 0)) + ' given', 'middle', sameDon.has(d.id) ? 'k' : ''));
  govs.forEach(g => node('g', g, xG, P.g[g], GN[g], '', 'start', ''));
  svg._LK = LK; svg._N = NODES;
  $('mmCount').textContent = `${dons.length} donors · ${offs.length} officials · ${gifts.length} gifts`;
  if (sel && !NODES.some(n => n._k.t === sel.t && n._k.id === sel.id)) sel = null;
  highlight(); detail();
  writeURL(true);
}

function highlight() {
  const svg = $('mmSvg');
  svg.classList.toggle('dim', !!sel);
  if (!sel) { svg._N.forEach(n => n.classList.remove('on')); svg._LK.forEach(l => l.classList.remove('on')); return; }
  const on = {d: new Set(), o: new Set(), g: new Set()};
  // a donor shows its gifts and its contracts; an official shows its gifts and those donors' contracts; a government shows the donors it pays and their gifts
  const donorsOf = sel.t === 'd' ? new Set([sel.id]) : sel.t === 'o' ? new Set(GIFTS.filter(g => g.o === sel.id).map(g => g.d)) : new Set(CON.filter(c => c.g === sel.id).map(c => c.d));
  svg._LK.forEach(l => {
    const k = l._k; let hit;
    if (sel.t === 'o') hit = k.o === sel.id || (k.g && k.g === OFF[sel.id].g && donorsOf.has(k.d));
    else if (sel.t === 'g') hit = k.g === sel.id || (!k.g && donorsOf.has(k.d));
    else hit = k.d === sel.id;
    hit = !!hit; l.classList.toggle('on', hit);
    if (hit) { on.d.add(k.d); if (k.o != null) on.o.add(k.o); if (k.g) on.g.add(k.g); }
  });
  on[sel.t].add(sel.id);
  svg._N.forEach(n => n.classList.toggle('on', on[n._k.t].has(n._k.id)));
}
function conLine(c) {
  const parts = [];
  if (c.n) parts.push(`${c.n} contract${c.n > 1 ? 's' : ''}${c.a ? ' totaling ' + M(c.a) : ''}`);
  if (c.p) parts.push(`${M(c.p)} in payments`);
  if (c.co) parts.push(`${c.co} change order${c.co > 1 ? 's' : ''} or other records`);
  return parts.join(', ');
}
function items(c) { return `<details class="flds"><summary>Records</summary><ul class="plain small">${c.items.map(s => `<li>${esc(s)}</li>`).join('')}</ul><p class="small">${c.urls.map((u, i) => `<a class="src" href="${esc(u)}" target="_blank" rel="noopener">Source ${i + 1}</a>`).join(' · ')}</p></details>`; }
const giftTxt = g => `<b>${M(g.a)}</b>${g.dates && g.dates.length ? ` <span class="muted small">${g.dates.map(fd).join(', ')}</span>` : ''}`;
function detail() {
  const el = $('mmDetail');
  if (!sel) { el.innerHTML = '<p class="muted">Tap an official, donor or government to see its connections and the records behind them.</p>'; return; }
  if (sel.t === 'd') {
    const d = DON[sel.id], gs = GIFTS.filter(g => g.d === d.id).sort((a, b) => b.a - a.a), cs = CON.filter(c => c.d === d.id), vs = VOTES.filter(v => v.d === d.id);
    el.innerHTML = `<h3>${d.vp ? `<a href="/public-money/vendors/${esc(d.vp)}">${esc(d.n)}</a>` : esc(d.n)}</h3><p class="small muted">${d.t === 'pac' ? 'Political committee' : 'Organization'} · gave ${M(gs.reduce((s, g) => s + g.a, 0))} to ${gs.length} official${gs.length > 1 ? 's' : ''}</p>
      <h4>Campaign gifts</h4><ul class="plain mm-list">${gs.map(g => `<li>${giftTxt(g)} to ${esc(OFF[g.o].n)} <span class="muted">${esc(OFF[g.o].off)}</span>${g.same ? ' <span class="badge warn">Their government pays this donor</span>' : ''}</li>`).join('')}</ul>
      ${cs.length ? `<h4>Paid by local governments</h4><ul class="plain mm-list">${cs.map(c => `<li><b>${esc(GN[c.g])}</b>: ${conLine(c)}${c.likely ? ' <span class="muted small">(name spelled differently in the campaign filing)</span>' : ''}${items(c)}</li>`).join('')}</ul>` : '<p class="small muted">No contracts or payments from a local government matched on this site.</p>'}
      ${vs.length ? `<h4>Votes on this donor's contracts</h4><ul class="plain mm-list">${vs.map(v => `<li>${esc(OFF[v.o].n)} voted <b>${esc(v.vote)}</b> · ${fd(v.date)} · ${esc(v.h)}${v.consent ? ' <span class="muted small">(consent agenda)</span>' : ''}</li>`).join('')}</ul>` : ''}`;
  } else if (sel.t === 'o') {
    const o = OFF[sel.id], gs = GIFTS.filter(g => g.o === o.id).sort((a, b) => b.a - a.a), same = gs.filter(g => g.same), vs = VOTES.filter(v => v.o === o.id);
    el.innerHTML = `<h3>${esc(o.n)}</h3><p class="small muted">${esc(o.off)} · raised ${M(o.raised)}: ${M(o.ind)} from ${o.indn} individuals, ${M(gs.reduce((s, g) => s + g.a, 0))} from ${gs.length} organizations · <a class="src" href="${esc(o.url)}" target="_blank" rel="noopener">Campaign report</a></p>
      ${same.length ? `<h4>Donors that ${esc(GN[o.g])} also pays</h4><ul class="plain mm-list">${same.map(g => { const c = CON.find(x => x.d === g.d && x.g === o.g); return `<li><b>${esc(DON[g.d].n)}</b> gave ${giftTxt(g)} · ${esc(GN[o.g])}: ${c ? conLine(c) : ''}${c ? items(c) : ''}</li>`; }).join('')}</ul>` : `<p class="small muted">None of this official's organization donors matched a contract with ${esc(GN[o.g] || 'their government')}.</p>`}
      ${vs.length ? `<h4>Recorded votes on those donors' contracts</h4><ul class="plain mm-list">${vs.map(v => `<li>Voted <b>${esc(v.vote)}</b> · ${fd(v.date)} · ${esc(DON[v.d].n)}: ${esc(v.h)}${v.consent ? ' <span class="muted small">(consent agenda)</span>' : ''}${v.when === 'before' ? ' · the gift came after this vote' : v.when === 'after' ? ' · the gift came before this vote' : ''}</li>`).join('')}</ul>` : ''}
      <details class="flds"><summary>All ${gs.length} organization donors</summary><ul class="plain small">${gs.map(g => `<li>${esc(DON[g.d].n)} · ${M(g.a)}</li>`).join('')}</ul></details>`;
  } else {
    const cs = CON.filter(c => c.g === sel.id).sort((a, b) => conAmt(b) - conAmt(a));
    el.innerHTML = `<h3>${esc(GN[sel.id])}</h3><p class="small muted">Pays ${cs.length} organization${cs.length > 1 ? 's' : ''} that gave to current officials' campaigns. Each is counted once.</p>
      <ul class="plain mm-list">${cs.map(c => { const gs = GIFTS.filter(g => g.d === c.d); return `<li><b>${esc(DON[c.d].n)}</b>: ${conLine(c)}<br><span class="small">Gave to ${gs.map(g => `${esc(OFF[g.o].n)} (${M(g.a)})${g.same ? ' <span class="badge warn">' + esc(GN[OFF[g.o].g]) + ' official</span>' : ''}`).join(', ')}</span>${items(c)}</li>`; }).join('')}</ul>`;
  }
}

function votesTable() {
  const t = $('mmVotes'), VG = (D.vgroups || []).filter(v => inGov(v.g));
  let none = $('mmVotesNone');
  if (!none) { none = document.createElement('p'); none.id = 'mmVotesNone'; none.className = 'muted'; t.after(none); }
  t.hidden = !VG.length; none.hidden = !!VG.length; if (!VG.length) t.innerHTML = '';
  none.textContent = GOV() ? `No recorded votes by ${BCM.city.label(GOV())} officials on their donors' contracts.` : 'No recorded votes found.';
  if (!VG.length) return;
  const member = (m, v) => {
    const name = m.gift ? `<b>${esc(m.n)}</b>` : esc(m.n);
    const vote = m.vote === 'yes' ? 'yes' : `<b>${esc(m.vote)}</b>`;
    const gift = m.gift ? `<span class="small">, got ${M(m.gift)}${giftWhen(m.gift_dates, v.date)}</span>` : '';
    return `<li>${name}: ${vote}${gift}</li>`;
  };
  t.innerHTML = `<thead><tr><th scope="col">Date</th><th scope="col">Donor</th><th scope="col">Item</th><th scope="col">Roll call</th></tr></thead><tbody>${VG.map(v => `<tr>
    <td>${fd(v.date)}<small>${esc(GN[v.g] || '')}</small></td>
    <th scope="row">${esc(DON[v.d].n)}</th>
    <td class="wrap small">${esc(v.h)}${v.amount ? ' · ' + M(v.amount) : ''}${v.consent ? ' <span class="muted">(consent agenda)</span>' : ''}${v.url ? ` <a class="src" href="${esc(v.url)}" target="_blank" rel="noopener">Minutes</a>` : ''}</td>
    <td class="wrap small"><span>${esc(v.outcome || '')}${v.tally ? ' ' + esc(v.tally) : ''}</span><ul class="plain mm-roll">${v.roll.map(m => member(m, v)).join('')}</ul></td></tr>`).join('')}</tbody>`;
}

function shade(v, max) { if (!v) return ''; const t = Math.pow(v / max, 0.5); return `style="--h:${(12 + t * 78).toFixed(0)}%"${t > 0.55 ? ' data-hi' : ''}`; }
function heat1() {
  const govs = GORDER.filter(g => inGov(g) && OFF.some(o => o.g === g)), GIFTS_ = GIFTS.filter(g => inGov(OFF[g.o].g));
  const tot = {}; GIFTS_.forEach(g => tot[g.d] = (tot[g.d] || 0) + g.a);
  const top = Object.keys(tot).map(Number).sort((a, b) => tot[b] - tot[a]).slice(0, 30);
  const cell = {}; let mx = 1;
  GIFTS_.forEach(g => { if (!top.includes(g.d)) return; const k = g.d + '|' + OFF[g.o].g; cell[k] = (cell[k] || 0) + g.a; mx = Math.max(mx, cell[k]); });
  const ring = new Set(CON.map(c => c.d + '|' + c.g));
  if (!top.length) { $('mmHeat1').innerHTML = `<tbody><tr><td class="muted">No organization gave to ${esc(BCM.city.label(GOV()))} officials' campaigns.</td></tr></tbody>`; return; }
  $('mmHeat1').innerHTML = `<thead><tr><th scope="col">Donor</th>${govs.map(g => `<th scope="col"><span>${esc(GN[g])}</span></th>`).join('')}<th scope="col" class="num">Total</th></tr></thead><tbody>${top.map(d => `<tr><th scope="row">${esc(DON[d].n)}</th>${govs.map(g => { const v = cell[d + '|' + g]; const offs = GIFTS.filter(x => x.d === d && OFF[x.o].g === g).map(x => `${OFF[x.o].n} ${M(x.a)}`).join(', '); return `<td class="hc${v ? ' v' : ''}${v && ring.has(d + '|' + g) ? ' ring' : ''}" ${shade(v, mx)}${v ? ` title="${esc(DON[d].n)} → ${esc(offs)}"` : ''}>${v ? M(v) : ''}</td>`; }).join('')}<td class="num">${M(tot[d])}</td></tr>`).join('')}</tbody>`;
}

$('mmShow').addEventListener('change', () => { sel = null; render(); });
$('mmQ').addEventListener('input', render);
let rt; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { if (!$('v-donors')?.hidden) render(); }, 150); });
let first = true;
const all = () => { if (!first) sel = null; first = false; render(); votesTable(); heat1(); };
if (window.BCM && BCM.city) BCM.city.on(all); else all();
// the Connections page shows this as its "Donors and votes" view: redraw when the view opens, at its real width
window.MM = {render: () => { render(); votesTable(); heat1(); }};
if (sel && qs.get('sel') && !$('v-donors')?.hidden) $('map').scrollIntoView();
})();
