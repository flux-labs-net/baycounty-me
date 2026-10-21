"""Download the Bay County SOE (VoterFocus) campaign finance lists, candidate pages and itemized exports.
Usage: python3 fetch.py WORKDIR [elections...]   (default elections: 35 36 34 37)
Writes WORKDIR/list_<e>.html, lists.json, cand_<id>.html, exp_<id>.csv. Exits 2 if the service is down."""
import html as H, json, os, re, sys, time, urllib.request

BASE = 'https://www.voterfocus.com'
D = sys.argv[1]; os.makedirs(D, exist_ok=True)
ELS = sys.argv[2:] or ['35', '36', '34', '37']


def get(url, tries=4):
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (BayCounty.me public records)'}), timeout=60)
            b = r.read()
            if b'temporarily unavailable for maintenance' in b[:300]:
                raise RuntimeError('maintenance')
            return b
        except Exception as e:
            err = e
            time.sleep(5 * (i + 1))
    raise err


def parse_list(t, e):
    out = []
    for sec in re.finditer(r'<section class="row well" id="(\w+)">(.*?)</section>', t, re.S):
        sid, body = sec.group(1), sec.group(2)
        for og in re.split(r'<div class="col-xs-12 officename">', body)[1:]:
            office = H.unescape(re.sub(r'<[^>]+>', '', og.split('</div>', 1)[0])).replace('Office:', '').strip()
            for m in re.finditer(r'<a class="rowlink" href="([^"]+)">(.*?)</a>', og, re.S):
                cells = [re.sub(r'\s+', ' ', H.unescape(re.sub(r'<span class="for-screen-reader">.*?</span>|<[^>]+>', ' ', c))).strip()
                         for c in re.findall(r'role="gridcell">(.*?)</div>', m.group(2), re.S)]
                cells = [c for c in cells if c]
                money = [x for c in cells for x in re.findall(r'\$[-\d,.]+', c)]
                rest = [c for c in cells if not re.search(r'\$[-\d,.]+', c)]
                out.append({'e': e, 'sec': sid, 'office': office, 'href': H.unescape(m.group(1)), 'txt': rest[:1] + [' '.join(rest[1:])] + money[:3]})
    return out


L = []
for e in ELS:
    t = get(f'{BASE}/CampaignFinance/candidate_pr.php?c=bay&el={e}').decode('utf-8', 'replace')
    open(f'{D}/list_{e}.html', 'w').write(t)
    L += parse_list(t, e)
json.dump(L, open(f'{D}/lists.json', 'w'), indent=1)
for o in L:
    if o['sec'] != 'candidates':
        continue
    ca = re.search(r'ca=(\d+)', o['href']).group(1)
    open(f'{D}/cand_{ca}.html', 'wb').write(get(BASE + o['href']))
    open(f'{D}/exp_{ca}.csv', 'wb').write(get(f'{BASE}/CampaignFinance/export.php?op=CFINANCE&cand_id={ca}&dhc=0&county=bay'))
    time.sleep(0.5)
print(len(L), 'rows;', sum(o['sec'] == 'candidates' for o in L), 'candidates')
