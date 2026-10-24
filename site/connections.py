"""Connections (/connections): who every local government paid, how those payees connect, and business campaign gifts
to the officials who approve that spending.

Covers every government and agency with payment records (the county, cities, school district, CRAs and tourism
agencies) and every kind of record: contracts, change orders, emergency purchases, check registers, tourism agency
payments and the CRA ledger (data/entities/records.py). A CRA is its own payer here, but it is one filter among many,
not the frame. Gifts come from data/entities/records.py donations() (officeholders and 2026 candidates); a donor is
"paid" when data/campaign/vendor_matches.json resolves it to the same vendor as a payment record.

Individual donors are never shown, only businesses, PACs and committees. Unnamed recipients of grant programs
(homeowners, small businesses) are grouped, never listed, and private home addresses are not shown.
"""
import json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
sys.path.insert(0, os.path.join(DATA, 'entities'))
import ids  # noqa: E402
import records  # noqa: E402
from city_filter import city_bar, gkey  # noqa: E402

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
    return ids.biz_case(re.sub(r'\s*\(.*?\)\s*', ' ', s).strip(' ,;'))


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


# record types, in the order the page lists them
TYPES = {'contract': 'Contracts', 'change_order': 'Change orders', 'emergency': 'Emergency purchases', 'register': 'Check registers',
         'tdc': 'Tourism agency payments', 'cra': 'CRA ledger'}
TOP = 40  # payees the graph shows by dollars in its default view (connections.js TOP)
CRA_OF = {v: k for k, v in CRA_GOV.items()}  # city gov id -> CRA code
CRA_SHOWN = ('Spent', 'Committed', 'Budgeted')  # planned or proposed CRA items are on the CRA ledger page, not here
GIFT_TYPES = ('business', 'pac', 'committee', 'other')  # organizations only; individuals are never listed
NOT_NAMED = records.NOT_NAMED
# check register payees that are other public bodies or employee funds (registers cut names at 15 characters)
PUBLICLIKE = re.compile(r'^(bay county\b|general employe|.*\b(pension|retirement)\b)', re.I)


def _payee(r, V, cra_code):
    """(key, name, kind) for any payment record. CRA rows keep the CRA ledger's own grouping (property owners,
    grant programs), so CRA ledger rows and connections payees share one id (cra_payments.payee_entity_id)."""
    if r['src'] == 'cra':
        return _entity({'payee': r['name'], 'category': r['extra'].get('category')}, cra_code, V)
    name = r['name'] or ''
    for vid in ids.vendor_ids(name):
        if vid in V:
            return 'v:' + vid, V[vid]['name'], 'biz'
    if not name.strip() or NOT_NAMED.search(name):
        return 'u:none-' + (r['gov_id'] or 'other'), 'Payee not named', 'unnamed'
    if GOVLIKE.match(name) or ids.gov_id(name) or PUBLICLIKE.match(name):
        n = _strip(name)
        return 'g:' + _slug(n), n, 'gov'
    n = _strip(name)
    return 'b:' + _slug(n), n, 'biz'


