"""'My Address' page for baycounty.me.

Everything is looked up live in the browser from Bay County's public GIS server
(gis.baycountyfl.gov, which allows cross-origin requests). This module only ships
the rates, district stacks and CRA totals the page needs to interpret the results.
"""
import json, os
from collections import defaultdict
from tax_page import build_data, YEARS

HERE = os.path.dirname(os.path.abspath(__file__))

# Property Appraiser tax district code -> DOR district id used by the rate stacks
TAXDIST = {'2': 'Callaway', '02': 'Callaway', '6': 'Lynn Haven', '06': 'Lynn Haven', '8': 'Mexico Beach', '08': 'Mexico Beach',
           '10': 'Parker', '13': 'Panama City Beach', '16': 'Panama City', '20': 'Springfield',
           '31': 'Panama City - Downtown DIB', '55': 'unincorporated', '56': 'unincorporated - beach area'}

# Bay County GIS CRA district names -> CRA agency used on the CRA page
CRA_AGENCY = {
    'Downtown Extension CRA': 'Panama City CRA', 'Downtown N Extension CRA': 'Panama City CRA', 'Downtown North CRA': 'Panama City CRA',
    'St. Andrews CRA': 'Panama City CRA', 'St Andrews CRA - West Expansion Area': 'Panama City CRA',
    'St Andrews CRA - East Expansion Area': 'Panama City CRA', 'Millville CRA': 'Panama City CRA', 'Downtown CRA / DIB': 'Panama City CRA',
    'Front Beach Road CRA': 'Panama City Beach CRA', 'Pier Park CRA': 'Panama City Beach CRA',
    'Lynn Haven CRA': 'Lynn Haven CRA', 'Callaway CRA': 'Callaway CRA', 'Springfield CRA': 'Springfield CRA', 'Parker CRA': 'Parker CRA',
}


NAV_LABEL = {
    'STWR': 'Bay County stormwater fee', 'STWC': 'Bay County stormwater fee (commercial)', 'ALSL1': 'Street lighting assessment', 'BOCA': 'Street lighting assessment',
    'OERR': 'Road improvement assessment', 'PPCD': 'Pier Park area assessment', 'PCF': 'Panama City fire assessment', 'PBF': 'Panama City Beach fire assessment',
    'PBSW': 'Panama City Beach stormwater assessment', 'PBCRA': 'Front Beach Road CRA assessment', 'LN': 'Lynn Haven stormwater assessment',
    'SF': 'Springfield fire assessment', 'LPWH1': 'Community development district assessment', 'SB': 'Special district assessment',
    'PW': 'Lighting district assessment', 'WMH': 'Lighting district assessment', 'TWIN': 'Special district assessment',
}


# Per-parcel lookups (/data/ex, /data/nav) are split into evenly sized files by a hash of the parcel id,
# so each fetch stays small (under ~40KB). address.js has the same function (shardOf); keep them in sync.
SHARDS = {'ex': 96, 'nav': 128}


def shard_key(pid, n):
    h = 0x811c9dc5  # 32-bit FNV-1a
    for c in pid.encode():
        h = ((h ^ c) * 0x01000193) & 0xffffffff
    return f'h{h % n}'


def write_nav(out_dir):
    nav = json.load(open(os.path.join(HERE, '..', 'data', 'fees', 'nav_2025.json')))
    shards = defaultdict(dict)
    for pid, items in nav.items():
        # levy code + dollar amount only; nothing about the owner
        shards[shard_key(pid, SHARDS['nav'])][pid] = [[str(c), float(a)] for c, a in items]
    d = os.path.join(out_dir, 'data', 'nav'); os.makedirs(d, exist_ok=True)
    for k, v in shards.items():
        json.dump(v, open(os.path.join(d, f'{k}.json'), 'w'), separators=(',', ':'))
    return len(shards)


