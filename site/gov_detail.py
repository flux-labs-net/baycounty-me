"""The full debt, audit and savings records for one government, drawn on its page (/governments/<slug>).

These used to be separate dashboards (/public-money/debt, /public-money/audits, /public-money/savings). Each government's
page now carries its own rows, and /compare carries the side-by-side totals. A city's rows include its CRA and port;
Bay County's include the airport district, an independent countywide district with no page of its own.

Data: data/debt_audit/debt_audit.json, data/money/bonds.json and the Savings finder build (site/savings_page.py).
The datasets (debt, bonds, audit-findings, savings-opportunities, savings-evidence) are unchanged.
"""
import html, json, os, re
from functools import lru_cache
from city_filter import gkey

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
e = lambda s: html.escape(str(s if s is not None else ''))
TYPES = [('revenue_bonds', 'Revenue bonds'), ('general_obligation_bonds', 'Voter-approved (GO) bonds'), ('notes_loans', 'Notes and loans'),
         ('certificates_of_participation', 'Certificates of participation'), ('leases', 'Leases'), ('sbitas', 'Software subscriptions'),
         ('financed_purchases', 'Financed purchases')]


def money(n, d=1):
    if n is None:
        return '—'
    n = float(n)
    sign, a = ('−' if n < 0 else ''), abs(n)
    return sign + (f'${a/1e6:,.{d}f}M' if a >= 1e6 else f'${a/1e3:,.0f}K' if a >= 1e3 else f'${a:,.0f}')


def src(u, t='Source'):
    return f'<a class="src" href="{e(u)}" target="_blank" rel="noopener">{e(t)}</a>' if u else ''


@lru_cache(None)
def _da():
    return json.load(open(os.path.join(DATA, 'debt_audit', 'debt_audit.json')))


@lru_cache(None)
def _bonds():
    fp = os.path.join(DATA, 'money', 'bonds.json')
    return json.load(open(fp)) if os.path.exists(fp) else {'issues': [], 'gaps': []}


def mine(name, key):
    """True when a record's government belongs on this government's page."""
    k = gkey(name)
    return k == key or (k is None and key == 'county')


def short(name):
    from debt_audit_page import short as s
    return s(name)


