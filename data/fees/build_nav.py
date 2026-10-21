"""Join Florida DOR's 2025 non-ad valorem files for Bay County (NAVN = parcel header, NAVD = levy detail)
into nav_2025.json: {parcel_id: [[levy_code, amount], ...]}.
Source: https://floridarevenue.com/property/dataportal/ (Tax Roll Data Files / NAV / 2025)."""
import csv, json, os, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
raw = sys.argv[1] if len(sys.argv) > 1 else HERE
pid = {}
for r in csv.reader(open(os.path.join(raw, 'NAVN132506.TXT'), newline='')):
    if r and r[0] == 'N': pid[r[2]] = r[3].strip()
out = defaultdict(list)
for r in csv.reader(open(os.path.join(raw, 'NAVD132506.TXT'), newline='')):
    if r and r[0] == 'D' and r[2] in pid:
        out[pid[r[2]]].append([r[3], round(float(r[6]), 2)])
json.dump(out, open(os.path.join(HERE, 'nav_2025.json'), 'w'), separators=(',', ':'))
print(len(pid), len(out), sum(a for v in out.values() for _, a in v))
