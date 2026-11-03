"""Government profile pages: /governments and /governments/<slug>."""
import html, json, os, re
from datetime import date
from city_filter import city_bar
from govs import CRA_NAME
from gov_detail import debt_detail, audit_section, savings_section, savings_hint, budget_detail
from site_menu import OPEN_BOOKS_PUBLIC
OPEN_BOOKS_LINKS = ' · <a href="/public-money/budget-tracker?gov={key}">Spending against the budget</a> · <a href="/public-money/checkbook?gov={key}">Every payment</a>'
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


_Y27 = {}


def budget27(key):
    """The adopted FY2027 budget total of a government as it published it, or None (Mexico Beach has not published one)."""
    if not _Y27:
        from page_datasets import government_years
        _Y27.update({r['gov_id']: r.get('budget_total') for r in government_years() if r['fiscal_year'] == 2027})
        _Y27.setdefault('_', None)
    return _Y27.get(key)


def hbars(rows, color='var(--s1)'):
    rows = [(k, v) for k, v in rows if v]
    if not rows:
        return ''
    mx = max(v for _, v in rows)
    return '<div class="hbars">' + ''.join(f'<div class="hb"><span class="hb-n">{e(k)}</span><span class="hb-track"><span class="hb-bar" style="width:{v/mx*100:.1f}%;background:{color}"></span></span><span class="hb-v">{money(v)}</span></div>' for k, v in sorted(rows, key=lambda kv: -kv[1])) + '</div>'


from ui import ico, avatar as _avatar, TONES, tone_of, photo_of, photos  # shared pieces (ui.css)


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
        # no change is shown when the two years are not the same kind of total (a draft, or one with and one without interfund transfers)
        if prev.get('budget_total') and not re.search(r'(?i)draft|tentative', prev.get('budget_status') or '') and bool(r.get('budget_excludes_transfers')) == bool(prev.get('budget_excludes_transfers')):
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
            last = max((x for x in rows if x.get('debt_total') and x['fiscal_year'] < fy), key=lambda x: x['fiscal_year'], default=None)
            if last:
                per = f"{usd(last['debt_total'] / last['population'])} per resident · " if last.get('population') and key != 'schools' else ''
                out.append(kpi('Debt', money(last['debt_total']), f"{per}latest audit, end of FY{last['fiscal_year']} " + src(last.get('debt_source_url'))))
            else:
                out.append(none('Debt', 'Audited total on file for ' + ', '.join(f"FY{x['fiscal_year']}" for x in rows if x.get('debt_total')) + ' only'))
    if has('employees_fte'):
        out.append(kpi('Employees', f"{r['employees_fte']:,g}", f'FY{fy} budget, staff positions') if r.get('employees_fte') else none('Employees', f'No FY{fy} count on file'))
    return out, fy, r.get('period') or ''


SAV_ASSETS = '<link rel="stylesheet" href="/assets/savings.css"><script src="/assets/savings.js" defer></script>'


