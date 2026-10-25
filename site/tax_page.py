"""'How your tax dollars are allocated' page for baycounty.me.

Reads data/tax/millage.json (DOR rates and levies), budgets.json (FY2026 budgets)
and finances.json (EDR audited actuals), builds one compact dataset, and writes
assets/tax.js. Returns the page body.
"""
import json, os
from city_filter import city_bar

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data', 'tax')

YEARS = [2020, 2021, 2022, 2023, 2024, 2025]           # tax years
FY = [f'FY{y + 1}' for y in YEARS]                      # budget years they pay for

# group order is the validated categorical order: never re-sort
GROUPS = [
    ('school', 'Schools'),
    ('county', 'Bay County'),
    ('city', 'Your city'),
    ('countysvc', 'County fire & mosquito'),
    ('other', 'Special districts'),
]

AUTH = {
    'bay_county_general': ('Bay County Commission', 'county'),
    'county_fire_mstu': ('County fire service (outside cities)', 'countysvc'),
    'county_mosquito_control': ('County mosquito control', 'countysvc'),
    'school_rle': ('Schools: state-required rate', 'school'),
    'school_discretionary': ('Schools: local operating', 'school'),
    'school_capital_outlay': ('Schools: buildings and buses', 'school'),
    'nwfwmd': ('NW Florida Water Management District', 'other'),
    'beach_mosquito': ('Beach Mosquito Control District', 'other'),
    'pc_downtown_improvement_board': ('Downtown Improvement Board', 'other'),
    'city_callaway': ('City of Callaway', 'city'),
    'city_lynn_haven': ('City of Lynn Haven', 'city'),
    'city_mexico_beach': ('City of Mexico Beach', 'city'),
    'city_panama_city': ('City of Panama City', 'city'),
    'city_parker': ('City of Parker', 'city'),
    'city_springfield': ('City of Springfield', 'city'),
}

DISTRICTS = [
    ('Panama City', 'Panama City'),
    ('Panama City - Downtown DIB', 'Panama City, downtown improvement district'),
    ('Panama City Beach', 'Panama City Beach'),
    ('Lynn Haven', 'Lynn Haven'),
    ('Callaway', 'Callaway'),
    ('Springfield', 'Springfield'),
    ('Parker', 'Parker'),
    ('Mexico Beach', 'Mexico Beach'),
    ('unincorporated', 'Unincorporated Bay County (not in a city)'),
    ('unincorporated - beach area', 'Unincorporated beach area (outside PCB city limits)'),
]

# second homestead exemption (non-school, on assessed value above $50,000): $25,000, CPI-indexed from tax year 2025
# Source: FL DOR, Additional Homestead Exemption Adjustment (revised Jan 2026)
SECOND_HX = {2020: 25000, 2021: 25000, 2022: 25000, 2023: 25000, 2024: 25000, 2025: 25722, 2026: 26411}
DOR_CPI = 'https://www.floridarevenue.com/property/Documents/cpi_homestead_exemption.pdf'

GOV_ORDER = ['bay_county', 'bay_district_schools', 'panama_city', 'panama_city_beach', 'lynn_haven',
             'callaway', 'springfield', 'parker', 'mexico_beach']
GOV_SHORT = {'bay_county': 'Bay County', 'bay_district_schools': 'Schools', 'panama_city': 'Panama City',
             'panama_city_beach': 'Panama City Beach', 'lynn_haven': 'Lynn Haven', 'callaway': 'Callaway',
             'springfield': 'Springfield', 'parker': 'Parker', 'mexico_beach': 'Mexico Beach'}
