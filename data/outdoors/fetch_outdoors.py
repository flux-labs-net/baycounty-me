#!/usr/bin/env python3
"""Beaches, beach water quality, parks, boat ramps and trails -> data/outdoors/<county>/*.json.

    python3 data/outdoors/fetch_outdoors.py [--county bay] [--only places,water,conditions]

Sources (all public, no sign-in):
  places      Bay County GIS (ArcGIS Online, BayCounty_GISadmin): Beach_Access, Bay_County_Beach_Parking, ParkPts,
              Bay_County_Parks_and_Boat_Launches, Boat_Ramps, Trail. Panama City Beach GIS (Recreation): which beach
              accesses are wheelchair accessible. Florida DEP Coastal Access Sites: amenities at each access.
  water       Florida Department of Health, Florida Healthy Beaches Program: sampling sites (FloridaBeachSamplingPoints)
              and every published sample per site (the Beach Detail lookup on floridahealth.gov, a Caspio data page).
  conditions  National Weather Service Tallahassee Surf Zone Forecast (SRF) for Coastal Bay (FLZ112): the beach flag
              color the beach officials reported, rip current risk, surf, UV and water temperature; and active beach
              alerts for the zone. Each run adds that day's flag to the flag history.

A source that fails keeps what is already on file and notes the error. Run daily (conditions, water) from
refresh-meetings.yml; places change rarely but are cheap to re-read.
"""
import argparse, datetime as dt, html, json, math, os, re, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'entities'))
import cutoff  # noqa: E402  the site's first year (2016): older samples are dropped
UA = 'Mozilla/5.0 (compatible; BayCounty.me public data reader; +https://baycounty.me/about)'
BAY = 'https://services1.arcgis.com/QB0VWfqR9MD4lF0F/arcgis/rest/services'
PCB = 'https://services7.arcgis.com/HMHYRsYOvuxpp8zD/arcgis/rest/services/Recreation/FeatureServer'
DEP = 'https://services1.arcgis.com/nRHtyn3uE1kyzoYc/arcgis/rest/services/BEACH_ACCESS_SITES/FeatureServer/0'
DOH = 'https://services1.arcgis.com/CY1LXxl9zlJeBuRZ/arcgis/rest/services/FloridaBeachSamplingPoints/FeatureServer/0'
CASPIO = 'https://c0cqk120.caspio.com/dp/cb8a100027f4e6ea6cbc4260a71e'
DOH_PAGE = 'https://www.floridahealth.gov/community-environmental-public-health/environmental-public-health/water-quality/beach-water-quality/beach-detail/'
COUNTIES = {'bay': {'name': 'Bay', 'nws_office': 'TAE', 'nws_zone': 'FLZ112', 'flag_label': 'Bay'}}
GOV = {'Bay County': 'county', 'Panama City': 'pc', 'Panama City Beach': 'pcb', 'Lynn Haven': 'lh', 'Callaway': 'cw',
       'Springfield': 'sp', 'Parker': 'parker', 'Mexico Beach': 'mb'}


def get(url, timeout=60, accept='application/json, */*'):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def features(layer, where='1=1', geometry='false', extra=''):
    out, offset = [], 0
    while True:
        q = urllib.parse.urlencode({'where': where, 'outFields': '*', 'returnGeometry': geometry, 'outSR': 4326, 'f': 'json',
                                    'resultOffset': offset, 'resultRecordCount': 1000}) + extra
        d = json.loads(get(f'{layer}/query?{q}'))
        if 'error' in d:
            raise RuntimeError(f"{layer}: {d['error']}")
        fs = d.get('features', [])
        out += fs
        if not d.get('exceededTransferLimit') or not fs:
            return out
        offset += len(fs)


def clean(s):
    s = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', str(s)))).strip() if s is not None else ''
    return s or None


def yes(v):
    v = (clean(v) or '').lower()
    return True if v in ('yes', 'y', 'true', '1') else False if v in ('no', 'n', 'false', '0') else None


