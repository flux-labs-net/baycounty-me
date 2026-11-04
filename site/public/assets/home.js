// Home page: the tax-bill sentence in the Your money band ("A $200,000 home in Lynn Haven pays $3,045 a year"). It
// follows the area and value last picked on the tax bill (localStorage homeBill), else the signed-in resident's home
// city. Data is the latest tax year's total rate per area (tax-districts dataset), embedded at build time in #homeData.
(() => {
  const el = document.getElementById('homeData'); if (!el) return;
  const D = JSON.parse(el.textContent);
  let area = D.area, value = D.value, picked = false;
  try { const s = JSON.parse(localStorage.getItem('homeBill') || '{}'); if (D.areas.some(a => a.id === s.area)) { area = s.area; picked = true; } if (s.value >= 50000 && s.value <= 600000) value = s.value; } catch (e) {}
  const homeArea = c => c && (c.gov === 'county' ? 'unincorporated' : c.name);
  const goHome = () => { const h = homeArea(window.BCHomeCity && window.BCHomeCity()); if (!picked && h && D.areas.some(a => a.id === h) && h !== area) { area = h; return true; } return false; };
  const usd = v => '$' + Math.round(v).toLocaleString('en-US');
  const draw = () => {
    const a = D.areas.find(x => x.id === area), $ = id => document.getElementById(id);
    if (!a || !$('hTeaseAmt')) return;
    $('hTeaseVal').textContent = usd(value); $('hTeaseArea').textContent = a.p; $('hTeaseAmt').textContent = usd(a.t * value / 1000);
  };
  if (goHome() || area !== D.area || value !== D.value) draw();
  if (window.BCHome) window.BCHome().then(() => { if (goHome()) draw(); });
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

// Signed in with a saved home: the next-meeting card shows the home's own government (its city, or the County
// Commission outside city limits). With none posted, it says so and shows the next one in the county.
(() => {
  const a = document.getElementById('hMeet'); if (!a || !window.BCHome) return;
  const MO = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  window.BCHome().then(() => {
    const c = window.BCHomeCity && window.BCHomeCity(); if (!c) return;
    let N; try { N = JSON.parse(a.dataset.next); } catch (e) { return; }
    const p = n => String(n).padStart(2, '0'), d = new Date();
    const today = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`, now = `${today}T${p(d.getHours())}:${p(d.getMinutes())}`;
    const ok = m => m[0] >= (m[0].length > 10 ? now : today);
    const fmt = s => { const [y, m, dd] = s.slice(0, 10).split('-').map(Number), x = new Date(y, m - 1, dd); return `${WD[x.getDay()]} ${MO[m - 1]} ${dd}`; };
    const b = a.querySelector('b'), sub = b && b.nextElementSibling; if (!sub) return;
    const mine = (N[c.gov] || []).find(ok);
    if (mine) { b.textContent = 'Next meeting · ' + fmt(mine[0]); sub.textContent = mine[1]; a.href = '/meetings?gov=' + encodeURIComponent(c.gov); return; }
    const next = Object.values(N).flat().filter(ok).sort((x, y) => (x[0] < y[0] ? -1 : 1))[0];
    if (next) { b.textContent = 'Next meeting · ' + fmt(next[0]); sub.textContent = `None posted for ${c.name} yet. Next in the county: ${next[1]}`; }
  });
})();

// Election banner (#hElb): live status from /api/v1/election-live, refreshed every 30 seconds while the count runs.
(() => {
  const b = document.getElementById('hElb'); if (!b) return;
  const sub = document.getElementById('hElbSub'), tag = document.getElementById('hElbTag');
  const n = v => Number(v || 0).toLocaleString('en-US');
  let timer;
  const read = () => fetch('/api/v1/election-live').then(r => r.ok ? r.json() : null).then(j => {
    const d = j && j.data; if (!d) return;
    if (d.status === 'waiting') sub.textContent = 'Waiting for the first results. Polls close at 7 p.m.';
    else {
      sub.textContent = `${n(d.precincts_reporting)} of ${n(d.precincts_total)} precincts in · ${n(d.ballots_cast)} ballots counted`;
      if (d.status === 'complete') { tag.classList.add('done'); tag.lastChild.textContent = 'Final'; clearInterval(timer); }
    }
  }).catch(() => {});
  read(); timer = setInterval(read, 30000);
})();
