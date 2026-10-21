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
        ('/public-money/debt', 'Debt', 'What local governments owe', 'Bonds and bank loans by government, big single payments ahead, and pension promises.', M(s['debt']), 'owed across Bay County governments'),
        ('/public-money/audits', 'Audit Findings', 'What the auditors found', 'Three years of audit findings in plain English, including problems that keep coming back.', f'{s["findings"]}', f'findings, {s["repeats"]} repeats in the latest audits'),
        ('/public-money/fees-and-bills', 'Fees & Bills', 'Fees on your tax bill, and water and garbage', 'Fire, stormwater and other flat fees, plus a typical monthly utility bill in each city.', '$28.1M', 'in flat fees on FY2026 tax bills'),
        ('/who-runs-bay-county', 'Officials', 'Who runs Bay County', 'Every elected seat and appointed manager, and what top officials are paid.', '5', 'independently elected county officers'),
        ('/public-money/contracts', 'Contracts', 'Who gets the contracts', 'Major contracts since 2022: winners, how they were awarded, change orders and who the county paid most.', str(s['ct_n']), 'contracts tracked'),
        ('/public-money/amendment-3', 'Amendment 3', 'What changes if it passes', 'The property tax amendment on the November ballot: your bill before and after, and the state\'s estimates.', M(s['a3']), 'less for Bay governments in FY2029 (state est.)'),
    ]


