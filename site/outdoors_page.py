"""Beaches (/beaches) and parks (/parks).

/beaches: today's beach flag and rip current risk (National Weather Service surf zone forecast, which carries the flag
color the beach officials report), what each flag means, Florida Healthy Beaches water samples at each sampling site,
and every public beach access and county beach lot on a map. /parks: every public park, boat ramp and trail, with
amenities, a map and each government's recreation pages.

Built from the beach-conditions, beach-water-sites, beach-water-samples, beach-access, beach-parking, parks, boat-ramps,
trails and recreation-departments datasets (site/page_datasets.py, from data/outdoors/<county>/). Government names link
to their profiles through entity_links.gov.
"""
import datetime as dt
import html
import json

from entity_links import gov as gov_link

e = lambda s: html.escape(str(s if s is not None else ''))
LEAFLET = ('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">'
           '<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js" defer></script>')
FLAG_HEX = {'Double red': '#C62828', 'Red': '#E53935', 'Yellow': '#F2C230', 'Green': '#2E9E5B', 'Purple': '#7E57C2'}
RATE_TONE = {'Good': 'good', 'Moderate': 'mod', 'Poor': 'poor'}

CSS = r"""
.od-today{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,2fr);gap:14px}
.od-flag{display:flex;gap:18px;align-items:center;padding:22px;border-radius:24px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.od-pole{flex:none;width:64px;height:84px;position:relative}
.od-pole::before{content:"";position:absolute;left:6px;top:0;bottom:0;width:4px;border-radius:2px;background:var(--muted);opacity:.6}
.od-pole i{position:absolute;left:10px;top:4px;width:50px;height:34px;border-radius:2px 6px 6px 2px;background:var(--fl,#999);box-shadow:inset 0 0 0 1px rgba(0,0,0,.08)}
.od-pole i + i{top:42px}
.od-flag b{display:block;font:700 1.6rem/1.1 var(--f-display);letter-spacing:-.02em}
.od-flag small{display:block;color:var(--muted);font-size:.84rem;margin-top:4px;line-height:1.4}
.od-flag .od-what{font-size:.95rem;font-weight:600;margin-top:2px}
.od-facts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:0}
.od-facts div{padding:14px 16px;border-radius:18px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.od-facts dt{font-size:.78rem;color:var(--muted)}
.od-facts dd{margin:4px 0 0;font:600 1.15rem var(--f-body);overflow-wrap:anywhere}
.od-risk-High{color:#D84315}.od-risk-Moderate{color:#B7791F}.od-risk-Low{color:#2E7D32}
:root[data-theme="dark"] .od-risk-Moderate{color:#F2C230}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .od-risk-Moderate{color:#F2C230}}
.od-days{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px}
.od-day{padding:14px 16px;border-radius:18px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.od-day b{display:block;font-size:.92rem}
.od-day span{display:block;font-size:.84rem;margin-top:4px}
.od-day small{display:block;font-size:.8rem;color:var(--muted);margin-top:4px;line-height:1.4}
.od-alert{display:flex;gap:10px;align-items:flex-start;padding:14px 16px;border-radius:18px;background:color-mix(in srgb,#E53935 10%,var(--surface));border:1px solid color-mix(in srgb,#E53935 40%,transparent)}
.od-legend{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}
.od-leg{display:flex;gap:12px;align-items:flex-start;padding:14px;border-radius:18px;background:var(--surface);box-shadow:var(--ui-shadow)}
.od-leg i{flex:none;width:28px;height:20px;border-radius:2px 5px 5px 2px;background:var(--fl);margin-top:2px;box-shadow:inset 0 0 0 1px rgba(0,0,0,.08)}
.od-leg i.dbl{box-shadow:6px 0 0 -0px var(--fl);width:22px;margin-right:6px}
.od-leg b{display:block;font-size:.9rem}
.od-leg small{display:block;font-size:.8rem;color:var(--muted);margin-top:2px;line-height:1.4}
.od-sites{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.od-site{padding:14px 16px;border-radius:18px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0;display:flex;flex-direction:column;gap:6px}
.od-site b{font-size:.94rem}
.od-site small{font-size:.8rem;color:var(--muted)}
.od-dots{display:flex;gap:3px;flex-wrap:wrap}
.od-dots i{width:10px;height:10px;border-radius:50%;background:var(--sunken)}
.od-dots i.good,.od-pill.good{background:#2E9E5B}.od-dots i.mod,.od-pill.mod{background:#E0A526}.od-dots i.poor,.od-pill.poor{background:#D84315}
.od-pill{display:inline-block;font-size:.74rem;font-weight:600;padding:2px 9px;border-radius:999px;color:#fff;background:var(--muted)}
.od-pill.mod{color:#2a1d00}
.od-map{height:440px;border-radius:24px;box-shadow:var(--ui-shadow);overflow:hidden;background:var(--sunken);z-index:0}
:root[data-theme="dark"] .od-map .leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) brightness(.9) contrast(.9)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .od-map .leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) brightness(.9) contrast(.9)}}
.od-map .leaflet-popup-content{font:.85rem/1.45 var(--f-body);margin:10px 12px}
.od-map .leaflet-popup-content b{display:block;font-size:.92rem}
.od-ctl{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center}
.od-ctl input[type=search]{min-height:40px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--ink);padding:0 16px;font:inherit;min-width:220px;flex:1 1 220px;max-width:360px}
.od-key{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.82rem;color:var(--muted)}
.od-key span{display:inline-flex;align-items:center;gap:6px}
.od-key i{width:12px;height:12px;border-radius:50%;display:inline-block;border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.2)}
.od-tags{display:flex;flex-wrap:wrap;gap:4px}
.od-tags span{font-size:.72rem;padding:2px 8px;border-radius:999px;background:var(--sunken);color:var(--ink);white-space:nowrap}
.od-tbl td,.od-tbl th{vertical-align:top}
.od-tbl td.n,.od-tbl th.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.od-tbl tr[hidden]{display:none!important}
.od .od-morebtn{width:auto;border:0;cursor:pointer;font-family:inherit}
.od .od-morebtn[hidden]{display:none}
.od-parks{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.od-park{display:flex;flex-direction:column;border-radius:20px;background:var(--surface);box-shadow:var(--ui-shadow);overflow:hidden;min-width:0}
.od-park[hidden]{display:none}
.od-park img{width:100%;height:132px;object-fit:cover;display:block;background:var(--sunken)}
.od-park > div{padding:14px 16px;display:flex;flex-direction:column;gap:6px;flex:1}
.od-park b{font-size:.96rem}
.od-park small{font-size:.8rem;color:var(--muted);line-height:1.4}
.od-park .od-go{margin-top:auto;font-size:.84rem}
.od-rec{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}
.od-rec div{padding:14px 16px;border-radius:18px;background:var(--surface);box-shadow:var(--ui-shadow)}
.od-rec b{display:block;font-size:.92rem}
.od-rec a{font-size:.85rem}
@media (max-width:860px){.od-today{grid-template-columns:1fr}.od-facts{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:760px){.od-map{height:340px;border-radius:18px}.od-flag{padding:18px}.od-flag b{font-size:1.35rem}}
"""

