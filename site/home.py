"""Home page for baycounty.me: a photo of the county with the address search, today's facts, a photo card per menu
section, this week, and the money in one band."""
import json, os, html
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')


def _j(*p):
    return json.load(open(os.path.join(DATA, *p)))


def M(n, d=1):
    return f'${n/1e9:,.2f}B' if n >= 1e9 else f'${n/1e6:,.{d}f}M'


def stats():
    from tax_page import build_data
    td = build_data(); lv = {g: v[td['levyYear']] for g, v in td['levy'].items()}; lv_tot = sum(lv.values())
    cra = _j('merged.json')['payments']
    cra_done = [p for p in cra if p['count'] and p['amount'] and p['status'] in ('Spent', 'Committed')]  # planned and budgeted records are not counted
    cra_spent = sum(p['amount'] for p in cra_done)
    mi = _j('michael', 'michael.json'); pa = mi['fema_pa']['bay_totals']
    da = _j('debt_audit', 'debt_audit.json')
    debt = sum(x['total_debt'] for x in da['debt'] if x['total_debt'])
    latest = {}
    for a in da['audits']:
        latest.setdefault(a['government'], a)
    findings = sum(len(a['findings']) for a in latest.values())  # latest audit of each entity, the same scope as the repeats
    repeats = sum(1 for a in latest.values() for f in a['findings'] if f.get('repeat'))
    ts = _j('tourism', 'tourism_surtax.json')
    bt25 = sum(c['amount'] for c in ts['bed_tax']['collections'] if c['fy'] == 2025)
    pcb25 = sum(c['amount'] for c in ts['bed_tax']['collections'] if c['fy'] == 2025 and c['district'] == 'Panama City Beach')
    sp = ts['infra_surtax']['projects']
    done = sum(1 for p in sp if p['status'] == 'completed')
    ct = _j('contracts', 'contracts.json'); ct_n = sum(1 for c in ct['contracts'] if c.get('amount'))
    rec = _j('amendment3', 'rec_bay.json')
    a3 = -sum(r['impact']['FY2029'] for r in rec['bay'])
    return dict(lv_tot=lv_tot, school_share=lv['school'] / lv_tot, ngovs=len(td['govs']), cra_spent=cra_spent, cra_n=len(cra_done),
                fema=pa['federal_obligated'], fema_n=pa['projects'], ia=mi['fema_ia']['bay_total_approved_ihp_owners_plus_renters'],
                debt=debt, findings=findings, repeats=repeats, bt25=bt25, pcb_share=pcb25 / bt25, sp_n=len(sp), sp_done=done, a3=a3, ct_n=ct_n)


def topics(s):
    """(href, eyebrow, heading, blurb, stat, stat label) for every topic card; also used for link-preview images."""
    return [
        ('/public-money/tax-dollars', 'Tax Dollars', 'How your tax dollars are allocated', 'Your property tax bill, slice by slice, and where each government gets and spends its money.', M(s['lv_tot']), 'property tax levied, FY2026'),
        ('/public-money/cra-spending', 'CRA Spending', "Where the CRA money goes", 'Map and ledger of what the six redevelopment agencies bought, built and granted, and who was paid.', M(s['cra_spent']), f'documented across {s["cra_n"]} records'),
        ('/public-money/hurricane-michael', 'Hurricane Michael', 'Where the recovery money went', 'Every FEMA rebuilding project, aid to households, Rebuild Florida awards and debris costs.', M(s['fema'], 0), f'FEMA rebuilding money, {s["fema_n"]} projects'),
        ('/public-money/sales-tax-projects', 'Sales Tax Projects', 'Promised vs built', 'Every half-cent sales tax project on the county map, with its status, plus the school half-cent.', f'{s["sp_done"]:,} of {s["sp_n"]:,}', 'projects marked completed'),
        ('/public-money/tourist-tax', 'Tourist Tax', 'What visitors pay, and where it goes', 'Ten years of bed tax collections, how the pennies are split and what Visit PCB spends.', M(s['bt25']), f'collected in FY2025, {s["pcb_share"]:.0%} from the PCB zone'),
        ('/compare', 'Debt', 'What local governments owe', 'Debt per resident for every government, side by side; each government\'s page lists its bonds and loans.', M(s['debt']), 'owed, latest audit of each (FY2024 or FY2025)'),
        ('/governments', 'Audit Findings', 'What the auditors found', 'Up to three years of audit findings in plain English on each government\'s page, including problems that keep coming back.', f'{s["findings"]}', f'findings in the latest audits, {s["repeats"]} of them repeats'),
        ('/public-money/fees-and-bills', 'Fees & Bills', 'Fees on your tax bill, and water and garbage', 'Fire, stormwater and other flat fees, plus a typical monthly utility bill in each city.', '$28.1M', 'in flat fees on FY2026 tax bills'),
        ('/people', 'Officials', 'Officials and pay', 'Every official and candidate, the five county officers, and what top officials are paid.', '5', 'independently elected county officers'),
        ('/public-money/contracts', 'Contracts', 'Who gets the contracts', 'Major contracts since 2022: winners, how they were awarded, change orders and who the county paid most.', str(s['ct_n']), 'contracts tracked'),
        ('/public-money/amendment-3', 'Amendment 3', 'What changes if it passes', 'The property tax amendment on the November ballot: your bill before and after, and the state\'s estimates.', M(s['a3']), 'less for Bay governments in FY2029 (state est.)'),
    ]


