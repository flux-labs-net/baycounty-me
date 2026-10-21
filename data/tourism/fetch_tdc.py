"""Snapshot Bay County Tourist Development Council zone boundaries (Admin_A12/MapServer/84)."""
import json, os, urllib.request, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
u = 'https://gis.baycountyfl.gov/arcgis/rest/services/Admin_A12/MapServer/84/query?' + urllib.parse.urlencode(
    {'where': '1=1', 'outFields': 'ID,Type', 'outSR': 4326, 'returnGeometry': 'true', 'maxAllowableOffset': 0.0004, 'geometryPrecision': 4, 'f': 'json'})
with urllib.request.urlopen(u, timeout=60) as r:
    fs = json.load(r)['features']
zones = {}
for f in fs:
    zones.setdefault(f['attributes']['ID'], []).append(f['geometry']['rings'])
json.dump({'source_url': u.split('?')[0], 'zones': zones}, open(os.path.join(HERE, 'tdc_zones.json'), 'w'), separators=(',', ':'))
print({k: sum(len(r) for p in v for r in p) for k, v in zones.items()})
