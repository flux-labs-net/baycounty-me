"""Debt and Audit Findings pages for baycounty.me (data: data/debt_audit/debt_audit.json)."""
import json, os, re, html
from city_filter import city_bar, data_g, by_city, gkey, KEYS, LABEL

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'data', 'debt_audit', 'debt_audit.json')

SHORT = [('Bay County', 'Bay County'), ('Bay District Schools', 'Bay District Schools'), ('City of Panama City Beach', 'Panama City Beach'),
         ('Panama City Beach Community', 'Panama City Beach CRA'), ('City of Panama City', 'Panama City'), ('Panama City Community Redevelopment', 'Panama City CRA'),
         ('Panama City Port', 'Port Panama City'), ('Panama City-Bay County Airport', 'Airport district'), ('City of Lynn Haven', 'Lynn Haven'),
         ('City of Callaway', 'Callaway'), ('City of Springfield', 'Springfield'), ('City of Parker', 'Parker'), ('City of Mexico Beach', 'Mexico Beach')]
TYPES = [('revenue_bonds', 'Revenue bonds'), ('general_obligation_bonds', 'Voter-approved (GO) bonds'), ('notes_loans', 'Notes and loans'),
         ('certificates_of_participation', 'Certificates of participation'), ('leases', 'Leases'), ('sbitas', 'Software subscriptions'), ('financed_purchases', 'Financed purchases')]


def finding_id(gov_short, a, f):
    return 'f-' + re.sub(r'[^a-z0-9]+', '-', f"{gov_short} {fy_label(a['fy'])} {f.get('id') or ''}".lower()).strip('-')


def short(g):
    for k, v in SHORT:
        if g.startswith(k):
            return v
    return g


def e(s):
    return html.escape(str(s if s is not None else ''))


def money(n, digits=1):
    if n is None:
        return '—'
    n = float(n)
    if abs(n) >= 1e6:
        return f'${n/1e6:,.{digits}f}M'
    if abs(n) >= 1e3:
        return f'${n/1e3:,.0f}K'
    return f'${n:,.0f}'


def fy_label(s):
    m = re.match(r'(FY\d{4})', s or '')
    return m.group(1) if m else (s or '')


def load():
    return json.load(open(SRC))


def _old_links():
    """Before the city bar reads ?gov=: older links used this page's short names ("Port Panama City"); turn them into keys."""
    m = {}
    for full, sh in SHORT:
        k = gkey(full) or gkey(sh)
        if k:
            m[sh] = k
    m['Port Panama City'] = 'pc'  # the port is a component unit of the City of Panama City
    js = json.dumps(m, separators=(',', ':'))
    return f'''<script>(() => {{ const m = {js}, u = new URL(location.href), g = u.searchParams.get('gov');
  if (g && m[g]) {{ u.searchParams.set('gov', m[g]); history.replaceState(history.state, '', u); }} }})();</script>'''


def _head(eyebrow, title, lede):
    return f'''<header class="tx-top"><div class="tx-brand"><span class="eyebrow">{eyebrow}</span><h1>{title}</h1><p class="lede">{lede}</p></div>
    <div class="stamp"><button type="button" class="pdf-btn" id="pdf"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>From audits filed with the Florida Auditor General<br>Data updated Oct 20, 2026</span></div></header>'''


