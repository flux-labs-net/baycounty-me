"""Awards with nothing after them: a contract award recorded in the minutes, then no later record of the job.

When a board awards a contract, a trail usually follows: a contract record, change orders, later votes on the same
company or bid (amendments, renewals, task orders, close-out), the company on later agendas, payments in a check
register, or a project history. This check takes every passed contract award read from the minutes (since 2016) and
looks for any of those, at the same government, dated after the award.

One row per award vote and company named (or one row with no company when the minutes name none). status:

  followed_up   at least one later record names the same company (or carries the same bid number)
  too_soon      no later record yet, but the award is less than WAIT_DAYS old
  no_follow_up  WAIT_DAYS or more since the award, and no later record of any kind: the flag
  as_needed     no later record, but the award is a standing or as-needed agreement (on-call services, disaster debris,
                a ranked list of firms): it is used only when work is ordered, so nothing following it is normal
  cant_check    no later record, and the minutes name no company, so there is nothing to follow

The company is the site's profile when the minutes name one we know (company_from 'profile', entity_id), else the name
as the motion writes it (company_from 'minutes text'), followed through later votes and agenda items by those words.

A flag is a question, not a finding. It means the records the site holds show nothing after the award. The work may
have happened with the paperwork in files we haven't read (most governments don't publish a check register), the
award may have been dropped or rebid, or the company may have changed its name. Each flag is something to ask the
government for: the signed contract, purchase orders and payments (see data/civic/scripts/stale_requests.py).

Consent agendas are left out (one vote, many items), and so are votes that approve no spending (contract_coverage.NOT_AN_APPROVAL).
Published as dataset `award-follow-up`.
"""
import datetime as dt
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
for _p in (os.path.join(DATA, 'campaign'), os.path.join(DATA, 'entities')):
    if _p not in sys.path:
        sys.path.append(_p)

import correlations as C  # noqa: E402
from contract_coverage import NOT_AN_APPROVAL  # noqa: E402

START = '2016-01-01'
WAIT_DAYS = 180          # about six months: long enough for a contract, a first payment or a change order to show up
# follow-ups to an earlier award (counted as later records, not as awards of their own)
NOT_NEW = re.compile(r'\b(change orders?|amend\w*|renew\w*|extension|extend\w*|close-?out|final pay\w*|pay(?:ment)? (?:application|request)|ratif\w*|'
                     r'budget (?:amendment|transfer)|work order change|supplement\w*|addend\w*|payment to)\b', re.I)
# standing agreements used only when work is ordered: nothing following them is normal
AS_NEEDED = re.compile(r'\b(on[- ]call|as[- ]needed|continuing (?:professional )?(?:services|contracts?|agreements?)|standby|stand-by|pre-?position\w*|debris (?:monitoring|removal|hauling)|'
                       r'disaster|emergency (?:services|response)|contingen\w*|pre-?event|master (?:services )?agreement|annual (?:contract|supply)|term contract|'
                       r'piggyback\w* on|price agreement|qualified (?:firms|vendors|list)|pool of|shortlist\w*|rank\w*)\b', re.I)
AWARD = re.compile(r'\b(award\w*|approv\w*|contract\w*|agreement|purchase\w*|bid|proposal|task order|piggyback\w*|sole source|quote)\b', re.I)
KIND_LABEL = {'vote': 'Later vote', 'bid': 'Later vote on the same bid number', 'agenda': 'Later agenda item', 'change_order': 'Change order',
              'contract': 'Contract record', 'emergency': 'Emergency purchase', 'register': 'Check register payment', 'tdc': 'Tourist tax payment',
              'cra': 'CRA payment', 'project': 'Project history'}

_C = {}


def _d(s):
    s = str(s or '')
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r'(?:FY)?\s*(\d{4})$', s.strip())
    if m:
        # a fiscal-year record (registers, tourist tax by year): count it from the year's last day, Sept 30
        return dt.date(int(m[1]), 9, 30)
    return None


def _today():
    return dt.date.fromisoformat(os.environ.get('BC_TODAY') or dt.date.today().isoformat())


def _awards():
    """Passed, non-consent contract votes since 2016 that approve spending."""
    out = []
    for v in C.all_votes():
        if v['date'] < START or not v['gov_id'] or v['consent']:
            continue
        if (v['category'] or '').lower() != 'contract' or (v['outcome'] or '').lower() != 'passed':
            continue
        if NOT_AN_APPROVAL.search(v['_raw']) or NOT_NEW.search(v['_raw']) or not AWARD.search(v['_raw']):
            continue
        out.append(v)
    return out


