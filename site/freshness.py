"""How current each headline figure is: the dataset data-freshness, shown on /data-sources#current.

One row per figure people ask about ("how many crimes this year?", "how many students?"): the newest period we have,
read from the data files themselves so it moves when a refresh brings in more, whether that is this year, this year so
far, or the newest the source has published, and when the next one is due. Due dates are the source's usual schedule,
checked by hand on the date in checked_on; they are not promises from the agency.
"""
import datetime as dt
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, '..', 'data')
CHECKED_ON = '2026-10-29'
MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

CURRENT, SO_FAR, WAITING, BY_HAND = 'Current', 'Year so far', 'Newest published', 'Newer data needs a by-hand download'


def _j(*p):
    path = os.path.join(D, *p)
    return json.load(open(path)) if os.path.exists(path) else {}


def _crime():
    from place import PLACE_ID
    f = _j('safety', PLACE_ID.split('-', 1)[-1], 'fbi.json')
    best = (0, 0)
    for a in (f.get('agencies') or {}).values():
        for y, offs in a['offenses'].items():
            bm = (offs.get('V') or {}).get('by_month') or []
            got = max((i + 1 for i, n in enumerate(bm) if n is not None), default=0)
            best = max(best, (int(y), got))
    staff = max((int(y) for a in (f.get('agencies') or {}).values() for y in a.get('staffing') or {}), default=None)
    return best, staff


