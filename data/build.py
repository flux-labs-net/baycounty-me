"""Merge CRA research files into one dataset for the dashboard.

Each payment gets:
  status : Spent | Committed | Budgeted | Proposed | Incoming | Not CRA-funded
  count  : True if it belongs in totals (False for roll-ups / components already in a project total)
  overlap: short reason when count is False
"""
import json, re, os

FILES = ['panama_city.json', 'lynn_haven.json', 'pcb.json']
cras = []
for f in FILES:
    if os.path.exists(f):
        cras.append(json.load(open(f)))
cras += json.load(open('others.json'))

# (cra, index) -> overrides
OV = {
  # Panama City
  ('Panama City CRA', 0): dict(status='Committed', count=False, overlap='Total of the five rebate awards listed separately'),
  ('Panama City CRA', 1): dict(status='Committed'), ('Panama City CRA', 2): dict(status='Committed'),
  ('Panama City CRA', 3): dict(status='Committed'), ('Panama City CRA', 4): dict(status='Committed'),
  ('Panama City CRA', 5): dict(status='Committed'),
  ('Panama City CRA', 6): dict(status='Budgeted'),
  ('Panama City CRA', 7): dict(status='Spent'),
  ('Panama City CRA', 8): dict(status='Budgeted'),
  ('Panama City CRA', 11): dict(status='Proposed'),
  ('Panama City CRA', 12): dict(status='Incoming', count=False, overlap='Land sale offer to the CRA (money in, not spending)'),
  ('Panama City CRA', 13): dict(status='Budgeted'),
  ('Panama City CRA', 35): dict(status='Committed'),
  ('Panama City CRA', 64): dict(status='Budgeted'), ('Panama City CRA', 65): dict(status='Budgeted'),
  ('Panama City CRA', 67): dict(status='Budgeted'), ('Panama City CRA', 68): dict(status='Budgeted'),
  ('Panama City CRA', 69): dict(status='Budgeted'), ('Panama City CRA', 70): dict(status='Budgeted'),
  ('Panama City CRA', 71): dict(status='Committed'),
  ('Panama City CRA', 72): dict(status='Proposed'),
  # Panama City Beach: keep project totals, drop components they already include
  ('Panama City Beach CRA', 0): dict(count=False, overlap='Included in the $15.4M South Thomas Dr project total'),
  ('Panama City Beach CRA', 4): dict(count=False, overlap='Included in the $16.0M Segment 2 project total'),
  ('Panama City Beach CRA', 5): dict(count=False, overlap='Included in the $16.0M Segment 2 project total'),
  ('Panama City Beach CRA', 6): dict(count=False, overlap='Included in the $16.0M Segment 2 project total'),
  ('Panama City Beach CRA', 9): dict(count=False, overlap='Part of the Segment 3 project cost'),
  ('Panama City Beach CRA', 10): dict(count=False, overlap='Part of the Segment 3 project cost'),
  ('Panama City Beach CRA', 11): dict(count=False, overlap='Part of the Segment 3 project cost'),
  ('Panama City Beach CRA', 12): dict(count=False, overlap='Included in the Segment 4.1 project spending'),
  ('Panama City Beach CRA', 13): dict(count=False, overlap='Included in the Segment 4.1 project spending'),
  ('Panama City Beach CRA', 14): dict(count=False, overlap='Included in the Segment 4.1 project spending'),
  ('Panama City Beach CRA', 15): dict(count=False, overlap='Included in the Segment 4.2 project spending'),
  ('Panama City Beach CRA', 16): dict(count=False, overlap='Included in the Segment 4.2 project spending'),
  ('Panama City Beach CRA', 20): dict(count=False, overlap='Included in the Segment 4.2 project spending'),
  ('Panama City Beach CRA', 18): dict(count=False, overlap='Included in the Segment 4.3 project spending'),
  ('Panama City Beach CRA', 19): dict(count=False, overlap='Included in the Segment 4.3 project spending'),
  ('Panama City Beach CRA', 22): dict(status='Not CRA-funded', count=False, overlap='Reported as grant-funded, not CRA money'),
  ('Panama City Beach CRA', 26): dict(count=False, overlap='Resolution does not say CRA; may be city utility funds'),
  ('Panama City Beach CRA', 31): dict(status='Budgeted'), ('Panama City Beach CRA', 32): dict(status='Budgeted'),
  ('Panama City Beach CRA', 38): dict(status='Budgeted'), ('Panama City Beach CRA', 39): dict(status='Budgeted'),
  ('Panama City Beach CRA', 43): dict(status='Budgeted'),
  # Callaway
  ('Callaway CRA', 0): dict(count=False, overlap='Included in FY2025 total capital outlay'),
  # Springfield: everything but the FY2025 actuals is a budget line
  ('Springfield CRA', 8): dict(status='Spent'),
  ('Parker CRA', 1): dict(status='Budgeted'),
}
LH_OV = {
  ('Lynn Haven CRA', 0): dict(status='Committed', count=False, overlap='Mostly FDOT grant money; CRA share not stated'),
  ('Lynn Haven CRA', 10): dict(count=False, overlap='May be the same storefront grant reported for FY2021'),
  ('Lynn Haven CRA', 19): dict(status='Budgeted'),
  ('Lynn Haven CRA', 3): dict(status='Spent'), ('Lynn Haven CRA', 5): dict(status='Spent'),
  ('Lynn Haven CRA', 29): dict(status='Not CRA-funded', count=False, overlap='Mostly state and federal grant money'),
}
OV[('Panama City CRA', 14)] = dict(status='Spent')


