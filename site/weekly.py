"""This week in Bay County: the weekly email's content, the /this-week page and the weekly-roundup dataset.

One edition per week, starting Monday (local time). Each edition lists:
  - events happening this week (community-events; one-off events first, repeating programs and meetings left out),
  - public meetings this week (meetings),
  - votes and contracts that reached BayCounty.me last week (votes, contracts, change-orders). Minutes come out weeks
    after a meeting, so "new" means first seen on the site last week (data/weekly/first_seen.json, written by
    data/weekly/track_new.py), not the meeting date.

The rows are the weekly-roundup dataset (database + /api/v1/datasets/weekly-roundup). The build also writes them to
/data/weekly.json, which the Monday email (api/weekly.js, weeklyEmail in api/_emails.js) reads, so the email, the
page and the API show the same edition.
"""
import datetime as dt
import html
import json
import math
import os
import sys
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
sys.path.insert(0, os.path.join(DATA, 'weekly'))
TZ = ZoneInfo('America/Chicago')
SITE = 'https://baycounty.me'
e = lambda s: html.escape(str(s if s is not None else ''))

# how many of each section the email and the page show up front (the rest are in the dataset and on the page)
FEATURED = {'event': 8, 'meeting': 10, 'vote': 6, 'contract': 6}
FRESH_DAYS = 60  # a record older than this is never "new", even if its key changed
WORTH = {'millage': 3, 'budget': 3, 'debt': 3, 'settlement': 3, 'fees': 2, 'contract': 2, 'land use': 2, 'ordinance': 2, 'grant': 2,
         'property': 2, 'policy': 1, 'resolution': 1, 'personnel': 0, 'other': 0, 'appointment': -1, 'procedural': -3, 'consent agenda': -3}


def week_of(today=None):
    today = today or dt.datetime.now(TZ).date()
    return today - dt.timedelta(days=today.weekday())


def _first_seen():
    try:
        return json.load(open(os.path.join(DATA, 'weekly', 'first_seen.json')))['first_seen']
    except FileNotFoundError:
        return {}


def _gov_names():
    from govs import GOVS
    return {g['key']: g['short'] for g in GOVS}


def _abs(u):
    return SITE + u if u and u.startswith('/') else u


def _person(name):
    import ids
    from entity_graph import page_url, build
    pid = ids.person_id(name) if name else None
    eid = 'person:' + pid if pid else None
    ok = eid and eid in build().ents
    return {'name': name, 'entity_id': eid if ok else None, 'url': _abs(page_url(eid)) if ok else None}


def _vendor(name):
    import ids
    from entity_graph import page_url, build
    vid = ids.vendor_id(name) if name else None
    eid = 'vendor:' + vid if vid else None
    if eid and eid in build().ents:
        return eid, _abs(page_url(eid))
    return None, None


def _events(start, end):
    from page_datasets import community_events
    rs = [r for r in community_events() if not r.get('same_as') and r.get('starts') and start.isoformat() <= r['starts'][:10] <= end.isoformat()
          and r.get('category') != 'Public meeting']
    rs.sort(key=lambda r: (bool(r.get('recurring')), r['category'] != 'Community', r['starts']))
    out = []
    for i, r in enumerate(rs):
        out.append(dict(section='event', rank=i + 1, record_id=r['event_id'], title=r['title'], summary=None, date=r['starts'][:10],
                        starts=r['starts'], ends=r.get('ends'), all_day=r.get('all_day'), gov_id=r.get('gov'), town=r.get('town'), venue=r.get('venue'),
                        category=r.get('category'), recurring=r.get('recurring'), url=r.get('url'), page_url=SITE + '/events', source=r.get('source'), source_url=r.get('source_url')))
    return out


def _meetings(start, end):
    from govs import _load
    md = _load().get('meetings') or {}
    boards = {b['id']: b for b in md.get('boards', [])}
    names = _gov_names()
    rs = []
    for m in md.get('meetings', []):
        s = m.get('start') or ''
        if not s or m.get('past') or not (start.isoformat() <= s[:10] <= end.isoformat()):
            continue
        b = boards.get(m.get('board')) or {}
        rs.append((s, m, b))
    rs.sort(key=lambda x: x[0])
    out = []
    for i, (s, m, b) in enumerate(rs):
        g = b.get('gov')
        out.append(dict(section='meeting', rank=i + 1, record_id=f'{m.get("board")}:{s}', title=f'{names.get(g, b.get("name") or "")}: {m.get("title") or "Meeting"}',
                        summary=None, date=s[:10], starts=s, gov_id=g, government=names.get(g), board=b.get('name'), venue=m.get('location'),
                        url=m.get('agenda_url') or m.get('detail_url'), agenda_posted=bool(m.get('agenda_url')), page_url=SITE + '/meetings', source_url=b.get('source_url')))
    return out


