"""One registry of every named entity on the site, and every documented connection between them.

Every company, official, candidate, nonprofit, board member, business and government gets one entity id and one
profile URL, so every page links a name the same way (site/entity_links.py, and BC.href in site.js for page scripts).

    entity_id      kind        profile page
    gov:pc         government  /governments/panama-city (the nine main governments), else /profile/gov/<id>
    vendor:<id>    company     /public-money/vendors/<id> when it has a vendor page, else /profile/vendor/<id>
    person:<id>    official or candidate (data/entities/people.json)           /people/<id>
    nonprofit:<id> nonprofit (data/nonprofits)                                 /profile/nonprofit/<id>
    member:<id>    nonprofit board member, as named in public filings          /profile/member/<id>
    owner:<id>     person who runs a registered business and gave to a campaign  /profile/owner/<id>
    business:<id>  registered business (Sunbiz document number, lowercased), or a named payee with no vendor id
    committee:<id> PAC, party or campaign committee that gave to a campaign

Only rows already published in public datasets are used, so nothing here is more private than the open data:
individual campaign donors appear only when they run a registered business (dataset owner-gifts: same name and
street address as a Sunbiz officer or agent), shared-owner groups and official name
matches are added by the API from their database-only datasets after an admin confirms them (api/_entities.js), and
unnamed grant recipients and property owners are left out.

Published as two datasets (site/page_datasets.py): entity-profiles (one row per entity) and entity-connections
(one row per documented connection, totalled per pair and kind of connection).
"""
import hashlib, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'data', 'entities'))
import ids  # noqa: E402

try:
    from place import PLACE_ID
except Exception:  # pragma: no cover
    PLACE_ID = 'fl-bay'
COUNTY = PLACE_ID.split('-', 1)[-1]

KIND_LABEL = {'gov': 'Government', 'vendor': 'Company', 'person': 'Official or candidate', 'nonprofit': 'Nonprofit',
              'member': 'Nonprofit board member', 'owner': 'Business owner', 'business': 'Business', 'committee': 'Committee or PAC'}
# relation -> (label from the "from" side, label from the "to" side)
RELATION = {
    'paid': ('paid', 'was paid by'),
    'gift': ('gave to the campaign of', 'got campaign gifts from'),
    'voted': ('voted on contracts with', 'had contracts voted on by'),
    'serves': ('serves', 'is served by'),
    'served': ('served', 'was served by'),
    'candidate': ('is a candidate for office in', 'has candidates for office'),
    'ran': ('ran for office in', 'had on the ballot'),
    'board': ('sits on the board of', 'has on its board'),
    'runs': ('runs', 'is run by'),
    'grant': ('gave a grant to', 'got a grant from'),
    'related': ('shares a project or address with', 'shares a project or address with'),
    'same': ('is the same organization as', 'is the same organization as'),
}
MAIN_GOVS = None
_C = {}


def _slug(s):
    return re.sub(r'[^a-z0-9]+', '-', (s or '').lower()).strip('-')[:80]


def _norm(s):
    s = re.sub(r"[.,'&]", '', (s or '').lower())
    return ' '.join(w for w in s.split() if w not in ('inc', 'llc', 'co', 'corp', 'company', 'the', 'pa', 'pllc'))


def _main_govs():
    global MAIN_GOVS
    if MAIN_GOVS is None:
        try:
            from govs import GOVS
            MAIN_GOVS = {g['key']: g['slug'] for g in GOVS}
        except Exception:
            MAIN_GOVS = {}
    return MAIN_GOVS


def _vendor_pages():
    if 'vp' not in _C:
        try:
            from vendor_pages import build
            _C['vp'] = set(build())
        except Exception:
            _C['vp'] = set()
    return _C['vp']


def page_url(entity_id):
    """The profile URL for any entity id (the rule every page and script follows)."""
    kind, _, key = entity_id.partition(':')
    if kind == 'gov' and key in _main_govs():
        return f'/governments/{_main_govs()[key]}'
    if kind == 'vendor' and key in _vendor_pages():
        return f'/public-money/vendors/{key}'
    if kind == 'person':
        return f'/people/{key}'
    return f'/profile/{kind}/{key}'


def _ds(did):
    """Rows of one published dataset, with the same ids added as in the downloads."""
    if did not in _C:
        import opendata
        fn = {d[0]: d[3] for d in opendata.datasets()}[did]
        _C[did] = opendata.add_gov_id(did, fn() or [])
    return _C[did]


