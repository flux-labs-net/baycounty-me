"""IRONMAN Florida (/events/ironman-florida): a live road-closure map for race week with a time slider (scrub, play race
day, jump to key moments, or follow the clock), and the visitor guide: schedule, course, where to watch, getting around
and things to do nearby.

Built from the event-road-closures and event-guide datasets (site/special_events.py). Closure lines are placed on the
county street centerlines from the street names (data/events/place_closures.py).
"""
import html
import json

from ui import ico

e = lambda s: html.escape(str(s if s is not None else ''))
EVENT_ID = 'ironman-florida-2026'
LEAFLET = ('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">'
           '<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js" defer></script>')

LEG_SVG = {
    'Swim': '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M2 16c2 0 2-1.5 4-1.5s2 1.5 4 1.5 2-1.5 4-1.5 2 1.5 4 1.5 2-1.5 4-1.5M2 20c2 0 2-1.5 4-1.5s2 1.5 4 1.5 2-1.5 4-1.5 2 1.5 4 1.5 2-1.5 4-1.5"/><circle cx="16" cy="6" r="2"/><path d="m5 12 5-4 3 3 3-2"/></svg>',
    'Bike': '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="5.5" cy="17.5" r="3.5"/><circle cx="18.5" cy="17.5" r="3.5"/><path d="M15 6a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM12 17.5V14l-3-3 4-3 2 3h2"/></svg>',
    'Run': '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13" cy="4" r="2"/><path d="m4 22 4-6 3 2 2-5 4 3h3M9 9l3-2 3 3-2 4"/></svg>',
}
LEG_TONE = {'Swim': 'sw', 'Bike': 'bk', 'Run': 'rn'}

