"""Police, fire and the Sheriff (/public-safety): the safety-agencies, crime-counts and police-staffing datasets.

safety-agencies: who polices and who fights fires in each local government (data/safety/<county>/agencies.json,
hand-checked), with the FY2026 budget line for each, read from data/civic/budgets_detail.json so the amounts always
match the government budget pages.
crime-counts and police-staffing: what each police agency reported to the FBI each year since 2016
(data/safety/fetch_cde.py -> data/safety/<county>/fbi.json). Counts only; no person is named anywhere in these rows.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
FBI_URL = 'https://cde.ucr.cjis.gov/LATEST/webapp/#/pages/explorer/crime/crime-trend'
_C = {}


def _files():
    if 'f' not in _C:
        from place import PLACE_ID
        d = os.path.join(HERE, '..', 'data', 'safety', PLACE_ID.split('-', 1)[-1])
        load = lambda f, empty: json.load(open(os.path.join(d, f))) if os.path.exists(os.path.join(d, f)) else empty
        _C['f'] = (PLACE_ID, load('agencies.json', {'agencies': []}), load('fbi.json', {'agencies': {}}))
    return _C['f']


def _budget(gov, lines):
    """Sum of the named budget lines and the budget's fiscal year and source, from data/civic/budgets_detail.json."""
    path = os.path.join(HERE, '..', 'data', 'civic', 'budgets_detail.json')
    if 'b' not in _C:
        _C['b'] = {g['gov']: g for g in json.load(open(path))['governments']} if os.path.exists(path) else {}
    g = _C['b'].get(gov)
    if not g:
        return None, None, None, None
    found = [r for ln in lines for r in g.get(ln['section']) or [] if r['name'] == ln['name']]
    if len(found) != len(lines):
        raise ValueError(f'safety agencies: budget line missing for {gov}: {lines}')
    return sum(r['amount'] for r in found), '; '.join(r['name'] for r in found), g['fiscal_year'].split(' ')[0], g.get('source_url')


def _short(gid):
    from govs import GOVS
    return next((g['short'] for g in GOVS if g['key'] == gid), gid)


def residents(gov, service):
    """People the budget line serves: the city's residents; for the county's fire fund (unincorporated only), the county
    minus the cities; for the Sheriff, the whole county (it runs the jail for everyone)."""
    from govs import GOVS, profile
    pop = profile(gov).get('population')
    if gov == 'county' and service == 'fire' and pop:
        cities = [g['key'] for g in GOVS if g.get('kind') == 'city']
        pop -= sum(profile(c).get('population') or 0 for c in cities)
    return pop


def safety_agencies():
    place, A, F = _files()
    out = []
    for r in A['agencies']:
        amt, lines, fy, src = _budget(r['gov'], r.get('budget') or [])
        fbi = F['agencies'].get(r.get('fbi_ori') or '') or {}
        staff = fbi.get('staffing') or {}
        last = max(staff) if staff else None
        if last and int(last) < int(F.get('as_of', '2026')[:4]) - 2:
            last = None  # an old count from a department that no longer exists (Mexico Beach)
        out.append({'place_id': place, 'agency_id': r['agency_id'], 'agency': r['agency'], 'service': r['service'],
                    'gov_id': r['gov'], 'government': _short(r['gov']), 'agency_gov_id': r.get('agency_gov') or r['gov'],
                    'arrangement': r['arrangement'], 'budget_amount': amt, 'budget_lines': lines, 'budget_fiscal_year': fy,
                    'budget_source_url': src, 'residents': residents(r['gov'], r['service']),
                    'cost_per_resident': round(amt / residents(r['gov'], r['service']), 2) if amt and residents(r['gov'], r['service']) else None,
                    'fbi_ori': r.get('fbi_ori'),
                    'officers': staff[last]['officers'] if last else None, 'civilians': staff[last]['civilians'] if last else None,
                    'staffing_year': int(last) if last else None, 'website': r.get('website'), 'source_url': r.get('source_url')})
    return out