MAP_JS = r"""
function odMap(id, pts, opts) {
  const el = document.getElementById(id); if (!el || !window.L) return null;
  const m = L.map(el, {scrollWheelZoom: false, attributionControl: true});
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    {maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(m);
  const layers = {};
  for (const p of pts) {
    if (p.lat == null) continue;
    const mk = L.circleMarker([p.lat, p.lon], {radius: p.r || 6, color: '#fff', weight: 1.5, fillColor: p.c, fillOpacity: .95});
    mk.bindPopup(p.html); mk._od = p;
    (layers[p.g] = layers[p.g] || L.layerGroup().addTo(m)).addLayer(mk);
  }
  const all = pts.filter(p => p.lat != null).map(p => [p.lat, p.lon]);
  if (all.length) m.fitBounds(all, {padding: [24, 24]});
  return {map: m, layers};
}
const odDir = (lat, lon) => `https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}`;
"""


def _yes(v, label):
    return f'<span>{e(label)}</span>' if v else ''


def _dir(lat, lon):
    return f'<a href="https://www.google.com/maps/dir/?api=1&amp;destination={lat},{lon}" rel="noopener" target="_blank">Directions</a>' if lat and lon else ''


def _time(iso):
    try:
        d = dt.datetime.fromisoformat(iso).astimezone(dt.timezone(dt.timedelta(hours=-5)))  # Central daylight time
    except (TypeError, ValueError):
        return ''
    return d.strftime('%a, %b %-d at %-I:%M %p').replace('AM', 'a.m.').replace('PM', 'p.m.')


def _pole(color):
    c = FLAG_HEX.get(color, '#9AA3AF')
    return f'<span class="od-pole" id="odPole" aria-hidden="true"><i style="--fl:{c}"></i>{f"<i style=--fl:{c}></i>" if color == "Double red" else ""}</span>'


