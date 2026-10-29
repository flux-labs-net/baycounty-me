"""Overlaps between datasets (/connections/overlaps): records from different sources that name the same company,
organization or person, put side by side.

Everything here is built from data the site already publishes; nothing is new about any one record. What is new is
the join: a vote read from the minutes that names a company that gave to the member who cast it, a company on an
agenda, the company behind a development project, a bid from notice to vote to award, companies paid by one government
that share an officer, chamber board members whose company is a donor or a vendor, emergency purchases from donors,
and money raised next to votes won.

Names in vote text and agendas are matched to profiles from the entity graph (site/entity_graph.py): company names
with their usual spellings (the same phrases data/campaign/build_contract_votes.py uses), nonprofits and registered
businesses with at least two distinctive words. A match says the record names the organization, not why anyone voted
as they did. Individual donors are never named; business owners are named only through owner-gifts (CLAUDE.md).

Two links go into the entity graph itself (entity_graph.build calls add_graph_links): 'motion' (an official voted on
a motion that names the company or organization) and 'agenda' (the organization is named on a board's agenda).
Overlaps that need hand-confirmed matches (officials' own businesses, officials on nonprofit boards) or rows that only
the database holds (the city checkbooks, school grades and spending) are joined live by api/_overlaps.js.
"""
import collections, datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
for _p in (os.path.join(DATA, 'entities'), os.path.join(DATA, 'campaign'), os.path.join(DATA, 'sunbiz')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import ids  # noqa: E402

_C = {}
TRAIL = {'inc', 'incorporated', 'llc', 'l', 'c', 'corp', 'corporation', 'co', 'company', 'pa', 'pllc', 'lp', 'llp', 'ltd', 'the'}
# words that alone make no name: places and plain business words
GENERIC = {'gulf', 'coast', 'bay', 'county', 'panama', 'city', 'beach', 'florida', 'fl', 'north', 'south', 'east', 'west', 'st', 'saint',
           'andrews', 'emerald', 'lynn', 'haven', 'mexico', 'callaway', 'springfield', 'parker', 'of', 'and', 'the', 'a', 'for', 'in', 'at',
           'services', 'service', 'group', 'center', 'centre', 'association', 'inc', 'llc', 'company', 'construction', 'contracting',
           'engineering', 'solutions', 'systems', 'consultants', 'associates', 'enterprises', 'holdings', 'properties', 'management',
           'development', 'church', 'club', 'foundation', 'society', 'council', 'department', 'office', 'school', 'schools', 'district',
           'board', 'commission', 'community', 'national', 'american', 'united', 'states', 'state', 'first', 'new', 'home', 'homes',
           'park', 'parks', 'police', 'fire', 'public', 'works', 'utility', 'utilities', 'water', 'sewer', 'airport', 'port', 'authority',
           'chamber', 'commerce', 'friends', 'inc', 'trust', 'fund', 'project', 'program', 'citizens', 'health', 'care', 'medical'}
GENERIC |= {'underground', 'leasing', 'striping', 'paving', 'equipment', 'supply', 'rentals', 'repair'}
# names that end like a place (a street, park or dock) are read as the place in minutes, not the company
PLACE_END = {'street', 'st', 'avenue', 'ave', 'road', 'rd', 'boulevard', 'blvd', 'drive', 'dr', 'park', 'point', 'dock', 'pier', 'lake', 'island',
             'landing', 'harbor', 'marina', 'plaza', 'parkway', 'highway', 'hwy', 'lane', 'way', 'trail', 'bridge', 'bayou', 'creek', 'beach'}
PUBLIC_BODY = re.compile(r'\b(department of|state college|university|school board|sheriff|clerk of|county of|city of|state of|transportation)\b')


def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', (s or '').lower().replace('&', ' and '))).strip()


def _phrase(name):
    """A name as words without legal endings and a leading 'the'; None when too plain to find in free text."""
    toks = norm(re.sub(r'\(.*?\)', ' ', name or '')).split()
    while toks and toks[-1] in TRAIL:
        toks = toks[:-1]
    while toks and toks[0] == 'the':
        toks = toks[1:]
    if len(toks) < 2 or len(''.join(toks)) < 10 or all(t in GENERIC or re.match(r'^\d+(st|nd|rd|th)?$', t) for t in toks):
        return None
    p = ' '.join(toks)
    if toks[-1] in PLACE_END or PUBLIC_BODY.search(p):
        return None
    return p


def _dates(ds):
    return sorted({m for d in ds or [] for m in re.findall(r'\d{4}-\d{2}-\d{2}', str(d))})


def _money(x):
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return None


# --- votes ----------------------------------------------------------------------------------------------------------

def all_votes():
    """Every recorded vote: hand-researched (votes.json) and read from minutes (minutes_votes.json), with one id each."""
    if 'votes' in _C:
        return _C['votes']
    from govs import gov_of_body
    vj = json.load(open(os.path.join(DATA, 'votes', 'votes.json')))
    names = {b['id']: re.sub(r'\bCity City\b', 'City', b['name']) for b in vj['bodies']}
    vid = ids.vote_ids(vj['votes'])
    mv = (json.load(open(os.path.join(DATA, 'votes', 'minutes_votes.json'))) if os.path.exists(os.path.join(DATA, 'votes', 'minutes_votes.json')) else {}).get('votes') or []
    out = []
    for src, v, i in [('researched', v, vid[n]) for n, v in enumerate(vj['votes'])] + [('minutes', v, v.get('vote_id')) for v in mv]:
        if not v.get('date') or str(v['date'])[:4] < '2016':
            continue
        text = ' '.join(str(v.get(k) or '') for k in ('item', 'headline', 'summary', 'plain_summary'))
        out.append({'vote_id': i or f"{v['body']}:{v['date']}:{len(out)}", 'body': v['body'], 'board': names.get(v['body']), 'gov_id': gov_of_body(v['body']),
                    'date': str(v['date'])[:10], 'headline': v.get('headline') or v.get('item'), 'agenda_item': v.get('item'), 'category': v.get('category'),
                    'amount': _money(v.get('amount')), 'outcome': v.get('outcome'), 'tally': v.get('tally'),
                    'consent': bool(v.get('consent')) or 'consent' in (v.get('item') or '').lower(), 'by_member': v.get('by_member') or {},
                    'source_type': src, 'source_url': v.get('source_url'), '_t': ' ' + norm(text) + ' ', '_raw': text})
    _C['votes'] = out
    return out


def _index(G):
    """phrase -> entity id, from every company, nonprofit and registered business in the graph (and the other names
    those carry). Phrases that point at two different entities are dropped."""
    if 'index' in _C:
        return _C['index']
    from build_contract_votes import alias_phrases
    idx, bad = {}, set()

    def put(p, eid):
        if not p or p in bad:
            return
        if p in idx and idx[p] != eid:
            bad.add(p)
            idx.pop(p, None)
            return
        idx[p] = eid
    for eid, e in G.ents.items():
        kind = e['kind']
        if kind == 'vendor':
            try:
                for p in alias_phrases(eid.split(':', 1)[1]):
                    t = p.split()
                    if (len(t) > 1 or (len(p) >= 8 and p not in GENERIC)) and t[-1] not in PLACE_END and not PUBLIC_BODY.search(p) \
                            and not all(w in GENERIC or w.isdigit() for w in t):
                        put(p, eid)
            except Exception:
                put(_phrase(e['name']), eid)
        elif kind in ('nonprofit', 'business'):
            put(_phrase(e['name']), eid)
            for a in e.get('aliases') or []:
                put(_phrase(a), eid)
    for aid, (target, name) in G.alias.items():
        if G.ents.get(target, {}).get('kind') in ('vendor', 'nonprofit', 'business'):
            put(_phrase(name), target)
    for g in ids.governments():  # a government's own name is never a company
        for n in [g.get('name'), g.get('short')]:
            p = _phrase(n)
            if p:
                idx.pop(p, None)
                bad.add(p)
    _C['index'] = idx
    _C['maxlen'] = max((len(p.split()) for p in idx), default=1)
    return idx


def find_names(G, text):
    """Entity ids named in free text: the longest phrase at each word wins."""
    idx = _index(G)
    toks = norm(text).split()
    out, i, n = {}, 0, _C['maxlen']
    while i < len(toks):
        for k in range(min(n, len(toks) - i), 0, -1):
            p = ' '.join(toks[i:i + k])
            if p in idx:
                out.setdefault(idx[p], p)
                i += k
                break
        else:
            i += 1
    return out


def mentions(G):
    """[(vote, entity id, matched words)] for every vote that names a company or organization."""
    if 'mentions' in _C:
        return _C['mentions']
    out = []
    for v in all_votes():
        for eid, p in find_names(G, v['_t']).items():
            if eid in G.ents:
                out.append((v, eid, p))
    _C['mentions'] = out
    return out


# --- agenda items -----------------------------------------------------------------------------------------------------

def agenda_items():
    p = os.path.join(DATA, 'agendas', 'agenda_items.json')
    return json.load(open(p)).get('items', []) if os.path.exists(p) else []


def _registry():
    if 'reg' not in _C:
        try:
            import build_sunbiz as B
            ents, roles = B.load_registry('bay')
            by = collections.defaultdict(list)
            for e in ents.values():
                by[e['key']].append(e)
            _C['reg'] = (B, ents, roles, by)
        except Exception:
            _C['reg'] = (None, {}, [], {})
    return _C['reg']


def resolve_party(G, name, business=None):
    """A party's profile id: a government, a company, a nonprofit or business already in the graph, else (with
    business, the graph's own business() helper) the one Bay County Sunbiz filing with exactly that name."""
    if not name or len(name) < 3:
        return None
    gid = ids.gov_id(name)
    if gid and 'gov:' + gid in G.ents:
        return 'gov:' + gid
    vid = ids.vendor_id(name)
    if vid and 'vendor:' + vid in G.ents:
        return 'vendor:' + vid
    p = _phrase(name)
    idx = _index(G)
    if p and p in idx:
        return idx[p]
    if business and p:
        B, ents, roles, by = _registry()
        if B:
            hit = by.get(B.biz_key(name)) or []
            if len(hit) == 1 and hit[0].get('status') == 'A':
                return business(hit[0]['doc_number'], hit[0]['name'])
    return None


# --- entity graph links ---------------------------------------------------------------------------------------------------

def add_graph_links(G, business):
    """Called at the end of entity_graph.build(): 'motion' links (official -> company or organization named in a vote
    they cast) and 'agenda' links (organization -> the government whose board has it on an agenda)."""
    tally = collections.defaultdict(collections.Counter)
    last = {}
    for v, eid, _ in mentions(G):
        for name, val in v['by_member'].items():
            pid = ids.person_id(name)
            if not pid or 'person:' + pid not in G.ents or ('person:' + pid, eid, 'voted', '') in G.links:
                continue
            k = ('person:' + pid, eid)
            tally[k][str(val).lower()] += 1
            G.link(k[0], eid, 'motion', None, v['date'], None, v['source_url'])
    for k, t in tally.items():
        G.links[(k[0], k[1], 'motion', '')]['detail'] = [', '.join(f'{n} {x}' for x, n in sorted(t.items(), key=lambda kv: -kv[1]))]
    for it in agenda_items():
        gid = 'gov:' + (it.get('gov') or '')
        if gid not in G.ents or not it.get('date'):
            continue
        for p in it.get('parties') or []:
            eid = resolve_party(G, p, business)
            if eid and not eid.startswith('gov:') and eid in G.ents:
                G.link(eid, gid, 'agenda', it.get('amount') if isinstance(it.get('amount'), (int, float)) else None, it['date'],
                       (it.get('title') or '')[:160], it.get('url'), key=it.get('kind') or '')
    for r in development_matches(G, business):
        G.link(r['company_id'], 'gov:' + r['gov_id'], 'project', None, r.get('applied_date') or r.get('approved_date'),
               r['project'] + (f" ({r['status'].lower()})" if r.get('status') else ''), r.get('source_page') or r.get('source_url'), key=r['project_id'])


# --- shared helpers on the built graph ---------------------------------------------------------------------------------

def _graph():
    from entity_graph import build
    return build()


def _gifts(G):
    """from entity id -> [(person id, amount, dates, report url)] for campaign gifts, and company id -> owner ids."""
    if 'gifts' in _C:
        return _C['gifts']
    gifts, owners = collections.defaultdict(list), collections.defaultdict(set)
    for x in G.links.values():
        if x['relation'] == 'gift' and x['to_id'].startswith('person:'):
            gifts[x['from_id']].append((x['to_id'], x['amount'], _dates(x['dates']), x['source_url']))
        elif x['relation'] == 'runs' and x['from_id'].startswith('owner:'):
            owners[x['to_id']].add(x['from_id'])
    _C['gifts'] = (gifts, owners)
    return _C['gifts']


def _serving(G):
    """government id -> person ids who serve or served it."""
    if 'serving' not in _C:
        s = collections.defaultdict(set)
        for x in G.links.values():
            if x['relation'] in ('serves', 'served') and x['to_id'].startswith('gov:'):
                s[x['to_id'][4:]].add(x['from_id'])
        _C['serving'] = s
    return _C['serving']


def _paid(G):
    """payee id -> {government id: amount} from the payment records."""
    if 'paid' not in _C:
        p = collections.defaultdict(lambda: collections.defaultdict(float))
        for x in G.links.values():
            if x['relation'] in ('paid', 'hired') and x['from_id'].startswith('gov:') and x['amount']:
                p[x['to_id']][x['from_id'][4:]] += x['amount']
        _C['paid'] = p
    return _C['paid']


def _gifts_to(G, eid, people=None):
    """Gifts from a company (or the owners who run it) to people (all when people is None): [(donor id, kind, person, amount, dates, url)]."""
    gifts, owners = _gifts(G)
    out = []
    for d, kind in [(eid, 'company')] + [(o, 'business owner') for o in sorted(owners.get(eid, ()))]:
        for pid, amt, ds, url in gifts.get(d, []):
            if people is None or pid in people:
                out.append((d, kind, pid, amt, ds, url))
    return out


def _url(eid):
    from entity_graph import page_url
    return page_url(eid)


def _name(G, eid):
    return G.ents[eid]['name'] if eid in G.ents else None


def _roll(v):
    return '; '.join(f'{n}: {x}' for n, x in v['by_member'].items()) or None


def _member_ids(v):
    return '; '.join(dict.fromkeys(p for p in (ids.person_id(n) for n in v['by_member']) if p)) or None


# --- datasets -------------------------------------------------------------------------------------------------------

def vote_mentions():
    """One row per recorded vote and company or organization its motion names."""
    from place import PLACE_ID
    G = _graph()
    out = []
    for v, eid, p in mentions(G):
        out.append({'place_id': PLACE_ID, 'vote_id': v['vote_id'], 'date': v['date'], 'gov_id': v['gov_id'], 'board': v['board'],
                    'entity_id': eid, 'entity_name': _name(G, eid), 'entity_kind': G.ents[eid]['kind'], 'entity_url': _url(eid), 'matched_words': p,
                    'headline': v['headline'], 'agenda_item': v['agenda_item'], 'category': v['category'], 'amount': v['amount'], 'outcome': v['outcome'],
                    'tally': v['tally'], 'consent_agenda': v['consent'], 'roll_call': _roll(v), 'member_ids': _member_ids(v),
                    'source_type': v['source_type'], 'source_url': v['source_url']})
    out.sort(key=lambda r: (r['date'], r['vote_id'], r['entity_id']), reverse=True)
    return out


def _timing(ds, day):
    if not ds:
        return None
    b, a = any(d <= day for d in ds), any(d > day for d in ds)
    return 'before and after the vote' if b and a else 'before the vote' if b else 'after the vote'


def donor_votes():
    """One row per member vote on a motion naming a company that gave to that member's campaign, or whose owner did."""
    from place import PLACE_ID
    G = _graph()
    out = []
    for v, eid, p in mentions(G):
        voters = {}
        for n, x in v['by_member'].items():
            pid = ids.person_id(n)
            if pid:
                voters['person:' + pid] = (n, x)
        if not voters:
            continue
        for d, kind, pid, amt, ds, url in _gifts_to(G, eid, set(voters)):
            n, x = voters[pid]
            out.append({'place_id': PLACE_ID, 'vote_id': v['vote_id'], 'date': v['date'], 'gov_id': v['gov_id'], 'board': v['board'],
                        'member': G.ents[pid]['name'], 'member_id': pid, 'member_url': _url(pid), 'member_vote': x,
                        'donor': _name(G, d), 'donor_id': d, 'donor_url': _url(d), 'donor_kind': kind,
                        'company': _name(G, eid), 'company_id': eid, 'company_url': _url(eid), 'gift_amount': round(amt, 2) if amt else None,
                        'gift_first_date': ds[0] if ds else None, 'gift_last_date': ds[-1] if ds else None, 'gift_timing': _timing(ds, v['date']),
                        'headline': v['headline'], 'amount': v['amount'], 'outcome': v['outcome'], 'tally': v['tally'], 'consent_agenda': v['consent'],
                        'source_type': v['source_type'], 'source_url': v['source_url'], 'report_url': url})
    out.sort(key=lambda r: (r['date'], r['vote_id'], r['member_id'], r['donor_id']), reverse=True)
    return out


def agenda_parties():
    """One row per company, organization or government named on a board's agenda, with gifts from it (or its owners)
    to the members of that government."""
    from place import PLACE_ID
    G = _graph()
    serving = _serving(G)
    out = []
    for it in agenda_items():
        if not it.get('date') or str(it['date'])[:4] < '2016':
            continue
        for p in it.get('parties') or []:
            eid = resolve_party(G, p)
            gifts = _gifts_to(G, eid, serving.get(it.get('gov'), set())) if eid and not eid.startswith('gov:') else []
            out.append({'place_id': PLACE_ID, 'gov_id': it.get('gov'), 'board': it.get('body'), 'meeting_date': it['date'], 'meeting': it.get('meeting'),
                        'item_number': it.get('number'), 'title': it.get('title'), 'kind': it.get('kind'), 'rezoning': it.get('kind') == 'rezoning_land_use',
                        'amount': _money(it.get('amount')), 'party': p, 'entity_id': eid, 'entity_name': _name(G, eid), 'entity_kind': eid.split(':')[0] if eid else None,
                        'entity_url': _url(eid) if eid else None,
                        'gave_to_members': round(sum(g[3] or 0 for g in gifts), 2) or None,
                        'gave_to': '; '.join(dict.fromkeys(G.ents[g[2]]['name'] for g in gifts)) or None, 'source_url': it.get('url')})
    out.sort(key=lambda r: (r['meeting_date'], r['gov_id'] or '', r['item_number'] or ''), reverse=True)
    return out


def development_matches(G, business=None):
    """Development projects whose name is exactly the name of one active Bay County business filing (Sunbiz)."""
    if 'dev' in _C:
        return _C['dev']
    from entity_graph import _ds
    B, ents, roles, by = _registry()
    out = []
    for r in _ds('development-projects'):
        if not B or not r.get('name') or len(norm(r['name']).split()) < 2:
            continue
        hit = by.get(B.biz_key(r['name'])) or by.get(B.loose_key(r['name'])) or []
        hit = [e for e in hit if e.get('status') == 'A'] or hit
        if len(hit) != 1:
            continue
        e = hit[0]
        cid = business(e['doc_number'], e['name']) if business else None
        if not cid:
            continue
        out.append({**{k: r.get(k) for k in ('project_id', 'gov_id', 'status', 'applied_date', 'approved_date', 'source_url', 'source_page', 'description', 'location', 'size')},
                    'project': r['name'], 'company': ids.biz_case(e['name']), 'company_id': cid, 'sunbiz_doc_number': e['doc_number']})
    _C['dev'] = out
    return out


def development_companies():
    """One row per development project matched to the registered business with its exact name, with that business's
    payments and campaign gifts."""
    from place import PLACE_ID
    G = _graph()
    paid, serving = _paid(G), _serving(G)
    out = []
    for r in _C.get('dev') or []:
        cid = G.alias.get(r['company_id'], (r['company_id'],))[0]
        gifts = _gifts_to(G, cid, serving.get(r['gov_id'], set()))
        out.append({'place_id': PLACE_ID, 'project_id': r['project_id'], 'project': r['project'], 'gov_id': r['gov_id'], 'description': r.get('description'),
                    'status': r.get('status'), 'applied_date': r.get('applied_date'), 'approved_date': r.get('approved_date'),
                    'company': _name(G, cid) or r['company'], 'company_id': cid, 'company_url': _url(cid), 'sunbiz_doc_number': r['sunbiz_doc_number'],
                    'match': 'same name as one active Sunbiz filing',
                    'paid_by_this_government': round(paid.get(cid, {}).get(r['gov_id'], 0), 2) or None,
                    'gave_to_members': round(sum(g[3] or 0 for g in gifts), 2) or None,
                    'gave_to': '; '.join(dict.fromkeys(G.ents[g[2]]['name'] for g in gifts)) or None,
                    'source_url': r.get('source_page') or r.get('source_url')})
    return out


def bid_trail():
    """Each bid or proposal request in the public notices, followed by number to the votes and contract records that
    carry the same bid number at the same government."""
    from place import PLACE_ID
    from entity_graph import _ds
    import records
    from build_contract_votes import nums
    G = _graph()
    recs = [r for r in records.all_records() if r['src'] in ('contract', 'change_order', 'emergency')]
    votes = all_votes()
    out = []
    for n in _ds('public-notices'):
        if n.get('kind') != 'bid' or n.get('same_as'):
            continue
        refs = nums(n.get('reference') or '') or nums(n.get('title') or '')
        if not refs:
            continue
        pub = str(n.get('published') or '')[:10]
        vh = [v for v in votes if v['gov_id'] == n.get('gov_id') and v['date'] >= pub and refs & nums(v['_raw'])]
        rh = [r for r in recs if r['gov_id'] == n.get('gov_id') and refs & nums(r.get('what') or '')]
        base = {'place_id': PLACE_ID, 'notice_id': n['notice_id'], 'reference': n.get('reference'), 'gov_id': n.get('gov_id'), 'agency': n.get('agency'),
                'published': pub, 'due_date': n.get('event_date'), 'notice_title': n.get('title'), 'notice_url': n.get('pdf_url') or n.get('source_url')}
        if not vh and not rh:
            out.append({**base, 'stage': 'notice', 'date': pub, 'what': 'Bid notice published', 'vendor': None, 'vendor_id': None, 'amount': None,
                        'outcome': None, 'source_url': base['notice_url']})
            continue
        out.append({**base, 'stage': 'notice', 'date': pub, 'what': 'Bid notice published', 'vendor': None, 'vendor_id': None, 'amount': None, 'outcome': None,
                    'source_url': base['notice_url']})
        for v in vh:
            named = [e for e in find_names(G, v['_t']) if not e.startswith('gov:')]
            out.append({**base, 'stage': 'vote', 'date': v['date'], 'what': v['headline'], 'vendor': '; '.join(_name(G, e) for e in named) or None,
                        'vendor_id': '; '.join(named) or None, 'amount': v['amount'], 'outcome': v['outcome'], 'source_url': v['source_url']})
        for r in rh:
            vids = ids.vendor_ids(r['name'])
            out.append({**base, 'stage': {'contract': 'award', 'change_order': 'change order', 'emergency': 'emergency purchase'}[r['src']], 'date': str(r.get('date') or '')[:10],
                        'what': r.get('what'), 'vendor': r['name'], 'vendor_id': '; '.join('vendor:' + x for x in vids) or None, 'amount': _money(r.get('amount')),
                        'outcome': None, 'source_url': r.get('url')})
    out.sort(key=lambda r: (r['published'], r['notice_id'], r['date'] or ''), reverse=True)
    return out


def _doc_of(G):
    """profile id -> Sunbiz document number for companies and businesses: the business's own filing, the one Bay County
    filing with a company's exact name, else the state registry's donor matcher (exact or near-exact name)."""
    if 'docs' in _C:
        return _C['docs']
    from entity_graph import _vendor_single_docs
    doc = {}
    for vid, d in _vendor_single_docs().items():
        doc['vendor:' + vid] = d.upper()
    for aid, (target, _) in G.alias.items():
        if aid.startswith('business:') and re.match(r'^[a-z0-9]+$', aid[9:]) and re.search(r'\d', aid[9:]):
            doc.setdefault(target, aid[9:].upper())
    for eid in G.ents:
        if eid.startswith('business:') and re.match(r'^[a-z0-9]+$', eid[9:]) and re.search(r'\d', eid[9:]):
            doc.setdefault(eid, eid[9:].upper())
    B, ents, roles, by = _registry()
    rest = [eid for eid in G.ents if eid.startswith('vendor:') and eid not in doc]
    if B and rest:
        for eid, m in zip(rest, B.match_donors(ents, [{'name': G.ents[e]['name']} for e in rest])):
            if m.get('doc_number') and m.get('match_method') in ('exact', 'vendor_alias', 'plural_variant'):
                doc[eid] = m['doc_number'].upper()
    _C['docs'] = doc
    return doc


def shared_owner_vendors():
    """Companies paid by the same government that share an officer or manager (Sunbiz), one row per company and shared
    person. Registered agents are left out: agent firms and lawyers act for many unrelated companies."""
    from place import PLACE_ID
    G = _graph()
    B, ents, roles, by = _registry()
    paid = _paid(G)
    doc = _doc_of(G)
    by_doc = {d: eid for eid, d in doc.items() if eid in paid}
    people = collections.defaultdict(set)  # person key -> {doc}
    names, streets = {}, {}
    for r in roles:
        if r['doc_number'] not in by_doc or not r.get('is_person') or r.get('role') == 'agent':
            continue
        nm = re.sub(r'(?i)\s+d?esq\b\.?', '', ids.sunbiz_person(r.get('raw_name') or ''))
        if not nm or len(nm.split()) < 2:
            continue
        k = ids.person_key(nm)
        if not k:
            continue
        people[k].add(r['doc_number'])
        names[k] = nm
        streets.setdefault((k, r['doc_number']), (r.get('street') or '').upper().strip())
    out = []
    for k, docs in people.items():
        if len(docs) < 2:
            continue
        cos = [by_doc[d] for d in sorted(docs)]
        for gid in sorted({g for c in cos for g in paid[c] if ids.gov(g)}):
            here = [c for c in cos if gid in paid[c]]
            if len(set(here)) < 2:
                continue
            gk = f"{gid}:" + re.sub(r'[^a-z0-9]+', '-', names[k].lower()).strip('-')
            for c in dict.fromkeys(here):
                out.append({'place_id': PLACE_ID, 'group_id': gk, 'gov_id': gid, 'officer': names[k], 'company': _name(G, c), 'company_id': c, 'company_url': _url(c),
                            'sunbiz_doc_number': doc.get(c), 'paid_by_this_government': round(paid[c][gid], 2), 'companies_in_group': len(set(here)),
                            'match': 'same name and address' if len({streets.get((k, doc.get(x))) for x in here}) == 1 else 'same name',
                            'source_url': ids.sunbiz_url(G.ents[c]['name'], doc.get(c))})
    out.sort(key=lambda r: (r['gov_id'], r['group_id'], -(r['paid_by_this_government'] or 0)))
    return out


def chamber_overlaps():
    """Chamber of commerce board members and staff whose company is paid by a local government or gave to a local
    campaign, or who gave to one themselves as a business owner. Rows with no overlap are left out."""
    from place import PLACE_ID
    from entity_graph import _ds
    G = _graph()
    paid = _paid(G)
    gifts, owners = _gifts(G)
    owner_by_name = collections.defaultdict(set)
    for c, os_ in owners.items():
        for o in os_:
            owner_by_name[ids.person_key(G.ents[o]['name'])].add((o, c))
    out = []
    for r in _ds('chamber-leaders'):
        pid, oid = r.get('person_entity_id'), r.get('organization_entity_id')
        oid = G.alias.get(oid, (oid,))[0] if oid else None
        if oid and oid not in G.ents:
            oid = None
        org_paid = round(sum(v for g, v in paid.get(oid, {}).items() if ids.gov(g)), 2) if oid else 0  # local governments only, not federal contracts
        org_gave = round(sum(a or 0 for _, a, _, _ in gifts.get(oid, [])), 2) if oid else 0
        own = []
        if pid and pid.startswith('person:'):
            own = [g for g in gifts.get(pid, [])]
        for o, c in owner_by_name.get(ids.person_key(r.get('person_name') or ''), ()):
            if c == oid or (not oid and _phrase(G.ents[c]['name']) and _phrase(G.ents[c]['name']) == _phrase(r.get('organization') or '')):
                own += gifts.get(o, [])  # the same person only when they run the company the chamber lists them with
        person_gave = round(sum(a or 0 for _, a, _, _ in own), 2)
        official = bool(pid and pid.startswith('person:'))
        if not (org_paid or org_gave or person_gave or official):
            continue
        out.append({'place_id': PLACE_ID, 'chamber': r['chamber'], 'chamber_entity_id': r.get('chamber_entity_id'), 'person': r['person_name'], 'person_id': pid,
                    'person_url': _url(pid) if pid and pid in G.ents else None, 'title': r.get('title'), 'role_group': r.get('role_group'), 'year': r.get('year'),
                    'current': r.get('current'), 'organization': r.get('organization'), 'organization_id': oid, 'organization_url': _url(oid) if oid else None,
                    'is_official': official, 'organization_paid_by_governments': org_paid or None, 'organization_gave_to_campaigns': org_gave or None,
                    'person_gave_to_campaigns': person_gave or None,
                    'gave_to': '; '.join(dict.fromkeys(G.ents[g[0]]['name'] for g in (own + (gifts.get(oid, []) if oid else [])) if g[0] in G.ents)) or None,
                    'source_url': r.get('source_url')})
    return out


def emergency_purchase_donors():
    """Every emergency purchase (bought without the usual bidding), with gifts from the company or its owners to the
    officials of the government that bought."""
    from place import PLACE_ID
    G = _graph()
    serving = _serving(G)
    ct = json.load(open(os.path.join(DATA, 'contracts', 'contracts.json')))
    out = []
    for c in ct.get('emergency_purchases') or []:
        gid = ids.gov_id(c.get('government'))
        vid = next((v for v in ids.vendor_ids(c.get('vendor') or '') if 'vendor:' + v in G.ents), None)
        eid = 'vendor:' + vid if vid else None
        gifts = _gifts_to(G, eid, serving.get(gid, set())) if eid else []
        out.append({'place_id': PLACE_ID, 'gov_id': gid, 'government': c.get('government'), 'vendor': c.get('vendor'), 'vendor_id': eid, 'vendor_url': _url(eid) if eid else None,
                    'amount': _money(c.get('amount')), 'date': c.get('date'), 'purpose': c.get('purpose'), 'basis': c.get('basis'),
                    'gave_to_officials_here': round(sum(g[3] or 0 for g in gifts), 2) or None,
                    'gave_to': '; '.join(dict.fromkeys(G.ents[g[2]]['name'] for g in gifts)) or None, 'source_url': c.get('source_url')})
    out.sort(key=lambda r: str(r['date'] or ''), reverse=True)
    return out


def campaign_results():
    """Each local candidate since 2016: money raised and spent next to the votes they got, their rank in the race by
    money and by votes, and the cost per vote. Joined on election date and candidate name."""
    from place import PLACE_ID
    from entity_graph import _ds
    res = collections.defaultdict(list)
    for r in _ds('election-results'):
        if r.get('measure') in (True, 'True', 'true'):
            continue
        res[(str(r.get('election_date'))[:10], ids.person_key(r.get('choice') or ''))].append(r)
    camp = [c for c in _ds('campaign-history') if c.get('election_date')]
    race_money = collections.defaultdict(list)
    for c in camp:
        race_money[(c['election_date'], c['office'])].append(_money(c.get('total_raised')) or 0)
    out = []
    for c in camp:
        hits = res.get((str(c['election_date'])[:10], ids.person_key(c.get('candidate') or ''))) or []
        if len(hits) != 1:
            continue
        r = hits[0]
        raised, votes = _money(c.get('total_raised')) or 0, int(float(r.get('votes') or 0))
        money = sorted(race_money[(c['election_date'], c['office'])], reverse=True)
        out.append({'place_id': PLACE_ID, 'election_date': c['election_date'], 'election': c.get('election'), 'gov_id': c.get('gov_id'), 'office': c.get('office'),
                    'contest': r.get('contest'), 'candidate': c.get('candidate'), 'person_id': c.get('person_id'), 'outcome': c.get('outcome'),
                    'total_raised': raised, 'total_spent': _money(c.get('total_spent')), 'from_businesses': _money(c.get('from_businesses')),
                    'from_individuals': _money(c.get('from_individuals_total')), 'own_money': _money(c.get('own_money')), 'votes': votes, 'vote_pct': _money(r.get('pct')),
                    'vote_rank': int(float(r['rank'])) if r.get('rank') not in (None, '') else None, 'money_rank': money.index(raised) + 1 if raised in money else None,
                    'candidates_with_reports': len(money), 'cost_per_vote': round((_money(c.get('total_spent')) or 0) / votes, 2) if votes else None,
                    'report_url': c.get('report_url'), 'source_url': r.get('source_url')})
    out.sort(key=lambda r: (r['election_date'], r['office'], r['vote_rank'] or 99), reverse=True)
    return out


DATASETS = [
    ('vote-mentions', 'Votes that name a company or organization', "One row per recorded vote and each company, nonprofit or registered business its motion names, matched by name from the minutes (hand-researched votes and every vote read from minutes since 2016): the vote, the organization and its profile (entity_id), the words that matched, the roll call (roll_call, 'Name: vote' pairs) and the members' profile ids (member_ids). A match means the minutes name the organization in that motion; consent agendas name many items in one vote.", vote_mentions),
    ('donor-votes', "Votes on motions naming a member's donor", "One row per member vote on a motion that names a company which gave to that member's campaign (donor_kind company) or whose owner gave personally (donor_kind business owner; owners are named only when their name and address match a Sunbiz officer, manager or registered agent). With the gift total, the first and last gift dates and whether the gifts came before or after the vote. A gift near a vote does not show why anyone voted the way they did. Individual donors are never named.", donor_votes),
    ('agenda-parties', 'Companies and organizations on agendas', "One row per company, organization or government named on a board's agenda (agenda items read from the published agenda packets), linked to its profile where the name matches, with any campaign gifts from it (or from the owners who run it) to people who serve that government (gave_to_members, gave_to). rezoning is true for rezoning and land-use items.", agenda_parties),
    ('development-companies', 'Development projects and the businesses behind them', "Development projects on the county and city planning maps whose name is exactly the name of one active Bay County business filing (Sunbiz), with that business's payments from the same government and campaign gifts from it or its owners to that government's officials. The maps don't list owners or developers, so only projects named after their business are matched.", development_companies),
    ('bid-trail', 'Bids from notice to award', "Each bid or proposal request in the public notices, followed by its bid number to the recorded votes and contract records (awards, change orders, emergency purchases) at the same government that carry the same number: one row per step (stage notice, vote, award, change order), oldest notice last.", bid_trail),
    ('shared-owner-vendors', 'Companies paid by one government that share an officer', "Companies paid by the same local government that list the same person (same name and Sunbiz address) as an officer or manager, one row per company, government and shared person. Registered agents are left out. Sharing an officer is common among related companies and is not a finding of wrongdoing.", shared_owner_vendors),
    ('chamber-overlaps', 'Chamber board members who are donors, vendors or officials', "Chamber of commerce board members and staff (chamber-leaders) whose company is paid by a local government or gave to a local campaign, who gave to a campaign themselves as a business owner, or who are elected officials. Rows with none of these are left out.", chamber_overlaps),
    ('emergency-purchase-donors', 'Emergency purchases and campaign gifts', "Every emergency purchase (bought without the usual bidding), with campaign gifts from the company, or from the owners who run it, to people who serve the government that bought.", emergency_purchase_donors),
    ('campaign-results', 'Money raised and votes won', "Each local candidate since 2016 with a campaign report and an official result: money raised and spent, where it came from (individuals summed, never named), votes, vote share, rank in the race by votes and by money, and cost per vote (spent / votes). Joined on election date and candidate name.", campaign_results),
]

COLUMNS = {}  # column types for datasets that can be empty (none yet)