# ---- Tax bill and budget figures for the Your money band ----

AREA_SHORT = {'Panama City - Downtown DIB': 'Downtown Panama City', 'unincorporated': 'Unincorporated',
              'unincorporated - beach area': 'Unincorporated beach'}
DEFAULT_AREA = 'Lynn Haven'
DEFAULT_VALUE = 200000


def bill_data():
    """Rates by taxing authority and the stack each area pays, latest tax year (tax/millage.json via tax_page).
    The same numbers are in the property-tax-rates and tax-districts datasets."""
    from tax_page import build_data, FY
    td = build_data()
    i = len(td['years']) - 1
    used = {a for d in td['districts'] for a in d['stack']}
    auth = {a: {'n': v['n'], 'g': v['g'], 'm': v['m'][i]} for a, v in td['auth'].items() if a in used}
    areas = [{'id': d['id'], 'n': AREA_SHORT.get(d['id'], d['label']), 'stack': d['stack'], 't': d['total'][i]} for d in td['districts']]
    return {'year': td['years'][i], 'fy': FY[i], 'auth': auth, 'areas': areas, 'value': DEFAULT_VALUE, 'area': DEFAULT_AREA}


def budget_data():
    """This year's adopted budgets: the total for every government, and the everyday General Fund
    spending of the county and cities grouped by service (same grouping as the budget explorer)."""
    from money_pages import SERVICES, _bench
    from govs import GOVS
    d = _j('civic', 'budgets_detail.json')
    kind = {g['key']: g['kind'] for g in GOVS}
    svc = {}
    for g in d['governments']:
        if kind.get(g['gov']) == 'schools':
            continue
        for k, v in _bench(g.get('general_fund_departments')).items():
            if k != 'total':
                svc[k] = svc.get(k, 0) + v['amount']
    names = dict(SERVICES)
    fy = d['governments'][0]['fiscal_year'].split(' ')[0]
    # the headline total is the adopted FY2027 budget of each government as it published it (Panama City's leaves out interfund
    # transfers; the county's and Parker's final-hearing figures await posted minutes); governments with no total are named, not guessed
    from page_datasets import government_years
    y27 = {r['gov_id']: r for r in government_years() if r['fiscal_year'] == 2027}
    have = [g for g in GOVS if (y27.get(g['key']) or {}).get('budget_total')]
    missing = [g['short'] for g in GOVS if g not in have]
    pending = [g['short'] for g in have if 'final hearing' in (y27[g['key']].get('budget_status') or '')]  # hearing held, minutes not posted yet
    return {'fy': fy, 'total': sum(g['total'] for g in d['governments']), 'n': len(d['governments']),
            'total27': sum(y27[g['key']]['budget_total'] for g in have), 'n27': len(have), 'n_all': len(GOVS), 'missing27': missing, 'pending27': pending,
            'services': sorted(((names[k], v) for k, v in svc.items()), key=lambda r: -r[1])}


