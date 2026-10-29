import json, math, sys
j = json.load(open('geo/basemap.json'))
LON0, LON1, LAT0, LAT1 = -86.06, -85.30, 29.84, 30.60
C = math.cos(math.radians(30.2))
def proj(lon, lat, k, ox, oy): return (ox + (lon - LON0) * C * k, oy + (LAT1 - lat) * k)
def path(polys, k, ox, oy):
    d = []
    for poly in polys:
        for ring in poly:
            pts = [proj(x, y, k, ox, oy) for x, y in ring]
            d.append('M' + 'L'.join(f'{x:.1f},{y:.1f}' for x, y in pts) + 'Z')
    return ''.join(d)
def svg(k, ox, oy):
    land = path(j['land'], k, ox, oy)
    county = path(j['county'], k, ox, oy)
    cities = ''.join(f'<path d="{path(v, k, ox, oy)}" fill="#DCE5F5"/>' for v in j['cities'].values())
    return land, county, cities
k = float(sys.argv[1]); ox = float(sys.argv[2]); oy = float(sys.argv[3])
land, county, cities = svg(k, ox, oy)
pts = {n: proj(lon, lat, k, ox, oy) for n, (lon, lat) in {
    'beach': (-85.80, 30.175), 'food': (-85.648, 30.245), 'meeting': (-85.66, 30.158),
    'trash': (-85.62, 30.215), 'tax': (-85.655, 30.27), 'events': (-85.42, 29.95)}.items()}
json.dump({'land': land, 'county': county, 'cities': cities, 'pts': pts}, sys.stdout)
