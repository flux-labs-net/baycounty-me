(() => {
const D = __A3__;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const usd = n => (n < 0 ? '−$' : '$') + Math.abs(Math.round(n)).toLocaleString('en-US');
const big = n => n == null ? '—' : n >= 1e6 ? '$' + (n / 1e6).toFixed(n >= 1e7 ? 1 : 2) + 'M' : n >= 1e3 ? '$' + Math.round(n / 1e3) + 'K' : usd(n);
const pct = x => (x * 100).toFixed(x < .1 ? 1 : 0) + '%';
const GI = Object.fromEntries(D.groups.map(([g], i) => [g, i + 1]));
const col = g => `var(--s${GI[g]})`;
const L = D.districts[0].total.length - 1;

/* tooltip */
const tt = $('tt');
function tip(e, html) { tt.innerHTML = html; tt.hidden = false; const w = tt.offsetWidth, h = tt.offsetHeight; let x = e.clientX + 14, y = e.clientY + 14; if (x + w > innerWidth - 8) x = e.clientX - w - 14; if (y + h > innerHeight - 8) y = e.clientY - h - 14; tt.style.left = Math.max(8, x) + 'px'; tt.style.top = Math.max(8, y) + 'px'; }
function bindTips(root, fn) { root.querySelectorAll('[data-tip]').forEach(el => { el.addEventListener('pointermove', e => tip(e, fn(el.dataset.tip))); el.addEventListener('pointerleave', () => tt.hidden = true); el.addEventListener('focus', () => { const r = el.getBoundingClientRect(); tip({clientX: r.left + r.width / 2, clientY: r.bottom}, fn(el.dataset.tip)); }); el.addEventListener('blur', () => tt.hidden = true); }); }

/* ---------- calculator ---------- */
const sel = $('cDist'), valIn = $('cVal');
sel.innerHTML = D.districts.map(d => `<option value="${esc(d.id)}">${esc(d.label)}</option>`).join('');
try { const s = localStorage.getItem('taxDist'); if (s && D.districts.some(d => d.id === s)) sel.value = s; } catch (e) {}
const readVal = () => { const n = parseInt(String(valIn.value).replace(/[^0-9]/g, ''), 10); return isFinite(n) ? Math.min(n, 1e9) : 0; };
const kind = () => document.querySelector('input[name="kind"]:checked').value;

// taxable values per scenario: [label, school, non-school]
function scenarios(v, k) {
  const today = k === 'non' ? [v, v] : [Math.max(0, v - 25000), Math.max(0, v - Math.min(v, 25000) - Math.max(0, Math.min(v - 50000, D.second)))];
  if (k === 'non') return [['Today', ...today], ['2027 bill', ...today], ['2028 bill and after', ...today]];
  const sch = Math.max(0, v - 25000);
  const e27 = k === 'new' ? 50000 : 150000, e28 = k === 'new' ? 51220 : 250000;
  return [['Today', ...today], ['2027 bill', sch, Math.max(0, v - e27)], ['2028 bill and after', sch, Math.max(0, v - e28)]];
}
function bill(dist, sc) {
  return dist.stack.map(id => { const a = D.auth[id], m = a.m[L] || 0, base = a.school ? sc[1] : sc[2]; return {id, n: a.n, g: a.g, school: a.school, m, amt: base / 1000 * m}; }).filter(r => r.m > 0);
}
function calc() {
  const dist = D.districts.find(d => d.id === sel.value), v = readVal(), k = kind();
  try { localStorage.setItem('taxDist', dist.id); } catch (e) {}
  const scs = scenarios(v, k), bills = scs.map(sc => bill(dist, sc));
  const tots = bills.map(b => b.reduce((a, r) => a + r.amt, 0));
  const schoolT = bills.map(b => b.filter(r => r.school).reduce((a, r) => a + r.amt, 0));
  const max = Math.max(...tots, 1);
  $('cmp').innerHTML = scs.map(([lbl], i) => {
    const save = tots[0] - tots[i];
    return `<div class="cmp-col" tabindex="0" data-tip="${i}">
      <span class="eyebrow">${lbl}</span>
      <span class="bill-v sm">${usd(tots[i])}</span>
      <span class="cmp-save">${i === 0 ? 'per year' : save > 0.5 ? `${usd(save)} less (${pct(save / (tots[0] || 1))})` : 'No change'}</span>
      <span class="cmp-bar"><span style="width:${(tots[i] - schoolT[i]) / max * 100}%;background:var(--s2)"></span><span style="width:${schoolT[i] / max * 100}%;background:var(--s1)"></span></span>
    </div>`;
  }).join('') + `<ul class="leg mini"><li><i style="background:var(--s2)"></i><span>County, city and districts</span></li><li><i style="background:var(--s1)"></i><span>Schools</span></li></ul>`;
  bindTips($('cmp'), i => `<b>${scs[i][0]}</b><br>Schools: ${usd(schoolT[i])} (taxed on ${usd(scs[i][1])})<br>Everything else: ${usd(tots[i] - schoolT[i])} (taxed on ${usd(scs[i][2])})`);
  $('cmpNote').innerHTML = k === 'non'
    ? 'Amendment 3 doesn\'t lower this property\'s taxes directly. It slows how fast the taxed value can rise: at most 5% a year instead of 10% for non-school taxes. That only matters if the market value is rising faster than 5%.'
    : k === 'new'
      ? 'Newer residents get $50,000 off non-school taxes for their first four years with a homestead, then the larger exemption in year five.'
      : (scs[2][2] === 0 ? 'At this value the home would owe <b>no county, city or special-district property tax</b>, only school tax.' : 'The savings top out once the exemption reaches $250,000. Above that, every extra dollar of value is taxed as it is today.');
  const t = $('cmpTable');
  t.innerHTML = `<thead><tr><th scope="col">Who gets it</th><th scope="col" class="num">Rate</th>${scs.map(s => `<th scope="col" class="num">${s[0]}</th>`).join('')}</tr></thead><tbody>` +
    bills[0].map((r, ri) => `<tr><th scope="row"><i class="dot" style="background:${col(r.g)}"></i>${esc(r.n)}</th><td class="num">${String(+r.m.toFixed(4))}</td>${bills.map(b => `<td class="num">${usd(b[ri].amt)}</td>`).join('')}</tr>`).join('') +
    `</tbody><tfoot><tr><th scope="row">Total</th><td></td>${tots.map(x => `<td class="num">${usd(x)}</td>`).join('')}</tr></tfoot>`;
}
valIn.addEventListener('input', () => { const pos = valIn.value.length - valIn.selectionStart, n = readVal(); valIn.value = n ? n.toLocaleString('en-US') : ''; const p = Math.max(0, valIn.value.length - pos); valIn.setSelectionRange(p, p); calc(); });
sel.addEventListener('change', calc);
document.querySelectorAll('input[name="kind"]').forEach(r => r.addEventListener('change', calc));
calc();

/* ---------- budget impact ---------- */
const FYS = ['FY2028', 'FY2029', 'FY2030', 'FY2031', 'FY2032'];
(() => {
  const gs = D.govs, max = gs[0].imp[1], el = $('lossBars');
  el.innerHTML = gs.map((g, i) => `<div class="hb" tabindex="0" data-tip="${i}"><span class="hb-n">${esc(g.n)}</span><span class="hb-track"><span class="hb-bar" style="width:${g.imp[1] ? Math.max(.5, g.imp[1] / max * 100) : 0}%;background:var(--s2)"></span></span><span class="hb-v">${g.imp[1] ? big(g.imp[1]) : '$0'} <em>${g.levy ? pct(g.imp[1] / g.levy) + ' of levy' : 'no levy'}</em></span></div>`).join('');
  bindTips(el, i => { const g = gs[i]; return `<b>${esc(g.n)}</b><br>FY2029 estimate: ${usd(-g.imp[1])}<br>FY2026 property tax levied: ${big(g.levy)}${g.gf ? `<br>FY2026 general fund: ${big(g.gf)}` : ''}`; });
  const tot = FYS.map((_, j) => gs.reduce((a, g) => a + g.imp[j], 0));
  $('lossTable').innerHTML = `<thead><tr><th scope="col">Government</th>${FYS.map(f => `<th scope="col" class="num">${f}</th>`).join('')}<th scope="col" class="num">FY2026 levy</th></tr></thead><tbody>` +
    gs.map(g => `<tr><th scope="row">${esc(g.n)}</th>${g.imp.map(v => `<td class="num">${v ? '−' + big(v) : '$0'}</td>`).join('')}<td class="num">${g.levy ? big(g.levy) : '$0'}</td></tr>`).join('') +
    `</tbody><tfoot><tr><th scope="row">All Bay County governments</th>${tot.map(v => `<td class="num">−${big(v)}</td>`).join('')}<td class="num">${big(gs.reduce((a, g) => a + g.levy, 0))}</td></tr></tfoot>`;
})();

/* PDF */
$('pdf').addEventListener('click', () => { document.querySelectorAll('.amend details').forEach(d => d.open = true); setTimeout(() => window.print(), 60); });
})();
