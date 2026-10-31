"""Upcoming meetings (/meetings) and a subscribable calendar (/meetings.ics)."""
import html, json, os, re
from datetime import datetime, timedelta, timezone
from govs import GOVS, _load
from city_filter import city_bar, data_g

e = lambda s: html.escape(str(s if s is not None else ''))
GN = {g['key']: g['short'] for g in GOVS}


def _dt(s):
    try:
        if len(s) == 10:
            return datetime.fromisoformat(s + 'T00:00:00-05:00'), False
        return datetime.fromisoformat(s), True
    except Exception:
        return None, False


def _when(s):
    d, timed = _dt(s)
    if not d:
        return s
    return d.strftime('%a, %b %-d') + (d.strftime(' · %-I:%M %p').replace(':00 ', ' ') if timed else '')


def _date_tile(s):
    """The month, day and weekday in a small calendar tile (ui.css .ui-date)."""
    d, _ = _dt(s or '')
    if not d:
        return ''
    return f'<span class="ui-date" aria-hidden="true"><span class="mo">{d.strftime("%b").upper()}</span><span class="d">{d.day}</span><span class="wd">{d.strftime("%a")}</span></span>'


def ics(meetings, boards):
    def esc_ics(t):
        return re.sub(r'([,;\\])', r'\\\1', str(t or '')).replace('\n', '\\n')
    now = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//BayCounty.me//Meetings//EN', 'CALSCALE:GREGORIAN', 'X-WR-CALNAME:Bay County public meetings', 'X-WR-TIMEZONE:America/Chicago']
    for i, m in enumerate(meetings):
        d, timed = _dt(m.get('start') or '')
        if not d or m.get('past'):
            continue
        b = boards.get(m['board'], {})
        uid = re.sub(r'[^a-z0-9]', '', (m['board'] + (m.get('start') or '') + (m.get('title') or '')).lower())[:60] + '@baycounty.me'
        out += ['BEGIN:VEVENT', f'UID:{uid}', f'DTSTAMP:{now}']
        if timed:
            u = d.astimezone(timezone.utc)
            out += [f'DTSTART:{u.strftime("%Y%m%dT%H%M%SZ")}', f'DTEND:{(u + timedelta(hours=2)).strftime("%Y%m%dT%H%M%SZ")}']
        else:
            out += [f'DTSTART;VALUE=DATE:{d.strftime("%Y%m%d")}', f'DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime("%Y%m%d")}']
        title = f'{b.get("name", m["board"])}: {m.get("title") or "Meeting"}' + (' (expected)' if m.get('expected') else '')
        desc = (m.get('agenda_url') and f'Agenda: {m["agenda_url"]}\n' or '') + ('Expected from the regular schedule; confirm before going.\n' if m.get('expected') else '') + 'From BayCounty.me/meetings'
        out += [f'SUMMARY:{esc_ics(title)}', f'LOCATION:{esc_ics(m.get("location") or b.get("location") or "")}', f'DESCRIPTION:{esc_ics(desc)}']
        if m.get('agenda_url'):
            out.append(f'URL:{m["agenda_url"]}')
        out.append('END:VEVENT')
    out.append('END:VCALENDAR')
    return '\r\n'.join(out) + '\r\n'


