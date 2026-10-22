"""Budget explorer (/public-money/budget-explorer) and tourism-agency payments (/public-money/who-gets-paid)."""
import html, json, os, re

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


BUDGET_JS = r"""
(() => {
const B = __B__, SV = __SV__;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const M = n => { const a = Math.abs(n); return a >= 1e9 ? '$' + (n/1e9).toFixed(2) + 'B' : a >= 1e6 ? '$' + (n/1e6).toFixed(1) + 'M' : a >= 1e4 ? '$' + Math.round(n/1e3).toLocaleString() + 'K' : '$' + Math.round(n).toLocaleString(); };
const R = (n, pop) => { if (!pop || n == null) return ''; const v = n / pop; return Math.abs(v) < 1 && v !== 0 ? (v < 0 ? '−' : '') + '<$1' : (v < 0 ? '−$' : '$') + Math.round(Math.abs(v)).toLocaleString(); };
const med = a => { if (a.length < 3) return null; const s = [...a].sort((x, y) => x - y), m = s.length >> 1; return s.length ? (s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2) : null; };
$('beG').innerHTML = B.map(b => `<option value="${b.gov}">${esc(b.short)}</option>`).join('');
const P = new URLSearchParams(location.search);
if (P.get('gov') && B.some(b => b.gov === P.get('gov'))) $('beG').value = P.get('gov');
let svc = SV.some(s => s[0] === P.get('svc')) ? P.get('svc') : 'police';
function bars(list, total, pop, note) {
  if (!list || !list.length) return `<p class="muted">${note || 'Not broken out in the published budget.'}</p>`;
  const xs = [...list].sort((a, b) => b.amount - a.amount), mx = xs[0].amount, sum = xs.reduce((s, x) => s + x.amount, 0);
  return '<div class="hbars per">' + xs.map(x => `<div class="hb"><span class="hb-n">${esc(x.name)}${x.type ? ` <em>${esc(x.type)}</em>` : ''}</span><span class="hb-track"><span class="hb-bar" style="width:${Math.max(.5, x.amount / mx * 100).toFixed(1)}%"></span></span><span class="hb-v">${M(x.amount)} <em>${(x.amount / (total || sum) * 100).toFixed(1)}%</em>${pop ? `<small>${R(x.amount, pop)} per resident</small>` : ''}</span></div>`).join('') + '</div>';
}
const cmp = B.filter(b => b.bench && b.pop);
function bench(b) {
  $('bnChips').innerHTML = SV.map(s => `<button type="button" class="chip" data-s="${s[0]}" aria-pressed="${s[0] === svc}">${esc(s[1])}</button>`).join('');
  const rows = cmp.map(g => ({g, v: g.bench[svc] ? g.bench[svc].amount / g.pop : null, inc: g.bench[svc] ? g.bench[svc].lines : []}));
  const cities = rows.filter(r => r.g.kind === 'city' && r.v != null), m = med(cities.map(r => r.v));
  const mx = Math.max(...rows.map(r => r.v || 0));
  rows.sort((a, b) => (b.v ?? -1) - (a.v ?? -1));
  $('bnBars').innerHTML = '<div class="hbars bench">' + rows.map(r => `<div class="hb${r.g.gov === b.gov ? ' me' : ''}${r.g.kind !== 'city' ? ' ctx' : ''}" tabindex="0" title="${esc(r.inc.length ? 'Includes: ' + r.inc.join('; ') : 'No separate line in the General Fund')}"><span class="hb-n">${esc(r.g.short)}${r.g.kind !== 'city' ? ' <em>countywide</em>' : ''}<small>${r.inc.length ? esc(r.inc.join(' · ')) : 'Not a separate General Fund line'}</small></span><span class="hb-track">${r.v != null ? `<span class="hb-bar" style="width:${Math.max(.5, r.v / mx * 100).toFixed(1)}%"></span>` : ''}${m != null && mx ? `<span class="hb-med" style="left:${(m / mx * 100).toFixed(1)}%"></span>` : ''}</span><span class="hb-v">${r.v != null ? R(r.v, 1) : '—'} <em>${r.v != null ? 'per resident' : ''}</em><small>${r.v != null ? M(r.g.bench[svc].amount) + ' · ' + r.g.pop.toLocaleString() + ' residents' : ''}</small></span></div>`).join('') + '</div>';
  const me = rows.find(r => r.g.gov === b.gov);
  let s = m != null ? `City median: <b>${R(m, 1)}</b> per resident for ${esc(SV.find(x => x[0] === svc)[1].toLowerCase())}.` : '';
  if (me && me.v != null && m && b.kind === 'city') { const d = (me.v / m - 1) * 100; s += ` ${esc(b.short)} is <b>${R(me.v, 1)}</b>, ${Math.abs(d) < 5 ? 'about the same as the median' : Math.round(Math.abs(d)) + '% ' + (d > 0 ? 'above' : 'below') + ' the median'}.`; }
  else if (b.kind !== 'city') s += ` ${esc(b.short)} ${b.bench ? 'serves the whole county, so it is shown for context and left out of the median.' : 'isn\'t compared here: its budget pays for schools, so cost per student is the fairer measure.'}`;
  $('bnSum').innerHTML = s;
  // matrix
  const cols = [...SV, ['total', 'Everyday General Fund']];
  const meds = Object.fromEntries(cols.map(c => [c[0], med(cmp.filter(g => g.kind === 'city' && g.bench[c[0]]).map(g => g.bench[c[0]].amount / g.pop))]));
  $('bnTbl').innerHTML = `<thead><tr><th scope="col">Per resident</th>${cols.map(c => `<th scope="col" class="num${c[0] === svc ? ' on' : ''}">${esc(c[1])}</th>`).join('')}</tr></thead><tbody>` +
    cmp.map(g => `<tr class="${g.gov === b.gov ? 'me' : ''}"><th scope="row">${esc(g.short)}${g.kind !== 'city' ? ' <span class="muted">(countywide)</span>' : ''}</th>${cols.map(c => { const x = g.bench[c[0]]; if (!x) return '<td class="num muted">—</td>'; const v = x.amount / g.pop, md = meds[c[0]], hi = g.kind === 'city' && md && v > md * 1.25, lo = g.kind === 'city' && md && v < md * .75; return `<td class="num${c[0] === svc ? ' on' : ''}">${R(v, 1)}${hi ? '<span class="ar" title="More than 25% above the city median">▲</span>' : lo ? '<span class="ar" title="More than 25% below the city median">▼</span>' : ''}</td>`; }).join('')}</tr>`).join('') +
    `</tbody><tfoot><tr><th scope="row">City median</th>${cols.map(c => `<td class="num${c[0] === svc ? ' on' : ''}">${meds[c[0]] != null ? R(meds[c[0]], 1) : '—'}</td>`).join('')}</tr></tfoot>`;
}
function run() {
  const b = B.find(x => x.gov === $('beG').value), pop = b.pop;
  history.replaceState(null, '', '?gov=' + b.gov + (svc !== 'police' ? '&svc=' + svc : ''));
  const gf = (b.funds || []).find(f => /general/i.test(f.type || '') || /general fund/i.test(f.name));
  const gfd = (b.general_fund_departments || []).reduce((s, x) => s + x.amount, 0), gfv = gf ? gf.amount : gfd || null;
  $('beKpis').innerHTML = `<div class="kpi"><span class="eyebrow">Total budget</span><span class="v">${M(b.total)}</span><span class="s">${pop ? R(b.total, pop) + ' per resident · ' : ''}${esc(b.fiscal_year)}</span></div>
    <div class="kpi"><span class="eyebrow">General Fund</span><span class="v">${gfv ? M(gfv) : '—'}</span><span class="s">${gfv && pop ? R(gfv, pop) + ' per resident · ' : ''}day-to-day operations</span></div>
    <div class="kpi"><span class="eyebrow">Residents</span><span class="v">${pop ? pop.toLocaleString() : '—'}</span><span class="s">${b.gov === 'schools' ? 'everyone in Bay County' : b.gov === 'county' ? 'whole county, cities included' : 'state estimate, April 2025'}</span></div>
    <div class="kpi"><span class="eyebrow">Status</span><span class="v">${b.status === 'adopted' ? 'Adopted' : 'Tentative'}</span><span class="s">${b.status === 'adopted' ? 'Final budget approved in September' : 'Final adopted budget not posted online'}</span></div>`;
  $('beFunds').innerHTML = bars(b.funds, b.total, pop);
  $('beDepts').innerHTML = bars(b.general_fund_departments, null, pop);
  $('beRev').innerHTML = bars(b.revenues, null, pop, 'Revenues by source are not broken out for all funds in the published budget.');
  $('beRevNote').textContent = b.rev_scope || '';
  const notes = Array.isArray(b.notes) ? b.notes : (b.notes ? [b.notes] : []);
  $('beNotes').innerHTML = notes.map(n => `<p>${esc(n)}</p>`).join('') + (b.source_url ? `<p><a class="src" href="${esc(b.source_url)}" target="_blank" rel="noopener">Budget document</a></p>` : '');
  $('beGov').href = '/governments/' + b.slug; $('beGov').textContent = b.short + ' overview →';
  $('beTitle').textContent = b.short + ' budget';
  bench(b);
}
$('bnChips').addEventListener('click', ev => { const c = ev.target.closest('[data-s]'); if (c) { svc = c.dataset.s; run(); } });
$('beG').addEventListener('change', run); run();
})();
"""


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


