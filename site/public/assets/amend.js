(() => {
const D = {"districts":[{"id":"Panama City","label":"Panama City","stack":["bay_county_general","county_mosquito_control","school_rle","school_discretionary","school_capital_outlay","nwfwmd","city_panama_city"],"total":[15.6352,15.4125,14.9662,15.9425,15.7689,15.7938]},{"id":"Panama City - Downtown DIB","label":"Panama City, downtown improvement district","stack":["bay_county_general","county_mosquito_control","school_rle","school_discretionary","school_capital_outlay","nwfwmd","city_panama_city","pc_downtown_improvement_board"],"total":[18.6352,18.4125,17.9662,18.9425,18.7689,18.7938]},{"id":"Panama City Beach","label":"Panama City Beach","stack":["bay_county_general","beach_mosquito","school_rle","school_discretionary","school_capital_outlay","nwfwmd"],"total":[10.7853,10.6126,10.1863,11.1226,10.909,10.9139]},{"id":"Lynn Haven","label":"Lynn Haven","stack":["bay_county_general","county_mosquito_control","school_rle","school_discretionary","school_capital_outlay","nwfwmd","city_lynn_haven"],"total":[14.9353,14.6126,14.2663,15.1426,15.019,15.0439]},{"id":"Callaway","label":"Callaway","stack":["bay_county_general","county_mosquito_control","school_rle","school_discretionary","school_capital_outlay","nwfwmd","city_callaway"],"total":[13.3853,13.2626,12.9163,13.8926,13.719,13.6939]},{"id":"Springfield","label":"Springfield","stack":["bay_county_general","county_mosquito_control","school_rle","school_discretionary","school_capital_outlay","nwfwmd","city_springfield"],"total":[14.1003,14.9776,15.0313,16.0076,15.834,15.8589]},{"id":"Parker","label":"Parker","stack":["bay_county_general","county_mosquito_control","school_rle","school_discretionary","school_capital_outlay","nwfwmd","city_parker"],"total":[10.6353,10.5126,10.1663,14.1426,13.969,13.9939]},{"id":"Mexico Beach","label":"Mexico Beach","stack":["bay_county_general","county_mosquito_control","school_rle","school_discretionary","school_capital_outlay","nwfwmd","city_mexico_beach"],"total":[18.6353,17.5126,16.6663,17.1425,16.719,16.2439]},{"id":"unincorporated","label":"Unincorporated Bay County (not in a city)","stack":["bay_county_general","county_fire_mstu","county_mosquito_control","school_rle","school_discretionary","school_capital_outlay","nwfwmd"],"total":[12.0153,11.8926,11.5463,12.5226,12.349,12.3739]},{"id":"unincorporated - beach area","label":"Unincorporated beach area (outside PCB city limits)","stack":["bay_county_general","county_fire_mstu","beach_mosquito","school_rle","school_discretionary","school_capital_outlay","nwfwmd"],"total":[12.1653,11.9926,11.5663,12.5026,12.289,12.2939]}],"auth":{"bay_county_general":{"n":"Bay County Commission","g":"county","school":false,"m":[4.4362,4.4362,4.4362,5.4362,5.4362,5.4362],"rb":[4.1815,4.1604,4.0397,4.0479,5.1719,5.2561],"lv":[77782542,86257830,99987435,143997444,161094369,173437899]},"county_fire_mstu":{"n":"County fire service (outside cities)","g":"countysvc","school":false,"m":[1.38,1.38,1.38,1.38,1.38,1.38],"rb":[1.2827,1.281,1.2352,1.2266,1.2807,1.3074],"lv":[9637453,10734882,12562216,14877077,16975667,18744318]},"county_mosquito_control":{"n":"County mosquito control","g":"countysvc","school":false,"m":[0.2,0.2,0.2,0.2,0.2,0.2],"rb":[0.1868,0.185,0.1811,0.1825,0.1898,0.1913],"lv":[1239783,1423598,1672463,1986072,2254848,2499800]},"school_rle":{"n":"Schools: state-required rate","g":"school","school":true,"m":[3.72,3.599,3.256,3.235,3.063,3.089],"rb":[null,null,null,null,null,null],"lv":[null,null,null,null,null,null]},"school_discretionary":{"n":"Schools: local operating","g":"school","school":true,"m":[0.748,0.748,0.748,0.748,0.748,0.748],"rb":[null,null,null,null,null,null],"lv":[null,null,null,null,null,null]},"school_capital_outlay":{"n":"Schools: buildings and buses","g":"school","school":true,"m":[1.5,1.5,1.5,1.5,1.5,1.5],"rb":[null,null,null,null,null,null],"lv":[null,null,null,null,null,null]},"nwfwmd":{"n":"NW Florida Water Management District","g":"other","school":false,"m":[0.0311,0.0294,0.0261,0.0234,0.0218,0.0207],"rb":[0.0311,0.0294,0.0261,0.0234,0.0218,0.0207],"lv":[548290,574387,590247,622514,649004,663367]},"beach_mosquito":{"n":"Beach Mosquito Control District","g":"other","school":false,"m":[0.35,0.3,0.22,0.18,0.14,0.12],"rb":[0.4863,0.3256,0.2632,0.1937,0.1669,0.1341],"lv":[3477762,3260297,2777985,2656670,2290201,2087639]},"pc_downtown_improvement_board":{"n":"Downtown Improvement Board","g":"other","school":false,"m":[3.0,3.0,3.0,3.0,3.0,3.0],"rb":[2.8634,2.3199,2.4559,2.7145,2.8992,3.2227],"lv":[117286,152151,186541,212729,263038,246996]},"city_callaway":{"n":"City of Callaway","g":"city","school":false,"m":[2.75,2.75,2.75,2.75,2.75,2.7],"rb":[2.571,2.64,2.543,2.5499,2.738,2.6981],"lv":[1340353,1561142,1914647,2343145,2625932,2758284]},"city_lynn_haven":{"n":"City of Lynn Haven","g":"city","school":false,"m":[4.3,4.1,4.1,4.0,4.05,4.05],"rb":[3.7044,3.9403,3.7602,3.7837,3.7594,3.8866],"lv":[4593303,5109952,5781446,6466185,7199341,7674166]},"city_mexico_beach":{"n":"City of Mexico Beach","g":"city","school":false,"m":[8.0,7.0,6.5,5.9999,5.75,5.25],"rb":[7.0107,7.178,5.6073,5.565,5.36,5.128],"lv":[2836928,2891371,3478767,3857208,4378852,4696116]},"city_panama_city":{"n":"City of Panama City","g":"city","school":false,"m":[4.9999,4.8999,4.7999,4.7999,4.7999,4.7999],"rb":[5.2385,4.6788,4.5411,4.4388,4.6007,4.6529],"lv":[10923022,12048297,13345551,15752974,17573644,18951299]},"city_parker":{"n":"City of Parker","g":"city","school":false,"m":[0.0,0.0,0.0,3.0,3.0,3.0],"rb":[null,null,0.0,null,2.7178,2.4991],"lv":[0,0,0,829456,932951,967589]},"city_springfield":{"n":"City of Springfield","g":"city","school":false,"m":[3.465,4.465,4.865,4.865,4.865,4.865],"rb":[3.2478,3.1555,3.9672,4.2606,4.6096,4.6658],"lv":[666562,998061,1395735,1712167,1912706,2083737]}},"groups":[["school","Schools"],["county","Bay County"],["city","Your city"],["countysvc","County fire & mosquito"],["other","Special districts"]],"second":25722,"govs":[{"n":"Bay County Commission (incl. fire and mosquito control)","levy":194682017,"gf":281737981,"imp":[21456254,34951396,35415219,35568776,35443810]},{"n":"City of Panama City","levy":18951299,"gf":67703379,"imp":[2426616,3743903,3749738,3709591,3618649]},{"n":"City of Lynn Haven","levy":7674166,"gf":24353606,"imp":[1596668,2570421,2549825,2508064,2447909]},{"n":"City of Callaway","levy":2758284,"gf":null,"imp":[598387,861816,860137,850339,832808]},{"n":"City of Springfield","levy":2083737,"gf":null,"imp":[383959,504531,504166,498976,490007]},{"n":"City of Mexico Beach","levy":4696116,"gf":null,"imp":[272952,499972,596563,694956,794765]},{"n":"Special districts (water management, beach mosquito)","levy":2751006,"gf":null,"imp":[201530,341089,352081,359990,365412]},{"n":"City of Parker","levy":967589,"gf":7098904,"imp":[164874,236612,236159,233697,229229]},{"n":"City of Panama City Beach","levy":0,"gf":71918315,"imp":[0,0,0,0,0]}],"state":[4929543878,8714492521,9647862749,10710157749,11834731658],"vote":"2026-11-03"};
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
// inputs live in the link (?v=value&d=district&k=home|new|non) so an estimate can be shared, e.g. from My Address
const P0 = new URLSearchParams(location.search);
if (P0.get('d') && D.districts.some(d => d.id === P0.get('d'))) sel.value = P0.get('d');
if (/^\d+$/.test(P0.get('v') || '')) valIn.value = Math.min(+P0.get('v'), 1e9).toLocaleString('en-US');
{ const k0 = P0.get('k') || (P0.get('h') === '0' ? 'non' : P0.get('h') === '1' ? 'home' : ''), r = document.querySelector(`input[name="kind"][value="${['home', 'new', 'non'].includes(k0) ? k0 : 'x'}"]`); if (r) r.checked = true; }
function saveUrl(v) {
  const u = new URL(location.href);
  u.searchParams.set('v', v); u.searchParams.set('d', sel.value); u.searchParams.set('k', kind()); u.searchParams.delete('h');
  try { history.replaceState(null, '', u); } catch (e) {}
}

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
  if (calc.ready) saveUrl(v);
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
calc(); calc.ready = true; // don't add params to a plain visit until someone changes an input
if (['v', 'd', 'k', 'h'].some(k => P0.has(k))) { saveUrl(readVal()); if (!location.hash) $('calc')?.scrollIntoView(); }

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