def gov_page(key):
    from fees_page import roster_li, STAFF, split_note
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
        pay_rows = _fold_pay(p.get('pay') or [])
        # a staff member who also has a pay row gets one card: the pay goes on their staff card
        import ids
        staff_pay = {}
        for s in staff:
            pid = ids.person_id(split_note(s.get('holder'))[0] or '')
            hit = next((x for x in pay_rows if pid and x.get('name') and ids.person_id(x['name']) == pid), None)
            if hit:
                staff_pay[s['seat']] = hit
                pay_rows.remove(hit)
        pay = ''.join(_pay_card(x) for x in pay_rows)
        links = ''.join(x for x in [
            f'<a class="ui-tag" href="{e(off["website"])}" target="_blank" rel="noopener">{ico("globe")}Website</a>' if off.get('website') else '',
            f'<a class="ui-tag" href="{e(off["contact_url"])}" target="_blank" rel="noopener">{ico("mail")}Contact</a>' if off.get('contact_url') else '',
            f'<a class="ui-tag" href="/people">{ico("users")}All officials</a>'])
        secs.append(f'''<section class="tx-sec"><div class="sec-hd"><h2 id="who">Who's in charge</h2><span class="muted">{e(off.get("form") or "")}</span></div>
          <p class="small muted" id="gxBoardNote">Today's officials. Pick a year in the bar at the top to see who held each seat, and who was manager, that year.</p>
          <div class="ui-people" id="gxBoard">{"".join(_person_card(s, i) for i, s in enumerate(board))}</div>
          {f'<h3 class="ui-h3">Appointed staff and pay</h3><div class="ui-row" id="gxStaff">{"".join(_person_card(s, i + 1, staff=True, pay=staff_pay.get(s['seat'])) for i, s in enumerate(staff))}{pay}</div>' if staff or pay else ''}
          <div class="ui-links">{links}</div></section>''')
    # money
    if b.get('revenue') or b.get('spending'):
        srcs = ' '.join(src(u, t) for t, u in b.get('sources', [])[:2])
        ctx = ''.join(f'<p class="note">{e(t)} {src(u)}</p>' for t, u in (b.get('context') or [])[:2])
        secs.append(f'''<section class="tx-sec"><div class="sec-hd"><h2 id="money">Money in, money out</h2><span class="muted" data-money-sub>{e(b.get("status") or "")} budget{" · general fund " + money(b["general_fund"]) if b.get("general_fund") else ""}</span></div>
          <div data-money-body><div class="two"><div><h3 class="h4">Where the money comes from</h3>{hbars(list((b.get("revenue") or {}).items()), "var(--s3)")}</div><div><h3 class="h4">What the general fund pays for</h3>{hbars(list((b.get("spending") or {}).items()))}</div></div>
          {ctx}{budget_detail(key, pop)}</div><p class="src-line"><span data-money-src>{srcs}</span> · <a href="/compare#services">Compare every government's budget</a> · <a href="/public-money/budget-compare?gov={key}">Compare years</a>{OPEN_BOOKS_LINKS.format(key=key) if OPEN_BOOKS_PUBLIC else ''}{' · <a href="/public-money/cra-tax-increment">Property tax paid to CRAs</a>' if key == 'county' else ''}</p></section>''')
    # tax rate history
    m = p.get('millage')
    if m and any(x is not None for x in m.get('rate') or []):
        trip = [(y, v, (m.get('rolled_back') or [None] * len(m['rate']))[i]) for i, (y, v) in enumerate(zip(m['years'], m['rate'])) if v is not None]
        yrs, r, rb = [t[0] for t in trip], [t[1] for t in trip], [t[2] for t in trip]
        mx = max(r + [x for x in rb if x]) or 1
        rows = ''.join(f'<div class="hb" data-ty="{y}"><span class="hb-n">Tax year {y}</span><span class="hb-track"><span class="hb-bar" style="width:{v/mx*100:.1f}%;background:var(--s1)"></span>{f"<i class=mk style=left:{rb[i]/mx*100:.1f}% title=\"Rolled-back rate {rb[i]}\"></i>" if i < len(rb) and rb[i] else ""}</span><span class="hb-v">{v:g}</span></div>' for i, (y, v) in enumerate(zip(yrs, r)))
        up = (r[-1] > rb[-1]) if r and rb and rb[-1] else None
        secs.append(f'''<section class="tx-sec"><div class="sec-hd"><h2 id="rate">Property tax rate</h2><span class="muted">Mills: dollars per $1,000 of taxable value</span></div>
          <p class="gx-yr" data-rate-yr hidden></p>
          <div class="hbars">{rows}</div>
          <p class="note">The tick on each bar is the <span class="term" data-term="rolled-back">rolled-back rate</span>, the rate that would bring in the same money as the year before. {f"The latest rate is {'above' if up else 'at or below'} it{', so the city takes in more from existing property than the year before' if up else ''}." if up is not None else ''} <a href="/public-money/tax-dollars">See your full tax bill</a></p></section>''')
    # debt
    d = p.get('debt')
    if d:
        secs.append(f'''<section class="tx-sec"><div class="sec-hd"><h2 id="debt">Debt</h2><span class="muted">{e(d.get("fy") or "")}</span></div>
          <p class="gx-yr" data-debt-yr hidden></p>
          <p><b>{money(d["total"])}</b> owed{f" — about {usd(pr['debt'])} per resident" if pr.get("debt") else ""}. {e(d.get("note") or "")}</p>
          {debt_detail(key)}
          <p class="src-line">{src(d.get("source_url"), "Audited financial statements")} · <a href="/compare">Compare debt across governments</a></p></section>''')
    # audits: every year on file, with each finding
    au = p.get('audits')
    if audit_section(key):
        secs.append(audit_section(key))
    if p.get('utility_bill'):
        u = p['utility_bill']; static.append(kpi('Typical utility bill', f'${u["total"]:,.2f}', f'a month at 5,000 gallons at today\'s rates{"" if u.get("garbage") else ", garbage not included"} · <a href="/public-money/fees-and-bills?gov={key}">compare</a>', static=True))
    # meetings
    up = [x for x in p.get('meetings') or [] if not x.get('past')][:6]
    secs.append(f'''<section class="tx-sec"><div class="sec-hd"><h2 id="meet" data-meet-h>Upcoming meetings</h2><span class="muted" data-meet-sub>{len(up)} on the calendar</span><a class="ui-crumb" href="/meetings?gov={key}">All meetings {ico("arrow")}</a></div>
      <div data-meet-up>{_meetings(up, key, p["short"]) if up else f'<p class="muted small">No meetings on the calendar right now. <a href="/alerts?gov={key}">Email me when {e(p["short"])} posts an agenda</a></p>'}</div><div data-meet-yr hidden></div></section>''')
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
    live_secs = {'contracts': live('contracts', 'Contracts'), 'cra': live('cra', 'Redevelopment (CRA) spending', '<p class="src-line"><a href="/public-money/cra-tax-increment#cras">How much property tax this CRA gets each year, and from whom →</a></p>') if cra else '',
                 'projects': live('projects', 'Projects'), 'votes': live('votes', 'How they voted'), 'savings': savings_section(key)}
    live_secs['savings'] = live_secs['savings'].replace('<div class="sec-hd"><h2>', f'<div class="sec-hd">{ico(*SEC["savings"][:2])}<h2>', 1)
    order = ['who', 'money', 'rate', 'contracts', 'cra', 'projects', 'votes', 'meet', 'debt', 'audits', 'savings', 'act']
    body = ''.join(by_id.get(i) or live_secs.get(i) or '' for i in order)
    # section tiles: a one-line preview under each name (gov.js fills the year-dependent ones)
    seats = off.get('seats') or []
    n_el = sum(1 for x in seats if x.get('elected') or not STAFF.search(x['seat']))
    up = [x for x in p.get('meetings') or [] if not x.get('past')]
    hint = {'who': ', '.join(x for x in [f'{n_el} elected' if n_el else '', f'{len(seats) - n_el} appointed' if len(seats) > n_el else ''] if x),
            'money': f'{money(budget27(p["key"]))} FY2027 budget' if budget27(p['key']) else (f'{money(b["total"])} FY2026 budget' if b.get('total') else 'Money in and out'),
            'rate': f'{mills:g} mills' if mills else ('No city property tax' if mills == 0 else 'Rate history'),
            'contracts': 'Awards and how they were bid', 'cra': 'Redevelopment spending', 'projects': 'Budget to close-out', 'votes': 'Every recorded vote',
            'meet': f'Next: {_md(up[0]["start"])}' if up else 'Calendar', 'debt': f'{money(p["debt"]["total"])} · {e(p["debt"].get("fy") or "").split(" ")[0]}' if p.get('debt') else 'What it owes',
            'audits': (lambda au: f'{len(au[0]["findings"])} finding{"s" if len(au[0]["findings"]) != 1 else ""} in {e(au[0]["fy"])}')(p['audits']) if p.get('audits') else 'Audit findings',
            'savings': savings_hint(key)}
    ids = [i for i in ['who', 'money', 'rate', 'contracts', 'cra', 'projects', 'votes', 'meet', 'debt', 'audits', 'savings'] if f'id="{i}"' in body]
    tiles = ''.join(f'<a href="#{i}" data-jump="{i}">{ico(SEC[i][0], SEC[i][1])}<span><b>{SEC[i][2]}</b><small>{hint.get(i, "")}</small></span></a>' for i in ids)
    mini = ''.join(f'<a href="#{i}">{ico(SEC[i][0])}{SEC[i][2]}</a>' for i in ids)
    glance = (f'<section class="tx-sec gx-glance" hidden><div class="sec-hd">{ico("pulse", "blue")}<h2 id="year">At a glance</h2><span class="muted" id="gxGlanceH"></span></div>'
              '<div class="kpis" id="gxGlance"></div><p class="muted small" data-gx-loading>Loading this government\'s records…</p></section>')
    from gov_detail import budget_fy
    cfg = {'key': key, 'short': p['short'], 'cra': cra or '', 'craName': CRA_NAME.get(cra, '') if cra else '', 'fyStart': fy_start, 'budgetFY': budget_fy(key),
           'photos': {k: v['photo_path'] for k, v in photos().items() if ':' not in k}}
    year = '<label class="sc-f sc-year" data-scope><span>Year</span><select id="gxYear" aria-label="Year"><option value="all">All years</option></select></label>'
    bar = city_bar(None, fixed=key, extra=year)
    lede = g.get('blurb') or f'{e(p["name"])}: who runs it, what it spends and owes, how its commission votes, and what the auditors found, all from public records.'
    kind = 'County' if key == 'county' else 'Schools' if key == 'schools' else 'City'
    form = (off.get('form') or '').split(';')[0].strip()
    tags = ''.join(x for x in [f'<span class="ui-tag">{ico({"County": "county", "Schools": "school"}.get(kind, "city"))}{kind}</span>',
                               f'<span class="ui-tag">{ico("gavel")}{e(form[:1].upper() + form[1:])}</span>' if form else '',
                               f'<a class="ui-tag" href="{e(off["website"])}" target="_blank" rel="noopener">{ico("globe")}Official website</a>' if off.get('website') else ''])
    import completeness
    dc = completeness.by_gov(key)
    tags = completeness.chip(key, dc) + tags if dc else tags
    return f'''<div class="page tax gov-page ui">
  <header class="ui-hero">
    <div class="ui-id"><span class="ui-badge t-blue">{ico({"County": "county", "Schools": "school"}.get(kind, "city"))}</span>
      <div><a class="ui-crumb" href="/governments">{ico("back")}All governments</a><h1>{e(p["short"])}</h1><p class="lede">{e(lede)}</p><div class="ui-tags">{tags}</div></div></div>
    <div class="ui-pick" data-report="skip">{bar}<button type="button" class="pdf-btn" id="pdf">{ico("folder")}Export PDF</button><span class="ui-upd">Data updated {DATA_UPDATED}</span></div>
  </header>
  <nav class="ui-tiles" aria-label="On this page" data-report="skip">{tiles}</nav>
  <nav class="ui-mini" aria-label="Sections" data-off data-report="skip">{mini}</nav>
  {completeness.table(key, dc, p["short"]) if dc else ""}
  <section class="gx-top" aria-labelledby="gxTopH"><h2 class="gx-top-h muted" id="gxTopH">Fiscal year {fy_shown}{f" · {e(period)}" if period else ""}</h2>
  <div class="kpis" id="gxTop">{"".join(kp + static)}</div>{'' if gy else '<p class="muted small">No yearly figures on file for this government yet.</p>'}</section>
  {glance}
  {body}
  {_connections(key, p["short"])}
</div>
<link rel="stylesheet" href="/assets/tax.css">
<link rel="stylesheet" href="/assets/gov.css">
<script>window.GOVPAGE={_dumps(cfg)};</script>
<script src="/assets/gov.js" defer></script><script src="/assets/completeness.js" defer></script>{SAV_ASSETS if 'id="svList"' in body else ''}'''


