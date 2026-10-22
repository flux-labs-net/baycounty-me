"""Snapshot Bay County's infrastructure sales tax project layer (SurtaxProjects MapServer)."""
import json, os, urllib.request, urllib.parse, datetime, re
HERE = os.path.dirname(os.path.abspath(__file__))
B = 'https://gis.baycountyfl.gov/arcgis/rest/services/SurtaxProjects/MapServer'
def q(i):
    u = f'{B}/{i}/query?' + urllib.parse.urlencode({'where': '1=1', 'outFields': 'NAME,FY,CITY,TYPE,PIC_URL,WEBSITE,SHORT_DESC,DESC_1,DESC_2,DESC_3,PctComplete,last_edited_date' + (',EstCost' if i == 0 else ''),
        'outSR': 4326, 'f': 'json', 'returnGeometry': 'true', 'maxAllowableOffset': 0.0002, 'geometryPrecision': 5})
    with urllib.request.urlopen(u, timeout=60) as r: return json.load(r)['features']
clean = lambda s: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s or '')).strip()
out = []
for i, kind in ((0, 'point'), (1, 'line')):
    for f in q(i):
        a, g = f['attributes'], f.get('geometry') or {}
        geom = [round(g['x'], 5), round(g['y'], 5)] if kind == 'point' else g.get('paths')
        out.append({'name': a['NAME'], 'fy': a['FY'], 'gov': a['CITY'], 'type': a['TYPE'], 'pct': a.get('PctComplete'), 'cost': a.get('EstCost'),
                    'desc': ' '.join(clean(a.get(k)) for k in ('DESC_1', 'DESC_2', 'DESC_3') if a.get(k)), 'doc': a.get('WEBSITE'), 'pic': a.get('PIC_URL'),
                    'edited': datetime.datetime.fromtimestamp((a.get('last_edited_date') or 0) / 1000, datetime.UTC).strftime('%Y-%m-%d') if a.get('last_edited_date') else None,
                    'kind': kind, 'geom': geom})
dest = os.path.join(HERE, 'gis_projects.json')
fetched = datetime.date.today().isoformat()
try:  # keep the old date when nothing changed, so the weekly refresh doesn't commit a date-only change
    prev = json.load(open(dest))
    if prev.get('projects') == json.loads(json.dumps(out)):
        fetched = prev.get('fetched') or fetched
except (FileNotFoundError, ValueError):
    pass
if not out:
    raise SystemExit('No projects returned; keeping the existing file.')
json.dump({'source_url': B, 'fetched': fetched, 'projects': out}, open(dest, 'w'), separators=(',', ':'))
from collections import Counter
print(len(out), Counter(p['gov'] for p in out), Counter(p['fy'] for p in out), Counter(p['type'] for p in out))
