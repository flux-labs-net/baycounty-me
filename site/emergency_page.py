"""Emergencies and alerts (/emergency): what is happening now (weather warnings, evacuation orders, open shelters,
boil-water notices, road closures), the evacuation zone for any address, every county shelter, the zone map, and how to
get alerts.

Built from the evacuation-zones, emergency-shelters, emergency-resources and emergency-notices datasets
(site/page_datasets.py, from data/emergency/<county>/). The live part reads /api/v1/emergency (checked every 5 minutes by
api/emergency-run.js) and /api/v1/evacuation-zone; the server-rendered notices are the last daily snapshot, so the page
still says something useful without JavaScript.
"""
import datetime as dt
import html
import json

from entity_links import gov as gov_link
from ui import ico

e = lambda s: html.escape(str(s if s is not None else ''))
KIND = {'evacuation': ('Evacuation order', 'flag', 'salmon'), 'weather': ('Weather', 'storm', 'blue'), 'shelter': ('Shelter open', 'home', 'teal'),
        'boil-water': ('Boil-water notice', 'drop', 'amber'), 'road': ('Road closure', 'pin', 'amber'), 'utility': ('Water or utility', 'drop', 'blue'),
        'storm': ('Storm update', 'megaphone', 'teal')}
TYPE = {'special-needs': 'Special needs', 'general': 'General population', 'mass-care': 'Mass care support', 'recovery': 'After the storm',
        'extreme-weather': 'Overflow and extreme weather', 'pet-friendly': 'Pet friendly', 'other': 'Shelter'}