def issues_section():
    import os, re
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'money', 'bonds.json')
    if not os.path.exists(fp):
        return ''
    b = json.load(open(fp))
    iss = b['issues']
    govs = sorted({i['gov'] for i in iss}, key=lambda g: -sum(x.get('outstanding') or 0 for x in iss if x['gov'] == g))
    TYPE = {'loan': 'Loan', 'note': 'Note', 'bond': 'Bond', 'certificates of participation': 'Certificates of participation'}
    rows = ''
    for g in govs:
        xs = sorted((x for x in iss if x['gov'] == g), key=lambda x: -(x.get('outstanding') or 0))
        rows += f'<tr class="grp"{data_g(g)}><th colspan="5" scope="colgroup">{e(g)} <span class="muted small">· {money(sum(x.get("outstanding") or 0 for x in xs))} outstanding</span></th></tr>'
        for x in xs:
            mat = re.sub(r'\s*\(.*', '', str(x.get('final_maturity') or '—'))
            retired = 'likely retired' in (x.get('status') or '') or 'has passed' in (x.get('status') or '')
            src = ' · '.join(f'<a class="src" href="{e(u)}" target="_blank" rel="noopener">Source {k + 1}</a>' for k, u in enumerate((x.get('sources') or [])[:3]))
            rows += f"""<tr{data_g(g)}><th scope="row"><b>{e(x.get('series'))}</b><small>{e(TYPE.get(x.get('type'), x.get('type') or ''))}{' · ' + e(x['placement']) if x.get('placement') else ''}{' · rated ' + e(x['rating']) if x.get('rating') else ''}</small></th>
              <td class="num">{money(x['par_amount']) if x.get('par_amount') else '—'}<small>{e((x.get('dated_date') or '')[:4])}</small></td>
              <td class="num">{money(x['outstanding']) if x.get('outstanding') is not None else '—'}<small>{e(x.get('outstanding_as_of') or '')}</small></td>
              <td class="small">{e(x.get('interest_rate') or '—')}<br>until {e(mat)}{'<br><span class="badge warn">May be paid off</span>' if retired else ''}</td>
              <td class="wrap small">{e(x.get('purpose') or '')}{'<br><span class="muted">Repaid from: ' + e(x['security']) + '</span>' if x.get('security') else ''}<br>{src}</td></tr>"""
    gaps = ''.join(f'<li>{e(g)}</li>' for g in b.get('gaps') or [])
    return f"""<section class="tx-sec"><div class="sec-hd"><h2 id="issues">Every bond, note and loan</h2><span class="muted">{len(iss)} issues · {money(sum(x.get('outstanding') or 0 for x in iss))} outstanding at the latest audit</span></div>
    <div class="tablewrap"><table data-tt-year="off" class="tx-table cm-table bond-table"><thead><tr><th scope="col">Issue</th><th scope="col" class="num">Borrowed</th><th scope="col" class="num">Still owed</th><th scope="col">Rate and term</th><th scope="col">What it paid for</th></tr></thead><tbody>{rows}</tbody></table></div>
    <p class="note">From each government's latest audit, with issue dates and terms from the resolutions and loan documents. Most local borrowing here is a private loan from a bank or the state, so there is no public bond document or rating. Issue totals differ from "Who owes what" above, which also counts leases, software subscriptions and bond premiums.</p>
    <details class="gaps"><summary>Gaps in the bond records ({len(b.get('gaps') or [])})</summary><ul>{gaps}</ul></details></section>"""