# Corrections from independent source check (verify_results.json)
MIX = 'Mixed funding: the source lists CRA money alongside state/federal grants, so the CRA share is smaller than this figure. '
PATCH = {
  ('Panama City Beach CRA', 8): dict(payee='Contractor not named in this source (other city records name GAC Contractors, later CWR Contracting)', notes_pre='Funded by the CRA, FDOT and a property-owner share. '),
  ('Panama City Beach CRA', 33): dict(notes_pre=MIX), ('Panama City Beach CRA', 34): dict(notes_pre=MIX), ('Panama City Beach CRA', 35): dict(notes_pre=MIX),
  ('Panama City Beach CRA', 36): dict(payee='Various (contractor not named in source)', purpose='Hills Road Segment I improvements (project total)'),
  ('Panama City Beach CRA', 41): dict(status='Not CRA-funded', count=False, overlap='Business tax receipts the City remits to the Pier Park CDD; City money, not CRA spending'),
  ('Panama City Beach CRA', 42): dict(status='Not CRA-funded', count=False, overlap='Business tax receipts the City remits to the Pier Park CDD; City money, not CRA spending'),
  ('Panama City Beach CRA', 44): dict(status='Not CRA-funded', count=False, overlap='State DEO grant amount obtained for streetlights, not CRA spending', payee='Contractor not named in source', purpose='Replacement of streetlights on Segment 1 and South Thomas Dr, paid with a state DEO grant'),
  ('Panama City Beach CRA', 38): dict(payee='Bondholders (Series 2015 and 2020 bonds)', notes_pre='Amended budget cut 2024-bond interest to $0. '),
  ('Panama City Beach CRA', 15): dict(notes_pre='Construction inspection is listed as excluded from this task order. '),
  ('Panama City Beach CRA', 0): dict(date_or_fy='Sep 2009 - Nov 2011'),
  ('Panama City CRA', 6): dict(payee='Inland Construction & Engineering (bid awarded May 28, 2024)', purpose='Millville Waterfront Park renovation, Phase II: playground, amphitheater, trees, restrooms (total project cost, paid from FY2024-26 Millville district budgets)'),
  ('Panama City CRA', 28): dict(status='Incoming', count=False, overlap='Payment to the City in a land swap, not CRA spending'),
  ('Panama City CRA', 50): dict(notes_pre=''),
  ('Panama City CRA', 7): dict(payee='City of Panama City (2008 park purchase)', purpose='Acquisition of the 4.2-acre Watson Bayou/Millville waterfront park site, bought by the City with a bank loan and repaid by the Millville district', notes_pre='Bought by the City in Sept 2008 for about $2.5M with a bank loan; final loan payment FY2022. '),
  ('Panama City CRA', 71): dict(date_or_fy='Approved March 2026; runs FY2027 onward', payee='City of Panama City (paid by the CRA; much of the work goes to outside contractors)'),
  # World Changers: the FY2017 and FY2018 annual reports each describe their own year of the program (41 homes in FY2017;
  # a new MOU with First Baptist covering 30+ sites in FY2018, "the second year"), $80,000 each ($70K Downtown North, $10K Millville).
  ('Panama City CRA', 30): dict(notes_post=' Checked against both annual reports: FY2017 and FY2018 were separate program years, each with $80,000 ($70,000 Downtown North, $10,000 Millville), so both are counted. The report gives the amount budgeted for the program.'),
  ('Panama City CRA', 31): dict(notes_post='Checked against both annual reports: a separate MOU for the program\'s second year (30+ sites), not a repeat of FY2017. The report gives the amount allocated for the program.'),
  # payee named from the city's own award for the same project (same government); source in notes
  ('Panama City CRA', 10): dict(payee='Mainline Construction (Bid PC-23-020)', notes_post=' Payee from the Panama City Commission award of Bid PC-23-020, St. Andrews parking lots, to Mainline Construction on 2023-07-25 ($927,051.13): https://panamacity.gov/AgendaCenter/ViewFile/Agenda/_07252023-627?html=true'),
  ('Panama City CRA', 60): dict(payee='Piney Grove Nursery and Landscaping, Inc. (PC24-038)', notes_post='Payee from the Panama City Commission approval of PC24-038, US 98/Beck Ave FDOT beautification (CRA), to Piney Grove Nursery and Landscaping on 2024-10-22 ($520,300, the same project total): https://panamacity.gov/AgendaCenter/ViewFile/Agenda/_10222024-714?html=true'),
  ('Panama City CRA', 70): dict(payee='Art Construction of Northwest Florida LLC (Bid PC26-023)', notes_post=' Payee from the Panama City Commission award of Bid PC26-023, Truesdell clubhouse exterior renovations, on 2026-08-25 ($498,797.47 with contingency, more than this CRA budget line, so other money may also pay for it): https://panamacity.gov/AgendaCenter/ViewFile/Agenda/_08252026-880?html=true'),
}

