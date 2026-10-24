"""Government profile pages: /governments and /governments/<slug>."""
import html, json, os, re
from datetime import date
from city_filter import city_bar
from govs import CRA_NAME
_dumps = json.dumps


def nice(d):
    try:
        return date.fromisoformat(d[:10]).strftime("%b %-d, %Y")
    except Exception:
        return d or ""
from govs import GOVS, profile, all_profiles

e = lambda s: html.escape(str(s if s is not None else ''))


def money(n, d=1):
    if n is None:
        return '—'
    sign, n = ('−' if n < 0 else ''), abs(n)
    return sign + (f'${n/1e9:,.2f}B' if n >= 1e9 else f'${n/1e6:,.{d}f}M' if n >= 1e6 else f'${n/1e3:,.0f}K' if n >= 1e3 else f'${n:,.0f}')


def usd(n):
    return '—' if n is None else f'${n:,.0f}'


def src(u, t='Source'):
    return f'<a class="src" href="{e(u)}" target="_blank" rel="noopener">{e(t)}</a>' if u else ''


PDF = '''<div class="stamp"><button type="button" class="pdf-btn" id="pdf"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>Data updated Oct 21, 2026</span></div>'''


def hbars(rows, color='var(--s1)'):
    rows = [(k, v) for k, v in rows if v]
    if not rows:
        return ''
    mx = max(v for _, v in rows)
    return '<div class="hbars">' + ''.join(f'<div class="hb"><span class="hb-n">{e(k)}</span><span class="hb-track"><span class="hb-bar" style="width:{v/mx*100:.1f}%;background:{color}"></span></span><span class="hb-v">{money(v)}</span></div>' for k, v in sorted(rows, key=lambda kv: -kv[1])) + '</div>'


def kpi(label, value, sub=''):
    return f'<div class="kpi"><span class="eyebrow">{e(label)}</span><span class="v">{value}</span><span class="s">{sub}</span></div>'


