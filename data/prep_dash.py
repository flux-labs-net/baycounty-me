"""Turn merged.json + basemap.json into dash_data.json for the dashboard page."""
import json, re, random
from shapely.geometry import shape

m = json.load(open('merged.json'))
base = json.load(open('../geo/basemap.json'))
gis = json.load(open('../geo/cra_gis.json'))

CRA_IDS = {
    'Panama City CRA': 'pc', 'Panama City Beach CRA': 'pcb', 'Lynn Haven CRA': 'lh',
    'Callaway CRA': 'cw', 'Springfield CRA': 'sf', 'Parker CRA': 'pk',
}
GIS_CRA = {
    'Downtown CRA / DIB': ('pc', 'Downtown'), 'Downtown Extension CRA': ('pc', 'Downtown'),
    'Downtown North CRA': ('pc', 'Downtown North'), 'Downtown N Extension CRA': ('pc', 'Downtown North'),
    'St. Andrews CRA': ('pc', 'St. Andrews'), 'St Andrews CRA - West Expansion Area': ('pc', 'St. Andrews'),
    'St Andrews CRA - East Expansion Area': ('pc', 'St. Andrews'), 'Millville CRA': ('pc', 'Millville'),
    'Front Beach Road CRA': ('pcb', 'Front Beach Road'), 'Pier Park CRA': ('pcb', 'Pier Park'),
    'Lynn Haven CRA': ('lh', 'Lynn Haven'), 'Callaway CRA': ('cw', 'Callaway'),
    'Springfield CRA': ('sf', 'Springfield'), 'Parker CRA': ('pk', 'Parker'),
}
REC_DISTRICT = {  # record district string -> dashboard district key
    'Downtown': 'Downtown', 'Downtown North (Glenwood)': 'Downtown North', 'St. Andrews': 'St. Andrews',
    'Millville': 'Millville', 'All': 'Downtown', 'Front Beach Road CRA': 'Front Beach Road',
    'Pier Park CRA': 'Pier Park', 'Lynn Haven Community Redevelopment Area': 'Lynn Haven',
    'Callaway Community Redevelopment Area': 'Callaway', 'Springfield Community Redevelopment Area': 'Springfield',
    'Parker Community Redevelopment Area': 'Parker',
}

# district polygons + centroids (official county GIS)
districts, cent_src = [], {}
bmap = {d['name']: d for d in base['cra_districts']}
for f in gis['features']:
    raw = f['properties']['CRA']
    cra, key = GIS_CRA[raw]
    g = shape(f['geometry'])
    nm = raw.replace('St Andrews', 'St. Andrews')
    districts.append({'cra': cra, 'key': key, 'name': nm, 'est': f['properties']['EST_YEAR'],
                      'acres': bmap[nm]['acres'], 'geom': bmap[nm]['geom']})
    cent_src.setdefault(key, []).append(g)
centroids = {}
for k, gs in cent_src.items():
    big = max(gs, key=lambda g: g.area)
    p = big.representative_point()
    centroids[k] = [round(p.y, 5), round(p.x, 5)]

random.seed(7)
pays = []
for i, p in enumerate(m['payments']):
    dkey = REC_DISTRICT.get(p['district'], None)
    lat, lng, prec = p['lat'], p['lng'], p['coord_precision'] or 'approximate'
    placed = 'site'
    if lat is None or lng is None:
        lat, lng = centroids[dkey]
        lat += random.uniform(-0.003, 0.003); lng += random.uniform(-0.003, 0.003)
        placed = 'district'
    elif re.search(r'aggregate|district cent|not a specific site|program total', (p.get('notes') or '') + p['payee'], re.I):
        placed = 'district'
    pays.append({
        'id': i, 'cra': CRA_IDS[p['cra']], 'district': dkey, 'payee': p['payee'], 'amount': p['amount'],
        'when': p['date_or_fy'], 'purpose': p['purpose'], 'cat': p['category'],
        'loc': p['location_name'] or '', 'addr': p['address'] or '', 'lat': round(lat, 5), 'lng': round(lng, 5),
        'prec': prec, 'placed': placed, 'src': p['source_title'] or '', 'url': p['source_url'] or '',
        'conf': p['confidence'], 'notes': p['notes'] or '', 'status': p['status'], 'count': p['count'],
        'overlap': p['overlap'],
    })

def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def fy(s):
    mm = re.search(r'(\d{4})', str(s)); return int(mm.group(1)) if mm else None

# tax increment series: prefer district == all / whole-CRA rows
tif = {}
for b in m['budgets']:
    c = CRA_IDS[b['cra']]; y = fy(b['fy']); v = num(b['tif_revenue'])
    if y is None or v is None: continue
    dist = (b.get('district') or 'all').lower()
    if c == 'pcb' and 'pier' in dist:
        continue  # Pier Park increment is passed through to the CDD; chart Front Beach Rd
    tif.setdefault(c, {})
    if c == 'pc':  # Panama City rows may be by district; sum per year
        if dist in ('all', 'all districts', 'combined', 'total'):
            tif[c][y] = ('all', v)
        else:
            prev = tif[c].get(y)
            if not prev or prev[0] != 'all':
                tif[c][y] = ('sum', (prev[1] if prev else 0) + v)
    else:
        if y not in tif[c] or dist in ('all', 'front beach road cra'):
            tif[c][y] = ('all', v)
tif_out = {c: sorted([[y, round(v[1])] for y, v in d.items() if y <= 2025]) for c, d in tif.items()}

cras = []
for c in m['cras']:
    cid = CRA_IDS[c['cra']]
    cras.append({'id': cid, 'name': c['cra'], 'city': c['city'], 'created': c['created'], 'overview': c['overview']})

out = {
    'cras': cras, 'districts': districts, 'payments': pays, 'tif': tif_out,
    'controversies': [{'cra': CRA_IDS[x['cra']], 'text': x['summary'], 'url': x.get('source_url', '')} for x in m['controversies']],
    'gaps': [{'cra': CRA_IDS[g['cra']], 'text': g['text']} for g in m['gaps']],
    'land': base['land'], 'county': base['county'], 'cities': base['cities'],
}
json.dump(out, open('dash_data.json', 'w'), separators=(',', ':'))
print({c: v[-3:] for c, v in tif_out.items()})
print(len(json.dumps(out)))
