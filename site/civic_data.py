"""Rows for the elections hub (/elections/results, /elections/voting), public notices (/notices) and government job
openings (/jobs). Each list is published as a dataset (page_datasets.DATASETS), so it reaches the database and the API.

Inputs (all refreshed by the daily refresh workflow):
  data/elections/results.json   fetch_results.py   every Bay County election since 2016, contest by contest
  data/elections/voting.json    fetch_voting.py    key dates, early voting sites and Election Day polling places
  data/notices/<county>/notices.json   build_notices.py   government legal notices
  data/jobs/<county>/jobs.json         fetch_jobs.js      job openings from each government's job board
"""
import datetime as dt, functools, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
sys.path.insert(0, os.path.join(DATA, 'entities'))


def _place():
    from place import PLACE_ID
    return PLACE_ID


def _county_dir():
    return _place().split('-', 1)[-1]


def _load(*p):
    try:
        return json.load(open(os.path.join(DATA, *p)))
    except FileNotFoundError:
        return None


# --- Election results ------------------------------------------------------------------------------------------------

CITIES = [('pcb', r'Panama City Beach|^PCB\b'), ('pc', r'Panama City|^PAC\b'), ('lh', r'Lynn Haven|^LYN\b'), ('cw', r'Callaway'),
          ('mb', r'Mexico Beach'), ('sp', r'Springfield'), ('parker', r'Parker')]
CITY_PREFIX = re.compile(r'^(LYN|PCB|PAC)\s+')
LEVELS = [  # (level, gov_id, pattern); the first match wins
    ('Party', None, r'State Committee(man|woman)'),
    ('Federal', None, r'^President|United States Senator|Representative in Congress'),
    ('State', None, r'^Partisan Election of Members of District School Boards'),  # a statewide amendment
    ('Court', 'county', r'^County Judge'),
    ('Court', None, r'Retention|Justice|Court of Appeal'),
    ('Special district', 'beach_mosquito', r'Beach Mosquito Control'),
    ('Special district', 'lake_powell_cdd', r'Lake Powell (Residential Golf )?Community Development'),
    ('Special district', None, r'Mosquito Control|Community Development District'),
    ('School district', 'schools', r'School Board|Superintendent of Schools|District School Boards'),
    ('County', 'county', r'County Commission|Property Appraiser|Tax Collector|Sheriff|Clerk of|Supervisor of Elections|'
                         r"Bay County|County Property Tax"),
    ('State', None, r'Governor|Attorney General|Chief Financial Officer|Commissioner of Agriculture|State Senator|'
                    r'State Representative|State Attorney|Public Defender'),
]
SKIP_CITY_LEVELS = {'Party', 'Federal', 'Court', 'Special district', 'School district', 'State'}


def _city_of(name):
    for gid, pat in CITIES:
        if re.search(pat, name, re.I if not pat.startswith('^') else 0):
            return gid
    return None


def classify(contest, election_kind, view_city=None):
    """(level, gov_id, is_measure is decided by the caller) for a contest name."""
    for level, gid, pat in LEVELS:
        if re.search(pat, contest, re.I):
            if level == 'County' and _city_of(contest) and not re.search(r'County Commission|Bay County', contest):
                break
            return level, gid
    city = _city_of(contest) or view_city
    if city:
        return 'City', city
    if election_kind in ('general', 'primary'):
        return 'State', None  # a statewide constitutional amendment
    return 'City', None


def _norm_contest(name):
    n = CITY_PREFIX.sub('', name).lower()
    for _, pat in CITIES:
        n = re.sub(pat.lower().replace('^', ''), ' ', n)
    return re.sub(r'\b(city of|district|election)\b|[^a-z0-9 ]', ' ', n).split()


def _same_contest(a, b):
    """A city view repeats a countywide contest: the same candidates (one view can list a write-in the other leaves out,
    and counts can differ by a provisional ballot or two), or for a ballot question, the same wording without the city's
    name or the same vote counts."""
    ca, cb = {x['choice'].lower() for x in a['choices']}, {x['choice'].lower() for x in b['choices']}
    na, nb = ' '.join(_norm_contest(a['contest'])), ' '.join(_norm_contest(b['contest']))
    if _is_measure(a) and _is_measure(b):
        return na == nb or (na in nb or nb in na) and min(len(na), len(nb)) > 8 or sorted(x['votes'] or 0 for x in a['choices']) == sorted(x['votes'] or 0 for x in b['choices'])
    small, large = sorted((ca, cb), key=len)
    return bool(small) and small <= large and len(large) - len(small) <= 1


