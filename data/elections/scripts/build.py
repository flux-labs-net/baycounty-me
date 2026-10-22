import csv, io, json, sys, re, collections, os
D = sys.argv[1]; OUT = sys.argv[2]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overrides import *
L = json.load(open(D + '/lists.json')); P = json.load(open(D + '/pages.json'))
ELEC = {'37': '2027 Municipal Super Tuesday (Apr 20, 2027)', '34': '2026 Lynn Haven Recall (Jan 20, 2026)', '35': '2026 Primary/General (Aug 18 / Nov 3, 2026)', '36': '2026 Municipal Super Tuesday (Apr 21, 2026)'}
def money(s): return round(float(s.replace('$', '').replace(',', '')), 2)
def clean(n):
    n = (n or '').replace('<br>', ' ').replace('&amp;', '&').replace('’', "'")
    return re.sub(r'\s+', ' ', n).strip()
def nk(n): return re.sub(r'[^a-z0-9]', '', (n or '').lower())
def mdy(s):
    m, d, y = s.split('/'); return f'{y}-{int(m):02d}-{int(d):02d}'
OFFICE_LABEL = {
 'County Commissioner, District 2': 'Bay County Commission, District 2', 'County Commissioner, District 4': 'Bay County Commission, District 4',
 'County Judge, Group 1': 'Bay County Judge, Group 1', 'County Judge, Group 4': 'Bay County Judge, Group 4',
 'School Board Member, District 2': 'School Board, District 2', 'School Board Member, District 3': 'School Board, District 3', 'School Board Member, District 5': 'School Board, District 5',
 'Callaway Commissioner Ward 1': 'Callaway Commission, Ward 1', 'Callaway Commissioner Ward 2': 'Callaway Commission, Ward 2',
 'Panama City Beach Council Ward 1': 'Panama City Beach Council, Ward 1', 'Panama City Beach Council Ward 3': 'Panama City Beach Council, Ward 3',
 'Lake Powell CDD Seat 2': 'Lake Powell Community Development District, Seat 2', 'Lake Powell CDD Seat 5': 'Lake Powell Community Development District, Seat 5',
 'Mexico Beach Council Member Group 4': 'Mexico Beach Council, Group 4', 'Mexico Beach Council Member Group 5': 'Mexico Beach Council, Group 5',
 'Springfield Mayor': 'Springfield Mayor', 'Springfield Commissioner Ward 3': 'Springfield Commission, Ward 3', 'Springfield Commissioner Ward 4': 'Springfield Commission, Ward 4',
 'Lynn Haven Mayor': 'Lynn Haven Mayor (recall election)'}
PARTY = {'REP': 'Republican', 'DEM': 'Democrat', 'LIB': 'Libertarian', 'NPA': 'No Party Affiliation', 'NON': 'Nonpartisan'}
BAY_CITIES = {'panama city', 'panama city beach', 'lynn haven', 'callaway', 'springfield', 'parker', 'mexico beach', 'youngstown', 'fountain',
              'southport', 'bayou george', 'tyndall afb', 'tyndall air force base', 'laguna beach', 'pc', 'pcb', 'lh', 'panama city bch', 'panama cty', 'panama city fl',
              'pc beach', 'west bay', 'sunny hills', 'cedar grove', 'hiland park', 'pana city', 'panama ciity', 'panama city becah', 'panama cit'}
BAY_ZIPS = {'32401', '32402', '32403', '32404', '32405', '32406', '32407', '32408', '32409', '32410', '32411', '32412', '32413', '32417', '32444', '32466', '32438'}
def county(r):
    city = nk(clean(r['city'])); st = clean(r['state']).upper().replace('.', ''); z = (r['zip'] or '')[:5]
    if not city and not z: return None
    cn = clean(r['city']).lower().rstrip('.').strip()
    if cn in BAY_CITIES or z in BAY_ZIPS:
        if st in ('', 'FL', 'F', 'FLORIDA', 'FLA') or z in BAY_ZIPS: return True
    return False
def band(a):
    if a < 100: return 'under_100'
    if a < 500: return '100_499'
    if a < 1000: return '500_999'
    return '1000_plus'
ITEM = {'CH': 'check', 'CA': 'cash', 'IK': 'in-kind', 'LO': 'loan', 'RE': 'refund', 'IN': 'interest', 'MO': 'money order', 'DI': 'distribution', 'RM': 'reimbursement'}
ORG_RE = re.compile(r"\b(inc|llc|l\.l\.c|corp|co|company|pa|pllc|ltd|lp|llp|holdings|group|bank|credit union|associates|association|enterprises|services|properties|realty|construction|partners|trust company|foundation|club|church|party|committee|pac|realtors|chamber)\b\.?", re.I)
PAC_RE = re.compile(r"(realtors|political|\bpac\b|committee|\becc\b|executive committee|republican|democrat|federation|fund\b)", re.I)

