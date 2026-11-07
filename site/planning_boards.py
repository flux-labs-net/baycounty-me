"""Planning and zoning boards: the appointed board in each government that holds the first public hearing on
rezonings, land-use changes, site plans and variances and recommends to the commission or council.

Two datasets (migration 0107_planning_boards.sql):
  planning-boards         one row per board: what it does, who appoints it, when it meets, its next and last meeting
                          (from data/meetings/meetings.json, same board ids) and where its records are
  planning-board-members  one row per member, from data/civic/planning_boards.json (city pages and minutes roll calls)

Shown in the "Planning board" section of each government page (gov_pages.py) and on members' profiles (entity_graph.py).
"""
import html
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
e = lambda s: html.escape(str(s if s is not None else ''))

KIND = {'planning': 'Planning board', 'adjustment': 'Board of adjustment'}
DOES = {'planning': 'Holds the first public hearing on rezonings, land-use and comprehensive plan changes, site plans and subdivisions, then recommends to the {to}, which makes the final decision.',
        'adjustment': 'Hears requests for variances from the zoning code and advises the {to}.'}


def _j(*p, default=None):
    try:
        return json.load(open(os.path.join(DATA, *p)))
    except FileNotFoundError:
        return default


def _file():
    return _j('civic', 'planning_boards.json', default={'boards': [], 'rosters': []})


def _meetings():
    return _j('meetings', 'meetings.json', default={'meetings': []}).get('meetings', [])


def member_entity(name):
    """person:<id> for a name that is a known official, else member:<id> (the board-member id nonprofit and chamber
    board members share, so the same person gets one profile)."""
    import sys
    sys.path.insert(0, os.path.join(DATA, 'entities'))
    import ids
    from page_datasets import _member_key
    pid = ids.person_id(name)
    return ('person:' + pid, 'official') if pid else ('member:' + _member_key(name), None)


def boards():
    """planning-boards rows."""
    F = _file()
    ros = {r['board_id']: r for r in F.get('rosters', [])}
    ms = _meetings()
    out = []
    for b in F.get('boards', []):
        mine = [m for m in ms if m.get('board') == b['board_id'] and not m.get('cancelled')]
        nxt = next((m for m in sorted(mine, key=lambda m: m['start']) if not m.get('past')), None)
        last = next((m for m in mine if m.get('past')), None)
        r = ros.get(b['board_id']) or {}
        out.append({
            'board_id': b['board_id'], 'gov_id': b['gov_id'], 'name': b['name'], 'kind': KIND[b['kind']],
            'also': b.get('also'), 'what_it_does': DOES[b['kind']].format(to=b['recommends_to']),
            'recommends_to': b['recommends_to'], 'appointed_by': b['appointed_by'], 'seats': b.get('seats'),
            'alternates': b.get('alternates'), 'term_years': b.get('term_years'),
            'members_listed': len(r.get('members') or []), 'roster_as_of': r.get('as_of'), 'roster_source': r.get('source_title'),
            'roster_source_url': r.get('source_url'), 'roster_note': r.get('note'),
            'records_online': b.get('records_online'),
            'next_meeting': nxt['start'] if nxt else None, 'next_meeting_status': nxt.get('status') if nxt else None,
            'next_agenda_url': nxt.get('agenda_url') if nxt else None,
            'last_meeting': last['start'] if last else None, 'last_agenda_url': last.get('agenda_url') if last else None,
            'last_minutes_url': last.get('minutes_url') if last else None,
            'page_url': b['page_url'], 'source_url': b['page_url']})
    return out


ROLE_ORDER = {'Chair': 0, 'Vice Chair': 1, 'Member': 2, 'Alternate': 3}


def members():
    """planning-board-members rows."""
    from entity_graph import page_url
    F = _file()
    names = {b['board_id']: b for b in F.get('boards', [])}
    out = []
    for r in F.get('rosters', []):
        b = names.get(r['board_id'])
        if not b:
            continue
        rows = sorted(r['members'], key=lambda m: (ROLE_ORDER.get(m['role'], 9), m.get('seat') or '', m['name'].split()[-1]))
        for i, m in enumerate(rows):
            eid, match = member_entity(m['name'])
            out.append({'board_id': b['board_id'], 'gov_id': b['gov_id'], 'board': b['name'], 'sort_order': i + 1,
                        'name': m['name'], 'role': m['role'], 'seat': m.get('seat'), 'term_end': m.get('term_end'),
                        'appointed_by': b['appointed_by'], 'person_entity_id': eid, 'person_url': page_url(eid), 'person_match': match,
                        'as_of': r['as_of'], 'source_title': r['source_title'], 'source_url': r['source_url']})
    return out


DATASETS = [
    ('planning-boards', 'Planning and zoning boards',
     "Each government's appointed planning board (planning commission, planning board, planning & zoning board) and board of adjustment: "
     "what it decides, who it recommends to (the commission or council makes the final decision), who appoints it, seats and terms, "
     "how many members are listed and from what record (roster_as_of, roster_source_url), the next and last meeting from the meetings dataset "
     "(board_id matches meetings.board) with agenda and minutes links, and what records the government posts online.",
     boards),
    ('planning-board-members', 'Planning and zoning board members',
     "Who sits on each planning and zoning board: name, role (chair, vice chair, member, alternate), seat and term end where the city lists them, "
     "and who appoints the board. Members are public appointees, named because the government publishes them; no addresses, phone numbers or emails. "
     "From the city's own board page where there is one (Mexico Beach, Parker), otherwise the roll call in the board's latest posted minutes "
     "(as_of is that meeting's date). Only full names are listed. person_entity_id links to the member's profile; person_match is 'official' "
     "when the member is also a local official.",
     members),
]


