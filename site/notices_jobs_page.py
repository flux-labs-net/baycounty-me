"""Public notices (/notices) and government job openings (/jobs).

/notices: legal notices local governments publish on the county's public notice website (bids, public hearings,
meetings), from the public-notices dataset. /jobs: open jobs on every local government's own job board, from the
job-openings and job-boards datasets. Both are read daily by the refresh workflow (site/civic_data.py has the inputs).
"""
import datetime as dt
import html
import json

from entity_links import gov as gov_link

e = lambda s: html.escape(str(s if s is not None else ''))


def _govs():
    from place import governments
    return {g['key']: g.get('short') or g['name'] for g in governments()}


def _d(s):
    try:
        return dt.date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


def _short(d):
    return d.strftime('%b %-d, %Y') if d else ''


def _kpi(lab, v, s):
    return f'<div class="kpi"><span class="eyebrow">{lab}</span><span class="v">{v}</span><span class="s">{s}</span></div>'


def _gov_hrefs():
    from entity_links import href, build
    from place import governments
    return {g['key']: href('gov:' + g['key']) for g in governments() if 'gov:' + g['key'] in build().ents}


def _js_data(obj):
    return json.dumps(obj, separators=(',', ':')).replace('</', '<\\/')


CSS = r"""
.nj-ctl{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;margin-bottom:12px}
.nj-other{margin:0 0 4px;font-size:.92rem;color:var(--muted)}.nj-other b{color:var(--ink);font-weight:600}
.nj-ctl input[type=search],.nj-ctl select{min-height:44px;padding:0 12px;border-radius:12px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font:inherit;max-width:100%}
.nj-ctl input[type=search]{flex:1 1 240px}
.nj-list{display:flex;flex-direction:column;gap:10px}
.nj-item{display:flex;gap:14px;padding:14px 16px;border-radius:20px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.nj-item .ui-date{flex:none}
.nj-body{min-width:0;flex:1}
.nj-body h3{margin:0;font-size:.98rem;font-weight:600;text-wrap:pretty;overflow-wrap:anywhere}
.nj-body h3 a{color:inherit;text-decoration:none}
.nj-body h3 a:hover{color:var(--blue);text-decoration:underline}
.nj-meta{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:.82rem;color:var(--muted);margin-top:4px}
.nj-pill{font-size:.72rem;font-weight:600;padding:2px 9px;border-radius:999px;background:var(--sunken);color:var(--muted)}
.nj-pill.bid{background:color-mix(in srgb,var(--amber) 18%,transparent);color:var(--ink)}
.nj-pill.hearing{background:color-mix(in srgb,var(--salmon) 18%,transparent);color:var(--ink)}
.nj-pill.meeting{background:color-mix(in srgb,var(--teal) 16%,transparent);color:var(--ink)}
.nj-body details{margin-top:8px}
.nj-body details summary{cursor:pointer;font-size:.84rem;color:var(--blue)}
.nj-body details p{font-size:.86rem;line-height:1.5;white-space:pre-line;margin:8px 0 0;overflow-wrap:anywhere}
.nj-more{margin-top:10px}
.nj-more[hidden]{display:none}
.nj-boards{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.nj-board{padding:12px 14px;border-radius:18px;background:var(--surface);box-shadow:var(--ui-shadow);font-size:.88rem;min-width:0}
.nj-board b{display:block;font-weight:600}
.nj-board small{display:block;color:var(--muted);margin-top:2px}
.nj-tbl td,.nj-tbl th{vertical-align:top}
.nj-tbl td.n,.nj-tbl th.n{white-space:nowrap;font-variant-numeric:tabular-nums}
@media (max-width:760px){.nj-item{padding:12px 14px;gap:10px}}
"""

