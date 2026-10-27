#!/usr/bin/env python3
"""Public schools for a place -> data/schools/<county>/: schools.json, zones.json, calendar.json.

    python3 data/schools/fetch_schools.py [--place fl-bay] [--only directory,zones,calendar]

Sources (all public, no sign-in), set per place in places/<id>/place.json "schools":
- directory: the U.S. Department of Education's Common Core of Data school directory, read through the Urban
  Institute's Education Data API (educationdata.urban.org). Name, state school number, level, grades, address, phone,
  charter, enrollment and teachers for every public school in the district, plus enrollment for each year since 2016.
- zones: the district's attendance zones (elementary, middle and high) as the county's GIS server publishes them.
  Shapes are simplified to about 40 meters, which is plenty to tell which zone an address is in.
- calendar: the district website's events feed (Apptegy/Thrillshare): first and last day, holidays, no-school days,
  early release, grading periods, graduations and School Board meetings. Past events of the school year are kept.

A source that fails keeps what is already on file and records the error. Nothing before 2016 is kept.
"""
import argparse, datetime as dt, json, os, re, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'data', 'entities'))
from cutoff import FIRST_YEAR  # noqa: E402

UA = 'Mozilla/5.0 (compatible; BayCounty.me public records reader; +https://baycounty.me/about)'
URBAN = 'https://educationdata.urban.org/api/v1/schools/ccd/directory/{year}/'
LEVEL = {1: 'Elementary', 2: 'Middle', 3: 'High', 4: 'Combined', 5: 'Other', 6: 'Other', 7: 'Other'}
TYPE = {1: 'Regular', 2: 'Special education', 3: 'Career and technical', 4: 'Alternative'}


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def place_conf(place):
    p = json.load(open(os.path.join(ROOT, 'places', place, 'place.json')))
    return p, p['schools']


def out_dir(place):
    d = os.path.join(HERE, place.split('-', 1)[-1])
    os.makedirs(d, exist_ok=True)
    return d


def load(path, default):
    try:
        return json.load(open(path))
    except (FileNotFoundError, ValueError):
        return default


def save(path, obj, compact=False):
    with open(path, 'w') as f:
        json.dump(obj, f, indent=None if compact else 1, separators=(',', ':') if compact else None, ensure_ascii=False)
        f.write('\n')


def grade_label(g):
    return {-1: 'PK', 0: 'K', 13: 'Adult'}.get(g, str(g)) if g is not None and g > -2 else None


def title_case(s):
    s = (s or '').title()
    s = re.sub(r"\b(Of|At|In|And|The)\b", lambda m: m.group(1).lower(), s)
    s = re.sub(r'\b(Ii|Iii|Iv|Ese|Sabl|Mlk)\b', lambda m: m.group(1).upper(), s)
    s = re.sub(r"\b([A-Z])\.([a-z])", lambda m: m.group(1) + '.' + m.group(2).upper(), s)
    s = s.replace('J.R.', 'J.R.').replace(' Inc', ' Inc.').replace('Inc..', 'Inc.')
    return s[0].upper() + s[1:] if s else s