def gov_page(key):
    from fees_page import roster_li, STAFF
    p = profile(key)
    g = next(x for x in GOVS if x['key'] == key)
    b = p.get('budget') or {}
    pop = p.get('population')
    pr = p.get('per_resident') or {}
    off = p.get('officials') or {}
    mills = b.get('mills')
    # header facts
    if key == 'schools':
        import json, os
        st = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'data', 'salaries', 'schools.json'))).get('stats') or {}
        n = st.get('total_employees_approx')
        kp = [kpi('Employees', f'About {n:,}' if n else '—', 'per the superintendent, Oct 2025' if n else '')]
    else:
        kp = [kpi('Residents', f'{pop:,}' if pop else '—', '2025 state estimate' if pop else '')]
    if b.get('total'):
        kp.append(kpi('Budget', money(b['total']), f'{e(b.get("status") or "FY2026")}' + (f' · {money(pr["budget"], 0) if pr.get("budget", 0) >= 1e6 else usd(pr.get("budget"))} per resident' if pr.get('budget') else '')))
    nx = b.get('next') or {}
    if nx.get('total'):
        kp.append(kpi('New budget', money(nx['total']), f"{nx['fy']} · " + ('adopted Sept 2026' if nx.get('adopted') else 'final hearing held')))
    if mills is not None and key != 'schools':
        kp.append(kpi('Property tax rate', f'{mills:g} mills' if mills else 'None', f'${mills*100:,.0f} per $100,000 of taxable value' if mills else 'No city property tax'))
    elif mills:
        kp.append(kpi('School tax rate', f'{mills:g} mills', 'most of it set by the state'))
    if p.get('debt'):
        kp.append(kpi('Debt', money(p['debt']['total']), (usd(pr['debt']) + ' per resident · ' if pr.get('debt') else '') + e((p['debt'].get('fy') or '')[:6])))
    if off.get('employees'):
        kp.append(kpi('Employees', f'{off["employees"]:,g}', 'full-time equivalent'))
    secs = []
    # who's in charge
    if off.get('seats'):
        seats = off['seats']
        board = [s for s in seats if s.get('elected') or not STAFF.search(s['seat'])]
        staff = [s for s in seats if s not in board]
        secs.append(f'''<section class="tx-sec"><div class="sec-hd"><h2 id="who">Who's in charge</h2><span class="muted">{e(off.get("form") or "")}</span></div>
          <div class="two"><div class="card gov"><h3 class="h4 roster-h">Elected</h3><ul class="roster">{"".join(roster_li(s) for s in board)}</ul></div>
          <div class="card gov">{f'<h3 class="h4 roster-h">Appointed staff</h3><ul class="roster">{"".join(roster_li(s) for s in staff)}</ul>' if staff else ''}
          {('<h3 class="h4 roster-h">Top pay</h3><ul class="roster">' + ''.join(f'<li><span class="seat">{e(x["title"])}</span><span class="who"><b>{usd(x["annual"])}</b><small>{e(x.get("name") or "")} {e(x.get("year") or "")}</small></span><span class="r-term"></span></li>' for x in p['pay']) + '</ul>') if p.get('pay') else ''}
          <p class="gov-ft small">{f'<a href="{e(off["website"])}" target="_blank" rel="noopener">Website</a> · ' if off.get("website") else ""}{f'<a href="{e(off["contact_url"])}" target="_blank" rel="noopener">Contact</a> · ' if off.get("contact_url") else ""}<a href="/who-runs-bay-county">All officials</a></p></div></div></section>''')
    # money
    if b.get('revenue') or b.get('spending'):
        srcs = ' '.join(src(u, t) for t, u in b.get('sources', [])[:2])
        ctx = ''.join(f'<p class="note">{e(t)} {src(u)}</p>' for t, u in (b.get('context') or [])[:2])
        secs.append(f'''<section class="tx-sec"><div class="sec-hd"><h2 id="money">Money in, money out</h2><span class="muted">{e(b.get("status") or "")} budget{" · general fund " + money(b["general_fund"]) if b.get("general_fund") else ""}</span></div>
          <div class="two"><div><h3 class="h4">Where the money comes from</h3>{hbars(list((b.get("revenue") or {}).items()), "var(--s3)")}</div><div><h3 class="h4">What the general fund pays for</h3>{hbars(list((b.get("spending") or {}).items()))}</div></div>
          {ctx}<p class="src-line">{srcs} · <a href="/public-money/tax-dollars">Compare every government's budget</a>{' · <a href="/public-money/budget-explorer?gov=' + key + '">Budget explorer</a>' if p.get("budget_detail") else ''}</p></section>''')
    # tax rate history
    m = p.get('millage')
    if m and any(x is not None for x in m.get('rate') or []):
        trip = [(y, v, (m.get('rolled_back') or [None] * len(m['rate']))[i]) for i, (y, v) in enumerate(zip(m['years'], m['rate'])) if v is not None]
        yrs, r, rb = [t[0] for t in trip], [t[1] for t in trip], [t[2] for t in trip]
        mx = max(r + [x for x in rb if x]) or 1
        rows = ''.join(f'<div class="hb"><span class="hb-n">Tax year {y}</span><span class="hb-track"><span class="hb-bar" style="width:{v/mx*100:.1f}%;background:var(--s1)"></span>{f"<i class=mk style=left:{rb[i]/mx*100:.1f}% title=\"Rolled-back rate {rb[i]}\"></i>" if i < len(rb) and rb[i] else ""}</span><span class="hb-v">{v:g}</span></div>' for i, (y, v) in enumerate(zip(yrs, r)))
        up = (r[-1] > rb[-1]) if r and rb and rb[-1] else None
        secs.append(f'''<section class="tx-sec"><div class="sec-hd"><h2 id="rate">Property tax rate</h2><span class="muted">Mills: dollars per $1,000 of taxable value</span></div>
          <div class="hbars">{rows}</div>
          <p class="note">The tick on each bar is the <span class="term" data-term="rolled-back">rolled-back rate</span>, the rate that would bring in the same money as the year before. {f"The latest rate is {'above' if up else 'at or below'} it{', so the city takes in more from existing property than the year before' if up else ''}." if up is not None else ''} <a href="/public-money/tax-dollars">See your full tax bill</a></p></section>''')
    # debt
    d = p.get('debt')
    if d:
        LBL = {'notes_loans': 'Notes and loans', 'revenue_bonds': 'Revenue bonds', 'general_obligation_bonds': 'General obligation bonds', 'leases': 'Leases', 'sbitas': 'Software subscriptions (SBITAs)', 'bond_premium': 'Bond premium', 'finance_purchases': 'Finance purchases'}
        bt = ''.join(f'<tr><th scope="row">{e(LBL.get(k, k.replace("_", " ").capitalize()))}</th><td class="num">{usd(v)}</td></tr>' for k, v in (d.get('by_type') or {}).items()
                     if isinstance(v, (int, float)) and v and not any(x in k for x in ('compensated', 'pension', 'opeb', 'landfill', 'claims', 'total')))
        rel = ''.join(f'<li>{e(x["name"])}: {money(x["total"])}</li>' for x in d.get('related') or [] if x.get('total'))
        secs.append(f'''<section class="tx-sec"><div class="sec-hd"><h2 id="debt">Debt</h2><span class="muted">{e(d.get("fy") or "")}</span></div>
          <p><b>{money(d["total"])}</b> owed{f" — about {usd(pr['debt'])} per resident" if pr.get("debt") else ""}. {e(d.get("note") or "")}</p>
          {f'<div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Kind of debt</th><th scope="col" class="num">Owed</th></tr></thead><tbody>{bt}</tbody></table></div>' if bt else ''}
          {f'<p class="small">Related agencies:</p><ul class="plain small">{rel}</ul>' if rel else ''}
          <p class="src-line">{src(d.get("source_url"), "Audited financial statements")} · <a href="/public-money/debt">All local debt</a></p></section>''')
    # audits
    au = p.get('audits')
    if au:
        last = au[0]
        fl = ''.join(f'<li class="fd"><div class="fd-hd"><b>{e(f["title"])}</b>{" <span class=\"badge warn\">Repeat</span>" if f["repeat"] else ""}</div><p class="small">{e(f.get("plain") or "")}</p></li>' for f in last['findings'][:4])
        counts = ' · '.join(f'{a["fy"]}: {len(a["findings"])} finding{"s" if len(a["findings"]) != 1 else ""}' for a in au)
        secs.append(f'''<section class="tx-sec"><div class="sec-hd"><h2 id="audits">What the auditors found</h2><span class="muted">{e(counts)}</span></div>
          {f'<ol class="findings">{fl}</ol>' if fl else '<p>No findings in the latest audit.</p>'}
          <p class="src-line">{src(last.get("source_url"), last["fy"] + " audit")} · <a href="/public-money/audits">All audit findings</a></p></section>''')
    if p.get('utility_bill'):
        u = p['utility_bill']; kp.append(kpi('Typical utility bill', f'${u["total"]:,.2f}', f'a month at 5,000 gallons{"" if u.get("garbage") else ", garbage not included"} · <a href="/public-money/fees-and-bills?gov={key}">compare</a>'))
    # meetings
    if p.get('meetings'):
        up = [x for x in p['meetings'] if not x.get('past')][:5]
        if up:
            secs.append('<section class="tx-sec"><div class="sec-hd"><h2 id="meet">Upcoming meetings</h2></div><ul class="plain">' + ''.join(f'<li><b>{e((x.get("start") or "")[:16].replace("T", " "))}</b> {e(x.get("title"))}{" <span class=muted>(expected)</span>" if x.get("expected") else ""} {src(x.get("agenda_url"), "Agenda")}</li>' for x in up) + f'</ul><p class="src-line"><a href="/meetings?gov={key}">All meetings</a></p></section>')
    # get involved
    secs.append(f'''<section class="tx-sec act"><div class="sec-hd"><h2 id="act">Stay informed</h2></div>
      <div class="cols"><div><h3>Get updates</h3><p>Email when {e(p["short"])} has new votes, contracts or corrections on this site.</p><p><a class="pill" href="/alerts?gov={key}">Follow {e(p["short"])}</a></p></div>
      <div><h3>Ask for a record</h3><p>Something missing here? Request it from {e(p["short"])} under Florida's public records law.</p><p><a class="pill" href="/records-request?gov={key}">Request a record</a></p></div>
      <div><h3>Compare</h3><p>See {e(p["short"])} side by side with other Bay County governments.</p><p><a class="pill" href="/compare?g={key}">Compare</a></p></div></div></section>''')
    # sections filled in the browser by gov.js from the dashboards' published data, for the year in the bar
    def live(i, title, more=''):
        return (f'<section class="tx-sec gx" id="{i}" hidden><div class="sec-hd"><h2>{title}</h2><span class="muted" data-gx-sub></span></div>'
                f'<div class="kpis gx-kpis" data-gx-kpis></div><div data-gx-body></div><p class="src-line" data-gx-link></p>{more}</section>')
    by_id = {re.search(r'id="([a-z]+)"', x).group(1): x for x in secs}
    cra = g.get('cra')
    live_secs = {'contracts': live('contracts', 'Contracts'), 'cra': live('cra', 'Redevelopment (CRA) spending') if cra else '',
                 'projects': live('projects', 'Projects'), 'votes': live('votes', 'How they voted'), 'savings': live('savings', 'Where it could spend less')}
    order = ['who', 'money', 'rate', 'contracts', 'cra', 'projects', 'votes', 'meet', 'debt', 'audits', 'savings', 'act']
    body = ''.join(by_id.get(i) or live_secs.get(i) or '' for i in order)
    labels = [('who', 'Officials'), ('money', 'Budget'), ('contracts', 'Contracts'), ('cra', 'CRA'), ('projects', 'Projects'), ('votes', 'Votes'),
              ('meet', 'Meetings'), ('debt', 'Debt'), ('audits', 'Audits'), ('savings', 'Savings')]
    nav = ''.join(f'<a href="#{i}">{t}</a>' for i, t in labels if f'id="{i}"' in body)
    glance = ('<section class="tx-sec gx-glance" hidden><div class="sec-hd"><h2 id="year">At a glance</h2><span class="muted" id="gxGlanceH"></span></div>'
              '<div class="kpis" id="gxGlance"></div><p class="muted small" data-gx-loading>Loading this government\'s records…</p></section>')
    cfg = {'key': key, 'short': p['short'], 'cra': cra or '', 'craName': CRA_NAME.get(cra, '') if cra else ''}
    year = '<label class="sc-f sc-year" data-scope><span>Year</span><select id="gxYear" aria-label="Year"><option value="all">All years</option></select></label>'
    bar = city_bar(None, fixed=key, extra=f'{year}<nav class="gx-jump" aria-label="On this page">{nav}</nav>')
    lede = g.get('blurb') or f'{e(p["name"])}: who runs it, what it spends and owes, how its commission votes, and what the auditors found, all from public records.'
    return f'''<div class="page tax gov-page">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow"><a href="/governments">Governments</a> · {e("County" if key == "county" else "Schools" if key == "schools" else "City")}</span><h1>{e(p["short"])}</h1>
    <p class="lede">{e(lede)}</p></div>{PDF}</header>
  {bar}
  <div class="kpis">{"".join(kp)}</div>
  {glance}
  {body}
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>window.GOVPAGE={_dumps(cfg)};</script>
<script src="/assets/gov.js" defer></script>'''


