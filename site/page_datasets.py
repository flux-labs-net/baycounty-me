"""Datasets for pages whose data used to live only inside the page (or only in the app's /data/app files).

Every page's data is published as an open-data dataset so it reaches the database (db/scripts/load.py) and the API
(/api/v1/datasets/<id>). Rows are flat, one record per row, with plain column names. Same privacy rules as the site:
individual campaign donors are named only when they run a registered business (owner-gifts); everyone else appears
only in summed totals. Grant programs' unnamed recipients stay grouped.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'data', 'entities'))
import cutoff  # noqa: E402  the site's first year (2016)


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
        a['total'] += 0 if r.get('x') else (r['a'] or 0)  # x: already counted inside a project total
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
                    'candidate_2026': bool(o['cand'] and not o.get('yr')), 'past_campaign_year': o.get('yr'), 'sits_on': [D['payers'][p]['n'] for p in o['gp']] or None,
                    'amount': d['a'], 'gifts': d['n'], 'dates': d['date'] or None, 'payee_entity_id': d['e'], 'match_confidence': d['cf'],
                    'report_url': D['urls'][d['u']] if d.get('u') is not None else None, 'as_of': D.get('as_of')})
    return out


# --- Money map (/connections#donors) ----------------------------------------------------------------------------------

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
    from people_pages import TITLE_RANKS
    return [{'person_id': p['id'], 'name': p['name'], 'district': p['district'], 'gov_ids': p['gov_ids'] or None, 'roles': p['roles'] or None,
             'primary_gov_id': p['gov'], 'title_rank': p['rank'], 'title_group': TITLE_RANKS[p['rank']], 'status': p['status'], 'sort_order': p['order']}
            for p in people()['people']]


def vendors_directory():
    from app_data import vendors
    return [{'vendor_id': v['id'], 'name': v['name'], 'aliases': v['aliases'] or None, 'gov_ids': v['gov_ids'] or None,
             'records': v['records'] or None, 'vendor_type': v['type'], 'page': v['page']} for v in vendors()['vendors']]


def donor_contracts():
    from app_data import donor_contracts as dc
    return [{k: (v if v not in ([], '') else None) for k, v in m.items()} for m in dc()['matches']]


# --- CRA tax increment (/public-money/cra-tax-increment) -----------------------------------------------------------------

def _cra_increment():
    """Yearly tax increment for each CRA (reported, gap-filled, adopted budget, projected) and the county/city split.
    Facts in data/cra/tax_increment.json; yearly figures from each CRA's budget_by_year; millage from data/tax/millage.json.
    Split: both the county and the city pay 95% of their own levy on the same growth in value, so the county's share is
    county millage / (county + city millage) for the tax year that funds the fiscal year (TY = FY - 1)."""
    import json
    data = os.path.join(HERE, '..', 'data')
    F = json.load(open(os.path.join(data, 'cra', 'tax_increment.json')))
    mill = json.load(open(os.path.join(data, 'tax', 'millage.json')))
    M = {a['id']: {y['tax_year']: y['millage'] for y in a['years'] if y['millage'] is not None} for a in mill['authorities']}

    def rate(aid, ty):
        if not aid:
            return 0.0
        r = M[aid]
        return r.get(ty, r[min(r)] if ty < min(r) else r[max(r)])  # before 2020: the 2020 rate (assumption)

    def share(c, fy):
        cm, km = rate('bay_county_general', fy - 1), rate(c.get('city_millage'), fy - 1)
        return cm / (cm + km) if cm + km else 1.0

    last = F['last_reported_fy']
    files = {}
    agencies, years = [], []
    for c in F['cras']:
        d = files.setdefault(c['file'], json.load(open(os.path.join(data, c['file']))))
        if isinstance(d, list):
            d = next(x for x in d if x['cra'] == c['cra'])
        rep = {int(r['fy'][2:]): r for r in d['budget_by_year'] if r['tif_revenue'] is not None and r['district'] == c['district'] and cutoff.keep(r['fy'])}
        known = sorted(k for k in rep if k <= last)
        hist = []
        for fy in range(known[0], last + 1):
            if fy in rep:
                v, kind, src = rep[fy]['tif_revenue'], 'reported', rep[fy]['source_url']
            else:
                a, b = max(k for k in known if k < fy), min(k for k in known if k > fy)
                va, vb = rep[a]['tif_revenue'], rep[b]['tif_revenue']
                v = va * (vb / va) ** ((fy - a) / (b - a)) if va > 0 and vb > 0 else va + (vb - va) * (fy - a) / (b - a)
                kind, src = 'filled gap', None
            hist.append((fy, v, kind, src))
        anchors = {fy: (r['tif_revenue'], r['source_url']) for fy, r in rep.items() if fy > last}
        anchors.update({a['fy']: (a['increment'], a['source_url']) for a in c.get('anchors', [])})
        base = dict(cra_id=c['id'], cra=c['name'], gov_id=c['gov_id'])

        def row(fy, v, kind, scen, src):
            sh = share(c, fy)
            return dict(base, fiscal_year=fy, fy=f'FY{fy}', basis=kind, scenario=scen, increment=round(v),
                        county_share=round(sh, 4), county_amount=round(v * sh), city_amount=round(v * (1 - sh)), source_url=src)
        for fy, v, kind, src in hist:
            years.append(row(fy, v, kind, 'history', src))
        for scen, g in F['scenarios'].items():
            v = hist[-1][1]
            for fy in range(last + 1, c['sunset_fy'] + 1):
                if fy in anchors:
                    v, kind, src = anchors[fy][0], 'adopted budget', anchors[fy][1]
                else:
                    v, kind, src = v * (1 + g), f'projected {round(g * 100)}% a year', None
                years.append(row(fy, min(v, c.get('cap') or v), kind, scen, src))
        h = [r for r in years if r['cra_id'] == c['id'] and r['scenario'] == 'history']
        fut = lambda s: sum(r['increment'] for r in years if r['cra_id'] == c['id'] and r['scenario'] == s)
        agencies.append(dict(base, city={'pcb': 'Panama City Beach', 'pc': 'Panama City', 'lh': 'Lynn Haven', 'cw': 'Callaway', 'sp': 'Springfield', 'parker': 'Parker'}[c['gov_id']],
                             created=c['created'], base_year=c['base'], first_fy_on_record=h[0]['fiscal_year'], years_filled=sum(1 for r in h if r['basis'] == 'filled gap'),
                             increment_fy2025=h[-1]['increment'], county_share_fy2025=h[-1]['county_share'], county_fy2025=h[-1]['county_amount'], city_fy2025=h[-1]['city_amount'],
                             paid_on_record=sum(r['increment'] for r in h), county_paid_on_record=sum(r['county_amount'] for r in h),
                             sunset_fy=c['sunset_fy'], sunset_assumed=c['sunset_assumed'], sunset_basis=c['sunset_basis'], yearly_cap=c.get('cap'),
                             to_come_low=fut('low'), to_come_mid=fut('mid'), to_come_high=fut('high'),
                             source_url=next((r['source_url'] for r in reversed(h) if r['source_url']), None)))
    hist = [r for r in years if r['scenario'] == 'history']
    model = {'county_except_fbr': lambda fy: sum(r['county_amount'] for r in hist if r['fiscal_year'] == fy and r['cra_id'] != 'pcb-fbr'),
             'county_budget_fy2026': lambda fy: sum(r['county_amount'] for r in years if r['fiscal_year'] == fy and r['scenario'] == 'mid')}
    checks = []
    for k in F['checks']:
        m = model[k['model']](k['fiscal_year'])
        checks.append({'figure': k['check'], 'fiscal_year': k['fiscal_year'], 'official_figure': k['official'], 'estimate': m,
                       'difference_pct': round((m - k['official']) / k['official'] * 100, 1), 'source_url': k['source_url']})
    return agencies, years, checks, F


def cra_agencies():
    return _cra_increment()[0]


def cra_tax_increment():
    return _cra_increment()[1]


def cra_increment_checks():
    return _cra_increment()[2]


# --- Chambers of commerce (/chambers) -------------------------------------------------------------------------------------

def _chamber_files():
    """data/chambers/<county>/chambers.json (hand-copied from each chamber's site) and events.json (fetch_events.py)."""
    import json
    from place import PLACE_ID
    d = os.path.join(HERE, '..', 'data', 'chambers', PLACE_ID.split('-', 1)[-1])
    if not os.path.exists(os.path.join(d, 'chambers.json')):
        return None, {'events': []}
    ev = os.path.join(d, 'events.json')
    return json.load(open(os.path.join(d, 'chambers.json'))), (json.load(open(ev)) if os.path.exists(ev) else {'events': []})


def _member_key(name):
    """The board-member id the nonprofits build gives this name ('b_' + sha1(county|LAST FIRST|middle), nicknames
    folded; data/nonprofits/build_nonprofits.py group_key), so a chamber board member and the same person on another
    nonprofit's IRS filing share one profile."""
    import hashlib, re, ids
    s = re.sub(r'\b(dr|mr|mrs|ms|jr|sr|ii|iii|iv)\b\.?', ' ', re.sub(r'\([^)]*\)', ' ', name), flags=re.I)
    toks = [t for t in re.sub(r'[^A-Za-z ]', '', s.replace('-', ' ')).split() if len(t) > 1]
    first, last = toks[0].lower(), toks[-1].upper()
    county = os.environ.get('PLACE', 'fl-bay').split('-', 1)[-1]
    return 'b_' + hashlib.sha1(f"{county}|{last} {ids.NICK.get(first, first).upper()}|".encode()).hexdigest()[:12]


def _sunbiz_names():
    """Active Bay County Sunbiz filings by normalized name (only names that match one filing)."""
    import csv, gzip, re
    from collections import defaultdict
    p = os.path.join(HERE, '..', 'data', 'sunbiz', 'bay', 'entities.csv.gz')
    by = defaultdict(set)
    if os.path.exists(p):
        for r in csv.DictReader(gzip.open(p, 'rt', encoding='utf-8', errors='replace')):
            if r.get('status') == 'A':
                by[_org_norm(r['name'])].add((r['doc_number'], r['name']))
    return {k: next(iter(v)) for k, v in by.items() if len(v) == 1 and k}


def _org_norm(s):
    import re
    s = re.sub(r"[.,'’&°]", ' ', (s or '').lower())
    return ' '.join(w for w in s.split() if w not in ('inc', 'llc', 'co', 'corp', 'corporation', 'company', 'the', 'pa', 'pllc', 'of', 'incorporated'))


def _chamber_rows():
    import ids
    from entity_graph import page_url
    C, E = _chamber_files()
    if not C:
        return [], [], []
    from opendata import datasets
    fn = {d[0]: d[3] for d in datasets()}
    nps = {n['nonprofit_id']: n for n in fn['nonprofits']()}
    np_by_name = {_org_norm(n['name']): n['nonprofit_id'] for n in nps.values()}
    members = {r['person_id'] for r in fn['nonprofit-board-members']()}
    pay = fn['nonprofit-payments']()
    sb = _sunbiz_names()
    place = C['place_id']

    def org_entity(name, explicit=None):
        """How an organization name links: hand-set id, a government, a company paid by one, a local nonprofit, or one
        active Sunbiz filing with exactly this name (two or more words, so 'Firefly' doesn't match a stranger)."""
        if explicit:
            return explicit, 'set by hand'
        if not name or name == 'Consultant':
            return None, None
        g = ids.gov_id(name)
        if g:
            return 'gov:' + g, 'government'
        v = ids.vendor_id(name)
        if v:
            return 'vendor:' + v, 'company paid by a local government'
        k = _org_norm(name)
        if k in np_by_name:
            return 'nonprofit:' + np_by_name[k], 'nonprofit'
        if len(k.split()) >= 2 and k in sb:
            return 'business:' + sb[k][0].lower(), 'Sunbiz filing with the same name'
        return None, None

    chambers, leaders = [], []
    for c in C['chambers']:
        n = nps.get(c['nonprofit_id']) or {}
        f = nps.get(c.get('foundation_id') or '') or {}
        cp = [p for p in pay if p['nonprofit_id'] == c['nonprofit_id']]
        rows = C['leaders'].get(c['chamber_id'], [])
        chambers.append({
            'place_id': place, 'chamber_id': c['chamber_id'], 'name': c['name'], 'short_name': c['short_name'],
            'legal_name': ids.biz_case(n.get('name') or c['name']), 'entity_id': 'nonprofit:' + c['nonprofit_id'], 'page_url': page_url('nonprofit:' + c['nonprofit_id']),
            'ein': n.get('ein'), 'sunbiz_doc_number': n.get('sunbiz_doc_number'), 'tax_status': n.get('subsection'), 'founded': c.get('founded'),
            'serves': c['serves'], 'tagline': c.get('tagline'), 'about': c['about'], 'mission': (n.get('mission') or '').capitalize() or None,
            'board_meets': c.get('board_meets'), 'board_seats': sum(1 for r in rows if r['group'] not in ('Staff', 'Past chairs')),
            'staff_listed': sum(1 for r in rows if r['group'] == 'Staff'),
            'latest_return_year': n.get('latest_return_year'), 'latest_return_form': n.get('latest_return_form'),
            'revenue': n.get('total_revenue'), 'expenses': n.get('total_expenses'), 'assets': n.get('total_assets'), 'employees': n.get('employees'),
            'public_money_total': round(sum(p['amount'] or 0 for p in cp), 2) or None,
            'public_money_from': '; '.join(dict.fromkeys(p['payer'] for p in cp)) or None,
            'foundation_name': ids.biz_case(f['name']) if f else None, 'foundation_entity_id': 'nonprofit:' + f['nonprofit_id'] if f else None,
            'foundation_revenue': f.get('total_revenue') if f else None,
            'website': c['website'], 'events_url': c['events_url'], 'directory_url': c['directory_url'], 'join_url': c['join_url'],
            'board_url': c['board_url'], 'staff_url': c['staff_url'], 'as_of': C['as_of'], 'source_url': c['about_url']})
        for i, r in enumerate(rows):
            if r.get('person_id'):
                pid, pmatch = 'person:' + r['person_id'], 'official, named with their government post on the chamber site'
            else:
                k = _member_key(r['name'])
                pid, pmatch = 'member:' + k, ('same name on a local nonprofit filing' if k in members else None)
            oid, omatch = org_entity(r.get('organization'), r.get('organization_id'))
            leaders.append({
                'place_id': place, 'chamber_id': c['chamber_id'], 'chamber': c['short_name'], 'chamber_entity_id': 'nonprofit:' + c['nonprofit_id'],
                'role_group': r['group'], 'sort_order': i + 1,
                'person_name': r['name'], 'title': r['title'], 'organization': r.get('organization'), 'term_ends': r.get('term_ends'), 'year': r.get('year'),
                'current': r['group'] != 'Past chairs', 'person_entity_id': pid, 'person_url': page_url(pid), 'person_match': pmatch,
                'organization_entity_id': oid, 'organization_url': page_url(oid) if oid else None, 'organization_match': omatch,
                'as_of': C['as_of'], 'source_url': c['staff_url'] if r['group'] == 'Staff' else c['board_url']})
    programs = []
    for c in C['chambers']:
        for i, p in enumerate(C.get('programs', {}).get(c['chamber_id'], [])):
            programs.append({'place_id': place, 'chamber_id': c['chamber_id'], 'chamber': c['short_name'], 'kind': 'program', 'sort_order': i + 1,
                             'title': p['name'], 'schedule': p['schedule'], 'about': p['about'], 'starts': None, 'ends': None, 'all_day': None,
                             'venue': None, 'city': None, 'category': 'Signature program', 'chamber_event': True, 'cost': None,
                             'event_id': f"{c['chamber_id']}:program:{i + 1}", 'url': p['url'], 'source_url': p['url']})
    short = {c['chamber_id']: c['short_name'] for c in C['chambers']}
    events = [{'place_id': place, 'chamber_id': e['chamber_id'], 'chamber': short.get(e['chamber_id']), 'kind': 'event', 'sort_order': None,
               'title': e['title'], 'schedule': None, 'about': None, **{k: e.get(k) for k in ('starts', 'ends', 'all_day', 'venue', 'city', 'category', 'chamber_event', 'cost', 'event_id', 'url', 'source_url')}}
              for e in E['events']]
    return chambers, leaders, programs + events


def chambers():
    return _chamber_rows()[0]


def chamber_leaders():
    return _chamber_rows()[1]


def chamber_events():
    return _chamber_rows()[2]


# --- Schools (/schools) -------------------------------------------------------------------------------------------------
# data/schools/<county>/: schools.json, zones.json and calendar.json (data/schools/fetch_schools.py), grades.json and
# spending.json (data/schools/fetch_fldoe.py), zone_schools.json (which school each attendance zone feeds, by hand).

SCHOOL_GOV = 'schools'  # the district's gov_id in places/<id>/place.json
# Charter schools run by a local nonprofit, by state school number (checked by hand against each school's site and
# the nonprofits dataset). University Academy and Central High aren't matched to a local filing.
CHARTER_OPERATORS = {
    '03-0701': 'np-651121807', '03-0711': 'np-651121807', '03-0731': 'np-651121807', '03-0741': 'np-651121807', '03-0751': 'np-651121807',
    '03-0771': 'np-261413851', '03-0801': 'np-261413851', '03-0781': 'np-861145087', '03-2701': 'np-800688292', '03-0764': 'np-880556695',
}


def _school_files():
    import json
    from place import PLACE_ID, PLACE
    d = os.path.join(HERE, '..', 'data', 'schools', PLACE_ID.split('-', 1)[-1])
    j = lambda n, default: json.load(open(os.path.join(d, n))) if os.path.exists(os.path.join(d, n)) else default
    return {'conf': PLACE.get('schools') or {}, 'place': PLACE_ID, 'dir': j('schools.json', None), 'zones': j('zones.json', {'zones': []}),
            'calendar': j('calendar.json', {'events': []}), 'grades': j('grades.json', {'rows': []}),
            'spending': j('spending.json', {'rows': [], 'files': []}), 'zone_schools': j('zone_schools.json', {'zones': {}})}


def _sy(end_year):
    """School year label from the year it ends: 2025 -> '2024-25'."""
    return f'{end_year - 1}-{str(end_year)[2:]}'


def _school_rows():
    if '_schools' in _SCH:
        return _SCH['_schools']
    F = _school_files()
    D = F['dir']
    if not D:
        _SCH['_schools'] = {k: [] for k in ('schools', 'grades', 'spending', 'enrollment', 'calendar', 'zones')}
        return _SCH['_schools']
    place = F['place']
    name = {s['school_number']: s['name'] for s in D['schools']}
    for r in F['grades'].get('rows', []):  # a school in the state's grade file but not the federal directory
        name.setdefault(r['school_number'], (r.get('school_name_raw') or r['school_number']).title())
    grade_src = F['grades'].get('source_url') or 'https://www.fldoe.org/accountability/accountability-reporting/school-grades/'
    spend_src = {f['year']: f['source_url'] for f in F['spending'].get('files', [])}

    # enrollment, one row per school and year (CCD year 2024 = the 2024-25 school year, which ends in 2025)
    enrollment = []
    for s in D['schools']:
        for y, n in sorted(s.get('enrollment_by_year', {}).items()):
            if n and int(y) + 1 >= cutoff.FIRST_YEAR:
                enrollment.append({'place_id': place, 'school_id': s['school_number'], 'school': s['name'], 'year': int(y) + 1,
                                   'school_year': _sy(int(y) + 1), 'enrollment': n, 'source_url': D['source_url'].replace(str(D['directory_year']), y)})
    enr = {(r['school_id'], r['year']): r['enrollment'] for r in enrollment}

    grades = []
    comp_keys = ['ela_achievement', 'ela_gains', 'ela_gains_low25', 'math_achievement', 'math_gains', 'math_gains_low25', 'science_achievement',
                 'social_studies_achievement', 'middle_acceleration', 'graduation_rate', 'college_career_acceleration', 'total_points',
                 'percent_of_points', 'percent_tested', 'pct_economically_disadvantaged']
    for r in sorted(F['grades'].get('rows', []), key=lambda r: (r['school_number'], r['year'])):
        if r['year'] < cutoff.FIRST_YEAR:
            continue
        g = {'place_id': place, 'school_id': r['school_number'], 'school': name.get(r['school_number']), 'year': r['year'], 'school_year': _sy(r['year']),
             'grade': r['grade'], 'informational_baseline': r['year'] == 2023}
        g.update({k: r.get(k) for k in comp_keys})
        g['source_url'] = grade_src
        grades.append(g)

    spending = []
    rows = F['spending'].get('rows', [])
    for r in sorted(rows, key=lambda r: (r['year'], r['school_number'])):
        if not r.get('year') or r['year'] < cutoff.FIRST_YEAR:
            continue
        n = enr.get((r['school_number'], r['year']))
        spending.append({'place_id': place, 'school_id': r['school_number'], 'school': name.get(r['school_number']) or r.get('school_name_raw'),
                         'year': r['year'], 'school_year': _sy(r['year']), 'federal_per_student': r.get('federal_ppe'),
                         'state_local_per_student': r.get('state_local_ppe'), 'total_per_student': r.get('total_ppe'), 'enrollment': n,
                         'estimated_total': round(r['total_ppe'] * n) if r.get('total_ppe') and n else None,
                         'source_url': spend_src.get(r['year']) or F['spending'].get('page_url')})

    zs = F['zone_schools'].get('zones', {})
    zones = []
    try:
        from shapely.geometry import shape
        have_shapely = True
    except ImportError:
        have_shapely = False
    import json, math, re
    for z in F['zones'].get('zones', []):
        sid = zs.get(z['zone_name'])
        geom = {'type': 'Polygon', 'coordinates': z['rings']} if len(z['rings']) == 1 else {'type': 'MultiPolygon', 'coordinates': [[r] for r in z['rings']]}
        area = None
        if have_shapely:
            # Esri rings: outer rings run clockwise, holes counter-clockwise; an even-odd fill gives the zone's area
            lat0 = sum(p[1] for r in z['rings'] for p in r) / max(1, sum(len(r) for r in z['rings']))
            kx, ky = 69.172 * math.cos(math.radians(lat0)), 69.0
            from shapely.geometry import Polygon
            tot = 0.0
            for r in z['rings']:
                if len(r) >= 4:
                    p = Polygon([(x * kx, y * ky) for x, y in r])
                    signed = sum((r[i][0] - r[i - 1][0]) * (r[i][1] + r[i - 1][1]) for i in range(len(r)))  # >0 clockwise
                    tot += p.area if signed > 0 else -p.area
            area = round(abs(tot), 2)
        zones.append({'place_id': place, 'zone_id': re.sub(r'[^a-z0-9]+', '-', f"{z['level']} {z['zone_name']}".lower()).strip('-'),
                      'level': z['level'], 'zone_name': z['zone_name'], 'school_id': sid, 'school': name.get(sid),
                      'mou_area': 'MOU' in z['zone_name'], 'pieces': z['pieces'], 'area_sq_mi': area, 'last_edited': z.get('last_edited'),
                      'geometry': json.dumps(geom, separators=(',', ':')), 'source_url': z.get('layer_url') or F['zones'].get('source_url')})

    by_g = {}
    for g in grades:
        by_g.setdefault(g['school_id'], []).append(g)
    by_s = {}
    for s in spending:
        by_s.setdefault(s['school_id'], []).append(s)
    zoned = {}
    for z in zones:
        if z['school_id'] and not z['mou_area']:
            zoned.setdefault(z['school_id'], set()).add(z['level'])
    schools = []
    for s in D['schools']:
        sid = s['school_number']
        gl = sorted(by_g.get(sid, []), key=lambda g: g['year'])
        sl = sorted((x for x in by_s.get(sid, []) if x['total_per_student']), key=lambda x: x['year'])
        op = CHARTER_OPERATORS.get(sid) if s['charter'] else None
        st = s.get('teachers_fte')
        schools.append({
            'place_id': place, 'school_id': sid, 'nces_id': s['nces_id'], 'name': s['name'], 'status': s['status'], 'level': s['level'],
            'school_type': s['school_type'], 'grades': s['grades'], 'charter': s['charter'], 'virtual': s['virtual'],
            'operator_entity_id': 'nonprofit:' + op if op else None,
            'address': s['address'], 'city': s['city'], 'zip': s['zip'], 'phone': s['phone'], 'latitude': s['latitude'], 'longitude': s['longitude'],
            'enrollment': s['enrollment'] if s['status'] == 'Open' else None, 'enrollment_year': D['school_year'] if s['status'] == 'Open' else None,
            'last_year_open': None if s['status'] == 'Open' else _sy(s['last_directory_year'] + 1),
            'teachers_fte': st if s['status'] == 'Open' else None,
            'students_per_teacher': round(s['enrollment'] / st, 1) if s['status'] == 'Open' and st and s.get('enrollment') else None,
            'free_reduced_lunch_pct': round(100 * s['free_reduced_lunch'] / s['enrollment'], 1) if s.get('free_reduced_lunch') and s.get('enrollment') else None,
            'latest_grade': gl[-1]['grade'] if gl else None, 'latest_grade_year': gl[-1]['year'] if gl else None,
            'prior_grade': gl[-2]['grade'] if len(gl) > 1 else None, 'grades_on_record': len(gl),
            'latest_per_student': sl[-1]['total_per_student'] if sl else None, 'latest_spending_year': sl[-1]['year'] if sl else None,
            'zoned_levels': ', '.join(l for l in ('Elementary', 'Middle', 'High') if l in zoned.get(sid, ())) or None,
            'district': F['conf'].get('district_name'), 'page_url': f'/schools/#s-{sid}', 'source_url': D['source_url'],
        })
    schools.sort(key=lambda r: (r['status'] != 'Open', r['name']))

    cal_src = F['calendar'].get('source_url')
    calendar = [{'place_id': place, 'event_id': e['event_id'], 'title': e['title'], 'kind': e['kind'], 'starts': e['starts'], 'ends': e.get('ends'),
                 'all_day': e['all_day'], 'venue': re.sub(r',?\s*(United States|USA)\s*$', '', e.get('venue') or '').strip(' ,') or None, 'school_year': e.get('school_year'), 'source_url': cal_src}
                for e in F['calendar'].get('events', [])]
    _SCH['_schools'] = {'schools': schools, 'grades': grades, 'spending': spending, 'enrollment': enrollment, 'calendar': calendar, 'zones': zones}
    return _SCH['_schools']


_SCH = {}


def schools():
    return _school_rows()['schools']


def school_grades():
    return _school_rows()['grades']


def school_spending():
    return _school_rows()['spending']


def school_enrollment():
    return _school_rows()['enrollment']


def school_calendar():
    return _school_rows()['calendar']


def school_zones():
    return _school_rows()['zones']


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


# --- Savings ideas (government pages) --------------------------------------------------------------------------------

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
    import glob, json
    from govs import GOVS
    D = os.path.join(HERE, '..', 'data')
    J = lambda *p: json.load(open(os.path.join(D, *p)))
    bud = {g['id']: g for g in J('tax', 'budgets.json')['governments']}
    fin = {g['id']: g for g in J('tax', 'finances.json')['governments']}
    mil = {a['id']: a for a in J('tax', 'millage.json')['authorities']}
    da = J('debt_audit', 'debt_audit.json')
    fees = {g['name']: g for g in J('fees', 'fees_pay_officials.json')['governments']}
    pop = J('civic', 'population.json')
    files = {}
    for fp in sorted(glob.glob(os.path.join(D, 'budgets', '*.json'))):
        f = json.load(open(fp))
        files[f['gov']] = f['years']
    from place import NAME as PLACE_NAME
    out = []
    for g in GOVS:
        rows = {}
        row = lambda y: rows.setdefault(y, {})
        b = bud.get(g['tax']) or {}
        # budgets: the yearly budget file (data/budgets/<gov>.json), then history, FY2026 and FY2027, which win where both have a year
        entries = [(f"FY{y['fiscal_year']}", {'total_budget': y.get('total'), 'general_fund': y.get('general_fund'), 'source_url': y.get('source_url')}, y.get('status'))
                   for y in files.get(g['key'], [])]
        entries += [(h.get('fy'), h, h.get('note') or 'adopted') for h in b.get('history') or []]
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


# --- Budgets by year (/public-money/budget-compare) -------------------------------------------------------------------

_LINE_ALIAS = {'comprehensive planning': 'planning', 'protective inspection': 'building', 'law enforcement': 'police',
               'community redevelopment': 'cra', 'community redevelopment agency': 'cra'}


def _line_key(section, name, code=None):
    """One key per budget line, so the same fund or department lines up across years even when a document words it
    differently ("Legislative - Commission" and "Legislative (commission)", "Community Redevelopment Fund (CRA)" and
    "CRA Fund"). A department or fund number wins when the source gives one."""
    import re
    if code:
        return f'{section[0]}{code}'
    n = re.sub(r'\(.*?\)', '', str(name or '').lower())
    n = re.split(r'\s+[-–]\s+|/', n)[0]
    n = re.sub(r'^\d+\s+', '', n).replace('&', 'and')
    n = re.sub(r'\b(fund|department|dept\.?)\b', '', n)
    n = re.sub(r'[^a-z0-9 ]', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return f'{section[0]}:' + _LINE_ALIAS.get(n, n)


def budget_years():
    """Every budget line we have for each government and fiscal year, for comparing one year with another.

    basis 'adopted': the adopted budget's total and General Fund (same figures as government-years), its funds and its
    General Fund departments. Department and fund lines come from data/budgets/<gov>.json (one file per government,
    every year of its budget documents) where there is one, else data/civic/budgets_detail.json (FY2026) and the
    FY2027 lines in data/tax/budgets.json.
    basis 'actual': audited revenue by source and spending by function from the state's Local Government Financial
    Reports (data/tax/finances.json). in_total is false for transfers and borrowing, which the totals leave out.
    """
    import glob, json
    from govs import GOVS
    from money_pages import service_of, SVC_NAME
    D = os.path.join(HERE, '..', 'data')
    J = lambda *p: json.load(open(os.path.join(D, *p)))
    bud = {g['id']: g for g in J('tax', 'budgets.json')['governments']}
    det = {g['gov']: g for g in J('civic', 'budgets_detail.json')['governments']}
    fin = {g['id']: g for g in J('tax', 'finances.json')['governments']}
    files = {}
    for fp in sorted(glob.glob(os.path.join(D, 'budgets', '*.json'))):
        f = json.load(open(fp))
        files[f['gov']] = {y['fiscal_year']: y for y in f['years']}
    gy = {(r['gov_id'], r['fiscal_year']): r for r in government_years()}
    SVC_OTHER = {None: 'Transfers, reserves, debt & disaster', 'other': 'Other services'}
    out = []

    def add(g, y, basis, section, name, amount, **kw):
        if amount is None:
            return
        key = kw.pop('key', None) or _line_key(section, name, kw.pop('code', None))
        svc = service_of(name) if section == 'department' else None
        if svc == 'other':  # a renamed line ("Protective inspection") takes its usual name's service ("building")
            svc = service_of(key.split(':', 1)[-1])
        out.append({'gov_id': g['key'], 'government': g['name'], 'fiscal_year': y, 'fy': f'FY{y}', 'basis': basis, 'section': section,
                    'line_key': key, 'name': name,
                    'service': (SVC_NAME.get(svc) or SVC_OTHER.get(svc)) if section == 'department' else None,
                    'fund_type': kw.pop('fund_type', None), 'amount': round(amount), 'in_total': kw.pop('in_total', True),
                    'status': kw.pop('status', None), 'source_url': kw.pop('source_url', None)})

    for g in GOVS:
        k, b = g['key'], bud.get(g['tax']) or {}
        # totals: the same figures as government-years
        for (gk, y), r in sorted(gy.items()):
            if gk != k:
                continue
            st = r.get('budget_status')
            add(g, y, 'adopted', 'total', 'Total budget' + (' (without transfers between funds)' if r.get('budget_excludes_transfers') else ''), r.get('budget_total'),
                key='total', status=st, source_url=r.get('budget_source_url'))
            add(g, y, 'adopted', 'total', 'General Fund', r.get('general_fund'), key='general_fund', status=st, source_url=r.get('budget_source_url'))
            add(g, y, 'actual', 'total', 'Revenue (audited)', r.get('actual_revenue'), key='revenue_total', status='audited', source_url=r.get('actuals_source_url'))
            add(g, y, 'actual', 'total', 'Spending (audited, without transfers)', r.get('actual_spending'), key='spending_total', status='audited', source_url=r.get('actuals_source_url'))
        # funds and General Fund departments, by year
        years = dict(files.get(k, {}))
        d = det.get(k)
        if d and _fy(d.get('fiscal_year')) not in years:
            years[_fy(d['fiscal_year'])] = {'status': d.get('status'), 'source_url': d.get('source_url'), 'total': d.get('total'), 'funds': d.get('funds') or [],
                                            'general_fund_departments': d.get('general_fund_departments') or []}
        x27 = b.get('fy2027') or {}
        if 2027 not in years and (x27.get('fund_totals') or (x27.get('gf_expenditures') and 'Other departments' not in x27['gf_expenditures'])):
            years[2027] = {'status': _budget_status(x27.get('status')), 'source_url': x27.get('source_url'),
                           'funds': [{'name': n, 'amount': a} for n, a in (x27.get('fund_totals') or {}).items()],
                           'general_fund_departments': [{'name': n, 'amount': a} for n, a in (x27.get('gf_expenditures') or {}).items()]}
        for y, x in sorted(years.items()):
            st = _budget_status(x.get('status'))
            if x.get('total') and not (gy.get((k, y)) or {}).get('budget_total'):  # a total the yearly file doesn't carry
                add(g, y, 'adopted', 'total', 'Total budget', x['total'], key='total', status=st, source_url=x.get('source_url'))
            for f in x.get('funds') or []:
                add(g, y, 'adopted', 'fund', f['name'], f.get('amount'), code=f.get('code'), fund_type=f.get('type'), status=st, source_url=x.get('source_url'))
            for dp in x.get('general_fund_departments') or []:
                add(g, y, 'adopted', 'department', dp['name'], dp.get('amount'), code=dp.get('code'), status=st, source_url=x.get('source_url'))
        # audited actuals
        for a in (fin.get(g['tax']) or {}).get('years') or []:
            y = _fy(a['fy'])
            for n, v in (a.get('revenues') or {}).items():
                add(g, y, 'actual', 'revenue', n, v, in_total='not revenue' not in n, status='audited', source_url=a.get('revenue_source_url') or a.get('source_url'))
            for n, v in (a.get('expenditures') or {}).items():
                add(g, y, 'actual', 'spending', n, v, in_total=n != 'Transfers & other', status='audited', source_url=a.get('expenditure_source_url') or a.get('source_url'))
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


def owner_gifts():
    """Personal campaign gifts from people who run a registered business (data/campaign/owner_gifts.py), one row per
    person and campaign. The person is named, with the businesses they run; no addresses or occupations."""
    import json
    sys.path.insert(0, os.path.join(HERE, '..', 'data', 'entities'))
    import ids
    fp = os.path.join(HERE, '..', 'data', 'campaign', 'owner_gifts.json')
    if not os.path.exists(fp):
        return []
    d = json.load(open(fp))
    agg = {}
    for g in d['gifts']:
        r = agg.setdefault((g['owner_id'], g['cand_id']), {'n': 0, 'amt': 0.0, 'dates': []})
        r['n'] += 1
        r['amt'] += g['amount']
        if g.get('date'):
            r['dates'].append(g['date'])
    rows = []
    for (pk, cid), r in agg.items():
        o, c = d['owners'][pk], d['campaigns'][cid]
        biz = o['businesses']
        rows.append({'donor_id': 'owner:' + pk, 'donor': o['name'], 'businesses': '; '.join(ids.biz_case(b['name']) for b in biz),
                     'business_doc_numbers': '; '.join(b['doc_number'] for b in biz), 'active_businesses': sum(1 for b in biz if b['status'] == 'active'),
                     'candidate': c['candidate'], 'candidate_id': ids.person_id(c['candidate']), 'office': c['office'], 'election': c['election'],
                     'gifts': r['n'], 'amount': round(r['amt'], 2), 'first_date': min(r['dates']) if r['dates'] else None,
                     'last_date': max(r['dates']) if r['dates'] else None, 'match': 'same name and street address as a Sunbiz officer, manager or registered agent',
                     'source_url': c['report_url']})
    rows.sort(key=lambda r: (-r['amount'], r['donor'], r['candidate']))
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


# School grades and spending come from fldoe.org files read by hand (data/schools/fetch_fldoe.py); until a file is on
# hand the datasets are empty, so their columns are listed here to keep the table and the API stable.
_GRADE_NUM = ['year', 'ela_achievement', 'ela_gains', 'ela_gains_low25', 'math_achievement', 'math_gains', 'math_gains_low25', 'science_achievement',
              'social_studies_achievement', 'middle_acceleration', 'graduation_rate', 'college_career_acceleration', 'total_points',
              'percent_of_points', 'percent_tested', 'pct_economically_disadvantaged']
DB_ONLY_COLUMNS['school-grades'] = {**{c: 'string' for c in ('place_id', 'school_id', 'school', 'school_year', 'grade')}, 'informational_baseline': 'boolean',
                                    **{c: 'number' for c in _GRADE_NUM}, 'source_url': 'string', 'gov_id': 'string'}
DB_ONLY_COLUMNS['school-spending'] = {**{c: 'string' for c in ('place_id', 'school_id', 'school')}, 'year': 'number', 'school_year': 'string',
                                      **{c: 'number' for c in ('federal_per_student', 'state_local_per_student', 'total_per_student', 'enrollment', 'estimated_total')},
                                      'source_url': 'string', 'gov_id': 'string'}


# Gifts over the per-election limit: rows are written by registry.publish_limit_case() when an admin confirms or
# resolves a case (migration 0038), not by the site build.
OVER_LIMIT_COLUMNS = ['case_id', 'candidate', 'office', 'election', 'election_phase', 'contributor', 'contributor_type', 'gifts', 'gross_amount',
                      'refunds', 'net_amount', 'over_by', 'gift_list', 'first_date', 'last_date', 'possible_double_entry', 'status', 'resolution',
                      'resolution_note', 'resolution_url', 'reviewed_on', 'county', 'source_url', 'gov_id']
DB_ONLY_COLUMNS['over-limit-gifts'] = {c: ('number' if c in ('gifts', 'gross_amount', 'refunds', 'net_amount', 'over_by') else
                                           'boolean' if c == 'possible_double_entry' else 'string') for c in OVER_LIMIT_COLUMNS}


def over_limit_gifts():
    return []


# --- Open books (/public-money/checkbook, /public-money/budget-tracker) ------------------------------------------------
# Each government's own accounting: rows are written to the database when an admin publishes a finance file
# (api/_finance/publish.js, migration 0047), not by the site build, so the build's files hold only the columns.
CHECKBOOK_COLUMNS = ['government', 'fiscal_year', 'paid_on', 'payee', 'payee_kind', 'payee_entity_id', 'amount', 'method', 'doc_no', 'invoice_no',
                     'fund', 'account', 'description', 'source_file', 'upload_id', 'published_at', 'source_url', 'gov_id']
DB_ONLY_COLUMNS['checkbook-payments'] = {c: ('number' if c in ('fiscal_year', 'amount', 'upload_id') else 'string') for c in CHECKBOOK_COLUMNS}
BUDGET_ACTUAL_COLUMNS = ['government', 'fiscal_year', 'as_of', 'line_type', 'fund', 'department', 'account', 'description', 'original_budget',
                         'amended_budget', 'actual_ytd', 'encumbered', 'source_file', 'upload_id', 'published_at', 'source_url', 'gov_id']
DB_ONLY_COLUMNS['budget-actuals'] = {c: ('number' if c in ('fiscal_year', 'original_budget', 'amended_budget', 'actual_ytd', 'encumbered', 'upload_id') else 'string')
                                     for c in BUDGET_ACTUAL_COLUMNS}


def checkbook_payments():
    return []


def budget_actuals():
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


def officeholder_terms():
    """Who held each elected seat, one row per term, from data/civic/officeholders.json
    (data/civic/scripts/officeholders.py). person_name null is a known vacancy (vacant true) or a stretch nobody could
    confirm (confirmed false). start_date null = in office before 2016, the site's first year; end_date null = in office now."""
    import json
    d = json.load(open(os.path.join(HERE, '..', 'data', 'civic', 'officeholders.json')))
    sys.path.insert(0, os.path.join(HERE, '..', 'data', 'entities'))
    import ids
    rows = []
    for g in d['governments']:
        for s in g['seats']:
            for i, t in enumerate(s['terms']):
                src = d['sources'].get(t.get('src')) or {}
                name = t.get('name')
                rows.append({'place_id': d['place_id'], 'gov_id': g['gov_id'], 'government': g['government'], 'body': g['body'],
                             'seat': s['seat'], 'seat_order': s['order'], 'appointed': bool(s.get('appointed')), 'term_order': i, 'person_name': name,
                             'person_id': ids.person_id(name) if name else None,
                             'start_date': t.get('start'), 'end_date': t.get('end'),
                             'start_approx': bool(t.get('start_approx')), 'end_approx': bool(t.get('end_approx')),
                             'how': t.get('how'), 'vacant': bool(t.get('vacant')), 'confirmed': not t.get('gap') or bool(t.get('vacant')), 'note': t.get('note'),
                             'source_title': src.get('title'), 'source_url': src.get('url'),
                             'date_start': t.get('start'), 'date_end': t.get('end'), 'date_precision': 'day'})
    return rows


def official_photos():
    """Official headshots of current officials and department leaders, one row per person, from
    data/civic/official_photos.json (data/civic/scripts/official_photos.py). Only photos the government publishes."""
    import json
    d = json.load(open(os.path.join(HERE, '..', 'data', 'civic', 'official_photos.json')))
    return [{'place_id': d['place_id'], 'person_id': r['person_id'], 'entity_id': 'person:' + r['person_id'], 'name': r['name'],
             'photo_url': 'https://baycounty.me' + r['photo_path'], 'photo_path': r['photo_path'], 'width': r['width'],
             'height': r['height'], 'credit': r['credit'], 'source_url': r['source_url'],
             'image_source_url': r['image_source_url'], 'fetched_on': r['fetched_on']} for r in d['photos']]


def data_completeness():
    import completeness
    return completeness.rows()


def site_menu():
    from site_menu import site_menu_rows
    return site_menu_rows()


def data_sources():
    from data_sources import rows
    return rows()


def data_source_sites():
    from data_sources import site_rows
    return site_rows()


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
    ('people-directory', 'People', 'Elected officials, department leaders and 2026 candidates named in BayCounty.me records, with their roles. sort_order is the People page\'s order: by the government they are listed under (primary_gov_id), then title (title_rank 0 mayor, chair or elected officer to 8 past candidate, named in title_group), then last name. status is current (in office, on staff or on the 2026 ballot) or past (former officials and past candidates).', people_directory),
    ('glossary-terms', 'Glossary', 'Plain-English definitions of the government and tax terms used on the site.', glossary_terms),
    ('site-updates', 'What\'s new', 'Each change to the site\'s data and pages, newest first.', site_updates),
    ('savings-opportunities', 'Savings finder: opportunities', 'Places Bay County governments could spend less: the spending each touches, a low and high estimate with its stated assumption, the next step and the records still needed. Every figure is computed from the Accountability projects and the CRA ledger.', savings_opportunities),
    ('savings-evidence', 'Savings finder: evidence', 'The records behind each savings opportunity, one row per project or CRA ledger record: the figure, what it is compared with, the gap or share, cost per unit where one applies, and the source.', savings_evidence),
    ('government-years', 'Governments by year', 'One row per government per fiscal year: adopted budget and its status, general fund, property tax rate and levy, audited actual revenue and spending, residents, audited debt and staff count. A blank means no record for that year. fiscal_year is the year the fiscal year ends (FY2026 = Oct 2025 to Sep 2026; schools Jul to Jun).', government_years),
    ('budget-years', 'Budgets by year, line by line', "Every budget line on record for each government and fiscal year, to compare one year with another. basis adopted: the adopted budget's total and General Fund, each fund and each General Fund department. basis actual: audited revenue by source and spending by function from the state's Local Government Financial Reports (in_total is false for transfers and borrowing, which the audited totals leave out). line_key lines the same fund or department up across years; service groups departments into common services. fiscal_year is the year the fiscal year ends (FY2026 = Oct 2025 to Sep 2026; schools Jul to Jun).", budget_years),
    ('business-donor-sunbiz', 'Business donors in the state corporate registry', 'Each business that gave to a current officeholder or 2026 local candidate, matched to its Florida Division of Corporations (Sunbiz) record: document number, registered name, status and principal city, with the match method. Business-level only; no owner or officer names.', business_donor_sunbiz),
    ('shared-owner-groups', 'Shared-owner campaign gifts', 'Businesses that share an officer, manager or registered agent (state corporate records) and gave to the same local candidate, one row per business. Only groups checked by hand are listed. People are not named. Each company is its own contributor under Florida law, so a group is legal when each company is a real contributor.', shared_owner_groups),
    ('over-limit-gifts', 'Gifts over the contribution limit', "Organizations that gave one local candidate more than Florida's $1,000-per-election limit, as the campaign reported it (s. 106.08, F.S.), net of reported refunds. The primary and general are separate elections. Each case was checked by hand. status is Open (over the limit as reported, no explanation found) or Resolved (resolution says why: a reporting error, an amended report, a refund, a check designated for the general election, or a Florida Elections Commission ruling). A reported overage is not a finding of wrongdoing. Individual donors are not listed.", over_limit_gifts),
    ('nonprofits', 'Nonprofits', 'Every nonprofit in the county: organizations recognized by the IRS with a local address, and active Florida nonprofit corporations (Sunbiz) based here. Type, IRS subsection, latest 990 revenue, expenses and assets, how many board members its filings list, how many of those sit on another local board, government payment records and grants. Board members are in nonprofit-board-members.', nonprofits),
    ('nonprofit-payments', 'Nonprofits: government payment records', 'Payment records on the site (contracts, check registers, tourism agency payments, CRA ledger) whose payee is a local nonprofit, matched by name.', nonprofit_payments),
    ('nonprofit-grants', 'Nonprofits: grants they gave', 'Grants to organizations reported on Schedule I of local nonprofits\' 990 returns, with the recipient linked when it is also a local nonprofit.', nonprofit_grants),
    ('nonprofit-board-members', 'Nonprofits: board members', 'Officers, directors, trustees and key employees of local nonprofits as listed on their IRS returns (2019 on), 990-N postcards and state corporate filings: one row per person per nonprofit with titles, years on file, reported pay and hours, and how many other current local boards the same name sits on (homeowner associations aside). person_id groups the same name across boards; two people with a common name can share one.', nonprofit_board_members),
    ('nonprofit-board-businesses', "Nonprofits: board members' businesses", 'Businesses that local nonprofit board members run, from Florida corporate filings (Sunbiz officers and registered agents), with each business\'s gifts to local campaigns. match is "Name and address" when the person on the nonprofit\'s own state filing is the same Sunbiz person, or "Name" when only one Sunbiz person in the county has that name. person_id matches nonprofit-board-members.', nonprofit_board_businesses),
    ('charity-registrations', 'Nonprofits: Florida charity registrations', 'Charities with a county address registered with the Florida Department of Agriculture and Consumer Services to ask the public for donations (Check-A-Charity): registration status and dates, the revenue and the program, fundraising and management spending each reported to the state, and the professional fundraising firms it uses. nonprofit_id links to the nonprofits dataset (joined by FEIN, then by exact name); the officers and directors each registration lists are in nonprofit-board-members.', charity_registrations),
    ('nonprofit-officials', 'Officials on nonprofit boards', 'Elected officials, department leaders and candidates listed as an officer or director of a local nonprofit in its IRS returns or state corporate filings. Only matches checked by hand are listed.', nonprofit_officials),
    ('official-businesses', "Officials' businesses", 'Registered businesses (Florida Division of Corporations) that list an elected official, department leader or local candidate as an officer, manager or registered agent, with the filing date and status. Each official-to-record match was checked by hand. Only officials and candidates are named.', official_businesses),
    ('official-business-links', "Officials' business ties", "How officials' and candidates' registered businesses connect to public life: two officials on the same business, an official's business giving to a campaign, a donor business that shares an officer with a candidate's business (the shared person is counted, not named), and an official's business paid by a local government. Published only for hand-checked matches.", official_business_links),
    ('owner-gifts', 'Campaign gifts from business owners', "Personal gifts to local campaigns from people who run a registered Florida business, one row per person and campaign. A contributor filed as an individual is listed when the name and street address on the Supervisor of Elections filing are the same as an officer, manager or registered agent of a for-profit business on Sunbiz that was active around the gift; middle initials and Jr/Sr must agree, and protected voters are never matched. Other individual donors are never named. No addresses or occupations.", owner_gifts),
    ('entity-profiles', 'Profiles: people, companies and organizations', 'Every company, elected official, candidate, nonprofit, nonprofit board member, registered business, committee and government named in BayCounty.me records, one row each, with its profile page and how many documented connections it has. entity_id (kind:key) joins entity-connections. Board members are named as their nonprofits\' public filings list them; individual campaign donors are included only when they run a registered business (owner-gifts).', entity_profiles),
    ('entity-connections', 'Connections between people, companies and organizations', "Every documented connection between two entities in entity-profiles, totalled per pair and kind: a government paid a payee, an organization gave to an official's or candidate's campaign, an official voted on a company's contracts, a person sits on a nonprofit's board or runs a business, a nonprofit gave a grant, two payees share a project. Each row has its source. Individual campaign donors are included only when they run a registered business (owner-gifts); officials' board seats and businesses are added by the API once checked by hand.", entity_connections),
    ('officeholder-terms', 'Officeholders by year', "Who held each elected seat, and each government's appointed manager, on every local government since 2016: one row per person per seat, with start_date and end_date, so the officials in office on any date or in any fiscal year can be picked out. person_name is blank for a known vacancy (vacant true) and for a stretch nobody could confirm from the records found (confirmed false); the note says which. start_date blank = in office before 2016; end_date blank = in office now. start_approx / end_approx mark dates known only to the month or year. appointed is true for the government's appointed manager or administrator (the county manager, city managers, Mexico Beach's administrator) and false for elected seats. how is elected, special election, appointed, interim or commission (chosen by the commission). Each term names its source: election results, minutes, budget books, city sites or news. place_id is the place (fl-bay = Bay County).", officeholder_terms),
    ('data-sources', 'Where the data comes from', "Every source BayCounty.me takes records from, one row per source: the topic, the government it covers (or state and federal databases), the link, how we get it (automatic fetch, downloaded and read by hand, a state or federal bulk file, or a live lookup), how often, what we take from it, how we process it and the checks we run.", data_sources),
    ('official-photos', 'Official photos', "Official headshots of current elected officials and department leaders, one row per person: the photo on BayCounty.me (photo_url, a 320px square WebP), who published it (credit) and the government page it came from (source_url), and when it was copied. Only photos a government publishes on its own website; never campaign, news or social media photos. person_id joins officeholder-terms and entity_id joins entity-profiles. Anyone not listed has no published photo and is shown with initials.", official_photos),
    ('data-completeness', 'How complete each government\'s data is', "For each government and each portion of its records (adopted budgets, audited spending, tax rates, debt, audit findings, officials by year): the years since 2016 we expect (period, expected), how many we have on file (have), the percent loaded (pct) and a status: complete (100%), partial (50-99%) or missing (under 50%). missing lists the fiscal years not on file. For officials, have and expected are seat-years and pct is the share where the officeholder is confirmed. Votes read from minutes change every few hours and are in /api/v1/import-progress instead.", data_completeness),
    ('data-source-sites', 'Websites our records cite', "Every website cited by the records behind BayCounty.me, per topic, with how many distinct documents and pages from it the data links to. Counted from the data files at each build.", data_source_sites),
    ('site-menu', 'Site menu', "Every link in the site's main menu, one row per link, in English and Spanish: the section and the question it answers, the link's place in the section, and the section's start-here page. place_id is the place the menu belongs to (fl-bay = Bay County), so a menu for another place sits beside it.", site_menu),
    ('checkbook-payments', 'Checkbook: every payment', "Every payment in each government's own check register (checks, ACH, wires and cards), as published from the files the government sends: date, payee, amount, check number, invoice, fund, account and description. fiscal_year is the year the fiscal year ends. Voided checks are left out. Payments to private individuals (refunds, reimbursements) are listed as \"Individual (name withheld)\" with payee_kind individual and a category instead of the description. payee_entity_id links a payee to its profile (entity-profiles) when the site knows it. Bank statements and reconciliations are never published.", checkbook_payments),
    ('budget-actuals', 'Budget vs. actual, month by month', "Each government's budget-vs-actual report as of each month end (as_of), line by line: fund, department, account, the original and amended budget, actual_ytd (spending, or revenue collected, to date) and encumbered (open purchase orders). line_type is expense or revenue. One report per month end, so a fiscal year has a row per line per report. fiscal_year is the year the fiscal year ends (FY2026 = Oct 2025 to Sep 2026).", budget_actuals),
    ('cra-agencies', 'CRAs: tax increment by agency', "One row per Community Redevelopment Agency that collects tax increment in Bay County: when it was created, its base year, the FY2025 increment and how much of it Bay County and the city paid, the total on record, its sunset date and what that date rests on, and the increment still to come under a 3%, 6% or 9% growth scenario. sunset_assumed is true where the CRA's plan was not found.", cra_agencies),
    ('cra-tax-increment', 'CRAs: tax increment by year', "Property tax paid to each CRA by fiscal year, split between Bay County and the city by millage. scenario history: basis reported (from CRA reports, audits and budgets) or filled gap (between two reported years). scenario low, mid, high: FY2026 to the CRA's sunset, from adopted budgets where they exist, then 3%, 6% or 9% growth a year (Front Beach Road capped at $30M). Schools and the water management district are exempt and pay nothing.", cra_tax_increment),
    ('cra-increment-checks', 'CRAs: estimate checked against official figures', "Official county figures for CRA payments next to this estimate for the same year, with the difference in percent.", cra_increment_checks),
    ('chambers', 'Chambers of commerce', "One row per chamber of commerce: what it is and who it serves, its board meetings, its latest IRS Form 990 (revenue, expenses, assets, employees), public money paid to it by local governments and tourism agencies (from nonprofit-payments), its foundation, and links to its member directory, events and join page. entity_id is its profile (entity-profiles). Chambers are private, member-owned nonprofits, not government agencies.", chambers),
    ('chamber-leaders', 'Chambers of commerce: boards and staff', "Each chamber's board (executive committee, directors, ex officio and honorary members), staff and past chairs since 2016, as listed on the chamber's own website on as_of: name, title and the organization each board member represents. No phone numbers, emails or addresses. person_entity_id and organization_entity_id link to profiles; person_match and organization_match say how each link was made (blank = no match, shown as plain text).", chamber_leaders),
    ('chamber-events', 'Chambers of commerce: events and programs', "Upcoming events from each chamber's public calendar (kind event: title, start and end in local time, venue and city, category, the event's own link) and each chamber's yearly and monthly signature programs (kind program: schedule and what it is). chamber_event is false for community events a chamber lists on its calendar. Refreshed daily where the calendar has a public feed.", chamber_events),
    ('schools', 'Public schools', "One row per public school in the district, open now or closed since 2016: state school number (school_id, district-school), federal id, level, grades taught, district or charter, address and phone of the school building, enrollment and teachers for the latest federal school directory year, students per teacher, share of students eligible for free or reduced-price lunch, latest state school grade and the one before it, latest per-student spending, and which attendance zone levels feed it. operator_entity_id is the nonprofit that runs a charter school (entity-profiles).", schools),
    ('school-grades', 'School grades', "Every Florida school grade (A to F, or I for incomplete) on record for each school since 2016, from the Florida Department of Education's school grades file, one row per school and year. year is the school year's end (2025 = 2024-25). Components (percent of students: English and math achievement and learning gains, science, social studies, acceleration, graduation rate; total points and percent of points) are filled in for the latest year in the file. No grades were given for 2019-20 (testing was canceled); 2020-21 grades were only given to schools that asked; 2022-23 grades were an informational baseline (informational_baseline true).", school_grades),
    ('school-spending', 'Spending per school', "Per-student spending at each school from the Florida Department of Education's yearly Every Student Succeeds Act (ESSA) per-pupil expenditure reports: federal, state and local, and total, one row per school and year (year = the school year's end). estimated_total multiplies the per-student figure by that year's enrollment from the federal school directory, so it is an estimate, not a reported total.", school_spending),
    ('school-enrollment', 'School enrollment by year', "Students enrolled at each public school each school year since 2015-16 (year = the school year's end), from the U.S. Department of Education's Common Core of Data school directory.", school_enrollment),
    ('school-calendar', 'School district calendar', "The school district's calendar as posted on its website: first and last day, holidays and breaks, no-school days, early release days, end of each grading period, graduations and School Board meetings. kind is first-day, last-day, no-school, break, early-release, grading, graduation, board-meeting or other. starts and ends are local dates (all_day) or local date and time. Refreshed daily; past events of the school year stay on file.", school_calendar),
    ('school-zones', 'School attendance zones', "The school district's attendance zones (which elementary, middle and high school serves each part of the county), from the county GIS server, one row per zone with the school it feeds (school_id), area in square miles, the county's last edit date and the zone's shape as GeoJSON (geometry, longitude/latitude, simplified to about 40 meters). mou_area marks zones the county map labels MOU (covered by a separate agreement). Choice, magnet and charter schools take students from outside their zone.", school_zones),
    ('tax-districts', 'Tax districts', 'Which taxing authorities levy property tax in each tax district, and the combined millage. Rates by year are in property-tax-rates (authority_id).', tax_districts),
]
