#!/usr/bin/env python3
"""Government legal notices -> data/notices/<county>/notices.json, from the raw list fetch_notices.js saves.

    node data/notices/fetch_notices.js > "$RUNNER_TEMP/notices_raw.json"
    python3 data/notices/build_notices.py "$RUNNER_TEMP/notices_raw.json"

Keeps notices that a government or public agency published (bids, public hearings, meetings, ordinances, rules) and
leaves out the court and private notices the same site carries: tax deed applications, foreclosures, notices to
creditors and other probate or court cases. Those name private people and their homes (site privacy rule).

Each kept notice gets the government that posted it (matched on its opening words), a kind (bid, hearing, meeting,
other), a short title, the first date it mentions after publication (the meeting, hearing or bid due date), and its
text. The site only shows the last 30 days, so notices already on file are kept: the file becomes the archive.
"""
import datetime as dt, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTY = os.environ.get('PLACE', 'fl-bay').split('-', 1)[-1]
OUT = os.path.join(HERE, COUNTY, 'notices.json')
FIRST_YEAR = 2016

DROP_TYPES = re.compile(r'tax deed|foreclosure|creditors|probate|name change|fictitious|divorce|adoption|summons', re.I)
DROP_TEXT = re.compile(r'NOTICE OF APPLICATION FOR TAX DEED|NOTICE TO CREDITORS|IN THE CIRCUIT COURT|IN THE COUNTY COURT|'
                       r'NOTICE OF (FORECLOSURE|SALE)\b|PERSONAL REPRESENTATIVE|ESTATE OF\b|CASE NO\.?:? ?\d', re.I)

# (government key or None, agency name, pattern on the notice's opening words); the first match wins, so the more
# specific names come first (Panama City Beach before Panama City, the Port Authority before both).
AGENCIES = [
    (None, 'Panama City Port Authority', r'Port Authority|Intermodal Distribution Center'),
    (None, 'Gulf Coast State College', r'Gulf Coast State College'),
    (None, 'Bay County Tax Collector', r'CERTIFICATE TO ROLL|Tax Collector'),
    (None, 'Bay County Clerk of Court', r'Clerk of (the )?Court'),
    ('county', 'Bay County Tourist Development Council', r'Tourist Development Council|Visit Panama City Beach'),
    ('pcb', 'City of Panama City Beach', r'Panama City Beach'),
    ('schools', 'Bay District Schools', r'Bay District Schools|School Board of Bay County|North Bay Haven|Chief Educational Officer'),
    ('lh', 'City of Lynn Haven', r'Lynn Haven'),
    ('cw', 'City of Callaway', r'Callaway'),
    ('mb', 'City of Mexico Beach', r'Mexico Beach'),
    ('sp', 'City of Springfield', r'Springfield'),
    ('parker', 'City of Parker', r'City of Parker|Parker City'),
    ('pc', 'City of Panama City', r'City of Panama City(?! Beach)|Panama City Commission|Panama City Infrastructure|Panama City Community'),
    ('county', 'Bay County', r'Board of County Commissioners|Bay County Planning Commission|Bay County, Florida|BOCC'),
    (None, 'Community development district', r'Community Development District|\bCDD\b'),
]

KINDS = [
    ('bid', r'INVITATION (TO|FOR) BIDS?|REQUEST FOR (PROPOSALS?|QUALIFICATIONS|BIDS)|NOTICE TO PROPOSERS|SEALED (BIDS|PROPOSALS)|'
            r'requesting Bids|ADVERTISEMENT FOR BIDS|\bRFP\b|\bRFQ\b|\bITB\b|seeks proposals|professional services of'),
    ('hearing', r'PUBLIC HEARING|ORDINANCE|ANNEXATION|ZONING|COMPREHENSIVE PLAN|SITE PLAN|NOTICE OF INTENT|ADOPT NEW RULES|REVISE SCHOOL BOARD RULES|LAND CLEARING'),
    ('meeting', r'MEETING|WORKSHOP|AGENDA|TOWN HALL|ATTORNEY-CLIENT SESSION|CANCELL?ED'),
]
KIND_LABEL = {'bid': 'Bid or proposal request', 'hearing': 'Public hearing or ordinance', 'meeting': 'Public meeting', 'other': 'Other notice'}
BOILER = re.compile(r'^(Published online on the Bay County, Florida website\s*\**\s*|PUBLIC NOTICE\s+|LEGAL NOTICE\s+|Ad to Run on [A-Za-z]+ \d+, \d{4}\s+)+', re.I)
MONTHS = 'January|February|March|April|May|June|July|August|September|October|November|December'
DATE = re.compile(rf'\b({MONTHS})\.? (\d{{1,2}})(?:st|nd|rd|th)?,? (\d{{4}})|\b(\d{{1,2}})/(\d{{1,2}})/(\d{{4}})\b', re.I)


def clean(s):
    return re.sub(r'\s+', ' ', (s or '').replace(' ', ' ')).strip()


def earliest(pairs, text):
    """The (value, pattern) pair whose pattern appears first in text, or None."""
    best = None
    for v, pat in pairs:
        m = re.search(pat, text, re.I)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), v)
    return best[1] if best else None