LIST_JS = r"""
(() => {
  const D = JSON.parse(document.getElementById('njData').textContent), C = window.NJ;
  const box = document.getElementById('njList'), more = document.getElementById('njMore'), cnt = document.getElementById('njCount');
  const qi = document.getElementById('njQ'), gs = document.getElementById('njGov'), chips = document.getElementById('njKind');
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  let kind = '', open = false; const N = 25;
  const p = new URLSearchParams(location.search);
  if (p.get('q')) qi.value = p.get('q'); if (p.get('gov')) gs.value = p.get('gov');
  // no government in the link: a signed-in reader starts on their home's (kept out of the link unless they change it)
  let homeG = '', homeNone = '';
  const homeStart = () => { const h = !p.has('gov') && window.BCHomeCity && window.BCHomeCity(); if (!h) return;
    if ([...gs.options].some(o => o.value === h.gov)) gs.value = homeG = h.gov; else homeNone = h.gov === 'county' ? 'Bay County' : h.name; };
  if (p.get('kind')) { kind = p.get('kind'); chips.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', b.dataset.v === kind)); }
  function show() {
    const q = qi.value.trim().toLowerCase(), g = gs.value;
    const fit = r => (!kind || C.kindOf(r) === kind) && (!q || C.text(r).toLowerCase().includes(q));
    let rows = D.rows.filter(r => (!g || r.g === g || (g === 'other' && !r.g)) && fit(r)), note = '';
    // a government with nothing that matches says so, then shows every government's
    if (!g && homeNone && !q && !kind) note = `<p class="nj-other"><b>None from ${esc(homeNone)} right now.</b> Here are the rest in Bay County:</p>`;
    if (g && !rows.length && D.rows.some(fit)) { note = `<p class="nj-other"><b>None from ${esc(gs.options[gs.selectedIndex].textContent)} right now.</b> Here are the rest in Bay County:</p>`; rows = D.rows.filter(fit); }
    box.innerHTML = note + (rows.slice(0, open ? rows.length : N).map(r => C.card(r, esc, D)).join('') || '<p class="muted">Nothing matches.</p>');
    more.hidden = open || rows.length <= N; more.textContent = `Show all ${rows.length}`;
    cnt.textContent = `${rows.length} ${rows.length === 1 ? C.one : C.many}`;
    const u = new URL(location.href); [['q', q], ['gov', g === homeG ? '' : g], ['kind', kind]].forEach(([k, v]) => v ? u.searchParams.set(k, v) : u.searchParams.delete(k)); history.replaceState(null, '', u);
  }
  qi.addEventListener('input', () => { open = false; show(); }); gs.addEventListener('change', () => { open = false; homeNone = ''; show(); });
  chips.addEventListener('click', ev => { const b = ev.target.closest('button'); if (!b) return; chips.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); kind = b.dataset.v; open = false; show(); });
  more.addEventListener('click', () => { open = true; show(); });
  // site.js (BC.longText) is deferred: draw once it has run
  const go = () => { homeStart(); show(); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', go); else go();
})();
"""

NOTICE_JS = r"""
window.NJ = {one: 'notice', many: 'notices', kindOf: r => r.k, text: r => [r.t, r.a, r.x, r.f && r.f.reference].join(' '),
  card(r, esc, D) {
    const d = new Date(r.p + 'T12:00:00'), mo = d.toLocaleString('en-US', {month: 'short'}).toUpperCase(), wd = d.toLocaleString('en-US', {weekday: 'short'});
    const ev = r.ev ? new Date(r.ev + 'T12:00:00').toLocaleDateString('en-US', {weekday: 'short', month: 'short', day: 'numeric', year: 'numeric'}) : '';
    const evLab = {bid: 'Due or opens', hearing: 'Hearing', meeting: 'Meets'}[r.k] || 'Date';
    const who = r.g && D.gh[r.g] ? `<a href="${esc(D.gh[r.g])}">${esc(r.a)}</a>` : esc(r.a || 'Other agency');
    return `<article class="nj-item"><span class="ui-date" aria-hidden="true"><span class="mo">${mo}</span><span class="d">${d.getDate()}</span><span class="wd">${wd}</span></span><div class="nj-body">
      <h3>${r.pdf ? `<a href="${esc(r.pdf)}" target="_blank" rel="noopener">${esc(r.t)}</a>` : esc(r.t)}</h3>
      <div class="nj-meta"><span class="nj-pill ${esc(r.k)}">${esc(D.kinds[r.k])}</span><span>${who}</span>${ev ? `<span>${evLab}: <b>${esc(ev)}</b></span>` : ''}<span>${r.fp && r.fp < r.p ? `First published ${esc(new Date(r.fp + 'T12:00:00').toLocaleDateString('en-US', {month: 'short', day: 'numeric'}))}, again ` : 'Published '}${esc(d.toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'}))}${r.np ? ' in ' + esc(r.np) : ''}</span></div>
      ${window.BC && BC.longText ? BC.longText(r.x, r.f) : `<details><summary>Read the notice</summary><p>${esc(r.x)}</p></details>`}</div></article>`;
  }};
"""

