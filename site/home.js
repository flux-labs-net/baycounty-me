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

// Signed in with a saved home (the bcm_in cookie; the home comes from /api/account?action=me): the home takes the
// address box's place and opens its address page. Signed-out visitors and accounts without a home keep the box.
(async () => {
  const box = document.getElementById('hMine');
  if (!box || !/(?:^|; )bcm_in=1/.test(document.cookie)) return;
  let me;
  try { const r = await fetch('/api/account?action=me', {credentials: 'same-origin'}); if (!r.ok) return; me = await r.json(); } catch (e) { return; }
  const $ = id => document.getElementById(id), form = document.querySelector('.h-addr'), note = $('hAddrNote'), h = me && me.home;
  if (!h) { note.innerHTML = 'Save your home on <a href="/account">My home</a> and it will be here next time, with what’s happening nearby.'; return; }
  $('hMineAddr').textContent = String(h.address).replace(/\s+\d{5}(-\d{4})?$/, '');
  $('hMineSub').textContent = [[h.city, h.zip].filter(Boolean).join(' '), h.zone ? `Evacuation zone ${h.zone}` : ''].filter(Boolean).join(' · ');
  $('hMineLink').href = window.BCHomeLink(h);
  $('hMineLink').setAttribute('aria-label', `Your home, ${$('hMineAddr').textContent}: tax bill, trash day, schools and more`);
  form.hidden = true; note.hidden = true; box.hidden = false;
  $('hMineOther').addEventListener('click', () => { form.hidden = false; note.hidden = false; $('hMineOther').hidden = true; $('hq').focus(); });
})();