class Graph:
    def __init__(self):
        self.ents = {}
        self.links = {}
        self.alias = {}  # entity id -> (the entity it is the same as, name as written)

    def ent(self, eid, name, sub=None, gov_id=None, source_url=None, aliases=None):
        e = self.ents.get(eid)
        if not e:
            e = self.ents[eid] = {'entity_id': eid, 'kind': eid.split(':', 1)[0], 'name': name, 'subtitle': sub, 'gov_id': gov_id,
                                  'source_url': source_url, 'aliases': []}
        else:
            e['subtitle'] = e['subtitle'] or sub
            e['gov_id'] = e['gov_id'] or gov_id
            e['source_url'] = e['source_url'] or source_url
        for a in aliases or []:
            if a and a != e['name'] and a not in e['aliases']:
                e['aliases'].append(a)
        return eid

    def link(self, a, b, rel, amount=None, date=None, detail=None, source_url=None, key=''):
        if a == b or a not in self.ents or b not in self.ents:
            return
        k = (a, b, rel, key)
        x = self.links.get(k)
        if not x:
            x = self.links[k] = {'from_id': a, 'to_id': b, 'relation': rel, 'amount': None, 'records': 0, 'dates': [], 'detail': [],
                                 'source_url': source_url}
        x['records'] += 1
        if isinstance(amount, (int, float)):
            x['amount'] = (x['amount'] or 0) + amount
        if date:
            x['dates'].append(str(date))
        if detail and detail not in x['detail']:
            x['detail'].append(detail)
        x['source_url'] = x['source_url'] or source_url


def _gov(G, gid):
    g = ids.gov(gid)
    if not g:
        return None
    return G.ent('gov:' + gid, g['short'], {'county': 'County government', 'city': 'City', 'schools': 'School district'}.get(g['kind'], g['kind'].replace('_', ' ').capitalize()), gid)


def person_title(p):
    """'Mayor, Panama City · 2026 candidate for Panama City Commission, Ward 2' from people.json roles."""
    roles = p.get('roles') or []
    short = lambda g: (ids.gov(g or '') or {}).get('short', g or '')
    def first(src, pre=None):
        for r in roles:
            if r.get('source') == src and (pre is None or (r.get('role') or '').startswith(pre)):
                return r
    t = None
    r = first('salaries') or first('officials-pay')
    if r:
        t = f"{r['role']}, {short(r['gov_id'])}" if short(r['gov_id']).lower() not in r['role'].lower() else r['role']
    elif first('campaign', 'officeholder'):
        t = first('campaign', 'officeholder')['role'].split(':', 1)[1].strip()
    elif first('officeholders'):  # an elected seat since 2016 (officeholder-terms): more exact than the vote records' member lists
        oh = [x for x in roles if x.get('source') == 'officeholders']
        r = next((x for x in oh if not x['role'].startswith('former')), oh[-1])  # the seat held now, else the latest one
        t = r['role'][:1].upper() + r['role'][1:] + f', {short(r["gov_id"])}'
    elif first('votes', 'board member'):
        r = first('votes', 'board member')
        t = f"Board member, {short(r['gov_id'])}" + (f" ({r['seat']})" if r.get('seat') and not str(r['seat']).isdigit() else '')
    elif first('votes', 'former'):
        t = f"Former board member, {short(first('votes', 'former')['gov_id'])}"
    past = [r for r in roles if r.get('source') == 'campaign_history']
    if past and not t:  # someone known here only from a past campaign (campaign-history): their latest race
        r = max(past, key=lambda r: r.get('year') or 0)
        t = f"Ran for {r['office']} in {r['year']}" + (' (won)' if r.get('outcome') == 'won' else '')
    c = first('candidates_2026') or first('finance_2026')
    if c:
        race = _race(c['role'], c.get('gov_id')) if ':' in c['role'] else ''
        race = f'{race}, {short(c["gov_id"])}' if race and short(c['gov_id']).lower() not in race.lower() else race or short(c['gov_id'])
        again = t and _seat(race) and _seat(race) == _seat(t) and short(c['gov_id']).lower() in t.lower()
        t = t + ' · running again in 2026' if again else (t + ' · ' if t else '') + f'2026 candidate for {race}'
    return t


