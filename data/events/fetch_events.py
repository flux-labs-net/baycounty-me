#!/usr/bin/env python3
"""Upcoming community events from public calendars around the county -> data/events/<county>/events.json.

    python3 data/events/fetch_events.py [--county bay] [--days 60]

Sources (all public feeds the publishers offer for sharing their calendars):
  * County and city calendars on CivicPlus sites: the calendar's RSS feed (RSSFeed.aspx?ModID=58).
  * Sites running The Events Calendar plugin: its public JSON feed (/wp-json/tribe/events/v1/events).
  * Sites that only offer an iCal export: the .ics feed.
  * The PCB Chamber's events, already fetched by data/chambers/fetch_events.py, are read from that file.

A source that fails keeps the events it had (and the error is recorded), so one site being down never empties the
calendar. Feeds that only publish the next week or two are merged with what we already had further out.

Only what the calendar publishes: title, dates, venue name and town, category and the event's own link. No addresses.
"""
import argparse, datetime as dt, html, json, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
UA = 'Mozilla/5.0 (compatible; BayCounty.me public calendar reader; +https://baycounty.me/about)'

# Towns in the county; a library or tourism event elsewhere (the library system also serves Gulf and Liberty) is skipped.
TOWNS = {'Panama City', 'Panama City Beach', 'Lynn Haven', 'Callaway', 'Parker', 'Springfield', 'Mexico Beach',
         'Southport', 'Youngstown', 'Fountain', 'Laguna Beach', 'Inlet Beach', 'Bay County'}

SOURCES = {
    'bay': [
        {'id': 'bay-county', 'name': 'Bay County', 'kind': 'civicplus', 'gov': 'county', 'town': 'Bay County',
         'url': 'https://www.baycountyfl.gov/RSSFeed.aspx?ModID=58&CID=All-calendar.xml', 'page': 'https://www.baycountyfl.gov/Calendar.aspx'},
        {'id': 'panama-city', 'name': 'City of Panama City', 'kind': 'civicplus', 'gov': 'pc', 'town': 'Panama City',
         'url': 'https://www.panamacity.gov/RSSFeed.aspx?ModID=58&CID=All-calendar.xml', 'page': 'https://www.panamacity.gov/Calendar.aspx'},
        {'id': 'lynn-haven', 'name': 'City of Lynn Haven', 'kind': 'civicplus', 'gov': 'lh', 'town': 'Lynn Haven',
         'url': 'https://www.cityoflynnhaven.gov/RSSFeed.aspx?ModID=58&CID=All-calendar.xml', 'page': 'https://www.cityoflynnhaven.gov/Calendar.aspx'},
        {'id': 'callaway', 'name': 'City of Callaway', 'kind': 'civicplus', 'gov': 'cw', 'town': 'Callaway',
         'url': 'https://www.cityofcallaway.com/RSSFeed.aspx?ModID=58&CID=All-calendar.xml', 'page': 'https://www.cityofcallaway.com/Calendar.aspx'},
        {'id': 'parker', 'name': 'City of Parker', 'kind': 'tribe', 'gov': 'parker', 'town': 'Parker',
         'url': 'https://cityofparker.com', 'page': 'https://cityofparker.com/events/'},
        {'id': 'destination-pc', 'name': 'Destination Panama City', 'kind': 'tribe', 'gov': None, 'town': 'Panama City',
         'url': 'https://www.destinationpanamacity.com', 'page': 'https://www.destinationpanamacity.com/events/', 'category': 'Community'},
        {'id': 'mexico-beach', 'name': 'Mexico Beach (visitor events)', 'kind': 'ics', 'gov': None, 'town': 'Mexico Beach',
         'url': 'https://www.mexicobeach.com/events/list/?ical=1', 'page': 'https://www.mexicobeach.com/events/', 'category': 'Community'},
        {'id': 'library', 'name': 'Northwest Regional Library System', 'kind': 'tribe', 'gov': None, 'town': None,
         'url': 'https://www.nwrls.com', 'page': 'https://www.nwrls.com/events', 'category': 'Library'},
        {'id': 'pcb-chamber', 'name': 'Panama City Beach Chamber', 'kind': 'chamber', 'gov': None, 'town': 'Panama City Beach',
         'url': None, 'page': 'https://pcbeach.org/local-events/'},
    ],
}

MEETING = re.compile(r'\b(meeting|commission|council|board|workshop|committee|hearing|authority|budget|charter review|'
                     r'planning|zoning|special magistrate|code enforcement|ULDC)\b', re.I)