def _vote_score(r, consent):
    s = WORTH.get(r.get('category') or 'other', 0)
    if r.get('split'):
        s += 5
    if r.get('outcome') in ('failed', 'tabled'):
        s += 3
    if r.get('source_type') == 'researched':
        s += 3
    if consent:
        s -= 3
    if r.get('amount'):
        s += min(4, math.log10(max(r['amount'], 1)) - 3)
    return s


def _votes(seen, lo, hi):
    import opendata
    rows = opendata.add_vote_links('votes', opendata._votes())
    consent = {v['vote_id'] for v in (opendata._j('votes', 'minutes_votes.json') or {}).get('votes') or [] if v.get('consent')}
    names = _gov_names()
    fresh = (lo - dt.timedelta(days=FRESH_DAYS)).isoformat()
    picks = []
    for r in rows:
        k = 'vote:' + (r.get('vote_id') or '')
        f = seen.get(k)
        if not f or not (lo.isoformat() <= f <= hi.isoformat()) or (r.get('date') or '') < fresh:
            continue
        picks.append((_vote_score(r, r.get('vote_id') in consent), r, f))
    picks.sort(key=lambda x: x[1].get('date') or '', reverse=True)  # newest first among equal scores
    picks.sort(key=lambda x: -x[0])
    out = []
    for i, (sc, r, f) in enumerate(picks):
        no = [n for n in (r.get('voted_no') or '').split('; ') if n]
        out.append(dict(section='vote', rank=i + 1, record_id=r.get('vote_id'), title=r.get('headline') or r.get('agenda_item'), summary=r.get('summary'),
                        date=r.get('date'), gov_id=r.get('government'), government=names.get(r.get('government')), board=r.get('board'),
                        category=r.get('category'), amount=r.get('amount'), outcome=r.get('outcome'), tally=r.get('tally'), split=r.get('split'),
                        voted_no=r.get('voted_no') or None, people=[_person(n) for n in no] or None,
                        url=SITE + '/public-money/votes?q=' + __import__('urllib.parse').parse.quote((r.get('headline') or '')[:40]) + '#all',
                        page_url=SITE + '/public-money/votes', source_url=r.get('source_url'), first_seen=f))
    return out


def _contracts(seen, lo, hi):
    import opendata
    from track_new import record_key
    ct = opendata._j('contracts', 'contracts.json') or {}
    names = _gov_names()
    fresh = (lo - dt.timedelta(days=FRESH_DAYS)).isoformat()
    picks = []
    for kind, recs in (('contract', ct.get('contracts') or []), ('change_order', ct.get('change_orders') or [])):
        did = 'contracts' if kind == 'contract' else 'change-orders'
        keyed = [(record_key(kind, r), r) for r in recs]
        flat = opendata.add_gov_id(did, [dict(r) for _, r in keyed])  # gov_id (same order; nothing before 2016 here)
        gid = {k: f.get('gov_id') for (k, _), f in zip(keyed, flat)} if len(flat) == len(keyed) else {}
        for k, r in keyed:
            f = seen.get(k)
            if not f or not (lo.isoformat() <= f <= hi.isoformat()) or (r.get('date') or '') < fresh:
                continue
            picks.append((kind, k, r, f, gid.get(k)))
    amt = lambda x: (x[2].get('amount') if x[0] == 'contract' else x[2].get('change_amount')) or 0
    picks.sort(key=lambda x: -abs(amt(x)))
    out = []
    for i, (kind, k, r, f, g) in enumerate(picks):
        veid, vurl = _vendor(r.get('vendor'))
        import ids
        out.append(dict(section=kind, rank=i + 1, record_id=k, title=ids.biz_case(r.get('vendor') or '') or None,
                        summary=r.get('purpose') if kind == 'contract' else r.get('project'), date=r.get('date'), gov_id=g, government=names.get(g) or r.get('government'),
                        amount=amt((kind, k, r)), vendor=r.get('vendor'), vendor_entity_id=veid, vendor_url=vurl,
                        method=r.get('method') if kind == 'contract' else None, new_total=r.get('new_total') if kind == 'change_order' else None,
                        url=vurl or SITE + '/public-money/contracts', page_url=SITE + '/public-money/contracts', source_url=r.get('source_url'), first_seen=f))
    return out


