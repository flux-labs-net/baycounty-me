"""Every nonprofit in a county, who sits on its board, and how those people and organizations connect to the rest of
the site's records.

Inputs (per county)
  data/nonprofits/<county>/*.csv.gz   from fetch_irs.py: IRS master file rows, 990-N postcards, 990 returns, their
                                      officer/director lists and Schedule I grants
  data/nonprofits/<county>/fdacs_*.csv.gz
                                      from fetch_fdacs.py: Florida charitable solicitation registrations (FDACS
                                      Check-A-Charity) with their financial summary and officers and directors
  data/sunbiz/<county>/*.csv.gz       Sunbiz nonprofit corporations and their officers (build_sunbiz.py)
  data/entities/people.json           elected officials, department leaders and 2026 candidates
  data/entities/records.py            every payment record on the site (contracts, registers, CRA ledger ...)

Steps
  1. Organizations. An IRS-recognized organization with a county address, or a Sunbiz nonprofit corporation whose
     principal address is in the county and that is active (or recognized by the IRS). IRS and Sunbiz records join on
     the EIN the corporation lists with the state, then on an exact name match. An EIN whose IRS address is outside the
     county (a national parent's group exemption) is not joined: the local corporation stays a state-only record.
     Florida charity registrations (FDACS) join on the FEIN, then on an exact name (or DBA) match. A registration with a
     county address that matches neither becomes its own record (np-fd-<registration number>).
  2. Board seats. Officers and directors from each 990 / 990-EZ / 990-PF return (every year on file), the officers in
     the Sunbiz file (latest annual report), the principal officer on a 990-N postcard and the officers and directors
     on the FDACS charity registration. Paid staff who are not
     officers or directors (key employees, highest paid) are kept with their role, not counted as board.
  3. Board people. Seats are grouped into one person by last + first name (and middle initial when two differ) across
     the county. Each person is checked against people.json (officials, department leaders, candidates) and against the
     Sunbiz people with the same name, which links them to the businesses they run and those businesses' campaign gifts.
     Name matches are leads: an official match is published only after an admin confirms it.
  4. Money. Payment records whose payee is the organization (same name once punctuation and legal suffixes are
     removed, or the same vendor id), campaign gifts the organization made (Sunbiz match), and Schedule I grants
     between organizations.

Outputs
  build() returns everything, names included, for the private `registry` schema (db/scripts/load_registry.py).
  main() writes data/nonprofits/<county>/nonprofits.json: organizations, payments, grants and board members (names as
  filed with the IRS and the state, which are public records). Official matches and Sunbiz business links stay private
  until reviewed.
"""
import collections, csv, datetime, gzip, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'data', 'sunbiz'))
sys.path.insert(0, os.path.join(ROOT, 'data', 'entities'))
import ids  # noqa: E402
import cutoff  # noqa: E402  the site's first year: filings, registrations and seats before 2016 are left out
import build_sunbiz as sb  # noqa: E402
from counties import county  # noqa: E402

SUBSECTION = {'02': '501(c)(2) title-holding', '03': '501(c)(3) charity', '04': '501(c)(4) social welfare', '05': '501(c)(5) labor or agricultural',
              '06': '501(c)(6) business league', '07': '501(c)(7) social club', '08': '501(c)(8) fraternal benefit', '09': '501(c)(9) employee benefit',
              '10': '501(c)(10) fraternal', '12': '501(c)(12) cooperative', '13': '501(c)(13) cemetery', '14': '501(c)(14) credit union',
              '19': '501(c)(19) veterans', '25': '501(c)(25) title-holding', '91': '4947(a)(1) charitable trust', '92': '4947(a)(1) private foundation trust'}
FOUNDATION = {'02': 'private operating foundation', '03': 'private foundation', '04': 'private foundation', '10': 'church', '11': 'school',
              '12': 'hospital', '13': 'medical research', '14': 'college support', '15': 'public charity', '16': 'public charity', '17': 'supporting org',
              '18': 'public safety testing', '21': 'supporting org', '22': 'supporting org', '23': 'supporting org', '24': 'supporting org'}
FILING = {'01': '990 or 990-EZ', '02': '990-N postcard', '03': 'group return', '06': 'not required (church)', '07': 'government',
          '13': 'not required (religious)', '14': 'not required (instrumentality)', '00': 'not required'}
NTEE = {'A': 'Arts and culture', 'B': 'Education', 'C': 'Environment', 'D': 'Animals', 'E': 'Health care', 'F': 'Mental health', 'G': 'Disease and disorders',
        'H': 'Medical research', 'I': 'Crime and legal', 'J': 'Employment', 'K': 'Food and agriculture', 'L': 'Housing', 'M': 'Public safety and disaster',
        'N': 'Recreation and sports', 'O': 'Youth development', 'P': 'Human services', 'Q': 'International', 'R': 'Civil rights and advocacy',
        'S': 'Community improvement', 'T': 'Philanthropy and grantmaking', 'U': 'Science and technology', 'V': 'Social science', 'W': 'Public and societal benefit',
        'X': 'Religion', 'Y': 'Mutual and membership benefit', 'Z': 'Unknown'}
SUNBIZ_TITLE = {'P': 'President', 'VP': 'Vice President', 'S': 'Secretary', 'T': 'Treasurer', 'D': 'Director', 'C': 'Chair', 'CEO': 'CEO', 'CFO': 'CFO',
                'CHAIR': 'Chair', 'VC': 'Vice Chair', 'ST': 'Secretary/Treasurer', 'TR': 'Trustee', 'PT': 'President/Treasurer', 'DIR': 'Director',
                'PRES': 'President', 'SEC': 'Secretary', 'TREA': 'Treasurer', 'TRUS': 'Trustee', 'EXEC': 'Executive Director', 'ED': 'Executive Director'}
# Sunbiz officer titles are a 4-character field: letter codes ("TD" = Treasurer and Director) or the start of a word ("DIRE").
SUNBIZ_LETTER = {'P': 'President', 'V': 'Vice President', 'VP': 'Vice President', 'S': 'Secretary', 'T': 'Treasurer', 'D': 'Director',
                 'C': 'Chair', 'CH': 'Chair', 'VC': 'Vice Chair', 'O': 'Officer', 'M': 'Member', 'B': 'Board Member'}