CSS = r"""
.im{--im-closed:#E5564A;--im-delay:#E8A33D;--im-soon:#8A93A1}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .im{--im-closed:#FF8C82;--im-delay:#FFC36B;--im-soon:#768092}}
:root[data-theme="dark"] .im{--im-closed:#FF8C82;--im-delay:#FFC36B;--im-soon:#768092}
.im-warn{display:flex;gap:12px;align-items:center;background:var(--tint-amber);border-radius:16px;padding:12px 16px;font-size:.92rem}
.im-warn .ico{flex:none}
.im-live{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(280px,1fr);gap:16px;align-items:start}
.im-mapbox{position:relative;min-width:0;isolation:isolate}
.im-map{height:560px;border-radius:22px;box-shadow:var(--ui-shadow);overflow:hidden;background:var(--sunken);z-index:0}
:root[data-theme="dark"] .im-map .leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) brightness(.9) contrast(.9)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .im-map .leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) brightness(.9) contrast(.9)}}
.im-map .leaflet-popup-content{font:.85rem/1.45 var(--f-body);margin:10px 12px}
.im-map .leaflet-popup-content b{display:block;font-size:.92rem}
.im-map .leaflet-tooltip{font:600 .76rem var(--f-body);padding:3px 8px;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.2)}
.im-clock{position:absolute;right:12px;bottom:28px;z-index:500;background:var(--surface);border-radius:14px;padding:8px 12px;box-shadow:var(--ui-shadow);font-size:.8rem;line-height:1.3;pointer-events:none}
.im-clock b{display:block;font:600 1.05rem var(--f-data);font-variant-numeric:tabular-nums}
.im-clock span{color:var(--muted)}
.im-status{display:flex;flex-direction:column;gap:10px;min-width:0}
.im-st{display:grid;grid-template-columns:auto minmax(0,1fr);gap:3px 12px;padding:12px 14px;border-radius:16px;background:var(--surface);box-shadow:var(--ui-shadow);cursor:pointer;border:2px solid transparent;text-align:left;font:inherit;color:inherit;width:100%}
.im-st:hover,.im-st.hl{border-color:var(--line)}
.im-st:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.im-pill{grid-row:1/4;align-self:start;font:600 .7rem var(--f-data);letter-spacing:.05em;text-transform:uppercase;padding:4px 8px;border-radius:999px;min-width:76px;text-align:center}
.im-pill.closed{background:var(--im-closed);color:#fff}
.im-pill.delay{background:var(--im-delay);color:#1b1407}
.im-pill.soon{background:var(--sunken);color:var(--blue);box-shadow:inset 0 0 0 1px var(--line)}
.im-pill.open{background:var(--tint-teal);color:var(--teal)}
:root[data-theme="dark"] .im-pill.closed{color:#1b0d0b}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .im-pill.closed{color:#1b0d0b}}
.im-st b{font-size:.92rem;line-height:1.3}
.im-st small{color:var(--muted);font-size:.8rem;line-height:1.4}
.im-st small em{font-style:normal;font-family:var(--f-data);color:var(--ink)}
.im-key{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.82rem;color:var(--muted)}
.im-key i{display:inline-block;width:22px;height:5px;border-radius:3px;margin-right:6px;vertical-align:middle}
.im-ctl{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.im-btn{font:600 .84rem var(--f-body);border:0;border-radius:999px;padding:8px 14px;cursor:pointer;background:var(--surface);box-shadow:var(--ui-shadow);color:var(--ink);display:inline-flex;gap:7px;align-items:center}
.im-btn:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.im-btn.primary,.im-btn[aria-pressed="true"]{background:var(--navy);color:var(--on-navy)}
.im-dot{width:8px;height:8px;border-radius:50%;background:var(--salmon)}
.im-btn[aria-pressed="true"] .im-dot{animation:im-pulse 1.4s infinite}
@keyframes im-pulse{50%{opacity:.25}}
.im-gantt{display:grid;grid-template-columns:minmax(0,10rem) minmax(0,1fr);gap:7px 12px;align-items:center;font-size:.8rem}
.im-gantt .lab{color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.im-track{position:relative;height:14px;background:var(--surface);box-shadow:inset 0 0 0 1px var(--line);border-radius:7px}
.im-track span{position:absolute;top:0;bottom:0;border-radius:7px;min-width:4px}
.im-track .c{background:var(--im-closed)}.im-track .d{background:var(--im-delay)}
.im-head{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink);border-radius:1px;pointer-events:none}
.im-axis{position:relative;height:18px;font:500 .7rem var(--f-data);color:var(--faint)}
.im-axis span{position:absolute;transform:translateX(-50%);white-space:nowrap}
.im-axis span:first-child{transform:none}
.im-axis b{font-weight:500}
.im input[type=range]{width:100%;accent-color:var(--salmon);margin:0}
.im-sched{list-style:none;margin:0;padding:6px 20px;display:flex;flex-direction:column;background:var(--surface);border-radius:22px;box-shadow:var(--ui-shadow)}
.im-sched li{display:grid;grid-template-columns:7.5rem minmax(0,1fr);gap:14px;padding:12px 0;border-top:1px solid var(--line)}
.im-sched li:first-child{border-top:0}
.im-sched time{font:600 .82rem var(--f-data);color:var(--accent-ink);font-variant-numeric:tabular-nums}
.im-sched b{display:block;font-size:.93rem}
.im-sched span{font-size:.87rem;color:var(--muted)}
.im-sched li.now time{color:var(--teal)}
.im-legs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.im-leg{background:var(--surface);border-radius:22px;box-shadow:var(--ui-shadow);padding:18px 20px;display:flex;flex-direction:column;gap:8px;min-width:0}
.im-leg .k{font:600 1.7rem var(--f-data);line-height:1}
.im-leg .k small{font-size:.8rem;color:var(--muted);margin-left:5px;font-family:var(--f-body);font-weight:500}
.im-leg p{margin:0;font-size:.9rem;line-height:1.5}
.im-leg h3{margin:0;font-size:1rem}
.im-ic{width:38px;height:38px;border-radius:12px;display:grid;place-items:center}
.im-ic.sw{background:var(--tint-blue);color:var(--blue)}.im-ic.bk{background:var(--tint-amber);color:var(--gold)}.im-ic.rn{background:var(--tint-salmon);color:var(--salmon)}
.im-two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.im-card{background:var(--surface);border-radius:22px;box-shadow:var(--ui-shadow);padding:18px 20px;display:flex;flex-direction:column;gap:10px;min-width:0}
.im-card h3{margin:0;display:flex;gap:10px;align-items:center;font-size:1.02rem}
.im-card ul{margin:0;padding-left:1.1rem;display:flex;flex-direction:column;gap:7px;font-size:.92rem;line-height:1.5}
.im-adv{display:grid;grid-template-columns:minmax(0,280px) minmax(0,1fr);gap:22px;align-items:start;background:var(--surface);border-radius:22px;box-shadow:var(--ui-shadow);padding:16px}
.im-adv a{display:block;line-height:0}.im-adv img{display:block;width:100%;height:auto;aspect-ratio:1/1;object-fit:contain;border-radius:14px}
.im-adv p{margin:6px 0 0;line-height:1.6;overflow-wrap:anywhere}
@media (prefers-reduced-motion:reduce){.im-btn .im-dot{animation:none}}
@media (max-width:900px){.im-live{grid-template-columns:1fr}.im-legs{grid-template-columns:1fr}}
@media (max-width:760px){.im-map{height:400px;border-radius:18px}.im-clock{position:static;margin-top:10px;box-shadow:none;background:var(--sunken)}.im-axis b{display:none}.im-two{grid-template-columns:1fr}.im-adv{grid-template-columns:1fr}.im-adv img{max-width:360px;margin:0 auto}
  .im-gantt{grid-template-columns:minmax(0,6.8rem) minmax(0,1fr)}.im-sched li{grid-template-columns:5.8rem minmax(0,1fr)}.im-sched{padding:4px 16px}}
"""

