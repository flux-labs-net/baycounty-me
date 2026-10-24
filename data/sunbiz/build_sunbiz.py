"""Link county residents to the businesses they run, and business campaign gifts to those businesses.

Inputs (per county, from sunbiz_filter.py): data/sunbiz/<county>/entities.csv.gz and officers.csv.gz.
Gifts: business contributors in data/campaign/campaign.json and data/elections/finance_2026.json (records.donations()).

Steps
  1. People. Every officer/manager and every registered agent who is a person is grouped into one person when the
     name (last + first) and the address (ZIP + street, units dropped) match, or when the full name with middle
     initial matches inside the same ZIP. People listed on 25+ active entities are flagged as corporate officers
     (subsidiary boards, not owners); registered agents on 20+ entities they don't run are flagged as agent services
     and never link businesses.
  2. Donor match. Each business contributor name is matched to a Sunbiz entity: exact name after removing punctuation
     and legal suffixes, then a hand-checked vendor alias (data/entities/vendors.json), then a unique prefix match for
     names the filing cut off, then data/sunbiz/donor_overrides.json. A dissolved entity counts only if it was still
     filing around the gift (last annual report no more than 2 years before it).
  3. Shared owners. For each candidate, a person whose 2 or more matched businesses gave is a finding. Co-owners
     listed on the same set of businesses form one group, identified by an opaque id.

Outputs
  build() returns everything (people with names, for the private `registry` schema; see db/scripts/load_registry.py).
  main() writes only the business-level public file data/sunbiz/<county>/business_donor_sunbiz.json: no person names.
"""
import collections, csv, datetime, gzip, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'data', 'entities'))
from counties import county  # noqa: E402
from ids import sunbiz_person  # noqa: E402

CORPORATE_OFFICER_MIN = 25   # active entities
AGENT_SERVICE_MIN = 20       # entities as registered agent
STALE_YEARS = 2

SUFFIX = r'(L ?L ?C|L ?L ?P|L ?P|P ?L ?L ?C|P ?L|P ?A|L ?T ?D|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LIMITED|LC|PC|N ?A)'
STREET_ABBR = {'STREET': 'ST', 'AVENUE': 'AVE', 'AV': 'AVE', 'DRIVE': 'DR', 'ROAD': 'RD', 'BOULEVARD': 'BLVD', 'LANE': 'LN',
               'COURT': 'CT', 'CIRCLE': 'CIR', 'PLACE': 'PL', 'PARKWAY': 'PKWY', 'HIGHWAY': 'HWY', 'TERRACE': 'TER', 'TRAIL': 'TRL',
               'NORTH': 'N', 'SOUTH': 'S', 'EAST': 'E', 'WEST': 'W', 'COVE': 'CV', 'POINT': 'PT', 'WAY': 'WAY', 'LOOP': 'LOOP'}
UNIT = re.compile(r'\b(SUITE|STE|UNIT|APT|APARTMENT|BLDG|BUILDING|FLOOR|FL|RM|ROOM|LOT|SPC|SPACE)\b\.?\s*\S*|#\s*\S+')
NAME_SUFFIX = {'JR', 'SR', 'II', 'III', 'IV', 'MD', 'DDS', 'ESQ', 'CPA', 'PA', 'DMD', 'PHD'}


def _clean(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^A-Z0-9 ]', ' ', (s or '').upper())).strip()


def biz_key(name):
    """Business name for matching: upper case, & -> AND, no punctuation, no legal suffixes, no leading THE."""
    s = (name or '').upper().replace('&', ' AND ').replace('+', ' AND ')
    s = re.split(r'\b(D/B/A|DBA|D B A|A/K/A|AKA)\b', s)[0]
    s = re.sub(r"[.,']", '', s)
    s = _clean(s)
    s = re.sub(r'^THE ', '', s)
    for _ in range(2):
        s = re.sub(r'\s+' + SUFFIX + r'$', '', s).strip()
    return s


