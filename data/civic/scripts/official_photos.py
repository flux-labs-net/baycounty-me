"""Official headshots for current officials and department leaders, from their government's own website.

Only photos a government publishes on its own pages (commission, council and school board pages, staff directories,
constitutional officers' sites). Never campaign, news or social media photos. Each photo keeps the page it came
from and a credit line, and a photo is taken down on request (remove its row here and rerun).

Each photo is cropped to a square (from the top of a portrait, so the face stays in) and saved as a 320px WebP in
site/photos/people/<person id>.webp; site/build_site.py copies them to /photos/people/. Anyone without a photo keeps
the initials circle.

Gaps (no photo on the government's site, or the site blocks downloads): Lynn Haven's mayor and two commissioners,
Panama City Beach (its site blocks automated downloads), Springfield, Mexico Beach, two Parker council members, the
tax collector and the property appraiser.

Writes data/civic/official_photos.json, read by site/page_datasets.py official_photos() (dataset official-photos).
Run: python3 data/civic/scripts/official_photos.py   (add --refetch to download every photo again)
"""
import hashlib, io, json, os, sys, time, urllib.request

from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
OUT = os.path.join(HERE, '..', 'official_photos.json')
PHOTOS = os.path.join(ROOT, 'site', 'photos', 'people')
AS_OF = '2026-10-27'
PLACE = 'fl-bay'
SIZE = 320

BAY = 'https://www.baycountyfl.gov'
PC = 'https://panamacity.gov'
LH = 'https://www.cityoflynnhaven.gov'
CW = 'https://www.cityofcallaway.com'
BDS = 'https://cmsv2-assets.apptegy.net/uploads/31249/file/'
doc = lambda base, n: f'{base}/ImageRepository/Document?documentID={n}'

# where each government's photos are published: (credit, page)
PAGES = {
    'county': ('Bay County Board of County Commissioners', f'{BAY}/directory.aspx'),
    'pc': ('City of Panama City', f'{PC}/directory.aspx'),
    'lh': ('City of Lynn Haven', f'{LH}/directory.aspx'),
    'cw_staff': ('City of Callaway', f'{CW}/directory.aspx'),
    'cw': ('City of Callaway', f'{CW}/70/Mayor-Commission'),
    'parker': ('City of Parker', 'https://cityofparker.com/government/city-council/'),
    'schools': ('Bay District Schools', 'https://www.bay.k12.fl.us/page/school-board'),
    'sheriff': ("Bay County Sheriff's Office", 'https://www.bayso.org/'),
    'clerk': ('Bay County Clerk of Court and Comptroller', 'https://www.baycoclerk.com/'),
    'soe': ('Bay County Supervisor of Elections', 'https://www.bayvotesfl.gov/about/meet-the-supervisor/'),
    'soe_staff': ('Bay County Supervisor of Elections', 'https://www.bayvotesfl.gov/about/meet-the-staff/'),
}

