// Community events on the home page (#homeEvents) and /events (#evPage). Data is the community-events dataset,
// embedded at build time in #evData. Everything is filtered against today's date in the visitor's browser, so a page
// built yesterday still starts at today. The server-rendered list is the no-script fallback.
(() => {
  const el = document.getElementById('evData'); if (!el) return;
  const D = JSON.parse(el.textContent);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const pad = n => String(n).padStart(2, '0');
  const iso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const now = new Date(), today = iso(now), tomorrow = iso(new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1));
  const plus = n => iso(new Date(now.getFullYear(), now.getMonth(), now.getDate() + n));
  const MO = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const WDL = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const day = s => { const [y, m, d] = s.slice(0, 10).split('-').map(Number); return new Date(y, m - 1, d); };
  const time = s => { const h = +s.slice(11, 13), m = s.slice(14, 16); if (!h && m === '00') return ''; return `${h % 12 || 12}${m === '00' ? '' : ':' + m} ${h < 12 ? 'a.m.' : 'p.m.'}`; };
  const dayLabel = s => s === today ? 'Today' : s === tomorrow ? 'Tomorrow' : (() => { const d = day(s); return `${WDL[d.getDay()]}, ${MO[d.getMonth()]} ${d.getDate()}`; })();
  const tone = c => ({'Public meeting': 'navy', Library: 'teal', Chamber: 'amber'}[c] || 'salmon');
  // an event is "on" a day from its start through its end; multi-day events show on each day only on /events
  const live = D.filter(e => (e.e || e.s).slice(0, 10) >= today);

  function row(e, opts = {}) {
    const t = e.a ? 'All day' : time(e.s);
    const where = [e.v, e.w].filter(Boolean).join(' · ');
    return `<li class="ev-row"><span class="ev-t">${esc(t || 'All day')}</span><span class="ev-b"><a href="${esc(e.u)}" rel="noopener">${esc(e.t)}</a>` +
      `<small>${esc(where)}${opts.src ? ` · ${esc(e.src)}` : ''}</small></span><span class="ev-c t-${tone(e.c)}">${esc(e.c)}</span></li>`;
  }
  function card(e) {
    const d = day(e.s), multi = e.e && e.e.slice(0, 10) !== e.s.slice(0, 10);
    const when = (e.s.slice(0, 10) <= today && multi ? 'Now through ' + (() => { const x = day(e.e); return `${MO[x.getMonth()]} ${x.getDate()}`; })()
      : dayLabel(e.s.slice(0, 10))) + (e.a || multi ? '' : ' · ' + time(e.s));
    return `<a class="ui-mc ev-card" href="${esc(e.u)}" rel="noopener"><span class="ui-date" aria-hidden="true"><span class="mo">${MO[d.getMonth()].toUpperCase()}</span>` +
      `<span class="d">${d.getDate()}</span><span class="wd">${WD[d.getDay()]}</span></span><span class="ev-cb"><b>${esc(e.t)}</b><small>${esc(when)}</small>` +
      `<small>${esc([e.v, e.w].filter(Boolean).join(' · '))}</small></span></a>`;
  }
  function chips(g, onPick) {
    g.addEventListener('click', ev => { const b = ev.target.closest('button'); if (!b) return;
      g.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); onPick(b.dataset.v); });
  }

  // Home page: today's list, featured one-off events in the next two weeks, and counts for the side cards.
  const home = document.getElementById('homeEvents');
  if (home) {
    let town = '';
    const draw = () => {
      const mine = live.filter(e => !town || e.w === town);
      const todays = mine.filter(e => e.s.slice(0, 10) <= today);
      const list = document.getElementById('heToday');
      const N = matchMedia('(max-width:560px)').matches ? 5 : 7;
      list.innerHTML = todays.length ? todays.slice(0, N).map(e => row(e)).join('') :
        '<li class="ev-none">Nothing listed for today. See what\'s coming up.</li>';
      document.getElementById('heTodayMore').hidden = todays.length <= N;
      document.getElementById('heTodayMore').textContent = `All ${todays.length} today →`;
      const feat = mine.filter(e => !e.r && e.c !== 'Public meeting' && e.s.slice(0, 10) > today && e.s.slice(0, 10) <= plus(21));
      // one card per title, soonest first, so a three-day festival shows once
      // one card per title, soonest first, so a three-day festival shows once; community and chamber events before library programs
      const seen = new Set(), picks = [];
      for (const e of [...feat.filter(x => x.c !== 'Library'), ...feat.filter(x => x.c === 'Library')]) { if (seen.has(e.t)) continue; seen.add(e.t); picks.push(e); if (picks.length === 8) break; }
      picks.sort((x, y) => x.s < y.s ? -1 : 1);
      document.getElementById('heSoon').innerHTML = picks.map(card).join('') || '<p class="ev-none">No one-off events listed in the next three weeks.</p>';
      const wk = live.filter(e => e.c === 'Public meeting' && e.s.slice(0, 10) <= plus(7));
      const m = document.getElementById('heMeet');
      if (m) m.innerHTML = wk.slice(0, 4).map(e => `<li><span>${esc(dayLabel(e.s.slice(0, 10)).replace(/day,.*/, 'day'))}<br>${esc(time(e.s))}</span><a href="${esc(e.u)}" rel="noopener">${esc(e.t)}</a><small>${esc(e.src)}</small></li>`).join('') || '<li class="ev-none">No public meetings listed this week.</li>';
      const n = document.getElementById('heCount'); if (n) n.textContent = `${live.filter(e => e.s.slice(0, 10) <= plus(7)).length} events this week`;
    };
    const g = document.getElementById('heTown'); if (g) chips(g, v => { town = v; draw(); });
    draw();
  }

  // /events: every upcoming event, grouped by day, with town, kind and search filters.
  const page = document.getElementById('evPage');
  if (page) {
    const P = new URLSearchParams(location.search);
    let town = P.get('town') || '', kind = P.get('kind') || '', q = '', oneoff = false, limit = 14;
    const pick = (id, v) => document.querySelectorAll(`#${id} button`).forEach(b => b.setAttribute('aria-pressed', b.dataset.v === v));
    pick('evTown', town); pick('evKind', kind);
    const box = document.getElementById('evList'), more = document.getElementById('evMore');
    const draw = () => {
      const ql = q.trim().toLowerCase();
      const mine = live.filter(e => (!town || e.w === town) && (!kind || e.c === kind) && (!oneoff || !e.r) &&
        (!ql || (e.t + ' ' + (e.v || '') + ' ' + e.src).toLowerCase().includes(ql)));
      const days = new Map();
      for (const e of mine) { const k = e.s.slice(0, 10) < today ? today : e.s.slice(0, 10); if (!days.has(k)) days.set(k, []); days.get(k).push(e); }
      const keys = [...days.keys()].sort();
      box.innerHTML = keys.slice(0, limit).map(k => `<section class="ev-day" data-share-date="${esc(k)}"><h3>${esc(dayLabel(k))}<span>${days.get(k).length}</span></h3><ul class="ev-list">${days.get(k).map(e => row(e, {src: true})).join('')}</ul></section>`).join('') ||
        '<p class="ev-none">No upcoming events match.</p>';
      more.hidden = keys.length <= limit;
      document.getElementById('evCount').textContent = `${mine.length} event${mine.length === 1 ? '' : 's'}`;
    };
    chips(document.getElementById('evTown'), v => { town = v; limit = 14; draw(); });
    chips(document.getElementById('evKind'), v => { kind = v; limit = 14; draw(); });
    document.getElementById('evQ').addEventListener('input', ev => { q = ev.target.value; draw(); });
    document.getElementById('evOne').addEventListener('change', ev => { oneoff = ev.target.checked; draw(); });
    more.addEventListener('click', () => { limit += 14; draw(); });
    draw();
  }
})();
