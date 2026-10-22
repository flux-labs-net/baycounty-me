"""Build exemption data from Florida DOR's 2026 final NAL file for Bay County (county 13).

Source: https://floridarevenue.com/property/dataportal/ -> Tax Roll Data Files / NAL / 2026F / "Bay 13 Final NAL 2026.zip"
Usage: python3 build_exemptions.py /path/to/NAL13F202601.csv   (or --migrate to convert an older parcels_2026.json)
Writes:
  exemptions_2026.json  countywide summary by exemption type, veterans by tax district, estimated taxes each type removes
  parcels_2026.json     per parcel with a personal (homestead-type) exemption, PRIVACY-SAFE shape (see public_row):
                        [school taxable, non-school taxable, homestead $, additional homestead $, other exemptions $]
                        No exemption types other than homestead are written: widow/widower, disability, blindness, veteran,
                        deployment, first-responder, senior and similar personal-status exemptions are summed into one
                        'other exemptions' dollar amount so no one's personal circumstances can be read off a parcel.
                        Only one non-school taxable value is written (the certified one), because a separate city value
                        would reveal a county-only senior exemption by subtraction.
                        Countywide counts by type stay in exemptions_2026.json.
Estimated taxes use the latest complete set of adopted rates on the site (tax year 2025, FY2026 bills), the same rates My Address uses.
"""
import csv, json, os, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'site'))
from tax_page import build_data, YEARS  # noqa: E402
from addr_page import TAXDIST  # noqa: E402

CODES = {  # DOR NAL exemption fields (Florida Statutes)
    '01': ('Homestead', '196.031(1)(a)', 'all'), '02': ('Additional homestead', '196.031(1)(b)', 'nonschool'),
    '03': ('Senior (65+, limited income), county', '196.075', 'county'), '04': ('Senior (65+, limited income), city', '196.075', 'city'),
    '05': ('Totally and permanently disabled veteran or surviving spouse', '196.081', 'all'), '06': ('Disabled veteran in a wheelchair', '196.091', 'all'),
    '08': ('Totally and permanently disabled person (quadriplegic, or limited income)', '196.101', 'all'),
    '31': ('Blind person', '196.202', 'all'), '32': ('Widower', '196.202', 'all'), '33': ('Widow', '196.202', 'all'),
    '34': ('Disabled person ($5,000)', '196.202', 'all'), '35': ('Disabled veteran, 10%+ service-connected ($5,000)', '196.24', 'all'),
    '38': ('Deployed service member', '196.173', 'all'), '39': ('Long-term senior (65+, 25 years in home, limited income), county', '196.075', 'county'),
    '40': ('Long-term senior, city', '196.075', 'city'), '41': ('Disabled first responder or surviving spouse', '196.102', 'all'),
    '80': ('Combat-disabled veteran 65+ discount', '196.082', 'all'), '81': ('Granny flat (parent or grandparent living quarters)', '193.703', 'all'),
    '09': ('Religious, charitable and other nonprofit', '196.196', 'all'), '12': ('Hospitals and nursing homes', '196.197', 'all'),
    '13': ('Nonprofit homes for the aged', '196.1975', 'all'), '15': ('Affordable housing (nonprofit)', '196.1978', 'all'),
    '16': ('Educational', '196.198', 'all'), '17': ('Charter schools', '196.1983', 'all'), '20': ('Government property', '196.199', 'all'),
    '22': ('Economic development (county)', '196.1995', 'county'), '36': ('Conservation land', '196.26', 'all'),
    '43': ('Affordable housing (Florida Housing certified)', '196.1978(3)', 'all'),
}
PERSONAL = {'01', '02', '03', '04', '05', '06', '08', '31', '32', '33', '34', '35', '38', '39', '40', '41', '80', '81'}
VETERAN = {'05', '06', '35', '38', '80'}


HOMESTEAD = ('01', '02')  # value-based homestead exemptions shown by name; everything else is lumped


def public_row(tv_sd, tv_nsd, ex):
    """Per-parcel row safe to publish: taxable values, homestead amounts, and one lumped 'other exemptions' amount (no types)."""
    other = sum(a for c, a in ex.items() if c not in HOMESTEAD)
    return [round(tv_sd), round(tv_nsd), round(ex.get('01', 0)), round(ex.get('02', 0)), round(other)]


def migrate(fp):
    """Convert an older parcels_2026.json ([tsd, tnsd, senior, {code: amount}]) to the public shape, in place."""
    P = json.load(open(fp))
    out = {k: (public_row(v[0], v[1], v[3]) if len(v) == 4 and isinstance(v[3], dict) else v) for k, v in P.items()}
    json.dump(out, open(fp, 'w'), separators=(',', ':'))
    return len(out)