GOV_STATUS = {
    'bay_county': ('ok', 'Adopted Sept 16, 2025'),
    'bay_district_schools': ('warn', 'Total is the tentative July 2025 figure; the final adopted total was not found online'),
    'panama_city': ('ok', 'Adopted September 2025'),
    'panama_city_beach': ('ok', 'Adopted Aug 28, 2025'),
    'lynn_haven': ('ok', 'Adopted Sept 23, 2025'),
    'callaway': ('warn', 'Only the first-hearing total is public; the adopted budget is not posted online'),
    'springfield': ('warn', 'Budget not posted online; only the tax rate and levy are public'),
    'parker': ('warn', 'Only a draft budget is posted online'),
    'mexico_beach': ('warn', 'Adopted September 2025, but the budget is not posted online'),
}
GOV_LEVY = {  # authority ids whose FY2026 levy belongs to each government
    'bay_county': ['bay_county_general', 'county_fire_mstu', 'county_mosquito_control'],
    'bay_district_schools': ['school_total'],
    'panama_city': ['city_panama_city'], 'panama_city_beach': [], 'lynn_haven': ['city_lynn_haven'],
    'callaway': ['city_callaway'], 'springfield': ['city_springfield'], 'parker': ['city_parker'],
    'mexico_beach': ['city_mexico_beach'],
}

DOR_T1 = 'https://floridarevenue.com/property/dataportal/Documents/PTO%20Data%20Portal/County%20Municipal%20Reports/Table%201-Comparison%20of%20Levies/25table1/Bay%20Table%201.pdf'
DOR_TACD = 'https://floridarevenue.com/property/dataportal/Documents/PTO%20Data%20Portal/TACD%20History/2025%20Taxing%20Authority%20Code%20Descriptions/2025%20Bay%20TACD.pdf'
TC_RATES = 'https://baycountyfltax.gov/?p=2190'
EDR_C = 'https://edr.state.fl.us/content/local-government/data/revenues-expenditures/cntyfiscal.cfm'
EDR_M = 'https://edr.state.fl.us/content/local-government/data/revenues-expenditures/munifiscal.cfm'
RELABEL = {
    'State FEFP': 'State school funding formula (FEFP)',
    'Local property tax: Required Local Effort + discretionary operating (combined)': 'Local property tax (state-required rate plus local operating rate)',
}

GAPS = [
    "Bay District Schools' final adopted budget for 2025-26 could not be downloaded from the district's site. The total shown is the tentative July 2025 figure, and the fund detail comes from a state education department file.",
    "The school board's split between the state-required rate and the local operating rate is published only as one combined dollar figure ($128.6M).",
    "School rolled-back rates are not published in the state data used here.",
    "The Sheriff's own full budget, including contract and grant money, was not found. The county's link to it opens the Property Appraiser's budget instead. Only the county-funded part is shown.",
    "Callaway, Springfield and Mexico Beach do not post their FY2026 budgets online. Parker posts only a draft. Their tax rates and levies are official.",
    "Where Bay County books its $22.2M Front Beach Road CRA payment is not shown as a line in the county general fund.",
    "Audited figures for FY2025 are not out yet (only Callaway's FY2025 spending has been posted by the state).",
    "Rates for non-ad valorem fees (fire, stormwater, garbage) are incomplete, so the calculator leaves them out.",
    "In the audited figures, CRAs set up as separate legal entities are reported apart from the city or county and are not included here. Bay County's figures include the Sheriff and other constitutional officers but do not split them out.",
    "Tax year 2026 (FY2027) rates had not been published by the state when this page was built.",
]
CRA_AMD3 = 'https://www.baycountyfl.gov/829/Understanding-Amendment-3'


def r0(x):
    return None if x is None else round(x)


