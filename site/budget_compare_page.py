"""Compare a government's budget across years (/public-money/budget-compare).

The page holds no data. assets/budget_compare.js reads GET /api/v1/budget-compare (api/_budget.js), which compares two
fiscal years from the budget-years dataset (site/page_datasets.py budget_years()): totals, funds, General Fund
departments and services for adopted budgets, or audited revenue and spending.
"""
import os
from city_filter import city_bar, scope
from money_pages import PDF_BTN

HERE = os.path.dirname(os.path.abspath(__file__))

CSS = r"""
.bc-ctl{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;margin:6px 0 4px}
.bc-ctl select{min-height:38px}
.bc-swap{min-height:38px;padding:0 12px;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:var(--ink);font:500 .86rem var(--f-body);cursor:pointer}
.bc-swap:hover{border-color:var(--blue)}
.bc-basis{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 0}
.bc-sum{font-size:1rem;line-height:1.6;margin:14px 0 4px;max-width:62rem}
.bc-up{color:var(--blue);font-weight:600}.bc-dn{color:var(--accent-ink);font-weight:600}
.tax .kpi .v .bc-arrow{font-size:.8em;margin-left:4px}
.bc-notes{margin:12px 0 0}.bc-notes p{margin:4px 0}
.dv{display:flex;flex-direction:column;gap:4px}
.dv-r{display:grid;grid-template-columns:minmax(0,15rem) minmax(0,1fr) 11rem;gap:12px;align-items:center;padding:5px 6px;border-radius:8px;font-size:.88rem}
.dv-r:hover,.dv-r:focus-visible{background:var(--sunken);outline:none}
.dv-n{min-width:0;overflow-wrap:anywhere}.dv-n small{display:block;color:var(--muted);font-size:.76rem}
.dv-t{position:relative;height:16px}
.dv-t::before{content:"";position:absolute;left:50%;top:-3px;bottom:-3px;border-left:1px solid var(--faint)}
.dv-b{position:absolute;top:2px;height:12px;border-radius:3px}
.dv-b.up{left:50%;background:var(--blue)}
.dv-b.dn{right:50%;background:var(--gold)}
.dv-v{font:500 .82rem var(--f-data);text-align:right;white-space:nowrap}
.dv-v small{display:block;color:var(--muted);font:400 .74rem var(--f-data)}
.dv-tag{display:inline-block;font:600 .68rem var(--f-body);text-transform:uppercase;letter-spacing:.04em;border:1px solid currentColor;border-radius:999px;padding:0 6px;margin-left:6px;vertical-align:1px}
.dv-tag.add{color:var(--teal)}.dv-tag.rem{color:var(--muted)}
.dv-legend{display:flex;gap:16px;flex-wrap:wrap;font-size:.8rem;color:var(--muted);margin:2px 0 10px}
.dv-legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.yh{display:flex;align-items:flex-end;gap:8px;height:190px;padding:8px 2px 0;overflow-x:auto}
.yh-c{flex:1 0 54px;display:flex;flex-direction:column;align-items:center;gap:4px;height:100%;justify-content:flex-end;cursor:pointer;background:none;border:0;padding:0;color:var(--ink);font:inherit}
.yh-c:focus-visible{outline:2px solid var(--blue);outline-offset:2px;border-radius:6px}
.yh-bars{display:flex;align-items:flex-end;gap:3px;height:130px;width:100%;justify-content:center}
.yh-bar{width:42%;max-width:22px;border-radius:4px 4px 0 0;background:var(--bar)}
.yh-bar.gf{background:color-mix(in srgb,var(--bar) 55%,var(--surface))}
.yh-c.on .yh-bar{background:var(--blue)}.yh-c.on .yh-bar.gf{background:color-mix(in srgb,var(--blue) 50%,var(--surface))}
.yh-v{font:500 .74rem var(--f-data);white-space:nowrap}
.yh-y{font:600 .8rem var(--f-display)}.yh-c.on .yh-y{color:var(--blue)}
.yh-c small{font-size:.68rem;color:var(--muted);min-height:1em}
.bc-tbl td.num,.bc-tbl th.num{white-space:nowrap}
.bc-cov td{font-size:.86rem}.bc-cov .miss{color:var(--muted)}
@media (max-width:640px){.dv-r{grid-template-columns:minmax(0,1fr) auto;row-gap:4px}.dv-t{grid-column:1/-1;grid-row:2}}
"""


