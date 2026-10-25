"""Bay County (Board of County Commissioners) adopted budgets by fund, FY2016 (the site's first year) to the latest year.

Reads the "Summary of All Funds" table in the county's budget books. Each table prints three years side by side, so
six documents cover every year from FY2016 (the FY2017 book's FY2015 column is dropped, see data/entities/cutoff.py). Documents are on the Budget Office page
(https://www.baycountyfl.gov/262/Budget-Office) and its "Previous Annual Budgets" archive (Archive.aspx?AMID=40).

Every year is checked: the funds must add up to the printed "Total all Funds" and the General Fund row must match.
General Fund departments for FY2026 come from data/civic/budgets_detail.json (older books print departments only in
the long expenditure reports).
Run: python3 data/budgets/scripts/bay_county.py [pdf-folder]   (downloads the PDFs when missing). Needs pdftotext.
"""
import json, os, re, subprocess, sys, urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'entities'))
import cutoff  # noqa: E402  the site's first year

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'bay_county.json')
SITE = 'https://www.baycountyfl.gov/'
# document -> (title, {column index: fiscal year}, status). Columns are the three budget years the table prints.
DOCS = {
    'Archive.aspx?ADID=113': ('2017 Summary of All Funds', {0: 2015, 1: 2016, 2: 2017}, 'adopted'),
    'Archive.aspx?ADID=219': ('FY 19 Summary of Funds (final hearing, Sept 18, 2018)', {1: 2018, 2: 2019}, 'adopted'),
    'Archive.aspx?ADID=293': ('FY22 Commission Books 9-14-2021', {0: 2020, 1: 2021, 2: 2022}, 'adopted'),
    'Archive.aspx?ADID=329': ('Bay County FY25 Tentative Budget - Commissioners Book 09-04-2024', {0: 2023, 1: 2024}, 'adopted'),
    'DocumentCenter/View/18382': ("FY 2026 Final Budget Commissioners' Book 09-16-2025", {1: 2025, 2: 2026}, 'adopted'),
    'DocumentCenter/View/21090': ('FY 2027 Tentative Budget Commissioner Book 09-15-26',
                                  {2: 2027}, 'final hearing Sept 23, 2026 (the book and presentation still label it tentative)'),
}
# the FY2019 column of ADID=219 matches the Sept 18, 2018 final hearing presentation (ADID=221): $341,640,225
TYPES = [((1, 1), 'general'), ((101, 299), 'special revenue'), ((300, 399), 'capital'), ((400, 499), 'enterprise'), ((500, 599), 'internal service')]
NUM = r'\(?\$?\s*-?[\d,]+\)?|\$?\s*-'


def money(s):
    s = s.replace('$', '').replace(',', '').strip()
    if s in ('', '-'):
        return 0
    neg = s.startswith('(') or s.startswith('-')
    v = int(s.strip('()-').strip())
    return -v if neg else v


def ftype(code):
    c = int(code)
    return next((t for (a, b), t in TYPES if a <= c <= b), 'other')


def table(txt):
    """The first Summary of All Funds table: [(code, name, [3 amounts])], total row amounts."""
    lines = txt.splitlines()
    i = next(n for n, l in enumerate(lines) if 'Summary of All Funds' in l)
    rows = []
    for l in lines[i + 1:]:
        if 'Total all Funds' in l:
            return rows, [money(x) for x in re.findall(NUM, l.split('Total all Funds', 1)[1])][:3]
        m = re.match(r'\s*(\d{3})\s+(.+?)\s{2,}((?:(?:' + NUM + r')\s+){3})', l + ' ')
        if m:
            rows.append((m.group(1), ' '.join(m.group(2).split()), [money(x) for x in re.findall(NUM, m.group(3))][:3]))
    raise ValueError('no Total all Funds row')


def pdf_text(folder, doc):
    fn = os.path.join(folder, re.sub(r'\W+', '_', doc) + '.pdf')
    if not os.path.exists(fn):
        req = urllib.request.Request(SITE + doc, headers={'User-Agent': 'Mozilla/5.0'})
        open(fn, 'wb').write(urllib.request.urlopen(req, timeout=120).read())
    return subprocess.run(['pdftotext', '-layout', fn, '-'], capture_output=True, text=True, check=True).stdout


def main(folder):
    os.makedirs(folder, exist_ok=True)
    years = {}
    for doc, (title, cols, status) in DOCS.items():
        rows, tot = table(pdf_text(folder, doc))
        for c, fy in cols.items():
            funds = [{'code': code, 'name': f'{code} {name}', 'type': ftype(code), 'amount': v[c]} for code, name, v in rows if v[c]]
            s = sum(f['amount'] for f in funds)
            assert s == tot[c], (fy, s, tot[c])
            gf = next(f['amount'] for f in funds if f['code'] == '001')
            years[fy] = {'fiscal_year': fy, 'status': status, 'source_title': title, 'source_url': SITE + doc,
                         'total': tot[c], 'general_fund': gf, 'funds': funds, 'general_fund_departments': []}
    # later documents name a fund the way the county names it now, so every year uses the latest name for each number
    latest = {}
    for fy in sorted(years):
        for f in years[fy]['funds']:
            latest[f['code']] = f['name']
    for y in years.values():
        for f in y['funds']:
            f['name'] = latest[f['code']]
    det = {g['gov']: g for g in json.load(open(os.path.join(HERE, '..', '..', 'civic', 'budgets_detail.json')))['governments']}['county']
    years[2026]['general_fund_departments'] = det.get('general_fund_departments') or []
    out = {'gov': 'county', 'name': 'Bay County Board of County Commissioners', 'as_of': '2026-10-25', 'notes': [
        'Each year is the adopted budget from the "Summary of All Funds" table in the county budget books; each table prints three years, so the source is the earliest book that shows that year as adopted.',
        'Fund amounts include reserves and cash carried forward, and add up to the printed "Total all Funds" in every year. That total counts transfers between funds twice (FY2026: $734.5M with transfers).',
        'Each fund keeps its number across years and takes the latest name the county gives it (for example "101 Transportation Trust" is now "101 Transportation").',
        'FY2019 is the figure presented at the Sept 18, 2018 final hearing. FY2027 is the Sept 2026 final-hearing figure, which the county still labels tentative.',
        'General Fund departments are on record for FY2026 only; older books print departments in long line-item reports that are not parsed yet.']}
    out['years'] = [years[y] for y in sorted(years) if cutoff.keep(y)]
    json.dump(out, open(OUT, 'w'), indent=1)
    for y in out['years']:
        print(y['fiscal_year'], len(y['funds']), y['total'], y['general_fund'])


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '.pdf_cache'))
