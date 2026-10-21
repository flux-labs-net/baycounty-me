"""One profile per local government, gathered from every dataset on the site.

Used by the government pages (/governments/<slug>), the compare tool and open data.
Every figure keeps the source URL it came from.
"""
import json, os, re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')


def _j(*p):
    try:
        return json.load(open(os.path.join(DATA, *p)))
    except FileNotFoundError:
        return None


# key, slug, short name, full name, kind, and how each dataset names it
GOVS = [
    dict(key='county', slug='bay-county', short='Bay County', name='Bay County Board of County Commissioners', kind='county',
         tax='bay_county', auth='bay_county_general', debt='Bay County (Board', audit='Bay County', contracts='Bay County BOCC',
         fees='Bay County Board of County Commissioners', surtax='Bay County', fema=['Bay County'], cra=None, util='Bay County Utility Services',
         blurb='The County Commission sets the countywide property tax, runs county roads, utilities, parks, libraries and emergency services, and funds the five elected county officers.'),
    dict(key='schools', slug='bay-district-schools', short='Bay District Schools', name='Bay District Schools (School Board of Bay County)', kind='schools',
         tax='bay_district_schools', auth=None, debt='Bay District Schools', audit='Bay District Schools', contracts=None,
         fees='Bay District Schools (School Board of Bay County)', surtax=None, fema=['School Board of Bay County Florida'], cra=None, util=None,
         blurb='The elected School Board and superintendent run Bay County\'s public schools. School property taxes are the largest slice of most Bay County tax bills; most of the rate is set by the state.'),
    dict(key='pc', slug='panama-city', short='Panama City', name='City of Panama City', kind='city',
         tax='panama_city', auth='city_panama_city', debt='City of Panama City (primary', audit='City of Panama City', contracts='City of Panama City',
         fees='City of Panama City', surtax='City of Panama City', fema=['Panama City, City of'], cra='pc', util='City of Panama City'),
    dict(key='pcb', slug='panama-city-beach', short='Panama City Beach', name='City of Panama City Beach', kind='city',
         tax='panama_city_beach', auth='city_panama_city_beach', debt='City of Panama City Beach', audit='City of Panama City Beach', contracts='City of Panama City Beach',
         fees='City of Panama City Beach', surtax='City of Panama City Beach', fema=['Panama City Beach, City of'], cra='pcb', util='City of Panama City Beach'),
    dict(key='lh', slug='lynn-haven', short='Lynn Haven', name='City of Lynn Haven', kind='city',
         tax='lynn_haven', auth='city_lynn_haven', debt='City of Lynn Haven', audit='City of Lynn Haven', contracts='City of Lynn Haven',
         fees='City of Lynn Haven', surtax='City of Lynn Haven', fema=['Lynn Haven, City of'], cra='lh', util='City of Lynn Haven'),
    dict(key='cw', slug='callaway', short='Callaway', name='City of Callaway', kind='city',
         tax='callaway', auth='city_callaway', debt='City of Callaway', audit='City of Callaway', contracts='City of Callaway',
         fees='City of Callaway', surtax='City of Callaway', fema=['Callaway, City of'], cra='cw', util='City of Callaway'),
    dict(key='sp', slug='springfield', short='Springfield', name='City of Springfield', kind='city',
         tax='springfield', auth='city_springfield', debt='City of Springfield', audit='City of Springfield', contracts='City of Springfield',
         fees='City of Springfield', surtax='City of Springfield', fema=['Springfield, City of'], cra='sf', util='City of Springfield'),
    dict(key='parker', slug='parker', short='Parker', name='City of Parker', kind='city',
         tax='parker', auth='city_parker', debt='City of Parker', audit='City of Parker', contracts='City of Parker',
         fees='City of Parker', surtax='City of Parker', fema=['Parker, City Of'], cra='pk', util='City of Parker'),
    dict(key='mb', slug='mexico-beach', short='Mexico Beach', name='City of Mexico Beach', kind='city',
         tax='mexico_beach', auth='city_mexico_beach', debt='City of Mexico Beach', audit='City of Mexico Beach', contracts='City of Mexico Beach',
         fees='City of Mexico Beach', surtax='City of Mexico Beach', fema=['Mexico Beach, City Of'], cra=None, util='City of Mexico Beach'),
]
BY_KEY = {g['key']: g for g in GOVS}
BY_SLUG = {g['slug']: g for g in GOVS}
CRA_NAME = {'pc': 'Panama City CRA', 'pcb': 'Panama City Beach CRA', 'lh': 'Lynn Haven CRA', 'cw': 'Callaway CRA', 'sf': 'Springfield CRA', 'pk': 'Parker CRA'}


