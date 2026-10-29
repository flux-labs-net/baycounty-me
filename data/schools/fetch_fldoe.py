#!/usr/bin/env python3
"""School grades and spending per school from the Florida Department of Education -> data/schools/<county>/.

    python3 data/schools/fetch_fldoe.py [--place fl-bay] [--only grades,spending] [--file path.xlsx ...]

- grades.json: every school grade on record since 2016 for the district's schools, from the state's latest School
  Grades spreadsheet (one file holds each school's grades back to 1999), plus that year's components: achievement and
  learning gains in English and math, science, social studies, graduation and acceleration, percent of points.
  https://www.fldoe.org/accountability/accountability-reporting/school-grades/
- spending.json: per-pupil spending at each school, federal and state/local, from the state's yearly Every Student
  Succeeds Act (ESSA) per-pupil expenditure files. https://www.fldoe.org/finance/fl-edu-finance-program-fefp/essa.stml

The fldoe.org site turns some cloud servers away. When it does, the script keeps what is on file and says so. A
spreadsheet downloaded by hand can be read with --file (grades or spending is told apart by its columns).
"""
import argparse, datetime as dt, html, io, json, os, re, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'data', 'entities'))
from cutoff import FIRST_YEAR  # noqa: E402

UA = 'Mozilla/5.0 (compatible; BayCounty.me public records reader; +https://baycounty.me/about)'
GRADES_PAGE = 'https://www.fldoe.org/accountability/accountability-reporting/school-grades/'
GRADES_ARCHIVE = 'https://www.fldoe.org/accountability/accountability-reporting/school-grades/archives.stml'
ESSA_PAGE = 'https://www.fldoe.org/finance/fl-edu-finance-program-fefp/essa.stml'