SUNBIZ_WORD = {'DIRE': 'Director', 'DIREC': 'Director', 'SECR': 'Secretary', 'SECT': 'Secretary', 'SEC.': 'Secretary', 'TRES': 'Treasurer',
               'TRE': 'Treasurer', 'TRS': 'Treasurer', 'BOAR': 'Board Member', 'BD': 'Board Member', 'BM': 'Board Member', 'BRD': 'Board Member',
               'DMBR': 'Director', 'MBR': 'Member', 'MEM': 'Member', 'MEMB': 'Member', 'OFFI': 'Officer', 'CHAI': 'Chair', 'VCHM': 'Vice Chair',
               'VICE': 'Vice President', 'DEAC': 'Deacon', 'ELDE': 'Elder', 'PAST': 'Past Officer', 'OTHE': 'Officer', 'ASST': 'Assistant Officer',
               'ASSI': 'Assistant Officer', 'CAM': 'Community Association Manager', 'MGR': 'Manager', 'MANA': 'Manager', 'MGRM': 'Managing Member',
               'AMBR': 'Authorized Member', 'AUTH': 'Authorized Representative', 'AT L': 'Director at Large', 'ATL': 'Director at Large',
               'AL': 'Director at Large', 'FINA': 'Finance Officer', 'CORR': 'Corresponding Secretary', 'ADJU': 'Adjutant', 'SERG': 'Sergeant at Arms',
               'CLER': 'Clerk', 'ADMI': 'Administrator', 'PARL': 'Parliamentarian', 'QUAR': 'Quartermaster', 'COO': 'COO', 'CEO': 'CEO', 'CFO': 'CFO',
               'CO-T': 'Co-Treasurer', 'CO-P': 'Co-President', 'REGI': 'Registered Agent', 'ADVI': 'Advisor', 'STEW': 'Steward', 'CHAP': 'Chaplain',
               'EXEC': 'Executive Director', 'ED': 'Executive Director', 'TR': 'Trustee', 'TRUS': 'Trustee'}


def sunbiz_title(raw):
    """A readable title from a Sunbiz officer code: "TD" -> "Treasurer, Director", "DIRE" -> "Director", "D-VP" -> "Director, Vice President".
    Unknown codes come back title-cased, as before."""
    t = ' '.join((raw or '').upper().split()).strip(' ,;.')
    if not t:
        return 'Officer'
    if t in SUNBIZ_TITLE:
        return SUNBIZ_TITLE[t]
    if t in SUNBIZ_WORD:
        return SUNBIZ_WORD[t]
    parts = []
    for tok in filter(None, re.split(r'[\s,;/\\&-]+', t)):
        if tok in SUNBIZ_WORD:
            parts.append(SUNBIZ_WORD[tok])
            continue
        i, got = 0, []
        while i < len(tok):  # greedy: two-letter codes (VP, VC, CH) first, then single letters
            two = tok[i:i + 2]
            if two in ('VP', 'VC', 'CH') and two in SUNBIZ_LETTER:
                got.append(SUNBIZ_LETTER[two]); i += 2
            elif tok[i] in SUNBIZ_LETTER:
                got.append(SUNBIZ_LETTER[tok[i]]); i += 1
            else:
                got = None
                break
        if not got:
            return t.title()
        parts += got
    return ', '.join(dict.fromkeys(parts)) or t.title()


TITLE_WORDS = ['President', 'Director', 'Chairman', 'Chairperson', 'Secretary', 'Treasurer', 'Executive', 'Elect', 'Communications',
               'Operations', 'Development', 'Administrator', 'Administration', 'Coordinator', 'Officer', 'Member', 'Commander', 'Committee',
               'Finance', 'Financial', 'Programs', 'Marketing', 'Membership', 'Emeritus', 'Large']
TITLE_ACRONYMS = {'Ceo': 'CEO', 'Cfo': 'CFO', 'Coo': 'COO', 'Vp': 'VP', 'Svp': 'SVP', 'Evp': 'EVP', 'Cpa': 'CPA', 'Hoa': 'HOA', 'Pta': 'PTA', 'Ed': 'ED'}


def clean_title(title):
    """IRS and FDACS titles: title case for all-caps text, acronyms kept (CEO, VP), and words the IRS's 12-character field cut off
    completed when only one common title word fits ("Executive Di" -> "Executive Director", "Secretary/Tr" -> "Secretary/Treasurer")."""
    t = ' '.join((title or '').split())
    if not t:
        return t
    u = t.upper().strip(' ,.')
    if len(u) <= 4 and (u in SUNBIZ_TITLE or u in SUNBIZ_WORD):
        return SUNBIZ_TITLE.get(u) or SUNBIZ_WORD[u]
    if t.isupper():
        t = t.title()
    t = re.sub(r"\b(\w+)\b", lambda m: TITLE_ACRONYMS.get(m.group(1), m.group(1)), t)
    t = re.sub(r"\bOf\b|\bAnd\b|\bThe\b|\bFor\b", lambda m: m.group(0).lower(), t)
    if t in ('VP', 'D'):
        return {'VP': 'Vice President', 'D': 'Director'}[t]
    m = re.search(r"([A-Za-z]+)$", t)
    if m and len(m.group(1)) >= 2 and len(t) == 12:  # the IRS title field holds 12 characters
        w = m.group(1).lower()
        hits = [x for x in TITLE_WORDS if x.lower().startswith(w)]
        if len(hits) == 1 and hits[0].lower() != w:
            t = t[:m.start(1)] + hits[0]
    return t


HONORIFIC = re.compile(r'\b(DR|MR|MRS|MS|MISS|REV|REVEREND|PASTOR|HON|HONORABLE|FR|FATHER|SR\.? PASTOR|BISHOP|ELDER|DEACON|ATTY|COL|LTC|MAJ|CAPT|SGT|CMDR|RET|USAF|USN|USMC|USA)\b\.?')
POST_TITLE = re.compile(r'\s+(PRESIDENT|VICE PRESIDENT|TREASURER|SECRETARY|DIRECTOR|EXECUTIVE DIRECTOR|CHAIRMAN|CHAIR|CHAIRPERSON|CEO|CFO|PASTOR|'
                        r'TRUSTEE|COMMANDER|MANAGER|OWNER|FOUNDER|MEMBER|OFFICER|AGENT|PRES|SEC|TREAS|ADMINISTRATOR|COORDINATOR)\b.*$')
IN_NAME_TITLE = re.compile(r'\b(MAYOR|COMMISSIONER|COUNCILMAN|COUNCILWOMAN|CHAIRMAN|CHAIR|PRESIDENT|PRES|DIRECTOR|DIR|LDR|LEADER|SUPT|SHERIFF|JUDGE|TRUSTEE)\b\.?')
BOARD_ROLES = {'director', 'institutional_trustee', 'officer'}
PROPUBLICA = 'https://projects.propublica.org/nonprofits/organizations/'
FDACS_URL = 'https://csapp.fdacs.gov/CSPublicApp/CheckACharity/CheckACharity.aspx'


def _rows(path):
    if not os.path.exists(path):
        return []
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def _num(s):
    try:
        return float(s) if s not in (None, '') else None
    except ValueError:
        return None


def _int(s):
    n = _num(s)
    return int(n) if n is not None else None


def person_name(raw):
    """(name_key 'LAST FIRST', first, last, middle initial) from a 990 / postcard / Sunbiz person name, or None."""
    s = (raw or '').upper().replace('.', ' ')
    s = re.sub(r'\([^)]*\)', ' ', s)
    if ',' not in s:
        s = POST_TITLE.sub('', s)
    s = HONORIFIC.sub(' ', s)
    s = re.split(r'\s(?:AND|&)\s', s)[0]  # "John and Jane Smith": the first person only
    s = re.sub(r'\s+', ' ', s).strip(' ,')
    if not s or sb.looks_like_org(s):
        return None
    key, mid = sb.split_name(s)
    words = key.split()
    if len(words) < 2:
        return None
    if ',' in s:
        last = sb._clean(s.split(',', 1)[0])
    else:
        toks = [t for t in sb._clean(s).split() if t not in sb.NAME_SUFFIX]
        last = toks[-1] if toks else words[0]
    first = key[len(last):].strip().split(' ')[0] if key.startswith(last) else words[-1]
    return key, first, last, mid