def govs_index():
    ps = all_profiles()
    cards = ''
    for p in ps:
        b = p.get('budget') or {}
        facts = [f'{p["population"]:,} residents' if p.get('population') and p['kind'] == 'city' else '',
                 f'{money(b["total"])} budget' if b.get('total') else '',
                 (f'{b["mills"]:g} mills' if b.get('mills') else 'no city property tax') if p['kind'] == 'city' else '',
                 f'{(p.get("votes") or {}).get("n", 0)} votes recorded']
        cards += f'''<a class="topic" href="/governments/{p["slug"]}"><span class="eyebrow">{e("County" if p["kind"] == "county" else "Schools" if p["kind"] == "schools" else "City")}</span><h3>{e(p["short"])}</h3><p>{e(" · ".join(x for x in facts if x))}</p><span class="t-stat"><b>{money((p.get("debt") or {}).get("total"))}</b> in debt</span></a>'''
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Governments</span><h1>Bay County's local governments</h1>
    <p class="lede">One page for each government: who runs it, its budget and tax rate, debt, audit findings, votes, contracts and projects. Pick yours, or compare them side by side.</p></div>
    <div class="stamp"><a class="pill" href="/compare">Compare governments</a></div></header>
  <h2 class="sr">Every local government</h2>
  <div class="topics">{cards}</div>
  <p class="note">Bay County residents pay the county and school district, and city residents also pay their city. Unincorporated areas are served by the county alone. <a href="/my-address/">Find yours by address</a>.</p>
</div>
<link rel="stylesheet" href="/assets/tax.css">'''
