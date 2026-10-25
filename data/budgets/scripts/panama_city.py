"""Panama City adopted budgets by fund group, FY2018 to FY2022.

The city's Annual Budget books for FY2019 to FY2022 (Archive Center, https://www.panamacity.gov/Archive.aspx) are
scanned images with no text layer. Each book's Executive Budget Summary prints a "BUDGET SUMMARY" table of the
adopted year and the year before, by fund group. The figures below were read from those tables (OCR, then checked by
eye) and every year adds up to the printed GRAND TOTAL. FY2018 is the prior-year column of the FY2019 book.
The FY2018 book itself (Item 326) and FY2023/FY2024 books are not posted.
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
    2018: ('379', 'Annual Budget Fiscal Year 2019 (prior-year column)', 100117973,
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


def main():
    years = []
    for fy, (item, title, total, amounts) in sorted(YEARS.items()):
        assert sum(amounts) == total, (fy, sum(amounts), total)
        years.append({'fiscal_year': fy, 'status': 'adopted', 'source_title': title, 'source_url': ITEM + item, 'total': total,
                      'general_fund': amounts[0], 'general_fund_departments': [],
                      'funds': [{'name': n, 'type': t, 'amount': a} for (n, t), a in zip(GROUPS, amounts) if a]})
    json.dump({'gov': 'pc', 'name': 'City of Panama City', 'as_of': '2026-10-25', 'notes': [
        'Adopted budgets by fund group from the BUDGET SUMMARY table in each Annual Budget book (scanned; figures read from the page images and checked against the printed grand total).',
        'The grand total includes transfers between funds and appropriated reserves.',
        'FY2025 onward come from the city\'s newer budget books, which list individual funds, so only the General Fund lines up line for line with these years.',
        'Not posted online: the FY2023 and FY2024 budget books, and the FY2018 book (its figures here are the prior-year column of the FY2019 book).'], 'years': years},
        open(OUT, 'w'), indent=1)
    for y in years:
        print(y['fiscal_year'], y['total'], y['general_fund'])


if __name__ == '__main__':
    main()