def _pay_year(x):
    import re
    m = re.search(r'(19|20)\d\d', str(x.get('year') or ''))
    return int(m.group(0)) if m else 0


def _fold_pay(rows):
    """One pay row per person and job, in the order given: the latest year, with the year before noted as 'was'."""
    import ids
    key = lambda x: (ids.person_id(x['name']) if x.get('name') else None, (x.get('title') or '').lower())
    best = {}
    for x in rows:
        k = key(x)
        best.setdefault(k, []).append(x)
    out = []
    for x in rows:
        k = key(x)
        if k not in best:
            continue
        group = sorted(best.pop(k), key=_pay_year, reverse=True)
        top = dict(group[0])
        if len(group) > 1 and group[1].get('annual'):
            prev = group[1]
            top['was'] = f"was {usd(prev['annual'])}" + (f" in {prev['year']}" if prev.get('year') else '')
        out.append(top)
    return out


def _pay_line(x, with_title):
    return ' · '.join(v for v in [e(x['title']) if with_title else '', usd(x['annual']), e(x.get('year') or ''), e(x.get('was') or '')] if v)


def _pay_card(x):
    """One pay row as a card. The person's name is the title (linked to their profile, like the staff cards);
    the job, salary and year sit underneath. A row with no name (a combined board total) leads with the job."""
    from entity_links import href
    from entity_graph import build
    import ids
    name = x.get('name')
    sub = _pay_line(x, bool(name))
    if not name:
        return f'<div class="ui-person">{_avatar(None, "amber", "dollar")}<span><b>{e(x["title"])}</b><small>{sub}</small></span></div>'
    pid = ids.person_id(name)
    url = href('person:' + pid) if pid and 'person:' + pid in build().ents else None
    inner = f'{_avatar(name, tone_of(name), photo=photo_of(pid))}<span><b>{e(name)}</b><small>{sub}</small></span>'
    return f'<a class="ui-person" href="{e(url)}">{inner}</a>' if url else f'<div class="ui-person">{inner}</div>'