CSS = r"""
.em{--sev-extreme:#c0392b;--sev-severe:#d35400;--sev-moderate:#b7791f;--sev-minor:var(--blue);--sev-info:var(--muted)}
.em-status{display:flex;gap:16px;align-items:flex-start;padding:20px 22px;border-radius:24px;background:var(--surface);box-shadow:var(--ui-shadow);border-left:6px solid var(--teal)}
.em-status[data-sev=extreme]{border-left-color:var(--sev-extreme)}.em-status[data-sev=severe]{border-left-color:var(--sev-severe)}.em-status[data-sev=moderate]{border-left-color:var(--sev-moderate)}
.em-status .ui-ti{flex:none}
.em-status h2{font-size:1.25rem;margin:0;line-height:1.3;text-wrap:balance}
.em-status p{margin:4px 0 0;color:var(--muted);font-size:.88rem}
.em-kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}
.em-kpi{display:flex;flex-direction:column;gap:2px;padding:14px 16px;border-radius:18px;background:var(--surface);box-shadow:var(--ui-shadow);text-decoration:none;color:inherit;min-width:0}
.em-kpi b{font:600 1.6rem var(--f-data);font-variant-numeric:tabular-nums;line-height:1.1}
.em-kpi span{font-size:.8rem;color:var(--muted)}
.em-kpi.on b{color:var(--sev-moderate)}.em-kpi.on.hot b{color:var(--sev-extreme)}
.em-zone{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:14px}
.em-form{display:flex;gap:8px;flex-wrap:wrap}
.em-form input{flex:1 1 220px;min-height:46px;padding:0 14px;border:1px solid var(--line);border-radius:14px;background:var(--surface);color:var(--ink);font:500 1rem var(--f-body)}
.em-form button{min-height:46px}
.em-result{padding:18px 20px;border-radius:20px;background:var(--surface);box-shadow:var(--ui-shadow);min-height:120px}
.em-result .z{display:inline-flex;align-items:center;justify-content:center;width:56px;height:56px;border-radius:16px;font:700 1.7rem var(--f-display);color:#fff;margin-right:12px;flex:none}
.em-result .zh{display:flex;align-items:center}
.em-result h3{margin:0;font-size:1.1rem}
.em-result p{margin:8px 0 0;font-size:.92rem;line-height:1.5}
.em-result ul{margin:8px 0 0;padding-left:18px;font-size:.88rem}
.em-ctl{display:flex;flex-wrap:wrap;gap:8px}
.em-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.em-n{display:flex;flex-direction:column;gap:6px;padding:16px 18px;border-radius:20px;background:var(--surface);box-shadow:var(--ui-shadow);border-top:4px solid var(--sev-info);min-width:0;scroll-margin-top:90px}
.em-n[data-sev=extreme]{border-top-color:var(--sev-extreme)}.em-n[data-sev=severe]{border-top-color:var(--sev-severe)}.em-n[data-sev=moderate]{border-top-color:var(--sev-moderate)}.em-n[data-sev=minor]{border-top-color:var(--sev-minor)}
.em-n .k{display:flex;gap:8px;align-items:center;font-size:.76rem;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.em-n h3{font-size:1rem;margin:0;line-height:1.35;overflow-wrap:anywhere}
.em-n p{margin:0;font-size:.88rem;line-height:1.5;overflow-wrap:anywhere}
.em-n small{color:var(--muted);font-size:.8rem}
.em-n details summary{cursor:pointer;font-size:.84rem;color:var(--blue)}
.em-n details p{margin-top:6px;white-space:pre-line}
.em-n .em-upd{font-weight:600;color:var(--ink)}.em-n details p.em-ver{font-size:.8rem;color:var(--muted);white-space:normal}
.em-n[hidden],.em-sh[hidden]{display:none!important}
.em-empty{padding:18px;border-radius:18px;background:var(--sunken);color:var(--muted);font-size:.92rem}
.em-shg{display:flex;flex-direction:column;gap:10px}
.em-shs{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}
.em-sh{display:flex;flex-direction:column;gap:4px;padding:14px 16px;border-radius:18px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.em-sh b{font-size:.95rem;font-weight:600}
.em-sh small{color:var(--muted);font-size:.82rem;line-height:1.4}
.em-pill{align-self:flex-start;font-size:.72rem;font-weight:700;padding:2px 10px;border-radius:999px;background:var(--sunken);color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.em-pill.open{background:color-mix(in srgb,var(--teal) 18%,transparent);color:var(--teal)}
.em-map{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:16px;align-items:start}
.em-map svg{width:100%;height:auto;border-radius:20px;background:var(--sunken)}
.em-map svg .sea{fill:color-mix(in srgb,var(--blue) 12%,var(--sunken))}
.em-map svg .land{fill:var(--surface)}
.em-map svg .county{fill:none;stroke:var(--muted);stroke-width:1;stroke-dasharray:4 3}
.em-map svg .zn{stroke:var(--surface);stroke-width:.6;fill-opacity:.78}
.em-map svg .sh{fill:var(--ink);stroke:var(--surface);stroke-width:1.5}
.em-zl{display:flex;flex-direction:column;gap:10px}
.em-zc{display:flex;gap:12px;padding:12px 14px;border-radius:16px;background:var(--surface);box-shadow:var(--ui-shadow)}
.em-zc .z{flex:none;width:38px;height:38px;border-radius:12px;display:flex;align-items:center;justify-content:center;color:#fff;font:700 1.1rem var(--f-display)}
.em-zc b{display:block;font-size:.92rem}
.em-zc small{display:block;color:var(--muted);font-size:.82rem;line-height:1.4}
.em-zc.ordered{box-shadow:0 0 0 2px var(--sev-extreme)}
.em-get{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.em-get a,.em-get div{display:flex;flex-direction:column;gap:4px;padding:16px;border-radius:18px;background:var(--surface);box-shadow:var(--ui-shadow);text-decoration:none;color:inherit}
.em-get b{font-size:.95rem}
.em-get small{color:var(--muted);font-size:.84rem;line-height:1.45}
.em-res{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px}
.em-r{padding:12px 14px;border-radius:16px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.em-r b{display:block;font-size:.92rem}
.em-r b a{color:inherit}
.em-r .ph{font:600 .95rem var(--f-data);color:var(--blue);text-decoration:none}
.em-r small{display:block;color:var(--muted);font-size:.82rem;line-height:1.4;margin-top:2px}
.em-tbl td{vertical-align:top}
.em-tbl td.d{white-space:nowrap;font-variant-numeric:tabular-nums}
@media (max-width:860px){.em-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}.em-zone,.em-map{grid-template-columns:1fr}}
@media (max-width:520px){.em-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.em-status{padding:16px}.em-status h2{font-size:1.08rem}.em-list{grid-template-columns:1fr}}
"""

