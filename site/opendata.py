"""Open data: every dataset on the site as CSV and JSON (/open-data)."""
import csv, html, io, json, os, re
from govs import all_profiles, gov_of_body, is_split

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
e = lambda s: html.escape(str(s if s is not None else ''))
import sys as _sys
_sys.path.insert(0, os.path.join(DATA, 'entities'))
import ids  # noqa: E402  shared government / vendor / person ids (data/entities)
import cutoff  # noqa: E402  the site's first year (data/entities/cutoff.py)

# which columns name the government, per dataset, tried in order (office titles are matched by contained name)
GOV_COLS = {'beach-access': ['run_by'], 'beach-parking': [], 'beach-water-sites': [], 'beach-water-samples': [], 'beach-conditions': [], 'parks': ['gov_id'], 'boat-ramps': ['gov_id'], 'trails': [], 'recreation-departments': ['gov_id'], 'development-projects': ['gov_id'], 'housing-permits': ['gov_id'], 'road-contracts': [], 'road-work-program': [], 'chambers': [], 'chamber-leaders': [], 'chamber-events': [], 'owner-gifts': ['office'], 'entity-profiles': ['gov_id'], 'entity-connections': [], 'government-profiles': ['government'], 'government-years': ['gov_id', 'government'], 'budget-years': ['gov_id'], 'cra-agencies': ['gov_id'], 'cra-tax-increment': ['gov_id'], 'cra-increment-checks': [], 'officeholder-terms': ['gov_id'], 'official-photos': [], 'data-completeness': ['gov_id'], 'votes': ['government'], 'member-votes': ['gov_id'], 'cra-payments': ['city'],
            'property-tax-rates': ['authority_id'], 'fema-michael-projects': ['applicant'], 'officials-pay': ['title', 'government'],
            'meetings': ['gov', 'board'], 'campaign-finance': ['office', 'gov'], 'bonds': ['gov'], 'salary-positions': ['employer_id'],
            'salary-leaders': ['employer_id'], 'candidates-2026': ['office', 'government'], 'campaign-contributions-2026': ['office'], 'campaign-history': ['gov_id'], 'campaign-contributions-history': ['gov_id'],
            'bed-tax-collections': [], 'property-tax-exemptions': [],
            'connections-gifts': ['official_gov_id', 'office'], 'connections-payments': ['payer_gov_id'], 'donor-contracts': ['contract_gov_id'], 'connections-payees': [], 'connections-links': [],
            'vendors-directory': [], 'people-directory': [], 'glossary-terms': [], 'site-updates': [], 'tax-districts': ['district'],
            'savings-opportunities': ['government'], 'savings-evidence': [], 'business-donor-sunbiz': ['gov_id', 'office'], 'shared-owner-groups': [], 'over-limit-gifts': [], 'official-businesses': ['gov_id'], 'official-business-links': ['gov_id'], 'checkbook-payments': ['gov_id'], 'budget-actuals': ['gov_id']}
# county bed tax in every zone; the county-wide tax roll; the school datasets are all the school district's
FIXED_GOV = {'bed-tax-collections': 'county', 'property-tax-exemptions': 'county',
             'schools': 'schools', 'school-grades': 'schools', 'school-spending': 'schools', 'school-enrollment': 'schools', 'school-calendar': 'schools', 'school-zones': 'schools'}


VENDOR_COL = {'contracts': 'vendor', 'change-orders': 'vendor', 'emergency-purchases': 'vendor', 'cra-payments': 'payee', 'vendor-payments': 'vendor',
              'campaign-contributions-2026': 'contributor', 'campaign-contributions-history': 'contributor', 'business-donor-sunbiz': 'contributor', 'road-contracts': 'contractor'}


def add_vendor_id(did, rows):
    """vendor_id from data/entities/vendors.json; vendor_ids lists every firm when one record names several (a joint award)."""
    col = VENDOR_COL.get(did)
    if not col:
        return rows
    for r in rows:
        v = [] if did in ('campaign-contributions-2026', 'campaign-contributions-history') and r.get('contributor_type') != 'business' else ids.vendor_ids(r.get(col))
        r['vendor_id'] = v[0] if v else None
        r['vendor_ids'] = v if len(v) > 1 else None
    return rows


PERSON_COL = {'member-votes': 'member', 'officials-pay': 'name', 'salary-leaders': 'name', 'campaign-finance': 'official', 'candidates-2026': 'candidate',
              'business-donor-sunbiz': 'candidate', 'campaign-history': 'candidate'}


def add_person_id(did, rows):
    """person_id from data/entities/people.json (elected officials, department leaders, 2026 candidates only).
    A '(D2)' style suffix moves out of the name into district."""
    col = PERSON_COL.get(did)
    if not col:
        return rows
    for r in rows:
        nm = r.get(col)
        if isinstance(nm, str):
            clean, dist = ids.split_district(nm)
            if dist:
                r[col] = clean
                r['district'] = dist
            elif did == 'officials-pay':
                r['district'] = None
        r['person_id'] = ids.person_id(nm) if isinstance(nm, str) else None
    return rows


