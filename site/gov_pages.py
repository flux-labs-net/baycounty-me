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


DATA_UPDATED = 'Oct 21, 2026'
PDF = '''<div class="stamp"><button type="button" class="pdf-btn" id="pdf"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>Data updated Oct 21, 2026</span></div>'''


def hbars(rows, color='var(--s1)'):
    rows = [(k, v) for k, v in rows if v]
    if not rows:
        return ''
    mx = max(v for _, v in rows)
    return '<div class="hbars">' + ''.join(f'<div class="hb"><span class="hb-n">{e(k)}</span><span class="hb-track"><span class="hb-bar" style="width:{v/mx*100:.1f}%;background:{color}"></span></span><span class="hb-v">{money(v)}</span></div>' for k, v in sorted(rows, key=lambda kv: -kv[1])) + '</div>'


from ui import ico, avatar as _avatar, TONES  # shared pieces (ui.css)


# the icon and tint of each top card, by its label (gov.js has the same table for the cards it redraws)
KPI_ICON = {'Residents': ('users', 'teal'), 'Budget': ('wallet', 'blue'), 'Spent (audited)': ('wallet', 'blue'),
            'Property tax rate': ('percent', 'amber'), 'School tax rate': ('percent', 'amber'), 'Debt': ('dollar', 'salmon'),
            'Employees': ('briefcase', 'blue'), 'Typical utility bill': ('drop', 'teal')}
# each section: its icon and tint, and its label in the section tiles
SEC = {'who': ('users', 'blue', 'Officials'), 'money': ('wallet', 'blue', 'Budget'), 'rate': ('percent', 'amber', 'Tax rate'),
       'contracts': ('file', 'blue', 'Contracts'), 'cra': ('columns', 'teal', 'CRA'), 'projects': ('crane', 'salmon', 'Projects'),
       'votes': ('vote', 'amber', 'Votes'), 'meet': ('calendar', 'salmon', 'Meetings'), 'debt': ('dollar', 'salmon', 'Debt'),
       'audits': ('search', 'teal', 'Audits'), 'savings': ('piggy', 'teal', 'Savings'), 'act': ('bell', 'blue', 'Stay informed'),
       'year': ('pulse', 'blue', 'At a glance')}


def kpi(label, value, sub='', static=False, none=False):
    cls = 'kpi ui-k' + (' kpi-none' if none else '')
    i, t = KPI_ICON.get(label, ('grid', 'blue'))
    return f'<div class="{cls}"{" data-static" if static else ""}><span class="kh">{ico(i, t)}<span class="eyebrow">{e(label)}</span></span><span class="v">{value}</span><span class="s">{sub}</span></div>'


def year_cards(key, rows, fy):
    """The top cards for fiscal year fy, from the government-years rows. Mirrors topCards() in gov.js, which redraws
    them when the Year picker changes. A card whose figure has no record that year says so, never another year's number."""
    has = lambda k: any(r.get(k) is not None for r in rows)
    by = {r['fiscal_year']: r for r in rows}
    if fy not in by and rows:
        fy = max(by)
    r, prev = by.get(fy) or {}, by.get(fy - 1) or {}
    none = lambda label, why: kpi(label, 'No data', why, none=True)
    out = []
    if key != 'schools' and has('population'):
        out.append(kpi('Residents', f"{r['population']:,}", f"FY{fy} state figure" if r.get('population_year') == fy else f"{r.get('population_year')} state estimate")
                   if r.get('population') else none('Residents', f'No count for FY{fy}'))
    if r.get('budget_total'):
        bits = [f"FY{fy} · {e(r.get('budget_status') or 'adopted')}"]
        if r.get('budget_per_resident'):
            bits.append(f"{usd(r['budget_per_resident'])} per resident")
        if prev.get('budget_total'):
            ch = (r['budget_total'] / prev['budget_total'] - 1) * 100
            bits.append(f"{'up' if ch >= 0 else 'down'} {abs(ch):.0f}% from FY{fy - 1}")
        out.append(kpi('Budget', money(r['budget_total']), ' · '.join(bits) + ' ' + src(r.get('budget_source_url'))))
    elif r.get('actual_spending'):
        out.append(kpi('Spent (audited)', money(r['actual_spending']), f'FY{fy} actual spending; no adopted budget on file ' + src(r.get('actuals_source_url'))))
    elif has('budget_total') or has('actual_spending'):
        out.append(none('Budget', f'No FY{fy} budget on file'))
    if has('millage'):
        lbl = 'School tax rate' if key == 'schools' else 'Property tax rate'
        m = r.get('millage')
        if m is None:
            out.append(none(lbl, f'No FY{fy} rate on file'))
        elif not m:
            out.append(kpi(lbl, 'None', 'No city property tax'))
        else:
            out.append(kpi(lbl, f'{m:g} mills', f'${m * 100:,.0f} per $100,000 of taxable value' + (f" · tax year {r['tax_year']}" if r.get('tax_year') else '')))
    if has('debt_total'):
        if r.get('debt_total'):
            per = f"{usd(r['debt_total'] / r['population'])} per resident · " if r.get('population') and key != 'schools' else ''
            out.append(kpi('Debt', money(r['debt_total']), f'{per}audited, end of FY{fy} ' + src(r.get('debt_source_url'))))
        else:
            out.append(none('Debt', 'Audited total on file for ' + ', '.join(f"FY{x['fiscal_year']}" for x in rows if x.get('debt_total')) + ' only'))
    if has('employees_fte'):
        out.append(kpi('Employees', f"{r['employees_fte']:,g}", f'FY{fy} budget, staff positions') if r.get('employees_fte') else none('Employees', f'No FY{fy} count on file'))
    return out, fy, r.get('period') or ''


