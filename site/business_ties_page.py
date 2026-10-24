"""Officials' business ties (/connections/business-ties): registered businesses that list an elected official,
department leader or local candidate, and how those businesses connect to campaigns and public money.

The page holds no data. assets/business_ties.js reads /api/v1/datasets/official-businesses and
/api/v1/datasets/official-business-links, which list only matches an admin confirmed in /admin (Business ties tab).
Only officials and candidates are named; anyone else on a business is counted, never named.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

CSS = r"""
.bt-list{display:flex;flex-direction:column;gap:14px;margin-top:12px}
.bt-c{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px}
.bt-c h3{font:600 1.05rem var(--f-display);margin:0 0 2px}
.bt-meta{color:var(--muted);font-size:.86rem;margin-bottom:10px}
.bt-row{display:grid;grid-template-columns:minmax(0,1fr) minmax(120px,38%);gap:12px;padding:8px 0;border-top:1px solid var(--line);font-size:.92rem;align-items:center}
.bt-row small{color:var(--muted);display:block}
.bt-track{position:relative;height:10px;border-radius:999px;background:color-mix(in srgb,var(--line) 60%,transparent)}
.bt-bar{position:absolute;top:0;bottom:0;border-radius:999px;background:var(--accent,#2563eb)}
.bt-bar.off{background:var(--muted);opacity:.55}
.bt-axis{display:flex;justify-content:space-between;color:var(--muted);font-size:.72rem;margin:2px 0 0 auto;width:38%}
.bt-links{margin:12px 0 0;padding:0;list-style:none;font-size:.9rem}
.bt-links li{padding:6px 0;border-top:1px dashed var(--line)}
.bt-tag{font-size:.74rem;border:1px solid var(--line);border-radius:999px;padding:1px 8px;color:var(--muted);margin-right:6px;white-space:nowrap}
.bt-tag.hot{border-color:var(--accent,#2563eb);color:var(--accent,#2563eb)}
@media (max-width:560px){.bt-row{grid-template-columns:1fr}.bt-axis{width:100%}}
"""


def business_ties_page(out_dir):
    open(os.path.join(out_dir, 'assets', 'business_ties.js'), 'w').write(open(os.path.join(HERE, 'business_ties.js')).read())
    return f'''<style>{CSS}</style>
<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Connections · Business ties</span><h1>Officials' businesses</h1>
    <p class="lede">The registered businesses and nonprofits that list a Bay County official, department leader or candidate as an officer, manager or registered agent, and where those businesses meet campaigns and public money. Each match was checked by hand against state corporate records.</p></div></header>
  <section class="tx-sec">
    <div class="filters-row"><input id="btQ" type="search" placeholder="Search a name or business" aria-label="Search">
      <select id="btT" aria-label="Show"><option value="">Everyone</option><option value="links">Only people with links</option></select></div>
    <p class="muted small" id="btCount" aria-live="polite" style="margin:10px 0 0"></p>
    <div id="btList" class="bt-list"><p class="muted">Loading…</p></div>
  </section>
  <section class="tx-sec method"><div class="sec-hd"><h2>About this list</h2></div><ul class="plain">
    <li><b>Where it comes from.</b> The Florida Division of Corporations (Sunbiz) quarterly file lists each company's officers, managers and registered agent. Officials are matched by name, then each match is checked by hand (address, middle initial, the business itself) before it is listed.</li>
    <li><b>The bars.</b> Each bar runs from the year the business was filed to today, or to its last filing (usually the dissolution) if it has closed. Sunbiz shows only current officers, so a bar says when the business existed, not exactly when the official joined it. From late 2026 on, BayCounty.me records when each officer first and last appears.</li>
    <li><b>Links.</b> Two officials on the same business; an official's business giving to a campaign; a business that gave to a candidate and shares an officer with that candidate's own business (the shared person is counted, not named); and an official's business paid by a local government. A link is a fact in public records, not a finding of wrongdoing. Many are civic nonprofits that officials serve on as part of the job.</li>
    <li><b>Only officials and candidates are named.</b> Other people on these businesses are never listed.</li>
    <li><b>Something wrong?</b> <a href="/about#contact">Tell us</a> and we'll correct it. The data is also at <a href="/api/v1/datasets/official-businesses">/api/v1/datasets/official-businesses</a> and <a href="/api/v1/datasets/official-business-links">/api/v1/datasets/official-business-links</a>.</li>
  </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/business_ties.js" defer></script>'''
