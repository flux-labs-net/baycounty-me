"""Building and development (/development) and road projects (/roads).

/development: new homes permitted each year (housing-permits, Census Building Permits Survey) and the development
projects on each government's public planning map (development-projects).
/roads: state road contracts (road-contracts) and FDOT's five-year work program (road-work-program) from FDOT's GIS,
plus the county and city road work paid for by the half-cent sales tax (sales-tax-projects).

All rows come from the datasets in site/page_datasets.py, so the page, the downloads, the database and /api/v1 show the
same thing. Contractors link to their profiles through entity_links (vendor ids from opendata.add_vendor_id).
"""
import datetime as dt
import html
import json
import os

from entity_links import a as link, build
from place import NAME as PLACE_NAME

e = lambda s: html.escape(str(s if s is not None else ''))
HERE = os.path.dirname(os.path.abspath(__file__))


def _money(n):
    if n is None:
        return '—'
    a = abs(n)
    return f'${a / 1e9:.2f}B' if a >= 1e9 else f'${a / 1e6:.1f}M' if a >= 1e6 else f'${round(a / 1e3):,}K' if a >= 1e4 else f'${round(a):,}'


def _date(s, fmt='%b %-d, %Y'):
    try:
        return dt.date.fromisoformat(s[:10]).strftime(fmt)
    except (TypeError, ValueError):
        return ''


def _rows(did):
    import opendata
    fn = {d[0]: d[3] for d in opendata.datasets()}[did]
    return opendata.add_gov_id(did, fn() or [])


CSS = r"""
.gr-ctl{display:flex;flex-wrap:wrap;gap:8px 16px;margin:4px 0 12px}
.gr-wrap{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:16px;align-items:start}
.gr-map{background:var(--surface);border-radius:24px;box-shadow:var(--ui-shadow);padding:10px;position:sticky;top:76px}
.gr-map svg{display:block;width:100%;height:auto}
.gr-map .land{fill:var(--sunken)}
.gr-map .cty{fill:none;stroke:var(--line);stroke-width:1.2}
.gr-map .city{fill:color-mix(in srgb,var(--blue) 7%,transparent);stroke:color-mix(in srgb,var(--blue) 35%,transparent);stroke-width:.6}
.gr-map .lbl{font:600 9px var(--f-body);fill:var(--ink);text-anchor:middle;pointer-events:none;paint-order:stroke;stroke:var(--surface);stroke-width:3px;stroke-linejoin:round;opacity:.85}
.gr-map circle{stroke:var(--surface);stroke-width:1.5;cursor:pointer}
.gr-map a:focus-visible circle,.gr-map circle:hover{stroke:var(--ink);stroke-width:2}
.gr-map [hidden]{display:none}
.gr-leg{display:flex;flex-wrap:wrap;gap:6px 14px;list-style:none;margin:6px 4px 2px;padding:0;font-size:.8rem;color:var(--muted)}
.gr-leg i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:-1px}
.gr-list{display:flex;flex-direction:column;gap:10px;min-width:0}
.gr-card{padding:14px 16px;border-radius:18px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0;scroll-margin-top:90px}
.gr-card:target{outline:2px solid var(--blue);outline-offset:2px}
.gr-card[hidden]{display:none}
.gr-card h3{font-size:1rem;font-weight:600;margin:0;overflow-wrap:anywhere}
.gr-card p{margin:4px 0 0;font-size:.88rem;line-height:1.45}
.gr-card .gr-meta{display:flex;flex-wrap:wrap;gap:4px 14px;margin-top:8px;font-size:.8rem;color:var(--muted)}
.gr-card .gr-meta b{color:var(--ink);font-weight:600}
.gr-pill{display:inline-block;font-size:.72rem;font-weight:600;padding:2px 9px;border-radius:999px;margin-right:6px;vertical-align:1px;background:var(--sunken);color:var(--muted)}
.gr-pill.s-review{background:color-mix(in srgb,var(--gold) 20%,transparent);color:var(--ink)}
.gr-pill.s-ok{background:color-mix(in srgb,var(--teal) 16%,transparent);color:var(--teal)}
.gr-pill.s-go{background:color-mix(in srgb,var(--blue) 14%,transparent);color:var(--blue)}
.gr-more{width:auto;border:0;cursor:pointer;font-family:inherit;align-self:flex-start}
.gr-more[hidden]{display:none}
.gr-bars{display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:6px;align-items:end;height:220px;padding:12px 4px 0;border-bottom:1px solid var(--line)}
.gr-bar{display:flex;flex-direction:column-reverse;gap:2px;height:100%;justify-content:flex-start;position:relative}
.gr-bar span{display:block;border-radius:0}
.gr-bar span:last-child{border-radius:4px 4px 0 0}
.gr-bar .sf{background:var(--blue)}
.gr-bar .mf{background:var(--teal)}
.gr-bar.ytd .sf,.gr-bar.ytd .mf{opacity:.55}
.gr-bar b{position:absolute;left:0;right:0;text-align:center;font:600 .74rem var(--f-body);color:var(--muted);font-variant-numeric:tabular-nums}
.gr-bar:hover span{filter:brightness(1.08)}
.gr-yrs{display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:6px;padding:6px 4px 0;font-size:.74rem;color:var(--muted);text-align:center;font-variant-numeric:tabular-nums}
.gr-tip{position:fixed;z-index:50;pointer-events:none;background:var(--ink);color:var(--surface);font-size:.8rem;line-height:1.4;padding:8px 10px;border-radius:10px;max-width:260px}
.gr-tip[hidden]{display:none}
.gr-tbl td.n,.gr-tbl th.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.gr-tbl td{vertical-align:top}
.gr-prog{height:6px;border-radius:999px;background:var(--sunken);overflow:hidden;margin-top:8px}
.gr-prog span{display:block;height:100%;background:var(--blue);border-radius:999px}
.gr-phases{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.gr-phases span{font-size:.76rem;padding:3px 9px;border-radius:999px;background:var(--sunken)}
.gr-phases span b{font-weight:600}
@media (max-width:860px){.gr-wrap{grid-template-columns:1fr}.gr-map{position:static}.gr-bars{height:170px}.gr-bar b{font-size:.66rem}.gr-yrs{font-size:.66rem}}
"""