def fetch_directory(conf, latest):
    """Every school in the district: latest CCD directory year plus each year's enrollment since FIRST_YEAR."""
    q = f"?fips={conf['fips']}&leaid={conf['nces_leaid']}"
    years = {}
    for y in range(FIRST_YEAR, latest + 1):
        try:
            rows = get(URBAN.format(year=y) + q)['results']
            if rows:
                years[y] = rows
        except Exception as e:  # a year not published yet
            print(f'  directory {y}: {e}', file=sys.stderr)
    if not years:
        raise RuntimeError('no directory year answered')
    last = max(years)
    hist = {}
    for y, rows in years.items():
        for s in rows:
            if s.get('enrollment') is not None and s['enrollment'] >= 0:
                hist.setdefault(s['seasch'], {})[str(y)] = s['enrollment']
    schools = []
    for s in years[last]:
        if s.get('school_status') not in (1, 3, 4, 5, 8):  # open, new, added, changed, reopened
            continue
        lo, hi = grade_label(s.get('lowest_grade_offered')), grade_label(s.get('highest_grade_offered'))
        frl = s.get('free_or_reduced_price_lunch')
        enr = s.get('enrollment') if (s.get('enrollment') or 0) > 0 else None
        schools.append({
            'school_number': s['seasch'], 'nces_id': s['ncessch'], 'name_raw': s['school_name'], 'name': title_case(s['school_name']),
            'level': LEVEL.get(s.get('school_level'), 'Other'), 'school_type': TYPE.get(s.get('school_type'), 'Other'),
            'charter': s.get('charter') == 1, 'virtual': s.get('virtual') == 1,
            'grades': f'{lo}-{hi}' if lo and hi and lo != hi else lo,
            'address': title_case(s.get('street_location')), 'city': title_case(s.get('city_location')), 'zip': s.get('zip_location'),
            'phone': s.get('phone'), 'latitude': s.get('latitude'), 'longitude': s.get('longitude'),
            'enrollment': enr, 'teachers_fte': s.get('teachers_fte') if (s.get('teachers_fte') or 0) > 0 else None,
            'free_reduced_lunch': frl if (frl or 0) > 0 else None,
            'enrollment_by_year': hist.get(s['seasch'], {}),
        })
    schools.sort(key=lambda r: r['school_number'])
    return {'directory_year': last, 'school_year': f'{last}-{str(last + 1)[2:]}', 'schools': schools,
            'source_url': f"https://educationdata.urban.org/api/v1/schools/ccd/directory/{last}/{q}",
            'source_title': "U.S. Department of Education, Common Core of Data school directory (via the Urban Institute Education Data API)"}


def fetch_zones(conf):
    """Attendance zone polygons, one feature per zone (pieces of the same zone are kept together)."""
    out = []
    for level, layer in conf['zone_layers'].items():
        base = f"{conf['zones_service']}/{layer}"
        p = urllib.parse.urlencode({'where': '1=1', 'outFields': 'OBJECTID,TYPE,NAME,LAST_EDIT_DATE', 'returnGeometry': 'true', 'outSR': 4326,
                                    'maxAllowableOffset': 0.0004, 'geometryPrecision': 5, 'f': 'json'})
        d = get(f'{base}/query?{p}', timeout=120)
        if d.get('error'):
            raise RuntimeError(d['error'].get('message'))
        zones = {}
        for f in d.get('features', []):
            a, g = f['attributes'], f.get('geometry') or {}
            name = re.sub(r'\s+', ' ', (a.get('NAME') or '').strip())
            if not name or not g.get('rings'):
                continue
            z = zones.setdefault(name, {'level': level, 'zone_name': name, 'rings': [], 'pieces': 0, 'last_edited': None, 'layer_url': base})
            z['rings'] += g['rings']
            z['pieces'] += 1
            if a.get('LAST_EDIT_DATE'):
                d8 = dt.datetime.fromtimestamp(a['LAST_EDIT_DATE'] / 1000, dt.timezone.utc).date().isoformat()
                z['last_edited'] = max(z['last_edited'] or d8, d8)
        out += sorted(zones.values(), key=lambda z: z['zone_name'])
    return out


KINDS = [  # first match wins
    ('board-meeting', r'school board|board meeting|workshop'),
    ('graduation', r'graduation'),
    ('first-day', r'first day'),
    ('last-day', r'last day'),
    ('early-release', r'early release|early dismissal'),
    ('grading', r'end of (the )?(first|second|third|fourth) nine weeks|end of (semester|quarter)|report card'),
    ('break', r'break|holidays\b|christmas|winter'),
    ('no-school', r'no school|holiday|labor day|veterans|thanksgiving|martin luther|presidents|good friday|memorial|teacher planning|planning day|records w'),
]


