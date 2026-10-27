"""State road projects (FDOT) for one place (default fl-bay): data/roads/<county>/fdot.json.

From the Florida Department of Transportation's public GIS services (data/roads/<county>/sources.json):

  * contracts: every FDOT construction and maintenance contract in the county (All Construction Contracts layer),
    one row per contract: what and where, contractor, current contract amount, letting, start, estimated finish and
    final acceptance dates. Contracts that ended before 2016 are left out.
  * work_program: the projects in FDOT's current adopted five-year work program in the county (Work Program Current
    layers), one row per project and phase: what and where, the phase (design, right of way, construction...), its
    fiscal years and the project's status. The GIS layers don't carry dollar amounts.

Run: python3 data/roads/fetch_fdot.py   (PLACE=fl-bay by default).
"""
import datetime as dt, json, os, re, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'entities'))
import cutoff  # noqa: E402

PLACE = os.environ.get('PLACE', 'fl-bay')
D = os.path.join(HERE, PLACE.split('-', 1)[-1])
CFG = json.load(open(os.path.join(D, 'sources.json')))
F = CFG['fdot']
UA = {'User-Agent': 'BayCounty.me data refresh (+https://baycounty.me/data-sources)'}

CONTRACT_TYPE = {'CC': 'Construction', 'CDB': 'Design-build', 'CFR': 'Construction', 'CLS': 'Lump sum construction', 'CSL': 'Construction',
                 'MC': 'Maintenance', 'MAM': 'Asset maintenance', 'MEC': 'Maintenance', 'MLC': 'Maintenance', 'TO': 'Task order', 'TOPB': 'Task order'}
TODAY = dt.date.today().isoformat()
STATUS = {'ACTV': 'Under way', 'PEND': 'Awarded, not started', 'CMPL': 'Complete'}


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                raise


def query(layer, where, fields='*', geometry=False):
    out, start = [], 0
    while True:
        q = urllib.parse.urlencode({'where': where, 'outFields': fields, 'returnGeometry': str(geometry).lower(), 'outSR': 4326,
                                    'resultOffset': start, 'resultRecordCount': 1000, 'f': 'json'})
        d = get(f'{layer}/query?{q}')
        if 'error' in d:
            raise SystemExit(f'{layer}: {d["error"]}')
        out += d['features']
        if not d.get('exceededTransferLimit') or not d['features']:
            return out
        start += len(d['features'])


def day(v):
    if isinstance(v, (int, float)) and abs(v) > 1e11:
        d = dt.datetime.fromtimestamp(v / 1000, dt.UTC).date()
        return d.isoformat() if d.year > 1901 else None
    return None


def s(v):
    v = re.sub(r'\s+', ' ', str(v or '')).strip()
    return v or None