JS = r"""
(() => {
  // filter chips + "show more" for each card list, and the map dots that go with it
  document.querySelectorAll('[data-gr-list]').forEach(list => {
    const id = list.dataset.grList, cards = [...list.querySelectorAll('.gr-card')], more = document.getElementById(id + 'More');
    const map = document.getElementById(id + 'Map'), N = matchMedia('(max-width:860px)').matches ? 6 : 10;
    const f = {}; let open = false;
    const ok = c => Object.entries(f).every(([k, v]) => !v || (c.dataset[k] || '').split(' ').includes(v));
    function show() {
      let n = 0;
      for (const c of cards) { const y = ok(c); c.hidden = !y || (!open && n >= N); if (y) n++; }
      if (map) map.querySelectorAll('a[data-id]').forEach(a => { const c = document.getElementById(a.dataset.id); a.hidden = !c || !ok(c); });
      const left = n - N; if (more) { more.hidden = open || left <= 0; more.textContent = `Show ${left} more`; }
      const none = document.getElementById(id + 'None'); if (none) none.hidden = n > 0;
    }
    document.querySelectorAll(`[data-gr-for="${id}"]`).forEach(g => g.addEventListener('click', ev => {
      const b = ev.target.closest('button'); if (!b) return;
      g.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); f[g.dataset.key] = b.dataset.v; open = false; show();
    }));
    if (more) more.addEventListener('click', () => { open = true; show(); });
    if (map) map.addEventListener('click', ev => { const a = ev.target.closest('a[data-id]'); if (!a) return;
      const c = document.getElementById(a.dataset.id); if (c && c.hidden) { open = true; show(); } });
    show();
  });
  // bar chart tooltips
  const tip = document.createElement('div'); tip.className = 'gr-tip'; tip.hidden = true; document.body.appendChild(tip);
  document.querySelectorAll('.gr-bar[data-tip]').forEach(b => {
    const on = ev => { tip.innerHTML = b.dataset.tip; tip.hidden = false; const r = b.getBoundingClientRect();
      tip.style.left = Math.min(innerWidth - 270, Math.max(8, r.left + r.width / 2 - 120)) + 'px'; tip.style.top = Math.max(8, r.top - tip.offsetHeight - 8) + 'px'; };
    b.addEventListener('mouseenter', on); b.addEventListener('focus', on);
    b.addEventListener('mouseleave', () => tip.hidden = true); b.addEventListener('blur', () => tip.hidden = true);
  });
})();
"""


# --- a small map of the county, drawn on the server ------------------------------------------------------------------

def _basemap():
    return json.load(open(os.path.join(HERE, '..', 'geo', 'basemap.json')))


