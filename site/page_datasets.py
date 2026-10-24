"""Datasets for pages whose data used to live only inside the page (or only in the app's /data/app files).

Every page's data is published as an open-data dataset so it reaches the database (db/scripts/load.py) and the API
(/api/v1/datasets/<id>). Rows are flat, one record per row, with plain column names. Same privacy rules as the site:
individual campaign donors are never named (they appear only as summed totals), and grant programs' unnamed
recipients stay grouped.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


# --- CRA network (/public-money/cra-network) -------------------------------------------------------------------------

def _network():
    from cra_network import network_data
    return network_data()


KIND = {'biz': 'business', 'gov': 'government', 'prop': 'property owner', 'unnamed': 'payee not named', 'grants': 'grant recipients (grouped)'}


def cra_payee_ids():
    """payee_entity_id for each cra-payments row (same order as data/merged.json payments), or None."""
    import json, re
    from cra_network import _entity, CRA_CODE, DATA
    M = json.load(open(os.path.join(DATA, 'merged.json')))
    V = {v['id']: v for v in json.load(open(os.path.join(DATA, 'entities', 'vendors.json')))['vendors']}
    out = []
    for p in M['payments']:
        code = CRA_CODE.get(p['cra'])
        out.append(_entity(p, code, V)[0] if code else None)
    return out


def cra_network_payees():
    D = _network()
    agg = {}
    for r in D['recs']:
        a = agg.setdefault(r['e'], {'cras': [], 'records': 0, 'counted_total': 0.0})
        if r['c'] not in a['cras']:
            a['cras'].append(r['c'])
        a['records'] += 1
        if r['k'] and isinstance(r['a'], (int, float)):
            a['counted_total'] += r['a']
    rows = []
    for key, e in D['ents'].items():
        a = agg.get(key, {'cras': [], 'records': 0, 'counted_total': 0.0})
        rows.append({'entity_id': key, 'name': e['n'], 'kind': KIND.get(e['k'], e['k']), 'subconsultant_only': bool(e.get('sub')),
                     'cras': [D['cras'][c]['n'] for c in a['cras']], 'records': a['records'], 'counted_total': round(a['counted_total'], 2),
                     'vendor_page': f"/public-money/vendors/{e['vp']}" if e.get('vp') else None})
    rows.sort(key=lambda r: (-r['counted_total'], r['name']))
    return rows


def cra_network_links():
    D = _network()
    return [{'entity_a': x['a'], 'name_a': D['ents'][x['a']]['n'], 'entity_b': x['b'], 'name_b': D['ents'][x['b']]['n'],
             'connection': x['t'], 'source_url': x['u']} for x in D['rel']]


def cra_network_gifts():
    D = _network()
    board = lambda b: (D['cras'].get(b) or {}).get('n') if b else None
    return [{'donor': d['dn'], 'donor_type': d['ty'], 'official': d['o'], 'office': d['off'], 'cra_board': board(d['b']),
             'amount': d['a'], 'gifts': d['n'], 'dates': d['date'] or None, 'payee_entity_id': d['e'], 'match_confidence': d['cf'],
             'report_url': d['u'], 'as_of': D.get('as_of')} for d in D['don']]


# --- Money map (/public-money/money-map) -------------------------------------------------------------------------------

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


DATASETS = [
    ('cra-network-payees', 'CRA network: payees', 'Every payee in the CRA ledger as one entity (businesses, governments, property owners; unnamed grant recipients grouped), with the CRAs that paid it and the counted total.', cra_network_payees),
    ('cra-network-links', 'CRA network: documented connections', 'Documented links between CRA payees that are not payments (shared project, address or subcontract), each with its source.', cra_network_links),
    ('cra-network-gifts', 'CRA network: campaign gifts', 'Business and committee campaign gifts to the officials who sit as each CRA\'s board, and gifts from donors who are CRA payees. Individual donors are not included.', cra_network_gifts),
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
    ('tax-districts', 'Tax districts', 'Which taxing authorities levy property tax in each tax district, and the combined millage. Rates by year are in property-tax-rates (authority_id).', tax_districts),
]
