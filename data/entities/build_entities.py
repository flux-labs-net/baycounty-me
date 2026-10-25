"""Build data/entities/vendors.json (+ vendor_review.json) and people.json from the research files.

Run by data/build.py after merged.json is written. Vendors:
  1. every payee name in contracts, change orders, emergency purchases, check registers, TDC payments and the CRA ledger
     (minus "not named", groups of private owners, and public bodies) is reduced to a key by ids.vkey();
  2. names with the same key are one vendor;
  3. SAME below joins keys that are the same firm (truncated register names, typos, d/b/a names), each with the evidence;
  4. business campaign contributors whose key matches a vendor become aliases of that vendor (never a new vendor);
  5. pairs that look alike but were NOT joined are written to vendor_review.json for a person to check.
Nothing is fuzzy-merged automatically.
"""
import collections, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ids  # noqa: E402
import records  # noqa: E402

K = ids.vkey

# ---- hand-reviewed: keys that are one firm. (keys, display name, evidence) ----
SAME = [
    (['marshallbrothers', 'marshallbrothersconstruction', 'marshallbrothersconstructionengineering', 'marshallbothers'], 'Marshall Brothers Construction & Engineering, Inc.',
     'Agendas use "Marshall Brothers", "Marshall Brothers, Inc." and the full name for the same water/sewer contractor; "Marshall Bothers" is a typo in one campaign filing.'),
    (['cwrobertscontracting', 'cwroberts', 'cwrobertscont'], 'C.W. Roberts Contracting, Inc.',
     'Spacing variants ("C. W.", "C.W.", "CW") and the Lynn Haven warrant list\'s 15-character "CW ROBERTS CONT". Kept separate from Roberts and Roberts, Inc., a different company.'),
    (['robertsroberts', 'robertsrober', 'robersroberts'], 'Roberts and Roberts, Inc.',
     '"ROBERTS & ROBER" is the Lynn Haven warrant list cut at 15 characters; "Robers and Roberts, Inc" is a typo in one 2026 campaign filing.'),
    (['gulfcoastutilitycontractors', 'gulfcoastutilitycontractor', 'gulfcoastutil'], 'Gulf Coast Utility Contractors, LLC',
     'Agendas add "(GCUC)" or drop the plural; "GULF COAST UTIL" is the Lynn Haven warrant list cut at 15 characters.'),
    (['dewberryengineers', 'dewberryengineering', 'dewberry'], 'Dewberry Engineers Inc.',
     'Panama City awarded Project RESTORE Glenwood task orders to "Dewberry Engineering Inc." (2023-11-28 agenda) and the CEI task order for the same project to "Dewberry Engineers Inc." (2025-06-10); '
     'Dewberry\'s Panhandle offices came from its 2016 purchase of Preble-Rish (dewberry.com). "DEWBERRY" is the Lynn Haven warrant list; "Dewberry" is how two campaign filings list it.'),
    (['americansandasphaltpaving', 'americansandasphalt', 'americansand', 'americansandasphaltpavi'], 'American Sand and Asphalt Paving, Inc.',
     '"AMERICAN SAND &" is the Lynn Haven warrant list cut at 15 characters; "American Sand and Asphalt Pavi" is a campaign filing cut at 30 characters.'),
    (['bgncontractors', 'gagegoldenconstruction', 'gagegoldenconstructiondbabgncontractors'], 'BGN Contractors (Gage Golden Construction)',
     'The county agenda names the firm "Gage Golden Construction dba BGN Contractors"; the county check register lists "GAGE GOLDEN CONSTRUCTION".'),
    (['ecsc', 'emeraldcoastsiteconstruction'], 'ECSC, LLC (Emerald Coast Site Construction)',
     'Agendas give both names together: "ECSC, LLC (Emerald Coast Site Construction)" and "Emerald Coast Site Construction (ECSC)".'),
    (['culpepperconstruction', 'culpepperconst', 'culpepper'], 'Culpepper Construction Co.',
     '"CULPEPPER CONST" is the Lynn Haven warrant list cut at 15 characters; one campaign filing lists just "Culpepper".'),
    (['rjgormanmarineconstruction', 'rjgormanmarine'], 'RJ Gorman Marine Construction, LLC',
     'Register spelling "R.J. Gorman Marine Construction LLC"; one campaign filing cuts it to "RJ Gorman Marine". Kept separate from RJ Gorman Contracting, LLC (a different LLC that built the Mexico Beach and PCB piers).'),
    (['panhandleengineering', 'panhandleengin'], 'Panhandle Engineering, Inc.', '"PANHANDLE ENGIN" is the Lynn Haven warrant list cut at 15 characters.'),
    (['bclcivilcontractors', 'bclcivilcontr'], 'BCL Civil Contractors, Inc.', '"BCL CIVIL CONTR" is the Lynn Haven warrant list cut at 15 characters.'),
    (['cbcconstruction', 'cbcconstructio'], 'CBC Construction', '"CBC CONSTRUCTIO" is the Lynn Haven warrant list cut at 15 characters.'),
    (['850constructionservices', '850constructio'], '850 Construction Services, LLC', '"850 CONSTRUCTIO" is the Lynn Haven warrant list cut at 15 characters.'),
    (['phoenixconstructionservices', 'phoenixconstru'], 'Phoenix Construction Services, Inc.', '"PHOENIX CONSTRU" is the Lynn Haven warrant list cut at 15 characters.'),
    (['arrisgeneralcontractors', 'arrisgeneral'], 'ARRIS General Contractors', '"ARRIS GENERAL" is the Lynn Haven warrant list cut short.'),
    (['davisonfuelsoil', 'davisonfuelsi'], 'Davison Fuels & Oil, LLC', '"DAVISON FUELS I" is the Lynn Haven warrant list cut at 15 characters.'),
    (['telemetryprocesscontrol', 'telemetryprocesscon'], 'Telemetry and Process Control, Inc.', 'The county register cuts the name at "TELEMETRY AND PROCESS CON".'),
    (['southeasternoutdoormanagement', 'southeasternoutdoormet', 'southeasternoutdoormgt', 'southeasternoutdoormgmt'], 'Southeastern Outdoor Management',
     '"Southeastern Outdoor Met Inc" and "Mgt Inc" are how the scanned Visit PCB register reads; "Southeastern Outdoor Mgmt" is a campaign filing.'),
    (['halffassociates', 'halff'], 'Halff Associates, Inc.', 'Panama City\'s agenda names "Halff (Halff Engineering / Halff Associates)".'),
    (['hydraservices', 'hydraservice'], 'Hydra Service(s), Inc.', 'Same pump-station firm spelled with and without the final "s" in Panama City and county agendas.'),
    (['inlandconstructionengineering', 'inlandconstruction'], 'Inland Construction and Engineering, Inc.',
     'Panama City agendas use both the full name and "Inland Construction"; the CRA ledger names "Inland Construction & Engineering" for the Millville park bid.'),
    (['southernconstructionservice', 'southernconstructionservices', 'southernconstruction'], 'Southern Construction Services, Inc.', 'Singular/plural and a shortened form in the same governments\' agendas.'),
    (['ten8', 'ten8firesafety'], 'Ten-8 Fire & Safety, LLC', 'Fire apparatus dealer named "Ten-8" in the county agenda and "Ten-8 Fire & Safety, LLC" elsewhere.'),
    (['hghardersons', 'hghardersson', 'hgharderssons'], 'H.G. Harders & Sons, Inc.', 'Apostrophe and plural variants of the same contractor.'),
    (['sjelectrosystemsdbaprimax', 'sjelectrosystemsdbaprimex'], 'S.J. Electro Systems, LLC (PRIMEX)', 'The two county agenda spellings differ only in "Primax"/"Primex".'),
    (['bayoubuildersofbay', 'bayoubuildersofbaycounty'], 'Bayou Builders of Bay County, LLC', '"Bay Co." and "Bay County" spellings in Panama City agendas.'),
    (['vyde', 'vydeltds'], 'Vyde LTD', 'The scanned Visit PCB register reads one line as "Vyde LTD S)"; the extra characters are a scan error.'),
    (['carvertise', 'carvertiseincis'], 'Carvertise, Inc', 'The scanned Destination Panama City register reads one line as "Carvertise, Inc iS)"; the extra characters are a scan error.'),
    (['floridablue', 'floridabluebluecrossblueshield'], 'Florida Blue (Blue Cross and Blue Shield of Florida)',
     'The county register names the payee "Florida Blue / Blue Cross Blue Shield of Florida"; Florida Blue is that insurer\'s trade name.'),
    (['worldchangersfirstbaptistchurchofpanamacity', 'worldchangersorganization', 'worldchangers'], 'World Changers (with First Baptist Church of Panama City)',
     'Panama City CRA annual reports name the same volunteer home-repair program as "World Changers / First Baptist Church of Panama City" and "World Changers Organization".'),
]
# a payee field that names more than one firm: raw text -> [(key, display)]
JOINT = {
    'Mott MacDonald and Panhandle Engineering': [('mottmacdonald', 'Mott MacDonald'), ('panhandleengineering', None)],
    'Gulf Coast Utility Contractors (GCUC) and STAline Waterworks, Inc.': [('gulfcoastutilitycontractors', None), ('stalinewaterworks', None)],
    'Dewberry Engineers (with Halff Associates and Magnum Engineering)': [('dewberryengineers', None), ('halffassociates', None), ('magnumengineering', 'Magnum Engineering')],
    'AT&T Enterprises, LLC and T-Mobile USA, Inc.': [('attenterprises', 'AT&T Enterprises, LLC'), ('tmobileusa', 'T-Mobile USA, Inc.')],
    'Leasing 2, Inc. (financing); Ten-8 Fire & Safety, LLC (apparatus proposal)': [('leasing2', 'Leasing 2, Inc.'), ('ten8', None)],
    'FUSUS (camera program) / 20 participating businesses': [('fusus', 'FUSUS')],
}
# looked alike, deliberately kept apart (written to the review file with the reason)
KEEP_APART = [
    ('gulfcoastutilityconstruction', 'gulfcoastutilitycontractors', 'Panama City\'s 2024-05-14 agenda awards Bid PC24-019 to "Gulf Coast Utility Construction"; no record ties it to Gulf Coast Utility Contractors, LLC. Probably the same firm, not confirmed.'),
    ('rjgormancontracting', 'rjgormanmarineconstruction', 'Two different LLC names in the agendas. Campaign gifts are matched to whichever name the filing used; "RJ Gorman Construction" (one filing) matches neither and is left unmatched.'),
    ('cwrcontracting', 'cwrobertscontracting', 'CWR Contracting, Inc. (PCB Front Beach Road Segment 3) may be C.W. Roberts Contracting; no source says so.'),
    ('americansandasphaltxcavation', 'americansandasphaltpaving', 'The county register line reads "American Sand & Asphalt / X-Cavation"; it may combine two payees, so it is not added to American Sand and Asphalt Paving.'),
    ('mottmacdonaldconsultants', 'mottmacdonald', '"Mott MacDonald Florida, LLC" and plain "Mott MacDonald" are one vendor (same key once "Florida, LLC" is dropped). "Mott MacDonald Consultants, Inc." is a different legal entity and is kept separate.'),
    ('andersonconstruction', 'andersoncolumbia', 'Anderson Construction Company (of North Florida) is not Anderson Columbia Co., Inc.'),
    ('andersonconstruction', 'andersonconstructioncompanyofnorth', 'Panama City agendas name "Anderson Construction Company of North Florida" (2023) and "Anderson Construction Company" (2026); probably one firm, not confirmed.'),
    ('baypointbillfishopen', 'baypointbillfish', 'Visit PCB paid both "Bay Point Billfish, LLC" and "Bay Point Billfish Open"; the tournament may be a separate account.'),
    ('imageworksc317', 'imageworkscommercialinteriors', 'Lynn Haven warrant list "IMAGEWORKS C317" may be Imageworks Commercial Interiors; not confirmed.'),
    ('royalamericanhospitality', 'royalamericanconstruction', 'Different businesses.'),
    ('keydata', 'keydatadashboard', 'Visit PCB paid "Key Data Dashboard, Inc" and Destination Panama City paid "Key Data"; probably the same data firm, not confirmed.'),
    ('grownfolksentertainment', 'grownfolksentertainmentpromotions', 'Two spellings in the Destination Panama City register; probably one business, not confirmed.'),
    ('publiceyesoar', 'publiceyesoarfestival', 'A company and its festival; may be separate accounts.'),
    ('cdrmaguirecdremergencymanagement', 'cdrmaguire', 'One change order names "CDR Maguire / CDR Emergency Management", which may be two related companies; kept as its own record.'),
    ('robertsfamily', 'robertsroberts', '"Roberts Family, LLC" (a 2026 campaign contributor) is not Roberts and Roberts, Inc.'),
    ('hallscontracting', 'hallcontractingconstruction', '"Halls Contracting" (a campaign filing) may be Hall Contracting & Construction, Inc.; not confirmed, left unmatched.'),
    ('escs', 'ecsc', '"ESCS LLC" (a campaign filing) may be a typo for ECSC, LLC; not confirmed, left unmatched.'),
    ('emeraldcoastcivilconstructi', 'ecsc', '"Emerald Coast Civil Constructi[on]" (a campaign filing) is not the same name as Emerald Coast Site Construction; left unmatched.'),
    ('rjgormanconstruction', 'rjgormanmarineconstruction', '"RJ Gorman Construction" in one campaign filing could be either RJ Gorman company; left unmatched.'),
]
# display names to use instead of the most common spelling
DISPLAY = {'mottmacdonald': 'Mott MacDonald Florida, LLC'}