def network_data():
    M = json.load(open(os.path.join(DATA, 'merged.json')))
    V = {v['id']: v for v in json.load(open(os.path.join(DATA, 'entities', 'vendors.json')))['vendors']}
    G = {g['id']: g for g in ids.governments()}
    vm = json.load(open(os.path.join(DATA, 'campaign', 'vendor_matches.json')))
    camp = json.load(open(os.path.join(DATA, 'campaign', 'campaign.json')))
    try:
        from vendor_pages import build as _vb
        pages = set(_vb())
    except Exception:
        pages = set()
    cra_city = {c['cra']: c.get('city') for c in M['cras']}
    cat = {i: p.get('category') for i, p in enumerate(M['payments'])}

    payers, ents, recs = {}, {}, []
    for r in records.all_records():
        x = r['extra']
        if r['src'] == 'cra':
            code = CRA_CODE.get(x['cra'])
            if not code or x.get('status') not in CRA_SHOWN:
                continue
            if x.get('count') is False and str(x.get('overlap') or '').startswith('Total of'):
                continue  # an aggregate of rows listed separately
            pk = 'cra:' + code
            payers.setdefault(pk, {'n': x['cra'], 'k': 'cra', 'g': CRA_GOV[code]})
            r = {**r, 'extra': {**x, 'category': cat.get(r['idx'])}}
        else:
            gid = r['gov_id']
            if not gid:
                continue
            g = G.get(gid) or {}
            pk = 'g:' + gid
            payers.setdefault(pk, {'n': g.get('short') or gid, 'k': 'tourism' if r['src'] == 'tdc' else 'gov', 'g': gkey(gid) or gkey(g.get('parent')) or ''})
            code = None
        key, name, kind = _payee(r, V, code)
        e = ents.setdefault(key, {'n': name, 'k': kind})
        if key.startswith('v:') and key[2:] in pages:
            e['vp'] = key[2:]
        a = r['amount'] if isinstance(r['amount'], (int, float)) else None
        rec = {'id': f"{r['src']}:{r['idx']}", 'p': pk, 'e': key, 't': r['src'], 'a': a, 'when': str(r['date'] or ''),
               'w': (r['what'] or '')[:300], 'u': r['url']}
        if r['src'] == 'cra':
            rec['s'] = x.get('status')
            if not x.get('count'):
                rec['x'] = 1  # inside a larger project total in the CRA ledger
        recs.append(rec)

    # payees that are local nonprofits (data/nonprofits matches payment records to organizations by name)
    np_of = {}
    for fp in sorted(__import__('glob').glob(os.path.join(DATA, 'nonprofits', '*', 'nonprofits.json'))):
        for p in json.load(open(fp))['payments']:
            np_of[p['record_id']] = p['nonprofit_id']
    for r in recs:
        if r['id'] in np_of and r['e'] in ents:
            ents[r['e']]['np'] = np_of[r['id']]

    rel = []
    for a, b, t, u in RELATED:
        for k in (a, b):
            if k in SUBS:
                ents.setdefault(k, {'n': SUBS[k], 'k': 'biz', 'sub': True})
        if a in ents and b in ents:
            rel.append({'a': a, 'b': b, 't': t, 'u': u})

    # a donor is "paid" when the site's vendor matching resolves it to the vendor on a payment record
    paid = {}
    for m in vm['matches']:
        k = 'v:' + m['vendor_id'] if m.get('vendor_id') else None
        if k in ents:
            for n in [m['contributor']] + (m.get('contributor_spellings') or []):
                old = paid.get(_norm(n))
                if not old or old[1] == 'likely':
                    paid[_norm(n)] = (k, m.get('match_confidence'))

    def office_gov(c):
        return c.get('gov') if c.get('gov') in G and c.get('gov') != 'constitutional' else (ids.gov_id(c.get('office'), contains=True) or ('county' if c.get('gov') == 'constitutional' else None))

    officials = {}
    agg = {}
    for d in records.donations(GIFT_TYPES):
        cand = d['src'] == 'candidates_2026'
        oid = 'm:' + d['candidate']  # m: an elected official or candidate (o: is a property owner)
        o = officials.setdefault(oid, {'n': d['candidate'], 'off': d.get('office') or '', 'g': None, 'cand': cand, 'u': d.get('report_url')})
        if not o['g']:
            o['g'] = office_gov({'gov': d.get('gov'), 'office': d.get('office')})
        if not cand:
            o['cand'] = False  # a sitting official who is also on the 2026 ballot
        k = _norm(d['name'])
        ent, conf = paid.get(k, (None, None))
        dk = ent or 'd:' + k
        x = agg.setdefault((dk, oid), {'dn': ids.biz_case(d['name']), 'ty': _gift_type(d), 'o': oid, 'a': 0.0, 'n': 0, 'ds': [],
                                       'e': ent, 'cf': conf, 'u': d.get('report_url'), 'cand': cand})
        x['a'] += d.get('amount') or 0
        x['n'] += 1
        if d.get('date'):
            x['ds'].append(d['date'])
    don = []
    for x in agg.values():
        ds = sorted(x.pop('ds'))
        x['date'] = (ds[0] + (' to ' + ds[-1] if ds[-1] != ds[0] else '')) if ds else ''
        x['a'] = round(x['a'], 2)
        don.append(x)
    don.sort(key=lambda x: (-(x['e'] is not None), -x['a']))
    for o in officials.values():
        o['pid'] = ids.person_id(o['n'])  # /people/<pid>
        o['gid'] = o['g'] or ''
        o['g'] = gkey(o['g']) or '' if o['g'] else ''  # city filter key (county officers count with the county)
        o['gp'] = [] if o['cand'] else [k for k, p in payers.items() if p['k'] != 'tourism' and k[k.index(':') + 1:] in (o['gid'], CRA_OF.get(o['gid']))]  # boards they sit on
    order = list(G)
    rank = lambda kv: (kv[1]['k'] == 'tourism', order.index(kv[1]['g']) if kv[1]['g'] in order else 50, kv[1]['k'] == 'cra', kv[1]['n'])
    pay_sorted = dict(sorted(payers.items(), key=rank))
    # source links repeat across records: send each once
    U = []
    ui = {}
    for x in recs + don:
        u = x.pop('u', None)
        if u:
            if u not in ui:
                ui[u] = len(U)
                U.append(u)
            x['u'] = ui[u]
    return {'payers': pay_sorted, 'ents': ents, 'recs': recs, 'rel': rel, 'don': don, 'off': officials, 'types': TYPES, 'urls': U,
            'as_of': camp.get('as_of')}