# Pins that fell outside every county CRA polygon (geo/cra_gis.json, which already includes the 2025 St. Andrews
# expansion areas). Where the record gives a street address, the point is the U.S. Census Bureau geocoder's match for
# that address (geocoding.geo.census.gov, Public_AR_Current); records with no address go to the district center.
CENSUS = 'U.S. Census Bureau geocoder match for the address in the record (geocoding.geo.census.gov).'
COORD = {
  ('Panama City CRA', 10): (30.16738, -85.70165, 'address', CENSUS), ('Panama City CRA', 59): (30.16738, -85.70165, 'address', CENSUS),
  ('Panama City CRA', 50): (30.16915, -85.70148, 'address', CENSUS), ('Panama City CRA', 51): (30.16915, -85.70148, 'address', CENSUS),
  ('Panama City CRA', 39): (30.16934, -85.70161, 'address', CENSUS),
  ('Panama City CRA', 8): (30.16923, -85.7027, 'street', 'Census geocoder match for 1101 Bayview Ave, on the documented block of Bayview Ave.'),
  ('Panama City CRA', 54): (30.16923, -85.7027, 'street', 'Census geocoder match for 1101 Bayview Ave, on the documented block (10th-12th St).'),
  ('Panama City CRA', 56): (30.16923, -85.7027, 'street', 'Census geocoder match for 1101 Bayview Ave, on the documented block of Bayview Ave.'),
  ('Panama City CRA', 41): (30.1689, -85.70149, 'approximate', 'On Beck Ave in the St. Andrews district (Census geocoder, 1100 block); the record gives no street number.'),
  ('Panama City CRA', 40): (None, None, 'approximate', 'The record gives no address, so it is pinned at the middle of the St. Andrews district.'),
  ('Panama City CRA', 42): (None, None, 'approximate', 'The record gives no address, so it is pinned at the middle of the St. Andrews district.'),
  ('Panama City CRA', 47): (None, None, 'approximate', 'The record gives no address, so it is pinned at the middle of the St. Andrews district.'),
  ('Panama City Beach CRA', 29): (30.22241, -85.88933, 'address', CENSUS),
  ('Panama City Beach CRA', 43): (30.22997, -85.88801, 'address', CENSUS),
}