def _agency_rows():
    place, A, F = _files()
    for r in A['agencies']:
        fbi = F['agencies'].get(r.get('fbi_ori') or '')
        if fbi and fbi['agency_id'] == r['agency_id']:
            yield place, r, fbi


def crime_counts():
    state = _files()[2].get('state') or {}
    sr = state.get('per_100k') or {}
    out = []
    for place, r, fbi in _agency_rows():
        for y, offs in sorted(fbi['offenses'].items()):
            for code, v in offs.items():
                p = v.get('population')
                out.append({'place_id': place, 'agency_id': r['agency_id'], 'agency': r.get('fbi_agency') or r['agency'], 'fbi_ori': r['fbi_ori'],
                            'gov_id': r['gov'], 'year': int(y), 'offense_code': code, 'offense': v['label'], 'offense_group': v['group'],
                            'total_row': code in ('V', 'P'), 'count': v['count'], 'cleared': v.get('cleared'), 'months_reported': v['months'],
                            'population': p, 'per_1000': round(1000 * v['count'] / p, 2) if p and v['count'] is not None and v['months'] == 12 else None,
                            'florida_per_1000': round(sr[y][code] / 100, 2) if code in sr.get(y, {}) else None,
                            'reporting': 'monthly incident reports (NIBRS)' if int(y) >= 2025 else 'yearly summary',
                            'source_url': FBI_URL})
    return out


def police_staffing():
    out = []
    for place, r, fbi in _agency_rows():
        for y, s in sorted(fbi['staffing'].items()):
            out.append({'place_id': place, 'agency_id': r['agency_id'], 'agency': r.get('fbi_agency') or r['agency'], 'fbi_ori': r['fbi_ori'],
                        'gov_id': r['gov'], 'year': int(y), 'officers': s['officers'], 'civilians': s['civilians'],
                        'employees': s['officers'] + s['civilians'], 'female_officers': s['female_officers'],
                        'employees_per_1000': s['per_1000'], 'population': s['population'], 'source_url': FBI_URL})
    return out


DATASETS = [
    ('safety-agencies', 'Police and fire departments', "Who polices and who fights fires in each local government: the agency, how it is arranged (own department, the Sheriff, or a city paying the Sheriff by contract), the FY2026 budget for it (budget_lines names the lines added from the government's adopted budget, the same figures as the budget pages), cost_per_resident (the budget over residents: the city's population; the whole county for the Sheriff, who runs the jail for everyone; the unincorporated county for county fire), the latest sworn officers and civilian staff the agency reported to the FBI, and its FBI reporting number (fbi_ori). Hand-checked.", safety_agencies),
    ('crime-counts', 'Crimes reported by police agency', "Offenses each police agency in the county reported to the FBI's Uniform Crime Reporting program each year since 2016, from the FBI Crime Data Explorer: violent and property crime totals (total_row true) and murder, rape, robbery, aggravated assault, burglary, larceny-theft, motor vehicle theft and arson, with offenses cleared (solved or closed), the population the agency covers, and the statewide rate for the same offense and year (florida_per_1000; blank for 2021, when only half of Florida reported). A missing year means the agency sent nothing that year (no Florida agency reported for 2021; Panama City Beach has not reported since 2020). Florida agencies sent one yearly summary until 2024 and monthly incident reports (NIBRS) from 2025, so 2025 on is not directly comparable with earlier years. months_reported below 12 means the year is partial; per_1000 is left blank then. Counts only; no person is named.", crime_counts),
    ('police-staffing', 'Police staffing', "Sworn officers and civilian employees at each police agency in the county on October 31 each year since 2016, as the agency reported them to the FBI (Crime Data Explorer police employee data), with employees per 1,000 residents covered. The Sheriff's reported civilian staff went from 71 in 2022 to 271 in 2023; the FBI data does not say why.", police_staffing),
]