# what a person is, by their strongest current role (shown where a list would otherwise say "Official or candidate")
PERSON_LABEL = {'elected': 'Elected official', 'staff': 'Department leader', 'candidate': 'Candidate', 'former': 'Former official'}
ROMAN = {'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5', 'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9', 'x': '10'}
SEAT_RE = re.compile(r'\b(ward|district|seat|group|zone|place)\s+(\d+|[ivx]+)\b|\b(mayor|at[- ]large|chair)\b')


def _seat(text):
    """'Commissioner, Ward III' and 'City Commission, Ward 3' -> 'ward 3'; 'Springfield Mayor' -> 'mayor'."""
    m = SEAT_RE.search((text or '').lower())
    if not m:
        return None
    return f"{m.group(1)} {ROMAN.get(m.group(2), m.group(2))}" if m.group(1) else m.group(3).replace('-', ' ')


def _sentence(t):
    """'Police Chief' -> 'Police chief', keeping acronyms and words after a comma ('CRA Director', 'Ward 4')."""
    t = re.sub(r'\b(Ward|District|Seat|Group) ([IVX]+)\b', lambda m: f"{m.group(1)} {ROMAN[m.group(2).lower()]}", (t or '').strip())
    words = t.split(' ')
    out = [words[0][:1].upper() + words[0][1:]] if words else []
    for i, w in enumerate(words[1:], 1):
        keep = w.isupper() or words[i - 1].endswith((',', '(')) or w[:1].isdigit() or w.lower() in ROMAN
        out.append(w if keep or not w[:1].isupper() else w.lower())
    return ' '.join(out)


def _race(text, gid):
    """A race or office as written in the filings, without the government's name: 'City of Springfield Mayor' -> 'Mayor'."""
    t = (text or '').split(':', 1)[-1].strip()
    g = ids.gov(gid or '') or {}
    for pre in sorted({g.get('name') or '', 'City of ' + (g.get('short') or ''), 'Town of ' + (g.get('short') or ''), g.get('short') or ''}, key=len, reverse=True):
        if pre.strip() and t.lower().startswith(pre.lower() + ' '):
            t = t[len(pre):].strip(' ,')
            break
    return t[:1].upper() + t[1:]


def _term_label(t):
    seat = t.get('seat') or ''
    if t.get('appointed') or not re.match(r'(?i)(ward|district|seat|group|zone|place|at[- ]large|\d)', seat):
        return seat  # 'Mayor', 'City Manager'
    return f"{re.sub(r' and Superintendent$', '', t.get('body') or '')}, {seat}"


