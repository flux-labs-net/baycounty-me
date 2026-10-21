"""Upcoming meetings (/meetings) and a subscribable calendar (/meetings.ics)."""
import html, json, os, re
from datetime import datetime, timedelta, timezone
from govs import GOVS, _load

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
    boards = {b['id']: b for b in md.get('boards', [])}
    open(os.path.join(out_dir, 'meetings.ics'), 'w', newline='').write(ics(md['meetings'], boards))
    up = sorted((m for m in md['meetings'] if not m.get('past') and m.get('start')), key=lambda m: m['start'])
    past = sorted((m for m in md['meetings'] if m.get('past')), key=lambda m: m.get('start') or '', reverse=True)

    def card(m):
        b = boards.get(m['board'], {})
        items = ''.join(f'<li>{e(x["title"][:220])}{"…" if len(x["title"]) > 220 else ""}{f" <b>{e(x["amount"])}</b>" if x.get("amount") else ""}</li>' for x in (m.get('items') or [])[:6])
        links = ' · '.join(x for x in [f'<a href="{e(m["agenda_url"])}" target="_blank" rel="noopener">Agenda</a>' if m.get('agenda_url') else '',
                                       f'<a href="{e(m["packet_url"])}" target="_blank" rel="noopener">Packet</a>' if m.get('packet_url') else '',
                                       f'<a href="{e(m["minutes_url"])}" target="_blank" rel="noopener">Minutes</a>' if m.get('minutes_url') else ''] if x)
        return f'''<li class="fd mt" data-g="{e(b.get("gov"))}"><div class="vt-top"><span class="vt-board">{e(b.get("name") or m["board"])}</span>{'<span class="badge">Expected</span>' if m.get("expected") else '<span class="badge ok">Agenda posted</span>' if m.get("agenda_url") and not m.get("past") else ''}</div>
          <div class="vt-h">{e(_when(m["start"]))}</div><p class="small">{e(m.get("title") or "")}{(" · " + e(m.get("location"))) if m.get("location") else ""}</p>
          {f'<details class="mt-items"><summary>{len(m["items"])} money item{"s" if len(m["items"]) != 1 else ""} on the agenda</summary><ul class="plain small">{items}</ul></details>' if m.get("items") else ""}
          {f'<p class="small">{links}</p>' if links else ('<p class="small muted">From the regular schedule; the agenda isn\'t posted yet.</p>' if m.get("expected") else '<p class="small muted">On the government\'s calendar; the agenda isn\'t posted yet.</p>' if not m.get("past") else '')}</li>'''
    sched = ''.join(f'<tr><th scope="row">{e(b["name"])}<small>{e(GN.get(b.get("gov"), ""))}</small></th><td class="small">{e(b.get("schedule"))}{(" · " + e(b.get("location"))) if b.get("location") else ""}</td><td class="small">{f"<a class=src href={json.dumps(b.get("calendar_url") or b.get("source_url"))} target=_blank rel=noopener>Calendar</a>" if (b.get("calendar_url") or b.get("source_url")) else ""}</td></tr>' for b in md.get('boards', []))
    opts = ''.join(f'<option value="{g["key"]}">{e(g["short"])}</option>' for g in GOVS if any(b.get('gov') == g['key'] for b in boards.values()))
    gen = md.get('generated', '')[:10]
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Get involved</span><h1>Upcoming public meetings</h1>
    <p class="lede">When and where every Bay County board meets, with agenda links and the money items on each agenda. Public comment is open at regular meetings; check the agenda for how to speak.</p></div>
    <div class="stamp"><a class="pill" href="/meetings.ics">Add to my calendar</a><span>Checked {e(gen)}</span></div></header>
  <div class="vt-filters mt-f"><label class="vf"><span>Government</span><select id="mtG" data-param="gov"><option value="">All governments</option>{opts}</select></label></div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="next">Coming up</h2><span class="muted" id="mtCount" aria-live="polite">{len(up)} meetings in the next 60 days</span></div>
    <ol class="findings" id="mtList">{"".join(card(m) for m in up) or '<li class="muted">No upcoming meetings found.</li>'}</ol></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="recent">Most recent meeting of each board</h2></div><ol class="findings" id="mtPast">{"".join(card(m) for m in past)}</ol></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="sched">Regular schedules</h2></div>
    <div class="tablewrap"><table class="tx-table mt-sched"><thead><tr><th scope="col">Board</th><th scope="col">When and where</th><th scope="col"></th></tr></thead><tbody>{sched}</tbody></table></div>
    <p class="note">"Expected" meetings are projected from a board's regular schedule because no agenda is posted yet. Boards cancel and move meetings, so confirm on the agenda before you go. The School Board's site couldn't be read by our tools; check bay.k12.fl.us. The calendar link works with Apple, Google and Outlook calendars.</p></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>
(() => {{
  const s = document.getElementById('mtG'), q = new URLSearchParams(location.search).get('gov');
  const run = () => {{ let n = 0; document.querySelectorAll('#mtList > li[data-g], #mtPast > li[data-g]').forEach(li => {{ const on = !s.value || li.dataset.g === s.value; li.hidden = !on; if (on && li.closest('#mtList')) n++; }}); document.getElementById('mtCount').textContent = n + ' meeting' + (n === 1 ? '' : 's') + ' in the next 60 days'; }};
  if (q && [...s.options].some(o => o.value === q)) s.value = q; s.addEventListener('input', run); s.addEventListener('change', run); run();
}})();
</script>'''