def dms(v):
    """FDOT stores latitude/longitude as DDMMSS integers (301114 = 30 deg 11' 14")."""
    try:
        v = int(v)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return round(v // 10000 + (v // 100 % 100) / 60 + (v % 100) / 3600, 5)


WORK = {'ADD LANES & RECONSTR': 'Add lanes and reconstruct', 'RIGHT OF WAY - FUTUR': 'Right of way for a future project', 'BRIDGE-REPAIR/REHABI': 'Bridge repair',
        'INTERSECTION IMPROVE': 'Intersection improvement', 'TRAFFIC OPS IMPROVEM': 'Traffic operations improvement', 'PD&E/EMO STUDY': 'Project study (PD&E)',
        'INTERCHANGE - ADD LA': 'Interchange: add lanes', 'NEW ROAD CONSTRUCTIO': 'New road construction', 'RAIL CAPACITY PROJEC': 'Rail capacity project',
        'PRELIMINARY ENGINEER': 'Design (preliminary engineering)', 'BIKE LANE/SIDEWALK': 'Bike lane and sidewalk', 'BIKE PATH/TRAIL': 'Bike path or trail', 'PRELIM ENG FOR FUTUR': 'Design for a future project'}
STAGE = {'CONST.COMPLETE': 'Construction complete', 'ROW ACQUISITION BEG.': 'Buying land', 'PRE-CONST.UNDERWAY': 'Design under way',
         'ADOPTED, NOT BEGUN': 'Not started', 'UNDER CONSTRUCTION': 'Under construction', 'ADVERTISED': 'Out for bids', 'BIDS RECEIVED': 'Bids received',
         'CONTRACT EXECUTED': 'Contract signed', 'WORK IN PROGRESS': 'Work in progress'}


def fix(t):
    """FDOT's fixed-width text runs some words together: 'FROMSR 30A', 'LANETO', 'EOF CR 2312'."""
    t = re.sub(r'\b(FROM|TO)(SR|CR|US|NORTH|SOUTH|EAST|WEST)\b', r'\1 \2', t or '')
    t = re.sub(r'\b(\w+?)TO (EAST|WEST|NORTH|SOUTH|E|W|N|S) OF\b', lambda m: (m.group(1) + ' TO ' if m.group(1).endswith(('LANE', 'ROAD', 'AVE', 'ST', 'DR')) else m.group(0)) + (m.group(2) + ' OF' if m.group(1).endswith(('LANE', 'ROAD', 'AVE', 'ST', 'DR')) else ''), t)
    t = re.sub(r'\bEOF\b', 'E OF', t)
    return t


VOCAB = set()


def unsplit(t):
    """Join words FDOT's fixed-width text broke in two ('BR IDGE', 'RESUR FACING') when the joined word appears elsewhere."""
    w = (t or '').split(' ')
    out = []
    for x in w:
        keep = {'SR', 'CR', 'US', 'OF', 'TO', 'AT', 'ST', 'RD', 'NO', 'N', 'S', 'E', 'W', 'AND', 'FROM', 'OVER'}
        a, b = (out[-1].upper() if out else ''), x.upper()
        if out and (a + b) in VOCAB and a not in keep and b not in keep and not (a in VOCAB and b in VOCAB):
            out[-1] += x
        else:
            out.append(x)
    return ' '.join(out)


def title(t):
    """FDOT descriptions are all caps; keep road numbers and abbreviations as they are."""
    t = fix(unsplit(fix(t)))
    keep = {'SR', 'US', 'CR', 'I', 'PC', 'BCH', 'PKWY', 'E', 'W', 'N', 'S', 'NE', 'NW', 'SE', 'SW', 'ADA', 'CEI', 'PD&E', 'ITS', 'RR', 'BLVD', 'FDOT'}
    words = []
    for w in (t or '').split(' '):
        core = re.sub(r'[^A-Z&]', '', w)
        words.append(w if (core in keep or any(c.isdigit() for c in w)) else w.capitalize())
    return ' '.join(words).replace('Of ', 'of ').replace('To ', 'to ').replace('And ', 'and ').replace('At ', 'at ').replace('From ', 'from ').strip() or None


def contracts():
    feats = query(F['contracts_url'], f"PROJECTCOUNTY = '{F['county_code']}' OR PROJECTCOUNTYNAME = '{F['county_name'].title()}'")
    by = {}
    for ft in feats:
        a = ft['attributes']
        cid = s(a['CONTRACTNUMBER'])
        if not cid:
            continue
        r = by.get(cid)
        fin = s(a.get('FINANCIALPROJECTSEQUENCE'))
        if 'DO NOT USE' in (s(a['CONTRACTPROJECTDESCRIPTION']) or '').upper():
            continue  # FDOT placeholder records (insurance, accounting), not road work
        if r and fin and fin not in r['_fin']:  # each financial project on the contract carries its own amount
            r['_fin'][fin] = a.get('PRESENTPROJECTAMOUNT')
            continue
        if r:  # one row per road segment: add up the length and keep each road
            r['length_miles'] = round((r['length_miles'] or 0) + (a.get('Length') or 0), 2)
            if s(a.get('ROADNAME')) and s(a['ROADNAME']) not in r['_roads']:
                r['_roads'].append(s(a['ROADNAME']))
            continue
        ended = day(a['FINALACCEPTANCEDATE']) or day(a['PAIDOFFDATE']) or day(a['TERMINATEDDATE'])
        # FDOT leaves many old contracts marked active; trust its "active" map flag, then the dates
        code, est = s(a['CONTRACTSTATUS']), day(a['ADJESTIMATEDCOMPLETIONDATE'])
        if day(a['TERMINATEDDATE']):
            status = 'Terminated'
        elif s(a.get('FDOTActive')) == 'Y':
            status = 'Under way'
        elif code == 'PEND':
            status = 'Awarded, not started'
        elif ended or code == 'CMPL' or (est and est < TODAY):
            status = 'Complete'
        else:
            status = STATUS.get(code, code)
        ctype = s(a['CONTRACTTYPE'])
        desc = s(a['CONTRACTPROJECTDESCRIPTION'])
        by[cid] = {
            'contract_id': cid, 'project_id': s(a['ITEMANDSEG']), 'description': title(desc), 'description_fdot': desc,
            'contract_type': CONTRACT_TYPE.get(ctype, 'Other'), 'contract_type_code': ctype, 'status': status, 'active_on_fdot_map': s(a.get('FDOTActive')) == 'Y',
            'contractor': s(a['VENDORNAME']), 'amount': a.get('PRESENTPROJECTAMOUNT'),
            'let_date': day(a['LETTINGDATE']) or day(a['PROJECTEDLETTINGDATE']), 'executed_date': day(a['EXECUTIONDATE']),
            'work_began_date': day(a['WORKBEGANDATE']) or day(a['TIMEBEGANDATE']), 'estimated_completion_date': day(a['ADJESTIMATEDCOMPLETIONDATE']),
            'final_acceptance_date': day(a['FINALACCEPTANCEDATE']), 'ended_date': ended,
            'bid_days': a.get('BIDDAYS'), 'length_miles': round(a.get('Length') or 0, 2) or None,
            'lat': dms(a.get('LATITUDE')), 'lng': -dms(a.get('LONGITUDE')) if dms(a.get('LONGITUDE')) else None,
            'district': s(a.get('CONTRACTDISTRICT')), 'website': s(a.get('Website')),
            'data_date': day(a.get('PULLDATE')), '_fin': {fin: a.get('PRESENTPROJECTAMOUNT')}, '_roads': [s(a['ROADNAME'])] if s(a.get('ROADNAME')) else [],
            'source_url': F['contracts_url'],
        }
    rows = []
    for r in by.values():
        fins = r.pop('_fin')
        amts = [v for v in fins.values() if isinstance(v, (int, float))]
        r['amount'] = round(sum(amts), 2) if amts else None
        r['financial_projects'] = len(fins)
        r['roads'] = ', '.join(re.sub(r'\s+', ' ', x) for x in r.pop('_roads')) or None
        last = r['ended_date'] or r['estimated_completion_date'] or r['work_began_date'] or r['let_date']
        if cutoff.keep(last) or (r['status'] == 'Awarded, not started' and not last):
            rows.append(r)
    rows.sort(key=lambda r: (r['let_date'] or '', r['contract_id']), reverse=True)
    return rows


def work_program():
    root = get(f"{F['work_program_url']}?f=json")
    phases, segs = {}, None
    for L in root['layers']:
        if L['name'].strip().lower() == 'item segments':
            segs = L['id']
            continue
        d = get(f"{F['work_program_url']}/{L['id']}/query?" + urllib.parse.urlencode({'where': '1=1', 'outFields': 'WPPHAZGP', 'returnDistinctValues': 'true', 'returnGeometry': 'false', 'f': 'json'}))
        for ft in d.get('features', []):
            phases[ft['attributes']['WPPHAZGP']] = L['name'].replace(' Phase', '').strip()
    feats = query(f"{F['work_program_url']}/{segs}", f"CONTYDOT = '{F['county_code']}'")
    by = {}
    for ft in feats:
        a = ft['attributes']
        key = (s(a['ITMSEG']), s(a['WPPHAZGP']))
        r = by.get(key)
        if not r:
            r = by[key] = {'project_id': key[0], 'phase_code': key[1], 'phase': phases.get(key[1], f'Other (code {key[1]})'),
                           'description': title(s(a['LOCALFULL'])), 'description_fdot': s(a['LOCALFULL']), 'work_type': WORK.get(s(a['WPWKMIXN']) or '', (s(a['WPWKMIXN']) or '').capitalize() or None),
                           'project_status': STAGE.get(s(a['WPITSTNM']) or '', (s(a['WPITSTNM']) or '').capitalize() or None), '_years': set(), '_roads': set(), 'length_miles': 0.0,
                           'district': s(a['MANDISDV']), 'source_url': f"{F['work_program_url']}/{segs}"}
        if a.get('FISCALYR'):
            r['_years'].add(int(a['FISCALYR']))
        if s(a.get('RDWYID')) and s(a['RDWYID']) not in r['_roads']:
            r['_roads'].add(s(a['RDWYID']))
            r['length_miles'] += max(0, (a.get('ENDSECPT') or 0) - (a.get('BEGSECPT') or 0))
    rows = []
    for r in by.values():
        ys = sorted(r.pop('_years'))
        r.pop('_roads')
        r.update({'fiscal_years': ys, 'first_fiscal_year': ys[0] if ys else None, 'last_fiscal_year': ys[-1] if ys else None,
                  'length_miles': round(r['length_miles'], 2) or None})
        rows.append(r)
    rows.sort(key=lambda r: (r['project_id'], r['first_fiscal_year'] or 0, r['phase']))
    return rows, phases


def _vocab():
    from collections import Counter
    n = Counter()
    for u, f, w in ((F['contracts_url'], 'CONTRACTPROJECTDESCRIPTION', f"PROJECTCOUNTY = '{F['county_code']}'"), (f"{F['work_program_url']}/20", 'LOCALFULL', '1=1')):
        for ft in query(u, w if 'PROJECTCOUNTY' in w else f"CONTYDOT = '{F['county_code']}'", f):
            n.update(re.findall(r"[A-Z][A-Z']{3,}", (ft['attributes'][f] or '').upper()))
    n.update(x.upper() for v in WORK.values() for x in v.split())
    n.update(['BRIDGE', 'REPLACEMENT', 'RESURFACING', 'LANDSCAPING', 'SAFETY', 'SIDEWALK', 'SIGNAL', 'UPDATE', 'BEACH', 'INTERSECTION',
              'IMPROVEMENTS', 'IMPROVEMENT', 'REHABILITATION', 'REPAIR', 'PROJECT', 'CREEK', 'AND', 'STREET', 'AVENUE', 'ENTRANCE'])
    VOCAB.update(k for k, c in n.items() if c >= 2)


def main():
    _vocab()
    C = contracts()
    W, phases = work_program()
    wp = {w['project_id']: w for w in W}
    for c in C:  # the work program's text is cleaner than the contract's (which FDOT wraps mid-word)
        w = wp.get(c['project_id'])
        if w:
            c['description'] = w['description'] + (f" - {w['work_type']}" if w.get('work_type') else '')
    print('contracts', len(C), 'work program rows', len(W), 'projects', len({w['project_id'] for w in W}))
    if not C or not W:
        raise SystemExit('Nothing returned; keeping the existing file.')
    dest = os.path.join(D, 'fdot.json')
    fetched = dt.date.today().isoformat()
    try:
        prev = json.load(open(dest))
        if prev.get('contracts') == json.loads(json.dumps(C)) and prev.get('work_program') == json.loads(json.dumps(W)):
            fetched = prev.get('fetched') or fetched
    except (FileNotFoundError, ValueError):
        pass
    json.dump({'place_id': CFG['place_id'], 'fetched': fetched, 'district_site': F['district_site'], 'phases': phases,
               'contracts': C, 'work_program': W}, open(dest, 'w'), indent=1)


if __name__ == '__main__':
    main()
