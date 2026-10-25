"""Open books: each government's own accounting, published from the files it sends.

  /public-money/checkbook        every payment in the government's check register (assets/checkbook.js)
  /public-money/budget-tracker   spending and revenue against the budget, month by month (assets/budget_tracker.js)

The pages hold no data. Their scripts read GET /api/v1/checkbook and /api/v1/budget-actual (api/_openbooks.js) and
the checkbook-payments and budget-actuals datasets, whose rows an admin publishes from the private finance workspace
(api/_finance/publish.js). Until a government's files are published, each page says so.
"""
import os
from city_filter import city_bar, scope
from money_pages import PDF_BTN

HERE = os.path.dirname(os.path.abspath(__file__))

CSS = r"""
.ob-empty{background:var(--surface);border:1px dashed var(--line);border-radius:12px;padding:22px 20px;margin:16px 0;display:grid;gap:8px;max-width:62rem}
.ob-empty h2{font-size:1.15rem;margin:0}
.ob-sum{font-size:1rem;line-height:1.6;margin:14px 0 4px;max-width:62rem}
.ob-up{color:var(--accent-ink);font-weight:600}.ob-ok{color:var(--teal);font-weight:600}
.ob-bars{display:flex;flex-direction:column;gap:4px}
.ob-r{display:grid;grid-template-columns:minmax(0,15rem) minmax(0,1fr) 9rem;gap:12px;align-items:center;padding:5px 6px;border-radius:8px;font-size:.88rem}
.ob-r:hover{background:var(--sunken)}
.ob-n{min-width:0;overflow-wrap:anywhere}.ob-n small{display:block;color:var(--muted);font-size:.76rem}
.ob-t{position:relative;height:14px;background:var(--sunken);border-radius:3px}
.ob-b{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--blue)}
.ob-b.enc{background:color-mix(in srgb,var(--blue) 45%,var(--surface))}
.ob-b.over{background:var(--accent-ink)}
.ob-mark{position:absolute;top:-4px;bottom:-4px;border-left:2px solid var(--ink)}
.ob-v{font:500 .82rem var(--f-data);text-align:right;white-space:nowrap}.ob-v small{display:block;color:var(--muted);font:400 .74rem var(--f-data)}
.ob-legend{display:flex;gap:16px;flex-wrap:wrap;font-size:.8rem;color:var(--muted);margin:2px 0 10px}
.ob-legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.ob-legend i.mk{width:2px;height:12px;border-radius:0;background:var(--ink)}
.ob-months{display:flex;align-items:flex-end;gap:6px;height:180px;padding:8px 2px 0;overflow-x:auto}
.ob-m{flex:1 0 44px;display:flex;flex-direction:column;align-items:center;gap:4px;height:100%;justify-content:flex-end}
.ob-mb{width:60%;max-width:30px;border-radius:4px 4px 0 0;background:var(--blue)}
.ob-mv{font:500 .7rem var(--f-data);white-space:nowrap}.ob-ml{font:600 .76rem var(--f-display)}
.ob-search{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:0 0 10px}
.ob-search input{min-height:38px;flex:1 1 16rem;padding:0 12px;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:var(--ink);font:inherit}
.ob-pager{display:flex;gap:10px;align-items:center;justify-content:flex-end;margin:10px 0 0;font-size:.86rem}
.ob-btn{min-height:36px;padding:0 12px;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:var(--ink);font:500 .86rem var(--f-body);cursor:pointer}
.ob-btn:disabled{opacity:.45;cursor:default}
.ob-dept summary{list-style:none;cursor:pointer}.ob-dept summary::-webkit-details-marker{display:none}
.ob-dept[open] .ob-r{background:var(--sunken)}
.ob-lines{margin:4px 0 10px 6px}
.ob-tag{display:inline-block;font:600 .68rem var(--f-body);text-transform:uppercase;letter-spacing:.04em;border:1px solid currentColor;border-radius:999px;padding:0 6px;margin-left:6px;vertical-align:1px}
.ob-tag.over{color:var(--accent-ink)}.ob-tag.ahead{color:var(--gold)}.ob-tag.ind{color:var(--muted)}
.tx-table td.num,.tx-table th.num{white-space:nowrap}
@media (max-width:640px){.ob-r{grid-template-columns:minmax(0,1fr) auto;row-gap:4px}.ob-t{grid-column:1/-1;grid-row:2}}
"""

EMPTY = '''<div class="ob-empty" id="{id}" hidden><h2>Not published yet</h2>
    <p id="{id}Txt">This government's files haven't been published yet.</p>
    <p class="muted small">BayCounty.me publishes each government's own monthly accounting files once they arrive and add up to their printed totals. Want them sooner? <a href="/records-request">Ask for the records</a>.</p></div>'''


def _copy(out_dir, name):
    open(os.path.join(out_dir, 'assets', name), 'w').write(open(os.path.join(HERE, name)).read())


