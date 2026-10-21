"""How They Voted page for baycounty.me (data: data/votes/votes.json)."""
import json, os, html
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'data', 'votes', 'votes.json')
e = lambda s: html.escape(str(s if s is not None else ''))
CAT = {'budget': 'Budget', 'millage': 'Tax rate', 'contract': 'Contract', 'cra': 'CRA', 'land': 'Land', 'debt': 'Borrowing', 'other': 'Other'}


def votes_page(out_dir):
    d = json.load(open(SRC))
    bodies = {b['id']: b for b in d['bodies']}
    vs = sorted(d['votes'], key=lambda v: v.get('date') or '', reverse=True)
    cnt = Counter(v['body'] for v in vs)
    split = [v for v in vs if isinstance(v.get('by_member'), dict) and 'no' in v['by_member'].values()]
    # per-member tallies (only members with recorded roll calls)
    mem = defaultdict(lambda: Counter())
    for v in vs:
        for n, x in (v.get('by_member') or {}).items():
            mem[(v['body'], n)][x] += 1
    data = {'bodies': {k: {'n': b['name']} for k, b in bodies.items()}, 'cat': CAT,
            'votes': [{'b': v['body'], 'd': v.get('date'), 'c': v.get('category'), 'i': v.get('item'), 'a': v.get('amount'), 'o': v.get('outcome'), 't': v.get('tally'),
                       'm': v.get('by_member') or {}, 's': v.get('plain_summary'), 'u': v.get('source_url'), 'ut': v.get('source_title')} for v in vs]}
    js = open(os.path.join(HERE, 'votes.js')).read().replace('__VT__', json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    open(os.path.join(out_dir, 'assets', 'votes.js'), 'w').write(js)

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
        roster += f'''<details class="tbl-toggle"{" open" if cnt[k] else ""}><summary>{e(b["name"])} <span class="muted">· {cnt[k]} votes recorded</span></summary><div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Member</th><th scope="col">Seat</th><th scope="col">Term</th><th scope="col" class="num">Recorded votes</th><th scope="col" class="num">Voted no</th></tr></thead><tbody>{rows}</tbody></table></div>{f'<p class="note"><a class="src" href="{e(b["source_url"])}" target="_blank" rel="noopener">Roster source</a></p>' if b.get("source_url") else ""}</details>'''
    sp_html = ''.join(f'''<li class="fd"><div class="fd-hd"><b>{e(bodies.get(v["body"], {}).get("name", v["body"]))}</b> <span class="muted">{e(v.get("date"))} · {e(CAT.get(v.get("category"), v.get("category")))}{" · $" + format(v["amount"], ",.0f") if v.get("amount") else ""}</span> <span class="badge warn">{e(v.get("tally"))} {e(v.get("outcome"))}</span></div>
      <div class="fd-t">{e(v.get("plain_summary") or v.get("item"))}</div><p class="small"><b>No:</b> {e(", ".join(n for n, x in v["by_member"].items() if x == "no"))} · <b>Yes:</b> {e(", ".join(n for n, x in v["by_member"].items() if x == "yes"))}{" · <b>Absent:</b> " + e(", ".join(n for n, x in v["by_member"].items() if x == "absent")) if "absent" in v["by_member"].values() else ""}</p>
      <a class="src" href="{e(v.get("source_url"))}" target="_blank" rel="noopener">{e(v.get("source_title") or "Minutes")}</a></li>''' for v in split[:25])
    missing = [bodies[k]['name'] for k in bodies if not cnt[k] and not k.endswith('-cra')]
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Accountability · Votes</span><h1>How they voted</h1>
    <p class="lede">Budgets, tax rates, big contracts, land deals and borrowing are decided by recorded votes. Here's how each elected official voted on the money decisions since 2024, from official minutes.</p></div>
    <div class="stamp"><button type="button" class="pdf-btn" id="pdf"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>Minutes Jan 2024 to Oct 2026<br>Research compiled Oct 20, 2026</span></div></header>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>Reading the votes</h2>
    <ol class="ex-steps">
      <li><b>Most votes are unanimous.</b> Many items pass 5-0, often together on a "consent agenda" with no discussion. A unanimous vote still means every member approved it.</li>
      <li><b>Split votes show disagreement.</b> When the tally isn't unanimous, those are the decisions where members saw it differently. They're listed first below.</li>
      <li><b>Absent isn't a no.</b> Members who missed a meeting are shown as absent.</li>
    </ol></div></section>
  <div class="kpis">
    <div class="kpi"><span class="eyebrow">Votes recorded</span><span class="v">{len(vs)}</span><span class="s">Money decisions with a source</span></div>
    <div class="kpi"><span class="eyebrow">Split votes</span><span class="v">{len(split)}</span><span class="s">Not unanimous</span></div>
    <div class="kpi"><span class="eyebrow">Tax rate votes</span><span class="v">{sum(1 for v in vs if v.get("category") == "millage")}</span><span class="s">Millage adoptions</span></div>
    <div class="kpi"><span class="eyebrow">Boards covered so far</span><span class="v">{sum(1 for k in bodies if cnt[k])} of {len([k for k in bodies if not k.endswith("-cra")])}</span><span class="s">School Board still limited</span></div>
  </div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="split">Split votes</h2><span class="muted">Most recent first</span></div><ol class="findings">{sp_html}</ol></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="all">Every recorded vote</h2><span class="muted" id="vtCount"></span></div>
    <div class="filters-row"><input id="vtQ" type="search" placeholder="Search items or names" aria-label="Search votes">
      <select id="vtB" aria-label="Board"><option value="">All boards</option></select>
      <select id="vtC" aria-label="Type"><option value="">All types</option></select>
      <label class="chk"><input type="checkbox" id="vtS"> Split votes only</label></div>
    <ol class="findings" id="vtList"></ol><button type="button" class="pill" id="vtMore">Show more</button></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="who">Members and their records</h2><span class="muted">Counts cover only the votes recorded on this page</span></div>{roster}</section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">Coverage and gaps</h2></div>
    <p>{f"Not yet compiled: {e(', '.join(missing))}. Their minutes are being reviewed and will be added." if missing else ""} Votes come from official minutes; where minutes give only a tally, members are shown as "unknown". Minutes for Lynn Haven, Callaway, Panama City Beach, Mexico Beach, Parker and Springfield are mostly scanned and were read with text recognition, so check the linked minutes before relying on any single vote.</p>
    <ul class="plain">{''.join(f"<li>{e(n)}</li>" for n in (d.get("notes") or []))}</ul>
    {f'<details class="gaps"><summary>What we couldn\'t find ({len(d.get("gaps") or [])})</summary><ul>' + ''.join(f"<li>{e(g)}</li>" for g in d.get("gaps") or []) + '</ul></details>' if d.get("gaps") else ''}</section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/votes.js" defer></script>'''
