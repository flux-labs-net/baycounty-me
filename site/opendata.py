"""Open data: every dataset on the site as CSV and JSON (/open-data)."""
import csv, html, io, json, os, re
from govs import all_profiles, gov_of_body, is_split

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
e = lambda s: html.escape(str(s if s is not None else ''))
import sys as _sys
_sys.path.insert(0, os.path.join(DATA, 'entities'))
import ids  # noqa: E402  shared government / vendor / person ids (data/entities)

# which columns name the government, per dataset, tried in order (office titles are matched by contained name)
GOV_COLS = {'government-profiles': ['government'], 'votes': ['government'], 'member-votes': ['gov_id'], 'cra-payments': ['city'],
            'property-tax-rates': ['authority_id'], 'fema-michael-projects': ['applicant'], 'officials-pay': ['title', 'government'],
            'meetings': ['gov', 'board'], 'campaign-finance': ['office', 'gov'], 'bonds': ['gov'], 'salary-positions': ['employer_id'],
            'salary-leaders': ['employer_id'], 'candidates-2026': ['office', 'government'], 'campaign-contributions-2026': ['office'],
            'bed-tax-collections': [], 'property-tax-exemptions': []}
FIXED_GOV = {'bed-tax-collections': 'county', 'property-tax-exemptions': 'county'}  # county bed tax in every zone; the county-wide tax roll


VENDOR_COL = {'contracts': 'vendor', 'change-orders': 'vendor', 'emergency-purchases': 'vendor', 'cra-payments': 'payee', 'vendor-payments': 'vendor',
              'campaign-contributions-2026': 'contributor'}


def add_vendor_id(did, rows):
    """vendor_id from data/entities/vendors.json; vendor_ids lists every firm when one record names several (a joint award)."""
    col = VENDOR_COL.get(did)
    if not col:
        return rows
    for r in rows:
        v = [] if did == 'campaign-contributions-2026' and r.get('contributor_type') != 'business' else ids.vendor_ids(r.get(col))
        r['vendor_id'] = v[0] if v else None
        r['vendor_ids'] = v if len(v) > 1 else None
    return rows


PERSON_COL = {'member-votes': 'member', 'officials-pay': 'name', 'salary-leaders': 'name', 'campaign-finance': 'official', 'candidates-2026': 'candidate'}


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


def add_gov_id(did, rows):
    cols = GOV_COLS.get(did, ['government', 'gov'])
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
    return rows


def _j(*p):
    try:
        return json.load(open(os.path.join(DATA, *p)))
    except FileNotFoundError:
        return None


def _votes():
    d = _j('votes', 'votes.json'); names = {b['id']: re.sub(r'\bCity City\b', 'City', b['name']) for b in d['bodies']}
    return [{'date': v.get('date'), 'government': gov_of_body(v['body']), 'board': names.get(v['body']), 'category': v.get('category'), 'headline': v.get('headline'),
             'summary': v.get('summary'), 'amount': v.get('amount'), 'outcome': v.get('outcome'), 'tally': v.get('tally'), 'split': is_split(v),
             'voted_yes': '; '.join(n for n, x in (v.get('by_member') or {}).items() if x == 'yes'), 'voted_no': '; '.join(n for n, x in (v.get('by_member') or {}).items() if x == 'no'),
             'absent_or_abstained': '; '.join(n for n, x in (v.get('by_member') or {}).items() if x in ('absent', 'abstain')), 'agenda_item': v.get('item'),
             'source_title': v.get('source_title'), 'source_url': v.get('source_url'),
             'members': [{'name': n, 'person_id': ids.person_id(n), 'vote': x} for n, x in (v.get('by_member') or {}).items()] or None} for v in d['votes']]


def _member_votes():
    d = _j('votes', 'votes.json'); names = {b['id']: re.sub(r'\bCity City\b', 'City', b['name']) for b in d['bodies']}
    return [{'date': v.get('date'), 'board': names.get(v['body']), 'member': n, 'vote': x, 'headline': v.get('headline'), 'source_url': v.get('source_url'), 'gov_id': gov_of_body(v['body'])}
            for v in d['votes'] for n, x in (v.get('by_member') or {}).items()]


