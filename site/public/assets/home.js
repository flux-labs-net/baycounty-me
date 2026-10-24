// Home page: the interactive tax bill. Data is the latest tax year's rates (property-tax-rates and
// tax-districts datasets), embedded at build time in #homeData. The page is fully rendered without this script.
(() => {
  const el = document.getElementById('homeData'); if (!el) return;
  const D = JSON.parse(el.textContent), A = D.auth;
  let area = D.area, value = D.value;
  try { const s = JSON.parse(localStorage.getItem('homeBill') || '{}'); if (D.areas.some(a => a.id === s.area)) area = s.area; if (s.value >= 50000 && s.value <= 600000) value = s.value; } catch (e) {}
  const $ = id => document.getElementById(id);
  const usd = v => '$' + Math.round(v).toLocaleString('en-US');
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const range = $('hVal'); range.value = value;
  function draw() {
    const a = D.areas.find(x => x.id === area);
    $('billArea').textContent = a.n;
    $('billStack').innerHTML = a.stack.map(id => `<span class="g-${A[id].g}" style="flex:${A[id].m}"></span>`).join('');
    $('billLines').innerHTML = a.stack.map(id => `<li class="g-${A[id].g}"><span class="rl-n"><i></i>${esc(A[id].n)}</span><span class="rl-m">${A[id].m.toFixed(4)}</span><span class="rl-v">${usd(A[id].m * value / 1000)}</span></li>`).join('');
    $('billMills').textContent = a.t.toFixed(4);
    $('billTotal').textContent = usd(a.t * value / 1000);
    $('hValOut').textContent = usd(value);
    document.querySelectorAll('[data-val]').forEach(n => n.textContent = usd(value));
    document.querySelectorAll('.h-chips [data-area]').forEach(b => b.setAttribute('aria-pressed', b.dataset.area === area));
    const max = Math.max(...D.areas.map(x => x.t));
    $('cmpBars').innerHTML = [...D.areas].sort((x, y) => y.t - x.t).map(x => `<li${x.id === area ? ' class="on"' : ''}><button type="button" data-area="${esc(x.id)}" aria-pressed="${x.id === area}"><span class="cb-n">${esc(x.n)}</span><span class="cb-t"><span style="width:${(x.t / max * 100).toFixed(1)}%"></span></span><span class="cb-v">${usd(x.t * value / 1000)}</span></button></li>`).join('');
    try { localStorage.setItem('homeBill', JSON.stringify({area, value})); } catch (e) {}
  }
  document.addEventListener('click', e => { const b = e.target.closest('[data-area]'); if (b && b.closest('.h-home')) { area = b.dataset.area; draw(); } });
  range.addEventListener('input', () => { value = +range.value; draw(); });
  draw();
})();
