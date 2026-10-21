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
    (['southeasternoutdoormanagement', 'southeasternoutdoormet', 'southeasternoutdoormgmt'], 'Southeastern Outdoor Management',
     '"Southeastern Outdoor Met Inc" is how the scanned Visit PCB register reads; "Southeastern Outdoor Mgmt" is a campaign filing.'),
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
    out, used = [], set()
    for gk, c in sorted(clusters.items(), key=lambda kv: -sum(kv[1]['src'].values())):
        names = [n for n, _ in c['names'].most_common()]
        disp = c.get('display') or DISPLAY.get(gk) or _pick_display(c['names'])
        vid = slug(disp) or gk
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
    review = {'kept_apart_by_hand': [], 'possible_matches_not_joined': [], 'joined_by_hand': [{'name': d, 'spellings_joined': ks, 'evidence': w} for ks, d, w in SAME]}
    for a, b, why in KEEP_APART:
        if (a in by_key or a in {K(x['name']) for x in records.donations()}) and b in by_key:
            review['kept_apart_by_hand'].append({'a': a, 'b': by_key[b], 'a_vendor': by_key.get(a), 'why': why})
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
    return re.sub(r'\s*\((bid awarded|consultant|buyer|camera|program)[^)]*\)', '', best).strip()


def main():
    v, rev = build_vendors()
    json.dump(v, open(os.path.join(HERE, 'vendors.json'), 'w'), indent=1, ensure_ascii=False)
    json.dump(rev, open(os.path.join(HERE, 'vendor_review.json'), 'w'), indent=1, ensure_ascii=False)
    ids.reset()
    print('vendors:', v['count'], 'joint names:', len(v['joint']), 'skipped:', v['skipped'], 'review pairs:', len(rev['possible_matches_not_joined']))


if __name__ == '__main__':
    main()