def _money(v):
    return f'${round(v):,}'


# ---- Home page (2026-11 "Postcard" layout): a photo of the county up top, today's facts, four photo doors, this week,
# then the money in one band. Photos come from the site-photos dataset (site/site_photos.py) with their credits. ----

# the links each homepage door shows first; the rest of its menu section opens under "All N"
DOOR_PICKS = {'Living here': ['/my-address', '/beaches', '/events'],
              'Your money': ['/public-money/tax-dollars', '/public-money/fees-and-bills', '/compare'],
              'Your government': ['/people', '/governments', '/connections'],
              'Get involved': ['/meetings', '/notices', '/volunteer']}
# how the tax-bill sentence names each area ("A $200,000 home in ... pays")
AREA_IN = {'Panama City - Downtown DIB': 'downtown Panama City', 'unincorporated': 'unincorporated Bay County',
           'unincorporated - beach area': 'the unincorporated beach area'}


def _img(r, cls='', eager=False, big=False, alt=None):
    """An <img> for a site-photos row: the small copy for cards, the big one (with the small in srcset) for bands."""
    e = html.escape
    alt = r['title'] if alt is None else alt
    if big and r['small_path'] != r['photo_path']:
        src = (f'src="{e(r["photo_path"])}" srcset="{e(r["small_path"])} 800w, {e(r["photo_path"])} 1600w" sizes="(max-width: 640px) 100vw, 1360px"')
    else:
        src = f'src="{e(r["small_path"])}"'
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return f'<img class="{cls}" {src} alt="{e(alt)}" {load} decoding="async">'


def _credit(r, cls='h-pc-credit'):
    from site_photos import credit_html
    return f'<p class="{cls}">{html.escape(r["title"])} · {credit_html(r)}</p>'


def _doors():
    """One photo card per menu section (site_menu.menu()), so the homepage and the menu always list the same pages.
    The election-season section isn't a card: it's on the Today strip while it lasts."""
    from site_menu import menu, links
    from site_photos import photo, credit_html
    out = []
    for m in menu():
        if m.get('footer') or m.get('season'):
            continue
        ls = links(m)
        picks = [l for h in DOOR_PICKS.get(m['label'], []) for l in ls if l['href'] == h] or ls[:3]
        rest = [l for l in ls if l not in picks]
        start = (m.get('start') or {}).get('href') or ls[0]['href']
        ph = photo('door:' + m['label'])
        img = (f'<a class="h-pc-dimg" href="{start}" tabindex="-1" aria-hidden="true">{_img(ph, alt="")}</a>'
               f'<p class="h-pc-dcred">{credit_html(ph)}</p>') if ph else ''
        li = lambda l: f'<li><a href="{l["href"]}">{html.escape(l["label"])}</a></li>'
        more = (f'<details class="h-more"><summary>All {len(ls)}</summary><ul>{"".join(li(l) for l in rest)}</ul></details>' if rest else '')
        out.append(f'<div class="h-pc-door">{img}<div class="h-pc-dbody"><h3><a href="{start}">{html.escape(m["label"])}</a></h3>'
                   f'<p>{html.escape(m["question"])}</p><ul class="h-pc-picks">{"".join(li(l) for l in picks)}</ul>{more}</div></div>')
    return ''.join(out)


def _election_card():
    """The Today strip's election card, in election season only: where to vote until Election Day, then results."""
    from site_menu import election_season, ELECTION_DAY
    from ui import ico
    t = date.today()
    if not election_season(t):
        return ''
    day = f"{ELECTION_DAY.strftime('%a %b')} {ELECTION_DAY.day}"
    if t < ELECTION_DAY:
        href, title, sub = '/elections/voting', f'Election Day · {day}', 'Where and when to vote'
    elif t == ELECTION_DAY:
        href, title, sub = '/elections/live', 'Election Day is today', 'Live results from 7 p.m.'
    elif (t - ELECTION_DAY).days <= 17:
        href, title, sub = '/elections/live', 'Election results', f'The {ELECTION_DAY.strftime("%B")} {ELECTION_DAY.day} count, race by race'
    else:
        href, title, sub = '/elections/results', 'Election results', f'The {ELECTION_DAY.strftime("%B")} {ELECTION_DAY.day} election'
    return f'<a class="h-td" href="{href}">{ico("vote", "salmon")}<span><b>{title}</b><span>{sub}</span></span></a>'