JS = r"""
(() => {
  const $ = id => document.getElementById(id);
  const D = JSON.parse($('imData').textContent);
  const T = s => Date.parse(s);
  const C = D.closures.map(c => ({...c, a: T(c.starts_at), b: T(c.ends_at)}));
  const START = T(D.starts_at), END = T(D.ends_at);
  const PH = D.phases.map(([t, s]) => [T(t), s]);
  const fmt = (t, o) => new Date(t).toLocaleString('en-US', {timeZone: 'America/Chicago', ...o});
  const when = t => fmt(t, {weekday: 'short', month: 'short', day: 'numeric'}) + ', ' + fmt(t, {hour: 'numeric', minute: '2-digit'});
  const left = ms => { const h = Math.round(ms / 36e5); return h >= 48 ? Math.round(h / 24) + ' days' : h >= 1 ? h + ' h' : Math.max(1, Math.round(ms / 6e4)) + ' min'; };
  const pct = t => ((t - START) / (END - START) * 100).toFixed(2) + '%';
  const css = n => getComputedStyle($('imPage')).getPropertyValue(n).trim();

  // timeline rows
  const days = []; for (let t = START; t <= END; t += 864e5) days.push(t);
  $('imGantt').innerHTML = C.map(c => `<span class="lab">${c.road}</span><div class="im-track"><span class="${c.kind === 'delay' ? 'd' : 'c'}" style="left:${pct(c.a)};width:calc(${pct(c.b)} - ${pct(c.a)})"></span><i class="im-head"></i></div>`).join('')
    + `<span class="lab">Time</span><div><input type="range" id="imSlider" min="${START}" max="${END}" step="900000" aria-label="Time during race week"></div>`
    + `<span></span><div class="im-axis">${days.map(t => `<span style="left:${pct(t)}"><b>${fmt(t, {weekday: 'short'})} </b>${fmt(t, {day: 'numeric'})}</span>`).join('')}</div>`;

  let map = null, lines = {};
  function setupMap() {
    if (!window.L || map) return;
    map = L.map('imMap', {scrollWheelZoom: false});
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      {maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
    const all = [];
    for (const c of C) {
      if (!c.line) continue;
      const ll = c.line.map(([x, y]) => [y, x]); all.push(...ll);
      lines[c.closure_id] = L.polyline(ll, {weight: 8, lineCap: 'round', lineJoin: 'round'}).addTo(map)
        .bindPopup(`<b>${c.road}</b>${c.limits}<br>${c.kind === 'delay' ? 'Delays' : 'Closed'} ${when(c.a)} to ${when(c.b)}`);
    }
    for (const p of D.points) {
      L.circleMarker([p.lat, p.lon], {radius: 7, color: '#fff', weight: 2, fillColor: css(p.c) || '#3F6FB0', fillOpacity: 1})
        .addTo(map).bindTooltip(p.title, {permanent: true, direction: p.dir || 'right', offset: [8, 0], className: 'im-tip'}).bindPopup(`<b>${p.title}</b>${p.text}`);
    }
    if (all.length) map.fitBounds(all, {padding: [28, 28]});
    draw(now);
  }

  let now = T(D.race_morning);
  function draw(t) {
    now = t;
    $('imSlider').value = t;
    document.querySelectorAll('.im-head').forEach(h => h.style.left = pct(t));
    $('imDay').textContent = fmt(t, {weekday: 'long', month: 'short', day: 'numeric'});
    $('imTime').textContent = fmt(t, {hour: 'numeric', minute: '2-digit'});
    const ph = PH.filter(p => p[0] <= t).pop();
    $('imPhase').textContent = ph ? ph[1] : 'Before race week';
    for (const c of C) {
      const on = t >= c.a && t < c.b, soon = t < c.a, p = $('imP-' + c.closure_id);
      p.className = 'im-pill ' + (on ? (c.kind === 'delay' ? 'delay' : 'closed') : soon ? 'soon' : 'open');
      p.textContent = on ? (c.kind === 'delay' ? 'Delays' : 'Closed') : soon ? 'Upcoming' : 'Open';
      $('imW-' + c.closure_id).innerHTML = on ? `Until <em>${when(c.b)}</em> · ${left(c.b - t)} left`
        : soon ? `${c.kind === 'delay' ? 'Delays' : 'Closes'} <em>${when(c.a)}</em> · in ${left(c.a - t)}` : `Reopened <em>${when(c.b)}</em>`;
      const l = lines[c.closure_id];
      if (l) l.setStyle({color: on ? css(c.kind === 'delay' ? '--im-delay' : '--im-closed') : css('--im-soon'),
        opacity: on ? 1 : soon ? .55 : .25, dashArray: on && c.kind === 'delay' ? '12 8' : soon ? '2 12' : null});
    }
  }
  document.querySelectorAll('.im-st').forEach(s => {
    const id = s.dataset.id, hl = v => { s.classList.toggle('hl', v); const l = lines[id]; if (l) l.setStyle({weight: v ? 13 : 8}); };
    s.addEventListener('mouseenter', () => hl(true)); s.addEventListener('mouseleave', () => hl(false));
    s.addEventListener('focus', () => hl(true)); s.addEventListener('blur', () => hl(false));
    s.addEventListener('click', () => { const l = lines[id]; if (l && map) { map.fitBounds(l.getBounds(), {padding: [60, 60], maxZoom: 17}); l.openPopup(); } });
  });
  let live = false, timer = null, play = null;
  const stopPlay = () => { if (play) { cancelAnimationFrame(play); play = null; $('imPlay').textContent = '▶ Play race day'; } };
  const setLive = v => {
    live = v; $('imLive').setAttribute('aria-pressed', String(v)); clearInterval(timer);
    if (v) { stopPlay(); const tick = () => draw(Math.min(END, Math.max(START, Date.now()))); tick(); timer = setInterval(tick, 30000); }
  };
  $('imSlider').addEventListener('input', ev => { setLive(false); stopPlay(); draw(+ev.target.value); });
  $('imLive').addEventListener('click', () => setLive(!live));
  $('imJumps').addEventListener('click', ev => { const b = ev.target.closest('[data-t]'); if (!b) return; setLive(false); stopPlay(); draw(T(b.dataset.t)); });
  $('imPlay').addEventListener('click', () => {
    if (play) return stopPlay();
    setLive(false);
    const a = T(D.play[0]), b = T(D.play[1]), slow = matchMedia('(prefers-reduced-motion:reduce)').matches ? 3 : 1;
    let t = now >= a && now < b ? now : a, last = performance.now();
    $('imPlay').textContent = '❚❚ Pause';
    const step = ts => { t += (ts - last) * 9000 / slow; last = ts; if (t >= b) { draw(b); return stopPlay(); } draw(t); play = requestAnimationFrame(step); };
    play = requestAnimationFrame(step);
  });
  // follow the clock during race week; otherwise open on race morning
  if (Date.now() >= START && Date.now() <= END) setLive(true); else draw(now);
  addEventListener('load', setupMap);
  if (document.readyState === 'complete') setupMap();
})();
"""