def service(p, gid, terms):
    """Everything one person does or did for one government, as one connection: relation, detail, dates, kind.

    'Commissioner, Ward 4 (2022–now) · Running again in 2026' instead of one row per record that names them."""
    roles = [r for r in p.get('roles') or [] if r.get('gov_id') == gid and r.get('source') != 'campaign_history']
    now = [t for t in terms if not t.get('end_date')]
    past = sorted((t for t in terms if t.get('end_date')), key=lambda t: t['end_date'], reverse=True)
    def yrs(t):
        a, b = (t.get('start_date') or '')[:4], (t.get('end_date') or '')[:4]
        return (a if a == b else f"{a}–{b or 'now'}") if a else f'until {b}' if b else 'current'
    parts, seats, kind = [], set(), None
    pay = [r for r in roles if r.get('source') in ('salaries', 'officials-pay') and r.get('role')]
    for t in now:
        seat = _seat(t.get('seat')) or (t.get('seat') or '').lower()
        title = next((r['role'] for r in pay if _seat(r['role']) == seat), None)  # 'Commissioner, Ward 4' from the pay record
        parts.append(f'{_sentence(title) if title else _term_label(t)} ({yrs(t)})')
        seats.add(seat)
        kind = kind or ('staff' if t.get('appointed') else 'elected')
    # pay records: department leaders, and elected officials' titles when the seat isn't already listed
    jobs = {}
    elected_now = any(not t.get('appointed') for t in now)
    for r in pay:
        k = _seat(r['role']) or r['role'].lower()
        if k in seats or any(s and s in r['role'].lower() for s in seats):
            continue
        if elected_now and not _seat(r['role']) and re.search(r'(?i)commission|council|board|mayor', r['role']):
            continue  # 'County Commissioner' from the state pay list, already shown with its district
        jobs.setdefault(re.sub(r'[^a-z0-9]+', ' ', r['role'].lower()).strip(), r)
    # the campaign filing and vote records are older than the seat terms, so they count only when there are no terms
    elected_title = None if terms else next((r for r in roles if r.get('source') == 'campaign' and (r.get('role') or '').startswith('officeholder')), None)
    for r in jobs.values():
        parts.append(_sentence(r['role']))
        kind = kind or ('elected' if elected_title else 'staff')
    if not terms and not jobs:  # no seat or pay record: the campaign filing, else the vote records
        board = next((r for r in roles if r.get('source') == 'votes' and r.get('role') == 'board member'), None)
        if elected_title:
            parts.append(_race(elected_title['role'], gid))
            kind = 'elected'
        elif board:
            parts.append('Board member' + (f", {board['seat']}" if board.get('seat') and not str(board['seat']).isdigit() else ''))
            kind = 'elected'
    if elected_title and kind == 'staff':
        kind = 'elected'
    cand = next((r for r in roles if r.get('source') == 'candidates_2026'), None) or next((r for r in roles if r.get('source') == 'finance_2026'), None)
    if cand:
        race = _race(cand['role'], gid)
        same = _seat(race) and (_seat(race) in seats or (elected_title and _seat(race) == _seat(elected_title['role'])))
        parts.append('Running again in 2026' if same else f'2026 candidate for {race}')
        kind = kind or 'candidate'
    for t in past:
        parts.append(f'{_term_label(t)} ({yrs(t)})')
    if not past and not parts and any('former' in (r.get('role') or '') for r in roles):
        parts.append(_sentence(next(r['role'] for r in roles if 'former' in (r.get('role') or ''))))
    if not parts:
        return None
    if not kind:
        kind = 'former'
    rel = {'elected': 'serves', 'staff': 'serves', 'candidate': 'candidate', 'former': 'served'}[kind]
    dates = sorted({d for t in terms for d in (t.get('start_date'), t.get('end_date')) if d})
    src = next((t.get('source_url') for t in now + past if t.get('source_url')), None)
    return {'relation': rel, 'detail': ' · '.join(dict.fromkeys(p for p in parts if p)), 'dates': dates, 'source_url': src, 'kind': kind}