def budget_page(out_dir):
    from govs import GOVS, profile
    d = _j('civic', 'budgets_detail.json')
    if not d:
        return '<div class="page prose"><h1>Budget explorer</h1><p>Coming soon.</p></div>'
    meta = {g['key']: g for g in GOVS}
    B = []
    for g in d['governments']:
        m = meta.get(g['gov'])
        if not m:
            continue
        rv = g.get('revenues') or []
        B.append({**{k: g.get(k) for k in ('gov', 'name', 'fiscal_year', 'status', 'total', 'source_url', 'funds', 'general_fund_departments', 'revenues', 'notes')},
                  'short': m['short'], 'slug': m['slug'], 'kind': m['kind'], 'pop': profile(g['gov']).get('population'),
                  'bench': None if m['kind'] == 'schools' else _bench(g.get('general_fund_departments')),
                  'rev_scope': '' if not rv else ('All funds.' if g['gov'] in ('county', 'schools', 'pc', 'mb') else 'General Fund only.')})
    B.sort(key=lambda b: [g['key'] for g in GOVS].index(b['gov']))
    js = BUDGET_JS.replace('__B__', json.dumps(B, ensure_ascii=False, separators=(',', ':'))).replace('__SV__', json.dumps(SERVICES, separators=(',', ':')))
    open(os.path.join(out_dir, 'assets', 'budget.js'), 'w').write(js)
    gnotes = ''.join(f'<li>{e(n)}</li>' for n in (d.get('notes') or []))
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Public Money · Budgets</span><h1 id="beTitle">Budget explorer</h1>
    <p class="lede">Open up any local government's FY2026 budget: how much goes into each fund, what the General Fund spends by department, and what each service costs per resident, side by side with the other cities.</p></div>
    <div class="stamp">{PDF_BTN}<a class="pill" id="beGov" href="/governments">Overview →</a></div></header>
  <div class="vt-filters mt-f"><label class="vf"><span>Government</span><select id="beG"></select></label></div>
  <div class="kpis" id="beKpis"></div>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>How a government budget is organized</h2>
    <ol class="ex-steps"><li><b>Funds are separate bank accounts.</b> Money raised for one purpose, like water bills or a sales tax, goes into its own fund and can only be spent on that purpose.</li>
    <li><b>The General Fund is the everyday account.</b> Police, parks, roads and city hall are paid from it, mostly with property tax.</li>
    <li><b>Totals count some money twice.</b> When one fund pays another (a transfer), both show it, so totals aren't a perfect measure of size. The notes below say what each total includes.</li></ol></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="bench">Cost per resident, by service</h2><span class="muted">FY2026 General Fund budget ÷ residents</span></div>
    <div class="chips print-hide" id="bnChips" role="group" aria-label="Service to compare"></div>
    <p class="bn-sum" id="bnSum"></p>
    <div id="bnBars"></div>
    <details class="tbl-toggle" open><summary>Every service, every government</summary><div class="tablewrap"><table class="tx-table bn-tbl" id="bnTbl"></table></div>
      <p class="note">▲ more than 25% above the city median · ▼ more than 25% below. Download: <a href="/downloads/budget-per-resident.csv">CSV</a> · <a href="/downloads/budget-per-resident.json">JSON</a> · <a href="/open-data">all open data</a></p></details>
    <details class="gaps"><summary>How the services are grouped, and what to watch for</summary><ul>
      <li><b>Departments are grouped by name.</b> Each government names its departments differently, so they're sorted into common services. Hover a bar or read the line under each name to see exactly which departments were added together.</li>
      <li><b>Only the General Fund is counted.</b> Some cities pay for a service partly from other funds (a roads fund, a fire assessment, the CRA), so their General Fund figure can understate the full cost.</li>
      <li><b>Left out of every service:</b> transfers to other funds, reserves, debt payments and hurricane-recovery (FEMA and debris) lines. "Everyday General Fund" is the General Fund without those.</li>
      <li><b>Contract services count too.</b> Callaway and Mexico Beach pay the Sheriff for policing; that contract is their police cost.</li>
      <li><b>Visitors raise the numbers.</b> Panama City Beach and Mexico Beach serve far more people than live there, so their per-resident costs run high.</li>
      <li><b>Bay County</b> is shown for context only. Its figures are spread over every county resident, though much of the Sheriff's patrol serves unincorporated areas. The school district isn't compared here.</li>
      <li><b>Residents</b> are the University of Florida's April 2025 state estimates.</li></ul></details></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="funds">Where the money is budgeted, by fund</h2></div><div id="beFunds"></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="depts">General Fund spending, by department</h2></div><div id="beDepts"></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="rev">Where the money comes from</h2><span class="muted" id="beRevNote"></span></div><div id="beRev"></div></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">About this budget</h2></div><div id="beNotes"></div>
    <details class="gaps"><summary>About all the budgets</summary><ul>{gnotes}<li>Department and fund names are shortened from the budget documents. Scanned budgets (Callaway, Springfield, Parker) were read by OCR; each list was checked against the document's printed total.</li></ul></details></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/budget.js" defer></script>'''


