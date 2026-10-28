#!/usr/bin/env python3
"""News stories from the county's military installations -> data/military/<county>/news.json.

    python3 data/military/fetch_news.py [--county bay]

Source: DVIDS (dvidshub.net, the Defense Department's public media hub), one RSS feed per unit (/rss/unit/<id>?type=news).
The base websites themselves (tyndall.af.mil, cnrse.cnic.navy.mil, navsea.navy.mil) turn away automated readers, and
every story they publish is also posted to DVIDS by the same public affairs office.

Each feed carries only the latest 10 stories, so the file keeps every story it has seen and adds new ones each run.
A failed feed never removes stories already on file. Stories before 2016 are dropped (data/entities/cutoff.py).
"""
import argparse, datetime as dt, email.utils, html, json, os, re, sys, urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'entities'))
import cutoff  # noqa: E402

UA = 'Mozilla/5.0 (compatible; BayCounty.me public news reader; +https://baycounty.me/about)'
MEDIA = '{http://search.yahoo.com/mrss/}'


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/rss+xml, application/xml, */*'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip() or None


def units(county):
    return json.load(open(os.path.join(HERE, county, 'installations.json')))['news_units']


def feed(u):
    root = ET.fromstring(get(f"https://www.dvidshub.net/rss/unit/{u['dvids_id']}?type=news"))
    out = []
    for it in root.iter('item'):
        guid = (it.findtext('guid') or '').strip()
        link = (it.findtext('link') or '').strip()
        if not (guid.startswith('news:') or '/news/' in link):
            continue
        when = email.utils.parsedate_to_datetime(it.findtext('pubDate')) if it.findtext('pubDate') else None
        desc = it.findtext('description') or ''
        img = it.find(MEDIA + 'thumbnail')
        m = re.search(r'<img[^>]+src="([^"]+)"', desc)
        out.append({'news_id': 'dvids:' + (guid.split(':', 1)[1] if guid.startswith('news:') else link.rstrip('/').split('/')[-2]),
                    'installation_id': u['installation_id'], 'unit': u['unit'], 'unit_id': u['unit_id'],
                    'title': clean(it.findtext('title')), 'summary': clean(desc),
                    'published': when.astimezone(dt.timezone(dt.timedelta(hours=-5))).replace(tzinfo=None).isoformat(timespec='minutes') if when else None,
                    'author': clean(it.findtext('author')), 'url': link,
                    'image_url': img.get('url') if img is not None else (m.group(1) if m else None),
                    'source_url': f"https://www.dvidshub.net/unit/{u['dvids_unit']}"})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--county', default='bay')
    a = ap.parse_args()
    path = os.path.join(HERE, a.county, 'news.json')
    old = json.load(open(path)) if os.path.exists(path) else {'stories': []}
    seen = {r['news_id']: r for r in old['stories']}
    errors, fetched = [], dict(old.get('fetched') or {})
    for u in units(a.county):
        try:
            rows = feed(u)
            new = 0
            for r in rows:
                if r['news_id'] in seen:
                    first = seen[r['news_id']]
                    if first['unit_id'] != r['unit_id']:  # one story posted by two units: keep the first unit, note the second
                        r = {**first, 'also_unit': r['unit']}
                    else:
                        r = {**first, **{k: v for k, v in r.items() if v}}
                else:
                    new += 1
                seen[r['news_id']] = r
            fetched[u['unit_id']] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
            print(f"{u['unit']}: {len(rows)} stories, {new} new")
        except Exception as e:  # noqa: BLE001  keep what we had
            errors.append({'unit_id': u['unit_id'], 'error': f'{type(e).__name__}: {e}'[:300]})
            print(f"{u['unit']}: failed ({e}); kept stories on file", file=sys.stderr)
    stories = [r for r in seen.values() if (r.get('published') or cutoff.FIRST_DATE) >= cutoff.FIRST_DATE]
    stories.sort(key=lambda r: (r.get('published') or ''), reverse=True)
    json.dump({'as_of': dt.date.today().isoformat(), 'fetched': fetched, 'errors': errors, 'stories': stories},
              open(path, 'w'), indent=1, ensure_ascii=False)
    print(f'{len(stories)} stories -> {path}')


if __name__ == '__main__':
    main()