def _person_card(s, i, staff=False, pay=None):
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
    if staff and pid:
        ds += f' data-pid="{e(pid)}"'
    url = href('person:' + pid) if pid and 'person:' + pid in build().ents else None
    inner = f'{_avatar(name, TONES[i % 4], photo=photo_of(pid))}<span><b>{e(name)}</b><small>{sub}</small>{f"<small>{e(note)}</small>" if note else ""}{f'<small class="gx-pay">{_pay_line(pay, False)}</small>' if pay else ""}</span>'
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
    import completeness
    dc_rows = completeness.rows()
    ps = all_profiles()
    cards = []
    look = {'county': ('Bay County government', 'map', 'blue'), 'schools': ('School district', 'book', 'amber'), 'city': ('City', 'city', 'teal')}
    for p in ps:
        b = p.get('budget') or {}
        kind, icon, tone = look.get(p['kind'], look['city'])
        facts = [f'{p["population"]:,} residents' if p.get('population') and p['kind'] == 'city' else '',
                 (f'{money(budget27(p["key"]))} FY2027 budget' if budget27(p['key']) else f'{money(b["total"])} FY2026 budget' if b.get('total') else ''),
                 (f'{b["mills"]:g} mills' if b.get('mills') else 'no city property tax') if p['kind'] == 'city' else '',
                 f'{money((p.get("debt") or {}).get("total"))} in debt' if (p.get("debt") or {}).get("total") else '']
        dc = completeness.by_gov(p['key'], dc_rows)
        cards.append(dir_card(f'/governments/{p["slug"]}', p['short'], ' · '.join(x for x in facts if x), '', completeness.card_chip(p['key'], dc) if dc else kind,
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
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/completeness.js" defer></script>'''