def title(s):
    s = clean(s)
    if not s:
        return None
    small = {'of', 'and', 'the', 'at', 'on'}
    keep = {'pcb', 'bcc', 'ii', 'iii', 'us', 'fl', 'dep', 'ymca'}
    words = re.split(r'(\s+)', s.lower())
    return ''.join(w.upper() if w in keep else (w if (w in small and i) else w[:1].upper() + w[1:]) for i, w in enumerate(words))


def miles(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    h = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    return 7917.6 * math.asin(math.sqrt(h))


def centroid(geom):
    pts = [p for ring in (geom or {}).get('rings') or [] for p in ring] or [p for path in (geom or {}).get('paths') or [] for p in path]
    if (geom or {}).get('x') is not None:
        return geom['y'], geom['x']
    if not pts:
        return None
    return sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts)


def city_of(addr, lat, lon):
    a = (addr or '').upper()
    for k in ('PANAMA CITY BEACH', 'MEXICO BEACH', 'LYNN HAVEN', 'CALLAWAY', 'SPRINGFIELD', 'PARKER', 'YOUNGSTOWN', 'FOUNTAIN', 'SOUTHPORT', 'PANAMA CITY'):
        if k in a:
            return title(k)
    return None


# --- places --------------------------------------------------------------------------------------------------------

def facilities(desc):
    """'<p>-Restrooms</p><p>-Picnic Area</p>' from the county's park tour layer -> ['Restrooms', 'Picnic Area'], address, acres."""
    parts = [clean(p) for p in re.split(r'</p>|<br\s*/?>', desc or '')]
    parts = [p for p in parts if p]
    fac = [p.lstrip('-').strip() for p in parts if p.startswith('-')]
    acres = next((float(m.group(1)) for p in parts for m in [re.search(r'\*?\s*([\d.]+)\s*Acres', p, re.I)] if m), None)
    addr = [p for p in parts if not p.startswith(('-', '*')) and not p.lower().startswith('facilities') and not re.search(r'acres', p, re.I)]
    return fac, acres, addr


