"""CRA network (/public-money/cra-network): who each redevelopment agency (CRA) paid, how those payees connect, and
business campaign gifts to the officials who sit as each CRA's board.

Built at site-build time from data/merged.json (the CRA ledger), data/entities (vendor ids), data/campaign/campaign.json
(gifts to current officeholders) and data/campaign/vendor_matches.json (donors resolved to CRA ledger records).
Individual donors are never shown. Unnamed recipients of grant programs (homeowners, small businesses) are grouped,
never listed, and private home addresses are not shown.
"""
import json, os, re, shutil, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
sys.path.insert(0, os.path.join(DATA, 'entities'))
import ids  # noqa: E402

CRA_CODE = {'Panama City CRA': 'PC', 'Panama City Beach CRA': 'PCB', 'Lynn Haven CRA': 'LH',
            'Callaway CRA': 'CW', 'Springfield CRA': 'SF', 'Parker CRA': 'PK'}
CRA_GOV = {'PC': 'pc', 'PCB': 'pcb', 'LH': 'lh', 'CW': 'cw', 'SF': 'sp', 'PK': 'parker'}
# the city commission or council sits as each CRA's board
BOARD_PREFIX = [('Panama City Beach', 'PCB'), ('Panama City', 'PC'), ('Lynn Haven', 'LH'), ('Callaway', 'CW'),
                ('Springfield', 'SF'), ('Parker', 'PK')]
UNNAMED = re.compile(r'not (named|stated)|^various\b|^seller|^contractors?\b|^vendor|^not applicable|^grant recipient', re.I)
GROUPED = re.compile(r'homeowner|property owners|residential|businesses|^local business|applicants|business owners|\(program\)', re.I)
GOVLIKE = re.compile(r'^(city of |.*police department|pier park community development|downtown improvement board|bondholders)', re.I)
# documented links between payees that aren't payments (shared project, address or subcontract), each with its source
RELATED = [
    ('v:dewberry', 'v:cwr-contracting', 'Dewberry is engineer of record on CWR\'s Segment 3 change order (Res. 23-195)',
     'https://d3n9y02raazwpg.cloudfront.net/pcbgov/0d86e393-7c8e-11ed-9024-0050569183fa-b95fcb69-f19b-4652-8495-9f0a506dc971-1688747339.pdf'),
    ('v:gac-contractors', 'v:cwr-contracting', 'Both hold Front Beach Road Segment 3 contract records: GAC\'s low bid (Res. 21-127) and CWR\'s final payment',
     'https://www.pcbfl.gov/home/showpublisheddocument/27668/638887882812000000'),
    ('v:pbs-j', 'v:dewberry', 'Both designed SR 79 / Segment 3 work: PBS&J\'s final design, then Dewberry\'s construction administration',
     'https://pcbfl.gov/home/showpublisheddocument/262/635288586904330000'),
    ('v:dewberry', 's:southern-earth-sciences', 'Southern Earth Sciences is a subconsultant on Dewberry\'s Segment 4.1 and 4.2 task orders',
     'https://pcbfl.gov/home/showpublisheddocument/13909/636870324888970000'),
    ('v:volkert', 's:southern-earth-sciences', 'Southern Earth Sciences is a subconsultant on Volkert\'s Segment 4.3 design',
     'https://pcbfl.gov/home/showpublisheddocument/18302/637617846736370000'),
    ('v:dewberry', 's:gortemoller-engineering', 'Gortemoller Engineering is a subconsultant on Dewberry\'s Segment 4.1 and 4.2 task orders',
     'https://pcbfl.gov/home/showpublisheddocument/16673/637266931768470000'),
    ('v:acorns-to-oaks-academy', 'o:owner-of-401-e-6th-st', 'Same address, 401 E 6th St: a commercial grant and a TIF rebate award',
     'https://www.panamacity.gov/DocumentCenter/View/10977'),
]
SUBS = {'s:southern-earth-sciences': 'Southern Earth Sciences', 's:gortemoller-engineering': 'Gortemoller Engineering'}


def _slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def _strip(s):
    return re.sub(r'\s*\(.*?\)\s*', ' ', s).strip(' ,;')


def _norm(s):
    s = re.sub(r"[.,'&]", '', (s or '').lower())
    return ' '.join(w for w in s.split() if w not in ('inc', 'llc', 'co', 'corp', 'company', 'the', 'pa', 'pllc'))


