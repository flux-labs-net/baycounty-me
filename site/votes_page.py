"""How They Voted page for baycounty.me (data: data/votes/votes.json)."""
import json, os, html, shutil
from collections import defaultdict, Counter
from city_filter import city_bar, data_g, by_city

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'data', 'votes', 'votes.json')
e = lambda s: html.escape(str(s if s is not None else ''))
from datetime import date as _date
import re as _re2


def board_name(n):
    return _re2.sub(r'\bCity City\b', 'City', n or '')


def nice(d):
    try:
        return _date.fromisoformat(d[:10]).strftime('%b %-d, %Y')
    except Exception:
        return d or ''


def tally(t):
    return _re2.sub(r'\s*\(.*?\)', '', t or '').strip()


def src_label(v):
    t = (v.get('source_title') or '').lower()
    kind = 'Minutes' if 'minute' in t else 'Agenda' if 'agenda' in t else 'Source'
    return f'{kind}, {nice(v.get("date"))}'


METHOD = [
    'Each vote comes from the official minutes posted by that government. A few recent votes whose minutes aren\'t posted yet come from the agenda packet or local news, and the source link says so.',
    'Panama City, Lynn Haven, Panama City Beach and Parker minutes list how each member voted. Callaway, Mexico Beach and Springfield minutes usually say "carried unanimously" and name only the no votes, so members present are shown as yes. A member shown as absent may also have abstained or stepped out.',
    'County Commission items on the consent agenda are approved together in one vote. The count shown is that vote.',
    'Many city minutes are scanned images read with text recognition, so a name or number can be misread. Every vote links to its minutes so you can check.',
    'The headline and summary for each vote are rewritten in plain English from the motion in the minutes, without adding anything the minutes don\'t say. The dollar amount is the largest figure in the motion.',
    'Lynn Haven: Judy Vandergrift served through May 2025 and Judy Tinder\'s recorded votes run through September 2026. Corey Langford now holds that seat. Mayor Jesse Nelson was followed by Dave Lowery in early 2026.',
]

GOVS = [('county', 'Bay County Commission', ('bay-',)), ('pc', 'Panama City', ('pc-',)), ('pcb', 'Panama City Beach', ('pcb-',)),
        ('lh', 'Lynn Haven', ('lh-',)), ('cw', 'Callaway', ('cw-',)), ('sp', 'Springfield', ('sp-',)), ('parker', 'Parker', ('parker-',)),
        ('mb', 'Mexico Beach', ('mb-',)), ('schools', 'School Board', ('bds-',))]


def gov_of(body):
    for k, _, pre in GOVS:
        if body.startswith(pre):
            return k
    return 'other'


ORDER = {'no': 0, 'yes': 1, 'abstain': 2, 'absent': 3, 'unknown': 4}
VL = {'yes': 'Yes', 'no': 'No', 'absent': 'Absent', 'abstain': 'Abstained', 'unknown': '?'}


def chips(bm):
    items = sorted((bm or {}).items(), key=lambda kv: ORDER.get(kv[1], 9))
    return ''.join(f'<span class="vchip v-{e(x)}">{e(n)} <b>{VL.get(x, e(x))}</b></span>' for n, x in items)


CAT = {'budget': 'Budget', 'millage': 'Tax rate', 'contract': 'Contract', 'cra': 'CRA', 'land': 'Land', 'debt': 'Borrowing', 'other': 'Other'}


