"""Budget data shared by government pages and /compare (formerly the Budget explorer), and tourism-agency payments
(a section of /public-money/tourist-tax, formerly /public-money/who-gets-paid)."""
import html, json, os, re
from city_filter import city_bar, data_g, by_city, KEYS

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
e = lambda s: html.escape(str(s if s is not None else ''))
PDF_BTN = '<button type="button" class="pdf-btn" id="pdf"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button>'


def money(n):
    if n is None:
        return '—'
    a = abs(n)
    return f'${n/1e9:,.2f}B' if a >= 1e9 else f'${n/1e6:,.1f}M' if a >= 1e6 else f'${n/1e3:,.0f}K' if a >= 1e4 else f'${n:,.0f}'


def _j(*p):
    fp = os.path.join(DATA, *p)
    return json.load(open(fp)) if os.path.exists(fp) else None


# ---------------- Budget explorer ----------------
# Common service groups, so each government's own department names line up for benchmarking.
SERVICES = [
    ('police', 'Police / law enforcement'),
    ('fire', 'Fire'),
    ('streets', 'Streets & public works'),
    ('parks', 'Parks & recreation'),
    ('library', 'Libraries'),
    ('dev', 'Planning, building & code'),
    ('admin', 'Administration & support'),
]
SVC_NAME = dict(SERVICES)
# Order matters: first match wins. None = left out of service totals (transfers, reserves, debt, disaster money).
SVC_RULES = [
    (None, r'transfer|\breserves?\b|fund balance|debt service|fema|debris|non-departmental'),
    ('other', r'jail|emergency medical|emergency management|human services|economic|court|canal|trash|animal|community services$|instruction|pupil|plant|facilities acquisition'),
    ('police', r'police|law enforcement|sheriff'),
    ('fire', r'\bfire\b'),
    ('streets', r'street|roads|public works'),
    ('parks', r'park|recreation|leisure|sports|bayou preserve'),
    ('library', r'librar'),
    ('dev', r'planning|building|code|development'),
    ('admin', r'legislative|executive|admin|legal|finance|human resources|\bhr\b|\bit\b|information technology|manager|clerk|elected|general government|customer service|communications|fleet|vehicle|maintenance|constitutional|indirect cost|school board|fiscal|central services|technology'),
]


def service_of(name):
    n = (name or '').lower()
    for svc, rx in SVC_RULES:
        if re.search(rx, n):
            return svc
    return 'other'


def _bench(depts):
    out = {}
    for x in depts or []:
        s = service_of(x.get('name'))
        if s is None:
            continue
        if s in SVC_NAME:
            o = out.setdefault(s, {'amount': 0, 'lines': []})
            o['amount'] += x['amount']
            o['lines'].append(x['name'])
        t = out.setdefault('total', {'amount': 0, 'lines': []})
        t['amount'] += x['amount']
    for o in out.values():
        o['amount'] = round(o['amount'])
    return out


def per_resident_rows():
    """One row per government and service: General Fund budget, residents, cost per resident, city median.
    Same grouping as the budget explorer's benchmark, so the download matches the page."""
    from govs import GOVS, profile
    d = _j('civic', 'budgets_detail.json')
    if not d:
        return []
    meta = {g['key']: g for g in GOVS}
    gs = []
    for g in d['governments']:
        mt = meta.get(g['gov'])
        if not mt or mt['kind'] == 'schools':
            continue
        pop = profile(g['gov']).get('population')
        if pop:
            gs.append((g, mt, pop, _bench(g.get('general_fund_departments'))))
    gs.sort(key=lambda x: [k['key'] for k in GOVS].index(x[0]['gov']))

    def med(a):
        if len(a) < 3:
            return None
        s = sorted(a); n = len(s) // 2
        return s[n] if len(s) % 2 else (s[n - 1] + s[n]) / 2

    rows = []
    for sid, label in SERVICES + [('total', 'Everyday General Fund')]:
        md = med([b[sid]['amount'] / pop for g, mt, pop, b in gs if mt['kind'] == 'city' and sid in b])
        for g, mt, pop, b in gs:
            x = b.get(sid)
            pr = x['amount'] / pop if x else None
            rows.append({'government': g.get('name'), 'kind': mt['kind'], 'fiscal_year': g.get('fiscal_year'),
                         'service_id': sid, 'service': label,
                         'general_fund_amount': x['amount'] if x else None, 'residents': pop,
                         'per_resident': round(pr, 2) if pr is not None else None,
                         'city_median_per_resident': round(md, 2) if md is not None else None,
                         'vs_city_median_pct': round((pr / md - 1) * 100, 1) if pr is not None and md and mt['kind'] == 'city' else None,
                         'in_city_median': mt['kind'] == 'city' and x is not None,
                         'departments_included': '; '.join(x['lines']) if x and sid != 'total' else ('All General Fund lines except transfers, reserves, debt and FEMA/debris' if x else 'Not a separate General Fund line'),
                         'source_url': g.get('source_url')})
    return rows