def vkey(s):
    s = re.sub(r'[^a-z0-9 ]', ' ', (s or '').lower())
    s = re.sub(r'\b(inc|llc|l l c|co|corp|corporation|company|ltd|lp|llp|pa|p a|the|of|and)\b', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


_cache = {}


def _load():
    if _cache:
        return _cache
    import sys
    sys.path.insert(0, HERE)
    from tax_page import build_data
    _cache['tax'] = build_data()
    _cache['da'] = _j('debt_audit', 'debt_audit.json')
    _cache['ct'] = _j('contracts', 'contracts.json')
    _cache['fees'] = _j('fees', 'fees_pay_officials.json')
    _cache['mi'] = _j('michael', 'michael.json')
    _cache['ts'] = _j('tourism', 'tourism_surtax.json')
    _cache['cra'] = _j('merged.json')
    _cache['votes'] = _j('votes', 'votes.json')
    _cache['civic_pop'] = _j('civic', 'population.json')
    _cache['budgets_detail'] = _j('civic', 'budgets_detail.json')
    _cache['meetings'] = _j('meetings', 'meetings.json')
    _cache['campaign'] = _j('campaign', 'campaign.json')
    _cache['records'] = _j('civic', 'records.json')
    return _cache


def gov_of_body(body):
    for k, pre in (('county', 'bay-'), ('pcb', 'pcb-'), ('pc', 'pc-'), ('lh', 'lh-'), ('cw', 'cw-'), ('sp', 'sp-'), ('parker', 'parker-'), ('mb', 'mb-'), ('schools', 'bds-')):
        if body.startswith(pre):
            return k
    return None


def is_split(v):
    if isinstance(v.get('by_member'), dict) and 'no' in v['by_member'].values():
        return True
    m = re.search(r'(\d+)\s*(?:-|to)\s*(\d+)', v.get('tally') or '')
    return bool(m and int(m.group(2)) > 0)


def profile(key):
    """Everything the site knows about one government, as plain data."""
    D = _load()
    g = BY_KEY[key]
    out = {'key': key, 'slug': g['slug'], 'short': g['short'], 'name': g['name'], 'kind': g['kind']}
    # budget + tax
    tg = next((x for x in D['tax']['govs'] if x.get('id') == g['tax']), None)
    if tg:
        out['budget'] = {'total': tg.get('total'), 'general_fund': tg.get('gf'), 'mills': tg.get('mills'), 'levy': tg.get('levy'),
                         'status': (tg.get('status') or [None, None])[1], 'revenue': tg.get('rev') or {}, 'spending': tg.get('exp') or {},
                         'sources': tg.get('src') or [], 'context': tg.get('ctx') or [], 'history': tg.get('hist') or [], 'actuals': tg.get('act') or []}
    if g['auth']:
        a = D['tax']['auth'].get(g['auth'])
        if a:
            out['millage'] = {'years': D['tax']['years'], 'rate': a.get('m'), 'rolled_back': a.get('rb'), 'levy': a.get('lv')}
    # population: state estimate from the debt file, else latest EDR actuals
    debt = [x for x in D['da']['debt'] if x['government'].startswith(g['debt'])] if g['debt'] else []
    pop = next((x.get('population_2025_estimate') for x in debt if x.get('population_2025_estimate')), None)
    pop_src = next((x.get('population_source_url') for x in debt if x.get('population_2025_estimate')), None)
    cp = D.get('civic_pop')
    if cp and cp.get('places'):
        nm = {'county': 'Bay County', 'schools': 'Bay County'}.get(key, g['short'])
        pl = cp['places'].get(nm)
        if pl and pl.get('est'):
            pop, pop_src = pl['est'], cp.get('source_url')
    if key == 'schools' and not pop:
        pop = profile_pop_county()
    out['population'] = pop
    out['population_source'] = pop_src
    # debt
    if debt:
        d0 = debt[0]
        out['debt'] = {'total': d0.get('total_debt'), 'fy': d0.get('fy'), 'note': d0.get('total_debt_note'), 'by_type': d0.get('by_type') or {},
                       'debt_service_year': d0.get('debt_service_year') or {}, 'issues': d0.get('issues') or [], 'ratings': d0.get('ratings'),
                       'source_url': d0.get('source_url'), 'related': [{'name': x['government'], 'total': x.get('total_debt')} for x in debt[1:]]}
    # audits (latest first)
    aud = [x for x in D['da']['audits'] if x['government'] == g['audit']]
    aud.sort(key=lambda x: x.get('fy') or '', reverse=True)
    if aud:
        out['audits'] = [{'fy': (x.get('fy') or '')[:6], 'opinion': x.get('opinion'), 'source_url': x.get('source_url'),
                          'findings': [{'title': f.get('title'), 'plain': f.get('plain'), 'repeat': bool(f.get('repeat'))} for f in x.get('findings') or []]} for x in aud]
    # votes
    vs = [v for v in D['votes']['votes'] if gov_of_body(v['body']) == key]
    if vs:
        vs.sort(key=lambda v: v.get('date') or '', reverse=True)
        out['votes'] = {'n': len(vs), 'split': sum(1 for v in vs if is_split(v)),
                        'recent_split': [{'date': v.get('date'), 'headline': v.get('headline'), 'tally': v.get('tally'), 'no': [n for n, x in (v.get('by_member') or {}).items() if x == 'no']}
                                         for v in vs if is_split(v)][:4]}
    # contracts
    if g['contracts']:
        cs = [c for c in D['ct']['contracts'] if c.get('government') == g['contracts']]
        if cs:
            by = defaultdict(float)
            for c in cs:
                by[c.get('vendor')] += c.get('amount') or 0
            out['contracts'] = {'n': len(cs), 'total': sum(c.get('amount') or 0 for c in cs),
                                'top_vendors': [{'vendor': v, 'total': t} for v, t in sorted(by.items(), key=lambda kv: -kv[1])[:5]],
                                'biggest': sorted(({'vendor': c.get('vendor'), 'purpose': c.get('purpose'), 'amount': c.get('amount'), 'date': c.get('date'), 'source_url': c.get('source_url')} for c in cs if c.get('amount')), key=lambda c: -c['amount'])[:3]}
    # sales tax projects
    if g['surtax']:
        ps = [p for p in D['ts']['infra_surtax']['projects'] if p.get('government') == g['surtax']]
        if ps:
            st = Counter(p.get('status') for p in ps)
            out['surtax'] = {'n': len(ps), 'completed': st.get('completed', 0), 'in_progress': st.get('in_progress', 0), 'not_started': st.get('not_started', 0)}
    # FEMA Hurricane Michael
    fa = [a for a in D['mi']['fema_pa']['by_applicant'] if a.get('applicant') in g['fema']]
    if fa:
        out['fema'] = {'projects': sum(a.get('projects') or 0 for a in fa), 'federal_obligated': sum(a.get('federal_obligated') or 0 for a in fa)}
    # CRA
    if g['cra']:
        nm = CRA_NAME[g['cra']]
        pays = [p for p in D['cra']['payments'] if p.get('cra') == nm]
        info = next((c for c in D['cra']['cras'] if c.get('cra') == nm), {})
        out['cra'] = {'id': g['cra'], 'name': nm, 'created': info.get('created'), 'records': len(pays),
                      'spent': sum(p['amount'] for p in pays if p.get('count') and p.get('amount') and p.get('status') in ('Spent', 'Committed'))}
    # officials
    fg = next((x for x in D['fees']['governments'] if x['name'] == g['fees']), None)
    if fg:
        out['officials'] = {'form': fg.get('form'), 'seats': fg.get('seats') or [], 'website': fg.get('website'), 'contact_url': fg.get('contact_url'), 'source_url': fg.get('source_url'),
                            'employees': (fg.get('ftes') or {}).get('value') if isinstance(fg.get('ftes'), dict) else fg.get('ftes')}
    # top pay
    pay = [p for p in D['fees']['pay'] if (p.get('government') or '').replace('City of ', '') in (g['short'], g['name'])]
    if pay:
        out['pay'] = sorted(({'title': p['title'], 'name': p.get('name'), 'annual': p.get('annual'), 'year': p.get('year'), 'source_url': p.get('source_url')} for p in pay if p.get('annual')), key=lambda p: -p['annual'])[:5]
    # utility bill
    if g['util']:
        from fees_page import BILL_PARTS
        for prov, parts in BILL_PARTS.items():
            if prov == g['util']:
                out['utility_bill'] = {'provider': prov, 'water_sewer': parts['ws'], 'garbage': parts['garbage'], 'other': parts['other'],
                                       'total': round(parts['ws'] + (parts['garbage'] or 0) + (parts['other'] or 0), 2)}
                break
    # optional datasets from research
    if D.get('meetings'):
        out['meetings'] = [m for m in D['meetings'].get('meetings', []) if any(b['id'] == m.get('board') and b.get('gov') == key for b in D['meetings'].get('boards', []))]
    if D.get('budgets_detail'):
        out['budget_detail'] = next((b for b in D['budgets_detail'].get('governments', []) if b.get('gov') == key), None)
    if D.get('records'):
        out['records'] = [a for a in D['records'].get('agencies', []) if a.get('gov') == key]
    # per-resident figures
    if pop:
        b = out.get('budget') or {}
        out['per_resident'] = {k: round(v / pop) for k, v in (('budget', b.get('total')), ('property_tax', b.get('levy')), ('debt', (out.get('debt') or {}).get('total'))) if v}
    return out


def profile_pop_county():
    D = _load()
    d = next((x for x in D['da']['debt'] if x['government'].startswith('Bay County (Board')), {})
    return d.get('population_2025_estimate')


def all_profiles():
    return [profile(g['key']) for g in GOVS]
