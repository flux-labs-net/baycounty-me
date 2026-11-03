"""Charts and the town picker for /public-safety (site/safety_page.py). Plain SVG built at page time; every mark has
a tooltip (<title>) and the full numbers stay in the tables below the charts.

Colors: two series slots, checked with the dataviz palette validator against the site's light (#FFFFFF) and dark
(#151C27) surfaces: police blue #2a78d6 / #3987e5, fire orange #eb6834 / #d95926. Florida is a muted dashed line.
"""
import html
from collections import defaultdict

from entity_links import gov

e = lambda s: html.escape(str(s if s is not None else ''))
NEW_SYSTEM = 2025  # Florida agencies switched from yearly summaries to monthly incident reports (NIBRS)

CSS = r"""
.ps{--ps-1:#2a78d6;--ps-2:#eb6834;--ps-ref:var(--muted)}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) .ps{--ps-1:#3987e5;--ps-2:#d95926}}
:root[data-theme="dark"] .ps{--ps-1:#3987e5;--ps-2:#d95926}
.ps-svg{width:100%;height:auto;display:block;overflow:visible}
.ps-svg text{font:11px var(--f-body);fill:var(--muted)}

.ps-bars{display:flex;flex-direction:column;gap:12px}
.ps-bar{display:grid;grid-template-columns:minmax(120px,190px) 1fr 56px;gap:10px;align-items:center;font-size:.9rem}
.ps-bar.two{grid-template-columns:minmax(120px,190px) 1fr}
.ps-bar .lab{text-align:right;color:var(--ink);line-height:1.25}
.ps-bar .lab small{display:block;color:var(--muted);font-size:.76rem}
.ps-bar .pair{display:grid;grid-template-columns:1fr 64px;gap:4px 10px;align-items:center}
.ps-bar .trk{display:block;height:14px;border-radius:4px;background:var(--sunken)}
.ps-bar .trk i{display:block;height:100%;border-radius:4px;min-width:2px}
.ps-bar .trk i.b1{background:var(--ps-1)}.ps-bar .trk i.b2{background:var(--ps-2)}
.ps-bar .v{font-weight:600;font-variant-numeric:tabular-nums}
@media (max-width:760px){.ps-bar,.ps-bar.two{grid-template-columns:1fr}.ps-bar{grid-template-columns:1fr 48px}.ps-bar .lab{grid-column:1/-1;text-align:left}}
.ps-svg .val{fill:var(--ink);font-weight:600;font-variant-numeric:tabular-nums}
.ps-svg .grid{stroke:var(--line);stroke-width:1}
.ps-svg .ln{fill:none;stroke:var(--ps-1);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.ps-svg .ref{fill:none;stroke:var(--ps-ref);stroke-width:1.5;stroke-dasharray:4 4;opacity:.8}
.ps-svg .dot{fill:var(--ps-1);stroke:var(--surface);stroke-width:2}
.ps-svg .hit{fill:transparent}
.ps-svg .hit:hover+.dot,.ps-svg .dot:hover{r:5}
.ps-svg .new{fill:var(--sunken)}
.ps-svg .b1{fill:var(--ps-1)}.ps-svg .b2{fill:var(--ps-2)}
.ps-multi{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.ps-panel{padding:14px 16px 10px;border-radius:18px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.ps-panel h3{margin:0;font-size:.95rem;font-weight:600}
.ps-panel p{margin:2px 0 6px;font-size:.8rem;color:var(--muted)}
.ps-key{display:flex;gap:16px;flex-wrap:wrap;font-size:.84rem;color:var(--muted);margin:0 0 10px}
.ps-key i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:6px;vertical-align:3px;background:var(--ps-1)}
.ps-key i.ref{background:none;border-top:2px dashed var(--ps-ref);height:0;border-radius:0}
.ps-key i.sq{width:10px;height:10px;border-radius:3px;vertical-align:-1px}
.ps-key i.f{background:var(--ps-2)}
.ps-key i.new{background:var(--sunken);height:10px;width:14px;vertical-align:-1px;border:1px solid var(--line)}
.ps-chartcard{padding:18px;border-radius:22px;background:var(--surface);box-shadow:var(--ui-shadow)}
.ps-trend[hidden],.ps-solved[hidden],.ps-town[hidden]{display:none}
.ps-towns{margin-bottom:12px}
.ps-town{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.ps-tc{padding:18px;border-radius:20px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0;display:flex;flex-direction:column;gap:6px}
.ps-tc .eyebrow{font-size:.74rem}
.ps-tc b{font-size:1.02rem;font-weight:600;line-height:1.3}
.ps-tc .big{font:600 1.6rem var(--f-display);font-variant-numeric:tabular-nums;line-height:1.1}
.ps-tc .big small{font:400 .82rem var(--f-body);color:var(--muted);margin-left:4px}
.ps-tc p{margin:0;font-size:.86rem;line-height:1.45;color:var(--muted)}
.ps-tc .row{display:flex;gap:18px;flex-wrap:wrap}
@media (max-width:760px){.ps-town{grid-template-columns:1fr}}
"""

