"""Money map (/public-money/money-map): donor organizations -> officials -> governments where those donors hold contracts.

Built from data/campaign (the same data as the Campaign Money page). Individual donors are never named.
"""
import json, os, re
from collections import defaultdict
import campaign_page as cp

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data', 'campaign')
GOV_KEY = {'Bay County BOCC': 'county', 'City of Lynn Haven': 'lh', 'City of Panama City': 'pc', 'City of Panama City Beach': 'pcb',
           'City of Mexico Beach': 'mb', 'City of Callaway': 'cw', 'City of Springfield': 'sp', 'City of Parker': 'parker', 'Bay District Schools': 'schools'}
GSHORT = {'county': 'Bay County', 'constitutional': 'County officers', 'schools': 'School Board', 'pc': 'Panama City', 'pcb': 'Panama City Beach',
          'lh': 'Lynn Haven', 'cw': 'Callaway', 'sp': 'Springfield', 'parker': 'Parker', 'mb': 'Mexico Beach'}
AWARD = re.compile(r'^(Contract|ITB|RFP|Award|Emergency)', re.I)


def _amt(s):
    m = re.findall(r'\$([\d,]+(?:\.\d+)?)', s)
    return float(m[-1].replace(',', '')) if m else 0.0


def map_data():
    d = json.load(open(os.path.join(DATA, 'campaign.json')))
    vm = json.load(open(os.path.join(DATA, 'vendor_matches.json')))
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
    contracts = defaultdict(lambda: {'a': 0.0, 'p': 0.0, 'n': 0, 'co': 0, 'items': [], 'urls': []})
    for m in vm['matches']:
        nm = canon(m['contributor'])
        if nm not in donors or m['candidate'] not in by_name:
            continue
        g = GOV_KEY.get(m.get('contract_government'))
        if not g:
            continue
        k = (donors[nm]['id'], by_name[m['candidate']], g)
        r = contracts[k]
        r['same'] = bool(m.get('same_government_as_office'))
        r['ent'] = m.get('vendor_entity') or nm
        r['likely'] = m.get('match_confidence') == 'likely'
        for s in m.get('contract_ids_or_descriptions') or []:
            r['items'].append(s)
            if AWARD.match(s):
                r['a'] += _amt(s); r['n'] += 1
            elif re.search(r'\bpaid\b', s, re.I):
                r['p'] += _amt(s)
            else:
                r['co'] += 1
        r['urls'] += [u for u in m.get('contract_source_urls') or [] if u not in r['urls']]
    cons = [{'d': k[0], 'o': k[1], 'g': k[2], **{x: (round(v, 2) if isinstance(v, float) else v) for x, v in r.items()}} for k, r in contracts.items()]
    for c in cons:
        donors_list = donors  # noqa
    contractor_ids = {c['d'] for c in cons}
    dl = list(donors.values())
    for x in dl:
        x['k'] = x['id'] in contractor_ids
        x['tot'] = round(sum(g['a'] for g in gifts if g['d'] == x['id']), 2)
    return {'officials': officials, 'donors': dl, 'gifts': gifts, 'contracts': cons, 'govs': GSHORT, 'as_of': d.get('as_of')}


def money_map_page(out_dir):
    try:
        D = map_data()
    except FileNotFoundError:
        return '<div class="page prose"><h1>Money map</h1><p>Coming soon.</p></div>'
    js = open(os.path.join(HERE, 'money_map.js')).read().replace('__MM__', json.dumps(D, ensure_ascii=False, separators=(',', ':')))
    open(os.path.join(out_dir, 'assets', 'money_map.js'), 'w').write(js)
    nk = sum(1 for x in D['donors'] if x['k'])
    gtot = sum(g['a'] for g in D['gifts'])
    return f'''<div class="page tax mm">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Accountability · Money map</span><h1>Money map</h1>
    <p class="lede">How campaign money connects to local contracts: which businesses and groups gave to which officials, and where those same donors hold contracts with a Bay County government. Tap anything on the map to follow its connections.</p></div>
    <div class="stamp"><a class="pill" href="/public-money/campaign-money">Campaign money tables</a><span>Reports as of {cp.e(D.get("as_of"))}</span></div></header>
  <div class="kpis">
    <div class="kpi"><span class="eyebrow">Donor organizations</span><span class="v">{len(D["donors"])}</span><span class="s">${gtot:,.0f} given to {len(D["officials"])} officials</span></div>
    <div class="kpi"><span class="eyebrow">Also hold contracts</span><span class="v">{nk}</span><span class="s">donors with a local government contract or payment</span></div>
    <div class="kpi"><span class="eyebrow">Same government</span><span class="v">{sum(1 for c in D["contracts"] if c["same"])}</span><span class="s">gifts to an official of the government that pays the donor</span></div>
  </div>
  <div class="vt-filters mm-f">
    <label class="vf"><span>Show donors</span><select id="mmShow"><option value="k">With local contracts</option><option value="top">Top 40 by amount</option><option value="all">All organizations</option></select></label>
    <label class="vf"><span>Officials of</span><select id="mmGov"><option value="">Every government</option></select></label>
    <label class="vf"><span>Find</span><input id="mmQ" type="search" placeholder="Donor or official"></label>
  </div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="map">Relationship map</h2><span class="muted" id="mmCount"></span></div>
    <div class="mm-legend"><span><i class="lg-gift"></i>Campaign gift</span><span><i class="lg-con"></i>Donor's contracts with a government</span><span><i class="lg-same"></i>Same government as the official</span><span class="muted">Line thickness shows dollars</span></div>
    <p class="mm-hint muted small">Scroll sideways to see the whole map.</p><div class="mm-wrap" id="mmWrap"><svg id="mmSvg" role="img" aria-label="Map of donor organizations, the officials they gave to, and the governments where those donors hold contracts"></svg></div>
    <div class="mm-detail" id="mmDetail" aria-live="polite"><p class="muted">Tap a donor, official or government to see its connections and the records behind them.</p></div>
  </section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="heat1">Heat map: who gave to which government's officials</h2><span class="muted">Top 30 donor organizations</span></div>
    <div class="tablewrap"><table class="heat" id="mmHeat1"></table></div>
    <p class="note">Each cell is what the organization gave to the campaigns of that government's current officials. Darker means more. A ring marks a donor that also holds a contract with that government.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="heat2">Heat map: officials and their donors' contracts</h2><span class="muted">Contract awards to each official's donors, by government</span></div>
    <div class="tablewrap"><table class="heat" id="mmHeat2"></table></div>
    <p class="note">Each cell totals the contract awards, by the government in the column, to organizations that gave to the official in the row. A ring marks the official's own government. Change orders and payment records are counted in the details, not in the totals.</p></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">How to read this</h2></div>
    <p>A line between a donor and an official is a campaign contribution in the official's most recent race, from the Supervisor of Elections' reports. A line from an official to a government means some of that official's donors hold contracts with that government, matched by organization name against the contracts and payments on this site. A gift and a contract appearing together is a fact in the public record, not evidence that one caused the other; contracts can come before or after a gift, and the details list the dates.</p>
    <p>Only organizations are shown. Gifts from individual people are counted on the <a href="/public-money/campaign-money">Campaign Money</a> page but not named, and gifts from a company's owners or employees as individuals aren't linked to the company.</p></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/money_map.js" defer></script>'''
