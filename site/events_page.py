"""Community events: the /events page and the home page's "today and coming up" section.

Built from the community-events dataset (site/page_datasets.py community_events, from data/events/<county>/events.json,
refreshed daily by data/events/fetch_events.py). The rows are embedded once as #evData and site/events.js filters them
against the visitor's own date, so the page is right even between rebuilds. The server-rendered list is the fallback.
"""
import datetime as dt
import html
import json

e = lambda s: html.escape(str(s if s is not None else ''))
KINDS = ['Community', 'Public meeting', 'Library', 'Chamber']
TONE = {'Public meeting': 'navy', 'Library': 'teal', 'Chamber': 'amber'}


def rows():
    from page_datasets import community_events
    return [r for r in community_events() if not r.get('same_as')]  # one event on two calendars shows once (data/dupes.py)


def towns(rs):
    """Towns with events, biggest first, county-wide last."""
    n = {}
    for r in rs:
        if r['town']:
            n[r['town']] = n.get(r['town'], 0) + 1
    return sorted((t for t in n if t != 'Bay County'), key=lambda t: -n[t]) + (['Bay County'] if 'Bay County' in n else [])


def data_json(rs):
    """Short keys keep the embedded copy small: t title, s/e start/end, a all day, v venue, w town, c category,
    r recurring, u link, src source."""
    out = [{'t': r['title'], 's': r['starts'], 'e': r['ends'], 'a': r['all_day'], 'v': r['venue'], 'w': r['town'],
            'c': r['category'], 'r': r['recurring'], 'u': r['url'], 'src': r['source']} for r in rs]
    return json.dumps(out, separators=(',', ':'), ensure_ascii=False).replace('</', '<\\/')


def _time(s):
    d = dt.datetime.fromisoformat(s)
    if d.hour == 0 and d.minute == 0:
        return 'All day'
    return d.strftime('%-I:%M %p').replace(':00 ', ' ').lower().replace('am', 'a.m.').replace('pm', 'p.m.')


def _row(r, src=False):
    where = ' · '.join(e(x) for x in (r['venue'], r['town'], r['source'] if src else None) if x)
    return (f'<li class="ev-row"><span class="ev-t">{"All day" if r["all_day"] else _time(r["starts"])}</span><span class="ev-b">'
            f'<a href="{e(r["url"])}" rel="noopener">{e(r["title"])}</a><small>{where}</small></span>'
            f'<span class="ev-c t-{TONE.get(r["category"], "salmon")}">{e(r["category"])}</span></li>')


def _chips(id_, label, vals, all_label):
    b = ''.join(f'<button type="button" class="chip" data-v="{e(v)}" aria-pressed="false">{e(v)}</button>' for v in vals)
    return f'<div class="chips" id="{id_}" role="group" aria-label="{label}"><button type="button" class="chip" data-v="" aria-pressed="true">{all_label}</button>{b}</div>'


def home_section():
    """The home page block: today's events, featured one-off events coming up, public meetings this week and the
    business community (chambers)."""
    rs = rows()
    if not rs:
        return ''
    today = dt.date.today().isoformat()
    todays = [r for r in rs if r['starts'][:10] <= today <= (r['ends'] or r['starts'])[:10]][:7]
    from page_datasets import chamber_leaders
    execs = [r for r in chamber_leaders() if r['role_group'] == 'Executive committee' and r.get('photo')][:8]
    faces = ''.join(f'<img src="{e(r["photo"])}" alt="{e(r["person_name"])}, {e(r["title"])}, {e(r["chamber"])}" title="{e(r["person_name"])}" width="40" height="40" loading="lazy">' for r in execs)
    tchips = ('<div class="h-chips he-chips" id="heTown" role="group" aria-label="Town"><button type="button" data-v="" aria-pressed="true">Everywhere</button>' +
              ''.join(f'<button type="button" data-v="{e(t)}" aria-pressed="false">{e(t)}</button>' for t in towns(rs)[:6]) + '</div>')
    return f'''<section class="h-events" id="homeEvents" aria-labelledby="hev">
    <div class="h-sec-hd"><div><span class="eyebrow">This week in Bay County</span><h2 id="hev">What's happening, and where.</h2></div><a href="/events">All events →</a></div>
    {tchips}
    <div class="he-grid">
      <div class="h-card he-today">
        <div class="h-card-hd"><b>Today</b><span class="muted" id="heCount"></span></div>
        <ul class="ev-list" id="heToday">{"".join(_row(r) for r in todays) or '<li class="ev-none">Nothing listed for today.</li>'}</ul>
        <a class="he-more" id="heTodayMore" href="/events" hidden>All today →</a>
      </div>
      <div class="he-soon-wrap">
        <div class="h-card-hd he-soon-hd"><b>Coming soon</b><a href="/events">Calendar →</a></div>
        <div class="he-soon" id="heSoon"></div>
      </div>
    </div>
    <div class="h-row he-row">
      <div class="h-card"><div class="h-card-hd"><b>Public meetings this week</b><a href="/meetings">Meetings →</a></div><ul class="he-meet" id="heMeet"></ul></div>
      <div class="h-card he-biz"><div class="h-card-hd"><b>Business community</b><a href="/chambers">Chambers →</a></div>
        <a class="he-faces" href="/chambers#boards" aria-label="Chamber executive committees">{faces}</a>
        <p>Who leads the Bay County and Panama City Beach chambers, their events, and the public money they get.</p>
        <nav class="h-take"><a href="/chambers#events">Chamber events</a><a href="/chambers#boards">Boards and staff</a><a href="/chambers#business">Board members' businesses</a><a href="/connections/nonprofits">Nonprofits</a></nav></div>
      <div class="h-card"><div class="h-card-hd"><b>Around the county</b></div>
        <nav class="h-take"><a href="/events?kind=Library">Library programs</a><a href="/events?kind=Community">Community events</a><a href="/my-address">Your address</a><a href="/alerts">Alerts</a><a href="/governments">Governments</a><a href="/elections">Elections</a></nav></div>
    </div>
    <p class="he-src">From public calendars: Bay County, Panama City, Lynn Haven, Callaway, Parker, the library system, Destination Panama City, Mexico Beach and the PCB Chamber. Check the organizer's page before you go.</p>
  </section>
  <script type="application/json" id="evData">{data_json(rs)}</script>
  <script src="/assets/events.js" defer></script>'''