def build():
    if 'G' in _C:
        return _C['G']
    G = Graph()
    for g in ids.governments():
        _gov(G, g['id'])

    # officials, department leaders and candidates
    for p in (ids._load('people.json') or {'people': []})['people']:
        roles = p.get('roles') or []
        sub = person_title(p)
        G.ent('person:' + p['id'], p['name'], sub, (p.get('gov_ids') or [None])[0], aliases=p.get('aliases'))

    # one "serves" row per person and government, with every role from every source folded in (pay records, elected
    # seats from officeholder-terms, vote records, campaign filings and 2026 candidate lists all name the same people)
    terms = defaultdict(list)
    for t in _ds('officeholder-terms'):
        if t.get('person_id') and 'person:' + t['person_id'] in G.ents:
            terms[(t['person_id'], t['gov_id'])].append(t)
    for p in (ids._load('people.json') or {'people': []})['people']:
        pid = 'person:' + p['id']
        govs = list(dict.fromkeys([r['gov_id'] for r in p.get('roles') or [] if r.get('gov_id')] + [g for (i, g) in terms if i == p['id']]))
        kinds = set()
        for gid in govs:
            sv = service(p, gid, terms.get((p['id'], gid), []))
            if sv and 'gov:' + gid in G.ents:
                kinds.add(sv['kind'])
                G.link(pid, 'gov:' + gid, sv['relation'], None, None, sv['detail'], sv['source_url'])
                G.links[(pid, 'gov:' + gid, sv['relation'], '')]['dates'] = sv['dates']
        G.ents[pid]['label'] = next((PERSON_LABEL[k] for k in PERSON_LABEL if k in kinds), None)

    # every local race they ran in since 2016 (campaign-history), one link per person, government and office
    for r in _ds('campaign-history'):
        if r.get('person_id') and 'person:' + r['person_id'] in G.ents and r.get('gov_id') and 'gov:' + r['gov_id'] in G.ents:
            G.link('person:' + r['person_id'], 'gov:' + r['gov_id'], 'ran', r.get('total_raised'), r.get('election_date'),
                   f"{_race(r['office'], r['gov_id'])}, {r['election_year']}" + (f" ({r['outcome']})" if r.get('outcome') else ''), r.get('report_url'), key=f"ran:{r['office']}:{r['election_year']}")
            G.ents['person:' + r['person_id']]['label'] = G.ents['person:' + r['person_id']].get('label') or 'Past candidate'

    # companies (every vendor id, with or without a vendor page)
    for v in (ids._load('vendors.json') or {'vendors': []})['vendors']:
        G.ent('vendor:' + v['id'], v['name'], 'Company paid or hired by local governments', (v.get('gov_ids') or [None])[0], aliases=[a for a in v['aliases'] if not a.isupper()])

    # nonprofits
    np_names = {}
    for n in _ds('nonprofits'):
        nid = 'nonprofit:' + n['nonprofit_id']
        np_names[n['nonprofit_id']] = nid
        G.ent(nid, ids.biz_case(n['name']), ' · '.join(x for x in [n.get('kind') or n.get('category'), n.get('city')] if x) or 'Nonprofit', None,
              n.get('source_url') or n.get('sunbiz_url'))

    # payments: every government and agency payment record (connections-payments), totalled per payer, payee and type
    payee_np = {r['entity_id']: r['nonprofit_id'] for r in _ds('connections-payees') if r.get('nonprofit_id')}

    def payee(eid, name):
        kind, _, key = eid.partition(':')
        if kind == 'v':
            return 'vendor:' + key
        if kind in ('b', 's'):
            if payee_np.get(eid) and payee_np[eid] in np_names:
                return np_names[payee_np[eid]]
            return G.ent('business:' + key, name, 'Business paid by a local government')
        if kind == 'g':
            gid = ids.gov_id(name)
            return 'gov:' + gid if gid and 'gov:' + gid in G.ents else None
        return None  # property owners, unnamed and grouped grant recipients stay off profiles
    for r in _ds('connections-payments'):
        to = payee(r['entity_id'], r['payee'])
        gid = r.get('payer_gov_id')
        if not to or not gid or 'gov:' + gid not in G.ents:
            continue
        via = r['payer'] if r['payer_kind'] != 'government' else None  # a CRA or tourism agency pays as itself
        G.link('gov:' + gid, to, 'paid', r.get('amount') if not r.get('inside_project_total') else None, r.get('date'),
               r['record_type'] + (f' ({via})' if via else ''), r.get('source_url'), key=r['record_type'] + (via or ''))
    for eid, npid in payee_np.items():  # a payee that is also a local nonprofit
        if eid.startswith('v:') and npid in np_names:
            G.link('vendor:' + eid[2:], np_names[npid], 'same', detail='Matched by name to the nonprofit record')

    for r in _ds('connections-links'):
        a, b = payee(r['entity_a'], r['name_a']), payee(r['entity_b'], r['name_b'])
        if a and b:
            G.link(a, b, 'related', detail=r['connection'], source_url=r.get('source_url'), key=r['connection'][:40])

    # business donors: Sunbiz document numbers (and vendor ids) for donor names, so a donor, a board member's business
    # and a vendor are one entity
    doc_of, doc_vendor = {}, {}
    for r in _ds('business-donor-sunbiz'):
        if r.get('sunbiz_doc_number'):
            doc_of[_norm(r['contributor'])] = r['sunbiz_doc_number'].lower()
            if r.get('vendor_id'):
                doc_vendor[r['sunbiz_doc_number'].lower()] = r['vendor_id']

    def business(doc, name, sub=None, url=None):
        doc = doc.lower()
        if doc in doc_vendor and 'vendor:' + doc_vendor[doc] in G.ents:
            G.alias['business:' + doc] = ('vendor:' + doc_vendor[doc], ids.biz_case(name))  # /profile/business/<doc> still finds it
            return 'vendor:' + doc_vendor[doc]
        return G.ent('business:' + doc, ids.biz_case(name), sub or 'Registered business', None, url or
                     ids.sunbiz_url(name, doc))

    # campaign gifts from organizations (never individuals) to officials and candidates
    for r in _ds('connections-gifts'):
        pid = ids.person_id(r['official'])
        if not pid or 'person:' + pid not in G.ents:
            continue
        if r.get('payee_entity_id'):
            frm = payee(r['payee_entity_id'], r['donor'])
        elif r['donor_type'] == 'business':
            doc = doc_of.get(_norm(r['donor']))
            frm = business(doc, r['donor']) if doc else G.ent('business:' + _slug(r['donor']), ids.biz_case(r['donor']), 'Business that gave to a local campaign')
        else:
            frm = G.ent('committee:' + _slug(r['donor']), ids.biz_case(r['donor']), {'pac': 'Political committee', 'committee': 'Committee'}.get(r['donor_type'], 'Organization') + ' that gave to a local campaign')
        if frm:
            G.link(frm, 'person:' + pid, 'gift', r.get('amount'), r.get('dates'), (r.get('office') or '') + (' (2026 candidate)' if r.get('candidate_2026') else f" ({r['past_campaign_year']} campaign)" if r.get('past_campaign_year') else ''),
                   r.get('report_url'), key=r.get('office') or '')

    # recorded votes on a vendor's contracts (data/votes/contract_votes.json), per member and vendor
    try:
        import json
        cv = json.load(open(os.path.join(HERE, '..', 'data', 'votes', 'contract_votes.json')))['links']
        votes = json.load(open(os.path.join(HERE, '..', 'data', 'votes', 'votes.json')))['votes']
    except FileNotFoundError:
        cv, votes = [], []
    tally = defaultdict(lambda: defaultdict(int))
    meta = {}
    for l in cv:
        v = votes[l['vote_index']]
        for name, val in (v.get('by_member') or {}).items():
            pid = ids.person_id(name)
            for vid in l['vendor_ids']:
                if pid and 'person:' + pid in G.ents and 'vendor:' + vid in G.ents:
                    k = (pid, vid)
                    tally[k][str(val).lower()] += 1
                    meta.setdefault(k, []).append((v['date'], v.get('source_url'), l.get('record_amount')))
    for (pid, vid), t in tally.items():
        m = sorted(meta[(pid, vid)])
        for d, u, a in m:
            G.link('person:' + pid, 'vendor:' + vid, 'voted', None, d, None, u)
        G.links[('person:' + pid, 'vendor:' + vid, 'voted', '')]['detail'] = [', '.join(f'{n} {k}' for k, n in sorted(t.items(), key=lambda kv: -kv[1]))]

    # nonprofit boards (public IRS and state filings) and board members' businesses
    for r in _ds('nonprofit-board-members'):
        nid = np_names.get(r['nonprofit_id'])
        if not nid:
            continue
        mid = G.ent('member:' + r['person_id'], ids.person_case(r['person']), 'Nonprofit board member', None)
        yrs = f"{r['first_year']}" + (f"–{r['last_year']}" if r.get('last_year') and r['last_year'] != r['first_year'] else '') if r.get('first_year') else None
        G.link(mid, nid, 'board', r.get('compensation'), yrs, ' · '.join(x for x in [r.get('titles') or r.get('role'), 'current' if r.get('current') else None] if x),
               r.get('source_url'), key=r.get('titles') or '')
    for r in _ds('nonprofit-board-businesses'):
        mid = 'member:' + r['person_id']
        if mid not in G.ents:
            continue
        b = business(r['doc_number'], r['business'], 'Registered business' + (f" ({r['business_status'].lower()})" if r.get('business_status') and r['business_status'] != 'Active' else ''), r.get('source_url'))
        G.link(mid, b, 'runs', detail='Matched by ' + (r.get('match') or 'name').lower(), source_url=r.get('source_url'))

    # people who run a registered business and gave to a campaign personally (data/campaign/owner_gifts.py)
    for r in _ds('owner-gifts'):
        pid = r.get('candidate_id')
        if not pid or 'person:' + pid not in G.ents:
            continue
        oid = G.ent(r['donor_id'], r['donor'], 'Runs a registered business · gave to a local campaign')
        for doc, name in zip(r['business_doc_numbers'].split('; '), r['businesses'].split('; ')):
            b = business(doc, name) if doc else None
            if b and (oid, b, 'runs', 'sunbiz') not in G.links:  # once per business, not once per campaign row
                G.link(oid, b, 'runs', detail='Same name and address on Sunbiz', key='sunbiz')
        G.link(oid, 'person:' + pid, 'gift', r.get('amount'), r.get('first_date'), r.get('office'), r.get('source_url'), key=r.get('office') or '')
        if r.get('last_date') and r['last_date'] != r.get('first_date'):
            G.links[(oid, 'person:' + pid, 'gift', r.get('office') or '')]['dates'].append(r['last_date'])

    for r in _ds('nonprofit-grants'):
        a, b = np_names.get(r['grantor_id']), np_names.get(r.get('recipient_id'))
        if a and b:
            G.link(a, b, 'grant', r.get('cash'), r.get('tax_year'), r.get('purpose'), r.get('source_url'))

    _C['G'] = G
    return G