def gov_page(key):
    from fees_page import roster_li, STAFF
    p = profile(key)
    g = next(x for x in GOVS if x['key'] == key)
    b = p.get('budget') or {}
    pop = p.get('population')
    pr = p.get('per_resident') or {}
    off = p.get('officials') or {}
    mills = b.get('mills')
    # top cards: this government's figures for one fiscal year (government-years dataset; gov.js redraws them for the year in the bar)
    from page_datasets import government_years
    gy = [r for r in government_years() if r['gov_id'] == key]
    fy_start = 7 if key == 'schools' else 10
    today = date.today()
    cur_fy = today.year + 1 if today.month >= fy_start else today.year
    kp, fy_shown, period = year_cards(key, gy, cur_fy)
    static = []
    if key == 'schools':
        st = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'data', 'salaries', 'schools.json'))).get('stats') or {}
        n = st.get('total_employees_approx')
        if n:
            static.append(kpi('Employees', f'About {n:,}', 'per the superintendent, Oct 2025', static=True))
    secs = []
    # who's in charge
    if off.get('seats'):
        seats = off['seats']
        board = [s for s in seats if s.get('elected') or not STAFF.search(s['seat'])]
        staff = [s for s in seats if s not in board]
        pay = ''.join(f'<div class="ui-person">{_avatar(None, "amber", "dollar")}<span><b>{usd(x["annual"])}</b><small>{e(x["title"])}{" · " + e(x["name"]) if x.get("name") else ""} · {e(x.get("year") or "")}</small></span></div>' for x in p.get('pay') or [])
        links = ''.join(x for x in [
            f'<a class="ui-tag" href="{e(off["website"])}" target="_blank" rel="noopener">{ico("globe")}Website</a>' if off.get('website') else '',
            f'<a class="ui-tag" href="{e(off["contact_url"])}" target="_blank" rel="noopener">{ico("mail")}Contact</a>' if off.get('contact_url') else '',
            f'<a class="ui-tag" href="/who-runs-bay-county">{ico("users")}All officials</a>'])
        secs.append(f'''<section class="tx-sec"><div class="sec-hd"><h2 id="who">Who's in charge</h2><span class="muted">{e(off.get("form") or "")}</span></div>
          <p class="small muted" id="gxBoardNote">Today's officials. Pick a year in the bar at the top to see who held each seat, and who was manager, that year.</p>
          <div class="ui-people" id="gxBoard">{"".join(_person_card(s, i) for i, s in enumerate(board))}</div>
          {f'<h3 class="ui-h3">Appointed staff and pay</h3><div class="ui-row" id="gxStaff">{"".join(_person_card(s, i + 1, staff=True) for i, s in enumerate(staff))}{pay}</div>' if staff or pay else ''}
          <div class="ui-links">{links}</div></section>''')
    # money
    if b.get('revenue') or b.get('spending'):
        srcs = ' '.join(src(u, t) for t, u in b.get('sources', [])[:2])
        ctx = ''.join(f'<p class="note">{e(t)} {src(u)}</p>' for t, u in (b.get('context') or [])[:2])
        secs.append(f'''<section class="tx-sec"><div class="sec-hd"><h2 id="money">Money in, money out</h2><span class="muted">{e(b.get("status") or "")} budget{" · general fund " + money(b["general_fund"]) if b.get("general_fund") else ""}</span></div>
          <div class="two"><div><h3 class="h4">Where the money comes from</h3>{hbars(list((b.get("revenue") or {}).items()), "var(--s3)")}</div><div><h3 class="h4">What the general fund pays for</h3>{hbars(list((b.get("spending") or {}).items()))}</div></div>
          {ctx}<p class="src-line">{srcs} · <a href="/public-money/tax-dollars">Compare every government's budget</a>{' · <a href="/public-money/budget-explorer?gov=' + key + '">Budget explorer</a>' if p.get("budget_detail") else ''} · <a href="/public-money/budget-compare?gov={key}">Compare years</a></p></section>''')
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
        u = p['utility_bill']; static.append(kpi('Typical utility bill', f'${u["total"]:,.2f}', f'a month at 5,000 gallons at today\'s rates{"" if u.get("garbage") else ", garbage not included"} · <a href="/public-money/fees-and-bills?gov={key}">compare</a>', static=True))
    # meetings
    if p.get('meetings'):
        up = [x for x in p['meetings'] if not x.get('past')][:6]
        if up:
            secs.append(f'''<section class="tx-sec"><div class="sec-hd"><h2 id="meet">Upcoming meetings</h2><span class="muted">{len(up)} on the calendar</span><a class="ui-crumb" href="/meetings?gov={key}">All meetings {ico("arrow")}</a></div>
              {_meetings(up, key, p["short"])}</section>''')
    # get involved
    secs.append(f'''<section class="tx-sec act"><div class="sec-hd"><h2 id="act">Stay informed</h2></div>
      <div class="ui-act"><div>{ico("bell", "blue")}<h3>Get updates</h3><p>Email when {e(p["short"])} has new votes, contracts or corrections on this site.</p><p><a class="ui-btn pri" href="/alerts?gov={key}">Follow {e(p["short"])}</a></p></div>
      <div>{ico("folder", "amber")}<h3>Ask for a record</h3><p>Something missing here? Request it from {e(p["short"])} under Florida's public records law.</p><p><a class="ui-btn" href="/records-request?gov={key}">Request a record</a></p></div>
      <div>{ico("compare", "teal")}<h3>Compare</h3><p>See {e(p["short"])} side by side with other Bay County governments.</p><p><a class="ui-btn" href="/compare?g={key}">Compare</a></p></div></div></section>''')
    # sections filled in the browser by gov.js from the dashboards' published data, for the year in the bar
    def live(i, title, more=''):
        ic, tone, _ = SEC[i]
        return (f'<section class="tx-sec gx" id="{i}" hidden><div class="sec-hd">{ico(ic, tone)}<h2>{title}</h2><span class="muted" data-gx-sub></span></div>'
                f'<div class="kpis gx-kpis" data-gx-kpis></div><div data-gx-body></div><p class="src-line" data-gx-link></p>{more}</section>')
    # an icon in front of each server-drawn section heading
    secs = [re.sub(r'<div class="sec-hd"><h2 id="([a-z]+)">', lambda m: f'<div class="sec-hd">{ico(*SEC[m.group(1)][:2])}<h2 id="{m.group(1)}">', x, count=1) for x in secs]
    by_id = {re.search(r'id="([a-z]+)"', x).group(1): x for x in secs}
    cra = g.get('cra')
    live_secs = {'contracts': live('contracts', 'Contracts'), 'cra': live('cra', 'Redevelopment (CRA) spending') if cra else '',
                 'projects': live('projects', 'Projects'), 'votes': live('votes', 'How they voted'), 'savings': live('savings', 'Where it could spend less')}
    order = ['who', 'money', 'rate', 'contracts', 'cra', 'projects', 'votes', 'meet', 'debt', 'audits', 'savings', 'act']
    body = ''.join(by_id.get(i) or live_secs.get(i) or '' for i in order)
    # section tiles: a one-line preview under each name (gov.js fills the year-dependent ones)
    seats = off.get('seats') or []
    n_el = sum(1 for x in seats if x.get('elected') or not STAFF.search(x['seat']))
    up = [x for x in p.get('meetings') or [] if not x.get('past')]
    hint = {'who': ', '.join(x for x in [f'{n_el} elected' if n_el else '', f'{len(seats) - n_el} appointed' if len(seats) > n_el else ''] if x),
            'money': f'{money(b["total"])} {e(b.get("status") or "").split(" ")[0].lower() or "budget"}'.strip() if b.get('total') else 'Money in and out',
            'rate': f'{mills:g} mills' if mills else ('No city property tax' if mills == 0 else 'Rate history'),
            'contracts': 'Awards and how they were bid', 'cra': 'Redevelopment spending', 'projects': 'Budget to close-out', 'votes': 'Money votes',
            'meet': f'Next: {_md(up[0]["start"])}' if up else 'Calendar', 'debt': f'{money(p["debt"]["total"])} · {e(p["debt"].get("fy") or "").split(" ")[0]}' if p.get('debt') else 'What it owes',
            'audits': (lambda au: f'{len(au[0]["findings"])} finding{"s" if len(au[0]["findings"]) != 1 else ""} in {e(au[0]["fy"])}')(p['audits']) if p.get('audits') else 'Audit findings',
            'savings': 'Ways to spend less'}
    ids = [i for i in ['who', 'money', 'rate', 'contracts', 'cra', 'projects', 'votes', 'meet', 'debt', 'audits', 'savings'] if f'id="{i}"' in body]
    tiles = ''.join(f'<a href="#{i}" data-jump="{i}">{ico(SEC[i][0], SEC[i][1])}<span><b>{SEC[i][2]}</b><small>{hint.get(i, "")}</small></span></a>' for i in ids)
    mini = ''.join(f'<a href="#{i}">{ico(SEC[i][0])}{SEC[i][2]}</a>' for i in ids)
    glance = (f'<section class="tx-sec gx-glance" hidden><div class="sec-hd">{ico("pulse", "blue")}<h2 id="year">At a glance</h2><span class="muted" id="gxGlanceH"></span></div>'
              '<div class="kpis" id="gxGlance"></div><p class="muted small" data-gx-loading>Loading this government\'s records…</p></section>')
    cfg = {'key': key, 'short': p['short'], 'cra': cra or '', 'craName': CRA_NAME.get(cra, '') if cra else '', 'fyStart': fy_start}
    year = '<label class="sc-f sc-year" data-scope><span>Year</span><select id="gxYear" aria-label="Year"><option value="all">All years</option></select></label>'
    bar = city_bar(None, fixed=key, extra=year)
    lede = g.get('blurb') or f'{e(p["name"])}: who runs it, what it spends and owes, how its commission votes, and what the auditors found, all from public records.'
    kind = 'County' if key == 'county' else 'Schools' if key == 'schools' else 'City'
    form = (off.get('form') or '').split(';')[0].strip()
    tags = ''.join(x for x in [f'<span class="ui-tag">{ico({"County": "county", "Schools": "school"}.get(kind, "city"))}{kind}</span>',
                               f'<span class="ui-tag">{ico("gavel")}{e(form[:1].upper() + form[1:])}</span>' if form else '',
                               f'<a class="ui-tag" href="{e(off["website"])}" target="_blank" rel="noopener">{ico("globe")}Official website</a>' if off.get('website') else ''])
    return f'''<div class="page tax gov-page ui">
  <header class="ui-hero">
    <div class="ui-id"><span class="ui-badge t-blue">{ico({"County": "county", "Schools": "school"}.get(kind, "city"))}</span>
      <div><a class="ui-crumb" href="/governments">{ico("back")}All governments</a><h1>{e(p["short"])}</h1><p class="lede">{e(lede)}</p><div class="ui-tags">{tags}</div></div></div>
    <div class="ui-pick" data-report="skip">{bar}<button type="button" class="pdf-btn" id="pdf">{ico("folder")}Export PDF</button><span class="ui-upd">Data updated {DATA_UPDATED}</span></div>
  </header>
  <nav class="ui-tiles" aria-label="On this page" data-report="skip">{tiles}</nav>
  <nav class="ui-mini" aria-label="Sections" data-off data-report="skip">{mini}</nav>
  <section class="gx-top" aria-labelledby="gxTopH"><h2 class="gx-top-h muted" id="gxTopH">Fiscal year {fy_shown}{f" · {e(period)}" if period else ""}</h2>
  <div class="kpis" id="gxTop">{"".join(kp + static)}</div>{'' if gy else '<p class="muted small">No yearly figures on file for this government yet.</p>'}</section>
  {glance}
  {body}
  {_connections(key, p["short"])}
</div>
<link rel="stylesheet" href="/assets/tax.css">
<link rel="stylesheet" href="/assets/gov.css">
<script>window.GOVPAGE={_dumps(cfg)};</script>
<script src="/assets/gov.js" defer></script>'''


