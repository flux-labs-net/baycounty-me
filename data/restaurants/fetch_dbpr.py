#!/usr/bin/env python3
"""
Restaurant and food service inspections and licenses for one county, from the Florida Department of Business and
Professional Regulation (DBPR), Division of Hotels and Restaurants public records:
https://www2.myfloridalicense.com/hotels-restaurants/public-records/

  python3 data/restaurants/fetch_dbpr.py              # this fiscal year's inspections + today's license list
  python3 data/restaurants/fetch_dbpr.py --history    # also every past fiscal year back to July 2016 (one time)
  python3 data/restaurants/fetch_dbpr.py --dir <folder>  # read files already downloaded to a folder

Writes (ingestion inputs, read by site/page_datasets.py):
  data/restaurants/<county>/inspections.csv  one row per inspection visit since 2016 (merged by visit id, so older
                                             fiscal years stay when the state's current-year file rolls over in July)
  data/restaurants/<county>/licenses.csv     every food service license in the county today
  data/restaurants/<county>/fetch.json       when each file was read, and any error

Only location data is kept: the licensee's mailing address and phone numbers in the state files are dropped.
The current-year file needs no extra packages; --history needs openpyxl and xlrd for the older .xlsx/.xls files.
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
B = 'https://www2.myfloridalicense.com'
SOURCE_PAGE = B + '/hotels-restaurants/public-records/'

# county key -> DBPR county number and region (district) file number
COUNTIES = {'bay': {'dbpr_county': '13', 'region': '6', 'name': 'Bay'}}

FIRST_DATE = '2016-01-01'  # the site's first year (data/entities/cutoff.py)


def history_files(region):
    """Past fiscal years (July to June). The state moved these files around over the years."""
    return [
        f'{B}/sto/file_download/hr/{region}fdinspi_1516.csv',  # July 2015 to June 2016: only 2016 rows are kept
        f'{B}/sto/file_download/hr/{region}fdinspi_1617.csv',
        f'{B}/sto/file_download/hr/{region}fdinspi_1718.csv',
        f'{B}/sto/file_download/hr/{region}fdinspi_1819.csv',
        f'{B}/sto/file_download/extracts/{region}fdinspi_1920.xls',
        f'{B}/sto/file_download/hr/{region}fdinspi_2021.csv',
        f'{B}/sto/file_download/hr/fdinspi_2122.xlsx',  # statewide from here on
        f'{B}/sto/file_download/hr/fdinspi_2223.xlsx',
        f'{B}/hr/inspections/fdinspi_2324.xlsx',
        f'{B}/hr/inspections/fdinspi_2425.xlsx',
        f'{B}/hr/inspections/fdinspi_2526.xlsx',
    ]


def current_files(region):
    return {'inspections': f'{B}/sto/file_download/extracts/{region}fdinspi.csv',
            'licenses': f'{B}/sto/file_download/extracts/hrfood{region}.csv'}


INSPECTION_COLS = ['visit_id', 'inspection_number', 'visit_number', 'license_number', 'license_type_code', 'business_name',
                   'address', 'city', 'zip', 'inspection_type', 'disposition', 'date', 'total_violations',
                   'high_priority', 'intermediate', 'basic', 'violations', 'license_id']
LICENSE_COLS = ['license_number', 'license_type_code', 'rank', 'licensee', 'business_name', 'address', 'address2', 'city',
                'zip', 'status_code', 'expires', 'last_inspection', 'seats', 'risk_level']


def fetch(url, folder=None):
    name = url.rsplit('/', 1)[1]
    if folder and os.path.exists(os.path.join(folder, name)):
        return open(os.path.join(folder, name), 'rb').read()
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (BayCounty.me public records reader)'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def rows_of(name, data):
    """Every row of a .csv, .xlsx or .xls file as a list of strings."""
    if name.endswith('.csv'):
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            text = data.decode('cp1252', errors='replace')
        yield from csv.reader(io.StringIO(text))
    elif name.endswith('.xlsx'):
        import openpyxl
        for r in openpyxl.load_workbook(io.BytesIO(data), read_only=True).worksheets[0].iter_rows(values_only=True):
            yield [_cell(v) for v in r]
    else:
        import xlrd
        book = xlrd.open_workbook(file_contents=data)
        s = book.sheet_by_index(0)
        for i in range(s.nrows):
            row = []
            for j, v in enumerate(s.row_values(i)):
                if s.cell_type(i, j) == xlrd.XL_CELL_DATE:
                    v = xlrd.xldate.xldate_as_datetime(v, book.datemode).strftime('%m/%d/%Y')
                row.append(_cell(v))
            yield row


def _cell(v):
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime('%m/%d/%Y')
    return str(v).strip()


def iso(d):
    d = (d or '').strip()
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', d)
    if m:
        return f'{m[3]}-{int(m[1]):02d}-{int(m[2]):02d}'
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', d)
    return m[0] if m else ''


def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def inspection_rows(name, data, county_no):
    """Inspection visits in one county. Layout: A-U fixed, then (in the newer statewide files) a lodging-only count,
    then the mobile-device flag, 58 violation counts, license id and visit id."""
    for r in rows_of(name, data):
        if len(r) < 80 or r[1].lstrip('0') != county_no.lstrip('0') or (r[11] or '').lower() != 'food':
            continue
        p = 21 if r[21] in ('Y', 'N', '') and r[22] not in ('Y', 'N') else 22
        v = r[p + 1:p + 59]
        date = iso(r[14])
        if date < FIRST_DATE:
            continue
        codes = ';'.join(f'{i + 1:02d}:{num(c)}' for i, c in enumerate(v) if num(c))
        yield {'visit_id': r[p + 60] if len(r) > p + 60 else '', 'inspection_number': r[9], 'visit_number': num(r[10]),
               'license_number': r[4], 'license_type_code': r[3], 'business_name': r[5].strip(), 'address': r[6].strip(),
               'city': r[7].strip(), 'zip': re.sub(r'\D', '', r[8])[:5], 'inspection_type': r[12].strip(),
               'disposition': r[13].strip(), 'date': date, 'total_violations': num(r[17]), 'high_priority': num(r[18]),
               'intermediate': num(r[19]), 'basic': num(r[20]), 'violations': codes, 'license_id': r[p + 59]}


def license_rows(name, data, county_no):
    it = rows_of(name, data)
    head = [h.strip().lower() for h in next(it)]
    ix = {h: i for i, h in enumerate(head)}
    g = lambda r, k: (r[ix[k]] if k in ix and ix[k] < len(r) else '').strip()
    for r in it:
        if g(r, 'location county code').lstrip('0') != county_no.lstrip('0'):
            continue
        yield {'license_number': g(r, 'license number'), 'license_type_code': g(r, 'license type code'), 'rank': g(r, 'rank code'),
               'licensee': g(r, 'licensee name'), 'business_name': g(r, 'business name'), 'address': g(r, 'location street address'),
               'address2': g(r, 'location address line 2'), 'city': g(r, 'location city'), 'zip': re.sub(r'\D', '', g(r, 'location zip code'))[:5],
               'status_code': g(r, 'primary status code'), 'expires': iso(g(r, 'license expiry date')),
               'last_inspection': iso(g(r, 'last inspection date')), 'seats': num(g(r, 'number of seats or rental units')),
               'risk_level': g(r, 'base risk level')}


def write_csv(path, cols, rows):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--county', default='bay')
    ap.add_argument('--history', action='store_true')
    ap.add_argument('--dir', help='folder with files already downloaded (same file names as the state uses)')
    a = ap.parse_args()
    c = COUNTIES[a.county]
    out = os.path.join(HERE, a.county)
    os.makedirs(out, exist_ok=True)
    ipath, lpath, log = os.path.join(out, 'inspections.csv'), os.path.join(out, 'licenses.csv'), {'source': SOURCE_PAGE, 'files': []}

    old = {}
    if os.path.exists(ipath):
        for r in csv.DictReader(open(ipath)):
            old[r['visit_id'] or r['inspection_number'] + '-' + r['visit_number']] = r
    urls = (history_files(c['region']) if a.history else []) + [current_files(c['region'])['inspections']]
    for u in urls:
        try:
            n = 0
            for r in inspection_rows(u.rsplit('/', 1)[1], fetch(u, a.dir), c['dbpr_county']):
                old[r['visit_id'] or f"{r['inspection_number']}-{r['visit_number']}"] = r
                n += 1
            log['files'].append({'url': u, 'rows': n, 'read': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')})
            print(f'{u}: {n} inspections', file=sys.stderr)
        except Exception as e:  # keep what we had; the log says which file failed
            log['files'].append({'url': u, 'error': str(e)[:200]})
            print(f'{u}: {e}', file=sys.stderr)
    rows = sorted(old.values(), key=lambda r: (r['date'], r['license_number'], str(r['visit_id'])), reverse=True)
    if rows:
        write_csv(ipath, INSPECTION_COLS, rows)

    u = current_files(c['region'])['licenses']
    try:
        lic = sorted(license_rows(u.rsplit('/', 1)[1], fetch(u, a.dir), c['dbpr_county']), key=lambda r: r['license_number'])
        if len(lic) > 100:  # a short or empty file is a bad download: keep yesterday's list
            write_csv(lpath, LICENSE_COLS, lic)
        log['files'].append({'url': u, 'rows': len(lic), 'read': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')})
    except Exception as e:
        log['files'].append({'url': u, 'error': str(e)[:200]})
        print(f'{u}: {e}', file=sys.stderr)
    log['inspections'] = len(rows)
    log['latest_inspection'] = rows[0]['date'] if rows else None
    json.dump(log, open(os.path.join(out, 'fetch.json'), 'w'), indent=1)
    print(f'{len(rows)} inspections, latest {log["latest_inspection"]}', file=sys.stderr)


if __name__ == '__main__':
    main()
