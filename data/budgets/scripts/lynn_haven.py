"""Lynn Haven adopted budgets, FY2021 to the latest year: fund totals and General Fund departments.

Reads the "TOTAL EXPENDITURES by funding source" table in each Final Approved Budget PDF from
https://www.cityoflynnhaven.gov/192/Budgets and writes data/budgets/lynn_haven.json.

Every year is checked: the funds must add up to the printed grand total and the departments to the General Fund.
Run: python3 data/budgets/scripts/lynn_haven.py [pdf-folder]   (downloads the PDFs when the folder is empty)
Needs pdftotext (poppler).
"""
import json, os, re, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'lynn_haven.json')
BASE = 'https://www.cityoflynnhaven.gov/DocumentCenter/View/'
# fiscal year -> (document id, title as listed on the city's Budgets page)
DOCS = {
    2021: ('1104', 'FY 2020-2021 Final Approved Budget'),
    2022: ('1828', 'FY 2021-2022 Final Approved Budget'),
    2023: ('2294', 'FY 2022-2023 Final Approved Budget'),
    2024: ('2684', 'FY 2023-2024 Final Approved Budget'),
    2025: ('3330', 'FY 2024-25 Final Approved Budget'),
    2026: ('4411', 'FY2025-26 Final Approved Budget 9-23-25'),
    2027: ('5091', 'FY 2026-2027 Final Approved Budget'),
}
FUNDS = {
    '001': ('General Fund', 'general'), '021': ('General Impact Fees', 'special revenue'), '101': ('Disaster Recovery Fund', 'special revenue'),
    '102': ('Hurricane Michael Relief Fund', 'special revenue'), '103': ('COVID-19 Fund', 'special revenue'), '104': ('ARPA Fund', 'special revenue'),
    '301': ('Surtax Fund', 'special revenue / capital'), '401': ('Water Fund', 'enterprise (utilities)'), '402': ('Sewer Fund', 'enterprise (utilities)'),
    '404': ('Stormwater Fund', 'enterprise'), '405': ('Sanitation Fund', 'enterprise'), '501': ('Water Impact Fees', 'enterprise (impact fees)'),
    '502': ('Sewer Impact Fees', 'enterprise (impact fees)'), '504': ('Stormwater Impact Fees', 'enterprise (impact fees)'), '701': ('CRA Fund', 'CRA'),
}
# one name per department number, so a department lines up across years even when the document abbreviates it
DEPTS = {
    '511': 'Legislative', '512': 'Executive', '513': 'Finance', '515': 'Planning', '516': 'Public Works', '517': 'General Fund Debt Service',
    '518': 'Facility Maintenance', '519': 'Admin', '520': 'IT', '521': 'Police', '522': 'Fire', '523': 'Code Enforcement', '524': 'Building Department',
    '527': 'HR', '528': 'LH Bayou Preserve', '529': 'Budgeting', '539': 'Customer Service', '541': 'Street', '549': 'Fleet', '552': 'Economic Development',
    '571': 'Library', '572': 'Community Services/Sports', '573': 'Community Services/Parks', '574': 'Communications/Marketing', '576': 'Animal Shelter',
    '581': 'Indirect cost recovery (credit)', '581R': 'Reserve',
}
# Lines the text layer prints out of row order (checked by hand against the PDF page).
FIXES = {2021: {'581': -1782558.00, '581R': 0.0}, 2022: {'576': 258315.44, '581': -1619589.75, '581R': 0.0}}

TOK = r'\(?-?\$?\s?\(?\d[\d,]*(?:\.\d+)?\)?%?|N/A'


def _num(t):
    v = float(re.sub(r'[^\d.]', '', t) or 0)
    return -v if ('(' in t or '-' in t) else v


def _nums(s):
    toks = re.findall(TOK, s)
    stop = next((i for i, t in enumerate(toks) if t.endswith('%') or t == 'N/A'), len(toks))
    return [_num(t) for t in toks[:stop]]


def parse(text, fy):
    """The table's columns are the funds, then this year's grand total, last year's, and the change. A row's
    amount for this year is the second-to-last number before the percent."""
    L = text.replace('‐', '-').split('\n')
    hdrs = [i for i, l in enumerate(L) if re.search(r'Depart(ment)?\s*#\s*Department', l)]
    start = next(i for i in hdrs if any(re.match(r'^\s*511\s', x) for x in L[i + 1:i + 4]))
    funds = re.findall(r'\b(\d{3})\b', L[start].split('Department', 2)[-1])
    depts, total = {}, None
    for i in range(start + 1, start + 250):
        line = L[i]
        m = re.match(r'^\s*(\d{3})\s+(\D.+?)(?:\s{2,}(.*))?$', line)
        if m:
            code = m.group(1) + ('R' if m.group(1) == '581' and 'reserve' in m.group(2).lower() else '')
            rest, n = m.group(3) or '', _nums(m.group(3) or '')
            for j in range(i + 1, i + 4):  # amounts wrapped onto the next line
                if len(n) >= 2 or re.match(r'^\s*\d{3,6}\s+\D', L[j]):
                    break
                rest += ' ' + L[j]
                n = _nums(rest)
            if len(n) >= 2:
                depts[code] = n[-2]
        elif re.match(r'^\s*\$?\s?\(?[\d,]+', line) and len(_nums(line)) >= len(funds) + 1:
            total = _nums(line)
            break
    depts.update(FIXES.get(fy, {}))
    fund_totals = dict(zip(funds, total[:len(funds)]))
    grand = total[len(funds)]
    # checks: funds add up to the grand total, departments to the General Fund (to the dollar, allowing rounding)
    assert abs(sum(fund_totals.values()) - grand) < 5, (fy, 'funds', sum(fund_totals.values()), grand)
    assert abs(sum(depts.values()) - fund_totals['001']) < 5, (fy, 'departments', sum(depts.values()), fund_totals['001'])
    unknown = set(depts) - set(DEPTS) | set(fund_totals) - set(FUNDS)
    assert not unknown, (fy, unknown)
    return {
        'fiscal_year': fy, 'status': 'adopted', 'source_title': DOCS[fy][1], 'source_url': BASE + DOCS[fy][0],
        'total': round(grand), 'general_fund': round(fund_totals['001']),
        'funds': [{'code': c, 'name': f'{c} {FUNDS[c][0]}', 'type': FUNDS[c][1], 'amount': round(a)} for c, a in fund_totals.items() if round(a)],
        'general_fund_departments': [{'code': c, 'name': DEPTS[c], 'amount': round(a)} for c, a in depts.items() if round(a)],
    }

