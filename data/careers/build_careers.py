"""Officials' and candidates' business ties, from public records: which registered businesses each elected official,
department leader and local candidate is listed on (Florida Division of Corporations), and how those businesses touch
campaigns and public money.

Inputs
  - data/entities/people.json: the officials, department leaders and candidates the site already names.
  - data/sunbiz/build_sunbiz.build(): the county's Sunbiz entities, officers/agents grouped into people, and business
    campaign gifts matched to entities.
  - data/entities/records.all_records(): every contract, change order, check-register and payment row naming a payee.

Steps
  1. Match. Each named official is paired with every Sunbiz person whose first name (nicknames folded: Chris =
     Christopher) and last name match. A pair is scored: lives or does business in the county (+2), Sunbiz city is in the
     official's own city (+2) or elsewhere in the county for a countywide office (+1), same first name without folding a
     nickname (+1), the only Sunbiz person with that name (+1), listed as an officer of 25+ active companies (a corporate
     board seat, not a local owner: -3). high >= 5, medium 3-4, low <= 2. A name match is a lead: an admin confirms
     each pair before anything is public.
  2. Roles. For each pair, the businesses that person is an officer, manager or registered agent of, with the entity's
     filing date (the role began on or after it) and, for a dissolved entity, its last annual report year (the role
     ended by then; the year of its last filing, usually the dissolution, when later). Sunbiz lists current officers only, so earlier officers are not visible; the loader keeps a
     first-seen / last-seen date for every role from now on (careers.role_seen).
  3. Links between those businesses and public life:
     - shared_business: two named officials or candidates are listed on the same business.
     - own_business_gift: an official's or candidate's business gave to a campaign (their own or someone else's).
     - partner_business_gift: a business that gave to a candidate shares an officer or agent with one of that
       candidate's own businesses (the shared person is never named publicly, only counted).
     - public_payee: an official's or candidate's business was paid by a local government (contract, change order,
       check register, tourism or CRA payment); own_government is true when it is the government the person serves.
     Each link lists the official/Sunbiz pairs it depends on (requires); it is published only once all are confirmed.

Outputs: build() for db/scripts/load_careers.py. Nothing here is written to a public file: names of people who are not
officials or candidates never leave the private `careers` / `registry` schemas.
"""
import collections, datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'data', 'sunbiz'))
sys.path.insert(0, os.path.join(ROOT, 'data', 'entities'))
import build_sunbiz  # noqa: E402
import ids  # noqa: E402

HIGH, MEDIUM = 5, 3
COUNTYWIDE = {'county', 'schools', 'sheriff', 'clerk', 'property_appraiser', 'tax_collector', 'soe', 'county_court', 'airport', 'port'}


def sunbiz_key(raw):
    """(first, last) for a Sunbiz person name, the same shape as ids.person_key()."""
    last, first, _ = build_sunbiz.split_name_parts(raw)
    lw = [w for w in last.lower().split() if w.upper() not in build_sunbiz.NAME_SUFFIX and len(w) > 1]
    fw = [w for w in first.lower().split() if len(w) > 1]
    if not lw or not fw:
        return None, None
    f = fw[0]
    return (ids.NICK.get(f, f), lw[-1]), f


def official_first_names(p):
    out = set()
    for a in [p['name']] + list(p.get('aliases') or []):
        s = re.sub(r'\([^)]*\)', ' ', a)
        s = re.sub(r'\b(dr|mr|mrs|ms|jr|sr|ii|iii|iv)\b\.?', ' ', s, flags=re.I)
        toks = [t for t in re.sub(r'[^a-z ]', ' ', s.lower()).split() if len(t) > 1]
        if toks:
            out.add(toks[0])
        m = re.search(r'\(([^)]+)\)', a)
        if m and ' ' not in m.group(1).strip():
            out.add(m.group(1).strip().lower())
    return out


def _gov_cities():
    out = {}
    for g in ids.governments():
        if g.get('kind') == 'city':
            out[g['id']] = g['short'].upper()
    return out


def officials():
    d = json.load(open(os.path.join(ROOT, 'data', 'entities', 'people.json')))
    return d['people']