# ---------------- Who gets paid (tourism agencies) ----------------
SHORT = {'visit_pcb_cvb': 'Visit Panama City Beach', 'destination_panama_city_cdc': 'Destination Panama City', 'mexico_beach_cdc': 'Mexico Beach CDC'}
# the city each county tourist-tax agency markets (they are county agencies, not city departments)
AG_CITY = {'visit_pcb_cvb': 'pcb', 'destination_panama_city_cdc': 'pc', 'mexico_beach_cdc': 'mb'}
CAT = {'payroll/benefit/tax pass-through': 'Payroll or benefits', 'government': 'Government', 'credit card payment (underlying merchants not itemized)': 'Credit card bill'}


def VLINK(name):
    try:  # link to the vendor's profile page when it has one (vendor_pages.py)
        from vendor_pages import link
        return link(name)
    except Exception:
        return e(name)


def fy_cell(a, v, f):  # a payee's total for one year, linked to that year's monthly registers on the page
    amt = v['by_fy'].get(f)
    if not amt:
        return '<span class=muted>—</span>'
    if not (a.get('coverage_by_fy') or {}).get(f):
        return money(amt)
    return f'<a href="#reg-{a["gov"]}-{f}" title="{f} check registers">{money(amt)}</a>'


def payments_section():
    """Every payment by the three county tourism agencies, as sections of the Tourist tax page (/public-money/tourist-tax).
    This used to be its own page, /public-money/who-gets-paid. Dataset vendor-payments."""
    p = _j('money', 'payments.json')
    if not p:
        return ''
    A = p['governments']
    tot = sum(a['parsed_total_all_payees'] for a in A)
    fys = ['FY2024', 'FY2025', 'FY2026']
    reg = {}  # month -> Clerk register document (the same monthly registers carry the agency sections)
    for r in (_j('contracts', 'contracts.json') or {}).get('registers', []):
        for m in r.get('monthly_sources') or []:
            if m.get('month') and m.get('url'):
                reg[m['month']] = m
    mon = lambda m: __import__('datetime').date(int(m[:4]), int(m[5:7]), 1).strftime('%b %Y')
    tabs, secs = '', ''
    for i, a in enumerate(A):
        nm = SHORT.get(a['gov'], a['name'])
        tabs += f'<option value="{a["gov"]}" data-city="{AG_CITY.get(a["gov"], "")}">{e(nm)}</option>'
        rows = ''
        for v in a['vendors']:
            cat = v.get('category')
            badge = f' <span class="badge">{e(CAT.get(cat, cat))}</span>' if cat else ''
            rows += (f'<tr data-v="{e(v["vendor"].lower())}"><th scope="row">{VLINK(v["vendor"])}{badge}</th><td class="num">{money(v["total"])}</td><td class="num">{v["n_payments"]}</td>'
                     + ''.join(f'<td class="num">{fy_cell(a, v, f)}</td>' for f in fys) + '</tr>')
        cov = a.get('coverage_by_fy') or {}
        covtxt = ' · '.join(f'{f}: {len(cov.get(f, []))} of 12 months' for f in fys)
        src_urls = set(a.get('source_urls') or [])
        reglist = ''.join(f'<li id="reg-{a["gov"]}-{f}"><b>{f}</b>: ' + ', '.join(
            f'<a class="src" href="{e(reg[m]["url"])}" target="_blank" rel="noopener" title="{e(reg[m].get("document") or "")}">{mon(m)}</a>' if m in reg and reg[m]['url'] in src_urls else e(mon(m))
            for m in cov.get(f, [])) + '</li>' for f in fys if cov.get(f))
        notes = ''.join(f'<li>{e(n)}</li>' for n in a.get('notes') or [])
        ex = a.get('excluded_individuals') or {}
        listed = f'Top {a["vendors_listed"]} of {a["vendor_count_total"]} payees' if a['vendors_listed'] < a['vendor_count_total'] else f'All {a["vendor_count_total"]} payees'
        secs += f'''<div class="wp-ag" data-ag="{a["gov"]}"{"" if i == 0 else " hidden"}>
    <h3 class="h4">{e(a["name"])} <span class="muted small">{e(covtxt)}</span></h3>
    <div class="kpis"><div class="kpi"><span class="eyebrow">Paid out</span><span class="v">{money(a["parsed_total_all_payees"])}</span><span class="s">{a["parsed_payments"]:,} payments in the months covered</span></div>
      <div class="kpi"><span class="eyebrow">Payees</span><span class="v">{a["vendor_count_total"]}</span><span class="s">{e(listed)} shown</span></div>
      <div class="kpi"><span class="eyebrow">Checked</span><span class="v">{e(a["reconciliation_summary"].split(" match")[0])}</span><span class="s">months match the register's printed total</span></div>
      <div class="kpi"><span class="eyebrow">To individuals</span><span class="v">{money(ex.get("total"))}</span><span class="s">{ex.get("n_payments", 0)} payments, not named here</span></div></div>
    <details class="tbl-toggle wp-list"><summary>Every payee ({len(a["vendors"])} listed), largest first</summary>
    <div class="tablewrap"><table class="tx-table cm-table wp-table" data-tt-search="off" data-tt-sort="5:desc"><thead><tr><th scope="col">Paid to</th><th scope="col" class="num">Total</th><th scope="col" class="num">Payments</th>{"".join(f'<th scope="col" class="num">{f}</th>' for f in fys)}</tr></thead><tbody>{rows}</tbody></table></div>
    <p class="note">Each amount links to that year's registers below. The registers are monthly, so a payee's total for a year comes from one or more of that year's files.</p></details>
    <details class="tbl-toggle"><summary>Monthly check registers ({sum(len(cov.get(f, [])) for f in fys)})</summary><ul class="plain small">{reglist}</ul><p class="note">The Clerk of Court's monthly "Check Register – Sorted by Dollar Amount," attached to County Commission agendas. Each file has a section for this agency.</p></details>
    <details class="gaps"><summary>Notes on this register ({len(a.get("notes") or [])})</summary><ul>{notes}</ul><p>{" · ".join(f'<a class="src" href="{e(u)}" target="_blank" rel="noopener">{k + 1}</a>' for k, u in enumerate(a.get("source_urls") or []))}</p></details></div>'''
    gaps = ''.join(f'<li>{e(g)}</li>' for g in p.get('gaps') or [])
    return f'''<section class="tx-sec wp"><div class="sec-hd"><h2 id="paid" data-tile="Who gets paid">Who the tourism agencies paid</h2><span class="muted">Registers through July 2026</span></div>
    <p>Part of the bed tax pays three agencies that market each tourism area. The Clerk of Court pays their bills, and each agency's payments are listed in the Clerk's monthly check register: {money(tot)} over the months covered. Credit card bills and payroll services show as one payment, and payments to individual people are counted but not named. The county's own payments are on the <a href="/public-money/contracts">Contracts</a> page.</p>
    <div class="callout">In January 2026 the Clerk of Court published an <a href="https://apps.baycoclerk.com/Web_File_Repo/bocc_finance/Panama_City_Beach_TDC_CVB_Public_CAP.pdf" target="_blank" rel="noopener">action plan for Visit Panama City Beach</a>, describing a criminal investigation and forensic audit and putting the agency's payments under the Clerk's review. The payments here are listed as recorded; this site makes no finding about any of them.</div>
    <div class="vt-filters mt-f two"><label class="vf"><span>Agency</span><select id="wpA" data-param="agency">{tabs}</select></label><label class="vf"><span>Search payees</span><input id="wpQ" type="search" placeholder="e.g. Meta, printing, hotel" data-param="q"></label></div>
    {secs}
    <details class="gaps"><summary>Where the payments come from, and what we couldn't find ({len(p.get("gaps") or [])})</summary>
      <p>Most months come from the Clerk's public records search as text PDFs; one month (December 2024) was only available as a scan and was read by OCR. Every month was added up and checked against the register's printed totals for each agency. No city or the School Board posts a check register; you can <a href="/records-request">request one</a>.</p><ul>{gaps}</ul></details></section>
<script>
(() => {{ const a = document.getElementById('wpA'), q = document.getElementById('wpQ'), u = new URLSearchParams(location.search);
  if (!a) return;
  if (u.get('agency') && [...a.options].some(o => o.value === u.get('agency'))) a.value = u.get('agency');
  addEventListener('hashchange', () => {{ const t = document.getElementById(location.hash.slice(1)); if (t && t.closest('details')) {{ t.closest('details').open = true; t.scrollIntoView({{block: 'center'}}); }} }});
  // a payee's year links to that year's registers, in the list below the table
  document.querySelectorAll('.wp-table a[href^="#reg-"]').forEach(x => x.addEventListener('click', () => {{ const t = document.getElementById(x.getAttribute('href').slice(1)); if (t) t.closest('details').open = true; }}));
  const run = () => {{ document.querySelectorAll('.wp-ag').forEach(s => s.hidden = s.dataset.ag !== a.value); const t = q.value.trim().toLowerCase();
    document.querySelectorAll('.wp-ag:not([hidden]) tbody tr').forEach(tr => tr.hidden = !!t && !tr.dataset.v.includes(t));
    if (t) document.querySelectorAll('.wp-ag:not([hidden]) details.wp-list').forEach(d => d.open = true); }};
  if (u.get('q')) q.value = u.get('q');
  a.addEventListener('change', run); q.addEventListener('input', run);
  // the city bar: show the agency that markets that zone (all three for Bay County or no pick)
  const city = k => {{ const m = k && [...a.options].find(o => o.dataset.city === k); [...a.options].forEach(o => o.hidden = !!m && o !== m); if (m) a.value = m.value; run(); }};
  const go = () => {{ if (window.BCM && BCM.city) BCM.city.on(city); else run(); }};
  if (window.BCM) go(); else addEventListener('DOMContentLoaded', go); }})();
</script>'''
