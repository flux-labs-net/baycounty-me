"""Shared-owner campaign gifts (/connections/shared-owners): businesses that share an officer, manager or registered
agent and gave to the same candidate.

The page holds no data. assets/shared_owners.js reads /api/v1/datasets/shared-owner-groups, which lists only groups an
admin confirmed in /admin (Business owners tab). People are never named, only counted.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

CSS = r"""
.so-list{display:flex;flex-direction:column;gap:14px;margin-top:12px}
.so-c{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px}
.so-c h3{font:600 1.05rem var(--f-display);margin:0 0 2px}
.so-meta{color:var(--muted);font-size:.86rem;margin-bottom:10px}
.so-total{font:600 1.4rem var(--f-display);font-variant-numeric:tabular-nums}
.so-tags{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0 10px}
.so-tag{font-size:.78rem;border:1px solid var(--line);border-radius:999px;padding:1px 8px;color:var(--muted)}
.so-sum{margin:2px 0 10px;font-size:.9rem;color:var(--muted)}
.so-grp{border-top:1px solid var(--line);padding-top:10px;margin-top:12px}
.so-grp:first-of-type{border-top:0;margin-top:0;padding-top:0}
.so-gh{display:flex;justify-content:space-between;gap:10px;font:600 .95rem var(--f-display);margin-bottom:4px}
.so-gh span{font-variant-numeric:tabular-nums}
.so-biz{width:100%;border-collapse:collapse;font-size:.92rem}
.so-biz td{padding:7px 0;border-top:1px solid var(--line);vertical-align:top}
.so-biz td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;padding-left:12px}
.so-biz small{color:var(--muted);display:block}
.ol-c{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.ol-c h3{font:600 1rem var(--f-display);margin:0 0 2px}
.ol-st{display:inline-block;font-size:.76rem;font-weight:600;border-radius:999px;padding:1px 9px;margin-left:6px;vertical-align:2px}
.ol-st.open{color:#b45309;border:1px solid currentColor}
.ol-st.res{color:#15803d;border:1px solid currentColor}
.ol-res{margin:10px 0 0;padding:10px 12px;border-radius:10px;background:var(--bg);font-size:.9rem}
.so-years{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.so-yr{display:flex;flex-direction:column;align-items:flex-start;gap:1px;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:8px 12px;color:var(--ink);cursor:pointer;font:inherit;min-width:96px}
.so-yr:hover{border-color:var(--muted)}
.so-yr b{font:600 .95rem var(--f-display)}.so-yr span{font-variant-numeric:tabular-nums}.so-yr small{color:var(--muted);font-size:.76rem}
"""


def shared_owners_page(out_dir):
    open(os.path.join(out_dir, 'assets', 'shared_owners.js'), 'w').write(open(os.path.join(HERE, 'shared_owners.js')).read())
    return f'''<style>{CSS}</style>
<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Connections · Shared owners</span><h1>One owner, several checks</h1>
    <p class="lede">Groups of businesses that list the same officer, manager or registered agent in state corporate records and each gave to the same local candidate. Each group was checked by hand against the state's records before it was listed here.</p></div></header>
  <section class="tx-sec">
    <div class="filters-row"><select id="soY" aria-label="Election year"><option value="">All elections</option></select> <select id="soC" aria-label="Candidate"><option value="">All candidates</option></select></div>
    <div id="soYears" class="so-years" aria-label="Totals by election year"></div>
    <p class="muted small" id="soCount" aria-live="polite" style="margin:10px 0 0"></p>
    <div id="soList" class="so-list"><p class="muted">Loading…</p></div>
  </section>
  <section class="tx-sec" id="over-limit"><div class="sec-hd"><h2>Gifts over the $1,000 limit</h2><span class="muted">One organization, one candidate, one election</span></div>
    <p class="small muted" style="margin:0">Florida limits each contributor to $1,000 per election for a local candidate (s. 106.08, F.S.); the primary and the general each count as their own election. These are cases where a campaign's own reports show more than that from one organization, net of refunds. Each was checked by hand. <b>Open</b> means no explanation has been found yet. <b>Resolved</b> means it was explained (for example a reporting error, an amended report, a refund, a check meant for the general election, or an Elections Commission ruling), and the explanation is shown.</p>
    <div id="olList" class="so-list"><p class="muted">Loading…</p></div>
  </section>
  <section class="tx-sec method"><div class="sec-hd"><h2>About this list</h2></div><ul class="plain">
    <li><b>This is legal.</b> Under Florida law each corporation or LLC is its own contributor with its own limit ($1,000 per election for local offices), so one owner's companies can each give. Giving in someone else's name is what the law forbids (s. 106.08(5), F.S.). A group here is a pattern in public records, not a finding of wrongdoing.</li>
    <li><b>How businesses are linked.</b> Business contributors in the Supervisor of Elections reports are matched to the Florida Division of Corporations (Sunbiz) file. Businesses are grouped when they list the same person as an officer, manager or registered agent, matched by name and address. Corporate officers on 25 or more companies and registered-agent services are left out.</li>
    <li><b>Years.</b> Groups are listed by the election the checks were for, newest first. Candidates often raise money a year or more ahead, so checks for a 2024 race can be dated 2023; each card says when its checks were written.</li>
    <li><b>Inactive businesses are flagged.</b> A business marked <span class="biz-off" style="cursor:auto">Inactive</span> is dissolved, revoked or no longer filing annual reports with the state; "since" is the last year it filed. Its gift was made while it was still filing.</li>
    <li><b>Over the limit.</b> A reported overage is not a finding of wrongdoing. Reports can contain typing errors, a check written before the primary can be meant for the general election, and a campaign fixes an overage by refunding it. Only the Florida Elections Commission decides whether the law was broken. Data: <a href="/api/v1/datasets/over-limit-gifts">/api/v1/datasets/over-limit-gifts</a>.</li>
    <li><b>People aren't named.</b> BayCounty.me doesn't name individual donors. Each business links to its public Sunbiz record.</li>
    <li><b>Something wrong?</b> If a business is grouped by mistake, <a href="/about#contact">tell us</a> and we'll correct it. The data is also at <a href="/api/v1/datasets/shared-owner-groups">/api/v1/datasets/shared-owner-groups</a>.</li>
  </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/shared_owners.js" defer></script>'''