def _person_card(s, i, staff=False):
    """One official as a card: initials, name, seat. The card links to the person's profile when there is one.
    A staff card carries data-seat, so gov.js can swap in whoever held that job in the year picked."""
    from fees_page import split_note, term_txt
    from entity_links import href
    from entity_graph import build
    import ids
    name, note = split_note(s.get('holder'))
    term, _ = term_txt(s.get('term_end'))
    sub = ' · '.join(x for x in [e(s['seat']), f'until {e(term)}' if term else ''] if x)
    ds = f' data-seat="{e(s["seat"])}"' if staff else ''
    if not name:
        return f'<div class="ui-person vac"{ds}>{_avatar(None, "blue", "users")}<span><b>Not published online</b><small>{sub}</small></span></div>'
    pid = ids.person_id(name)
    url = href('person:' + pid) if pid and 'person:' + pid in build().ents else None
    inner = f'{_avatar(name, TONES[i % 4])}<span><b>{e(name)}</b><small>{sub}</small>{f"<small>{e(note)}</small>" if note else ""}</span>'
    return f'<a class="ui-person" href="{e(url)}"{ds}>{inner}</a>' if url else f'<div class="ui-person"{ds}>{inner}</div>'


def _dt(iso):
    from datetime import datetime
    try:
        return datetime.fromisoformat(iso)
    except Exception:
        return None


