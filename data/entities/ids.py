"""Shared identifiers for BayCounty.me datasets: governments, vendors, people, and structured dates.

    import sys; sys.path.insert(0, 'data/entities'); import ids
    ids.gov_id('Panama City, City of')            -> 'pc'
    ids.vendor_ids('Marshall Bothers')            -> ['marshall-brothers-construction-engineering']
    ids.person_id('Douglas Moore')                -> 'doug-moore'
    ids.parse_date('FY2024')                      -> ('2023-10-01', '2024-09-30', 'fiscal_year')

governments.json is hand-maintained. vendors.json and people.json are written by build_entities.py
(run from data/build.py), so they always reflect the current research files plus the hand-reviewed overrides there.
Nothing here guesses: a name that isn't matched gets None.
"""
import calendar, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
_C = {}


def _load(name):
    if name not in _C:
        try:
            _C[name] = json.load(open(os.path.join(HERE, name)))
        except FileNotFoundError:
            _C[name] = None
    return _C[name]


def reset():
    _C.clear()


# ---------- display casing ----------
# Check registers and some agendas print names in all caps. biz_case gives those a normal business casing; names that
# already have lower-case letters were typed by a person and are left alone.
_UPPER_KEEP = {'LLC', 'LLP', 'LP', 'PA', 'PLLC', 'PC', 'NA', 'USA', 'US', 'FL', 'II', 'III', 'IV', 'ADP', 'AT&T', 'FPL', 'CSX', 'UPS',
               'HVAC', 'AC', 'TV', 'FM', 'AM', 'DBA', 'GIS', 'IT', 'PCB', 'PCBH', 'EMR', 'EMS', 'RV', 'ACH', 'CPA', 'PE', 'DDA',
               'PMT', 'ECSC', 'CRI', 'MWB', 'USFA', 'WSL', 'EPCI', 'EJHG', 'FTS', 'NCMC', 'JDF', 'RDK', 'CK', 'JS&S', 'PBS&J'}
_LOWER = {'and', 'of', 'the', 'for', 'in', 'on', 'at', 'to', 'by', 'a', 'an', 'or', 'de'}
_WORDS3 = set('bay sea oak sun pro air one new top ace all big red car art law lab dog day way old gas oil ice tax box van bus cab fix '
               'net web map pet eye joe bob tom jim ann sam dan ray lee kim fun hot joy key max mix now own pay run sky tee toy two six '
               'ten bar inn spa tan tin mr dr st mt ft go my we me so up oh hi pc ma pa'.split()) - {'pc', 'pa'}
_FIXED = {'INC': 'Inc', 'CO': 'Co', 'CORP': 'Corp', 'LTD': 'Ltd', 'MGM': 'Mgmt', 'MGMT': 'Mgmt', 'SVCS': 'Svcs', 'AMEX': 'Amex', 'VISA': 'Visa',
          'MCDONALD': 'McDonald', 'MCKIM': 'McKim', 'MCMAHON': 'McMahon'}


def _case_word(w, first):
    if re.fullmatch(r'[WK][A-Z]{2,3}-(TV|FM|AM),?', w):  # TV and radio call signs: WJHG-TV
        return w
    core = re.sub(r'[^A-Za-z&]', '', w)
    up = core.upper()
    if not core:
        return w
    if up in _FIXED:
        return w.replace(core, _FIXED[up])
    if up in _UPPER_KEEP or '&' in core or re.search(r'\d', w):
        return w
    if not first and core.lower() in _LOWER:
        return w.lower()
    if len(core) <= 3 and core.lower() not in _WORDS3:  # short initials: CW, RJ, GAC, BGN
        return w
    # Title-case each piece split by apostrophes and hyphens, and keep 's lower: O'NEAL -> O'Neal, HALL'S -> Hall's
    out = re.sub(r"[A-Za-z]+", lambda m: m.group(0).capitalize(), w.lower())
    return re.sub(r"'S\b", "'s", out)


