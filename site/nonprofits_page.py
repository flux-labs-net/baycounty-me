"""Nonprofits (/connections/nonprofits): every nonprofit in the county, what it reports to the IRS, the government
money and grants that reach it, and officials who sit on its board.

The page holds no data. assets/nonprofits.js reads /api/v1/datasets/nonprofits, nonprofit-board-members,
nonprofit-payments, nonprofit-grants and nonprofit-officials. Board members are public records (IRS returns and state
filings); officials are tagged only when an admin confirmed the name match in /admin (Nonprofit boards tab).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

CSS = r"""
.np-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:14px 0}
.np-kpi{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px}
.np-kpi b{display:block;font:600 1.45rem var(--f-display);font-variant-numeric:tabular-nums}
.np-kpi span{color:var(--muted);font-size:.84rem}
.np-off{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px;margin-top:10px}
.np-off article{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px}
.np-off h3{font:600 1rem var(--f-display);margin:0}
.np-off .m{color:var(--muted);font-size:.84rem;margin:2px 0 8px}
.np-off ul{list-style:none;padding:0;margin:0}
.np-off li{font-size:.9rem;margin:4px 0}
.np-off>p{grid-column:1/-1}
.np-list{margin-top:10px}
.np-row{border-top:1px solid var(--line)}
.np-row>button{all:unset;box-sizing:border-box;cursor:pointer;display:grid;grid-template-columns:1fr auto;gap:4px 14px;width:100%;padding:12px 4px}
.np-row>button:focus-visible{outline:2px solid var(--navy);outline-offset:2px;border-radius:8px}
.np-row h3{font:600 .98rem var(--f-display);margin:0}
.np-row .m{color:var(--muted);font-size:.82rem}
.np-row .v{text-align:right;font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}
.np-tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:4px}
.np-tag{font-size:.74rem;border:1px solid var(--line);border-radius:999px;padding:1px 8px;color:var(--muted)}
.np-tag.hot{border-color:var(--salmon);color:var(--salmon)}
.np-d{padding:0 4px 16px;font-size:.92rem}
.np-d dl{display:grid;grid-template-columns:minmax(120px,max-content) 1fr;gap:4px 14px;margin:0 0 10px}
.np-d dt{color:var(--muted)}
.np-d dd{margin:0}
.np-d table{width:100%;border-collapse:collapse;font-size:.88rem;margin:6px 0 10px}
.np-d td{padding:6px 0;border-top:1px solid var(--line);vertical-align:top}
.np-d td.num{text-align:right;white-space:nowrap;padding-left:10px;font-variant-numeric:tabular-nums}
.np-more{margin:14px 0 0}
.np-p{all:unset;cursor:pointer;color:var(--navy);text-decoration:underline;text-underline-offset:2px}
.np-p:focus-visible{outline:2px solid var(--navy);outline-offset:2px;border-radius:4px}
.np-pp{background:var(--ground,transparent);border:1px solid var(--line);border-radius:10px;padding:8px 10px;margin:6px 0;line-height:1.6}
.np-ppr td{white-space:normal}
.np-d details{margin:0 0 10px}
@media (max-width:600px){.np-row>button{grid-template-columns:1fr}.np-row .v{text-align:left}}
"""


def nonprofits_page(out_dir):
    open(os.path.join(out_dir, 'assets', 'nonprofits.js'), 'w').write(open(os.path.join(HERE, 'nonprofits.js')).read())
    return f'''<style>{CSS}</style>
<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Connections · Nonprofits</span><h1>Every nonprofit in Bay County</h1>
    <p class="lede">Charities, foundations, churches, clubs and homeowner associations: what each one reports to the IRS, who sits on its board, the government money and grants that reach it, and the people who sit on several boards at once.</p></div>
    <div class="stamp"><a class="pill" href="/connections">Network</a><a class="pill" href="/connections/shared-owners">Shared owners</a></div></header>
  <div class="np-kpis" id="npKpis" aria-live="polite"></div>
  <section class="tx-sec"><div class="sec-hd"><h2>Officials on nonprofit boards</h2></div>
    <p class="muted small" style="margin:0">Elected officials, department leaders and candidates listed as an officer or director in a nonprofit's IRS returns or state filings. Each was matched by name and checked by hand. Serving on a board is common and legal; it matters when that nonprofit receives public money or comes before the official's board.</p>
    <div id="npOff" class="np-off"><p class="muted">Loading…</p></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2>People on several boards</h2></div>
    <p class="muted small" style="margin:0">Names listed on the latest filings of two or more local nonprofits (homeowner associations aside). Tap a name to see every board it appears on. People are matched by name, so check the filing before drawing conclusions.</p>
    <div id="npMulti" class="np-off"><p class="muted">Loading…</p></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2>Board members whose businesses gave to campaigns</h2></div>
    <p class="muted small" style="margin:0">Nonprofit board members who are officers or registered agents of a business (Florida corporate filings) that gave to a local campaign. Tap a name to see every board it appears on.</p>
    <div id="npDon" class="np-off"><p class="muted">Loading…</p></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2>Find a nonprofit</h2></div>
    <div class="filters-row">
      <input id="npQ" type="search" placeholder="Name, city or EIN" aria-label="Search nonprofits" autocomplete="off">
      <select id="npK" aria-label="Type"><option value="">All types</option></select>
      <select id="npC" aria-label="City"><option value="">All cities</option></select>
      <select id="npS" aria-label="Sort"><option value="rev">Largest revenue</option><option value="gov">Most government money</option><option value="board">Shared board members</option><option value="name">Name</option></select>
    </div>
    <div class="filters-row" style="margin-top:8px"><label class="small"><input type="checkbox" id="npHoa"> Include homeowner and condo associations</label>
      <label class="small"><input type="checkbox" id="npGov"> Only those paid by a government</label></div>
    <p class="muted small" id="npCount" aria-live="polite" style="margin:10px 0 0"></p>
    <div id="npList" class="np-list"><p class="muted">Loading…</p></div>
    <p class="np-more"><button type="button" class="pill" id="npMore" hidden>Show more</button></p>
  </section>
  <section class="tx-sec method"><div class="sec-hd"><h2>Sources and method</h2></div><ul class="plain">
    <li><b>Which organizations.</b> Every organization the IRS recognizes as tax-exempt with an address in Bay County (the IRS Exempt Organizations Business Master File), plus active Florida nonprofit corporations (Sunbiz) whose principal address is in the county. IRS and state records are joined by the EIN the corporation gives the state, then by exact name.</li>
    <li><b>Money.</b> Revenue, expenses and assets come from the latest 990, 990-EZ or 990-PF the organization e-filed (2019 on). Small organizations file a 990-N postcard with no figures, and churches don't have to file. Government payment records are the site's contracts, check registers, tourism agency payments and CRA ledger, matched to the nonprofit by name. Grants are from Schedule I of local nonprofits' returns.</li>
    <li><b>Board members.</b> 990 and 990-EZ returns list officers, directors, trustees and key employees with their hours and pay; 990-N postcards name a principal officer; the state lists up to six officers. Names are shown as filed and grouped across boards by last and first name (nicknames such as Bob and Robert count as one), so two people with a common name can be grouped together. "Shares board members" counts other local nonprofits whose latest filings list the same name. Businesses come from Florida corporate filings (Sunbiz officers and registered agents): "name and address" means the person on the nonprofit's own state filing is the same Sunbiz person; "name" means only one Sunbiz person in the county has that name. Campaign gifts are the business's own gifts in Supervisor of Elections reports. An "official" tag means the name was checked by hand against an elected official, department leader or candidate.</li>
    <li><b>Something wrong?</b> <a href="/about#contact">Tell us</a>. The data is at <a href="/api/v1/datasets/nonprofits">/api/v1/datasets/nonprofits</a>, <a href="/api/v1/datasets/nonprofit-board-members">nonprofit-board-members</a>, <a href="/api/v1/datasets/nonprofit-board-businesses">nonprofit-board-businesses</a>, <a href="/api/v1/datasets/nonprofit-payments">nonprofit-payments</a>, <a href="/api/v1/datasets/nonprofit-grants">nonprofit-grants</a> and <a href="/api/v1/datasets/nonprofit-officials">nonprofit-officials</a>. IRS e-file data comes through the GivingTuesday 990 data lake.</li>
  </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/nonprofits.js" defer></script>'''