BUDGET_RX = re.compile(r'\b(budget(ed)? (amount|appropriation)|appropriation|budgeted)\b', re.I)
PROPOSED_RX = re.compile(r'\b(proposed only|request(ed)?|proposal)\b', re.I)

def classify(cra, i, p):
    o = dict(OV.get((cra, i), {}))
    o.update(LH_OV.get((cra, i), {}))
    text = f"{p.get('notes') or ''} {p.get('date_or_fy') or ''}"
    status = o.get('status')
    if not status:
        if cra == 'Springfield CRA' or BUDGET_RX.search(text):
            status = 'Budgeted'
        elif PROPOSED_RX.search(text):
            status = 'Proposed'
        else:
            status = 'Spent'
    count = o.get('count', status not in ('Incoming', 'Not CRA-funded', 'Proposed'))
    overlap = o.get('overlap', '')
    if p.get('amount') is None:
        count = False
        overlap = overlap or 'Amount not stated in the source'
    return status, count, overlap

out = {'cras': [], 'payments': [], 'budgets': [], 'controversies': [], 'gaps': []}
for c in cras:
    name = c['cra']
    out['cras'].append({k: c.get(k) for k in ('cra', 'city', 'created', 'overview')} |
                       {'districts': [{k: d.get(k) for k in ('name', 'created', 'acres', 'center')} for d in c['districts']]})
    for i, p in enumerate(c['payments']):
        pt = dict(PATCH.get((name, i), {}))
        if 'notes_pre' in pt: p['notes'] = pt.pop('notes_pre') + (p.get('notes') or '')
        if 'notes_post' in pt: p['notes'] = ((p.get('notes') or '') + pt.pop('notes_post')).strip()
        if (name, i) in COORD:
            lat, lng, prec, why = COORD[(name, i)]
            p['lat'], p['lng'], p['coord_precision'] = lat, lng, prec
            p['notes'] = ((p.get('notes') or '') + ' Map location: ' + why).strip()
        for k in ('payee', 'purpose', 'date_or_fy'):
            if k in pt: p[k] = pt.pop(k)
        if pt: OV[(name, i)] = {**OV.get((name, i), {}), **pt}
        status, count, overlap = classify(name, i, p)
        q = {k: p.get(k) for k in ('payee', 'amount', 'date_or_fy', 'purpose', 'category', 'location_name',
                                     'address', 'lat', 'lng', 'coord_precision', 'district', 'source_title',
                                     'source_url', 'confidence', 'notes')}
        q.update(cra=name, city=c['city'], status=status, count=count, overlap=overlap,
                 confidence='Official record' if (p.get('confidence') or '').startswith('documented') else 'News report')
        out['payments'].append(q)
    for b in c['budget_by_year']:
        out['budgets'].append(b | {'cra': name})
    for x in c.get('controversies', []):
        out['controversies'].append(x | {'cra': name})
    for g in c.get('data_gaps', []):
        out['gaps'].append({'cra': name, 'text': g})

