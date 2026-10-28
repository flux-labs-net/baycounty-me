"""Every person's photo, by profile id: one lookup for profiles, connection lists, People cards, government pages,
search, the network maps and the apps (dataset person-photos).

Two sources, both hand-checked and both published by the organization the person serves:
  1. official headshots a government publishes (data/civic/official_photos.json, data/civic/scripts/official_photos.py)
  2. board and staff headshots a chamber of commerce publishes (data/chambers/<county>/photos.json,
     data/chambers/scripts/chamber_photos.py), matched to the chamber's board list in chambers.json

A government photo wins over a chamber photo for the same person. A chamber board member who is also an official
(person_id in chambers.json) gets the chamber photo on their official profile when their government publishes none.
Board members without an official post have a member: profile (the nonprofits build's b_ id, page_datasets._member_key),
so the same photo shows on the chamber page and on that profile.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = 'https://baycounty.me'
_C = {}


def _load(p):
    return json.load(open(p)) if os.path.exists(p) else None


def rows():
    """One row per person with a photo, government photos first."""
    if 'rows' in _C:
        return _C['rows']
    out, seen = [], set()
    off = _load(os.path.join(HERE, '..', 'data', 'civic', 'official_photos.json')) or {'photos': []}
    for r in off['photos']:
        eid = 'person:' + r['person_id']
        seen.add(eid)
        out.append({'entity_id': eid, 'person_id': r['person_id'], 'name': r['name'], 'photo_path': r['photo_path'],
                    'photo_url': SITE + r['photo_path'], 'published_by': 'government', 'credit': r['credit'],
                    'source_url': r['source_url'], 'image_source_url': r['image_source_url'], 'fetched_on': r['fetched_on']})
    from place import PLACE_ID
    d = os.path.join(HERE, '..', 'data', 'chambers', PLACE_ID.split('-', 1)[-1])
    C, P = _load(os.path.join(d, 'chambers.json')), _load(os.path.join(d, 'photos.json'))
    if C and P:
        from page_datasets import _member_key
        ph = {(p['chamber_id'], p['name']): p for p in P['photos']}
        names = {c['chamber_id']: c['name'] for c in C['chambers']}
        for cid, leaders in C['leaders'].items():
            for r in leaders:
                p = ph.get((cid, r['name']))
                if not p:
                    continue
                pid = r.get('person_id')
                eid = 'person:' + pid if pid else 'member:' + _member_key(r['name'])
                if eid in seen:
                    continue
                seen.add(eid)
                out.append({'entity_id': eid, 'person_id': pid, 'name': r['name'], 'photo_path': p['photo'],
                            'photo_url': SITE + p['photo'], 'published_by': 'chamber', 'credit': names.get(cid, cid),
                            'source_url': p['source_url'], 'image_source_url': p['image_url'], 'fetched_on': C.get('as_of')})
    _C['rows'] = out
    return out


def by_id():
    """Rows by profile id ('person:x', 'member:b_...') and by bare person id ('x'), for the site's /people/<id> pages."""
    if 'by' not in _C:
        m = {}
        for r in rows():
            m[r['entity_id']] = r
            if r['person_id']:
                m.setdefault(r['person_id'], r)
        _C['by'] = m
    return _C['by']