def agency(text):
    text = BOILER.sub('', text)
    hit = earliest([((k, n), p) for k, n, p in AGENCIES], text[:600])
    if hit:
        return hit
    for key, name, pat in AGENCIES:  # some notices name the agency only further down
        if re.search(pat, text, re.I):
            return key, name
    return None, None


def kind(text):
    if re.search(r'Lost Property|CERTIFICATE TO ROLL', text[:300], re.I):
        return 'other'
    return earliest(KINDS, text[:700]) or 'other'


SMALL = {'a', 'an', 'and', 'as', 'at', 'by', 'for', 'in', 'of', 'on', 'or', 'the', 'to', 'with', 'from'}
AGENCY_PREFIX = re.compile(r'^(BOARD OF COUNTY COMMISSIONERS,? BAY COUNTY,? FLORIDA|(CITY OF )?(PANAMA CITY BEACH|PANAMA CITY|LYNN HAVEN|CALLAWAY|MEXICO BEACH|'
                           r'SPRINGFIELD|PARKER)(,? (FL|FLORIDA)\b)?|BAY DISTRICT SCHOOLS|-|–|:)\s*', re.I)


def tcase(s):
    words = s.lower().split()
    keep_upper = {'cra', 'rfp', 'rfq', 'itb', 'cei', 'srf', 'psac', 'shac', 'cdd', 'us', 'fy27', 'fy26', 'bocc', 'tdc', 'kw'}
    out = []
    for i, w in enumerate(words):
        core = w.strip('(),:;')
        if core in keep_upper or re.match(r'^[a-z]*\d', core):
            out.append(w.upper())
        elif i and core in SMALL:
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:])
    return ' '.join(out)


def title(text, k):
    t = BOILER.sub('', text).strip(' *')
    m = re.search(r'(ITB|RFP|RFQ|Request for Proposals?|Invitation to Bid)\s*(NO\.?|#|Number)?:?\s*([A-Z]*\d[\w-]{2,})\s+([^.]{5,90}?)(?= will be| is | are |\.|$)', t, re.I) if k == 'bid' else None
    if m:
        lab = m.group(1).upper() if len(m.group(1)) <= 3 else tcase(m.group(1))
        return clean(f'{lab} {m.group(3)}: {m.group(4)}')[:140]
    for _ in range(3):
        t2 = AGENCY_PREFIX.sub('', t).strip()
        if t2 == t:
            break
        t = t2
    caps = re.match(r"((?:[A-Z0-9][A-Z0-9,'’&:\-–()#./§]*\s+){2,}?)(?=[A-Z][a-z])", t + ' ')
    if caps and len(caps.group(1)) > 12:
        s = tcase(caps.group(1).strip(' ,:-–'))
    else:
        s = re.split(r'(?<=[a-z0-9)])\.\s', t, maxsplit=1)[0]
    return (s[:96].rsplit(' ', 1)[0] + '…') if len(s) > 100 else s


def first_date_after(text, published):
    for m in DATE.finditer(text):
        try:
            if m.group(1):
                d = dt.datetime.strptime(f'{m.group(1)[:3].title()} {m.group(2)} {m.group(3)}', '%b %d %Y').date()
            else:
                d = dt.date(int(m.group(6)), int(m.group(4)), int(m.group(5)))
        except ValueError:
            continue
        if published <= d <= published + dt.timedelta(days=400):
            return d.isoformat()
    return None


def main(raw_path):
    raw = json.load(open(raw_path))
    old = json.load(open(OUT)) if os.path.exists(OUT) else {'notices': []}
    keep = {n['notice_id']: n for n in old['notices']}
    dropped = 0
    for n in raw['notices']:
        text = clean(n.get('text'))
        if not text or DROP_TYPES.search(n.get('noticetype') or '') or DROP_TEXT.search(text[:1500]):
            dropped += 1
            continue
        pub = dt.datetime.fromtimestamp(n['publishedtimestamp'] / 1000, dt.timezone.utc).date()
        if pub.year < FIRST_YEAR:
            continue
        key, name = agency(text)
        k = kind(text)
        nid = 'pn:' + hashlib.sha1(n['id'].encode()).hexdigest()[:12]
        keep[nid] = {'notice_id': nid, 'published': pub.isoformat(), 'gov_id': key, 'agency': name, 'kind': k,
                     'kind_label': KIND_LABEL[k], 'title': title(text, k), 'event_date': first_date_after(text, pub),
                     'notice_type': n.get('noticetype'), 'text': text[:6000], 'pdf_url': n.get('pdfurl') or None,
                     'publication': n.get('newspapername'), 'source_url': raw['source_url']}
    rows = sorted(keep.values(), key=lambda r: (r['published'], r['notice_id']), reverse=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({'as_of': raw['fetched_at'], 'source_url': raw['source_url'],
               'about': 'Government notices from the county public notice website; court, tax deed and private notices left out.',
               'notices': rows}, open(OUT, 'w'), indent=1)
    print(f'{len(rows)} notices on file ({len(raw["notices"])} fetched, {dropped} court or private notices left out)')


if __name__ == '__main__':
    main(sys.argv[1])
