"""Draft public records requests when a source we follow stops publishing (stale data).

Each check below looks at a data file the daily refresh keeps up to date and finds the places where the official
source's newest record is older than the source's usual schedule allows. Example: the Florida Department of Health
samples beach water at each Healthy Beaches site every week or two, so a site whose newest published sample is from 2025
is a gap.

For each check and records custodian this writes the gaps to data/civic/stale_requests.json. /admin (and the daily
alerts run) turns them into drafts in corr.records_requests (api/_records_requests.js seedStale, letters in
api/_stale_requests.js) and lists them in the Records requests tab, where an
admin reviews, edits, sends or dismisses each one. Nothing is sent from here.

Each gap has a gap_id made of the check, the place and the date of its newest record ("beach-water:Bay11:2025-05-05").
A gap that is already in a sent or dismissed request is never drafted again; the same place going stale again later (a
newer last record) is a new gap.

Run: python3 data/civic/scripts/stale_requests.py [--today 2026-10-30] [--out file.json]
To add a check: write a function that returns gaps (see beach_water) and add it to CHECKS with its custodian.
"""
import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
OUT = os.path.join(HERE, '..', 'stale_requests.json')

# Who keeps each source's records, and where they say to send a request. contact_url is where the address is published.
CUSTODIANS = {
    'fdoh': {'government': 'Florida Department of Health', 'government_key': 'fdoh',
             'recipient_name': 'Public Records Coordinator, Florida Department of Health', 'recipient_email': 'PublicRecordsRequest@FLHealth.gov',
             'contact_url': 'https://www.floridahealth.gov/public-records/',
             'notes': 'The Department of Health takes records requests centrally (PublicRecordsRequest@FLHealth.gov, 850-245-4005). '
                      'Beach sampling in Bay County is done by the Florida Department of Health in Bay County.'},
}


def _date(s):
    return dt.date.fromisoformat(str(s)[:10])


def beach_water(today):
    """Healthy Beaches sites whose newest published sample is more than 45 days old. The state samples weekly, every
    other week off season, so 45 days is three missed samples at the slower pace."""
    path = os.path.join(ROOT, 'data', 'outdoors', 'bay', 'water_quality.json')
    if not os.path.exists(path):
        return []
    w = json.load(open(path))
    gaps = []
    for s in w.get('sites', []):
        if not s.get('active'):
            continue
        mine = sorted((r for r in w.get('samples', []) if r['site_id'] == s['site_id']), key=lambda r: r['date'])
        if not mine:
            continue
        last = mine[-1]
        d = _date(last['date'])
        age = (today - d).days
        if age <= 45:
            continue
        name = s['name']
        listed = s.get('lookup_name') or ''
        listed = None if not listed or listed.lower().replace(' ', '') in name.lower().replace(' ', '') else listed.title()
        result = f'rated {last["rating"]} ({last["reported"]} enterococci per 100 mL)' if last.get('rating') else 'not rated'
        gaps.append({'gap_id': f'beach-water:{s["site_id"]}:{d.isoformat()}', 'location': name, 'listed_as': listed, 'site_id': s['site_id'], 'epa_beach_id': s.get('epa_beach_id'),
                     'last_record': d.isoformat(), 'expected_every_days': 14,
                     'last_result': result, 'source_url': s['source_url'],
                     'need': f'Healthy Beaches samples at {name} after {d:%B} {d.day}, {d.year}'})
    return gaps


def _gov_custodians():
    """Each local government's records custodian (the same list the budget requests use)."""
    sys.path.insert(0, HERE)
    from records_requests import RECIPIENTS, NOTES
    return {g: {'government': gov, 'government_key': g, 'recipient_name': who, 'recipient_email': email, 'contact_url': url,
                'notes': NOTES.get(g) if g in ('pcb', 'sp', 'schools') else None}
            for g, (gov, who, email, url) in RECIPIENTS.items()}


# biggest and newest first; a draft asks for at most this many awards, and the rest wait for the next one
AWARDS_PER_REQUEST = 12


