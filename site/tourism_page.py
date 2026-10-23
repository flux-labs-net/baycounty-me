"""Tourist (bed) tax and sales tax project pages for baycounty.me."""
import json, os, html, re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, '..', 'data', 'tourism')


def e(s):
    return html.escape(str(s if s is not None else ''))


def money(n, d=1):
    if n is None:
        return '—'
    n = float(n)
    return f'${n/1e6:,.{d}f}M' if abs(n) >= 1e6 else (f'${n/1e3:,.0f}K' if abs(n) >= 1e3 else f'${n:,.0f}')


def load():
    return json.load(open(os.path.join(DIR, 'tourism_surtax.json')))


def a(u, t='Source'):
    return f'<a class="src" href="{e(u)}" target="_blank" rel="noopener">{t}</a>'


PDF = '''<div class="stamp"><button type="button" class="pdf-btn" id="pdf"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>Data updated Oct 20, 2026</span></div>'''


def bedtax_page(out_dir):
    d = load(); b = d['bed_tax']
    zones = json.load(open(os.path.join(DIR, 'tdc_zones.json')))
    ZN = ['Panama City Beach', 'Panama City', 'Mexico Beach']
    col = defaultdict(dict)
    for c in b['collections']:
        col[c['fy']][c['district']] = c['amount']
    years = sorted(y for y in col if y <= 2025)
    partial = max(col) if max(col) > 2025 else None
    cvb26 = {s['category']: s['amount'] for s in b['spending'] if s['entity'].startswith('Panama City Beach CVB') and s['fy'] == 2026}
    depts = [(k, v) for k, v in cvb26.items() if re.search(r'\((Dept|acct)', k) is None and k != 'TOTAL' and ':' not in k] + \
            [(k, v) for k, v in cvb26.items() if '(Dept' in k]
    depts = [(re.sub(r'\s*\(Dept \d+\)', '', k), v) for k, v in depts if ':' not in k and k != 'TOTAL']
    lines = sorted([(k.split(':', 1)[1].strip(), v, k.split(':', 1)[0]) for k, v in cvb26.items() if ':' in k], key=lambda x: -x[1])
    data = {'years': years, 'zones': ZN, 'col': {str(y): col[y] for y in years}, 'geo': zones['zones'],
            'depts': sorted(depts, key=lambda x: -x[1]), 'total26': cvb26.get('TOTAL')}
    js = open(os.path.join(HERE, 'bedtax.js')).read().replace('__BT__', json.dumps(data, separators=(',', ':')))
    open(os.path.join(out_dir, 'assets', 'bedtax.js'), 'w').write(js)

    fy25 = sum(col[2025].values()); pcb_share = col[2025]['Panama City Beach'] / fy25
    rates = ''.join(f'<li><b>{r["rate_percent"]:g}%</b> {e(re.sub(r",? s\.[0-9.()a-z]+ F\.S\.", "", r["levy"]))} <span class="muted">since {e(r["effective"][:4])}</span></li>' for r in b['rates'] if r.get('effective') and r.get('rate_percent'))
    # county TDC funds, fund level
    fund = defaultdict(lambda: defaultdict(float))
    for s in b['spending']:
        if s['entity'].startswith('Bay County BOCC'):
            m = re.search(r'Fund (\d+)', s['category']); f = m.group(1) if m else '?'
            fund[f][s['fy']] += s['amount'] or 0
    FN = {'125': 'Tourism promotion and administration (PCB zone)', '127': 'Beach nourishment (PCB zone)', '128': '5th cent, incl. Sports Park debt (PCB zone)',
          '124': 'Publix Sports Park operations', '129': 'Panama City zone', '126': 'Mexico Beach zone'}
    ftbl = ''.join(f'<tr><th scope="row">{e(FN.get(k, "Fund " + k))} <span class="muted small">Fund {k}</span></th>' + ''.join(f'<td class="num">{money(fund[k].get(y))}</td>' for y in (2024, 2025, 2026, 2027)) + '</tr>' for k in ('125', '127', '128', '124', '129'))
    gov = ''.join(f'<li><b>{e(g["item"])}.</b> {e(g["text"])} {a(g["source_url"])}</li>' for g in b['governance'])
    con = ''.join(f'<li><b>{e(c["party"])}</b>: {e(c["type"])}. {e(c.get("detail", ""))} {a(c["source_url"])}</li>' for c in b['contracts'])
    ctx = ''.join(f'<li><span class="tl-d">{e(c["date"])}</span><span><b>{e(c["topic"])}.</b> {e(c["text"])} {a(c["source_url"])}</span></li>' for c in b['context'] if not c['date'].startswith('SFY'))
    linelist = ''.join(f'<tr><td>{e(n)}</td><td class="small muted">{e(g)}</td><td class="num">{money(v)}</td></tr>' for n, v, g in lines)
    T = lambda tid, t: f'<span class="term" data-term="{tid}">{t}</span>'
    return f'''<div class="page tax bt">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Public Money · Tourist Tax</span><h1>The bed tax: what visitors pay and where it goes</h1>
    <p class="lede">Visitors who rent a hotel room, condo or house for six months or less pay a 5% tourist development tax on top of sales tax. It brings in tens of millions a year, almost all from Panama City Beach, and state law limits what it can be spent on.</p></div>{PDF}</header>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>How the bed tax works</h2>
    <ol class="ex-steps">
      <li><b>Visitors pay it, not residents.</b> It's added to short-term rentals in a taxing area covering Panama City Beach, Panama City, Mexico Beach and nearby areas.</li>
      <li><b>Each penny has a job.</b> State law ties the pennies to tourism marketing, beach nourishment, and tourist facilities like sports complexes.</li>
      <li><b>A council recommends, the County Commission decides.</b> The 9-member Tourist Development Council (TDC) recommends spending; the County Commission adopts the budget. Visit Panama City Beach (the CVB) runs most of the PCB-zone money under a county contract.</li>
    </ol>
    <ul class="plain">{rates}</ul><p class="muted small">State law would allow a 6th cent. Bay County doesn't levy it; the County Commission declined to add it in 2023.</p></div>
    <svg class="ex-fig" id="tdcMap" viewBox="0 0 400 260" role="img" aria-label="Map of the three tourist tax zones"></svg></section>
  <div class="kpis">
    <div class="kpi"><span class="eyebrow">Collected, FY2025</span><span class="v">{money(fy25)}</span><span class="s">All three zones</span></div>
    <div class="kpi"><span class="eyebrow">From the PCB zone</span><span class="v">{pcb_share:.0%}</span><span class="s">{money(col[2025]["Panama City Beach"])}</span></div>
    <div class="kpi"><span class="eyebrow">Visit PCB budget, FY2026</span><span class="v">{money(data["total26"])}</span><span class="s">Including money carried over</span></div>
    <div class="kpi"><span class="eyebrow">Beach nourishment reserves</span><span class="v">{money(next((x["amount"] for x in b["spending"] if "reserves" in x["category"] and x["fy"] == 2026), None))}</span><span class="s">Budgeted reserves, FY2026 (Fund 127)</span></div>
  </div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="coll">Ten years of collections</h2><span class="muted">By zone, county fiscal years</span></div>
    <div class="vbars stacked bt-bars" id="btBars"></div><ul class="leg" id="btLeg"></ul>
    <p class="note">Hurricane Michael (October 2018) shows in FY2019–FY2020 for Mexico Beach and Panama City; FY2020 also reflects the pandemic. {f"FY{partial} so far (through July): {money(sum(col[partial].values()))}. " if partial else ""}Collections include penalties and interest, as reported by the Clerk. {a(b["collections"][-1]["source_url"], "Clerk reports")}</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="split">How the 5 cents are split in the PCB zone</h2></div>
    <p class="note">In FY2024 the PCB zone's tax revenue went about <b>60% to tourism promotion</b> (3 cents), <b>20% to beach nourishment</b> (1 cent) and <b>20% to the "5th cent"</b> fund that pays the Publix Sports Park debt and other projects (1 cent). This is worked out from the county's budget book; the ordinance itself wasn't available to check. {a(b["pcb_zone_penny_split_observed"]["source_url"])}</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="cvb">What Visit Panama City Beach spends it on</h2><span class="muted">FY2026 budget, {money(data["total26"])}</span></div>
    <div class="hbars" id="cvbBars"></div>
    <details class="tbl-toggle"><summary>Largest line items</summary><div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Item</th><th scope="col">Department</th><th scope="col" class="num">FY2026</th></tr></thead><tbody>{linelist}</tbody></table></div></details>
    <p class="note">"Tourism development projects" is mostly the SABRE indoor event center at the Publix Sports Park ($26.3M budgeted), which the TDC paused in June 2026.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="funds">The county's tourist tax funds</h2><span class="muted">Spending and reserves by fund</span></div>
    <div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Fund</th><th scope="col" class="num">FY2024 actual</th><th scope="col" class="num">FY2025 actual</th><th scope="col" class="num">FY2026 adopted</th><th scope="col" class="num">FY2027 tentative</th></tr></thead><tbody>{ftbl}</tbody></table></div>
    <p class="note">Budget columns include reserves (for example, $53.5M of beach nourishment reserves in FY2026), so they are much larger than actual spending. Mexico Beach's zone fund (126) is left out because its FY2025 lines include large one-time transfers we couldn't reconcile; its CVB contract was $1.1M in FY2026. Fund-level sums of the line items in the county budget book. {a("https://www.baycountyfl.gov/DocumentCenter/View/21090/FY-2027-Tentative-Budget-Commissioner-Book---09-15-26", "FY2027 budget book")}</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="gov">Who decides</h2></div><ul class="plain">{gov}</ul></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="con">Major contracts</h2></div><ul class="plain">{con}</ul></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="news">Recent decisions and news</h2></div><ol class="timeline">{ctx}</ol>
    <p class="note">Criminal charges described above are allegations, not convictions.</p></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">Gaps</h2></div><ul class="plain">{''.join(f"<li>{e(g)}</li>" for g in d["gaps"] if any(w in g for w in ("TDT", "TDC", "bed", "ad agency", "CVB")))}</ul></section>
  <div class="tt" id="tt" role="tooltip" hidden></div>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/bedtax.js" defer></script>'''