def budget_compare_page(out_dir, keys):
    open(os.path.join(out_dir, 'assets', 'budget_compare.js'), 'w').write(open(os.path.join(HERE, 'budget_compare.js')).read())
    sel = lambda i, lab: scope(f'<select id="{i}" aria-label="{lab}"></select>', lab)
    return f'''<style>{CSS}</style>
<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Public Money · Budgets</span><h1 id="bcTitle">Compare budgets across years</h1>
    <p class="lede">Pick a government and any two fiscal years to see what grew, what shrank and what's new: the total, the General Fund, each department, each service and each fund, in dollars and percent.</p></div>
    <div class="stamp">{PDF_BTN}<a class="pill" href="/public-money/budget-explorer">One year in detail →</a></div></header>
  {city_bar(keys, note='All governments shows Lynn Haven, which has the most years of detail')}
  <div class="bc-ctl">{sel('bcFrom', 'From')}{sel('bcTo', 'To')}<button type="button" class="bc-swap" id="bcSwap" data-scope title="Swap the two years">⇄ Swap</button></div>
  <div class="chips bc-basis" id="bcBasis" role="group" aria-label="What to compare">
    <button type="button" class="chip" data-b="adopted" aria-pressed="true">Adopted budgets</button>
    <button type="button" class="chip" data-b="actual" aria-pressed="false">Audited actuals</button></div>
  <p class="bc-sum" id="bcSum" aria-live="polite">Loading…</p>
  <div class="kpis" id="bcKpis"></div>
  <div class="callout bc-notes" id="bcNotes" hidden></div>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>How to read a year-over-year change</h2>
    <ol class="ex-steps"><li><b>Each fiscal year starts October 1.</b> FY2026 runs from October 2025 to September 2026 (schools: July to June).</li>
    <li><b>Adopted budgets are the plan</b> the commission approved before the year began. <b>Audited actuals</b> are what really came in and went out, reported to the state after the year closed, so they lag about two years.</li>
    <li><b>A big swing isn't always new spending.</b> Hurricane recovery money, a one-time grant or moving a cost from one department to another can make a line jump or vanish. The notes under each budget say what changed.</li></ol></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="years" data-tile="Every year">Every year on record</h2><span class="muted" id="bcHistNote">Tap a year to compare it</span></div>
    <div class="dv-legend" id="bcHistLegend"></div><div class="yh" id="bcHist"></div></section>
  <section class="tx-sec" id="secA"><div class="sec-hd"><h2 id="departments" data-tile="Departments">What changed, by department</h2><span class="muted" id="bcAnote">General Fund</span></div>
    <div class="chips print-hide" id="bcSort" role="group" aria-label="Sort"><button type="button" class="chip" data-s="change" aria-pressed="true">Biggest change</button><button type="button" class="chip" data-s="pct" aria-pressed="false">Biggest % change</button><button type="button" class="chip" data-s="to" aria-pressed="false">Largest now</button></div>
    <div class="dv-legend"><span><i style="background:var(--blue)"></i>Went up</span><span><i style="background:var(--gold)"></i>Went down</span></div>
    <div class="dv" id="bcA"></div>
    <details class="tbl-toggle"><summary>Table</summary><div class="tablewrap"><table class="tx-table bc-tbl" id="bcAt"></table></div></details></section>
  <section class="tx-sec" id="secS"><div class="sec-hd"><h2 id="services" data-tile="Services">What changed, by service</h2><span class="muted">Departments grouped into common services</span></div>
    <div class="dv" id="bcS"></div>
    <details class="tbl-toggle"><summary>Table</summary><div class="tablewrap"><table class="tx-table bc-tbl" id="bcSt"></table></div></details></section>
  <section class="tx-sec" id="secB"><div class="sec-hd"><h2 id="funds" data-tile="Funds">What changed, by fund</h2><span class="muted" id="bcBnote">Every fund</span></div>
    <div class="dv" id="bcB"></div>
    <details class="tbl-toggle"><summary>Table</summary><div class="tablewrap"><table class="tx-table bc-tbl" id="bcBt"></table></div></details></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="coverage" data-tile="Years on record">Which years we have</h2><span class="muted">For every government</span></div>
    <div class="tablewrap"><table class="tx-table bc-cov" id="bcCov"><tbody><tr><td class="muted">Loading…</td></tr></tbody></table></div>
    <p class="note">Missing a year? Budgets come from each government's adopted budget document. Where a city doesn't post one, you can <a href="/records-request">ask for it</a>.</p></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">Sources and how this is compared</h2></div>
    <div id="bcSrc"></div>
    <ul class="plain">
      <li><b>Lines are matched across years</b> by department or fund number where the budget prints one (Lynn Haven), and otherwise by name, so "Legislative - Commission" and "Legislative (commission)" count as one line. A line marked <span class="dv-tag add">new</span> or <span class="dv-tag rem">gone</span> is in only one of the two years; often it was renamed, merged or split.</li>
      <li><b>Departments are the General Fund only.</b> Utilities, the CRA, disaster recovery and other funds are in "by fund".</li>
      <li><b>Totals count transfers twice.</b> When one fund pays another, both show it, so a total can rise just because more money moved between funds.</li>
      <li><b>Services</b> group each government's own department names, the same way as the <a href="/public-money/budget-explorer#bench">budget explorer</a>. Transfers, reserves, debt and disaster lines are kept apart.</li>
      <li><b>Data:</b> <a href="/api/v1/budget-compare?gov=lh&amp;from=2025&amp;to=2026">/api/v1/budget-compare</a> · every line: <a href="/api/v1/datasets/budget-years">budget-years</a> (<a href="/downloads/budget-years.csv">CSV</a>).</li></ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/budget_compare.js" defer></script>'''