def _map_svg(map_id, points, label):
    """points: (card id, lng, lat, color, title). The county outline, land and city limits from geo/basemap.json."""
    B = _basemap()
    x0, x1, y0, y1 = -86.02, -85.36, 29.92, 30.59
    W = 400
    import math
    k = math.cos(math.radians(30.25))
    H = round(W * (y1 - y0) / ((x1 - x0) * k))
    P = lambda x, y: ((x - x0) / (x1 - x0) * W, (y1 - y) / (y1 - y0) * H)
    path = lambda mp: ''.join('M' + 'L'.join(f'{a:.1f},{b:.1f}' for a, b in (P(*p) for p in ring)) + 'Z' for poly in mp for ring in poly)
    parts = [f'<path class="land" d="{path(B["land"])}"/>', f'<path class="cty" d="{path(B["county"])}"/>']
    for nm, mp in B['cities'].items():
        parts.append(f'<path class="city" d="{path(mp)}"><title>{e(nm)}</title></path>')
    for cid, lng, lat, color, t in points:
        if lng is None or lat is None or not (x0 < lng < x1 and y0 < lat < y1):
            continue
        a, b = P(lng, lat)
        parts.append(f'<a href="#{e(cid)}" data-id="{e(cid)}" aria-label="{e(t)}"><circle cx="{a:.1f}" cy="{b:.1f}" r="4.8" fill="{color}"><title>{e(t)}</title></circle></a>')
    for nm, (x, y), anc in (('Panama City', (-85.64, 30.16), 'middle'), ('Panama City Beach', (-85.88, 30.19), 'middle'), ('Lynn Haven', (-85.65, 30.29), 'middle'),
                            ('Mexico Beach', (-85.40, 29.975), 'end'), ('Youngstown', (-85.43, 30.38), 'middle')):
        a, b = P(x, y)
        parts.append(f'<text class="lbl" x="{a:.0f}" y="{b:.0f}" style="text-anchor:{anc}">{e(nm)}</text>')
    return f'<svg id="{map_id}" viewBox="0 0 {W} {H}" role="img" aria-label="{e(label)}">{"".join(parts)}</svg>'


def _maps_link(r):
    if r.get('lat') and r.get('lng'):
        return f'<a href="https://www.google.com/maps/search/?api=1&query={r["lat"]},{r["lng"]}" rel="noopener" target="_blank">Map</a>'
    return ''


def _kpi(lab, v, s):
    return f'<div class="kpi"><span class="eyebrow">{lab}</span><span class="v">{v}</span><span class="s">{s}</span></div>'


def _chips(list_id, key, opts, label):
    b = ''.join(f'<button type="button" class="chip" data-v="{e(v)}" aria-pressed="{"true" if i == 0 else "false"}">{e(t)}</button>' for i, (v, t) in enumerate(opts))
    return f'<div class="chips" data-gr-for="{list_id}" data-key="{key}" role="group" aria-label="{e(label)}">{b}</div>'


# --- /development ------------------------------------------------------------------------------------------------------

DEV_COLOR = {'Under review': 'var(--gold)', 'Applied': 'var(--gold)', 'Approved': 'var(--teal)', 'Permitted': 'var(--blue)', 'Built': 'var(--blue)', 'Denied': 'var(--salmon)'}
DEV_PILL = {'Under review': 's-review', 'Applied': 's-review', 'Approved': 's-ok', 'Permitted': 's-go', 'Built': 's-go'}


def _permit_chart(rows):
    tot = sorted((r for r in rows if r['area_id'] == 'county-total'), key=lambda r: r['year'])
    if not tot:
        return ''
    top = max(r['total_units'] for r in tot) or 1
    bars, yrs = [], []
    for r in tot:
        sf, mf = r['single_family_units'], r['two_to_four_units'] + r['five_plus_units']
        h = lambda n: f'{n / top * 88:.1f}%'
        tip = (f"<b>{e(r['period'])}</b><br>{r['total_units']:,} new homes permitted<br>Single-family: {sf:,}<br>"
               f"In buildings with 2+ homes: {mf:,}<br>Value on the permits: {_money(r['total_value'])}")
        aria = f"{r['period']}: {r['total_units']:,} homes, {sf:,} single-family and {mf:,} in buildings with 2 or more homes"
        bars.append(f'<div class="gr-bar{" ytd" if r["year_to_date"] else ""}" tabindex="0" data-tip="{e(tip)}" aria-label="{e(aria)}">'
                    f'<span class="sf" style="height:{h(sf)}"></span>{f"<span class=mf style=height:{h(mf)}></span>" if mf else ""}'
                    f'<b style="bottom:calc({h(sf + mf)} + 4px)">{r["total_units"]:,}</b></div>')
        yrs.append(f'<span>{r["year"]}{"*" if r["year_to_date"] else ""}</span>')
    last = tot[-1]
    leg = ('<ul class="gr-leg"><li><i style="background:var(--blue)"></i>Single-family homes</li><li><i style="background:var(--teal)"></i>Homes in buildings with 2 or more units</li>'
           + (f'<li>* {e(last["period"])} so far</li>' if last['year_to_date'] else '') + '</ul>')
    return f'<div style="--n:{len(tot)}"><div class="gr-bars">{"".join(bars)}</div><div class="gr-yrs">{"".join(yrs)}</div></div>{leg}'