JS = r"""
(() => {
  const pick = (id, sel, attr) => { const g = document.getElementById(id); if (!g) return;
    g.addEventListener('click', ev => { const b = ev.target.closest('button'); if (!b) return;
      g.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b));
      document.querySelectorAll(sel).forEach(t => t.hidden = t.dataset[attr] !== b.dataset.v);
      if (id === 'psTown') try { localStorage.setItem('ps-town', b.dataset.v); } catch (_) {} }); };
  pick('psTown', '.ps-town', 'g'); pick('psTrendPick', '.ps-trend,.ps-solved', 'o');
  // a signed-in reader starts on their home's town, others on the town they last picked
  const start = () => { let t = null; try { t = localStorage.getItem('ps-town'); } catch (_) {}
    const h = window.BCHomeCity && window.BCHomeCity(); if (h) t = h.gov;
    const b = t && document.querySelector(`#psTown button[data-v="${t}"]`); if (b) b.click(); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
"""


def _nice(v):
    for step in (1, 2, 2.5, 5, 10, 20, 25, 50, 100):
        if v <= step * 4:
            return step, step * (int(v / step) + 1)
    return 100, 100 * (int(v / 100) + 1)


def full_years(C, code):
    """{agency_id: {year: row}} for full reported years of one offense."""
    out = defaultdict(dict)
    for r in C:
        if r['offense_code'] == code and r['count'] is not None and r['months_reported'] == 12 and r['per_1000'] is not None:
            out[r['agency_id']][r['year']] = r
    return out


def short_name(name):
    """'Panama City Police Department' -> 'Panama City police', for small chart titles."""
    return (name.replace(' Police Department (reported until 2019)', ' police (until 2019)').replace(' Police Department', ' police')
            .replace('Bay County Sheriff\'s Office', 'Sheriff\'s Office'))


def _panel(name, sub, rows, state, years, ymax, step, label):
    W, H, L, R, T, B = 300, 150, 30, 40, 10, 22
    x = lambda y: L + (y - years[0]) * (W - L - R) / max(1, years[-1] - years[0])
    yv = lambda v: T + (H - T - B) * (1 - v / ymax)
    out = []
    if years[-1] >= NEW_SYSTEM:
        x0 = x(NEW_SYSTEM) - (x(years[0] + 1) - x(years[0])) / 2
        out.append(f'<rect class="new" x="{x0:.1f}" y="{T}" width="{W - R - x0 + 4:.1f}" height="{H - T - B}" rx="4"><title>From {NEW_SYSTEM}: monthly incident reports, not directly comparable with earlier years</title></rect>')
    v = 0
    while v <= ymax + 1e-9:
        out.append(f'<line class="grid" x1="{L}" x2="{W - R + 4}" y1="{yv(v):.1f}" y2="{yv(v):.1f}"/><text x="{L - 6}" y="{yv(v) + 4:.1f}" text-anchor="end">{v:g}</text>')
        v += step
    for y in sorted({years[0], 2020, years[-1]}):
        if years[0] <= y <= years[-1]:
            out.append(f'<text x="{x(y):.1f}" y="{H - 6}" text-anchor="middle">{y}</text>')
    # Florida reference, broken where missing
    seg, segs = [], []
    for y in years:
        if state.get(y) is not None:
            seg.append(f'{x(y):.1f},{yv(state[y]):.1f}')
        elif seg:
            segs.append(seg); seg = []
    if seg:
        segs.append(seg)
    out += [f'<path class="ref" d="M{" L".join(s)}"><title>Florida</title></path>' for s in segs if len(s) > 1]
    # the agency, broken at years it did not report
    seg, segs = [], []
    for y in years:
        if y in rows:
            seg.append(y)
        elif seg:
            segs.append(seg); seg = []
    if seg:
        segs.append(seg)
    for s in segs:
        if len(s) > 1:
            out.append(f'<path class="ln" d="M{" L".join(f"{x(y):.1f},{yv(rows[y]["per_1000"]):.1f}" for y in s)}"/>')
    for y in sorted(rows):
        r = rows[y]
        fl = f'; Florida {state[y]:g}' if state.get(y) is not None else ''
        t = f'{y}: {r["per_1000"]:g} {label.lower()}s per 1,000 people ({r["count"]:,} reported){fl}'
        out.append(f'<circle class="hit" cx="{x(y):.1f}" cy="{yv(r["per_1000"]):.1f}" r="9"><title>{e(t)}</title></circle>'
                   f'<circle class="dot" cx="{x(y):.1f}" cy="{yv(r["per_1000"]):.1f}" r="3.5"><title>{e(t)}</title></circle>')
    if rows:
        ly = max(rows)
        out.append(f'<text class="val" x="{x(ly) + 8:.1f}" y="{yv(rows[ly]["per_1000"]) + 4:.1f}">{rows[ly]["per_1000"]:g}</text>')
    last = f'latest {max(rows)}' if rows else 'no full year reported'
    aria = f'{name}: {label.lower()}s per 1,000 people, {", ".join(f"{y} {rows[y]["per_1000"]:g}" for y in sorted(rows))}'
    return (f'<div class="ps-panel"><h3>{e(name)}</h3><p>{sub} · {e(last)}</p>'
            f'<svg class="ps-svg" viewBox="0 0 {W} {H}" role="img" aria-label="{e(aria)}">{"".join(out)}</svg></div>')