def describe(p):
    """Short public label for what a person is: 'Panama City Mayor', '2026 candidate', ..."""
    labels = []
    for r in p.get('roles') or []:
        role = r['role']
        if role.startswith('officeholder: '):
            labels.append(role.split(': ', 1)[1])
        elif role == '2026 candidate':
            labels.append('2026 candidate' + (': ' + r['seat'] if r.get('seat') else ''))
    if not labels:
        for r in p.get('roles') or []:
            g = ids.gov(r.get('gov_id')) if r.get('gov_id') else None
            if r['role'] not in ('board member', 'former board member') and g:
                labels.append(f"{g['short']} {r['role']}")
            elif r['role'] == 'board member' and g:
                labels.append(f"{g['short']} board member")
    seen, out = set(), []
    for x in labels:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return '; '.join(out[:3])


def match(people_list, sb_people, roles):
    """Official/Sunbiz person pairs with a score."""
    city_of = _gov_cities()
    first_of = {}  # person_key -> raw first names seen
    by_key = collections.defaultdict(set)
    for r in roles:
        pk = r.get('person_key')
        if not pk:
            continue
        k, f = sunbiz_key(r['raw_name'])
        if k:
            by_key[k].add(pk)
            first_of.setdefault(pk, set()).add(f)
    out = []
    for p in people_list:
        keys = set()
        for a in [p['name']] + list(p.get('aliases') or []):
            keys |= ids.person_alt_keys(ids.split_district(a)[0])
        cands = set()
        for k in keys:
            cands |= by_key.get(k, set())
        if not cands:
            continue
        firsts = official_first_names(p)
        govs = set(p.get('gov_ids') or [])
        cities = {city_of[g] for g in govs if g in city_of}
        countywide = bool(govs & COUNTYWIDE) or not govs
        resident_cands = [pk for pk in cands if sb_people[pk]['resident'] and not sb_people[pk]['corporate_officer']]
        for pk in sorted(cands):
            sp = sb_people[pk]
            score, why = 0, []
            if sp['resident']:
                score += 2; why.append('address in the county')
            if sp['city'] and sp['city'] in cities:
                score += 2; why.append(f"Sunbiz city {sp['city'].title()} matches the office")
            elif sp['city'] and countywide and sp['resident']:
                score += 1; why.append('countywide office, county address')
            if first_of.get(pk, set()) & firsts:
                score += 1; why.append('same first name')
            else:
                why.append('first name matched through a nickname')
            if len(resident_cands) == 1 and pk in resident_cands:
                score += 1; why.append('only county person with this name')
            elif len(resident_cands) > 1:
                why.append(f'{len(resident_cands)} county people share this name')
            if sp['corporate_officer']:
                score -= 3; why.append('officer of 25+ active companies (corporate board)')
            if sp['agent_service']:
                why.append('registered agent for 20+ companies')
            out.append({'person_id': p['id'], 'official_name': p['name'], 'label': describe(p), 'gov_ids': sorted(govs),
                        'person_key': pk, 'score': score, 'confidence': 'high' if score >= HIGH else 'medium' if score >= MEDIUM else 'low',
                        'reasons': why})
    return out


TITLE_WORDS = {'MGR': 'Manager', 'MANA': 'Manager', 'MGRM': 'Managing member', 'AMBR': 'Authorized member', 'AUTH': 'Authorized member',
               'MBR': 'Member', 'MEMB': 'Member', 'PRES': 'President', 'DIRE': 'Director', 'DIR': 'Director', 'SECR': 'Secretary', 'SEC': 'Secretary',
               'TREA': 'Treasurer', 'OWNE': 'Owner', 'CEO': 'CEO', 'CFO': 'CFO', 'COO': 'COO', 'CHAI': 'Chair', 'CHAIR': 'Chair', 'VC': 'Vice chair',
               'VCHA': 'Vice chair', 'TRUS': 'Trustee', 'TRUSTEE': 'Trustee', 'GP': 'General partner', 'G': 'General partner', 'PART': 'Partner',
               'AP': 'Authorized person', 'AR': 'Authorized representative', 'OFFI': 'Officer', 'EXEC': 'Executive director', 'ED': 'Executive director',
               'RA': 'Registered agent', 'MEM': 'Member', 'SOLE': 'Sole member', 'VP': 'Vice president', 'OTHE': 'Officer', 'CHAIRMAN': 'Chair'}
TITLE_LETTERS = {'P': 'President', 'V': 'Vice president', 'S': 'Secretary', 'T': 'Treasurer', 'D': 'Director', 'C': 'Chair'}


