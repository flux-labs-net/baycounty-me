"""'Amendment 3: what changes if it passes' page for baycounty.me.

Neutral explainer. Uses the state Revenue Estimating Conference's parcel-level estimate
(data/amendment3/rec_bay.json) and the tax-page dataset for rates and levies.
"""
import json, os
from tax_page import build_data, YEARS

HERE = os.path.dirname(os.path.abspath(__file__))
A3 = os.path.join(HERE, '..', 'data', 'amendment3')

REC_URL = 'https://edr.state.fl.us/Content/conferences/revenueimpact/archives/2026F/_pdf/impact0710.pdf'
SRC = {
    'rec': ('Florida Revenue Estimating Conference, CS/HJR 1F impact (adopted July 10, 2026)', REC_URL),
    'county': ('Bay County: Understanding Amendment 3', 'https://www.baycountyfl.gov/829/Understanding-Amendment-3'),
    'vcpa': ('Volusia County Property Appraiser: Proposed 2026 Property Tax Amendment 3', 'https://paproapp.vcgov.org/info/amendment3'),
    'fac': ('Florida Association of Counties: Property Tax Reform Summary (June 2026)', 'https://www.fl-counties.com/wp-content/uploads/2026/06/Property-Tax-Reform-Summary-.pdf'),
    'phoenix': ('Florida Phoenix voter guide: Amendment 3', 'https://floridaphoenix.com/voter-guides/ballot-measures/2026-amendment-3/'),
    'ruling': ('WFLX: Judge orders rewrite of Amendment 3 ballot language (Aug 4, 2026)', 'https://www.wflx.com/2026/08/04/florida-judge-orders-rewrite-amendment-3-ballot-language-calling-it-biased-misleading/'),
    'rewrite': ('WCTV: Voters to see modified ballot language for Amendment 3 (Aug 14, 2026)', 'https://www.wctv.tv/2026/08/14/voters-see-new-modified-ballot-language-amendment-3-ahead-general-election/'),
    'realtors': ('WGCU: Realtors back Amendment 3 (Sept 9, 2026)', 'https://www.wgcu.org/elections/2026-09-09/realtors-back-florida-amendment-3-property-tax-cut-measure'),
    'desantis': ('CBS12: DeSantis defends Amendment 3 (Sept 24, 2026)', 'https://cbs12.com/news/local/florida-governor-ron-desantis-defends-amendment-3-property-tax-change-amid-local-government-concerns-over-tax-revenue-service-cuts-new-fees-tax-shifts-november-3-election-ballot-issue'),
    'renters': ('WFLX: Expansion could shift tax burden to renters, critics warn (June 15, 2026)', 'https://www.wflx.com/2026/06/15/florida-homestead-exemption-expansion-could-shift-tax-burden-renters-critics-warn/'),
    'wjhg_oct': ('WJHG: Amendment 3 raises concerns among Bay County leaders (Oct 2, 2026)', 'https://www.wjhg.com/2026/10/03/amendment-3-raises-concerns-among-bay-county-leaders-ahead-november-vote/'),
    'wjhg_sep': ('WJHG: Bay County leaders weigh $36 million hit (Sept 15, 2026)', 'https://www.wjhg.com/2026/09/16/bay-county-leaders-weigh-36-million-hit-if-amendment-3-passes/'),
    'wjhg_lh': ('WJHG: Amendment could save homeowners money but strain budgets (July 29, 2026)', 'https://www.wjhg.com/2026/07/30/proposed-property-tax-amendment-could-save-homeowners-money-strain-governments-budgets/'),
    'cpi': ('Florida Department of Revenue: Additional homestead exemption adjustment', 'https://www.floridarevenue.com/property/Documents/cpi_homestead_exemption.pdf'),
}

# REC row name -> (display name, FY2026 levy authority ids, budget id for general fund)
REC_MAP = {
    'Bay County': ('Bay County Commission (incl. fire and mosquito control)', ['bay_county_general', 'county_fire_mstu', 'county_mosquito_control'], 'bay_county'),
    'Panama City': ('City of Panama City', ['city_panama_city'], 'panama_city'),
    'Lynn Haven': ('City of Lynn Haven', ['city_lynn_haven'], 'lynn_haven'),
    'Callaway': ('City of Callaway', ['city_callaway'], 'callaway'),
    'Springfield': ('City of Springfield', ['city_springfield'], 'springfield'),
    'Mexico Beach': ('City of Mexico Beach', ['city_mexico_beach'], 'mexico_beach'),
    'Parker': ('City of Parker', ['city_parker'], 'parker'),
    'All ISDs in Bay': ('Special districts (water management, beach mosquito)', ['nwfwmd', 'beach_mosquito'], None),
    'Panama City Beach': ('City of Panama City Beach', [], 'panama_city_beach'),
}