def biz_case(name):
    """'BALDWIN CONTAINER SYSTEMS INC' -> 'Baldwin Container Systems Inc'. Leaves names with lower-case letters as they are."""
    if not name or re.search(r'[a-z]', name) or not re.search(r'[A-Z]', name):
        return name
    words = name.split(' ')
    if len(words) == 1 and len(re.sub(r'[^A-Z]', '', name)) <= 4:  # a lone short acronym: CRI, AMEX, WSL
        return _FIXED.get(name, name)
    return ' '.join(_case_word(w, i == 0) for i, w in enumerate(words))


# ---------- governments ----------
def _gn(s):
    return re.sub(r'\s+', ' ', (s or '').strip().lower())


def _gov_tables():
    if 'gov_alias' in _C:
        return _C['gov_alias'], _C['gov_names']
    d = _load('governments.json')
    alias, names = {}, []
    for g in d['governments']:
        for a in [g['id'], g['name'], g['short']] + g.get('aliases', []):
            alias[_gn(a)] = g['id']
        # names used for the opt-in "contains" match (whole words, longest first); codes are exact-only
        for a in [g['name'], g['short']] + g.get('aliases', []):
            if (' ' in a.strip() or a == g['short']) and len(a) >= 5 and g['kind'] in ('county', 'schools', 'city', 'special_district', 'court'):
                names.append((_gn(a), g['id']))
    names.sort(key=lambda x: -len(x[0]))
    _C['gov_alias'], _C['gov_names'] = alias, names
    return alias, names


def governments():
    return _load('governments.json')['governments']


def gov(gid):
    return next((g for g in governments() if g['id'] == gid), None)


def gov_id(*values, contains=False):
    """First value that resolves to a government id. contains=True also accepts a string that contains
    exactly one government's name as whole words (for office titles like 'Springfield Mayor')."""
    alias, names = _gov_tables()
    for v in values:
        if not isinstance(v, str) or not v.strip():
            continue
        s = _gn(v)
        tries = [s, re.sub(r'\s*\([^)]*\)\s*$', '', s), re.sub(r'\s+-\s+.*$', '', s),
                 re.sub(r',?\s+(seat|district|ward|group)\s+[\w ]+$', '', re.sub(r'\s*\([^)]*\)', '', s)).strip()]
        for t in tries:
            if t in alias:
                return alias[t]
        if contains:
            if ' / ' in s or ' and city of ' in s:
                continue  # two governments named: leave it to a person
            found = [(n, gid) for n, gid in names if re.search(r'(^|\W)' + re.escape(n) + r'($|\W)', s)]
            # 'Panama City Beach' contains 'Panama City': a name inside a longer matched name doesn't count
            found = [(n, gid) for n, gid in found if not any(n != n2 and n in n2 for n2, _ in found)]
            hits = {gid for _, gid in found}
            if len(hits) == 1:
                return hits.pop()
    return None


# ---------- vendors ----------
TRAIL = {'inc', 'incorporated', 'llc', 'lc', 'llp', 'lllp', 'pllc', 'co', 'corp', 'corporation', 'company', 'pa', 'ltd', 'lp', 'fl', 'florida', 'of'}


def vkey(name):
    """Matching key: lowercase, '&' -> and, no parentheticals or punctuation, a leading 'the' and trailing legal
    suffixes ('Inc', 'LLC', 'Co', 'of Florida' ...) dropped, no spaces. 'Florida Architects' keeps 'florida'."""
    s = (name or '').lower().replace('&', ' and ')
    s = re.sub(r'\(.*?\)', ' ', s)
    s = re.sub(r"[’']", '', s)
    toks = re.sub(r'[^a-z0-9 ]', ' ', s).split()
    if toks and toks[0] == 'the':
        toks = toks[1:]
    while len(toks) > 1 and toks[-1] in TRAIL:
        toks = toks[:-1]
    return ''.join(t for t in toks if t != 'and')


