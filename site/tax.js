(() => {
const D = __TAX__;
const L = D.years.length - 1, LV = D.levyYear;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const GN = Object.fromEntries(D.groups);
const GI = Object.fromEntries(D.groups.map(([g], i) => [g, i + 1]));
const col = g => `var(--s${GI[g]})`;
const usd = n => '$' + Math.round(n).toLocaleString('en-US');
const big = n => n == null ? '—' : Math.abs(n) >= 1e9 ? '$' + (n / 1e9).toFixed(2) + 'B' : Math.abs(n) >= 1e6 ? '$' + (n / 1e6).toFixed(1) + 'M' : Math.abs(n) >= 1e3 ? '$' + Math.round(n / 1e3) + 'K' : usd(n);
const pct = x => (x * 100).toFixed(x < .1 ? 1 : 0) + '%';
const mills = m => m == null ? '—' : String(+(+m).toFixed(4));
const mills4 = m => m == null ? '—' : (+m).toFixed(4);

/* ---------- tooltip ---------- */
const tt = $('tt');
function tip(e, html) {
  tt.innerHTML = html; tt.hidden = false;
  const w = tt.offsetWidth, h = tt.offsetHeight;
  let x = e.clientX + 14, y = e.clientY + 14;
  if (x + w > innerWidth - 8) x = e.clientX - w - 14;
  if (y + h > innerHeight - 8) y = e.clientY - h - 14;
  tt.style.left = Math.max(8, x) + 'px'; tt.style.top = Math.max(8, y) + 'px';
}
const untip = () => { tt.hidden = true; };
function bindTips(root, fn) {
  root.querySelectorAll('[data-tip]').forEach(el => {
    el.addEventListener('pointermove', e => tip(e, fn(el.dataset.tip)));
    el.addEventListener('pointerleave', untip);
    el.addEventListener('focus', () => { const r = el.getBoundingClientRect(); tip({clientX: r.left + r.width / 2, clientY: r.bottom}, fn(el.dataset.tip)); });
    el.addEventListener('blur', untip);
  });
}

/* ---------- calculator ---------- */
const sel = $('cDist');
sel.innerHTML = D.districts.map(d => `<option value="${esc(d.id)}">${esc(d.label)} · ${mills(d.total[L])} mills</option>`).join('');
// distPicked: the reader (or a shared link, or an earlier visit) chose the district; the city bar only fills a default
let distPicked = false;
try { const s = localStorage.getItem('taxDist'); if (s && D.districts.some(d => d.id === s)) { sel.value = s; distPicked = true; } } catch (e) {}
const valIn = $('cVal'), home = $('cHome');
// inputs live in the link (?v=value&d=district&h=1|0) so an estimate can be shared, e.g. from My Address
const P0 = new URLSearchParams(location.search);
if (P0.get('d') && D.districts.some(d => d.id === P0.get('d'))) { sel.value = P0.get('d'); distPicked = true; }
if (/^\d+$/.test(P0.get('v') || '')) valIn.value = Math.min(+P0.get('v'), 1e9).toLocaleString('en-US');
if (P0.has('h')) home.checked = P0.get('h') !== '0';
function saveUrl(v) {
  const u = new URL(location.href);
  u.searchParams.set('v', v); u.searchParams.set('d', sel.value); u.searchParams.set('h', home.checked ? '1' : '0');
  try { history.replaceState(null, '', u); } catch (e) {}
}

function taxable(v, homestead, yi = L) {
  if (!homestead) return {school: v, other: v};
  const first = Math.min(v, 25000), second = Math.max(0, Math.min(v - 50000, D.second[yi]));
  return {school: Math.max(0, v - first), other: Math.max(0, v - first - second)};
}
function billAt(dist, yi, tv) {
  return dist.stack.map(id => {
    const a = D.auth[id], m = a.m[yi] || 0, base = a.school ? tv.school : tv.other;
    return {id, n: a.n, g: a.g, m, base, amt: base / 1000 * m};
  });
}
function readVal() { const n = parseInt(String(valIn.value).replace(/[^0-9]/g, ''), 10); return isFinite(n) ? Math.min(n, 1e9) : 0; }

function calc() {
  const dist = D.districts.find(d => d.id === sel.value), v = readVal(), tv = taxable(v, home.checked);
  if (calc.ready) { try { localStorage.setItem('taxDist', dist.id); } catch (e) {} saveUrl(v); }
  const rows = billAt(dist, L, tv).filter(r => r.m > 0), tot = rows.reduce((a, r) => a + r.amt, 0);
  $('bTotal').textContent = usd(tot);
  $('bSub').textContent = tot ? `about ${usd(tot / 12)} a month · ${mills(dist.total[L])} mills in all` : 'Enter a value to see your estimate';
  const byG = D.groups.map(([g]) => [g, rows.filter(r => r.g === g).reduce((a, r) => a + r.amt, 0)]).filter(([, a]) => a > 0);
  const stack = $('bStack');
  stack.setAttribute('aria-label', 'Your bill split: ' + byG.map(([g, a]) => `${GN[g]} ${usd(a)}`).join(', '));
  stack.innerHTML = byG.map(([g, a]) => `<span class="seg" tabindex="0" style="flex:${a} 1 0;background:${col(g)}" data-tip="${g}"></span>`).join('');
  bindTips(stack, g => { const a = byG.find(x => x[0] === g)[1]; return `<b>${esc(GN[g])}</b><br>${usd(a)} · ${pct(a / tot)} of your bill`; });
  $('bLeg').innerHTML = byG.map(([g, a]) => `<li><i style="background:${col(g)}"></i><span>${esc(GN[g] === 'Your city' ? cityName(dist) : GN[g])}</span><b>${usd(a)}</b><em>${pct(a / tot)}</em></li>`).join('');
  const tb = $('bTable');
  tb.tBodies[0].innerHTML = billAt(dist, L, tv).map(r => `<tr><th scope="row"><i class="dot" style="background:${col(r.g)}"></i>${esc(r.n)}</th><td class="num">${mills(r.m)}</td><td class="num">${usd(r.base)}</td><td class="num">${usd(r.amt)}</td><td class="num">${tot ? pct(r.amt / tot) : '—'}</td></tr>`).join('')
    + (dist.id === 'Panama City Beach' || dist.id.startsWith('unincorporated') ? `<tr class="zero"><th scope="row"><i class="dot"></i>${dist.id === 'Panama City Beach' ? 'City of Panama City Beach' : 'No city'}</th><td class="num">0</td><td class="num">—</td><td class="num">$0</td><td class="num">${dist.id === 'Panama City Beach' ? 'No city property tax' : 'County provides fire service'}</td></tr>` : '');
  tb.tFoot.innerHTML = `<tr><th scope="row">Total</th><td class="num">${mills(dist.total[L])}</td><td></td><td class="num">${usd(tot)}</td><td class="num">100%</td></tr>`;
  // same home, each year's rates
  const yrs = D.years.map((_, i) => { const r = billAt(dist, i, taxable(v, home.checked, i)); return {fy: D.fy[i], tot: r.reduce((a, x) => a + x.amt, 0), rows: r}; });
  const max = Math.max(...yrs.map(y => y.tot), 1);
  const tr = $('bTrend');
  tr.innerHTML = yrs.map((y, i) => `<div class="vb" tabindex="0" data-tip="${i}"><span class="vb-v">${usd(y.tot)}</span><span class="vb-bar" style="height:${y.tot / max * 100}%;background:var(--s1)"></span><span class="vb-x">${y.fy}</span></div>`).join('');
  bindTips(tr, i => { const y = yrs[i]; return `<b>${y.fy}</b> · ${usd(y.tot)}<br>` + D.groups.map(([g]) => [g, y.rows.filter(r => r.g === g).reduce((a, r) => a + r.amt, 0)]).filter(x => x[1] > 0).map(([g, a]) => `<span class="tt-row"><i style="background:${col(g)}"></i>${esc(g === 'city' ? cityName(dist) : GN[g])} <b>${usd(a)}</b></span>`).join(''); });
}
function cityName(dist) { const c = dist.stack.find(id => D.auth[id].g === 'city'); return c ? D.auth[c].n : 'Your city'; }
// Phone keypads: Enter/Done closes the keypad.
valIn.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); valIn.blur(); } });
valIn.addEventListener('input', () => {
  const pos = valIn.value.length - valIn.selectionStart, n = readVal();
  valIn.value = n ? n.toLocaleString('en-US') : '';
  const p = Math.max(0, valIn.value.length - pos); valIn.setSelectionRange(p, p);
  calc();
});
sel.addEventListener('change', e => { if (e.isTrusted) distPicked = true; calc(); }); home.addEventListener('change', calc);
calc(); calc.ready = true; // don't add params to a plain visit until someone changes an input
if (['v', 'd', 'h'].some(k => P0.has(k))) { saveUrl(readVal()); if (!location.hash) $('calc')?.scrollIntoView(); }

