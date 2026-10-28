"""repeats.py - write data/dupes/review.json: posts that may be the same thing listed twice and need a person's call.

data/dupes.py merges clear repeats on its own (the same alert re-posted with an update, a legal notice run on several days,
one event on two calendars). Pairs it isn't sure of (alike, but not alike enough, or an update that changes a date) are
listed here for /admin > Name matches (api/_name_matches.js, kind "repeat"). A call there is exported by
data/entities/export_name_decisions.py to data/dupes/decisions.json, and the next build merges or keeps apart. The live
alerts feed reads the calls straight from the database. Written by site/build_site.py.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'data'))
import dupes  # noqa: E402

OUT = os.path.join(HERE, '..', 'data', 'dupes', 'review.json')
FEEDS = {'alerts': 'Alert', 'notices': 'Public notice', 'events': 'Event', 'jobs': 'Job opening'}


def write_review(out=OUT):
    from page_datasets import emergency_notices, community_events, public_notices, job_openings
    for f in (emergency_notices, community_events, public_notices, job_openings):
        f()  # each fills dupes.REVIEW[its feed]
    pairs = [dict(p, feed=feed, feed_label=FEEDS[feed]) for feed in FEEDS for p in dupes.REVIEW.get(feed, [])]
    doc = {'about': 'Posts that may be the same thing listed twice, for /admin > Name matches. Written by site/repeats.py; see data/dupes.py.',
           'pairs': pairs}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write('\n')
    return len(pairs)