JS = r"""
(() => {
  const $ = id => document.getElementById(id), esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'})[c]);
  const KIND = JSON.parse($('emKinds').textContent), ZC = JSON.parse($('emZoneColors').textContent);
  const govA = (id, text) => id && window.BC && BC.href && BC.href('gov:' + id) ? BC.a('gov:' + id, text) : esc(text);
  const when = s => { if (!s) return ''; const d = new Date(/T\d\d:\d\d$/.test(s) ? s : s); if (isNaN(d)) return ''; return d.toLocaleString('en-US', {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago'}); };
  const ago = s => { const m = Math.round((Date.now() - Date.parse(s)) / 60000); return m < 1 ? 'just now' : m < 60 ? m + ' min ago' : Math.round(m / 60) + ' hr ago'; };
  let kind = '';
  const earlier = n => (n.versions || []).length > 1 ? `<p class="em-ver">Earlier version${n.versions.length > 2 ? 's' : ''}: ${n.versions.slice(1).map(v =>
    `${v.url ? `<a href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.title)}</a>` : esc(v.title)} (${esc(when(v.issued))})`).join('; ')}</p>` : '';
  function card(n) {
    const k = KIND[n.kind] || ['Notice', 'info'];
    const src = n.gov_id ? govA(n.gov_id, n.source) : esc(n.source);
    // A notice posted again with changes is one card: the newest text, with when it was first posted and updated.
    const upd = n.first_posted && n.issued && n.first_posted < n.issued;
    const times = [n.issued && (upd ? `Posted ${when(n.first_posted)} · <b class="em-upd">Updated ${when(n.issued)}</b>` : 'Posted ' + when(n.issued)), n.ends && (n.kind === 'weather' ? 'until ' + when(n.ends) : '')].filter(Boolean).join(' · ');
    const more = [n.summary && n.summary !== n.title ? n.summary : '', n.instruction || ''].filter(Boolean).join('\n\n');
    return `<article class="em-n" id="n-${esc(n.notice_id)}" data-k="${esc(n.kind)}" data-sev="${esc(n.severity)}">
      <span class="k"><span class="ico i-${k[1]}" aria-hidden="true"></span>${esc(n.kind === 'weather' && n.event ? n.event : k[0])}${n.zones ? ' · Zone' + (n.zones.includes(',') ? 's ' : ' ') + esc(n.zones) : ''}</span>
      <h3>${esc(n.title)}</h3>${n.area ? `<p>${esc(n.area.length > 220 ? n.area.slice(0, 217) + '…' : n.area)}</p>` : ''}
      ${more ? `<details><summary>Details</summary><p>${esc(more.length > 1600 ? more.slice(0, 1597) + '…' : more)}</p>${earlier(n)}</details>` : ''}
      <small>${src}${times ? ' · ' + times : ''}${n.url ? ` · <a href="${esc(n.url)}" target="_blank" rel="noopener">Source</a>` : ''}</small></article>`;
  }
  function filter() {
    let shown = 0;
    document.querySelectorAll('#emList .em-n').forEach(c => { const on = !kind || c.dataset.k === kind; c.hidden = !on; if (on) shown++; });
    $('emNone').hidden = shown > 0;
  }
  $('emKind').addEventListener('click', ev => {
    const b = ev.target.closest('.chip'); if (!b) return;
    kind = b.dataset.v; $('emKind').querySelectorAll('.chip').forEach(x => x.setAttribute('aria-pressed', x === b ? 'true' : 'false')); filter();
  });
  function render(d) {
    const worst = (d.notices[0] || {}).severity || 'info';
    const st = $('emStatus'); st.dataset.sev = d.counts.evacuation ? 'extreme' : ['extreme', 'severe'].includes(worst) && d.counts.weather ? worst : d.notices.length ? 'moderate' : 'info';
    $('emHead').textContent = d.headline;
    const bits = [d.counts['boil-water'] && `${d.counts['boil-water']} boil-water notice${d.counts['boil-water'] > 1 ? 's' : ''}`, d.counts.road && `${d.counts.road} road closure${d.counts.road > 1 ? 's' : ''}`,
      d.shelters_open && `${d.shelters_open} shelter${d.shelters_open > 1 ? 's' : ''} open`].filter(Boolean);
    $('emSub').textContent = (bits.length ? bits.join(' · ') + '. ' : '') + 'Checked ' + ago(d.checked_at) + '.';
    const set = (id, v) => { const el = $(id); if (!el) return; el.querySelector('b').textContent = v; el.classList.toggle('on', v > 0); };
    set('kWeather', d.counts.weather); set('kEvac', d.counts.evacuation); set('kShelter', d.shelters_open); set('kWater', d.counts['boil-water']); set('kRoad', d.counts.road);
    $('kEvac').classList.toggle('hot', d.counts.evacuation > 0);
    $('emList').innerHTML = d.notices.map(card).join('');
    filter();
    const st2 = new Map(d.shelters.map(s => [s.shelter_id, s]));
    document.querySelectorAll('.em-sh[data-id]').forEach(el => { const s = st2.get(el.dataset.id); if (!s) return; const p = el.querySelector('.em-pill'); p.textContent = s.status; p.classList.toggle('open', s.status === 'open'); });
    (d.zones || []).forEach(z => { const el = document.querySelector(`.em-zc[data-z="${z.zone}"]`); if (el) el.classList.toggle('ordered', !!z.ordered); });
    if (location.hash.startsWith('#n-')) { const t = document.getElementById(decodeURIComponent(location.hash.slice(1))); if (t) t.scrollIntoView(); }
  }
  const load = () => fetch('/api/v1/emergency').then(r => r.ok ? r.json() : Promise.reject(r.status)).then(render)
    .catch(() => { $('emSub').textContent = "Couldn't reach the live feed. The list below is from the last daily check."; });
  load(); setInterval(() => { if (!document.hidden) load(); }, 5 * 60e3);

  // ---- evacuation zone lookup
  const out = $('emZoneOut');
  function zoneHtml(r) {
    if (!r.found) return `<p>${esc(r.message)}</p>`;
    const z = r.zone, c = ZC[z] || '#777';
    const orders = (r.orders_now || []).map(o => `<li>${o.includes_you ? '<b>Includes your zone:</b> ' : ''}${esc(o.title)}</li>`).join('');
    const sh = (r.nearest_shelters || []).map(s => `<li>${esc(s.name)}, ${esc(s.address)} <span class="muted">(${s.miles} mi, ${esc(s.status)})</span></li>`).join('');
    return `<div class="zh">${z ? `<span class="z" style="background:${c}">${esc(z)}</span>` : `<span class="z" style="background:var(--muted)">–</span>`}
      <div><h3>${z ? 'Evacuation Zone ' + esc(z) : 'Not in an evacuation zone'}</h3><small class="muted">${esc(r.address ? r.address.address + (r.address.community ? ', ' + r.address.community : '') : r.query)}</small></div></div>
      <p>${esc(r.what_to_do)}</p>${orders ? `<p><b>Orders in effect now</b></p><ul>${orders}</ul>` : '<p class="muted">No evacuation order is in effect right now.</p>'}
      ${sh ? `<p><b>Nearest county shelters</b> (open only when the county opens them)</p><ul>${sh}</ul>` : ''}`;
  }
  async function lookup(params) {
    out.innerHTML = '<p class="muted">Looking up…</p>';
    try {
      const r = await fetch('/api/v1/evacuation-zone?' + new URLSearchParams(params)).then(x => x.json());
      out.innerHTML = r.error ? `<p>${esc(r.error)}</p>` : zoneHtml(r);
      if (params.address) { try { localStorage.setItem('bc.emAddr', params.address); } catch (e) {} const u = new URL(location.href); u.searchParams.set('a', params.address); history.replaceState(null, '', u); }
    } catch (e) { out.innerHTML = "<p>Couldn't look that up. Try again, or use the county's map below.</p>"; }
  }
  $('emZoneForm').addEventListener('submit', ev => { ev.preventDefault(); const a = $('emAddr').value.trim(); if (a) lookup({address: a}); });
  $('emLoc').addEventListener('click', () => {
    if (!navigator.geolocation) { out.innerHTML = '<p>Your browser can\'t share a location. Type your address instead.</p>'; return; }
    out.innerHTML = '<p class="muted">Finding you…</p>';
    navigator.geolocation.getCurrentPosition(p => lookup({lat: p.coords.latitude.toFixed(5), lng: p.coords.longitude.toFixed(5)}), () => { out.innerHTML = '<p>Location was not shared. Type your address instead.</p>'; }, {timeout: 10000});
  });
  let start = new URLSearchParams(location.search).get('a');
  if (!start) { try { start = localStorage.getItem('bc.emAddr'); } catch (e) {} }
  if (start) { $('emAddr').value = start; lookup({address: start}); }
})();
"""