def _dates(ds):
    toks = sorted(t for d in ds for t in re.findall(r'\d{4}(?:-\d{2}(?:-\d{2})?)?', d))
    return (toks[0], toks[-1]) if toks else (None, None)


def connection_rows():
    G = build()
    out = []
    for x in G.links.values():
        a, b = G.ents[x['from_id']], G.ents[x['to_id']]
        first, last = _dates(x['dates'])
        lid = hashlib.md5('|'.join([x['from_id'], x['to_id'], x['relation'], '; '.join(x['detail'])]).encode()).hexdigest()[:16]
        out.append({'link_id': lid, 'from_id': x['from_id'], 'from_name': a['name'], 'from_kind': a['kind'], 'from_url': page_url(x['from_id']),
                    'to_id': x['to_id'], 'to_name': b['name'], 'to_kind': b['kind'], 'to_url': page_url(x['to_id']), 'relation': x['relation'], 'relation_label': RELATION[x['relation']][0],
                    'amount': round(x['amount'], 2) if x['amount'] is not None else None, 'records': x['records'], 'first_date': first, 'last_date': last,
                    'detail': '; '.join(x['detail'])[:500] or None, 'source_url': x['source_url'], 'county': COUNTY})
    out.sort(key=lambda r: (r['from_id'], r['relation'], -(r['amount'] or 0), r['to_id']))
    return out