def kind_of(title):
    t = title.lower()
    for k, rx in KINDS:
        if re.search(rx, t):
            return k
    return 'other'


def school_year(d):
    y = int(d[:4]); m = int(d[5:7])
    a = y if m >= 7 else y - 1
    return f'{a}-{str(a + 1)[2:]}'


def fetch_calendar(conf, have):
    """District calendar events, merged with those already on file (the feed only lists upcoming ones)."""
    events, page = [], 1
    while page <= 20:
        d = get(f"{conf['calendar_feed']}?locale=en&page_no={page}")
        for e in d.get('events', []):
            title = re.sub(r'\s+', ' ', (e.get('title') or '')).strip()
            if not title:
                continue
            s, en = e.get('formatted_start'), e.get('formatted_end')
            all_day = bool(e.get('all_day'))
            events.append({'event_id': str(e['id']), 'title': title, 'kind': kind_of(title),
                           'starts': (s[:10] if all_day else s.replace(' ', 'T')[:16]) if s else None,
                           'ends': (en[:10] if all_day else en.replace(' ', 'T')[:16]) if en else None,
                           'all_day': all_day, 'venue': (e.get('venue') or '').strip() or None,
                           'school_year': school_year(s) if s else None})
        nxt = (d.get('meta') or {}).get('links', {}).get('next')
        last = (d.get('meta') or {}).get('links', {}).get('last') or ''
        if not nxt or f'page_no={page}' in last:
            break
        page += 1
    if not events:
        raise RuntimeError('calendar feed returned no events')
    by_id = {e['event_id']: e for e in have}
    fresh = {e['event_id'] for e in events}
    today = dt.date.today().isoformat()
    # an upcoming event that left the feed was cancelled or moved: drop it; past events stay on file
    kept = [e for i, e in by_id.items() if i not in fresh and (e.get('ends') or e.get('starts') or '')[:10] < today]
    allv = kept + events
    allv = [e for e in allv if (e.get('starts') or '')[:4] >= str(FIRST_YEAR)]
    return sorted(allv, key=lambda e: (e['starts'] or '', e['title']))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--place', default=os.environ.get('PLACE', 'fl-bay'))
    ap.add_argument('--only', default='directory,zones,calendar')
    ap.add_argument('--latest', type=int, default=dt.date.today().year - 1, help='newest directory year to try')
    a = ap.parse_args()
    place, conf = place_conf(a.place)
    od = out_dir(a.place)
    only = set(a.only.split(','))
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    errors = 0

    if 'directory' in only:
        path = os.path.join(od, 'schools.json')
        try:
            d = fetch_directory(conf, a.latest)
            d.update({'place_id': a.place, 'fetched': now})
            save(path, d)
            print(f"schools: {len(d['schools'])} in the {d['school_year']} directory")
        except Exception as e:
            errors += 1
            print(f'schools: kept the file on hand ({e})', file=sys.stderr)

    if 'zones' in only:
        path = os.path.join(od, 'zones.json')
        try:
            z = fetch_zones(conf)
            save(path, {'place_id': a.place, 'fetched': now, 'source_url': conf['zones_service'], 'zones': z}, compact=True)
            print(f'zones: {len(z)}')
        except Exception as e:
            errors += 1
            print(f'zones: kept the file on hand ({e})', file=sys.stderr)

    if 'calendar' in only:
        path = os.path.join(od, 'calendar.json')
        have = load(path, {'events': []})
        try:
            ev = fetch_calendar(conf, have.get('events') or [])
            save(path, {'place_id': a.place, 'fetched': now, 'source_url': conf['calendar_page'], 'feed_url': conf['calendar_feed'], 'error': None, 'events': ev})
            print(f'calendar: {len(ev)} events')
        except Exception as e:
            errors += 1
            have.update({'error': str(e), 'error_at': now})
            save(path, have)
            print(f'calendar: kept {len(have.get("events") or [])} events on hand ({e})', file=sys.stderr)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