def sunbiz_name(raw):
    """Sunbiz names are 'LAST FIRST MIDDLE' (fixed width): same output as person_name. Titles typed into the middle
    name field ('LUCAS JANICE MAYOR') are dropped so they don't read as a middle initial."""
    raw = (raw or '').rstrip()
    if len(raw) > 34:
        raw = raw[:34] + IN_NAME_TITLE.sub(' ', HONORIFIC.sub(' ', raw[34:].upper()))
    key, mid = sb.split_name(raw)
    if len(raw) > 20 and raw[:20].strip():
        last = sb._clean(raw[:20])
    else:
        last = key.split()[0] if key else ''
    first = key[len(last):].strip().split(' ')[0] if key.startswith(last) else ''
    if not key or len(key.split()) < 2:
        return None
    return key, first, last, mid


def city_name(raw):
    """'P C BEACH', 'Panama City Bch.', 'PANAMA CITY, FL 32405' -> one spelling per city."""
    c = re.sub(r',.*$|\b\d{5}\b|\bFL\b\.?', ' ', (raw or '').upper())
    c = re.sub(r'[^A-Z ]', ' ', c)
    c = re.sub(r'\s+', ' ', c).strip()
    if re.match(r'^(P ?C|PANAMA|PANMA|PANANA|PANAMA CITY|PANAMA CIY|PANAMA CTY)\b.*\b(BEACH|BCH|BEA)\b', c) or c in ('PCB', 'P C B'):
        return 'Panama City Beach'
    if re.match(r'^(PANAMA|PANMA|PANANA)( CITY| CIY| CTY)?$', c) or c in ('PC', 'P C'):
        return 'Panama City'
    if c.startswith('TYNDALL'):
        return 'Tyndall AFB'
    return c.title()


def _hash(*parts):
    return hashlib.sha1('|'.join(str(p) for p in parts).encode()).hexdigest()[:12]


# ---------- 1. organizations ----------

def organizations(county_key, entities):
    c = county(county_key)
    d = os.path.join(HERE, county_key)
    irs = {r['EIN']: r for r in _rows(os.path.join(d, 'orgs.csv.gz'))}
    filings = collections.defaultdict(list)
    for f in _rows(os.path.join(d, 'filings.csv.gz')):
        if cutoff.keep(f['tax_year']):
            filings[f['ein']].append(f)
    posts = {p['ein']: p for p in _rows(os.path.join(d, 'postcards.csv.gz')) if cutoff.keep(p['tax_year'])}
    sb_np = {dn: e for dn, e in entities.items() if e['nonprofit']}
    by_key = collections.defaultdict(list)
    for e in sb_np.values():
        by_key[e['key']].append(e)
    orgs = {}
    used_docs = set()
    for ein, r in irs.items():
        doc = r.get('sunbiz_doc') or ''
        e = entities.get(doc) if doc else None
        if r['in_county'] != 'True':
            # the state filing lists an EIN whose IRS address is elsewhere: usually a national parent's group
            # exemption (a local lodge or chapter). The local corporation is kept as a state-only record below,
            # without the parent's IRS figures or officers.
            continue
        if not e:
            hits = [x for x in by_key.get(sb.biz_key(r['NAME']), []) if x['in_county_principal']]
            if len(hits) == 1 and hits[0]['doc_number'] not in used_docs:
                e, doc = hits[0], hits[0]['doc_number']
        if e:
            used_docs.add(doc)
        orgs['np-' + ein] = {'irs': r, 'sunbiz': e, 'ein': ein, 'doc_number': doc if e else '', 'filings': sorted(filings.get(ein, []),
                             key=lambda f: (f['tax_period_end'] or '', f['submitted_on'] or '')), 'postcard': posts.get(ein)}
    for dn, e in sb_np.items():
        if dn in used_docs or not e['in_county_principal'] or e['status'] != 'A':
            continue
        orgs['np-sb-' + dn.lower()] = {'irs': None, 'sunbiz': e, 'ein': '', 'doc_number': dn, 'filings': [], 'postcard': None}
    attach_fdacs(orgs, county_key)
    for oid, o in orgs.items():
        o['id'] = oid
        r, e, fd = o['irs'], o['sunbiz'], o.get('fdacs')
        latest = o['filings'][-1] if o['filings'] else None
        o['latest'] = latest
        o['name'] = (r['NAME'] if r else e['name'] if e else fd['name']).strip()
        o['city'] = city_name(r['CITY'] if r else e['city'] if e else fd['city'])
        o['zip'] = ((r['ZIP'] if r else e['zip5'] if e else fd['zip']) or '')[:5]
        o['key'] = sb.biz_key(o['name'])
    return orgs


def _iso(s):
    """'2026-06-30', '06/30/2026' or '6/30/26' -> '2026-06-30' (None when it isn't a date)."""
    s = (s or '').strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}', s):
        return s[:10]
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})$', s)
    if m:
        y = int(m.group(3))
        y = y + 2000 if y < 70 else y + 1900 if y < 100 else y
        return f'{y:04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}'
    return None


def fdacs_rows(county_key):
    """Registrations (latest one per registration number) and their officers, from fetch_fdacs.py."""
    d = os.path.join(HERE, county_key)
    regs = {}
    for r in _rows(os.path.join(d, 'fdacs_registrations.csv.gz')):
        n = (r.get('registration_number') or '').strip().upper()
        if not n:
            continue
        r['registration_number'] = n
        r['fein'] = re.sub(r'\D', '', r.get('fein') or '')
        r['fein'] = r['fein'] if len(r['fein']) == 9 else ''
        r['name'] = ' '.join((r.get('name') or '').split())
        r['city'] = r.get('city') or ''
        r['zip'] = (r.get('zip') or '')[:5]
        if not cutoff.keep(_iso(r.get('expiration_date'))):
            continue  # lapsed before the site's first year
        if n not in regs or (r.get('fetched_at') or '') >= (regs[n].get('fetched_at') or ''):
            regs[n] = r
    offs = collections.defaultdict(list)
    for r in _rows(os.path.join(d, 'fdacs_officers.csv.gz')):
        n = (r.get('registration_number') or '').strip().upper()
        if n in regs and (r.get('name') or '').strip():
            offs[n].append(r)
    return regs, offs


