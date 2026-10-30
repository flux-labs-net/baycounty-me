"""/data-sources: where every record on BayCounty.me comes from. Data: site/data_sources.py
(datasets data-sources and data-source-sites). The "What we've loaded so far" section is live: assets/progress.js
reads GET /api/v1/import-progress (api/_progress.js), the same numbers the /admin Import progress tab shows."""
import collections, html, os

HERE = os.path.dirname(os.path.abspath(__file__))

from data_sources import GOVS, TOPICS, AUTO_DAILY, AUTO_WEEKLY, AUTO_30, LIVE, BULK, rows, site_rows

AUTO = {AUTO_DAILY, AUTO_WEEKLY, AUTO_30}

CSS = '''
.ds-fresh td{vertical-align:top}.ds-fresh .sub{display:block;color:var(--muted);font-size:.8rem;margin-top:2px;line-height:1.35}
.ds-st{display:inline-block;padding:3px 9px;border-radius:999px;font-size:.78rem;font-weight:600;line-height:1.3;white-space:nowrap}
.ds-st-ok{background:var(--tint-teal);color:var(--teal)}.ds-st-so{background:var(--tint-blue);color:var(--blue)}
.ds-sent-n{margin:0 0 10px}.ds-st+.sub{display:block;font-size:.78rem;color:var(--muted);margin-top:3px}
.ds-st-wait{background:color-mix(in srgb,var(--muted) 14%,transparent);color:var(--muted)}.ds-st-hand{background:var(--tint-amber);color:var(--gold)}
@media (max-width:640px){.ds-st{white-space:normal}}
.ds-mx{border-collapse:separate;border-spacing:0;font-size:.84rem;min-width:860px;width:100%}
.ds-mx th,.ds-mx td{padding:8px 6px;border-bottom:1px solid var(--line);text-align:center;vertical-align:middle}
.ds-mx thead th{font-weight:600;font-size:.74rem;line-height:1.2;color:var(--muted);vertical-align:bottom}
.ds-mx tbody th{text-align:left;font-weight:500;white-space:nowrap;position:sticky;left:0;background:var(--surface);z-index:1;padding-right:12px}
.ds-mx tbody th a{color:var(--ink);text-decoration:none}.ds-mx tbody th a:hover{color:var(--blue);text-decoration:underline}
.ds-c{display:inline-flex;align-items:center;justify-content:center;min-width:26px;height:24px;padding:0 6px;border-radius:999px;font:600 .74rem/1 var(--f-data);text-decoration:none}
.ds-a{background:var(--tint-teal);color:var(--teal);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--teal) 35%,transparent)}
.ds-h{background:var(--tint-blue);color:var(--blue);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--blue) 30%,transparent)}
.ds-l{background:var(--tint-amber);color:var(--gold);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--amber) 45%,transparent)}
.ds-none{color:var(--faint)}
.ds-key{display:flex;flex-wrap:wrap;gap:8px 18px;font-size:.84rem;color:var(--muted)}
.ds-key span{display:inline-flex;align-items:center;gap:6px}
.ds-steps{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.ds-step{display:flex;flex-direction:column;gap:8px;padding:16px 18px;border-radius:14px;background:var(--surface);box-shadow:var(--ui-shadow);scroll-margin-top:90px}
.ds-step h3{margin:0;font-size:1rem}
.ds-step p{margin:0;font-size:.88rem}
.ds-step .ds-chk{color:var(--muted)}
.ds-step .ds-go{margin-top:auto;font-size:.84rem}
.ds-step:target{box-shadow:var(--ui-ring)}
.ds-rules{margin:0;padding-left:20px;display:flex;flex-direction:column;gap:6px}
.ds-src a{word-break:break-word}
@media (max-width:560px){.ds-steps{grid-template-columns:minmax(0,1fr)}}
'''


def _kind(method):
    return 'a' if method in AUTO else 'l' if method == LIVE else 'h'