def _today():
    """Live cards: today's beach flag, active alerts, the next public meeting and, in election season, the election.
    A signed-in resident's trash card (#hTrash) stays hidden unless their saved home's pickup is today, or tomorrow once
    it's evening (home.js). The alert map (#hAlertMap) goes under the strip, filled by home.js."""
    from datetime import datetime
    from page_datasets import beach_conditions, emergency_notices
    from govs import _load
    from ui import ico
    card = lambda href, icon, tone, title, sub, id='': (f'<a class="h-td" href="{href}"{f" id={chr(34)}{id}{chr(34)}" if id else ""}>{ico(icon, tone)}<span><b>{title}</b>'
                                                        f'<span>{sub}</span></span></a>')
    fc = sorted((r for r in beach_conditions() if r['kind'] == 'forecast'), key=lambda r: r['sort_order'])
    now = fc[0] if fc else {}
    flag = now.get('flag_color')
    beach = card('/beaches', 'flag', 'amber', html.escape(f'{flag} beach flag') if flag else 'Beach flags',
                 html.escape(f"{now['rip_current_risk']} rip current risk") if now.get('rip_current_risk') else "Today's flag at each beach")
    act = [n for n in emergency_notices() if n.get('status') == 'active' and not n.get('same_as')]
    kinds = {'weather': 'weather', 'boil-water': 'boil-water', 'evacuation': 'evacuation', 'road': 'road', 'utility': 'utility', 'safety': 'safety'}
    if act:
        by = {}
        for n in act:
            k = kinds.get(n['kind'], 'other')
            by[k] = by.get(k, 0) + 1
        sub = ', '.join(f'{v} {k}' for k, v in sorted(by.items(), key=lambda x: -x[1]))
        alerts = card('/emergency', 'storm', 'salmon', f'{len(act)} active notice{"s" if len(act) != 1 else ""}', html.escape(sub), 'hAlerts')
    else:
        alerts = card('/emergency', 'storm', 'salmon', 'No active alerts', 'Weather, boil-water and road notices', 'hAlerts')
    md = _load().get('meetings') or {'boards': [], 'meetings': []}
    boards = {b['id']: b for b in md.get('boards', [])}
    stamp = datetime.now().strftime('%Y-%m-%dT%H:%M')
    up = sorted((m for m in md['meetings'] if not m.get('past') and (m.get('start') or '') >= stamp), key=lambda m: m['start'])
    if up:
        m0 = up[0]
        dt = datetime.fromisoformat(m0['start'][:16])
        when = f"{dt.strftime('%a %b')} {dt.day}"
        meet = card('/meetings', 'calendar', 'blue', 'Next meeting · ' + when, html.escape(boards.get(m0['board'], {}).get('name') or m0['board']))
    else:
        meet = card('/meetings', 'calendar', 'blue', 'Meetings', 'When every board meets, with agendas')
    # each government's next few meetings, so a signed-in resident's card shows their own government's (home.js)
    per = {}
    for m in up:
        g = boards.get(m['board'], {}).get('gov') or 'county'
        if len(per.setdefault(g, [])) < 3:
            per[g].append([m['start'][:16], boards.get(m['board'], {}).get('name') or m['board']])
    if up:
        meet = meet.replace('<a class="h-td" href="/meetings">', f'<a class="h-td" href="/meetings" id="hMeet" data-next="{html.escape(json.dumps(per, separators=(",", ":")))}">', 1)
    trash = (f'<a class="h-td" id="hTrash" href="/utilities" hidden>{ico('trash', 'teal')}<span><b id="hTrashT"></b>'
             f'<span id="hTrashS"></span></span></a>')
    amap = '<div class="h-td h-amap" id="hAlertMap" hidden><a id="hAlertMapT" href="/emergency"></a><div id="hAlertMapBox" role="img" aria-label="Map of where this alert applies"></div></div>'
    return trash + beach + alerts + meet + _election_card(), amap