def _permit_table(rows):
    years = sorted({r['year'] for r in rows})
    if not years:
        return ''
    full = [y for y in years if not any(r['year'] == y and r['year_to_date'] for r in rows)]
    show = full[-3:] + ([years[-1]] if years[-1] not in full else [])
    areas = []
    for r in rows:
        if r['area_id'] not in [a[0] for a in areas]:
            areas.append((r['area_id'], r['area'], r.get('gov_id')))
    areas.sort(key=lambda a: (a[0] != 'county-total', a[0] != 'county', a[1]))
    by = {(r['area_id'], r['year']): r for r in rows}
    head = ''.join(f'<th class="n">{e(by.get(("county-total", y), {}).get("period", y))}</th>' for y in show)
    body = ''
    for aid, area, gid in areas:
        cells = ''
        for y in show:
            r = by.get((aid, y))
            est = '<sup title="Census Bureau estimate: the government sent no monthly reports">e</sup>' if r and r['estimated'] else ''
            cells += f'<td class="n">{format(r["total_units"], ",") + est if r else "—"}</td>'
        name = f'<b>{e(area)}</b>' if aid == 'county-total' else (link('gov:' + gid, area) if gid and 'gov:' + gid in build().ents and aid != 'county' else e(area))
        body += f'<tr><td>{name}</td>{cells}</tr>'
    all_head = ''.join(f'<th class="n">{y}</th>' for y in years)
    all_body = ''.join('<tr><td>' + e(area) + '</td>' + ''.join(f'<td class="n">{by[(aid, y)]["total_units"]:,}</td>' if (aid, y) in by else '<td class="n">—</td>' for y in years) + '</tr>' for aid, area, _ in areas)
    return (f'<div class="tablewrap"><table class="tx-table gr-tbl"><thead><tr><th>Area</th>{head}</tr></thead><tbody>{body}</tbody></table></div>'
            f'<details class="tbl-toggle"><summary>Every year since 2016</summary><div class="tablewrap"><table class="tx-table gr-tbl"><thead><tr><th>Area</th>{all_head}</tr></thead><tbody>{all_body}</tbody></table></div></details>')