def beaches_page(out_dir):
    from page_datasets import beach_conditions, beach_water_sites, beach_water_samples, beach_access, beach_parking
    C, S, W, A, P = beach_conditions(), beach_water_sites(), beach_water_samples(), beach_access(), beach_parking()
    if not (C or S or A):
        return '<div class="page"><h1>Beaches</h1><p>No beach data on file for this place yet.</p></div>'
    fc = sorted((r for r in C if r['kind'] == 'forecast'), key=lambda r: r['sort_order'])
    legend = sorted((r for r in C if r['kind'] == 'legend'), key=lambda r: r['sort_order'])
    alerts = [r for r in C if r['kind'] == 'alert']
    hist = sorted((r for r in C if r['kind'] == 'flag'), key=lambda r: r['date'])
    now = fc[0] if fc else {}
    flag = now.get('flag_color')
    meaning = next((l['meaning'] for l in legend if l['flag_color'] == flag), '')
    issued = now.get('issued')

    # --- today
    risk = now.get('rip_current_risk')
    facts = [('Rip current risk', f'<span class="od-risk-{e(risk)}" id="odRisk">{e(risk or "—")}</span>'), ('Surf', e(now.get('surf_height') or '—')),
             ('Water', e((now.get('water_temperature') or '—').replace(' degrees', '°F'))), ('UV index', e(now.get('uv_index') or '—'))]
    today = f'''<div class="od-today">
  <div class="od-flag">{_pole(flag)}<div><span class="eyebrow">Beach flag</span><b id="odFlag">{e(flag + " flag" if flag else "Not reported")}</b>
    <span class="od-what" id="odMeaning">{e(meaning)}</span><small id="odIssued">As reported by beach officials to the National Weather Service, {e(_time(issued))}. Flags can change during the day: check the pole at the beach.</small></div></div>
  <dl class="od-facts">{"".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in facts)}</dl>
</div>'''
    alert_html = ''.join(f'<div class="od-alert"><span class="ico i-alert" aria-hidden="true"></span><div><b>{e(a["period"])}</b><br><span class="muted">{e(a.get("summary") or "")}</span> <a href="{e(a["source_url"])}" rel="noopener" target="_blank">Details</a></div></div>' for a in alerts)
    days = ''.join(f'''<div class="od-day"><b>{e(r["period"])}</b><span>Rip currents: <b class="od-risk-{e(r.get("rip_current_risk"))}" style="display:inline">{e(r.get("rip_current_risk") or "—")}</b></span>
  {f"<span>Surf: {e(r['surf_height'])}</span>" if r.get("surf_height") else ""}<small>{e(r.get("weather") or "") + (", " + e(r["winds"]) if r.get("winds") else "") if r.get("weather") else e((r.get("summary") or "").replace("*", ""))}</small></div>''' for r in fc[1:])
    leg = ''.join(f'<div class="od-leg"><i class="{"dbl" if l["flag_color"] == "Double red" else ""}" style="--fl:{FLAG_HEX[l["flag_color"]]}"></i><div><b>{e(l["flag_color"])}: {e(l["meaning"])}</b><small>{e(l["summary"])}</small></div></div>' for l in legend)
    counts = {}
    for h in hist:
        counts[h['flag_color']] = counts.get(h['flag_color'], 0) + 1
    hist_note = (f'Flags recorded on {len(hist)} day{"s" if len(hist) != 1 else ""} since {dt.date.fromisoformat(hist[0]["date"]).strftime("%B %-d, %Y")}: '
                 + ', '.join(f'{n} {c.lower()}' for c, n in sorted(counts.items(), key=lambda x: -x[1])) + '.') if hist else ''

    # --- water quality
    by_site = {}
    for r in W:
        by_site.setdefault(r['site_id'], []).append(r)
    year_ago = (dt.date.today() - dt.timedelta(days=365)).isoformat()
    site_cards = []
    for s in sorted((s for s in S if s['active']), key=lambda s: s['longitude'] or 0):
        rs = sorted((r for r in by_site.get(s['site_id'], []) if r.get('rating') in RATE_TONE), key=lambda r: r['date'])
        dots = ''.join(f'<i class="{RATE_TONE[r["rating"]]}" title="{e(r["date"])}: {e(r["rating"])} ({e(r["reported"])})"></i>' for r in rs[-16:])
        poor_yr = sum(1 for r in rs if r['rating'] == 'Poor' and r['date'] >= year_ago)
        lr = s.get('latest_rating')
        site_cards.append(f'''<div class="od-site"><div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start"><b>{e(s["name"])}</b>{f'<span class="od-pill {RATE_TONE.get(lr, "")}">{e(lr)}</span>' if lr else ''}</div>
  <small>Latest sample {e(dt.date.fromisoformat(s["latest_date"]).strftime("%b %-d, %Y") if s.get("latest_date") else "none")}{f" · {s['latest_enterococcus']:g} per 100 mL" if s.get("latest_enterococcus") is not None else ""}{" · health advisory" if s.get("latest_advisory") else ""}</small>
  <div class="od-dots" aria-label="Last {len(rs[-16:])} samples">{dots}</div>
  <small>{poor_yr} poor sample{"s" if poor_yr != 1 else ""} in the past year · <a href="{e(s["source_url"])}" rel="noopener" target="_blank">State lookup</a></small></div>''')
    recent = (dt.date.today() - dt.timedelta(days=45)).isoformat()
    poor_now = [s for s in S if s['active'] and s.get('latest_rating') == 'Poor' and (s.get('latest_date') or '') >= recent]
    yr = [r for r in W if r['date'] >= year_ago and r.get('rating') in RATE_TONE]
    pct_good = round(100 * sum(1 for r in yr if r['rating'] == 'Good') / len(yr)) if yr else None

    # --- accesses and parking
    pts = []
    for a in A:
        tags = [t for t in (('Wheelchair accessible', a['wheelchair_access']), ('Drive-on', a['vehicle_access']), ('Parking', a['parking']), ('Restrooms', a['restroom']),
                            ('Showers', a['shower']), ('Lifeguard', a['lifeguard'])) if t[1]]
        pts.append({'g': 'access', 'lat': a['latitude'], 'lon': a['longitude'], 'c': '#2563EB', 'r': 5,
                    'html': f'<b>{e(a["name"])}</b>{e(a["address"] or "")}<br>{e(", ".join(t[0] for t in tags) or a["area"])}<br><a href="https://www.google.com/maps/dir/?api=1&destination={a["latitude"]},{a["longitude"]}" target="_blank" rel="noopener">Directions</a>'})
    for s in S:
        if s['active']:
            col = {'Good': '#2E9E5B', 'Moderate': '#E0A526', 'Poor': '#D84315'}.get(s.get('latest_rating'), '#888')
            pts.append({'g': 'water', 'lat': s['latitude'], 'lon': s['longitude'], 'c': col, 'r': 8,
                        'html': f'<b>{e(s["name"])}</b>Water sample site: {e(s.get("latest_rating") or "no recent result")}{(" on " + e(s["latest_date"])) if s.get("latest_date") else ""}'})
    for l in P:
        pts.append({'g': 'parking', 'lat': l['latitude'], 'lon': l['longitude'], 'c': '#64748B', 'r': 6,
                    'html': f'<b>County beach parking</b>{e(l["spaces"])} spaces · near {e(l["nearest_access"])}'})
    rows = ''.join(f'''<tr data-q="{e((a["name"] + " " + (a["address"] or "") + " " + a["area"]).lower())}" data-w="{1 if a["wheelchair_access"] else 0}" data-v="{1 if a["vehicle_access"] else 0}" data-p="{1 if a["parking"] else 0}">
  <td><b>{e(a["name"])}</b><br><span class="muted" style="font-size:.8rem">{e(a["address"] or "")}</span></td><td>{e(a["area"])}</td>
  <td><div class="od-tags">{_yes(a["wheelchair_access"], "Wheelchair")}{_yes(a["vehicle_access"], "Drive-on")}{_yes(a["parking"], "Parking" + (f" ({a['parking_spaces']})" if a.get("parking_spaces") else ""))}{_yes(a["restroom"], "Restrooms")}{_yes(a["shower"], "Showers")}{_yes(a["lifeguard"], "Lifeguard")}</div></td>
  <td>{_dir(a["latitude"], a["longitude"])}</td></tr>''' for a in sorted(A, key=lambda a: a['longitude'] or 0))
    n_wc = sum(1 for a in A if a['wheelchair_access'])
    n_spaces = sum(l['spaces'] or 0 for l in P)

    k = lambda lab, v, s, i='': f'<div class="kpi"><span class="eyebrow">{lab}</span><span class="v"{i}>{v}</span><span class="s">{s}</span></div>'
    kpis = (k('Water samples rated good', f'{pct_good}%' if pct_good is not None else '—', f'Past 12 months, {len(yr)} samples at {len(site_cards)} sites') +
            k('Sites rated poor now', len(poor_now), 'At a test in the past six weeks' if poor_now else 'No poor result in the past six weeks') +
            k('Public beach accesses', len(A), f'{n_wc} marked wheelchair accessible, {sum(1 for a in A if a["vehicle_access"])} drive-on') +
            k('County beach parking', f'{n_spaces:,}', f'Spaces in {len(P)} county lots'))
    from page_datasets import _outdoor_files
    raw = _outdoor_files()[3]
    state = json.dumps({'issued': issued, 'flag': flag, 'office': raw.get('office', 'TAE'), 'zone': raw.get('zone', 'FLZ112'), 'label': raw.get('flag_label', 'Bay'), 'legend': {l['flag_color']: l['meaning'] for l in legend}, 'hex': FLAG_HEX}).replace('</', '<\\/')
    data = json.dumps(pts, ensure_ascii=False).replace('</', '<\\/')
    fresh = f'Forecast issued {_time(issued)}' if issued else ''

    return f'''<style>{CSS}</style>{LEAFLET}
<div class="page tax od">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Outdoors · Beaches</span><h1>Beaches</h1>
    <p class="lede">Today's beach flag and rip current risk, what each flag means, how clean the water tested at each state sampling site, and every public beach access and county beach parking lot on one map.</p></div>
    <div class="stamp"><a class="pill" href="/parks">Parks, ramps and trails →</a><span>{e(fresh)}</span></div></header>
  <div class="kpis">{kpis}</div>

  <section class="tx-sec"><div class="sec-hd"><h2 id="today" data-tile="Today">Today at the beach</h2><span class="muted">Gulf beaches from Panama City Beach to Mexico Beach</span></div>
    {today}{alert_html}
    {f'<div class="od-days">{days}</div>' if days else ''}
    <p class="note">From the National Weather Service Tallahassee surf zone forecast. Rip currents cause most lifeguard rescues on these beaches: if you're caught in one, swim parallel to shore, then back in. For a text when Panama City Beach's flags change, text PCBFLAGS to 888777.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="flags" data-tile="Flag colors">What the flags mean</h2><span class="muted">The international beach warning flags flown on every public beach here</span></div>
    <div class="od-legend">{leg}</div>
    <p class="note">Double red flags close the water: going in can bring a fine in Panama City Beach and unincorporated Bay County. No flag flying doesn't mean the water is safe.{(" " + e(hist_note)) if hist_note else ""}</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="water" data-tile="Water quality">Water quality</h2><span class="muted">Florida Healthy Beaches Program, Florida Department of Health</span></div>
    <p>The state health department tests the water at {len(site_cards)} beaches here for enterococci, bacteria that point to sewage or animal waste, usually every two weeks. Each dot is one sample, oldest to newest.{(" " + str(len(poor_now)) + " site" + (" was" if len(poor_now) == 1 else "s were") + " rated poor at a test in the past six weeks.") if poor_now else " No site was rated poor in the past six weeks."}</p>
    <div class="od-key"><span><i style="background:#2E9E5B"></i>Good: 0 to 35 per 100 mL</span><span><i style="background:#E0A526"></i>Moderate: 36 to 70</span><span><i style="background:#D84315"></i>Poor: 71 or more (health advisory likely)</span></div>
    <div class="od-sites">{"".join(site_cards)}</div>
    <p class="note">A poor result usually brings a resample, then a health advisory if it holds: swimming isn't banned, but people with weak immune systems, young children and anyone with open cuts should stay out. Results take a day or two to come back, so the water today may differ.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="access" data-tile="Beach access">Beach access and parking</h2><span class="muted">{len(A)} public accesses</span></div>
    <div class="od-key"><span><i style="background:#2563EB"></i>Beach access</span><span><i style="background:#2E9E5B"></i>Water sample site</span><span><i style="background:#64748B"></i>County beach parking</span></div>
    <div class="od-map" id="odMap" role="img" aria-label="Map of public beach accesses, water sampling sites and county beach parking"></div>
    <div class="od-ctl"><input type="search" id="odQ" placeholder="Search by name, number or street" aria-label="Search beach accesses">
      <div class="chips" id="odF" role="group" aria-label="Filter"><button type="button" class="chip" data-v="" aria-pressed="true">All</button><button type="button" class="chip" data-v="w" aria-pressed="false">Wheelchair accessible</button><button type="button" class="chip" data-v="v" aria-pressed="false">Drive-on</button><button type="button" class="chip" data-v="p" aria-pressed="false">Parking</button></div></div>
    <div class="tablewrap"><table class="tx-table od-tbl" id="odTbl" data-tt="own"><thead><tr><th>Access</th><th>Area</th><th>What's there</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>
    <p class="note" id="odNone" hidden>No accesses match.</p>
    <div><button type="button" class="ui-btn od-morebtn" id="odMore" hidden>Show more</button></div>
    <p class="note">Accesses and drive-on points are from the county's map; wheelchair access is from Panama City Beach's map; parking, restrooms, showers and lifeguards from the state's coastal access survey where it covers that access (blank means not surveyed, not "none"). Driving on the beach needs a county permit.</p></section>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>Flag and forecast:</b> the National Weather Service Tallahassee surf zone forecast for coastal Bay County, read every morning and again in your browser when you open this page. The forecast lists the flag color the beach officials report to the weather service.</li>
      <li><b>Water quality:</b> the Florida Department of Health's Healthy Beaches Program sampling sites and results, read every day. The state's lookup shows each site's latest 50 samples; we keep every sample as it comes in.</li>
      <li><b>Beach access and parking:</b> Bay County's and Panama City Beach's public GIS maps and the Florida DEP coastal access survey.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/beach-conditions">beach-conditions</a> · <a href="/api/v1/datasets/beach-water-sites">beach-water-sites</a> · <a href="/api/v1/datasets/beach-water-samples">beach-water-samples</a> · <a href="/api/v1/datasets/beach-access">beach-access</a> · <a href="/api/v1/datasets/beach-parking">beach-parking</a> (CSV on <a href="/open-data">Open data</a>).</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>{MAP_JS}
(() => {{
  const S = {state};
  addEventListener('load', () => {{
    const M = odMap('odMap', {data});
    const tb = document.getElementById('odTbl'), rows = [...tb.tBodies[0].rows], more = document.getElementById('odMore');
    const N = matchMedia('(max-width:760px)').matches ? 10 : 20; let f = '', q = '', open = false;
    function show() {{
      let n = 0, hit = 0;
      for (const r of rows) {{
        const ok = (!q || r.dataset.q.includes(q)) && (!f || r.dataset[f] === '1');
        if (ok) hit++;
        r.hidden = !ok || (!open && !q && n >= N); if (ok) n++;
      }}
      more.hidden = open || q || hit <= N; more.textContent = `Show all ${{hit}}`;
      document.getElementById('odNone').hidden = hit > 0;
    }}
    document.getElementById('odQ').addEventListener('input', ev => {{ q = ev.target.value.trim().toLowerCase(); show(); }});
    const g = document.getElementById('odF');
    g.addEventListener('click', ev => {{ const b = ev.target.closest('button'); if (!b) return;
      g.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); f = b.dataset.v; show(); }});
    more.addEventListener('click', () => {{ open = true; show(); }});
    show();
  }});
  // newer flag than the last build: read the latest surf zone forecast straight from the weather service
  fetch(`https://api.weather.gov/products/types/SRF/locations/${{S.office}}`, {{headers: {{Accept: 'application/ld+json'}}}}).then(r => r.json()).then(l => {{
    const p = (l['@graph'] || [])[0]; if (!p || (S.issued && p.issuanceTime <= S.issued)) return;
    return fetch(p['@id']).then(r => r.json()).then(d => {{
      const t = d.productText || '', m = t.match(new RegExp('^' + S.label + '\\\\.{{3,}}\\\\s*(DOUBLE RED|RED|YELLOW|GREEN|PURPLE)', 'm'));
      const z = t.split(new RegExp('^' + S.zone + '-', 'm'))[1] || '', rk = (z.match(/Rip Current Risk\\.{{3,}}\\s*(Low|Moderate|High)/) || [])[1];
      if (!m) return;
      const c = m[1] === 'DOUBLE RED' ? 'Double red' : m[1][0] + m[1].slice(1).toLowerCase();
      document.getElementById('odFlag').textContent = c + ' flag';
      document.getElementById('odMeaning').textContent = S.legend[c] || '';
      document.querySelectorAll('#odPole i').forEach(i => i.style.setProperty('--fl', S.hex[c] || '#999'));
      const when = new Date(p.issuanceTime).toLocaleString('en-US', {{weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago'}});
      document.getElementById('odIssued').textContent = `As reported by beach officials to the National Weather Service, ${{when}}. Flags can change during the day: check the pole at the beach.`;
      if (rk) {{ const el = document.getElementById('odRisk'); el.textContent = rk; el.className = 'od-risk-' + rk; }}
    }});
  }}).catch(() => {{}});
}})();
</script>'''