def _when(s):
    if not s:
        return ''
    try:
        d = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except ValueError:
        return e(s)
    if d.tzinfo:
        d = d.astimezone(dt.timezone(dt.timedelta(hours=-5 if 3 <= d.month <= 10 else -6)))  # Central time, near enough for a date line
    return d.strftime('%b %-d, %Y')


def _when_t(s):
    """'Oct 23, 9:35 AM' in Central time (the date alone when there's no time)."""
    try:
        d = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except ValueError:
        return e(s)
    if 'T' not in str(s):
        return d.strftime('%b %-d, %Y')
    if d.tzinfo:
        d = d.astimezone(dt.timezone(dt.timedelta(hours=-5 if 3 <= d.month <= 10 else -6)))
    return d.strftime('%b %-d, %-I:%M %p')


def _posted(n):
    """'Posted Oct 23, 2026', or 'Posted Oct 22, 2026 · Updated Oct 23, 2026' for a notice that was posted again."""
    first = n.get('first_posted')
    if first and str(first) < str(n.get('issued') or ''):
        return f'Posted {_when_t(first)} · <b class="em-upd">Updated {_when_t(n.get("issued"))}</b>'
    return f'Posted {_when(n.get("issued"))}'


def _earlier(n):
    vs = sorted(n.get('earlier') or [], key=lambda v: str(v.get('issued') or ''), reverse=True)
    if not vs:
        return ''
    link = lambda v: f'<a href="{e(v["url"])}" target="_blank" rel="noopener">{e(v["title"])}</a>' if v.get('url') else e(v['title'])
    return f'<p class="em-ver">Earlier version{"s" if len(vs) > 1 else ""}: ' + '; '.join(f'{link(v)} ({_when(v.get("issued"))})' for v in vs) + '</p>'