def attach_fdacs(orgs, county_key):
    """Give each organization its FDACS charity registration: same FEIN, else the same name or DBA (only when one
    organization has it). Registrations that match nothing are added as their own organizations."""
    regs, offs = fdacs_rows(county_key)
    by_ein = {o['ein']: oid for oid, o in orgs.items() if o['ein']}
    by_key, by_loose = collections.defaultdict(set), collections.defaultdict(set)
    for oid, o in orgs.items():
        for nm in filter(None, [(o['irs'] or {}).get('NAME'), (o['sunbiz'] or {}).get('name')]):
            by_key[sb.biz_key(nm)].add(oid)
            by_loose[sb.loose_key(nm)].add(oid)
    # active registrations first, so an organization with an old lapsed registration and a current one keeps the current
    for n, r in sorted(regs.items(), key=lambda kv: ((kv[1].get('status') or '').lower() != 'active', kv[0])):
        oid, how = by_ein.get(r['fein']), 'fein'
        if not oid:
            how = 'name'
            for nm in filter(None, [r['name'], r.get('dba')]):
                hit = by_key.get(sb.biz_key(nm))
                if not hit:  # "Bay/Bays", "Booster/Boosters": the plural-insensitive key, still only when one org has it
                    hit = by_loose.get(sb.loose_key(nm))
                if hit and len(hit) == 1:
                    oid = next(iter(hit))
                    break
        if oid and orgs[oid].get('fdacs'):
            orgs[oid].setdefault('fdacs_other', []).append(n)
            continue
        if not oid:
            oid, how = 'np-fd-' + n.lower(), 'new'
            orgs[oid] = {'irs': None, 'sunbiz': None, 'ein': r['fein'], 'doc_number': '', 'filings': [], 'postcard': None}
        orgs[oid]['fdacs'] = r
        orgs[oid]['fdacs_join'] = how
        orgs[oid]['fdacs_officers'] = offs.get(n, [])
    return orgs


# ---------- 2. board seats ----------

def seats(orgs, roles, people, county_key):
    out = []
    by_doc = collections.defaultdict(list)
    for r in roles:
        if r['role'] == 'officer':
            by_doc[r['doc_number']].append(r)
    off990 = collections.defaultdict(list)
    for r in _rows(os.path.join(HERE, county_key, 'officers.csv.gz')):
        off990[r['ein']].append(r)
    for oid, o in orgs.items():
        e = o['sunbiz']
        if e:
            for r in by_doc.get(e['doc_number'], []):
                if not r['is_person']:
                    continue
                nm = sunbiz_name(r['raw_name'])
                if not nm:
                    continue
                t = r['title'].upper().strip()
                out.append({'nonprofit_id': oid, 'source': 'sunbiz', 'raw_name': ' '.join(r['raw_name'].split()), 'name': nm,
                            'title': sunbiz_title(t), 'tax_year': e['last_report_year'], 'board': True, 'roles': 'officer',
                            'hours': None, 'compensation': None, 'object_id': None, 'registry_person_key': r.get('person_key'),
                            'source_url': ids.sunbiz_url(e['name'], e['doc_number'])})
        fy = {f['object_id']: f for f in o['filings']}
        for r in off990.get(o['ein'], []):
            if r['is_person'] != 'True' or r['object_id'] not in fy:
                continue
            nm = person_name(r['name'])
            if not nm:
                continue
            rs = set(filter(None, r['roles'].split('|')))
            title = r['title'].strip()
            board = bool(rs & BOARD_ROLES) or (not rs and r['form'] in ('990EZ', '990PF'))
            if 'former' in rs:
                board = False
            out.append({'nonprofit_id': oid, 'source': 'irs_' + r['form'].lower(), 'raw_name': r['name'].strip(), 'name': nm, 'title': clean_title(title),
                        'tax_year': _int(r['tax_year']), 'board': board, 'roles': r['roles'], 'hours': _num(r['hours']),
                        'compensation': (_num(r['compensation']) or 0) + (_num(r['related_comp']) or 0) if r['compensation'] or r['related_comp'] else None,
                        'object_id': r['object_id'], 'registry_person_key': None,
                        'source_url': fy[r['object_id']].get('xml_url') or (PROPUBLICA + o['ein'])})
        p = o['postcard']
        if p and p.get('principal_officer'):
            nm = person_name(p['principal_officer'])
            if nm:
                out.append({'nonprofit_id': oid, 'source': 'irs_990n', 'raw_name': p['principal_officer'].strip(), 'name': nm, 'title': 'Principal officer',
                            'tax_year': _int(p['tax_year']), 'board': True, 'roles': 'officer', 'hours': None, 'compensation': None, 'object_id': None,
                            'registry_person_key': None, 'source_url': PROPUBLICA + o['ein']})
        fd = o.get('fdacs')
        for r in o.get('fdacs_officers') or []:
            nm = person_name(r['name'])
            if not nm:
                continue
            yr = (_iso(fd.get('fiscal_year_end')) or _iso(fd.get('registration_date')) or (fd.get('fetched_at') or ''))[:4]
            title = (r.get('title') or '').strip()
            out.append({'nonprofit_id': oid, 'source': 'fdacs', 'raw_name': ' '.join(r['name'].split()), 'name': nm,
                        'title': clean_title(title) or 'Officer or director', 'tax_year': int(yr) if yr.isdigit() else None,
                        'board': True, 'roles': 'officer', 'hours': None, 'compensation': None, 'object_id': None, 'registry_person_key': None,
                        'source_url': fd.get('detail_url') or FDACS_URL})
    out = [s for s in out if cutoff.keep(s['tax_year'])]  # seats on filings from before the site's first year
    # a seat is current when it is on the organization's latest filing of its kind
    latest = {}
    for s in out:
        k = (s['nonprofit_id'], s['source'] if s['source'] != 'irs_990ez' and s['source'] != 'irs_990pf' else 'irs_990')
        latest[k] = max(latest.get(k) or 0, s['tax_year'] or 0)
    for s in out:
        k = (s['nonprofit_id'], s['source'] if s['source'] not in ('irs_990ez', 'irs_990pf') else 'irs_990')
        s['current'] = (s['tax_year'] or 0) == latest[k]
        if s['source'] == 'sunbiz' and ((orgs[s['nonprofit_id']].get('sunbiz') or {}).get('status') or 'A') != 'A':
            s['current'] = False  # officers of a dissolved corporation are not a current board
        if s['source'] == 'fdacs':  # officers on a lapsed or withdrawn registration are not a current board
            st = (orgs[s['nonprofit_id']]['fdacs'].get('status') or '').lower()
            s['current'] = s['current'] and st in ('active', 'registered')
    return out


# ---------- 3. board people ----------

def group_key(name):
    """'LAST FIRST' with the first name's nickname folded (Josh = Joshua, Chris = Christopher)."""
    import ids
    key, first, last, _ = name
    f = first.lower()
    f = ids.NICK.get(f, f).upper()
    return f'{last} {f}'.strip() if last and f else key


def officials_index():
    import ids
    return ids


