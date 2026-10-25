"""Personal campaign gifts from people who run a Bay County business.

Individual campaign donors stay unnamed on the site, with one exception set by the site owner on 2026-10-24: a person
who runs a registered business (a Sunbiz officer, manager or registered agent) and gave to a local campaign is listed
by name, with the businesses they run.

Usage: python3 data/campaign/owner_gifts.py [WORKDIR]
  Downloads the itemized SOE (VoterFocus) export of every campaign in data/campaign/campaign.json and
  data/elections/finance_2026.json into WORKDIR (files already there are reused), matches the individual contributors
  to Sunbiz people (data/sunbiz/build_sunbiz.py) and writes data/campaign/owner_gifts.json. Exits 0 and keeps the old
  file when the SOE can't be reached.

Match rule (nothing fuzzy). A contributor filed as an individual is a business owner when:
  - the name (last + first, without Jr/Sr) and the street address and ZIP on the filing are the same as a Sunbiz officer,
    manager or registered agent of a for-profit business that was active or still filing around the gift,
  - a middle initial or a Jr/Sr given on both sides agrees, and
  - the address is not a protected voter's (those are never matched).
Registered-agent services (agents for 20+ businesses they don't run) don't count as running a business.
A name that matches only inside the same ZIP is counted (`held_zip_only`) but not published: it needs a person's check.

Only matched gifts are written. Street addresses, occupations and the gifts of everyone else are never stored.
"""
import collections, csv, datetime, io, json, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'data', 'sunbiz'))
import build_sunbiz as B  # noqa: E402
from ids import person_case  # noqa: E402  (build_sunbiz puts data/entities on the path)

OUT = os.path.join(HERE, 'owner_gifts.json')
SUFFIX = {'JR', 'SR', 'II', 'III', 'IV'}
ITEM = {'CH': 'check', 'CA': 'cash', 'IK': 'in-kind', 'MO': 'money order', 'LO': 'loan', 'RE': 'refund'}


def campaigns():
    """cand_id -> campaign facts, from both campaign files (an officeholder's 2026 campaign appears once)."""
    out = {}
    for c in json.load(open(os.path.join(ROOT, 'data', 'campaign', 'campaign.json')))['candidates']:
        m = re.search(r'cand_id=(\d+)', c.get('export_url') or '')
        if m:
            out[m.group(1)] = {'candidate': c['official'], 'office': c.get('office'), 'gov': c.get('gov'), 'election': c.get('election'),
                               'report_url': c.get('report_url'), 'export_url': c['export_url']}
    for c in json.load(open(os.path.join(ROOT, 'data', 'elections', 'finance_2026.json')))['candidates']:
        if c.get('export_url') and str(c['cand_id']) not in out:
            out[str(c['cand_id'])] = {'candidate': c['name'], 'office': c.get('office'), 'gov': None, 'election': c.get('election'),
                                      'report_url': c.get('report_url'), 'export_url': c['export_url']}
    return out


def fetch(work, camps):
    os.makedirs(work, exist_ok=True)
    for cid, c in camps.items():
        p = os.path.join(work, f'exp_{cid}.csv')
        if os.path.exists(p) and os.path.getsize(p):
            continue
        for i in range(4):
            try:
                b = urllib.request.urlopen(urllib.request.Request(c['export_url'], headers={'User-Agent': 'Mozilla/5.0 (BayCounty.me public records)'}), timeout=60).read()
                break
            except Exception:
                if i == 3:
                    raise
                time.sleep(5 * (i + 1))
        # A maintenance or error page saved as an export would quietly drop that campaign's owners; stop instead, so
        # main() keeps the last good file. Campaigns with no records answer with a "No records found" alert.
        if not (b.lstrip(b'\xef\xbb\xbf').startswith(b'"rpt code"') or b'No records found' in b[:200]):
            raise RuntimeError(f'export for campaign {cid} is not a CSV')
        open(p, 'wb').write(b)
        time.sleep(0.3)


def rows(path):
    b = open(path, 'rb').read()
    try:
        t = b.decode('utf-8')
    except UnicodeDecodeError:
        t = b.decode('latin-1')
    if not t.startswith('"rpt code"'):
        return []
    return list(csv.DictReader(io.StringIO(t)))