def checkbook_page(out_dir):
    _copy(out_dir, 'checkbook.js')
    return f'''<style>{CSS}</style>
<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Public Money · Open books</span><h1 id="cbTitle">Checkbook</h1>
    <p class="lede">Every payment a local government makes, from its own check register: who got paid, how much, when and from which fund. Search any company, or see where the money went month by month.</p></div>
    <div class="stamp">{PDF_BTN}<a class="pill" href="/public-money/budget-tracker">Budget tracker →</a></div></header>
  {city_bar(None, note='Governments appear here once their files are published')}
  {scope('<select id="cbFy" aria-label="Fiscal year"></select>', 'Fiscal year')}
  <p class="ob-sum" id="cbSum" aria-live="polite">Loading…</p>
  {EMPTY.format(id='cbEmpty')}
  <div id="cbBody">
  <div class="kpis" id="cbKpis"></div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="months" data-tile="By month">Payments by month</h2><span class="muted" id="cbMonthsNote"></span></div>
    <div class="ob-months" id="cbMonths"></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="payees" data-tile="Top payees">Who was paid the most</h2><span class="muted">Companies and agencies, this fiscal year</span></div>
    <div class="ob-bars" id="cbPayees"></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="funds" data-tile="By fund">Which fund paid</h2><span class="muted">Each fund is a separate pot of money with its own rules</span></div>
    <div class="ob-bars" id="cbFunds"></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="all" data-tile="Every payment">Every payment</h2><span class="muted" id="cbCount"></span></div>
    <div class="ob-search"><input type="search" id="cbQ" placeholder="Search a payee, description, check or invoice number" aria-label="Search payments"><a class="pill" id="cbCsv" href="/api/v1/datasets/checkbook-payments?format=csv">Download CSV</a></div>
    <div class="tablewrap"><table class="tx-table" id="cbTable"><thead><tr><th scope="col">Date</th><th scope="col">Payee</th><th scope="col">What for</th><th scope="col">Fund</th><th scope="col">Check</th><th scope="col" class="num">Amount</th></tr></thead><tbody></tbody></table></div>
    <div class="ob-pager"><span id="cbPage" class="muted"></span><button type="button" class="ob-btn" id="cbPrev">Newer</button><button type="button" class="ob-btn" id="cbNext">Older</button></div></section>
  </div>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>The government's own check register,</b> exported from its accounting system and sent to BayCounty.me each month. A file is published only after its payments add up to the total printed on the report.</li>
      <li><b>Voided checks are left out.</b> A check that was written and then voided would otherwise count twice.</li>
      <li><b>Private individuals aren't named.</b> Refunds, reimbursements and other payments to people show as "Individual (name withheld)", counted in every total. Companies, agencies and nonprofits are named and linked to their profiles.</li>
      <li><b>Fiscal years start October 1.</b> FY2026 runs from October 2025 to September 2026.</li>
      <li><b>Data:</b> <a href="/api/v1/checkbook?gov=lh">/api/v1/checkbook</a> · every payment: <a href="/api/v1/datasets/checkbook-payments">checkbook-payments</a>. <span id="cbFiles"></span></li></ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/checkbook.js" defer></script>'''


def budget_tracker_page(out_dir):
    _copy(out_dir, 'budget_tracker.js')
    return f'''<style>{CSS}</style>
<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Public Money · Open books</span><h1 id="btTitle">Budget tracker</h1>
    <p class="lede">How each department is spending against its budget this year, from the government's own monthly budget report: what's spent, what's committed, and whether it's running ahead of the calendar.</p></div>
    <div class="stamp">{PDF_BTN}<a class="pill" href="/public-money/checkbook">Checkbook →</a><a class="pill" href="/public-money/budget-compare">Compare years →</a></div></header>
  {city_bar(None, note='Governments appear here once their files are published')}
  {scope('<select id="btFy" aria-label="Fiscal year"></select>', 'Fiscal year')}{scope('<select id="btAsOf" aria-label="Report"></select>', 'As of')}
  <p class="ob-sum" id="btSum" aria-live="polite">Loading…</p>
  {EMPTY.format(id='btEmpty')}
  <div id="btBody">
  <div class="kpis" id="btKpis"></div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="departments" data-tile="Departments">Each department against its budget</h2><span class="muted">Tap a department for its lines</span></div>
    <div class="ob-legend"><span><i style="background:var(--blue)"></i>Spent</span><span><i style="background:color-mix(in srgb,var(--blue) 45%,var(--surface))"></i>Committed (open purchase orders)</span><span><i class="mk"></i>Share of the year gone</span><span><i style="background:var(--accent-ink)"></i>Over budget</span></div>
    <div class="ob-bars" id="btDepts"></div></section>
  <section class="tx-sec" id="btRevSec"><div class="sec-hd"><h2 id="revenue" data-tile="Revenue">Money coming in</h2><span class="muted">Collected so far against what the budget expects</span></div>
    <div class="ob-bars" id="btRev"></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="months" data-tile="Month by month">Month by month</h2><span class="muted">Every report published this year</span></div>
    <div class="tablewrap"><table class="tx-table" id="btMonths"></table></div></section>
  </div>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>How to read this</h2>
    <ol class="ex-steps"><li><b>The line on each bar is today's date in the fiscal year.</b> Halfway through the year, a department at about half its budget is on pace.</li>
    <li><b>Committed money counts.</b> An open purchase order is money promised to a vendor, so it's added to what's spent.</li>
    <li><b>Running ahead isn't always a problem.</b> Insurance, software licenses and debt payments are often paid once a year, early. Going over the budget needs the commission to approve a budget amendment.</li></ol></div></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>The government's own budget-vs-actual report</b> from its accounting system, as of each month end. A report is published only after its lines add up to the total printed on it.</li>
      <li><b>The budget is the amended budget</b> where the report gives one: the adopted budget plus any changes the commission approved during the year.</li>
      <li><b>Departments are grouped as the report lists them.</b> Revenue lines are shown separately and aren't counted as spending.</li>
      <li><b>Data:</b> <a href="/api/v1/budget-actual?gov=lh">/api/v1/budget-actual</a> · every line: <a href="/api/v1/datasets/budget-actuals">budget-actuals</a>. <span id="btFiles"></span></li></ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/budget_tracker.js" defer></script>'''
