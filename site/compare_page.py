"""Compare Bay County governments side by side (/compare)."""
import json, os
from govs import all_profiles

HERE = os.path.dirname(os.path.abspath(__file__))


def compare_data():
    rows = []
    for p in all_profiles():
        b, d, v = p.get('budget') or {}, p.get('debt') or {}, p.get('votes') or {}
        au = (p.get('audits') or [{}])[0]
        rows.append({
            'k': p['key'], 'n': p['short'], 'kind': p['kind'], 'slug': p['slug'], 'pop': p.get('population'),
            'budget': b.get('total'), 'gf': b.get('general_fund'), 'mills': b.get('mills'), 'levy': b.get('levy'),
            'debt': d.get('total'), 'debt_fy': (d.get('fy') or '')[:6],
            'findings': len(au.get('findings') or []) if au else None, 'repeats': sum(1 for f in au.get('findings') or [] if f.get('repeat')) if au else None, 'audit_fy': au.get('fy'),
            'votes': v.get('n'), 'split': v.get('split'),
            'bill': (p.get('utility_bill') or {}).get('total'),
            'fema': (p.get('fema') or {}).get('federal_obligated'),
            'cra': (p.get('cra') or {}).get('spent'),
            'emp': (p.get('officials') or {}).get('employees'),
            'contracts': (p.get('contracts') or {}).get('total'), 'ncontracts': (p.get('contracts') or {}).get('n'),
            'status': b.get('status'),
        })
    return rows


def compare_page(out_dir):
    js = open(os.path.join(HERE, 'compare.js')).read().replace('__CMP__', json.dumps(compare_data(), separators=(',', ':')))
    open(os.path.join(out_dir, 'assets', 'compare.js'), 'w').write(js)
    return '''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Governments · Compare</span><h1>Compare governments</h1>
    <p class="lede">Pick the governments you want to see side by side. Bigger places spend and owe more, so most measures can also be shown per resident.</p></div>
    <div class="stamp"><button type="button" class="pdf-btn" id="pdf"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>Data updated Oct 21, 2026</span></div></header>
  <section class="cmp-pick print-hide" aria-label="Choose governments">
    <div class="chips" id="cmpChips" role="group" aria-label="Governments to compare"></div>
    <div class="cmp-opts"><button type="button" class="linkbtn" data-set="cities">All cities</button><button type="button" class="linkbtn" data-set="all">Everything</button><button type="button" class="linkbtn" data-set="none">Clear</button>
      <label class="chk"><input type="checkbox" id="cmpPer" checked> Per resident where it applies</label></div>
  </section>
  <p class="print-meta" id="printMeta"></p>
  <div class="cmp-grid" id="cmpGrid"></div>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="notes">Reading the comparison</h2></div>
    <ul class="plain">
      <li><b>Different jobs.</b> The county serves everyone and runs countywide services; the school district runs schools; cities provide police, fire, water and other services that differ from city to city. Compare cities with cities.</li>
      <li><b>Visitors and second homes count too.</b> Panama City Beach and Mexico Beach serve far more people than live there, and much of their property is owned by non-residents, so their per-resident figures run high.</li>
      <li><b>Residents</b> are the State of Florida's 2025 population estimates. Budgets are the latest adopted budget on file; debt and audit findings are from the latest audited year. Each government's page links to every source.</li>
      <li><b>Panama City Beach</b> levies no city property tax; its revenue comes mostly from sales, tourist and utility taxes, fees and its CRA.</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/compare.js" defer></script>'''