# free-text date column -> structured date_start / date_end / date_precision next to it (the text is kept)
DATE_COL = {'cra-payments': 'date_or_fy', 'sales-tax-projects': 'fiscal_years', 'officials-pay': 'year', 'debt': 'fy', 'audit-findings': 'fy',
            'salary-positions': 'fiscal_year', 'salary-leaders': ('fiscal_year', 'as_of'), 'budget-detail': 'fiscal_year', 'budget-per-resident': 'fiscal_year',
            'fees-assessments': 'fiscal_year', 'bed-tax-collections': 'fy', 'government-years': 'fy', 'budget-years': 'fy'}


def add_dates(did, rows):
    cols = DATE_COL.get(did)
    if not cols:
        return rows
    cols = (cols,) if isinstance(cols, str) else cols
    for r in rows:
        fy_start = (ids.gov(r.get('gov_id') or '') or {}).get('fy_start_month', 10)
        val = next((r.get(c) for c in cols if r.get(c) not in (None, '')), None)
        r.update(ids.date_fields(val, fy_start))
    return rows


def _cv():
    try:
        return json.load(open(os.path.join(DATA, 'votes', 'contract_votes.json')))['links']
    except FileNotFoundError:
        return []


CV_SRC = {'contracts': 'contract', 'change-orders': 'change_order', 'emergency-purchases': 'emergency'}


def add_vote_links(did, rows):
    """contracts/change orders/emergency purchases get vote_ids; votes get contract_ids (record ids like 'contract:12'), from data/votes/contract_votes.json."""
    links = _cv()
    if did in CV_SRC:
        by = {}
        for l in links:
            by.setdefault(l['record_id'], []).append(l)
        for i, r in enumerate(rows):
            ls = by.get(f'{CV_SRC[did]}:{i}', [])
            r['record_id'] = f'{CV_SRC[did]}:{i}'
            r['vote_ids'] = [l['vote_id'] for l in ls] or None
            r['vote_match_method'] = '; '.join(l['match_method'] for l in ls) or None
    elif did == 'votes':
        by = {}
        for l in links:
            by.setdefault(l['vote_index'], []).append(l)
        d = _j('votes', 'votes.json')
        vids = ids.vote_ids(d['votes'])
        for i, (r, v) in enumerate(zip(rows, d['votes'])):
            ls = by.get(i, [])
            r['vote_id'] = vids[i]
            r['contract_ids'] = [l['record_id'] for l in ls] or None
            r['contract_match_method'] = '; '.join(l['match_method'] for l in ls) or None
        for r in rows[len(d['votes']):]:  # votes read from minutes: not linked to contracts yet
            r.setdefault('contract_ids', None)
            r.setdefault('contract_match_method', None)
    return rows


# The site's first year (2016, data/entities/cutoff.py). Ingestion already leaves older records out; this is the last
# check before rows reach the downloads, the API and the database. A row is dropped when the column below (or, for
# datasets with structured dates, date_end) is before 2016. Empty values are kept: a term or business with no end is
# still going.
FIRST_YEAR_COL = {'votes': 'date', 'member-votes': 'date', 'contracts': 'date', 'change-orders': 'date', 'emergency-purchases': 'date',
                  'property-tax-rates': 'tax_year', 'accountability-events': 'sort_date', 'connections-payments': 'date',
                  'nonprofit-payments': 'date', 'nonprofit-grants': 'tax_year', 'nonprofit-board-members': 'last_year',
                  'nonprofit-officials': 'last_year', 'charity-registrations': 'expiration_date', 'entity-connections': 'last_date',
                  'officeholder-terms': 'end_date', 'official-businesses': 'closed_year', 'official-business-links': 'last_date',
                  'business-donor-sunbiz': 'last_date', 'over-limit-gifts': 'last_date', 'owner-gifts': 'last_date',
                  'checkbook-payments': 'fiscal_year', 'budget-actuals': 'fiscal_year', 'cra-tax-increment': 'fiscal_year',
                  'cra-increment-checks': 'fiscal_year', 'campaign-contributions-2026': 'date', 'campaign-contributions-history': 'date', 'meetings': 'start', 'chamber-leaders': 'year', 'beach-water-samples': 'date',
                  'school-grades': 'year', 'school-spending': 'year', 'school-enrollment': 'year', 'school-calendar': 'starts'}
DROPPED_BEFORE_FIRST_YEAR = {}  # dataset -> rows the last check dropped (should stay empty: fix the ingestion instead)


def first_year_rows(did, rows):
    col = FIRST_YEAR_COL.get(did) or ('date_end' if did in DATE_COL else None)
    if not col:
        return rows
    kept = [r for r in rows if cutoff.keep(r.get(col))]
    if len(kept) < len(rows):
        DROPPED_BEFORE_FIRST_YEAR[did] = len(rows) - len(kept)
    return kept