def meetings_page(out_dir):
    md = _load().get('meetings') or {'boards': [], 'meetings': []}
    # the meetings file is written ahead of the build: a meeting dated before today is past, whatever its flag says
    today = datetime.now().date().isoformat()
    for m in md['meetings']:
        if m.get('start') and m['start'][:10] < today:
            m['past'] = True
    boards = {b['id']: b for b in md.get('boards', [])}
    open(os.path.join(out_dir, 'meetings.ics'), 'w', newline='').write(ics([m for m in md['meetings'] if not m.get('past')], boards))
    up = sorted((m for m in md['meetings'] if not m.get('past') and m.get('start')), key=lambda m: m['start'])
    past = sorted((m for m in md['meetings'] if m.get('past')), key=lambda m: m.get('start') or '', reverse=True)

    def card(m):
        b = boards.get(m['board'], {})
        items = ''.join(f'<li>{e(x["title"][:220])}{"…" if len(x["title"]) > 220 else ""}{f" <b>{e(x["amount"])}</b>" if x.get("amount") else ""}</li>' for x in (m.get('items') or [])[:6])
        links = ' · '.join(x for x in [f'<a href="{e(m["agenda_url"])}" target="_blank" rel="noopener">Agenda</a>' if m.get('agenda_url') else '',
                                       f'<a href="{e(m["packet_url"])}" target="_blank" rel="noopener">Packet</a>' if m.get('packet_url') else '',
                                       f'<a href="{e(m["minutes_url"])}" target="_blank" rel="noopener">Minutes</a>' if m.get('minutes_url') else ''] if x)
        return f'''<li class="fd mt ui-mtc" data-g="{e(b.get("gov"))}" data-gn="{e(GN.get(b.get("gov"), ""))}" data-d="{e(m.get("start") or "")}" data-b="{e(b.get("name") or m["board"])}" data-t="{e(m.get("title") or "")}" data-l="{e(m.get("location") or "")}" data-a="{e(m.get("agenda_url") or "")}" data-m="{e(m.get("minutes_url") or "")}" data-s="{"expected" if m.get("expected") else "posted" if m.get("agenda_url") else "calendar"}">{_date_tile(m.get("start"))}<div class="ui-mtc-b"><div class="vt-top"><span class="vt-board">{e(b.get("name") or m["board"])}</span>{'<span class="badge">Expected</span>' if m.get("expected") else '<span class="badge ok">Agenda posted</span>' if m.get("agenda_url") and not m.get("past") else ''}</div>
          <div class="vt-h">{e(_when(m["start"]))}</div><p class="small">{e(m.get("title") or "")}{(" · " + e(m.get("location"))) if m.get("location") else ""}</p>
          {f'<details class="mt-items"><summary>{len(m["items"])} money item{"s" if len(m["items"]) != 1 else ""} on the agenda</summary><ul class="plain small">{items}</ul></details>' if m.get("items") else ""}
          {f'<p class="small">{links}</p>' if links else ('<p class="small muted">From the regular schedule; the agenda isn\'t posted yet.</p>' if m.get("expected") else '<p class="small muted">On the government\'s calendar; the agenda isn\'t posted yet.</p>' if not m.get("past") else '')}</div></li>'''
    sched = ''.join(f'<tr{data_g(b.get("gov"))}><th scope="row">{e(b["name"])}<small>{e(GN.get(b.get("gov"), ""))}</small></th><td class="small">{e(b.get("schedule"))}{(" · " + e(b.get("location"))) if b.get("location") else ""}</td><td class="small">{f"<a class=src href={json.dumps(b.get("calendar_url") or b.get("source_url"))} target=_blank rel=noopener>Calendar</a>" if (b.get("calendar_url") or b.get("source_url")) else ""}</td></tr>' for b in md.get('boards', []))
    gk = [g['key'] for g in GOVS if any(b.get('gov') == g['key'] for b in boards.values())]
    opts = ''.join(f'<option value="{k}">{e(GN[k])}</option>' for k in gk)
    gen = md.get('generated', '')[:10]
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Get involved</span><h1>Upcoming public meetings</h1>
    <p class="lede">When and where every Bay County board meets, with agenda links and the money items on each agenda. Public comment is open at regular meetings; check the agenda for how to speak.</p></div>
    <div class="stamp"><a class="pill" href="/meetings.ics">Add to my calendar</a><button type="button" class="pdf-btn" id="pdf"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>Checked {e(gen)}</span></div></header>
  {city_bar(gk, hide=True)}
  <div class="vt-filters mt-f mt-tools"><label class="vf" hidden><span>Government</span><select id="mtG" data-city-link><option value="">All governments</option>{opts}</select></label>
    <label class="vf"><span>Search</span><input id="mtQ" type="search" placeholder="Board, place or agenda item"></label>
    <label class="vf"><span>Sort</span><select id="mtS"><option value="date">By date</option><option value="az">Board A to Z</option></select></label>
    <div class="vf"><span>&nbsp;</span><button type="button" class="tt-csv" id="mtCsv">Download CSV</button></div></div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="next">Coming up</h2><span class="muted" id="mtCount" aria-live="polite">{len(up)} meetings in the next 60 days{f' ({sum(1 for m in up if m.get("expected"))} expected from regular schedules)' if any(m.get('expected') for m in up) else ''}</span></div>
    <ol class="findings" id="mtList" data-city-empty="No upcoming meetings found for {{city}}.">{"".join(card(m) for m in up) or '<li class="muted">No upcoming meetings found.</li>'}</ol></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="recent">Most recent meeting of each board</h2></div><ol class="findings" id="mtPast" data-city-empty="No recent meetings found for {{city}}.">{"".join(card(m) for m in past)}</ol></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="sched">Regular schedules</h2></div>
    <div class="tablewrap"><table class="tx-table mt-sched"><thead><tr><th scope="col">Board</th><th scope="col">When and where</th><th scope="col"></th></tr></thead><tbody>{sched}</tbody></table></div>
    <p class="note">"Expected" meetings are projected from a board's regular schedule because no agenda is posted yet. Boards cancel and move meetings, so confirm on the agenda before you go. The School Board's site couldn't be read by our tools; check bay.k12.fl.us. The calendar link works with Apple, Google and Outlook calendars.</p></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>
(() => {{
  const $ = id => document.getElementById(id), s = $('mtG'), qs = $('mtQ'), so = $('mtS');
  const lists = [['mtList', 'asc'], ['mtPast', 'desc']];  // coming up: soonest first; recent: newest first
  const run = () => {{
    let n = 0; const w = qs.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    lists.forEach(([id, dir]) => {{
      const ol = $(id), lis = [...ol.querySelectorAll(':scope > li[data-g]')];
      lis.forEach(li => {{ const t = li.textContent.toLowerCase() + ' ' + li.dataset.gn.toLowerCase(); const on = (!s.value || li.dataset.g === s.value) && w.every(x => t.includes(x)); li.hidden = !on; if (on && id === 'mtList') n++; }});
      const keys = [{{get: li => li.dataset.d, type: 'date', dir}}, {{get: li => li.dataset.b, type: 'text', dir: 'asc'}}];
      if (so.value === 'az') keys.unshift(keys.pop());
      window.TT && TT.sortBy(lis, keys).forEach(li => ol.appendChild(li));
    }});
    $('mtCount').textContent = n + ' meeting' + (n === 1 ? '' : 's') + ' in the next 60 days';
  }};
  [s, qs, so].forEach(x => {{ x.addEventListener('input', run); x.addEventListener('change', run); }});
  $('mtCsv').addEventListener('click', () => {{
    const rows = [];
    lists.forEach(([id]) => $(id).querySelectorAll(':scope > li[data-g]:not([hidden])').forEach(li => {{ const d = li.dataset; rows.push([id === 'mtList' ? 'Coming up' : 'Most recent', d.d, d.b, d.gn, d.t, d.l, d.s, d.a, d.m]); }}));
    TT.csv('baycounty-meetings' + (s.value ? '-' + s.value : ''), ['list', 'date', 'board', 'government', 'meeting', 'location', 'agenda_status', 'agenda_url', 'minutes_url'], rows);
  }});
  if (window.TT) run(); else addEventListener('DOMContentLoaded', run);
}})();
</script>'''