def group_board_people(all_seats, people, entities, gift_docs, county_key):
    """board_key per seat; people dict. Same last + first name = one person, split by middle initial when two differ."""
    by_name = collections.defaultdict(list)
    for s in all_seats:
        by_name[group_key(s['name'])].append(s)
    reg_by_name = collections.defaultdict(list)
    for p in people.values():
        if not p['agent_service']:
            nm = sunbiz_name(p.get('raw_name') or p['display_name'])
            if nm:
                reg_by_name[group_key(nm)].append(p)
    ids = officials_index()
    bp = {}
    for nk, ss in by_name.items():
        mids = collections.Counter(s['name'][3] for s in ss if s['name'][3])
        groups = collections.defaultdict(list)
        top = mids.most_common(1)[0][0] if mids else ''
        for s in ss:
            m = s['name'][3] if len(mids) > 1 and s['name'][3] else (top if len(mids) > 1 else '')
            groups[m].append(s)
        for m, gs in groups.items():
            key = 'b_' + _hash(county_key, nk, m)
            first = collections.Counter(s['name'][1] for s in gs if s['name'][1]).most_common(1)
            last = collections.Counter(s['name'][2] for s in gs if s['name'][2]).most_common(1)
            first, last = (first[0][0] if first else ''), (last[0][0] if last else nk.split()[0])
            display = collections.Counter(s['raw_name'] for s in gs if s['source'] != 'sunbiz' and ',' not in s['raw_name']).most_common(1)
            display = ' '.join(display[0][0].split()) if display else ' '.join(filter(None, [first, m, last]))
            display = ids.person_case(display)
            for s in gs:
                s['board_key'] = key
            # Sunbiz people with this name (and a compatible middle initial): the businesses they run
            regs = reg_by_name.get(nk, [])
            linked = {s['registry_person_key'] for s in gs if s.get('registry_person_key')}
            official = None
            for nm in (f'{first} {last}', ' '.join(reversed(nk.split(' ', 1))) if ' ' in nk else nk):
                pid = ids.person_id(nm.title())
                if pid:
                    official = ids.person(pid)
                    break
            orgs = {s['nonprofit_id'] for s in gs}
            cur = {s['nonprofit_id'] for s in gs if s['current'] and s['board']}
            civic = {s['nonprofit_id'] for s in gs if s['current'] and s['board'] and not s.get('hoa')}
            bp[key] = {'board_key': key, 'county': county_key, 'display_name': display,
                       'name_key': nk, 'first': first, 'last': last, 'mid': m, 'n_nonprofits': len(orgs), 'n_current': len(cur), 'n_current_civic': len(civic),
                       'n_seats': len(gs), 'registry_person_keys': sorted({p['person_key'] for p in regs} | linked), 'linked_person_keys': sorted(linked),
                       'same_name_people': len(reg_by_name.get(nk, [])),
                       'official_id': official['id'] if official else None, 'official_name': official['name'] if official else None,
                       'official_roles': sorted({r['role'] for r in official['roles']})[:6] if official else []}
    return bp


def businesses_of(bp, roles, entities, gift_docs):
    """For each board person: the for-profit businesses their Sunbiz name-matches run, and which gave to campaigns."""
    by_person = collections.defaultdict(set)
    for r in roles:
        # officer roles only: being a company's registered agent (often an accountant or lawyer) is not running it
        if r.get('person_key') and r.get('role') == 'officer':
            by_person[r['person_key']].add(r['doc_number'])
    for p in bp.values():
        docs, strong = set(), set()
        for pk in p['registry_person_keys']:
            docs |= by_person.get(pk, set())
            if pk in p['linked_person_keys']:
                strong |= by_person.get(pk, set())
        biz = [entities[d] for d in docs if d in entities and not entities[d]['nonprofit']]
        # same_person: the Sunbiz person (name + address) who is on this nonprofit's own Sunbiz filing; same_name: name only
        p['businesses'] = sorted(({'doc_number': e['doc_number'], 'name': e['name'], 'status': e['status'],
                                   'via': 'same_person' if e['doc_number'] in strong else 'same_name',
                                   'gifts_total': round(gift_docs.get(e['doc_number'], {}).get('amount', 0), 2),
                                   'candidates': sorted(gift_docs.get(e['doc_number'], {}).get('candidates', []))} for e in biz),
                                 key=lambda b: (-b['gifts_total'], b['status'], b['name']))
        p['n_businesses'] = sum(1 for b in p['businesses'] if b['status'] == 'A')
        p['n_donor_businesses'] = sum(1 for b in p['businesses'] if b['gifts_total'] > 0)
        p['donor_gifts_total'] = round(sum(b['gifts_total'] for b in p['businesses']), 2)


# ---------- 4. money ----------

STOP = {'OF', 'THE', 'INC', 'INCORPORATED', 'CORP', 'CORPORATION', 'FL', 'FLA', 'FLORIDA', 'AND', 'A', 'CO', 'LLC', 'AT'}


def word_key(name):
    """Order-free key: 'First Baptist Church of Panama City' = 'Panama City First Baptist Church'."""
    w = sorted(set(sb._clean((name or '').upper().replace('&', ' AND ')).split()) - STOP)
    return 'w:' + ' '.join(w) if len(w) >= 3 else None


def payments_to(orgs):
    """Payment records whose payee is one of the organizations: the same name once punctuation and legal suffixes are
    removed, the same words in another order, or the same vendor id. A name that fits two organizations is skipped."""
    import ids, records
    by_key = collections.defaultdict(set)
    for oid, o in orgs.items():
        for nm in [o['name']] + ([o['sunbiz']['name']] if o['sunbiz'] else []):
            k = ids.vkey(nm)
            if len(k) >= 6:
                by_key[k].add(oid)
            if word_key(nm):
                by_key[word_key(nm)].add(oid)
            for vid in ids.vendor_ids(nm):
                by_key['v:' + vid].add(oid)
    out = []
    for r in records.all_records():
        name = r['name'] or ''
        hits = set()
        for part in re.split(r'\s+/\s+', name):
            for k in (ids.vkey(part), word_key(re.sub(r'\(.*?\)', ' ', part))):
                if k and k in by_key and len(by_key[k]) == 1:
                    hits |= by_key[k]
                    break
            for vid in ids.vendor_ids(part):
                if len(by_key.get('v:' + vid, ())) == 1:
                    hits |= by_key['v:' + vid]
        if not cutoff.keep(r['date']):
            continue
        for oid in hits:
            out.append({'nonprofit_id': oid, 'record_id': f"{r['src']}:{r['idx']}", 'record_type': r['src'], 'gov_id': r['gov_id'], 'payee_as_filed': name,
                        'amount': r['amount'] if isinstance(r['amount'], (int, float)) else None, 'date': str(r['date'] or ''),
                        'what': (r['what'] or '')[:300], 'source_url': r['url'],
                        'cra': (r['extra'] or {}).get('cra') if r['src'] == 'cra' else None, 'status': (r['extra'] or {}).get('status') if r['src'] == 'cra' else None})
    return out