JOB_JS = r"""
window.NJ = {one: 'opening', many: 'openings', kindOf: r => r.ty, text: r => [r.t, r.e, r.dp, r.jt].join(' '),
  card(r, esc, D) {
    const who = r.g && D.gh[r.g] ? `<a href="${esc(D.gh[r.g])}">${esc(r.e)}</a>` : esc(r.e);
    const fmt = s => new Date(s + 'T12:00:00').toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'});
    const meta = [who, r.dp ? esc(r.dp) : '', r.jt ? esc(r.jt) : '', r.pay ? '<b>' + esc(r.pay) + '</b>' : '', r.po ? 'Posted ' + fmt(r.po) : '', r.cl ? 'Closes <b>' + fmt(r.cl) + '</b>' : 'Open until filled'].filter(Boolean).map(x => `<span>${x}</span>`).join('');
    return `<article class="nj-item"><div class="nj-body"><h3>${r.u ? `<a href="${esc(r.u)}" target="_blank" rel="noopener">${esc(r.t)}</a>` : esc(r.t)}</h3><div class="nj-meta">${meta}</div></div>
      ${r.u ? `<a class="ui-btn" href="${esc(r.u)}" target="_blank" rel="noopener" style="align-self:center;flex:none">Apply</a>` : ''}</article>`;
  }};
"""


def _gov_select(rows, govs, label):
    present = [k for k in govs if any(r['gov_id'] == k for r in rows)]
    other = any(not r['gov_id'] for r in rows)
    return (f'<label class="sr-only" for="njGov">{label}</label><select id="njGov"><option value="">Every government</option>'
            + ''.join(f'<option value="{k}">{e(govs[k])}</option>' for k in present)
            + ('<option value="other">Other public agencies</option>' if other else '') + '</select>')


