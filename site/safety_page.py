"""Police, fire and the Sheriff (/public-safety): who polices and who fights fires in each town, what each costs, the
crimes each police agency reported to the FBI since 2016, and police staffing.

Built from the safety-agencies, crime-counts and police-staffing datasets (site/safety_data.py). Counts only: no
arrest, booking or incident that names a person is shown.
"""
import html
from collections import defaultdict

from entity_links import gov

e = lambda s: html.escape(str(s if s is not None else ''))

CSS = r"""
.ps-tbl td,.ps-tbl th{vertical-align:top}
.ps-tbl td.n,.ps-tbl th.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.ps-tbl .sub{display:block;color:var(--muted);font-size:.8rem;margin-top:2px;line-height:1.35}
.ps-tbl td.nr{color:var(--muted)}
.ps-tbl th.part,.ps-tbl td.part{font-style:italic}
.ps-off[hidden]{display:none}
.ps-chips{margin-bottom:10px}
.ps-two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.ps-card{padding:20px;border-radius:22px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.ps-card h3{margin:0 0 6px;font-size:1.05rem;font-weight:600}
.ps-card p{margin:0;font-size:.9rem;line-height:1.5}
@media (max-width:760px){.ps-two{grid-template-columns:1fr}.ps-tbl .hide-sm{display:none}}
"""

JS = r"""
(() => {
  const g = document.getElementById('psOff'); if (!g) return;
  g.addEventListener('click', ev => { const b = ev.target.closest('button'); if (!b) return;
    g.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b));
    document.querySelectorAll('.ps-off').forEach(t => t.hidden = t.dataset.o !== b.dataset.v); });
})();
"""


def _money(n):
    if n is None:
        return '—'
    return f'${n / 1e6:.1f}M' if n >= 1e6 else f'${round(n / 1e3):,}K'


def _num(n):
    return '—' if n is None else f'{n:,}'