# public bodies and pass-throughs: not vendors
PUBLIC = re.compile(r'^(dda check|city of |bay county (sheriff|clerk|property|fina|soli|wate|tpo)|panama city (police|beach convention)|lynn haven police|pier park community development|'
                    r'downtown improvement board|front beach cra|florida (department|retirement|agency|sheriffs|medicaid)|internal revenue|local provider participation|'
                    r'sports park fund|united states|u\.s\. (postal|treasury)|department of|mexico beach department|military point awtf|volusia county|general employe)', re.I)


def slug(s):
    s = re.sub(r'\(.*?\)', '', s.lower().replace('&', ' and '))
    toks = re.sub(r'[^a-z0-9 ]', ' ', s).split()
    while len(toks) > 1 and toks[-1] in ids.TRAIL:
        toks = toks[:-1]
    return '-'.join(toks)[:60].strip('-')


def build_vendors():
    recs = [r for r in records.all_records() if r['name']]
    keymap = {}  # key -> group key
    for keys, disp, why in SAME:
        for k in keys:
            keymap[k] = keys[0]
    G = lambda k: keymap.get(k, k)
    clusters = collections.defaultdict(lambda: {'names': collections.Counter(), 'src': collections.Counter(), 'govs': set(), 'keys': set()})
    joint_raw = {}
    skipped = collections.Counter()
    for r in recs:
        n = r['name'].strip()
        if r['src'] == 'cra' and (r['extra'].get('status') == 'Incoming'):
            skipped['cra money in'] += 1; continue
        if n in JOINT:
            joint_raw[n] = []
            for k, disp in JOINT[n]:
                c = clusters[G(k)]; c['keys'].add(k)
                if disp:
                    c['names'][disp] += 0
                c['src'][r['src']] += 1
                if r['gov_id']: c['govs'].add(r['gov_id'])
                joint_raw[n].append(G(k))
            continue
        if records.NOT_NAMED.search(n) or PUBLIC.search(n) or ids.gov_id(n):
            skipped['not a named vendor'] += 1; continue
        k = K(n)
        if len(k) < 3:
            continue
        c = clusters[G(k)]
        c['names'][n] += 1; c['src'][r['src']] += 1; c['keys'].add(k)
        if r['gov_id']: c['govs'].add(r['gov_id'])
    for keys, disp, why in SAME:
        if keys[0] in clusters:
            clusters[keys[0]]['display'] = disp
            clusters[keys[0]]['evidence'] = why
    # campaign spellings: aliases only, never new vendors
    camp = collections.defaultdict(set)
    for d in records.donations():
        k = G(K(d['name']))
        if k in clusters:
            camp[k].add(d['name'].strip())
    # ids
    # site/vendors.py (the Contracts page's company list) is the source of company ids and names: a cluster whose spellings
    # resolve to one company there takes that id. When vendors.py joins two of these clusters, it wins (its merges are
    # hand-reviewed too) and the join is listed in the review file.
    sys.path.insert(0, os.path.join(HERE, '..', '..', 'site'))
    import vendors as SV
    site_id = {}
    for gk, c in clusters.items():
        hits = collections.Counter(SV.resolve(n)[0] for n in c['names'] if SV.key(n) in SV._BY_KEY)
        if hits:
            site_id[gk] = hits.most_common(1)[0][0]
    by_site = collections.defaultdict(list)
    for gk, sid in site_id.items():
        by_site[sid].append(gk)
    merged_by_site = []
    for sid, gks in by_site.items():
        if len(gks) > 1:
            keep = max(gks, key=lambda k: sum(clusters[k]['src'].values()))
            for k in gks:
                if k != keep:
                    c, t = clusters.pop(k), clusters[keep]
                    t['names'].update(c['names']); t['src'].update(c['src']); t['govs'] |= c['govs']; t['keys'] |= c['keys'] | {k}
                    merged_by_site.append({'company': sid, 'joined': [keep, k]})
            for k in gks:
                if k != keep:
                    camp[keep] = camp.get(keep, set()) | camp.pop(k, set())
            site_id = {k: v for k, v in site_id.items() if k in clusters}
    out, used = [], set(SV.VENDORS)
    for gk, c in sorted(clusters.items(), key=lambda kv: -sum(kv[1]['src'].values())):
        names = [n for n, _ in c['names'].most_common()]
        if gk in site_id:
            sid = site_id[gk]
            out.append({'id': sid, 'name': SV.VENDORS[sid][0], 'aliases': sorted(set(names) | camp.get(gk, set()) | {SV.VENDORS[sid][0]}), 'keys': sorted(c['keys'] | {gk}),
                        'records': dict(c['src']), 'gov_ids': sorted(c['govs']), 'site_vendor_type': SV.VENDORS[sid][2],
                        **({'merge_evidence': c['evidence']} if c.get('evidence') else {})})
            continue
        disp = c.get('display') or DISPLAY.get(gk) or _pick_display(c['names'])
        vid = re.sub(r'[^a-z0-9]+', '-', SV.key(names[0])).strip('-') if names else (slug(disp) or gk)  # same id rule as vendors.resolve for unlisted names
        base, i = vid, 2
        while vid in used:
            vid = f'{base}-{i}'; i += 1
        used.add(vid)
        out.append({'id': vid, 'name': disp, 'aliases': sorted(set(names) | camp.get(gk, set()) | {disp}), 'keys': sorted(c['keys'] | {gk}),
                    'records': dict(c['src']), 'gov_ids': sorted(c['govs']), **({'merge_evidence': c['evidence']} if c.get('evidence') else {})})
    by_key = {k: v['id'] for v in out for k in v['keys']}
    joint = {raw: [by_key[k] for k in ks] for raw, ks in joint_raw.items()}
    out.sort(key=lambda v: v['id'])
    # review: look-alikes not joined
    review = {'kept_apart_by_hand': [], 'possible_matches_not_joined': [], 'joined_by_site_vendors_py': merged_by_site, 'joined_by_hand': [{'name': d, 'spellings_joined': ks, 'evidence': w} for ks, d, w in SAME]}
    for a, b, why in KEEP_APART:
        if (a in by_key or a in {K(x['name']) for x in records.donations()}) and b in by_key:
            same = by_key.get(a) == by_key[b]
            review['kept_apart_by_hand'].append({'a': a, 'b': by_key[b], 'a_vendor': by_key.get(a), 'why': why,
                                                 **({'status': 'JOINED anyway by site/vendors.py (the Contracts page company list); a person should confirm or split it there'} if same else {})})
    tok = collections.defaultdict(set)
    for v in out:
        for n in v['aliases']:
            t = re.sub(r'[^a-z0-9 ]', ' ', re.sub(r'\(.*?\)', '', n.lower())).split()
            t = [x for x in t if x not in ('the',)]
            if len(t) >= 2 and len(t[0]) > 2:
                tok[' '.join(t[:2])].add(v['id'])
    apart = {(by_key.get(a), by_key.get(b)) for a, b, _ in KEEP_APART} | {(by_key.get(b), by_key.get(a)) for a, b, _ in KEEP_APART}
    GENERIC = {'bay county', 'panama city', 'gulf coast', 'emerald coast', 'mexico beach', 'florida state', 'city of', 'department of', 'united states', 'u s', 'st andrews', 'bay high', 'pier park', 'north florida'}
    for t, vs in sorted(tok.items()):
        if len(vs) > 1 and t not in GENERIC:
            vs = sorted(vs)
            if any((x, y) in apart for x in vs for y in vs if x != y):
                continue
            review['possible_matches_not_joined'].append({'shared_words': t, 'vendors': vs, 'names': {x: next(v['name'] for v in out if v['id'] == x) for x in vs}})
    return {'about': 'One record per vendor (business or organization paid by a Bay County government, CRA or tourism agency). aliases are every spelling found in contracts, change orders, '
                     'emergency purchases, check registers (including 15-character truncations), TDC payments, the CRA ledger and business campaign contributions. Built by data/entities/build_entities.py; '
                     'hand-reviewed joins carry merge_evidence. Look-alike names that were not joined are in vendor_review.json.',
            'count': len(out), 'vendors': out, 'joint': joint, 'skipped': dict(skipped)}, review