def add_gov_id(did, rows):
    cols = GOV_COLS.get(did, ['government', 'gov'])
    add_vote_links(did, rows)
    add_vendor_id(did, rows)
    add_person_id(did, rows)
    for r in rows:
        if did in FIXED_GOV:
            r['gov_id'] = FIXED_GOV[did]; continue
        g = None
        for c in cols:
            v = r.get(c)
            g = ids.gov_id(v) or (ids.gov_id(v, contains=True) if c in ('office', 'title', 'board', 'government') else None)
            if g:
                break
        r['gov_id'] = g
    return first_year_rows(did, add_dates(did, rows))


def _j(*p):
    try:
        return json.load(open(os.path.join(DATA, *p)))
    except FileNotFoundError:
        return None


def _minutes_votes():
    """Votes read from official minutes (data/votes/minutes_votes.json, written by data/minutes/export_votes.py)."""
    return (_j('votes', 'minutes_votes.json') or {}).get('votes') or []


def _vote_row(v, names, source_type):
    bm = v.get('by_member') or {}
    return {'date': v.get('date'), 'government': gov_of_body(v['body']), 'board': names.get(v['body']), 'category': v.get('category'), 'headline': v.get('headline'),
            'summary': v.get('summary'), 'amount': v.get('amount'), 'outcome': v.get('outcome'), 'tally': v.get('tally'), 'split': is_split(v),
            'voted_yes': '; '.join(n for n, x in bm.items() if x == 'yes'), 'voted_no': '; '.join(n for n, x in bm.items() if x == 'no'),
            'absent_or_abstained': '; '.join(n for n, x in bm.items() if x in ('absent', 'abstain')), 'agenda_item': v.get('item'),
            'source_title': v.get('source_title'), 'source_url': v.get('source_url'),
            'members': [{'name': n, 'person_id': ids.person_id(n), 'vote': x} for n, x in bm.items()] or None,
            'source_type': source_type, 'verified': v.get('verified') or ('hand-checked' if source_type == 'researched' else None),
            'vote_method': v.get('vote_method'), 'mover': v.get('mover'), 'seconder': v.get('seconder'), 'source_page': v.get('source_page'),
            'vote_id': v.get('vote_id')}


def _votes():
    """Hand-researched votes (data/votes/votes.json) first, in file order (add_vote_links pairs them with
    contract_votes.json by index), then every vote read from minutes."""
    d = _j('votes', 'votes.json'); names = {b['id']: re.sub(r'\bCity City\b', 'City', b['name']) for b in d['bodies']}
    return [_vote_row(v, names, 'researched') for v in d['votes']] + [_vote_row(v, names, 'minutes') for v in _minutes_votes()]


def _member_votes():
    d = _j('votes', 'votes.json'); names = {b['id']: re.sub(r'\bCity City\b', 'City', b['name']) for b in d['bodies']}
    vids = ids.vote_ids(d['votes'])
    both = [(v, vids[i], 'researched') for i, v in enumerate(d['votes'])] + [(v, v.get('vote_id'), 'minutes') for v in _minutes_votes()]
    return [{'date': v.get('date'), 'board': names.get(v['body']), 'member': n, 'vote': x, 'headline': v.get('headline'), 'source_url': v.get('source_url'),
             'gov_id': gov_of_body(v['body']), 'source_type': st, 'vote_id': vid}
            for v, vid, st in both for n, x in (v.get('by_member') or {}).items()]


def _cra():
    from page_datasets import cra_payee_ids
    pid = cra_payee_ids()  # the Connections payee id (connections-payees.entity_id), same row order
    return [{**{k: p.get(k) for k in ('cra', 'city', 'payee', 'amount', 'date_or_fy', 'status', 'category', 'purpose', 'location_name', 'district', 'lat', 'lng', 'count', 'source_title', 'source_url', 'notes')},
             'payee_entity_id': pid[i]}
            for i, p in enumerate(_j('merged.json')['payments'])]


def _rates():
    import sys; sys.path.insert(0, HERE)
    from tax_page import build_data
    td = build_data(); out = []
    for k, a in td['auth'].items():
        for i, y in enumerate(td['years']):
            out.append({'authority_id': k, 'authority': a.get('n'), 'kind': a.get('g'), 'school': a.get('school'), 'tax_year': y,
                        'millage': (a.get('m') or [None] * 9)[i], 'rolled_back_rate': (a.get('rb') or [None] * 9)[i] if a.get('rb') else None, 'levy': (a.get('lv') or [None] * 9)[i] if a.get('lv') else None})
    return out