def _notice(n):
    lab, icon, _ = KIND.get(n['kind'], ('Notice', 'info', 'blue'))
    src = gov_link(n['gov_id'], n['source']) if n.get('gov_id') else e(n['source'])
    more = '\n\n'.join(x for x in [n.get('summary') if n.get('summary') != n['title'] else '', n.get('instruction') or ''] if x)
    return (f'<article class="em-n" id="n-{e(n["notice_id"])}" data-k="{e(n["kind"])}" data-sev="{e(n["severity"])}">'
            f'<span class="k">{ico(icon)}{e(n["event"] if n["kind"] == "weather" and n.get("event") else lab)}</span><h3>{e(n["title"])}</h3>'
            + (f'<details><summary>Details</summary><p>{e(more[:1600])}</p>{_earlier(n)}</details>' if more else '')
            + f'<small>{src} · {_posted(n)}' + (f' · <a href="{e(n["url"])}" target="_blank" rel="noopener">Source</a>' if n.get('url') else '') + '</small></article>')


def _project(zones, base, shelters, w=640):
    """Zone shapes clipped to land, with water, the county line and shelter points, as SVG (equirectangular, scaled for
    latitude). The view is the zones' extent plus a margin."""
    import math
    geoms = [json.loads(z['geometry']) for z in zones if z.get('geometry')]
    polys = lambda g: [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
    pts = [p for g in geoms for poly in polys(g) for r in poly for p in r] + [(s['lng'], s['lat']) for s in shelters if s.get('lat')]
    x0, x1 = min(p[0] for p in pts) - .03, max(p[0] for p in pts) + .03
    y0, y1 = min(p[1] for p in pts) - .03, max(p[1] for p in pts) + .03
    k = math.cos(math.radians((y0 + y1) / 2))
    sx = w / ((x1 - x0) * k)
    h = round((y1 - y0) * sx)
    X = lambda p: (p[0] - x0) * k * sx
    Y = lambda p: (y1 - p[1]) * sx
    ring = lambda r: 'M' + 'L'.join(f'{X(p):.1f},{Y(p):.1f}' for p in r) + 'Z'
    multi = lambda mp: ''.join(ring(r) for poly in mp for r in poly)
    land = multi(base['land'])
    county = multi(base['county'])
    zp = ''.join(f'<path class="zn" fill="{z["color"]}" fill-rule="evenodd" d="{multi(polys(json.loads(z["geometry"])))}"><title>Zone {e(z["zone"])}</title></path>'
                 for z in sorted(zones, key=lambda z: -z['sort_order']) if z.get('geometry'))
    sp = ''.join(f'<circle class="sh" r="5" cx="{X((s["lng"], s["lat"])):.1f}" cy="{Y((s["lng"], s["lat"])):.1f}"><title>{e(s["name"])}</title></circle>'
                 for s in shelters if s.get('lat') and s.get('lng'))
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Map of Bay County evacuation zones A to D, with county shelters as dots">'
            f'<defs><clipPath id="emLand"><path d="{land}"/></clipPath></defs><rect class="sea" width="{w}" height="{h}"/>'
            f'<path class="land" d="{land}"/><g clip-path="url(#emLand)">{zp}</g><path class="county" d="{county}"/>{sp}</svg>')