def main(path):
    td = build_data(); L = len(YEARS) - 1
    auth = td['auth']
    dist = {d['id']: d['stack'] for d in td['districts']}

    def mills(did, grp):
        st = dist.get(did) or dist['unincorporated']
        out = 0.0
        for a in st:
            A = auth[a]
            if grp == 'school' and A['school']:
                out += A['m'][L]
            elif grp == 'county' and not A['school'] and A['g'] in ('county', 'countysvc'):
                out += A['m'][L]
            elif grp == 'other' and not A['school'] and A['g'] not in ('county', 'countysvc'):
                out += A['m'][L]
        return out / 1000

    by = defaultdict(lambda: {'n': 0, 'value': 0.0, 'tax': 0.0, 'homes': 0})
    vet = defaultdict(lambda: defaultdict(int)); hs = defaultdict(int); full_vet_val = defaultdict(float)
    totals = {'parcels': 0, 'homesteads': 0, 'homestead_jv': 0.0, 'zero_school': 0, 'zero_all': 0, 'tax_removed': 0.0}
    parcels = {}
    for r in csv.DictReader(open(path, newline='', encoding='latin-1')):
        totals['parcels'] += 1
        ex = {}
        for k, v in r.items():
            if k and k.startswith('EXMPT_') and v and v.strip() not in ('', '0'):
                a = float(v)
                if a > 0:
                    ex[k[6:]] = a
        if not ex:
            continue
        did = TAXDIST.get(r['TAX_AUTH_CD'].strip(), 'unincorporated')
        av_sd, av_nsd, tv_sd, tv_nsd = (float(r[x] or 0) for x in ('AV_SD', 'AV_NSD', 'TV_SD', 'TV_NSD'))
        sr = sum(ex.get(c, 0) for c in ('03', '39'))
        tv_other = min(av_nsd, tv_nsd + sr)
        removed = {'school': max(0, av_sd - tv_sd) * mills(did, 'school'), 'county': max(0, av_nsd - tv_nsd) * mills(did, 'county'),
                   'other': max(0, av_nsd - tv_other) * mills(did, 'other')}
        totals['tax_removed'] += sum(removed.values())
        # share each levy group's removed tax among the codes that apply to it, by amount
        for grp in ('school', 'county', 'other'):
            app = {c: a for c, a in ex.items() if (CODES.get(c, ('', '', 'all'))[2] == 'all') or (grp != 'school' and CODES.get(c, ('', '', ''))[2] == 'nonschool') or (grp == 'county' and CODES.get(c, ('', '', ''))[2] == 'county') or (grp == 'other' and CODES.get(c, ('', '', ''))[2] == 'city')}
            s = sum(app.values())
            for c, a in app.items():
                by[c]['tax'] += removed[grp] * a / s if s else 0
        home = '01' in ex
        for c, a in ex.items():
            by[c]['n'] += 1; by[c]['value'] += a; by[c]['homes'] += home
        if home:
            totals['homesteads'] += 1; totals['homestead_jv'] += float(r['JV'] or 0); hs[did] += 1
            totals['zero_school'] += tv_sd == 0; totals['zero_all'] += tv_sd == 0 and tv_nsd == 0
            for c in VETERAN:
                if c in ex:
                    vet[did][c] += 1
            if '05' in ex:
                full_vet_val[did] += av_nsd
        if ex.keys() & PERSONAL:
            p = r['PARCEL_ID'].strip()
            pid = f'{p[:5]}-{p[5:8]}-{p[8:11]}' if len(p) == 11 else p
            parcels[pid] = public_row(tv_sd, tv_nsd, ex)
    out = {
        'as_of': '2026-10-21', 'roll': '2026 final tax roll (Florida DOR NAL, Bay County, posted 2026-10-16)', 'rates': td['fy'][L],
        'source': 'https://floridarevenue.com/property/dataportal/',
        'totals': {k: round(v) if isinstance(v, float) else v for k, v in totals.items()},
        'codes': {c: {'name': CODES.get(c, (c, '', ''))[0], 'statute': CODES.get(c, ('', '', ''))[1], 'applies': CODES.get(c, ('', '', 'all'))[2],
                      'parcels': v['n'], 'homes': v['homes'], 'value': round(v['value']), 'tax': round(v['tax'])} for c, v in sorted(by.items())},
        'veterans_by_district': {d: {'homesteads': hs[d], **{c: n for c, n in vet[d].items()}, 'full_exempt_value': round(full_vet_val[d])} for d in sorted(hs)},
    }
    json.dump(out, open(os.path.join(HERE, 'exemptions_2026.json'), 'w'), indent=1)
    json.dump(parcels, open(os.path.join(HERE, 'parcels_2026.json'), 'w'), separators=(',', ':'))
    print(out['totals']); print(len(parcels), 'parcels')
    for c, v in out['codes'].items():
        print(c, v)
    for d, v in out['veterans_by_district'].items():
        print(d, v)


if __name__ == '__main__':
    if sys.argv[1:] == ['--migrate']:
        print(migrate(os.path.join(HERE, 'parcels_2026.json')), 'parcels migrated')
    else:
        main(sys.argv[1])
