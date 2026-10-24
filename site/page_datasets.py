"""Datasets for pages whose data used to live only inside the page (or only in the app's /data/app files).

Every page's data is published as an open-data dataset so it reaches the database (db/scripts/load.py) and the API
(/api/v1/datasets/<id>). Rows are flat, one record per row, with plain column names. Same privacy rules as the site:
individual campaign donors are never named (they appear only as summed totals), and grant programs' unnamed
recipients stay grouped.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


# --- Connections (/connections) ----------------------------------------------------------------------------------------

def _network():
    from connections import network_data
    return network_data()


KIND = {'biz': 'business', 'gov': 'government', 'prop': 'property owner', 'unnamed': 'payee not named', 'grants': 'grant recipients (grouped)'}
PAYER_KIND = {'gov': 'government', 'cra': 'redevelopment agency', 'tourism': 'tourism agency'}


def cra_payee_ids():
    """payee_entity_id for each cra-payments row (same order as data/merged.json payments), or None.
    The ids are the Connections payee ids (connections-payees.entity_id)."""
    import json
    from connections import _entity, CRA_CODE, DATA
    M = json.load(open(os.path.join(DATA, 'merged.json')))
    V = {v['id']: v for v in json.load(open(os.path.join(DATA, 'entities', 'vendors.json')))['vendors']}
    out = []
    for p in M['payments']:
        code = CRA_CODE.get(p['cra'])
        out.append(_entity(p, code, V)[0] if code else None)
    return out


def _payer_gov(D, pk):
    return pk[2:] if pk.startswith('g:') else D['payers'][pk]['g']


def connections_payees():
    D = _network()
    gave = {d['e'] for d in D['don'] if d['e']}
    agg = {}
    for r in D['recs']:
        a = agg.setdefault(r['e'], {'payers': [], 'types': [], 'records': 0, 'total': 0.0})
        if r['p'] not in a['payers']:
            a['payers'].append(r['p'])
        if r['t'] not in a['types']:
            a['types'].append(r['t'])
        a['records'] += 1
        a['total'] += r['a'] or 0
    rows = []
    for key, e in D['ents'].items():
        a = agg.get(key, {'payers': [], 'types': [], 'records': 0, 'total': 0.0})
        rows.append({'entity_id': key, 'name': e['n'], 'kind': KIND.get(e['k'], e['k']), 'subconsultant_only': bool(e.get('sub')),
                     'paid_by': [D['payers'][p]['n'] for p in a['payers']], 'record_types': [D['types'][t] for t in a['types']],
                     'records': a['records'], 'dollars_in_records': round(a['total'], 2), 'gave_to_campaigns': key in gave,
                     'vendor_page': f"/public-money/vendors/{e['vp']}" if e.get('vp') else None, 'nonprofit_id': e.get('np')})
    rows.sort(key=lambda r: (-r['dollars_in_records'], r['name']))
    return rows


def connections_payments():
    D = _network()
    return [{'record_id': r['id'], 'payer_id': r['p'], 'payer': D['payers'][r['p']]['n'], 'payer_kind': PAYER_KIND[D['payers'][r['p']]['k']],
             'payer_gov_id': _payer_gov(D, r['p']), 'entity_id': r['e'], 'payee': D['ents'][r['e']]['n'], 'record_type': D['types'][r['t']],
             'amount': r['a'], 'date': r['when'] or None, 'what': r['w'] or None, 'cra_status': r.get('s'),
             'inside_project_total': bool(r.get('x')), 'source_url': D['urls'][r['u']] if r.get('u') is not None else None} for r in D['recs']]


def connections_links():
    D = _network()
    return [{'entity_a': x['a'], 'name_a': D['ents'][x['a']]['n'], 'entity_b': x['b'], 'name_b': D['ents'][x['b']]['n'],
             'connection': x['t'], 'source_url': x['u']} for x in D['rel']]


def connections_gifts():
    D = _network()
    out = []
    for d in D['don']:
        o = D['off'][d['o']]
        out.append({'donor': d['dn'], 'donor_type': d['ty'], 'official': o['n'], 'office': o['off'], 'official_gov_id': o['gid'] or None,
                    'candidate_2026': o['cand'], 'sits_on': [D['payers'][p]['n'] for p in o['gp']] or None,
                    'amount': d['a'], 'gifts': d['n'], 'dates': d['date'] or None, 'payee_entity_id': d['e'], 'match_confidence': d['cf'],
                    'report_url': D['urls'][d['u']] if d.get('u') is not None else None, 'as_of': D.get('as_of')})
    return out


# --- Money map (/connections/money-map) -------------------------------------------------------------------------------

def _mm():
    from money_map import map_data
    return map_data()


def money_map_gifts():
    M = _mm()
    O, Dn = {o['id']: o for o in M['officials']}, {d['id']: d for d in M['donors']}
    return [{'donor': Dn[g['d']]['n'], 'donor_type': Dn[g['d']]['t'], 'official': O[g['o']]['n'], 'office': O[g['o']]['off'], 'gov': O[g['o']]['g'],
             'amount': g['a'], 'dates': g['dates'] or None, 'donor_holds_contracts_here': g['same'],
             'official_total_raised': O[g['o']]['raised'], 'official_from_individuals': O[g['o']]['ind'],
             'official_individual_gifts': O[g['o']]['indn'], 'report_url': O[g['o']]['url']} for g in M['gifts']]


def money_map_contracts():
    M = _mm()
    Dn = {d['id']: d for d in M['donors']}
    return [{'donor': Dn[c['d']]['n'], 'donor_type': Dn[c['d']]['t'], 'gov': c['g'], 'government': M['govs'].get(c['g']),
             'awarded_total': c['a'], 'paid_total': c['p'], 'awards': c['n'], 'other_records': c['co'], 'records': c['items'],
             'source_urls': c['urls'], 'likely_match_only': c['likely'], 'vendor': c['ent']} for c in M['contracts']]


def money_map_votes():
    M = _mm()
    O, Dn = {o['id']: o for o in M['officials']}, {d['id']: d for d in M['donors']}
    return [{'donor': Dn[v['d']]['n'], 'official': O[v['o']]['n'], 'office': O[v['o']]['off'], 'gov': O[v['o']]['g'], 'gift_amount': v['gift'],
             'gift_dates': v['gift_dates'] or None, 'vote_date': v['date'], 'item': v['h'], 'amount': v['amount'], 'vote': v['vote'],
             'outcome': v['outcome'], 'tally': v['tally'], 'consent_agenda': v['consent'], 'gift_before_or_after_vote': v['when'],
             'source_url': v.get('url')} for v in M['votes']]


# --- App-only reference data -----------------------------------------------------------------------------------------

def site_updates():
    from app_data import updates
    return [{'date': u['date'], 'title': u['title'], 'text': u['text'], 'pages': u['pages'] or None} for u in updates()]


def glossary_terms():
    from app_data import glossary
    g = glossary()
    names = {x['id']: x['name'] for x in g['groups']}
    return [{'term_id': t['id'], 'group_id': t['group'], 'group_name': names.get(t['group']), 'term': t['term'], 'simple': t.get('simple'),
             'more': t.get('more'), 'example': t.get('example')} for t in g['terms']]


def people_directory():
    from app_data import people
    return [{'person_id': p['id'], 'name': p['name'], 'district': p['district'], 'gov_ids': p['gov_ids'] or None, 'roles': p['roles'] or None}
            for p in people()['people']]


def vendors_directory():
    from app_data import vendors
    return [{'vendor_id': v['id'], 'name': v['name'], 'aliases': v['aliases'] or None, 'gov_ids': v['gov_ids'] or None,
             'records': v['records'] or None, 'vendor_type': v['type'], 'page': v['page']} for v in vendors()['vendors']]


def donor_contracts():
    from app_data import donor_contracts as dc
    return [{k: (v if v not in ([], '') else None) for k, v in m.items()} for m in dc()['matches']]


def tax_districts():
    """Which taxing authorities levy in each tax district (My Address, tax calculator); rates are in property-tax-rates."""
    from addr_page import address_data
    a = address_data()
    codes = {}
    for code, name in a['taxdist'].items():
        codes.setdefault(name, set()).add(code.lstrip('0') or '0')
    return [{'district': k, 'label': d['label'], 'authority_ids': d['stack'], 'total_millage': d['total'],
             'tax_district_codes': sorted(codes.get(k, ()), key=int) or None}
            for k, d in a['districts'].items()]


# --- Savings finder (/public-money/savings) ----------------------------------------------------------------------------

def savings_opportunities():
    from savings_page import opportunity_rows
    return opportunity_rows()


def savings_evidence():
    from savings_page import evidence_rows
    return evidence_rows()


# --- Government profile pages (/governments/<slug>): the top cards, one row per government per fiscal year ----------

def _fy(text):
    """'FY2025', 'FY2025 (2024-25)', 'FY2025-26' -> the year the fiscal year ends in."""
    import re
    m = re.search(r'FY\s?(\d{4})(?:\s?-\s?(\d{2,4}))?', str(text or ''))
    if not m:
        return None
    y = int(m.group(1))
    if m.group(2):
        e = int(m.group(2))
        e = e + 2000 if e < 100 else e
        if e == y + 1:  # 'FY2025-26' names both calendar years
            y = e
    return y


def _budget_status(text):
    s = str(text or '').strip().lower()
    for pre, lbl in (('adopted', 'adopted'), ('final approved', 'adopted'), ('final hearing', 'final hearing held'), ('amended', 'amended'),
                     ('tentative', 'tentative'), ('total is the tentative', 'tentative'), ('draft', 'draft'), ('approximate', 'approximate'),
                     ('county-funded', 'county-funded share')):
        if s.startswith(pre):
            return lbl
    return 'adopted' if 'adopted' in s and 'not' not in s else ('on file' if s else 'adopted')


def government_years():
    """Budget, tax rate, audited actuals, residents, debt and staff for each government in each fiscal year on record.

    One row per government per fiscal year. A blank value means no record for that year (never carried over from
    another year). fiscal_year is the year the fiscal year ends in (FY2026 = Oct 2025 to Sep 2026; schools Jul to Jun).
    """
    import json
    from govs import GOVS
    D = os.path.join(HERE, '..', 'data')
    J = lambda *p: json.load(open(os.path.join(D, *p)))
    bud = {g['id']: g for g in J('tax', 'budgets.json')['governments']}
    fin = {g['id']: g for g in J('tax', 'finances.json')['governments']}
    mil = {a['id']: a for a in J('tax', 'millage.json')['authorities']}
    da = J('debt_audit', 'debt_audit.json')
    fees = {g['name']: g for g in J('fees', 'fees_pay_officials.json')['governments']}
    pop = J('civic', 'population.json')
    from place import NAME as PLACE_NAME
    out = []
    for g in GOVS:
        rows = {}
        row = lambda y: rows.setdefault(y, {})
        b = bud.get(g['tax']) or {}
        # budgets: history, FY2026, FY2027
        entries = [(h.get('fy'), h, h.get('note') or 'adopted') for h in b.get('history') or []]
        entries += [('FY2026', b.get('fy2026') or {}, (b.get('fy2026') or {}).get('status')), ('FY2027', b.get('fy2027') or {}, (b.get('fy2027') or {}).get('status'))]
        for fy, x, st in entries:
            y = _fy(fy)
            tot = x.get('total_budget') or x.get('total_budget_less_transfers') or x.get('total_budget_less_interfund_transfers')
            if not y or not (tot or x.get('general_fund')):
                continue
            r = row(y)
            r.update({'budget_total': round(tot) if tot else None, 'general_fund': round(x['general_fund']) if x.get('general_fund') else None,
                      'budget_status': _budget_status(st), 'budget_note': str(st or '')[:300] or None,
                      'budget_excludes_transfers': bool(not x.get('total_budget') and tot),
                      'budget_source_url': x.get('source_url')})
            if isinstance(x.get('millage'), (int, float)):  # the budget's own rate; replaced below by the state's figure where there is one
                r.update({'millage': x['millage'], 'millage_source_url': x.get('source_url')})
            if x.get('employees_fte'):
                r.update({'employees_fte': x['employees_fte'], 'employees_note': x.get('employees_fte_note'), 'employees_source_url': x.get('source_url')})
            elif (x.get('employees_positions') or {}).get('total'):
                r.update({'employees_fte': x['employees_positions']['total'], 'employees_note': x['employees_positions'].get('note'), 'employees_source_url': x.get('source_url')})
        # property tax rate (tax year T pays for FY T+1)
        for t in (mil.get(g['auth']) or {}).get('years') or [] if g.get('auth') else []:
            y = _fy(t.get('fiscal_year')) or (t['tax_year'] + 1)
            if t.get('millage') is None:
                continue
            row(y).update({'tax_year': t['tax_year'], 'millage': t['millage'], 'rolled_back_rate': t.get('rolled_back'), 'property_tax_levy': t.get('levy'),
                           'millage_source_url': t.get('source_url')})
        # audited actuals (state Local Government Financial Reports) and residents that year
        for a in (fin.get(g['tax']) or {}).get('years') or []:
            y = _fy(a['fy'])
            r = row(y)
            r.update({'actual_revenue': round(a['revenue_total']) if a.get('revenue_total') else None,
                      'actual_spending': round(a['expenditure_total_excl_transfers']) if a.get('expenditure_total_excl_transfers') else None,
                      'actuals_source_url': a.get('expenditure_source_url') or a.get('revenue_source_url') or a.get('source_url')})
            if a.get('population'):
                r.update({'population': a['population'], 'population_year': y, 'population_source': 'State population used in the audited financial report'})
        # residents: the April 1, 2025 state estimate counts for FY2025 on; earlier years only from the yearly reports above
        nm = PLACE_NAME if g['kind'] in ('county', 'schools') else g['short']
        est = ((pop.get('places') or {}).get(nm) or {}).get('est')
        if est:
            for y in [y for y in rows if y >= 2025]:
                if not rows[y].get('population'):
                    rows[y].update({'population': est, 'population_year': 2025, 'population_source': pop.get('source_url')})
        # debt: audited total for the fiscal year the audit covers
        d = next((x for x in da['debt'] if g.get('debt') and x['government'].startswith(g['debt'])), None)
        if d and d.get('total_debt') and _fy(d.get('fy')):
            row(_fy(d['fy'])).update({'debt_total': d['total_debt'], 'debt_source_url': d.get('source_url')})
        # staff count from the officials file, in the year its source names
        ft = (fees.get(g.get('fees')) or {}).get('ftes')
        if isinstance(ft, dict) and ft.get('value') and _fy(ft.get('detail')):
            r = row(_fy(ft['detail']))
            if not r.get('employees_fte'):
                r.update({'employees_fte': ft['value'], 'employees_note': ft.get('detail'), 'employees_source_url': ft.get('source_url')})
        start = 7 if g['kind'] == 'schools' else 10
        for y in sorted(rows):
            r = rows[y]
            per = round(r['budget_total'] / r['population']) if r.get('budget_total') and r.get('population') and g['kind'] != 'schools' else None
            out.append({'gov_id': g['key'], 'government': g['name'], 'fiscal_year': y, 'fy': f'FY{y}',
                        'period': f"{['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][start]} {y - 1} to {['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][start - 1]} {y}",
                        **{k: r.get(k) for k in ('budget_total', 'general_fund', 'budget_status', 'budget_note', 'budget_excludes_transfers', 'budget_source_url',
                                                 'tax_year', 'millage', 'rolled_back_rate', 'property_tax_levy', 'millage_source_url',
                                                 'actual_revenue', 'actual_spending', 'actuals_source_url', 'population', 'population_year', 'population_source',
                                                 'debt_total', 'debt_source_url', 'employees_fte', 'employees_note', 'employees_source_url')},
                        'budget_per_resident': per, 'source_url': r.get('budget_source_url') or r.get('actuals_source_url') or r.get('millage_source_url')})
    return out


# --- Business donors matched to the state corporate registry (data/sunbiz) ----------------------------------------

def business_donor_sunbiz():
    """Business campaign contributors matched to Sunbiz entities, every county with a build. Business-level only:
    no officer, owner or agent names and no addresses (those stay in the private registry schema)."""
    import glob, json
    rows = []
    for fp in sorted(glob.glob(os.path.join(HERE, '..', 'data', 'sunbiz', '*', 'business_donor_sunbiz.json'))):
        rows += json.load(open(fp))['rows']
    return rows


# Shared-owner groups: rows are written to the database by registry.publish_group() when an admin confirms a group
# (migration 0032), not by the site build, so the published file is empty and the columns are listed here.
SHARED_OWNER_COLUMNS = ['group_id', 'candidate', 'office', 'election', 'business', 'sunbiz_doc_number', 'business_status', 'business_amount',
                        'business_dates', 'group_businesses', 'group_checks', 'group_total', 'all_checks_1000', 'same_day', 'shared_people',
                        'county', 'source_url', 'campaign_report_url', 'gov_id', 'business_last_filed']
_NUM = {'business_amount', 'group_businesses', 'group_checks', 'group_total', 'shared_people', 'business_last_filed'}
DB_ONLY_COLUMNS = {'shared-owner-groups': {c: ('number' if c in _NUM else 'boolean' if c in ('all_checks_1000', 'same_day') else 'string')
                                           for c in SHARED_OWNER_COLUMNS}}


def shared_owner_groups():
    return []


# --- Nonprofits (data/nonprofits): organizations, money and board members (public IRS and state filings) ----------

def _nonprofit_files(part):
    import glob, json
    rows = []
    for fp in sorted(glob.glob(os.path.join(HERE, '..', 'data', 'nonprofits', '*', 'nonprofits.json'))):
        rows += json.load(open(fp)).get(part, [])
    return rows


def nonprofits():
    return _nonprofit_files('nonprofits')


def nonprofit_payments():
    return _nonprofit_files('payments')


def nonprofit_grants():
    return _nonprofit_files('grants')


def nonprofit_board_members():
    return _nonprofit_files('board_members')


def nonprofit_board_businesses():
    return _nonprofit_files('board_businesses')


# Florida charitable solicitation registrations (FDACS Check-A-Charity, data/nonprofits/fetch_fdacs.py). Column types
# are listed so the table and catalog stay right in a county with no registrations fetched yet.
CHARITY_REGISTRATION_COLUMNS = {c: 'string' for c in (
    'registration_number', 'nonprofit_id', 'name', 'dba', 'fein', 'matched_by', 'status', 'status_detail', 'registration_date', 'expiration_date',
    'city', 'zip', 'website', 'fiscal_year_end')}
CHARITY_REGISTRATION_COLUMNS.update({c: 'number' for c in (
    'total_revenue', 'contributions', 'government_grants', 'program_expenses', 'fundraising_expenses', 'management_expenses', 'total_expenses',
    'program_percent', 'fundraising_percent')})
CHARITY_REGISTRATION_COLUMNS.update({'fundraising_consultants': 'string', 'officers_listed': 'number', 'other_registrations': 'string', 'county': 'string',
                                     'source_url': 'string'})
DB_ONLY_COLUMNS['charity-registrations'] = CHARITY_REGISTRATION_COLUMNS


def charity_registrations():
    return _nonprofit_files('charity_registrations')


# Officials on nonprofit boards: written by registry.publish_board_officials() when an admin confirms a name match
# (migration 0034), not by the site build.
NONPROFIT_OFFICIAL_COLUMNS = ['official_id', 'person_id', 'official', 'official_roles', 'nonprofit_id', 'nonprofit', 'ein', 'titles', 'first_year', 'last_year',
                              'current', 'sources', 'county', 'source_url', 'gov_id']
DB_ONLY_COLUMNS['nonprofit-officials'] = {c: ('number' if c in ('first_year', 'last_year') else 'boolean' if c == 'current' else 'string')
                                          for c in NONPROFIT_OFFICIAL_COLUMNS}


def nonprofit_officials():
    return []


# Officials' business ties: rows are written by careers.publish() when an admin confirms a match (migration 0033).
OFFICIAL_BUSINESS_COLUMNS = {'person_id': 'string', 'official': 'string', 'official_role': 'string', 'business': 'string', 'sunbiz_doc_number': 'string',
                             'titles': 'string', 'role_kind': 'string', 'business_status': 'string', 'filing_type': 'string', 'nonprofit': 'boolean',
                             'principal_city': 'string', 'filed_date': 'string', 'closed_year': 'number', 'role_first_seen': 'string',
                             'county': 'string', 'source_url': 'string', 'gov_id': 'string'}
OFFICIAL_LINK_COLUMNS = {'link_type': 'string', 'person_id': 'string', 'official': 'string', 'other_person_id': 'string', 'other_official': 'string',
                         'candidate': 'string', 'office': 'string', 'business': 'string', 'sunbiz_doc_number': 'string', 'related_business': 'string',
                         'related_doc_number': 'string', 'shared_people': 'number', 'payer': 'string', 'own_government': 'boolean', 'self_gift': 'boolean',
                         'amount': 'number', 'items': 'number', 'first_date': 'string', 'last_date': 'string', 'detail': 'string', 'county': 'string',
                         'source_url': 'string', 'report_url': 'string', 'gov_id': 'string'}
DB_ONLY_COLUMNS['official-businesses'] = OFFICIAL_BUSINESS_COLUMNS
DB_ONLY_COLUMNS['official-business-links'] = OFFICIAL_LINK_COLUMNS


def official_businesses():
    return []


def official_business_links():
    return []


# --- Entity profiles (site/entity_graph.py): every named entity and every documented connection -----------------------

def entity_profiles():
    from entity_graph import profile_rows
    return profile_rows()


def entity_connections():
    from entity_graph import connection_rows
    return connection_rows()


DATASETS = [
    ('connections-payees', 'Connections: payees', 'Every payee in the payment records of every local government and agency (contracts, change orders, emergency purchases, check registers, tourism agency payments and the CRA ledger) as one entity, with who paid it and whether it gave to a campaign. dollars_in_records adds every record, and an award and the payments on it can both be records, so it is not a deduplicated total. Unnamed grant recipients are grouped.', connections_payees),
    ('connections-payments', 'Connections: payment records', 'One row per payment record behind the Connections network: which government or agency paid which payee, the record type, amount, date and source. CRA ledger items that are only proposed or planned are not included.', connections_payments),
    ('connections-links', 'Connections: documented links', 'Documented links between payees that are not payments (shared project, address or subcontract), each with its source.', connections_links),
    ('connections-gifts', 'Connections: business gifts to officials', 'Gifts from businesses, PACs and committees to current officeholders and 2026 candidates, one row per donor and official, with the payee id when the donor was also paid by a local government. Individual donors are never included.', connections_gifts),
    ('money-map-gifts', 'Money map: gifts to officials', 'Gifts from businesses and committees to each current officeholder, and whether the donor holds contracts with that official\'s government. Individuals appear only as totals.', money_map_gifts),
    ('money-map-contracts', 'Money map: donor contracts', 'Contracts, awards and payments held by campaign donors, per donor and government.', money_map_contracts),
    ('money-map-votes', 'Money map: votes on donors\' contracts', 'Recorded votes by an official on a contract with one of their own donors, and whether the gift came before or after.', money_map_votes),
    ('donor-contracts', 'Donors with government contracts', 'Each business donor matched to a local government contract, award or payment, with the match method and confidence.', donor_contracts),
    ('vendors-directory', 'Companies', 'Every company in BayCounty.me records, with its other spellings, the governments it works with and how many records name it.', vendors_directory),
    ('people-directory', 'People', 'Elected officials, department leaders and 2026 candidates named in BayCounty.me records, with their roles.', people_directory),
    ('glossary-terms', 'Glossary', 'Plain-English definitions of the government and tax terms used on the site.', glossary_terms),
    ('site-updates', 'What\'s new', 'Each change to the site\'s data and pages, newest first.', site_updates),
    ('savings-opportunities', 'Savings finder: opportunities', 'Places Bay County governments could spend less: the spending each touches, a low and high estimate with its stated assumption, the next step and the records still needed. Every figure is computed from the Accountability projects and the CRA ledger.', savings_opportunities),
    ('savings-evidence', 'Savings finder: evidence', 'The records behind each savings opportunity, one row per project or CRA ledger record: the figure, what it is compared with, the gap or share, cost per unit where one applies, and the source.', savings_evidence),
    ('government-years', 'Governments by year', 'One row per government per fiscal year: adopted budget and its status, general fund, property tax rate and levy, audited actual revenue and spending, residents, audited debt and staff count. A blank means no record for that year. fiscal_year is the year the fiscal year ends (FY2026 = Oct 2025 to Sep 2026; schools Jul to Jun).', government_years),
    ('business-donor-sunbiz', 'Business donors in the state corporate registry', 'Each business that gave to a current officeholder or 2026 local candidate, matched to its Florida Division of Corporations (Sunbiz) record: document number, registered name, status and principal city, with the match method. Business-level only; no owner or officer names.', business_donor_sunbiz),
    ('shared-owner-groups', 'Shared-owner campaign gifts', 'Businesses that share an officer, manager or registered agent (state corporate records) and gave to the same local candidate, one row per business. Only groups checked by hand are listed. People are not named. Each company is its own contributor under Florida law, so a group is legal when each company is a real contributor.', shared_owner_groups),
    ('nonprofits', 'Nonprofits', 'Every nonprofit in the county: organizations recognized by the IRS with a local address, and active Florida nonprofit corporations (Sunbiz) based here. Type, IRS subsection, latest 990 revenue, expenses and assets, how many board members its filings list, how many of those sit on another local board, government payment records and grants. Board members are in nonprofit-board-members.', nonprofits),
    ('nonprofit-payments', 'Nonprofits: government payment records', 'Payment records on the site (contracts, check registers, tourism agency payments, CRA ledger) whose payee is a local nonprofit, matched by name.', nonprofit_payments),
    ('nonprofit-grants', 'Nonprofits: grants they gave', 'Grants to organizations reported on Schedule I of local nonprofits\' 990 returns, with the recipient linked when it is also a local nonprofit.', nonprofit_grants),
    ('nonprofit-board-members', 'Nonprofits: board members', 'Officers, directors, trustees and key employees of local nonprofits as listed on their IRS returns (2019 on), 990-N postcards and state corporate filings: one row per person per nonprofit with titles, years on file, reported pay and hours, and how many other current local boards the same name sits on (homeowner associations aside). person_id groups the same name across boards; two people with a common name can share one.', nonprofit_board_members),
    ('nonprofit-board-businesses', "Nonprofits: board members' businesses", 'Businesses that local nonprofit board members run, from Florida corporate filings (Sunbiz officers and registered agents), with each business\'s gifts to local campaigns. match is "Name and address" when the person on the nonprofit\'s own state filing is the same Sunbiz person, or "Name" when only one Sunbiz person in the county has that name. person_id matches nonprofit-board-members.', nonprofit_board_businesses),
    ('charity-registrations', 'Nonprofits: Florida charity registrations', 'Charities with a county address registered with the Florida Department of Agriculture and Consumer Services to ask the public for donations (Check-A-Charity): registration status and dates, the revenue and the program, fundraising and management spending each reported to the state, and the professional fundraising firms it uses. nonprofit_id links to the nonprofits dataset (joined by FEIN, then by exact name); the officers and directors each registration lists are in nonprofit-board-members.', charity_registrations),
    ('nonprofit-officials', 'Officials on nonprofit boards', 'Elected officials, department leaders and candidates listed as an officer or director of a local nonprofit in its IRS returns or state corporate filings. Only matches checked by hand are listed.', nonprofit_officials),
    ('official-businesses', "Officials' businesses", 'Registered businesses (Florida Division of Corporations) that list an elected official, department leader or local candidate as an officer, manager or registered agent, with the filing date and status. Each official-to-record match was checked by hand. Only officials and candidates are named.', official_businesses),
    ('official-business-links', "Officials' business ties", "How officials' and candidates' registered businesses connect to public life: two officials on the same business, an official's business giving to a campaign, a donor business that shares an officer with a candidate's business (the shared person is counted, not named), and an official's business paid by a local government. Published only for hand-checked matches.", official_business_links),
    ('entity-profiles', 'Profiles: people, companies and organizations', 'Every company, elected official, candidate, nonprofit, nonprofit board member, registered business, committee and government named in BayCounty.me records, one row each, with its profile page and how many documented connections it has. entity_id (kind:key) joins entity-connections. Board members are named as their nonprofits\' public filings list them; individual campaign donors are never included.', entity_profiles),
    ('entity-connections', 'Connections between people, companies and organizations', "Every documented connection between two entities in entity-profiles, totalled per pair and kind: a government paid a payee, an organization gave to an official's or candidate's campaign, an official voted on a company's contracts, a person sits on a nonprofit's board or runs a business, a nonprofit gave a grant, two payees share a project. Each row has its source. Individual campaign donors are never included; officials' board seats and businesses are added by the API once checked by hand.", entity_connections),
    ('tax-districts', 'Tax districts', 'Which taxing authorities levy property tax in each tax district, and the combined millage. Rates by year are in property-tax-rates (authority_id).', tax_districts),
]