def notices_page():
    from page_datasets import public_notices
    from civic_data import notices_info
    rows, info = public_notices(), notices_info()
    rows = [r for r in rows if not r.get('same_as')]  # a notice published on several days shows once (data/dupes.py)
    if not rows:
        return '<div class="page"><h1>Public notices</h1><p>No notices on file for this place yet.</p></div>'
    govs = _govs()
    today = dt.date.today().isoformat()
    kinds = {'bid': 'Bid or proposal', 'hearing': 'Public hearing', 'meeting': 'Meeting', 'other': 'Other notice'}
    data = {'gh': _gov_hrefs(), 'kinds': kinds, 'rows': [{'p': r['published'], 'g': r['gov_id'], 'a': r['agency'], 'k': r['kind'], 't': r['title'], 'ev': r['event_date'],
                                      'x': r['text'], 'pdf': r['pdf_url'], 'np': r['publication'], 'fp': r.get('first_posted'),
                                      'f': {k: r[k] for k in ('reference', 'emails', 'phones', 'links') if r.get(k)} or None} for r in rows]}
    open_bids = sum(1 for r in rows if r['kind'] == 'bid' and (r['event_date'] or '') >= today)
    hearings = sum(1 for r in rows if r['kind'] == 'hearing' and (r['event_date'] or '') >= today)
    n_gov = len({r['gov_id'] or r['agency'] for r in rows})
    first = min(r['published'] for r in rows)
    kpis = (_kpi('Notices on file', len(rows), f'Since {_short(_d(first))}') +
            _kpi('Bids still open', open_bids, 'Due date still ahead') +
            _kpi('Hearings ahead', hearings, 'Ordinances, zoning and site plans') +
            _kpi('Governments and agencies', n_gov, 'That posted a notice'))
    chips = ''.join(f'<button type="button" class="chip" data-v="{k}" aria-pressed="false">{v}</button>' for k, v in (('bid', 'Bids and proposals'), ('hearing', 'Public hearings'), ('meeting', 'Meetings')))
    return f'''<style>{CSS}</style>
<div class="page tax nj">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Take part · Public notices</span><h1>Public notices</h1>
    <p class="lede">Bids, public hearings and meetings that Bay County, the School Board, the cities and other public agencies are required to announce, in one searchable list. Each links to the government that posted it.</p></div>
    <div class="stamp"><a class="pill" href="/meetings">Meeting calendar →</a><span>Read {e(_short(_d(info.get("as_of") or today)))}</span></div></header>
  <div class="kpis">{kpis}</div>
  <section class="tx-sec" data-staff-posts="notice" hidden></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="notices" data-tile="Notices">Every notice, newest first</h2><span class="muted" id="njCount"></span></div>
    <div class="nj-ctl"><label class="sr-only" for="njQ">Search notices</label><input id="njQ" type="search" placeholder="Search: a road, a business, a word like rezoning">
      {_gov_select(rows, govs, "Government")}
      <div class="chips" id="njKind" role="group" aria-label="Kind of notice"><button type="button" class="chip" data-v="" aria-pressed="true">All</button>{chips}</div></div>
    <div class="nj-list" id="njList"></div>
    <div class="nj-more"><button type="button" class="ui-btn" id="njMore" hidden>Show all</button></div>
    <p class="note">The date shown with each notice is the first date it mentions after it was published: the meeting, the hearing or when bids are due. Check the notice itself before you go.</p></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>Notices</b> are read every day from <a href="{e(info.get("source_url"))}" target="_blank" rel="noopener">the county's public notice website</a>, where local governments publish legal notices under Florida law (s. 50.0311, F.S.). The site shows the last 30 days; notices already on file stay here as an archive.</li>
      <li><b>Left out:</b> court and private notices on the same site (foreclosures, tax deed applications, probate, notices to creditors, name changes), because they name private people and their homes.</li>
      <li><b>Government</b> is matched from the notice's opening words; a notice from an agency that isn't one of the county's local governments (the port, the college, a community development district) is listed under other public agencies.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/public-notices">public-notices</a> (<a href="/downloads/public-notices.csv">CSV</a>).</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script type="application/json" id="njData">{_js_data(data)}</script>
<script>{NOTICE_JS}{LIST_JS}</script>
<script src="/assets/area-map.js" defer></script>
<script src="/assets/staff-posts.js" defer></script>'''


