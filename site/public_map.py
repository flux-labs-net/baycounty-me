"""Public money map (/public-money/map): CRA payments, sales tax projects, CRA district boundaries and city limits.

Reuses the Sales Tax Projects map (SVG, same projection, st-* styles) and the data files the CRA and sales tax pages
already publish (/data/cra-geo.json, cra-pay-*.json, surtax-projects.json), so it adds no data of its own.
Hurricane Michael projects have no locations in the FEMA data and are left off.
"""
import json, os, shutil
from city_filter import city_bar, gkey

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')


def public_map_page(out_dir):
    shutil.copy(os.path.join(HERE, 'public_map.js'), os.path.join(out_dir, 'assets', 'public_map.js'))
    ts = json.load(open(os.path.join(DATA, 'tourism', 'tourism_surtax.json')))['infra_surtax']['projects']
    cra = json.load(open(os.path.join(DATA, 'merged.json')))['payments']
    ncra = sum(1 for p in cra if p.get('lat') is not None)
    ntax = sum(1 for p in ts if p.get('lat') is not None)
    # the governments with a mark on the map: CRA records map to their city, tax projects name their government
    gk = {gkey(p.get('cra')) for p in cra if p.get('lat') is not None} | {gkey(p.get('government')) for p in ts if p.get('lat') is not None}
    return f'''<div class="page tax st addr pm">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Public Money · Map</span><h1>Public money on one map</h1>
    <p class="lede">Redevelopment agency (CRA) spending and half-cent sales tax projects across Bay County, with the CRA district lines and city limits. Tap any mark to see the record and where it came from.</p></div></header>
  {city_bar(gk)}
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>What the marks mean</h2>
    <ol class="ex-steps"><li><b>Diamonds are CRA records:</b> money a city's redevelopment agency spent, committed or budgeted inside its districts. Records with no address sit at the middle of their district.</li>
      <li><b>Dots are sales tax projects:</b> roads, bridges, drainage and sidewalks paid for with the infrastructure half-cent, from the county's project map. Road projects sit at the middle of the road segment.</li>
      <li><b>Colors show status.</b> Green is spent or finished, blue is under way, gray is planned. Hurricane Michael projects aren't on the map because the FEMA records don't give locations; they're on the <a href="/public-money/hurricane-michael">Hurricane Michael</a> page.</li></ol></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="map-h">The map</h2><span class="muted" id="pmCount"></span></div>
    <div class="filters-row">
      <input id="pmQ" type="search" placeholder="Search payee, project or street" aria-label="Search the map">
      <select id="pmS" aria-label="Status"><option value="">Any status</option><option value="done">Spent / completed</option><option value="active">Committed / in progress</option><option value="plan">Budgeted, proposed or not started</option></select>
    </div>
    <div class="filters-row small" role="group" aria-label="Layers">
      <label><input type="checkbox" id="pmLCra" checked> CRA records ({ncra})</label>
      <label><input type="checkbox" id="pmLTax" checked> Sales tax projects ({ntax:,})</label>
      <label><input type="checkbox" id="pmLDist" checked> CRA districts</label>
      <label><input type="checkbox" id="pmLCity" checked> City limits</label>
    </div>
    <div class="st-mapcol"><div class="st-mapbox"><svg id="pmMap" viewBox="0 0 400 300" role="img" aria-label="Map of CRA spending and sales tax projects in Bay County. Tap a mark for details." style="width:100%;height:auto;border:1px solid var(--line);border-radius:12px;background:var(--water)"></svg>
      <div class="st-zoom print-hide"><button type="button" id="pmIn" aria-label="Zoom in">+</button><button type="button" id="pmOut" aria-label="Zoom out">−</button><button type="button" id="pmAll" class="st-all">Show all</button></div></div>
      <div class="st-sel" id="pmSel" hidden aria-live="polite"></div></div>
    <ul class="leg mini" id="pmLeg"></ul>
    <p class="note">CRA records come from the <a href="/public-money/cra-spending">CRA Spending</a> ledger, and district lines from Bay County GIS (including the 2025 St. Andrews expansion areas). Projects come from the county's sales tax project map on the <a href="/public-money/sales-tax-projects">Sales Tax Projects</a> page; where a project matches a line in the county's program schedule, its programmed dollars are shown. City limits are from the U.S. Census Bureau.</p></section>
  <div class="tt" id="tt" role="tooltip" hidden></div>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<style>/* CRA colors, the same values as the CRA Spending page */
.pm{{--c-pc:#3F6FB0;--c-pcb:#E5564A;--c-lh:#D18A1E;--c-cw:#22897C;--c-sf:#7B5FBF;--c-pk:#2F95C4}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]) .pm{{--c-pc:#7FA6DA;--c-pcb:#FF8C82;--c-lh:#FFB84D;--c-cw:#4CC2B2;--c-sf:#A891E0;--c-pk:#7CC7E4}}}}
:root[data-theme="dark"] .pm{{--c-pc:#7FA6DA;--c-pcb:#FF8C82;--c-lh:#FFB84D;--c-cw:#4CC2B2;--c-sf:#A891E0;--c-pk:#7CC7E4}}
#pmMap [data-i]{{cursor:pointer}}</style>
<script src="/assets/public_map.js" defer></script>'''
