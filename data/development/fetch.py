"""Development projects and new-home permits for one place (default fl-bay).

Writes data/development/<county>/projects.json and permits.json from the sources in data/development/<county>/sources.json:

  * projects: each government's public development map layer (ArcGIS), one row per project: name, what it is, size,
    address, status, application and approval dates. Undated rows and rows whose last date is before 2016 are left out.
  * permits: new privately owned housing units authorized by building permits, from the Census Bureau's Building
    Permits Survey, per year for the county, each city and the unincorporated area (2016 on), plus this year so far.

Run: python3 data/development/fetch.py   (PLACE=fl-bay by default). Safe to re-run; keeps the old fetched date when
nothing changed so a scheduled refresh doesn't commit a date-only change.
"""
import csv, datetime as dt, io, json, os, re, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'entities'))
import cutoff  # noqa: E402  the site's first year (2016)

PLACE = os.environ.get('PLACE', 'fl-bay')
D = os.path.join(HERE, PLACE.split('-', 1)[-1])
CFG = json.load(open(os.path.join(D, 'sources.json')))
UA = {'User-Agent': 'BayCounty.me data refresh (+https://baycounty.me/data-sources)'}
BPS = 'https://www2.census.gov/econ/bps'


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise


def day(v):
    if isinstance(v, (int, float)) and abs(v) > 1e11:
        return dt.datetime.fromtimestamp(v / 1000, dt.UTC).date().isoformat()
    return None


def clean(s):
    s = re.sub(r'\s+', ' ', str(s or '')).strip()
    return s or None


def save(name, key, rows, extra):
    dest = os.path.join(D, name)
    fetched = dt.date.today().isoformat()
    try:
        prev = json.load(open(dest))
        if prev.get(key) == json.loads(json.dumps(rows)):
            fetched = prev.get('fetched') or fetched
    except (FileNotFoundError, ValueError):
        pass
    json.dump({'place_id': CFG['place_id'], 'fetched': fetched, **extra, key: rows}, open(dest, 'w'), indent=1)


# --- development projects -----------------------------------------------------------------------------------------

STATUS = {'order issued': 'Approved', 'approved': 'Approved', 'under review': 'Under review', 'denied': 'Denied', 'withdrawn': 'Withdrawn'}


def layer_rows(L):
    q = urllib.parse.urlencode({'where': '1=1', 'outFields': '*', 'returnGeometry': 'true', 'outSR': 4326, 'f': 'json'})
    feats = json.loads(get(f"{L['url']}/query?{q}"))['features']
    f = L['fields']
    out = []
    for ft in feats:
        a, g = ft['attributes'], ft.get('geometry') or {}
        v = lambda k: a.get(f[k]) if k in f else None
        applied, approved = day(v('applied')), day(v('approved'))
        permit, occ = day(v('building_permit')), day(v('occupancy'))
        dates = [x for x in (applied, approved, permit, occ) if x]
        if not dates or not cutoff.keep(max(dates)):
            continue  # undated, or nothing on record since 2016
        st = clean(v('status'))
        status = STATUS.get((st or '').lower(), st)
        if not status:  # layers without a status column: the furthest step on record
            status = 'Built' if occ else 'Permitted' if permit else 'Approved' if approved else 'Applied'
        name = clean(v('name')) or clean(v('description')) or 'Unnamed project'
        out.append({
            'project_id': f"{L['id']}:{clean(v('number')) or a.get('OBJECTID')}",
            'layer': L['id'], 'gov_id': L['gov_id'], 'name': name, 'case_number': clean(v('number')),
            'description': clean(v('description')), 'size': clean(v('size')), 'location': clean(v('location')),
            'status': status, 'applied_date': applied, 'approved_date': approved, 'permit_date': permit, 'occupancy_date': occ,
            'plans_url': clean(v('plans')), 'lat': round(g['y'], 6) if g.get('y') else None,
            'lng': round(g['x'], 6) if g.get('x') else None, 'source_url': L['url'],
        })
    return out


def projects():
    rows, layers = [], []
    for L in CFG['development_layers']:
        r = layer_rows(L)
        rows += r
        layers.append({k: L[k] for k in ('id', 'gov_id', 'label', 'url', 'page')} | {'rows': len(r)})
        print(L['id'], len(r))
    if not rows:
        raise SystemExit('No development projects returned; keeping the existing file.')
    rows.sort(key=lambda r: (r['applied_date'] or r['approved_date'] or r['permit_date'] or '', r['project_id']), reverse=True)
    save('projects.json', 'projects', rows, {'layers': layers})