def _pick_display(names):
    """Most-used spelling, preferring one with a legal suffix and normal capitalization (register OCR is all caps and cut short)."""
    def score(n):
        cnt = names[n]
        return (not n.isupper(), bool(re.search(r'\b(inc|llc|co|corp|company|lp)\b\.?', n, re.I)), cnt, len(n))
    best = max(names, key=score)
    return ids.biz_case(re.sub(r'\s*\((bid awarded|consultant|buyer|camera|program)[^)]*\)', '', best).strip())


# ---- people: elected officials, department leaders and 2026 candidates only ----
def _j(*p):
    try:
        return json.load(open(os.path.join(HERE, '..', *p)))
    except FileNotFoundError:
        return None


def _clean_person(n):
    n, dist = ids.split_district(n)
    n = re.sub(r'\s*\((?!chuck\)|bob\))[^)]*\)', '', n, flags=re.I).strip()  # drop notes like "(Vice Chairman ...)", keep "William (Chuck) Perdue"
    n = re.sub(r'\s*\((serving since|appointed|not seeking|FY\d|stepped down)[^)]*\)', '', n).strip()
    return n, dist


# hand-checked: different name keys that are one person (key, key, evidence)
SAME_PERSON = [
    (('william', 'perdue'), ('charles', 'perdue'), 'Tax Collector William (Chuck) Perdue; the salary file lists "Chuck Perdue".'),
]


