"""Rebuild money by ZIP code and disaster declarations, from OpenFEMA (public, no key). Run by hand or weekly:
  python3 data/emergency/fetch_fema.py [place]
Writes data/emergency/<county>/rebuild.json:
  declarations  every federal disaster or emergency declaration that included the county since 2016
  by_zip        one row per ZIP code, program and storm: FEMA housing aid to owners and renters (Individuals and
                Households Program) and flood insurance (NFIP) claims paid. Only totals per ZIP; no household is named.
"""
import json, os, sys, time, urllib.parse, urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
FIRST_YEAR = 2016
PLACES = {'fl-bay': {'state': 'FL', 'fips': '12005', 'county_fips': '005', 'fema_county': 'Bay (County)', 'zip_prefix': ('324',),
                     # One name per ZIP (FEMA's city field varies row to row). ZIPs that cross a county line say so.
                     'zip_names': {'32401': 'Panama City (downtown, St. Andrews)', '32403': 'Tyndall Air Force Base', '32404': 'East Panama City, Callaway, Springfield, Parker',
                                   '32405': 'North Panama City, Lynn Haven area', '32407': 'Panama City Beach (east)', '32408': 'Panama City Beach (central)',
                                   '32409': 'Southport, Bayou George', '32410': 'Mexico Beach', '32413': 'Panama City Beach (west), Inlet Beach area',
                                   '32438': 'Fountain', '32444': 'Lynn Haven', '32456': 'Mexico Beach and Port St. Joe area (part in Gulf County)', '32466': 'Youngstown'}}}
API = 'https://www.fema.gov/api/open'


def get(path, params):
    rows, skip = [], 0
    while True:
        q = urllib.parse.urlencode({**params, '$top': 1000, '$skip': skip}, safe="$,'() ")
        req = urllib.request.Request(f'{API}/{path}?{q}'.replace(' ', '%20'), headers={'User-Agent': 'BayCounty.me (hello@baycounty.me)'})
        for attempt in range(4):
            try:
                d = json.load(urllib.request.urlopen(req, timeout=120))
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(4 * (attempt + 1))
        key = [k for k in d if k != 'metadata'][0]
        rows += d[key]
        if len(d[key]) < 1000:
            return rows
        skip += 1000