# ---------- government page section ----------

def _when(iso):
    from datetime import datetime
    try:
        d = datetime.fromisoformat(iso)
    except Exception:
        return ''
    t = d.strftime('%-I:%M %p').replace(':00 ', ' ') if 'T' in iso else ''
    return d.strftime('%a, %b %-d, %Y') + (f' at {t}' if t else '')


def hint(key):
    bs = [b for b in boards() if b['gov_id'] == key]
    if not bs:
        return ''
    n = sum(b['members_listed'] for b in bs)
    nxt = min((b['next_meeting'] for b in bs if b['next_meeting']), default=None)
    return f'Next: {_when(nxt).split(",", 1)[1].split(",")[0].strip()}' if nxt else (f'{n} members listed' if n else 'Rezonings and variances')


def section(key):
    """The 'Planning board' section on a government page, or '' when the government has none on file."""
    from ui import ico, avatar, tone_of, photo_of
    bs = [b for b in boards() if b['gov_id'] == key]
    if not bs:
        return ''
    mem = members()
    cards = []
    for b in bs:
        ms = [m for m in mem if m['board_id'] == b['board_id']]
        people = []
        for m in ms:
            sub = ' · '.join(x for x in [m['role'] if m['role'] != 'Member' and not (m.get('seat') or '').startswith(m['role']) else '', m.get('seat') or '',
                                          f"term ends {_when(m['term_end']).split(', ', 1)[1]}" if m.get('term_end') else ''] if x) or 'Member'
            pid = m['person_entity_id'].split(':', 1)[1] if m['person_entity_id'].startswith('person:') else None
            inner = f'{avatar(m["name"], tone_of(m["name"]), photo=photo_of(pid) if pid else None)}<span><b>{e(m["name"])}</b><small>{e(sub)}</small></span>'
            people.append(f'<a class="ui-person" href="{e(m["person_url"])}" data-share-record>{inner}</a>')
        if not people:
            people.append(f'<div class="ui-person vac">{avatar(None, "blue", "users")}<span><b>Members not published online</b><small>Appointed by the {e(b["appointed_by"])}</small></span></div>')
        facts = ' · '.join(x for x in [
            f'{b["seats"]} seats' + (f' and {b["alternates"]} alternates' if b.get('alternates') else '') if b.get('seats') else '',
            f'{b["term_years"]}-year terms' if b.get('term_years') else '', f'appointed by the {b["appointed_by"]}'] if x)
        meet = []
        if b['next_meeting']:
            ag = f' · <a href="{e(b["next_agenda_url"])}" target="_blank" rel="noopener">Agenda</a>' if b.get('next_agenda_url') else ' · agenda not posted yet' if b['next_meeting_status'] != 'calendar' else ' · agenda not posted online'
            meet.append(f'<span>{ico("calendar")}Next meeting {e(_when(b["next_meeting"]))}{ag}</span>')
        if b['last_meeting']:
            links = ' · '.join(x for x in [f'<a href="{e(b["last_agenda_url"])}" target="_blank" rel="noopener">agenda</a>' if b.get('last_agenda_url') else '',
                                            f'<a href="{e(b["last_minutes_url"])}" target="_blank" rel="noopener">minutes</a>' if b.get('last_minutes_url') else ''] if x)
            meet.append(f'<span>{ico("clock")}Last met {e(_when(b["last_meeting"]))}{" · " + links if links else ""}</span>')
        roster = ''
        if b['members_listed']:
            roster = f'Members: {e(b["roster_source"])}' if b.get('roster_source') else ''
            roster = f'<a href="{e(b["roster_source_url"])}" target="_blank" rel="noopener">{roster}</a>' if b.get('roster_source_url') else roster
        note = f'<p class="small muted">{e(b["roster_note"])}</p>' if b.get('roster_note') else ''
        cards.append(f'''<article class="pb-card" id="pb-{e(b['board_id'])}" data-share-record>
          <h3 class="ui-h3">{e(b['name'])}</h3>
          <p class="small">{e(b['what_it_does'])}{f" It is also the {e(b['also'][0].lower() + b['also'][1:])}." if b.get('also') else ''}</p>
          <p class="small muted">{e(facts[0].upper() + facts[1:])}.</p>
          {f'<div class="ui-meta">{"".join(meet)}</div>' if meet else ''}
          <div class="ui-people">{"".join(people)}</div>{note}
          <p class="src-line">{roster}{" · " if roster else ""}<a href="{e(b['page_url'])}" target="_blank" rel="noopener">Board page</a> · {e(b['records_online'])}</p>
        </article>''')
    n = sum(b['members_listed'] for b in bs)
    sub = f'{len(bs)} board{"s" if len(bs) != 1 else ""}' + (f' · {n} members listed' if n else '')
    return (f'<section class="tx-sec"><div class="sec-hd"><h2 id="plan">Planning and zoning board{"s" if len(bs) != 1 else ""}</h2><span class="muted">{e(sub)}</span>'
            f'<a class="ui-crumb" href="/meetings?gov={e(key)}">All meetings {ico("arrow")}</a></div>{"".join(cards)}</section>')
