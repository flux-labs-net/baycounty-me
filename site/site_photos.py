"""Photos of places in the county on the site's own pages (the homepage first): the hero, the section cards, the
this-week story and the Your money band. Read from data/photos/<county>/site_photos.json (picked by hand, free
licenses only) and published as the site-photos dataset. Each photo shows its credit and license on the page.
"""
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _file():
    from place import PLACE_ID
    return os.path.join(HERE, '..', 'data', 'photos', PLACE_ID.split('-', 1)[-1], 'site_photos.json')


def rows():
    f = _file()
    if not os.path.exists(f):
        return []
    d = json.load(open(f))
    out = []
    for r in d['photos']:
        big, small = max(r['sizes']), min(r['sizes'])
        path = f"/photos/site/{r['file']}-{big}.webp"
        out.append({'place_id': d['place_id'], 'photo_id': r['photo_id'], 'page': r['page'], 'slot': r['slot'], 'title': r['title'],
                    'place_name': r['place_name'], 'photo_url': 'https://baycounty.me' + path, 'photo_path': path,
                    'small_path': f"/photos/site/{r['file']}-{small}.webp", 'credit': r['credit'], 'license': r['license'],
                    'license_url': r['license_url'], 'source_url': r['source_url'], 'taken': r.get('taken'), 'fetched_on': d['fetched_on']})
    return out


def photo(slot, page='/'):
    """The row for one slot on a page, or None."""
    return next((r for r in rows() if r['page'] == page and r['slot'] == slot), None)


def credit_html(r):
    """'Photo: Royalbroil, CC BY-SA 4.0' with the source page and license linked."""
    e = html.escape
    return (f'Photo: <a href="{e(r["source_url"])}" rel="noopener">{e(r["credit"])}</a>, '
            f'<a href="{e(r["license_url"])}" rel="license noopener">{e(r["license"])}</a>')


DATASETS = [
    ('site-photos', 'Site photos',
     "Photos of places in the county on BayCounty.me's own pages, one row per spot a photo fills (page and slot: hero is the top of the homepage, "
     "door:<section> the homepage card for that menu section, feature the this-week story, money the Your money band). title says what it shows and "
     "place_name where. photo_url is the WebP BayCounty.me serves (small_path a smaller copy for cards). Picked by hand from Wikimedia Commons, free "
     "licenses only: credit is the photographer, license and license_url the license, source_url the photo's Commons page.",
     rows),
]
