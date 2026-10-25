"""Panama City adopted budgets by fund group, FY2017 to FY2022, and the General Fund for FY2016 and FY2023-24.

The city's Annual Budget books for FY2018 to FY2022 (Archive Center, https://www.panamacity.gov/Archive.aspx) are
scanned images with no text layer. Each book's Executive Budget Summary prints a "BUDGET SUMMARY" table of the
adopted year and the year before, by fund group. The figures below were read from those tables (OCR, then checked by
eye) and every year adds up to the printed GRAND TOTAL. FY2017 is the prior-year column of the FY2018 book.
The FY2023 and FY2024 books are not posted.
Run: python3 data/budgets/scripts/panama_city.py
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'panama_city.json')
ITEM = 'https://www.panamacity.gov/ArchiveCenter/ViewFile/Item/'
GROUPS = [('General Fund', 'general'), ('Special Revenue Funds', 'special revenue'), ('Debt Service Fund', 'debt service'),
          ('Capital Projects Fund', 'capital'), ('Marinas Fund', 'enterprise'), ('Solid Waste Fund', 'enterprise'),
          ('Utilities Fund', 'enterprise (utilities)'), ('Internal Service Funds', 'internal service')]
# fiscal year -> (archive item, book title, printed grand total, amounts in GROUPS order)
YEARS = {
    2017: ('326', 'Annual Budget Fiscal Year 2018 (prior-year column)', 92795990,
           [39669038, 4430018, 1870258, 2844000, 4918978, 8779953, 22344770, 7938975]),
    2018: ('326', 'Annual Budget Fiscal Year 2018, adopted Sept 25, 2017', 100117973,
           [41385849, 8462214, 2120553, 1334500, 3294141, 8894582, 25008355, 9617779]),
    2019: ('379', 'Annual Budget Fiscal Year 2019, adopted Sept 25, 2018', 108690082,
           [44872653, 7786311, 2969654, 1849000, 3856812, 8226864, 29146778, 9982010]),
    2020: ('417', 'Annual Budget Fiscal Year 2020, adopted Sept 23, 2019', 118250732,
           [45808555, 13466886, 6998628, 1000000, 1433656, 8631149, 31482041, 9429817]),
    2021: ('1449', 'Annual Budget Fiscal Year 2021, adopted Sept 21, 2020', 123114028,
           [47647856, 26393661, 6801056, 0, 1597778, 9391093, 21566421, 9716163]),
    2022: ('1471', 'Annual Budget Fiscal Year 2022, adopted Sept 27, 2021', 132053778,
           [54980116, 23633876, 5904296, 1454484, 1568676, 9451446, 25652443, 9408441]),
}

# General Fund only, from the "Budget (GAAP basis) and Actual" schedule in each year's Annual Comprehensive Financial
# Report: original budgeted expenditures plus original transfers out. That sum matches the budget book's General Fund
# exactly in the years both exist (FY2017: $32,448,627 + $7,220,410; FY2022: $47,295,136 + $7,684,981).
# fiscal year -> (archive item, report title, original expenditures, original transfers out)
ACFR_GF = {
    2016: ('305', '2016 Comprehensive Annual Financial Report', 33153951, 7656706),
    2023: ('1536', '2023 Annual Comprehensive Financial Report', 50823188, 9762870),
    2024: ('1550', '2024 Annual Comprehensive Financial Report', 58537667, 4960413),
}


def main():
    years = []
    for fy, (item, title, total, amounts) in sorted(YEARS.items()):
        assert sum(amounts) == total, (fy, sum(amounts), total)
        years.append({'fiscal_year': fy, 'status': 'adopted', 'source_title': title, 'source_url': ITEM + item, 'total': total,
                      'general_fund': amounts[0], 'general_fund_departments': [],
                      'funds': [{'name': n, 'type': t, 'amount': a} for (n, t), a in zip(GROUPS, amounts) if a]})
    for fy, (item, title, exp, tout) in ACFR_GF.items():
        years.append({'fiscal_year': fy, 'status': 'adopted', 'source_title': f'{title} (General Fund original budget)', 'source_url': ITEM + item,
                      'total': None, 'general_fund': exp + tout, 'general_fund_departments': [],
                      'funds': []})
    years.sort(key=lambda y: y['fiscal_year'])
    json.dump({'gov': 'pc', 'name': 'City of Panama City', 'as_of': '2026-10-25', 'notes': [
        'Adopted budgets by fund group from the BUDGET SUMMARY table in each Annual Budget book (scanned; figures read from the page images and checked against the printed grand total).',
        'The grand total includes transfers between funds and appropriated reserves.',
        'FY2025 onward come from the city\'s newer budget books, which list individual funds, so only the General Fund lines up line for line with these years.',
        'FY2016, FY2023 and FY2024 have the General Fund only, from the original budget in that year\'s Annual Comprehensive Financial Report (original expenditures plus transfers out, which matches the budget book in FY2017 and FY2022). The budget books for those years are not posted.',
        'FY2017 is the prior-year column of the FY2018 book.'], 'years': years},
        open(OUT, 'w'), indent=1)
    for y in years:
        print(y['fiscal_year'], y['total'], y['general_fund'])


if __name__ == '__main__':
    main()