def _nk(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def apply_amend(R):
    """Drop each "D" (deleted) line's matching earlier item, as the SOE totals do."""
    items = [r for r in R if r['Amend. code'] != 'D']
    for r in (r for r in R if r['Amend. code'] == 'D'):
        for exact in (True, False):
            hit = next((i for i, x in enumerate(items) if x['Cont/Exp'] == r['Cont/Exp'] and _nk(x['name']) == _nk(r['name'])
                        and abs(float(x['amount'] or 0) - float(r['amount'] or 0)) < 0.005 and (not exact or x['item date'] == r['item date'])), None)
            if hit is not None:
                items.pop(hit)
                break
    return items


def clean(n):
    return re.sub(r'\s+', ' ', (n or '').replace('<br>', ' ').replace('&amp;', '&')).strip()


def suffix(raw):
    w = set(re.sub(r'[^A-Z ]', ' ', (raw or '').upper()).split()) & SUFFIX
    return min(w) if w else ''


def display(name):
    """Name as filed, recased when it is in all caps (ids.person_case)."""
    return person_case(name)


def same_person(name):
    toks = [t for t in re.sub(r'[^a-z ]', ' ', name.lower()).split() if t not in ('dr', 'jr', 'sr', 'ii', 'iii', 'mr', 'mrs', 'ms')]
    return (toks[0], toks[-1]) if toks else ('', '')


def build(work):
    camps = campaigns()
    ents, roles = B.load_registry('bay')
    people = B.group_people(ents, roles, 'bay')
    own = B.owners_of(roles, people)
    runs = collections.defaultdict(dict)  # person_key -> doc -> titles
    for doc, ps in own.items():
        if ents[doc]['nonprofit']:
            continue
        for pk, titles in ps.items():
            runs[pk][doc] = titles
    by_addr, by_zip = collections.defaultdict(list), collections.defaultdict(set)
    for r in roles:
        pk = r.get('person_key')
        if pk in runs:
            by_addr[(r['name_key'], r['zip5'], r['street'])].append(r)
            by_zip[(r['name_key'], r['zip5'])].add(pk)

    counts = collections.Counter()
    gifts, owners, held = [], {}, set()
    for cid, c in sorted(camps.items(), key=lambda t: int(t[0])):
        p = os.path.join(work, f'exp_{cid}.csv')
        if not os.path.exists(p):
            continue
        cand = same_person(c['candidate'])
        for r in apply_amend(rows(p)):
            if r['Cont/Exp'] != 'C' or r['cont. type'] != 'I':
                continue
            name = clean(r['name'])
            # joint filings ("A and B Smith") would name a second person who may not run anything
            if not name or B.looks_like_org(name) or re.search(r'&|\bAND\b', name, re.I):
                continue
            counts['individual_lines'] += 1
            if 'protected' in (r['address 1'] or '').lower():
                counts['protected_skipped'] += 1
                continue
            if same_person(name) == cand:
                continue
            key, mid = B.split_name(name.upper())
            z, st = B.zip5(r['zip']), B.street_key(r['address 1'])
            if not key or not z or not st:
                continue
            year = int(r['item date'][:4]) if (r['item date'] or '')[:4].isdigit() else None
            sfx = suffix(name)
            hits = [x for x in by_addr.get((key, z, st), [])
                    if not (mid and x['mid'] and mid != x['mid']) and not (sfx and suffix(x['raw_name']) and sfx != suffix(x['raw_name']))]
            pks = {x['person_key'] for x in hits}
            biz = {}
            for pk in pks:
                for doc, titles in runs[pk].items():
                    if B._usable(ents[doc], year):
                        biz.setdefault(doc, set()).update(titles)
            if len(pks) != 1 or not biz:
                if by_zip.get((key, z)):
                    held.add((key, z))
                continue
            pk = pks.pop()
            o = owners.setdefault(pk, {'name': display(name), 'businesses': {}})
            for doc, titles in biz.items():
                o['businesses'].setdefault(doc, set()).update(titles)
            amt = round(float(r['amount'] or 0), 2)
            gifts.append({'person_key': pk, 'cand_id': cid, 'date': r['item date'], 'amount': amt, 'item': ITEM.get(r['item type'], r['item type'] or '')})
            counts['published_lines'] += 1

    # a person whose lines to a campaign net to zero or less (refunds only) did not give: don't name them for it
    net = collections.defaultdict(float)
    for g in gifts:
        net[(g['person_key'], g['cand_id'])] += g['amount']
    gifts = [g for g in gifts if net[(g['person_key'], g['cand_id'])] > 0]
    keep = {g['person_key'] for g in gifts}
    owners = {pk: o for pk, o in owners.items() if pk in keep}
    counts['published_lines'] = len(gifts)

    for pk, o in owners.items():
        o['businesses'] = sorted(({'doc_number': d, 'name': ents[d]['name'], 'status': 'active' if ents[d]['status'] == 'A' else 'inactive',
                                   'titles': sorted(t for t in ts if t)} for d, ts in o['businesses'].items()),
                                 key=lambda b: (b['status'] != 'active', b['name']))
    counts['published_donors'] = len(owners)
    counts['held_zip_only'] = len(held)
    used = {g['cand_id'] for g in gifts}
    return {
        'as_of': datetime.date.today().isoformat(),
        'source': 'Bay County Supervisor of Elections itemized campaign finance exports (VoterFocus); Florida Division of Corporations (Sunbiz)',
        'method': ('A contributor filed as an individual is listed when the name and the street address on the filing are the same as an '
                   'officer, manager or registered agent of a for-profit business on Sunbiz that was active or still filing around the gift. '
                   'Middle initials and Jr/Sr must agree. Protected voters are never matched. Name-only matches are not published.'),
        'counts': dict(counts),
        'campaigns': {cid: {k: camps[cid][k] for k in ('candidate', 'office', 'gov', 'election', 'report_url')} for cid in sorted(used, key=int)},
        'owners': dict(sorted(owners.items())),
        'gifts': sorted(gifts, key=lambda g: (g['person_key'], int(g['cand_id']), g['date'] or '')),
    }


def main():
    work = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get('RUNNER_TEMP', '/tmp'), 'soe_exports')
    camps = campaigns()
    try:
        fetch(work, camps)
    except Exception as e:
        print(f'SOE exports unavailable ({e}); keeping {os.path.relpath(OUT, ROOT)}')
        return
    res = build(work)
    if not res['gifts'] and os.path.exists(OUT):
        print('No matches (exports empty?); keeping the existing file')
        return
    json.dump(res, open(OUT, 'w'), indent=1, sort_keys=False)
    open(OUT, 'a').write('\n')
    print('owner gifts:', res['counts'])


if __name__ == '__main__':
    main()