def development_page(out_dir):
    P, D = _rows('housing-permits'), _rows('development-projects')
    if not P and not D:
        return '<div class="page"><h1>Building and development</h1><p>No building or development data for this place yet.</p></div>'
    tot = sorted((r for r in P if r['area_id'] == 'county-total'), key=lambda r: r['year'])
    full = [r for r in tot if not r['year_to_date']]
    ytd = next((r for r in tot if r['year_to_date']), None)
    last, prev = (full[-1] if full else None), (full[-2] if len(full) > 1 else None)
    first = full[0] if full else None
    review = [r for r in D if r['status'] in ('Under review', 'Applied') and r['gov_id'] == 'county']
    approved_recent = [r for r in D if r['status'] == 'Approved' and (r.get('approved_date') or '') >= f'{dt.date.today().year - 1}-01-01']
    unin = [r for r in P if r['area_id'] == 'county' and last and r['year'] == last['year']]
    share = round(unin[0]['total_units'] / last['total_units'] * 100) if unin and last and last['total_units'] else None

    kpis = ''
    if last:
        chg = f"{'up' if last['total_units'] >= prev['total_units'] else 'down'} {abs(round((last['total_units'] / prev['total_units'] - 1) * 100))}% from {prev['year']}" if prev and prev['total_units'] else ''
        kpis += _kpi(f'New homes permitted, {last["year"]}', f'{last["total_units"]:,}', chg + (f'. {share}% outside the cities' if share is not None else ''))
    if ytd:
        kpis += _kpi(f'{ytd["period"]}', f'{ytd["total_units"]:,}', f'New homes permitted so far, worth {_money(ytd["total_value"])} on the permits')
    kpis += _kpi('Projects under review', len(review), 'Development orders the county is reviewing now')
    kpis += _kpi('Approved since ' + str(dt.date.today().year - 1), len(approved_recent), 'Site plans and subdivisions cleared to build')

    # development cards + map
    govs = []
    for r in D:
        if r['gov_id'] and (r['gov_id'], r['government']) not in govs:
            govs.append((r['gov_id'], r['government']))
    cards, pts = [], []
    for r in D:
        cid = 'dev-' + ''.join(c if c.isalnum() else '-' for c in r['project_id'])
        st = r['status']
        dates = [('Applied', r.get('applied_date')), ('Approved', r.get('approved_date')), ('Building permit', r.get('permit_date')), ('Occupancy', r.get('occupancy_date'))]
        meta = [f'{k} <b>{_date(v)}</b>' for k, v in dates if v]
        if r.get('size'):
            meta.append(f'Size <b>{e(r["size"])}</b>')
        if r.get('case_number'):
            meta.append(f'Case {e(r["case_number"])}')
        links = ' · '.join(x for x in [_maps_link(r), f'<a href="{e(r["plans_url"])}" rel="noopener" target="_blank">Plans</a>' if r.get('plans_url') else '',
                                       f'<a href="{e(r["source_page"])}" rel="noopener" target="_blank">{e(r["government"])} planning</a>'] if x)
        kind = 'review' if st in ('Under review', 'Applied') else 'approved' if st == 'Approved' else 'built' if st in ('Permitted', 'Built') else 'other'
        cards.append(f'''<article class="gr-card" id="{cid}" data-status="{kind}" data-gov="{e(r["gov_id"])}">
  <h3><span class="gr-pill {DEV_PILL.get(st, "")}">{e(st)}</span>{e(r["name"])}</h3>
  <p>{e(r.get("description") or "")}{(" · " if r.get("description") and r.get("location") else "") + e(r.get("location") or "")}</p>
  <div class="gr-meta">{"".join(f"<span>{m}</span>" for m in meta)}</div>
  <div class="gr-meta"><span>{e(r["government"])}</span><span>{links}</span></div></article>''')
        pts.append((cid, r.get('lng'), r.get('lat'), DEV_COLOR.get(st, 'var(--faint)'), f'{r["name"]} ({st})'))
    dev_map = _map_svg('devMap', pts, f'Map of development projects in {PLACE_NAME}')
    leg = ''.join(f'<li><i style="background:{c}"></i>{t}</li>' for t, c in (('Under review', 'var(--gold)'), ('Approved', 'var(--teal)'), ('Permitted or built', 'var(--blue)')))
    status_chips = _chips('dev', 'status', [('', 'All'), ('review', 'Under review'), ('approved', 'Approved'), ('built', 'Permitted or built')], 'Status')
    gov_chips = _chips('dev', 'gov', [('', 'Everywhere')] + govs, 'Government')
    layers = sorted({(r['source'], r['source_page'], r['fetched']) for r in D})
    pcb_last = max((max(x for x in (r.get('applied_date'), r.get('approved_date'), r.get('permit_date'), r.get('occupancy_date')) if x) for r in D if r['gov_id'] == 'pcb'), default=None)

    return f'''<style>{CSS}</style>
<div class="page tax gr">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Living here · Growth</span><h1>Building and development</h1>
    <p class="lede">How many new homes are being permitted in {e(PLACE_NAME)} each year, city by city, and the commercial buildings, subdivisions and apartments working their way through planning review.</p></div>
    <div class="stamp"><a class="pill" href="/roads">Road projects →</a><span>Permits through {e(ytd["period"].split(" to ")[-1] if ytd else (last["period"] if last else ""))} · projects as of {e(_date(max((r["fetched"] for r in D), default="")))}</span></div></header>
  <div class="kpis">{kpis}</div>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>How a project gets built</h2>
    <ol class="ex-steps"><li><b>Zoning says what can go where.</b> Changing it (a rezoning or land use change) takes a public hearing before the planning board and a vote of the commission. Those votes are on <a href="/public-money/votes">How they voted</a> and the agendas on <a href="/meetings">Meetings</a>.</li>
    <li><b>A site plan gets a development order.</b> Bigger projects such as shopping centers, subdivisions and apartments file a site plan. Planning staff review it against the rules and issue a development order when it passes.</li>
    <li><b>Then come building permits.</b> Each building needs a permit and inspections. The Census Bureau counts the new homes those permits allow every month, which is the yearly count below.</li></ol></div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="homes" data-tile="New homes">New homes permitted each year</h2><span class="muted">All of {e(PLACE_NAME)}, from the Census Bureau's Building Permits Survey</span></div>
    {_permit_chart(P)}
    <p class="note">{f"Since {first['year']}, permits have allowed {sum(r['total_units'] for r in tot):,} new homes countywide." if first else ""} Counts are homes (units) authorized by permits, not finished homes. Mobile homes are not counted.</p>
    <h3 class="ch-grp" style="margin-top:14px">By city</h3>
    {_permit_table(P)}
    <p class="note">e: the Census Bureau's estimate, because that government sent no monthly permit reports that year. Lynn Haven, Callaway, Springfield and Panama City are often estimated. Unincorporated means outside every city, where the county issues the permits.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="projects" data-tile="Projects">Development projects</h2><span class="muted">{len(D)} projects since 2016 on the planning maps</span></div>
    <div class="gr-ctl">{status_chips}{gov_chips}</div>
    <div class="gr-wrap">
      <div class="gr-map">{dev_map}<ul class="gr-leg">{leg}</ul></div>
      <div class="gr-list" data-gr-list="dev">{"".join(cards)}
        <p class="note" id="devNone" hidden>No projects match.</p>
        <button type="button" class="ui-btn gr-more" id="devMore" hidden>Show more</button></div>
    </div>
    <p class="note">Bay County's map covers the unincorporated county, where the county is the planning authority. Panama City Beach's map{f" was last updated in {pcb_last[:4]}" if pcb_last else ""}, so its newer projects are missing, and the other cities don't publish a development map. Owners and developers are not named on these maps.</p></section>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>New homes</b>: the U.S. Census Bureau's <a href="https://www.census.gov/construction/bps/" rel="noopener" target="_blank">Building Permits Survey</a>, which every permit office reports to monthly. Yearly files for 2016 on, and this year's file through the latest month posted. Checked weekly.</li>
      {"".join(f'<li><b>{e(s)}</b>: the government\'s public planning map, read weekly. See <a href="{e(p)}" rel="noopener" target="_blank">its planning page</a>. Projects with no date, or nothing on record since 2016, are left out.</li>' for s, p, _ in layers)}
      <li><b>Individual building permits</b> are in each government's permit portal. Bay County's portal asks for a picture code before every search, so permits are not copied here one by one; the Census counts above are the same permits, totalled.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/housing-permits">housing-permits</a> (<a href="/downloads/housing-permits.csv">CSV</a>) · <a href="/api/v1/datasets/development-projects">development-projects</a> (<a href="/downloads/development-projects.csv">CSV</a>).</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>{JS}</script>'''


