"""Nonprofits (/connections/nonprofits): every nonprofit in the county, what it reports to the IRS, the government
money and grants that reach it, and officials who sit on its board.

Layout: three cards with the strongest connections, a Nonprofits / People switch, a short ranked list (connected
first) and a details panel (side panel on desktop, full screen on phones). The page holds no data. assets/nonprofits.js reads /api/v1/datasets/nonprofits, nonprofit-board-members,
nonprofit-payments, nonprofit-grants, nonprofit-officials and charity-registrations (FDACS). Board members are public records (IRS returns and state
filings); officials are tagged only when an admin confirmed the name match in /admin (Nonprofit boards tab).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

CSS = r"""
.np-seg{display:inline-flex;width:max-content;border-radius:999px;padding:4px;margin:4px 0 16px;background:var(--surface);box-shadow:var(--ui-shadow)}
.np-seg button{all:unset;cursor:pointer;font:500 .9rem var(--f-body);padding:6px 18px;border-radius:999px;color:var(--muted)}
.np-seg button[aria-pressed=true]{background:var(--navy);color:var(--bg)}
.np-seg button:focus-visible,.np-card:focus-visible,.np-tabs button:focus-visible,.np-row:focus-visible{outline:2px solid var(--navy);outline-offset:2px}
.np-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin:0 0 22px}
.np-card{all:unset;box-sizing:border-box;display:flex;flex-direction:column;align-items:flex-start;cursor:pointer;background:var(--surface);border-radius:20px;padding:16px 18px;box-shadow:var(--ui-shadow);transition:box-shadow .15s ease-out,scale .15s ease-out}
.np-card:hover,.np-card[aria-pressed=true]{box-shadow:var(--ui-ring)}
.np-card:active{scale:.98}
.np-card .ui-ti{margin-bottom:10px}
.np-card b{display:block;font:600 1.85rem var(--f-display);letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.np-card strong{display:block;font-weight:600;margin:2px 0}
.np-card > span:last-child{color:var(--muted);font-size:.85rem;line-height:1.45}
.np-lay{display:grid;grid-template-columns:minmax(0,1fr) 400px;gap:24px;align-items:start}
.np-q{width:100%;box-sizing:border-box;min-height:48px;border:0;border-radius:14px;padding:0 16px;background:var(--surface);box-shadow:var(--ui-shadow);color:var(--ink);font:inherit}
.np-q:focus{outline:none;box-shadow:var(--ui-ring)}
.np-filters{margin:8px 0 0;font-size:.88rem}
.np-filters summary{cursor:pointer;color:var(--muted)}
.np-filters .filters-row{margin-top:8px}
.np-tabs{display:flex;gap:20px;border-bottom:1px solid var(--line);margin:12px 0 0;overflow-x:auto}
.np-tabs button{all:unset;cursor:pointer;padding:10px 0;color:var(--muted);font-size:.92rem;white-space:nowrap;border-bottom:2px solid transparent}
.np-tabs button[aria-selected=true]{color:var(--ink);font-weight:600;border-bottom-color:var(--navy)}
.np-row{display:grid;grid-template-columns:1fr auto;gap:4px 16px;padding:14px 12px;border-bottom:1px solid var(--line);cursor:pointer;border-radius:12px}
.np-row:hover,.np-row.sel{background:color-mix(in srgb,var(--navy) 5%,transparent)}
.np-row h3{font:600 1rem var(--f-display);margin:0}
.np-row .m,.np-panel .m{color:var(--muted);font-size:.84rem}
.np-row .v{text-align:right;font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap}
.np-chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.np-chip{font-size:.78rem;border-radius:999px;padding:3px 10px;background:var(--tint-teal);color:var(--teal)}
.np-chip.hot{background:var(--tint-salmon);color:var(--accent-ink)}a.np-chip{text-decoration:none}
.np-more{margin:14px 0 0}
.np-panel{position:sticky;top:80px;max-height:calc(100vh - 96px);overflow:auto;background:var(--surface);border-radius:20px;box-shadow:var(--ui-shadow);padding:20px}
.np-panel h2{font:700 1.15rem var(--f-display);margin:0 0 2px}
.np-panel .np-x{display:none}
.np-kv{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0}
.np-kv div{border-radius:12px;padding:10px;background:var(--sunken)}
.np-kv b{display:block;font:600 1rem var(--f-display);font-variant-numeric:tabular-nums}
.np-kv span{font-size:.75rem;color:var(--muted)}
.np-panel .np-tabs{gap:16px;margin:6px 0 4px}
.np-tie{padding:10px 0;border-top:1px solid var(--line);font-size:.9rem}
.np-face{float:left;width:32px;height:32px;border-radius:50%;object-fit:cover;margin:0 10px 0 0;background:var(--sunken)}
h2 .np-face{width:48px;height:48px;margin-top:-6px}
.np-tie:first-child{border-top:0}
.np-panel dl{display:grid;grid-template-columns:minmax(110px,max-content) 1fr;gap:6px 12px;margin:8px 0;font-size:.9rem}
.np-panel dt{color:var(--muted)}
.np-panel dd{margin:0}
.np-panel table{width:100%;border-collapse:collapse;font-size:.88rem;margin:4px 0 10px}
.np-panel td{padding:7px 0;border-top:1px solid var(--line);vertical-align:top}
.np-panel td.num{text-align:right;white-space:nowrap;padding-left:10px;font-variant-numeric:tabular-nums}
.np-panel details{margin:6px 0}
.np-p{all:unset;cursor:pointer;color:var(--navy);text-decoration:underline;text-underline-offset:2px}
.np-p:focus-visible{outline:2px solid var(--navy);outline-offset:2px;border-radius:4px}
.np-empty{color:var(--muted);padding:24px 6px}
@media (max-width:860px){
  .np-lay{grid-template-columns:minmax(0,1fr)}
  .np-cards{grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
  .np-panel{display:none;position:fixed;inset:0;top:0;max-height:none;border-radius:0;z-index:50;padding:16px 16px 40px}
  .np-panel.open{display:block}
  .np-panel .np-x{display:inline-flex;margin:0 0 10px}
  body.np-lock{overflow:hidden}
}
"""


def nonprofits_page(out_dir):
    open(os.path.join(out_dir, 'assets', 'nonprofits.js'), 'w').write(open(os.path.join(HERE, 'nonprofits.js')).read())
    return f'''<style>{CSS}</style>
<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Connections · Nonprofits</span><h1>Bay County nonprofits</h1>
    <p class="lede" id="npLede">Every local nonprofit, starting with the ones tied to public money and campaigns. Search for any one, or tap a card.</p></div>
    <div class="stamp"><a class="pill" href="/connections">Network</a><a class="pill" href="/connections/shared-owners">Shared owners</a></div></header>
  <div class="np-seg" role="group" aria-label="View"><button type="button" id="npVOrg" aria-pressed="true">Nonprofits</button><button type="button" id="npVPpl" aria-pressed="false">People</button></div>
  <div class="np-cards" id="npCards" aria-live="polite"></div>
  <div class="np-lay"><div>
    <input id="npQ" class="np-q" type="search" placeholder="Search a nonprofit, person, city or EIN" aria-label="Search" autocomplete="off">
    <details class="np-filters" id="npFilters"><summary>More filters</summary><div class="filters-row">
      <select id="npK" aria-label="Type"><option value="">All types</option></select>
      <select id="npC" aria-label="City"><option value="">All cities</option></select>
      <label class="small"><input type="checkbox" id="npHoa"> Include homeowner and condo associations</label>
      <label class="small"><input type="checkbox" id="npFd"> Registered Florida charities only</label></div></details>
    <div class="np-tabs" role="tablist" id="npTabs"></div>
    <div id="npList" aria-live="polite"><p class="np-empty">Loading…</p></div>
    <p class="np-more"><button type="button" class="pill" id="npMore" hidden>Show more</button></p>
  </div>
  <aside class="np-panel" id="npPanel" aria-label="Details"><p class="muted small">Pick a nonprofit or a person to see its connections, board, money and filings.</p></aside></div>
  <section class="tx-sec method"><div class="sec-hd"><h2>Sources and method</h2></div><ul class="plain">
    <li><b>Which organizations.</b> Every organization the IRS recognizes as tax-exempt with an address in Bay County (the IRS Exempt Organizations Business Master File), plus active Florida nonprofit corporations (Sunbiz) whose principal address is in the county. IRS and state records are joined by the EIN the corporation gives the state, then by exact name.</li>
    <li><b>Money.</b> Revenue, expenses and assets come from the latest 990, 990-EZ or 990-PF the organization e-filed (2019 on). Small organizations file a 990-N postcard with no figures, and churches don't have to file. Government payment records are the site's contracts, check registers, tourism agency payments and CRA ledger, matched to the nonprofit by name. Grants are from Schedule I of local nonprofits' returns.</li>
    <li><b>Florida charity registrations.</b> Charities that ask Floridians for donations must register each year with the Florida Department of Agriculture and Consumer Services. The registrations with a Bay County address come from its <a href="https://csapp.fdacs.gov/CSPublicApp/CheckACharity/CheckACharity.aspx" target="_blank" rel="noopener">Check-A-Charity</a> database: status, expiration, the revenue and the program, fundraising and management spending the charity reported, and its professional fundraising firms. Officers, directors and the tax ID (FEIN) come from the registration application each charity uploads; people the application marks as removed or exempt from public records are left out, and scanned applications without readable text are not read yet. Registrations are joined to the IRS and state records by FEIN, then by exact name; those that match neither are listed on their own. Churches and some small charities are exempt from registering, so a missing registration is not by itself a problem.</li>
    <li><b>Board members.</b> 990 and 990-EZ returns list officers, directors, trustees and key employees with their hours and pay; 990-N postcards name a principal officer; the state lists up to six officers; Florida charity registration applications list officers and directors. Names are shown as filed and grouped across boards by last and first name (nicknames such as Bob and Robert count as one), so two people with a common name can be grouped together. "Shares board members" counts other local nonprofits whose latest filings list the same name. Businesses come from Florida corporate filings (Sunbiz officers and registered agents): "name and address" means the person on the nonprofit's own state filing is the same Sunbiz person; "name" means only one Sunbiz person in the county has that name. Campaign gifts are the business's own gifts in Supervisor of Elections reports. An "official" tag means the name was checked by hand against an elected official, department leader or candidate.</li>
    <li><b>Something wrong?</b> <a href="/about#contact">Tell us</a>. The data is at <a href="/api/v1/datasets/nonprofits">/api/v1/datasets/nonprofits</a>, <a href="/api/v1/datasets/nonprofit-board-members">nonprofit-board-members</a>, <a href="/api/v1/datasets/nonprofit-board-businesses">nonprofit-board-businesses</a>, <a href="/api/v1/datasets/nonprofit-payments">nonprofit-payments</a>, <a href="/api/v1/datasets/nonprofit-grants">nonprofit-grants</a>, <a href="/api/v1/datasets/charity-registrations">charity-registrations</a> and <a href="/api/v1/datasets/nonprofit-officials">nonprofit-officials</a>. IRS e-file data comes through the GivingTuesday 990 data lake.</li>
  </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/nonprofits.js" defer></script>'''