def title_words(code):
    """Sunbiz officer title codes in words: MGRM -> Managing member, PSTD -> President, Secretary, Treasurer, Director."""
    c = re.sub(r'[^A-Z]', '', (code or '').upper())
    if not c:
        return ''
    if c in TITLE_WORDS:
        return TITLE_WORDS[c]
    if c.startswith('VP') and set(c[2:]) <= set(TITLE_LETTERS):
        return ', '.join(['Vice president'] + [TITLE_LETTERS[x] for x in c[2:]])
    if set(c) <= set(TITLE_LETTERS):
        return ', '.join(dict.fromkeys(TITLE_LETTERS[x] for x in c))
    return code.strip().title()


def _end_year(e):
    """Dissolved entity: the later of its last annual report and its last filing (usually the dissolution)."""
    if e['status'] == 'A':
        return None
    ys = [y for y in (e['last_report_year'], e['last_txn_date'].year if e['last_txn_date'] else None) if y]
    return max(ys) if ys else None


def _year_of(v):
    m = re.search(r'(19|20)\d\d', str(v or ''))
    return int(m.group(0)) if m else None


def build(county_key='bay', res=None, payees=None):
    res = res or build_sunbiz.build(county_key)
    E, P, R, gifts = res['entities'], res['people'], res['roles'], res['gifts']
    owners = res['owners']
    plist = officials()
    pmap = {p['id']: p for p in plist}
    matches = match(plist, P, R)

    # roles of each matched pair
    by_pk = collections.defaultdict(list)
    for r in R:
        if r.get('person_key'):
            by_pk[r['person_key']].append(r)
    roles = []
    docs_of = collections.defaultdict(set)      # (person_id, person_key) -> docs
    pairs_on_doc = collections.defaultdict(set)  # doc -> {(person_id, person_key)}
    for m in matches:
        pair = (m['person_id'], m['person_key'])
        per_doc = collections.defaultdict(lambda: {'titles': set(), 'kinds': set()})
        for r in by_pk[m['person_key']]:
            per_doc[r['doc_number']]['titles'].add(r['title'] or r['role'])
            per_doc[r['doc_number']]['kinds'].add(r['role'])
        for dn, x in per_doc.items():
            e = E[dn]
            roles.append({'person_id': m['person_id'], 'person_key': m['person_key'], 'doc_number': dn, 'entity_name': e['name'],
                          'titles': ', '.join(dict.fromkeys(w for t in sorted(x['titles']) for w in title_words(t).split(', ') if w)), 'role_kind': 'officer' if 'officer' in x['kinds'] else 'registered_agent',
                          'entity_status': e['status'], 'filing_type': e['filing_type'], 'nonprofit': e['nonprofit'], 'principal_city': e['city'],
                          'file_date': e['file_date'],
                          'closed_year': _end_year(e),
                          'source_url': ids.sunbiz_url(e['name'], dn)})
            docs_of[pair].add(dn)
            pairs_on_doc[dn].add(pair)

    links = []
    req = lambda *pairs: sorted({f'{a}|{b}' for a, b in pairs})  # noqa: E731

    # shared_business
    for dn, pairs in pairs_on_doc.items():
        pids = sorted({a for a, _ in pairs})
        if len(pids) < 2:
            continue
        e = E[dn]
        for i, a in enumerate(pids):
            for b in pids[i + 1:]:
                pa = [x for x in pairs if x[0] == a]
                pb = [x for x in pairs if x[0] == b]
                links.append({'link_type': 'shared_business', 'person_id': a, 'other_person_id': b, 'doc_number': dn, 'entity_name': e['name'],
                              'requires': req(*pa, *pb), 'detail': f"Both listed on {e['name']}", 'source_url': ids.sunbiz_url(e['name'], dn)})

    # gifts by person_id of the candidate
    cand_pid = {}
    for g in gifts:
        if g['candidate'] not in cand_pid:
            cand_pid[g['candidate']] = ids.person_id(g['candidate'])

    def agg(gs):
        amt = round(sum(g.get('amount') or 0 for g in gs), 2)
        ds = sorted({str(g['date']) for g in gs if g.get('date')})
        return amt, len(gs), (ds[0] if ds else None), (ds[-1] if ds else None)

    gifts_by = collections.defaultdict(list)
    for g in gifts:
        if g['doc_number'] and (g.get('amount') or 0) > 0:
            gifts_by[(g['doc_number'], g['candidate'])].append(g)

    # own_business_gift
    for (dn, cand), gs in gifts_by.items():
        for pair in pairs_on_doc.get(dn, ()):
            amt, n, d1, d2 = agg(gs)
            cp = cand_pid.get(cand)
            links.append({'link_type': 'own_business_gift', 'person_id': pair[0], 'other_person_id': cp, 'candidate': cand,
                          'office': gs[0].get('office'), 'doc_number': dn, 'entity_name': E[dn]['name'], 'amount': amt, 'items': n,
                          'first_date': d1, 'last_date': d2, 'self_gift': cp == pair[0], 'requires': req(pair),
                          'detail': f"{E[dn]['name']} gave {'to their own campaign' if cp == pair[0] else 'to ' + cand}",
                          'source_url': ids.sunbiz_url(e['name'], dn), 'report_url': gs[0].get('report_url')})

    # partner_business_gift: donor business D shares a (non-corporate) person with a business of the candidate
    for (dn, cand), gs in gifts_by.items():
        cp = cand_pid.get(cand)
        if not cp:
            continue
        own_pairs = [pr for pr in docs_of if pr[0] == cp]
        own_pks = {pk for _, pk in own_pairs}
        if not own_pairs or any(pr[0] == cp for pr in pairs_on_doc.get(dn, ())):
            continue  # candidate is on the donor business itself: that's own_business_gift
        donor_people = {pk for pk in owners.get(dn, {}) if not P[pk]['corporate_officer'] and not P[pk]['agent_service'] and pk not in own_pks}
        for pr in own_pairs:
            for od in sorted(docs_of[pr]):
                if od == dn:
                    continue
                shared = donor_people & {pk for pk in owners.get(od, {}) if pk not in own_pks}
                if not shared:
                    continue
                amt, n, d1, d2 = agg(gs)
                links.append({'link_type': 'partner_business_gift', 'person_id': cp, 'candidate': cand, 'office': gs[0].get('office'),
                              'doc_number': dn, 'entity_name': E[dn]['name'], 'related_doc': od, 'related_name': E[od]['name'],
                              'shared_people': len(shared), 'shared_person_keys': sorted(shared), 'amount': amt, 'items': n,
                              'first_date': d1, 'last_date': d2, 'requires': req(pr),
                              'detail': f"{E[dn]['name']} gave to {cand}; it shares {len(shared)} officer{'s' if len(shared) > 1 else ''} with {E[od]['name']}",
                              'source_url': ids.sunbiz_url(e['name'], dn), 'report_url': gs[0].get('report_url')})

    # public_payee
    if payees is None:
        import records
        payees = records.all_records()
    rows = [dict(r, name=r['name']) for r in payees if r.get('name')]
    matched = build_sunbiz.match_donors(E, [{'name': r['name'], 'date': _year_of(r.get('date'))} for r in rows])
    pay_by = collections.defaultdict(list)
    for r, mm in zip(rows, matched):
        if mm['doc_number'] and mm['doc_number'] in pairs_on_doc:
            pay_by[(mm['doc_number'], r.get('gov_id'))].append(r)
    for (dn, gov), rs in pay_by.items():
        for pair in pairs_on_doc[dn]:
            p = pmap[pair[0]]
            amt = round(sum(x.get('amount') or 0 for x in rs if isinstance(x.get('amount'), (int, float))), 2)
            srcs = sorted({x['src'] for x in rs})
            g = ids.gov(gov) if gov else None
            links.append({'link_type': 'public_payee', 'person_id': pair[0], 'doc_number': dn, 'entity_name': E[dn]['name'],
                          'gov_id': gov, 'payer': g['short'] if g else gov, 'own_government': gov in set(p.get('gov_ids') or []), 'amount': amt, 'items': len(rs),
                          'first_date': min((str(x['date']) for x in rs if x.get('date')), default=None),
                          'last_date': max((str(x['date']) for x in rs if x.get('date')), default=None),
                          'record_types': srcs, 'requires': req(pair),
                          'detail': f"{E[dn]['name']} paid by {g['short'] if g else 'a local government'} ({', '.join(srcs)})",
                          'source_url': next((x['url'] for x in rs if x.get('url')), ids.sunbiz_url(e['name'], dn))})
    return {'matches': matches, 'roles': roles, 'links': links, 'people': pmap, 'registry': res}


def summary(out):
    m = out['matches']
    c = collections.Counter(x['confidence'] for x in m)
    lt = collections.Counter(x['link_type'] for x in out['links'])
    return {'officials_with_a_match': len({x['person_id'] for x in m}), 'pairs': len(m), 'pairs_by_confidence': dict(c),
            'roles': len(out['roles']), 'businesses': len({r['doc_number'] for r in out['roles']}), 'links': dict(lt)}


if __name__ == '__main__':
    o = build(sys.argv[1] if len(sys.argv) > 1 else 'bay')
    print(json.dumps(summary(o), indent=1))
