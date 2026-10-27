#!/usr/bin/env python3
"""Open volunteer needs in the county from public volunteer boards -> data/volunteer/<county>/needs.json.

    python3 data/volunteer/fetch_needs.py [--county bay]

Sources (both public pages, no sign-in):
- United Way of Northwest Florida's volunteer center (volunteer.unitedwaynwfl.org, a Galaxy Digital "Get Connected"
  site): the open needs list, then each need's page for its description, city, ZIP, dates and the agency that posted it.
- Idealist's volunteer listings for the county's towns (idealist.org/en/volunteer-in-<town>-fl): each listing's
  schema.org JobPosting data (title, organization, description, city, posted and closing dates).

Only needs in a county town or ZIP are kept. Only what the boards publish about the opening: title, organization, what
volunteers do, when, the city and ZIP, and the link to sign up. No street addresses, contact names, emails or phone
numbers. A board that fails keeps the needs it had on file (until they close) and notes the error.
"""
import argparse, datetime as dt, json, os, re, sys, time, urllib.request
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'sunbiz'))
from counties import county as county_info  # noqa: E402

UA = 'Mozilla/5.0 (compatible; BayCounty.me volunteer board reader; +https://baycounty.me/about)'
UW = 'https://volunteer.unitedwaynwfl.org'
IDEALIST = 'https://www.idealist.org'
TOWNS = {'bay': ['panama-city-fl', 'panama-city-beach-fl', 'lynn-haven-fl', 'callaway-fl']}


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,*/*'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []

    def handle_data(self, d):
        self.out.append(d)

    def handle_starttag(self, tag, attrs):
        if tag in ('br', 'p', 'li', 'div'):
            self.out.append(' ')


def clean(s):
    """Plain text from an HTML fragment (a real parser: some descriptions carry pasted markup with '>' inside
    attribute values, which a tag regex would leak)."""
    t = _Text()
    t.feed(s or '')
    t.close()
    return re.sub(r'\s+', ' ', ''.join(t.out)).strip() or None


def short(s, n=600):
    s = clean(s) or ''
    # no contact details: emails and phone numbers are left out (the sign-up link carries them)
    s = re.sub(r'[\w.+-]+@[\w-]+\.[\w.]+', '', s)
    s = re.sub(r'\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]\d{4}\b', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'(?i)[\s,]*(for more information[^.]*?)?(give us a call|call us|contact us)?[\s:@]*$', '', s).strip()
    if len(s) <= n:
        return s or None
    cut = s[:n].rsplit(' ', 1)[0]
    return cut.rstrip(',;:') + '…'


def in_county(city, zip_, c):
    z = (zip_ or '')[:5]
    if z and z in c['zips'] and z not in c['shared_zips']:
        return True
    return (city or '').upper().strip() in c['cities']


# --- United Way of Northwest Florida (Galaxy Digital) ----------------------------------------------------------------

def _uw_when(text, page):
    """'Is Ongoing', 'Happens On Dec 3, 2026', 'Multiple Shifts Available', 'Happens From Nov 1, 2026 To ...'"""
    t = clean(text) or ''
    dates = re.findall(r'([A-Z][a-z]{2} \d{1,2}, \d{4})', t)
    iso = [dt.datetime.strptime(d, '%b %d, %Y').date().isoformat() for d in dates]
    if 'ongoing' in t.lower():
        kind = 'Ongoing'
    elif 'shift' in t.lower():
        kind = 'Shifts'
        sh = sorted(set(re.findall(r'data-shift-date="(\d{4}-\d{2}-\d{2})', page)))
        iso = sh[:1] + sh[-1:] if sh else iso
    else:
        kind = 'One day' if len(iso) == 1 else 'Date range' if iso else 'Ongoing'
    return kind, t, (iso[0] if iso else None), (iso[-1] if iso else None)


def united_way(c):
    page = get(f'{UW}/need/')
    cards = re.findall(r'need_id=(\d+)" class="card-body.*?title="([^"]*)".*?<div class="date">(.*?)</div>.*?'
                       r'<div class="title"\s*>(.*?)</div>.*?<div class="excerpt">(.*?)</div>', page, re.S)
    out = []
    for nid, interest, when, title, agency in cards:
        url = f'{UW}/need/detail/?need_id={nid}'
        d = get(url)
        time.sleep(1.5)
        loc = re.search(r'<tr class="address">.*?<td class="text">(.*?)</td>', d, re.S)
        city = zip_ = None
        if loc:
            last = (clean(re.split(r'<br\s*/?>', loc.group(1))[-1].replace('&nbsp;', ' ')) or '')
            m = re.search(r'([A-Za-z .]+?),\s*FL\s*(\d{5})?', last)
            if m:
                city, zip_ = m.group(1).strip().title(), m.group(2)
        other = re.search(r'\b(Calhoun|Gulf|Holmes|Jackson|Washington|Walton|Okaloosa) County', title + ' ' + agency)
        if (loc and not in_county(city, zip_, c)) or (not loc and other):
            continue
        desc = re.search(r'<h2 class="section-header">Description</h2>(.*?)(?:<section class="(?:requirements|location|shifts)|<h2 class="section-header")', d, re.S)
        ag = re.search(r'agency_id=(\d+)"\s*class="card-body">.*?<div class="title">(.*?)</div>', d, re.S)
        kind, label, start, end = _uw_when(when, d)
        reqs = [clean(x) for x in re.findall(r'<tr class="requirement"[^>]*>.*?<td class="text">(.*?)</td>', d, re.S)]
        out.append({
            'need_id': f'uw:{nid}', 'board': 'United Way of Northwest Florida', 'title': clean(title),
            'organization': clean(ag.group(2) if ag else agency), 'organization_board_id': f'uw:{ag.group(1)}' if ag else None,
            'cause': clean(interest), 'schedule': kind, 'when': label, 'starts': start, 'ends': end,
            'description': short(desc.group(1) if desc else None), 'details': '; '.join(r for r in reqs if r) or None,
            'city': city, 'zip': zip_, 'remote': False, 'posted': None, 'closes': None,
            'url': url, 'source_url': f'{UW}/need/'})
    return out