# ---------------- debt ----------------
def debt_detail(key):
    """Everything below the headline in a government's Debt section: what kind, payments this year and pension promises,
    loans repaid in one lump sum, every debt from the audit, and every bond, note and loan issue."""
    from debt_audit_page import fy_label
    rows = [x for x in _da()['debt'] if mine(x['government'], key) and x.get('total_debt')]
    if not rows:
        return ''
    out = []
    many = len(rows) > 1

    def bt(x, k):
        v = (x.get('by_type') or {}).get(k)
        return money(v) if v else '<span class="muted">—</span>'
    cols = [(k, n) for k, n in TYPES if any((x.get('by_type') or {}).get(k) for x in rows)]
    if cols:
        out.append('<h3 class="h4">What kind of debt</h3><div class="tablewrap"><table class="tx-table" data-tt="off"><thead><tr><th scope="col">Owed by</th>'
                   + ''.join(f'<th scope="col" class="num">{n}</th>' for _, n in cols) + '<th scope="col" class="num">Total</th></tr></thead><tbody>'
                   + ''.join(f'<tr><th scope="row">{e(short(x["government"]))} <span class="muted small">{e(fy_label(x["fy"]))}</span></th>'
                             + ''.join(f'<td class="num">{bt(x, k)}</td>' for k, _ in cols) + f'<td class="num"><b>{money(x["total_debt"])}</b></td></tr>' for x in rows)
                   + '</tbody></table></div>')
    pay = [x for x in rows if (x.get('debt_service_year') or {}).get('total') or (x.get('pension_opeb') or {}).get('net_pension_liability') is not None
           or (x.get('pension_opeb') or {}).get('total_opeb_liability')]
    if pay:
        out.append('<h3 class="h4">Payments this year, and pension promises</h3><div class="tablewrap"><table class="tx-table" data-tt="off"><thead><tr>'
                   + ('<th scope="col">Owed by</th>' if many else '<th scope="col">Year</th>')
                   + '<th scope="col" class="num">Principal</th><th scope="col" class="num">Interest</th><th scope="col" class="num">Total this year</th>'
                   '<th scope="col" class="num">Net pension liability</th><th scope="col" class="num">Retiree health (OPEB)</th></tr></thead><tbody>'
                   + ''.join(f'''<tr><th scope="row">{e(short(x["government"]) if many else fy_label(x["fy"]))}</th><td class="num">{money((x.get("debt_service_year") or {}).get("principal"))}</td>
                     <td class="num">{money((x.get("debt_service_year") or {}).get("interest"))}</td><td class="num"><b>{money((x.get("debt_service_year") or {}).get("total"))}</b></td>
                     <td class="num">{money((x.get("pension_opeb") or {}).get("net_pension_liability"))}</td><td class="num">{money((x.get("pension_opeb") or {}).get("total_opeb_liability"))}</td></tr>''' for x in pay)
                   + '</tbody></table></div><p class="note small">A negative pension figure is a net pension <i>asset</i>: the plan holds more than it owes. A dash means the audit didn\'t report that item.</p>')
    balloons = [(x, i) for x in rows for i in x.get('issues', [])
                if re.search(r'single|one payment|balloon|entire principal', f"{i.get('final_maturity', '')} {i.get('notes', '')}", re.I) and (i.get('outstanding') or 0) >= 5e6]
    if balloons:
        out.append('<h3 class="h4">Big single payments ahead</h3><p class="small muted">Loans paid back all at once at the end, rather than a bit each year.</p><ul class="plain">'
                   + ''.join(f'<li><b>{money(i.get("outstanding"))}</b> due {e(i.get("final_maturity"))}{" (" + e(short(x["government"])) + ")" if many else ""}. {e(i.get("name"))}'
                             f'{", " + e(i.get("interest_rate")) if i.get("interest_rate") else ""}. {e(i.get("purpose") or "")} {src(x.get("source_url"), "Audit")}</li>' for x, i in balloons)
                   + '</ul>')
    det = ''
    for x in rows:
        iss = x.get('issues', [])
        if not iss:
            continue
        lis = ''.join(f'''<tr><td class="wrap"><b>{e(i.get("name"))}</b><br><span class="muted small">{e(i.get("purpose") or "Purpose not stated in the audit")}</span></td><td class="num">{e(i.get("year_issued") or "—")}</td>
          <td class="num">{money(i.get("original_amount"))}</td><td class="num">{money(i.get("outstanding"))}</td><td class="num">{e(i.get("interest_rate") or "—")}</td>
          <td class="small">{e(i.get("final_maturity") or "—")}</td><td class="wrap small">{e(i.get("repaid_by") or "—")}</td></tr>''' for i in iss)
        det += (f'<details class="tbl-toggle"><summary>{e(short(x["government"]))}: {len(iss)} debt{"s" if len(iss) != 1 else ""}, {money(x["total_debt"])}</summary>'
                f'<p class="note">{e(x.get("total_debt_note", ""))} {src(x.get("source_url"), "Audit (" + fy_label(x["fy"]) + ")")}</p>'
                '<div class="tablewrap"><table data-tt-year="off" class="tx-table"><thead><tr><th scope="col">Debt</th><th scope="col" class="num">Issued</th><th scope="col" class="num">Original</th>'
                f'<th scope="col" class="num">Owed</th><th scope="col" class="num">Rate</th><th scope="col">Final payment</th><th scope="col">Repaid from</th></tr></thead><tbody>{lis}</tbody></table></div></details>')
    if det:
        out.append(f'<h3 class="h4">Every debt in the audit</h3>{det}')
    issues = _issues(key)
    if issues:
        out.append(issues)
    return ''.join(out)