def _clean_contest(c):
    """Older result pages list over and under votes as choices; move them to the contest's own fields."""
    ch, c = [], dict(c)
    for x in c['choices']:
        k = (x.get('choice') or '').upper()
        if k in ('OVER VOTES', 'UNDER VOTES'):
            c['over_votes' if k.startswith('OVER') else 'under_votes'] = x.get('votes')
        else:
            ch.append(x)
    c['choices'] = ch
    return c


def _is_measure(c):
    names = {(x['choice'] or '').strip().lower() for x in c['choices']}
    return bool(names) and names <= {'yes', 'no', 'for', 'against', 'yes for approval', 'no for rejection'}


@functools.lru_cache(maxsize=1)
def _results():
    """Elections with city views and recounts folded in: ([election rows], [result rows])."""
    R = _load('elections', 'results.json')
    if not R:
        return [], []
    import ids
    place = _place()
    today = dt.date.today()
    by_date = {}
    for e in R['elections']:
        by_date.setdefault(e['date'], []).append(e)
    elections, results = [], []
    for d, es in sorted(by_date.items()):
        es = sorted(es, key=lambda e: e['election_id'])
        recounts = [e for e in es if e['kind'] == 'recount']
        mains = [e for e in es if e['kind'] != 'recount' and not (e is not es[0] and _city_of(e['name']) and e['name'] != es[0]['name'])]
        views = [e for e in es if e not in mains and e not in recounts]
        # a recount replaces the first count for the contests recounted; the manual recount (higher id) is final
        recount = {}
        for e in sorted(recounts, key=lambda e: e['election_id']):
            for c in e['contests']:
                recount[c['contest']] = (e, c)
        for m in mains:
            contests = [(m, _clean_contest(c), None) for c in m['contests']]
            for v in views if m is mains[0] else []:
                vcity = _city_of(v['name'])
                for c in map(_clean_contest, v['contests']):
                    i = next((i for i, (_, mc, _v) in enumerate(contests) if _norm_contest(mc['contest']) == _norm_contest(c['contest']) and _same_contest(mc, c)),
                             next((i for i, (_, mc, _v) in enumerate(contests) if _same_contest(mc, c)), None))
                    if i is None:
                        contests.append((v, c, vcity))
                    else:  # same contest: now we know the city, and keep the fuller list of choices
                        src, mc, city = contests[i]
                        if len(c['choices']) > len(mc['choices']):
                            src, mc = v, c
                        contests[i] = (src, mc, city or vcity)
            canceled = not m.get('ballots_cast') and dt.date.fromisoformat(d) < today
            status = 'canceled' if canceled else 'final' if m.get('complete') else 'counting'
            elections.append({'place_id': place, 'election_id': m['election_id'], 'date': d, 'name': m['name'], 'kind': m['kind'],
                              'status': status, 'registered_voters': m.get('registered_voters'), 'ballots_cast': m.get('ballots_cast'),
                              'turnout_pct': m.get('turnout_pct'), 'precincts_reporting': m.get('precincts_reporting'),
                              'precincts_total': m.get('precincts_total'), 'contests': len(contests), 'updated': m.get('updated'),
                              'source_url': m['source_url']})
            # a ballot question that names no city: the city whose own contest drew about the same number of votes
            totals = [(_city_of(CITY_PREFIX.sub('', c['contest'])) or vc, sum(x.get('votes') or 0 for x in c['choices'])) for _, c, vc in contests]
            for i, (src, c, vcity) in enumerate(contests):
                if vcity or _city_of(CITY_PREFIX.sub('', c['contest'])) or m['kind'] in ('general', 'primary'):
                    continue
                t = sum(x.get('votes') or 0 for x in c['choices'])
                near = sorted((abs(t - n) / max(n, 1), g) for g, n in totals if g)
                if near and near[0][0] < 0.03:
                    contests[i] = (src, c, near[0][1])
            for src, c, vcity in contests:
                rc = recount.get(c['contest'])
                if rc:
                    src, c = rc[0], _clean_contest(rc[1])
                name = c['contest']
                level, gid = classify(CITY_PREFIX.sub('', name), m['kind'], vcity)
                measure = _is_measure(c)
                pp = re.search(r'\((Republican|Florida Democratic|Libertarian)[^)]*\)|\(Universal Primary Contest\)', name)
                party_primary = None
                if pp:
                    party_primary = {'Republican': 'REP', 'Florida Democratic': 'DEM', 'Libertarian': 'LPF'}.get(pp.group(1), 'Universal primary') if pp.group(1) else 'Universal primary'
                office = re.sub(r'\s*\((Republican|Florida Democratic|Libertarian)[^)]*\)|\s*\(Universal Primary Contest\)', '', name).strip()
                ranked = sorted(c['choices'], key=lambda x: -(x.get('votes') or 0))
                rank = {id(x): i + 1 for i, x in enumerate(ranked)}
                local = level in ('County', 'School district', 'City') or (level == 'Court' and gid == 'county')
                for x in c['choices']:
                    pid = ids.person_id(x['choice']) if local and not measure else None
                    if level == 'Special district' and gid and not measure:  # only someone already on record with that district
                        pid = ids.person_id(x['choice'])
                        pid = pid if pid and gid in ((ids.person(pid) or {}).get('gov_ids') or []) else None
                    results.append({'place_id': place, 'election_id': m['election_id'], 'election_date': d, 'election_name': m['name'],
                                    'election_kind': m['kind'], 'contest_id': c['contest_id'], 'contest': name, 'office': office,
                                    'level': level, 'gov_id': gid, 'measure': measure, 'party_primary': party_primary,
                                    'recount': src['kind'] == 'recount', 'choice': x['choice'], 'party': x.get('party'),
                                    'person_entity_id': 'person:' + pid if pid else None,
                                    'election_day': x.get('election_day'), 'early_voting': x.get('early_voting'),
                                    'vote_by_mail': x.get('vote_by_mail'), 'votes': x.get('votes'), 'pct': x.get('pct'),
                                    'rank': rank[id(x)], 'over_votes': c.get('over_votes'), 'under_votes': c.get('under_votes'),
                                    'source_url': src['source_url']})
    return elections, results