def _evidence(G):
    """(gov id, entity id) -> [(date, kind, what, url)] and (gov id, bid number) -> [(date, kind, what, url)]."""
    import ids
    import records
    from build_contract_votes import nums
    by_ent, by_num = {}, {}

    def put(gov, eid, d, kind, what, url):
        if gov and eid and d:
            by_ent.setdefault((gov, eid), []).append((d, kind, what, url))
    for v in C.all_votes():
        d = _d(v['date'])
        for eid in C.find_names(G, v['_t']):
            if not eid.startswith('gov:'):
                put(v['gov_id'], eid, d, 'vote', v['headline'], v['source_url'])
        for n in nums(v['_raw']):
            by_num.setdefault((v['gov_id'], n), []).append((d, 'bid', v['headline'], v['source_url']))
    for it in C.agenda_items():
        d = _d(it.get('date'))
        text = ' '.join(str(it.get(k) or '') for k in ('title', 'summary'))
        ents = set(C.find_names(G, text))
        for p in it.get('parties') or []:
            e = C.resolve_party(G, p)
            if e:
                ents.add(e)
        for eid in ents:
            if not eid.startswith('gov:'):
                put(it.get('gov'), eid, d, 'agenda', it.get('title'), it.get('url'))
    for r in records.all_records():
        vids = ['vendor:' + x for x in ids.vendor_ids(r['name'])]
        if r['src'] == 'tdc':
            dates = [_d(fy) for fy in (r['extra'].get('by_fy') or {})]
        else:
            dates = [_d(r.get('date'))]
        for eid in vids:
            for d in dates:
                put(r['gov_id'], eid, d, r['src'], r.get('what'), r.get('url'))
    seed = json.load(open(os.path.join(DATA, 'projects', 'seed.json')))
    for p in seed['projects']:
        gov = ids.gov_id(p.get('gov')) or p.get('gov')
        for e in p.get('events') or []:
            for eid in ['vendor:' + x for x in ids.vendor_ids(e.get('payee') or '')] or list(C.find_names(G, e.get('t') or '')):
                put(gov, eid, _d(e.get('d')), 'project', f"{p['name']}: {e.get('t')}", e.get('u'))
    return by_ent, by_num


# a company named in the motion text that isn't on the site yet: "... with HST Utility Contractors for ...", "... to Design West Group"
NAMED = re.compile(r"\b(?:with|to|from)\s+((?:the\s+)?[A-Z][\w&'.-]*(?:[ ,]+(?:of|and|&|[A-Z][\w&'.-]*)){0,5})")
NOT_A_COMPANY = re.compile(r'\b(City|County|Commission|Council|Board|Florida|FDOT|Department|State|Mayor|Manager|Resolution|Ordinance|Item|Staff|'
                           r'Chapter|Phase|Bid|RFP|RFQ|ITB|Fund|Funding|Grant|Act|Purchase|Publish|Increase|Proceed|Approve|Repairs?|Street|Avenue|Road|'
                           r'Park|Parish|Complex|School|Elementary|Middle|High|Center|Building|Units?|Materials|Parts|Rates|Attorney|Project)\b')
# a name written in the minutes counts as a company only with a word like these in it; two plain words ("Jane Smith")
# may be a private person, who is never named
BUSINESS = re.compile(r'\b(Inc|LLC|LLP|PLLC|P\.?A|Corp|Corporation|Company|Co|Group|Construction|Constructors|Contracting|Contractors?|'
                      r'Engineering|Engineers|Associates|Solutions|Consultants|Consulting|Services|Systems|Technolog(?:y|ies)|Industries|Partners|'
                      r'Enterprises|International|Integrations?|Pump|Lighting|Electric|Electronics|Paving|Excavating|Dredging|Landscap\w*|Motors?|'
                      r'Trucks|Leasing|Supply|Equipment|Architects|Advisors|Management|Parking|Skateparks|Elevators?|Controls|Stucco|Pros|Tractor|'
                      r'Studios|Utility|Separation|Marine|Sports Lighting)\b\.?')


def text_names(text):
    """Company names written in a motion that the site has no profile for: [(name as written, words to match)]."""
    out = []
    for m in NAMED.findall(text or ''):
        m = re.sub(r'^the\s+', '', m, flags=re.I)
        while True:  # "L and R Construction and" -> "L and R Construction"
            t = re.sub(r'(?:[,.&\s]+|\s+(?:and|of))$', '', m)
            if t == m:
                break
            m = t
        ph = C._phrase(m)
        if ph and BUSINESS.search(m) and not NOT_A_COMPANY.search(m) and not re.search(r'\d', m) and ph not in [x[1] for x in out]:
            out.append((m, ph))
    return out


def _texts():
    """gov id -> [(date, kind, normalized text, what, url)] for every vote and agenda item, to follow names with no profile."""
    by = {}
    for v in C.all_votes():
        by.setdefault(v['gov_id'], []).append((_d(v['date']), 'vote', v['_t'], v['headline'], v['source_url']))
    for it in C.agenda_items():
        t = ' ' + C.norm(' '.join(str(it.get(k) or '') for k in ('title', 'summary'))) + ' '
        by.setdefault(it.get('gov'), []).append((_d(it.get('date')), 'agenda', t, it.get('title'), it.get('url')))
    return by