# A pin with no street number that still falls outside its own district (the Front Beach Road CRA is a narrow corridor,
# and corridor/segment records were placed by hand) is moved to the nearest point just inside that district and marked approximate.
from shapely.geometry import shape as _shape, Point as _Pt
from shapely.ops import nearest_points as _near, unary_union as _union
_GIS = {'Downtown': ['Downtown CRA / DIB', 'Downtown Extension CRA'], 'Downtown North (Glenwood)': ['Downtown North CRA', 'Downtown N Extension CRA'],
        'St. Andrews': ['St. Andrews CRA', 'St Andrews CRA - West Expansion Area', 'St Andrews CRA - East Expansion Area'], 'Millville': ['Millville CRA'],
        'Front Beach Road CRA': ['Front Beach Road CRA'], 'Pier Park CRA': ['Pier Park CRA'], 'Lynn Haven Community Redevelopment Area': ['Lynn Haven CRA'],
        'Callaway Community Redevelopment Area': ['Callaway CRA'], 'Springfield Community Redevelopment Area': ['Springfield CRA'], 'Parker Community Redevelopment Area': ['Parker CRA']}
_feat = {f['properties']['CRA']: _shape(f['geometry']) for f in json.load(open('../geo/cra_gis.json'))['features']}
moved = 0
for q in out['payments']:
    names = _GIS.get(q.get('district'))
    if q.get('lat') is None or not names or re.match(r'^\d', q.get('address') or ''):
        continue
    area = _union([_feat[n] for n in names])
    pt = _Pt(q['lng'], q['lat'])
    if area.contains(pt):
        continue
    inner = area.buffer(-0.0004)
    tgt = _near(inner if not inner.is_empty else area, pt)[0]
    q['lat'], q['lng'] = round(tgt.y, 5), round(tgt.x, 5)
    q['coord_precision'] = 'approximate'
    q['notes'] = ((q.get('notes') or '') + ' Map location: approximate. The record names a street or corridor but no address, so the pin sits just inside the district boundary nearest the street named.').strip()
    moved += 1
print('pins moved inside their district:', moved)

# structured dates next to the free text (date_or_fy is kept): local fiscal years run Oct 1 - Sep 30
import sys
sys.path.insert(0, 'entities')
import ids
for q in out['payments']:
    q.update(ids.date_fields(q.get('date_or_fy')))

# the site's first year (entities/cutoff.py): payments that ended before 2016 and older yearly figures are left out.
# This runs after the (cra, index) overrides above, which count every payment in the research files.
import cutoff
n_all = len(out['payments'])
out['payments'] = [q for q in out['payments'] if cutoff.keep_span(q.get('date_start'), q.get('date_end') or q.get('date_start'))]
out['budgets'] = [b for b in out['budgets'] if cutoff.keep(b.get('fy'))]
print('payments before', cutoff.FIRST_YEAR, 'left out:', n_all - len(out['payments']))

json.dump(out, open('merged.json', 'w'), indent=1)
from collections import Counter
print(len(out['payments']), Counter((p['cra'], p['status'], p['count']) for p in out['payments']))

# shared ids (data/entities): vendors.json, vendor_review.json, people.json, joins; they read merged.json, so run them last
import subprocess, sys
subprocess.run([sys.executable, os.path.join('entities', 'build_entities.py')], check=True)
subprocess.run([sys.executable, os.path.join('campaign', 'build_vendor_matches.py')], check=True)
subprocess.run([sys.executable, os.path.join('campaign', 'build_contract_votes.py')], check=True)
subprocess.run([sys.executable, os.path.join('sunbiz', 'build_sunbiz.py'), 'bay'], check=True)  # business donors -> Sunbiz entities
subprocess.run([sys.executable, os.path.join('nonprofits', 'build_nonprofits.py'), 'bay'], check=True)  # nonprofits, their money and boards (names stay private)
subprocess.run([sys.executable, os.path.join('surtax', 'match_schedule.py')], check=True)
subprocess.run([sys.executable, os.path.join('weekly', 'track_new.py')], check=True)  # first-seen dates for the weekly email (site/weekly.py)
