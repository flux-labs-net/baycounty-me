"""Special events with road closures (IRONMAN Florida first): the closures with their times and map lines, and each
event's visitor guide (schedule, course, where to watch, getting around).

Read from data/events/<county>/special/<event>.json (entered by hand from the police traffic advisory and the event's
own guide) and <event>.geo.json (map lines, data/events/place_closures.py). Published as the event-road-closures and
event-guide datasets; /events/ironman-florida (site/ironman_page.py) is built from them.
"""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def events():
    """Every special event on file for this place, with its map lines, in date order."""
    from place import PLACE_ID
    d = os.path.join(HERE, '..', 'data', 'events', PLACE_ID.split('-', 1)[-1], 'special')
    out = []
    for f in sorted(glob.glob(os.path.join(d, '*.json'))):
        if f.endswith('.geo.json'):
            continue
        ev = json.load(open(f))
        g = f[:-5] + '.geo.json'
        ev['lines'] = json.load(open(g)).get('lines', {}) if os.path.exists(g) else {}
        out.append(ev)
    return sorted(out, key=lambda e: e['starts_at'])


def event(event_id):
    return next((e for e in events() if e['id'] == event_id), None)


def event_road_closures():
    from place import PLACE_ID
    rows = []
    for ev in events():
        for i, c in enumerate(ev['closures']):
            line = ev['lines'].get(c['id'])
            rows.append({'place_id': PLACE_ID, 'event_id': ev['id'], 'event_name': ev['name'], 'event_page': ev['page'], 'closure_id': c['id'],
                         'sort_order': i + 1, 'road': c['road'], 'limits': c['limits'], 'kind': c['kind'], 'starts_at': c['starts_at'],
                         'ends_at': c['ends_at'], 'town': ev['town'], 'gov_id': ev.get('gov_id'),
                         'geometry': json.dumps({'type': line['type'], 'coordinates': line['coordinates']}, separators=(',', ':')) if line else None,
                         'placed': (line or {}).get('properties', {}).get('placed'), 'as_of': ev['as_of'],
                         'source': ev['closure_source'], 'source_url': 'https://baycounty.me' + ev['closure_source_url']})
    return rows


def event_guide():
    from place import PLACE_ID
    rows = []
    for ev in events():
        for i, g in enumerate(ev['guide']):
            police = g.get('source') == 'police'
            rows.append({'place_id': PLACE_ID, 'event_id': ev['id'], 'event_name': ev['name'], 'section': g['section'], 'sort_order': i + 1,
                         'title': g['title'], 'text': g['text'], 'when_text': g.get('when'), 'at': g.get('at'),
                         'distance_miles': g.get('distance'), 'lat': g.get('lat'), 'lon': g.get('lon'), 'link': g.get('link'),
                         'as_of': ev['as_of'], 'source': ev['closure_source'] if police else ev['guide_source'],
                         'source_url': 'https://baycounty.me' + ev['closure_source_url'] if police else ev['guide_source_url']})
    return rows


DATASETS = [
    ('event-road-closures', 'Special event road closures',
     "Road closures and traffic delays for special events such as IRONMAN Florida, one row per closure, from the police department's traffic advisory: "
     "the road and the cross streets it is closed between, closed or delay, and when it starts and ends (ISO times with the Central offset). "
     "geometry is the closed stretch as a GeoJSON line in WGS84, placed on the county street centerlines from the street names (placed = street-names).",
     event_road_closures),
    ('event-guide', 'Special event visitor guide',
     "The visitor guide for each special event on the site, one row per item: the race week schedule (at = start time), the course (distance_miles), "
     "where to watch (with a map point where there is one), getting around and things to do nearby, each with its source.",
     event_guide),
]


def banner():
    """A card linking to each special event page from a week before it starts until it ends (pages rebuild daily)."""
    import datetime as dt
    import html
    from ui import ico
    today = dt.date.today().isoformat()
    out = []
    for ev in events():
        first = (dt.date.fromisoformat(ev['starts_at'][:10]) - dt.timedelta(days=7)).isoformat()
        if first <= today <= ev['ends_at'][:10]:
            n = len(ev['closures'])
            out.append(f'''<a class="im-ban" href="{html.escape(ev["page"])}">{ico("flag", "salmon")}<span class="im-ban-t"><b>{html.escape(ev["name"])}: road closures and race week guide</b>
  <small>{n} road closures and delays around Pier Park. See what's closed now and play through race day on the map.</small></span><span class="im-go">Open map →</span></a>''')
    if not out:
        return ''
    return ('<style>.im-ban{display:flex;gap:14px;align-items:center;padding:14px 18px;border-radius:20px;background:var(--surface);box-shadow:var(--ui-shadow);'
            'color:inherit;text-decoration:none;border:2px solid var(--tint-salmon)}.im-ban:hover{border-color:var(--salmon)}.im-ban .im-ban-t{display:flex;flex-direction:column;gap:2px;min-width:0;flex:1}'
            '.im-ban small{color:var(--muted);font-size:.86rem}.im-ban .im-go{flex:none;font-weight:600;color:var(--accent-ink);font-size:.88rem}'
            '@media (max-width:640px){.im-ban .im-go{display:none}}</style>' + ''.join(out))