COLS = ['place_id', 'week_of', 'section', 'rank', 'featured', 'record_id', 'title', 'summary', 'date', 'starts', 'ends', 'all_day',
        'gov_id', 'government', 'board', 'town', 'venue', 'category', 'recurring', 'agenda_posted', 'amount', 'new_total', 'method',
        'outcome', 'tally', 'split', 'voted_no', 'people', 'vendor', 'vendor_entity_id', 'vendor_url', 'url', 'page_url', 'source',
        'source_url', 'first_seen']


_cache = {}


def edition(today=None):
    """Every row of this week's edition (or the week holding `today`)."""
    from place import PLACE_ID
    wk = week_of(today)
    if wk in _cache:
        return _cache[wk]
    end, lo, hi = wk + dt.timedelta(days=6), wk - dt.timedelta(days=7), wk - dt.timedelta(days=1)
    seen = _first_seen()
    rows = _events(wk, end) + _meetings(wk, end) + _votes(seen, lo, hi) + _contracts(seen, lo, hi)
    out = []
    for r in rows:
        cap = FEATURED['contract' if r['section'] == 'change_order' else r['section']]
        r['featured'] = r['rank'] <= cap
        out.append({'place_id': PLACE_ID, 'week_of': wk.isoformat(), **{k: r.get(k) for k in COLS if k not in ('place_id', 'week_of')}})
    # contracts and change orders share one featured list, biggest first
    money = sorted([r for r in out if r['section'] in ('contract', 'change_order')], key=lambda r: -abs(r['amount'] or 0))
    for i, r in enumerate(money):
        r['featured'] = i < FEATURED['contract']
    _cache[wk] = out
    return out


def weekly_roundup():
    """Dataset rows (site/page_datasets.py DATASETS)."""
    return edition()


def write_json(out_dir):
    rows = edition()
    wk = week_of()
    os.makedirs(os.path.join(out_dir, 'data'), exist_ok=True)
    json.dump({'week_of': wk.isoformat(), 'week_ends': (wk + dt.timedelta(days=6)).isoformat(),
               'new_since': (wk - dt.timedelta(days=7)).isoformat(), 'generated': dt.datetime.now(TZ).isoformat(timespec='minutes'), 'rows': rows},
              open(os.path.join(out_dir, 'data', 'weekly.json'), 'w'), ensure_ascii=False, separators=(',', ':'))


# ---------- the /this-week page ----------

def _money(n):
    if n is None:
        return ''
    a = abs(n)
    s = f'${a / 1e6:,.1f} million' if a >= 1e6 else f'${a:,.0f}'
    return ('-' if n < 0 else '') + s


def _when(s, all_day=False):
    d = dt.datetime.fromisoformat(s)
    day = d.strftime('%a, %b %-d')
    if all_day or (d.hour == 0 and d.minute == 0 and len(s) <= 19):
        return day
    return day + ', ' + d.strftime('%-I:%M %p').replace(':00 ', ' ').replace('AM', 'a.m.').replace('PM', 'p.m.')


def _nice(d):
    return dt.date.fromisoformat(d[:10]).strftime('%b %-d') if d else ''


def _item(title, href, meta, text='', extra=''):
    t = f'<a href="{e(href)}">{e(title)}</a>' if href else e(title)
    return f'<li class="wk-item"><b>{t}</b>{f"<small>{meta}</small>" if meta else ""}{f"<p>{e(text)}</p>" if text else ""}{extra}</li>'


def _section(id_, title, sub, items, more_href, more_label, total):
    if not items:
        body = '<p class="muted">Nothing new this week.</p>'
    else:
        body = f'<ul class="wk-list">{"".join(items)}</ul>'
        if total > len(items):
            body += f'<p><a href="{more_href}">{more_label} ({total}) →</a></p>'
    return f'<section class="tx-sec" id="{id_}"><div class="sec-hd"><h2 data-tile="{e(title)}">{e(title)}</h2><span class="muted">{e(sub)}</span></div>{body}</section>'