def build_data():
    mil = json.load(open(os.path.join(DATA, 'millage.json')))
    bud = json.load(open(os.path.join(DATA, 'budgets.json')))
    fin = json.load(open(os.path.join(DATA, 'finances.json')))
    A = {a['id']: a for a in mil['authorities']}

    def series(aid, key):
        by = {y['tax_year']: y.get(key) for y in A[aid]['years']}
        return [by.get(y) for y in YEARS]

    auth = {}
    for aid, (name, g) in AUTH.items():
        auth[aid] = {'n': name, 'g': g, 'school': aid.startswith('school_'),
                     'm': series(aid, 'millage'), 'rb': series(aid, 'rolled_back'), 'lv': series(aid, 'levy')}
    stacks = mil['stacks']
    districts = [{'id': k, 'label': lbl, 'stack': stacks[k]} for k, lbl in DISTRICTS]
    for d in districts:  # check our stacks reproduce DOR's published totals
        tot = round(sum(auth[a]['m'][-1] for a in d['stack']), 4)
        assert abs(tot - stacks['stack_totals_2025'][d['id']]) < 1e-3, (d['id'], tot)
        d['total'] = [round(sum(auth[a]['m'][i] for a in d['stack']), 4) for i in range(len(YEARS))]

    # levy by group by year (school levy only published as a total)
    school_total = series('school_total', 'levy')
    levy = {g: [0] * len(YEARS) for g, _ in GROUPS}
    for aid, a in auth.items():
        if a['school']:
            continue
        for i, v in enumerate(a['lv']):
            levy[a['g']][i] += v or 0
    levy['school'] = school_total

    # FY2026 levy per government/district for the countywide bars
    last = len(YEARS) - 1
    bars = [{'n': 'Bay District Schools', 'g': 'school', 'v': school_total[last]}]
    for aid, a in auth.items():
        if not a['school'] and a['lv'][last]:
            bars.append({'n': a['n'], 'g': a['g'], 'v': a['lv'][last]})
    bars.sort(key=lambda b: -b['v'])

    fin_by = {g['id']: g for g in fin['governments']}
    bud_by = {g['id']: g for g in bud['governments']}
    govs = []
    for gid in GOV_ORDER:
        b = bud_by[gid]; f = b['fy2026']
        lv = sum((series(a, 'levy')[last] or 0) for a in GOV_LEVY[gid]) if GOV_LEVY[gid] else 0
        g = {'id': gid, 'short': GOV_SHORT[gid], 'name': b['name'], 'status': GOV_STATUS[gid],
             'total': r0(f.get('total_budget')), 'gf': r0(f.get('general_fund')), 'mills': f.get('millage'),
             'levy': lv, 'rev': {RELABEL.get(k, k): r0(v) for k, v in (f.get('gf_revenues') or {}).items()},
             'exp': {k: r0(v) for k, v in (f.get('gf_expenditures') or {}).items()},
             'src': [[f.get('source_title') or 'Budget source', f.get('source_url')]] + [['Related: ' + u.split('/')[2].replace('www.', ''), u] for u in f.get('other_sources', [])],
             'ctx': [[c['text'], c['source_url']] for c in b.get('context', [])],
             'hist': [[h['fy'], r0(h.get('total_budget'))] for h in b.get('history', []) if h.get('total_budget')]}
        notes = [f.get(k) for k in ('total_budget_note', 'gf_expenditures_note', 'gf_revenues_note', 'millage_note') if f.get(k)]
        g['notes'] = notes
        # FY2027 budgets adopted in Sept 2026. The breakdowns above stay FY2026 (FY2027 detail isn't
        # published for most governments yet); FY2027 is shown as its own line with its own source.
        n = b.get('fy2027') or {}
        nt = n.get('total_budget') or n.get('total_budget_less_transfers') or n.get('total_budget_less_interfund_transfers')
        if nt or n.get('general_fund'):
            st = str(n.get('status') or '')
            g['next'] = {'fy': 'FY2027', 'total': r0(nt), 'gf': r0(n.get('general_fund')), 'mills': n.get('millage'),
                         'adopted': st.lower().startswith('adopted'),
                         'status': st.split(';')[0].split('. ')[0][:140],
                         'excl': bool(not n.get('total_budget') and nt),
                         'src': [n.get('source_title') or 'FY2027 budget source', n.get('source_url')]}
        if g['total'] and not any(h[0].startswith('FY2026') for h in g['hist']):
            g['hist'].append(['FY2026', g['total']])
        g['hist'].sort(key=lambda h: h[0])
        if g.get('next') and g['next']['total']:
            g['hist'].append(['FY2027', g['next']['total']])
        if gid == 'bay_county':
            s = bud_by['bay_sheriff']
            g['ctx'].append([f"The Sheriff is elected separately, but the County Commission pays for most of the office: ${s['fy2026']['county_funded_total']/1e6:.1f}M from the county general fund in FY2026 for law enforcement (${s['fy2026']['gf_expenditures']['Law enforcement (county dept 0120)']/1e6:.1f}M) and the jail (${s['fy2026']['gf_expenditures']['Jail operations (county dept 0121)']/1e6:.1f}M).", s['fy2026']['source_url']])
            g['hist'] = [[h['fy'], r0(h['total_budget'])] for h in sorted(b['history'], key=lambda h: h['fy'])] + [['FY2026', g['total']]] + ([['FY2027', g['next']['total']]] if g.get('next') and g['next']['total'] else [])
        if gid == 'bay_district_schools':
            g['mix'] = {k: r0(v) for k, v in f['revenue_mix_all_funds'].items() if k != 'note'}
            g['other'] = {k: r0(v) for k, v in f['other_funds'].items()}
        if gid in fin_by:
            yrs = []
            for y in fin_by[gid]['years']:
                rev = {k: r0(v) for k, v in (y.get('revenues') or {}).items() if not k.startswith('Debt proceeds')}
                exp = {k: r0(v) for k, v in (y.get('expenditures') or {}).items() if not k.startswith('Transfers')}
                yrs.append({'fy': y['fy'], 'rev': rev, 'exp': exp, 'pop': y.get('population'),
                            'rt': r0(y.get('revenue_total')), 'et': r0(y.get('expenditure_total_excl_transfers')),
                            'rs': y.get('revenue_source_url'), 'es': y.get('expenditure_source_url')})
            g['act'] = yrs
            g['edr'] = EDR_C if gid == 'bay_county' else EDR_M
        govs.append(g)

    return {
        'years': YEARS, 'fy': FY, 'second': [SECOND_HX[y] for y in YEARS], 'groups': GROUPS, 'auth': auth, 'districts': districts,
        'levy': levy, 'bars': bars, 'govs': govs,
        'gaps': GAPS,
    }