def jobs_page():
    from page_datasets import job_openings, job_boards
    from civic_data import jobs_info
    rows, boards, info = job_openings(), job_boards(), jobs_info()
    rows = [r for r in rows if not r.get('same_as')]  # one opening posted twice shows once (data/dupes.py)
    if not boards:
        return '<div class="page"><h1>Government jobs</h1><p>No job boards on file for this place yet.</p></div>'
    govs = _govs()
    today = dt.date.today()
    week = (today - dt.timedelta(days=7)).isoformat()

    def ty(r):
        t = (r.get('job_type') or '').lower()
        return 'part' if 'part' in t or 'temporary' in t or 'seasonal' in t or 'substitut' in t else 'full' if 'full' in t else 'other'
    rows = sorted(rows, key=lambda r: (r.get('posted') or '0000', r['title']), reverse=True)
    data = {'gh': _gov_hrefs(), 'rows': [{'t': r['title'], 'e': r['employer'], 'g': r['gov_id'], 'dp': r['department'], 'jt': r['job_type'], 'ty': ty(r), 'pay': r['pay'],
                      'po': r['posted'], 'cl': r['closes'], 'u': r['url']} for r in rows]}
    new = sum(1 for r in rows if (r.get('posted') or r.get('first_seen') or '') >= week)
    closing = sum(1 for r in rows if r.get('closes') and r['closes'] <= (today + dt.timedelta(days=7)).isoformat())
    read = [b for b in boards if b['read']]
    board_cards = ''.join(
        f'<div class="nj-board"><b>{gov_link(b["gov_id"], b["employer"]) if b["gov_id"] else e(b["employer"])}</b>'
        f'<small>{(str(b["openings"]) + " open now") if b["read"] else e(b["note"] or "Not read automatically")}</small>'
        f'<small><a href="{e(b["url"])}" target="_blank" rel="noopener">{"All openings and how to apply" if b["read"] else "Its job page"}</a></small></div>' for b in boards)
    kpis = (_kpi('Open jobs', len(rows), f'At {len({r["employer"] for r in rows})} public employers') +
            _kpi('New this week', new, 'Posted in the last 7 days') +
            _kpi('Closing soon', closing, 'Closing date in the next 7 days') +
            _kpi('Job boards read', f'{len(read)} of {len(boards)}', 'The rest link to the employer'))
    chips = '<button type="button" class="chip" data-v="full" aria-pressed="false">Full time</button><button type="button" class="chip" data-v="part" aria-pressed="false">Part time, temporary or substitute</button>'
    return f'''<style>{CSS}</style>
<div class="page tax nj">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Take part · Jobs</span><h1>Government jobs</h1>
    <p class="lede">Open jobs at Bay County, Bay District Schools, the cities and the airport, from each employer's own job board, in one list. Apply on the employer's site.</p></div>
    <div class="stamp"><a class="pill" href="/notices">Public notices →</a><span>Read {e(_short(_d(info.get("as_of") or today.isoformat())))}</span></div></header>
  <div class="kpis">{kpis}</div>
  <section class="tx-sec" data-staff-posts="job" hidden></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="jobs" data-tile="Openings">Open jobs, newest first</h2><span class="muted" id="njCount"></span></div>
    <div class="nj-ctl"><label class="sr-only" for="njQ">Search jobs</label><input id="njQ" type="search" placeholder="Search: teacher, paramedic, mechanic, a department">
      {_gov_select(rows, govs, "Employer")}
      <div class="chips" id="njKind" role="group" aria-label="Job type"><button type="button" class="chip" data-v="" aria-pressed="true">All</button>{chips}</div></div>
    <div class="nj-list" id="njList"></div>
    <div class="nj-more"><button type="button" class="ui-btn" id="njMore" hidden>Show all</button></div>
    <p class="note">Pay is shown where the job board lists it. Jobs drop off once their closing date passes; "open until filled" jobs stay until the employer takes them down.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="boards" data-tile="Job boards">Each employer's job board</h2></div>
    <div class="nj-boards">{board_cards}</div></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>Openings</b> are read every day from each employer's public job board, the same list a job seeker sees: title, department, type, pay where listed, and posting and closing dates.</li>
      <li>Some boards can't be read automatically; they're listed above with a link to the employer's own page.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/job-openings">job-openings</a> (<a href="/downloads/job-openings.csv">CSV</a>) · <a href="/api/v1/datasets/job-boards">job-boards</a> (<a href="/downloads/job-boards.csv">CSV</a>).</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script type="application/json" id="njData">{_js_data(data)}</script>
<script>{JOB_JS}{LIST_JS}</script>
<script src="/assets/staff-posts.js" defer></script>'''
