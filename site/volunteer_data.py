"""Volunteer and nonprofit needs board (/volunteer): the volunteer-needs and volunteer-orgs datasets.

volunteer-needs: open volunteer needs in the county from public volunteer boards (data/volunteer/fetch_needs.py ->
data/volunteer/<county>/needs.json), each joined to the local nonprofit that posted it where the name matches.
volunteer-orgs: local nonprofits that use volunteers, from the volunteer count on their latest Form 990
(data/volunteer/fetch_990_volunteers.py) and from the needs they have open, with what each does and how to reach it.

One plain cause per row, so both lists filter the same way on the site and in the apps.
"""
import csv, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))

# plain causes, in the order the filters show them; keyword rules are tried first, then the board's own interest, then
# the IRS category of the matched nonprofit
CAUSES = ['Kids and mentoring', 'Schools and reading', 'Food and basic needs', 'Health and hospice', 'Seniors',
          'Disaster and emergency', 'Housing and neighborhoods', 'Animals', 'Arts and culture', 'Environment',
          'Veterans and service clubs', 'Sports and recreation', 'Events and fundraisers', 'Faith', 'Other']
KEYWORDS = [
    ('Disaster and emergency', r'\b(red cross|shelter service|disaster|hurricane|emergency)'),
    ('Health and hospice', r'\b(hospice|memory bear|hospital|clinic|medical|health)'),
    ('Kids and mentoring', r'\b(mentor|big brothers|boys & girls|boys and girls|youth|host famil|exchange student|child)'),
    ('Schools and reading', r'\b(reading|tutor|literacy|kindergarten|school|books?)\b'),
    ('Food and basic needs', r'\b(food|pantry|meal|lasagna|hunger|farmers market|tax assistance|vita)\b'),
    ('Seniors', r'\b(senior|elder|aging)'),
    ('Animals', r'\b(animal|humane|pet|dog|cat|turtle|wildlife|spay)s?\b'),
    ('Events and fundraisers', r'\b(event set-up|gala|cocktails|fundraiser|5k)'),
]
BOARD_INTEREST = {'Education': 'Schools and reading', 'Food Prep': 'Food and basic needs', 'Finance': 'Food and basic needs',
                  'Physical Labor': 'Events and fundraisers', 'Health': 'Health and hospice', 'Animals': 'Animals',
                  'Seniors': 'Seniors', 'Disaster': 'Disaster and emergency', 'Environment': 'Environment',
                  'Children & Youth': 'Kids and mentoring', 'Arts & Culture': 'Arts and culture', 'Housing': 'Housing and neighborhoods'}
NP_CATEGORY = {'Youth development': 'Kids and mentoring', 'Education': 'Schools and reading', 'Human services': 'Food and basic needs',
               'Food and agriculture': 'Food and basic needs', 'Health care': 'Health and hospice', 'Mental health': 'Health and hospice',
               'Disease and disorders': 'Health and hospice', 'Public safety and disaster': 'Disaster and emergency',
               'Housing': 'Housing and neighborhoods', 'Community improvement': 'Housing and neighborhoods', 'Animals': 'Animals',
               'Arts and culture': 'Arts and culture', 'Environment': 'Environment', 'Recreation and sports': 'Sports and recreation',
               'Religion': 'Faith', 'Church or religious group': 'Faith', 'Club, lodge or veterans group': 'Veterans and service clubs'}
# kinds of organization that don't go on a volunteer board even when their 990 counts volunteers
SKIP_KINDS = {'Homeowner or condo association', 'Business league or chamber', 'Private foundation'}


def _dir():
    from place import PLACE_ID
    return os.path.join(HERE, '..', 'data', 'volunteer', PLACE_ID.split('-', 1)[-1])


def _norm(s):
    s = re.sub(r"[.,'’&°\-]", ' ', (s or '').lower())
    return ' '.join(w.rstrip('s') for w in s.split()
                    if w not in ('inc', 'llc', 'co', 'corp', 'corporation', 'company', 'the', 'of', 'and', 'incorporated', 'fl', 'florida'))


def cause_of(text, interest=None, np_category=None):
    t = (text or '').lower()
    for c, rx in KEYWORDS:
        if re.search(rx, t):
            return c
    return BOARD_INTEREST.get(interest or '') or NP_CATEGORY.get(np_category or '') or 'Other'


def _np_cause(n, overrides):
    if n['nonprofit_id'] in overrides:
        return overrides[n['nonprofit_id']]
    name = (n.get('name') or '').lower()
    if re.search(r'\b(veteran|legion|vfw|amvets|lodge|eastern star|rotary|kiwanis|lions club|elks|moose|navy league|junior league|civic club)', name):
        return 'Veterans and service clubs'
    if re.search(r'\b(arts?|music|symphony|theat|museum)\b', name):
        return 'Arts and culture'
    if re.search(r'\b(gymnastic|soccer|aquatic|baseball|softball|football|athletic)', name):
        return 'Sports and recreation'
    if re.search(r'\b(rescue mission|homeless|hunger)', name):
        return 'Food and basic needs'
    return NP_CATEGORY.get(n.get('category') or '') or NP_CATEGORY.get(n.get('kind') or '') or cause_of(name + ' ' + (n.get('mission') or '').lower())


_CACHE = {}