def this_week_page(out_dir=None):
    from entity_links import a as ent, gov as gov_link
    from place import NAME
    if out_dir:
        write_json(out_dir)
    rows = edition()
    wk = week_of()
    end, lo = wk + dt.timedelta(days=6), wk - dt.timedelta(days=7)
    by = lambda s: [r for r in rows if r['section'] in s]
    feat = lambda s: [r for r in by(s) if r['featured']]
    ev = [_item(r['title'], r['url'], ' · '.join(e(x) for x in (_when(r['starts'], r['all_day']), r['venue'], r['town']) if x))
          for r in sorted(feat(('event',)), key=lambda r: r['starts'])]
    place = lambda v: v.split('; ')[-1] if v else v  # "Venue not stated...; City offices: ..." -> the address
    mt = [_item(r['title'], r['url'], ' · '.join(e(x) for x in (_when(r['starts']), place(r['venue'])) if x),
                extra='' if r['agenda_posted'] else '<span class="wk-pill">Agenda not posted yet</span>') for r in feat(('meeting',))]
    vt = []
    for r in by(('vote',)):  # the page lists every new vote and contract (the email links here for the rest)
        meta = ' · '.join(x for x in (gov_link(r['gov_id'], r['government']) if r['gov_id'] else e(r['board']), e(_nice(r['date'])),
                                       e(f'{(r["outcome"] or "").capitalize()} {r["tally"] or ""}'.strip())) if x)
        no = ''
        if r['people']:
            no = '<p class="wk-no">Voted no: ' + ', '.join(ent(p['entity_id'], p['name']) if p['entity_id'] else e(p['name']) for p in r['people']) + '</p>'
        vt.append(_item(r['title'], r['url'], meta, r['summary'] if r['summary'] != r['title'] else '', no))
    ct = []
    for r in sorted(by(('contract', 'change_order')), key=lambda r: -abs(r['amount'] or 0)):
        who = ent(r['vendor_entity_id'], r['title']) if r['vendor_entity_id'] else e(r['title'] or 'Vendor not named')
        kind = 'Change order' if r['section'] == 'change_order' else 'Contract'
        meta = ' · '.join(x for x in (e(f'{kind} {_money(r["amount"])}'), gov_link(r['gov_id'], r['government']) if r['gov_id'] else e(r['government']), e(_nice(r['date']))) if x)
        ct.append(f'<li class="wk-item"><b>{who}</b><small>{meta}</small>{f"<p>{e(r["summary"])}</p>" if r["summary"] else ""}'
                  f'{f"""<a class="wk-src" href="{e(r["source_url"])}" rel="noopener">Source</a>""" if r["source_url"] else ""}</li>')
    rng = f'{wk.strftime("%b %-d")} to {end.strftime("%b %-d")}'
    k = lambda t, v, c: f'<div class="kpi"><span class="eyebrow">{t}</span><span class="v">{v}</span><span class="s">{c}</span></div>'
    kpis = (k('Events', len(by(('event',))), 'Happening this week') + k('Public meetings', len(by(('meeting',))), 'This week') +
            k('New votes', len(by(('vote',))), f'Added {lo.strftime("%b %-d")} to {(wk - dt.timedelta(days=1)).strftime("%b %-d")}') +
            k('New contracts', len(by(('contract', 'change_order'))), 'Contracts and change orders added last week'))
    return f'''<div class="page tax wk" id="wkPage">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Weekly email · Week of {wk.strftime("%B %-d")}</span><h1>This week in {e(NAME)}</h1>
    <p class="lede">What's happening this week, the public meetings on the calendar, and the votes and contracts that reached BayCounty.me last week. The same list goes out by email every Monday.</p></div>
    <div class="stamp"><a class="pill" href="#signup">Get it by email →</a><span>{e(rng)}</span></div></header>
  <div class="kpis">{kpis}</div>
  {_section('events', 'Happening this week', 'One-off events first', ev, '/events', 'Every event this week', len(by(('event',))))}
  {_section('meetings', 'Public meetings', 'Agendas when posted', mt, '/meetings', 'All meetings', len(by(('meeting',))))}
  {_section('votes', 'New votes', 'Read from meeting minutes and records last week', vt, '/public-money/votes', 'All votes', len(by(('vote',))))}
  {_section('contracts', 'New contracts', 'Biggest first', ct, '/public-money/contracts', 'All contracts', len(by(('contract', 'change_order'))))}
  <section class="tx-sec" id="signup"><div class="sec-hd"><h2 data-tile="Sign up">Get it every Monday</h2></div>
    <p>One short email on Monday mornings. No email in a week with nothing in it. Every email has a one-click unsubscribe.</p>
    <div class="al-status" id="wkStatus" hidden></div>
    <form class="contact al-form" id="wkForm" novalidate>
      <label class="cf-f"><span>Email</span><input name="email" type="email" autocomplete="email" required maxlength="200" placeholder="you@example.com"></label>
      <label class="cf-hp" aria-hidden="true">Website <input name="website" type="text" tabindex="-1" autocomplete="off"></label>
      <div class="cf-go"><button type="submit">Sign up</button><p class="cf-msg" id="wkMsg" role="status" aria-live="polite"></p></div>
      <p class="cf-note">We'll email you a link to confirm first. Your address is used only for BayCounty.me emails, never shared or published. Want updates for one government instead? <a href="/alerts">Pick governments on the alerts page</a>.</p>
    </form></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">How this is put together</h2></div><ul class="plain">
    <li><b>Events</b> come from public calendars (<a href="/events">Events</a>). Repeating programs and public meetings are left out of this list.</li>
    <li><b>New votes and contracts</b> are the ones that first appeared on BayCounty.me last week. Minutes are often approved weeks after a meeting, so a vote can be from an earlier meeting.</li>
    <li>Votes are ranked to put split votes, failed motions, budgets, taxes and contracts first. Every vote is on <a href="/public-money/votes">How they voted</a>.</li>
    <li><b>Data:</b> <a href="/api/v1/datasets/weekly-roundup">weekly-roundup</a> (<a href="/downloads/weekly-roundup.csv">CSV</a>), rebuilt every morning.</li></ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<style>.wk-list{{list-style:none;padding:0;margin:0 0 12px}}.wk-item{{padding:12px 0;border-bottom:1px solid var(--line)}}.wk-item b{{display:block;font-weight:600}}.wk-item small{{display:block;color:var(--muted);margin-top:2px}}.wk-item p{{margin:6px 0 0;color:var(--muted)}}.wk-pill{{display:inline-block;margin-top:6px;font-size:.78rem;padding:2px 9px;border-radius:999px;background:var(--amber-bg,#FDF5E6);color:var(--amber,#9A6512)}}.wk-no{{font-size:.9rem}}.wk-src{{display:inline-block;margin-top:6px;font-size:.85rem}}</style>
<script>
(() => {{
  const f = document.getElementById('wkForm'), msg = document.getElementById('wkMsg'), btn = f.querySelector('button[type=submit]'), t0 = Date.now();
  const q = new URLSearchParams(location.search), st = document.getElementById('wkStatus');
  if (q.get('status') === 'confirmed') {{ st.hidden = false; st.className = 'al-status ok'; st.textContent = "You're signed up. The next email comes Monday morning."; }}
  fetch('/api/subscribe').then(r => r.json()).then(j => {{ if (!j.ready) {{ f.querySelectorAll('input,button').forEach(x => x.disabled = true); msg.textContent = 'Email sign-up is launching soon.'; }} }}).catch(() => {{}});
  f.addEventListener('submit', async ev => {{
    ev.preventDefault();
    if (!f.email.checkValidity() || !f.email.value) {{ msg.className = 'cf-msg err'; msg.textContent = 'Please enter a valid email address.'; f.email.focus(); return; }}
    btn.disabled = true; msg.className = 'cf-msg'; msg.textContent = 'Sending…';
    try {{
      const r = await fetch('/api/subscribe', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{email: f.email.value, govs: ['week'], website: f.website.value, t: t0}})}});
      const j = await r.json().catch(() => ({{}}));
      if (!r.ok || !j.ok) throw new Error(j.error || 'Sign-up failed. Please try again.');
      msg.className = 'cf-msg ok'; msg.textContent = 'Check your email for a link to confirm.'; f.email.value = '';
    }} catch (err) {{ msg.className = 'cf-msg err'; msg.textContent = err.message; }}
    btn.disabled = false;
  }});
}})();
</script>'''