def _profiles():
    out = []
    for p in all_profiles():
        b, d, v = p.get('budget') or {}, p.get('debt') or {}, p.get('votes') or {}
        au = (p.get('audits') or [{}])[0]
        out.append({'government': p['short'], 'kind': p['kind'], 'population_2025': p.get('population'), 'budget_total': b.get('total'), 'general_fund': b.get('general_fund'),
                    'budget_status': b.get('status'), 'millage': b.get('mills'), 'property_tax_levy': b.get('levy'), 'debt_total': d.get('total'), 'debt_year': d.get('fy'),
                    'audit_year': au.get('fy'), 'audit_findings': len(au.get('findings') or []), 'repeat_findings': sum(1 for f in au.get('findings') or [] if f.get('repeat')),
                    'votes_recorded': v.get('n'), 'split_votes': v.get('split'), 'employees_fte': (p.get('officials') or {}).get('employees'),
                    'typical_utility_bill': (p.get('utility_bill') or {}).get('total'), 'fema_michael_obligated': (p.get('fema') or {}).get('federal_obligated'),
                    'page': f'https://baycounty.me/governments/{p["slug"]}'})
    return out


def _flat(rows, keys):
    return [{k: r.get(k) for k in keys} for r in rows]


def _salaries(kind):
    import glob
    out = []
    for fp in sorted(glob.glob(os.path.join(DATA, 'salaries', '*.json'))):
        d = json.load(open(fp)); src = d.get('sources') or []
        def url(x):
            if isinstance(x, int) and 0 <= x < len(src):
                return src[x].get('url')
            return x if isinstance(x, str) else None
        if kind == 'positions':
            for r in d.get('positions') or []:
                act = [a for a in (r.get('actual_salaries') or []) if isinstance(a, (int, float))]
                out.append({'employer': d.get('employer'), 'employer_id': d.get('employer_id'), 'government': d.get('gov'), 'fiscal_year': d.get('fiscal_year'),
                            'title': r.get('title'), 'department': r.get('department'), 'category': r.get('category'), 'grade': r.get('grade'),
                            'pay_min': r.get('pay_min'), 'pay_mid': r.get('pay_mid'), 'pay_max': r.get('pay_max'), 'pay_basis': r.get('pay_basis'),
                            'hourly_min': r.get('hourly_min'), 'hourly_max': r.get('hourly_max'), 'actual_salaries': act or None, 'budgeted_fte': r.get('budgeted_fte'),
                            'union': r.get('union'), 'source_url': url(r.get('source')), 'notes': r.get('notes')})
                fte_only = not act and not any(r.get(k) for k in ('pay_min', 'pay_mid', 'pay_max', 'hourly_min', 'hourly_max'))
                out[-1]['fte_only'] = fte_only
                out[-1]['pay_status'] = 'Position count only: the source lists this job but not its pay' if fte_only else 'Pay listed'
        else:
            for r in d.get('leaders') or []:
                out.append({'employer': d.get('employer'), 'employer_id': d.get('employer_id'), 'government': d.get('gov'), 'name': r.get('name'), 'title': r.get('title'),
                            'department': r.get('department'), 'salary': r.get('salary'), 'basis': r.get('basis'), 'as_of': r.get('as_of'), 'source_url': url(r.get('source')), 'notes': r.get('notes')})
    return out


def _candidates():
    c, f = _j('elections', 'candidates_2026.json'), _j('elections', 'finance_2026.json')
    if not c:
        return []
    import sys; sys.path.insert(0, HERE)
    from elections_page import match_finance
    fin = (f or {}).get('candidates') or []; out = []
    for r in c['races']:
        for k in r.get('candidates') or []:
            m = match_finance(k, r.get('office'), fin) or {}
            bt = m.get('by_type_total') or {}; fi = m.get('from_individuals') or {}
            out.append({'race_id': r.get('id'), 'office': r.get('office'), 'government': r.get('gov'), 'race_status': r.get('status'), 'candidate': k.get('name'),
                        'party': k.get('party'), 'incumbent': k.get('incumbent'), 'status': k.get('status'), 'website': k.get('website'),
                        'platform': k.get('platform') or None, 'platform_sources': k.get('platform_sources') or None,
                        'total_raised': m.get('total_raised'), 'total_spent': m.get('total_spent'), 'from_individuals_total': fi.get('total'), 'from_individuals_count': fi.get('count'),
                        'from_organizations': round(sum(v for x, v in bt.items() if x not in ('individual', 'candidate_self')), 2) if bt else None,
                        'own_money': bt.get('candidate_self'), 'reports_through': m.get('through'), 'finance_report_url': m.get('report_url')})
    return out


def _contributions():
    f = _j('elections', 'finance_2026.json')
    if not f:
        return []
    # organizations only; individual donors are never published on this site.
    # Bank interest on a campaign account (kind 'interest', a few cents a month) is not a contribution from anyone: left out.
    return [{'candidate': c['name'], 'office': c.get('office'), 'contributor': x.get('name'), 'contributor_type': x.get('type'), 'city': x.get('city'),
             'amount': x.get('amount'), 'date': x.get('date'), 'kind': x.get('kind'), 'report_url': c.get('report_url')}
            for c in f.get('candidates') or [] for x in c.get('contributors') or []
            if x.get('type') not in ('candidate', 'individual', 'self') and x.get('kind') != 'interest']