def main(place='fl-bay'):
    P = PLACES[place]
    out_dir = os.path.join(HERE, place.split('-', 1)[1])
    decl = get('v2/DisasterDeclarationsSummaries', {'$filter': f"state eq '{P['state']}' and fipsCountyCode eq '{P['county_fips']}' and declarationDate ge '{FIRST_YEAR}-01-01'",
                                                    '$select': 'disasterNumber,declarationTitle,declarationDate,incidentType,declarationType,incidentBeginDate,incidentEndDate,ihProgramDeclared,iaProgramDeclared,paProgramDeclared,hmProgramDeclared'})
    decl = [d for d in decl if d['incidentType'] != 'Biological']  # the COVID-19 declarations aren't storms or fires
    declarations = [{'disaster_number': d['disasterNumber'], 'title': d['declarationTitle'].title(), 'kind': {'DR': 'Major disaster', 'EM': 'Emergency', 'FM': 'Fire management'}.get(d['declarationType'], d['declarationType']),
                     'incident_type': d['incidentType'], 'declared': d['declarationDate'][:10], 'began': (d.get('incidentBeginDate') or '')[:10] or None,
                     'ended': (d.get('incidentEndDate') or '')[:10] or None, 'individual_aid': bool(d.get('ihProgramDeclared') or d.get('iaProgramDeclared')),
                     'public_aid': bool(d.get('paProgramDeclared')), 'mitigation': bool(d.get('hmProgramDeclared')),
                     'source_url': f"https://www.fema.gov/disaster/{d['disasterNumber']}"} for d in decl]
    declarations.sort(key=lambda d: d['declared'], reverse=True)
    titles = {d['disaster_number']: d['title'] for d in declarations}

    rows = []
    for d in declarations:
        if not d['individual_aid'] or d['kind'] != 'Major disaster':
            continue
        for ds, who in (('v2/HousingAssistanceOwners', 'owners'), ('v2/HousingAssistanceRenters', 'renters')):
            for r in get(ds, {'$filter': f"disasterNumber eq {d['disaster_number']} and county eq '{P['fema_county']}'"}):
                z = str(r.get('zipCode') or '')
                if not z.startswith(P['zip_prefix']) or not r.get('validRegistrations'):
                    continue
                rows.append({'zip': z, 'area_name': (r.get('city') or '').title(), 'program': f'FEMA housing aid ({who})', 'disaster_number': d['disaster_number'],
                             'event': d['title'], 'year': int(d['declared'][:4]), 'count': r['validRegistrations'], 'count_label': 'households that applied',
                             'approved': r.get('approvedForFemaAssistance'), 'amount_paid': round(r.get('totalApprovedIhpAmount') or 0, 2),
                             'repair_amount': round((r.get('repairReplaceAmount') or 0) if who == 'owners' else 0, 2), 'rental_amount': round(r.get('rentalAmount') or 0, 2),
                             'inspected_damage': round(r.get('totalDamage') or 0, 2) if who == 'owners' else None,
                             'source_url': f"https://www.fema.gov/openfema-data-page/housing-assistance-program-data-{who}-v2"})

    claims = get('v3/NfipClaims', {'$filter': f"countyCode eq '{P['fips']}' and yearOfLoss ge {FIRST_YEAR}",
                                   '$select': 'yearOfLoss,reportedZipCode,floodEvent,amountPaidOnBuildingClaim,amountPaidOnContentsClaim,amountPaidOnIncreasedCostOfComplianceClaim,nfipCommunityName'})
    agg = defaultdict(lambda: {'count': 0, 'paid': 0.0, 'communities': defaultdict(int)})
    for c in claims:
        z = str(c.get('reportedZipCode') or '')
        if not z.startswith(P['zip_prefix']):
            continue
        paid = sum(float(c.get(k) or 0) for k in ('amountPaidOnBuildingClaim', 'amountPaidOnContentsClaim', 'amountPaidOnIncreasedCostOfComplianceClaim'))
        a = agg[(z, c['yearOfLoss'], c.get('floodEvent') or 'Other flooding')]
        a['count'] += 1
        a['paid'] += paid
        a['communities'][(c.get('nfipCommunityName') or '').title()] += 1
    names = {}
    for r in rows:
        names.setdefault(r['zip'], r['area_name'])
    for (z, y, ev), a in agg.items():
        comm = max(a['communities'], key=a['communities'].get)
        rows.append({'zip': z, 'area_name': names.get(z) or comm.replace(', City Of', '').replace('Bay County*', 'Bay County').strip(), 'program': 'Flood insurance claims (NFIP)',
                     'disaster_number': next((n for n, t in titles.items() if ev and ev.lower() in t.lower()), None), 'event': ev, 'year': y,
                     'count': a['count'], 'count_label': 'claims', 'approved': None, 'amount_paid': round(a['paid'], 2), 'repair_amount': None, 'rental_amount': None,
                     'inspected_damage': None, 'source_url': 'https://www.fema.gov/openfema-data-page/fima-nfip-redacted-claims-v2'})
    merged = {}
    for r in rows:
        # ZIPs outside the list (P.O. boxes, typos, mailing addresses in nearby counties) are added up as one row.
        if r['zip'] not in P['zip_names']:
            r['zip'], r['area_name'] = 'other', 'Other ZIP codes (P.O. boxes or mailing addresses outside the county)'
        else:
            r['area_name'] = P['zip_names'][r['zip']]
        k = (r['zip'], r['program'], r['event'], r['year'])
        if k not in merged:
            merged[k] = r
            continue
        m = merged[k]
        for f in ('count', 'approved', 'amount_paid', 'repair_amount', 'rental_amount', 'inspected_damage'):
            if r.get(f) is not None:
                m[f] = round((m.get(f) or 0) + r[f], 2)
    rows = list(merged.values())
    rows.sort(key=lambda r: (-r['year'], r['zip'], r['program']))
    json.dump({'_about': 'Written by data/emergency/fetch_fema.py from OpenFEMA. Totals per ZIP code; FEMA does not publish who received aid and neither do we.',
               'checked': time.strftime('%Y-%m-%d'), 'declarations': declarations, 'by_zip': rows},
              open(os.path.join(out_dir, 'rebuild.json'), 'w'), indent=1)
    print(f'{len(declarations)} declarations, {len(rows)} ZIP rows ({len(claims)} flood claims)')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'fl-bay')
