#!/usr/bin/env python3
"""Board and staff headshots that each chamber publishes on its own board and staff pages.

    python3 data/chambers/scripts/chamber_photos.py [--county bay] [--refetch]

Reads the board_url and staff_url of each chamber in data/chambers/<county>/chambers.json, pairs each headshot with the
leader named next to it (the image's alt text when it names them, else the nearest image just before their name),
and saves a 320px square WebP to site/photos/chamber/<chamber>-<name>.webp (site/build_site.py copies site/photos to
/photos/). The pairs go to data/chambers/<county>/photos.json with the source page, so each one can be checked and a
photo can be taken down on request: add the name to SKIP and rerun.

Only photos the chamber publishes of its own board and staff. No other sources.
"""
import argparse, html, io, json, os, re, sys, urllib.request

from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, 'site', 'photos', 'chamber')
UA = 'Mozilla/5.0 (compatible; BayCounty.me; +https://baycounty.me/about)'
SIZE = 320
SKIP = set()  # 'chamber-id|Name' pairs that must not get a photo (wrong match or a takedown request)


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def images(page):
    """(position, url, alt) for each content image, in page order; lazy-loaded images use data-src."""
    out = []
    for m in re.finditer(r'<img\b[^>]*>', page):
        tag = m.group(0)
        src = (re.search(r'\sdata-src="([^"]+)"', tag) or re.search(r'\ssrc="([^"]+)"', tag) or [None, ''])[1]
        if not src or src.startswith('data:') or not re.search(r'\.(jpe?g|png|webp)(\?|$)', src, re.I):
            continue
        if re.search(r'logo|icon|sponsor|banner|728x90|cloudinary', src, re.I):
            continue
        alt = html.unescape((re.search(r'\salt="([^"]*)"', tag) or [None, ''])[1])
        if out and out[-1][1] == src:  # the no-script copy of a lazy image
            continue
        out.append((m.start(), src, alt))
    return out


def pair(page, names):
    imgs, used, found = images(page), set(), {}
    # 1. alt text naming the person
    for n in names:
        last = n.split()[-1].lower()
        for pos, src, alt in imgs:
            if src not in used and n.lower() in alt.lower() or (alt and alt.lower().startswith(n.split()[0].lower()) and last in alt.lower()):
                found[n] = src; used.add(src); break
    # 2. the image whose caption is the person: the text right after the image (up to the next image) starts with the name.
    #    Pages list people we don't track, so "nearest image before the name" alone would hand out their photos.
    for i, (pos, src, alt) in enumerate(imgs):
        if src in used:
            continue
        end = imgs[i + 1][0] if i + 1 < len(imgs) else pos + 3000
        cap = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', page[pos:end]))).strip()[:120].lower()
        for n in names:
            if n not in found and cap.startswith(n.lower()):
                found[n] = src; used.add(src); break
    return found


def square(img):
    img = ImageOps.exif_transpose(img).convert('RGB')
    w, h = img.size
    s = min(w, h)
    x, y = (w - s) // 2, 0 if h > w else (h - s) // 2
    return img.crop((x, y, x + s, y + s)).resize((SIZE, SIZE), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--county', default='bay')
    ap.add_argument('--refetch', action='store_true')
    a = ap.parse_args()
    d = json.load(open(os.path.join(ROOT, 'data', 'chambers', a.county, 'chambers.json')))
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for c in d['chambers']:
        cid = c['chamber_id']
        leaders = d['leaders'].get(cid, [])
        for url, groups in ((c.get('board_url'), None), (c.get('staff_url'), {'Staff'})):
            if not url:
                continue
            names = sorted({l['name'] for l in leaders if l['group'] != 'Past chairs' and (groups is None or l['group'] in groups)
                            and (groups is not None or l['group'] != 'Staff')})
            page = get(url).decode('utf-8', 'replace')
            for n, src in sorted(pair(page, names).items()):
                if f'{cid}|{n}' in SKIP:
                    continue
                file = f'{cid}-{slug(n)}.webp'
                path = os.path.join(OUT, file)
                if a.refetch or not os.path.exists(path):
                    try:
                        square(Image.open(io.BytesIO(get(src)))).save(path, 'WEBP', quality=82)
                    except Exception as ex:  # noqa: BLE001
                        print(f'{n}: {ex}', file=sys.stderr)
                        continue
                rows.append({'chamber_id': cid, 'name': n, 'photo': f'/photos/chamber/{file}', 'image_url': src, 'source_url': url})
    keep = {r['photo'].rsplit('/', 1)[1] for r in rows}
    for f in os.listdir(OUT):  # photos for people no longer listed (or skipped) come down
        if f.endswith('.webp') and f not in keep:
            os.remove(os.path.join(OUT, f))
    with open(os.path.join(ROOT, 'data', 'chambers', a.county, 'photos.json'), 'w') as f:
        json.dump({'note': 'Headshots each chamber publishes on its own board and staff pages.', 'photos': rows}, f, indent=1, ensure_ascii=False)
        f.write('\n')
    print(f'{len(rows)} photos', file=sys.stderr)


if __name__ == '__main__':
    main()
