/* Connections (/connections). Data is built by site/connections.py and inlined below.
   One page, four parts: a money flow (governments -> businesses -> campaigns), a ranked list of businesses that were
   paid and gave, a story panel for any picked name (who paid it, who it gave to, how those officials voted, with a
   one-name connections map and a gift-and-vote timeline), and tables of every record. */
(function () {
const D = __CN__;
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const money = v => v == null ? 'Amount not stated' : v >= 1e6 ? '$' + (v / 1e6).toFixed(v >= 1e7 ? 1 : 2) + 'M' : v >= 1e3 ? '$' + (v >= 1e4 ? Math.round(v / 1e3) : (v / 1e3).toFixed(1).replace(/\.0$/, '')) + 'K' : '$' + Math.round(v).toLocaleString();
const full = v => v == null ? '—' : '$' + Math.round(v).toLocaleString();
const url = i => i == null ? null : D.urls[i];
const plural = (n, w, ws) => `${n.toLocaleString()} ${n === 1 ? w : (ws || w + 's')}`;
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const day = s => { const m = /^(\d{4})-(\d\d)-(\d\d)/.exec(s || ''); return m ? `${MON[+m[2] - 1]} ${+m[3]}, ${m[1]}` : (s || ''); };
const KIND = { biz: 'Business or nonprofit', gov: 'Public body, fund or bondholders', prop: 'Property owner', unnamed: 'Payee not named', grants: 'Grant recipients, not named', official: 'Elected official', candidate: 'Candidate', payer: 'Government or agency' };
const PKIND = { gov: 'Government', cra: 'Redevelopment agency (CRA)', tourism: 'Tourism agency' };
const st = { pay: new Set(Object.keys(D.payers)), types: new Set(Object.keys(D.types)), don: 'payees', sel: null, pv: 'story', view: 'payees', city: '', sort: 'paid', more: false, picked: false };
const candLbl = o => o.yr ? `${o.yr} candidate` : '2026 candidate';
const ent = id => id.startsWith('m:') ? { n: (D.off[id] || {}).n || id.slice(2), k: (D.off[id] || {}).cand ? 'candidate' : 'official' }
  : id.startsWith('p:') ? { n: D.payers[id.slice(2)].n, k: 'payer' } : D.ents[id] || (id.startsWith('d:') ? { n: id.slice(2), k: 'biz' } : { n: id, k: 'biz' });
const payerName = p => D.payers[p] ? D.payers[p].n : p;
const visible = () => D.recs.filter(r => st.pay.has(r.p) && st.types.has(r.t));
const offShown = o => !st.city || o.g === st.city;
const amt = r => r.x ? 0 : (r.a || 0);  // x: already inside a larger CRA project total
const offLabel = o => o ? (o.off || '') + (o.cand ? ` (${candLbl(o)})` : '') : '';
const isDonor = d => d.e && offShown(D.off[d.o] || {});
const bcHref = id => window.BC ? BC.href(id) : null;
function personHref(oid) { const o = D.off[oid]; return o && o.pid ? `/people/${o.pid}` : null; }

/* ---------- shared numbers ---------- */
function paidMap(rows) {  // payee -> payer -> dollars
  const m = new Map();
  rows.forEach(r => { const x = m.get(r.e) || new Map(); x.set(r.p, (x.get(r.p) || 0) + amt(r)); m.set(r.e, x); });
  return m;
}
const sum = m => [...m.values()].reduce((a, v) => a + v, 0);
function giftsOf(e) { return D.don.filter(d => d.e === e && offShown(D.off[d.o] || {})); }
function votesFor(e) { return D.votes.filter(v => v.c === e && (!st.city || offShown(D.off[v.m] || { g: '' }))); }
const voteKey = v => v.d + '|' + v.h;
function groupVotes(vs) {  // one row per motion, with the members who had a gift
  const g = new Map();
  vs.forEach(v => { const k = voteKey(v) + '|' + v.cn; const o = g.get(k) || { ...v, who: [] }; o.who.push(v); g.set(k, o); });
  return [...g.values()].sort((a, b) => b.d.localeCompare(a.d));
}

/* ---------- KPIs ---------- */
function kpis(rows) {
  const m = paidMap(rows), named = [...m.keys()].filter(e => /^[vb]:/.test(e));
  const gifts = D.don.filter(d => offShown(D.off[d.o] || {}));
  const paidGifts = gifts.filter(d => d.e && m.has(d.e));
  const paidDon = new Set(paidGifts.map(d => d.e));
  const vs = D.votes.filter(v => v.c && paidDon.has(v.c));
  $('cnKpis').innerHTML = [
    ['Named payees', named.length.toLocaleString(), `paid by ${new Set(rows.map(r => r.p)).size} governments and agencies`],
    ['Paid and gave', paidDon.size, 'businesses paid in these records that gave to a campaign'],
    ['Their gifts', money(paidGifts.reduce((a, d) => a + d.a, 0)), `${plural(paidGifts.length, 'business and official pair')}`],
    ['Votes on their work', new Set(vs.map(voteKey)).size.toLocaleString(), 'motions naming one of them, voted on by someone it gave to'],
  ].map(([l, v, s]) => `<div class="kpi"><span class="eyebrow">${l}</span><span class="v">${v}</span><span class="s">${s}</span></div>`).join('');
}

/* ---------- the ranked list (paid and gave) ---------- */
function listData(rows) {
  const pm = paidMap(rows), out = new Map();
  D.don.forEach(d => {
    if (!isDonor(d) || !pm.has(d.e)) return;
    const o = out.get(d.e) || { e: d.e, paid: sum(pm.get(d.e)), govs: pm.get(d.e).size, gave: 0, offs: new Set() };
    o.gave += d.a; o.offs.add(d.o); out.set(d.e, o);
  });
  out.forEach(o => { o.votes = new Set(votesFor(o.e).map(voteKey)).size; });
  return [...out.values()];
}
function list(rows) {
  const L = listData(rows);
  const by = { paid: (a, b) => b.paid - a.paid, gave: (a, b) => b.gave - a.gave || b.paid - a.paid, votes: (a, b) => b.votes - a.votes || b.paid - a.paid }[st.sort];
  L.sort(by);
  const cut = 10, shown = st.more ? L : L.slice(0, cut);
  $('cnListNote').textContent = L.length ? `${plural(L.length, 'business was', 'businesses were')} paid by a local government and gave to a campaign. Tap one to see its story.` : 'No business in these records was both paid and a campaign donor.';
  $('cnList').innerHTML = shown.map((o, i) => `<li><button type="button" class="cn-ri" data-sel="${esc(o.e)}"${st.sel === o.e ? ' aria-current="true"' : ''}><span class="cn-n">${i + 1}</span><span class="cn-rb"><b>${esc(ent(o.e).n)}</b><span class="cn-mini"><span>${money(o.paid)} paid · ${plural(o.govs, 'govt')}</span><span class="g">${full(o.gave)} to ${plural(o.offs.size, 'campaign')}</span>${o.votes ? `<span class="v">${plural(o.votes, 'vote')}</span>` : ''}</span></span></button></li>`).join('');
  $('cnList').querySelectorAll('[data-sel]').forEach(b => b.onclick = () => select(b.dataset.sel, true));
  const more = $('cnMore'); more.hidden = L.length <= cut; more.textContent = st.more ? 'Show fewer' : `Show all ${L.length}`;
  more.onclick = () => { st.more = !st.more; list(visible()); };
  return L;
}

/* ---------- money flow (Sankey) ---------- */
let flowHl = () => {};
function flow(rows) {
  const svg = d3.select('#cnFlow'); svg.selectAll('*').remove();
  const avail = svg.node().parentElement.clientWidth || 900, phone = avail < 640;
  const L = listData(rows).sort((a, b) => b.paid - a.paid), NB = phone ? 8 : 12, NO = phone ? 9 : 14;
  const biz = L.slice(0, NB).map(o => o.e);
  $('cnFlowCount').textContent = L.length ? (L.length > NB ? `Top ${NB} of ${L.length} businesses by dollars paid` : `${plural(L.length, 'business', 'businesses')}`) : '';
  if (!biz.length) { svg.attr('viewBox', '0 0 600 60').attr('height', 60); svg.append('text').attr('x', 12).attr('y', 34).attr('class', 'cn-empty').text('No business in these records was both paid and a campaign donor.'); flowHl = () => {}; return; }
  const pm = paidMap(rows);
  const pay = new Map(biz.map(b => [b, pm.get(b)]));
  const gift = new Map(biz.map(b => [b, new Map()]));
  D.don.forEach(d => { if (isDonor(d) && gift.has(d.e)) gift.get(d.e).set(d.o, (gift.get(d.e).get(d.o) || 0) + d.a); });
  // officials: the largest recipients; the rest share one "other campaigns" node
  const offTot = new Map(); gift.forEach(m => m.forEach((v, o) => offTot.set(o, (offTot.get(o) || 0) + v)));
  const offs = [...offTot.keys()].sort((a, b) => offTot.get(b) - offTot.get(a));
  const keepO = new Set(offs.slice(0, NO)), OTHER = 'm:*';
  if (offs.length > NO) gift.forEach(m => { let x = 0; [...m.keys()].forEach(o => { if (!keepO.has(o)) { x += m.get(o); m.delete(o); } }); if (x) m.set(OTHER, x); });
  const order = Object.keys(D.payers), pays = order.filter(p => biz.some(b => pay.get(b).has(p)));
  const main = b => order.indexOf([...pay.get(b).entries()].sort((a, c) => c[1] - a[1])[0][0]);
  biz.sort((a, b) => main(a) - main(b) || pay.get(b).size - pay.get(a).size);
  const bi = new Map(biz.map((b, i) => [b, i])), mean = xs => xs.reduce((a, x) => a + x, 0) / xs.length;
  const pays2 = pays.sort((a, b) => mean(biz.filter(x => pay.get(x).has(a)).map(x => bi.get(x))) - mean(biz.filter(x => pay.get(x).has(b)).map(x => bi.get(x))));
  const offL = [...new Set(biz.flatMap(b => [...gift.get(b).keys()]))].sort((a, b) => a === OTHER ? 1 : b === OTHER ? -1 : mean(biz.filter(x => gift.get(x).has(a)).map(x => bi.get(x))) - mean(biz.filter(x => gift.get(x).has(b)).map(x => bi.get(x))));
  // geometry: payments and gifts get their own scale so both sides fill the same height
  const W = phone ? avail : Math.max(720, avail), top = 30, gap = phone ? 6 : 8, minRow = phone ? 26 : 22;
  const body = Math.max(phone ? 300 : 380, biz.length * (minRow + gap));
  const totP = biz.reduce((a, b) => a + sum(pay.get(b)), 0) || 1, totG = biz.reduce((a, b) => a + sum(gift.get(b)), 0) || 1;
  const kP = body * 0.72 / totP, kG = body * 0.72 / totG;
  const nw = phone ? 6 : 10;
  const x0 = phone ? 76 : Math.min(190, W * 0.2), x1 = phone ? W * 0.43 : W * 0.44, x2 = phone ? W - 92 : W - Math.min(200, W * 0.22);
  const col = (ids, hOf) => { let y = top; const m = new Map(); ids.forEach(id => { const h = Math.max(2, hOf(id)); const row = Math.max(h, minRow); m.set(id, { y: y + (row - h) / 2, h }); y += row + gap; }); return [m, y]; };
  const [PY, yP] = col(pays2, p => biz.reduce((a, b) => a + (pay.get(b).get(p) || 0), 0) * kP);
  const [BY, yB] = col(biz, b => Math.max(sum(pay.get(b)) * kP, sum(gift.get(b)) * kG));
  const [OY, yO] = col(offL, o => biz.reduce((a, b) => a + (gift.get(b).get(o) || 0), 0) * kG);
  const H = Math.max(yP, yB, yO) + 6;
  const center = (m, yEnd) => { const off = (H - yEnd) / 2; m.forEach(v => { v.y += off; }); };
  center(PY, yP); center(BY, yB); center(OY, yO);
  svg.attr('viewBox', `0 0 ${W} ${H}`).attr('width', W).attr('height', H);
  const hd = svg.append('g').attr('class', 'cn-th');
  [[x0 + nw / 2, phone ? 'middle' : 'middle', 'Paid by'], [x1 + nw / 2, 'middle', 'Business'], [x2 + nw / 2, 'middle', 'Gave to']].forEach(([x, a, t]) => hd.append('text').attr('x', x).attr('y', 14).attr('text-anchor', a).text(t));
  // bands
  const bands = [], outP = new Map(), inB = new Map(), outB = new Map(), inO = new Map();
  const take = (m, id, h) => { const o = m.get(id) || 0; m.set(id, o + h); return o; };
  biz.forEach(b => pays2.filter(p => pay.get(b).has(p)).forEach(p => { const v = pay.get(b).get(p), h = Math.max(1, v * kP); bands.push({ a: 'p:' + p, b, v, h, ya: PY.get(p).y + take(outP, p, h), yb: BY.get(b).y + take(inB, b, h), xa: x0 + nw, xb: x1, k: 'pay' }); }));
  biz.forEach(b => offL.filter(o => gift.get(b).has(o)).forEach(o => { const v = gift.get(b).get(o), h = Math.max(1, v * kG); bands.push({ a: b, b: o, v, h, ya: BY.get(b).y + take(outB, b, h), yb: OY.get(o).y + take(inO, o, h), xa: x1 + nw, xb: x2, k: 'gift' }); }));
  const band = d => { const m = (d.xa + d.xb) / 2; return `M${d.xa},${d.ya}C${m},${d.ya} ${m},${d.yb} ${d.xb},${d.yb}L${d.xb},${d.yb + d.h}C${m},${d.yb + d.h} ${m},${d.ya + d.h} ${d.xa},${d.ya + d.h}Z`; };
  const nm = id => id === OTHER ? 'Other campaigns' : id.startsWith('p:') ? payerName(id.slice(2)) : ent(id).n;
  const bk = svg.append('g').selectAll('path').data(bands).join('path').attr('class', d => 'cn-band ' + d.k).attr('d', band)
    .on('mousemove', (e, d) => tip(e, d.k === 'pay' ? `${esc(nm(d.a))} paid ${esc(nm(d.b))} ${full(d.v)} in records` : `${esc(nm(d.a))} gave ${esc(nm(d.b))} ${full(d.v)}`))
    .on('mouseleave', hideTip).on('click', (e, d) => select(d.k === 'pay' ? d.b : d.a, true));
  // nodes and labels
  const fit = (t, px) => { const n = Math.max(6, Math.floor(px / (phone ? 5.9 : 6.6))); return t.length > n ? t.slice(0, n - 1).trimEnd() + '…' : t; };
  const node = (id, x, v, cls, lx, anchor, room) => {
    const g = svg.append('g').attr('class', 'cn-nd ' + cls).attr('data-id', id);
    if (id !== OTHER) g.attr('tabindex', 0).attr('role', 'button').attr('aria-label', nm(id)).on('click', () => select(id, true)).on('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(id, true); } });
    g.append('rect').attr('x', x).attr('y', v.y).attr('width', nw).attr('height', v.h).attr('rx', 2);
    const t = g.append('text').attr('x', lx).attr('y', v.y + v.h / 2).attr('dy', '0.35em').attr('text-anchor', anchor).text(fit(nm(id), room));
    t.append('title').text(nm(id));
  };
  pays2.forEach(p => node('p:' + p, x0, PY.get(p), 'pay', x0 - 6, 'end', x0 - 8));
  biz.forEach(b => node(b, x1, BY.get(b), 'biz', x1 + nw + 6, 'start', (x2 - x1) * (phone ? 0.62 : 0.5)));
  offL.forEach(o => node(o, x2, OY.get(o), o === OTHER ? 'off other' : 'off', x2 + nw + 6, 'start', W - x2 - nw - 8));
  flowHl = () => {
    const s = st.picked ? st.sel : null, ids = new Set([...PY.keys()].map(p => 'p:' + p).concat(biz, offL));
    if (!s || !ids.has(s)) { bk.classed('dim', false).classed('on', false); svg.selectAll('.cn-nd').classed('dim', false).classed('on', false); return; }
    const bs = new Set(biz.includes(s) ? [s] : bands.filter(d => d.a === s || d.b === s).map(d => d.a === s ? d.b : d.a));
    const keep = new Set(bands.filter(d => biz.includes(s) ? (d.a === s || d.b === s) : (d.a === s || d.b === s || (bs.has(d.a) && d.k === (s.startsWith('p:') ? 'gift' : 'pay')) || (bs.has(d.b) && d.k === (s.startsWith('p:') ? 'gift' : 'pay')))));
    const on = new Set([s, ...[...keep].flatMap(d => [d.a, d.b])]);
    bk.classed('dim', d => !keep.has(d)).classed('on', d => keep.has(d));
    svg.selectAll('.cn-nd').classed('dim', function () { return !on.has(this.dataset.id); }).classed('on', function () { return this.dataset.id === s; });
  };
  flowHl();
}
function tip(e, h) { const t = $('cnTip'), b = t.parentElement.getBoundingClientRect(); t.innerHTML = h; t.hidden = false; let lx = e.clientX - b.left + 12; if (lx > b.width - 250) lx = e.clientX - b.left - 252; t.style.left = Math.max(4, lx) + 'px'; t.style.top = (e.clientY - b.top + 12) + 'px'; }
function hideTip() { $('cnTip').hidden = true; }

/* ---------- the story panel ---------- */
const bars = (items, cls) => { const max = Math.max(...items.map(x => x.v), 1); return `<div class="cn-bars">${items.map(x => `<div class="cn-bar1 ${cls || ''}">${x.id ? `<button type="button" class="cn-link" data-sel="${esc(x.id)}">${esc(x.n)}</button>` : `<span>${esc(x.n)}</span>`}<span class="t"><i style="width:${Math.max(2, x.v / max * 100).toFixed(1)}%"></i></span><em>${money(x.v)}</em></div>`).join('')}</div>`; };
const fold = (label, html) => html ? `<details class="cn-fold"><summary>${label}</summary>${html}</details>` : '';
const step = (n, title, body) => `<section class="cn-step"><h3><span class="cn-sn">${n}</span>${title}</h3>${body}</section>`;
const facts = fs => `<div class="cn-facts">${fs.map(([v, s]) => `<div><b>${v}</b><span>${s}</span></div>`).join('')}</div>`;
const vpill = v => `<span class="cn-vp ${v === 'yes' ? 'yes' : 'other'}">${v === 'yes' ? 'Yes' : v === 'abstain' ? 'Abstained' : v === 'absent' ? 'Absent' : esc(v)}</span>`;
const srcA = (u, t) => u ? `<a href="${esc(u)}" target="_blank" rel="noopener">${t || 'Source'}</a>` : '';
const timing = v => !v.gf ? '' : v.gl && v.gl > v.d ? (v.gf > v.d ? 'gift came after this vote' : 'gifts before and after this vote') : 'gift came before this vote';
function offBtn(oid, name) { return oid && D.off[oid] ? `<button type="button" class="cn-link" data-sel="${esc(oid)}">${esc(name || D.off[oid].n)}</button>` : esc(name); }
function voteRows(groups, showCompany) {
  return groups.map(g => `<div class="cn-vote"><div class="cn-vd">${esc(day(g.d))}</div><div><b>${esc(g.h)}</b>${g.a ? ` · ${money(g.a)}` : ''}${showCompany ? ` · ${g.c ? `<button type="button" class="cn-link" data-sel="${esc(g.c)}">${esc(g.cn)}</button>` : esc(g.cn)}` : ''}
    <div class="cn-who">${g.who.map(v => `${vpill(v.v)} ${offBtn(v.m, v.mn)}`).join(' ')}</div>
    <div class="cn-meta">${g.g && window.BCM && BCM.city ? `<span>${esc(BCM.city.label(g.g) || '')}</span>` : ''}${g.ca ? '<span>Consent agenda</span>' : ''}${g.who.some(v => v.ow) ? '<span>Gift from the company\'s owner</span>' : ''}<span>${esc(timing(g.who[0]))}</span>${srcA(g.u, 'Minutes')}</div></div></div>`).join('');
}
function timeline(e, oid) {
  const ev = [];
  D.don.filter(d => d.e === e && d.o === oid).forEach(d => {
    const [a, b] = (d.date || '').split(' to ');
    if (a) ev.push({ d: a, k: 'gift', t: d.n > 1 ? `First of ${d.n} gifts, ${full(d.a)} in all` : `${full(d.a)} campaign gift`, u: url(d.u) });
    if (b) ev.push({ d: b, k: 'gift', t: 'Latest gift', u: url(d.u) });
  });
  D.votes.filter(v => v.c === e && v.m === oid).forEach(v => ev.push({ d: v.d, k: 'vote', t: `${v.v === 'yes' ? 'Voted yes' : v.v === 'abstain' ? 'Abstained' : 'Absent'}: ${v.h}${v.a ? ` (${money(v.a)})` : ''}${v.ca ? ' · consent agenda' : ''}`, u: v.u }));
  if (!ev.some(x => x.k === 'vote')) return '';
  ev.sort((a, b) => a.d.localeCompare(b.d));
  return `<ol class="cn-tl">${ev.map(x => `<li class="${x.k}"><span class="cn-td">${esc(day(x.d))}</span><span>${esc(x.t)}${x.u ? ` · ${srcA(x.u, x.k === 'vote' ? 'Minutes' : 'Report')}` : ''}</span></li>`).join('')}</ol><p class="cn-note">Dot: gift. Square: vote. "Consent agenda" means the item passed in one vote with other routine items.</p>`;
}
function recList(rs) {
  return `<div class="cn-recs">${rs.map(r => `<div class="cn-rec"><span>${esc(r.w || D.types[r.t])}</span><span class="num">${full(r.a)}</span><span class="cn-meta"><span class="cn-pill">${esc(D.types[r.t])}</span>${r.s ? `<span>${esc(r.s)}</span>` : ''}<span>${esc(r.when)}</span><span>${esc(payerName(r.p))}</span>${r.x ? '<span>inside a project total</span>' : ''}${srcA(url(r.u))}</span></div>`).join('')}</div>`;
}
function profileHref(id, e) {
  if (e.vp) return `/public-money/vendors/${e.vp}`;
  const k = id.slice(0, 2), key = id.slice(2);
  const pid = e.np && k !== 'v:' ? 'nonprofit:' + e.np : k === 'v:' ? 'vendor:' + key : (k === 'b:' || k === 's:') ? 'business:' + key : null;
  return pid ? bcHref(pid) : null;
}

function storyBiz(id) {
  const e = ent(id), rows = visible().filter(r => r.e === id), pm = paidMap(rows).get(id) || new Map();
  const gifts = giftsOf(id).sort((a, b) => (D.off[a.o] || {}).cand - (D.off[b.o] || {}).cand || b.a - a.a);
  const vg = groupVotes(votesFor(id)), href = profileHref(id, e);
  const now = gifts.filter(d => !(D.off[d.o] || {}).cand).length;
  const head = `<div class="cn-ph"><span class="eyebrow">${KIND[e.k] || ''}</span><h2 data-nolink>${esc(e.n)}</h2>${href ? `<a href="${esc(href)}">Full profile</a>` : ''}</div>` +
    facts([[money(sum(pm)), `in ${plural(rows.length, 'record')} from ${plural(pm.size, 'government')}`], ...(e.k === 'biz' ? [[full(gifts.reduce((a, d) => a + d.a, 0)), `to ${plural(gifts.length, 'campaign')} since 2016`], [vg.length, 'votes by people it gave to']] : [])]);
  const paidItems = [...pm.entries()].sort((a, b) => b[1] - a[1]).map(([p, v]) => ({ n: payerName(p), v, id: 'p:' + p }));
  const s1 = step(1, 'Who paid it', paidItems.length ? bars(paidItems.slice(0, 6)) + (paidItems.length > 6 ? `<p class="cn-note">And ${paidItems.length - 6} more.</p>` : '') + `<p class="cn-note">An award and the payments on it can both appear, so totals can count the same money twice.</p>` + fold(`See all ${plural(rows.length, 'record')}`, recList(rows)) : '<p class="cn-note">No payments in the records chosen.</p>');
  const giftRow = d => { const o = D.off[d.o] || {}, tl = timeline(id, d.o); return `<div class="cn-gift"><div class="cn-gr">${offBtn(d.o)}<span class="cn-note">${esc(offLabel(o))}</span><span class="num">${full(d.a)}</span></div>${tl ? `<details class="cn-tlw"><summary>Gifts and votes over time</summary>${tl}</details>` : ''}</div>`; };
  const s2 = e.k !== 'biz' ? '' : step(2, 'Who it gave to', gifts.length ? gifts.slice(0, 6).map(giftRow).join('') + (gifts.length > 6 ? fold(`Show all ${gifts.length}`, gifts.slice(6).map(giftRow).join('')) : '') + `<p class="cn-note">${plural(now, 'official')} in office now, ${plural(gifts.length - now, 'past or 2026 campaign')}.</p>` : '<p class="cn-note">No campaign gifts on file.</p>');
  const s3 = e.k !== 'biz' ? '' : step(3, 'How they voted on its work', vg.length ? voteRows(vg.slice(0, 4)) + (vg.length > 4 ? fold(`Show all ${vg.length} votes`, voteRows(vg.slice(4))) : '') : '<p class="cn-note">No votes in the minutes name this business alongside a member it gave to.</p>');
  const rel = D.rel.filter(x => x.a === id || x.b === id).map(x => { const o = x.a === id ? x.b : x.a; return `<div><button type="button" class="cn-link" data-sel="${esc(o)}">${esc(ent(o).n)}</button><div class="cn-note">${esc(x.t)} ${srcA(x.u)}</div></div>`; });
  return head + s1 + s2 + s3 + (rel.length ? `<section class="cn-step"><h3>Connected payees</h3><div class="cn-rel">${rel.join('')}</div></section>` : '');
}
function storyOff(id) {
  const o = D.off[id] || {}, ds = D.don.filter(d => d.o === id).sort((a, b) => b.a - a.a), pm = paidMap(visible());
  const paidDs = ds.filter(d => d.e && pm.has(d.e)), vs = D.votes.filter(v => v.m === id), vg = groupVotes(vs);
  const head = `<div class="cn-ph"><span class="eyebrow">${o.cand ? candLbl(o) : 'Elected official'}</span><h2 data-nolink>${esc(o.n)}</h2><span class="cn-note">${esc(o.off)}</span>${personHref(id) ? `<a href="${esc(personHref(id))}">Full profile</a>` : ''}</div>` +
    facts([[full(ds.reduce((a, d) => a + d.a, 0)), `from ${plural(ds.length, 'business or group', 'businesses and groups')}`], [paidDs.length, 'of them paid by a local government'], [vg.length, 'votes on their work']]);
  const row = d => `<div class="cn-gr">${d.e ? `<button type="button" class="cn-link" data-sel="${esc(d.e)}">${esc(ent(d.e).n)}</button>` : `<span>${esc(d.dn)}</span>`}<span class="cn-note">${d.e && pm.has(d.e) ? 'paid by a government' : ''}</span><span class="num">${full(d.a)}</span></div>`;
  const s1 = step(1, 'Who gave', ds.length ? ds.slice(0, 8).map(row).join('') + fold(ds.length > 8 ? `Show all ${ds.length}` : '', ds.slice(8).map(row).join('')) + '<p class="cn-note">Businesses, PACs and committees only. Gifts from individual people are never named here.</p>' : '<p class="cn-note">No business gifts on file.</p>');
  const items = paidDs.map(d => ({ n: ent(d.e).n, id: d.e, v: sum(pm.get(d.e)) })).sort((a, b) => b.v - a.v);
  const s2 = step(2, 'What those businesses were paid', items.length ? bars(items.slice(0, 8)) + (items.length > 8 ? `<p class="cn-note">And ${items.length - 8} more.</p>` : '') : '<p class="cn-note">None of the businesses that gave were paid in the records chosen.</p>');
  const one = g => g.who.filter(v => v.m === id);
  const s3 = step(3, 'How they voted on those businesses', vg.length ? voteRows(vg.slice(0, 5).map(g => ({ ...g, who: one(g) })), true) + (vg.length > 5 ? fold(`Show all ${vg.length} votes`, voteRows(vg.slice(5).map(g => ({ ...g, who: one(g) })), true)) : '') : '<p class="cn-note">No votes in the minutes name a business that gave to them.</p>');
  const boards = (o.gp || []).length ? `<p class="cn-note">Sits on: ${o.gp.map(k => `<button type="button" class="cn-link" data-sel="p:${esc(k)}">${esc(payerName(k))}</button>`).join(', ')}</p>` : '';
  return head + boards + s1 + s2 + s3;
}
function storyPayer(id) {
  const k = id.slice(2), P = D.payers[k], rows = visible().filter(r => r.p === k), pm = paidMap(rows);
  const offs = Object.entries(D.off).filter(([, o]) => (o.gp || []).includes(k));
  const items = [...pm.entries()].map(([e, m]) => ({ n: ent(e).n, id: /^[vbs]:|^o:|^g:/.test(e) ? e : null, v: sum(m) })).sort((a, b) => b.v - a.v);
  const donors = [...pm.keys()].filter(e => giftsOf(e).length).sort((a, b) => sum(pm.get(b)) - sum(pm.get(a)));
  const gp = k.startsWith('g:') ? bcHref('gov:' + k.slice(2)) : null;
  const head = `<div class="cn-ph"><span class="eyebrow">${PKIND[P.k]}</span><h2 data-nolink>${esc(P.n)}</h2>${gp ? `<a href="${esc(gp)}">Full profile</a>` : ''}</div>` +
    facts([[plural(rows.length, 'record'), 'in the records chosen'], [items.length, 'payees'], [donors.length, 'payees that gave to a campaign']]);
  const s1 = step(1, 'Its biggest payees', items.length ? bars(items.slice(0, 8)) + '<p class="cn-note">An award and the payments on it can both appear, so totals can count the same money twice.</p>' : '<p class="cn-note">No payments in the records chosen.</p>');
  const drow = e => { const gs = giftsOf(e); return `<div class="cn-gift"><div class="cn-gr"><button type="button" class="cn-link" data-sel="${esc(e)}">${esc(ent(e).n)}</button><span></span><span class="num">${money(sum(pm.get(e)))}</span></div><div class="cn-note">Gave ${full(gs.reduce((a, d) => a + d.a, 0))} to ${gs.slice(0, 4).map(d => offBtn(d.o)).join(', ')}${gs.length > 4 ? ` and ${gs.length - 4} more` : ''}</div></div>`; };
  const s2 = step(2, 'Payees that gave to campaigns', donors.length ? donors.slice(0, 6).map(drow).join('') + fold(donors.length > 6 ? `Show all ${donors.length}` : '', donors.slice(6).map(drow).join('')) : '<p class="cn-note">None of its payees gave to a campaign.</p>');
  const s3 = offs.length ? step(3, 'Who sits on its board', offs.map(([oid, o]) => { const n = new Set(D.votes.filter(v => v.m === oid).map(voteKey)).size; return `<div class="cn-gr">${offBtn(oid)}<span class="cn-note">${esc(o.off)}</span><span class="num">${n ? plural(n, 'vote') : ''}</span></div>`; }).join('') + '<p class="cn-note">Votes: motions naming a business that gave to that member.</p>') : '';
  return head + s1 + s2 + s3;
}

/* ---------- connections map: one name in the middle, one step out ---------- */
function neighbors(id) {
  const pm = paidMap(visible());
  if (id.startsWith('m:')) {
    const o = D.off[id] || {};
    return { L: D.don.filter(d => d.o === id).map(d => ({ id: d.e || null, n: d.e ? ent(d.e).n : d.dn, v: d.a, k: 'gift' })), R: (o.gp || []).map(p => ({ id: 'p:' + p, n: payerName(p), v: 1, k: 'board' })), lt: 'Gave to them', rt: 'Boards they sit on' };
  }
  if (id.startsWith('p:')) {
    const k = id.slice(2), m = paidMap(visible().filter(r => r.p === k));
    return { L: Object.entries(D.off).filter(([, o]) => (o.gp || []).includes(k)).map(([oid, o]) => ({ id: oid, n: o.n, v: 1, k: 'board' })), R: [...m.entries()].map(([e, x]) => ({ id: e, n: ent(e).n, v: sum(x), k: 'pay' })), lt: 'Board', rt: 'Paid' };
  }
  const p = pm.get(id) || new Map();
  return { L: [...p.entries()].map(([k, v]) => ({ id: 'p:' + k, n: payerName(k), v, k: 'pay' })), R: giftsOf(id).map(d => ({ id: d.o, n: (D.off[d.o] || {}).n, v: d.a, k: 'gift' })),
    B: D.rel.filter(x => x.a === id || x.b === id).map(x => { const o = x.a === id ? x.b : x.a; return { id: o, n: ent(o).n, v: 1, k: 'rel' }; }), lt: 'Paid it', rt: 'It gave to' };
}
function mapView(id) {
  const nb = neighbors(id), cap = 12;
  const side = a => { a.sort((x, y) => y.v - x.v); return [a.slice(0, cap), Math.max(0, a.length - cap)]; };
  const [Ls, Lx] = side(nb.L), [Rs, Rx] = side(nb.R), Bs = (nb.B || []).slice(0, 4);
  const W = 400, n = Math.max(Ls.length, Rs.length, 3), H = Math.max(300, n * 30 + 80 + (Bs.length ? 50 : 0)), cx = W / 2, cy = (H - (Bs.length ? 50 : 0)) / 2 + 6;
  const rx = 100, ry = Math.min(cy - 34, n * 15 + 10);
  const pos = (arr, left) => arr.map((d, i) => { const t = arr.length === 1 ? 0 : (i / (arr.length - 1) - 0.5) * 2; const a = t * 1.15; return { ...d, x: cx + (left ? -1 : 1) * rx * Math.cos(a), y: cy + ry * Math.sin(a) * 1.0 }; });
  const P = [...pos(Ls, true).map(d => ({ ...d, s: 'L' })), ...pos(Rs, false).map(d => ({ ...d, s: 'R' })), ...Bs.map((d, i) => ({ ...d, s: 'B', x: cx + (i - (Bs.length - 1) / 2) * 90, y: H - 34 }))];
  const vmax = k => Math.max(1, ...P.filter(d => d.k === k).map(d => d.v));
  const sw = d => d.k === 'board' || d.k === 'rel' ? 1.5 : 1.5 + 6 * Math.sqrt(d.v / vmax(d.k));
  const col = { pay: 'var(--cn-pay)', gift: 'var(--salmon)', board: 'var(--muted)', rel: 'var(--amber)' };
  const dot = { pay: 'var(--navy)', gift: 'var(--salmon)', board: 'var(--navy)', rel: 'var(--amber)' };
  const nmc = d => d.id && d.id.startsWith('m:') ? 'var(--salmon)' : d.id && d.id.startsWith('p:') ? 'var(--navy)' : 'var(--blue)';
  const fit = (t, k) => t && t.length > k ? t.slice(0, k - 1).trimEnd() + '…' : (t || '');
  const lines = P.map(d => `<path d="M${cx},${cy} Q${(cx + d.x) / 2},${d.s === 'B' ? cy + 10 : (cy + d.y) / 2} ${d.x.toFixed(1)},${d.y.toFixed(1)}" fill="none" stroke="${col[d.k]}" stroke-width="${sw(d).toFixed(1)}" stroke-linecap="round"${d.k === 'rel' ? ' stroke-dasharray="4 4"' : ''} opacity=".7"/>`).join('');
  const nodes = P.map(d => { const lx = d.s === 'L' ? d.x - 11 : d.s === 'R' ? d.x + 11 : d.x, ly = d.s === 'B' ? d.y + 20 : d.y, an = d.s === 'L' ? 'end' : d.s === 'R' ? 'start' : 'middle';
    return `<g class="cn-mn${d.id ? '' : ' nolink'}"${d.id ? ` data-sel="${esc(d.id)}" tabindex="0" role="button" aria-label="${esc(d.n)}"` : ''}><circle cx="${d.x.toFixed(1)}" cy="${d.y.toFixed(1)}" r="7" fill="${d.id ? nmc(d) : 'var(--surface)'}" stroke="${d.id ? 'none' : 'var(--faint)'}"/><text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" dy="0.35em" text-anchor="${an}">${esc(fit(d.n, d.s === 'B' ? 14 : 15))}<title>${esc(d.n)}${d.k === 'pay' || d.k === 'gift' ? ' · ' + full(d.v) : ''}</title></text></g>`; }).join('');
  const nm = ent(id).n, words = nm.split(' '), l1 = [], l2 = [];
  words.forEach(w => ((l1.join(' ') + ' ' + w).trim().length <= 11 && !l2.length ? l1 : l2).push(w));
  const c = `<circle cx="${cx}" cy="${cy}" r="40" fill="var(--navy-fill)"/><text class="cn-mc" x="${cx}" y="${cy - (l2.length ? 7 : 0)}" dy="0.35em" text-anchor="middle">${esc(fit(l1.join(' '), 12))}</text>${l2.length ? `<text class="cn-mc" x="${cx}" y="${cy + 8}" dy="0.35em" text-anchor="middle">${esc(fit(l2.join(' '), 11))}</text>` : ''}`;
  const hd = `<text class="cn-mh" x="8" y="14">${esc(nb.lt)}${Lx ? ` · +${Lx} more` : ''}</text><text class="cn-mh" x="${W - 8}" y="14" text-anchor="end">${esc(nb.rt)}${Rx ? ` · +${Rx} more` : ''}</text>`;
  const empty = !P.length ? `<text class="cn-mh" x="${cx}" y="${cy + 56}" text-anchor="middle">No connections in the records chosen.</text>` : '';
  return `<svg class="cn-map" viewBox="0 0 ${W} ${H}" role="img" aria-label="Connections of ${esc(nm)}">${hd}${lines}${c}${nodes}${empty}</svg>
    <p class="cn-note">Navy: governments. Blue: businesses. Red: officials and candidates. Line width shows dollars; dashed lines are a shared project, address or subcontract. Tap any dot to put it in the middle.</p>`;
}

function profile() {
  const p = $('cnProfile'), id = st.sel;
  if (!id) { p.innerHTML = '<p class="cn-note">Pick a name in the list, the money flow or the search box to see its story.</p>'; return; }
  const kind = id.startsWith('m:') ? 'off' : id.startsWith('p:') ? 'payer' : 'biz';
  const body = st.pv === 'map' ? mapView(id) : kind === 'off' ? storyOff(id) : kind === 'payer' ? storyPayer(id) : storyBiz(id);
  const mapHead = st.pv === 'map' ? `<div class="cn-ph"><span class="eyebrow">Connections map</span><h2 data-nolink>${esc(ent(id).n)}</h2></div>` : '';
  p.innerHTML = `<div class="cn-pv" role="group" aria-label="Show"><button type="button" class="cn-chip" data-pv="story" aria-pressed="${st.pv === 'story'}">Story</button><button type="button" class="cn-chip" data-pv="map" aria-pressed="${st.pv === 'map'}">Connections map</button></div>${mapHead}${body}
    <div hidden data-share-text="${esc(shareText(id))}"></div>`;
  p.querySelectorAll('[data-sel]').forEach(b => { b.onclick = () => select(b.dataset.sel, false); b.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(b.dataset.sel, false); } }; });
  p.querySelectorAll('[data-pv]').forEach(b => b.onclick = () => { st.pv = b.dataset.pv; profile(); });
}
function shareText(id) {
  if (id.startsWith('m:') || id.startsWith('p:')) return `${ent(id).n} on BayCounty.me Connections: who was paid, who gave and how they voted`;
  const g = giftsOf(id), pm = paidMap(visible()).get(id);
  return `${ent(id).n}: ${pm ? money(sum(pm)) + ' in public records' : 'no payments'}${g.length ? `, gave ${full(g.reduce((a, d) => a + d.a, 0))} to ${plural(g.length, 'campaign')}` : ''}`;
}

function select(id, scroll, auto) {
  st.sel = id; if (!auto) st.picked = true;
  try { const q = new URLSearchParams(location.search); id ? q.set('name', id) : q.delete('name'); history.replaceState(null, '', location.pathname + (q.toString() ? '?' + q : '') + location.hash); } catch (e) {}
  profile(); flowHl();
  $('cnList').querySelectorAll('[data-sel]').forEach(b => b.toggleAttribute('aria-current', b.dataset.sel === id));
  const p = $('cnProfile');
  if (id && !auto && (scroll || innerWidth <= 900)) { const r = p.getBoundingClientRect(); if (r.top < 0 || r.top > innerHeight * 0.6 || innerWidth <= 900) p.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
}

/* ---------- search ---------- */
function searchBox() {
  const opts = new Map();
  Object.entries(D.payers).forEach(([k, p]) => opts.set(p.n, 'p:' + k));
  Object.entries(D.off).forEach(([k, o]) => opts.set(o.n + (o.cand ? ` (${candLbl(o)})` : ''), k));
  const has = new Set(D.recs.map(r => r.e));
  Object.entries(D.ents).forEach(([k, e]) => { if (has.has(k) && /^[vb]:/.test(k)) opts.set(e.n, k); });
  $('cnFind').innerHTML = [...opts.keys()].sort().map(n => `<option value="${esc(n)}">`).join('');
  const names = [...opts.keys()], low = names.map(n => n.toLowerCase());
  const find = q => {
    if (opts.has(q)) return opts.get(q);
    const t = q.toLowerCase(); if (t.length < 2) return null;
    let i = low.indexOf(t); if (i < 0) i = low.findIndex(n => n.startsWith(t)); if (i < 0) i = low.findIndex(n => n.includes(t));
    return i < 0 ? null : opts.get(names[i]);
  };
  const go = () => { const v = $('cnQ').value.trim(); if (!v) return; const id = find(v); $('cnMiss').hidden = !!id; if (!id) return; $('cnQ').value = ''; select(id, true); };
  $('cnSearch').addEventListener('submit', e => { e.preventDefault(); go(); });
  $('cnQ').addEventListener('change', () => { if (opts.has($('cnQ').value)) go(); });
}

/* ---------- tables of every record ---------- */
function chip(label, pressed, onclick, id) {
  const b = document.createElement('button'); b.type = 'button'; b.className = 'cn-chip'; b.textContent = label; if (id) b.id = id;
  b.setAttribute('aria-pressed', pressed); b.onclick = () => onclick(b); return b;
}
function controls() {
  Object.entries(D.types).forEach(([k, l]) => $('cnTypes').appendChild(chip(l, st.types.has(k), b => { st.types.has(k) ? st.types.delete(k) : st.types.add(k); b.setAttribute('aria-pressed', st.types.has(k)); render(); })));
  [['payees', 'Donors who were paid'], ['all', 'All business donors']].forEach(([k, l]) => $('cnDon').appendChild(chip(l, st.don === k, b => { st.don = k; $('cnDon').querySelectorAll('.cn-chip').forEach(x => x.setAttribute('aria-pressed', x === b)); donTable(visible()); }, 'cnDon-' + k)));
  document.querySelectorAll('.cn-tab').forEach(b => b.onclick = () => setView(b.dataset.v));
  document.querySelectorAll('[data-sort]').forEach(b => b.onclick = () => { st.sort = b.dataset.sort; document.querySelectorAll('[data-sort]').forEach(x => x.setAttribute('aria-pressed', x === b)); list(visible()); });
}
function cityToPayers(k) {
  st.city = k || '';
  st.pay = new Set(Object.keys(D.payers).filter(p => !k || D.payers[p].g === k));
}
function payees(rows) {
  const m = new Map();
  rows.forEach(r => { const o = m.get(r.e) || { e: r.e, tot: 0, n: 0, p: new Set(), t: new Set(), unk: 0 }; o.tot += amt(r); o.n++; o.p.add(r.p); o.t.add(r.t); if (r.a == null) o.unk++; m.set(r.e, o); });
  const gave = new Set(D.don.filter(d => d.e).map(d => d.e));
  const L = [...m.values()].sort((a, b) => b.tot - a.tot);
  $('cnPayCount').textContent = `${plural(L.length, 'payee')} · tap a row for its story`;
  $('cnPay').innerHTML = `<thead><tr><th>Payee</th><th>Type</th><th>Paid by</th><th>Records</th><th class="num">Count</th><th class="num">Dollars in records</th></tr></thead><tbody>` +
    L.map(o => { const e = ent(o.e); return `<tr class="cn-row" data-tt-role="row" tabindex="0" data-e="${esc(o.e)}"><td><b>${esc(e.n)}</b>${gave.has(o.e) ? ' <span class="cn-flag red">gave</span>' : ''}</td><td>${KIND[e.k]}</td><td>${[...o.p].map(payerName).map(esc).join(', ')}</td><td>${[...o.t].map(t => esc(D.types[t])).join(', ')}</td><td class="num">${o.n}${o.unk ? ` <span class="cn-flag">${o.unk} no $</span>` : ''}</td><td class="num">${full(o.tot)}</td></tr>`; }).join('') + '</tbody>';
  $('cnPay').querySelectorAll('tr.cn-row').forEach(t => { t.onclick = () => select(t.dataset.e, true); t.onkeydown = e => { if (e.key === 'Enter') select(t.dataset.e, true); }; });
}
function donTable(vis) {
  const paidNow = new Set(vis.map(r => r.e));
  const rows = D.don.filter(d => offShown(D.off[d.o] || {}) && (st.don !== 'payees' || (d.e && paidNow.has(d.e))));
  $('cnDonCount').textContent = `${plural(rows.length, 'donor and official pair')} · ${money(rows.reduce((a, d) => a + d.a, 0))}`;
  $('cnDonT').innerHTML = `<thead><tr><th>Business or group</th><th>Official</th><th>Office</th><th class="num">Amount</th><th>Date</th><th>Also paid by a government</th></tr></thead><tbody>` +
    rows.map(d => { const o = D.off[d.o] || {}; return `<tr data-tt-role="row"><td>${esc(d.dn)}${d.ty === 'pac' || d.ty === 'committee' ? ` <span class="cn-flag">${d.ty === 'pac' ? 'PAC' : 'committee'}</span>` : ''}</td><td><button type="button" class="cn-link" data-sel="${esc(d.o)}">${esc(o.n)}</button>${o.cand ? ` <span class="cn-flag">${candLbl(o)}</span>` : ''}</td><td>${esc(o.off)}</td><td class="num">${full(d.a)}${d.n > 1 ? ` <span class="cn-flag">${d.n} gifts</span>` : ''}</td><td class="num">${esc(d.date)}</td><td>${d.e ? `<button type="button" class="cn-link" data-sel="${esc(d.e)}">${esc(ent(d.e).n)}</button>${d.cf === 'likely' ? ' <span class="cn-flag">likely</span>' : ''}` : '—'}</td></tr>`; }).join('') + '</tbody>';
  $('cnDonT').querySelectorAll('[data-sel]').forEach(b => b.onclick = () => select(b.dataset.sel, true));
}
const VIEWS = ['payees', 'gifts', 'donors'];
function setView(v) {
  st.view = v;
  VIEWS.forEach(k => { $('v-' + k).hidden = k !== v; $('t-' + k).setAttribute('aria-selected', k === v); });
  $('cnDon').hidden = v !== 'gifts';
  tables(visible());
}
function tables(rows) { if (st.view === 'payees') payees(rows); else if (st.view === 'gifts') donTable(rows); else if (window.MM) MM.render(); }

function render() {
  const rows = visible(); kpis(rows);
  const L = list(rows);
  if (!st.sel && L.length) st.sel = L[0].e;  // open on the top business so the story is never empty
  flow(rows); tables(rows); select(st.sel, false, true);
}

function start() {
  controls(); searchBox();
  const q = new URLSearchParams(location.search).get('name');
  if (q && (D.ents[q] || D.off[q] || (q.startsWith('p:') && D.payers[q.slice(2)]))) { st.sel = q; st.picked = true; }
  BCM.city.on((k, d) => { cityToPayers(k); if (d.why !== 'now') render(); });
  // old links: #payees, #gifts and #donors open that table; #map and friends were the money map
  const h = location.hash.slice(1), v = VIEWS.includes(h) ? h : h === 'donations' ? 'gifts' : ['map', 'votes', 'heat1'].includes(h) ? 'donors' : 'payees';
  setView(v); render();
  if (h && h !== 'payees' && v !== 'payees') $('records').scrollIntoView();
  else if (q && st.sel === q) select(q, true);
  let rt, w0 = innerWidth; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { if (innerWidth !== w0) { w0 = innerWidth; flow(visible()); } }, 250); });
}
if (window.d3) start(); else addEventListener('load', start);
})();
