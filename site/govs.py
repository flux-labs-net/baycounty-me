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


# key, slug, short name, full name, kind, and how each dataset names it: from places/<id>/place.json
from place import governments as _governments, NAME as PLACE_NAME
GOVS = _governments()
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
                         'sources': tg.get('src') or [], 'context': tg.get('ctx') or [], 'history': tg.get('hist') or [], 'actuals': tg.get('act') or [], 'next': tg.get('next')}
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
        nm = PLACE_NAME if g['kind'] in ('county', 'schools') else g['short']
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
        bd = out['budget_detail']
        # newer research found adopted budgets the tax data lacks (Callaway, Parker): use them where the tax data has no adopted figure
        if bd and bd.get('status') == 'adopted' and 'budget' in out and not str(out['budget'].get('status') or '').lower().startswith('adopted'):
            gf = next((f.get('amount') for f in bd.get('funds') or [] if 'general' in str(f.get('type') or f.get('name') or '').lower()), None)
            out['budget'].update({'total': bd.get('total'), 'general_fund': gf or out['budget'].get('general_fund'),
                                  'status': 'Adopted ' + str(bd.get('fiscal_year') or '').split(' (')[0]})
    if D.get('records'):
        out['records'] = [a for a in D['records'].get('agencies', []) if a.get('gov') == key]
    # per-resident figures
    if pop:
        b = out.get('budget') or {}
        out['per_resident'] = {k: round(v / pop) for k, v in (('budget', b.get('total')), ('property_tax', b.get('levy')), ('debt', (out.get('debt') or {}).get('total'))) if v}
    return out


def profile_pop_county():
    D = _load()
    county = next(g for g in GOVS if g['kind'] == 'county')
    d = next((x for x in D['da']['debt'] if x['government'].startswith(county['debt'])), {})
    return d.get('population_2025_estimate')


def all_profiles():
    return [profile(g['key']) for g in GOVS]