def _history():
    """campaign-history: one row per local campaign 2016-2025 (data/campaign/campaign_history.json). Individuals summed only."""
    h = _j('campaign', 'campaign_history.json')
    out = []
    for c in (h or {}).get('candidates') or []:
        bt = c.get('by_type_total') or {}; fi = c.get('from_individuals') or {}; me = c.get('candidate_self') or {}
        out.append({'election_year': c['year'], 'election': c['election'], 'election_date': c['election_date'], 'primary_date': c.get('primary_date'),
                    'government': (ids.gov(c['gov_id']) or {}).get('short'), 'gov_id': c['gov_id'], 'office': c['office'], 'candidate': c['name'], 'party': c.get('party'),
                    'outcome': c.get('outcome'), 'soe_status': c.get('soe_status'), 'total_raised': c.get('total_raised'), 'monetary': c.get('monetary'), 'in_kind': c.get('in_kind'),
                    'loans': c.get('loans'), 'total_spent': c.get('total_spent'), 'n_contributions': c.get('n_contributions'),
                    'from_individuals_total': fi.get('total'), 'from_individuals_count': fi.get('count'), 'from_individuals_in_county': (fi.get('in_county') or {}).get('total'),
                    'from_businesses': bt.get('business'), 'from_pacs_and_committees': bt.get('pac'), 'from_parties': bt.get('party'), 'from_other': bt.get('other'),
                    'own_money': bt.get('candidate_self'), 'own_loans': me.get('loans') or None, 'reports_through': c.get('through'), 'reconciliation': c.get('reconciliation'),
                    'soe_candidate_id': c.get('cand_id'), 'report_url': c.get('report_url'), 'source_url': c.get('export_url')})
    return out


def _history_contributions():
    """campaign-contributions-history: every gift from an organization to a 2016-2025 local campaign. No individuals, no bank interest."""
    h = _j('campaign', 'campaign_history.json')
    return [{'election_year': c['year'], 'election': c['election'], 'gov_id': c['gov_id'], 'office': c['office'], 'candidate': c['name'], 'outcome': c.get('outcome'),
             'contributor': x.get('name'), 'contributor_type': x.get('type'), 'city': x.get('city'), 'amount': x.get('amount'), 'date': x.get('date'), 'kind': x.get('kind'),
             'report_url': c.get('report_url')}
            for c in (h or {}).get('candidates') or [] for x in c.get('contributors') or []
            if x.get('type') not in ('candidate', 'individual', 'self') and x.get('kind') != 'interest']


def _officials_pay(f):
    """A row with no name is a whole board's pay (e.g. 'Mayor and 4 Commissioners (combined)' or 'each of 5'): say so."""
    out = _flat(f['pay'], ['government', 'title', 'name', 'annual', 'year', 'basis', 'source_url'])
    for r in out:
        t = r.get('title') or ''
        r['row_type'] = 'person' if r.get('name') else ('board_each_member' if re.search(r'\beach\b', t, re.I) else 'board_total')
        if not r.get('name'):
            r['name'] = 'Board total (all members combined)' if r['row_type'] == 'board_total' else 'Each board member (not named)'
    return out


def schedule_by_project():
    """GIS project index -> county program schedule lines matched to it (data/surtax/schedule_matches.json)."""
    m = _j('surtax', 'schedule_matches.json') or {'matches': []}
    out = {}
    for x in m['matches']:
        out.setdefault(x['project_index'], []).append(x)
    return out


def _surtax_rows(ts):
    rows = _flat(ts['infra_surtax']['projects'], ['name', 'government', 'category', 'status', 'pct_complete', 'promised_cost', 'programmed_cost', 'actual_cost', 'fiscal_years', 'location', 'lat', 'lng', 'description', 'source_url'])
    sb = schedule_by_project()
    for i, r in enumerate(rows):
        xs = sb.get(i, [])
        r['schedule_programmed_total'] = sum(x['programmed_total'] or 0 for x in xs) if xs else None
        r['schedule_fy_amounts'] = {k: v for x in xs for k, v in (x['fy_amounts'] or {}).items()} if xs else None
        r['schedule_line'] = '; '.join(x['schedule_name'] for x in xs) or None
        r['schedule_match_method'] = '; '.join(x['method'] for x in xs) or None
        r['schedule_source_url'] = xs[0]['source_url'] if xs else None
    return rows


def _exemptions():
    d = _j('exemptions', 'exemptions_2026.json')
    if not d:
        return []
    return [{'code': k, 'exemption': v['name'], 'statute': v['statute'], 'applies_to': v['applies'], 'parcels': v['parcels'], 'homesteads': v['homes'],
             'value_exempted': v['value'], 'estimated_tax_removed': v['tax'], 'roll': d.get('roll'), 'source_url': d.get('source')} for k, v in d['codes'].items()]


