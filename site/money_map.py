"""Money map (/public-money/money-map): officials <- donor organizations -> governments that pay those donors.

The donor sits in the middle so each fact is shown once and attached to who it belongs to:
a gift links a donor to the official who received it; a contract links the donor to the government that awarded it.
Contract dollars are never attributed to an official. Votes are shown only where the minutes record the official
voting on a contract with their own donor.
Built from data/campaign and data/votes. Individual donors are never named.
"""
import json, os, re
from collections import defaultdict
import campaign_page as cp

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
GOV_KEY = {'Bay County BOCC': 'county', 'City of Lynn Haven': 'lh', 'City of Panama City': 'pc', 'City of Panama City Beach': 'pcb',
           'City of Mexico Beach': 'mb', 'City of Callaway': 'cw', 'City of Springfield': 'sp', 'City of Parker': 'parker', 'Bay District Schools': 'schools'}
GSHORT = {'county': 'Bay County', 'constitutional': 'County officers', 'schools': 'School Board', 'pc': 'Panama City', 'pcb': 'Panama City Beach',
          'lh': 'Lynn Haven', 'cw': 'Callaway', 'sp': 'Springfield', 'parker': 'Parker', 'mb': 'Mexico Beach'}
BODY = {'county': ('bay-bocc',), 'pc': ('pc-commission', 'pc-cra'), 'pcb': ('pcb-council',), 'lh': ('lh-commission', 'lh-cra'), 'mb': ('mb-council',),
        'cw': ('cw-commission', 'cw-cra'), 'sp': ('sp-commission',), 'parker': ('parker-council',), 'schools': ('bds-board',)}
AWARD = re.compile(r'^(Contract|ITB|RFP|Award|Emergency)', re.I)
# exact names used to find a donor's contracts in the minutes (loose matching confuses, e.g., C.W. Roberts with Roberts and Roberts)
ALIAS = {'ecsc': ['ecsc', 'emerald coast site'], 'cwroberts': ['c.w. roberts', 'cw roberts', 'c. w. roberts'], 'robertsandroberts': ['roberts and roberts', 'roberts & roberts'],
         'rjgorman': ['rj gorman', 'r.j. gorman', 'r. j. gorman'], 'panhandleengineering': ['panhandle engineering'], 'dewberry': ['dewberry'], 'culpepper': ['culpepper'],
         'marshallbrothers': ['marshall brothers', 'marshall bros'], 'andersoncolumbia': ['anderson columbia', 'anderson-columbia'], 'americansand': ['american sand'],
         'gulfcoastutility': ['gulf coast utility'], 'coastalparasail': ['coastal parasail'], 'bgn': ['bgn contractors'], 'southeasternoutdoor': ['southeastern outdoor'],
         'mainline': ['mainline construction'], 'williamscommunications': ['williams communications'], 'mrfence': ['mr. fence', 'mr fence'],
         'floridaarchitects': ['florida architects'], 'tkvandy': ['tk vandy', 'tkvandy']}


def _amt(s):
    m = re.findall(r'\$([\d,]+(?:\.\d+)?)', s)
    return float(m[-1].replace(',', '')) if m else 0.0


def _aliases(name):
    n = re.sub(r'[^a-z]', '', name.lower().replace('bothers', 'brothers'))
    for k, v in ALIAS.items():
        if k in n:
            return v
    return [re.sub(r',?\s*(inc|llc|co)\.?$', '', name.lower()).strip()]


