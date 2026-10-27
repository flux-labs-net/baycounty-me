#!/usr/bin/env python3
"""Where and when to vote in Bay County -> data/elections/voting.json.

    python3 data/elections/scripts/fetch_voting.py

Three parts, all from the Supervisor of Elections (SOE):

  calendar        key dates. The SOE's "Dates to Remember" page (bayvotesfl.gov/elections/events/) is read on every run
                  for canvassing board meetings and early voting; registration deadlines, vote-by-mail deadlines and
                  election days are kept by hand in voting_dates.json (from the SOE's 2026 Voter's Guide), because the
                  events page only lists what is coming up next.
  polling_places  the normal Election Day polling place for every precinct, from the SOE's precinct directory
                  (voterfocus.com PrecinctFinder/precinctDirectory, linked from the SOE's "Where to vote" page).
  early_voting    the early voting sites and hours for the next election, kept by hand in voting_dates.json from the SOE's
                  early voting page and its live locations map (vls.vrswebapps.com, the map on bayvotesfl.gov/voters/vote-early/).

Every site gets map coordinates from Bay County's address points (county GIS), or the U.S. Census Bureau geocoder when
the county has no match (cached in the output, so an address is looked up once). A source that fails keeps what the file already had and notes the error.
"""
import datetime as dt, html, json, os, re, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'voting.json')
HAND = os.path.join(HERE, '..', 'voting_dates.json')
SOE = 'https://www.bayvotesfl.gov'
EVENTS = SOE + '/elections/events/'
DIRECTORY = 'https://www.voterfocus.com/PrecinctFinder/precinctDirectory?county=FL-BAY'
FINDER = 'https://www.voterfocus.com/PrecinctFinder/addressSearch?county=BAY'
GEOCODER = 'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress'
ADDRESS_POINTS = 'https://gis.baycountyfl.gov/arcgis/rest/services/Admin_A12/MapServer/3/query'  # county address points
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36 BayCounty.me voting info reader'


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode('utf-8', 'replace')


def txt(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def events():
    """Upcoming SOE events: [{starts, all_day, title, url}]."""
    t = get(EVENTS)
    out = []
    for url, when, summ in re.findall(r'<a href="([^"]+/events/[^"]+)".*?class="event-datetime">([^<]+)</span>.*?class="event-summary[^"]*">(.*?)</p>', t, re.S):
        when = txt(when)
        try:
            d = dt.datetime.strptime(when.upper(), '%b %d, %Y %I:%M%p'); all_day = False
        except ValueError:
            d = dt.datetime.strptime(when, '%b %d, %Y'); all_day = True
        out.append({'starts': d.isoformat(timespec='minutes') if not all_day else d.date().isoformat(), 'all_day': all_day,
                    'title': txt(summ), 'url': url, 'source_url': EVENTS})
    return out


def precincts():
    t = get(DIRECTORY)
    out = []
    for sec in re.findall(r'<section class="PrecinctSummary.*?</section>', t, re.S):
        p = re.search(r'class="Title">\s*Precinct\s+([^<]+?)\s*<', sec)
        name = re.search(r'<div class="Name">(.*?)</div>', sec, re.S)
        addr = re.search(r'<div class="Address">\s*<a[^>]*>(.*?)</a>', sec, re.S)
        if not (p and name and addr):
            continue
        lines = [txt(x) for x in re.split(r'<br\s*/?>', addr.group(1)) if txt(x)]
        street = lines[0] if lines else None
        m = re.match(r'(.+?),\s*([A-Z]{2})\s+(\d{5})', lines[-1]) if len(lines) > 1 else None
        out.append({'precinct': p.group(1).strip(), 'name': txt(name.group(1)), 'address': street,
                    'city': m.group(1) if m else None, 'zip': m.group(3) if m else None,
                    'url': f"https://www.voterfocus.com/PrecinctFinder/precinctSummary?county=FL-BAY&precinct={urllib.parse.quote(p.group(1).strip().rjust(3))}",
                    'source_url': DIRECTORY})
    return out


def county_point(street):
    """[lat, lon] of a Bay County address point: '4201 W 22nd St' -> ADDRESS LIKE '4201 W 22ND ST%', then by street name."""
    m = re.match(r'(\d+)\s+(.+)', (street or '').upper().replace('HIGHWAY', 'HWY'))
    if not m:
        return None
    longest = max(m.group(2).split(), key=len)
    for where in (f"ADDRESS LIKE '{m.group(1)} {m.group(2)}%'", f"ADDRESS LIKE '{m.group(1)} %{longest}%'"):
        u = ADDRESS_POINTS + '?' + urllib.parse.urlencode({'where': where.replace("''", "'"), 'outFields': 'ADDRESS', 'returnGeometry': 'true',
                                                           'outSR': 4326, 'resultRecordCount': 1, 'f': 'json'})
        f = json.loads(get(u)).get('features') or []
        if f:
            return [round(f[0]['geometry']['y'], 6), round(f[0]['geometry']['x'], 6)]
    return None


def geocode(cache, street, city, zip_):
    key = f'{street}, {city}, FL {zip_ or ""}'.strip()
    if cache.get(key):
        return cache[key]
    try:
        pt = county_point(street)
        if not pt:
            u = GEOCODER + '?' + urllib.parse.urlencode({'address': key, 'benchmark': 'Public_AR_Current', 'format': 'json'})
            m = json.loads(get(u))['result']['addressMatches']
            pt = [round(m[0]['coordinates']['y'], 6), round(m[0]['coordinates']['x'], 6)] if m else None
        cache[key] = pt
        time.sleep(0.2)
    except Exception:
        return None  # not cached: try again next run
    return cache[key]


def main():
    old = json.load(open(OUT)) if os.path.exists(OUT) else {}
    hand = json.load(open(HAND))
    cache = old.get('geocode_cache') or {}
    errors = []
    try:
        ev = events()
    except Exception as ex:
        ev = old.get('soe_events') or []
        errors.append({'source': EVENTS, 'error': str(ex)[:200]})
    try:
        pp = precincts()
        if len(pp) < 10:
            raise ValueError(f'only {len(pp)} precincts found')
    except Exception as ex:
        pp = old.get('polling_places') or []
        errors.append({'source': DIRECTORY, 'error': str(ex)[:200]})
    for p in pp:
        p['lat_lon'] = geocode(cache, p['address'], p['city'], p['zip'])
    ev_sites = hand.get('early_voting') or {}
    for s in ev_sites.get('sites') or []:
        s['lat_lon'] = geocode(cache, s['address'], s['city'], s.get('zip'))
    json.dump({'as_of': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'errors': errors,
               'finder_url': FINDER, 'directory_url': DIRECTORY, 'events_url': EVENTS,
               'calendar': hand['calendar'], 'soe_events': ev, 'early_voting': ev_sites, 'polling_places': pp,
               'geocode_cache': cache}, open(OUT, 'w'), indent=1)
    print(f'{len(hand["calendar"])} key dates, {len(ev)} SOE events, {len(ev_sites.get("sites") or [])} early voting sites, '
          f'{len(pp)} polling places, {len(errors)} errors')


if __name__ == '__main__':
    sys.exit(main())