GOV_PANEL = '''  <section class="tx-sec" id="govs" aria-labelledby="gov-h">
    <div class="sec-hd"><h2 id="gov-h">Each government's money</h2><span class="muted">Where it comes from, and what it pays for</span></div>
    <div class="pills" id="govPills" role="tablist" aria-label="Choose a government"></div>
    <div id="govBody"></div>
  </section>'''


def gov_links():
    """Each government's budget is on its own page: one card per government, with its budget and tax rate."""
    from govs import all_profiles
    import html as _h
    cards = ''.join(f'<li><a href="/governments/{p["slug"]}#money"><b>{_h.escape(p["short"])}</b></a> <span class="muted small">'
                    + ' · '.join(x for x in [f'${(p.get("budget") or {}).get("total")/1e6:,.1f}M budget' if (p.get('budget') or {}).get('total') else '',
                                             (f'{p["budget"]["mills"]:g} mills' if (p.get('budget') or {}).get('mills') else '')] if x) + '</span></li>' for p in all_profiles())
    return f'''  <section class="tx-sec" id="govs" aria-labelledby="gov-h">
    <div class="sec-hd"><h2 id="gov-h">Each government's money</h2><span class="muted">Where it comes from, what it pays for, and what it owes</span></div>
    <p>Each government's page has its whole budget: every fund and department, where the money comes from, what each service costs per resident, its debt and its audits. <a href="/compare">Compare them side by side</a> or <a href="/public-money/budget-compare">compare any two years</a>, including audited actuals.</p>
    <ul class="plain cols-2">{cards}</ul>
  </section>'''


