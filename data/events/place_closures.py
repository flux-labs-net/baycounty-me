#!/usr/bin/env python3
"""Map lines for special-event road closures -> data/events/<county>/special/<event>.geo.json.

    python3 data/events/place_closures.py [--county bay] [event-id ...]

Each closure in data/events/<county>/special/<event>.json names a street and the two cross streets it runs between.
This reads that street from the county street centerline layer (the same layer api/_road_map.js uses for road
notices), finds where it meets each cross street, and keeps the shortest run of the street between the two. The line is
written as GeoJSON (WGS84) with properties.placed = 'street-names', so pages can say it was placed from the names.
A closure that can't be placed is left out and reported; the page then lists it without a line.
"""
import argparse, glob, heapq, json, math, os, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = 'Mozilla/5.0 (compatible; BayCounty.me road closure mapper; +https://baycounty.me/about)'
LAYER = {'bay': 'https://gis.baycountyfl.gov/arcgis/rest/services/Admin_A12/MapServer/5/query'}


def street(county, name, town):
    q = urllib.parse.urlencode({'where': f"FULL_NAME = '{name}' AND (LCOMM = '{town.upper()}' OR RCOMM = '{town.upper()}')",
                                'outFields': 'FULL_NAME', 'outSR': 4326, 'f': 'json'})
    req = urllib.request.Request(LAYER[county] + '?' + q, headers={'User-Agent': UA})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    return [[(round(x, 6), round(y, 6)) for x, y in p] for f in d.get('features', []) for p in f['geometry']['paths']]


def dist(a, b):
    return math.hypot((a[0] - b[0]) * math.cos(math.radians(a[1])), a[1] - b[1]) * 111_320


def meet(segs, cross):
    """The end point of a segment of `segs` closest to the cross street, and how far off it is (metres)."""
    pts = [p for s in cross for p in s]
    return min(((min(dist(e, q) for q in pts), e) for s in segs for e in (s[0], s[-1])), default=(None, None))


def run(segs, a, b):
    """Shortest path along the street's segments from end point a to end point b, as a list of points."""
    g = {}
    for s in segs:
        n = sum(dist(s[k], s[k + 1]) for k in range(len(s) - 1))
        g.setdefault(s[0], []).append((s[-1], n, s))
        g.setdefault(s[-1], []).append((s[0], n, s[::-1]))
    keys = list(g)
    for k in keys:  # join ends that are a few metres apart
        for k2 in keys:
            if k != k2 and dist(k, k2) < 3:
                g[k].append((k2, dist(k, k2), [k, k2]))
    q, seen = [(0, a, [a])], set()
    while q:
        c, n, line = heapq.heappop(q)
        if n in seen:
            continue
        seen.add(n)
        if n == b:
            return line
        for m, w, s in g.get(n, []):
            if m not in seen:
                heapq.heappush(q, (c + w, m, line + s[1:]))
    return None


def place(county, ev):
    out = {'id': ev['id'], 'source': 'Bay County street centerlines', 'source_url': LAYER[county].rsplit('/query', 1)[0], 'lines': {}}
    for c in ev['closures']:
        segs = street(county, c['street'], ev['town'])
        da, a = meet(segs, street(county, c['from_street'], ev['town']))
        db, b = meet(segs, street(county, c['to_street'], ev['town']))
        line = run(segs, a, b) if a and b and max(da, db) < 60 else None
        if not line:
            print(f"  {c['id']}: could not place {c['street']} between {c['from_street']} and {c['to_street']}", file=sys.stderr)
            continue
        out['lines'][c['id']] = {'type': 'LineString', 'coordinates': [[round(x, 5), round(y, 5)] for x, y in line],
                                 'properties': {'placed': 'street-names'}}
        print(f"  {c['id']}: {len(line)} points, {round(sum(dist(line[i], line[i + 1]) for i in range(len(line) - 1)))} m")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--county', default='bay')
    ap.add_argument('events', nargs='*')
    a = ap.parse_args()
    for f in sorted(glob.glob(os.path.join(HERE, a.county, 'special', '*.json'))):
        if f.endswith('.geo.json'):
            continue
        ev = json.load(open(f))
        if a.events and ev['id'] not in a.events:
            continue
        print(ev['id'])
        g = place(a.county, ev)
        json.dump(g, open(f[:-5] + '.geo.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