_TYPE_OF = {}


def _gift_type(d):
    """business / pac / committee / other, from the contributor list the gift came from."""
    if not _TYPE_OF:
        c = records._j('campaign', 'campaign.json') or {}
        f = records._j('elections', 'finance_2026.json') or {}
        for src in (c, f):
            for cd in src.get('candidates') or []:
                for x in cd.get('contributors') or []:
                    _TYPE_OF[x['name']] = x.get('type')
    return _TYPE_OF.get(d['name'], 'business')


def connections_page(out_dir):
    D = network_data()
    js = open(os.path.join(HERE, 'connections.js')).read().replace('__CN__', json.dumps(D, ensure_ascii=False, separators=(',', ':')))
    open(os.path.join(out_dir, 'assets', 'connections.js'), 'w').write(js)
    shutil.copy(os.path.join(HERE, 'connections.css'), os.path.join(out_dir, 'assets', 'connections.css'))
    named = {r['e'] for r in D['recs'] if r['e'][0] in 'vb'}
    paid_donors = {d['e'] for d in D['don'] if d['e']}
    cities = list(dict.fromkeys(p['g'] for p in D['payers'].values() if p['g']))
    kinds = [('gov', 'Governments'), ('cra', 'Redevelopment agencies'), ('tourism', 'Tourism agencies')]
    chips = ''.join(f'<div class="cn-grp"><span class="cn-lbl">{lbl}</span>' + ''.join(
        f'<button type="button" class="cn-chip" data-payer="{k}" aria-pressed="true">{v["n"]}</button>' for k, v in D['payers'].items() if v['k'] == kind) + '</div>'
        for kind, lbl in kinds if any(v['k'] == kind for v in D['payers'].values()))
    n_types = 'contracts, change orders, emergency purchases, check registers, tourism agency payments and CRA ledger'
    return f'''<div class="page tax cn">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Connections · Network</span><h1>Who local governments paid, and who gave to the officials in charge</h1>
    <p class="lede">Every contract, payment and grant on the site, linked to who received it, to other payees on the same project or address, and to business gifts to the officials who approve the spending. Tap any name to follow its connections.</p></div>
    <div class="stamp"><a class="pill" href="/connections/campaign-gifts">Campaign gifts</a><a class="pill" href="/connections/money-map">Money map</a><a class="pill" href="/connections/nonprofits">Nonprofits</a><span>Campaign reports as of {D.get("as_of") or ""}</span></div></header>
  {city_bar(cities, label='Government')}
  <section class="explain"><div class="ex-txt"><span class="eyebrow">Read this first</span><h2>What a line means</h2>
    <ol class="ex-steps"><li><b>A gray line is money from a government or agency.</b> Thicker lines carry more dollars in the records. A contract award and the check register payments on it can describe the same money, so record types are never added together.</li>
      <li><b>A dashed line is a documented link between two payees:</b> the same project, the same address, or one working as the other's subconsultant. Each one cites its record.</li>
      <li><b>A red line is a business campaign gift</b>, and a dotted line joins an official to the board they sit on. A city commission also sits as its redevelopment agency's board. Only businesses, PACs and committees are shown, never individual donors, and none of this shows wrongdoing.</li></ol></div></section>
  <div class="kpis" id="cnKpis"></div>
  <div class="cn-bar" role="group" aria-label="Filters">
    {chips}
    <div class="cn-grp" id="cnTypes"><span class="cn-lbl">Records</span></div>
    <div class="cn-grp" id="cnScope"><span class="cn-lbl">Payees</span></div>
    <div class="cn-grp" id="cnDon"><span class="cn-lbl">Gifts</span></div>
  </div>
  <div class="cn-tabs" role="tablist" aria-label="Views">
    <button type="button" role="tab" class="cn-tab" id="t-trail" data-v="trail">Money trail</button>
    <button type="button" role="tab" class="cn-tab" id="t-network" data-v="network">Network</button>
    <button type="button" role="tab" class="cn-tab" id="t-payees" data-v="payees">Payees</button>
    <button type="button" role="tab" class="cn-tab" id="t-gifts" data-v="gifts">Campaign gifts</button>
  </div>
  <div class="cn-main">
    <div class="cn-view">
      <section id="v-trail"><div class="cn-vh"><h2>Paid by a government, and gave to a campaign</h2><span class="cn-note" id="cnTrailCount"></span></div>
        <div class="cn-wrap cn-scroll"><svg id="cnTrail" role="img" aria-label="Governments that paid each business, and the officials each business gave to"></svg><div class="cn-tip" id="cnTip3" hidden></div></div>
        <p class="cn-note">Each business in the middle was paid in the records on the left and gave to the campaigns on the right. Gray lines are payments (thicker means more dollars in the records), red lines are campaign gifts. Tap any name to highlight its lines and see its records. A gift and a payment together are facts about the records, not evidence of why either happened.</p></section>
      <section id="v-network" hidden><div class="cn-vh"><h2>Who the governments paid</h2><label class="cn-find"><span class="sr">Find a name</span><input id="cnQ" list="cnFind" type="search" placeholder="Find a business, official or government" autocomplete="off"><datalist id="cnFind"></datalist></label><button type="button" class="cn-btn" id="cnClear">Clear</button><div class="cn-fsbar"><button type="button" class="cn-btn cn-fs" aria-pressed="false">Full screen</button></div><div class="cn-legend">
        <span><i style="background:var(--navy)"></i>Government or agency</span><span><i style="background:var(--blue)"></i>Business or nonprofit</span>
        <span><i style="background:var(--muted)"></i>Public body, fund or bondholders</span><span><i style="background:var(--amber)"></i>Property owner</span>
        <span><i class="hollow"></i>Not named</span><span><i style="background:var(--salmon)"></i>Official or candidate</span>
        <span><i class="ln dash"></i>Shared project, address or sub</span><span><i class="ln red"></i>Campaign gift</span></div></div>
        <div class="cn-wrap"><svg id="cnGraph" role="img" aria-label="Network of local governments, the payees they paid, and business campaign gifts to the officials who oversee them"></svg><div class="cn-zoom"><button type="button" id="cnGin" aria-label="Zoom in">+</button><button type="button" id="cnGout" aria-label="Zoom out">−</button><button type="button" id="cnGreset">Reset</button></div><div class="cn-tip" id="cnTip" hidden></div></div>
        <p class="cn-note">Drag a circle to move it, drag the background to pan, and scroll, pinch or use the buttons to zoom. The graph starts from one name: search above or tap a name anywhere on the page, then tap any circle to add its connections. "Donors and top payees" shows every payee that gave to a campaign or has a documented link plus the {TOP} largest, and "Every payee" shows all of them.</p></section>
      <section id="v-payees" hidden><div class="cn-vh"><h2>Every payee, ranked</h2><span class="cn-note" id="cnPayCount"></span></div>
        <div class="tablewrap"><table class="tx-table" id="cnPay"></table></div></section>
      <section id="v-gifts" hidden><div class="cn-vh"><h2>Business gifts to officials and candidates</h2><span class="cn-note" id="cnDonCount"></span></div>
        <div class="cn-pad"><div class="tablewrap"><table class="tx-table" id="cnDonT"></table></div>
        <p class="cn-note">Each row totals one business or group's gifts to one official's most recent campaign, or to a 2026 candidate, from Supervisor of Elections reports. Donors that were also paid by a local government are listed first. "Likely" means the names matched after a hand check rather than exactly. Gifts from individual people are counted on <a href="/connections/campaign-gifts">Campaign gifts</a>, where people who run a registered business are named.</p></div></section>
    </div>
    <aside class="cn-profile" id="cnProfile" aria-live="polite"></aside>
  </div>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">Sources and method</h2></div>
    <p>Payment records cover {n_types} records, from agendas, check registers, tourism agency payment files and each redevelopment agency's reports; every record links to its source. CRA ledger items that are only proposed or planned stay on the <a href="/public-money/cra-spending">CRA ledger</a>. Payees are matched to the site's vendor list by name. {len(named)} payees are named; grant programs whose recipients aren't named are grouped, and private home addresses are left out. Campaign gifts come from officials' most recent reports and 2026 candidates' reports with the Supervisor of Elections; {len(paid_donors)} businesses both gave to a campaign and were paid in these records. A gift and a payment appearing together is a fact about the records. It says nothing about why either happened, and most spending is approved by the full board.</p></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<link rel="stylesheet" href="/assets/connections.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js" defer></script>
<script src="/assets/connections.js" defer></script>'''