def grants_between(orgs, county_key):
    """Schedule I grants where the grantor or the recipient is one of the county's organizations."""
    by_ein = {o['ein']: oid for oid, o in orgs.items() if o['ein']}
    by_key = collections.defaultdict(set)
    for oid, o in orgs.items():
        by_key[o['key']].add(oid)
    out = []
    for g in _rows(os.path.join(HERE, county_key, 'grants.csv.gz')):
        if not cutoff.keep(g['tax_year']):
            continue
        rein = re.sub(r'\D', '', g['recipient_ein'] or '')
        rid = by_ein.get(rein)
        if not rid and not rein and (g['recipient_state'] or 'FL') == 'FL':  # a different EIN is a different org
            hit = by_key.get(sb.biz_key(g['recipient']))
            rid = next(iter(hit)) if hit and len(hit) == 1 else None
        gid = by_ein.get(g['ein'])
        if not (gid or rid):
            continue
        out.append({'grantor_id': gid, 'grantor_ein': g['ein'], 'recipient_id': rid, 'recipient': g['recipient'].strip(), 'recipient_ein': rein or None,
                    'recipient_city': (g['recipient_city'] or '').title(), 'recipient_state': g['recipient_state'], 'tax_year': _int(g['tax_year']),
                    'cash': _num(g['cash']), 'noncash': _num(g['noncash']), 'purpose': g['purpose'], 'object_id': g['object_id']})
    return out


def build(county_key='bay', sunbiz_res=None):
    res = sunbiz_res or sb.build(county_key)
    entities, roles, people = res['entities'], res['roles'], res['people']
    gift_docs = {}
    for g in res['gifts']:
        if g.get('doc_number') and (g.get('amount') or 0) > 0:
            x = gift_docs.setdefault(g['doc_number'], {'amount': 0.0, 'candidates': set(), 'n': 0})
            x['amount'] += g['amount']
            x['n'] += 1
            x['candidates'].add(g['candidate'])
    orgs = organizations(county_key, entities)
    for o in orgs.values():
        o['kind'] = kind(o, o['irs'])
    all_seats = seats(orgs, roles, people, county_key)
    hoa = {oid for oid, o in orgs.items() if o['kind'] == HOA_KIND}
    for st in all_seats:
        st['hoa'] = st['nonprofit_id'] in hoa
    bp = group_board_people(all_seats, people, entities, gift_docs, county_key)
    businesses_of(bp, roles, entities, gift_docs)
    pays = payments_to(orgs)
    grants = grants_between(orgs, county_key)
    for oid, o in orgs.items():
        o['gift_docs'] = gift_docs.get(o['doc_number']) if o['doc_number'] else None
    return {'county': county_key, 'orgs': orgs, 'seats': all_seats, 'people': bp, 'payments': pays, 'grants': grants, 'sunbiz': res}


HOA = re.compile(r"\b(HOMEOWNERS?|HOME OWNERS?|PROPERTY OWNERS?|OWNERS|OWNER'?S|CONDOMINIUMS?|CONDO|TOWNHOMES?|TOWNHOUSES?|VILLAS?|MASTER ASSOCIATION|POA|HOA|"
                 r"(COMMUNITY|NEIGHBORHOOD|RESIDENCES?|AMENITY|AMENITIES|IMPROVEMENT|COMMERCIAL|MANAGEMENT|RESORT|BUSINESS PARK|PHASE [IVX\d]+) ASSOCIATION)\b")
CHURCH = re.compile(r'\b(CHURCH|MINISTR(Y|IES)|BAPTIST|METHODIST|EPISCOPAL|PRESBYTERIAN|LUTHERAN|CATHOLIC|PARISH|ASSEMBLY OF GOD|ASSEMBLIES|TABERNACLE|'
                    r'CONGREGATION|SYNAGOGUE|TEMPLE|MOSQUE|FELLOWSHIP|GOSPEL|APOSTOLIC|PENTECOSTAL|KINGDOM HALL|DIOCESE|CHAPEL)\b')


HOA_KIND = 'Homeowner or condo association'


def kind(o, r):
    """A plain label for filtering: homeowner/condo association, church or religious group, private foundation, or the
    IRS activity category."""
    name = o['name'].upper()
    sub, fnd, ntee = (r or {}).get('SUBSECTION'), (r or {}).get('FOUNDATION'), ((r or {}).get('NTEE_CD') or '')
    # "Resource/Deer/Emergency Management Association" are not property owners' associations
    mgmt_only = 'MANAGEMENT ASSOCIATION' in name and not re.search(r'\b(OWNERS?|HOMEOWNERS?|CONDOMINIUMS?)\b', name)
    if HOA.search(name) and 'ASSOC' in name and not mgmt_only or re.search(r'\b(HOA|POA|CONDOMINIUM)\b', name) or ntee.startswith('S22') or ntee.startswith('L5'):
        return HOA_KIND
    if fnd == '10' or ntee.startswith('X') or CHURCH.search(name):
        return 'Church or religious group'
    if fnd in ('02', '03', '04') or sub in ('92',):
        return 'Private foundation'
    if sub in ('07', '08', '10', '19') or re.search(r'\b(LODGE|POST \d+|VFW|AMERICAN LEGION|ROTARY|KIWANIS|LIONS|ELKS|MOOSE|SHRINE|MASONS?)\b', name):
        return 'Club, lodge or veterans group'
    if sub == '06' or re.search(r'\bCHAMBER OF COMMERCE\b', name):
        return 'Business league or chamber'
    if ntee:
        return NTEE.get(ntee[:1]) or 'Other nonprofit'
    if re.search(r'\b(BOOSTERS?|PTA|PTO|PARENT TEACHER|SCHOOL|ACADEMY|EDUCATION)\b', name):
        return 'Education'
    if re.search(r'\b(LEAGUE|SOFTBALL|BASEBALL|SOCCER|FOOTBALL|ATHLETIC|SPORTS|SWIM|TENNIS|GOLF)\b', name):
        return 'Recreation and sports'
    return 'Other nonprofit'


def _ruling_year(r):
    s = (r or {}).get('RULING') or ''
    return int(s[:4]) if len(s) >= 4 and s[:4].isdigit() and s[:4] != '0000' else None


def _index(res):
    if '_idx' not in res:
        ix = {k: collections.defaultdict(list) for k in ('np', 'bk', 'pay', 'given', 'got')}
        for st in res['seats']:
            ix['np'][st['nonprofit_id']].append(st)
            ix['bk'][st['board_key']].append(st)
        for p in res['payments']:
            ix['pay'][p['nonprofit_id']].append(p)
        for g in res['grants']:
            ix['given'][g['grantor_id']].append(g)
            if g['grantor_id']:
                ix['got'][g['recipient_id']].append(g)
        res['_idx'] = ix
    return res['_idx']