def amend_data():
    """Amendment 3 calculator data (also published for the app)."""
    td = build_data()
    rec = json.load(open(os.path.join(A3, 'rec_bay.json')))
    gov_gf = {g['id']: g['gf'] for g in td['govs']}
    L = len(YEARS) - 1
    govs = []
    for r in rec['bay']:
        name, ids, bid = REC_MAP[r['name']]
        levy = sum(td['auth'][a]['lv'][L] or 0 for a in ids)
        govs.append({'n': name, 'levy': levy, 'gf': gov_gf.get(bid) if bid else None,
                     'imp': [-r['impact'][k] for k in ('FY2028', 'FY2029', 'FY2030', 'FY2031', 'FY2032')]})
    govs.sort(key=lambda g: -g['imp'][1])
    data = {'districts': td['districts'], 'auth': td['auth'], 'groups': td['groups'], 'second': td['second'][L], 'govs': govs,
            'state': [-v for v in rec['statewide'].values()],
            # Election day, so the app can show the ballot reminder only until the vote.
            'vote': json.load(open(os.path.join(os.path.dirname(A3), 'elections', 'candidates_2026.json')))['election_date']}
    return data


def amend_page(out_dir):
    data = amend_data()
    govs = data['govs']
    js = open(os.path.join(HERE, 'amend.js')).read().replace('__A3__', json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    open(os.path.join(out_dir, 'assets', 'amend.js'), 'w').write(js)

    bay29 = sum(g['imp'][1] for g in govs)
    cty = next(g for g in govs if g['n'].startswith('Bay County'))
    lh = next(g for g in govs if 'Lynn Haven' in g['n'])

    def T(tid, text):
        return f'<span class="term" data-term="{tid}">{text}</span>'

    def S(k, text='Source'):
        t, u = SRC[k]
        return f'<a class="src" href="{u}" target="_blank" rel="noopener" title="{t}">{text}</a>'

    srcs = ''.join(f'<li><a href="{u}" target="_blank" rel="noopener">{t}</a></li>' for t, u in SRC.values())
    return f'''<div class="page tax amend">
  <header class="tx-top">
    <div class="tx-brand">
      <span class="eyebrow">Public Money · Amendment 3</span>
      <h1>Amendment 3: what changes in Bay County if it passes</h1>
      <p class="lede">On November 3, 2026, Florida voters decide Amendment 3, a property tax change. It needs at least 60% "yes" to pass. This page shows what it would do to your bill and to local budgets here, using the state's own estimates.</p>
      <p class="neutral">BayCounty.me takes no position on Amendment 3. Arguments on both sides are summarized below, with sources.</p>
    </div>
    <div class="stamp"><button type="button" id="pdf" class="pdf-btn"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>Data updated Oct 20, 2026</span></div>
  </header>

  <section class="explain" aria-labelledby="what-h">
    <div class="ex-txt">
      <span class="eyebrow">The simple version</span>
      <h2 id="what-h">What Amendment 3 does</h2>
      <ol class="ex-steps">
        <li><b>A much bigger discount for homeowners.</b> Today a {T('homestead', 'homestead')} gets about $50,000 knocked off its value for city, county and special-district taxes. Amendment 3 raises that to <b>$150,000 in 2027</b> and <b>$250,000 in 2028</b>, then grows it with inflation.</li>
        <li><b>School taxes don't change.</b> Homeowners still get only the first $25,000 off for school taxes, so almost everyone keeps paying those.</li>
        <li><b>New Floridians wait.</b> People who weren't Florida residents on December 31, 2026 get a $50,000 discount for their first four years, then the bigger one.</li>
        <li><b>Slower growth for everyone else.</b> For rentals, businesses, second homes and land, the yearly limit on how fast the taxed value can rise drops from 10% to 5% (not for school taxes).</li>
        <li><b>Limits on what property tax can pay for.</b> Cities and counties could spend it only on listed things such as public safety, schools, infrastructure, natural resources, debt and pensions, and running government.</li>
      </ol>
      <p class="muted">It takes effect January 1, 2027. The first bills affected would be the ones mailed in November 2027. The amendment also tells the Legislature to set up a way for cities and counties to go further and exempt homesteads completely. {S('rec', 'State analysis')} · {S('vcpa', 'Property appraiser explainer')}</p>
    </div>
  </section>

  <section class="tx-sec" id="calc" aria-labelledby="calc-h">
    <div class="sec-hd"><h2 id="calc-h">Your bill, before and after</h2><span class="muted">Uses today's tax rates for every column</span></div>
    <div class="calc">
      <form class="calc-in" onsubmit="return false">
        <label class="fld"><span>Where is the property?</span><select id="cDist"></select></label>
        <label class="fld"><span>{T('assessed-value', 'Assessed value')}</span>
          <span class="money"><span aria-hidden="true">$</span><input id="cVal" type="text" inputmode="numeric" autocomplete="off" value="250,000"></span>
          <small class="muted">On your TRIM notice or the Property Appraiser's site.</small></label>
        <fieldset class="seg-ctl"><legend>This property is</legend>
          <label><input type="radio" name="kind" value="home" checked> My homestead, and I lived in Florida before 2027</label>
          <label><input type="radio" name="kind" value="new"> My homestead, but I moved to Florida in 2027 or later</label>
          <label><input type="radio" name="kind" value="non"> A rental, second home, business or land</label>
        </fieldset>
      </form>
      <div class="calc-out" aria-live="polite">
        <div class="cmp" id="cmp"></div>
        <p class="note" id="cmpNote"></p>
      </div>
    </div>
    <div class="tablewrap"><table class="tx-table" id="cmpTable"></table></div>
    <p class="note">This is a simple estimate. It holds every tax rate at today's level and your value where it is now. In reality, values change, local governments may change their rates, and other exemptions (seniors, veterans, disability) and non-ad valorem fees aren't included.</p>
  </section>

  <section class="tx-sec" aria-labelledby="bud-h">
    <div class="sec-hd"><h2 id="bud-h">What it means for local budgets</h2><span class="muted">State estimate of property tax each government would no longer collect</span></div>
    <p class="note">The state's {T('rec', 'Revenue Estimating Conference')} ran every Bay County property through the new rules. It estimates local governments here would collect <b>${bay29/1e6:,.1f}M less</b> in FY2029, the first full year. That's money that would stay with property owners instead. Schools lose nothing, because school taxes aren't covered. {S('rec')}</p>
    <div class="hbars" id="lossBars"></div>
    <details class="tbl-toggle" open><summary>Year by year</summary><div class="tablewrap"><table class="tx-table" id="lossTable"></table></div></details>
    <p class="note">"Share of levy" compares the FY2029 estimate with what each government levied in FY2026, so it's a rough guide. Panama City Beach has no city property tax, so its city budget isn't affected.</p>
  </section>

  <section class="tx-sec" aria-labelledby="local-h">
    <div class="sec-hd"><h2 id="local-h">What local officials have said</h2></div>
    <div class="cards">
      <article class="card"><h3>Bay County</h3>
        <p>The county estimates it would lose about $22M in FY2028 and $36M a year starting FY2029, close to the state's ${cty['imp'][0]/1e6:.1f}M and ${cty['imp'][1]/1e6:.1f}M. {S('county')}</p>
        <p>The county says that after the loss its general fund would collect about $133.5M in property tax, against $141.7M already committed to public safety, constitutional officers and other legal obligations, leaving a gap of more than $8M. It lists parks, libraries, veterans services, transit and other programs as possible cuts, and franchise fees, sales tax, EMS fees, a gas tax and impact fees as possible new revenue. {S('county')}</p>
        <p>County Manager Joel Schubert: "87% of every property tax dollar is already spoken for." Sheriff Tommy Ford: "As written, I don't think Amendment 3 protects public safety." {S('wjhg_oct')}</p>
      </article>
      <article class="card"><h3>Lynn Haven</h3>
        <p>Mayor Dave Lowery has described a possible 40% to 45% drop in the city's property tax revenue. {S('wjhg_lh')} The state's estimate is ${lh['imp'][1]/1e6:.2f}M a year, about {lh['imp'][1]/lh['levy']:.0%} of what the city levied in FY2026. {S('rec')}</p>
      </article>
      <article class="card"><h3>CRAs</h3>
        <p>The county says it can't reduce its required {T('cra', 'CRA')} payments on its own. That includes about $22.2M a year to Panama City Beach's Front Beach Road CRA. As county revenue shrinks, those payments take up a bigger share of it. {S('county')} <a href="/public-money/cra-spending">CRA spending →</a></p>
      </article>
    </div>
  </section>

  <section class="tx-sec" aria-labelledby="args-h">
    <div class="sec-hd"><h2 id="args-h">The arguments</h2><span class="muted">In each side's own words, with sources</span></div>
    <div class="two args">
      <div class="arg"><h3>Supporters say</h3>
        <p class="who">Gov. Ron DeSantis, the Legislature, which put it on the ballot, Florida Realtors, the Republican Party of Florida and the Central Panhandle Association of Realtors</p>
        <ul>
          <li>Homeowners need relief from rising costs: "Families can afford to keep the homes they worked so hard to purchase" (Florida Realtors). {S('realtors')}</li>
          <li>Property taxes on a home you own are "paying rent to the government" (DeSantis). {S('realtors')}</li>
          <li>Local governments have benefited from fast-growing property tax collections and should control spending before asking homeowners to pay more. {S('desantis')}</li>
          <li>The lower 5% cap limits tax growth for landlords and businesses too: "You actually have less exposure on the business side if three passes than you do today" (DeSantis). {S('desantis')}</li>
        </ul>
      </div>
      <div class="arg"><h3>Opponents say</h3>
        <p class="who">Vote No on 3, many city and county governments, sheriffs and public safety groups, the Florida Association of Special Districts and the Florida Democratic Party</p>
        <ul>
          <li>The revenue loss would force cuts to services, and the amendment doesn't guarantee public safety funding. {S('wjhg_oct')} {S('fac', 'FAC summary')}</li>
          <li>Local governments may raise rates or fees to make up the difference, which would fall on renters, businesses and newer residents who don't get the bigger exemption. {S('renters')}</li>
          <li>The state provides no replacement money to local governments. {S('fac')}</li>
          <li>Realtors support it because their business depends on more sales at higher prices (Vote No on 3). {S('realtors')}</li>
        </ul>
      </div>
    </div>
    <aside class="callout"><b>Some context from this site's data.</b> Bay County's countywide property tax levy grew from $77.8M in FY2021 to $173.4M in FY2026, from rising values plus a 1-mill rate increase in FY2024. Over the same years, the county's total budget grew from $389M to $734M. <a href="/public-money/tax-dollars">Tax dollars page →</a></aside>
  </section>

  <section class="tx-sec" aria-labelledby="unk-h">
    <div class="sec-hd"><h2 id="unk-h">What's still unknown</h2></div>
    <ul class="plain">
      <li><b>Future rates.</b> Whether the county and cities would raise {T('millage', 'tax rates')}, add fees or cut services, and in what mix, is up to each local board.</li>
      <li><b>Going further.</b> The Legislature has to write the rules for how cities and counties could exempt homesteads completely. No timeline is set. {S('rec')}</li>
      <li><b>New residents.</b> How property appraisers will verify who was a Florida resident on December 31, 2026 isn't settled. {S('rec')}</li>
      <li><b>Ballot wording.</b> In August a Leon County judge ruled the original ballot summary misleading and ordered a rewrite. The Attorney General revised it, and voters will see the revised language. {S('ruling', 'Ruling')} · {S('rewrite', 'Revised language')}</li>
    </ul>
  </section>

  <section class="tx-sec method" aria-labelledby="src-h">
    <div class="sec-hd"><h2 id="src-h">Sources and method</h2></div>
    <p>The calculator applies today's ({T('fiscal-year', 'FY2026')}) rates for your area. Today, a homestead gets $25,000 off all taxes and a second ${data['second']:,} off non-school taxes on value above $50,000. Under Amendment 3, the first $25,000 applies only to school taxes, and non-school taxes get $150,000 off in 2027 and $250,000 in 2028 (for people who moved to Florida after 2026: $50,000, then about $51,220). These amounts follow the state's analysis. Budget figures are the state Revenue Estimating Conference's estimate by government, adopted July 10, 2026. Its "Board of County Commissioners" figure includes the county fire and mosquito control taxes.</p>
    <ul class="srcs">{srcs}</ul>
  </section>
  <div class="tt" id="tt" role="tooltip" hidden></div>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/amend.js" defer></script>'''
