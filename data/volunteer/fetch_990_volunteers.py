#!/usr/bin/env python3
"""Volunteers each county nonprofit reported on its latest Form 990 -> data/volunteer/<county>/volunteers_990.csv.

    python3 data/volunteer/fetch_990_volunteers.py [--county bay]

Form 990 Part I line 6 asks for the total number of volunteers (an estimate the organization makes). The 990-EZ and
990-PF don't ask. For every organization in data/nonprofits/<county>/filings.csv.gz, this reads its latest e-filed 990
XML (the same GivingTuesday data lake mirror of IRS e-files that fetch_irs.py uses) and keeps TotalVolunteersCnt.
"""
import argparse, csv, gzip, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = 'Mozilla/5.0 (compatible; BayCounty.me nonprofit data reader; +https://baycounty.me/about)'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--county', default='bay')
    a = ap.parse_args()
    src = os.path.join(HERE, '..', 'nonprofits', a.county, 'filings.csv.gz')
    latest = {}
    for r in csv.DictReader(gzip.open(src, 'rt', encoding='utf-8')):
        if r['form'] != '990' or not r.get('xml_url'):
            continue
        k = (r['tax_year'], r['submitted_on'])
        if r['ein'] not in latest or k > (latest[r['ein']]['tax_year'], latest[r['ein']]['submitted_on']):
            latest[r['ein']] = r
    out_path = os.path.join(HERE, a.county, 'volunteers_990.csv')
    old = {}
    if os.path.exists(out_path):
        old = {r['ein']: r for r in csv.DictReader(open(out_path))}
    rows = []
    for i, (ein, r) in enumerate(sorted(latest.items())):
        o = old.get(ein)
        if o and o['object_id'] == r['object_id']:
            rows.append(o)
            continue
        try:
            req = urllib.request.Request(r['xml_url'], headers={'User-Agent': UA})
            x = urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'replace')
        except Exception as e:  # noqa: BLE001  keep the old value if there was one
            print(f'{ein}: {e}', file=sys.stderr)
            if o:
                rows.append(o)
            continue
        m = re.search(r'<TotalVolunteersCnt>(\d+)</TotalVolunteersCnt>', x)
        rows.append({'ein': ein, 'object_id': r['object_id'], 'tax_year': r['tax_year'], 'volunteers': m.group(1) if m else '',
                     'employees': r.get('employees') or '', 'xml_url': r['xml_url']})
        time.sleep(0.2)
        if i % 25 == 0:
            print(f'{i}/{len(latest)}')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['ein', 'object_id', 'tax_year', 'volunteers', 'employees', 'xml_url'])
        w.writeheader()
        w.writerows(rows)
    print(f'{len(rows)} returns, {sum(1 for r in rows if r["volunteers"] not in ("", "0"))} with volunteers -> {out_path}')


if __name__ == '__main__':
    main()
