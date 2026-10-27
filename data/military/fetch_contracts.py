#!/usr/bin/env python3
"""Federal contracts paid to companies based in the county -> data/military/<county>/federal_contracts.json.

    python3 data/military/fetch_contracts.py [--county bay]

Source: USAspending.gov (api.usaspending.gov, public, no key), contract award types A-D, filtered to recipients whose
business address is in the county (recipient location, county FIPS). Two pulls:

  1. every contract transaction since 2016-01-01 (one row per obligation or modification), so totals count only
     money obligated in 2016 or later, even on a contract that started earlier (the site's first year, cutoff.py);
  2. the award record for each contract (description, start and end dates, industry, place of performance).

The recipient's street address is not kept, only the city. USAspending names the recipient as registered in SAM.gov.
"""
import argparse, datetime as dt, json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'entities'))
import cutoff  # noqa: E402

API = 'https://api.usaspending.gov/api/v2'
UA = 'BayCounty.me public records reader (+https://baycounty.me/about)'
COUNTIES = {'bay': {'state': 'FL', 'county': '005', 'name': 'Bay County'}}
TYPES = ['A', 'B', 'C', 'D']


def post(path, body, tries=5):
    data = json.dumps(body).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(API + path, data=data, headers={'Content-Type': 'application/json', 'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001  retry with backoff
            if i == tries - 1:
                raise
            print(f'  retry {path} ({e})', file=sys.stderr)
            time.sleep(2 ** (i + 1))


def filters(c, start, end):
    return {'award_type_codes': TYPES, 'recipient_locations': [{'country': 'USA', 'state': c['state'], 'county': c['county']}],
            'time_period': [{'start_date': start, 'end_date': end}]}


def windows(today):
    """Half-year windows, so no one search pages past USAspending's result limit."""
    for y in range(cutoff.FIRST_YEAR, today.year + 1):
        for a, b in (('01-01', '06-30'), ('07-01', '12-31')):
            s, e = f'{y}-{a}', f'{y}-{b}'
            if s <= today.isoformat():
                yield s, min(e, today.isoformat())


TX_FIELDS = ['Award ID', 'Recipient Name', 'Recipient UEI', 'Action Date', 'Transaction Amount', 'Awarding Agency',
             'Awarding Sub Agency', 'Mod', 'generated_internal_id', 'internal_id']
AW_FIELDS = ['Award ID', 'Recipient Name', 'Recipient UEI', 'Award Amount', 'Description', 'Start Date', 'End Date',
             'Awarding Agency', 'Awarding Sub Agency', 'Contract Award Type', 'NAICS', 'PSC', 'Recipient Location',
             'Primary Place of Performance', 'generated_internal_id']


def pages(path, body, key='results'):
    page = 1
    while True:
        d = post(path, {**body, 'limit': 100, 'page': page})
        yield from d.get(key, [])
        if not (d.get('page_metadata') or {}).get('hasNext'):
            break
        page += 1
        time.sleep(0.3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--county', default='bay')
    a = ap.parse_args()
    c = COUNTIES[a.county]
    today = dt.date.today()

    tx = []
    for s, e in windows(today):
        n = 0
        for r in pages('/search/spending_by_transaction/', {'filters': filters(c, s, e), 'fields': TX_FIELDS, 'sort': 'Action Date', 'order': 'asc'}):
            if (r.get('Action Date') or '') < cutoff.FIRST_DATE:
                continue
            tx.append({'award_key': r.get('generated_internal_id'), 'award_id': r.get('Award ID'), 'recipient': r.get('Recipient Name'),
                       'uei': r.get('Recipient UEI'), 'date': r.get('Action Date'), 'amount': r.get('Transaction Amount'),
                       'agency': r.get('Awarding Agency'), 'sub_agency': r.get('Awarding Sub Agency'), 'mod': r.get('Mod')})
            n += 1
        print(f'transactions {s}..{e}: {n}')

    awards = {}
    for s, e in windows(today):
        n = 0
        for r in pages('/search/spending_by_award/', {'filters': filters(c, s, e), 'fields': AW_FIELDS, 'sort': 'Award Amount', 'order': 'desc'}):
            k = r.get('generated_internal_id')
            if not k or k in awards:
                continue
            loc, pop = r.get('Recipient Location') or {}, r.get('Primary Place of Performance') or {}
            naics, psc = r.get('NAICS') or {}, r.get('PSC') or {}
            awards[k] = {'award_key': k, 'award_id': r.get('Award ID'), 'recipient': r.get('Recipient Name'), 'uei': r.get('Recipient UEI'),
                         'recipient_city': (loc.get('city_name') or '').title() or None, 'award_amount': r.get('Award Amount'),
                         'description': r.get('Description'), 'start_date': r.get('Start Date'), 'end_date': r.get('End Date'),
                         'agency': r.get('Awarding Agency'), 'sub_agency': r.get('Awarding Sub Agency'), 'award_type': r.get('Contract Award Type'),
                         'naics': naics.get('code') if isinstance(naics, dict) else naics, 'naics_description': naics.get('description') if isinstance(naics, dict) else None,
                         'psc': psc.get('code') if isinstance(psc, dict) else psc, 'psc_description': psc.get('description') if isinstance(psc, dict) else None,
                         'performance_city': (pop.get('city_name') or '').title() or None, 'performance_county': (pop.get('county_name') or '').title() or None,
                         'performance_state': pop.get('state_code')}
            n += 1
        print(f'awards {s}..{e}: {n} new')

    out = os.path.join(HERE, a.county, 'federal_contracts.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({'as_of': today.isoformat(), 'county': c['name'], 'first_date': cutoff.FIRST_DATE,
               'source_url': 'https://www.usaspending.gov/search', 'awards': sorted(awards.values(), key=lambda r: r['award_key']),
               'transactions': sorted(tx, key=lambda r: (r['date'] or '', r['award_key'] or '', r['mod'] or ''))},
              open(out, 'w'), indent=0, ensure_ascii=False, separators=(',', ':'))
    print(f'{len(awards)} awards, {len(tx)} transactions -> {out}')


if __name__ == '__main__':
    main()