def safety_page(out_dir):
    from safety_data import safety_agencies, crime_counts, police_staffing
    A, C, S = safety_agencies(), crime_counts(), police_staffing()
    if not A:
        return '<div class="page"><h1>Police, fire and the Sheriff</h1><p>No public safety agencies on file for this place yet.</p></div>'

    # --- who covers each town
    by_gov = defaultdict(dict)
    for r in A:
        by_gov[r['gov_id']][r['service']] = r
    order = list(dict.fromkeys(r['gov_id'] for r in A))

    def who(r):
        if not r:
            return '—'
        name = gov(r['agency_gov_id'], r['agency']) if r['agency_gov_id'] != r['gov_id'] else e(r['agency'])
        return f'{name}<span class="sub">{e(r["arrangement"])}</span>'

    town_rows = ''.join(
        f'<tr><td>{gov(g, by_gov[g].get("police", by_gov[g].get("fire"))["government"])}</td>'
        f'<td>{who(by_gov[g].get("police"))}</td><td class="n">{_money((by_gov[g].get("police") or {}).get("budget_amount"))}</td>'
        f'<td>{who(by_gov[g].get("fire"))}</td><td class="n">{_money((by_gov[g].get("fire") or {}).get("budget_amount"))}</td></tr>'
        for g in order)
    police_total = sum(r['budget_amount'] or 0 for r in A if r['service'] == 'police')
    fire_total = sum(r['budget_amount'] or 0 for r in A if r['service'] == 'fire')
    contracts = sum(r['budget_amount'] or 0 for r in A if r['service'] == 'police' and r['agency_gov_id'] != r['gov_id'] and r['gov_id'] != 'county')
    fy = next((r['budget_fiscal_year'] for r in A if r['budget_fiscal_year']), 'FY2026')

    # --- crimes reported
    agencies = list(dict.fromkeys((r['agency_id'], r['agency'], r['gov_id']) for r in C))
    years = sorted({r['year'] for r in C})
    cell = {(r['agency_id'], r['year'], r['offense_code']): r for r in C}
    offenses = list(dict.fromkeys((r['offense_code'], r['offense']) for r in C))
    partial = {y for y in years if any(r['months_reported'] < 12 for r in C if r['year'] == y)}

    def yl(y):
        return f'{y} so far' if y in partial else str(y)

    def off_table(code, label, hidden):
        head = ''.join(f'<th class="n{" part" if y in partial else ""}{" hide-sm" if y < years[-1] - 5 else ""}">{yl(y)}</th>' for y in years)
        rows = []
        for aid, name, g in agencies:
            tds = []
            for y in years:
                r = cell.get((aid, y, code))
                cls = 'n' + (' part' if y in partial else '') + (' hide-sm' if y < years[-1] - 5 else '')
                if not r or r['count'] is None:
                    tds.append(f'<td class="{cls} nr" title="Not reported to the FBI">—</td>')
                else:
                    t = f'{r["count"]:,} {label.lower()} reported, {r["cleared"] or 0:,} cleared' + (f', {r["per_1000"]} per 1,000 people' if r['per_1000'] else '')
                    tds.append(f'<td class="{cls}" title="{e(t)}">{r["count"]:,}</td>')
            rows.append(f'<tr><td>{e(name)}<span class="sub">{gov(g)}</span></td>{"".join(tds)}</tr>')
        return (f'<div class="ps-off" data-o="{e(code)}"{" hidden" if hidden else ""}><div class="tablewrap"><table class="tx-table ps-tbl" data-tt-year="off" data-tt-filter="off">'
                f'<thead><tr><th>{e(label)}</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></div>')

    chips = ''.join(f'<button type="button" class="chip" data-v="{e(c)}" aria-pressed="{"true" if i == 0 else "false"}">{e(l)}</button>' for i, (c, l) in enumerate(offenses))
    tables = ''.join(off_table(c, l, i > 0) for i, (c, l) in enumerate(offenses))

    # headline numbers: the latest full year every reporting agency has
    full = [y for y in years if y not in partial and y < 2025]
    ky = full[-1] if full else years[-1]
    v_ky = sum(cell[(a, ky, 'V')]['count'] or 0 for a, _, _ in agencies if (a, ky, 'V') in cell)
    p_ky = sum(cell[(a, ky, 'P')]['count'] or 0 for a, _, _ in agencies if (a, ky, 'P') in cell)
    first_full = full[0] if full else years[0]
    v_first = sum(cell[(a, first_full, 'V')]['count'] or 0 for a, _, _ in agencies if (a, ky, 'V') in cell and (a, first_full, 'V') in cell)
    p_first = sum(cell[(a, first_full, 'P')]['count'] or 0 for a, _, _ in agencies if (a, ky, 'P') in cell and (a, first_full, 'P') in cell)
    pct = lambda a, b: f'{round(100 * (a - b) / b):+d}%' if b else ''

    # --- staffing
    s_agencies = list(dict.fromkeys((r['agency_id'], r['agency'], r['gov_id']) for r in S))
    s_years = sorted({r['year'] for r in S})
    scell = {(r['agency_id'], r['year']): r for r in S}
    s_head = ''.join(f'<th class="n{" hide-sm" if y < s_years[-1] - 4 else ""}">{y}</th>' for y in s_years)
    s_rows = ''
    for aid, name, g in s_agencies:
        tds = ''
        for y in s_years:
            r = scell.get((aid, y))
            cls = 'n' + (' hide-sm' if y < s_years[-1] - 4 else '')
            tds += (f'<td class="{cls}" title="{r["officers"]} sworn officers, {r["civilians"]} civilian staff">{r["officers"]:,}<span class="sub">+{r["civilians"]:,} civilian</span></td>'
                    if r else f'<td class="{cls} nr" title="Not reported to the FBI">—</td>')
        s_rows += f'<tr><td>{e(name)}<span class="sub">{gov(g)}</span></td>{tds}</tr>'
    officers = sum(r['officers'] or 0 for r in A if r['service'] == 'police' and r['officers'])

    k = lambda lab, v, s: f'<div class="kpi"><span class="eyebrow">{lab}</span><span class="v">{v}</span><span class="s">{s}</span></div>'
    kpis = (k(f'Police budgets, {e(fy)}', _money(police_total), f'Including {_money(contracts)} cities pay the Sheriff by contract') +
            k(f'Fire budgets, {e(fy)}', _money(fire_total), f'{sum(1 for r in A if r["service"] == "fire")} fire departments') +
            k('Sworn officers', _num(officers), 'Latest count each agency gave the FBI') +
            k(f'Violent crimes reported, {ky}', _num(v_ky), f'{pct(v_ky, v_first)} since {first_full}, same agencies; {_num(p_ky)} property crimes'))

    data = ' · '.join(f'<a href="/api/v1/datasets/{d}">{d}</a> (<a href="/downloads/{d}.csv">CSV</a>)' for d in ('safety-agencies', 'crime-counts', 'police-staffing'))
    return f'''<style>{CSS}</style>
<div class="page tax ps">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Living here · Police, fire and the Sheriff</span><h1>Police, fire and the Sheriff</h1>
    <p class="lede">Who answers when you call 911 in each part of Bay County, what each police and fire department costs, how many crimes each police agency has reported since 2016, and how many officers they have.</p></div>
    <div class="stamp"><a class="pill" href="#crime">Crimes reported →</a><span>Crime counts from the FBI, budgets from each government</span></div></header>
  <div class="kpis">{kpis}</div>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>Who covers what</h2>
    <ol class="ex-steps"><li><b>The Sheriff covers the whole county.</b> The {gov("sheriff", "Bay County Sheriff's Office")} patrols everywhere outside city limits, runs the county jail, and polices Callaway and Mexico Beach, which pay it by contract.</li>
    <li><b>Five cities have their own police.</b> Panama City, Panama City Beach, Lynn Haven, Springfield and Parker run police departments paid from their city budgets.</li>
    <li><b>Every city has a fire department.</b> Bay County Fire Rescue covers the unincorporated areas, paid by a fire fee on tax bills there.</li></ol></div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="who" data-tile="Who covers each town">Who covers each town</h2><span class="muted">{e(fy)} adopted budgets</span></div>
    <div class="tablewrap"><table class="tx-table ps-tbl" data-tt-year="off" data-tt-filter="off"><thead><tr><th>Government</th><th>Police</th><th class="n">Police budget</th><th>Fire</th><th class="n">Fire budget</th></tr></thead><tbody>{town_rows}</tbody></table></div>
    <p class="note">Budgets are the lines in each government's adopted budget, the same figures as the government pages. The Sheriff's line is the county's general fund money for law enforcement and the jail. Bay County Fire Rescue is the county's fire services fund (MSTU).</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="crime" data-tile="Crimes reported">Crimes reported, by agency</h2><span class="muted">What each agency reported to the FBI, {years[0]} to {years[-1]}</span></div>
    <div class="chips ps-chips" id="psOff" role="group" aria-label="Offense">{chips}</div>
    {tables}
    <div class="ps-two" style="margin-top:14px">
      <div class="ps-card"><h3>Read with care</h3><p>A dash means the agency sent the FBI nothing that year. No Florida agency reported for 2021 while the state changed systems, and Panama City Beach has not reported since 2020. From 2025, agencies send monthly incident reports instead of one yearly summary, so 2025 and later are not directly comparable with earlier years.</p></div>
      <div class="ps-card"><h3>What the numbers are</h3><p>Offenses known to police, not arrests or convictions. Hover a number to see how many were cleared (solved or closed) and the rate per 1,000 people the agency covers. The Sheriff's numbers cover only the areas it patrols, not the cities with their own police.</p></div>
    </div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="staff" data-tile="Officers">Police officers and staff</h2><span class="muted">Sworn officers on October 31 each year, with civilian staff</span></div>
    <div class="tablewrap"><table class="tx-table ps-tbl" data-tt-year="off" data-tt-filter="off"><thead><tr><th>Agency</th>{s_head}</tr></thead><tbody>{s_rows}</tbody></table></div>
    <p class="note">As each agency reported to the FBI. The Sheriff's civilian count jumped from 71 in 2022 to 271 in 2023; the FBI data does not say why. Missing years were not reported.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="records" data-tile="Ask for records">Ask for police and fire records</h2></div>
    <p>Incident reports, call logs, body camera video and fire reports are public records in Florida, with some parts held back by law. Each agency's records contact is on the <a href="/records">public records page</a>.</p></section>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>Crimes and staffing</b> come from the <a href="https://cde.ucr.cjis.gov/" rel="noopener" target="_blank">FBI Crime Data Explorer</a>, which publishes what each agency reports to the FBI's Uniform Crime Reporting program. Checked every week.</li>
      <li><b>Who covers each town</b> is checked by hand. Budgets come from each government's adopted {e(fy)} budget (see <a href="/public-money/budget-compare">Budgets by year</a>).</li>
      <li><b>Not here yet:</b> fire and rescue call counts and response times. Florida's fire reporting system does not publish them by department; they can be asked for as a public record.</li>
      <li><b>Data:</b> {data}.</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>{JS}</script>'''