def loose_key(name):
    """biz_key with plurals and possessives folded (RESTAURANTS -> RESTAURANT, HOLDING -> HOLDINGS both -> HOLDING)."""
    return ' '.join(w[:-1] if len(w) > 3 and w.endswith('S') and not w.endswith('SS') else w for w in biz_key(name).split())


def dba_part(name):
    m = re.split(r'\b(?:D/B/A|DBA|D B A)\b', (name or '').upper(), maxsplit=1)
    return biz_key(m[1]) if len(m) > 1 else None


def street_key(addr):
    s = UNIT.sub(' ', (addr or '').upper())
    s = _clean(s)
    return ' '.join(STREET_ABBR.get(w, w) for w in s.split())


def zip5(z):
    z = (z or '').strip()
    return z[:5] if len(z) >= 5 and z[:5].isdigit() else ''


def split_name(raw):
    """Sunbiz person names are fixed width: last (20), first (14), middle. Free-text names fall back to word order.
    Returns ('LAST FIRST' without suffixes, middle initial)."""
    last, first, mid = split_name_parts(raw)
    words = [w for w in (last + ' ' + first).split() if w not in NAME_SUFFIX]
    return ' '.join(words), mid


def split_name_parts(raw):
    """(last, first, middle initial), upper case, punctuation removed."""
    raw = (raw or '').rstrip()
    if len(raw) > 20 and raw[:20].strip() and ' ' not in raw[:20].strip() or re.search(r'\S\s{2,}\S', raw):
        last, first, middle = raw[:20].strip(), raw[20:34].strip(), raw[34:].strip()
        if not first:  # unpadded name longer than 20 chars
            parts = re.split(r'\s{2,}', raw.strip())
            last, first, middle = (parts + ['', ''])[:3]
    else:
        parts = raw.strip().split()
        if ',' in raw:  # "SMITH, JOHN A"
            a, b = raw.split(',', 1)
            parts2 = b.split()
            last, first, middle = a.strip(), (parts2[0] if parts2 else ''), ' '.join(parts2[1:])
        elif len(parts) >= 2:  # "JOHN A SMITH"
            first, last, middle = parts[0], parts[-1], ' '.join(parts[1:-1])
        else:
            last, first, middle = raw.strip(), '', ''
    last, first = _clean(last), _clean(first)
    mid = _clean(middle)
    mid = mid.split()[0][:1] if mid and mid.split()[0] not in NAME_SUFFIX else ''
    return last, first, mid


def looks_like_org(name):
    return bool(re.search(r'\b(LLC|L\.L\.C|INC|CORP|COMPANY|TRUST|PARTNERSHIP|HOLDINGS|SERVICES|GROUP|ASSOCIATION|BANK|LP|LTD|PA|FOUNDATION|CHURCH|FUND)\b',
                          (name or '').upper()))