def _issues(key):
    b = _bonds()
    iss = sorted((x for x in b['issues'] if mine(x['gov'], key)), key=lambda x: -(x.get('outstanding') or 0))
    if not iss:
        return ''
    TYPE = {'loan': 'Loan', 'note': 'Note', 'bond': 'Bond', 'certificates of participation': 'Certificates of participation'}
    rows = ''
    for x in iss:
        mat = re.sub(r'\s*\(.*', '', str(x.get('final_maturity') or '—'))
        retired = 'likely retired' in (x.get('status') or '') or 'has passed' in (x.get('status') or '')
        s = ' · '.join(src(u, f'Source {k + 1}') for k, u in enumerate((x.get('sources') or [])[:3]))
        rows += f"""<tr><th scope="row"><b>{e(x.get('series'))}</b><small>{e(TYPE.get(x.get('type'), x.get('type') or ''))}{' · ' + e(x['placement']) if x.get('placement') else ''}{' · rated ' + e(x['rating']) if x.get('rating') else ''}{' · ' + e(short(x['gov'])) if gkey(x['gov']) != key else ''}</small></th>
          <td class="num">{money(x['par_amount']) if x.get('par_amount') else '—'}<small>{e((x.get('dated_date') or '')[:4])}</small></td>
          <td class="num">{money(x['outstanding']) if x.get('outstanding') is not None else '—'}<small>{e(x.get('outstanding_as_of') or '')}</small></td>
          <td class="small">{e(x.get('interest_rate') or '—')}<br>until {e(mat)}{'<br><span class="badge warn">May be paid off</span>' if retired else ''}</td>
          <td class="wrap small">{e(x.get('purpose') or '')}{'<br><span class="muted">Repaid from: ' + e(x['security']) + '</span>' if x.get('security') else ''}<br>{s}</td></tr>"""
    return (f'<details class="tbl-toggle"><summary>Every bond, note and loan issue ({len(iss)}, {money(sum(x.get("outstanding") or 0 for x in iss))} still owed)</summary>'
            '<div class="tablewrap"><table data-tt-year="off" class="tx-table cm-table bond-table"><thead><tr><th scope="col">Issue</th><th scope="col" class="num">Borrowed</th>'
            f'<th scope="col" class="num">Still owed</th><th scope="col">Rate and term</th><th scope="col">What it paid for</th></tr></thead><tbody>{rows}</tbody></table></div>'
            '<p class="note">Issue dates and terms come from the resolutions and loan documents. Most local borrowing here is a private loan from a bank or the state, so there is no public bond document or rating. '
            'Issue totals differ from the audited total above, which also counts leases, software subscriptions and bond premiums.</p></details>')


# ---------------- audits ----------------
def _fy(s):
    """'FY2024 (year ended 2024-09-30)' -> 2024."""
    m = re.search(r'FY\s*(\d{4})', str(s or ''))
    return int(m.group(1)) if m else None


