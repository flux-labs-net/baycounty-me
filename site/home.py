"""Home page for baycounty.me: address search, headline numbers, every topic, what's new."""
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
    td = build_data(); lv = {g: v[-1] for g, v in td['levy'].items()}; lv_tot = sum(lv.values())
    cra = _j('merged.json')['payments']
    cra_spent = sum(p['amount'] for p in cra if p['count'] and p['amount'] and p['status'] in ('Spent', 'Committed'))
    mi = _j('michael', 'michael.json'); pa = mi['fema_pa']['bay_totals']
    da = _j('debt_audit', 'debt_audit.json')
    debt = sum(x['total_debt'] for x in da['debt'] if x['total_debt'])
    findings = sum(len(a['findings']) for a in da['audits'])
    latest = {}
    for a in da['audits']:
        latest.setdefault(a['government'], a)
    repeats = sum(1 for a in latest.values() for f in a['findings'] if f.get('repeat'))
    ts = _j('tourism', 'tourism_surtax.json')
    bt25 = sum(c['amount'] for c in ts['bed_tax']['collections'] if c['fy'] == 2025)
    pcb25 = sum(c['amount'] for c in ts['bed_tax']['collections'] if c['fy'] == 2025 and c['district'] == 'Panama City Beach')
    sp = ts['infra_surtax']['projects']
    done = sum(1 for p in sp if p['status'] == 'completed')
    ct = _j('contracts', 'contracts.json'); ct_n = sum(1 for c in ct['contracts'] if c.get('amount'))
    rec = _j('amendment3', 'rec_bay.json')
    a3 = -sum(r['impact']['FY2029'] for r in rec['bay'])
    return dict(lv_tot=lv_tot, school_share=lv['school'] / lv_tot, ngovs=len(td['govs']), cra_spent=cra_spent, cra_n=len(cra),
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
        ('/compare', 'Debt', 'What local governments owe', 'Debt per resident for every government, side by side; each government\'s page lists its bonds and loans.', M(s['debt']), 'owed across Bay County governments'),
        ('/governments', 'Audit Findings', 'What the auditors found', 'Three years of audit findings in plain English on each government\'s page, including problems that keep coming back.', f'{s["findings"]}', f'findings, {s["repeats"]} repeats in the latest audits'),
        ('/public-money/fees-and-bills', 'Fees & Bills', 'Fees on your tax bill, and water and garbage', 'Fire, stormwater and other flat fees, plus a typical monthly utility bill in each city.', '$28.1M', 'in flat fees on FY2026 tax bills'),
        ('/people', 'Officials', 'Officials and pay', 'Every official and candidate, the five county officers, and what top officials are paid.', '5', 'independently elected county officers'),
        ('/public-money/contracts', 'Contracts', 'Who gets the contracts', 'Major contracts since 2022: winners, how they were awarded, change orders and who the county paid most.', str(s['ct_n']), 'contracts tracked'),
        ('/public-money/amendment-3', 'Amendment 3', 'What changes if it passes', 'The property tax amendment on the November ballot: your bill before and after, and the state\'s estimates.', M(s['a3']), 'less for Bay governments in FY2029 (state est.)'),
    ]


# ---- Home page (2026 redesign): start with your bill, then follow the money ----

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


def money_data():
    """Small breakdowns for the follow-the-money tiles."""
    from govs import GOVS
    mi = _j('michael', 'michael.json')
    cats = sorted(mi['fema_pa']['by_category'], key=lambda c: -c['federal_obligated'])
    da = _j('debt_audit', 'debt_audit.json')
    short = lambda name: next((g['short'] for g in GOVS if g['debt'] and name.startswith(g['debt'])), name.split(' (')[0])
    debt = sorted(((short(x['government']), x['total_debt']) for x in da['debt'] if x['total_debt']), key=lambda r: -r[1])
    return {'fema': [(c['description'], c['federal_obligated']) for c in cats], 'debt': debt, 'budget': budget_data()}


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
    return {'fy': fy, 'total': sum(g['total'] for g in d['governments']), 'n': len(d['governments']),
            'services': sorted(((names[k], v) for k, v in svc.items()), key=lambda r: -r[1])}


def _money(v):
    return f'${round(v):,}'