def trends(C, state_rates, agencies, code, label, hidden):
    """Small multiples: one panel per agency, its rate per 1,000 people and Florida's, same scale in every panel."""
    fy = full_years(C, code)
    st = {int(y): v[code] / 100 for y, v in state_rates.items() if code in v}
    years = sorted({y for a in fy.values() for y in a})
    if not years:
        return ''
    ymax_raw = max([r['per_1000'] for a in fy.values() for r in a.values()] + [v for y, v in st.items() if y in years])
    step, ymax = _nice(ymax_raw)
    panels = ''.join(_panel(short_name(name), gov(g), fy.get(aid, {}), st, years, ymax, step, label) for aid, name, g in agencies if fy.get(aid))
    return f'<div class="ps-trend" data-o="{code}"{" hidden" if hidden else ""}><div class="ps-multi">{panels}</div></div>'


def solved(C, agencies, code, label, hidden, years_back=3):
    """Share of offenses cleared over each agency's latest three full years (yearly summaries, before 2025)."""
    fy = full_years(C, code)
    bars = []
    for aid, name, g in agencies:
        ys = sorted(y for y in fy.get(aid, {}) if y < NEW_SYSTEM)[-years_back:]
        n = sum(fy[aid][y]['count'] for y in ys)
        c = sum(fy[aid][y]['cleared'] or 0 for y in ys)
        if n >= 20:
            bars.append((name, c / n, c, n, f'{ys[0]}–{ys[-1]}' if len(ys) > 1 else str(ys[0])))
    if not bars:
        return ''
    bars.sort(key=lambda b: -b[1])
    rows = ''.join(
        f'<div class="ps-bar"><span class="lab">{e(short_name(name))}<small>{span}</small></span>'
        f'<span class="trk" title="{e(f"{c:,} of {n:,} {label.lower()}s cleared, {span}")}"><i class="b1" style="width:{max(100 * p, .5):.1f}%"></i></span>'
        f'<span class="v">{round(100 * p)}%</span></div>' for name, p, c, n, span in bars)
    return (f'<div class="ps-solved ps-bars" data-o="{code}"{" hidden" if hidden else ""} role="img" aria-label="Share of {label.lower()}s cleared by each agency">{rows}</div>')


def per_resident(A, order):
    """Paired bars: police and fire budget per resident, one pair per government."""
    by = defaultdict(dict)
    for r in A:
        by[r['gov_id']][r['service']] = r
    rows = [g for g in order if any((by[g].get(s) or {}).get('cost_per_resident') for s in ('police', 'fire'))]
    top = max((by[g][s]['cost_per_resident'] or 0) for g in rows for s in by[g])
    out = []
    for g in rows:
        name = (by[g].get('police') or by[g].get('fire'))['government']
        pair = ''
        for s, cls in (('police', 'b1'), ('fire', 'b2')):
            r = by[g].get(s)
            if not r or not r['cost_per_resident']:
                continue
            t = f'{name} {s}: ${r["cost_per_resident"]:,.0f} per resident (${r["budget_amount"]:,.0f} over {r["residents"]:,} residents)'
            pair += (f'<span class="trk" title="{e(t)}"><i class="{cls}" style="width:{100 * r["cost_per_resident"] / top:.1f}%"></i></span>'
                     f'<span class="v">${r["cost_per_resident"]:,.0f}</span>')
        out.append(f'<div class="ps-bar two"><span class="lab">{e(name)}</span><span class="pair">{pair}</span></div>')
    return (f'<p class="ps-key"><span><i class="sq"></i>Police</span><span><i class="sq f"></i>Fire</span></p>'
            f'<div class="ps-bars" role="img" aria-label="Police and fire budget per resident by government">{"".join(out)}</div>')