def _week():
    """This week: the special event on now (its road-closure page, with a photo) beside the next one-off events from
    the community-events dataset. Built daily; with no special event the list runs the full width."""
    import datetime as dtm
    from events_page import rows, _time
    from special_events import events as special
    from site_photos import photo
    from place import NAME
    e = html.escape
    rs = rows()
    today = date.today()
    t0, wk, soon = today.isoformat(), (today + dtm.timedelta(days=6)).isoformat(), (today + dtm.timedelta(days=21)).isoformat()
    n_week = sum(1 for r in rs if t0 <= r['starts'][:10] <= wk or r['starts'][:10] <= t0 <= (r['ends'] or r['starts'])[:10])
    cand = [r for r in rs if not r['recurring'] and r['category'] != 'Public meeting' and t0 < r['starts'][:10] <= soon]
    cand.sort(key=lambda r: (r['category'] == 'Library', r['starts']))  # community and chamber events before library programs
    seen, picks = set(), []
    for r in cand:
        if r['title'] in seen:
            continue
        seen.add(r['title'])
        picks.append(r)
    feat = ''
    for ev in special():
        first = (dtm.date.fromisoformat(ev['starts_at'][:10]) - dtm.timedelta(days=7)).isoformat()
        if first <= t0 <= ev['ends_at'][:10]:
            ph = photo('event:' + ev['id']) or photo('feature')
            day = dtm.date.fromisoformat(ev.get('race_day') or ev['starts_at'][:10])
            n = len(ev['closures'])
            img = _img(ph, 'h-pc-fimg', big=True, alt='') if ph else ''
            feat = (f'<a class="h-pc-feat" href="{e(ev["page"])}">{img}<span class="h-pc-fbody">'
                    f'<span class="h-pc-tag">{day.strftime("%A, %b")} {day.day} · {e(ev["town"])}</span><b>{e(ev["name"])}</b>'
                    f'<span>{n} road closures and delays. See what\'s closed now and play through the day on the map.</span>'
                    f'<span class="h-pc-btn">See the closure map →</span></span></a>')
            if ph:
                feat = f'<div class="h-pc-featw">{feat}{_credit(ph, "h-pc-fcred")}</div>'
            break
    picks = sorted(picks[:4 if feat else 6], key=lambda r: r['starts'])

    def row(r):
        d = dtm.date.fromisoformat(r['starts'][:10])
        when = d.strftime('%A') + ('' if r['all_day'] else ', ' + _time(r['starts']))
        where = ' · '.join(e(x) for x in (when, r['venue'] or r['town']) if x)
        return (f'<li><span class="h-pc-date" aria-hidden="true"><b>{d.strftime("%b").upper()}</b>{d.day}</span>'
                f'<span><a href="{e(r["url"])}" rel="noopener">{e(r["title"])}</a><small>{where}</small></span></li>')
    lst = (f'<div class="h-pc-list"><ul>{"".join(row(r) for r in picks) or "<li class=ev-none>No one-off events listed in the next three weeks.</li>"}</ul>'
           f'<a class="h-pc-lmore" href="/meetings">Public meetings this week →</a></div>')
    return f'''<section class="h-pc-sec" aria-labelledby="hweek">
    <div class="h-sec-hd"><div><h2 id="hweek" class="h-pc-h2">This week in {e(NAME)}</h2><p class="h-pc-lede">{n_week} events from public calendars.</p></div><a href="/events">All events →</a></div>
    <div class="h-pc-week{'' if feat else ' solo'}">{feat}{lst}</div>
  </section>'''


