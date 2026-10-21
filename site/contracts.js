(async () => {
const $ = id => document.getElementById(id);
let D; // page data loads after the page has rendered; the markup shows a loading note until then
try { const r = await fetch('/data/contracts-page.json'); if (!r.ok) throw new Error(r.status); D = await r.json(); }
catch (e) { $('ctCount').textContent = 'The contracts could not be loaded. Please refresh the page.'; return; }
const R = D;
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const usd = n => '$' + Math.round(n).toLocaleString('en-US');
const big = n => (n < 0 ? '\u2212' : '') + (Math.abs(n) >= 1e6 ? '$' + (Math.abs(n) / 1e6).toFixed(1) + 'M' : '$' + Math.round(Math.abs(n) / 1e3) + 'K');
let shown = 50, cur = [], sk = null, sd = -1; // sort key and direction; null = as published (largest first)
const KEYS = ['g', 'v', 'p', 'a', 'm', 'd'];
const coll = new Intl.Collator('en', {numeric: true, sensitivity: 'base'});
function filt() {
  const q = $('ctQ').value.trim().toLowerCase(), g = $('ctG').value, m = $('ctM').value;
  cur = R.filter(r => (!g || r.g === g) && (!m || r.m === m) && (!q || (r.v + ' ' + r.p + ' ' + r.n).toLowerCase().includes(q)));
  if (sk) cur = cur.map((r, i) => [r, i]).sort(([a, i], [b, j]) => { const x = a[sk], y = b[sk];
    if (!x !== !y) return !x ? 1 : -1; return (sk === 'a' ? x - y : coll.compare(String(x), String(y))) * sd || i - j; }).map(x => x[0]);
  $('ctCount').textContent = `${cur.length} contracts · ${big(cur.reduce((a, r) => a + r.a, 0))}`;
  $('ctT').tBodies[0].innerHTML = cur.slice(0, shown).map(r => `<tr><td>${esc(r.g)}</td><td class="wrap"><b>${esc(r.v)}</b></td><td class="wrap small">${esc(r.p)}${r.n ? `<br><span class="muted">${esc(r.n)}</span>` : ''}</td><td class="num">${usd(r.a)}</td><td class="small">${esc(r.m)}</td><td class="small">${esc(r.d)} ${r.u ? `<a class="src" href="${esc(r.u)}" target="_blank" rel="noopener">Source</a>` : ''}</td></tr>`).join('') || '<tr><td colspan="6" class="muted">No contracts match.</td></tr>';
  $('ctMore').hidden = cur.length <= shown;
}
['ctQ', 'ctG', 'ctM'].forEach(id => $(id).addEventListener('input', () => { shown = 50; filt(); }));
if (window.BCM) BCM.sortable($('ctT'), {onSort: (k, dir, col) => { sk = KEYS[col]; sd = dir; filt(); }});
$('ctMore').addEventListener('click', () => { shown += 100; filt(); });
$('ctCsv').addEventListener('click', () => {
  const rows = [['government', 'vendor', 'purpose', 'amount', 'method', 'method_as_stated', 'date', 'source_url', 'notes']].concat(cur.map(r => [r.g, r.v, r.p, r.a, r.m, r.mf, r.d, r.u, r.n]));
  BCM.download('bay-county-contracts.csv', BCM.toCSV(rows)); BCM.announce('Downloaded ' + cur.length + ' contracts');
});
filt();
})();
