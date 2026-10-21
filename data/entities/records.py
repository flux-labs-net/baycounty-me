"""Every record on the site that names who was paid, as one flat list (used by build_entities.py and the vendor pages).

Each record: {src, idx, gov_id, name, amount, date, what, url, extra}
  src: contract | change_order | emergency | register | tdc | cra
  idx: position in its source list (registers and TDC: "<list>/<fy>/<i>")
Nothing is summed here; register and TDC rows are already totals for a fiscal year (or the months covered).
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..')
sys.path.insert(0, HERE)
import ids  # noqa: E402

NOT_NAMED = re.compile(r'^(not (named|stated|applicable)|various|vendor not named|contractors? (\(s\) )?not named|contractor\(s\) not named|seller not named|grant recipient|'
                       r'property owners|bondholders|\d+ (downtown|st\. andrews|businesses|homeowners|residential|local|participating)|five |three |four |six |seven |twelve |owners? of |homeowners?|downtown (north )?(homeowners|businesses)|'
                       r'st\. andrews businesses|local business|residential property|storefront|hardware store|commercial property|glenwood homeowners|'
                       r'south thomas drive|richard jackson blvd construction contractor|roberts hall and mcmullin)', re.I)


def _j(*p):
    try:
        return json.load(open(os.path.join(DATA, *p)))
    except FileNotFoundError:
        return None


def payee_parts(name):
    """A CRA payee field can name two parties ('World Changers / First Baptist Church'); keep it whole for matching,
    but strip an explanatory parenthetical ('Inland Construction & Engineering (bid awarded May 28, 2024)')."""
    return name


def all_records():
    out = []
    ct = _j('contracts', 'contracts.json')
    for i, c in enumerate(ct['contracts']):
        out.append({'src': 'contract', 'idx': i, 'gov_id': ids.gov_id(c['government']), 'name': c['vendor'], 'amount': c.get('amount'), 'date': c.get('date'),
                    'what': c.get('purpose'), 'url': c.get('source_url'), 'extra': {'method': c.get('method')}})
    for i, c in enumerate(ct['change_orders']):
        out.append({'src': 'change_order', 'idx': i, 'gov_id': ids.gov_id(c['government']), 'name': c['vendor'], 'amount': c.get('change_amount'), 'date': c.get('date'),
                    'what': c.get('project'), 'url': c.get('source_url'), 'extra': {'new_total': c.get('new_total'), 'reason': c.get('reason')}})
    for i, c in enumerate(ct.get('emergency_purchases') or []):
        out.append({'src': 'emergency', 'idx': i, 'gov_id': ids.gov_id(c['government']), 'name': c['vendor'], 'amount': c.get('amount'), 'date': c.get('date'),
                    'what': c.get('purpose'), 'url': c.get('source_url'), 'extra': {}})
    for ri, g in enumerate(ct['registers']):
        seen = set()
        # top_vendors is the vendor-only ranking; top_payees_all also has non-vendors (payroll, other governments). Use each name once per register.
        for lst in ('top_vendors', 'top_payees_all'):
            for i, v in enumerate(g.get(lst) or []):
                n = v.get('vendor') or v.get('payee')
                if n in seen:
                    continue
                seen.add(n)
                if lst == 'top_payees_all' and (v.get('category') or '').startswith('non-vendor'):
                    continue
                out.append({'src': 'register', 'idx': f'{ri}/{lst}/{i}', 'gov_id': ids.gov_id(g['government']), 'name': n, 'amount': v.get('amount'), 'date': f'FY{g["fy"]}',
                            'what': f'Check register FY{g["fy"]}, ' + (f'{len(g.get("months_covered") or [])} of 12 months' if g.get('months_covered') else 'months covered as listed'),
                            'url': g.get('url'), 'extra': {'fy': g['fy'], 'months_missing': g.get('months_missing') or []}})
    pay = _j('money', 'payments.json')
    for gi, g in enumerate(pay['governments'] if pay else []):
        for i, v in enumerate(g['vendors']):
            out.append({'src': 'tdc', 'idx': f'{gi}/{i}', 'gov_id': ids.gov_id(g['gov']), 'name': v['vendor'], 'amount': v.get('total'), 'date': ', '.join(sorted(v.get('by_fy') or {})),
                        'what': f'{g["name"].split(" - ")[0]}: {v.get("n_payments")} payments', 'url': (g.get('source_urls') or [None])[0],
                        'extra': {'by_fy': v.get('by_fy'), 'n_payments': v.get('n_payments'), 'agency': g['gov']}})
    m = _j('merged.json')
    for i, p in enumerate(m['payments'] if m else []):
        out.append({'src': 'cra', 'idx': i, 'gov_id': ids.gov_id(p['city']), 'name': p['payee'], 'amount': p.get('amount'), 'date': p.get('date_or_fy'),
                    'what': p.get('purpose'), 'url': p.get('source_url'), 'extra': {'cra': p['cra'], 'status': p.get('status'), 'count': p.get('count'), 'overlap': p.get('overlap')}})
    return out


def donations():
    """Business contributions only (individuals are never listed), from officeholders' campaigns and 2026 candidates."""
    out = []
    c = _j('campaign', 'campaign.json')
    for ci, cd in enumerate(c['candidates'] if c else []):
        for i, x in enumerate(cd.get('contributors') or []):
            if x.get('type') == 'business':
                out.append({'src': 'officeholders', 'cand_idx': ci, 'idx': i, 'name': x['name'], 'amount': x.get('amount'), 'date': x.get('date'), 'kind': x.get('kind'),
                            'candidate': cd['official'], 'office': cd.get('office'), 'gov': cd.get('gov'), 'election': cd.get('election'), 'report_url': cd.get('report_url')})
    f = _j('elections', 'finance_2026.json')
    for ci, cd in enumerate(f['candidates'] if f else []):
        for i, x in enumerate(cd.get('contributors') or []):
            if x.get('type') == 'business':
                out.append({'src': 'candidates_2026', 'cand_idx': ci, 'idx': i, 'name': x['name'], 'amount': x.get('amount'), 'date': x.get('date'), 'kind': x.get('kind'),
                            'candidate': cd['name'], 'office': cd.get('office'), 'gov': None, 'election': cd.get('election'), 'report_url': cd.get('report_url')})
    return out