# --- /roads ------------------------------------------------------------------------------------------------------------

ROAD_CATS = ('Resurfacing', 'Road Rehabilitation from Hurricane Michael', 'Local Road Microsurfacing', 'Utility  and Road Improvement', 'Dirt Road Stabilization',
             'Local Road Reconstruction', 'Capacity Improvement', 'Projected Resurfacing and Reconstruction', 'Roadway Safety', 'Bridge Repair', 'Intersection Improvement')
PHASE_ORDER = ['Planning', 'PD&E', 'Environmental', 'Preliminary Engineering', 'Right of Way', 'Construction', 'Construction Support', 'Capital']
PHASE_LABEL = {'PD&E': 'Study (PD&E)', 'Preliminary Engineering': 'Design', 'Construction Support': 'Construction inspection', 'Capital': 'Capital grant'}


def _contractor(r):
    nm = r.get('contractor')
    if not nm:
        return ''
    import ids
    nice = ids.biz_case(nm)
    G = build()
    if r.get('vendor_id') and 'vendor:' + r['vendor_id'] in G.ents:
        return link('vendor:' + r['vendor_id'], G.ents['vendor:' + r['vendor_id']]['name'])
    from entity_graph import _slug
    bid = 'business:' + _slug(nm)
    return link(bid, nice) if bid in G.ents else e(nice)


def _sstatus(r):
    if r['status'] != 'in_progress':
        return 'Next'
    return 'In progress' + (f" ({r['pct_complete']}%)" if r.get('pct_complete') else '')


def _progress(r):
    try:
        s, f = dt.date.fromisoformat(r['work_began_date']), dt.date.fromisoformat(r['estimated_completion_date'])
    except (TypeError, ValueError):
        return ''
    pct = max(0, min(100, round((dt.date.today() - s).days / max(1, (f - s).days) * 100)))
    return f'<div class="gr-prog" role="img" aria-label="{pct}% of the scheduled time has passed"><span style="width:{pct}%"></span></div>'


