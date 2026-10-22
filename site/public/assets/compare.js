(() => {
const R = [{"k":"county","n":"Bay County","kind":"county","slug":"bay-county","pop":199950,"budget":734465609,"gf":281737981,"mills":5.4362,"levy":194682017,"debt":281388749,"debt_fy":"FY2024","findings":4,"repeats":0,"audit_fy":"FY2024","votes":61,"split":1,"bill":120.7,"fema":319014690.78,"cra":null,"emp":835,"contracts":299343304.36,"ncontracts":137,"status":"Adopted Sept 16, 2025"},{"k":"schools","n":"Bay District Schools","kind":"schools","slug":"bay-district-schools","pop":199950,"budget":648500000,"gf":345030839,"mills":5.337,"levy":187128449,"debt":147037357,"debt_fy":"FY2025","findings":5,"repeats":2,"audit_fy":"FY2025","votes":104,"split":34,"bill":null,"fema":135113457.66,"cra":null,"emp":null,"contracts":null,"ncontracts":null,"status":"Total is the tentative July 2025 figure; the final adopted total was not found online"},{"k":"pc","n":"Panama City","kind":"city","slug":"panama-city","pop":38078,"budget":153837293,"gf":67703379,"mills":4.7999,"levy":18951299,"debt":234437765,"debt_fy":"FY2024","findings":1,"repeats":1,"audit_fy":"FY2024","votes":150,"split":63,"bill":183.19,"fema":151288143.77,"cra":14042978.68,"emp":631,"contracts":182181008.43,"ncontracts":102,"status":"Adopted September 2025"},{"k":"pcb","n":"Panama City Beach","kind":"city","slug":"panama-city-beach","pop":19581,"budget":282221725,"gf":71918315,"mills":0,"levy":0,"debt":87554742,"debt_fy":"FY2025","findings":0,"repeats":0,"audit_fy":"FY2025","votes":94,"split":14,"bill":87.42,"fema":2341007.64,"cra":80404359.28,"emp":null,"contracts":86322205.26,"ncontracts":44,"status":"Adopted Aug 28, 2025"},{"k":"lh","n":"Lynn Haven","kind":"city","slug":"lynn-haven","pop":21733,"budget":61858708,"gf":24353606,"mills":4.05,"levy":7674166,"debt":31549735,"debt_fy":"FY2025","findings":1,"repeats":1,"audit_fy":"FY2025","votes":59,"split":26,"bill":129.76,"fema":44541806.79,"cra":1800963.7,"emp":219.5,"contracts":15440578.4,"ncontracts":26,"status":"Adopted Sept 23, 2025"},{"k":"cw","n":"Callaway","kind":"city","slug":"callaway","pop":15157,"budget":55429117,"gf":13705820,"mills":2.7,"levy":2758284,"debt":13230554,"debt_fy":"FY2025","findings":0,"repeats":0,"audit_fy":"FY2025","votes":41,"split":5,"bill":117.11,"fema":26072972.47,"cra":648087,"emp":99.0,"contracts":9099602.92,"ncontracts":11,"status":"Adopted FY2026"},{"k":"sp","n":"Springfield","kind":"city","slug":"springfield","pop":9213,"budget":28655332,"gf":17954071,"mills":4.865,"levy":2083737,"debt":25380717,"debt_fy":"FY2025","findings":8,"repeats":7,"audit_fy":"FY2025","votes":63,"split":1,"bill":180.2,"fema":35007817.88,"cra":60017,"emp":null,"contracts":31713711.43,"ncontracts":8,"status":"Adopted FY2026"},{"k":"parker","n":"Parker","kind":"city","slug":"parker","pop":4608,"budget":17252341,"gf":5691404,"mills":3.0,"levy":967589,"debt":766663,"debt_fy":"FY2025","findings":7,"repeats":5,"audit_fy":"FY2025","votes":14,"split":7,"bill":null,"fema":12112698.0,"cra":148377,"emp":null,"contracts":7719391.75,"ncontracts":2,"status":"Adopted FY2026"},{"k":"mb","n":"Mexico Beach","kind":"city","slug":"mexico-beach","pop":1402,"budget":null,"gf":null,"mills":5.25,"levy":4696116,"debt":3124600,"debt_fy":"FY2025","findings":7,"repeats":6,"audit_fy":"FY2025","votes":20,"split":10,"bill":147.9,"fema":105720322.65,"cra":null,"emp":null,"contracts":17225372.97,"ncontracts":9,"status":"Adopted September 2025, but the budget is not posted online"}];
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const big = n => n == null ? '—' : n >= 1e9 ? '$' + (n / 1e9).toFixed(2) + 'B' : n >= 1e6 ? '$' + (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? '$' + Math.round(n / 1e3) + 'K' : '$' + Math.round(n);
const usd = n => n == null ? '—' : '$' + Math.round(n).toLocaleString('en-US');
const num = n => n == null ? '—' : Math.round(n).toLocaleString('en-US');
const COL = ['var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s4)', 'var(--s5)', '#6b7fa8', '#8a6bb0', '#4f9a9a', '#b07a4f'];
const color = Object.fromEntries(R.map((r, i) => [r.k, COL[i % COL.length]]));
// [id, title, plain explanation, value fn(r, per), formatter, higherMeans]
const M = [
  ['pop', 'Residents', '2025 state estimate.', r => r.pop, num],
  ['budget', 'Budget', 'Total adopted budget, all funds.', (r, per) => per ? r.budget && r.pop && r.budget / r.pop : r.budget, (v, per) => per ? usd(v) : big(v), 'perable'],
  ['mills', 'Property tax rate', 'Mills: dollars of tax per $1,000 of taxable value.', r => r.kind === 'schools' ? null : r.mills, v => v == null ? '—' : v ? v + ' mills' : 'none'],
  ['levy', 'Property tax collected', 'What this government\'s property tax rate brings in.', (r, per) => per ? r.levy && r.pop && r.levy / r.pop : r.levy, (v, per) => per ? usd(v) : big(v), 'perable'],
  ['debt', 'Debt', 'Bonds, notes, loans and leases owed, latest audit.', (r, per) => per ? r.debt && r.pop && r.debt / r.pop : r.debt, (v, per) => per ? usd(v) : big(v), 'perable'],
  ['emp', 'Employees', 'Full-time equivalent staff.', (r, per) => per ? r.emp && r.pop && r.emp / r.pop * 1000 : r.emp, (v, per) => v == null ? '—' : per ? v.toFixed(1) : num(v), 'perable'],
  ['findings', 'Audit findings', 'Problems the outside auditor reported in the latest audit (repeats in brackets).', r => r.findings, (v, per, r) => v == null ? '—' : v + (r && r.repeats ? ` (${r.repeats} repeat)` : '')],
  ['split', 'Split votes', 'Share of recorded money votes that were not unanimous.', r => r.votes ? r.split / r.votes * 100 : null, (v, per, r) => v == null ? '—' : Math.round(v) + '% of ' + r.votes],
  ['bill', 'Typical utility bill', 'Monthly water and sewer (and garbage where the city bills it) at 5,000 gallons.', r => r.bill, v => v == null ? '—' : '$' + v.toFixed(2)],
  ['contracts', 'Major contracts', 'Contracts tracked on this site since October 2022. Coverage is fullest for Bay County and Panama City, thinner for small cities.', (r, per) => per ? r.contracts && r.pop && r.contracts / r.pop : r.contracts, (v, per) => per ? usd(v) : big(v), 'perable'],
  ['fema', 'Hurricane Michael money', 'FEMA rebuilding money obligated.', (r, per) => per ? r.fema && r.pop && r.fema / r.pop : r.fema, (v, per) => per ? usd(v) : big(v), 'perable'],
  ['cra', 'CRA spending documented', 'Redevelopment agency spending and awards documented on this site; records are more complete for some agencies than others.', (r, per) => per ? r.cra && r.pop && r.cra / r.pop : r.cra, (v, per) => per ? usd(v) : big(v), 'perable'],
];
const qs = new URLSearchParams(location.search);
let sel = new Set((qs.get('g') || '').split(',').filter(k => R.some(r => r.k === k)));
if (sel.size === 1) R.filter(r => r.kind === R.find(x => x.k === [...sel][0]).kind && r.kind === 'city').forEach(r => sel.add(r.k));
if (!sel.size) R.filter(r => r.kind === 'city').forEach(r => sel.add(r.k));
function chips() {
  $('cmpChips').innerHTML = R.map(r => `<button type="button" class="chip" data-k="${r.k}" aria-pressed="${sel.has(r.k)}" style="--dot:${color[r.k]}"><span class="dot"></span>${esc(r.n)}</button>`).join('');
}
function draw() {
  const per = $('cmpPer').checked, rows = R.filter(r => sel.has(r.k));
  $('printMeta').textContent = 'Comparing: ' + rows.map(r => r.n).join(', ') + (per ? ' · per resident where it applies' : '');
  $('cmpGrid').innerHTML = rows.length < 2 ? '<p class="muted">Pick at least two governments.</p>' : M.map(([id, title, help, fn, fmt, perable]) => {
    const vals = rows.map(r => [r, fn(r, per && perable)]).filter(([, v]) => v != null && !isNaN(v));
    const missing = rows.filter(r => !vals.some(([x]) => x === r)).map(r => r.n);
    if (!vals.length) return '';
    const mx = Math.max(...vals.map(([, v]) => v)) || 1;
    vals.sort((a, b) => b[1] - a[1]);
    return `<section class="card cmp-card"><h3>${esc(title)}${per && perable ? ` <span class="muted small">${id === 'emp' ? 'per 1,000 residents' : 'per resident'}</span>` : ''}</h3><p class="muted small">${esc(help)}</p>
      <div class="hbars">${vals.map(([r, v]) => `<div class="hb"><span class="hb-n"><a href="/governments/${r.slug}">${esc(r.n)}</a></span><span class="hb-track"><span class="hb-bar" style="width:${Math.max(0.5, v / mx * 100).toFixed(1)}%;background:${color[r.k]}"></span></span><span class="hb-v">${esc(fmt(v, per && perable, r))}</span></div>`).join('')}</div>
      ${missing.length ? `<p class="note small">Not available: ${esc(missing.join(', '))}</p>` : ''}</section>`;
  }).join('');
  const u = new URL(location.href); u.searchParams.set('g', [...sel].join(',')); history.replaceState(null, '', u);
}
$('cmpChips').addEventListener('click', e => { const b = e.target.closest('[data-k]'); if (!b) return; sel.has(b.dataset.k) ? sel.delete(b.dataset.k) : sel.add(b.dataset.k); chips(); draw(); });
document.querySelectorAll('[data-set]').forEach(b => b.addEventListener('click', () => {
  sel = new Set(b.dataset.set === 'all' ? R.map(r => r.k) : b.dataset.set === 'cities' ? R.filter(r => r.kind === 'city').map(r => r.k) : []); chips(); draw(); }));
$('cmpPer').addEventListener('input', draw);
chips(); draw();
})();