# UI text added to the address hub. es_pages swaps this whole object for i18n/es_address.json "txt".
ADDR_TXT = {
    'website': 'website', 'tally': '{y} yes · {n} no in recorded money votes', 'campaign': 'Campaign money →',
    'ballotH': '2026 ballot', 'ballot': 'See the 2026 races for your area →',
    'whatif': 'Try what-if numbers in the calculator →', 'whatifA3': 'Try your own numbers →',
    'hsH': 'No homestead exemption',
    'hs': "This home has no homestead exemption on the 2026 tax roll. That's normal for a rental or a second home. If you own it and it was your permanent home on January 1, you can apply with the {pa}. Applications are due March 1 for that year's taxes.",
    'pa': 'Bay County Property Appraiser', 'exLink': 'About exemptions →',
    'nearCraH': 'CRA spending within half a mile', 'nearStH': 'Sales tax projects within a mile', 'nearNone': 'None on file nearby.',
    'craTotal': '{n} records · {amt} spent or committed', 'stTotal': '{n} projects', 'more': 'and {n} more', 'source': 'Source',
    'nearNote': "Distances are from the address point. CRA records placed only somewhere in a district, and rows left out of CRA totals, aren't shown; the dollar total counts spent and committed money.",
    'seeCra': 'CRA map and ledger →', 'seeSt': 'Sales tax project map →', 'fail': "Couldn't load right now.",
    'st_completed': 'Completed', 'st_in_progress': 'In progress', 'st_not_started': 'Not started', 'st_unknown': 'Status unknown',
    'cs_Spent': 'Spent', 'cs_Committed': 'Committed', 'cs_Budgeted': 'Budgeted', 'cs_Proposed': 'Proposed',
    'l_page': 'Overview', 'l_contracts': 'Contracts', 'l_meetings': 'Meetings', 'l_budget': 'Budget', 'l_alerts': 'Alerts',
    'l_records': 'Request a record', 'l_michael': 'Hurricane Michael projects',
    'govNote': 'Each link opens the page filtered to that government.',
    'barLabel': 'Estimated property tax split: {parts}',
}


def member_votes():
    """{gov: [[member name as votes.js expects it, yes, no], ...]} from recorded roll calls."""
    from votes_page import gov_of
    d = json.load(open(os.path.join(HERE, '..', 'data', 'votes', 'votes.json')))
    tally = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for v in d['votes']:
        for n, x in (v.get('by_member') or {}).items():
            if x in ('yes', 'no'):
                tally[gov_of(v['body'])][n][x == 'no'] += 1
    return {g: [[n, y, no] for n, (y, no) in sorted(ms.items())] for g, ms in tally.items() if g != 'other'}


def gov_links():
    """What each government's own records pages accept as a filter (see gov_pages.py for the same links)."""
    from govs import GOVS, CRA_NAME
    bud = {g.get('gov') for g in json.load(open(os.path.join(HERE, '..', 'data', 'civic', 'budgets_detail.json'))).get('governments', [])}
    return {g['key']: {'s': g['short'], 'slug': g['slug'], 'c': g.get('contracts'), 'f': (g.get('fema') or [None])[0], 'cra': g.get('cra'), 'b': g['key'] in bud}
            for g in GOVS}, {v: k for k, v in CRA_NAME.items()}


def address_data():
    """Rates, district stacks, CRA totals and links the address lookup needs (also published for the app)."""
    td = build_data()
    L = len(YEARS) - 1
    merged = json.load(open(os.path.join(HERE, '..', 'data', 'merged.json')))
    cra = defaultdict(lambda: {'spent': 0, 'n': 0})
    for p in merged['payments']:
        c = cra[p['cra']]; c['n'] += 1
        if p['count'] and p['amount'] and p['status'] in ('Spent', 'Committed'):
            c['spent'] += p['amount']
    data = {
        'taxdist': TAXDIST, 'craAgency': CRA_AGENCY, 'cra': {k: {'spent': round(v['spent']), 'n': v['n']} for k, v in cra.items()},
        'districts': {d['id']: {'label': d['label'], 'stack': d['stack'], 'total': d['total'][L]} for d in td['districts']},
        'auth': {k: {'n': a['n'], 'g': a['g'], 'school': a['school'], 'm': a['m'][L]} for k, a in td['auth'].items()},
        'groups': td['groups'], 'fy': td['fy'][L], 'second2026': 26411, 'navLabel': NAV_LABEL, 'shards': SHARDS,
    }
    data['govs'], data['craId'] = gov_links()
    data['members'] = member_votes()
    data['elections'] = os.path.exists(os.path.join(HERE, '..', 'data', 'elections', 'candidates_2026.json'))
    return data