def rows():
    today = dt.date.today()
    out = []

    def add(topic, figure, page, latest, year, status, next_due, how, source, source_url, notes=''):
        out.append({'topic': topic, 'figure': figure, 'page': page, 'latest_period': latest, 'latest_year': year, 'status': status,
                    'next_due': next_due, 'how_we_get_it': how, 'source': source, 'source_url': source_url, 'notes': notes or None,
                    'checked_on': CHECKED_ON})

    # crime and police staffing
    (cy, cm), staff = _crime()
    if cy:
        from safety_data import crime_monthly, year_to_date
        w = year_to_date(crime_monthly(), 'V', today)
        latest = (f'Jan to {MON[w["through_month"] - 1]} {w["year"]} for every agency; some through {MON[cm - 1]}' if w and w['through_month'] < cm
                  else f'Jan to {MON[cm - 1]} {cy}' if cm < 12 else str(cy))
        add('Public safety', 'Crimes reported by each police agency', '/public-safety#ytd', latest, cy,
            SO_FAR if cy == today.year else WAITING, 'More months each week as the FBI posts them, usually one to two months behind',
            'Automatic, weekly', 'FBI Crime Data Explorer', 'https://cde.ucr.cjis.gov/',
            'Florida moved to monthly reports in 2025, so this year is compared with the same months last year. The latest months are left out of that comparison while agencies finish them.')
    if staff:
        add('Public safety', 'Sworn officers and civilian staff', '/public-safety#staff', f'Oct 31, {staff}', staff, WAITING,
            f'The Oct 31, {staff + 1} count, published by the FBI in the fall of {staff + 2}', 'Automatic, weekly', 'FBI Crime Data Explorer (police employees)',
            'https://cde.ucr.cjis.gov/')

    # tourist tax
    ts = _j('tourism', 'tourism_surtax.json')
    col = (ts.get('bed_tax') or {}).get('collections') or []
    if col:
        last = max(col, key=lambda c: c['fy'])
        add('Tourist tax', 'Bed tax collected by zone', '/public-money/tourist-tax', f'FY{last["fy"]} ' + (last.get('period') or 'full year').replace('fiscal year to date ', ''),
            last['fy'], SO_FAR if last.get('partial') else CURRENT, 'The Clerk posts each month about four to six weeks after it ends; September closes the fiscal year',
            'Read by hand from the Clerk\'s monthly report', 'Bay County Clerk, monthly TDT report', last.get('source_url'))
        dist = (ts.get('infra_surtax') or {}).get('combined_surtax_distributions') or []
        if dist:
            y = max(r['state_fy'] for r in dist)
            add('Sales tax', 'Half-cent sales tax money sent to Bay County', '/public-money/sales-tax-projects', f'State FY{y} (July {y - 1} to June {y})', y, WAITING,
                f'State FY{y + 1} (to June {y + 1}), when the state updates its yearly file', 'State bulk file, by hand',
                'Florida EDR, discretionary sales surtax distributions', 'https://edr.state.fl.us/Content/local-government/data/data-a-to-z/discstxco.xlsx')

    # population
    pop = _j('civic', 'population.json')
    if pop.get('year'):
        y = pop['year']
        add('People', 'Residents of the county and each city', '/governments', f'April 1, {y} estimate', y, WAITING,
            f'April 1, {y + 1} estimates, usually published in December {y + 1}', 'State file, by hand', 'University of Florida BEBR',
            pop.get('source_page') or pop.get('source_url'))

    # budgets, tax rates, pay
    bud = _j('tax', 'budgets.json')
    n27 = sum(1 for g in bud.get('governments') or [] if (g.get('fy2027') or {}).get('status'))
    if n27:
        add('Budgets', 'Adopted budget of each government', '/public-money/budget-compare', 'FY2027 (Oct 1, 2026 to Sept 30, 2027)', 2027, CURRENT,
            'FY2028 budgets are adopted in September 2027', 'Read by hand from each budget book', 'Each government\'s budget documents', None,
            'Police and fire department lines on /public-safety still use FY2026, the newest year with department lines for every government.')
    fin = _j('tax', 'finances.json')
    fy = [int(str(y.get('fy') or y.get('fiscal_year'))[-4:]) for g in fin.get('governments') or [] for y in g.get('years') or []
          if str(y.get('fy') or y.get('fiscal_year') or '')[-4:].isdigit()]
    # a year counts once most governments have it (one city's early filing doesn't make it the newest year)
    n_gov = len(fin.get('governments') or [])
    fy_max = max((y for y in set(fy) if fy.count(y) * 2 > n_gov), default=None)
    if fy_max:
        add('Budgets', 'Audited revenue and spending', '/public-money/budget-compare', f'FY{fy_max}', fy_max, WAITING,
            f'FY{fy_max + 1}, once the state compiles the reports governments filed by June {fy_max + 2}', 'State workbook, by hand',
            'Florida EDR, local government financial reports', 'https://edr.state.fl.us/Content/local-government/data/revenues-expenditures/index.cfm')
    da = _j('debt_audit', 'debt_audit.json')
    if da.get('debt'):
        late = [x['government'].split(' (')[0] for x in da['debt'] if 'not yet filed' in (x.get('fy') or '')]
        add('Budgets', 'Debt and audit findings', '/public-money/accountability', 'FY2025 for most governments' + (f'; FY2024 for {", ".join(late)}' if late else ''),
            2025, WAITING, 'FY2026 audits are due by June 30, 2027' + ('; the late FY2025 audits as soon as they are filed' if late else ''),
            'Read by hand from each audit', 'Florida Auditor General', 'https://flauditor.gov/pages/municipalities_efiles.html')

    # schools
    sch = _j('schools', 'bay', 'schools.json')
    if sch.get('school_year'):
        y = int(sch['school_year'][:4]) + 1
        add('Schools', 'Students enrolled', '/schools', f'{sch["school_year"]} school year', y, BY_HAND,
            f'{y}-{(y + 1) % 100:02d} counts are on fldoe.org now; the federal directory adds them about a year later',
            'Automatic (federal directory); the state file needs a by-hand download', 'U.S. Department of Education, Common Core of Data',
            sch.get('source_url'), "The state's education site blocks automated downloads, so the newer state count has to be saved by hand.")
    gr = _j('schools', 'bay', 'grades.json')
    if gr.get('file_year'):
        y = int(gr['file_year'])
        add('Schools', 'School grades', '/schools', f'{y - 1}-{y % 100:02d} school year', y, CURRENT, f'{y}-{(y + 1) % 100:02d} grades, usually July {y + 1}',
            'By-hand download', 'Florida Department of Education', gr.get('page_url'))
    sp = _j('schools', 'bay', 'spending.json')
    if sp.get('rows'):
        y = max(r['year'] for r in sp['rows'])
        add('Schools', 'Spending per student at each school', '/schools', f'{y - 1}-{y % 100:02d} school year', y, WAITING,
            f'{y}-{(y + 1) % 100:02d} figures, usually posted the next spring', 'By-hand download', 'Florida Department of Education (ESSA per-pupil spending)', sp.get('page_url'))

    # homes and businesses
    pm = _j('development', 'bay', 'permits.json')
    if pm.get('permits'):
        last = max(pm['permits'], key=lambda r: (r['year'], r.get('months') or 12))
        add('Growth', 'New homes permitted', '/development', last.get('period') or str(last['year']), last['year'],
            SO_FAR if last.get('year_to_date') else CURRENT, 'Each month about four weeks after it ends', 'Automatic, weekly',
            'U.S. Census Bureau, Building Permits Survey', pm.get('source_page'))
    add('Growth', 'New businesses filed', '/new-businesses', 'Updated every day', today.year, CURRENT, 'Every day', 'Automatic, daily',
        'Florida Division of Corporations (Sunbiz)', 'https://dos.fl.gov/sunbiz/')
    add('Living here', 'Restaurant inspections', '/restaurants', 'Updated every day', today.year, CURRENT, 'Every day', 'Automatic, daily',
        'Florida DBPR, Division of Hotels and Restaurants', 'https://www2.myfloridalicense.com/hotels-restaurants/')
    return out


DATASETS = [
    ('data-freshness', 'How current each figure is', "One row per headline figure on the site: the newest period we have (latest_period, read from the data itself so it moves as refreshes bring in more), whether that is this year, this year so far, the newest the source has published, or newer data that needs a by-hand download (status), when the next period is usually published (next_due, the source's usual schedule as checked on checked_on, not a promise), how we get it, and the source.", rows),
]