def surtax_id(p):  # stable id for ?p= links: the county GIS object id (points: p<id>, road segments: l<first id>)
    return f"p{p['gis_objectid']}" if p.get('gis_objectid') is not None else (f"l{p['gis_objectids'][0]}" if p.get('gis_objectids') else '')


GIS_REC = 'https://services1.arcgis.com/QB0VWfqR9MD4lF0F/arcgis/rest/services/Surtax_Projects/FeatureServer/'


def _gis_docs():
    """Project web pages (WEBSITE field) from the county GIS snapshot made by data/surtax/fetch_gis.py, keyed by name and city."""
    k = lambda n, c: (re.sub(r'\W+', '', (n or '').lower()), (c or '').replace('City of ', ''))
    try:
        g = json.load(open(os.path.join(HERE, '..', 'data', 'surtax', 'gis_projects.json')))
    except FileNotFoundError:
        return {}, k
    out = {}
    for x in g['projects']:
        if x.get('doc'):
            out.setdefault(k(x['name'], x['gov']), set()).add(x['doc'])
    return {kk: next(iter(v)) for kk, v in out.items() if len(v) == 1}, k


def surtax_page(out_dir):
    d = load(); inf, sch = d['infra_surtax'], d['school_surtax']
    docs, dk = _gis_docs()
    projs = []
    from opendata import schedule_by_project
    sb = schedule_by_project()
    for pi, p in enumerate(inf['projects']):
        if p.get('lat') is None:
            continue
        sx = sb.get(pi)  # county program schedule lines matched to this project (programmed dollars by year)
        projs.append({**({'sp': sum(x['programmed_total'] or 0 for x in sx), 'sfy': {k: v for x in sx for k, v in x['fy_amounts'].items()}, 'su': sx[0]['source_url']} if sx else {}), 'i': pi, 'id': surtax_id(p), 'n': p['name'], 'g': p['government'], 'c': p.get('category') or 'Other', 's': p['status'], 'p': p.get('pct_complete'),
                      'k': p.get('programmed_cost') or p.get('promised_cost'), 'y': p.get('fiscal_years') or '', 'x': round(p['lng'], 5), 'yy': round(p['lat'], 5),
                      'd': (p.get('description') or '')[:260],
                      # GIS record: [layer, object ids]; the page rebuilds p['source_url'] from it (checked below)
                      'r': [0, [p['gis_objectid']]] if p.get('gis_objectid') is not None else [1, p.get('gis_objectids') or []],
                      **({'w': docs[dk(p['name'], p['government'])]} if dk(p['name'], p['government']) in docs else {})})
        r = projs[-1]['r']
        assert p['source_url'] == GIS_REC + f"{r[0]}/query?where=" + (f"OBJECTID%3D{r[1][0]}" if r[0] == 0 else "OBJECTID+IN+(" + ",".join(map(str, r[1])) + ")") + "&outFields=*&outSR=4326&f=json", p['source_url']
    json.dump(projs, open(os.path.join(out_dir, 'data', 'surtax-projects.json'), 'w'), separators=(',', ':'))
    rules = inf['rules']
    cols = {c['fy']: c['amount'] for c in inf['collections']}
    fin = inf['county_program_finance']
    shares = ''.join(f'<tr><th scope="row">{e(s["government"])}</th><td class="num">{s["percent"]:.1f}%</td></tr>' for s in sorted(inf['allocation']['shares_percent'], key=lambda x: -x['percent']))
    fin_rows = ''.join(f'<tr><th scope="row">FY{f["fy"]}</th><td class="num">{money(f["surtax_received"])}</td><td class="num">{money(f.get("grants_other"))}</td><td class="num">{money(f["expenditures"])}</td></tr>' for f in fin)
    scol = ''.join(f'<tr><th scope="row">FY{c["fy"]}</th><td class="num">{money(c["amount"])}</td></tr>' for c in sch['collections'])
    sproj = ''.join(f'<li><b>{e(p["name"])}</b>: {e(p.get("status", "status not stated"))}{", about " + money(p["promised_cost"]) if p.get("promised_cost") else ""}. {a(p["source_url"])}</li>' for p in sch['projects'])
    hl = ''.join(f'<li><b>{e(p["name"])}</b>: {e(p.get("status", "status not stated"))}{", " + money(p["total_cost"]) + " total" if p.get("total_cost") else ""}{", " + money(p["county_surtax_share"]) + " from the surtax" if p.get("county_surtax_share") else ""}. {e(p.get("note", ""))} {a(p["source_url"])}</li>' for p in inf['project_highlights'])
    js = open(os.path.join(HERE, 'surtax.js')).read()
    open(os.path.join(out_dir, 'assets', 'surtax.js'), 'w').write(js)
    tot_fin = sum(f['surtax_received'] for f in fin)
    return f'''<div class="page tax st addr">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Public Money · Sales Tax Projects</span><h1>The half-cent sales taxes: what was promised, what got built</h1>
    <p class="lede">Bay County has two extra half-cent sales taxes that voters approved: one for roads and infrastructure, one for school buildings. Here is every infrastructure project on the county's map, and what we could find about the school tax.</p></div>{PDF}</header>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>How the half-cent taxes work</h2>
    <ol class="ex-steps">
      <li><b>Everyone who shops here pays.</b> Each adds half a cent to every dollar of taxable purchases in Bay County, including purchases by tourists.</li>
      <li><b>Voters set the rules.</b> The infrastructure tax started January 2017 and voters extended it in November 2024 through {e(rules["extension"]["new_expiration"][:4])}. The school tax runs through 2030.</li>
      <li><b>It can only build things.</b> The infrastructure money goes to roads, bridges, dirt-road paving, drainage and safety projects. The school money goes to school construction, renovation, security and technology.</li>
      <li><b>The county and cities split the infrastructure tax</b> by a state formula based on population.</li>
    </ol></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="map-h">Infrastructure projects on the county map</h2><span class="muted" id="stCount" aria-live="polite"></span></div>
    <div class="filters-row">
      <input id="stQ" type="search" placeholder="Search projects or roads" aria-label="Search projects" data-param="q">
      <select id="stG" aria-label="Government" data-param="gov"><option value="">All governments</option></select>
      <select id="stC" aria-label="Type" data-param="type"><option value="">All types</option></select>
      <select id="stS" aria-label="Status" data-param="status"><option value="">Any status</option><option value="completed">Completed</option><option value="in_progress">In progress</option><option value="not_started">Not started</option></select>
      <select id="stO" aria-label="Sort"><option value="new">Newest first</option><option value="az">Name A to Z</option><option value="big">Largest cost</option></select>
      <button type="button" class="tt-csv" id="stCsv">Download CSV</button>
    </div>
    <div class="st-wrap"><div class="st-mapcol"><div class="st-mapbox"><svg id="stMap" viewBox="0 0 400 300" role="group" aria-label="Map of sales tax projects. Each dot is a project: tab to a dot and press Enter, or pick one in the list, for details."></svg>
        <div class="st-zoom print-hide"><button type="button" id="stIn" aria-label="Zoom in">+</button><button type="button" id="stOut" aria-label="Zoom out">−</button><button type="button" id="stAll" class="st-all">Show all</button></div></div>
        <div class="st-sel" id="stSel" hidden aria-live="polite"></div></div>
      <ol class="st-list" id="stList"></ol></div>
    <ul class="leg mini" id="stLeg"></ul>
    <p class="note">From the county's sales tax project map service. Status comes from each project's "percent complete" field, which the county maintains; some records haven't been updated in years. Road projects are shown at the middle of the segment. {a(inf.get("projects_source_url") or "https://bayhalfcent.com/", "bayhalfcent.com")}</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="money-h">The county's share, year by year</h2><span class="muted">Surtax received, grants and spending on the county's program</span></div>
    <div class="two"><div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Year</th><th scope="col" class="num">Surtax received</th><th scope="col" class="num">Grants</th><th scope="col" class="num">Spent</th></tr></thead><tbody>{fin_rows}</tbody></table></div>
    <div><h3 class="h4">How the tax is split</h3><div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Government</th><th scope="col" class="num">Share</th></tr></thead><tbody>{shares}</tbody></table></div><p class="note">State formula shares, local FY2027. {a(inf["allocation"]["source_url"])}</p></div></div>
    <p class="note">{e(inf["county_program_finance_note"])} {a(fin[0]["source_url"])}</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="hl-h">Big projects</h2></div><ul class="plain">{hl}</ul></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="sch-h">The school half-cent</h2></div>
    <div class="two"><div><h3 class="h4">Collected by Bay District Schools</h3><div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Year</th><th scope="col" class="num">Collected</th></tr></thead><tbody>{scol}</tbody></table></div><p class="note">From the district's audited statements (school years end June 30).</p></div>
    <div><h3 class="h4">Projects tied to the tax by a source</h3><ul class="plain">{sproj}</ul><p class="note">{e(sch["promised_project_list_note"])} The district had ${sch["construction_commitments_total"]["total_contract"]/1e6:,.1f}M in construction contracts open at June 30, 2025, paid from all sources, not only the surtax. {a(sch["construction_commitments_total"]["source_url"])}</p></div></div></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">Gaps</h2></div><ul class="plain">{''.join(f"<li>{e(g)}</li>" for g in d["gaps"] if any(w in g.lower() for w in ("surtax", "school", "oversight", "infrastructure")))}</ul></section>
  <div class="tt" id="tt" role="tooltip" hidden></div>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/surtax.js" defer></script>'''