def org_row(o, res, gov_names):
    r, e, f = o['irs'] or {}, o['sunbiz'], o['latest'] or {}
    ix = _index(res)
    pays = ix['pay'][o['id']]
    board_keys = {s['board_key'] for s in ix['np'][o['id']] if s['current'] and s['board']}
    shared = set()
    if o['kind'] != HOA_KIND:  # homeowner associations are left out: a developer or manager often sits on dozens
        for bk in board_keys:
            for s in ix['bk'][bk]:
                if s['nonprofit_id'] != o['id'] and s['current'] and s['board'] and not s.get('hoa'):
                    shared.add(s['nonprofit_id'])
    given, got = ix['given'][o['id']], ix['got'][o['id']]
    gd = o.get('gift_docs') or {}
    fd = o.get('fdacs') or {}
    ntee = (r.get('NTEE_CD') or '').strip()
    return {
        'nonprofit_id': o['id'], 'name': o['name'], 'ein': o['ein'] or None, 'sunbiz_doc_number': o['doc_number'] or None,
        'city': o['city'], 'zip': o['zip'], 'county': res['county'],
        'kind': o['kind'], 'irs_recognized': bool(o['irs']), 'subsection': SUBSECTION.get(r.get('SUBSECTION'), ('501(c)(' + r['SUBSECTION'].lstrip('0') + ')') if r.get('SUBSECTION') else None),
        'foundation_type': FOUNDATION.get(r.get('FOUNDATION')), 'ntee_code': ntee or None, 'category': NTEE.get(ntee[:1]) if ntee else None,
        'ruling_year': _ruling_year(r), 'irs_filing_requirement': FILING.get(r.get('FILING_REQ_CD')),
        'sunbiz_status': ({'A': 'Active', 'I': 'Inactive'}.get(e['status'], e['status']) if e else None),
        'sunbiz_filed': e['file_date'].isoformat() if e and e['file_date'] else None,
        'irs_assets': _num(r.get('ASSET_AMT')), 'irs_income': _num(r.get('INCOME_AMT')), 'irs_revenue': _num(r.get('REVENUE_AMT')),
        'latest_return_form': f.get('form') or ('990N' if o['postcard'] else None),
        'latest_return_year': _int(f.get('tax_year')) or (_int(o['postcard']['tax_year']) if o['postcard'] else None),
        'total_revenue': _num(f.get('total_revenue')), 'total_expenses': _num(f.get('total_expenses')), 'total_assets': _num(f.get('total_assets')),
        'employees': _int(f.get('employees')), 'returns_on_file': len(o['filings']), 'website': (f.get('website') or (o['postcard'] or {}).get('website') or '').strip() or None,
        'mission': f.get('mission') or None,
        'board_members_listed': len(board_keys), 'shares_board_with': len(shared),
        'gov_payment_records': len(pays), 'gov_dollars_in_records': round(sum(p['amount'] or 0 for p in pays), 2) or None,
        'paid_by': ', '.join(sorted({gov_names.get(p['gov_id'], p['gov_id'] or '') if p['record_type'] != 'cra' else p['cra'] for p in pays} - {''})) or None,
        'grants_given_count': len(given), 'grants_given_cash': round(sum(g['cash'] or 0 for g in given), 2) or None,
        'grants_from_local_nonprofits': round(sum(g['cash'] or 0 for g in got), 2) or None,
        'campaign_gifts_total': round(gd.get('amount', 0), 2) or None, 'campaign_gift_candidates': ', '.join(sorted(gd.get('candidates', []))) or None,
        'fdacs_registration': fd.get('registration_number'), 'fdacs_status': fd.get('status') or None,
        'fdacs_expires': _iso(fd.get('expiration_date')), 'fdacs_fiscal_year_end': _iso(fd.get('fiscal_year_end')),
        'fdacs_revenue': _num(fd.get('total_revenue')), 'fdacs_program_expenses': _num(fd.get('program_expenses')),
        'fdacs_fundraising_expenses': _num(fd.get('fundraising_expenses')), 'fdacs_management_expenses': _num(fd.get('management_expenses')),
        'fdacs_url': (fd.get('detail_url') or FDACS_URL) if fd else None,
        'source_url': (PROPUBLICA + o['ein']) if o['ein'] and o['irs'] else ids.sunbiz_url((e or o)['name'], o['doc_number']) if o['doc_number'] else (fd.get('detail_url') or FDACS_URL),
        'sunbiz_url': ids.sunbiz_url((e or o)['name'], o['doc_number']) if o['doc_number'] else None,
    }


def public(res):
    """Public rows: nonprofits, government payment records, grants, board members and their businesses."""
    import ids
    gov_names = {g['id']: g.get('short') or g.get('name') for g in ids.governments()}
    orgs = sorted((org_row(o, res, gov_names) for o in res['orgs'].values()), key=lambda r: (-(r['total_revenue'] or r['irs_revenue'] or 0), r['name']))
    names = {o['id']: o['name'] for o in res['orgs'].values()}
    pays = [{'nonprofit_id': p['nonprofit_id'], 'nonprofit': names[p['nonprofit_id']], 'payer': p['cra'] if p['record_type'] == 'cra' else gov_names.get(p['gov_id'], p['gov_id']),
             'gov_id': p['gov_id'], 'record_type': p['record_type'], 'record_id': p['record_id'], 'payee_as_filed': p['payee_as_filed'], 'amount': p['amount'],
             'date': p['date'], 'what': p['what'], 'cra_status': p['status'], 'county': res['county'], 'source_url': p['source_url']} for p in res['payments']]
    grants = [{'grantor_id': g['grantor_id'], 'grantor': names.get(g['grantor_id']) if g['grantor_id'] else None, 'grantor_ein': g['grantor_ein'],
               'recipient_id': g['recipient_id'], 'recipient': names.get(g['recipient_id']) or g['recipient'], 'recipient_ein': g['recipient_ein'],
               'recipient_city': g['recipient_city'], 'recipient_state': g['recipient_state'], 'tax_year': g['tax_year'], 'cash': g['cash'], 'noncash': g['noncash'],
               'purpose': g['purpose'], 'county': res['county'],
               'source_url': f"https://gt990datalake-rawdata.s3.amazonaws.com/EfileData/XmlFiles/{g['object_id']}_public.xml"} for g in res['grants']
              if g['grantor_id']]  # recipients' grants from outside the county are in the private tables only
    return orgs, pays, grants, board_rows(res), business_rows(res), registration_rows(res)


def _pct(part, whole):
    return round(100 * part / whole, 1) if part is not None and whole else None


def registration_rows(res):
    """One row per FDACS charity registration with a county address: status, dates, the financial summary the charity
    reported to the state, its fundraising consultants (firms) and how many officers and directors it lists."""
    rows = []
    for o in res['orgs'].values():
        regs = [o['fdacs']] if o.get('fdacs') else []
        for fd in regs:
            rev, prog, fr, mg = (_num(fd.get(k)) for k in ('total_revenue', 'program_expenses', 'fundraising_expenses', 'management_expenses'))
            tot = _num(fd.get('total_expenses'))
            if tot is None and any(v is not None for v in (prog, fr, mg)):
                tot = sum(v or 0 for v in (prog, fr, mg))
            rows.append({'registration_number': fd['registration_number'], 'nonprofit_id': o['id'], 'name': fd['name'] or o['name'],
                         'dba': fd.get('dba') or None, 'fein': fd['fein'] or None, 'matched_by': o.get('fdacs_join'),
                         'status': fd.get('status') or None, 'status_detail': fd.get('status_detail') or None,
                         'registration_date': _iso(fd.get('registration_date')), 'expiration_date': _iso(fd.get('expiration_date')),
                         'city': city_name(fd.get('city')) or None, 'zip': fd['zip'] or None, 'website': fd.get('website') or None,
                         'fiscal_year_end': _iso(fd.get('fiscal_year_end')), 'total_revenue': rev, 'contributions': _num(fd.get('contributions')),
                         'government_grants': _num(fd.get('government_grants')), 'program_expenses': prog, 'fundraising_expenses': fr,
                         'management_expenses': mg, 'total_expenses': tot,
                         'program_percent': (_num(fd.get('program_percent')) if fd.get('program_percent') else _pct(prog, tot)) if tot else None,
                         'fundraising_percent': _pct(fr, tot),
                         'fundraising_consultants': '; '.join(x.strip() for x in (fd.get('fundraising_consultants') or '').split(';') if x.strip()) or None,
                         'officers_listed': len(o.get('fdacs_officers') or []), 'other_registrations': ', '.join(o.get('fdacs_other', [])) or None,
                         'county': res['county'], 'source_url': fd.get('detail_url') or FDACS_URL})
    rows.sort(key=lambda r: (-(r['total_revenue'] or 0), r['name']))
    return rows