AMENITY = [('playground', 'Playground'), ('restroom', 'Restrooms'), ('pavilion', 'Pavilion'), ('picnic_tables', 'Picnic tables'), ('trail', 'Trail'),
           ('boat_ramp', 'Boat ramp'), ('boat_dock', 'Dock'), ('fishing_pier', 'Fishing pier'), ('beach_access', 'Beach access'), ('baseball', 'Baseball'),
           ('softball', 'Softball'), ('basketball', 'Basketball'), ('football', 'Football'), ('soccer', 'Soccer'), ('tennis', 'Tennis'), ('volleyball', 'Volleyball'),
           ('community_building', 'Community building')]
FILTERS = [('playground', 'Playground'), ('restroom', 'Restrooms'), ('sports', 'Sports fields and courts'), ('water', 'Boat ramp, dock or pier'), ('trail', 'Trail'), ('beach_access', 'Beach access')]
SPORTS = ('baseball', 'basketball', 'football', 'soccer', 'tennis', 'volleyball')


def parks_page(out_dir):
    from page_datasets import parks, boat_ramps, trails, recreation_departments
    from place import governments
    PK, BR, TR, RD = parks(), boat_ramps(), trails(), recreation_departments()
    if not PK:
        return '<div class="page"><h1>Parks</h1><p>No parks on file for this place yet.</p></div>'
    short = {g['key']: g['short'] for g in governments()}
    runner = lambda gid, txt: gov_link(gid, short.get(gid, txt)) if gid else e(txt or '')

    cards, pts = [], []
    for p in sorted(PK, key=lambda p: p['name']):
        tags = [lbl for k, lbl in AMENITY if p.get(k)]
        flags = {'playground': p.get('playground'), 'restroom': p.get('restroom'), 'sports': any(p.get(s) for s in SPORTS),
                 'water': p.get('boat_ramp') or p.get('boat_dock') or p.get('fishing_pier'), 'trail': p.get('trail'), 'beach_access': p.get('beach_access')}
        fac = p.get('facilities')
        sub = ' · '.join(x for x in [p.get('kind'), (f"{p['acres']:g} acres" if p.get('acres') else None)] if x)
        img = f'<img src="{e(p["photo_url"])}" alt="" loading="lazy" referrerpolicy="no-referrer">' if p.get('photo_url') else ''
        cards.append(f'''<article class="od-park" data-g="{e(p.get("gov_id") or "other")}" {" ".join(f'data-{k}="1"' for k, v in flags.items() if v)} data-q="{e((p["name"] + " " + (p.get("address") or "")).lower())}">{img}<div>
  <b>{e(p["name"])}</b><small>{e(p.get("address") or "")}{"<br>" if p.get("address") else ""}Run by {runner(p.get("gov_id"), p.get("run_by"))}{(" · " + e(sub)) if sub else ""}</small>
  {f'<div class="od-tags">{"".join(f"<span>{e(t)}</span>" for t in tags)}</div>' if tags else ""}
  {f"<small>{e(fac)}</small>" if fac and not tags else ""}
  <span class="od-go">{_dir(p.get("latitude"), p.get("longitude"))}</span></div></article>''')
        pts.append({'g': 'park', 'lat': p.get('latitude'), 'lon': p.get('longitude'), 'c': '#2E9E5B', 'r': 6,
                    'html': f'<b>{e(p["name"])}</b>{e(", ".join(tags[:6]) or (p.get("kind") or "Park"))}<br><a href="https://www.google.com/maps/dir/?api=1&destination={p.get("latitude")},{p.get("longitude")}" target="_blank" rel="noopener">Directions</a>'})
    for r in BR:
        pts.append({'g': 'ramp', 'lat': r['latitude'], 'lon': r['longitude'], 'c': '#2563EB', 'r': 6,
                    'html': f'<b>{e(r["name"])}</b>{e(r.get("waterbody") or "")}{(" · " + e(r["water"]) + " water") if r.get("water") else ""}'})
    for t in TR:
        pts.append({'g': 'trail', 'lat': t['latitude'], 'lon': t['longitude'], 'c': '#B7791F', 'r': 5,
                    'html': f'<b>{e(t["name"])}</b>{e(t["miles"])} miles{(" · " + e(t["area"])) if t.get("area") else ""}'})

    gov_ids = [g for g in short if any(p.get('gov_id') == g for p in PK)]
    gov_opts = ''.join(f'<option value="{e(g)}">{e(short[g])} ({sum(1 for p in PK if p.get("gov_id") == g)})</option>' for g in gov_ids)
    n_other = sum(1 for p in PK if not p.get('gov_id'))
    if n_other:
        gov_opts += f'<option value="other">State parks and forest ({n_other})</option>'
    chips = ''.join(f'<button type="button" class="chip" data-v="{k}" aria-pressed="false">{e(lbl)}</button>' for k, lbl in FILTERS)

    ramp_rows = ''.join(f'''<tr><td><b>{e(r["name"])}</b><br><span class="muted" style="font-size:.8rem">{e(r.get("address") or "")}</span></td><td>{e(r.get("waterbody") or "")}<br><span class="muted" style="font-size:.8rem">{e((r.get("water") or "").capitalize())}{" water" if r.get("water") else ""}</span></td>
  <td>{runner(r.get("gov_id"), r.get("run_by"))}</td><td><div class="od-tags">{_yes(r.get("restroom"), "Restrooms")}{_yes(r.get("boat_dock"), "Dock")}{_yes(r.get("fishing_pier"), "Fishing pier")}</div></td><td>{_dir(r["latitude"], r["longitude"])}</td></tr>''' for r in BR)
    trail_rows = ''.join(f'''<tr><td><b>{e(t["name"])}</b>{f'<br><span class="muted" style="font-size:.8rem">{e(t["area"])}</span>' if t.get("area") else ""}</td><td class="n">{t["miles"]:.1f}</td><td>{e(t.get("surface") or "")}</td><td>{e((t.get("uses") or "").capitalize())}</td><td>{e(t.get("skill_level") or "")}</td><td>{_dir(t["latitude"], t["longitude"])}</td></tr>'''
                         for t in sorted(TR, key=lambda t: -t['miles']))
    rec = ''.join(f'''<div><b>{e(d["name"])}</b><span class="muted" style="font-size:.8rem;display:block;margin-bottom:6px">{gov_link(d["gov_id"], d["run_by"]) if d.get("gov_id") else e(d.get("run_by") or "")}</span>
  <a href="{e(d["parks_url"])}" rel="noopener" target="_blank">Parks and facilities</a>{f' · <a href="{e(d["programs_url"])}" rel="noopener" target="_blank">{e(d["programs_label"])}</a>' if d.get("programs_url") and d["programs_url"] != d["parks_url"] else ""}</div>''' for d in RD)

    miles = sum(t['miles'] for t in TR)
    k = lambda lab, v, s: f'<div class="kpi"><span class="eyebrow">{lab}</span><span class="v">{v}</span><span class="s">{s}</span></div>'
    kpis = (k('Public parks', len(PK), f'Run by {len(gov_ids)} local governments and the state') +
            k('With a playground', sum(1 for p in PK if p.get('playground')), f'{sum(1 for p in PK if p.get("restroom"))} have restrooms') +
            k('Boat ramps and launches', len(BR), f'{sum(1 for r in BR if (r.get("water") or "").lower().startswith("salt"))} on salt water') +
            k('Trail miles', f'{miles:,.0f}', f'{len(TR)} named trails, including forest roads in Pine Log'))
    data = json.dumps(pts, ensure_ascii=False).replace('</', '<\\/')

    return f'''<style>{CSS}</style>{LEAFLET}
<div class="page tax od">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Outdoors · Parks</span><h1>Parks, boat ramps and trails</h1>
    <p class="lede">Every public park, boat ramp and trail in the county, from city ball fields to state parks: what each has, who runs it, how to get there, and where to sign up for leagues and programs.</p></div>
    <div class="stamp"><a class="pill" href="/beaches">Beaches →</a><span>From the county's parks inventory</span></div></header>
  <div class="kpis">{kpis}</div>

  <section class="tx-sec"><div class="sec-hd"><h2 id="map" data-tile="Map">Map</h2></div>
    <div class="od-key"><span><i style="background:#2E9E5B"></i>Park</span><span><i style="background:#2563EB"></i>Boat ramp</span><span><i style="background:#B7791F"></i>Trailhead</span></div>
    <div class="od-map" id="odMap" role="img" aria-label="Map of public parks, boat ramps and trails"></div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="parks" data-tile="Parks">Parks</h2><span class="muted">{len(PK)} parks</span></div>
    <div class="od-ctl"><input type="search" id="odQ" placeholder="Search parks by name or street" aria-label="Search parks">
      <select id="odG" aria-label="Who runs it" class="ui-btn" style="min-height:40px"><option value="">Every government</option>{gov_opts}</select></div>
    <div class="chips" id="odF" role="group" aria-label="Has"><button type="button" class="chip" data-v="" aria-pressed="true">Any park</button>{chips}</div>
    <div class="od-parks" id="odParks">{"".join(cards)}</div>
    <p class="note" id="odNone" hidden>No parks match.</p>
    <div><button type="button" class="ui-btn od-morebtn" id="odMore" hidden>Show more</button></div>
    <p class="note">Amenities are from the county's parks inventory and its park guide; a blank doesn't always mean a park lacks something. Tell us about a missing park or a wrong detail with the corrections link at the bottom of the page.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="signup" data-tile="Sign up">Programs, leagues and rentals</h2><span class="muted">Each government runs its own sign-ups</span></div>
    <div class="od-rec">{rec}</div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="ramps" data-tile="Boat ramps">Boat ramps and launches</h2><span class="muted">{len(BR)} public ramps</span></div>
    <details class="tbl-toggle"><summary>All boat ramps and small-craft launches</summary><div class="tablewrap"><table class="tx-table od-tbl"><thead><tr><th>Ramp</th><th>Water</th><th>Run by</th><th>At the ramp</th><th></th></tr></thead><tbody>{ramp_rows}</tbody></table></div></details></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="trails" data-tile="Trails">Trails</h2><span class="muted">{len(TR)} named trails, {miles:,.0f} miles</span></div>
    <details class="tbl-toggle"><summary>All trails, longest first</summary><div class="tablewrap"><table class="tx-table od-tbl"><thead><tr><th>Trail</th><th class="n">Miles</th><th>Surface</th><th>For</th><th>Level</th><th></th></tr></thead><tbody>{trail_rows}</tbody></table></div></details>
    <p class="note">Miles add up each trail's mapped segments, so loops and spurs count once each. Directions go to one end of the trail.</p></section>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>Parks and boat ramps:</b> Bay County's public GIS parks inventory, which covers every city's parks as well as the county's, plus the county's park guide for facility lists and photos.</li>
      <li><b>Trails:</b> the county's and Panama City Beach's public trail maps.</li>
      <li><b>Programs:</b> each government's own parks and recreation pages, checked by hand.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/parks">parks</a> · <a href="/api/v1/datasets/boat-ramps">boat-ramps</a> · <a href="/api/v1/datasets/trails">trails</a> · <a href="/api/v1/datasets/recreation-departments">recreation-departments</a> (CSV on <a href="/open-data">Open data</a>).</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>{MAP_JS}
addEventListener('load', () => {{
  odMap('odMap', {data});
  const cards = [...document.querySelectorAll('#odParks .od-park')], more = document.getElementById('odMore');
  const N = matchMedia('(max-width:760px)').matches ? 8 : 18; let f = '', g = '', q = '', open = false;
  function show() {{
    let n = 0, hit = 0;
    for (const c of cards) {{
      const ok = (!q || c.dataset.q.includes(q)) && (!f || c.dataset[f] === '1') && (!g || c.dataset.g === g);
      if (ok) hit++;
      c.hidden = !ok || (!open && n >= N); if (ok) n++;
    }}
    more.hidden = open || hit <= N; more.textContent = `Show all ${{hit}}`;
    document.getElementById('odNone').hidden = hit > 0;
  }}
  document.getElementById('odQ').addEventListener('input', ev => {{ q = ev.target.value.trim().toLowerCase(); show(); }});
  document.getElementById('odG').addEventListener('change', ev => {{ g = ev.target.value; show(); }});
  const fg = document.getElementById('odF');
  fg.addEventListener('click', ev => {{ const b = ev.target.closest('button'); if (!b) return;
    fg.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); f = b.dataset.v; show(); }});
  more.addEventListener('click', () => {{ open = true; show(); }});
  show();
}});
</script>'''