def _md(iso):
    d = _dt(iso or '')
    return d.strftime('%b %-d') if d else ''


def _date_tile(d):
    return (f'<span class="ui-date" aria-hidden="true"><span class="mo">{d.strftime("%b").upper()}</span>'
            f'<span class="d">{d.day}</span><span class="wd">{d.strftime("%a")}</span></span>')


def _meetings(up, key, short):
    """Upcoming meetings as cards: the next one large (agenda items, links), the rest as date cards.
    Each card carries data-start so gov.js can drop meetings that have passed since the page was built."""
    def when(d):
        return d.strftime('%-I:%M %p').replace(':00 ', ' ') if d and (d.hour or d.minute) else ''
    out = []
    for n, m in enumerate(up):
        d = _dt(m.get('start') or '')
        if not d:
            continue
        full = d.strftime('%A, %B %-d, %Y') + (f' at {when(d)}' if when(d) else '')
        posted = bool(m.get('agenda_url'))
        if not out:
            items = m.get('agenda_items') or [x.get('title') for x in m.get('items') or [] if x.get('title')]
            li = ''.join(f'<li>{e(t)}</li>' for t in items[:3]) + (f'<li class="more">+ {len(items) - 3} more agenda item{"s" if len(items) - 3 != 1 else ""}</li>' if len(items) > 3 else '')
            loc = re.sub(r'\s+-\s+', ', ', m.get('location') or '')
            acts = ''.join(x for x in [
                f'<a class="ui-btn pri" href="{e(m["agenda_url"])}" target="_blank" rel="noopener">{ico("file")}Agenda</a>' if posted else '',
                f'<a class="ui-btn" href="{e(m["packet_url"])}" target="_blank" rel="noopener">{ico("folder")}Full packet</a>' if m.get('packet_url') else '',
                f'<a class="ui-btn" href="{e(m["detail_url"])}" target="_blank" rel="noopener">{ico("globe")}Meeting page</a>' if m.get('detail_url') and not posted else '',
                f'<a class="ui-btn" href="/alerts?gov={key}">{ico("bell")}Get agenda alerts</a>' if not posted else ''])
            out.append(f'''<article class="ui-next" data-start="{e(m["start"])}" aria-label="{e(m.get("title") or "Meeting")}, {e(full)}"><div class="ui-nx">{_date_tile(d)}
              <div style="min-width:0"><span class="ui-pill t-salmon" data-when>Next meeting</span>{'<span class="ui-pill t-teal">Agenda posted</span>' if posted else ('<span class="ui-pill t-amber">Expected</span>' if m.get('expected') else '')}
              <h3>{e(m.get("title") or "Meeting")}</h3><div class="ui-meta">{f'<span>{ico("clock")}{e(full)}</span>'}{f'<span>{ico("pin")}{e(loc)}</span>' if loc else ''}</div></div></div>
              {f'<ol class="ui-items">{li}</ol>' if li else ''}{f'<div class="ui-acts">{acts}</div>' if acts else ''}</article>''')
            continue
        status = (f'<a href="{e(m["agenda_url"])}" target="_blank" rel="noopener">Agenda posted</a>' if posted else 'Expected' if m.get('expected') else 'Agenda not posted yet')
        out.append(f'<div class="ui-mc" data-start="{e(m["start"])}">{_date_tile(d)}<div style="min-width:0"><b>{e(m.get("title") or "Meeting")}</b><small>{e(full.split(", ")[0])}{" · " + when(d) if when(d) else ""}</small><small>{status}</small></div></div>')
    if not out:
        return ''
    later = ''.join(out[1:5])
    return (f'<div class="ui-meet{" solo" if not later else ""}">{out[0]}'
            + (f'<div class="ui-later">{later}<a class="ui-alert" href="/alerts?gov={key}">{ico("mail")}Email me when {e(short)} posts an agenda</a></div>' if later else '')
            + '</div>')