def addr_page(out_dir):
    write_nav(out_dir)
    data = address_data()
    js = open(os.path.join(HERE, 'address.js')).read().replace('__ADDR__', json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    js = js.replace('__ADDR_TXT__', json.dumps(ADDR_TXT, ensure_ascii=False, separators=(',', ':')))
    open(os.path.join(out_dir, 'assets', 'address.js'), 'w').write(js)

    def T(tid, text):
        return f'<span class="term" data-term="{tid}">{text}</span>'

    return f'''<div class="page tax addr">
  <header class="tx-top">
    <div class="tx-brand">
      <span class="eyebrow">My Address</span>
      <h1>What applies to your address</h1>
      <p class="lede">Type a Bay County street address to see your property tax estimate, who represents you, your schools, your flood and evacuation zones, and whether you're inside a redevelopment district.</p>
    </div>
  </header>

  <section class="addr-search" role="search">
    <label for="q" class="fld"><span>Street address</span></label>
    <div class="ac">
      <input id="q" type="search" autocomplete="off" spellcheck="false" placeholder="e.g. 825 Ohio Ave" aria-autocomplete="list" aria-controls="acList" aria-expanded="false">
      <ul id="acList" class="ac-list" role="listbox" hidden></ul>
    </div>
    <p class="muted small">Start with the house number. Lookups go straight to Bay County's public map server; BayCounty.me doesn't store what you search.</p>
    <p class="err" id="err" role="alert" hidden></p>
  </section>

  <div id="out" class="addr-out" hidden aria-live="polite">
    <div class="addr-hd">
      <div><h2 id="aTitle"></h2><p class="muted" id="aSub"></p></div>
      <div class="addr-act"><button type="button" class="pdf-btn" id="pdf"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button>
      <a class="pdf-btn" id="paLink" target="_blank" rel="noopener">Property Appraiser record ↗</a></div>
    </div>
    <p class="print-meta" id="printMeta"></p>
    <div class="addr-grid">
      <section class="card a-map"><svg id="map" viewBox="0 0 400 260" role="img" aria-label="Map of the address"></svg><p class="muted small" id="mapCap"></p></section>
      <section class="card" id="cTax"><h3>Property tax estimate</h3><div id="taxBody"></div></section>
      <section class="card" id="cProp"><h3>The property</h3><dl class="kv" id="propBody"></dl></section>
      <section class="card" id="cA3"><h3>If Amendment 3 passes</h3><div id="a3Body"></div></section>
      <section class="card" id="cReps"><h3>Who represents you</h3><dl class="kv" id="repBody"></dl></section>
      <section class="card" id="cSch"><h3>Zoned public schools</h3><dl class="kv" id="schBody"></dl></section>
      <section class="card" id="cCra"><h3>Redevelopment district ({T('cra', 'CRA')})</h3><div id="craBody"></div></section>
      <section class="card" id="cSafe"><h3>Flood, storms and services</h3><dl class="kv" id="safeBody"></dl></section>
      <section class="card" id="cDev"><h3>Zoning and development nearby</h3><div id="devBody"></div></section>
      <section class="card" id="cNear"><h3>Public money near you</h3><div id="nearBody"></div></section>
      <section class="card" id="cGov"><h3>Your government's records</h3><div id="govBody"></div></section>
    </div>
    <p class="note">Owner names are not shown here. They're public at the Property Appraiser's site, linked above. Representative names come from Bay County's GIS and may lag an election.</p>
  </div>

  <section class="tx-sec method" aria-labelledby="src-h">
    <div class="sec-hd"><h2 id="src-h">How this works</h2></div>
    <p>Addresses, parcels, property values and district boundaries come live from <a href="https://gis.baycountyfl.gov/arcgis/rest/services" target="_blank" rel="noopener">Bay County's public GIS server</a>, which publishes the Property Appraiser's parcel data. Property values are the 2026 roll. Flood zones come live from <a href="https://hazards.fema.gov/femaportal/wps/portal/NFHLWMS" target="_blank" rel="noopener">FEMA's National Flood Hazard Layer</a>, the official current flood map, with the FIRM panel and any map revision (LOMR) that applies.</p>
    <p>The tax estimate applies the latest complete set of official rates (tax year 2025, {data['fy']} bills, from the Florida Department of Revenue) to the 2026 values. The rates adopted in September 2026 will replace them when the state publishes the full set. Flat {T('non-ad-valorem', 'non-ad valorem')} fees (fire, stormwater, lighting and similar) come from the Florida Department of Revenue's parcel-level file for the 2025 tax roll, so they show what was on the FY2026 bill. For a homestead, school tax is figured on the value before the second homestead exemption, since that one doesn't apply to schools. Other exemptions are taken as reported by the Property Appraiser. Your official bill comes from the Tax Collector.</p>
  </section>
  <div class="tt" id="tt" role="tooltip" hidden></div>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/address.js" defer></script>'''