def fetch(url, timeout=90):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def links(page_url):
    """(absolute url, link text) for every spreadsheet linked from a page."""
    text = fetch(page_url).decode('utf-8', 'replace')
    out = []
    for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', text, re.S | re.I):
        if re.search(r'\.xlsx?(\?|$)', href, re.I):
            out.append((urllib.parse.urljoin(page_url, html.unescape(href)), re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', label))).strip()))
    return out


def norm(s):
    return re.sub(r'[^a-z0-9%]+', ' ', str(s or '').lower()).strip()


def sheets(blob):
    """Every sheet of a spreadsheet as a list of row tuples (xlsx through openpyxl, old xls through xlrd)."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
        return [(ws.title, [tuple(r) for r in ws.iter_rows(values_only=True)]) for ws in wb.worksheets]
    except Exception:
        import xlrd  # only for old .xls files
        wb = xlrd.open_workbook(file_contents=blob)
        return [(sh.name, [tuple(sh.row_values(i)) for i in range(sh.nrows)]) for sh in wb.sheets()]


def header_row(rows, need):
    for i, r in enumerate(rows[:40]):
        cells = [norm(c) for c in r]
        if all(any(n in c for c in cells) for n in need):
            return i, cells
    return None, None


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace('$', '').replace(',', '').replace('%', '').strip()
    try:
        return float(s)
    except ValueError:
        return None


def school_no(district, school):
    d, s = num(district), num(school)
    if d is None or s is None:
        return None
    return f'{int(d):02d}-{int(s):04d}'


def text(v):
    s = re.sub(r'\s+', ' ', str(v if v is not None else '')).strip()
    return s or None


# --- grades ----------------------------------------------------------------------------------------------------------

COMPONENTS = [  # output key, words that must all appear in the header
    ('ela_achievement', ['english', 'achievement']), ('ela_gains', ['english', 'learning gains']),
    ('ela_gains_low25', ['english', 'lowest']), ('math_achievement', ['math', 'achievement']),
    ('math_gains', ['math', 'learning gains']), ('math_gains_low25', ['math', 'lowest']),
    ('grade3_ela_achievement', ['grade 3 english']), ('science_achievement', ['science']), ('social_studies_achievement', ['social studies']),
    ('middle_acceleration', ['middle school acceleration']), ('graduation_rate', ['graduation']),
    ('college_career_acceleration', ['college and career']),
    ('total_points', ['total points']), ('percent_of_points', ['percent of total possible']),
    ('percent_tested', ['percent tested']), ('pct_minority', ['minority']),
    ('pct_economically_disadvantaged', ['economically disadvantaged']),
]


SCHOOL_TYPE = {'01': 'Elementary', '02': 'Middle', '03': 'High', '04': 'Combination'}


def merge_grades(parsed):
    """Several School Grades files -> one set of rows: grades from the newest file, each year's components from that year's file."""
    parsed = sorted(parsed, key=lambda p: p[0])
    fy, rows, _ = parsed[-1]
    comp = {(r['school_number'], r['year']): r for _, rs, _ in parsed for r in rs if r['year'] == r['file_year']}
    seen = {(r['school_number'], r['year']) for r in rows}
    out = [comp.get((r['school_number'], r['year']), r) | {'grade': r['grade'], 'file_year': fy} for r in rows]
    out += [r | {'file_year': fy} for k, r in comp.items() if k not in seen]  # a school dropped from the newest file
    state = [s for _, _, ss in parsed for s in ss]
    return fy, sorted(out, key=lambda r: (r['school_number'], r['year'])), state


def parse_grades(blob, district, label=''):
    """One row per school and year from a School Grades spreadsheet. Components are for the file's own year."""
    for name, rows in sheets(blob):
        i, cells = header_row(rows, ['district number', 'school number'])
        if i is None:
            continue
        col = {c: j for j, c in enumerate(cells)}
        di = next(j for c, j in col.items() if 'district number' in c)
        si = next(j for c, j in col.items() if 'school number' in c)
        ni = next((j for c, j in col.items() if 'school name' in c), None)
        gcols = {}
        for c, j in col.items():
            m = re.search(r'grade\D*(\d{4})', c)
            if m and 'percent' not in c and 'level' not in c:
                gcols[int(m.group(1))] = j
        if not gcols:
            continue
        file_year = max(gcols)
        comp = {}
        for key, words in COMPONENTS:
            j = next((j for c, j in col.items() if all(w in c for w in words) and not re.search(r'grade\D*\d{4}', c)
                      and (key == 'grade3_ela_achievement' or not c.startswith('grade 3'))), None)
            if j is not None:
                comp[key] = j
        flag = lambda words: next((j for c, j in col.items() if all(w in c for w in words)), None)
        ci, ti, ai = flag(['charter']), flag(['title i']), flag(['alternative'])
        sti = flag(['school type'])
        out = []
        state = {}  # statewide summary for the file's own year, by school type
        for r in rows[i + 1:]:
            if len(r) <= max(di, si) or text(r[di]) is None or num(r[di]) is None:
                continue
            fg = text(r[gcols[file_year]]) if gcols[file_year] < len(r) else None
            if fg and fg not in ('-', 'N/A', 'NA'):
                stype = SCHOOL_TYPE.get(text(r[sti]) if sti is not None else None, 'Other')
                for t in (stype, 'All'):
                    b = state.setdefault(t, {'schools': 0, 'grades': {}, 'sums': {}, 'counts': {}})
                    b['schools'] += 1
                    b['grades'][fg.upper()] = b['grades'].get(fg.upper(), 0) + 1
                    for k, jj in comp.items():
                        v = num(r[jj]) if jj < len(r) else None
                        if v is not None and k not in ('total_points',):
                            b['sums'][k] = b['sums'].get(k, 0) + v
                            b['counts'][k] = b['counts'].get(k, 0) + 1
            if int(num(r[di])) != int(district):
                continue
            sn = school_no(r[di], r[si])
            for y, j in sorted(gcols.items()):
                if y < FIRST_YEAR or j >= len(r):
                    continue
                g = text(r[j])
                if not g or g in ('-', 'N/A', 'NA'):
                    continue
                row = {'school_number': sn, 'school_name_raw': text(r[ni]) if ni is not None else None, 'year': y, 'grade': g.upper(),
                       'file_year': file_year}
                if y == file_year:
                    for k, jj in comp.items():
                        row[k] = num(r[jj]) if jj < len(r) else None
                    row['charter'] = text(r[ci]) if ci is not None and ci < len(r) else None
                    row['title_i'] = text(r[ti]) if ti is not None and ti < len(r) else None
                    row['alternative_ese'] = text(r[ai]) if ai is not None and ai < len(r) else None
                    row['school_type'] = SCHOOL_TYPE.get(text(r[sti]) if sti is not None and sti < len(r) else None)
                out.append(row)
        print(f'  grades {label} sheet {name!r}: years {sorted(gcols)}, components {sorted(comp)}, {len(out)} rows for district {district}')
        summary = []
        for t, b in sorted(state.items()):
            row = {'year': file_year, 'school_type': t, 'schools_graded': b['schools'], **{f'grade_{g.lower()}': b['grades'].get(g, 0) for g in 'ABCDFI'}}
            row.update({k: round(b['sums'][k] / b['counts'][k], 1) for k in b['sums']})
            summary.append(row)
        return file_year, out, summary
    raise ValueError(f'no School Grades table found in {label}')


def fetch_grades(district):
    found = links(GRADES_PAGE)
    print(f'  {len(found)} spreadsheets linked from the school grades page:', *[f'    {u} | {t}' for u, t in found[:30]], sep='\n')
    cands = []
    for u, t in found:
        m = re.search(r'SchoolGrades(\d{2})\.xlsx?', u, re.I)
        if m:
            cands.append((2000 + int(m.group(1)), u))
    if not cands:
        raise RuntimeError('no SchoolGradesYY spreadsheet linked from the school grades page')
    cands.sort()
    parsed = [parse_grades(fetch(u), district, u) for _, u in cands[-2:]]  # newest file has every grade; the one before adds last year's components
    fy, rows, state = merge_grades(parsed)
    return {'file_year': fy, 'source_url': cands[-1][1], 'page_url': GRADES_PAGE, 'rows': rows, 'state': state}


# --- spending (ESSA per-pupil expenditures) ---------------------------------------------------------------------------

def year_of(url, label):
    """'2122School...' or '2021-22' -> 2022 (the school year's end)."""
    for s in (os.path.basename(urllib.parse.urlparse(url).path), label):
        m = re.search(r'(20\d{2})\s*-\s*(\d{2})\b', s or '')
        if m:
            return int(m.group(1)) + 1
        m = re.search(r'(?<!\d)(\d{2})(\d{2})(?!\d)', s or '')
        if m and int(m.group(2)) == int(m.group(1)) + 1:
            return 2000 + int(m.group(2))
        m = re.search(r'(20\d{2})', s or '')
        if m:
            return int(m.group(1))
    return None


def parse_spending(blob, district, label='', year=None):
    out = []
    for name, rows in sheets(blob):
        i, cells = header_row(rows, ['school'])
        if i is None:
            continue
        # headers can span two rows ("Per-Pupil Expenditures" over "Federal | State/Local | Total")
        nxt = [norm(c) for c in rows[i + 1]] if i + 1 < len(rows) else []
        cells = [(a + ' ' + b).strip() if b and not re.match(r'^[\d.]+$', b) else a for a, b in zip(cells, nxt + [''] * (len(cells) - len(nxt)))]
        has_sub = any(nxt) and not any(num(c) is not None for c in rows[i + 1][:4] if c is not None)
        start = i + (2 if has_sub else 1)
        col = {c: j for j, c in enumerate(cells)}
        di = next((j for c, j in col.items() if 'district' in c and ('number' in c or 'code' in c or c.endswith('no') or c == 'district' or 'id' in c)), None)
        si = next((j for c, j in col.items() if 'school' in c and ('number' in c or 'code' in c or c.endswith('no') or 'id' in c)), None)
        if di is None or si is None:
            continue
        ni = next((j for c, j in col.items() if 'school' in c and 'name' in c), None)
        fed = next((j for c, j in col.items() if 'federal' in c), None)
        sl = next((j for c, j in col.items() if 'state' in c and 'local' in c), None)
        tot = next((j for c, j in col.items() if 'total' in c and j not in (fed, sl)), None)
        if fed is None and sl is None and tot is None:
            continue
        for r in rows[start:]:
            if len(r) <= max(di, si) or num(r[di]) is None or int(num(r[di])) != int(district):
                continue
            if num(r[si]) is None:
                continue
            f_, s_ = num(r[fed]) if fed is not None else None, num(r[sl]) if sl is not None else None
            t_ = num(r[tot]) if tot is not None else (f_ or 0) + (s_ or 0) if (f_ is not None or s_ is not None) else None
            out.append({'school_number': school_no(r[di], r[si]), 'school_name_raw': text(r[ni]) if ni is not None else None,
                        'year': year, 'federal_ppe': f_, 'state_local_ppe': s_, 'total_ppe': t_})
        print(f'  spending {label} sheet {name!r}: {len(out)} rows for district {district} (federal col {fed}, state/local {sl}, total {tot})')
        if out:
            return out
    return out


def fetch_spending(district, have):
    found = links(ESSA_PAGE)
    print(f'  {len(found)} spreadsheets linked from the ESSA page:', *[f'    {u} | {t}' for u, t in found[:40]], sep='\n')
    by_year = {r['year']: r for r in (have or {}).get('files', [])}
    rows = [r for r in (have or {}).get('rows', [])]
    for u, t in found:
        if not re.search(r'school', u + ' ' + t, re.I):
            continue
        y = year_of(u, t)
        if not y or y < FIRST_YEAR:
            continue
        try:
            got = parse_spending(fetch(u), district, u, y)
        except Exception as e:
            print(f'  {u}: {e}', file=sys.stderr)
            continue
        if got:
            rows = [r for r in rows if r['year'] != y] + got
            by_year[y] = {'year': y, 'source_url': u, 'label': t, 'schools': len(got)}
    if not by_year:
        raise RuntimeError('no school-level per-pupil spreadsheet could be read')
    return {'page_url': ESSA_PAGE, 'files': sorted(by_year.values(), key=lambda f: f['year']), 'rows': sorted(rows, key=lambda r: (r['year'], r['school_number']))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--place', default=os.environ.get('PLACE', 'fl-bay'))
    ap.add_argument('--only', default='grades,spending')
    ap.add_argument('--file', nargs='*', default=[], help='read these downloaded spreadsheets instead of fetching')
    ap.add_argument('--year', type=int, help='school year end for a --file spending sheet')
    a = ap.parse_args()
    conf = json.load(open(os.path.join(ROOT, 'places', a.place, 'place.json')))['schools']
    district = int(conf['fldoe_district'])
    od = os.path.join(HERE, a.place.split('-', 1)[-1])
    os.makedirs(od, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    gpath, spath = os.path.join(od, 'grades.json'), os.path.join(od, 'spending.json')
    load = lambda p: json.load(open(p)) if os.path.exists(p) else None
    save = lambda p, o: (json.dump(o, open(p, 'w'), indent=1, ensure_ascii=False), open(p, 'a').write('\n'))
    errors = 0

    if a.file:
        parsed = []
        for f in a.file:
            blob = open(f, 'rb').read()
            try:
                parsed.append(parse_grades(blob, district, f) + (f,))
            except ValueError:
                have = load(spath) or {'files': [], 'rows': []}
                y = a.year or year_of(f, '')
                got = parse_spending(blob, district, f, y)
                have['rows'] = [r for r in have['rows'] if r['year'] != y] + got
                have['files'] = [x for x in have['files'] if x['year'] != y] + [{'year': y, 'source_url': ESSA_PAGE, 'label': os.path.basename(f), 'schools': len(got)}]
                have.update({'place_id': a.place, 'fetched': now, 'page_url': ESSA_PAGE})
                save(spath, have)
        if parsed:
            fy, rows, state = merge_grades([p[:3] for p in parsed])
            newest = max(parsed, key=lambda p: p[0])[3]
            m = re.search(r'SchoolGrades\d{2}\.xlsx?', os.path.basename(newest), re.I)
            src = f'https://www.fldoe.org/file/18534/{m.group(0)}' if m else GRADES_PAGE
            save(gpath, {'place_id': a.place, 'fetched': now, 'file_year': fy, 'source_url': src, 'page_url': GRADES_PAGE, 'rows': rows, 'state': state})
            print(f'grades: {len(rows)} school-years through {fy}, {len(state)} statewide summary rows')
        return 0

    only = set(a.only.split(','))
    if 'grades' in only:
        try:
            g = fetch_grades(district)
            g.update({'place_id': a.place, 'fetched': now})
            save(gpath, g)
            print(f"grades: {len(g['rows'])} school-years through {g['file_year']}")
        except Exception as e:
            errors += 1
            print(f'grades: kept the file on hand ({e})', file=sys.stderr)
    if 'spending' in only:
        try:
            s = fetch_spending(district, load(spath))
            s.update({'place_id': a.place, 'fetched': now})
            save(spath, s)
            print(f"spending: {len(s['rows'])} school-years in {len(s['files'])} files")
        except Exception as e:
            errors += 1
            print(f'spending: kept the file on hand ({e})', file=sys.stderr)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
