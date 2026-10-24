"""Pull a county's tax-exempt organizations and their filed officers and directors from IRS data.

Source: the IRS public files as mirrored by the GivingTuesday 990 data lake (s3://gt990datalake-rawdata, public):
  - EO Business Master File (BMF): every recognized exempt organization, its address, subsection, NTEE code, assets
  - 990-N e-Postcards: small organizations (receipts under $50,000) and their principal officer
  - 990 / 990-EZ / 990-PF e-file XML (index + one XML per return): Part VII officers, directors, trustees and key
    employees with title, hours and pay; Schedule I grants to other organizations; revenue, expenses and assets

An organization is in the county when its BMF address ZIP is one of counties.py's ZIPs (shared ZIPs also need a county
city), or when a Sunbiz nonprofit corporation in the county's filter output lists its EIN (FEI).

Usage: python3 data/nonprofits/fetch_irs.py --county bay [--work /tmp/np] [--years 2019-2025]
Writes data/nonprofits/<county>/{orgs,filings,officers,grants,postcards}.csv.gz. Downloads (~600 MB of BMF and
postcards, then a few MB of XML) are cached in --work. The XML index files are streamed, not stored.
"""
import argparse, concurrent.futures as cf, csv, gzip, io, json, os, re, sys, urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'sunbiz'))
from counties import county  # noqa: E402

LAKE = 'https://gt990datalake-rawdata.s3.amazonaws.com'
csv.field_size_limit(10 ** 8)


def _get(url, path=None):
    req = urllib.request.Request(url, headers={'User-Agent': 'baycounty.me data build'})
    if path:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
        with urllib.request.urlopen(req, timeout=600) as r, open(path + '.part', 'wb') as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
        os.replace(path + '.part', path)
        return path
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def _latest(prefix, pattern):
    """Newest key under prefix whose name matches pattern (data lake files carry their build date)."""
    xml = _get(f'{LAKE}/?prefix={prefix}').decode()
    keys = re.findall(r'<Key>([^<]+)</Key>', xml)
    while 'IsTruncated>true' in xml:
        xml = _get(f'{LAKE}/?prefix={prefix}&marker={keys[-1]}').decode()
        keys += re.findall(r'<Key>([^<]+)</Key>', xml)
    keys = [k for k in keys if re.search(pattern, k)]

    def stamp(k):
        return tuple(int(x) for x in re.findall(r'(\d{4})[_-](\d{1,2})[_-](\d{1,2})', k)[-1])
    return max(keys, key=stamp)


def in_county(c, zipcode, city):
    z = (zipcode or '')[:5]
    if z not in c['zips']:
        return False
    if z in c.get('shared_zips', set()):
        return (city or '').upper().strip() in c['cities']
    return True