def _vendor_tables():
    if 'v_alias' in _C:
        return _C['v_alias'], _C['v_key'], _C['v_by_id']
    d = _load('vendors.json') or {'vendors': [], 'joint': {}}
    alias, key, by = {}, {}, {}
    for v in d['vendors']:
        by[v['id']] = v
        for a in v['aliases']:
            alias[_gn(a)] = [v['id']]
        for k in v.get('keys', []):
            key[k] = v['id']
    for raw, lst in (d.get('joint') or {}).items():
        alias[_gn(raw)] = lst
    _C['v_alias'], _C['v_key'], _C['v_by_id'] = alias, key, by
    return alias, key, by


def vendor_ids(name):
    """All vendor ids for a payee name (a joint award names more than one firm). [] when not a matched vendor."""
    alias, key, _ = _vendor_tables()
    if not name:
        return []
    hit = alias.get(_gn(name))
    if hit is not None:
        return list(hit)
    k = vkey(name)
    return [key[k]] if k in key else []


def vendor_id(name):
    """The vendor id when the name is one firm (for a joint award, the first firm named)."""
    v = vendor_ids(name)
    return v[0] if v else None


def vendor(vid):
    return _vendor_tables()[2].get(vid)


# ---------- people ----------
NICK = {'doug': 'douglas', 'chris': 'christopher', 'dave': 'david', 'bob': 'robert', 'bobby': 'robert', 'rob': 'robert', 'robbie': 'robert',
        'bill': 'william', 'chuck': 'charles', 'jim': 'james', 'jamie': 'james', 'mike': 'michael', 'steve': 'steven', 'stephen': 'steven',
        'tom': 'thomas', 'tommy': 'thomas', 'nick': 'nicholas', 'pat': 'patrick', 'dan': 'daniel', 'ed': 'edward', 'andy': 'andrew',
        'josh': 'joshua', 'sam': 'samuel', 'ken': 'kenneth', 'rick': 'richard'}


def person_key(name):
    """(first, last) with nicknames, titles, middle initials, suffixes and parentheticals removed."""
    s = re.sub(r'\([^)]*\)', ' ', name or '')
    s = re.sub(r'\b(dr|mr|mrs|ms|jr|sr|ii|iii|iv)\b\.?', ' ', s, flags=re.I)
    toks = [t for t in re.sub(r'[^a-z ]', ' ', s.lower()).split() if len(t) > 1]
    if len(toks) < 2:
        return None
    first, last = toks[0], toks[-1]
    return (NICK.get(first, first), last)


def person_alt_keys(name):
    """Keys for 'William (Chuck) Perdue' style names: the nickname in parentheses is also a first name."""
    out = {person_key(name)}
    m = re.search(r'\(([^)]+)\)', name or '')
    if m and ' ' not in m.group(1).strip():
        rest = re.sub(r'\([^)]*\)', ' ', name)
        toks = rest.split()
        if len(toks) >= 2:
            out.add(person_key(m.group(1) + ' ' + toks[-1]))
    return {k for k in out if k}


def _people_tables():
    if 'p_key' in _C:
        return _C['p_key'], _C['p_by_id']
    d = _load('people.json') or {'people': []}
    key, by = {}, {}
    for p in d['people']:
        by[p['id']] = p
        for a in p['aliases'] + [p['name']]:
            for k in person_alt_keys(a):
                key.setdefault(k, p['id'])
    _C['p_key'], _C['p_by_id'] = key, by
    return key, by


DISTRICT = re.compile(r'\s*\((D\d|District \d|Ward [IVX\d]+|Seat \d|Group \d)\)\s*$')


def split_district(name):
    """'Daniel Raffield (D1)' -> ('Daniel Raffield', 'District 1'); other names are returned unchanged."""
    if not isinstance(name, str):
        return name, None
    m = DISTRICT.search(name)
    if not m:
        return name, None
    d = m.group(1)
    d = re.sub(r'^D(\d)$', r'District \1', d)
    return name[:m.start()].strip(), d