def data_sources_page(out_dir=None):
    if out_dir:
        os.makedirs(os.path.join(out_dir, 'assets'), exist_ok=True)
        open(os.path.join(out_dir, 'assets', 'progress.js'), 'w').write(open(os.path.join(HERE, 'progress.js')).read())
    R = rows()
    W = site_rows()
    e = html.escape
    cells = collections.defaultdict(list)
    for r in R:
        cells[(r['topic_id'], r['government_id'])].append(r)
    n_auto = sum(1 for r in R if r['method'] in AUTO)
    n_bulk = sum(1 for r in R if r['method'] == BULK)
    sites = len({w['website'] for w in W})
    docs = sum(w['documents_cited'] for w in W)

    # matrix: topics down, governments across
    head = ''.join(f'<th scope="col">{e(name)}</th>' for _, name in GOVS)
    body = []
    for tid, label, *_ in TOPICS:
        tds = []
        for gid, gname in GOVS:
            c = cells.get((tid, gid), [])
            if not c:
                tds.append('<td><span class="ds-none" aria-label="none">·</span></td>')
                continue
            k = 'a' if any(r['method'] in AUTO for r in c) else 'l' if all(r['method'] == LIVE for r in c) else 'h'
            names = '; '.join(r['source_name'] for r in c)
            tds.append(f'<td><a class="ds-c ds-{k}" href="#t-{tid}" title="{e(names)}" aria-label="{len(c)} source{"s" if len(c) != 1 else ""} for {e(label)}, {e(gname)}: {e(names)}">{len(c)}</a></td>')
        body.append(f'<tr><th scope="row"><a href="#t-{tid}">{e(label)}</a></th>{"".join(tds)}</tr>')

    def link(r):
        name = e(r['source_name'])
        return f'<a href="{e(r["source_url"])}" target="_blank" rel="noopener">{name}</a>' if r['source_url'] else name

    src_rows = ''.join(
        f'<tr><td>{e(r["topic"])}</td><td>{e(r["government"])}</td><td class="ds-src">{link(r)}</td>'
        f'<td>{e(r["method"])}</td><td>{e(r["refresh"])}</td><td>{e(r["what_we_take"])}</td></tr>'
        for r in R)

    steps = ''.join(
        f'<article class="ds-step" id="t-{tid}"><h3>{e(label)}</h3><p>{e(how)}</p><p class="ds-chk"><b>Checks:</b> {e(checks)}</p>'
        f'<p class="ds-go">{len([r for r in R if r["topic_id"] == tid])} sources · <a href="{page}">See the page</a></p></article>'
        for tid, label, page, how, checks in TOPICS)

    from freshness import rows as fresh_rows, CHECKED_ON
    FR = fresh_rows()
    tag = {'Current': 'ok', 'Year so far': 'so', 'Newest published': 'wait', 'Newer data needs a by-hand download': 'hand'}
    fresh_tr = ''.join(
        f'<tr><td><a href="{e(r["page"])}">{e(r["figure"])}</a><span class="sub">{e(r["topic"])}</span></td><td>{e(r["latest_period"])}</td>'
        f'<td><span class="ds-st ds-st-{tag.get(r["status"], "wait")}">{e(r["status"])}</span></td><td>{e(r["next_due"])}'
        + (f'<span class="sub">{e(r["notes"])}</span>' if r['notes'] else '') + '</td></tr>'
        for r in FR)
    n_now = sum(1 for r in FR if r['status'] in ('Current', 'Year so far'))

    site_tr = ''.join(
        f'<tr><td><a href="{e(w["source_url"])}" target="_blank" rel="noopener">{e(w["website"])}</a></td><td>{e(w["topic"])}</td><td class="num">{w["documents_cited"]:,}</td></tr>'
        for w in W)

    return f'''<style>{CSS}</style>
<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">About</span><h1>Where our data comes from</h1>
    <p class="lede">Every figure on BayCounty.me comes from a public record. This page lists every source we take records from, for every government and every state and federal database, with the link, how we get it, how often, and what we do with it.</p></div></header>

  <section class="tx-sec"><div class="sec-hd"><h2 id="glance" data-tile="At a glance">At a glance</h2></div>
    <div class="kpis">
      <div class="kpi"><span class="eyebrow">Sources</span><span class="v">{len(R)}</span><span class="s">agenda systems, websites and databases</span></div>
      <div class="kpi"><span class="eyebrow">Automatic</span><span class="v">{n_auto}</span><span class="s">checked every 30 minutes, daily or weekly</span></div>
      <div class="kpi"><span class="eyebrow">State and federal files</span><span class="v">{n_bulk}</span><span class="s">bulk data downloads</span></div>
      <div class="kpi"><span class="eyebrow">Websites cited</span><span class="v">{sites}</span><span class="s">{docs:,} documents and pages linked</span></div>
    </div>
    <p>Data is still being loaded and checked, so some totals are not final and may change (<a href="#progress">see how far we’ve got</a>). Found something wrong or missing? <a href="/about#contact">Send a correction</a>.</p>
  </section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="current" data-tile="How current">How current each figure is</h2><span class="muted">{n_now} of {len(FR)} are this year or this year so far</span></div>
    <p>Many public numbers come out months or a year after the period they cover. This shows the newest period we have for each headline figure, and when the next one is usually published. Where a full 2026 figure isn't out yet, the page shows this year so far against the same months last year.</p>
    <div class="tablewrap"><table class="tx-table ds-fresh" data-tt="off"><thead><tr><th scope="col">Figure</th><th scope="col">Newest we have</th><th scope="col">Status</th><th scope="col">Next one</th></tr></thead><tbody>{fresh_tr}</tbody></table></div>
    <p class="note">The newest period is read from the data each time the site is built. The usual release schedules were checked on {CHECKED_ON}; agencies sometimes publish late. Data: <a href="/api/v1/datasets/data-freshness">data-freshness</a>.</p>
  </section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="sent" data-tile="Sent by governments">Sent by the governments</h2><span class="muted">Live</span></div>
    <p>Instead of waiting for us to find their records, each city and the county can send them to us straight from their own systems: the check register, the budget-vs-actual report and a list of contracts awarded. Their staff check a preview before anything is published, and payments to private people are listed without a name. This shows who sends what, and whether the latest is in.</p>
    <div data-records-sent="scorecard"><p class="muted">Loading…</p></div>
    <p class="note">Current means the latest period we expect is in: last month’s payments, last quarter’s budget report, and contracts sent in the last month. Data: <a href="/api/v1/records-sent">/api/v1/records-sent</a>, and the rows themselves in <a href="/api/v1/datasets/checkbook-payments">checkbook-payments</a>, <a href="/api/v1/datasets/budget-actuals">budget-actuals</a> and <a href="/api/v1/datasets/contracts">contracts</a>.</p>
  </section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="progress" data-tile="Loaded so far">What we’ve loaded so far</h2><span class="muted">Live: every vote in every board’s minutes since 2016</span></div>
    <p>We’re reading every set of meeting minutes each governing board has posted since 2016, so every vote and how each member voted can be searched. This tracks it as it runs: files found in each government’s archive, downloaded, read into motions and roll calls, and checked. The same numbers are in the API at <a href="/api/v1/import-progress">/api/v1/import-progress</a>.</p>
    <div data-import-progress><p class="muted">Loading progress…</p></div>
  </section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="rules" data-tile="Our rules">How we work</h2></div>
    <ul class="ds-rules">
      <li><b>Public records only.</b> Everything comes from documents anyone can download or request: agendas, minutes, budgets, audits, state databases and official map servers.</li>
      <li><b>A link on every figure.</b> Each record carries the link to the document it came from.</li>
      <li><b>Nothing made up.</b> Where we estimate (for example future CRA tax increment), the page says so and shows the method. Where a record is missing, we say it is missing.</li>
      <li><b>Checked against the source.</b> Totals are added back up and compared with the printed totals; matches between names are checked by hand before anything about a person is published.</li>
      <li><b>Privacy.</b> Individual campaign donors are only counted, unless they run a registered business. Pay names only elected officials and department leaders. Home addresses are never shown.</li>
      <li><b>Open.</b> Every dataset, including this list, can be downloaded on <a href="/open-data">Open data</a> or read through the <a href="/developers">API</a>.</li>
    </ul>
  </section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="matrix" data-tile="Matrix">Sources by government</h2><span class="muted">Number of sources; tap one for how we work it</span></div>
    <div class="ds-key"><span><span class="ds-c ds-a">1</span>Includes an automatic fetch</span><span><span class="ds-c ds-h">1</span>Downloaded and read by hand, or a bulk file</span><span><span class="ds-c ds-l">1</span>Live lookup</span></div>
    <div class="tablewrap"><table class="ds-mx" data-tt="off"><thead><tr><th scope="col"><span class="sr">Topic</span></th>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>
  </section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="sources" data-tile="Every source">Every source</h2><span class="muted">{len(R)} sources</span></div>
    <div class="tablewrap"><table class="tx-table" data-tt-sort="0:asc"><thead><tr><th scope="col">Topic</th><th scope="col">Government</th><th scope="col">Source</th><th scope="col">How we get it</th><th scope="col">How often</th><th scope="col">What we take</th></tr></thead><tbody>{src_rows}</tbody></table></div>
  </section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="process" data-tile="How we process">How we process each kind of record</h2></div>
    <div class="ds-steps">{steps}</div>
  </section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="sites" data-tile="Websites cited">Every website our records cite</h2><span class="muted">Counted from the data at each update</span></div>
    <p>The records behind the site link to {docs:,} distinct documents and pages on {sites} websites. This counts them by website and topic.</p>
    <div class="tablewrap"><table class="tx-table" data-tt-sort="2:desc"><thead><tr><th scope="col">Website</th><th scope="col">Topic</th><th scope="col" class="num">Documents linked</th></tr></thead><tbody>{site_tr}</tbody></table></div>
  </section>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="download">Download this list</h2></div>
    <p>Both tables are open data: <a href="/api/v1/datasets/data-sources">data-sources</a> and <a href="/api/v1/datasets/data-source-sites">data-source-sites</a> in the API, or as CSV on <a href="/open-data">Open data</a>.</p>
  </section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/progress.js" defer></script>
<script src="/assets/records-sent.js" defer></script>'''