def town_cards(A, C, S, state_rates, order):
    """One card set per government, picked with chips: who covers it, cost per resident, officers, crime vs Florida."""
    by = defaultdict(dict)
    for r in A:
        by[r['gov_id']][r['service']] = r
    fyV, fyP = full_years(C, 'V'), full_years(C, 'P')
    staff = defaultdict(dict)
    for r in S:
        staff[r['agency_id']][r['year']] = r
    st = {int(y): v for y, v in state_rates.items()}
    chips, cards = [], []
    for i, g in enumerate(order):
        pol, fire = by[g].get('police'), by[g].get('fire')
        name = (pol or fire)['government']
        chips.append(f'<button type="button" class="chip" data-v="{e(g)}" aria-pressed="{"true" if i == 0 else "false"}">{e(name)}</button>')
        # whose crime numbers cover this town: its own department, or the Sheriff
        crime_aid = pol['agency_id'] if pol and pol.get('fbi_ori') and pol['agency_gov_id'] == pol['gov_id'] else 'bcso'
        crime_name = pol['agency'] if crime_aid == (pol or {}).get('agency_id') else "the Sheriff's Office"
        v, p = fyV.get(crime_aid, {}), fyP.get(crime_aid, {})
        ly = max(v) if v else None
        if ly == NEW_SYSTEM and NEW_SYSTEM - 1 in v:
            ly = NEW_SYSTEM - 1  # the switch year's counts dip as agencies change systems; show the last yearly summary

        def vs(rows, code, noun):
            if not ly or ly not in rows:
                return f'<p>No full year reported to the FBI.</p>'
            r = rows[ly]
            fl = st.get(ly, {}).get(code)
            cmp = ''
            if fl:
                ratio = r['per_1000'] / (fl / 100)
                cmp = ('about the same as Florida' if 0.9 <= ratio <= 1.1 else
                       f'{ratio:.1f} times Florida\'s rate' if ratio > 1.1 else f'{round(100 * (1 - ratio))}% below Florida\'s rate')
            return (f'<div><span class="big">{r["per_1000"]:g}<small>{noun} per 1,000 people, {ly}</small></span>'
                    f'<p>{r["count"]:,} reported{"; " + cmp if cmp else ""}.</p></div>')

        lag = ''
        if ly and ly < 2024:
            lag = f'<p>{e(crime_name[0].upper() + crime_name[1:])} has not sent the FBI a full year since {ly}.</p>'
        shared = '' if crime_aid != 'bcso' or g == 'county' else f'<p>{e(name)} is policed by the Sheriff, so its crimes are counted in the Sheriff\'s numbers for all the areas it patrols.</p>'
        sy = max(staff.get(pol['agency_id'], {})) if pol and staff.get(pol['agency_id']) else None
        srow = staff[pol['agency_id']][sy] if sy else None
        officers = (f'<p>{srow["officers"]:,} sworn officers and {srow["civilians"]:,} civilian staff in {sy}'
                    f'{f", {1000 * srow["officers"] / srow["population"]:.1f} officers per 1,000 people" if srow.get("population") else ""}.</p>') if srow and sy >= 2023 else ''
        money = lambda r: f'<span class="big">${r["cost_per_resident"]:,.0f}<small>per resident, {e(r["budget_fiscal_year"])}</small></span>' if r and r.get('cost_per_resident') else ''
        pol_name = (gov(pol['agency_gov_id'], pol['agency']) if pol['agency_gov_id'] != pol['gov_id'] else e(pol['agency'])) if pol else '—'
        cards.append(f'''<div class="ps-town" data-g="{e(g)}"{" hidden" if i else ""}>
  <div class="ps-tc"><span class="eyebrow">Police</span><b>{pol_name}</b><p>{e((pol or {}).get("arrangement", ""))}</p>{money(pol)}{officers}</div>
  <div class="ps-tc"><span class="eyebrow">Fire</span><b>{e((fire or {}).get("agency", "—"))}</b><p>{e((fire or {}).get("arrangement", ""))}</p>{money(fire)}</div>
  <div class="ps-tc"><span class="eyebrow">Crimes reported{f" by {e(crime_name)}" if crime_aid == "bcso" and g != "county" else ""}</span>
    <div class="row">{vs(v, "V", "violent")}{vs(p, "P", "property")}</div>{lag}{shared}</div>
</div>''')
    return (f'<div class="chips ps-towns" id="psTown" role="group" aria-label="Town">{"".join(chips)}</div>' + ''.join(cards))