def fetch_places(county):
    out = {'fetched_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}
    # beach accesses: county list (all of the county's Gulf beach), PCB's list for wheelchair access, DEP's for amenities
    acc = features(f'{BAY}/Beach_Access/FeatureServer/0')
    pcb = {(clean(f['attributes'].get('NUM')) or '', clean(f['attributes'].get('ADDRESS')) or ''): f['attributes'] for f in features(f'{PCB}/0')}
    pcb_num = {k[0]: v for k, v in pcb.items()}
    dep = [f['attributes'] for f in features(DEP, "COUNTY='Bay'")]
    rows = []
    for f in acc:
        a = f['attributes']
        lat, lon = a.get('lat'), a.get('long')
        num = clean(a.get('NUM'))
        addr = title(a.get('ADDRESS'))
        p = pcb.get((num or '', clean(a.get('ADDRESS')) or '')) or (pcb_num.get(num) if num and lat and lon and pcb_num.get(num) and miles((lat, lon), (pcb_num[num]['lat'], pcb_num[num]['long'])) < 0.1 else None)
        near = min(dep, key=lambda d: miles((lat, lon), (d['Y_LATITUDE'], d['X_LONGITUD']))) if dep and lat else None
        dist = miles((lat, lon), (near['Y_LATITUDE'], near['X_LONGITUD'])) if near else 99
        d = near if dist <= 0.04 else {}
        name = title(a.get('ACCESS')) or (f'Beach Access {num}' if num else None) or clean(d.get('ACCESS_NAM')) or addr or 'Beach access'
        rows.append({
            'access_id': f"{county}-access-{a['OBJECTID']}", 'name': name, 'number': num, 'address': addr,
            'area': 'Mexico Beach' if lon and lon > -85.45 else ('Panama City Beach' if p else 'Unincorporated Bay County'),
            'latitude': round(lat, 6) if lat else None, 'longitude': round(lon, 6) if lon else None,
            'vehicle_access': yes(a.get('VEH')), 'wheelchair_access': yes(p.get('HANDICAP_ACCESS')) if p else yes(d.get('ADA_ACCESS')),
            'parking': yes(d.get('REGULAR_PA')), 'parking_spaces': int(d['NUMBER_OF_']) if str(d.get('NUMBER_OF_') or '').strip().isdigit() else None,
            'ada_parking': yes(d.get('ADA_PARKIN')), 'restroom': yes(d.get('RESTROOM')), 'shower': yes(d.get('SHOWER')),
            'lifeguard': yes(d.get('LIFEGUARD')), 'boardwalk': yes(d.get('BOARDWALK_')), 'notes': clean(d.get('NOTES')),
            'state_access_name': clean(d.get('ACCESS_NAM')), 'state_site_id': clean(d.get('STATE_ID')),
            'source_url': f'{BAY}/Beach_Access/FeatureServer/0'})
    out['beach_access'] = sorted(rows, key=lambda r: (r['longitude'] or 0))
    # beach parking lots (county): spaces and the nearest access
    lots = []
    for f in features(f'{BAY}/Bay_County_Beach_Parking/FeatureServer/0', geometry='true'):
        c = centroid(f.get('geometry'))
        a = f['attributes']
        near = min(rows, key=lambda r: miles(c, (r['latitude'], r['longitude']))) if c and rows else None
        lots.append({'lot_id': f"{county}-beach-lot-{a['OBJECTID']}", 'spaces': a.get('NumberOfSpaces'), 'parking_type': clean(a.get('TypeOfParking')),
                     'latitude': round(c[0], 6) if c else None, 'longitude': round(c[1], 6) if c else None,
                     'nearest_access': near['name'] if near else None, 'nearest_access_id': near['access_id'] if near else None,
                     'source_url': f'{BAY}/Bay_County_Beach_Parking/FeatureServer/0'})
    out['beach_parking'] = lots
    # parks: the county's inventory of every government's parks, plus the facility lists and photos from its park tour
    tour = {}
    for f in features(f'{BAY}/Bay_County_Parks_and_Boat_Launches/FeatureServer/0', geometry='true') + features(f'{BAY}/Beach_Accesses/FeatureServer/0', geometry='true'):
        a = f['attributes']
        fac, acres, addr = facilities(a.get('description'))
        c = centroid(f.get('geometry'))
        tour.setdefault(re.sub(r'[^a-z0-9]', '', (clean(a.get('name')) or '').lower()), {'name': clean(a.get('name')), 'facilities': fac, 'acres': acres,
                                                                                          'address': ', '.join(addr) or None, 'photo_url': a.get('pic_url'), 'lat_lon': c})
    parks = []
    used = set()
    for f in features(f'{BAY}/ParkPts/FeatureServer/0'):
        a = f['attributes']
        nm = clean(a.get('NAME'))
        if not nm:
            continue
        key = re.sub(r'[^a-z0-9]', '', nm.lower())
        t = tour.get(key) or tour.get(key.replace('park', '')) or next((v for k, v in tour.items() if k and (k in key or key in k) and len(k) > 6), None)
        if t:
            used.add(t['name'])
        admin = (clean(a.get('ADMINISTRA')) or '').strip()
        amen = {k: yes(a.get(src)) for k, src in (('restroom', 'RESTROOM'), ('community_building', 'COM_BUILD'), ('pavilion', 'PAVILION'), ('picnic_tables', 'PICNIC_TAB'),
                                                   ('beach_access', 'BEACH_ACCE'), ('boat_ramp', 'BOAT_RAMP'), ('boat_dock', 'BOAT_DOCK'), ('fishing_pier', 'FISHING_PI'),
                                                   ('baseball', 'BASEBALL'), ('basketball', 'BASKETBALL'), ('football', 'FOOTBALL'), ('soccer', 'SOCCER'),
                                                   ('volleyball', 'VOLLEYBALL'), ('tennis', 'TENNIS'), ('trail', 'TRAIL'), ('playground', 'PLAYGROUND'))}
        use = clean(a.get('PRIMARY_US'))
        parks.append({'park_id': f"{county}-park-{a['OBJECTID']}", 'name': nm, 'address': title(a.get('ADDRESS')), 'run_by': admin or None,
                      'gov_id': GOV.get(admin), 'acres': a.get('SIZE_AC') or (t or {}).get('acres'),
                      'kind': (use[:1].upper() + use[1:].lower()) if use else None, 'also': clean(a.get('SEC_USE')),
                      **amen, 'other': clean(a.get('OTHER')),
                      'facilities': '; '.join(t['facilities']) if t and t['facilities'] else None, 'photo_url': (t or {}).get('photo_url'),
                      'latitude': round(a['Latitude'], 6) if a.get('Latitude') else None, 'longitude': round(a['Longitude'], 6) if a.get('Longitude') else None,
                      'source_url': f'{BAY}/ParkPts/FeatureServer/0'})
    # county parks in the tour that the inventory doesn't have (newer parks, the shooting range, piers)
    for k, t in tour.items():
        if t['name'] in used or not t['lat_lon'] or not t['name'] or re.search(r'boat ramp|launch|beach access \d', t['name'], re.I):
            continue
        first = lambda n: re.sub(r'[^a-z]', '', n.lower().split()[0])[:5]
        norm = lambda n: re.sub(r'[^a-z0-9]', '', n.lower().replace('park', ''))
        if any(norm(p['name']) == norm(t['name']) for p in parks):
            continue
        if any(p['latitude'] and (miles(t['lat_lon'], (p['latitude'], p['longitude'])) < 0.05 or
                                  (first(p['name']) == first(t['name']) and miles(t['lat_lon'], (p['latitude'], p['longitude'])) < 0.6)) for p in parks):
            continue
        parks.append({'park_id': f"{county}-park-t{abs(hash(k)) % 100000}", 'name': t['name'], 'address': t['address'], 'run_by': 'Bay County', 'gov_id': 'county',
                      'acres': t['acres'], 'kind': None, 'also': None, **{x: None for x in ('restroom', 'community_building', 'pavilion', 'picnic_tables', 'beach_access', 'boat_ramp',
                      'boat_dock', 'fishing_pier', 'baseball', 'basketball', 'football', 'soccer', 'volleyball', 'tennis', 'trail', 'playground')},
                      'other': None, 'facilities': '; '.join(t['facilities']) or None, 'photo_url': t['photo_url'],
                      'latitude': round(t['lat_lon'][0], 6), 'longitude': round(t['lat_lon'][1], 6), 'source_url': f'{BAY}/Bay_County_Parks_and_Boat_Launches/FeatureServer/0'})
    for p in parks:  # stable ids for tour-only parks
        if p['park_id'].startswith(f'{county}-park-t'):
            p['park_id'] = f"{county}-park-" + re.sub(r'[^a-z0-9]+', '-', p['name'].lower()).strip('-')
    out['parks'] = sorted(parks, key=lambda p: p['name'])
    # boat ramps
    ramps = []
    for f in features(f'{BAY}/Boat_Ramps/FeatureServer/0', geometry='true'):
        a = f['attributes']
        c = centroid(f.get('geometry'))
        admin = clean(a.get('ADMINISTRA'))
        ramps.append({'ramp_id': f"{county}-ramp-{a['OBJECTID']}", 'name': clean(a.get('NAME')), 'park': clean(a.get('PARK_NAME')), 'address': title(a.get('ADDRESS')),
                      'run_by': admin, 'gov_id': GOV.get(admin or ''), 'water': clean(a.get('WATER')), 'waterbody': clean(a.get('WATERBODY')),
                      'ramp_surface': clean(a.get('TYPE')), 'restroom': yes(a.get('RESTROOM')), 'boat_dock': yes(a.get('BOAT_DOCK')), 'fishing_pier': yes(a.get('FISHING_PI')),
                      'acres': a.get('SIZE_AC'), 'latitude': round(c[0], 6) if c else None, 'longitude': round(c[1], 6) if c else None,
                      'source_url': f'{BAY}/Boat_Ramps/FeatureServer/0'})
    out['boat_ramps'] = sorted(ramps, key=lambda r: r['name'] or '')
    # trails: segments grouped into named trails
    groups = {}
    for f in features(f'{BAY}/Trail/FeatureServer/0', geometry='true') + [dict(x, _pcb=True) for x in features(f'{PCB}/2', geometry='true')]:
        a = f['attributes']
        nm, fac = clean(a.get('NAME')), clean(a.get('FACILITYID'))
        if not nm and not fac:
            continue
        key = ((fac or '').lower(), (nm or fac).lower())
        g = groups.setdefault(key, {'name': nm or fac, 'area': fac if fac and fac != nm else None, 'meters': 0.0, 'surfaces': set(), 'uses': set(), 'levels': set(), 'pts': []})
        paths = (f.get('geometry') or {}).get('paths') or []
        for path in paths:
            for i in range(1, len(path)):
                g['meters'] += miles((path[i - 1][1], path[i - 1][0]), (path[i][1], path[i][0])) * 1609.344
            g['pts'] += path[:1]
        if clean(a.get('SURFTYPE')):
            g['surfaces'].add(clean(a['SURFTYPE']).capitalize())
        for k, lbl in (('HIKING', 'walking'), ('MTBCYCLE', 'mountain bikes'), ('ROADCYCLE', 'bikes'), ('EQUESTRIAN', 'horses'), ('ATV', 'ATVs'), ('MOTORCYCLE', 'motorcycles')):
            if yes(a.get(k)):
                g['uses'].add(lbl)
        if clean(a.get('SKILLLEVEL')):
            g['levels'].add(clean(a['SKILLLEVEL']).capitalize())
    trails = []
    for (fk, nk), g in groups.items():
        if g['meters'] < 50:
            continue
        pt = g['pts'][0] if g['pts'] else None
        trails.append({'trail_id': f"{county}-trail-" + re.sub(r'[^a-z0-9]+', '-', (fk + ' ' + nk)).strip('-'), 'name': title(g['name']) if g['name'].isupper() else g['name'],
                       'area': {'Saint Andrews': 'St. Andrews State Park', 'Pine Log': 'Pine Log State Forest', 'Camp Helen': 'Camp Helen State Park'}.get(g['area'], g['area']),
                       'miles': round(g['meters'] / 1609.344, 2), 'surface': ', '.join(sorted(g['surfaces'])) or None,
                       'uses': ', '.join(sorted(g['uses'])) or None, 'skill_level': ', '.join(sorted(g['levels'])) or None,
                       'latitude': round(pt[1], 6) if pt else None, 'longitude': round(pt[0], 6) if pt else None,
                       'source_url': f'{BAY}/Trail/FeatureServer/0'})
    out['trails'] = sorted(trails, key=lambda t: (t['area'] or '', t['name']))
    return out


# --- water quality ----------------------------------------------------------------------------------------------------

RATING = ((35.5, 'Good'), (70.5, 'Moderate'), (float('inf'), 'Poor'))


def rating(n):
    return None if n is None else next(lbl for lim, lbl in RATING if n < lim)


def caspio_rows(page_html):
    rows = []
    for r in re.findall(r'<tr[^>]*>(.*?)</tr>', page_html, re.S):
        cells = re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)
        txt = [re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', c))).strip() for c in cells]
        ident = next((t for t in txt if t.startswith('ID:')), None)
        date = next((t for t in txt if t.startswith('Date:')), None)
        if not ident or not date:
            continue
        ent = re.search(r"\(\s*'([^']*)'\s*>=\s*35\.5", r)
        adv = next((t.split(':', 1)[1].strip() for t in txt if t.startswith('Advisory:')), None)
        m, d, y = date.split(':', 1)[1].strip().split('/')
        val = ent.group(1).strip() if ent else ''
        rows.append({'sample_number': ident.split(':', 1)[1].strip(), 'date': f'{int(y):04d}-{int(m):02d}-{int(d):02d}',
                     'enterococcus': float(val) if re.fullmatch(r'[\d.]+', val) else None, 'reported': val or None,
                     'advisory': True if (adv or '').lower().startswith('y') else False if adv else None})
    nxt = re.findall(r'href="([^"]*cpipage=(\d+)[^"]*)"', page_html)
    return rows, {int(n): html.unescape(u) for u, n in nxt}


def fetch_water(county, prev):
    cname = COUNTIES[county]['name']
    sites = []
    for f in features(DOH, f"County='{cname}'"):
        a = f['attributes']
        link = clean(a.get('Link'))
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(link).query)) if link else {}
        sites.append({'site_id': clean(a.get('STORET_Sta')), 'name': title(a.get('SPLocation')), 'epa_beach_id': clean(a.get('EPAbeachID')),
                      'active': yes(a.get('Active')), 'latitude': a.get('SPLat'), 'longitude': a.get('SPLong'),
                      'lookup_name': q.get('SPLocation'), 'layer_name': clean(a.get('SPLocation')), 'source_url': link or DOH_PAGE})
    old = {(s['site_id'], s['sample_number']): s for s in (prev or {}).get('samples', []) if s['date'] >= cutoff.FIRST_DATE}
    samples, errors = dict(old), []
    for s in sites:
        # The state renames sites in its sample lookup without always updating the map layer's link (Dupont Bridge became
        # Earl Gilbert Park, PCB Beach Access became PCB Beach Access 41), so samples are looked up under both names.
        names = list(dict.fromkeys(n for n in (s['lookup_name'], s.pop('layer_name', None)) if n))
        if not s['active'] or not names:
            continue
        found = []
        for name in names:
            url = f"{CASPIO}?{urllib.parse.urlencode({'County': cname, 'SPLocation': name})}"
            try:
                page, seen = get(url, accept='text/html'), {1}
                while True:
                    rows, nxt = caspio_rows(page)
                    for r in rows:
                        if r['date'] < cutoff.FIRST_DATE:
                            continue
                        found.append((name, r['date']))
                        samples[(s['site_id'], r['sample_number'])] = {'site_id': s['site_id'], 'site': s['name'], **r,
                                                                        'rating': rating(r['enterococcus']) if r['enterococcus'] is not None else ('No result' if r['reported'] == 'NR' else None),
                                                                        'source_url': s['source_url']}
                    more = sorted(n for n in nxt if n not in seen)
                    if not more:
                        break
                    seen.add(more[0])
                    page = get(nxt[more[0]], accept='text/html')
            except Exception as ex:  # keep what's on file for this site
                errors.append(f"{s['name']}: {ex}")
        # Link to the name the state posts its newest samples under.
        if found:
            newest = max(found, key=lambda f: f[1])[0]
            if newest != s['lookup_name']:
                s['lookup_name'] = newest
                s['source_url'] = f"{DOH_PAGE}?{urllib.parse.urlencode({'County': cname, 'SPLocation': newest, 'SPLat': s['latitude'], 'SPLong': s['longitude']})}"
    return {'fetched_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'sites': sites,
            'samples': sorted(samples.values(), key=lambda r: (r['site_id'], r['date'])), 'errors': errors}


