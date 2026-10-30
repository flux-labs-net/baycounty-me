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
  // Trash day at the saved home: only shown on pickup day, or from 4 p.m. the day before. Otherwise nothing.
  if (h.lat && h.lon) {
    try {
      const j = await (await fetch(`/api/v1/utilities?lat=${h.lat}&lon=${h.lon}`)).json();
      const c = window.BCTrashCard(j && j.data);
      if (c) { $('hTrashT').textContent = c.title; $('hTrashS').textContent = c.detail; $('hTrash').hidden = false; }
    } catch (e) {}
  }
})();

// The trash card for one /api/v1/utilities lookup, or null when pickup isn't today (or tomorrow, after 4 p.m.).
// Bay County time. A holiday with no garbage pickup says so instead. Same rules as TodayBrief.trashCard in the apps.
window.BCTrashCard = (lookup, now = new Date()) => {
  const g = ((lookup && lookup.pickup) || []).find(p => p.service === 'garbage' && p.days);
  if (!g) return null;
  const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const p = Object.fromEntries(new Intl.DateTimeFormat('en-US', {timeZone: 'America/Chicago', year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', hourCycle: 'h23'})
    .formatToParts(now).map(x => [x.type, +x.value]));
  const day = off => new Date(Date.UTC(p.year, p.month - 1, p.day + off));
  const runs = d => new RegExp(`\\b${DAYS[d.getUTCDay()]}\\b`, 'i').test(g.days);
  // "January 1", "4th Thursday in November", "Last Monday in May"
  const isOn = (when, d) => {
    let m = /^(\w+) (\d{1,2})$/.exec(when || '');
    if (m) return MONTHS.indexOf(m[1]) === d.getUTCMonth() && +m[2] === d.getUTCDate();
    m = /^(1st|2nd|3rd|4th|5th|Last) (\w+) in (\w+)$/i.exec(when || '');
    if (!m || MONTHS.indexOf(m[3]) !== d.getUTCMonth() || DAYS.indexOf(m[2]) !== d.getUTCDay()) return false;
    const last = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
    return /last/i.test(m[1]) ? d.getUTCDate() + 7 > last : Math.ceil(d.getUTCDate() / 7) === parseInt(m[1], 10);
  };
  const closed = d => ((lookup.holidays || []).find(x => /^(no pickup|moved)/i.test(x.garbage || '') && isOn(x.when_observed, d)));
  const card = (d, word, detail) => {
    const h = closed(d);
    if (!h) return {title: `Trash pickup ${word}`, detail};
    // "No pickup; in 2025 Thursday's route moved to Saturday, December 27": a note about another year is left off.
    let rest = h.garbage.replace(/^no pickup[;,.]?\s*/i, '');
    if ((rest.match(/\b20\d\d\b/g) || []).some(y => +y !== d.getUTCFullYear())) rest = '';
    return {title: `No trash pickup ${word}`, detail: rest ? `${h.holiday} · ${rest[0].toUpperCase()}${rest.slice(1)}` : h.holiday};
  };
  if (runs(day(0))) return card(day(0), 'today', 'At your home');
  if (p.hour >= 16 && runs(day(1))) return card(day(1), 'tomorrow', 'Put it out tonight');
  return null;
};

// Live alerts: the alert card follows the live feed (the page is built once a day), and when a live alert has a map
// drawn by government staff (a boil-water area, a closed street) it shows under the card.
(async () => {
  const card = document.getElementById('hAlerts'), mapCard = document.getElementById('hAlertMap');
  if (!card) return;
  let d;
  try { const r = await fetch('/api/v1/emergency'); if (!r.ok) return; d = await r.json(); } catch (e) { return; }
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const n = d.notices || [];
  const b = card.querySelector('b'), sub = card.querySelector('b + span');
  if (n.length) {
    const by = {};
    n.forEach(x => { by[x.kind] = (by[x.kind] || 0) + 1; });
    b.textContent = `${n.length} active notice${n.length === 1 ? '' : 's'}`;
    sub.textContent = Object.entries(by).sort((x, y) => y[1] - x[1]).map(([k, v]) => `${v} ${k}`).join(', ');
  } else { b.textContent = 'No active alerts'; sub.textContent = 'Weather, boil-water and road notices'; }
  const m = n.find(x => x.geometry);
  if (!m || !mapCard) return;
  const t = document.getElementById('hAlertMapT');
  t.href = '/emergency#n-' + encodeURIComponent(m.notice_id);
  t.innerHTML = `${esc(m.title)}<small>${esc([m.source, m.area && m.area !== m.source ? m.area : ''].filter(Boolean).join(' · '))}</small>`;
  mapCard.hidden = false;
  const load = () => window.BCMap ? Promise.resolve() : new Promise((ok, no) => { const s = document.createElement('script'); s.src = '/assets/area-map.js'; s.onload = ok; s.onerror = no; document.head.appendChild(s); });
  try { await load(); await window.BCMap.view(document.getElementById('hAlertMapBox'), m.geometry); } catch (e) { mapCard.hidden = true; }
})();
