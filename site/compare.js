(() => {
const R = __CMP__;
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
    return `<section class="card cmp-card" id="m-${id}"><h3>${esc(title)}${per && perable ? ` <span class="muted small">${id === 'emp' ? 'per 1,000 residents' : 'per resident'}</span>` : ''}</h3><p class="muted small">${esc(help)}</p>
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
// links such as /compare#m-debt point at a card drawn above
{ const t = location.hash && document.getElementById(location.hash.slice(1)); if (t) t.scrollIntoView(); }
})();
