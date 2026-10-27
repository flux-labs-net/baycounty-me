"""First-seen dates for votes, contracts and change orders (data/weekly/first_seen.json), for the weekly email.

Minutes are posted weeks after a meeting, so "votes this week" by meeting date is nearly always empty. The weekly
email ("This week in Bay County", site/weekly.py) instead lists records that reached BayCounty.me in the past week.
This file remembers the day each record first showed up. It runs from data/build.py, so the daily refresh adds new
records with that day's date and commits the file.

The first run seeds every record with its own date (meeting or approval), so old records never count as new.
Keys: vote:<vote id>, contract:<hash>, change_order:<hash> (record_key below; site/weekly.py uses the same).
"""
import datetime as dt
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'first_seen.json')
sys.path.insert(0, os.path.join(DATA, 'entities'))


def _j(*p):
    try:
        return json.load(open(os.path.join(DATA, *p)))
    except FileNotFoundError:
        return None


def record_key(kind, r):
    """Stable key for a contract or change order: what it is, not where it sits in the file."""
    parts = [r.get('government'), r.get('vendor'), r.get('date'), r.get('amount') if kind == 'contract' else r.get('change_amount'),
             r.get('purpose') if kind == 'contract' else r.get('project')]
    return f'{kind}:' + hashlib.sha1('|'.join(str(x or '') for x in parts).encode()).hexdigest()[:12]


def records():
    """(key, record date) for every vote, contract and change order."""
    import ids
    out = []
    v = _j('votes', 'votes.json') or {'votes': []}
    out += [('vote:' + vid, x.get('date')) for vid, x in zip(ids.vote_ids(v['votes']), v['votes'])]
    out += [('vote:' + x['vote_id'], x.get('date')) for x in (_j('votes', 'minutes_votes.json') or {}).get('votes') or [] if x.get('vote_id')]
    ct = _j('contracts', 'contracts.json') or {}
    out += [(record_key('contract', r), r.get('date')) for r in ct.get('contracts') or []]
    out += [(record_key('change_order', r), r.get('date')) for r in ct.get('change_orders') or []]
    return out


def main(today=None):
    today = today or dt.date.today().isoformat()
    seeding = not os.path.exists(OUT)
    seen = {} if seeding else json.load(open(OUT))['first_seen']
    added = 0
    for key, date in records():
        if key in seen:
            continue
        # seeding: a record counts from its own date; later: from today (never before its own date)
        seen[key] = (date or today)[:10] if seeding else max(today, (date or today)[:10])
        added += 1
    json.dump({'note': 'Day each vote, contract and change order first appeared on BayCounty.me (data/weekly/track_new.py).',
               'first_seen': dict(sorted(seen.items()))}, open(OUT, 'w'), indent=0, separators=(',', ':'))
    print(f'weekly: {"seeded" if seeding else "new records"}: {added}')


if __name__ == '__main__':
    main()
