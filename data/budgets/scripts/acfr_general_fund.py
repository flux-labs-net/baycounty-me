"""General Fund original budgets from audited financial reports (ACFRs / annual financial audit reports).

Each audit has a General Fund "budget and actual" schedule with Original, Final and Actual columns. The original
budget's expenditures plus its transfers out equal the General Fund in the adopted budget book: checked exactly for
Panama City in FY2017 and FY2022. This script pulls those two figures from each report's text.

Reports come from the Florida Auditor General's filing pages (https://flauditor.gov/pages/efile_reports.html), which
keep the last five years, and from city archives for older years.
Run: python3 data/budgets/scripts/acfr_general_fund.py                writes data/budgets/<gov>.json from GF below
     python3 data/budgets/scripts/acfr_general_fund.py <txt folder>   re-reads {gov}_{year}.txt reports to check them

GF below holds the figures read from each report and checked by eye against its schedule. How each government's
General Fund is counted follows that government's own budget document:
- Panama City Beach, Callaway, Mexico Beach: original expenditures plus transfers out.
- Springfield, Parker: original expenditures (their "transfers" line is money coming in, which balances the budget).
  Parker FY2025 comes to $4,698,141 against $4,691,843 in its budget book.
- Bay District Schools: total available, as the district's budget states its General Fund: original revenues plus
  transfers in plus the beginning fund balance. FY2025 comes to $348.9M against about $348M reported for that year.
"""
import json
import glob, os, re, sys

NUM = r'\(?-?\$?\s*[\d,]{3,}\)?'


def val(s):
    s = s.replace('$', '').replace(',', '').strip()
    return -int(s.strip('()-')) if s.startswith('(') or s.startswith('-') else int(s)


def schedule(txt):
    """The lines of the General Fund budget-to-actual schedule, or None."""
    lines = txt.splitlines()
    for i, l in enumerate(lines):
        head = ' '.join(lines[max(0, i - 6):i + 8]).upper()
        if 'ORIGINAL' in l.upper() and 'GENERAL FUND' in head and 'BUDGET' in head and 'ACTUAL' in head and 'FINAL' in head:
            body = lines[i:i + 90]
            if any('Total expenditures' in b or 'TOTAL EXPENDITURES' in b for b in body):
                return head, body
    return None, None


def first_num(line):
    m = re.findall(NUM, line)
    return val(m[0]) if m else None


def extract(txt):
    head, body = schedule(txt)
    if not body:
        return None
    fy = re.search(r'(?:YEAR|PERIOD) ENDED\s+(SEPTEMBER|JUNE)\s+30,\s+(\d{4})', head)
    exp = tout = None
    for b in body:
        u = b.upper()
        if exp is None and re.search(r'TOTAL EXPENDITURES', u):
            exp = first_num(b.split(re.search(r'(?i)total expenditures', b).group(0), 1)[1])
        if tout is None and re.search(r'TRANSFERS?\s*-?\s*(OUT|TO)', u):
            tout = first_num(re.split(r'(?i)transfers?\s*-?\s*(?:out|to)[a-z ]*', b, maxsplit=1)[-1])
    return {'fy': int(fy.group(2)) if fy else None, 'expenditures': exp, 'transfers_out': abs(tout) if tout else 0}


AUD = 'https://flauditor.gov/pages/'
MUN = lambda name: lambda y: f'{AUD}mun_efile%20rpts/{y}%20{name.replace(" ", "%20")}.pdf'
# Parker posts its own older audits on https://cityofparker.com/government/budget/ (FY2020 is not posted)
PK = 'https://cityofparker.com/wp-content/uploads/filr/'
PARKER = {2016: PK + '2674/2016%20FINANCIAL%20STATEMENT.pdf',
          2017: PK + '1063/2017%20AUDIT%20REPORT.pdf', 2018: PK + '3182/September%2030,%202018%20Audited%20Financial%20Statements.pdf',
          2019: PK + '3183/September%2030,%202019%20Audited%20Financial%20Statements.pdf'}
SCH = {2019: 'dsb_efile%20rpts/2019%20bay%20county%20dsb.pdf'}
GOVS = {
    'pcb': ('City of Panama City Beach', 'panama_city_beach', MUN('panama city beach'),
            {2021: 36454770, 2022: 41559940, 2023: 72970287, 2024: 68694760, 2025: 68146565}),
    'cw': ('City of Callaway', 'callaway', MUN('callaway'),
           {2021: 13450163, 2022: 15561706, 2023: 14740954, 2024: 14379839, 2025: 13762612}),
    'sp': ('City of Springfield', 'springfield', MUN('springfield'),
           {2021: 8520589, 2022: 8873879, 2023: 13852200, 2024: 15003819, 2025: 13529841}),
    'parker': ('City of Parker', 'parker', lambda y: PARKER.get(y) or MUN('parker')(y),
               {2016: 2609730, 2017: 2579696, 2018: 2878321, 2019: 2869940, 2021: 4682926, 2022: 3017158, 2023: 3525131, 2024: 3802000, 2025: 4698141}),
    'mb': ('City of Mexico Beach', 'mexico_beach', MUN('mexico beach'),
           {2021: 3435691, 2022: 3192315, 2023: 4158845, 2024: 5598085, 2025: 8003671}),
    'schools': ('Bay District Schools', 'bay_district_schools',
                lambda y: AUD + SCH.get(y, f'dsb_efile%20rpts/{y}%20bay%20county%20district%20school%20board.pdf'),
                {2019: 243351498, 2021: 295347837, 2022: 301691505, 2024: 332446672, 2025: 348925303}),
}


def write():
    here = os.path.dirname(os.path.abspath(__file__))
    for gov, (name, fn, url, gf) in GOVS.items():
        years = [{'fiscal_year': y, 'status': 'adopted', 'source_title': f'FY{y} annual financial audit report, General Fund budget and actual schedule (original budget)',
                  'source_url': url(y), 'total': None, 'general_fund': v, 'funds': [], 'general_fund_departments': []} for y, v in sorted(gf.items())]
        json.dump({'gov': gov, 'name': name, 'as_of': '2026-10-25', 'notes': [
            'General Fund only: the original (adopted) budget from the General Fund budget-and-actual schedule in each year\'s audited financial report, filed with the Florida Auditor General.',
            'The Auditor General keeps the last five years of reports; earlier years need the reports from the government itself.'], 'years': years},
            open(os.path.join(here, '..', fn + '.json'), 'w'), indent=1)
        print(gov, {y: v for y, v in sorted(gf.items())})


if __name__ == '__main__':
    if len(sys.argv) < 2:
        write()
        sys.exit()
    for fp in sorted(glob.glob(os.path.join(sys.argv[1], '*.txt'))):
        r = extract(open(fp, errors='ignore').read())
        print(os.path.basename(fp), r, (r['expenditures'] or 0) + (r['transfers_out'] or 0) if r else '')