def roads_page(out_dir):
    C, W = _rows('road-contracts'), _rows('road-work-program')
    S = [r for r in _rows('sales-tax-projects') if r.get('category') in ROAD_CATS]
    if not C and not W:
        return '<div class="page"><h1>Road projects</h1><p>No road project data for this place yet.</p></div>'
    now = [r for r in C if r['status'] == 'Under way']
    done = [r for r in C if r['status'] == 'Complete']
    projects = {}
    for w in W:
        projects.setdefault(w['project_id'], []).append(w)
    s_now = [r for r in S if r['status'] == 'in_progress']
    s_next = [r for r in S if r['status'] == 'not_started']
    s_done = [r for r in S if r['status'] == 'completed']
    fetched = max((r['fetched'] for r in C), default='')
    district = 'https://www.nwflroads.com/'

    kpis = (_kpi('State road work under way', len(now), f'{_money(sum(r["amount"] or 0 for r in now))} in FDOT contracts') +
            _kpi('In the state\'s five-year plan', len(projects), 'FDOT projects funded from FY' + str(min((w['first_fiscal_year'] for w in W if w['first_fiscal_year']), default='')) + ' on') +
            _kpi('County and city road jobs', len(s_now) + len(s_next), f'In progress or next, paid for by the half-cent sales tax') +
            _kpi('State contracts since 2016', len(C), f'{_money(sum(r["amount"] or 0 for r in C))} in all'))

    # contracts under way: cards + map
    cards, pts = [], []
    for r in sorted(now, key=lambda r: -(r['amount'] or 0)):
        cid = 'fdot-' + r['contract_id']
        meta = [f'Contract <b>{_money(r["amount"])}</b>', f'Started <b>{_date(r["work_began_date"])}</b>' if r.get('work_began_date') else f'Let <b>{_date(r["let_date"])}</b>',
                f'Finish by <b>{_date(r["estimated_completion_date"])}</b>' if r.get('estimated_completion_date') else '',
                f'{r["length_miles"]:.1f} miles' if r.get('length_miles') else '']
        cards.append(f'''<article class="gr-card" id="{cid}" data-kind="now">
  <h3>{e(r["description"])}</h3>
  <div class="gr-meta"><span>Contractor: {_contractor(r)}</span><span>{e(r["contract_type"])} · FDOT contract {e(r["contract_id"])}</span></div>
  <div class="gr-meta">{"".join(f"<span>{m}</span>" for m in meta if m)}</div>{_progress(r)}
  <div class="gr-meta"><span>{_maps_link(r)}</span><span><a href="{e(r.get("website") or district)}" rel="noopener" target="_blank">Project updates (FDOT District 3)</a></span></div></article>''')
        pts.append((cid, r.get('lng'), r.get('lat'), 'var(--blue)', r['description']))
    road_map = _map_svg('nowMap', pts, f'Map of state road work under way in {PLACE_NAME}')

    # five-year work program, one card per project with its phases
    wp = []
    for pid, ws in sorted(projects.items(), key=lambda kv: (min(w['first_fiscal_year'] or 9999 for w in kv[1]), kv[0])):
        ws.sort(key=lambda w: (PHASE_ORDER.index(w['phase']) if w['phase'] in PHASE_ORDER else 99))
        ph = ''.join(f'<span><b>{e(PHASE_LABEL.get(w["phase"], w["phase"]))}</b> FY{w["first_fiscal_year"]}' + (f'–{str(w["last_fiscal_year"])[2:]}' if w['last_fiscal_year'] != w['first_fiscal_year'] else '') + '</span>' for w in ws if w['first_fiscal_year'])
        kinds = ' '.join(sorted({'build' if w['phase'] == 'Construction' else 'design' if w['phase'] in ('PD&E', 'Preliminary Engineering', 'Planning', 'Environmental') else 'row' if w['phase'] == 'Right of Way' else 'other' for w in ws}))
        st = ws[0].get('project_status') or ''
        wp.append(f'''<article class="gr-card" id="wp-{e(pid)}" data-phase="{kinds}">
  <h3>{e(ws[0]["description"])}</h3>
  <div class="gr-meta"><span>{e(ws[0].get("work_type") or "")}</span><span>FDOT project {e(pid)}</span>{f"<span>{e(st)}</span>" if st else ""}{f"<span>{ws[0]['length_miles']:.1f} miles</span>" if ws[0].get('length_miles') else ""}</div>
  <div class="gr-phases">{ph}</div></article>''')
    phase_chips = _chips('wp', 'phase', [('', 'All'), ('build', 'Construction'), ('design', 'Study or design'), ('row', 'Buying land')], 'Phase')

    # county and city road work from the sales tax
    cost = lambda r: r.get('actual_cost') or r.get('programmed_cost') or r.get('promised_cost')
    srow = lambda r: (f'<tr><td>{e(r["name"])}<br><span class="muted" style="font-size:.8rem">{e(r["category"].replace("  ", " "))}</span></td><td>{e(r["government"])}</td>'
                      f'<td>{_sstatus(r)}</td><td class="n">{_money(cost(r))}</td></tr>')
    ordered = sorted(s_now + s_next, key=lambda r: (r['status'] != 'in_progress', -(cost(r) or 0), r['name']))
    srows = ''.join(srow(r) for r in ordered[:12])
    srows_more = ''.join(srow(r) for r in ordered[12:])

    # who builds them
    agg = {}
    for r in C:
        k = r.get('vendor_id') or r.get('contractor')
        if not k:
            continue
        a = agg.setdefault(k, {'r': r, 'n': 0, 'amt': 0.0, 'now': 0})
        a['n'] += 1
        a['amt'] += r['amount'] or 0
        a['now'] += r['status'] == 'Under way'
    G = build()
    local = {}
    for x in G.links.values():
        if x['relation'] == 'paid' and x['amount'] and x['from_id'].startswith('gov:'):
            local[x['to_id']] = local.get(x['to_id'], 0) + x['amount']
    crow = ''.join(f'<tr><td>{_contractor(a["r"])}</td><td class="n">{a["n"]}</td><td class="n">{a["now"] or "—"}</td><td class="n">{_money(a["amt"])}</td>'
                   f'<td class="n">{_money(local.get("vendor:" + a["r"]["vendor_id"])) if a["r"].get("vendor_id") and local.get("vendor:" + a["r"]["vendor_id"]) else "—"}</td></tr>'
                   for a in sorted(agg.values(), key=lambda a: -a['amt'])[:15])
    drow = ''.join(f'<tr><td>{e(r["description"])}</td><td>{_contractor(r)}</td><td>{_date(r.get("final_acceptance_date") or r.get("ended_date") or r.get("estimated_completion_date"), "%b %Y")}</td><td class="n">{_money(r["amount"])}</td></tr>'
                   for r in sorted(done, key=lambda r: r.get('final_acceptance_date') or r.get('ended_date') or r.get('estimated_completion_date') or '', reverse=True))

    return f'''<style>{CSS}</style>
<div class="page tax gr">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Living here · Getting around</span><h1>Road projects</h1>
    <p class="lede">State highway work under way in {e(PLACE_NAME)} and what each contract costs, what the Florida Department of Transportation plans for the next five years, and the county and city road jobs paid for by the half-cent sales tax.</p></div>
    <div class="stamp"><a class="pill" href="https://fl511.com/" rel="noopener" target="_blank">Live lane closures (FL511) →</a><span>FDOT data as of {e(_date(fetched))}</span></div></header>
  <div class="kpis">{kpis}</div>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>Who fixes which road</h2>
    <ol class="ex-steps"><li><b>The state runs the highways.</b> State roads such as US 98, US 231, SR 77 and SR 390 belong to the Florida Department of Transportation (FDOT). Its District 3 office in Chipley plans and hires the work, mostly with state fuel tax and federal money.</li>
    <li><b>The county and cities run the rest.</b> Neighborhood streets and county roads are theirs. Much of that paving is paid for by the half-cent infrastructure sales tax voters approved in 2016.</li>
    <li><b>The plan comes first.</b> Each year FDOT adopts a five-year work program: a study, then design, then buying land, then construction. A project's construction year can move as money changes.</li></ol></div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="now" data-tile="Under way">State road work under way</h2><span class="muted">{len(now)} FDOT contracts, largest first</span></div>
    <div class="gr-wrap">
      <div class="gr-map">{road_map}<ul class="gr-leg"><li><i style="background:var(--blue)"></i>Contract under way (dot at the start of the work)</li></ul></div>
      <div class="gr-list" data-gr-list="now">{"".join(cards)}
        <button type="button" class="ui-btn gr-more" id="nowMore" hidden>Show more</button></div>
    </div>
    <p class="note">The bar under each project shows how much of the scheduled time has passed, not how much work is done. Contract amounts are the current amount of every funding line on the contract, with any changes FDOT has approved.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="plan" data-tile="Five-year plan">Coming up: FDOT's five-year work program</h2><span class="muted">{len(projects)} projects</span></div>
    <div class="gr-ctl">{phase_chips}</div>
    <div class="gr-list" data-gr-list="wp" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr))">{"".join(wp)}</div>
    <p class="note" id="wpNone" hidden>No projects match.</p>
    <div><button type="button" class="ui-btn gr-more" id="wpMore" hidden>Show more</button></div>
    <p class="note">FY is the state fiscal year, July to June, named for the year it ends (FY2027 = July 2026 to June 2027). FDOT's map layers don't give each phase's dollars; the full budget for each project is in FDOT's <a href="https://www.fdot.gov/workprogram/" rel="noopener" target="_blank">work program</a>.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="local" data-tile="County and city">County and city road work</h2><span class="muted">From the half-cent sales tax map</span></div>
    <p>{len(s_done):,} county and city road jobs paid for by the sales tax are finished; {len(s_now)} are in progress and {len(s_next)} are next. The <a href="/public-money/sales-tax-projects">sales tax page</a> has every job on a map, with what was promised.</p>
    <div class="tablewrap"><table class="tx-table gr-tbl"><thead><tr><th>Project</th><th>Government</th><th>Status</th><th class="n">Cost</th></tr></thead><tbody>{srows or '<tr><td colspan="4" class="muted">None on record.</td></tr>'}</tbody></table></div>
    {f'<details class="tbl-toggle"><summary>{len(ordered) - 12} more in progress or next</summary><div class="tablewrap"><table class="tx-table gr-tbl"><thead><tr><th>Project</th><th>Government</th><th>Status</th><th class="n">Cost</th></tr></thead><tbody>{srows_more}</tbody></table></div></details>' if srows_more else ''}</section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="contractors" data-tile="Contractors">Who builds the state's roads here</h2><span class="muted">FDOT contracts since 2016</span></div>
    <div class="tablewrap"><table class="tx-table gr-tbl"><thead><tr><th>Contractor</th><th class="n">Contracts</th><th class="n">Under way</th><th class="n">State contracts</th><th class="n">Paid by local governments</th></tr></thead><tbody>{crow}</tbody></table></div>
    <p class="note">Each name links to a profile with its local contracts, payments and campaign gifts. "Paid by local governments" adds every local payment record on the site for the same company, for comparison.</p>
    <details class="tbl-toggle"><summary>Finished state contracts since 2016 ({len(done)})</summary><div class="tablewrap"><table class="tx-table gr-tbl"><thead><tr><th>Project</th><th>Contractor</th><th>Finished</th><th class="n">Amount</th></tr></thead><tbody>{drow}</tbody></table></div></details></section>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>State contracts</b>: FDOT's public map of every construction and maintenance contract, read weekly. FDOT leaves some old contracts marked active; a contract counts as under way here only when FDOT's map flags it active, and as finished once its final acceptance or estimated finish date has passed.</li>
      <li><b>Five-year plan</b>: FDOT's current adopted work program layers, read weekly: each project's phases and the fiscal years they're funded in.</li>
      <li><b>County and city work</b>: the county's half-cent sales tax project map, the same data as the <a href="/public-money/sales-tax-projects">sales tax page</a>.</li>
      <li><b>Lane closures</b> change by the hour, so they aren't copied here; <a href="https://fl511.com/" rel="noopener" target="_blank">FL511</a> has them live.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/road-contracts">road-contracts</a> (<a href="/downloads/road-contracts.csv">CSV</a>) · <a href="/api/v1/datasets/road-work-program">road-work-program</a> (<a href="/downloads/road-work-program.csv">CSV</a>) · <a href="/api/v1/datasets/sales-tax-projects">sales-tax-projects</a>.</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>{JS}</script>'''
