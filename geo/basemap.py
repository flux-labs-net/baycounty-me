"""Build simplified basemap geometry (lng/lat) for the Bay County CRA dashboard."""
import json
from shapely.geometry import shape, box, mapping
from shapely.ops import unary_union

BBOX = box(-86.05, 29.85, -85.30, 30.62)
land = json.load(open('land.json'))
land_g = unary_union([shape(f['geometry']).intersection(BBOX)
                      for f in land['features'] if shape(f['geometry']).intersects(BBOX)])
bay = shape(json.load(open('bay.json'))['geometry'])

def simp(g, tol, minarea=1e-6):
    g = g.simplify(tol, preserve_topology=True)
    def ring(r):
        return [[round(x, 4), round(y, 4)] for x, y in r.coords]
    polys = [g] if g.geom_type == 'Polygon' else [p for p in getattr(g, 'geoms', []) if p.geom_type == 'Polygon']
    return [[ring(p.exterior)] + [ring(i) for i in p.interiors] for p in polys if p.area > minarea]

out = {
    'land': simp(land_g, 0.002),
    'county': simp(bay.intersection(land_g.buffer(0.01)), 0.002),
    'cities': {},
}
names = {'panama-city': 'Panama City', 'lynn-haven': 'Lynn Haven', 'panama-city-beach': 'Panama City Beach',
         'callaway': 'Callaway', 'springfield': 'Springfield', 'mexico-beach': 'Mexico Beach', 'parker': 'Parker'}
for slug, name in names.items():
    fc = json.load(open(f'{slug}.json'))
    g = unary_union([shape(f['geometry']) for f in fc['features']])
    out['cities'][name] = simp(g, 0.003, 4e-5)
json.dump(out, open('basemap.json', 'w'), separators=(',', ':'))
import os
print(os.path.getsize('basemap.json'))

# Official CRA district boundaries (Bay County GIS, Admin_A12/MapServer/27)
gis = json.load(open('cra_gis.json'))
out['cra_districts'] = []
for f in gis['features']:
    p = f['properties']
    g = shape(f['geometry'])
    out['cra_districts'].append({'name': p['CRA'].replace('St Andrews', 'St. Andrews'), 'est': p['EST_YEAR'],
                                 'acres': round(p['Shape.STArea()'] / 43560), 'geom': simp(g, 0.0003)})
json.dump(out, open('basemap.json', 'w'), separators=(',', ':'))
print('with cra', os.path.getsize('basemap.json'))
