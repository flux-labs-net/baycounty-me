"""Build the Bay County Hurricane Michael FEMA Public Assistance ledger from OpenFEMA.

Fetches DR-4399 project details and applicant names (no API key needed) and writes
pa_ledger.json with one row per Bay County project.
"""
import json, os, urllib.request, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
API = 'https://www.fema.gov/api/open'

def get(path, flt, top=1000):
    rows, skip = [], 0
    while True:
        q = urllib.parse.urlencode({'$filter': flt, '$top': top, '$skip': skip, '$format': 'json'})
        with urllib.request.urlopen(f'{API}/{path}?{q}', timeout=60) as r:
            d = json.load(r)
        key = [k for k in d if isinstance(d[k], list)][0]
        rows += d[key]
        if len(d[key]) < top: return rows
        skip += top

proj = get('v2/PublicAssistanceFundedProjectsDetails', "disasterNumber eq 4399 and county eq 'Bay County'")
apps = {a['applicantId']: a['applicantName'] for a in get('v1/PublicAssistanceApplicants', 'disasterNumber eq 4399')}
CAT = {'A': 'Debris removal', 'B': 'Emergency protective measures', 'C': 'Roads and bridges', 'D': 'Water control',
       'E': 'Buildings and equipment', 'F': 'Utilities', 'G': 'Parks and other', 'Z': 'Management costs'}
rows = []
for p in proj:
    rows.append({'a': apps.get(p.get('applicantId'), p.get('applicantId')), 'pw': p.get('pwNumber'), 't': (p.get('applicationTitle') or p.get('projectTitle') or '').strip(),
                 'c': p.get('damageCategoryCode'), 'f': round(p.get('federalShareObligated') or 0, 2), 'e': round(p.get('projectAmount') or 0, 2),
                 'd1': (p.get('firstObligationDate') or '')[:10], 'd2': (p.get('lastObligationDate') or '')[:10],
                 'st': p.get('projectProcessStep') or '', 'sz': p.get('projectSize') or ''})
rows.sort(key=lambda r: -r['f'])
out = {'source': 'OpenFEMA PublicAssistanceFundedProjectsDetails (v2) and PublicAssistanceApplicants (v1), DR-4399-FL',
       'source_url': f"{API}/v2/PublicAssistanceFundedProjectsDetails?$filter=disasterNumber eq 4399 and county eq 'Bay County'",
       'categories': CAT, 'rows': rows}
json.dump(out, open(os.path.join(HERE, 'pa_ledger.json'), 'w'), separators=(',', ':'))
print(len(rows), round(sum(r['f'] for r in rows), 2), len(set(r['a'] for r in rows)))