def debt_page():
    d = load()
    rows = [x for x in d['debt'] if x['total_debt']]
    rows.sort(key=lambda x: -x['total_debt'])
    tot = sum(x['total_debt'] for x in rows)
    mx = rows[0]['total_debt']

    def per(x):
        p = x.get('population_2025_estimate') or x.get('population')
        return x['total_debt'] / p if p and short(x['government']) not in ('Panama City CRA', 'Panama City Beach CRA', 'Airport district', 'Port Panama City') else None
    bars = ''.join(f'''<div class="hb"{data_g(x["government"])}><span class="hb-n">{e(short(x["government"]))} <em>{e(fy_label(x["fy"]))}</em></span><span class="hb-track"><span class="hb-bar" style="width:{max(.5, x["total_debt"]/mx*100):.1f}%"></span></span><span class="hb-v">{money(x["total_debt"])}{f" <em>${per(x):,.0f}/resident</em>" if per(x) else ""}</span></div>''' for x in rows)

    # by type table
    def bt(x, k):
        v = (x.get('by_type') or {}).get(k)
        return money(v) if v else '<span class="muted">—</span>'
    type_tbl = '<thead><tr><th scope="col">Government</th>' + ''.join(f'<th scope="col" class="num">{n}</th>' for _, n in TYPES) + '<th scope="col" class="num">Total</th></tr></thead><tbody>' + \
        ''.join(f'<tr{data_g(x["government"])}><th scope="row">{e(short(x["government"]))}</th>' + ''.join(f'<td class="num">{bt(x, k)}</td>' for k, _ in TYPES) + f'<td class="num"><b>{money(x["total_debt"])}</b></td></tr>' for x in rows) + '</tbody>'

    # payments this year + pensions
    pay_tbl = '<thead><tr><th scope="col">Government</th><th scope="col" class="num">Principal</th><th scope="col" class="num">Interest</th><th scope="col" class="num">Total this year</th><th scope="col" class="num">Net pension liability</th><th scope="col" class="num">Retiree health (OPEB)</th></tr></thead><tbody>' + \
        ''.join(f'''<tr{data_g(x["government"])}><th scope="row">{e(short(x["government"]))}</th><td class="num">{money((x.get("debt_service_year") or {}).get("principal"))}</td><td class="num">{money((x.get("debt_service_year") or {}).get("interest"))}</td><td class="num"><b>{money((x.get("debt_service_year") or {}).get("total"))}</b></td><td class="num">{money((x.get("pension_opeb") or {}).get("net_pension_liability"))}</td><td class="num">{money((x.get("pension_opeb") or {}).get("total_opeb_liability"))}</td></tr>''' for x in rows) + '</tbody>'

    # balloon payments
    balloons = []
    for x in rows:
        for i in x.get('issues', []):
            mat = str(i.get('final_maturity', ''))
            if re.search(r'single|one payment|balloon|entire principal', mat + ' ' + str(i.get('notes', '')), re.I) and (i.get('outstanding') or 0) >= 5e6:
                balloons.append((x, i))
    bl = ''.join(f'''<li{data_g(x["government"])}><b>{e(short(x["government"]))}: {money(i.get("outstanding"))}</b> due {e(i.get("final_maturity"))}. {e(i.get("name"))}{", " + e(i.get("interest_rate")) if i.get("interest_rate") else ""}. {e(i.get("purpose") or "")} <a href="{e(x["source_url"])}" target="_blank" rel="noopener">Audit</a></li>''' for x, i in balloons)

    # issue details per government
    det = ''
    for x in rows:
        iss = x.get('issues', [])
        if not iss:
            continue
        lis = ''.join(f'''<tr><td class="wrap"><b>{e(i.get("name"))}</b><br><span class="muted small">{e(i.get("purpose") or "Purpose not stated in the audit")}</span></td><td class="num">{e(i.get("year_issued") or "—")}</td><td class="num">{money(i.get("original_amount"))}</td><td class="num">{money(i.get("outstanding"))}</td><td class="num">{e(i.get("interest_rate") or "—")}</td><td class="small">{e(i.get("final_maturity") or "—")}</td><td class="wrap small">{e(i.get("repaid_by") or "—")}</td></tr>''' for i in iss)
        slug = re.sub(r'[^a-z0-9]+', '-', short(x['government']).lower()).strip('-')
        det += f'''<details class="tbl-toggle"{data_g(x["government"])}><summary>{e(short(x["government"]))}: {len(iss)} debts, {money(x["total_debt"])}</summary><p class="note">{e(x.get("total_debt_note", ""))} <a href="{e(x["source_url"])}" target="_blank" rel="noopener">Audit ({e(fy_label(x["fy"]))})</a></p>
        <div class="tablewrap"><table data-tt-year="off" class="tx-table"><thead><tr><th scope="col">Debt</th><th scope="col" class="num">Issued</th><th scope="col" class="num">Original</th><th scope="col" class="num">Owed</th><th scope="col" class="num">Rate</th><th scope="col">Final payment</th><th scope="col">Repaid from</th></tr></thead><tbody>{lis}</tbody></table></div></details>'''

    gk = [k for k in KEYS if any(gkey(x['government']) == k for x in rows)]

    def per(fn):  # a figure per city (rows are sorted by debt, so xs[0] is the largest)
        return by_city({'': fn(rows, None), **{k: fn([x for x in rows if gkey(x['government']) == k], k) for k in gk}})
    T = lambda tid, t: f'<span class="term" data-term="{tid}">{t}</span>'
    return f'''<div class="page tax">
  {_head('Public Money · Debt', 'What Bay County governments owe', "Local governments borrow to build things now and pay over time. Here's what each one owes, what for, and what it pays each year, from their audited financial statements.")}
  {city_bar(gk, hide=True, note='A city includes its CRA and port')}{_old_links()}
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>How local government borrowing works</h2>
    <ol class="ex-steps">
      <li><b>Borrow now, repay later.</b> A {T('bond', 'bond')} or loan pays for something big today, like a water plant or a building, and gets paid back with interest over years.</li>
      <li><b>Each debt names its money source.</b> Most local debt here is repaid from a specific stream (sales tax, utility bills, tourist tax) rather than from a property tax voters approved. That's why almost none of it is "general obligation" debt.</li>
      <li><b>Most of it is bank loans.</b> In Bay County, nearly all borrowing is placed directly with banks or the state, not sold to the public as bonds.</li>
      <li><b>Pensions are a separate promise.</b> Money owed to employees' future pensions and retiree health care is listed separately; it isn't borrowing, but it's still owed.</li>
    </ol></div></section>
  <div class="kpis">
    <div class="kpi"><span class="eyebrow"{per(lambda xs, k: 'Owed by all listed governments' if k is None else f'Owed by {LABEL[k]}' + (' and its agencies' if len(xs) > 1 else ''))}>Owed by all listed governments</span><span class="v"{per(lambda xs, k: money(sum(x["total_debt"] for x in xs)))}>{money(tot)}</span><span class="s">Bonds, notes, loans and leases</span></div>
    <div class="kpi"><span class="eyebrow">Largest borrower</span><span class="v"{per(lambda xs, k: e(short(xs[0]["government"])))}>{e(short(rows[0]["government"]))}</span><span class="s"{per(lambda xs, k: money(xs[0]["total_debt"]))}>{money(rows[0]["total_debt"])}</span></div>
    <div class="kpi"><span class="eyebrow">Voter-approved debt</span><span class="v">$0</span><span class="s">No general obligation bonds outstanding</span></div>
    <div class="kpi"><span class="eyebrow">Big single payments ahead</span><span class="v"{per(lambda xs, k: money(sum((i.get("outstanding") or 0) for x, i in balloons if x in xs)))}>{money(sum((i.get("outstanding") or 0) for _, i in balloons))}</span><span class="s"{per(lambda xs, k: (lambda n: f'{n} loan{"" if n == 1 else "s"} repaid in one lump sum')(sum(1 for x, _ in balloons if x in xs)))}>{len(balloons)} loans repaid in one lump sum</span></div>
  </div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="who">Who owes what</h2><span class="muted">Latest audited year; per resident where a population applies</span></div><div class="hbars">{bars}</div>
    <p class="note">Panama City Beach's figure includes $56.9M of Front Beach Road CRA bonds carried on the city's books. Port Panama City and the Panama City CRA are reported separately from the city.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="lump">Big single payments ahead</h2><span class="muted">Loans paid back all at once at the end, rather than a bit each year</span></div><ul class="plain" data-city-empty="No lump-sum loans for {{city}}.">{bl}</ul></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="types">What kind of debt</h2></div><div class="tablewrap"><table class="tx-table">{type_tbl}</table></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="pay">Payments this year, and pension promises</h2></div><div class="tablewrap"><table class="tx-table">{pay_tbl}</table></div>
    <p class="note">Lynn Haven reports a net pension <i>asset</i> of $4.4M (its plan holds more than it owes). Blank cells mean the audit didn't report that item for the government.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="each">Every debt, by government</h2></div>{det}</section>
  {issues_section()}
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">Sources and gaps</h2></div>{''.join(f"<p>{e(n)}</p>" for n in d["notes"])}
    <details class="gaps"><summary>What we couldn't find ({len(d["gaps"])})</summary><ul>{''.join(f"<li>{e(g)}</li>" for g in d["gaps"] if 'Lynn Haven federal' not in g)}</ul></details></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>
document.addEventListener('DOMContentLoaded', () => {{ // the city bar hides other governments' rows; open that government's debt tables
  BCM.city.on(k => document.querySelectorAll('main details.tbl-toggle[data-g]').forEach(el => {{ if (k && !el.hidden) el.open = true; }}));
}});
</script>'''