def home_page():
    s = stats()
    from place import NAME
    from site_photos import photo
    from ui import ico
    b = bill_data()
    bd = budget_data()
    area = next(a for a in b['areas'] if a['id'] == b['area'])
    val = b['value']
    today, amap = _today()
    hero = photo('hero')
    money = photo('money')
    data = json.dumps({'area': b['area'], 'value': val, 'areas': [{'id': a['id'], 'p': AREA_IN.get(a['id'], a['n']), 't': a['t']} for a in b['areas']]},
                      separators=(',', ':'))
    hero_img = _img(hero, 'h-pc-himg', eager=True, big=True) if hero else ''
    money_img = _img(money, 'h-pc-mimg', big=True, alt='') if money else ''
    return f'''<div class="page home h-home h-pc">
  <section class="h-pc-hero{'' if hero else ' nophoto'}" aria-labelledby="h1">
    {hero_img}
    <div class="h-pc-hin">
      <p class="h-pc-kick">{html.escape(NAME)}, Florida</p>
      <h1 id="h1">Everything about {html.escape(NAME)}, <span class="hl">in plain view.</span></h1>
      <p class="h-pc-sub">Beaches and storms, trash day and schools, your tax bill and who decides how it's spent. Every figure links to its source.</p>
      <form class="h-addr" action="/my-address/" method="get" role="search">
        <label class="sr" for="hq">Your address</label>
        <input id="hq" name="q" type="search" placeholder="Enter your address" autocomplete="street-address">
        <button type="submit">Look up</button>
      </form>
      <p class="h-addr-note" id="hAddrNote">One page for your address: tax bill, trash day, schools, evacuation zone and who represents you.</p>
      <div class="h-mine" id="hMine" hidden>
        <a class="h-mine-main" id="hMineLink" href="/my-address/">{ico('home', 'blue')}<span class="h-mine-t"><span class="h-mine-k">Your home</span><b id="hMineAddr"></b><span id="hMineSub"></span></span><span class="h-mine-go">Open<span class="ico i-arrow" aria-hidden="true"></span></span></a>
        <p class="h-mine-more"><a href="/account">My home: what's happening nearby</a><button type="button" id="hMineOther">Look up another address</button></p>
      </div>
    </div>
    {_credit(hero) if hero else ''}
  </section>

  <section class="h-pc-today" aria-labelledby="htd">
    <h2 class="sr" id="htd">Today in {html.escape(NAME)}</h2>
    <div class="h-today">{today}</div>
    {amap}
  </section>

  <section class="h-pc-sec" aria-labelledby="hdoors">
    <div class="h-sec-hd"><div><h2 id="hdoors" class="h-pc-h2">Find your way around</h2><p class="h-pc-lede">Four doors into everything on the site.</p></div></div>
    <div class="h-pc-doors">{_doors()}</div>
  </section>

  {_week()}

  <section class="h-pc-money{'' if money else ' nophoto'}" aria-labelledby="hmoneyband">
    {money_img}
    <div class="h-pc-min">
      <div class="h-pc-mlead">
        <p class="h-pc-kick">Your money</p>
        <h2 id="hmoneyband">A <span id="hTeaseVal">{_money(val)}</span> home in <span id="hTeaseArea">{html.escape(AREA_IN.get(area['id'], area['n']))}</span> pays <span class="hl" id="hTeaseAmt">{_money(area['t'] * val / 1000)}</span> a year.</h2>
        <p>Tax year {b['year']}, before exemptions. Pick where you live and your home's value to see each line of the bill, and how it compares across the county.</p>
        <a class="h-pc-cta" href="/public-money/tax-dollars">Open your tax bill →</a>
      </div>
      <div class="h-pc-stats">
        <a href="/compare#services"><b>{M(bd['total27'])}</b><span>Adopted FY2027 budgets, {bd['n27']} of {bd['n_all']} governments</span><i>Spending →</i></a>
        <a href="/compare#m-debt"><b>{M(s['debt'])}</b><span>Owed by the county, cities, schools and authorities, latest audits</span><i>Debt →</i></a>
        <a href="/compare#m-findings"><b>{s['findings']}</b><span>Findings in the latest audits, {s['repeats']} of them repeats</span><i>Audits →</i></a>
      </div>
    </div>
    {_credit(money, 'h-pc-credit h-pc-mcred') if money else ''}
  </section>
</div>
<script type="application/json" id="homeData">{data}</script>
<script src="/assets/home.js" defer></script>'''