/* ---------- countywide bars ---------- */
(() => {
  const tot = D.bars.reduce((a, b) => a + b.v, 0), max = D.bars[0].v, el = $('allBars');
  el.innerHTML = D.bars.map((b, i) => `<div class="hb" tabindex="0" data-tip="${i}"><span class="hb-n"><i class="dot" style="background:${col(b.g)}"></i>${esc(b.n)}</span><span class="hb-track"><span class="hb-bar" style="width:${Math.max(.4, b.v / max * 100)}%;background:${col(b.g)}"></span></span><span class="hb-v">${big(b.v)} <em>${pct(b.v / tot)}</em></span></div>`).join('');
  bindTips(el, i => { const b = D.bars[i]; return `<b>${esc(b.n)}</b><br>${usd(b.v)} levied in ${D.fy[LV]}<br>${pct(b.v / tot)} of all property tax`; });
})();

/* ---------- six-year levy trend (stacked) ---------- */
(() => {
  const gs = D.groups.map(([g]) => g), YL = D.years.slice(0, LV + 1);
  const tots = YL.map((_, i) => gs.reduce((a, g) => a + (D.levy[g][i] || 0), 0)), max = Math.max(...tots);
  const el = $('levyTrend');
  el.innerHTML = YL.map((_, i) => `<div class="vb" tabindex="0" data-tip="${i}"><span class="vb-v">${big(tots[i])}</span><span class="vb-stack" style="height:${tots[i] / max * 100}%">${gs.slice().reverse().map(g => D.levy[g][i] ? `<span style="flex:${D.levy[g][i]} 1 0;background:${col(g)}"></span>` : '').join('')}</span><span class="vb-x">${D.fy[i]}</span></div>`).join('');
  bindTips(el, i => `<b>${D.fy[i]}</b> · ${big(tots[i])} levied` + gs.map(g => `<span class="tt-row"><i style="background:${col(g)}"></i>${esc(g === 'city' ? 'Cities' : GN[g])} <b>${big(D.levy[g][i])}</b></span>`).join(''));
  $('levyLeg').innerHTML = gs.map(g => `<li><i style="background:${col(g)}"></i><span>${esc(g === 'city' ? 'Cities' : GN[g])}</span><b>${big(D.levy[g][LV])}</b></li>`).join('');
  $('levyTable').innerHTML = `<thead><tr><th scope="col">Who receives it</th>${D.fy.slice(0, LV + 1).map(f => `<th scope="col" class="num">${f}</th>`).join('')}</tr></thead><tbody>` +
    gs.map(g => `<tr><th scope="row"><i class="dot" style="background:${col(g)}"></i>${esc(g === 'city' ? 'Cities' : GN[g])}</th>${D.levy[g].slice(0, LV + 1).map(v => `<td class="num">${big(v)}</td>`).join('')}</tr>`).join('') +
    `</tbody><tfoot><tr><th scope="row">Total</th>${tots.map(v => `<td class="num">${big(v)}</td>`).join('')}</tr></tfoot>`;
  $('rateTable').innerHTML = `<thead><tr><th scope="col">Area</th>${D.fy.map(f => `<th scope="col" class="num">${f}</th>`).join('')}</tr></thead><tbody>` +
    D.districts.map(d => `<tr><th scope="row">${esc(d.label)}</th>${d.total.map((m, i) => `<td class="num${i && m > d.total[i - 1] + 1e-6 ? ' up' : i && m < d.total[i - 1] - 1e-6 ? ' down' : ''}">${mills4(m)}</td>`).join('')}</tr>`).join('') + '</tbody>';
})();