def emergency_page(out_dir):
    import os
    from page_datasets import evacuation_zones, emergency_shelters, emergency_resources, emergency_notices, _emergency_file
    Z, S, R, N = evacuation_zones(), emergency_shelters(), emergency_resources(), emergency_notices()
    # A notice posted twice shows once, as its newest version, with the earlier posts listed under Details (data/dupes.py).
    for n in N:
        if n.get('same_as'):
            keep = next((m for m in N if m['notice_id'] == n['same_as']), None)
            if keep is not None:
                keep.setdefault('earlier', []).append(n)
    N = [n for n in N if not n.get('same_as')]
    if not Z:
        return '<div class="page"><h1>Emergencies and alerts</h1><p>No emergency information on file for this place yet.</p></div>'
    zinfo = _emergency_file('zones.json')
    here = os.path.dirname(os.path.abspath(__file__))
    base = json.load(open(os.path.join(here, '..', 'geo', 'basemap.json')))
    active = [n for n in N if n['status'] == 'active']
    rank = {'extreme': 0, 'severe': 1, 'moderate': 2, 'minor': 3, 'info': 4}
    active.sort(key=lambda n: (rank.get(n['severity'], 5), str(n.get('issued') or '')), reverse=False)
    cnt = lambda k: sum(1 for n in active if n['kind'] == k)
    n_open = sum(1 for s in S if s['status'] == 'open')
    zc = {z['zone']: z['color'] for z in Z}

    kpi = lambda id_, v, lab, href: f'<a class="em-kpi{" on" if v else ""}" id="{id_}" href="{href}"><b>{v}</b><span>{lab}</span></a>'
    kpis = (kpi('kWeather', cnt('weather'), 'Weather alerts', '#now') + kpi('kEvac', cnt('evacuation'), 'Evacuation orders', '#now') +
            kpi('kShelter', n_open, 'Shelters open', '#shelters') + kpi('kWater', cnt('boil-water'), 'Boil-water notices', '#now') +
            kpi('kRoad', cnt('road'), 'Road closures', '#now'))
    chips = '<button type="button" class="chip" data-v="" aria-pressed="true">Everything</button>' + ''.join(
        f'<button type="button" class="chip" data-v="{k}" aria-pressed="false">{e(v[0])}</button>' for k, v in KIND.items())

    # shelters, by group
    groups = []
    for g in dict.fromkeys(s['group_name'] for s in S):
        ss = [s for s in S if s['group_name'] == g]
        cards = ''.join(f'''<div class="em-sh" data-id="{e(s["shelter_id"])}"><span class="em-pill{" open" if s["status"] == "open" else ""}">{e(s["status"])}</span>
  <b>{e(s["name"])}</b><small><a href="https://www.google.com/maps/search/?api=1&amp;query={html.escape(s["address"] or s["name"])}" target="_blank" rel="noopener">{e(s["address"])}</a></small>
  {f'<small>In evacuation Zone {e(s["evacuation_zone"])}</small>' if s.get("evacuation_zone") else ''}{f'<small>{e(s["note"])}</small>' if s.get("note") else ''}</div>''' for s in ss)
        groups.append(f'<div class="em-shg"><h3 class="ch-grp" style="margin:0">{e(TYPE.get(ss[0]["shelter_type"], g))} <span class="muted" style="font-weight:400;font-size:.86rem">· {e(g)}</span></h3>'
                      f'{f"<p class=muted style=font-size:.88rem;margin:0>{e(ss[0]["group_about"])}</p>" if ss[0].get("group_about") else ""}<div class="em-shs">{cards}</div></div>')
    as_of = S[0]['status_as_of'] if S else None

    zcards = ''.join(f'''<div class="em-zc" data-z="{e(z["zone"])}"><span class="z" style="background:{z["color"]}">{e(z["zone"])}</span>
  <div><b>Zone {e(z["zone"])}: {e(z["where_it_is"])}</b><small>{e(z["when_ordered"])}</small></div></div>''' for z in Z)

    # resources, by group
    res = []
    for g in dict.fromkeys(r['group'] for r in R):
        items = ''.join(f'''<div class="em-r"><b>{f'<a href="{e(r["url"])}" target="_blank" rel="noopener">{e(r["name"])}</a>' if r.get("url") else e(r["name"])}</b>
  {f'<a class="ph" href="tel:{e(r["phone"])}">{e(r["phone"])}</a>' if r.get("phone") else ''}<small>{e(r["about"])}</small></div>''' for r in R if r['group'] == g)
        res.append(f'<h3 class="ch-grp">{e(g)}</h3><div class="em-res">{items}</div>')

    # recent notices (last 90 days of the archive)
    cut = (dt.date.today() - dt.timedelta(days=90)).isoformat()
    recent = [n for n in N if str(n.get('issued') or n.get('first_seen') or '')[:10] >= cut][:80]
    rows = ''.join(f'<tr><td class="d">{_when(n.get("issued") or n.get("first_seen"))}</td><td>{e(KIND.get(n["kind"], ("Notice",))[0])}</td>'
                   f'<td>{f"<a href=\"{e(n["url"])}\" target=\"_blank\" rel=\"noopener\">{e(n["title"])}</a>" if n.get("url") else e(n["title"])}</td>'
                   f'<td>{gov_link(n["gov_id"], n["source"]) if n.get("gov_id") else e(n["source"])}</td><td>{e(n["status"])}</td></tr>' for n in recent)
    by_kind = {}
    for n in N:
        by_kind[n['kind']] = by_kind.get(n['kind'], 0) + 1

    headline = ('Evacuation order in effect.' if cnt('evacuation') else
                f'{cnt("weather")} weather alert{"s" if cnt("weather") != 1 else ""} in effect.' if cnt('weather') else 'No weather warnings or evacuation orders right now.')
    return f'''<style>{CSS}</style>
<div class="page tax em">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Take part · Stay safe</span><h1>Emergencies and alerts</h1>
    <p class="lede">What is happening now in Bay County: weather warnings, evacuation orders, open shelters, boil-water notices and road closures, gathered from the National Weather Service, the county and the cities every few minutes. Look up your evacuation zone, find every shelter and get alerts on your phone.</p></div>
    <div class="stamp"><a class="pill" href="#zone">Find my zone →</a><a class="pill" href="/hurricane-prep">Hurricane prep →</a><span>In an emergency, call 911. Follow instructions from emergency officials.</span></div></header>

  <div class="em-status" id="emStatus" data-sev="{"extreme" if cnt("evacuation") else "moderate" if active else "info"}" aria-live="polite">{ico("bell", "salmon")}
    <div><h2 id="emHead">{e(headline)}</h2><p id="emSub">From the last daily check. Live updates load in a moment.</p></div></div>
  <div class="em-kpis">{kpis}</div>

  <section class="tx-sec"><div class="sec-hd"><h2 id="zone" data-tile="My zone">Your evacuation zone</h2><span class="muted">From Bay County's evacuation zone map</span></div>
    <div class="em-zone"><div style="display:flex;flex-direction:column;gap:12px">
      <form class="em-form" id="emZoneForm" role="search"><label class="sr" for="emAddr">Street address</label>
        <input id="emAddr" name="a" autocomplete="street-address" placeholder="Your street address, like 825 Ohio Ave" maxlength="120">
        <button type="submit" class="ui-btn">Look up</button><button type="button" class="ui-btn" id="emLoc">{ico("pin")}Use my location</button></form>
      <p style="margin:0;font-size:.92rem">{e(zinfo["summary"])}</p>
      <p class="muted" style="margin:0;font-size:.86rem">{e(zinfo["outside"])}</p></div>
      <div class="em-result" id="emZoneOut" aria-live="polite"><p class="muted">Type an address to see its zone, whether an order covers it and the nearest county shelters.</p></div></div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="now" data-tile="Happening now">Happening now</h2><span class="muted">Most serious first</span></div>
    <div class="em-ctl"><div class="chips" id="emKind" role="group" aria-label="Kind of notice">{chips}</div></div>
    <div class="em-list" id="emList">{"".join(_notice(n) for n in active)}</div>
    <p class="em-empty" id="emNone" {"hidden" if active else ""}>Nothing of this kind right now.</p>
    <p class="note">Road closures cover state roads (FL511) and the closures cities post. City and county notices stay listed while their alert center lists them; news posts about storms and closures stay for {10} days.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="shelters" data-tile="Shelters">Shelters</h2><span class="muted">{f"Status as Bay County posted it, {e(_when(as_of))}" if as_of else "Status as Bay County posts it"}</span></div>
    <p>Bay County Emergency Services opens shelters with Bay District Schools and the Florida Department of Health. <b>Not every shelter opens for every storm</b>, and shelters are a last resort: plan to stay with family or friends outside the zone if you can. Special needs shelters need registration ahead of time.</p>
    {"".join(groups)}
    <p class="note">The status updates here within minutes of the county changing its <a href="{e(S[0]["source_url"] if S else "")}" target="_blank" rel="noopener">shelter page</a>. Bring medicines, bedding, ID and supplies for a few days; check whether a shelter takes pets before you go.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="zones" data-tile="Zone map">The four evacuation zones</h2><span class="muted">Zone A leaves first</span></div>
    <div class="em-map">{_project(Z, base, S)}<div class="em-zl">{zcards}<p class="muted" style="margin:0;font-size:.84rem">Simplified shapes; dots are county shelters. Check an exact address above or on <a href="{e(zinfo["map_url"])}" target="_blank" rel="noopener">the county's map</a>.</p></div></div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="get-alerts" data-tile="Get alerts">Get alerts</h2></div>
    <div class="em-get">
      <div><b>{ico("bell")} On your phone</b><small>Sign in to the BayCounty.me app, then turn on alerts in My home settings: weather warnings, evacuation orders, shelter openings, boil-water notices for your city, and agenda items near your home.</small></div>
      <a href="https://www.alertbay.org" target="_blank" rel="noopener"><b>{ico("megaphone")} AlertBay</b><small>Bay County's own text, call and email alerts, for unincorporated Bay County, every city and the schools.</small></a>
      <a href="/alerts"><b>{ico("mail")} Email from BayCounty.me</b><small>Weekly updates for the governments you follow, plus alerts for one thing.</small></a>
      <a href="/hurricane-prep"><b>{ico("shield")} Hurricane prep</b><small>Sandbags, generator safety, a kit and a plan, what to do after a storm, and the FEMA money past storms brought each ZIP code.</small></a>
      <a href="https://www.weather.gov/tae/" target="_blank" rel="noopener"><b>{ico("storm")} Weather radio and NWS</b><small>The National Weather Service office in Tallahassee issues every watch and warning for Bay County.</small></a>
    </div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="numbers" data-tile="Numbers">Phone numbers and links</h2></div>{"".join(res)}</section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="recent" data-tile="Recent">Recent notices</h2><span class="muted">The last 90 days</span></div>
    <details class="tbl-toggle" open><summary>{len(recent)} notices</summary><div class="tablewrap"><table class="tx-table em-tbl"><thead><tr><th>Posted</th><th>Kind</th><th>Notice</th><th>From</th><th>Status</th></tr></thead>
    <tbody>{rows or '<tr><td colspan="5" class="muted">None yet.</td></tr>'}</tbody></table></div></details>
    <p class="note">The archive started on October 27, 2026; older notices aren't on file. Every notice: <a href="/api/v1/datasets/emergency-notices">emergency-notices</a> ({", ".join(f"{v} {e(KIND.get(k, (k,))[0].lower())}" for k, v in sorted(by_kind.items(), key=lambda x: -x[1]))}).</p></section>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>Weather alerts</b> are every active watch, warning and advisory the National Weather Service issues for Bay County's land and coastal zones.</li>
      <li><b>Boil-water notices, closures and storm updates</b> come from the alert centers and news posts of Bay County, Panama City, Panama City Beach, Lynn Haven, Callaway, Parker and Mexico Beach, and from Springfield's boil-water notice page. All are checked every 5 minutes.</li>
      <li><b>State road closures</b> come from FL511, the Florida Department of Transportation's traffic service, for Bay County.</li>
      <li><b>Shelters</b> come from Bay County Emergency Services' shelter page; each address is placed on the map with the county's address points. <b>Zones</b> are the county's evacuation zone map.</li>
      <li>Everything is checked every 5 minutes. BayCounty.me is an independent site: when an order or notice here differs from what emergency officials say, follow the officials.</li>
      <li><b>Data:</b> <a href="/api/v1/emergency">/api/v1/emergency</a> (live) · <a href="/api/v1/evacuation-zone?address=825+Ohio+Ave">/api/v1/evacuation-zone</a> · <a href="/api/v1/datasets/emergency-notices">emergency-notices</a> · <a href="/api/v1/datasets/emergency-shelters">emergency-shelters</a> · <a href="/api/v1/datasets/evacuation-zones">evacuation-zones</a> · <a href="/api/v1/datasets/emergency-resources">emergency-resources</a>.</li>
    </ul></section>
</div>
<script type="application/json" id="emKinds">{json.dumps({k: [v[0], v[1]] for k, v in KIND.items()})}</script>
<script type="application/json" id="emZoneColors">{json.dumps(zc)}</script>
<link rel="stylesheet" href="/assets/tax.css">
<script>{JS}</script>'''
