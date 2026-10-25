"""How much property tax goes to Bay County's CRAs (/public-money/cra-tax-increment).

The page holds no data. assets/cra_increment.js reads /api/v1/datasets/cra-agencies, cra-tax-increment and
cra-increment-checks, built by site/page_datasets.py _cra_increment() from data/cra/tax_increment.json, each CRA's
budget_by_year (data/panama_city.json, pcb.json, lynn_haven.json, others.json) and data/tax/millage.json.
"""
import os
from money_pages import PDF_BTN

HERE = os.path.dirname(os.path.abspath(__file__))

CSS = r"""
.ci{--c-fbr:#E5564A;--c-pier:#F29A8F;--c-pc:#3F6FB0;--c-lh:#D18A1E;--c-cw:#22897C;--c-sf:#7B5FBF;--c-pk:#2F95C4;--c-band:rgba(63,111,176,.12)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .ci{--c-fbr:#FF8C82;--c-pier:#B8625A;--c-pc:#7FA6DA;--c-lh:#FFB84D;--c-cw:#4CC2B2;--c-sf:#A891E0;--c-pk:#7CC7E4;--c-band:rgba(127,166,218,.16)}}
:root[data-theme="dark"] .ci{--c-fbr:#FF8C82;--c-pier:#B8625A;--c-pc:#7FA6DA;--c-lh:#FFB84D;--c-cw:#4CC2B2;--c-sf:#A891E0;--c-pk:#7CC7E4;--c-band:rgba(127,166,218,.16)}
.ci-ctl{display:flex;flex-wrap:wrap;gap:8px 18px;margin:4px 0 10px}
.ci-chart{overflow-x:auto}
.ci-chart svg{display:block;min-width:640px;width:100%;height:auto}
.ci-chart text{font:400 11px var(--f-data);fill:var(--muted)}
.ci-legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.8rem;color:var(--muted);margin-top:8px}
.ci-legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.ci-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;vertical-align:1px}
.ci-tbl td small,.ci-tbl th small{display:block;color:var(--muted);font-weight:400;font-size:.76rem}
.ci-tbl tfoot td,.ci-tbl tfoot th{font-weight:600}
.ci-tag{display:inline-block;font:600 .68rem var(--f-body);text-transform:uppercase;letter-spacing:.04em;border:1px solid var(--line);border-radius:999px;padding:0 6px;margin-left:6px;color:var(--muted);vertical-align:1px}
.ci-who{display:flex;flex-direction:column;gap:8px;margin:6px 0 10px}
.ci-who-r{display:grid;grid-template-columns:minmax(0,11rem) minmax(0,1fr) 8.5rem;gap:12px;align-items:center;font-size:.88rem}
.ci-who-t{height:14px;border-radius:4px;background:var(--sunken);overflow:hidden}
.ci-who-t b{display:block;height:100%;border-radius:4px}
.ci-who-v{font:500 .84rem var(--f-data);text-align:right;white-space:nowrap}
.ci-two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.ci-two>div{min-width:0}
.ci ul.plain li{margin:0 0 8px}
@media (max-width:760px){.ci-two{grid-template-columns:1fr}.ci-who-r{grid-template-columns:minmax(0,7rem) minmax(0,1fr) 7rem}}
"""