# ---------------- Who gets paid (tourism agencies) ----------------
SHORT = {'visit_pcb_cvb': 'Visit Panama City Beach', 'destination_panama_city_cdc': 'Destination Panama City', 'mexico_beach_cdc': 'Mexico Beach CDC'}
CAT = {'payroll/benefit/tax pass-through': 'Payroll or benefits', 'government': 'Government', 'credit card payment (underlying merchants not itemized)': 'Credit card bill'}


def fy_cell(a, v, f):  # a payee's total for one year, linked to that year's monthly registers on the page
    amt = v['by_fy'].get(f)
    if not amt:
        return '<span class=muted>—</span>'
    if not (a.get('coverage_by_fy') or {}).get(f):
        return money(amt)
    return f'<a href="#reg-{a["gov"]}-{f}" title="{f} check registers">{money(amt)}</a>'


def payments_page():
    p = _j('money', 'payments.json')
    if not p:
        return '<div class="page prose"><h1>Who gets paid</h1><p>Coming soon.</p></div>'
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
        tabs += f'<option value="{a["gov"]}">{e(nm)}</option>'
        rows = ''
        for v in a['vendors']:
            cat = v.get('category')
            badge = f' <span class="badge">{e(CAT.get(cat, cat))}</span>' if cat else ''
            rows += (f'<tr data-v="{e(v["vendor"].lower())}"><th scope="row">{e(v["vendor"])}{badge}</th><td class="num">{money(v["total"])}</td><td class="num">{v["n_payments"]}</td>'
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
        secs += f'''<section class="tx-sec wp-ag" data-ag="{a["gov"]}"{"" if i == 0 else " hidden"}>
    <div class="sec-hd"><h2>{e(a["name"])}</h2><span class="muted">{e(covtxt)}</span></div>
    <div class="kpis"><div class="kpi"><span class="eyebrow">Paid out</span><span class="v">{money(a["parsed_total_all_payees"])}</span><span class="s">{a["parsed_payments"]:,} payments in the months covered</span></div>
      <div class="kpi"><span class="eyebrow">Payees</span><span class="v">{a["vendor_count_total"]}</span><span class="s">{e(listed)} shown</span></div>
      <div class="kpi"><span class="eyebrow">Checked</span><span class="v">{e(a["reconciliation_summary"].split(" match")[0])}</span><span class="s">months match the register's printed total</span></div>
      <div class="kpi"><span class="eyebrow">To individuals</span><span class="v">{money(ex.get("total"))}</span><span class="s">{ex.get("n_payments", 0)} payments, not named here</span></div></div>
    <div class="tablewrap"><table class="tx-table cm-table wp-table" data-tt-search="off"><thead><tr><th scope="col">Paid to</th><th scope="col" class="num">Total</th><th scope="col" class="num">Payments</th>{"".join(f'<th scope="col" class="num">{f}</th>' for f in fys)}</tr></thead><tbody>{rows}</tbody></table></div>
    <p class="note">Each amount links to that year's registers below. The registers are monthly, so a payee's total for a year comes from one or more of that year's files.</p>
    <details class="tbl-toggle"><summary>Monthly check registers ({sum(len(cov.get(f, [])) for f in fys)})</summary><ul class="plain small">{reglist}</ul><p class="note">The Clerk of Court's monthly "Check Register – Sorted by Dollar Amount," attached to County Commission agendas. Each file has a section for this agency.</p></details>
    <details class="gaps"><summary>Notes on this register ({len(a.get("notes") or [])})</summary><ul>{notes}</ul><p>{" · ".join(f'<a class="src" href="{e(u)}" target="_blank" rel="noopener">{k + 1}</a>' for k, u in enumerate(a.get("source_urls") or []))}</p></details></section>'''
    gaps = ''.join(f'<li>{e(g)}</li>' for g in p.get('gaps') or [])
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Accountability · Who gets paid</span><h1>Who gets paid: tourism agencies</h1>
    <p class="lede">Every payment by the three agencies that spend Bay County's tourist development tax on marketing, from the monthly check registers kept by the Clerk of Court. The county's own payments are on the <a href="/public-money/contracts">Contracts</a> page.</p></div>
    <div class="stamp">{PDF_BTN}<span>Registers through July 2026</span></div></header>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>Where the bed tax goes after the county</h2>
    <ol class="ex-steps"><li><b>Visitors pay a 5% bed tax</b> on hotel and rental stays. Part of it pays three agencies that market each tourism area: Panama City Beach, Panama City and Mexico Beach.</li>
      <li><b>The Clerk pays their bills.</b> Each agency's payments are listed in the Clerk's monthly check register. That's what this page shows: {money(tot)} in payments over the months covered. A few months were never posted; they're listed under Sources and gaps.</li>
      <li><b>Some bills hide the details.</b> Credit card payments and payroll services show as one payment; what was bought isn't listed. Payments to individual people are counted but not named.</li></ol></div></section>
  <div class="callout">In January 2026 the Clerk of Court published an <a href="https://apps.baycoclerk.com/Web_File_Repo/bocc_finance/Panama_City_Beach_TDC_CVB_Public_CAP.pdf" target="_blank" rel="noopener">action plan for Visit Panama City Beach</a>, describing a criminal investigation and forensic audit and putting the agency's payments under the Clerk's review. The payments here are listed as recorded; this site makes no finding about any of them.</div>
  <div class="vt-filters mt-f two"><label class="vf"><span>Agency</span><select id="wpA" data-param="agency">{tabs}</select></label><label class="vf"><span>Search payees</span><input id="wpQ" type="search" placeholder="e.g. Meta, printing, hotel" data-param="q"></label></div>
  {secs}
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">Sources and gaps</h2></div>
    <p>The Bay County Clerk of Court's monthly "Check Register – Sorted by Dollar Amount," attached to County Commission agendas. Most months come from the Clerk's public records search as text PDFs; one month (December 2024) was only available as a scan and was read by OCR. Every month was added up and checked against the register's printed totals for each agency.</p>
    <p>No city or the School Board posts a check register. You can <a href="/records-request">request one</a>; the request generator has them ready.</p>
    <details class="gaps"><summary>What we couldn't find ({len(p.get("gaps") or [])})</summary><ul>{gaps}</ul></details></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>
(() => {{ const a = document.getElementById('wpA'), q = document.getElementById('wpQ'), u = new URLSearchParams(location.search);
  if (u.get('agency')) a.value = u.get('agency');
  addEventListener('hashchange', () => {{ const t = document.getElementById(location.hash.slice(1)); if (t && t.closest('details')) {{ t.closest('details').open = true; t.scrollIntoView({{block: 'center'}}); }} }});
  const run = () => {{ document.querySelectorAll('.wp-ag').forEach(s => s.hidden = s.dataset.ag !== a.value); const t = q.value.trim().toLowerCase();
    document.querySelectorAll('.wp-ag:not([hidden]) tbody tr').forEach(tr => tr.hidden = !!t && !tr.dataset.v.includes(t)); }};
  if (u.get('q')) q.value = u.get('q');
  a.addEventListener('change', run); q.addEventListener('input', run); run(); }})();
</script>'''