def person_id(name):
    if not isinstance(name, str) or not name.strip():
        return None
    key, _ = _people_tables()
    for k in person_alt_keys(split_district(name)[0]):
        if k in key:
            return key[k]
    return None


def person(pid):
    return _people_tables()[1].get(pid)


# ---------- dates ----------
MON = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
MON.update({m.lower(): i for i, m in enumerate(calendar.month_name) if m})
MON['sept'] = 9
_MONRX = '|'.join(sorted(MON, key=len, reverse=True))


def _fy(y, start=10):
    y = int(y)
    if start == 1:
        return (f'{y}-01-01', f'{y}-12-31')
    s = f'{y - 1}-{start:02d}-01'
    em = start - 1
    return (s, f'{y}-{em:02d}-{calendar.monthrange(y, em)[1]:02d}')


def _end_of(tok):
    """Last day covered by an ISO-ish token (YYYY, YYYY-MM, YYYY-MM-DD) for comparisons."""
    if len(tok) == 4:
        return tok + '-12-31'
    if len(tok) == 7:
        y, m = map(int, tok.split('-'))
        return f'{tok}-{calendar.monthrange(y, m)[1]:02d}'
    return tok


def _start_of(tok):
    return tok + '-01-01' if len(tok) == 4 else tok + '-01' if len(tok) == 7 else tok