def ironman_page(out_dir=None):
    from special_events import event, event_guide, event_road_closures
    ev = event(EVENT_ID)
    if not ev:
        return '<div class="page"><h1>IRONMAN Florida</h1><p>No race information on file yet.</p></div>'
    R = [r for r in event_road_closures() if r['event_id'] == EVENT_ID]
    G = [g for g in event_guide() if g['event_id'] == EVENT_ID]
    sec = lambda s: [g for g in G if g['section'] == s]

    closures = [{'closure_id': r['closure_id'], 'road': r['road'], 'limits': r['limits'], 'kind': r['kind'], 'starts_at': r['starts_at'],
                 'ends_at': r['ends_at'], 'line': json.loads(r['geometry'])['coordinates'] if r['geometry'] else None} for r in R]
    tone = {'Swim start at Russell-Fields Pier': '--blue', 'Sunrise swim start': '--blue', 'IRONMAN Village': '--teal', 'The finish at Pier Park': '--navy'}
    label = {'Sunrise swim start': 'Swim start', 'The finish at Pier Park': 'Finish', 'IRONMAN Village': 'IRONMAN Village'}
    points, seen = [], set()
    for g in sec('watch'):
        if g['lat'] is not None and (g['lat'], g['lon']) not in seen:
            seen.add((g['lat'], g['lon']))
            points.append({'lat': g['lat'], 'lon': g['lon'], 'title': label.get(g['title'], g['title']), 'text': g['text'],
                           'c': tone.get(g['title'], '--blue'), 'dir': 'left' if g['title'] == 'IRONMAN Village' else 'right'})
    data = {'starts_at': ev['starts_at'], 'ends_at': ev['ends_at'], 'race_morning': '2026-11-07T07:30:00-06:00',
            'play': ['2026-11-07T00:00:00-06:00', '2026-11-08T13:00:00-06:00'], 'closures': closures, 'points': points,
            'phases': [['2026-11-01T06:00:00-06:00', 'Finish area and Village setup'], ['2026-11-06T06:00:00-06:00', 'Practice swim day'],
                       ['2026-11-07T02:00:00-06:00', 'Roads closing for race day'], ['2026-11-07T06:00:00-06:00', 'Swim under way'],
                       ['2026-11-07T07:15:00-06:00', 'Athletes on the bike'], ['2026-11-07T11:00:00-06:00', 'Bike and run on course'],
                       ['2026-11-07T15:00:00-06:00', 'Runners on Front Beach Road'], ['2026-11-07T19:00:00-06:00', 'Finish line under the lights'],
                       ['2026-11-08T00:00:00-06:00', 'Race over, crews clearing'], ['2026-11-08T04:00:00-06:00', 'Front Beach Road open'],
                       ['2026-11-08T12:00:00-06:00', 'All roads open']]}

    status = ''.join(f'''<button type="button" class="im-st" data-id="{e(r["closure_id"])}"><span class="im-pill" id="imP-{e(r["closure_id"])}"></span>
      <b>{e(r["road"])}</b><small>{e(r["limits"])}</small><small id="imW-{e(r["closure_id"])}"></small></button>''' for r in R)
    sched = ''.join(f'<li><time>{e(g["when_text"])}</time><div><b>{e(g["title"])}</b><span>{e(g["text"])}</span></div></li>' for g in sec('schedule'))
    legs = ''.join(f'''<div class="im-leg"><span class="im-ic {LEG_TONE.get(g["title"], "sw")}">{LEG_SVG.get(g["title"], "")}</span>
      <div class="k">{g["distance_miles"]:g}<small>mi {e(g["title"].lower())}</small></div><p>{e(g["text"])}</p></div>''' for g in sec('course'))
    total = sum(g['distance_miles'] or 0 for g in sec('course'))
    li = lambda rows: ''.join(f'<li><b>{e(g["title"])}.</b> {e(g["text"])}</li>' for g in rows)
    stay = ''.join(f'''<div class="im-leg"><h3>{e(g["title"])}</h3><p>{e(g["text"])}</p>{f'<a href="{e(g["link"])}">Open →</a>' if g["link"] else ""}</div>''' for g in sec('stay'))
    adv = ev['closure_source_url']

    return f'''<style>{CSS}</style>{LEAFLET}
<div class="page tax im" id="imPage">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Events · Panama City Beach</span><h1>IRONMAN Florida race week</h1>
    <p class="lede">Thousands of athletes swim, bike and run {total:g} miles through Panama City Beach on Saturday, November 7. See which roads are closed right now, play through race day hour by hour, and find the best places to watch.</p></div>
    <div class="stamp"><a class="pill" href="#map">Road closures →</a><a class="pill" href="/events">All events →</a><span>Race day is Saturday, November 7, 2026. Times are Central.</span></div></header>

  <div class="im-warn">{ico("megaphone")}<span><b>Plan ahead and allow extra travel time.</b> Expect heavy event traffic near Pier Park all week. Use Panama City Beach Parkway (US 98) to get around Front Beach Road on race day.</span></div>

  <section class="tx-sec"><div class="sec-hd"><h2 id="map" data-tile="Road closures">Road closures, hour by hour</h2><span class="muted">From the Panama City Beach Police Department</span></div>
    <div class="im-live">
      <div class="im-mapbox"><div class="im-map" id="imMap" role="region" aria-label="Map of road closures around Pier Park; the list beside it has every closure and its status"></div>
        <div class="im-clock" aria-live="polite"><span id="imDay"></span><b id="imTime"></b><span id="imPhase"></span></div></div>
      <div class="im-status">{status}</div>
    </div>
    <div class="im-key"><span><i style="background:var(--im-closed)"></i>Closed</span><span><i style="background:var(--im-delay)"></i>Bike course delays</span><span><i style="background:var(--im-soon);opacity:.6"></i>Open now, closes later</span></div>
    <div class="im-ctl">
      <button class="im-btn" id="imLive" type="button" aria-pressed="false"><span class="im-dot"></span>Live</button>
      <button class="im-btn primary" id="imPlay" type="button">▶ Play race day</button>
      <div class="chips" id="imJumps" role="group" aria-label="Jump to">
        <button class="chip" type="button" data-t="2026-11-01T06:00:00-06:00">Nov 1, closures begin</button>
        <button class="chip" type="button" data-t="2026-11-07T02:00:00-06:00">Race day, 2 AM</button>
        <button class="chip" type="button" data-t="2026-11-07T07:30:00-06:00">Bike out, 7:30 AM</button>
        <button class="chip" type="button" data-t="2026-11-07T21:00:00-06:00">Finish line, 9 PM</button>
        <button class="chip" type="button" data-t="2026-11-08T12:00:00-06:00">All open, Sun noon</button>
      </div>
    </div>
    <div class="im-gantt" id="imGantt"></div>
    <p class="note">Lines are placed on the county street map from the street names, between the cross streets the police named. Tap a road in the list to zoom to it.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="schedule" data-tile="Schedule">Race week schedule</h2><span class="muted">Central time</span></div>
    <ol class="im-sched">{sched}</ol></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="course" data-tile="Course">The course</h2><span class="muted">{total:g} miles from the Gulf to Pier Park</span></div>
    <div class="im-legs">{legs}</div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="watch" data-tile="Where to watch">Where to watch and getting around</h2></div>
    <div class="im-two">
      <div class="im-card"><h3>{ico("pin", "teal")}Where to watch</h3><ul>{li(sec("watch"))}</ul></div>
      <div class="im-card"><h3>{ico("map", "amber")}Getting around</h3><ul>{li(sec("getting-around"))}</ul></div>
    </div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="stay" data-tile="Make a week of it">Make a week of it</h2><span class="muted">Things to do in Bay County while you're here</span></div>
    <div class="im-legs">{stay}</div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="advisory" data-tile="Advisory">The police advisory</h2></div>
    <div class="im-adv"><a href="{e(adv)}" target="_blank" rel="noopener"><img src="{e(adv)}" alt="Panama City Beach Police Department IRONMAN road closures traffic advisory for Saturday, November 7, 2026" loading="lazy" width="1000" height="1000"></a>
      <p>The closures on this page come from the Panama City Beach Police Department's traffic advisory. Tap the image to see it full size. Call 911 in an emergency; for anything else on race day, follow the officers directing traffic.</p></div></section>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>Road closures and times:</b> {e(ev["closure_source"])}.</li>
      <li><b>Map lines:</b> Bay County street centerlines, between the cross streets the advisory names. The map is from OpenStreetMap.</li>
      <li><b>Race details:</b> <a href="{e(ev["guide_source_url"])}" target="_blank" rel="noopener">{e(ev["guide_source"])}</a>. The athlete guide on the IRONMAN Florida race page has exact start and cutoff times.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/event-road-closures">event-road-closures</a> · <a href="/api/v1/datasets/event-guide">event-guide</a> (CSV on <a href="/open-data">Open data</a>).</li>
    </ul></section>
</div>
<script type="application/json" id="imData">{json.dumps(data, separators=(",", ":"))}</script>
<link rel="stylesheet" href="/assets/tax.css">
<script>{JS}</script>'''