def tax_page(out_dir, gov_panel=True):
    """gov_panel: the per-government budget panel. English links to each government's page instead (it carries the
    same budget); the Spanish page keeps the panel, as there are no Spanish government pages."""
    d = build_data()
    last = len(YEARS) - 1
    total26 = sum(d['levy'][g][last] for g, _ in GROUPS)
    js = open(os.path.join(HERE, 'tax.js')).read().replace('__TAX__', json.dumps(d, ensure_ascii=False, separators=(',', ':')))
    open(os.path.join(out_dir, 'assets', 'tax.js'), 'w').write(js)

    def T(tid, text):
        return f'<span class="term" data-term="{tid}">{text}</span>'

    return f'''<div class="page tax">
  <header class="tx-top">
    <div class="tx-brand">
      <span class="eyebrow">Public Money · Tax Dollars</span>
      <h1>How your tax dollars are allocated</h1>
      <p class="lede">Your property tax bill isn't one tax. It's several governments each taking a slice. Here's who gets what from your bill, where each government's other money comes from, and what it pays for.</p>
    </div>
    <div class="stamp"><button type="button" id="pdf" class="pdf-btn"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>Rates for {FY[last]} (Oct 2025 to Sept 2026)<br>Data updated Oct 20, 2026</span></div>
  </header>
  {city_bar(['county', 'schools', 'pc', 'pcb', 'lh', 'cw', 'sp', 'parker', 'mb'], note='Opens that government in "Each government\'s money" and sets the calculator to its city')}

  <section class="explain" aria-labelledby="howbill">
    <div class="ex-txt">
      <span class="eyebrow">The simple version</span>
      <h2 id="howbill">How a property tax bill works</h2>
      <ol class="ex-steps">
        <li><b>Your home gets a value.</b> The Property Appraiser sets it each January. Subtract any {T('homestead', 'homestead exemption')} and you get your {T('taxable-value', 'taxable value')}.</li>
        <li><b>Each government picks a rate.</b> The county, the school board, your city and a few special districts each set a rate in {T('millage', 'mills')}. One mill is $1 for every $1,000 of taxable value.</li>
        <li><b>Add up the slices.</b> Your bill is every rate times your taxable value. The Tax Collector sends one bill and passes each slice to the government it belongs to.</li>
      </ol>
      <p class="muted">Each of these governments is a {T('taxing-authority', 'taxing authority')}. Rates here are for {T('fiscal-year', 'fiscal year')} {FY[last]}.</p>
    </div>
  </section>

  <section class="tx-sec" id="calc" aria-labelledby="calc-h">
    <div class="sec-hd"><h2 id="calc-h">Your bill, slice by slice</h2><span class="muted">Estimate using {FY[last]} rates</span></div>
    <div class="calc">
      <form class="calc-in" id="calcForm" onsubmit="return false">
        <label class="fld"><span>Where is the property?</span><select id="cDist"></select></label>
        <label class="fld"><span>{T('assessed-value', 'Assessed value')}</span>
          <span class="money"><span aria-hidden="true">$</span><input id="cVal" type="text" inputmode="numeric" autocomplete="off" value="250,000" aria-describedby="cValHint"></span>
          <small id="cValHint" class="muted">On your TRIM notice or the Property Appraiser's site. Not the sale price.</small></label>
        <label class="chk"><input id="cHome" type="checkbox" checked> <span>I live here full time and have a {T('homestead', 'homestead exemption')}</span></label>
      </form>
      <div class="calc-out" aria-live="polite">
        <div class="bill-hd"><span class="eyebrow">Estimated yearly property tax</span><span class="bill-v" id="bTotal">$0</span><span class="muted" id="bSub"></span></div>
        <div class="stackbar" id="bStack" role="img"></div>
        <ul class="leg" id="bLeg"></ul>
      </div>
    </div>
    <div class="tablewrap"><table class="tx-table" id="bTable"><thead><tr><th scope="col">Who gets it</th><th scope="col" class="num">Rate (mills)</th><th scope="col" class="num">Taxed on</th><th scope="col" class="num">Your share</th><th scope="col" class="num">Of your bill</th></tr></thead><tbody></tbody><tfoot></tfoot></table></div>
    <div class="trend-box">
      <div class="sub-hd"><h3>The same home at each year's rates</h3><span class="muted">Holds your value fixed, so only the rates change</span></div>
      <div class="vbars" id="bTrend"></div>
    </div>
    <p class="note">This covers {T('ad-valorem', 'property taxes')} only. Your actual bill also has {T('non-ad-valorem', 'non-ad valorem assessments')} (flat fees for things like fire service, stormwater or garbage) and may have other exemptions for seniors, veterans or disability. Paying in November takes 4% off.</p>
  </section>

  <section class="tx-sec" aria-labelledby="all-h">
    <div class="sec-hd"><h2 id="all-h">Where all of Bay County's property tax goes</h2><span class="muted">Total {T('levy', 'levied')} in {FY[last]}: <b>${total26/1e6:,.1f}M</b></span></div>
    <div class="hbars" id="allBars"></div>
    <aside class="callout">
      <b>Some of this goes to redevelopment districts.</b> Bay County says about $27 million (16.5%) of the countywide property tax it collects goes to city {T('cra', 'Community Redevelopment Agencies')}, including about $22.2 million a year to Panama City Beach's Front Beach Road CRA. That money is the {T('tif', 'tax increment')} from growth inside those districts. <a href="/public-money/cra-spending">See what the CRAs spend it on →</a> <a class="src" href="{CRA_AMD3}" target="_blank" rel="noopener">Source: Bay County</a>
    </aside>
  </section>

  <section class="tx-sec" aria-labelledby="trend-h">
    <div class="sec-hd"><h2 id="trend-h">Six years of property tax</h2><span class="muted">Total levied each year, by who receives it</span></div>
    <div class="vbars stacked" id="levyTrend"></div>
    <ul class="leg" id="levyLeg"></ul>
    <details class="tbl-toggle"><summary>Show as a table</summary><div class="tablewrap"><table class="tx-table" id="levyTable"></table></div></details>
    <div class="sub-hd"><h3>Total rate where you live</h3><span class="muted">All slices added up, in mills. Lower is less tax per $1,000 of value.</span></div>
    <div class="tablewrap"><table class="tx-table" id="rateTable"></table></div>
    <p class="note">Bay County raised its rate from 4.4362 to 5.4362 mills in FY2024. Parker started a city property tax in FY2024. Panama City Beach has no city property tax. A rate that stays the same can still be a tax increase under Florida law if it's above the {T('rolled-back', 'rolled-back rate')}, because rising values bring in more money.</p>
  </section>

{GOV_PANEL if gov_panel else gov_links()}

  <section class="tx-sec method" aria-labelledby="src-h">
    <div class="sec-hd"><h2 id="src-h">Sources and gaps</h2></div>
    <p>Tax rates and levies come from the Florida Department of Revenue: <a href="{DOR_T1}" target="_blank" rel="noopener">2025 Comparison of Taxes Levied, Bay County</a> and the <a href="{DOR_TACD}" target="_blank" rel="noopener">2025 Bay tax district rate report</a>, matched against the <a href="{TC_RATES}" target="_blank" rel="noopener">Bay County Tax Collector's 2025 rates</a>. Earlier years come from the same DOR tables for each year. Every district's rates add up to DOR's published total.</p>
    <p>FY2026 budgets come from each government's adopted budget, linked under each government above. Audited actuals for FY2021 to FY2024 come from the Florida Office of Economic and Demographic Research (<a href="{EDR_C}" target="_blank" rel="noopener">county</a> and <a href="{EDR_M}" target="_blank" rel="noopener">city</a> reports), which compiles each government's {T('audit', 'annual financial report')}. They cover operating funds, including utilities, and leave out borrowing and transfers between a government's own accounts so nothing is counted twice.</p>
    <p>The calculator applies each rate to your taxable value. With a homestead, the first $25,000 comes off every tax, and a second amount (on value above $50,000) comes off everything except school taxes. That second amount was $25,000 through 2024 and is now adjusted for inflation: <a href="{DOR_CPI}" target="_blank" rel="noopener">$25,722 for FY2026 bills</a>. It does not include other exemptions or non-ad valorem fees.</p>
    <details class="gaps"><summary>What we couldn't find ({len(d['gaps'])})</summary><ul>{''.join(f'<li>{g}</li>' for g in d['gaps'])}</ul></details>
  </section>
  <div class="tt" id="tt" role="tooltip" hidden></div>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/tax.js" defer></script>'''
