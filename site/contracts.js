(() => {
const R = __CT__;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const usd = n => '$' + Math.round(n).toLocaleString('en-US');
const big = n => n >= 1e6 ? '$' + (n / 1e6).toFixed(1) + 'M' : '$' + Math.round(n / 1e3) + 'K';
let shown = 50, cur = [];
function filt() {
  const q = $('ctQ').value.trim().toLowerCase(), g = $('ctG').value, m = $('ctM').value;
  cur = R.filter(r => (!g || r.g === g) && (!m || r.m === m) && (!q || (r.v + ' ' + r.p + ' ' + r.n).toLowerCase().includes(q)));
  $('ctCount').textContent = `${cur.length} contracts · ${big(cur.reduce((a, r) => a + r.a, 0))}`;
  $('ctT').tBodies[0].innerHTML = cur.slice(0, shown).map(r => `<tr><td>${esc(r.g)}</td><td class="wrap"><b>${esc(r.v)}</b></td><td class="wrap small">${esc(r.p)}${r.n ? `<br><span class="muted">${esc(r.n)}</span>` : ''}</td><td class="num">${usd(r.a)}</td><td class="small">${esc(r.m)}</td><td class="small">${esc(r.d)} ${r.u ? `<a class="src" href="${esc(r.u)}" target="_blank" rel="noopener">Source</a>` : ''}</td></tr>`).join('') || '<tr><td colspan="6" class="muted">No contracts match.</td></tr>';
  $('ctMore').hidden = cur.length <= shown;
}
['ctQ', 'ctG', 'ctM'].forEach(id => $(id).addEventListener('input', () => { shown = 50; filt(); }));
$('ctMore').addEventListener('click', () => { shown += 100; filt(); });
$('ctCsv').addEventListener('click', () => {
  const q = v => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const csv = ['government,vendor,purpose,amount,method,method_as_stated,date,source_url,notes'].concat(cur.map(r => [r.g, r.v, r.p, r.a, r.m, r.mf, r.d, r.u, r.n].map(q).join(','))).join('\n');
  const u = URL.createObjectURL(new Blob([csv], {type: 'text/csv'})), l = document.createElement('a'); l.href = u; l.download = 'bay-county-contracts.csv'; l.click(); setTimeout(() => URL.revokeObjectURL(u), 1000);
});
filt();
})();