def sunbiz_eins(county_key):
    """EIN -> Sunbiz doc number for the county's nonprofit corporations."""
    p = os.path.join(HERE, '..', 'sunbiz', county_key, 'entities.csv.gz')
    out = {}
    if not os.path.exists(p):
        return out
    with gzip.open(p, 'rt', encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            if r['filing_type'] in ('DOMNP', 'FORNP', 'NPREG'):
                e = re.sub(r'\D', '', r.get('fei') or '')
                if len(e) == 9 and len(set(e)) > 1:
                    out.setdefault(e, r['doc_number'])
    return out


def _t(el, *names):
    for n in names:
        x = el.find('.//{*}' + n)
        if x is not None and (x.text or '').strip():
            return x.text.strip()
    return ''


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def parse_return(raw):
    """(header, officers, grants) from one e-file XML."""
    root = ET.fromstring(raw)
    hdr = {'principal_officer': _t(root, 'PrincipalOfficerNm'), 'website': _t(root, 'WebsiteAddressTxt'),
           'mission': _t(root, 'ActivityOrMissionDesc', 'MissionDesc', 'PrimaryExemptPurposeTxt')[:500],
           'employees': _t(root, 'TotalEmployeeCnt'), 'voting_members': _t(root, 'VotingMembersGoverningBodyCnt'),
           'city': _t(root.find('.//{*}Filer') if root.find('.//{*}Filer') is not None else root, 'CityNm')}
    officers = []
    for tag, hours_tag, comp_tag in (('Form990PartVIISectionAGrp', 'AverageHoursPerWeekRt', 'ReportableCompFromOrgAmt'),
                                     ('OfficerDirectorTrusteeEmplGrp', 'AverageHrsPerWkDevotedToPosRt', 'CompensationAmt'),
                                     ('OfficerDirTrstKeyEmplGrp', 'AverageHrsPerWkDevotedToPosRt', 'CompensationAmt')):
        for g in root.iter('{http://www.irs.gov/efile}' + tag):
            name = _t(g, 'PersonNm')
            biz = '' if name else ' '.join(filter(None, [_t(g, 'BusinessNameLine1Txt'), _t(g, 'BusinessNameLine2Txt')]))
            if not (name or biz):
                continue
            flags = [k for k, t in (('director', 'IndividualTrusteeOrDirectorInd'), ('institutional_trustee', 'InstitutionalTrusteeInd'),
                                    ('officer', 'OfficerInd'), ('key_employee', 'KeyEmployeeInd'), ('highest_paid', 'HighestCompensatedEmployeeInd'),
                                    ('former', 'FormerOfcrDirectorTrusteeInd')) if g.find('{*}' + t) is not None]
            officers.append({'name': name or biz, 'is_person': bool(name), 'title': _t(g, 'TitleTxt'), 'hours': _num(_t(g, hours_tag, 'AverageHoursPerWeekRt')),
                             'compensation': _num(_t(g, comp_tag, 'CompensationAmt')), 'related_comp': _num(_t(g, 'ReportableCompFromRltdOrgAmt')),
                             'other_comp': _num(_t(g, 'OtherCompensationAmt', 'EmployeeBenefitProgramAmt')), 'roles': '|'.join(flags)})
    grants = []
    for g in root.iter('{http://www.irs.gov/efile}RecipientTable'):
        nm = ' '.join(filter(None, [_t(g, 'BusinessNameLine1Txt'), _t(g, 'BusinessNameLine2Txt')]))
        if not nm:
            continue
        grants.append({'recipient': nm, 'recipient_ein': _t(g, 'RecipientEIN', 'EINOfRecipient'), 'recipient_city': _t(g, 'CityNm'),
                       'recipient_state': _t(g, 'StateAbbreviationCd'), 'cash': _num(_t(g, 'CashGrantAmt')), 'noncash': _num(_t(g, 'NonCashAssistanceAmt')),
                       'purpose': _t(g, 'PurposeOfGrantTxt')[:300]})
    return hdr, officers, grants


def _write(path, cols, rows):
    with gzip.open(path, 'wt', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, cols, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--county', default='bay')
    ap.add_argument('--work', default='/tmp/np-work')
    ap.add_argument('--years', default='2019-2025', help='e-file index years (the year the return was processed)')
    a = ap.parse_args()
    c = county(a.county)
    os.makedirs(a.work, exist_ok=True)
    out = os.path.join(HERE, a.county)
    os.makedirs(out, exist_ok=True)

    # 1. BMF: organizations in the county, plus any EIN a county Sunbiz nonprofit lists
    sb = sunbiz_eins(a.county)
    bmf_key = _latest('EfileData/BMF/', r'IRS_BMF_\d{4}_\d+_\d+_raw\.csv$')
    bmf = _get(f'{LAKE}/{bmf_key}', os.path.join(a.work, os.path.basename(bmf_key)))
    orgs = {}
    with open(bmf, encoding='latin-1', newline='') as f:
        for r in csv.DictReader(f):
            ein = r['EIN'].zfill(9)
            local = r['STATE'] == 'FL' and in_county(c, r['ZIP'], r['CITY'])
            if local or ein in sb:
                orgs[ein] = dict(r, EIN=ein, in_county=local, sunbiz_doc=sb.get(ein, ''), bmf_file=bmf_key)
    print(f'BMF {bmf_key}: {len(orgs)} organizations ({sum(o["in_county"] for o in orgs.values())} with a county address)')

    # 2. 990-N postcards: latest postcard per EIN in the set
    pc_key = _latest('EfileData/Postcards/', r'990N_Postcards_\d{4}_\d+_\d+_raw\.txt$')
    pc = _get(f'{LAKE}/{pc_key}', os.path.join(a.work, os.path.basename(pc_key)))
    posts = {}
    with open(pc, encoding='latin-1') as f:
        for line in f:
            x = line.rstrip('\n').split('|')
            if len(x) > 22 and x[0] in orgs and (x[0] not in posts or x[1] > posts[x[0]]['tax_year']):
                posts[x[0]] = {'ein': x[0], 'tax_year': x[1], 'name': x[2], 'terminated': x[3], 'tax_period_end': x[6], 'website': x[7],
                               'principal_officer': x[8], 'officer_city': x[11], 'officer_state': x[13], 'officer_zip': x[14][:5],
                               'org_city': x[18], 'org_state': x[20], 'org_zip': x[21][:5]}
    print(f'990-N {pc_key}: {len(posts)} postcards')

    # 3. e-file index, every year: returns filed by those EINs (streamed)
    lo, hi = (int(y) for y in a.years.split('-'))
    returns = {}
    for y in range(lo, hi + 1):
        key = _latest('Indices/990xmls/yearly/', rf'/{y}_efiledata_xmls_created_on_[\d-]+\.csv$')
        req = urllib.request.Request(f'{LAKE}/{key}', headers={'User-Agent': 'baycounty.me data build'})
        with urllib.request.urlopen(req, timeout=1200) as r:
            rd = csv.DictReader(io.TextIOWrapper(r, encoding='utf-8', newline=''))
            for row in rd:
                ein = (row.get('EIN') or '').zfill(9)
                if ein in orgs and row.get('FormType') in ('990', '990EZ', '990PF'):
                    returns[row['ObjectId']] = row
        print(f'index {y}: {len(returns)} returns so far')

    # 4. one XML per return (cached)
    xdir = os.path.join(a.work, 'xml')
    os.makedirs(xdir, exist_ok=True)

    def fetch(oid):
        p = os.path.join(xdir, oid + '.xml')
        try:
            _get(returns[oid]['URL'] or f'{LAKE}/EfileData/XmlFiles/{oid}_public.xml', p)
            return oid, parse_return(open(p, 'rb').read())
        except Exception as e:  # a missing or broken XML loses that return only
            return oid, e
    filings, officers, grants = [], [], []
    with cf.ThreadPoolExecutor(16) as ex:
        for oid, res in ex.map(fetch, sorted(returns)):
            row = returns[oid]
            if isinstance(res, Exception):
                print('  skip', oid, res)
                continue
            hdr, offs, grs = res
            base = {'ein': row['EIN'].zfill(9), 'object_id': oid, 'form': row['FormType'], 'tax_year': row.get('TaxYear'),
                    'tax_period_end': row.get('TaxPeriodEndDate')}
            filings.append({**base, 'name': row.get('OrganizationName'), 'submitted_on': row.get('SubmittedOn'), 'total_revenue': row.get('TotalRevenueCY'),
                            'total_expenses': row.get('TotalExpensesCY'), 'total_assets': row.get('TotalAssetsBkEOY'), 'net_assets': row.get('TotalNetAssetsBkEOY'),
                            'gross_receipts': row.get('GrossReceipts'), 'website': hdr['website'] or row.get('Website'), 'year_formed': row.get('YearFormed'),
                            'principal_officer': hdr['principal_officer'], 'mission': hdr['mission'], 'employees': hdr['employees'],
                            'voting_members': hdr['voting_members'], 'n_officers': len(offs), 'xml_url': row.get('URL')})
            officers += [{**base, **o} for o in offs]
            grants += [{**base, **g} for g in grs]

    _write(os.path.join(out, 'orgs.csv.gz'), ['EIN', 'NAME', 'ICO', 'STREET', 'CITY', 'STATE', 'ZIP', 'GROUP', 'SUBSECTION', 'AFFILIATION', 'CLASSIFICATION',
                                              'RULING', 'DEDUCTIBILITY', 'FOUNDATION', 'ACTIVITY', 'ORGANIZATION', 'STATUS', 'TAX_PERIOD', 'ASSET_AMT',
                                              'INCOME_AMT', 'REVENUE_AMT', 'NTEE_CD', 'FILING_REQ_CD', 'in_county', 'sunbiz_doc', 'bmf_file'],
           sorted(orgs.values(), key=lambda o: o['EIN']))
    _write(os.path.join(out, 'postcards.csv.gz'), ['ein', 'tax_year', 'name', 'terminated', 'tax_period_end', 'website', 'principal_officer', 'officer_city',
                                                   'officer_state', 'officer_zip', 'org_city', 'org_state', 'org_zip'], sorted(posts.values(), key=lambda p: p['ein']))
    fcols = ['ein', 'object_id', 'form', 'tax_year', 'tax_period_end', 'name', 'submitted_on', 'total_revenue', 'total_expenses', 'total_assets', 'net_assets',
             'gross_receipts', 'website', 'year_formed', 'principal_officer', 'mission', 'employees', 'voting_members', 'n_officers', 'xml_url']
    _write(os.path.join(out, 'filings.csv.gz'), fcols, sorted(filings, key=lambda f: (f['ein'], f['tax_period_end'] or '', f['object_id'])))
    _write(os.path.join(out, 'officers.csv.gz'), ['ein', 'object_id', 'form', 'tax_year', 'tax_period_end', 'name', 'is_person', 'title', 'hours', 'compensation',
                                                  'related_comp', 'other_comp', 'roles'], officers)
    _write(os.path.join(out, 'grants.csv.gz'), ['ein', 'object_id', 'form', 'tax_year', 'tax_period_end', 'recipient', 'recipient_ein', 'recipient_city',
                                                'recipient_state', 'cash', 'noncash', 'purpose'], grants)
    json.dump({'bmf': bmf_key, 'postcards': pc_key, 'years': a.years, 'orgs': len(orgs), 'returns': len(filings), 'officers': len(officers),
               'grants': len(grants), 'postcards_n': len(posts)}, open(os.path.join(out, 'fetch_log.json'), 'w'), indent=1)
    print(f'{a.county}: {len(orgs)} orgs, {len(filings)} returns, {len(officers)} officer rows, {len(grants)} grants, {len(posts)} postcards')


if __name__ == '__main__':
    main()