# --- conditions --------------------------------------------------------------------------------------------------------

def parse_srf(text, zone, flag_label):
    flags = {}
    for m in re.finditer(r'^([A-Z][A-Za-z ]+?)\.{3,}\s*(DOUBLE RED|RED|YELLOW|GREEN|PURPLE)[^\n]*$', text, re.M):
        flags[m.group(1).strip()] = m.group(2).title()
    outlook = re.search(r'\.THE SURF ZONE FORECAST GENERAL OUTLOOK\.\.\.\s*(.*?)(?:\n\s*\n[A-Z]{2}Z\d{3}|Based on communication)', text, re.S)
    sec = re.search(rf'^{zone}-.*?(?=^\$\$)', text, re.S | re.M)
    periods = []
    if sec:
        body = sec.group(0)
        for m in re.finditer(r'^\.([A-Z ]+?)\.\.\.(.*?)(?=^\.[A-Z ]+?\.\.\.|^&&|\Z)', body, re.S | re.M):
            name, block = m.group(1).strip().title(), m.group(2)
            f = {k.strip(): v.strip().rstrip('.') for k, v in re.findall(r'^([A-Z][A-Za-z *]+?)\.{3,}(.+)$', block, re.M)}
            g = lambda *ks: next((f[k] for k in f for want in ks if k.replace('*', '').strip().lower() == want), None)
            short = re.sub(r'\s+', ' ', block).strip() if not f else None
            risk = g('rip current risk')
            if not risk and short:
                mm = re.search(r'(Low|Moderate|High) rip current risk', short, re.I)
                risk = mm.group(1).title() if mm else None
            surf = g('surf height')
            if not surf and short:
                mm = re.search(r'Surf height ([^.]+)', short)
                surf = mm.group(1) if mm else None
            periods.append({'period': name, 'rip_current_risk': risk, 'surf_height': surf, 'uv_index': g('uv index'),
                            'water_temperature': g('water temperature'), 'weather': g('weather'), 'high_temperature': g('high temperature'),
                            'winds': g('winds'), 'sunrise': g('sunrise'), 'sunset': g('sunset'), 'summary': short})
    return {'flag': flags.get(flag_label), 'flags_all': flags, 'outlook': re.sub(r'\s+', ' ', outlook.group(1)).strip() if outlook else None, 'periods': periods}