def _cra():
    return [{k: p.get(k) for k in ('cra', 'city', 'payee', 'amount', 'date_or_fy', 'status', 'category', 'purpose', 'location_name', 'district', 'lat', 'lng', 'count', 'source_title', 'source_url', 'notes')}
            for p in _j('merged.json')['payments']]


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
    # organizations only; individual donors are never published on this site
    return [{'candidate': c['name'], 'office': c.get('office'), 'contributor': x.get('name'), 'contributor_type': x.get('type'), 'city': x.get('city'),
             'amount': x.get('amount'), 'date': x.get('date'), 'kind': x.get('kind'), 'report_url': c.get('report_url')}
            for c in f.get('candidates') or [] for x in c.get('contributors') or [] if x.get('type') not in ('candidate', 'individual', 'self')]


def _exemptions():
    d = _j('exemptions', 'exemptions_2026.json')
    if not d:
        return []
    return [{'code': k, 'exemption': v['name'], 'statute': v['statute'], 'applies_to': v['applies'], 'parcels': v['parcels'], 'homesteads': v['homes'],
             'value_exempted': v['value'], 'estimated_tax_removed': v['tax'], 'roll': d.get('roll'), 'source_url': d.get('source')} for k, v in d['codes'].items()]


def datasets():
    ct = _j('contracts', 'contracts.json'); da = _j('debt_audit', 'debt_audit.json'); f = _j('fees', 'fees_pay_officials.json')
    ts = _j('tourism', 'tourism_surtax.json'); pa = _j('michael', 'pa_ledger.json')
    D = [
        ('government-profiles', 'Government profiles', 'One row per government: population, budget, tax rate, debt, audit findings, votes, staff, utility bill and Hurricane Michael money.', _profiles),
        ('votes', 'Recorded votes', 'Money votes by the County Commission, School Board, city commissions and CRA boards, with how each member voted.', _votes),
        ('member-votes', 'Votes by member', 'One row per member per vote (long format), for tallying individual records.', _member_votes),
        ('contracts', 'Contracts', 'Major contracts approved since October 2022: vendor, amount, purpose, how awarded.', lambda: _flat(ct['contracts'], ['government', 'vendor', 'amount', 'purpose', 'date', 'method', 'source_title', 'source_url', 'notes'])),
        ('change-orders', 'Change orders', 'Contract change orders with original and new totals.', lambda: _flat(ct['change_orders'], ['government', 'vendor', 'project', 'original_amount', 'change_amount', 'new_total', 'pct_of_original', 'reason', 'date', 'source_url'])),
        ('emergency-purchases', 'Emergency purchases', 'Purchases made under emergency rules without normal bidding.', lambda: _flat(ct.get('emergency_purchases') or [], ['government', 'vendor', 'amount', 'purpose', 'date', 'basis', 'source_url'])),
        ('cra-payments', 'CRA spending', 'What Bay County\'s Community Redevelopment Agencies paid for, with locations.', _cra),
        ('property-tax-rates', 'Property tax rates', 'Millage, rolled-back rate and levy for every taxing authority, by tax year.', _rates),
        ('debt', 'Debt by government', 'Total debt from the latest audited financial statements.', lambda: _flat(da['debt'], ['government', 'fy', 'total_debt', 'total_debt_note', 'population_2025_estimate', 'source_url'])),
        ('audit-findings', 'Audit findings', 'Findings from audits filed with the Florida Auditor General, in plain English.', lambda: [{'government': a['government'], 'fy': a.get('fy'), 'opinion': a.get('opinion'), 'finding': x.get('title'), 'plain_english': x.get('plain'), 'repeat': x.get('repeat'), 'management_response': x.get('mgmt_response'), 'source_url': x.get('source_url') or a.get('source_url')} for a in da['audits'] for x in a.get('findings') or []]),
        ('fema-michael-projects', 'Hurricane Michael FEMA projects', 'Every FEMA Public Assistance project in Bay County for disaster DR-4399.', lambda: [{'applicant': r['a'], 'project': r['pw'], 'title': r['t'], 'category': r['c'], 'federal_share': r['f'], 'eligible_amount': r['e'], 'first_obligated': r.get('d1'), 'last_obligated': r.get('d2'), 'status': r.get('st'), 'size': r.get('sz')} for r in pa['rows']]),
        ('sales-tax-projects', 'Half-cent sales tax projects', 'Every infrastructure sales tax project on the county map, with status and cost.', lambda: _flat(ts['infra_surtax']['projects'], ['name', 'government', 'category', 'status', 'pct_complete', 'promised_cost', 'programmed_cost', 'actual_cost', 'fiscal_years', 'location', 'lat', 'lng', 'description', 'source_url'])),
        ('bed-tax-collections', 'Tourist tax collections', 'Bed tax collected by zone and fiscal year.', lambda: _flat(ts['bed_tax']['collections'], ['fy', 'district', 'amount', 'partial', 'period', 'basis', 'source_url'])),
        ('fees-assessments', 'Fees on tax bills', 'Non-ad valorem assessments: fire, stormwater, CRA and other flat fees.', lambda: _flat(f['assessments'], ['government', 'area', 'name', 'category', 'how_charged', 'rate', 'residential_single_family_amount', 'fiscal_year', 'source_url'])),
        ('officials-pay', 'Officials and pay', 'Salaries of top elected and appointed officials.', lambda: _flat(f['pay'], ['government', 'title', 'name', 'annual', 'year', 'basis', 'source_url'])),
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
        (('salaries', 'bocc.json'), 'salary-positions', 'Public salaries by job title', 'Pay ranges, budgeted positions and unnamed actual salaries by job title for the county, constitutional officers, school district, cities, airport and port.', lambda d: _salaries('positions')),
        (('salaries', 'bocc.json'), 'salary-leaders', 'Salaries of officials and leaders', 'Named salaries of elected officials and top appointed leaders only.', lambda d: _salaries('leaders')),
        (('elections', 'candidates_2026.json'), 'candidates-2026', '2026 local candidates', 'Every 2026 local race and candidate with status, platform in their own words and campaign money totals.', lambda d: _candidates()),
        (('elections', 'finance_2026.json'), 'campaign-contributions-2026', '2026 contributions from organizations', 'Every contribution from a business, committee or party to a 2026 local candidate. Individual donors are not included.', lambda d: _contributions()),
        (('exemptions', 'exemptions_2026.json'), 'property-tax-exemptions', 'Property tax exemptions (2026 roll)', 'Every exemption type on the 2026 tax roll: parcels, value exempted and estimated tax removed.', lambda d: _exemptions()),
    ]
    for path, did, title, desc, fn in extra:
        d = _j(*path)
        if d:
            D.append((did, title, desc, (lambda d, fn: (lambda: fn(d)))(d, fn)))
    return D


def write_downloads(out_dir):
    dest = os.path.join(out_dir, 'downloads'); os.makedirs(dest, exist_ok=True)
    meta, catalog = [], []
    for did, title, desc, fn in datasets():
        rows = add_gov_id(did, fn() or [])
        keys = list(dict.fromkeys(k for r in rows for k in r))
        buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=keys, extrasaction='ignore'); w.writeheader()
        for r in rows:
            w.writerow({k: ('; '.join(map(str, v)) if isinstance(v, list) else json.dumps(v) if isinstance(v, dict) else v) for k, v in r.items()})
        open(os.path.join(dest, did + '.csv'), 'w', newline='').write(buf.getvalue())
        json.dump(rows, open(os.path.join(dest, did + '.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
        meta.append((did, title, desc, len(rows), keys, os.path.getsize(os.path.join(dest, did + '.csv'))))
        def typ(k):
            vals = [r.get(k) for r in rows if r.get(k) is not None][:200]
            if not vals: return 'string'
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