def _entity(p, code, V):
    """(key, name, kind) for a ledger payee. kind: biz | gov | prop | unnamed | grants"""
    name = p.get('payee') or ''
    for vid in ids.vendor_ids(name):
        if vid in V:
            return 'v:' + vid, V[vid]['name'], 'biz'
    m = re.match(r'^Owners? of ([^(]+)', name)
    if m and not re.search(r'homeowner', name, re.I):
        n = ('Owners of ' if name.startswith('Owners') else 'Owner of ') + m.group(1).strip().rstrip(';,')
        return 'o:' + _slug(n), n, 'prop'
    if re.search(r'^property owners / sellers', name, re.I):
        return 'u:sellers-' + code, 'Right-of-way sellers (various)', 'prop'
    if GOVLIKE.match(name) or ids.gov_id(name):
        n = _strip(name)
        n = re.sub(r'\s*/\s*CRA staff$| General Fund$', '', n)
        return 'g:' + _slug(n), n, 'gov'
    if GROUPED.search(name) or (UNNAMED.search(name) and p.get('category') in ('Grant to business', 'Housing')):
        return 'u:grants-' + code, 'Grant recipients, not named', 'grants'
    if UNNAMED.search(name):
        return 'u:none-' + code, 'Payee not named', 'unnamed'
    n = _strip(name)
    return 'b:' + _slug(n), n, 'biz'


def network_data():
    M = json.load(open(os.path.join(DATA, 'merged.json')))
    V = {v['id']: v for v in json.load(open(os.path.join(DATA, 'entities', 'vendors.json')))['vendors']}
    camp = json.load(open(os.path.join(DATA, 'campaign', 'campaign.json')))
    vm = json.load(open(os.path.join(DATA, 'campaign', 'vendor_matches.json')))
    try:
        from vendor_pages import build as _vb
        pages = set(_vb())
    except Exception:
        pages = set()
    cras = {}
    for c in M['cras']:
        code = CRA_CODE.get(c['cra'])
        if code:
            cras[code] = {'n': c['cra'], 'city': c.get('city')}
    ents, recs = {}, []
    for i, p in enumerate(M['payments']):
        code = CRA_CODE.get(p['cra'])
        if not code:
            continue
        if p.get('count') is False and p.get('overlap') and str(p.get('overlap')).startswith('Total of'):
            continue  # an aggregate of rows listed separately
        key, name, kind = _entity(p, code, V)
        e = ents.setdefault(key, {'n': name, 'k': kind})
        if key.startswith('v:') and key[2:] in pages:
            e['vp'] = key[2:]
        recs.append({'i': i, 'c': code, 'd': p.get('district') or '', 'a': p.get('amount'), 'e': key,
                     'w': p.get('purpose') or '', 't': p.get('category') or '', 'when': p.get('date_or_fy') or '',
                     's': p.get('status') or '', 'k': bool(p.get('count')), 'lat': p.get('lat'), 'lng': p.get('lng'),
                     'u': p.get('source_url'), 'nt': (p.get('notes') or '')[:400], 'ov': p.get('overlap') or ''})
    rel = []
    for a, b, t, u in RELATED:
        for k in (a, b):
            if k in SUBS:
                ents.setdefault(k, {'n': SUBS[k], 'k': 'biz', 'sub': True})
        if a in ents and b in ents:
            rel.append({'a': a, 'b': b, 't': t, 'u': u})
    # donors resolved to CRA ledger records by the site's vendor matching
    rec_ent = {r['i']: r['e'] for r in recs}
    donor_ent = {}
    for m in vm['matches']:
        for rid in m.get('record_ids') or []:
            if rid.startswith('cra:') and int(rid[4:]) in rec_ent:
                donor_ent[_norm(m['contributor'])] = (rec_ent[int(rid[4:])], m.get('match_confidence'))
    board = lambda off: next((b for pre, b in BOARD_PREFIX if (off or '').startswith(pre)), '')
    agg = {}

    def put(name, typ, who, off, b, amt, date, url):
        k = _norm(name)
        ent, conf = donor_ent.get(k, (None, None))
        o = agg.setdefault((k, who), {'dn': name, 'ty': typ, 'o': who, 'off': off, 'b': b, 'a': 0.0, 'n': 0, 'ds': [],
                                      'u': url, 'e': ent, 'cf': conf})
        o['a'] += amt or 0
        o['n'] += 1
        if date:
            o['ds'].append(date)
    for c in camp['candidates']:
        b = board(c.get('office'))
        for x in c.get('contributors') or []:
            if x.get('type') not in ('business', 'pac'):
                continue
            if b or _norm(x['name']) in donor_ent:
                put(x['name'], x['type'], c['official'], c.get('office'), b, x.get('amount'), x.get('date'), c.get('report_url'))
    for m in vm['matches']:  # 2026 candidates who are not yet officeholders
        k = _norm(m['contributor'])
        if k in donor_ent and (m.get('gift_source') or '').startswith('2026') and (k, m['candidate']) not in agg:
            put(m['contributor'], 'business', m['candidate'], (m.get('office') or '') + ' (2026 candidate)', board(m.get('office')),
                m.get('contribution_amount'), (m.get('contribution_dates') or [None])[0], m.get('campaign_report_url'))
    don = []
    for o in agg.values():
        ds = sorted(o.pop('ds'))
        o['date'] = (ds[0] + (' to ' + ds[-1] if ds[-1] != ds[0] else '')) if ds else ''
        o['a'] = round(o['a'], 2)
        don.append(o)
    don.sort(key=lambda o: (-(o['e'] is not None), -o['a']))
    return {'cras': cras, 'ents': ents, 'recs': recs, 'rel': rel, 'don': don, 'as_of': camp.get('as_of')}