def build_people():
    seen = []  # (raw name, role dict)
    v = _j('votes', 'votes.json')
    govb = lambda b: next((k for k, p in (('county', 'bay-'), ('pcb', 'pcb-'), ('pc', 'pc-'), ('lh', 'lh-'), ('cw', 'cw-'), ('sp', 'sp-'), ('parker', 'parker-'), ('mb', 'mb-'), ('schools', 'bds-')) if b.startswith(p)), None)
    for b in v['bodies']:
        mem = b['members'] if isinstance(b['members'], list) else []
        for m in mem:
            seen.append((m['name'], {'role': 'board member', 'gov_id': govb(b['id']), 'seat': m.get('seat'), 'source': 'votes'}))
        for m in b.get('former_members_in_period') or []:
            nm = re.sub(r'\s*\(.*$', '', m)
            seat = (re.search(r'\(([^,)]+)', m) or [None, None])[1]
            seen.append((nm, {'role': 'former board member', 'gov_id': govb(b['id']), 'seat': seat, 'source': 'votes'}))
    for x in v['votes']:
        for n in (x.get('by_member') or {}):
            seen.append((n, {'role': 'board member', 'gov_id': govb(x['body']), 'source': 'votes'}))
    import glob
    for fp in sorted(glob.glob(os.path.join(HERE, '..', 'salaries', '*.json'))):
        d = json.load(open(fp))
        for r in d.get('leaders') or []:
            if r.get('name'):
                seen.append((r['name'], {'role': r.get('title'), 'gov_id': ids.gov_id(d.get('employer_id')) or ids.gov_id(d.get('employer')), 'source': 'salaries'}))
    f = _j('fees', 'fees_pay_officials.json')
    for r in f['pay']:
        if r.get('name'):
            seen.append((r['name'], {'role': r.get('title'), 'gov_id': ids.gov_id(r.get('title')) if ids.gov(ids.gov_id(r.get('title')) or '') and ids.gov(ids.gov_id(r.get('title')))['kind'] == 'constitutional' else ids.gov_id(r.get('government')), 'source': 'officials-pay'}))
    c = _j('campaign', 'campaign.json')
    for r in c['candidates']:
        seen.append((r['official'], {'role': 'officeholder: ' + (r.get('office') or ''), 'gov_id': ids.gov_id(r.get('office'), contains=True) or ids.gov_id(r.get('gov')), 'source': 'campaign'}))
    fin = _j('elections', 'finance_2026.json')
    for r in fin['candidates']:
        seen.append((r['name'], {'role': '2026 candidate: ' + (r.get('office') or ''), 'gov_id': ids.gov_id(r.get('office'), contains=True), 'source': 'finance_2026'}))
    # every other local candidate since 2016 (data/campaign/campaign_history.json), winners and losers
    hist = _j('campaign', 'campaign_history.json') or {'candidates': []}
    for r in hist['candidates']:
        seen.append((r['name'], {'role': f"{r['year']} candidate: {r['office']}", 'gov_id': r.get('gov_id'), 'office': r['office'], 'year': r['year'],
                                 'outcome': r.get('outcome'), 'source': 'campaign_history'}))
    cand = _j('elections', 'candidates_2026.json')
    for race in cand['races']:
        for k in race.get('candidates') or []:
            seen.append((k['name'], {'role': '2026 candidate: ' + race['office'], 'gov_id': ids.gov_id(race['office'], contains=True) or race.get('gov'), 'source': 'candidates_2026'}))
    # every elected officeholder and appointed manager since 2014, current and former (data/civic/officeholders.json)
    oh = _j('civic', 'officeholders.json')
    for g in oh['governments']:
        for st in g['seats']:
            for t in st['terms']:
                if t.get('name'):
                    member = {'Board of County Commissioners': 'County commissioner', 'City Commission': 'City commissioner', 'City Council': 'Council member'}.get(g['body'], 'School board member')
                    office = st['seat'].split(' (')[0] if st.get('appointed') or st['seat'].startswith(('Mayor', 'Superintendent')) else f"{member}, {st['seat']}"
                    a, b = (t.get('start') or '')[:4], (t.get('end') or '')[:4]
                    seen.append((t['name'], {'role': ('former ' + (office.lower() if st.get('appointed') else office[0].lower() + office[1:])) if b else office, 'gov_id': g['gov_id'], 'seat': st['seat'],
                                             'years': f'{a}–{b}' if a and b else f'until {b}' if b else f'since {a}' if a else 'since before 2015', 'source': 'officeholders'}))
    join = {}
    for a, b, _ in SAME_PERSON:
        join[b] = a
    groups = collections.defaultdict(lambda: {'names': collections.Counter(), 'roles': [], 'districts': set(), 'govs': set()})
    for raw, role in seen:
        nm, dist = _clean_person(raw)
        keys = sorted(ids.person_alt_keys(nm))
        if not keys:
            continue
        k = join.get(ids.person_key(nm), ids.person_key(nm))
        g = groups[k]
        g['names'][nm] += 1
        if dist:
            g['districts'].add(dist)
        if role.get('gov_id'):
            g['govs'].add(role['gov_id'])
        r = {kk: vv for kk, vv in role.items() if vv}
        if r not in g['roles']:
            g['roles'].append(r)
    out, used, review = [], set(), []
    for k, g in groups.items():
        # display: the spelling seen most often; ties go to the one without a middle initial
        disp = max(g['names'], key=lambda n: (g['names'][n], -len(n)))
        toks = [t for t in re.sub(r'\([^)]*\)', ' ', disp.lower()).replace('.', ' ').replace(',', ' ').split() if t not in ('dr', 'jr', 'sr', 'ii', 'iii') and len(t) > 1]
        pid = re.sub(r'[^a-z0-9]+', '-', ' '.join(toks)).strip('-')
        base, i = pid, 2
        while pid in used:
            pid = f'{base}-{i}'; i += 1
        used.add(pid)
        if len(g['govs']) > 1 and not ({'county', 'schools'} >= g['govs']):
            review.append({'person_id': pid, 'governments': sorted(g['govs']), 'names': sorted(g['names'])})
        out.append({'id': pid, 'name': disp, 'aliases': sorted(g['names']), 'district': sorted(g['districts'])[0] if len(g['districts']) == 1 else (sorted(g['districts']) or None),
                    'gov_ids': sorted(g['govs']), 'roles': g['roles']})
    out.sort(key=lambda p: p['id'])
    return {'about': 'Elected officials, department leaders, 2026 local candidates and local candidates since 2016 named in the site\'s datasets, one id per person. Names are matched on first and last name with common nicknames '
                     '(Doug = Douglas, Chris = Christopher, Dave = David ...), ignoring middle initials, titles and notes in parentheses; "(D2)" style suffixes become the district field. '
                     'People who appear under more than one government are listed in multi_government for checking. No other people are included.',
            'count': len(out), 'people': out, 'same_person_by_hand': [{'keys': [list(a), list(b)], 'why': w} for a, b, w in SAME_PERSON], 'multi_government': review}


def main():
    p = build_people()
    json.dump(p, open(os.path.join(HERE, 'people.json'), 'w'), indent=1, ensure_ascii=False)
    print('people:', p['count'], 'multi-government:', len(p['multi_government']))
    v, rev = build_vendors()
    json.dump(v, open(os.path.join(HERE, 'vendors.json'), 'w'), indent=1, ensure_ascii=False)
    json.dump(rev, open(os.path.join(HERE, 'vendor_review.json'), 'w'), indent=1, ensure_ascii=False)
    ids.reset()
    print('vendors:', v['count'], 'joint names:', len(v['joint']), 'skipped:', v['skipped'], 'review pairs:', len(rev['possible_matches_not_joined']))


if __name__ == '__main__':
    main()
