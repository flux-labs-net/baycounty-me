#!/usr/bin/env python3
"""Upcoming events from each chamber's public calendar -> data/chambers/<county>/events.json.

    python3 data/chambers/fetch_events.py [--county bay]

Panama City Beach Chamber: the site's events calendar (The Events Calendar plugin) has a public JSON feed,
/wp-json/tribe/events/v1/events. Bay County Chamber: its calendar is on GrowthZone (business.panamacity.org), which
turns away cloud servers; the script tries the calendar's public iCal and RSS feeds and, when they don't answer, keeps
the events it had and notes the error. A failed source never wipes events already on file.

Only what the calendar publishes: title, dates, venue name and city, category and the event's own link.
"""
import argparse, datetime as dt, html, json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = 'Mozilla/5.0 (compatible; BayCounty.me public calendar reader; +https://baycounty.me/about)'
TZ_OFFSET = None  # times are kept as the calendar's local wall time (America/Chicago)


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json, text/calendar, application/rss+xml, */*'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip() or None


def tribe(chamber_id, base, today):
    """Every upcoming event from a The Events Calendar site, page by page."""
    out, page = [], 1
    while page <= 20:
        d = json.loads(get(f'{base}/wp-json/tribe/events/v1/events?per_page=50&page={page}&start_date={today}'))
        for e in d.get('events', []):
            v = e.get('venue') if isinstance(e.get('venue'), dict) else {}
            cats = [clean(c.get('name')) for c in e.get('categories') or []]
            out.append({'chamber_id': chamber_id, 'event_id': f"{chamber_id}:{e['id']}", 'title': clean(e.get('title')),
                        'starts': e['start_date'].replace(' ', 'T'), 'ends': (e.get('end_date') or '').replace(' ', 'T') or None,
                        'all_day': bool(e.get('all_day')), 'venue': clean(v.get('venue')), 'city': clean(v.get('city')),
                        'category': ', '.join(c for c in cats if c) or None,
                        'chamber_event': any(c and 'chamber' in c.lower() for c in cats),
                        'cost': clean(e.get('cost')), 'url': e.get('url'), 'source_url': f'{base}/local-events/'})
        if page >= (d.get('total_pages') or 1):
            break
        page += 1
    return out


def ics(chamber_id, url, source_url):
    """Events from an iCal feed (VEVENT DTSTART/DTEND/SUMMARY/LOCATION/URL)."""
    text = re.sub(r'\r?\n[ \t]', '', get(url))
    out = []
    for block in re.findall(r'BEGIN:VEVENT(.*?)END:VEVENT', text, re.S):
        f = {}
        for line in block.strip().splitlines():
            k, _, v = line.partition(':')
            f[k.split(';')[0]] = v.strip()
        def when(v):
            v = (v or '').rstrip('Z')
            if re.fullmatch(r'\d{8}', v):
                return f'{v[:4]}-{v[4:6]}-{v[6:]}T00:00:00', True
            m = re.fullmatch(r'(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})', v)
            return (f'{m[1]}-{m[2]}-{m[3]}T{m[4]}:{m[5]}:{m[6]}', False) if m else (None, False)
        s, allday = when(f.get('DTSTART'))
        e, _ = when(f.get('DTEND'))
        if not s:
            continue
        uid = re.sub(r'[^A-Za-z0-9]+', '-', f.get('UID') or s + (f.get('SUMMARY') or ''))[:60]
        out.append({'chamber_id': chamber_id, 'event_id': f'{chamber_id}:{uid}', 'title': clean(f.get('SUMMARY', '').replace('\\,', ',')),
                    'starts': s, 'ends': e, 'all_day': allday, 'venue': clean((f.get('LOCATION') or '').replace('\\,', ',').split(',')[0]) or None,
                    'city': None, 'category': 'Chamber Events', 'chamber_event': True, 'cost': None, 'url': f.get('URL') or source_url,
                    'source_url': source_url})
    return out


SOURCES = {
    'bay': [
        ('pcb-chamber', lambda today: tribe('pcb-chamber', 'https://pcbeach.org', today)),
        ('bay-chamber', lambda today: _first(
            lambda: ics('bay-chamber', 'https://business.panamacity.org/events/calendarics', 'https://business.panamacity.org/events-calendar'),
            lambda: ics('bay-chamber', 'https://business.panamacity.org/events/ical', 'https://business.panamacity.org/events-calendar'))),
    ],
}


def _first(*fns):
    err = None
    for fn in fns:
        try:
            rows = fn()
            if rows:
                return rows
        except Exception as e:  # noqa: BLE001  try the next feed
            err = e
    raise err or RuntimeError('no events in any feed')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--county', default='bay')
    a = ap.parse_args()
    path = os.path.join(HERE, a.county, 'events.json')
    old = json.load(open(path)) if os.path.exists(path) else {'events': []}
    today = dt.date.today().isoformat()
    events, errors, fetched = [], [], {}
    for cid, fn in SOURCES[a.county]:
        try:
            rows = fn(today)
            events += rows
            fetched[cid] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
            print(f'{cid}: {len(rows)} events')
        except Exception as e:  # noqa: BLE001  keep what we had for this chamber
            kept = [r for r in old['events'] if r['chamber_id'] == cid and (r.get('ends') or r['starts'])[:10] >= today]
            events += kept
            fetched[cid] = (old.get('fetched') or {}).get(cid)
            errors.append({'chamber_id': cid, 'error': f'{type(e).__name__}: {e}'[:300], 'kept': len(kept)})
            print(f'{cid}: failed ({e}); kept {len(kept)} events on file', file=sys.stderr)
    events.sort(key=lambda r: (r['starts'], r['chamber_id'], r['title'] or ''))
    json.dump({'as_of': today, 'fetched': fetched, 'errors': errors, 'events': events}, open(path, 'w'), indent=1, ensure_ascii=False)
    print(f'{len(events)} events -> {path}')


if __name__ == '__main__':
    main()