def cra_network_page(out_dir):
    D = network_data()
    js = open(os.path.join(HERE, 'cra_network.js')).read().replace('__CRN__', json.dumps(D, ensure_ascii=False, separators=(',', ':')))
    open(os.path.join(out_dir, 'assets', 'cra_network.js'), 'w').write(js)
    shutil.copy(os.path.join(HERE, 'cra_network.css'), os.path.join(out_dir, 'assets', 'cra_network.css'))
    named = {r['e'] for r in D['recs'] if r['e'][0] in 'vb'}
    paid_donors = {d['e'] for d in D['don'] if d['e']}
    board_gifts = [d for d in D['don'] if d['b']]
    chips = ''.join(f'<button type="button" class="crn-chip" data-cra="{k}" aria-pressed="true">{v["n"].replace(" CRA", "")}</button>'
                    for k, v in D['cras'].items())
    return f'''<div class="page tax crn">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Accountability · CRA network</span><h1>Who the redevelopment agencies paid, and who gave to their boards</h1>
    <p class="lede">Every payment, contract and grant in the CRA ledger, linked to who received it, to other payees on the same project or address, and to business gifts to the officials who sit as each CRA's board. Tap any name to follow its connections.</p></div>
    <div class="stamp"><a class="pill" href="/public-money/cra-spending">CRA spending ledger</a><a class="pill" href="/public-money/money-map">Money map</a><span>Campaign reports as of {D.get("as_of") or ""}</span></div></header>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">Read this first</span><h2>What a line means</h2>
    <ol class="ex-steps"><li><b>A gray line is money from a CRA.</b> Thicker lines carry more dollars. Contract records that sit inside a larger project total are shown on the payee, but counted once in the totals.</li>
      <li><b>A dashed line is a documented link between two payees:</b> the same project, the same address, or one working as the other's subconsultant. Each one cites its record.</li>
      <li><b>A red line is a business campaign gift.</b> Each city's commission or council sits as its CRA's board. Only businesses and PACs are shown, never individual donors, and none of this shows wrongdoing.</li></ol></div></section>
  <div class="kpis" id="crnKpis"></div>
  <div class="crn-bar" role="group" aria-label="Filters">
    <div class="crn-grp"><span class="crn-lbl">Agency</span>{chips}</div>
    <div class="crn-grp" id="crnStatus"><span class="crn-lbl">Status</span></div>
    <div class="crn-grp" id="crnDon"><span class="crn-lbl">Donations</span></div>
  </div>
  <div class="crn-tabs" role="tablist" aria-label="Views">
    <button type="button" role="tab" class="crn-tab" id="t-network" data-v="network">Network</button>
    <button type="button" role="tab" class="crn-tab" id="t-map" data-v="map">Map</button>
    <button type="button" role="tab" class="crn-tab" id="t-payees" data-v="payees">Payees</button>
    <button type="button" role="tab" class="crn-tab" id="t-donations" data-v="donations">Donations</button>
  </div>
  <div class="crn-main">
    <div class="crn-view">
      <section id="v-network"><div class="crn-vh"><h2>Who the agencies paid</h2><div class="crn-fsbar"><span class="crn-fsonly"><button type="button" class="crn-chip crn-fsv" data-v="network">Network</button><button type="button" class="crn-chip crn-fsv" data-v="map">Map</button></span><button type="button" class="crn-btn crn-fs" aria-pressed="false">Full screen</button></div><div class="crn-legend">
        <span><i style="background:var(--navy)"></i>Agency</span><span><i style="background:var(--blue)"></i>Business or nonprofit</span>
        <span><i style="background:var(--muted)"></i>Government or bondholders</span><span><i style="background:var(--amber)"></i>Property owner</span>
        <span><i class="hollow"></i>Not named</span><span><i style="background:var(--salmon)"></i>Elected official</span>
        <span><i class="ln dash"></i>Shared project, address or sub</span><span><i class="ln red"></i>Campaign gift</span></div></div>
        <div class="crn-wrap"><svg id="crnGraph" role="img" aria-label="Network of CRAs, the payees they paid, and business campaign gifts to CRA board members"></svg><div class="crn-zoom"><button type="button" id="crnGin" aria-label="Zoom in">+</button><button type="button" id="crnGout" aria-label="Zoom out">−</button><button type="button" id="crnGreset">Reset</button></div><div class="crn-tip" id="crnTip" hidden></div></div>
        <p class="crn-note">Drag a circle to move it, drag the background to pan, and scroll, pinch or use the buttons to zoom. Names show on larger and connected nodes; tap any node for its record.</p></section>
      <section id="v-map" hidden><div class="crn-vh"><h2>Where the money went</h2><div class="crn-fsbar"><span class="crn-fsonly"><button type="button" class="crn-chip crn-fsv" data-v="network">Network</button><button type="button" class="crn-chip crn-fsv" data-v="map">Map</button></span><button type="button" class="crn-btn crn-fs" aria-pressed="false">Full screen</button></div><div class="crn-legend" id="crnMapLegend"></div></div>
        <div class="crn-wrap"><svg id="crnMap" role="img" aria-label="Map of CRA spending by location"></svg><div class="crn-zoom"><button type="button" id="crnZin" aria-label="Zoom in">+</button><button type="button" id="crnZout" aria-label="Zoom out">−</button><button type="button" id="crnZreset">Reset</button></div><div class="crn-tip" id="crnTip2" hidden></div></div>
        <p class="crn-note">Scroll or pinch to zoom, drag to pan. Circle area scales with dollars. Many records are placed at a district or corridor point rather than a street address. Select a payee to highlight its records.</p></section>
      <section id="v-payees" hidden><div class="crn-vh"><h2>Every payee, ranked</h2><span class="crn-note" id="crnPayCount"></span></div>
        <div class="tablewrap"><table class="tx-table" id="crnPay"></table></div></section>
      <section id="v-donations" hidden><div class="crn-vh"><h2>Business gifts to CRA board members</h2><span class="crn-note" id="crnDonCount"></span></div>
        <div class="crn-pad"><div class="crn-grp" id="crnBoards"><span class="crn-lbl">Board</span></div>
        <div class="tablewrap"><table class="tx-table" id="crnDonT"></table></div>
        <p class="crn-note">Each row totals one business's gifts to one official's most recent campaign, from Supervisor of Elections reports. Donors that were also paid from a CRA ledger record are listed first, including gifts to officials who are not on a CRA board. "Likely" means the names matched after a hand check rather than exactly. Springfield and Parker officials reported no itemized business gifts. Gifts from individual people are counted on <a href="/public-money/campaign-money">Campaign Money</a> but never named.</p></div></section>
    </div>
    <aside class="crn-profile" id="crnProfile" aria-live="polite"></aside>
  </div>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">Sources and method</h2></div>
    <p>Payments, contracts and grants come from the <a href="/public-money/cra-spending">CRA ledger</a>, compiled from each agency's annual reports, Auditor General filings, resolutions and news coverage; every record links to its source. Payees are matched to the site's vendor list by name. {len(named)} payees are named; grant programs whose recipients aren't named are grouped, and private home addresses are left out. Campaign gifts come from the officials' most recent reports with the Supervisor of Elections; {len(paid_donors)} businesses both gave to a campaign and were paid from a CRA record, and {len(board_gifts)} business or PAC gifts went to CRA board members. A gift and a payment appearing together is a fact about the records. It says nothing about why either happened, and most CRA spending is approved by the full board.</p></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<link rel="stylesheet" href="/assets/cra_network.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js" defer></script>
<script src="/assets/cra_network.js" defer></script>'''