def _acc(kind):
    from accountability_page import build, RULES
    rt = {r['id']: r['title'] for r in RULES}
    P = build()['projects']
    if kind == 'projects':
        return [{'project_id': p['id'], 'project': p['n'], 'government': p['g'], 'agency': p.get('agency'), 'kind': p['src'], 'stage': p['status'],
                 'first_figure': (p.get('base') or {}).get('a'), 'first_figure_is': (p.get('base') or {}).get('t'), 'latest_figure': (p.get('now') or {}).get('a'),
                 'latest_figure_is': (p.get('now') or {}).get('t'), 'growth_pct': p.get('growth'), 'project_total': (p.get('total') or {}).get('a'),
                 'flags': ' | '.join(f"{rt[f['r']]} ({f['sev']}): {f['note']}" for f in p['flags']), 'records_missing': ' | '.join(g['q'] for g in p['gaps']),
                 'agency_reply': p['reply']['status'], 'first_date': p.get('first'), 'last_date': p.get('last')} for p in P]
    return [{'project_id': p['id'], 'project': p['n'], 'government': p['g'], 'date': x.get('d'), 'sort_date': x.get('s'), 'event': x['k'], 'amount': x.get('a'),
             'approximate': bool(x.get('approx')), 'description': x['t'], 'paid_to': x.get('payee'), 'news_report': bool(x.get('news')), 'source_url': x.get('u')}
            for p in P for x in p['ev']]