def _connections(key, short):
    from people_pages import profile_section, ASSETS
    return profile_section('gov:' + key, 'Connections', f'Officials who serve {short} and who it paid, from every record on the site') + ASSETS


def govs_index():
    from ui import dir_card, avatar
    ps = all_profiles()
    cards = []
    look = {'county': ('Bay County government', 'map', 'blue'), 'schools': ('School district', 'book', 'amber'), 'city': ('City', 'city', 'teal')}
    for p in ps:
        b = p.get('budget') or {}
        kind, icon, tone = look.get(p['kind'], look['city'])
        facts = [f'{p["population"]:,} residents' if p.get('population') and p['kind'] == 'city' else '',
                 f'{money(b["total"])} budget' if b.get('total') else '',
                 (f'{b["mills"]:g} mills' if b.get('mills') else 'no city property tax') if p['kind'] == 'city' else '',
                 f'{money((p.get("debt") or {}).get("total"))} in debt' if (p.get("debt") or {}).get("total") else '']
        n = (p.get("votes") or {}).get("n", 0)
        cards.append(dir_card(f'/governments/{p["slug"]}', p['short'], ' · '.join(x for x in facts if x), '', f'{n:,} votes' if n else kind,
                              av=avatar(p['short'], tone, icon)))
    cards = ''.join(cards)
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Governments</span><h1>Bay County's local governments</h1>
    <p class="lede">One page for each government: who runs it, its budget and tax rate, debt, audit findings, votes, contracts and projects. Pick yours, or compare them side by side.</p></div>
    <div class="stamp"><a class="pill" href="/compare">Compare governments</a></div></header>
  <h2 class="sr">Every local government</h2>
  <div class="ui-dir ui-dir-govs">{cards}</div>
  <p class="note">Bay County residents pay the county and school district, and city residents also pay their city. Unincorporated areas are served by the county alone. <a href="/my-address/">Find yours by address</a>.</p>
</div>
<link rel="stylesheet" href="/assets/tax.css">'''
