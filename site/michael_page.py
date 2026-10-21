"""'Hurricane Michael money' page for baycounty.me."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, '..', 'data', 'michael')


def michael_page(out_dir):
    m = json.load(open(os.path.join(DIR, 'michael.json')))
    led = json.load(open(os.path.join(DIR, 'pa_ledger.json')))
    pa, ia, cd, oth = m['fema_pa'], m['fema_ia'], m['cdbg_dr'], m['other']
    tot = pa['bay_totals']
    cdbg_bay = [a for a in cd['bay_awards']]
    cdbg_sum = sum(a['amount'] for a in cdbg_bay if a.get('amount'))
    sba = next((f for f in oth['sba_and_nfip']['figures'] if f['item'].startswith('SBA')), None)
    data = {
        'rows': led['rows'], 'cats': led['categories'],
        'apps': [{'n': a['applicant'], 'p': a['projects'], 'f': a['federal_obligated']} for a in pa['by_applicant']],
        'catsum': [{'c': c['category'], 'n': c['description'], 'p': c['projects'], 'f': c['federal_obligated']} for c in pa['by_category']],
        'ia': [{'city': c['city'], 'oreg': c.get('owners_validRegistrations'), 'oapp': c.get('owners_approvedForFemaAssistance'), 'oamt': c.get('owners_totalApprovedIhpAmount'),
                'rreg': c.get('renters_validRegistrations'), 'rapp': c.get('renters_approvedForFemaAssistance'), 'ramt': c.get('renters_totalApprovedIhpAmount'), 't': c.get('total_approved_ihp')} for c in ia['by_city']],
        'cdbg': [{'prog': a['program'].replace('Rebuild Florida ', ''), 'r': a['recipient'], 'amt': a.get('amount'), 'p': a.get('project', ''), 'd': a.get('announced', ''), 'rounded': a.get('amount_is_rounded', False), 'u': a['source_url']} for a in cdbg_bay],
        'debris': [{'g': x['government'], 'p': x['fema_pa_category_A_projects'], 'f': x['fema_pa_category_A_federal_obligated']} for x in m['debris_fema_pa_category_a_by_government']],
    }
    js = open(os.path.join(HERE, 'michael.js')).read().replace('__MI__', json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    open(os.path.join(out_dir, 'assets', 'michael.js'), 'w').write(js)

    def a(u, t):
        return f'<a href="{u}" target="_blank" rel="noopener">{t}</a>'

    st = oth['state_appropriations_2019_session']
    state_rows = ''.join(f'<li>{x["recipient"]}: <b>${x["amount"]:,.0f}</b>{(" (" + x["detail"] + ")") if x.get("detail") else ""}</li>'
                         for x in st['items'] if not x['recipient'].startswith('Bay County -') and not x['recipient'].startswith('East Bay'))
    debris_rows = ''.join(f'<li><b>{x["government"]}</b>: {x["contractor"]}{": $" + format(x["amount"], ",.0f") if x.get("amount") else ""} <span class="muted">({x["amount_type"]})</span> {a(x["source_url"], "Source")}</li>' for x in m['debris_contracts'])
    case = ''.join(f'<li><span class="tl-d">{e["date"]}</span><span>{e["event"]} {a(e["source_url"], "Source")}</span></li>' for e in m['lynn_haven_case'])
    tyn = [t for t in oth['tyndall_afb']['figures'] if 'estimate' in t['item'].lower()]
    share = tot['federal_obligated'] / tot['project_amount']
    ia_total = ia['bay_total_approved_ihp_owners_plus_renters']

    return f'''<div class="page tax mi">
  <header class="tx-top">
    <div class="tx-brand">
      <span class="eyebrow">Public Money · Hurricane Michael</span>
      <h1>Where the Hurricane Michael money went</h1>
      <p class="lede">Hurricane Michael hit Bay County on October 10, 2018. Billions in federal, state and insurance money followed. This page tracks the public part: who received it, what it paid for, and what's still unclear.</p>
    </div>
    <div class="stamp"><button type="button" id="pdf" class="pdf-btn"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>FEMA data refreshed {pa.get('data_refreshed', '2026')[:10]}<br>Data updated Oct 20, 2026</span></div>
  </header>

  <section class="explain" aria-labelledby="how-h">
    <div class="ex-txt">
      <span class="eyebrow">The simple version</span>
      <h2 id="how-h">How disaster money works</h2>
      <ol class="ex-steps">
        <li><b>FEMA pays governments back.</b> After a disaster declaration, FEMA's Public Assistance program reimburses cities, the county, schools and some nonprofits for debris cleanup, emergency work and rebuilding public buildings. Each job is a "project" with its own paperwork.</li>
        <li><b>FEMA helps households.</b> Individual Assistance gives grants to homeowners and renters for repairs, temporary rent and other needs.</li>
        <li><b>HUD funds the long rebuild.</b> Congress later sent Florida disaster block grants (CDBG-DR), which the state handed out through "Rebuild Florida" for housing, infrastructure and downtowns.</li>
        <li><b>Loans and insurance fill in.</b> SBA disaster loans and flood insurance claims went straight to residents and businesses.</li>
      </ol>
    </div>
  </section>

  <div class="kpis">
    <div class="kpi"><span class="eyebrow">FEMA Public Assistance</span><span class="v">${tot['federal_obligated']/1e6:,.0f}M</span><span class="s">{tot['projects']} projects for {tot['applicants']} Bay County applicants</span></div>
    <div class="kpi"><span class="eyebrow">FEMA aid to households</span><span class="v">${ia_total/1e6:,.1f}M</span><span class="s">Approved for owners and renters</span></div>
    <div class="kpi"><span class="eyebrow">Rebuild Florida awards</span><span class="v">${cdbg_sum/1e6:,.1f}M</span><span class="s">HUD money to Bay governments, as announced</span></div>
    <div class="kpi"><span class="eyebrow">SBA disaster loans</span><span class="v">${(sba['amount'] if sba else 0)/1e6:,.0f}M</span><span class="s">Approved by Jan 2019 (early snapshot)</span></div>
  </div>

  <section class="tx-sec" aria-labelledby="who-h">
    <div class="sec-hd"><h2 id="who-h">Who got FEMA rebuilding money</h2><span class="muted">Federal share obligated, Public Assistance</span></div>
    <div class="hbars" id="appBars"></div>
    <p class="note">FEMA paid {share:.0%} of the ${tot['project_amount']/1e6:,.0f}M in eligible costs on these projects. The rest came from the state and the local governments themselves. Another {pa['statewide_projects_not_attributed']['projects']} projects (${pa['statewide_projects_not_attributed']['federal_obligated']/1e6:,.0f}M, mostly state agencies) are coded "statewide," so FEMA's data doesn't say how much was spent in Bay County. {a(tot['source_url'], 'OpenFEMA')}</p>
  </section>

  <section class="tx-sec" aria-labelledby="what-h">
    <div class="sec-hd"><h2 id="what-h">What it paid for</h2></div>
    <div class="hbars" id="catBars"></div>
  </section>

  <section class="tx-sec" aria-labelledby="led-h">
    <div class="sec-hd"><h2 id="led-h">Every FEMA project in Bay County</h2><span class="muted" id="ledCount" aria-live="polite"></span></div>
    <div class="filters-row">
      <input id="ledQ" type="search" data-param="q" placeholder="Search projects (e.g. school, pier, debris)" aria-label="Search projects">
      <select id="ledA" aria-label="Applicant" data-param="a"><option value="">All applicants</option></select>
      <select id="ledC" aria-label="Type" data-param="c"><option value="">All types</option></select>
      <button type="button" class="pill sm" id="ledCsv">Download this view (CSV)</button>
    </div>
    <div class="tablewrap"><table class="tx-table" id="ledT"><thead><tr><th scope="col">Applicant</th><th scope="col">Project</th><th scope="col">Type</th><th scope="col" class="num" aria-sort="descending">Federal</th><th scope="col" class="num">First paid</th><th scope="col">Status</th></tr></thead><tbody></tbody></table></div>
    <button type="button" class="pill" id="ledMore">Show more</button>
  </section>

  <section class="tx-sec" aria-labelledby="ia-h">
    <div class="sec-hd"><h2 id="ia-h">Help for households</h2><span class="muted">FEMA Individuals and Households Program, by mailing city</span></div>
    <div class="tablewrap"><table class="tx-table" id="iaT" data-csv="bay-county-fema-household-aid"></table></div>
    <p class="note">"Registered" counts everyone who applied; "approved" counts those FEMA found eligible for any aid. {a(ia['owners']['source_url'], 'Owners data')} · {a(ia['renters']['source_url'], 'Renters data')}</p>
  </section>

  <section class="tx-sec" aria-labelledby="cd-h">
    <div class="sec-hd"><h2 id="cd-h">Rebuild Florida (HUD) awards to Bay governments</h2></div>
    <div class="tablewrap"><table class="tx-table" id="cdT" data-csv="bay-county-rebuild-florida-awards"></table></div>
    <p class="note">Florida received ${cd['state_allocation'][2]['amount']/1e6:,.1f}M in HUD disaster block grants for Michael across the Panhandle. These are the announced awards to Bay County governments that we could confirm; housing repair spending in Bay County isn't broken out publicly. {a(cd['state_allocation'][2]['source_url'], 'Federal Register')}</p>
  </section>

  <section class="tx-sec" aria-labelledby="st-h">
    <div class="sec-hd"><h2 id="st-h">State money</h2><span class="muted">2019 legislative session, as reported</span></div>
    <ul class="plain">{state_rows}</ul>
    <p class="note">From a news summary of the 2019 budget, not the budget law itself. The housing and grant-pool amounts covered the whole region. {a(st['source_url'] if st.get('source_url') else st['items'][0]['source_url'], 'Source')}</p>
  </section>

  <section class="tx-sec" aria-labelledby="deb-h">
    <div class="sec-hd"><h2 id="deb-h">Debris cleanup</h2><span class="muted">The single biggest cost</span></div>
    <div class="two">
      <div><h4>FEMA debris money by government</h4><div class="hbars small" id="debBars"></div></div>
      <div><h4>Debris contracts we could confirm</h4><ul class="plain">{debris_rows}</ul></div>
    </div>
  </section>

  <section class="tx-sec" aria-labelledby="lh-h">
    <div class="sec-hd"><h2 id="lh-h">The Lynn Haven cleanup corruption case</h2><span class="muted">From federal court filings and news coverage</span></div>
    <p class="note">Federal prosecutors charged Lynn Haven officials and contractors over storm cleanup billing after Michael. This is a timeline of what the Justice Department announced and what courts decided.</p>
    <ol class="timeline">{case}</ol>
  </section>

  <aside class="callout"><b>Tyndall Air Force Base</b> is being rebuilt with federal military money, separate from local government recovery. Air Force cost estimates have ranged from ${min(t['amount'] for t in tyn)/1e9:.1f}B to ${max(t['amount'] for t in tyn)/1e9:.1f}B. {a(tyn[0]['source_url'], 'Source')}</aside>

  <section class="tx-sec method" aria-labelledby="gap-h">
    <div class="sec-hd"><h2 id="gap-h">Sources and gaps</h2></div>
    <p>FEMA figures come from OpenFEMA's Public Assistance and housing assistance datasets for disaster DR-4399-FL. Amounts are the federal share FEMA has obligated (committed), which can still change as projects close out. HUD awards come from the Governor's announcements; state money from a news summary of the 2019 budget; SBA and flood insurance from FEMA's January 2019 Bay County fact sheet.</p>
    <details class="gaps"><summary>What we couldn't find ({len(m['gaps'])})</summary><ul>{''.join(f'<li>{g}</li>' for g in m['gaps'])}</ul></details>
  </section>
  <div class="tt" id="tt" role="tooltip" hidden></div>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/michael.js" defer></script>'''