# --- Idealist ----------------------------------------------------------------------------------------------------------

def idealist(c, towns):
    ids = {}
    for t in towns:
        try:
            page = get(f'{IDEALIST}/en/volunteer-in-{t}')
        except Exception as e:  # noqa: BLE001  a town page with no listings can 404
            print(f'idealist {t}: {e}', file=sys.stderr)
            continue
        for m in re.finditer(r'/en/volunteer-opportunity/([0-9a-f]{32})-[a-z0-9-]+', page):
            ids.setdefault(m.group(1), m.group(0))
        time.sleep(1.5)
    out = []
    for oid, path in ids.items():
        url = IDEALIST + path
        try:
            d = get(url)
        except Exception as e:  # noqa: BLE001
            print(f'idealist {oid}: {e}', file=sys.stderr)
            continue
        time.sleep(1.5)
        job = None
        for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', d, re.S):
            try:
                j = json.loads(m.group(1))
            except ValueError:
                continue
            if j.get('@type') == 'JobPosting':
                job = j
        if not job:
            continue
        locs = job.get('jobLocation') or []
        locs = locs if isinstance(locs, list) else [locs]
        addr = [(l.get('address') or {}) for l in locs]
        city = next((a.get('addressLocality') for a in addr if in_county(a.get('addressLocality'), a.get('postalCode'), c)), None)
        if not city:
            continue
        zip_ = next((a.get('postalCode') for a in addr if a.get('addressLocality') == city), None)
        posted, closes = (job.get('datePosted') or '')[:10] or None, (job.get('validThrough') or '')[:10] or None
        org = job.get('hiringOrganization') or {}
        out.append({
            'need_id': f'idealist:{oid}', 'board': 'Idealist', 'title': clean(job.get('title')),
            'organization': clean(org.get('name')), 'organization_board_id': None,
            'cause': None, 'schedule': 'Ongoing', 'when': None, 'starts': None, 'ends': None,
            'description': short(job.get('description')), 'details': None,
            'city': city, 'zip': zip_, 'remote': job.get('jobLocationType') == 'TELECOMMUTE', 'posted': posted, 'closes': closes,
            'url': url, 'source_url': f'{IDEALIST}/en/volunteer-in-{towns[0]}'})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--county', default='bay')
    a = ap.parse_args()
    c = county_info(a.county)
    os.makedirs(os.path.join(HERE, a.county), exist_ok=True)
    path = os.path.join(HERE, a.county, 'needs.json')
    old = json.load(open(path)) if os.path.exists(path) else {'needs': []}
    today = dt.date.today().isoformat()
    needs, errors, fetched = [], [], {}
    for board, fn in [('United Way of Northwest Florida', lambda: united_way(c)), ('Idealist', lambda: idealist(c, TOWNS[a.county]))]:
        try:
            rows = fn()
            if not rows and any(r['board'] == board for r in old['needs']):
                raise RuntimeError('no needs found (page layout may have changed)')
            needs += rows
            fetched[board] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
            print(f'{board}: {len(rows)} needs')
        except Exception as e:  # noqa: BLE001  keep what we had for this board
            kept = [r for r in old['needs'] if r['board'] == board and (r.get('closes') or r.get('ends') or '9999') >= today]
            needs += kept
            fetched[board] = (old.get('fetched') or {}).get(board)
            errors.append({'board': board, 'error': f'{type(e).__name__}: {e}'[:300], 'kept': len(kept)})
            print(f'{board}: failed ({e}); kept {len(kept)} needs on file', file=sys.stderr)
    # the same opening posted on both boards: keep the first (United Way has dates and a cause)
    seen, uniq = set(), []
    for r in needs:
        k = (re.sub(r'\W+', '', (r['organization'] or '').lower())[:20], re.sub(r'\W+', '', (r['title'] or '').lower()))
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    uniq.sort(key=lambda r: (r['board'], r['organization'] or '', r['title'] or ''))
    first_seen = {r['need_id']: r.get('first_seen') for r in old['needs']}
    for r in uniq:
        r['first_seen'] = first_seen.get(r['need_id']) or today
    json.dump({'as_of': today, 'fetched': fetched, 'errors': errors, 'needs': uniq}, open(path, 'w'), indent=1, ensure_ascii=False)
    print(f'{len(uniq)} needs -> {path}')


if __name__ == '__main__':
    main()