def _rows():
    if 'rows' in _CACHE:
        return _CACHE['rows']
    import ids
    from entity_graph import page_url
    from opendata import datasets
    from place import PLACE_ID
    d = _dir()
    p = os.path.join(d, 'needs.json')
    if not os.path.exists(p):
        _CACHE['rows'] = ([], [])
        return _CACHE['rows']
    N = json.load(open(p))
    hand = json.load(open(os.path.join(d, 'organizations.json'))) if os.path.exists(os.path.join(d, 'organizations.json')) else {}
    aliases, overrides = hand.get('aliases', {}), hand.get('causes', {})
    vol = {}
    vp = os.path.join(d, 'volunteers_990.csv')
    if os.path.exists(vp):
        vol = {r['ein']: r for r in csv.DictReader(open(vp)) if r['volunteers'] not in ('', '0')}
    fn = {x[0]: x[3] for x in datasets()}
    nps = {n['nonprofit_id']: n for n in fn['nonprofits']()}
    by_name = {}
    for n in nps.values():
        by_name.setdefault(_norm(n['name']), []).append(n['nonprofit_id'])

    def match(org):
        if org in aliases:
            return aliases[org]
        hit = by_name.get(_norm(org)) or []
        return hit[0] if len(hit) == 1 else None

    needs = []
    for r in N['needs']:
        nid = match(r['organization'])
        n = nps.get(nid) or {}
        eid = 'nonprofit:' + nid if nid else None
        needs.append({
            'place_id': PLACE_ID, 'need_id': r['need_id'], 'title': r['title'], 'organization': r['organization'],
            'nonprofit_id': nid, 'organization_entity_id': eid, 'organization_url': page_url(eid) if eid else None,
            'cause': cause_of(' '.join(x or '' for x in (r['title'], r['organization'], r.get('description'))), r.get('cause'), n.get('category') or n.get('kind')),
            'board_interest': r.get('cause'), 'schedule': r.get('schedule'), 'when_text': r.get('when'),
            'starts': r.get('starts'), 'ends': r.get('ends'), 'posted': r.get('posted'), 'closes': r.get('closes'),
            'first_seen': r.get('first_seen'), 'description': r.get('description'), 'details': r.get('details'),
            'city': r.get('city'), 'zip': r.get('zip'), 'remote': bool(r.get('remote')) or 'virtual' in (r.get('details') or '').lower(),
            'board': r['board'], 'url': r['url'], 'as_of': N['as_of'], 'source_url': r['source_url']})

    open_by = {}
    for x in needs:
        if x['nonprofit_id']:
            open_by.setdefault(x['nonprofit_id'], []).append(x)
    orgs = []
    for nid, n in nps.items():
        v = vol.get(n.get('ein') or '')
        has = open_by.get(nid, [])
        if not v and not has:
            continue
        if (n.get('kind') in SKIP_KINDS or 'credit union' in (n.get('name') or '').lower()) and not has:
            continue
        eid = 'nonprofit:' + nid
        web = (n.get('website') or '').strip()
        if web and web.upper() not in ('N/A', 'NA', 'NONE', '0') and '.' in web:
            web = web.lower() if web.isupper() else web
            web = web if web.startswith('http') else 'https://' + web.lstrip('/')
        else:
            web = None
        orgs.append({
            'place_id': PLACE_ID, 'nonprofit_id': nid, 'entity_id': eid, 'page_url': page_url(eid),
            'name': ids.biz_case(re.sub(r'\s+FKA\b.*$', '', n['name'])), 'cause': _np_cause(n, overrides), 'kind': n.get('kind'), 'city': n.get('city'),
            'mission': (n.get('mission') or '').capitalize() or None, 'website': web,
            'volunteers_reported': int(v['volunteers']) if v else None, 'volunteers_year': int(v['tax_year']) if v else None,
            'employees': n.get('employees'), 'revenue': n.get('total_revenue'),
            'open_needs': len(has), 'needs_boards': '; '.join(dict.fromkeys(x['board'] for x in has)) or None,
            'latest_return_form': n.get('latest_return_form'), 'latest_return_year': n.get('latest_return_year'),
            'source_url': v['xml_url'] if v else n.get('source_url')})
    orgs.sort(key=lambda o: (-(o['open_needs'] or 0), -(o['volunteers_reported'] or 0), o['name']))
    _CACHE['rows'] = (needs, orgs)
    return _CACHE['rows']


def volunteer_needs():
    return _rows()[0]


def volunteer_orgs():
    return _rows()[1]


DATASETS = [
    ('volunteer-needs', 'Volunteer needs', "Open volunteer needs in the county, read every day from public volunteer boards (United Way of Northwest Florida's volunteer center and Idealist): what volunteers do, the organization, a plain cause, when (ongoing, one day or shifts), the city and ZIP, and the board's sign-up link. nonprofit_id and organization_entity_id link to the local nonprofit's profile where the name matches. No street addresses or contact details.", volunteer_needs),
    ('volunteer-orgs', 'Nonprofits that use volunteers', "Local nonprofits that reported volunteers on their latest IRS Form 990 (Part I line 6, the organization's own estimate, which can cover more than this county) or that have a volunteer need open now: what each does, a plain cause, website, volunteers and employees reported, revenue, and open needs. Homeowner associations, chambers and private foundations are left out unless they post a need.", volunteer_orgs),
]