def parse_date(text, fy_start=10):
    """Free-text date -> (date_start, date_end, date_precision).

    precision: day | month | year | fiscal_year | range | approx | unknown. Fiscal years run from fy_start
    (October for local governments, July for the school district): FY2024 = 2023-10-01..2024-09-30.
    'FY2025-26' is one fiscal year (FY2026). Two or more dates become a range from the earliest to the latest,
    unless the most specific date falls inside all the others ('Oct 2010 (FY2011)' -> 2010-10).
    """
    if text is None:
        return None, None, 'unknown'
    if isinstance(text, int):
        text = f'FY{text}'
    t = str(text).strip()
    if not t:
        return None, None, 'unknown'
    m = re.search(r'year ended (\d{4})-(\d{2})-(\d{2})', t, re.I)
    if m:
        y, mo, dd = map(int, m.groups())
        sm = mo % 12 + 1
        s = f'{y - 1 if sm > mo else y}-{sm:02d}-01'
        return s, f'{y}-{mo:02d}-{dd:02d}', 'fiscal_year'
    # resolution, task-order and change-order numbers look like dates ("Res. 19-76", "Task Order 2019-03"): drop them
    t = re.sub(r'\b(res\.?|resolution|task order|change order|co)\s*#?\s*[a-z]*\d[\w-]*', ' ', t, flags=re.I)
    t = re.sub(r'\b(\d{4} roll|since \d{4}( roll)?)\b', ' ', t, flags=re.I)
    # the text outside parentheses decides; a parenthetical is used only when the rest names no date
    main = re.sub(r'\([^)]*\)', ' ', t)
    if re.search(r'\d{4}', main) and main != t:
        return parse_date(main, fy_start)
    approx = bool(re.match(r'^(c\.|ca\.|circa|about|around)\s', t, re.I))
    toks = []  # (start, end, precision, pos)
    used = []

    def add(m, s, e, p):
        if any(m.start() < b and m.end() > a for a, b in used):
            return
        used.append((m.start(), m.end())); toks.append((s, e, p, m.start()))

    for m in re.finditer(r'\bFY\s?(\d{4})\s?-\s?(?:FY\s?)?(\d{2,4})\b', t, re.I):
        a, b = int(m.group(1)), m.group(2)
        b = int(b) if len(b) == 4 else int(str(a)[:2] + b)
        if len(m.group(2)) == 2 and b == a + 1:  # FY2025-26 = the fiscal year ending in 2026
            s, e = _fy(b, fy_start); add(m, s, e, 'fiscal_year')
        else:
            add(m, _fy(a, fy_start)[0], _fy(b, fy_start)[1], 'range')
    for m in re.finditer(r'\b(?<!-)(\d{4})-(\d{2})(?!\d|-\d{4})\b', t):  # 2025-26 school/fiscal year
        a, b = int(m.group(1)), int(m.group(2))
        if b == (a + 1) % 100 and not 1 <= b <= 12 or (b == (a + 1) % 100 and re.search(r'school|fy|fiscal', t, re.I)):
            s, e = _fy(a + 1, fy_start); add(m, s, e, 'fiscal_year')
    for m in re.finditer(r'\bFY\s?(\d{4})\b', t, re.I):
        s, e = _fy(m.group(1), fy_start); add(m, s, e, 'fiscal_year')
    for m in re.finditer(r'\b(\d{4})-(\d{2})-(\d{2})\b', t):
        d = m.group(0); add(m, d, d, 'day')
    for m in re.finditer(r'\b(\d{4})-(\d{2})\b(?!-\d)', t):
        if 1 <= int(m.group(2)) <= 12:
            d = m.group(0); add(m, d, d, 'month')
    for m in re.finditer(r'\b(' + _MONRX + r')\.?\s+(\d{1,2}),\s*(\d{4})\b', t, re.I):
        d = f'{m.group(3)}-{MON[m.group(1).lower()]:02d}-{int(m.group(2)):02d}'; add(m, d, d, 'day')
    for m in re.finditer(r'\b(' + _MONRX + r')\.?\s+(\d{4})\b', t, re.I):
        d = f'{m.group(2)}-{MON[m.group(1).lower()]:02d}'; add(m, d, d, 'month')
    for m in re.finditer(r'\b(19[5-9]\d|20[0-4]\d)\s?-\s?(19[5-9]\d|20[0-4]\d)\b', t):
        add(m, m.group(1), m.group(2), 'range')
    for m in re.finditer(r'\b(19[5-9]\d|20[0-4]\d)\b', t):
        add(m, m.group(1), m.group(1), 'year')
    if not toks:
        return None, None, 'unknown'
    before = re.search(r'\bbefore\s+(\d{4})\b', t, re.I)
    if before:
        return None, str(int(before.group(1)) - 1), 'approx'
    if re.match(r'^(spent\s+)?through\b|^to\b|^until\b', t, re.I) and len(toks) == 1:
        s, e, p, _ = toks[0]
        return None, e, p
    rank = {'day': 0, 'month': 1, 'year': 3, 'fiscal_year': 2, 'range': 4}
    if len(toks) == 1:
        s, e, p, _ = toks[0]
    else:
        best = min(toks, key=lambda x: rank[x[2]])
        inside = all(_start_of(o[0]) <= _start_of(best[0]) and _end_of(best[1]) <= _end_of(o[1]) for o in toks)
        if inside:
            s, e, p = best[0], best[1], best[2]
        else:
            s = min(toks, key=lambda x: _start_of(x[0]))[0]
            e = max(toks, key=lambda x: _end_of(x[1]))[1]
            p = 'range'
    if approx:
        p = 'approx'
    return s, e, p


def date_fields(text, fy_start=10):
    s, e, p = parse_date(text, fy_start)
    return {'date_start': s, 'date_end': e, 'date_precision': p}


# ---------- votes ----------
def vote_ids(votes):
    """Stable id per recorded vote: body:date:first-words-of-item, with -2, -3 ... when two votes would share one."""
    out, seen = [], {}
    for v in votes:
        base = f'{v["body"]}:{v["date"]}:' + re.sub(r'[^a-z0-9]+', '-', (v.get('item') or '').lower())[:40].strip('-')
        seen[base] = seen.get(base, 0) + 1
        out.append(base if seen[base] == 1 else f'{base}-{seen[base]}')
    return out