def datasets():
    ct = _j('contracts', 'contracts.json'); da = _j('debt_audit', 'debt_audit.json'); f = _j('fees', 'fees_pay_officials.json')
    ts = _j('tourism', 'tourism_surtax.json'); pa = _j('michael', 'pa_ledger.json')
    D = [
        ('government-profiles', 'Government profiles', 'One row per government: population, budget, tax rate, debt, audit findings, votes, staff, utility bill and Hurricane Michael money.', _profiles),
        ('votes', 'Recorded votes', 'Votes by the County Commission, School Board, city commissions and CRA boards since 2016, with how each member voted: hand-researched money votes plus every motion read from the official minutes.', _votes),
        ('member-votes', 'Votes by member', 'One row per member per vote (long format), for tallying individual records.', _member_votes),
        ('contracts', 'Contracts', 'Major contracts approved since October 2022: vendor, amount, purpose, how awarded.', lambda: _flat(ct['contracts'], ['government', 'vendor', 'amount', 'purpose', 'date', 'method', 'source_title', 'source_url', 'notes'])),
        ('change-orders', 'Change orders', 'Contract change orders with original and new totals.', lambda: _flat(ct['change_orders'], ['government', 'vendor', 'project', 'original_amount', 'change_amount', 'new_total', 'pct_of_original', 'reason', 'date', 'source_url'])),
        ('emergency-purchases', 'Emergency purchases', 'Purchases made under emergency rules without normal bidding.', lambda: _flat(ct.get('emergency_purchases') or [], ['government', 'vendor', 'amount', 'purpose', 'date', 'basis', 'source_url'])),
        ('cra-payments', 'CRA spending', 'What Bay County\'s Community Redevelopment Agencies paid for, with locations.', _cra),
        ('property-tax-rates', 'Property tax rates', 'Millage, rolled-back rate and levy for every taxing authority, by tax year.', _rates),
        ('debt', 'Debt by government', 'Total debt from the latest audited financial statements.', lambda: _flat(da['debt'], ['government', 'fy', 'total_debt', 'total_debt_note', 'population_2025_estimate', 'source_url'])),
        ('audit-findings', 'Audit findings', 'Findings from audits filed with the Florida Auditor General, in plain English.', lambda: [{'government': a['government'], 'fy': a.get('fy'), 'opinion': a.get('opinion'), 'finding': x.get('title'), 'plain_english': x.get('plain'), 'repeat': x.get('repeat'), 'management_response': x.get('mgmt_response'), 'source_url': x.get('source_url') or a.get('source_url')} for a in da['audits'] for x in a.get('findings') or []]),
        ('fema-michael-projects', 'Hurricane Michael FEMA projects', 'Every FEMA Public Assistance project in Bay County for disaster DR-4399.', lambda: [{'applicant': r['a'], 'project': r['pw'], 'title': r['t'], 'category': r['c'], 'federal_share': r['f'], 'eligible_amount': r['e'], 'first_obligated': r.get('d1'), 'last_obligated': r.get('d2'), 'status': r.get('st'), 'size': r.get('sz')} for r in pa['rows']]),
        ('sales-tax-projects', 'Half-cent sales tax projects', "Every infrastructure sales tax project on the county map, with status and cost. schedule_* columns add the county program schedule's programmed dollars by year where the schedule line could be matched to the project.", lambda: _surtax_rows(ts)),
        ('bed-tax-collections', 'Tourist tax collections', 'Bed tax collected by zone and fiscal year.', lambda: _flat(ts['bed_tax']['collections'], ['fy', 'district', 'amount', 'partial', 'period', 'basis', 'source_url'])),
        ('fees-assessments', 'Fees on tax bills', 'Non-ad valorem assessments: fire, stormwater, CRA and other flat fees.', lambda: _flat(f['assessments'], ['government', 'area', 'name', 'category', 'how_charged', 'rate', 'residential_single_family_amount', 'fiscal_year', 'source_url'])),
        ('officials-pay', 'Officials and pay', 'Salaries of top elected and appointed officials. Rows with row_type board_total are a whole board\'s combined pay, not one person.', lambda: _officials_pay(f)),
    ]
    extra = [
        (('meetings', 'meetings.json'), 'meetings', 'Upcoming meetings', 'Scheduled and expected meetings for every board.', lambda d: d.get('meetings', [])),
        (('campaign', 'campaign.json'), 'campaign-finance', 'Campaign finance totals', 'Money raised by current officeholders (organizations named; individuals summed).', lambda d: [{k: c.get(k) for k in ('official', 'office', 'gov', 'election', 'total_raised', 'total_spent', 'n_contributions', 'report_url')} for c in d.get('candidates', [])]),
        (('money', 'payments.json'), 'vendor-payments', 'Who gets paid', 'Payments to vendors from check registers, totaled by vendor and year.', lambda d: [{'government': g.get('name'), 'vendor': v.get('vendor'), 'total': v.get('total'), 'payments': v.get('n_payments')} for g in d.get('governments', []) for v in g.get('vendors', [])]),
        (('money', 'bonds.json'), 'bonds', 'Bonds and notes', 'Outstanding bond and note issues of Bay County governments.', lambda d: d.get('issues', [])),
        (('civic', 'budgets_detail.json'), 'budget-per-resident', 'Budget cost per resident, by service', 'FY2026 General Fund budget per resident for police, fire, streets, parks, libraries, planning and administration, with the city median. Departments are grouped by name; the departments_included column shows what was added together. Schools are not included.', lambda d: __import__('money_pages').per_resident_rows()),
        (('civic', 'budgets_detail.json'), 'budget-detail', 'Budgets by fund and department', 'Adopted budgets broken down by fund and general-fund department.', lambda d: [{'government': g.get('name'), 'fiscal_year': g.get('fiscal_year'), 'level': lvl, 'name': x.get('name'), 'amount': x.get('amount')} for g in d.get('governments', []) for lvl, key in (('fund', 'funds'), ('department', 'general_fund_departments')) for x in g.get(key) or []]),
    ]
    extra += [
        (('salaries', 'bocc.json'), 'salary-positions', 'Public salaries by job title', 'Pay ranges, budgeted positions and unnamed actual salaries by job title for the county, constitutional officers, school district, cities, airport and port. Rows with fte_only = true are positions the source counts but gives no pay for (see pay_status).', lambda d: _salaries('positions')),
        (('salaries', 'bocc.json'), 'salary-leaders', 'Salaries of officials and leaders', 'Named salaries of elected officials and top appointed leaders only.', lambda d: _salaries('leaders')),
        (('elections', 'candidates_2026.json'), 'candidates-2026', '2026 local candidates', 'Every 2026 local race and candidate with status, platform in their own words and campaign money totals.', lambda d: _candidates()),
        (('elections', 'finance_2026.json'), 'campaign-contributions-2026', '2026 contributions from organizations', 'Every contribution from a business, committee or party to a 2026 local candidate. Individual donors are not included, and neither is bank interest on campaign accounts.', lambda d: _contributions()),
        (('campaign', 'campaign_history.json'), 'campaign-history', 'Local campaigns since 2016', 'Every candidate who opened a campaign account with the Bay County Supervisor of Elections for a local race from 2016 through 2025, winners and losers: what each raised and spent, and how much came from individuals (summed, never named), businesses, committees, parties and the candidate. The 2026 races are in candidates-2026.', lambda d: _history()),
        (('campaign', 'campaign_history.json'), 'campaign-contributions-history', 'Contributions from organizations, 2016-2025', 'Every contribution from a business, committee or party to a local candidate in the 2016 to 2025 elections, as filed. Individual donors are not included, and neither is bank interest on campaign accounts.', lambda d: _history_contributions()),
        (('exemptions', 'exemptions_2026.json'), 'property-tax-exemptions', 'Property tax exemptions (2026 roll)', 'Every exemption type on the 2026 tax roll: parcels, value exempted and estimated tax removed.', lambda d: _exemptions()),
    ]
    D += [('accountability-projects', 'Accountability: projects', 'One row per project on the Accountability console: stage, first and latest figures, cost growth, questions raised by the published rules, records still missing and the agency reply.', lambda: _acc('projects')),
          ('accountability-events', 'Accountability: project timelines', 'Every dated event in each project timeline: budgets, approvals, awards, change orders, votes, payments and completion, with sources.', lambda: _acc('events'))]
    from page_datasets import DATASETS as PAGE_DATASETS  # pages whose data used to live only in the page or the app files
    D += PAGE_DATASETS
    for path, did, title, desc, fn in extra:
        d = _j(*path)
        if d:
            D.append((did, title, desc, (lambda d, fn: (lambda: fn(d)))(d, fn)))
    return D