def cra_increment_page(out_dir):
    open(os.path.join(out_dir, 'assets', 'cra_increment.js'), 'w').write(open(os.path.join(HERE, 'cra_increment.js')).read())
    return f'''<style>{CSS}</style>
<div class="page tax ci">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Public Money · Redevelopment</span><h1>How much property tax goes to the CRAs</h1>
    <p class="lede">Seven Community Redevelopment Agencies in Bay County collect tax increment: the property tax that Bay County and the cities levy on growth in value inside each district since its base year. Here is how much that is each year, who pays it, what has been paid so far and what it could add up to before each CRA ends.</p></div>
    <div class="stamp">{PDF_BTN}<a class="pill" href="/public-money/cra-spending">What the CRAs spend it on →</a></div></header>
  <div class="kpis" id="ciKpis"><div class="kpi"><span class="eyebrow">Loading</span><span class="v">…</span></div></div>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>What "lost" revenue means here</h2>
    <ol class="ex-steps"><li><b>A CRA starts with a base value.</b> The county and the city keep collecting tax on the value the district had in its base year.</li>
    <li><b>Growth above the base is the increment.</b> Each year the county and the city pay 95% of what their tax rate raises on that growth into the CRA's trust fund (s.163.387, F.S.). The CRA can spend it only inside the district.</li>
    <li><b>So the money isn't gone, it's set aside.</b> Without a CRA the county and city could spend it anywhere. A city paying into its own CRA still controls how it's spent; the county's payments leave its control. The school district and the water management district are exempt and pay nothing.</li></ol></div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="years" data-tile="By year">Tax increment by year</h2><span class="muted" id="ciYearNote">Reported through FY2025, then projected</span></div>
    <div class="ci-ctl">
      <div class="chips" id="ciScen" role="group" aria-label="Growth after FY2025"><button type="button" class="chip" data-s="low" aria-pressed="false">Low 3%</button><button type="button" class="chip" data-s="mid" aria-pressed="true">Middle 6%</button><button type="button" class="chip" data-s="high" aria-pressed="false">High 9%</button></div>
      <div class="chips" id="ciWho" role="group" aria-label="Who pays"><button type="button" class="chip" data-w="increment" aria-pressed="true">All payers</button><button type="button" class="chip" data-w="county_amount" aria-pressed="false">Bay County</button><button type="button" class="chip" data-w="city_amount" aria-pressed="false">Cities</button></div>
    </div>
    <div class="ci-chart"><svg id="ciChart" viewBox="0 0 1000 340" role="img" aria-label="Stacked bars of tax increment by CRA and fiscal year"></svg></div>
    <div class="ci-legend" id="ciLegend"></div>
    <p class="note">Lighter bars fill a gap between two reported years. After FY2025: adopted CRA budgets where they exist, then the growth rate picked above, until each CRA's sunset. Front Beach Road is held to its $30M yearly cap.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="cras" data-tile="Each CRA">Each CRA at a glance</h2><span class="muted">FY2025, the last year reported for all seven</span></div>
    <div class="tablewrap"><table class="tx-table ci-tbl" id="ciTbl"><tbody><tr><td class="muted">Loading…</td></tr></tbody></table></div>
    <p class="note">"Paid on record" adds the years we have figures for since FY2016, with gaps filled; the earliest of those years are missing for several CRAs. "Still to come" runs from FY2026 to the sunset under the growth rate picked above.</p>
    <details class="tbl-toggle"><summary>Sunset dates and what they rest on</summary><ul class="plain" id="ciSunsets"></ul></details></section>

  <section class="tx-sec"><div class="ci-two">
    <div><div class="sec-hd"><h2 id="who" data-tile="Who pays">Who pays, FY2025</h2></div>
      <div class="ci-who" id="ciWhoBars"></div>
      <p class="note">Bay County and the city each pay 95% of their own levy on the same growth, so the split follows their tax rates. Panama City Beach levies no city property tax, so Bay County funds its two CRAs alone.</p></div>
    <div><div class="sec-hd"><h2 id="checks" data-tile="Checks">Checked against official figures</h2></div>
      <div class="tablewrap"><table class="tx-table ci-tbl" id="ciChecks"></table></div></div>
  </div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="context" data-tile="Context">Things that change the picture</h2></div>
    <ul class="plain">
      <li><b>Front Beach Road is most of it.</b> About three of every four CRA dollars in the county go to Panama City Beach's Front Beach Road CRA, all from Bay County. Its plan was extended from 2031 to 2049 in 2019. A 2020 agreement rebates 20% of county increment above $15M a year, and a 2024 agreement caps yearly CRA revenue at $30M through 2049.</li>
      <li><b>Would the growth have happened anyway?</b> The estimate assumes it would have, which is the usual way to count revenue given up. CRAs say their spending causes some of the growth; critics say most of it would come regardless. This page doesn't try to settle that.</li>
      <li><b>Tax rates respond.</b> When a CRA takes part of the county's levy, the county may set a higher rate to pay for the same services. The county raised its rate by 1 mill in 2023, and some commissioners tied that to CRA costs; other costs also drove it.</li>
      <li><b>Negotiated exceptions.</b> Bay County keeps 26% of the increment from Panama City's 2025 St. Andrews expansion area, and auditors found Springfield and Parker paid their city share late or not at all for some years. Neither is in the estimate.</li>
    </ul></section>

  <section class="tx-sec method"><div class="ci-two">
    <div><div class="sec-hd"><h2 id="method">How the estimate was built</h2></div>
      <ul class="plain">
        <li><b>Yearly totals</b> come from each CRA's annual reports, audits filed with the Auditor General and budgets, linked on the <a href="/public-money/cra-spending">CRA spending</a> page. Years between two reported years are filled on a steady growth path.</li>
        <li><b>County and city shares</b>: county share = county rate ÷ (county rate + city rate) for the tax year that funds the fiscal year, from the <a href="/api/v1/datasets/property-tax-rates">property tax rates</a> (tax years 2020 to 2026). Earlier years use the 2020 rates.</li>
        <li><b>Only the county's general levy and the city levy</b> are counted. County mosquito control (0.20 mills) may also pay into some CRAs, which would add a few percent to the county share.</li>
        <li><b>Projections</b> use adopted FY2026 and FY2027 CRA budgets where they exist, then grow 3%, 6% or 9% a year. County taxable value grew about 13% a year from 2020 to 2025, so the high scenario is not a ceiling.</li>
        <li><b>Data:</b> <a href="/api/v1/datasets/cra-agencies">cra-agencies</a> (<a href="/downloads/cra-agencies.csv">CSV</a>) · <a href="/api/v1/datasets/cra-tax-increment">cra-tax-increment</a> (<a href="/downloads/cra-tax-increment.csv">CSV</a>) · <a href="/api/v1/datasets/cra-increment-checks">cra-increment-checks</a>.</li>
      </ul></div>
    <div><div class="sec-hd"><h2 id="gaps">What's missing</h2></div>
      <ul class="plain">
        <li>The site starts at FY2016, so nothing paid before then is counted, even where a CRA is decades older.</li>
        <li>Panama City: no yearly figures for FY2019 to FY2020.</li>
        <li>Lynn Haven: none for FY2016. Callaway: none before FY2021. Springfield: none before FY2023. Parker reports no positive increment before FY2024.</li>
        <li>Pier Park: none for FY2016 or FY2018, and no end date found.</li>
        <li>Callaway's FY2027 budget shows $3.02M of increment, nearly three times FY2025. It is used as published.</li>
        <li>We could not confirm whether Front Beach Road's yearly figures are before or after the county's 20% rebate.</li>
        <li>Mexico Beach has no CRA.</li>
        <li>Each CRA's yearly DR-420TIF form, certified by the Property Appraiser with the base value, current value and each taxing body's payment, would close most of these gaps. You can <a href="/records-request?gov=property_appraiser">ask for them</a>.</li>
      </ul></div>
  </div></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/cra_increment.js" defer></script>'''