def _iso(d):
    """A state report's date as YYYY-MM-DD (or YYYY-MM, YYYY) for gov.js to place it in a fiscal year."""
    from datetime import datetime
    for f in ('%Y-%m-%d', '%B %d, %Y', '%b %d, %Y', '%B %Y', '%b %Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(str(d).strip(), f).strftime('%Y-%m-%d' if '%d' in f else '%Y-%m')
        except ValueError:
            pass
    m = re.search(r'(19|20)\d\d', str(d or ''))
    return m.group(0) if m else ''


def audit_section(key):
    """Every audit on file for this government (and its CRA, port or district): the opinion each year and every finding,
    newest first, plus the state Auditor General's own reports. Each finding keeps its id, so search results link to it."""
    from debt_audit_page import fy_label, finding_id
    aud = sorted((a for a in _da()['audits'] if mine(a['government'], key)), key=lambda a: (gkey(a['government']) != key, a['government'], a['fy']), reverse=False)
    if not aud:
        return ''
    by = {}
    for a in aud:
        by.setdefault(a['government'], []).append(a)
    main = [g for g in by if gkey(g) == key][:1] or list(by)[:1]
    parts, n_all, n_rep = [], 0, 0
    for g in main + [g for g in by if g not in main]:
        aa = sorted(by[g], key=lambda a: a['fy'], reverse=True)
        nm = short(g)
        trend = ' → '.join(str(len(x['findings'])) for x in reversed(aa))
        items = ''
        for a in aa:
            op = 'Qualified' if a['opinion'].lower().startswith('qualified') else 'Clean'
            items += f'<li class="au-yr" data-au-fy="{_fy(a["fy"]) or ""}"><div class="fd-hd"><b>{e(fy_label(a["fy"]))}</b> <span class="badge {"warn" if op == "Qualified" else "ok"}">{op} opinion</span> <span class="muted small">{len(a["findings"])} finding{"s" if len(a["findings"]) != 1 else ""}</span> {src(a.get("source_url"), "Audit report")}</div>'
            if a['findings']:
                items += '<ol class="findings">' + ''.join(
                    f'''<li class="fd" id="{finding_id(nm, a, f)}"><div class="fd-hd"><b>{e(re.sub(r"\s*\(first reported \d{4}\)", "", f.get("title", "")))}</b> <span class="muted small">{e(f.get("id") or "")}</span>{' <span class="badge warn">Repeat</span>' if f.get("repeat") else ''}</div>
                    <p class="small">{e(f.get("plain") or "")}</p>{f'<p class="muted small"><b>Management response:</b> {e(f.get("mgmt_response"))}</p>' if f.get("mgmt_response") and "not extract" not in str(f.get("mgmt_response")).lower() else ""}
                    {src(f.get("source_url") or a.get("source_url"), "Audit report") if f.get("source_url") and f.get("source_url") != a.get("source_url") else ""}</li>''' for f in a['findings']) + '</ol>'
            items += '</li>'
            n_all += len(a['findings']); n_rep += sum(1 for f in a['findings'] if f.get('repeat'))
        open_ = g in main
        parts.append(f'<details class="tbl-toggle au-gov"{" open" if open_ else ""}><summary>{e(nm)} <span class="muted small">· findings by year, oldest to newest: {e(trend)}</span></summary><ul class="plain au-list">{items}</ul></details>')
    sr = ''
    for s in _da()['state_reports']:
        if 'indict' in s['type'].lower() or not mine(s['government'], key):
            continue
        fl = ''.join(f'<li><b>{e(f.get("id"))}.</b> {e(f.get("plain"))}</li>' for f in s.get('findings', []))
        sr += f'<details class="tbl-toggle" data-date="{e(_iso(s.get("date")))}"><summary>{e(s["type"])} ({e(s["report"])}, {e(s["date"])})</summary><ul class="plain">{fl}</ul><p>{src(s.get("source_url"), "Read the report")}</p></details>'
    latest = sorted(by[main[0]], key=lambda a: a['fy'], reverse=True)[0]
    sub = f'{len(latest["findings"])} finding{"s" if len(latest["findings"]) != 1 else ""} in {fy_label(latest["fy"])} · {n_all} across {len(aud)} audit{"s" if len(aud) != 1 else ""}'
    return f'''<section class="tx-sec"><div class="sec-hd"><h2 id="audits">What the auditors found</h2><span class="muted" data-au-sub>{e(sub)}</span></div>
      <p class="gx-yr" data-au-yr hidden></p>
      <p class="small muted">Every year outside accountants check the books. "Clean" means the numbers can be trusted overall; "qualified" means the auditor couldn't sign off on part of them. Findings are the to-do list, and a repeat finding means it wasn't fixed.</p>
      {"".join(parts)}
      {f'<h3 class="h4">State auditor reports</h3><p class="small muted">Florida Auditor General reviews beyond the yearly audit.</p>{sr}' if sr else ''}
      <p class="src-line">Audits and management letters filed with the <a href="https://flauditor.gov/" target="_blank" rel="noopener">Florida Auditor General</a> · <a href="/compare">Compare audit findings across governments</a></p></section>'''


# ---------------- savings ----------------
@lru_cache(None)
def _savings():
    from savings_page import build
    return build()


def savings_section(key):
    """Places this government could spend less: the Savings finder's cards for this government, drawn by savings.js."""
    D = _savings()
    ops = [o for o in D['opportunities'] if key in o['govs']]
    if not ops:
        return ''
    sm = lambda k: sum(o[k] or 0 for o in ops)
    reqs = ''.join(f'<li><b>{e(r["q"])}</b><br><span class="muted small">{e(r["why"])}</span> <a class="pill sm" href="/records-request?gov={key}&amp;d={e(r["q"])}">Request this record</a></li>' for r in D['general_requests'])
    return f'''<section class="tx-sec sav" id="savings"><div class="sec-hd"><h2>Where it could spend less</h2><span class="muted" id="svCount" aria-live="polite">{len(ops)} place{"s" if len(ops) != 1 else ""} to look</span></div>
      <p class="small muted">Found in records already on this site: projects that ran over, money budgeted but not spent, services bought separately that could be bought together. Each shows the records it rests on, an estimate with its assumption, and the question to ask next. An opportunity is a question worth asking, not a finding that money was wasted.</p>
      <div class="sav-stats" role="list">
        <div role="listitem"><b id="svM">{money(sm("in_play"))}</b><span>spending these touch</span></div>
        <div role="listitem"><b id="svL">{money(sm("savings_low"))}</b><span>potential savings, low estimate</span></div>
        <div role="listitem"><b id="svH">{money(sm("savings_high"))}</b><span>potential savings, high estimate</span></div>
        <div role="listitem"><b id="svN">{sum(1 for o in ops if o["estimate"] == "records")}</b><span>need records before an estimate</span></div></div>
      <div class="sav-filters" id="svF" role="group" aria-label="Filter by kind of saving"></div>
      <div id="svList" class="sav-list"><p class="muted">Loading…</p></div>
      <details class="tbl-toggle"><summary>Records that would find more</summary><p class="small muted">The CRA ledger covers projects and grants, not every payment. These records would show subscriptions, duplicate payments and price differences.</p><ul class="plain sav-reqs">{reqs}</ul></details>
      <p class="src-line">Estimates multiply the spending in play by a low and a high rate; the rate is the stated assumption, not a measured result. Some overlap, so treat totals as a scale. Data: <a href="/data/savings.json">JSON</a> · <a href="/open-data">open data</a></p></section>'''


def savings_hint(key):
    n = sum(1 for o in _savings()['opportunities'] if key in o['govs'])
    return f'{n} idea{"s" if n != 1 else ""}' if n else 'Ways to spend less'


def write_savings_data(out_dir):
    """public/data/savings.json, read by assets/savings.js on each government's page."""
    json.dump(_savings(), open(os.path.join(out_dir, 'data', 'savings.json'), 'w'), separators=(',', ':'))
    for f in ('savings.js', 'savings.css'):
        open(os.path.join(out_dir, 'assets', f), 'w').write(open(os.path.join(HERE, f)).read())


# ---------------- budget (formerly the Budget explorer) ----------------
@lru_cache(None)
def _budgets():
    fp = os.path.join(DATA, 'civic', 'budgets_detail.json')
    return {g['gov']: g for g in json.load(open(fp))['governments']} if os.path.exists(fp) else {}


@lru_cache(None)
def _per_resident():
    from money_pages import per_resident_rows
    return per_resident_rows()


def _bars(items, total, pop):
    xs = sorted((x for x in items or [] if x.get('amount')), key=lambda x: -x['amount'])
    if not xs:
        return '<p class="muted small">Not broken out in the published budget.</p>'
    mx, tot = xs[0]['amount'], total or sum(x['amount'] for x in xs)
    per = lambda v: (f'<small>${v / pop:,.0f} per resident</small>' if v / pop >= 1 else '<small>&lt;$1 per resident</small>') if pop else ''
    return '<div class="hbars per">' + ''.join(
        f'<div class="hb"><span class="hb-n">{e(x["name"])}{f" <em>{e(x["type"])}</em>" if x.get("type") else ""}</span><span class="hb-track"><span class="hb-bar" style="width:{max(.5, x["amount"] / mx * 100):.1f}%"></span></span>'
        f'<span class="hb-v">{money(x["amount"])} <em>{x["amount"] / tot * 100:.1f}%</em>{per(x["amount"])}</span></div>' for x in xs) + '</div>'


def budget_fy(key):
    """The fiscal year of the budget the Money section is drawn with at build (budgets_detail.json), so gov.js redraws it only for another year."""
    g = _budgets().get(key) or {}
    return _fy(g.get('fiscal_year'))


def budget_detail(key, pop):
    """The whole adopted budget for one government: every fund, General Fund departments, revenue by source, and what
    each service costs per resident next to the city median. Folded under the Money section of its page."""
    g = _budgets().get(key)
    if not g:
        return ''
    gname = g.get('name')
    svc = [r for r in _per_resident() if r['government'] == gname and r['per_resident'] is not None]
    bench = ''
    if svc:
        city = any(r['in_city_median'] for r in svc)
        def vs(r):
            p = r['vs_city_median_pct']
            if p is None:
                return '<span class="muted">—</span>'
            return 'about the same' if abs(p) < 5 else f'{abs(p):.0f}% {"above" if p > 0 else "below"}'
        bench = ('<h3 class="h4">What each service costs per resident</h3><div class="tablewrap"><table class="tx-table" data-tt="off"><thead><tr><th scope="col">Service</th>'
                 '<th scope="col" class="num">General Fund</th><th scope="col" class="num">Per resident</th>' + ('<th scope="col" class="num">City median</th><th scope="col">Compared with the median</th>' if city else '') + '</tr></thead><tbody>'
                 + ''.join(f'<tr><th scope="row" style="white-space:normal;min-width:11em;max-width:22em">{e(r["service"])}<br><span class="muted small">{e(r["departments_included"])}</span></th><td class="num">{money(r["general_fund_amount"])}</td><td class="num"><b>${r["per_resident"]:,.0f}</b></td>'
                           + (f'<td class="num">{"$" + format(r["city_median_per_resident"], ",.0f") if r["city_median_per_resident"] else "—"}</td><td class="small">{vs(r)}</td>' if city else '') + '</tr>' for r in svc)
                 + '</tbody></table></div><p class="note small">' + ('The median is the middle city of the seven. ' if city else 'Bay County serves every resident, cities included, so it is not compared with the city median. ')
                 + 'Only the General Fund is counted, without transfers, reserves, debt and hurricane-recovery lines. <a href="/compare#services">Compare every government, service by service</a></p>')
    notes = g.get('notes')
    notes = notes if isinstance(notes, list) else [notes] if notes else []
    rv = g.get('revenues') or []
    scope = '' if not rv else (' (all funds)' if key in ('county', 'schools', 'pc', 'mb') else ' (General Fund only)')
    return f'''<details class="tbl-toggle be-full"><summary>The whole {e((g.get("fiscal_year") or "").split(" ")[0])} budget: every fund and department{", and cost per resident" if svc else ""}</summary>
      <div class="kpis"><div class="kpi"><span class="eyebrow">Total budget</span><span class="v">{money(g.get("total"))}</span><span class="s">{f"${g['total'] / pop:,.0f} per resident · " if pop and g.get("total") else ""}{e("Adopted" if g.get("status") == "adopted" else "Tentative")}</span></div></div>
      {bench}
      <h3 class="h4">Where the money is budgeted, by fund</h3>{_bars(g.get("funds"), g.get("total"), pop)}
      <h3 class="h4">General Fund spending, by department</h3>{_bars(g.get("general_fund_departments"), None, pop)}
      {f'<h3 class="h4">Where the money comes from{scope}</h3>{_bars(rv, None, pop)}' if rv else ''}
      <p class="note small">Funds are separate accounts: money raised for one purpose can only be spent on it. When one fund pays another, both show it, so totals count some money twice. {" ".join(e(n) for n in notes)} {src(g.get("source_url"), "Budget document")}</p></details>'''