def map_data():
    d = json.load(open(os.path.join(DATA, 'campaign', 'campaign.json')))
    vm = json.load(open(os.path.join(DATA, 'campaign', 'vendor_matches.json')))
    votes = json.load(open(os.path.join(DATA, 'votes', 'votes.json')))['votes']
    cp.campaign_page()  # builds the shared canonical-name table
    canon = lambda n: cp.CANON.get(cp._base(cp.NAME_FIX.get(n.strip(), n.strip()))) or cp._display([cp.NAME_FIX.get(n.strip(), n.strip())])
    order = list(GSHORT)
    officials, donors, gifts = [], {}, []
    for c in sorted(d['candidates'], key=lambda c: (order.index(c.get('gov')) if c.get('gov') in order else 99, -(c.get('total_raised') or 0))):
        oid = len(officials)
        orgs = [x for x in c.get('contributors') or [] if x.get('type') not in ('individual', 'candidate')]
        ty = {canon(x['name']): x.get('type') for x in orgs}
        fi = c.get('from_individuals') or {}
        officials.append({'id': oid, 'n': c['official'], 'off': c.get('office'), 'g': c.get('gov'), 'raised': c.get('total_raised') or 0,
                          'ind': fi.get('total') or 0, 'indn': fi.get('count') or 0, 'url': c.get('report_url')})
        for name, amt in cp.merge_orgs(orgs):
            if name not in donors:
                donors[name] = {'id': len(donors), 'n': name, 't': ty.get(name) or 'business'}
            gifts.append({'d': donors[name]['id'], 'o': oid, 'a': round(amt, 2)})
    by_name = {o['n']: o['id'] for o in officials}
    # contracts: one record per donor and government, items de-duplicated (vendor_matches repeats them per official)
    con = defaultdict(lambda: {'items': {}, 'urls': [], 'likely': False, 'ent': None})
    gift_dates = {}
    for m in vm['matches']:
        nm = canon(m['contributor'])
        g = GOV_KEY.get(m.get('contract_government'))
        if nm not in donors or not g:
            continue
        r = con[(donors[nm]['id'], g)]
        for s in m.get('contract_ids_or_descriptions') or []:
            r['items'][s] = True
        r['urls'] += [u for u in m.get('contract_source_urls') or [] if u not in r['urls']]
        r['likely'] |= m.get('match_confidence') == 'likely'
        r['ent'] = r['ent'] or m.get('vendor_entity')
        if m['candidate'] in by_name:
            gift_dates[(donors[nm]['id'], by_name[m['candidate']])] = m.get('contribution_dates') or []
    cons = []
    for (did, g), r in con.items():
        items = list(r['items'])
        a = sum(_amt(s) for s in items if AWARD.match(s))
        p = sum(_amt(s) for s in items if re.search(r'\bpaid\b', s, re.I))
        cons.append({'d': did, 'g': g, 'a': round(a, 2), 'p': round(p, 2), 'n': sum(1 for s in items if AWARD.match(s)),
                     'co': sum(1 for s in items if not AWARD.match(s) and not re.search(r'\bpaid\b', s, re.I)), 'items': items, 'urls': r['urls'][:8], 'likely': r['likely'], 'ent': r['ent']})
    held = defaultdict(set)
    for c in cons:
        held[c['d']].add(c['g'])
    for gf in gifts:
        gf['same'] = OFFG(officials[gf['o']]) in held.get(gf['d'], set())
        gf['dates'] = gift_dates.get((gf['d'], gf['o'])) or []
    # recorded votes by an official on a contract with their own donor
    vrows = []
    for gf in gifts:
        if not gf['same']:
            continue
        o, dn = officials[gf['o']], donors_list(donors)[gf['d']]
        al = _aliases(dn['n'])
        last = o['n'].split()[-1].lower()
        for v in votes:
            if not v['body'].startswith(BODY.get(OFFG(o), ('~',))) or v.get('category') != 'contract':
                continue
            txt = ' '.join([v.get('item') or '', v.get('summary') or '', v.get('headline') or '']).lower()
            # skip plat approvals, judged by the headline (what the vote did): minutes sometimes file a contract award
            # under an unrelated plat item, e.g. Panama City's 2025-06-24 Marshall Brothers generator award
            if re.search(r'\bplat\b', (v.get('headline') or v.get('item') or '').lower()) or not any(a in txt for a in al):
                continue
            mv = next((val for n, val in (v.get('by_member') or {}).items() if n.split()[-1].lower() == last), None)
            if mv not in ('yes', 'no', 'abstain', 'absent'):
                continue
            before = [x for x in gf['dates'] if x <= v['date']]
            vrows.append({'d': gf['d'], 'o': gf['o'], 'gift': gf['a'], 'gift_dates': gf['dates'], 'date': v['date'], 'h': v.get('headline') or v['item'],
                          'amount': v.get('amount'), 'vote': mv, 'outcome': v.get('outcome'), 'tally': v.get('tally'), 'consent': 'consent' in (v.get('item') or '').lower(),
                          'when': None if not gf['dates'] else ('after' if before else 'before'), 'url': v.get('source_url'), '_v': v})
    vrows.sort(key=lambda r: (officials[r['o']]['n'], r['date']))
    vgroups = vote_groups(vrows, officials)
    for r in vrows:
        r.pop('_v')
    dl = donors_list(donors)
    try:  # vendor profile page for each donor that has one
        from vendor_pages import build as _vb
        import ids as _ids
        _prof = set(_vb())
        for x in dl:
            x['vp'] = next((v for v in _ids.vendor_ids(x['n']) if v in _prof), None)
    except Exception:
        pass
    for x in dl:
        x['k'] = bool(held.get(x['id']))
        x['tot'] = round(sum(g['a'] for g in gifts if g['d'] == x['id']), 2)
    return {'officials': officials, 'donors': dl, 'gifts': gifts, 'contracts': cons, 'votes': vrows, 'vgroups': vgroups, 'govs': GSHORT, 'as_of': d.get('as_of')}