def rows():
    if 'rows' in _C:
        return _C['rows']
    from build_contract_votes import nums
    G = C._graph()
    by_ent, by_num = _evidence(G)
    texts = _texts()
    today = _today()
    out, seen = [], set()
    for v in sorted(_awards(), key=lambda v: (v['source_type'] != 'minutes', v['date'], v['vote_id'])):
        vd = _d(v['date'])
        found = {e: p for e, p in C.find_names(G, v['_t']).items() if not e.startswith('gov:') and e in G.ents}
        # one firm found twice ("Kenny Strange Electric" and "Kenny Strange Electric and Service Company"): keep the longer name
        ents = [e for e, p in found.items() if not any(q != p and (' ' + q + ' ').startswith(' ' + p + ' ') for q in found.values())]
        ents = [e for e in ents if (v['gov_id'], v['date'], e) not in seen]
        # a hand-researched vote that repeats a minutes vote already counted
        if v['source_type'] != 'minutes' and not ents and any(k[:2] == (v['gov_id'], v['date']) for k in seen):
            continue
        seen |= {(v['gov_id'], v['date'], e) for e in ents}
        named = [] if ents else text_names(v['headline']) or text_names(v['agenda_item'])
        bids = sorted(nums(v['_raw']))
        age = (today - vd).days
        base = {'vote_id': v['vote_id'], 'gov_id': v['gov_id'], 'board': v['board'], 'award_date': v['date'], 'year': int(v['date'][:4]),
                'headline': v['headline'], 'amount': v['amount'], 'bid_numbers': '; '.join(bids) or None,
                'flag_after': (vd + dt.timedelta(days=WAIT_DAYS)).isoformat(), 'source_url': v['source_url']}
        firms = [(e, G.ents[e]['name'], None) for e in ents] + [(None, n, ph) for n, ph in named]
        for eid, name, ph in firms or [(None, None, None)]:
            later = []
            if eid:
                later += [x for x in by_ent.get((v['gov_id'], eid), []) if x[0] > vd]
            if ph:
                later += [(d, k, what, url) for d, k, t, what, url in texts.get(v['gov_id'], []) if d and d > vd and ' ' + ph + ' ' in t]
            for n in bids:
                later += [x for x in by_num.get((v['gov_id'], n), []) if x[0] > vd]
            later = sorted(set(later), key=lambda x: (x[0], x[1], x[2] or ''))
            if later:
                st = 'followed_up'
            elif not name:
                st = 'cant_check'
            elif AS_NEEDED.search(v['_raw']):
                st = 'as_needed'
            elif age < WAIT_DAYS:
                st = 'too_soon'
            else:
                st = 'no_follow_up'
            first = later[0] if later else None
            kinds = sorted({x[1] for x in later})
            out.append({**base, 'entity_id': eid, 'company': name, 'company_from': 'profile' if eid else ('minutes text' if name else None), 'status': st,
                        'later_records': len(later), 'later_kinds': '; '.join(KIND_LABEL[k] for k in kinds) or None,
                        'first_later_date': first[0].isoformat() if first else None, 'first_later_what': first[2] if first else None,
                        'first_later_url': first[3] if first else None,
                        'last_later_date': later[-1][0].isoformat() if later else None})
    out.sort(key=lambda r: (r['gov_id'], r['award_date'], r['vote_id'], r['company'] or ''), reverse=True)
    _C['rows'] = out
    return out


def flagged(gov_id=None):
    """The flags: awards with no later record, newest first."""
    return [r for r in rows() if r['status'] == 'no_follow_up' and (gov_id is None or r['gov_id'] == gov_id)]


DATASETS = [
    ('award-follow-up', 'Contract awards and what came after',
     "Every passed contract award read from the minutes since 2016 (consent agendas, votes that approve no spending, and change orders, amendments "
     "and renewals left out), one row per award and company named, checked for any later record at the same government that names the same "
     "company or carries the same bid number: later votes and agenda items, contract records and change orders, check register, tourist tax and CRA "
     "payments, and project histories. status: followed_up (later_records found; later_kinds says which, first_later_* is the first one), "
     "no_follow_up (no later record by flag_after, six months after the award), too_soon (not yet six months), as_needed (no later record, but the "
     "award is a standing or on-call agreement used only when work is ordered), cant_check (the minutes name no company). company_from says whether "
     "the company matched a profile (entity_id) or is the name as the motion writes it. A no_follow_up row is a question for the government, not a "
     "finding: the work may be recorded in files the site doesn't hold. Rules: site/award_followup.py.", rows),
]


if __name__ == '__main__':
    import collections
    rs = rows()
    print(len(rs), collections.Counter(r['status'] for r in rs))
    print(collections.Counter((r['gov_id'], r['status']) for r in rs if r['status'] == 'no_follow_up'))
    for r in [r for r in rs if r['status'] == 'no_follow_up'][:25]:
        print(r['award_date'], r['gov_id'], r['company'], r['amount'], '|', r['headline'][:110])