# person id (data/entities/people.json) -> (name as the page shows it, where, image url)
PHOTOS_LIST = [
    ('daniel-raffield', 'Daniel Raffield', 'county', doc(BAY, 16647)),
    ('robert-carroll', 'Robert Carroll', 'county', doc(BAY, 586)),
    ('doug-crosby', 'Doug Crosby', 'county', doc(BAY, 16648)),
    ('douglas-moore', 'Doug Moore', 'county', doc(BAY, 6626)),
    ('clair-pease', 'Clair Pease', 'county', doc(BAY, 13131)),
    ('joel-schubert', 'Joel Schubert', 'county', doc(BAY, 19701)),
    ('keith-bryant', 'Keith Bryant', 'county', doc(BAY, 19796)),
    ('scott-chandler', 'Scott Chandler', 'county', doc(BAY, 20176)),

    ('allan-branch', 'Allan Branch', 'pc', doc(PC, 9996)),
    ('robbie-hughes', 'Robbie Hughes', 'pc', doc(PC, 9997)),
    ('janice-lucas', 'Janice Lucas', 'pc', doc(PC, 9999)),
    ('brian-grainger', 'Brian Grainger', 'pc', doc(PC, 9998)),
    ('josh-street', 'Josh Street', 'pc', doc(PC, 6375)),
    ('jonathan-hayes', 'Jonathan Hayes', 'pc', doc(PC, 8227)),
    ('leslie-glaze', 'Leslie Glaze', 'pc', doc(PC, 12384)),
    ('mark-smith', 'Mark Smith', 'pc', doc(PC, 3113)),
    ('shiela-ware', 'Sheila Ware', 'pc', doc(PC, 4275)),

    ('jamie-warrick', 'Jamie Warrick', 'lh', doc(LH, 1670)),
    ('pat-perno', 'Pat Perno', 'lh', doc(LH, 1650)),
    ('chris-lightfoot', 'Chris Lightfoot', 'lh', doc(LH, 3539)),

    ('pamn-henderson', 'Pamn Henderson', 'cw', doc(CW, 3788)),
    ('bobby-birdsell', 'Bobby J. Birdsell', 'cw', doc(CW, 5513)),
    ('david-griggs', 'David Griggs', 'cw', doc(CW, 3786)),
    ('bob-pelletier', 'Bob Pelletier', 'cw', doc(CW, 3789)),
    ('kenneth-ayers', 'Kenneth L. Ayers, Jr.', 'cw', doc(CW, 4994)),
    ('ed-cook', 'Ed Cook', 'cw_staff', doc(CW, 5368)),

    ('andrew-kelly', 'Andrew Kelly', 'parker', 'https://cityofparker.com/wp-content/uploads/2022/01/Mayor-Andrew-Kelly--scaled.jpg'),
    ('mark-rega', 'Mark Rega', 'parker', 'https://cityofparker.com/wp-content/uploads/2022/01/IMG_2842-1-scaled.jpg'),
    ('ron-chaple', 'Ron Chaple', 'parker', 'https://cityofparker.com/wp-content/uploads/2022/01/IMG_2853-scaled.jpg'),

    ('mark-mcqueen', 'Mark McQueen', 'schools', BDS + '5574537/ae871009-e4c5-45cb-9934-a69b48dd7286.jpeg'),
    ('jerry-register', 'Jerry Register', 'schools', BDS + '5397541/bc9185d0-8521-4cf3-a2e9-5cfad0f5d074.jpeg'),
    ('ann-leonard', 'Ann Leonard', 'schools', BDS + '5397558/680840f3-3ed5-4378-b125-ef1d0a45aef5.jpeg'),
    ('chris-moore', 'Chris Moore', 'schools', BDS + '5397559/2105f677-1354-4891-a1c0-170451a58c24.jpeg'),
    ('winston-chester', 'Winston Chester', 'schools', BDS + '5397562/9f0072e9-fbd2-4bb4-801e-375fb0e48261.png'),
    ('steve-moss', 'Steve Moss', 'schools', BDS + '5397565/ca172edf-ac08-49ce-8a45-3ef83df2b8d3.jpeg'),

    ('tommy-ford', 'Tommy Ford', 'sheriff', 'https://bayso.org/wp-content/uploads/2025/09/Ford_Tommy-2021.jpg'),
    ('bill-kinsaul', 'Bill Kinsaul', 'clerk', 'https://www.baycoclerk.com/images/clerk-headshot.jpg'),
    ('nina-ward', 'Nina Ward', 'soe', 'https://bay-soe.s3.amazonaws.com/uploads/2025/07/15144812/Ward-HS-2025-1093x1200.jpg'),
    ('thien-cao', 'Thien Cao', 'soe_staff', 'https://bay-soe.s3.amazonaws.com/uploads/2025/10/24153531/Thein-450x600.jpg'),
    ('chelsea-hitt', 'Chelsea Hitt', 'soe_staff', 'https://bay-soe.s3.amazonaws.com/uploads/2025/10/24153630/Chelsea-450x600.jpg'),
]

# photos framed wider than a headshot: the square to keep, as fractions of the original (left, top, right, bottom)
CROP = {'chris-lightfoot': (0.3, 0.19, 0.7, 0.457)}


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (BayCounty.me official photos)'})
    for attempt in range(4):
        try:
            return urllib.request.urlopen(req, timeout=60).read()
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def square(img, box=None):
    img = ImageOps.exif_transpose(img).convert('RGB')
    w, h = img.size
    if box:
        img = img.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))
        w, h = img.size
    s = min(w, h)
    x = (w - s) // 2
    y = int((h - s) * 0.12)  # from near the top of a portrait, so the face stays in
    return img.crop((x, y, x + s, y + s)).resize((SIZE, SIZE), Image.LANCZOS)


def main(refetch=False):
    people = {p['id'] for p in json.load(open(os.path.join(ROOT, 'data', 'entities', 'people.json')))['people']}
    os.makedirs(PHOTOS, exist_ok=True)
    old = {}
    if os.path.exists(OUT):
        old = {r['person_id']: r for r in json.load(open(OUT)).get('photos', [])}
    rows = []
    for pid, name, where, url in PHOTOS_LIST:
        if pid not in people:
            sys.exit(f'{pid}: not in data/entities/people.json')
        path = os.path.join(PHOTOS, pid + '.webp')
        prev = old.get(pid)
        if refetch or not os.path.exists(path) or not prev or prev.get('image_source_url') != url:
            sq = square(Image.open(io.BytesIO(fetch(url))), CROP.get(pid))
            sq.save(path, 'WEBP', quality=80, method=6)
            fetched = AS_OF
        else:
            fetched = prev.get('fetched_on') or AS_OF
        credit, page = PAGES[where]
        rows.append({
            'person_id': pid, 'name': name, 'photo_path': f'/photos/people/{pid}.webp', 'width': SIZE, 'height': SIZE,
            'credit': credit, 'source_url': page, 'image_source_url': url, 'fetched_on': fetched,
            'sha256': hashlib.sha256(open(path, 'rb').read()).hexdigest()[:16],
        })
    keep = {r['person_id'] for r in rows}
    for f in os.listdir(PHOTOS):  # a photo taken off the list is deleted too
        if f.endswith('.webp') and f[:-5] not in keep:
            os.remove(os.path.join(PHOTOS, f))
    json.dump({'as_of': AS_OF, 'place_id': PLACE, 'notes': __doc__.split('\n\n')[1].replace('\n', ' '),
               'photos': rows}, open(OUT, 'w'), indent=1)
    print(f'{len(rows)} photos -> {os.path.relpath(OUT, ROOT)}')


if __name__ == '__main__':
    main('--refetch' in sys.argv)