def audits_page():
    d = load()
    by = {}
    for a in d['audits']:
        by.setdefault(short(a['government']), []).append(a)
    order = ['Bay County', 'Bay District Schools', 'Panama City', 'Panama City Beach', 'Lynn Haven', 'Callaway', 'Springfield', 'Parker', 'Mexico Beach',
             'Panama City CRA', 'Panama City Beach CRA', 'Airport district', 'Port Panama City']
    score = ''
    for g in order:
        aa = sorted(by.get(g, []), key=lambda a: a['fy'], reverse=True)
        if not aa:
            continue
        a = aa[0]
        op = 'Qualified' if a['opinion'].lower().startswith('qualified') else 'Clean (unmodified)'
        nf = len(a['findings']); nr = sum(1 for f in a['findings'] if f.get('repeat'))
        firsts = [int(m) for f in a['findings'] for m in re.findall(r'first reported (\d{4})', f.get('title', '') + ' ' + f.get('plain', ''))]
        trend = ' → '.join(str(len(x['findings'])) for x in reversed(aa))
        score += f'''<tr{data_g(aa[0]["government"])}><th scope="row">{e(g)}</th><td>{e(fy_label(a["fy"]))}</td><td><span class="badge {"warn" if op == "Qualified" else "ok"}">{op}</span></td><td class="num">{nf}</td><td class="num">{nr}</td><td class="num">{min(firsts) if firsts else "—"}</td><td class="num muted">{trend}</td></tr>'''
    items = ''
    for g in order:
        for a in sorted(by.get(g, []), key=lambda a: a['fy'], reverse=True):
            for f in a['findings']:
                items += f'''<li class="fd" id="{finding_id(g, a, f)}"{data_g(a["government"])} data-n="{e(g)}" data-r="{1 if f.get("repeat") else 0}" data-y="{e(fy_label(a["fy"]))}" data-id="{e(f.get("id") or "")}" data-t="{e(re.sub(r"\s*\(first reported \d{4}\)", "", f.get("title", "")))}" data-u="{e(f.get("source_url") or a["source_url"])}"><div class="fd-hd"><b>{e(g)}</b> <span class="muted">{e(fy_label(a["fy"]))} · {e(f.get("id"))}</span>{' <span class="badge warn">Repeat</span>' if f.get("repeat") else ''}</div>
                  <div class="fd-t">{e(re.sub(r"\s*\(first reported \d{4}\)", "", f.get("title", "")))}</div><p>{e(f.get("plain"))}</p>{f'<p class="muted small"><b>Management response:</b> {e(f.get("mgmt_response"))}</p>' if f.get("mgmt_response") and "not extract" not in str(f.get("mgmt_response")).lower() else ""}<a class="src" href="{e(f.get("source_url") or a["source_url"])}" target="_blank" rel="noopener">Audit report</a></li>'''
    sr = ''
    for s in d['state_reports']:
        if 'indict' in s['type'].lower():
            continue
        fl = ''.join(f'<li><b>{e(f.get("id"))}.</b> {e(f.get("plain"))}</li>' for f in s.get('findings', []))
        sr += f'''<details class="tbl-toggle"{data_g(s["government"])}><summary>{e(s["government"])}: {e(s["type"])} ({e(s["report"])}, {e(s["date"])})</summary><ul class="plain">{fl}</ul><p><a class="src" href="{e(s.get("source_url", ""))}" target="_blank" rel="noopener">Read the report</a></p></details>'''
    gk = [k for k in KEYS if any(gkey(a['government']) == k for a in d['audits'])]
    T = lambda tid, t: f'<span class="term" data-term="{tid}">{t}</span>'
    return f'''<div class="page tax">
  {_head('Public Money · Audits', 'What the auditors found', "Every year outside accountants check each government's books. Here's what they flagged over the last three years, in plain English, and what the state's own auditors found.")}
  {city_bar(gk, hide=True, note='A city includes its CRA and port')}{_old_links()}
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>How to read an audit</h2>
    <ol class="ex-steps">
      <li><b>The opinion is the headline.</b> "Clean" (unmodified) means the numbers can be trusted overall. "Qualified" means the auditor couldn't sign off on part of them.</li>
      <li><b>Findings are the to-do list.</b> Even with a clean opinion, auditors list problems: weak controls, late reports, rules not followed.</li>
      <li><b>Repeat findings matter most.</b> A finding that shows up year after year means it wasn't fixed.</li>
      <li><b>No Bay County government was in a state "financial emergency"</b> in the years reviewed.</li>
    </ol><p class="muted">Each finding links to the {T('audit', 'audit report')} filed with the Florida Auditor General.</p></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="score">Scorecard</h2><span class="muted">Latest audit for each government</span></div>
    <div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Government</th><th scope="col">Year</th><th scope="col">Opinion</th><th scope="col" class="num">Findings</th><th scope="col" class="num">Repeats</th><th scope="col" class="num">Oldest unfixed since</th><th scope="col" class="num">Findings by year</th></tr></thead><tbody>{score}</tbody></table></div>
    <p class="note">"Findings by year" runs oldest to newest across the three audits reviewed.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="list">Every finding</h2><span class="muted" id="fdCount" aria-live="polite"></span></div>
    <div class="filters-row"><input id="fdQ" type="search" placeholder="Search findings" aria-label="Search findings">
      <select id="fdS" aria-label="Sort"><option value="new">Newest first</option><option value="az">Government A to Z</option></select>
      <label class="chk"><input type="checkbox" id="fdR" data-param="repeat"> Repeats only</label><button type="button" class="tt-csv" id="fdCsv">Download CSV</button></div>
    <ol class="findings" id="fdList" data-city-empty="No audit findings for {{city}}.">{items}</ol></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="state">State auditor reports</h2><span class="muted">Florida Auditor General reviews beyond the yearly audit</span></div><div data-city-empty="No state auditor reports for {{city}} in the years reviewed.">{sr}</div></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">Sources</h2></div><p>Annual audits and management letters filed with the <a href="https://flauditor.gov/" target="_blank" rel="noopener">Florida Auditor General</a>, plus the Auditor General's own reports. Findings are summarized in plain English; the auditor's finding number is kept so you can find it in the report.</p></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>(()=>{{const $=id=>document.getElementById(id),cg=()=>(window.BCM&&BCM.city?BCM.city.get():''),r=$('fdR'),q=$('fdQ'),so=$('fdS'),ol=$('fdList'),li=[...ol.querySelectorAll('.fd')],c=$('fdCount');
/* newest audit year first, then government A to Z, then finding number */
function f(){{const w=q.value.trim().toLowerCase().split(/\s+/).filter(Boolean);let n=0;li.forEach(x=>{{const t=x.textContent.toLowerCase();const k=cg(),s=(!k||!x.dataset.g||x.dataset.g.split(' ').includes(k))&&(!r.checked||x.dataset.r==='1')&&w.every(y=>t.includes(y));x.hidden=!s;if(s)n++;}});c.textContent=n+' finding'+(n===1?'':'s');
  const k=[{{get:x=>x.dataset.y,type:'date',dir:'desc'}},{{get:x=>x.dataset.n,type:'text',dir:'asc'}}];if(so.value==='az')k.reverse();k.push({{get:x=>x.dataset.id,type:'text',dir:'asc'}});
  if(window.TT)TT.sortBy(li,k).forEach(x=>ol.appendChild(x));}}
[r,q,so].forEach(x=>x.addEventListener('input',f));
$('fdCsv').addEventListener('click',()=>TT.csv('baycounty-audit-findings'+(cg()?'-'+TT.slug(BCM.city.label(cg())):''),['government','audit_year','finding','title','plain_english','repeat','source'],
  li.filter(x=>!x.hidden).sort((a,b)=>[...ol.children].indexOf(a)-[...ol.children].indexOf(b)).map(x=>[x.dataset.n,x.dataset.y,x.dataset.id,x.dataset.t,(x.querySelector('p')||{{}}).textContent||'',x.dataset.r==='1'?'yes':'no',x.dataset.u])));
const go=()=>{{f();BCM.city.on(f);const t=location.hash&&document.getElementById(decodeURIComponent(location.hash.slice(1)));if(t)t.scrollIntoView();}};
if(window.TT&&window.BCM)go();else addEventListener('DOMContentLoaded',go);}})();</script>'''
