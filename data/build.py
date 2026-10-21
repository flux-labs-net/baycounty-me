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
    if p.get('amount') is None:
        count = False
    return status, count, o.get('overlap', '')

out = {'cras': [], 'payments': [], 'budgets': [], 'controversies': [], 'gaps': []}
for c in cras:
    name = c['cra']
    out['cras'].append({k: c.get(k) for k in ('cra', 'city', 'created', 'overview')} |
                       {'districts': [{k: d.get(k) for k in ('name', 'created', 'acres', 'center')} for d in c['districts']]})
    for i, p in enumerate(c['payments']):
        pt = dict(PATCH.get((name, i), {}))
        if 'notes_pre' in pt: p['notes'] = pt.pop('notes_pre') + (p.get('notes') or '')
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

json.dump(out, open('merged.json', 'w'), indent=1)
from collections import Counter
print(len(out['payments']), Counter((p['cra'], p['status'], p['count']) for p in out['payments']))
