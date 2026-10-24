"""The place this build of the site covers (a county and its local governments).

Everything that changes from one county to the next lives in places/<id>/place.json: the site's
name and domain, the list of local governments, and how each dataset names them. Pick the place
with the PLACE environment variable (default: fl-bay). Pages read names from here instead of
hard-coding them, so the same generator can build a site for another Florida county.

See docs/STATEWIDE.md for the plan.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
PLACE_ID = os.environ.get('PLACE', 'fl-bay')
PLACE_DIR = os.path.join(HERE, '..', 'places', PLACE_ID)
PLACE = json.load(open(os.path.join(PLACE_DIR, 'place.json')))

SITE = PLACE['site_name']                 # BayCounty.me
DOMAIN = PLACE['domain']                  # https://baycounty.me
NAME = PLACE['name']                      # Bay County
LABEL = PLACE['place_label']              # Bay County, Florida
STATE = PLACE['state_name']               # Florida
EMAIL = PLACE['contact_email']
OPERATOR = PLACE['operator']
OFFICIALS = PLACE['officials']


def wordmark_html():
    """The site name as the header and footer show it: 'BayCounty' with an accent '.me'."""
    a, b = PLACE['wordmark']
    return f'{a}<b>{b}</b>'


def governments():
    """Every local government, each a flat dict: key, slug, short, name, kind, blurb, menu_desc, plus
    the dataset name matchers (tax, auth, debt, audit, ...)."""
    out = []
    for g in PLACE['governments']:
        d = {k: v for k, v in g.items() if k != 'match'}
        d.update(g.get('match') or {})
        d.setdefault('blurb', None)
        out.append(d)
    return out