def elections():
    return _results()[0]


def election_results():
    return _results()[1]


# --- Where and when to vote ------------------------------------------------------------------------------------------

def election_dates():
    V = _load('elections', 'voting.json')
    if not V:
        return []
    place = _place()
    out = [{'place_id': place, 'date': c['date'], 'end_date': c.get('end_date'), 'starts_at': None, 'election': c.get('election'),
            'kind': c['kind'], 'title': c['title'], 'source': 'Supervisor of Elections voter guide', 'url': c.get('source_url'),
            'source_url': c.get('source_url')} for c in V.get('calendar') or []]
    for ev in V.get('soe_events') or []:
        starts = ev['starts']
        out.append({'place_id': place, 'date': starts[:10], 'end_date': None, 'starts_at': None if ev.get('all_day') else starts,
                    'election': None, 'kind': 'soe_event', 'title': ev['title'], 'source': 'Supervisor of Elections events',
                    'url': ev.get('url'), 'source_url': ev.get('source_url')})
    return sorted(out, key=lambda r: (r['date'], r['starts_at'] or '', r['title']))


def voting_locations():
    V = _load('elections', 'voting.json')
    if not V:
        return []
    place = _place()
    ev = V.get('early_voting') or {}
    out = []
    for s in ev.get('sites') or []:
        ll = s.get('lat_lon') or [None, None]
        out.append({'place_id': place, 'kind': 'early_voting', 'election': ev.get('election'), 'starts': ev.get('starts'), 'ends': ev.get('ends'),
                    'hours': s.get('hours') or ev.get('hours'), 'precinct': None, 'name': s['name'], 'address': s['address'], 'city': s['city'],
                    'zip': s.get('zip'), 'lat': ll[0], 'lon': ll[1], 'url': ev.get('live_wait_url'), 'source_url': ev.get('source_url')})
    for p in V.get('polling_places') or []:
        ll = p.get('lat_lon') or [None, None]
        out.append({'place_id': place, 'kind': 'polling_place', 'election': None, 'starts': None, 'ends': None, 'hours': '7 a.m. to 7 p.m. on Election Day',
                    'precinct': p['precinct'], 'name': p['name'], 'address': p['address'], 'city': p.get('city'), 'zip': p.get('zip'),
                    'lat': ll[0], 'lon': ll[1], 'url': p.get('url'), 'source_url': p.get('source_url')})
    return out