def events_page(out_dir=None):
    from place import NAME
    rs = rows()
    today = dt.date.today().isoformat()
    upcoming = [r for r in rs if (r['ends'] or r['starts'])[:10] >= today]
    by_src = {}
    for r in upcoming:
        by_src[r['source']] = by_src.get(r['source'], 0) + 1
    fallback, days = [], {}
    for r in upcoming:
        days.setdefault(max(r['starts'][:10], today), []).append(r)
    for k in sorted(days)[:7]:
        label = 'Today' if k == today else dt.date.fromisoformat(k).strftime('%A, %B %-d')
        fallback.append(f'<section class="ev-day"><h3>{label}<span>{len(days[k])}</span></h3><ul class="ev-list">{"".join(_row(r, True) for r in days[k])}</ul></section>')
    n = lambda c: sum(1 for r in upcoming if r['category'] == c)
    week = (dt.date.today() + dt.timedelta(days=7)).isoformat()
    k = lambda t, v, c, tone: f'<div class="kpi"><span class="eyebrow">{t}</span><span class="v">{v}</span><span class="s">{c}</span></div>'
    kpis = (k('This week', sum(1 for r in upcoming if r['starts'][:10] <= week), 'Events in the next seven days', 'salmon') +
            k('Next two months', len(upcoming), f'From {len(by_src)} public calendars', 'blue') +
            k('Public meetings', n('Public meeting'), 'Commissions, boards and workshops', 'navy') +
            k('Library programs', n('Library'), 'Story times, clubs and classes', 'teal'))
    src_list = ''.join(f'<li><b>{e(s)}</b> · {c} upcoming</li>' for s, c in sorted(by_src.items(), key=lambda x: -x[1]))
    return f'''<div class="page tax ev" id="evPage">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Community · Calendar</span><h1>Events in {e(NAME)}</h1>
    <p class="lede">What's happening around the county, from the county and city calendars, the library system, the visitor bureaus and the chambers. One list, every town, updated every morning.</p></div>
    <div class="stamp"><a class="pill" href="/meetings">Public meetings →</a><span>Next two months, from public calendars</span></div></header>
  <div class="kpis">{kpis}</div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="calendar" data-tile="Calendar">Coming up</h2><span class="muted" id="evCount">{len(upcoming)} events</span></div>
    <div class="ev-ctl">
      {_chips('evTown', 'Town', towns(rs), 'Every town')}
      {_chips('evKind', 'Kind', KINDS, 'All kinds')}
      <div class="ev-tools"><label class="sr" for="evQ">Search events</label><input id="evQ" type="search" placeholder="Search events, places, organizers" autocomplete="off">
        <label class="ev-one"><input type="checkbox" id="evOne"> One-off events only</label></div>
    </div>
    <div id="evList">{"".join(fallback)}</div>
    <div><button type="button" class="ui-btn ev-morebtn" id="evMore" hidden>Show more days</button></div>
    <p class="note">Times are local. Details change, so check the organizer's page (each title links to it) before you go.</p></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li>Read every morning from each organizer's public calendar feed: the county and city calendars, The Events Calendar feeds on the library, visitor bureau and city sites, and the Mexico Beach calendar export.</li>
      <li>Only what the calendar publishes: the title, dates, place name, town and a link. Library events outside Bay County are left out.</li>
      <li>Not here yet: Panama City Beach's city calendar (its feed is empty), Springfield, Visit Panama City Beach and the Bay County Chamber, whose calendars have no public feed we can read.</li>
      <li><b>Sources now:</b></li></ul>
    <ul class="plain ev-srcs">{src_list}</ul>
    <ul class="plain"><li><b>Data:</b> <a href="/api/v1/datasets/community-events">community-events</a> (<a href="/downloads/community-events.csv">CSV</a>).</li></ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script type="application/json" id="evData">{data_json(rs)}</script>
<script src="/assets/events.js" defer></script>'''