def award_follow_up(today):
    """Contract awards in the minutes with no later record of the job six months on (site/award_followup.py): ask the
    government for the signed contract, purchase orders and payments. Gaps carry their government's custodian."""
    os.environ.setdefault('BC_TODAY', today.isoformat())
    sys.path.insert(0, os.path.join(ROOT, 'site'))
    import award_followup as A
    cust = _gov_custodians()
    gaps = []
    for r in A.flagged():
        if r['gov_id'] not in cust:
            continue
        who = r['entity_id'] or 'text:' + r['company'].lower().replace(' ', '-')
        gaps.append({'gap_id': f'award-follow-up:{r["vote_id"]}:{who}', 'custodian': r['gov_id'], 'gov_id': r['gov_id'],
                     'location': f'{r["company"]}, awarded {r["award_date"]}', 'company': r['company'], 'entity_id': r['entity_id'],
                     'award_date': r['award_date'], 'last_record': r['award_date'], 'amount': r['amount'], 'bid_numbers': r['bid_numbers'],
                     'board': r['board'], 'headline': r['headline'], 'source_url': r['source_url'],
                     'need': f'Contract, purchase orders and payments for the {r["award_date"]} award to {r["company"]}'})
    gaps.sort(key=lambda g: g['award_date'], reverse=True)
    gaps.sort(key=lambda g: -(g['amount'] or 0))  # stable: biggest first, then newest
    return gaps


# check id -> (title, custodian key, find gaps, where the data shows on the site). custodian None: each gap names its
# own (gap['custodian'], a government key), and each custodian gets its own draft. The letter for each check is written
# in api/_stale_requests.js, which drafts it from the gaps that haven't been requested yet.
CHECKS = {
    'beach-water': ('Beach water quality samples', 'fdoh', beach_water, '/beaches#water'),
    'award-follow-up': ('Contract awards with no later record', None, award_follow_up, '/governments'),
}
# checks whose gaps are already in the order to ask for them (the rest are sorted by gap id), and how many go in one letter
ORDERED = {'award-follow-up'}
PER_REQUEST = {'award-follow-up': AWARDS_PER_REQUEST}


def drafts(today):
    out = []
    for check, (title, cust, find, page) in CHECKS.items():
        gaps = find(today)
        if not gaps:
            continue
        groups = {}
        for g in gaps:
            groups.setdefault(cust or g['custodian'], []).append(g)
        for ck, gs in groups.items():
            c = CUSTODIANS[ck] if cust else _gov_custodians()[ck]
            if check not in ORDERED:
                gs.sort(key=lambda g: g['gap_id'])
            pg = f'/governments/{_slug(ck)}#contracts' if check == 'award-follow-up' else page
            out.append({'key': f'stale-{check}-{ck}', 'kind': 'stale', 'check': check, 'check_title': title, 'page': pg,
                        'government': c['government'], 'government_key': c['government_key'], 'recipient_name': c['recipient_name'],
                        'recipient_email': c['recipient_email'], 'contact_url': c['contact_url'], 'notes': c.get('notes'),
                        'max_gaps': PER_REQUEST.get(check), 'gaps': gs})
    return out


def _slug(gov_id):
    """The government page's slug (/governments/<slug>)."""
    sys.path.insert(0, os.path.join(ROOT, 'data', 'entities'))
    import ids
    for g in ids.governments():
        if g.get('id') == gov_id:
            return g.get('slug') or gov_id
    return gov_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--today', help='YYYY-MM-DD (default: today)')
    ap.add_argument('--out', default=OUT, help='where to write (default: data/civic/stale_requests.json)')
    a = ap.parse_args()
    today = _date(a.today) if a.today else dt.date.today()
    d = drafts(today)
    json.dump({'as_of': today.isoformat(),
               'about': 'Records request drafts for sources whose newest official record is older than the source’s usual schedule. '
                        'Seeded into corr.records_requests and sent only from /admin after review.',
               'requests': d}, open(a.out, 'w'), indent=1, ensure_ascii=False)
    for r in d:
        print(r['key'], len(r['gaps']), ', '.join(g['location'] for g in r['gaps']))


if __name__ == '__main__':
    main()