def write_downloads(out_dir):
    from page_datasets import DB_ONLY_COLUMNS  # datasets whose rows are written to the database directly
    dest = os.path.join(out_dir, 'downloads'); os.makedirs(dest, exist_ok=True)
    meta, catalog = [], []
    for did, title, desc, fn in datasets():
        rows = add_gov_id(did, fn() or [])
        keys = list(dict.fromkeys(k for r in rows for k in r)) or list(DB_ONLY_COLUMNS.get(did, []))
        buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=keys, extrasaction='ignore'); w.writeheader()
        for r in rows:
            w.writerow({k: ('; '.join(map(str, v)) if isinstance(v, list) else json.dumps(v) if isinstance(v, dict) else v) for k, v in r.items()})
        open(os.path.join(dest, did + '.csv'), 'w', newline='').write(buf.getvalue())
        json.dump(rows, open(os.path.join(dest, did + '.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
        meta.append((did, title, desc, len(rows), keys, os.path.getsize(os.path.join(dest, did + '.csv'))))
        def typ(k):
            vals = [r.get(k) for r in rows if r.get(k) is not None][:200]
            if not vals: return DB_ONLY_COLUMNS.get(did, {}).get(k, 'string')
            if all(isinstance(v, bool) for v in vals): return 'boolean'
            if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals): return 'number'
            if all(isinstance(v, list) for v in vals): return 'array'
            if all(isinstance(v, dict) for v in vals): return 'object'
            return 'string'
        def col(k):
            c = {'name': k, 'type': typ(k)}
            vals = {r.get(k) for r in rows if isinstance(r.get(k), (str, bool)) and r.get(k) != ''}
            if c['type'] in ('string', 'boolean') and 0 < len(vals) <= 30 and len(rows) > len(vals):
                c['values'] = sorted(vals, key=str)
            return c
        catalog.append({'id': did, 'title': title, 'description': desc, 'rows': len(rows), 'columns': [col(k) for k in keys],
                        'json': f'/downloads/{did}.json', 'csv': f'/downloads/{did}.csv', 'api': f'/api/v1/datasets/{did}'})
    if DROPPED_BEFORE_FIRST_YEAR:
        print(f'open data: rows before {cutoff.FIRST_YEAR} dropped at the last check (leave them out at ingestion):', DROPPED_BEFORE_FIRST_YEAR, file=__import__('sys').stderr)
    import datetime
    json.dump({'name': 'BayCounty.me open data', 'updated': datetime.date.today().isoformat(), 'license': 'Public records; free to reuse with credit to BayCounty.me',
               'datasets': catalog}, open(os.path.join(dest, 'index.json'), 'w'), ensure_ascii=False, indent=1)
    return meta


def opendata_page(out_dir):
    meta = write_downloads(out_dir)
    rows = ''.join(f'''<tr><th scope="row"><b>{e(t)}</b><small>{e(d)}</small><details class="flds"><summary>{len(k)} columns</summary><p class="small muted">{e(", ".join(k))}</p></details></th>
      <td class="num">{n:,}</td><td class="dl"><a href="/downloads/{i}.csv" download>CSV</a> <span class="muted small">{sz/1024:,.0f} KB</span> · <a href="/downloads/{i}.json" download>JSON</a></td></tr>''' for i, t, d, n, k, sz in meta)
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Open data</span><h1>Download the data</h1>
    <p class="lede">Everything on BayCounty.me, as spreadsheets. Free to use for reporting, research or your own analysis. Please credit BayCounty.me, and check the original record before relying on any single figure: every row carries its source link.</p></div></header>
  <div class="tablewrap"><table class="tx-table od-table"><thead><tr><th scope="col">Dataset</th><th scope="col" class="num">Rows</th><th scope="col">Download</th></tr></thead><tbody>{rows}</tbody></table></div>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="notes">Notes</h2></div><ul class="plain">
    <li>CSV files open in Excel, Google Sheets or Numbers. JSON is the same data for programmers. To filter and query the data from your own app or AI assistant, use the <a href="/developers">API</a>.</li>
    <li>Files are rebuilt every time the site's data changes. The <a href="/updates">What's new</a> page lists each change.</li>
    <li>Found an error? <a href="/about#contact">Send a correction</a>.</li></ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">'''