def fetch_conditions(county, prev):
    c = COUNTIES[county]
    lst = json.loads(get(f"https://api.weather.gov/products/types/SRF/locations/{c['nws_office']}"))['@graph']
    latest = max(lst, key=lambda p: p['issuanceTime'])
    prod = json.loads(get(latest['@id']))
    p = parse_srf(prod['productText'], c['nws_zone'], c['flag_label'])
    al = json.loads(get(f"https://api.weather.gov/alerts/active?zone={c['nws_zone']}", accept='application/geo+json'))
    alerts = [{'event': x['properties']['event'], 'headline': x['properties'].get('headline'), 'starts': x['properties'].get('onset') or x['properties'].get('effective'),
               'ends': x['properties'].get('ends') or x['properties'].get('expires'), 'url': x['properties'].get('@id') or x.get('id')}
              for x in al.get('features', []) if any(w in x['properties']['event'] for w in ('Rip', 'Beach', 'Surf', 'Coastal', 'Tropical', 'Hurricane', 'Marine'))]
    issued = prod['issuanceTime']
    hist = {h['date']: h for h in (prev or {}).get('flag_history', [])}
    local_day = (dt.datetime.fromisoformat(issued) - dt.timedelta(hours=5)).date().isoformat()
    if p['flag']:
        old = hist.get(local_day)
        if not old or old['issued'] <= issued:
            hist[local_day] = {'date': local_day, 'flag': p['flag'], 'issued': issued, 'source_url': latest['@id']}
    return {'fetched_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'issued': issued, 'product_url': latest['@id'],
            'zone': c['nws_zone'], 'office': c['nws_office'], 'flag_label': c['flag_label'], 'flag': p['flag'], 'outlook': p['outlook'], 'periods': p['periods'], 'alerts': alerts,
            'flag_history': sorted(hist.values(), key=lambda h: h['date'])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--county', default='bay')
    ap.add_argument('--only', default='places,water,conditions')
    a = ap.parse_args()
    d = os.path.join(HERE, a.county)
    os.makedirs(d, exist_ok=True)
    load = lambda n: json.load(open(os.path.join(d, n))) if os.path.exists(os.path.join(d, n)) else None
    jobs = {'places': ('places.json', lambda prev: fetch_places(a.county)),
            'water': ('water_quality.json', lambda prev: fetch_water(a.county, prev)),
            'conditions': ('conditions.json', lambda prev: fetch_conditions(a.county, prev))}
    bad = 0
    for k in a.only.split(','):
        fn, job = jobs[k]
        prev = load(fn)
        try:
            data = job(prev)
        except Exception as ex:
            print(f'{k}: failed, keeping what is on file: {ex}', file=sys.stderr)
            bad += 1
            continue
        json.dump(data, open(os.path.join(d, fn), 'w'), indent=1, ensure_ascii=False)
        open(os.path.join(d, fn), 'a').write('\n')
        n = {kk: len(v) for kk, v in data.items() if isinstance(v, list)}
        print(f'{k}: {n}' + (f" ({len(data.get('errors') or [])} errors)" if data.get('errors') else ''))
    sys.exit(1 if bad == len(a.only.split(',')) else 0)


if __name__ == '__main__':
    main()