/* ---------- government explorer ---------- */
const SAVE = /fund balance|reserve|carr(y|ied)|cash carry/i;
function barList(obj, opts = {}) {
  const ent = Object.entries(obj).filter(([, v]) => v != null && v > 0);
  if (!ent.length) return `<p class="empty">${opts.empty || 'Not published online.'}</p>`;
  const max = Math.max(...ent.map(e => e[1])), tot = ent.filter(([k]) => !SAVE.test(k)).reduce((a, e) => a + e[1], 0);
  ent.sort((a, b) => (SAVE.test(a[0]) - SAVE.test(b[0])) || b[1] - a[1]);
  return `<div class="hbars small">${ent.map(([k, v]) => { const s = SAVE.test(k); return `<div class="hb${s ? ' save' : ''}"><span class="hb-n">${esc(k)}${s ? ' <em>(savings, not new money or spending)</em>' : ''}</span><span class="hb-track"><span class="hb-bar" style="width:${Math.max(.6, v / max * 100)}%"></span></span><span class="hb-v">${big(v)}${s ? '' : ` <em>${pct(v / tot)}</em>`}</span></div>`; }).join('')}</div>`;
}
let govSel = D.govs[0].id, actYear = {};
const HAS_GOV = !!$('govPills');  // the per-government panel moved to each government's page; only Spanish keeps it
function renderGov() {
  if (!HAS_GOV) return;
  const g = D.govs.find(x => x.id === govSel);
  $('govPills').innerHTML = D.govs.map(x => `<button type="button" role="tab" class="pill" aria-selected="${x.id === govSel}" data-g="${x.id}">${esc(x.short)}</button>`).join('');
  const [st, stText] = g.status;
  const tiles = [
    ['Total budget, FY2026', big(g.total), g.total ? 'All funds' : 'Not published online'],
    ['General fund', big(g.gf), 'The main account for everyday services'],
    ['Property tax levied', g.id === 'panama_city_beach' ? '$0' : big(g.levy), g.id === 'panama_city_beach' ? 'No city property tax' : g.id === 'bay_county' ? 'Countywide rate plus fire and mosquito' : 'At the adopted rate'],
    ['Tax rate', g.mills == null ? '—' : g.mills ? mills(g.mills) + ' mills' : 'None', g.id === 'bay_county' ? 'Countywide rate' : g.id === 'bay_district_schools' ? 'All three school rates' : ''],
  ];
  let h = `<div class="gov-hd"><h3>${esc(g.name)}</h3><span class="badge ${st}">${st === 'ok' ? '✓' : '!'} ${esc(stText)}</span></div>
  <div class="kpis">${tiles.map(([l, v, s]) => `<div class="kpi"><span class="eyebrow">${l}</span><span class="v">${v}</span><span class="s">${esc(s)}</span></div>`).join('')}</div>`;
  if (g.next) {
    const n = g.next, bits = [];
    if (n.total) bits.push(`total ${big(n.total)}${n.excl ? ' (not counting transfers between its own funds)' : ''}`);
    if (n.gf) bits.push(`general fund ${big(n.gf)}`);
    if (n.mills != null) bits.push(n.mills ? `${mills(n.mills)} mills` : 'no city property tax');
    h += `<p class="note"><b>New budget, ${esc(n.fy)} (Oct 2026 to Sept 2027):</b> ${bits.join(', ')}. ${n.adopted ? 'Adopted' : 'Final hearing held; adoption not yet confirmed in posted minutes'}. <a href="${esc(n.src[1] || '#')}" target="_blank" rel="noopener">${esc(n.src[0])}</a>. The breakdowns below are still the ${esc('FY2026')} budget.</p>`;
  }
  if (g.mix) h += `<p class="note">Across all funds, the schools expect ${big(g.mix.Local)} from local sources (mostly property tax), ${big(g.mix.State)} from the state and ${big(g.mix.Federal)} from the federal government.</p>`;
  h += `<div class="two">
    <div><h4>Where the general fund money comes from <span class="muted">FY2026 budget</span></h4>${barList(g.rev, {empty: 'This government does not post a budget online with this detail.'})}</div>
    <div><h4>What the general fund pays for <span class="muted">FY2026 budget</span></h4>${barList(g.exp, {empty: 'This government does not post a budget online with this detail.'})}</div>
  </div>`;
  if (g.other) h += `<details class="tbl-toggle"><summary>School construction, debt and other funds</summary>${barList(g.other)}</details>`;
  if (g.notes.length) h += g.notes.map(n => `<p class="note">${esc(n)}</p>`).join('');
  if (g.act) {
    const ys = g.act.map(y => y.fy), cur = actYear[g.id] && ys.includes(actYear[g.id]) ? actYear[g.id] : ys.filter(f => Object.keys(g.act.find(y => y.fy === f).rev).length).pop();
    const y = g.act.find(a => a.fy === cur);
    h += `<div class="act"><div class="sub-hd"><h4>What actually came in and went out</h4><span class="muted">From the <span class="term" data-term="audit">audited annual report</span>, all operating funds including utilities</span></div>
      <div class="pills yrs">${ys.map(f => `<button type="button" class="pill sm" aria-pressed="${f === cur}" data-y="${f}">${f}</button>`).join('')}</div>
      <div class="two">
        <div><h4>Money in, by source <span class="muted">${cur}${y.rt ? ' · ' + big(y.rt) : ''}</span></h4>${barList(y.rev, {empty: 'The state has not posted this year’s revenue yet.'})}</div>
        <div><h4>Money out, by service <span class="muted">${cur}${y.et ? ' · ' + big(y.et) : ''}</span></h4>${barList(y.exp)}</div>
      </div>
      <div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Measure</th>${g.act.map(a => `<th scope="col" class="num">${a.fy}</th>`).join('')}</tr></thead><tbody>
        <tr><th scope="row">Money in</th>${g.act.map(a => `<td class="num">${big(a.rt)}</td>`).join('')}</tr>
        <tr><th scope="row">Money out</th>${g.act.map(a => `<td class="num">${big(a.et)}</td>`).join('')}</tr>
        <tr><th scope="row">Property tax collected</th>${g.act.map(a => `<td class="num">${big(a.rev['Property taxes'])}</td>`).join('')}</tr>
        <tr><th scope="row">Residents</th>${g.act.map(a => `<td class="num">${a.pop ? a.pop.toLocaleString('en-US') : '—'}</td>`).join('')}</tr>
      </tbody></table></div>
      <p class="src-line">Source: <a href="${esc(y.rs || g.edr)}" target="_blank" rel="noopener">EDR revenues workbook</a> · <a href="${esc(y.es || g.edr)}" target="_blank" rel="noopener">EDR expenditures workbook</a> (sheet ${cur.slice(2)})</p></div>`;
  }
  if (g.hist.length > 1) h += `<p class="note"><b>Adopted total budget over time:</b> ${g.hist.map(([f, v]) => `${esc(f)} ${big(v)}`).join(' · ')}</p>`;
  if (g.ctx.length) h += `<div class="ctx-list"><h4>Worth knowing</h4><ul>${g.ctx.map(([t, u]) => `<li>${esc(t)} <a href="${esc(u)}" target="_blank" rel="noopener">Source</a></li>`).join('')}</ul></div>`;
  h += `<p class="src-line">Budget source: ${g.src.filter(s => s[1]).map(([t, u]) => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(t)}</a>`).join(' · ')}</p>`;
  $('govBody').innerHTML = h;
}
// a pill click moves the city bar too (and the bar moves the pills, below)
const pickGov = id => { govSel = id; renderGov(); BCM.city.set(BCM.city.key(id) || ''); $('govPills').querySelector(`[data-g="${govSel}"]`).focus(); };
if (HAS_GOV) {
$('govPills').addEventListener('click', e => { const b = e.target.closest('[data-g]'); if (b) pickGov(b.dataset.g); });
$('govPills').addEventListener('keydown', e => {
  if (!['ArrowRight', 'ArrowLeft'].includes(e.key)) return;
  const i = D.govs.findIndex(x => x.id === govSel), n = D.govs.length;
  pickGov(D.govs[(i + (e.key === 'ArrowRight' ? 1 : n - 1)) % n].id);
});
$('govBody').addEventListener('click', e => { const b = e.target.closest('[data-y]'); if (b) { actYear[govSel] = b.dataset.y; renderGov(); } });
renderGov();
}
/* the city bar: open that government's tab, and point the calculator at its city while the reader hasn't picked one */
BCM.city.on(k => {
  const g = k && D.govs.find(x => BCM.city.key(x.id) === k);
  if (g && g.id !== govSel) { govSel = g.id; renderGov(); }
  const d = k && !distPicked && D.districts.find(x => BCM.city.key(x.id) === k);
  if (d && sel.value !== d.id) { sel.value = d.id; const r = calc.ready; calc.ready = false; calc(); calc.ready = r; }
});

/* ---------- PDF ---------- */
$('pdf').addEventListener('click', () => {
  document.querySelectorAll('.tax details').forEach(d => { d.dataset.wasOpen = d.open; d.open = true; });
  setTimeout(() => { window.print(); }, 60);
});
addEventListener('afterprint', () => document.querySelectorAll('.tax details').forEach(d => { if (d.dataset.wasOpen === 'false') d.open = false; }));
})();