def rows(ca):
    p = f'{D}/exp_{ca}.csv'
    b = open(p, 'rb').read()
    try: t = b.decode('utf-8')
    except UnicodeDecodeError: t = b.decode('latin-1')
    if not t.startswith('"rpt code"'): return []
    return list(csv.DictReader(io.StringIO(t)))

def apply_amend(R, review, who):
    items = [r for r in R if r['Amend. code'] != 'D']
    for r in [r for r in R if r['Amend. code'] == 'D']:
        if True:
            hit = None
            for i, x in enumerate(items):
                if x['Cont/Exp'] == r['Cont/Exp'] and nk(x['name']) == nk(r['name']) and abs(float(x['amount']) - float(r['amount'] or 0)) < 0.005 and x['item date'] == r['item date']:
                    hit = i; break
            if hit is None:
                for i, x in enumerate(items):
                    if x['Cont/Exp'] == r['Cont/Exp'] and nk(x['name']) == nk(r['name']) and abs(float(x['amount']) - float(r['amount'] or 0)) < 0.005:
                        hit = i; break
            if hit is None: review.append(f'{who}: unmatched D line rpt {r["rpt code"]} line {r["line number"]} ({r["Cont/Exp"]} {clean(r["name"]) or "blank"} {r["amount"]})')
            else: items.pop(hit)
    return items

def self_match(name, cand):
    toks = [t for t in re.sub(r'[^a-z ]', ' ', cand.lower()).split() if t not in ('dr', 'jr', 'sr', 'ii', 'iii', 'mr', 'mrs', 'ms')]
    first, last = toks[0], toks[-1]
    n = nk(name)
    return last in n and (first in n or FIRST_ALIAS.get(first, '#') in n)

def classify_c(r, cand):
    n = clean(r['name']); low = n.lower().rstrip('.'); code = r['cont. type']
    if low in TYPE_OVERRIDE: return TYPE_OVERRIDE[low]
    if name_hash(low) in TYPE_OVERRIDE_HASHED: return TYPE_OVERRIDE_HASHED[name_hash(low)]
    if self_match(n, cand) and code in ('I', 'S', ''): return 'self'
    if code == 'S': return 'self' if self_match(n, cand) else ('business' if ORG_RE.search(n) else 'individual')
    if re.match(r'^friends of ', low) or re.search(r'campaign account|for (county|school|city)', low): return 'committee'
    if re.search(r'republican executive|democratic executive|republican party|democratic party|\brec\b|\bdec\b', low): return 'party'
    if code in ('C', 'F', 'E'): return 'pac'
    if PAC_RE.search(n) and code in ('B', 'O', 'I'): return 'pac'
    if code == 'B': return 'business'
    if code == 'O': return 'business' if ORG_RE.search(n) else 'other'
    if code == 'I': return 'business' if ORG_RE.search(n) else 'individual'
    return 'other'

def exp_is_person(name):
    low = clean(name).lower().rstrip('.')
    if low in {x.rstrip('.') for x in PAYEE_PERSON}: return True
    if low in PAYEE_ORG: return False
    if low in PAYEE_PERSON: return True
    if name_hash(low) in PAYEE_PERSON_HASHED: return True
    return False