def voting_info():
    """The links and notes the voting page shows beside the rows (not rows themselves)."""
    V = _load('elections', 'voting.json') or {}
    ev = V.get('early_voting') or {}
    return {'as_of': V.get('as_of'), 'finder_url': V.get('finder_url'), 'events_url': V.get('events_url'), 'early': {k: ev.get(k) for k in ('election', 'election_date', 'starts', 'ends', 'hours', 'note', 'live_wait_url', 'source_url')}}


# --- Public notices --------------------------------------------------------------------------------------------------

def public_notices():
    N = _load('notices', _county_dir(), 'notices.json')
    if not N:
        return []
    place = _place()
    return [{'place_id': place, **{k: n.get(k) for k in ('notice_id', 'published', 'gov_id', 'agency', 'kind', 'kind_label', 'title', 'event_date',
                                                       'notice_type', 'text', 'pdf_url', 'publication', 'source_url')}}
            for n in N['notices'] if (n.get('published') or '0') >= '2016']


def notices_info():
    N = _load('notices', _county_dir(), 'notices.json') or {}
    return {'as_of': N.get('as_of'), 'source_url': N.get('source_url')}


# --- Job openings ----------------------------------------------------------------------------------------------------

SMALL = {'a', 'an', 'and', 'as', 'at', 'by', 'for', 'in', 'of', 'on', 'or', 'the', 'to', 'with'}
UPPER = {'ese', 'pe', 'it', 'hvac', 'ii', 'iii', 'iv', 'ems', 'gis', 'cdl', 'ap', 'esol', 'ft', 'pt', 'jrotc', 'cte', 'ase', 'vpk', 'k-12', 'ib', 'aice', 'ccc', 'emt', 'emr', 'rn', 'lpn', 'cna', 'esl', 'ag', 'dj', 'asd'}


def _tcase(s):
    if not s or s != s.upper() or not re.search('[A-Z]', s):
        return s
    out = []
    for i, w in enumerate(s.lower().split()):
        core = w.strip('(),/-:')
        out.append(w.upper() if core in UPPER else w if i and core in SMALL else
                   '-'.join(p.upper() if p.strip('(),/:') in UPPER else p[:1].upper() + p[1:] for p in w.split('-')))
    return ' '.join(out)


def _jobs_file():
    return _load('jobs', _county_dir(), 'jobs.json')


def job_openings():
    J = _jobs_file()
    if not J:
        return []
    import hashlib, html
    place = _place()
    today = dt.date.today().isoformat()
    boards = {b['key']: b for b in J['boards']}
    out, seen = [], set()
    for j in J['jobs']:
        if j.get('closes') and j['closes'] < today:
            continue
        url = html.unescape(j.get('url') or '')
        key = f"{j['board']}|{j.get('ref') or url}|{j['title']}"
        if key in seen:
            continue
        seen.add(key)
        out.append({'place_id': place, 'job_id': 'job:' + hashlib.sha1(key.encode()).hexdigest()[:12], 'board': j['board'], 'gov_id': j.get('gov_id'),
                    'employer': j['employer'], 'title': _tcase(j['title']), 'department': _tcase(j.get('department')), 'job_type': j.get('job_type'),
                    'pay': j.get('pay'), 'posted': j.get('posted'), 'closes': j.get('closes'), 'ref': j.get('ref'), 'url': url or None,
                    'first_seen': j.get('first_seen'), 'source_url': boards.get(j['board'], {}).get('url')})
    return out


def job_boards():
    J = _jobs_file()
    if not J:
        return []
    place = _place()
    counts = {}
    for j in job_openings():
        counts[j['board']] = counts.get(j['board'], 0) + 1
    return [{'place_id': place, 'board': b['key'], 'gov_id': b.get('gov_id'), 'employer': b['employer'], 'url': b['url'], 'read': b['read'],
             'openings': counts.get(b['key'], 0) if b['read'] else None, 'note': b.get('note'), 'checked': J.get('as_of', '')[:10] or None}
            for b in J['boards']]


def jobs_info():
    J = _jobs_file() or {}
    return {'as_of': J.get('as_of')}