def _rows(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
        yield from csv.DictReader(f)


def _date(mmddyyyy):
    s = (mmddyyyy or '').strip()
    if len(s) == 8 and s.isdigit():
        try:
            return datetime.date(int(s[4:]), int(s[:2]), int(s[2:4]))
        except ValueError:
            return None
    return None


class UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def load_registry(county_key='bay'):
    d = os.path.join(HERE, county_key)
    c = county(county_key)
    entities = {}
    for r in _rows(os.path.join(d, 'entities.csv.gz')):
        reports = [int(r['report_year_1'])] if (r.get('report_year_1') or '').isdigit() else []
        entities[r['doc_number']] = {
            'doc_number': r['doc_number'], 'name': r['name'], 'key': biz_key(r['name']), 'status': r['status'],
            'filing_type': r['filing_type'], 'file_date': _date(r['file_date']), 'last_report_year': max(reports) if reports else None,
            'last_txn_date': _date(r['last_txn_date']), 'city': (r['city'] or '').upper().strip(), 'zip5': zip5(r['zip']),
            'nonprofit': r['filing_type'] in ('DOMNP', 'FORNP', 'NPREG'), 'in_county_principal': zip5(r['zip']) in c['zips'],
            'ra': (r['ra_name'], r['ra_type'], r['ra_addr'], r['ra_city'], r['ra_zip']),
        }
    roles = []  # one row per person-type officer / registered agent appearance
    for r in _rows(os.path.join(d, 'officers.csv.gz')):
        if r['doc_number'] not in entities:
            continue
        is_person = r['type'] == 'P' and not looks_like_org(r['name'])
        roles.append({'doc_number': r['doc_number'], 'role': 'officer', 'title': (r['title'] or '').strip(), 'raw_name': r['name'].strip(),
                      'is_person': is_person, 'street': street_key(r['addr']), 'city': (r['city'] or '').upper().strip(),
                      'zip5': zip5(r['zip'])})
    for e in entities.values():
        name, typ, addr, city, z = e.pop('ra')
        if not name:
            continue
        is_person = typ == 'P' and not looks_like_org(name)
        roles.append({'doc_number': e['doc_number'], 'role': 'registered_agent', 'title': 'RA', 'raw_name': name.strip(), 'is_person': is_person,
                      'street': street_key(addr), 'city': (city or '').upper().strip(), 'zip5': zip5(z)})
    return entities, roles


def group_people(entities, roles, county_key='bay'):
    """Assign person_key to each person role; return people dict."""
    c = county(county_key)
    uf = UF()
    for i, r in enumerate(roles):
        if not r['is_person']:
            continue
        name, mid = split_name(r['raw_name'])
        if not name or len(name.split()) < 2:
            r['is_person'] = False
            continue
        r['name_key'], r['mid'] = name, mid
        a = ('A', name, r['zip5'], r['street'])
        uf.union(('R', i), a)
        if mid and r['zip5']:
            uf.union(('R', i), ('M', name, mid, r['zip5']))
    groups = collections.defaultdict(list)
    for i, r in enumerate(roles):
        if r.get('name_key'):
            groups[uf.find(('R', i))].append(i)
    people = {}
    for members in groups.values():
        rs = [roles[i] for i in members]
        names = collections.Counter(r['raw_name'] for r in rs)
        key_src = sorted({(r['name_key'], r['zip5'], r['street']) for r in rs})[0]
        pkey = 'p_' + hashlib.sha1(('|'.join(key_src) + '|' + county_key).encode()).hexdigest()[:12]
        docs_off = {r['doc_number'] for r in rs if r['role'] == 'officer'}
        docs_ra = {r['doc_number'] for r in rs if r['role'] == 'registered_agent'}
        active_off = {dn for dn in docs_off if entities[dn]['status'] == 'A'}
        cities = collections.Counter(r['city'] for r in rs if r['city'])
        zips = collections.Counter(r['zip5'] for r in rs if r['zip5'])
        people[pkey] = {
            'person_key': pkey, 'county': county_key, 'raw_name': names.most_common(1)[0][0],
            'display_name': sunbiz_person(names.most_common(1)[0][0]), 'name_key': rs[0]['name_key'],
            'city': cities.most_common(1)[0][0] if cities else '', 'zip5': zips.most_common(1)[0][0] if zips else '',
            'resident': any(r['zip5'] in c['zips'] for r in rs),
            'address_hash': hashlib.sha1(('|'.join(key_src)).encode()).hexdigest()[:16],
            'entities_as_officer': len(docs_off), 'active_entities_as_officer': len(active_off), 'entities_as_agent': len(docs_ra),
            'corporate_officer': len(active_off) >= CORPORATE_OFFICER_MIN,
            'agent_service': len(docs_ra - docs_off) >= AGENT_SERVICE_MIN,
        }
        for r in rs:
            r['person_key'] = pkey
    return people


def owners_of(roles, people):
    """doc_number -> {person_key: set(titles)} for links that count as running the business."""
    out = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in roles:
        pk = r.get('person_key')
        if not pk:
            continue
        p = people[pk]
        if r['role'] == 'registered_agent' and p['agent_service']:
            continue
        out[r['doc_number']][pk].add(r['title'] or r['role'])
    return out


def _gift_year(g):
    try:
        return int(str(g.get('date'))[:4])
    except (TypeError, ValueError):
        return None


def _usable(e, year):
    """An entity can be the donor if it's active, or was still filing around the gift year."""
    if year is None or e['status'] == 'A':
        return True
    last = e['last_report_year'] or (e['last_txn_date'].year if e['last_txn_date'] else None) or (e['file_date'].year if e['file_date'] else None)
    if e['file_date'] and e['file_date'].year > year + 1:
        return False
    return last is not None and last >= year - STALE_YEARS


def _pick(cands, year):
    cands = [e for e in cands if _usable(e, year)]
    if not cands:
        return None
    cands.sort(key=lambda e: (e['status'] != 'A', not e['in_county_principal'], e['nonprofit'], -(e['last_report_year'] or 0)))
    return cands[0]


def match_donors(entities, gifts, overrides=None):
    by_key, by_loose = collections.defaultdict(list), collections.defaultdict(list)
    for e in entities.values():
        if e['key']:
            by_key[e['key']].append(e)
            by_loose[loose_key(e['name'])].append(e)
    keys_sorted = sorted(by_key)
    import bisect
    try:
        import ids
    except Exception:  # entities tables not available (tests)
        ids = None
    overrides = overrides or {}
    cache = {}
    out = []
    for g in gifts:
        name = g['name'].strip()
        year = _gift_year(g)
        ck = (name, year)
        if ck not in cache:
            hit, how = None, None
            if name in overrides:
                dn = overrides[name]
                hit, how = (entities.get(dn), 'reviewed') if dn else (None, 'reviewed_no_match')
            else:
                k = biz_key(name)
                if k in by_key:
                    hit, how = _pick(by_key[k], year), 'exact'
                if not hit and dba_part(name) and dba_part(name) in by_key:
                    hit, how = _pick(by_key[dba_part(name)], year), 'exact'
                if not hit and ids is not None:
                    vid = ids.vendor_id(name)
                    v = ids.vendor(vid) if vid else None
                    for alt in ([v['name']] + list(v.get('aliases') or [])) if v else []:
                        ak = biz_key(alt)
                        if ak != k and ak in by_key:
                            hit = _pick(by_key[ak], year)
                            if hit:
                                how = 'vendor_alias'
                                break
                if not hit and loose_key(name) in by_loose:
                    lo = [e for e in by_loose[loose_key(name)] if _usable(e, year)]
                    if len({e['key'] for e in lo}) == 1:
                        hit, how = _pick(lo, year), 'plural_variant'
                if not hit and len(k) >= 16:
                    i = bisect.bisect_left(keys_sorted, k)
                    pre = []
                    while i < len(keys_sorted) and keys_sorted[i].startswith(k):
                        pre.extend(e for e in by_key[keys_sorted[i]] if _usable(e, year))
                        i += 1
                    if len({e['key'] for e in pre}) == 1:
                        hit, how = _pick(pre, year), 'truncated_name'
            cache[ck] = (hit, how if hit else (how if how == 'reviewed_no_match' else None))
        hit, how = cache[ck]
        out.append(dict(g, doc_number=hit['doc_number'] if hit else None, match_method=how))
    return out


def gov_for(g):
    if g.get('gov'):
        return g['gov']
    try:
        import ids
        return ids.gov_id(g.get('office') or '', contains=True)
    except Exception:
        return None


def dedupe_gifts(gifts):
    """A 2026 candidate who is also a current officeholder appears in both files: keep one copy of each item."""
    seen, out = set(), []
    for g in gifts:
        k = (g['candidate'], g['name'].strip().upper(), g.get('amount'), g.get('date'))
        if k in seen:
            continue
        seen.add(k)
        out.append(g)
    return out


def shared_owner_findings(matched, entities, owners, people):
    """Per candidate: businesses that gave and share at least one person (officer/manager or registered agent who is a
    person, corporate officers left out) are joined into one group; a group of 2+ businesses is a finding.
    Each business and each check is counted once, however many people link it."""
    per = collections.defaultdict(lambda: collections.defaultdict(list))  # cand -> doc -> gifts
    for g in matched:
        if g['doc_number'] and (g.get('amount') or 0) > 0:
            per[g['candidate']][g['doc_number']].append(g)
    findings = []
    for cand, docs in per.items():
        uf = UF()
        links = collections.defaultdict(set)  # person -> docs
        for dn in docs:
            uf.find(dn)
            for pk in owners.get(dn, {}):
                if not people[pk]['corporate_officer']:
                    links[pk].add(dn)
        for pk, ds in links.items():
            ds = sorted(ds)
            for other in ds[1:]:
                uf.union(ds[0], other)
        comps = collections.defaultdict(set)
        for dn in docs:
            comps[uf.find(dn)].add(dn)
        for ds in comps.values():
            if len(ds) < 2:
                continue
            bridging = sorted(pk for pk, d2 in links.items() if len(d2 & ds) >= 2)
            gifts = [g for dn in ds for g in docs[dn]]
            amounts = [g['amount'] for g in gifts]
            first = gifts[0]
            gid = 'g_' + hashlib.sha1(('|'.join(sorted(ds))).encode()).hexdigest()[:10]
            findings.append({
                'group_id': gid, 'candidate': cand, 'office': first.get('office'), 'government_key': gov_for(first), 'election': first.get('election'),
                'person_keys': bridging, 'n_people': len(bridging),
                'max_businesses_one_person': max(len(links[pk] & ds) for pk in bridging),
                'businesses': sorted(({'doc_number': dn, 'entity_name': entities[dn]['name'], 'status': entities[dn]['status'],
                                       'filed_as': sorted({g['name'].strip() for g in docs[dn]}),
                                       'amount': round(sum(g['amount'] for g in docs[dn]), 2),
                                       'dates': sorted({str(g['date']) for g in docs[dn] if g.get('date')}),
                                       'people': sorted(pk for pk in bridging if dn in links[pk])} for dn in ds), key=lambda b: b['entity_name']),
                'n_businesses': len(ds), 'n_checks': len(gifts), 'combined_amount': round(sum(amounts), 2),
                'all_at_1000': all(abs(a - 1000) < 0.01 for a in amounts),
                'same_day': len({str(g['date']) for g in gifts}) == 1,
                'report_url': first.get('report_url'),
            })
    findings.sort(key=lambda f: (-f['combined_amount'], f['candidate']))
    return findings


def build(county_key='bay', gifts=None):
    entities, roles = load_registry(county_key)
    people = group_people(entities, roles, county_key)
    owners = owners_of(roles, people)
    if gifts is None:
        import records
        gifts = records.donations()
    gifts = dedupe_gifts(gifts)
    ov_path = os.path.join(HERE, 'donor_overrides.json')
    overrides = json.load(open(ov_path)).get('overrides', {}) if os.path.exists(ov_path) else {}
    matched = match_donors(entities, gifts, overrides)
    findings = shared_owner_findings(matched, entities, owners, people)
    return {'entities': entities, 'roles': roles, 'people': people, 'owners': owners, 'gifts': matched, 'findings': findings}


def public_rows(res, county_key='bay'):
    """Business-only rows: one per contributor spelling and candidate. No person names, no addresses."""
    agg = collections.OrderedDict()
    for g in res['gifts']:
        k = (g['name'].strip(), g['candidate'])
        a = agg.setdefault(k, {'g': g, 'amount': 0.0, 'n': 0, 'dates': set()})
        a['amount'] += g.get('amount') or 0
        a['n'] += 1
        if g.get('date'):
            a['dates'].add(str(g['date']))
    rows = []
    for (name, cand), a in agg.items():
        g = a['g']
        e = res['entities'].get(g['doc_number']) if g['doc_number'] else None
        rows.append({
            'contributor': name, 'candidate': cand, 'office': g.get('office'), 'election': g.get('election'), 'gov_id': gov_for(g),
            'contribution_amount': round(a['amount'], 2), 'contribution_items': a['n'],
            'first_date': min(a['dates']) if a['dates'] else None, 'last_date': max(a['dates']) if a['dates'] else None,
            'sunbiz_doc_number': e['doc_number'] if e else None, 'sunbiz_entity_name': e['name'] if e else None,
            'sunbiz_status': ({'A': 'Active', 'I': 'Inactive'}.get(e['status'], e['status']) if e else None),
            'sunbiz_filing_type': e['filing_type'] if e else None, 'sunbiz_principal_city': e['city'].title() if e else None,
            'match_method': g['match_method'], 'county': county_key,
            'source_url': ('https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResultDetail?inquirytype=DocumentNumber&directionType=Initial&searchTerm='
                           + e['doc_number']) if e else g.get('report_url'),
            'campaign_report_url': g.get('report_url'),
        })
    rows.sort(key=lambda r: (r['candidate'], r['contributor']))
    return rows


def summary(res):
    gifts = res['gifts']
    lines = [g for g in gifts if (g.get('amount') or 0) > 0]
    m = [g for g in lines if g['doc_number']]
    multi = [p for p in res['people'].values() if p['resident'] and p['active_entities_as_officer'] >= 2]
    return {
        'entities': len(res['entities']), 'active_entities': sum(1 for e in res['entities'].values() if e['status'] == 'A'),
        'people': len(res['people']), 'resident_people': sum(1 for p in res['people'].values() if p['resident']),
        'residents_on_2plus_active': len(multi),
        'corporate_officers': sum(1 for p in res['people'].values() if p['corporate_officer']),
        'agent_services': sum(1 for p in res['people'].values() if p['agent_service']),
        'business_gift_lines': len(lines), 'matched_lines': len(m),
        'matched_entities': len({g['doc_number'] for g in m}),
        'match_methods': dict(collections.Counter(g['match_method'] for g in m)),
        'shared_owner_groups': len(res['findings']),
        'shared_owner_people': len({pk for f in res['findings'] for pk in f['person_keys']}),
        'shared_owner_candidates': len({f['candidate'] for f in res['findings']}),
        'shared_owner_dollars': round(sum(f['combined_amount'] for f in res['findings']), 2),
        'groups_all_at_1000': sum(1 for f in res['findings'] if f['all_at_1000']),
    }


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else 'bay'
    res = build(key)
    out = {
        'as_of': datetime.date.today().isoformat(), 'county': key,
        'method': ('Business contributors to current officeholders and 2026 local candidates, matched to the Florida Division of Corporations (Sunbiz) '
                   'quarterly corporate file filtered to ' + county(key)['name'] + ' (any principal, mailing, registered-agent or officer address in the county). '
                   'exact = same name once punctuation and legal suffixes are removed; vendor_alias = a hand-checked spelling join in data/entities/vendors.json; '
                   'plural_variant = same name apart from plurals/possessives; truncated_name = the filing cut the name off and only one entity starts with it; reviewed = checked by hand (donor_overrides.json). '
                   'A dissolved company counts only if it was still filing within 2 years of the gift. A match says the filed name is that registered entity; '
                   'it says nothing about why a gift was made. Built by data/sunbiz/build_sunbiz.py.'),
        'summary': {k: v for k, v in summary(res).items() if not k.startswith('shared_owner') and k != 'groups_all_at_1000'},
        'rows': public_rows(res, key),
    }
    json.dump(out, open(os.path.join(HERE, key, 'business_donor_sunbiz.json'), 'w'), indent=1, ensure_ascii=False, default=str)
    print('sunbiz:', json.dumps(summary(res)))


if __name__ == '__main__':
    main()