def home_page():
    s = stats()
    from updates import CHANGES, nice
    news = ''.join(f'<li><span class="tl-d">{nice(c["date"])}</span><span><a href="{c["pages"][0]}"><b>{html.escape(c["title"])}</b></a> {html.escape(c["text"])}</span></li>' for c in CHANGES[:4])
    election = date.today() <= date(2026, 11, 3)
    topics_ = topics(s)
    cards = ''.join(f'''<a class="topic" href="{u}"><span class="eyebrow">{e}</span><h3>{h}</h3><p>{p}</p><span class="t-stat"><b>{v}</b> {l}</span></a>''' for u, e, h, p, v, l in topics_)
    from govs import GOVS
    GOVCHIPS = ''.join(f'<a href="/governments/{g["slug"]}">{html.escape(g["short"])}</a>' for g in GOVS)
    return f'''<div class="page home">
  <section class="hero">
    <span class="eyebrow">Bay County, Florida</span>
    <h1>Local government, in plain view.</h1>
    <p class="lede">Maps, money and the public records behind them, for Panama City, Panama City Beach, Lynn Haven, Callaway, Springfield, Parker, Mexico Beach and the rest of Bay County. Every figure links to its source.</p>
    <form class="home-search" action="/my-address/" method="get" role="search">
      <label for="hq">Look up your address</label>
      <div><input id="hq" name="q" type="search" placeholder="e.g. 825 Ohio Ave" autocomplete="off"><button type="submit">Look up</button></div>
      <small class="muted">Your tax estimate, who represents you, your schools, flood zone and more.</small>
    </form>
  </section>

  <section class="section" aria-labelledby="nums">
    <div class="sec-hd"><h2 id="nums">Bay County by the numbers</h2><span class="muted">From the latest public records</span></div>
    <div class="numbers">
      <a href="/public-money/tax-dollars"><b>{M(s['lv_tot'])}</b><span>property tax levied by all local governments, FY2026</span></a>
      <a href="/public-money/tax-dollars"><b>{s['school_share']:.0%}</b><span>of that goes to the schools</span></a>
      <a href="/public-money/hurricane-michael"><b>{M(s['fema'], 0)}</b><span>in FEMA money to rebuild after Hurricane Michael</span></a>
      <a href="/public-money/debt"><b>{M(s['debt'])}</b><span>owed by the county, schools, cities and authorities</span></a>
      <a href="/public-money/tourist-tax"><b>{M(s['bt25'])}</b><span>bed tax paid by visitors in FY2025</span></a>
    </div>
  </section>

  <section class="section" aria-labelledby="govs">
    <div class="sec-hd"><h2 id="govs">Pick your government</h2><a class="muted" href="/compare">Compare them side by side</a></div>
    <nav class="gov-chips" aria-label="Governments">{GOVCHIPS}</nav>
  </section>

  <section class="section" aria-labelledby="inv">
    <div class="sec-hd"><h2 id="inv">Take part</h2><span class="muted">Tools for following and asking</span></div>
    <div class="tools">
      <a href="/meetings"><b>Upcoming meetings</b><span>When every board meets, with agendas and the money items on them. Add them to your calendar.</span></a>
      <a href="/elections"><b>2026 elections</b><span>Who's running, what they say they'll do, and where their campaign money comes from.</span></a>
      <a href="/records-request"><b>Request a record</b><span>Write a Florida public records request in a minute.</span></a>
      <a href="/public-money/campaign-money"><b>Campaign money</b><span>Who funds local officials' campaigns, and which donors hold contracts.</span></a>
      <a href="/open-data"><b>Open data</b><span>Download everything on this site as CSV or JSON.</span></a>
      <a href="/es" hreflang="es" lang="es"><b>En español</b><span>Mi dirección, solicitudes de registros y el glosario, en español.</span></a>
    </div>
  </section>

  {f"""<aside class="banner"><div><span class="eyebrow">On the November 3 ballot</span><h2>Amendment 3: what it would change here</h2><p>The property tax amendment needs 60% to pass. See your own bill before and after, and the state's estimate of what each Bay County government would collect. BayCounty.me takes no position.</p></div><a class="banner-go" href="/public-money/amendment-3">See what changes →</a></aside>""" if election else ""}

  <section class="section" aria-labelledby="pm">
    <div class="sec-hd"><h2 id="pm">Public Money</h2><span class="muted">Where tax dollars come from, where they go, and who receives them</span></div>
    <div class="topics">{cards}</div>
  </section>

  <section class="section" aria-labelledby="new">
    <div class="sec-hd"><h2 id="new">What's new</h2><a class="muted" href="/updates">All updates</a><a class="muted" href="/updates.xml">RSS</a></div>
    <ol class="timeline">{news}</ol>
  </section>

  <section class="section" aria-labelledby="soon">
    <div class="sec-hd"><h2 id="soon">In the works</h2><span class="muted">Research underway now</span></div>
    <div class="cols">
      <div><h3>2026 County Commission minutes</h3><p>The Clerk hasn't posted Commission minutes after June 16, including the September budget hearings. Votes will be added when they are.</p></div>
      <div><h3>City check registers</h3><p>No city posts its vendor payments. The county's and the <a href="/public-money/who-gets-paid">tourism agencies'</a> are up; the cities' are being requested.</p></div>
    </div>
  </section>

  <section class="section how" aria-labelledby="how">
    <div class="sec-hd"><h2 id="how">How this site works</h2></div>
    <div class="cols">
      <div><h3>Public records only</h3><p>Figures come from audits, adopted budgets, state data, annual reports and council records. If a number isn't in a record, it isn't on the site.</p></div>
      <div><h3>Sources on every row</h3><p>Each payment, project or finding links to the document it came from, so you can check it yourself. Download reports as PDF or data as CSV.</p></div>
      <div><h3>Gaps stated plainly</h3><p>Where a government doesn't publish something, the page says so and names the record to request.</p></div>
    </div>
  </section>

  <section class="section">
    <a class="guide-cta" href="/glossary">
      <span class="eyebrow">New to this?</span>
      <h3>Government money, explained simply</h3>
      <p>What's a CRA? What's a mill? What does "rolled-back rate" mean? The plain-English guide explains every term on this site. Words with a dotted underline can also be tapped anywhere for a quick answer.</p>
      <span class="go">Read the guide →</span>
    </a>
  </section>
</div>
<link rel="stylesheet" href="/assets/tax.css">'''