SOURCE_LABEL = {'irs_990': 'IRS 990', 'irs_990ez': 'IRS 990-EZ', 'irs_990pf': 'IRS 990-PF', 'irs_990n': 'IRS 990-N', 'sunbiz': 'State filing',
                'fdacs': 'FDACS charity registration'}


def board_rows(res):
    """One row per person per nonprofit: titles, years on file, latest pay and hours, sources, and how many other
    current boards (homeowner associations aside) the same name sits on."""
    names = {o['id']: o for o in res['orgs'].values()}
    P = res['people']
    agg = collections.OrderedDict()
    for st in sorted(res['seats'], key=lambda x: (x['tax_year'] or 0)):
        a = agg.setdefault((st['board_key'], st['nonprofit_id']), {'seats': []})
        a['seats'].append(st)
    rows = []
    for (bk, nid), a in agg.items():
        ss = a['seats']
        last = ss[-1]
        o = names[nid]
        p = P[bk]
        cur = [x for x in ss if x['current']]
        board = any(x['board'] for x in (cur or ss))
        role = ('Board' if board else 'Staff') if cur else ('Past board' if any(x['board'] for x in ss) else 'Past staff')
        paid = [x for x in ss if x['compensation']]
        yrs = [x['tax_year'] for x in ss if x['tax_year']]
        other = p['n_current_civic'] - (1 if (cur and board and o['kind'] != HOA_KIND) else 0)
        rows.append({'person_id': bk, 'person': p['display_name'], 'nonprofit_id': nid, 'nonprofit': o['name'], 'ein': o['ein'] or None,
                     'role': role, 'titles': ', '.join(dict.fromkeys(p.strip() for x in reversed(ss) if x['title'] for p in x['title'].split(', ') if p.strip()))[:200] or None,
                     'first_year': min(yrs) if yrs else None, 'last_year': max(yrs) if yrs else None, 'current': bool(cur),
                     'hours_per_week': last['hours'], 'compensation': paid[-1]['compensation'] if paid else None,
                     'compensation_year': paid[-1]['tax_year'] if paid else None,
                     'sources': ', '.join(dict.fromkeys(SOURCE_LABEL.get(x['source'], x['source']) for x in ss)),
                     'other_current_boards': max(other, 0), 'county': res['county'], 'source_url': last['source_url']})
    rows.sort(key=lambda r: (r['nonprofit'], not r['current'], r['role'] != 'Board', r['person']))
    return rows


def business_rows(res):
    """One row per board member per Sunbiz business they appear on, with the business's campaign gifts. A match by name
    alone is kept only when one Sunbiz person in the county has that name; a match on the nonprofit's own Sunbiz filing
    (name and address) is always kept."""
    rows = []
    for bk, p in res['people'].items():
        for b in p.get('businesses', []):
            if b['via'] != 'same_person' and p['same_name_people'] != 1:
                continue
            rows.append({'person_id': bk, 'person': p['display_name'], 'doc_number': b['doc_number'], 'business': b['name'],
                         'business_status': 'Active' if b['status'] == 'A' else 'Inactive',
                         'match': 'Name and address' if b['via'] == 'same_person' else 'Name',
                         'campaign_gifts_total': b['gifts_total'] or 0, 'candidates': ', '.join(b['candidates']) or None,
                         'county': res['county'], 'source_url': ids.sunbiz_url(b['name'], b['doc_number'])})
    rows.sort(key=lambda r: (r['person'], -r['campaign_gifts_total'], r['business'], r['doc_number']))
    return rows


def summary(res):
    S, P = res['seats'], res['people']
    return {
        'nonprofits': len(res['orgs']), 'irs_recognized': sum(1 for o in res['orgs'].values() if o['irs']),
        'sunbiz_only': sum(1 for o in res['orgs'].values() if not o['irs']), 'with_returns': sum(1 for o in res['orgs'].values() if o['filings']),
        'with_board_list': len({s['nonprofit_id'] for s in S}), 'seats': len(S), 'board_people': len(P),
        'on_2plus_current_boards': sum(1 for p in P.values() if p['n_current_civic'] >= 2),
        'official_name_matches': sum(1 for p in P.values() if p['official_id']),
        'linked_to_businesses': sum(1 for p in P.values() if p['n_businesses']),
        'linked_to_donor_businesses': sum(1 for p in P.values() if p['n_donor_businesses']),
        'payment_records': len(res['payments']), 'nonprofits_paid': len({p['nonprofit_id'] for p in res['payments']}),
        'grants': len(res['grants']),
        'fdacs_registrations': sum(1 for o in res['orgs'].values() if o.get('fdacs')),
        'fdacs_joined_by_fein': sum(1 for o in res['orgs'].values() if o.get('fdacs_join') == 'fein'),
        'fdacs_joined_by_name': sum(1 for o in res['orgs'].values() if o.get('fdacs_join') == 'name'),
        'fdacs_only': sum(1 for o in res['orgs'].values() if o.get('fdacs_join') == 'new'),
    }


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else 'bay'
    if not os.path.exists(os.path.join(HERE, key, 'orgs.csv.gz')):
        print(f'nonprofits: no IRS data for {key} (run fetch_irs.py)')
        return
    res = build(key)
    orgs, pays, grants, board, biz, regs = public(res)
    out = {'as_of': datetime.date.today().isoformat(), 'county': key,
           'method': ('Organizations recognized by the IRS with an address in ' + county(key)['name'] + ' (EO Business Master File), plus active Florida '
                      'nonprofit corporations (Sunbiz) with a principal address there. Financials are from the latest 990, 990-EZ or 990-PF e-filed with the IRS; '
                      'government payment records are matched by exact name. Board members are the officers, directors, trustees and key employees '
                      'listed on IRS returns, 990-N postcards, state corporate filings and Florida charity registrations (FDACS), grouped by name '
                      'across boards. Charity registrations are the county\'s registrations in the FDACS Check-A-Charity database, with the financial '
                      'summary each charity reported to the state. Built by data/nonprofits/build_nonprofits.py.'),
           'summary': summary(res), 'nonprofits': orgs, 'payments': pays, 'grants': grants, 'board_members': board, 'board_businesses': biz,
           'charity_registrations': regs}
    json.dump(out, open(os.path.join(HERE, key, 'nonprofits.json'), 'w'), indent=1, ensure_ascii=False, default=str)
    print('nonprofits:', json.dumps(summary(res)))


if __name__ == '__main__':
    main()