# --- new-home permits (Census Building Permits Survey) ------------------------------------------------------------

COLS = ['1u', '2u', '34u', '5u']  # building types in each BPS file, in order: 1 unit, 2 units, 3-4 units, 5+ units


def bps_rows(text, place_file):
    """Parse a BPS .txt (two header lines). Returns {name: {months, '1u_bldgs', '1u_units', '1u_value', ...}}."""
    out = {}
    c = CFG['census']
    for rec in csv.reader(io.StringIO(text)):
        if len(rec) < 20 or not rec[0].strip().isdigit():
            continue
        if place_file:
            if rec[1].strip() != c['state_fips'] or rec[3].strip() != c['county_fips']:
                continue
            name, months, nums = rec[16].strip(), rec[15].strip(), rec[17:29]
        else:
            if rec[1].strip() != c['state_fips'] or rec[2].strip() != c['county_fips']:
                continue
            name, months, nums = rec[5].strip(), None, rec[6:18]
        r = {'months': int(months) if months and months.isdigit() else None}
        for i, t in enumerate(COLS):
            b, u, v = (int(float(x or 0)) for x in nums[i * 3:i * 3 + 3])
            r[f'{t}_bldgs'], r[f'{t}_units'], r[f'{t}_value'] = b, u, v
        out[name] = r
    return out


def permits():
    c = CFG['census']
    region = urllib.parse.quote(c['region'])
    today = dt.date.today()
    rows = []
    first = cutoff.FIRST_YEAR
    periods = [(y, f'{y}a', 12) for y in range(first, today.year)]
    # this year so far: the latest year-to-date file the Census Bureau has posted
    idx = get(f'{BPS}/County/').decode('utf-8', 'replace')
    ytd = sorted(set(re.findall(rf'co({today.year % 100:02d}\d\d)y\.txt', idx)))
    if ytd:
        periods.append((today.year, f'{ytd[-1]}y', int(ytd[-1][2:])))
    last_year = periods[-1][0]
    for year, code, months in periods:
        try:
            county = bps_rows(get(f'{BPS}/County/co{code}.txt').decode('latin-1'), False)
            places = bps_rows(get(f'{BPS}/Place/{region}/{c["region_prefix"]}{code}.txt').decode('latin-1'), True)
        except Exception as ex:  # the annual file for last year appears in spring
            if year >= today.year - 1:
                print('skip', year, ex)
                continue
            raise
        src = f'{BPS}/Place/{region}/{c["region_prefix"]}{code}.txt'
        period = f'{year}' if months == 12 and code.endswith('a') else f'Jan to {dt.date(2000, months, 1):%b} {year}'
        groups = [('county-total', None, 'All of ' + next(iter(county), 'the county'), county, f'{BPS}/County/co{code}.txt')]
        for name, rec in places.items():
            m = c['places'].get(name)
            if m:
                groups.append((m['gov_id'], m['gov_id'], m['area'], {name: rec}, src))
        for key, gov, area, recs, url in groups:
            rec = next(iter(recs.values()), None)
            if not rec:
                continue
            units = sum(rec[f'{t}_units'] for t in COLS)
            value = sum(rec[f'{t}_value'] for t in COLS)
            rows.append({
                'area_id': key, 'gov_id': gov, 'area': area, 'year': year, 'period': period, 'months': months, 'year_to_date': code.endswith('y'),
                'months_reported': rec['months'], 'estimated': rec['months'] == 0 if rec['months'] is not None else False,
                'single_family_units': rec['1u_units'], 'single_family_value': rec['1u_value'],
                'two_to_four_units': rec['2u_units'] + rec['34u_units'], 'two_to_four_buildings': rec['2u_bldgs'] + rec['34u_bldgs'],
                'two_to_four_value': rec['2u_value'] + rec['34u_value'],
                'five_plus_units': rec['5u_units'], 'five_plus_buildings': rec['5u_bldgs'], 'five_plus_value': rec['5u_value'],
                'total_units': units, 'total_value': value, 'source_url': url,
            })
        print(year, code, len(groups))
    if not rows:
        raise SystemExit('No permit rows; keeping the existing file.')
    save('permits.json', 'permits', rows, {'source': 'U.S. Census Bureau, Building Permits Survey', 'source_page': 'https://www.census.gov/construction/bps/', 'latest_year': last_year})


if __name__ == '__main__':
    what = sys.argv[1:] or ['projects', 'permits']
    if 'projects' in what:
        projects()
    if 'permits' in what:
        permits()