cands = []; gaps = []; allpayees = collections.Counter(); review = []
for o in L:
    if o['sec'] != 'candidates': continue
    ca = re.search(r'ca=(\d+)', o['href']).group(1); e = o['e']
    txt = o['txt']; nm = clean(txt[0]); m = re.match(r'(.*?)\s*\((\w+)\)$', nm)
    name, pcode = (m.group(1), m.group(2)) if m else (nm, None)
    status = ' '.join(v for v in txt[1:] if not v.startswith('$')).replace('( ', '(').replace(' )', ')')
    status = re.sub(r'\s+', ' ', status.replace('(Active-', 'Active -').replace('(Inactive - ', 'Inactive - ').replace('(', '').replace(')', '')).strip()
    mon, ik, ex = [money(v) for v in txt if v.startswith('$')][:3]
    pg = P[ca]; reps = pg['reports']
    # reconcile page vs list
    notes = []
    if reps:
        sm = round(sum(r['mon'] for r in reps), 2); si = round(sum(r['ik'] for r in reps), 2); se = round(sum(r['exp'] for r in reps), 2)
        if (sm, si, se) != (mon, ik, ex): notes.append(f'Sum of report rows on candidate page ({sm}/{si}/{se}) differs from list summary ({mon}/{ik}/{ex}).')
    R = apply_amend(rows(ca), review, name)
    C = [r for r in R if r['Cont/Exp'] == 'C']; X = [r for r in R if r['Cont/Exp'] == 'E']
    # itemized sums
    it_mon = round(sum(float(r['amount'] or 0) for r in C if r['item type'] != 'IK'), 2)
    it_ik = round(sum(float(r['amount'] or 0) for r in C if r['item type'] == 'IK'), 2)
    it_ex = round(sum(float(r['amount'] or 0) for r in X), 2)
    diffs = []
    for lab, a, b in (('monetary', it_mon, mon), ('in-kind', it_ik, ik), ('expenditures', it_ex, ex)):
        if abs(a - b) > 0.005: diffs.append(f'{lab}: itemized {a:,.2f} vs SOE {b:,.2f} (diff {a-b:+,.2f})')
    if not R and (mon or ik or ex): diffs.append('no itemized export available')
    recon = 'itemized matches summary' if not diffs else '; '.join(diffs)
    if not R and not (mon or ik or ex): recon = 'no activity reported (export empty; all SOE totals $0.00)'
    # contributions
    fi = dict(count=0, total=0.0, bands={b: {'count': 0, 'total': 0.0} for b in ('under_100', '100_499', '500_999', '1000_plus')},
              in_county={'count': 0, 'total': 0.0}, out_of_county={'count': 0, 'total': 0.0}, location_unknown={'count': 0, 'total': 0.0}, refunds_to_individuals=0.0)
    donors = set()
    bt = collections.Counter(); contributors = []; selfc = 0.0; selfl = 0.0; loans = 0.0; interest = 0.0; nc = 0
    for r in C:
        a = round(float(r['amount'] or 0), 2); it = r['item type']; typ = classify_c(r, name)
        if it == 'LO': loans += a
        if it == 'IN': interest += a
        if it in ('CH', 'CA', 'IK', 'LO', 'MO') and a > 0: nc += 1
        if typ == 'individual':
            bt['individual'] += a; fi['total'] += a
            if a > 0 and it != 'RE':
                fi['count'] += 1; donors.add(nk(r['name']))
                b = fi['bands'][band(a)]; b['count'] += 1; b['total'] += a
                loc = county(r); k = 'location_unknown' if loc is None else ('in_county' if loc else 'out_of_county')
                fi[k]['count'] += 1; fi[k]['total'] += a
            else:
                fi['refunds_to_individuals'] += a
                loc = county(r); k = 'location_unknown' if loc is None else ('in_county' if loc else 'out_of_county')
                fi[k]['total'] += a
            continue
        if typ == 'self':
            bt['candidate_self'] += a
            if it == 'LO': selfl += a
            else: selfc += a
            contributors.append({'name': name + ' (candidate)', 'city': None, 'type': 'candidate', 'amount': a, 'date': r['item date'] or None, 'kind': ITEM.get(it, it)})
            continue
        key = {'business': 'business', 'pac': 'pac', 'committee': 'pac', 'party': 'party', 'other': 'other'}[typ]
        if it == 'IN': key = 'other'
        bt[key] += a
        contributors.append({'name': clean(r['name']), 'city': clean(r['city']) or None, 'type': typ if it != 'IN' else 'other', 'amount': a, 'date': r['item date'] or None, 'kind': ITEM.get(it, it)})
    for k in ('total', 'refunds_to_individuals'): fi[k] = round(fi[k], 2)
    for b in fi['bands'].values(): b['total'] = round(b['total'], 2)
    for k in ('in_county', 'out_of_county', 'location_unknown'): fi[k]['total'] = round(fi[k]['total'], 2)
    fi['unique_donors_approx'] = len(donors)
    if not fi['refunds_to_individuals']: del fi['refunds_to_individuals']
    if not fi['location_unknown']['count'] and not fi['location_unknown']['total']: del fi['location_unknown']
    contributors.sort(key=lambda x: (x['date'] or '', x['name']))
    # expenditures
    pay = collections.defaultdict(lambda: {'total': 0.0, 'purposes': collections.Counter(), 'n': 0, 'names': collections.Counter()})
    for r in X:
        a = float(r['amount'] or 0); pn = clean(r['name']); allpayees[pn] += 1
        if exp_is_person(pn) and not self_match(pn, name): key = 'Payments to individuals'
        elif self_match(pn, name): key = 'Payments to the candidate (loan repayments, reimbursements, surplus returned)'
        else: key = canon_payee(pn)
        if r['item type'] == 'RE' and key == 'Payments to individuals': key = 'Refunds to individual contributors'
        p = pay[key]; p['total'] += a; p['n'] += 1; p['names'][pn] += 1
        pur = clean(r['description']) or ITEM.get(r['item type'], r['item type'])
        if r['item type'] == 'DI': pur = 'Distribution of surplus: ' + pur
        if r['item type'] == 'RE': pur = 'Refund: ' + pur if clean(r['description']) else 'Refund'
        p['purposes'][pur] += a
    top = sorted(pay.items(), key=lambda kv: -kv[1]['total'])[:15]
    tops = []
    for k, v in top:
        purs = [p for p, _ in v['purposes'].most_common()]
        purpose = '; '.join(purs[:4]) + (f'; and {len(purs)-4} other descriptions' if len(purs) > 4 else '')
        if k.startswith('Payments to individuals') or k.startswith('Refunds to individual'):
            purpose = '; '.join(purs[:4]) + (f'; and {len(purs)-4} other descriptions' if len(purs) > 4 else '')
        tops.append({'payee': k, 'total': round(v['total'], 2), 'payments': v['n'], 'purpose': purpose})
    # latest report
    latest = None; through = None
    if reps:
        lr = max(reps, key=lambda r: (mdy(r['end']), int(r['rpt'])))
        due = [d for c, d in pg['avail'] if c == lr['code']]
        latest = f"{lr['code']}{' (amended)' if lr['amended'] else ''} / period {mdy(lr['start'])} to {mdy(lr['end'])}" + (f" / due {mdy(due[-1])}" if due else '')
        through = mdy(lr['end'])
        if any(r['code'].startswith('TR') or r['code'] in ('MTR', 'MTRQ', 'RTRQ') for r in reps):
            notes.append('Campaign filed a termination report (' + ', '.join(sorted({r['code'] for r in reps if r['code'].startswith('TR') or r['code'] in ('MTR','MTRQ','RTRQ')})) + '); account is closed.')
    else:
        notes.append('No campaign finance reports listed on the SOE candidate page.')
    term = any(r['code'].startswith('TR') or r['code'] in ('MTR', 'MTRQ', 'RTRQ') for r in reps)
    coh = None if term or not reps else round(mon - ex, 2)
    if term and abs(mon - ex) > 0.005:
        notes.append(f'Monetary contributions minus expenditures/distributions = {mon-ex:,.2f} at termination (SOE figures).')
    if loans and not term: notes.append(f'Includes {loans:,.2f} in loans; loans count in SOE monetary contributions.')
    if interest: notes.append(f'Includes {interest:,.2f} bank interest (filed as a contribution item).')
    notes += NOTES.get(ca, [])
    cands.append({
        'name': name, 'office': OFFICE_LABEL.get(o['office'], o['office']), 'soe_office': o['office'], 'election': ELEC[e], 'party': PARTY.get(pcode, pcode),
        'soe_status': status, 'soe_campaign_name': nm, 'cand_id': int(ca),
        'report_url': 'https://www.voterfocus.com' + o['href'],
        'export_url': f'https://www.voterfocus.com/CampaignFinance/export.php?op=CFINANCE&cand_id={ca}&dhc=0&county=bay',
        'latest_report': latest, 'through': through,
        'total_raised': round(mon + ik, 2), 'monetary': mon, 'in_kind': ik, 'loans': round(loans, 2), 'total_spent': ex,
        'cash_on_hand_estimate': coh, 'n_contributions': nc,
        'from_individuals': fi, 'candidate_self': {'contributions': round(selfc, 2), 'loans': round(selfl, 2)},
        'by_type_total': {k: round(bt.get(k, 0.0), 2) for k in ('individual', 'business', 'pac', 'party', 'candidate_self', 'other')},
        'contributors': contributors, 'top_expenditures': tops, 'reconciliation': recon, 'notes': notes})
json.dump(cands, open(OUT, 'w'), indent=1)
json.dump(sorted(allpayees), open(OUT + '.payees.json', 'w'), indent=0)
for x in review: print('REVIEW', x)
for c in cands:
    s = sum(c['by_type_total'].values())
    flag = '' if abs(s - c['total_raised']) < 0.01 else f' BT-MISMATCH {s:.2f}'
    print(c['cand_id'], c['name'][:20].ljust(20), c['monetary'], c['in_kind'], c['total_spent'], c['through'], '|', c['reconciliation'], flag)