def votes_page(out_dir):
    d = json.load(open(SRC))
    bodies = {b['id']: b for b in d['bodies']}
    vs = sorted(d['votes'], key=lambda v: v.get('date') or '', reverse=True)
    cnt = Counter(v['body'] for v in vs)
    import re as _re

    def is_split(v):
        if isinstance(v.get('by_member'), dict) and 'no' in v['by_member'].values():
            return True
        m = _re.search(r'(\d+)\s*(?:-|to)\s*(\d+)', v.get('tally') or '')
        return bool(m and int(m.group(2)) > 0)
    split = [v for v in vs if is_split(v)]
    # per-member tallies (only members with recorded roll calls)
    mem = defaultdict(lambda: Counter())
    for v in vs:
        for n, x in (v.get('by_member') or {}).items():
            mem[(v['body'], n)][x] += 1
    data = {'bodies': {k: {'n': board_name(b['name']), 'g': gov_of(k)} for k, b in bodies.items()}, 'cat': CAT,
            'govs': [[k, n] for k, n, _ in GOVS if any(gov_of(v['body']) == k for v in vs)],
            'votes': [{'b': v['body'], 'g': gov_of(v['body']), 'd': v.get('date'), 'dn': nice(v.get('date')), 'c': v.get('category'), 'i': v.get('item'), 'a': v.get('amount'), 'o': v.get('outcome'), 't': tally(v.get('tally')),
                       'm': v.get('by_member') or {}, 'x': is_split(v), 'h': v.get('headline') or v.get('item'), 's': v.get('summary') or v.get('plain_summary'),
                       'u': v.get('source_url'), 'ut': v.get('source_title'), 'ul': src_label(v)} for v in vs]}
    json.dump(data, open(os.path.join(out_dir, 'data', 'votes-page.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    shutil.copy(os.path.join(HERE, 'votes.js'), os.path.join(out_dir, 'assets', 'votes.js'))

    roster = ''
    for k, b in bodies.items():
        ms = [m for m in b.get('members', []) if isinstance(m, dict)]
        if not ms:
            continue
        rows = ''
        for m in ms:
            c = mem.get((k, m['name']), Counter())
            rec = sum(c.values())
            rows += f'<tr><th scope="row">{e(m["name"])}</th><td class="small">{e(m.get("seat"))}</td><td class="small">{e(m.get("term_end"))}</td><td class="num">{rec or "—"}</td><td class="num">{c["no"] or ("0" if rec else "—")}</td></tr>'
        roster += f'''<details class="tbl-toggle"{data_g(gov_of(k))}{" open" if cnt[k] else ""}><summary>{e(board_name(b["name"]))} <span class="muted">· {cnt[k]} votes recorded</span></summary><div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Member</th><th scope="col">Seat</th><th scope="col">Term</th><th scope="col" class="num">Recorded votes</th><th scope="col" class="num">Voted no</th></tr></thead><tbody>{rows}</tbody></table></div>{f'<p class="note"><a class="src" href="{e(b["source_url"])}" target="_blank" rel="noopener">Roster source</a></p>' if b.get("source_url") else ""}</details>'''
    def card(v):
        meta = ' · '.join(x for x in [nice(v.get('date')), CAT.get(v.get('category'), v.get('category') or ''), ('$' + format(v['amount'], ',.0f')) if v.get('amount') else ''] if x)
        return f'''<li class="fd vt"{data_g(gov_of(v["body"]))} data-d="{e(v.get("date") or "")}" data-n="{e(v.get("headline") or v.get("item") or "")}"><div class="vt-top"><span class="vt-board">{e(board_name(bodies.get(v["body"], {}).get("name", v["body"])))}</span><span class="badge warn">{e(tally(v.get("tally")))} {e((v.get("outcome") or "").capitalize())}</span></div>
      <span class="vt-meta muted">{e(meta)}</span>
      <div class="vt-h">{e(v.get("headline") or v.get("item"))}</div>
      <p class="vt-s">{e(v.get("summary") or v.get("plain_summary") or "")}</p>
      {f'<p class="votes-row">{chips(v.get("by_member"))}</p>' if v.get("by_member") else ""}
      <a class="src" href="{e(v.get("source_url"))}" target="_blank" rel="noopener" title="{e(v.get("source_title") or "")}">{e(src_label(v))}</a></li>'''
    # the 25 newest split votes, plus each government's own newest, so the list still has content for one city
    keep = {id(v) for v in split[:25]}
    for g in {gov_of(v['body']) for v in split}:
        keep |= {id(v) for v in [x for x in split if gov_of(x['body']) == g][:10]}
    sp_html = ''.join(card(v) for v in split if id(v) in keep)
    gk = [k for k, _, _ in GOVS if any(gov_of(v['body']) == k for v in vs)]
    def per(fn):
        return by_city({'': fn(vs, None), **{k: fn([v for v in vs if gov_of(v['body']) == k], k) for k in gk}})
    def boards(xs, k):
        bs = [b for b in bodies if not b.endswith('-cra') and (k is None or gov_of(b) == k)]
        return f'{sum(1 for b in bs if cnt[b] or cnt[b.split("-")[0] + "-cra"])} of {len(bs)}'
    missing = [board_name(bodies[k]['name']) for k in bodies if not cnt[k] and not k.endswith('-cra')]
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Accountability · Votes</span><h1>How they voted</h1>
    <p class="lede">Budgets, tax rates, big contracts, land deals and borrowing are decided by recorded votes. Here's how each elected official voted on the money decisions since 2024, from official minutes.</p></div>
    <div class="stamp"><button type="button" class="pdf-btn" id="pdf"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>Minutes Jan 2024 to Oct 2026<br>Data updated Oct 20, 2026</span></div></header>
  {city_bar(gk, legacy='g', hide=True)}
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>Reading the votes</h2>
    <ol class="ex-steps">
      <li><b>Most votes are unanimous.</b> Many items pass 5-0, often together on a "consent agenda" with no discussion. A unanimous vote still means every member approved it.</li>
      <li><b>Split votes show disagreement.</b> When the tally isn't unanimous, those are the decisions where members saw it differently. They're listed first below.</li>
      <li><b>Absent isn't a no.</b> Members who missed a meeting are shown as absent.</li>
    </ol></div></section>
  <div class="kpis">
    <div class="kpi"><span class="eyebrow">Votes recorded</span><span class="v"{per(lambda xs, k: len(xs))}>{len(vs)}</span><span class="s">Money decisions with a source</span></div>
    <div class="kpi"><span class="eyebrow">Split votes</span><span class="v"{per(lambda xs, k: sum(1 for v in xs if is_split(v)))}>{len(split)}</span><span class="s">Not unanimous</span></div>
    <div class="kpi"><span class="eyebrow">Tax rate votes</span><span class="v"{per(lambda xs, k: sum(1 for v in xs if v.get("category") == "millage"))}>{sum(1 for v in vs if v.get("category") == "millage")}</span><span class="s">Millage adoptions</span></div>
    <div class="kpi"><span class="eyebrow">Boards covered so far</span><span class="v"{per(boards)}>{boards(vs, None)}</span><span class="s">Every county, city and School Board</span></div>
  </div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="split">Split votes</h2><span class="muted">Most recent first</span></div><ol class="findings" data-tt-list data-city-empty="No split votes recorded for {{city}} yet." aria-label="Split votes">{sp_html}</ol></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="all">Every recorded vote</h2><span class="muted">Filter by government, member, year or outcome</span></div>
    <div class="vt-filters">
      <input id="vtQ" type="search" placeholder="Search votes, vendors or names" aria-label="Search votes" class="vf-q">
      <label class="vf" hidden><span>Government</span><select id="vtG" data-city-link><option value="">All governments</option></select></label>
      <label class="vf"><span>Member</span><select id="vtM"><option value="">Anyone</option></select></label>
      <label class="vf"><span>Type</span><select id="vtC"><option value="">All types</option></select></label>
      <label class="vf"><span>Year</span><select id="vtY"><option value="all">All years</option></select></label>
      <label class="vf"><span>Outcome</span><select id="vtO"><option value="">All votes</option><option value="split">Split votes</option><option value="unan">Unanimous</option><option value="failed">Failed motions</option></select></label>
      <label class="vf"><span>Sort</span><select id="vtSort"><option value="new">Newest first</option><option value="old">Oldest first</option><option value="amt">Largest amount</option><option value="close">Closest votes</option><option value="az">Item A to Z</option></select></label>
    </div>
    <div class="vt-status"><span id="vtCount" class="muted" aria-live="polite">Loading votes…</span><span id="vtMember" class="vt-memsum"></span><button type="button" class="linkbtn" id="vtClear" hidden>Clear filters</button><button type="button" class="tt-csv" id="vtCsv">Download CSV</button></div>
    <ol class="findings" id="vtList"></ol><button type="button" class="pill" id="vtMore">Show more</button></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="who">Members and their records</h2><span class="muted">Counts cover only the votes recorded on this page</span></div>{roster}</section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">Coverage and gaps</h2></div>
    <p>{f"Not yet compiled: {e(', '.join(missing))}. Their minutes are being reviewed and will be added." if missing else ""} Votes come from official minutes; where minutes give only a tally, members are shown as "unknown". Minutes for Lynn Haven, Callaway, Panama City Beach, Mexico Beach, Parker and Springfield are mostly scanned and were read with text recognition, so check the linked minutes before relying on any single vote.</p>
    <h3 class="m-h">How we read the minutes</h3>
    <ul class="plain">{''.join(f"<li>{x}</li>" for x in METHOD)}</ul>
    {f'<details class="gaps"><summary>What we couldn\'t find ({len(d.get("gaps") or [])})</summary><ul>' + ''.join(f"<li>{e(g)}</li>" for g in d.get("gaps") or []) + '</ul></details>' if d.get("gaps") else ''}</section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/votes.js" defer></script>'''