def vote_groups(vrows, officials):
    """One row per recorded vote and donor, with the full roll call. Members who got a gift from that donor carry it."""
    groups = {}
    for r in vrows:
        v = r['_v']
        k = (v['body'], v['date'], v.get('item'), r['d'])
        if k not in groups:
            g = OFFG(officials[r['o']])
            cur = {o['n'].split()[-1].lower(): o['id'] for o in officials if o['g'] == g}
            roll = [{'n': n, 'vote': val, 'o': cur.get(n.split()[-1].lower())} for n, val in (v.get('by_member') or {}).items()]
            groups[k] = {'d': r['d'], 'g': g, 'date': r['date'], 'h': r['h'], 'amount': r['amount'], 'outcome': r['outcome'], 'tally': r['tally'],
                         'consent': r['consent'], 'url': r['url'], 'roll': roll}
        for m in groups[k]['roll']:
            if m['n'].split()[-1].lower() == officials[r['o']]['n'].split()[-1].lower():
                m.update({'o': r['o'], 'gift': r['gift'], 'gift_dates': r['gift_dates'], 'when': r['when']})
    out = list(groups.values())
    for x in out:  # gift recipients first, then the rest of the board in the minutes' order
        x['roll'].sort(key=lambda m: 'gift' not in m)
    out.sort(key=lambda x: x['date'], reverse=True)
    return out


def donors_list(donors):
    return sorted(donors.values(), key=lambda x: x['id'])


def OFFG(o):
    return o['g']


