"""Pull Bay County rows from the Revenue Estimating Conference's HJR 1F impact (July 10, 2026)."""
import json, re, subprocess, os
here = os.path.dirname(os.path.abspath(__file__))
txt = subprocess.run(['pdftotext', '-layout', os.path.join(here, 'rec_impact_2026-07-10.pdf'), '-'], capture_output=True, text=True).stdout
num = lambda s: 0 if s.strip() == '-' else -int(s.strip('()').replace(',', ''))
rows = []
for line in txt.splitlines():
    m = re.match(r'^Bay\s{2,}(Board of County Commissioners|Independent Special District|Municipality)\s{2,}(.+?)\s{2,}(-)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*$', line)
    if m:
        rows.append({'type': m.group(1), 'name': m.group(2).strip(),
                     'impact': dict(zip(['FY2027','FY2028','FY2029','FY2030','FY2031','FY2032'], [num(x) for x in m.groups()[2:]]))})
cty = {}
for line in txt.splitlines():
    m = re.match(r'^Bay\s{2,}0\.0\s+0\.0\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*$', line)
    if m: cty.setdefault('rows', []).append([m.group(1), m.group(2)])
out = {'source': 'Florida Revenue Estimating Conference, CS/HJR 1F impact, adopted July 10, 2026',
       'source_url': 'https://edr.state.fl.us/Content/conferences/revenueimpact/archives/2026F/_pdf/impact0710.pdf',
       'note': 'Dollars are revenue change (negative = loss) by state fiscal year label, e.g. FY2028 = 2027-28 = 2027 tax roll. Board of County Commissioners includes county-dependent districts (fire MSTU, mosquito control). School impact is zero.',
       'statewide': {'FY2028': -4929543878, 'FY2029': -8714492521, 'FY2030': -9647862749, 'FY2031': -10710157749, 'FY2032': -11834731658},
       'bay': rows}
assert len(rows) == 9, rows
json.dump(out, open(os.path.join(here, 'rec_bay.json'), 'w'), indent=1)
for r in rows: print(r['name'], r['impact'])
print('FY2029 total', sum(r['impact']['FY2029'] for r in rows))