def profile_rows():
    G = build()
    deg, got, gave = defaultdict(int), defaultdict(float), defaultdict(float)
    for x in G.links.values():
        deg[x['from_id']] += 1
        deg[x['to_id']] += 1
        if x['relation'] in ('paid', 'gift', 'grant') and x['amount']:
            gave[x['from_id']] += x['amount']
            got[x['to_id']] += x['amount']
    out = []
    for eid, e in G.ents.items():
        keep = e['kind'] in ('gov', 'person', 'nonprofit', 'vendor') or deg[eid]  # every vendor: page names link to them
        if not keep:
            continue
        out.append({'entity_id': eid, 'kind': e['kind'], 'kind_label': e.get('label') or KIND_LABEL[e['kind']], 'name': e['name'], 'subtitle': e['subtitle'],
                    'page_url': page_url(eid), 'aliases': e['aliases'] or None, 'connections': deg[eid],
                    'amount_received': round(got[eid], 2) or None, 'amount_given': round(gave[eid], 2) or None,
                    'gov_id': e['gov_id'], 'county': COUNTY, 'source_url': e['source_url']})
    for aid, (target, name) in G.alias.items():  # the same organization under another id: a row that points at the real profile
        t = G.ents[target]
        out.append({'entity_id': aid, 'kind': aid.split(':')[0], 'kind_label': KIND_LABEL[aid.split(':')[0]], 'name': name, 'subtitle': f"Same organization as {t['name']}",
                    'page_url': page_url(target), 'aliases': None, 'connections': 0, 'amount_received': None, 'amount_given': None,
                    'gov_id': None, 'county': COUNTY, 'source_url': None})
    out.sort(key=lambda r: (r['kind'], r['entity_id']))
    return out


def neighbors(eid, limit=None):
    """[(link, other_entity, direction)] for one entity, largest amounts first (used by the static profile pages)."""
    G = build()
    if 'adj' not in _C:
        adj = defaultdict(list)
        for x in G.links.values():
            adj[x['from_id']].append((x, 'out'))
            adj[x['to_id']].append((x, 'in'))
        _C['adj'] = adj
    rows = [(x, G.ents[x['to_id'] if d == 'out' else x['from_id']], d) for x, d in _C['adj'].get(eid, [])]
    rows.sort(key=lambda t: (-(t[0]['amount'] or 0), t[1]['name']))
    return rows[:limit] if limit else rows