def money_map_page(out_dir):
    try:
        D = map_data()
    except FileNotFoundError:
        return '<div class="page prose"><h1>Money map</h1><p>Coming soon.</p></div>'
    js = open(os.path.join(HERE, 'money_map.js')).read().replace('__MM__', json.dumps(D, ensure_ascii=False, separators=(',', ':')))
    open(os.path.join(out_dir, 'assets', 'money_map.js'), 'w').write(js)
    e = cp.e
    k_ids = {x['id'] for x in D['donors'] if x['k']}
    k_gift = sum(g['a'] for g in D['gifts'] if g['d'] in k_ids)
    same = [g for g in D['gifts'] if g['same']]
    voted = {(v['d'], v['o']) for v in D['votes']}
    return f'''<div class="page tax mm">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Accountability · Money map</span><h1>Money map</h1>
    <p class="lede">Which businesses and groups gave to which officials' campaigns, and which of those donors are paid by a local government. Tap any name to follow its connections.</p></div>
    <div class="stamp"><a class="pill" href="/public-money/campaign-money">Campaign money tables</a><button type="button" class="pdf-btn" id="pdf"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>Reports as of {e(D.get("as_of"))}</span></div></header>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">Read this first</span><h2>What the map does and doesn't show</h2>
    <ol class="ex-steps"><li><b>A gift and a contract are two separate facts.</b> A line to an official is a campaign gift. A line to a government is that government's contracts or payments to the same business. The map never adds contract dollars to an official.</li>
      <li><b>Officials only vote on their own government's contracts.</b> A county commissioner has no say in a city's contracts. The connections that can matter are marked: a gift to an official whose own government pays that donor.</li>
      <li><b>None of this shows wrongdoing.</b> Contracts are usually bid, and most are approved by the full board, often on a consent agenda with routine items. The dates are shown so you can see what came first.</li></ol></div></section>
  <div class="kpis">
    <div class="kpi"><span class="eyebrow">Donor organizations</span><span class="v">{len(D["donors"])}</span><span class="s">gave to {len(D["officials"])} current officials</span></div>
    <div class="kpi"><span class="eyebrow">Also paid by a local government</span><span class="v">{len(k_ids)}</span><span class="s">gave ${k_gift:,.0f} in all</span></div>
    <div class="kpi"><span class="eyebrow">Gift to the official's own government's contractor</span><span class="v">{len(same)}</span><span class="s">gifts totaling ${sum(g["a"] for g in same):,.0f}</span></div>
    <div class="kpi"><span class="eyebrow">Voted on that donor's contract</span><span class="v">{len(voted)}</span><span class="s">official–donor pairs, {len(D["vgroups"])} recorded votes</span></div>
  </div>
  <div class="vt-filters mm-f">
    <label class="vf"><span>Show donors</span><select id="mmShow"><option value="same">Gave to an official whose government pays them</option><option value="k">Paid by any local government</option><option value="top">Top 40 by amount given</option><option value="all">All organizations</option></select></label>
    <label class="vf"><span>Officials of</span><select id="mmGov"><option value="">Every government</option></select></label>
    <label class="vf"><span>Find</span><input id="mmQ" type="search" placeholder="Donor or official"></label>
  </div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="map">Relationship map</h2><span class="muted" id="mmCount"></span></div>
    <div class="mm-legend"><span><i class="lg-gift"></i>Campaign gift</span><span><i class="lg-same"></i>Gift to an official whose government pays the donor</span><span><i class="lg-con"></i>Government's contracts or payments to the donor</span><span class="muted">Line thickness shows dollars; gifts and contracts use separate scales</span></div>
    <p class="mm-hint muted small">Scroll sideways to see the whole map.</p><div class="mm-wrap" id="mmWrap"><svg id="mmSvg" role="img" aria-label="Map of officials, the organizations that gave to their campaigns, and the governments that pay those organizations"></svg></div>
    <div class="mm-detail" id="mmDetail" aria-live="polite"><p class="muted">Tap an official, donor or government to see its connections and the records behind them.</p></div>
  </section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="votes">Votes on a donor's contract</h2><span class="muted">Contract votes where at least one board member had received a gift from the business. The full roll call is shown; members who got a gift are listed first, in bold.</span></div>
    <div class="tablewrap"><table class="tx-table cm-table" id="mmVotes"></table></div>
    <p class="note">From the meeting minutes on the <a href="/public-money/votes">How They Voted</a> page, matched by the company's exact name. "Consent" means the item was approved in one vote with other routine items. Only the votes on this site are checked; contracts approved by staff under a purchasing limit never come to a vote.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="heat1">Heat map: who gave to which government's officials</h2><span class="muted">Top 30 donor organizations</span></div>
    <div class="tablewrap"><table data-tt="off" class="heat" id="mmHeat1"></table></div>
    <p class="note">Each cell is what the organization gave to the campaigns of that government's current officials. Darker means more. A ring marks a cell where that same government also pays the donor.</p></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">Sources and method</h2></div>
    <p>Gifts come from the officials' most recent campaign reports with the Supervisor of Elections. Contracts and payments come from the contracts, change orders and check registers on this site, matched by organization name; each donor's contracts with a government are counted once. Only organizations are shown; gifts from individual people, including a company's owners or employees, are counted on the <a href="/public-money/campaign-money">Campaign Money</a> page but not named or linked to a company.</p></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/money_map.js" defer></script>'''