def get(url, timeout=40, tries=3):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json, text/calendar, application/rss+xml, */*'})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode('utf-8', 'replace')
        except OSError:
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip() or None


def town_of(city):
    c = clean(city)
    if not c:
        return None
    c = c.title().replace('Pcb', 'Panama City Beach')
    return c if c in TOWNS else None


def category_of(title, default):
    if MEETING.search(title or '') and default not in ('Library',):
        return 'Public meeting'
    return default or 'Community'


def row(src, eid, title, starts, ends, all_day, venue, town, category, cost, url):
    title = clean(title)
    return {'event_id': f"{src['id']}:{eid}", 'source_id': src['id'], 'source': src['name'], 'gov': src['gov'],
            'town': town or src['town'], 'title': title, 'starts': starts, 'ends': ends or None, 'all_day': bool(all_day),
            'venue': clean(venue), 'category': category_of(title, category or src.get('category')), 'cost': clean(cost),
            'url': url or src['page'], 'source_url': src['page']}


def _t(day, s):
    """'October 29, 2026' + '05:30 PM' -> '2026-10-29T17:30:00'."""
    d = dt.datetime.strptime(day.strip(), '%B %d, %Y')
    if s:
        t = dt.datetime.strptime(s.strip().upper(), '%I:%M %p')
        d = d.replace(hour=t.hour, minute=t.minute)
    return d.strftime('%Y-%m-%dT%H:%M:%S')


def civicplus(src, today, horizon):
    text = get(src['url'])
    out = []
    for item in re.findall(r'<item>(.*?)</item>', text, re.S):
        tag = lambda k: (re.search(rf'<{k}>(.*?)</{k}>', item, re.S) or [None, None])[1]
        dates = clean(tag('calendarEvent:EventDates')) or ''
        times = clean(tag('calendarEvent:EventTimes')) or ''
        days = [d.strip() for d in dates.split(' - ')]
        tparts = [t.strip() for t in times.split(' - ')] if re.search(r'\d', times) else []
        try:
            starts = _t(days[0], tparts[0] if tparts else None)
            end_day = days[1] if len(days) > 1 else days[0]
            ends = _t(end_day, tparts[1] if len(tparts) > 1 else None) if (len(days) > 1 or len(tparts) > 1) else None
        except (ValueError, IndexError):
            continue
        if starts[:10] > horizon or (ends or starts)[:10] < today:
            continue
        link = clean(tag('link')) or ''
        eid = (re.search(r'EID=(\d+)', link) or [None, None])[1] or link
        loc = clean(tag('calendarEvent:Location'))
        venue = None
        if loc:  # the feed runs address lines together; keep only a named place, never a street address
            first = re.split(r'\d', loc, maxsplit=1)[0].strip(' ,')
            venue = first if len(first) > 3 and not re.search(r',\s*FL\b', first) else None
        out.append(row(src, f'{eid}:{starts[:10]}', tag('title'), starts, ends, not tparts, venue, None, None, None, link))
    return out


def tribe(src, today, horizon):
    out, page = [], 1
    while page <= 20:
        d = json.loads(get(f"{src['url']}/wp-json/tribe/events/v1/events?per_page=50&page={page}&start_date={today}&end_date={horizon}"))
        for e in d.get('events', []):
            v = e.get('venue') if isinstance(e.get('venue'), dict) else {}
            town = town_of(v.get('city'))
            if src['town'] is None and not town:
                continue  # library branches outside the county
            cats = [clean(c.get('name')) for c in e.get('categories') or []]
            out.append(row(src, f"{e['id']}:{e['start_date'][:10]}", e.get('title'), e['start_date'].replace(' ', 'T'),
                           (e.get('end_date') or '').replace(' ', 'T'), e.get('all_day'), v.get('venue'), town,
                           src.get('category') or (cats[0] if cats else None), e.get('cost'), e.get('url')))
        if page >= (d.get('total_pages') or 1):
            break
        page += 1
    return out


def ics(src, today, horizon):
    text = re.sub(r'\r?\n[ \t]', '', get(src['url']))
    out = []
    for block in re.findall(r'BEGIN:VEVENT(.*?)END:VEVENT', text, re.S):
        f = {}
        for line in block.strip().splitlines():
            k, _, v = line.partition(':')
            f.setdefault(k.split(';')[0], (k, v.strip()))

        def when(key):
            k, v = f.get(key, ('', ''))
            v = v.rstrip('Z')
            if not v:
                return None, False
            if len(v) == 8:
                return f'{v[:4]}-{v[4:6]}-{v[6:8]}T00:00:00', True
            return f'{v[:4]}-{v[4:6]}-{v[6:8]}T{v[9:11]}:{v[11:13]}:00', False
        starts, all_day = when('DTSTART')
        ends, _ = when('DTEND')
        if not starts or starts[:10] > horizon or (ends or starts)[:10] < today:
            continue
        if all_day and ends:  # iCal all-day end is exclusive
            ends = (dt.datetime.fromisoformat(ends) - dt.timedelta(days=1)).strftime('%Y-%m-%dT00:00:00')
        unesc = lambda s: (s or '').replace('\\,', ',').replace('\\;', ';').replace('\\n', ' ')
        loc = unesc(f.get('LOCATION', ('', ''))[1])
        venue = loc.split(',')[0].strip() if loc and not re.match(r'\d', loc) else None
        uid = f.get('UID', ('', starts))[1]
        out.append(row(src, f"{uid.split('@')[0]}:{starts[:10]}", unesc(f.get('SUMMARY', ('', ''))[1]), starts, ends,
                       all_day, venue, src['town'], None, None, f.get('URL', ('', ''))[1] or None))
    return out


def chamber(src, today, horizon):
    p = os.path.join(ROOT, 'data', 'chambers', ARGS.county, 'events.json')
    d = json.load(open(p))
    out = []
    for e in d.get('events', []):
        if e.get('chamber_id') != src['id'] or (e.get('ends') or e['starts'])[:10] < today or e['starts'][:10] > horizon:
            continue
        out.append(row(src, e['event_id'].split(':', 1)[1], e['title'], e['starts'], e.get('ends'), e.get('all_day'),
                       e.get('venue'), town_of(e.get('city')), 'Chamber' if e.get('chamber_event') else 'Community',
                       e.get('cost'), e.get('url')))
    return out


def main():
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument('--county', default='bay')
    ap.add_argument('--days', type=int, default=60)
    ARGS = ap.parse_args()
    out_dir = os.path.join(HERE, ARGS.county)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, 'events.json')
    old = json.load(open(path)) if os.path.exists(path) else {'events': []}
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=-5)))  # Central (close enough for a date cutoff)
    today = now.date().isoformat()
    horizon = (now.date() + dt.timedelta(days=ARGS.days)).isoformat()
    events, errors = [], {}
    for src in SOURCES[ARGS.county]:
        kept = [e for e in old['events'] if e['source_id'] == src['id'] and (e.get('ends') or e['starts'])[:10] >= today]
        try:
            got = globals()[src['kind']](src, today, horizon)
            if got:  # short feeds: keep what we had beyond the last day this fetch covered
                last = max(e['starts'][:10] for e in got)
                ids = {e['event_id'] for e in got}
                got += [e for e in kept if e['starts'][:10] > last and e['event_id'] not in ids]
            print(f"{src['id']}: {len(got)} events", file=sys.stderr)
        except Exception as ex:  # noqa: BLE001 - one bad source must not stop the rest
            errors[src['id']] = f'{type(ex).__name__}: {ex}'[:300]
            got = kept
            print(f"{src['id']}: failed ({errors[src['id']]}), kept {len(kept)}", file=sys.stderr)
        events += got
    seen, uniq = set(), []
    for e in sorted(events, key=lambda e: (e['starts'], e['title'] or '')):
        if e['event_id'] in seen or not e['title']:
            continue
        seen.add(e['event_id'])
        uniq.append(e)
    # repeating programs (the same title on two or more dates) are flagged so pages can lead with one-off events
    dates = {}
    for e in uniq:
        dates.setdefault((e['source_id'], e['title'].lower()), set()).add(e['starts'][:10])
    for e in uniq:
        e['recurring'] = len(dates[(e['source_id'], e['title'].lower())]) >= 2
    doc = {'place_id': f'fl-{ARGS.county}', 'as_of': today, 'fetched': now.strftime('%Y-%m-%dT%H:%M:%S%z'),
           'sources': [{k: s[k] for k in ('id', 'name', 'page')} for s in SOURCES[ARGS.county]],
           'errors': errors, 'events': uniq}
    with open(path, 'w') as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write('\n')
    print(f'{len(uniq)} events -> {os.path.relpath(path, ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