# FY2020's book (document 720) has no "by funding source" table, so its figures are copied from the City-Wide Budget
# Summary (pages 6 to 8): fund totals from the "Total Expenditures" row and General Fund departments from the General
# Fund column. The book prints the Disaster Recovery Fund beside the $38,923,414 city total; it is added here because
# FY2021 onward count it in the total. Checked by fund and department sums in main().
FY2020_FUNDS = {'001': 15231707, '701': 505174, '301': 2461272, '401': 8437369, '402': 7948751, '404': 1894564, '405': 2444577, '101': 68303743}
FY2020_DEPTS = [('511', 'City Commission', 104060), ('512', 'City Manager', 468204), ('513', 'Finance', 390169), (None, 'Professional Services', 283715),
                ('519', 'Administrative Support', 1414589), ('539', 'Customer Service', 392359), ('574', 'Communications & Marketing', 363932),
                ('518', 'Facility Maintenance', 665016), ('515', 'Comprehensive Planning', 253840), ('524', 'Building Department', 592298),
                ('521', 'Law Enforcement', 4086243), ('522', 'Fire', 2341029), ('516', 'Public Works Administration', 455752), ('541', 'Street', 1928427),
                ('549', 'Fleet Maintenance', 154272), ('571', 'Library', 11500), (None, 'Community Services', 2332657), ('576', 'Animal Shelter', 424772),
                (None, 'Community Redevelopment (General Fund share)', 96472), ('517', 'Debt Service', 158070), ('581', 'Indirect Allocation Transfers', -1685669)]


def fy2020():
    funds = [{'code': c, 'name': f'{c} {FUNDS[c][0]}', 'type': FUNDS[c][1], 'amount': a} for c, a in FY2020_FUNDS.items()]
    depts = [{'code': c, 'name': DEPTS[c] if c else n, 'amount': a} if c else {'name': n, 'amount': a} for c, n, a in FY2020_DEPTS]
    assert sum(FY2020_FUNDS.values()) - FY2020_FUNDS['101'] == 38923414 and sum(d['amount'] for d in depts) == FY2020_FUNDS['001']
    return {'fiscal_year': 2020, 'status': 'adopted', 'source_title': 'City of Lynn Haven 2020 Annual Budget (Fiscal Year 2019-2020, approved)',
            'source_url': BASE + '720', 'total': sum(FY2020_FUNDS.values()), 'general_fund': FY2020_FUNDS['001'], 'funds': funds,
            'general_fund_departments': depts}


def main(folder):
    os.makedirs(folder, exist_ok=True)
    years = [fy2020()]
    for fy, (doc, _) in sorted(DOCS.items()):
        pdf = os.path.join(folder, f'lh_fy{fy}.pdf')
        if not os.path.exists(pdf):
            urllib.request.urlretrieve(BASE + doc, pdf)
        text = subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True, text=True, check=True).stdout
        years.append(parse(text, fy))
        print(fy, years[-1]['total'], years[-1]['general_fund'], len(years[-1]['funds']), 'funds', len(years[-1]['general_fund_departments']), 'departments')
    json.dump({
        'gov': 'lh', 'name': 'City of Lynn Haven', 'as_of': '2026-10-25',
        'notes': [
            'Each year is the Final Approved (adopted) budget, from the "TOTAL EXPENDITURES by funding source" table (FY2020: the City-Wide Budget Summary). FY2025 is the original adopted budget; '
            'the city amended it to $64,870,778 at mid-year (April 2025).',
            'Fund amounts add up to the printed grand total and departments to the General Fund in every year (within a few dollars of rounding).',
            'Department numbers stay the same across years; names are the FY2026 document\'s, so "PD" is Police and "Bldg. Dept" is Building Department.',
            'Indirect cost recovery is a credit: the General Fund charges overhead to the utility funds, which lowers the General Fund total.',
            'FY2020\'s book prints the Disaster Recovery Fund ($68.3M) beside a $38.9M city total; it is counted here so FY2020 matches later years.',
            'Totals include transfers between funds, so some money is counted twice. FY2021 to FY2023 include large Hurricane Michael recovery budgets in the Disaster Recovery Fund.',
        ],
        'years': years,
    }, open(OUT, 'w'), indent=1)
    print('wrote', os.path.relpath(OUT))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '.pdf'))
