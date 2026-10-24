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
.so-biz{width:100%;border-collapse:collapse;font-size:.92rem}
.so-biz td{padding:7px 0;border-top:1px solid var(--line);vertical-align:top}
.so-biz td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;padding-left:12px}
.so-biz small{color:var(--muted);display:block}
"""


def shared_owners_page(out_dir):
    open(os.path.join(out_dir, 'assets', 'shared_owners.js'), 'w').write(open(os.path.join(HERE, 'shared_owners.js')).read())
    return f'''<style>{CSS}</style>
<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Connections · Shared owners</span><h1>One owner, several checks</h1>
    <p class="lede">Groups of businesses that list the same officer, manager or registered agent in state corporate records and each gave to the same local candidate. Each group was checked by hand against the state's records before it was listed here.</p></div></header>
  <section class="tx-sec">
    <div class="filters-row"><select id="soC" aria-label="Candidate"><option value="">All candidates</option></select></div>
    <p class="muted small" id="soCount" aria-live="polite" style="margin:10px 0 0"></p>
    <div id="soList" class="so-list"><p class="muted">Loading…</p></div>
  </section>
  <section class="tx-sec method"><div class="sec-hd"><h2>About this list</h2></div><ul class="plain">
    <li><b>This is legal.</b> Under Florida law each corporation or LLC is its own contributor with its own limit ($1,000 per election for local offices), so one owner's companies can each give. Giving in someone else's name is what the law forbids (s. 106.08(5), F.S.). A group here is a pattern in public records, not a finding of wrongdoing.</li>
    <li><b>How businesses are linked.</b> Business contributors in the Supervisor of Elections reports are matched to the Florida Division of Corporations (Sunbiz) file. Businesses are grouped when they list the same person as an officer, manager or registered agent, matched by name and address. Corporate officers on 25 or more companies and registered-agent services are left out.</li>
    <li><b>People aren't named.</b> BayCounty.me doesn't name individual donors. Each business links to its public Sunbiz record.</li>
    <li><b>Something wrong?</b> If a business is grouped by mistake, <a href="/about#contact">tell us</a> and we'll correct it. The data is also at <a href="/api/v1/datasets/shared-owner-groups">/api/v1/datasets/shared-owner-groups</a>.</li>
  </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/shared_owners.js" defer></script>'''