def _bars(rows, colors):
    top = rows[0][1]
    return ''.join(f'<span style="height:{max(4, v / top * 100):.0f}%;background:var({colors[min(k, len(colors) - 1)]})" title="{html.escape(n)}: {M(v)}"></span>'
                   for k, (n, v) in enumerate(rows[:5]))


def home_page():
    s = stats()
    from updates import CHANGES, nice
    from events_page import home_section
    from govs import GOVS
    from place import NAME
    b = bill_data()
    md = money_data()
    election = date.today() <= date(2026, 11, 3)
    area = next(a for a in b['areas'] if a['id'] == b['area'])
    val = b['value']
    # server-rendered first state; home.js redraws on every change
    lines = ''.join(
        f'<li class="g-{b["auth"][a]["g"]}"><span class="rl-n"><i></i>{html.escape(b["auth"][a]["n"])}</span>'
        f'<span class="rl-m">{b["auth"][a]["m"]:.4f}</span><span class="rl-v">{_money(b["auth"][a]["m"] * val / 1000)}</span></li>'
        for a in area['stack'])
    segs = ''.join(f'<span class="g-{b["auth"][a]["g"]}" style="flex:{b["auth"][a]["m"]}"></span>' for a in area['stack'])
    chips = ''.join(f'<button type="button" data-area="{html.escape(a["id"])}" aria-pressed="{"true" if a["id"] == b["area"] else "false"}">{html.escape(a["n"])}</button>'
                    for a in b['areas'])
    tmax = max(a['t'] for a in b['areas'])
    ranked = ''.join(
        f'<li{" class=on" if a["id"] == b["area"] else ""}><button type="button" data-area="{html.escape(a["id"])}"><span class="cb-n">{html.escape(a["n"])}</span>'
        f'<span class="cb-t"><span style="width:{a["t"] / tmax * 100:.1f}%"></span></span><span class="cb-v">{_money(a["t"] * val / 1000)}</span></button></li>'
        for a in sorted(b['areas'], key=lambda a: -a['t']))
    news = ''.join(f'<li><span class="hn-d">{nice(c["date"])}</span><a href="{c["pages"][0]}">{html.escape(c["title"])}</a></li>' for c in CHANGES[:4])
    govchips = ''.join(f'<a href="/governments/{g["slug"]}">{html.escape(g["short"])}</a>' for g in GOVS)
    bd = md['budget']
    budget_bars = _bars(bd['services'], ['--navy', '--blue', '--blue', '--bar', '--bar'])
    short = {'Police / law enforcement': 'police', 'Administration & support': 'administration', 'Parks & recreation': 'parks', 'Fire': 'fire', 'Streets & public works': 'streets'}
    top2 = ', '.join(f'{short.get(n, n.lower())} {M(v)}' for n, v in bd['services'][:2])
    debt_bars = _bars(md['debt'], ['--salmon', '--salmon', '--gold', '--gold', '--bar'])
    data = json.dumps(b, separators=(',', ':'))
    return f'''<div class="page home h-home">
  <section class="h-hero" aria-labelledby="h1">
    <div class="h-intro">
      <span class="eyebrow">Step 1 · What you pay</span>
      <h1 id="h1">Your money.<br>Their decisions.<br><span class="hl">Follow it.</span></h1>
      <p class="lede">Start with your tax bill, then follow the spending, the debt and the audits for {html.escape(NAME)}. Every figure links to its source.</p>
      <div class="h-ctl">
        <span class="h-lbl" id="areaLbl">Where you live</span>
        <div class="h-chips" role="group" aria-labelledby="areaLbl">{chips}</div>
        <label class="h-lbl h-val" for="hVal"><span>Taxable value</span><output id="hValOut" for="hVal">{_money(val)}</output></label>
        <input id="hVal" type="range" min="50000" max="600000" step="10000" value="{val}">
      </div>
    </div>

    <div class="h-bill">
      <div class="hb-hd"><div><span class="eyebrow mute">Who you pay · tax year {b["year"]}</span><b id="billArea">{html.escape(area["n"])}</b></div><span class="hb-fy">{b["fy"]}<br>rates</span></div>
      <div class="hb-stack" id="billStack" aria-hidden="true">{segs}</div>
      <div class="hb-cols"><span>Levied by</span><span>Mills</span><span>You pay</span></div>
      <ul class="hb-lines" id="billLines">{lines}</ul>
      <div class="hb-total" aria-live="polite"><b>Total</b><span id="billMills">{area["t"]:.4f}</span><span id="billTotal">{_money(area["t"] * val / 1000)}</span></div>
      <p class="hb-note">Rate × taxable value, before exemptions. Flat fees (fire, stormwater, garbage) are billed separately. <a href="/public-money/tax-dollars">Full calculator →</a></p>
      <form class="hb-addr" action="/my-address/" method="get" role="search">
        <label class="sr" for="hq">Your address</label>
        <input id="hq" name="q" type="search" placeholder="Use your exact address" autocomplete="off">
        <button type="submit">Look up</button>
      </form>
    </div>
    <div class="h-card h-compare">
        <div class="h-card-hd"><b>Same home, every area</b><span class="muted">at <span data-val>{_money(val)}</span></span></div>
        <ol class="cmp-bars" id="cmpBars">{ranked}</ol>
      </div>
  </section>

  {home_section()}

  <section class="h-follow" aria-labelledby="follow">
    <div class="h-sec-hd"><div><span class="eyebrow">Step 2 · Follow it</span><h2 id="follow">Where it went, and who's checking.</h2></div><a href="/public-money/accountability">Accountability console →</a></div>
    <div class="h-tiles">
      <a class="h-tile t-blue" href="/compare#services">
        <span class="eyebrow">Spending · {bd['fy']}</span>
        <span class="mini" aria-hidden="true">{budget_bars}</span>
        <b class="fig">{M(bd['total'])}</b><span class="h-tl">Budgeted this year</span><span class="muted">{bd['n']} governments · biggest everyday costs: {html.escape(top2)}</span>
      </a>
      <a class="h-tile t-salmon" href="/compare#m-debt">
        <span class="eyebrow">Debt</span>
        <span class="mini" aria-hidden="true">{debt_bars}</span>
        <b class="fig">{M(s['debt'])}</b><span class="h-tl">Owed by local governments</span><span class="muted">County, cities, schools and authorities</span>
      </a>
      <a class="h-tile t-amber" href="/compare#m-findings">
        <span class="eyebrow">Accountability</span>
        <span class="prog" aria-hidden="true"><span class="p-a"><i style="width:{(s['findings'] - s['repeats']) / s['findings'] * 100:.0f}%"></i></span><span class="p-b"><i style="width:{s['sp_done'] / s['sp_n'] * 100:.0f}%"></i></span></span>
        <b class="fig">{s['findings']} findings</b><span class="h-tl">{s['repeats']} repeat audit findings</span><span class="muted">{s['sp_done']:,} of {s['sp_n']:,} sales tax projects done</span>
      </a>
    </div>
    <nav class="h-links" aria-label="More public money">
      <a href="/public-money/contracts">{s['ct_n']} contracts</a>
      <a href="/public-money/votes">How they voted</a>
      <a href="/connections">Connections</a>
      <a href="/governments">Governments</a>
      <a href="/public-money/tourist-tax">Bed tax {M(s['bt25'])}</a>
      <a href="/public-money/hurricane-michael">Hurricane Michael {M(s['fema'], 0)}</a>
      {f'<a class="hot" href="/public-money/amendment-3">Amendment 3 · −{M(s["a3"])} FY2029</a>' if election else ''}
    </nav>
  </section>

  <section class="h-row" aria-label="Governments and updates">
    <div class="h-card">
      <div class="h-card-hd"><b>Pick a government</b><a href="/compare">Compare →</a></div>
      <nav class="gov-chips" aria-label="Governments">{govchips}</nav>
    </div>
    <div class="h-card">
      <div class="h-card-hd"><b>What's new</b><a href="/updates">All updates →</a></div>
      <ol class="h-news">{news}</ol>
    </div>
    <div class="h-card">
      <div class="h-card-hd"><b>Take part</b></div>
      <nav class="h-take" aria-label="Take part"><a href="/emergency">Emergencies &amp; alerts</a><a href="/meetings">Meetings</a><a href="/elections">2026 elections</a><a href="/records-request">Request a record</a><a href="/alerts">Email alerts</a><a href="/open-data">Open data</a><a href="/glossary">Plain-English guide</a><a href="/es" hreflang="es" lang="es">En español</a></nav>
    </div>
  </section>
</div>
<script type="application/json" id="homeData">{data}</script>
<script src="/assets/home.js" defer></script>'''
