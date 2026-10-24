"""Contracts & Vendors page for baycounty.me (data: data/contracts/contracts.json)."""
import json, os, re, html
from collections import defaultdict
import vendors as V
from change_growth import growth_section
from city_filter import city_bar, data_g, by_city, gkey

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'data', 'contracts', 'contracts.json')
e = lambda s: html.escape(str(s if s is not None else ''))

METHODS = [  # (bucket, regex) checked in order
    ('Emergency', r'emergenc'),
    ('Sole source', r'sole.?source|single.?source'),
    ('Cooperative / piggyback', r'piggyback|cooperative|sourcewell|omnia|state contract|fsa|another government'),
    ('Task order on existing contract', r'task order|work authorization|continuing'),
    ('Renewal or existing agreement', r'renewal|existing agreement|amendment|extension'),
    ('Competitive bid', r'sealed bid|invitation to bid|\bitb\b|low(est)? bidder|base bid'),
    ('Qualifications or proposals', r'rfq|rfp|qualifications|proposals'),
    ('Intergovernmental', r'intergovernmental|interlocal|fdot|agency'),
    ('Not stated', r'not stated|^$'),
]
SHORT = {'Bay County BOCC': 'Bay County', 'City of Panama City': 'Panama City', 'City of Panama City Beach': 'Panama City Beach', 'City of Lynn Haven': 'Lynn Haven',
         'City of Callaway': 'Callaway', 'City of Springfield': 'Springfield', 'City of Parker': 'Parker', 'City of Mexico Beach': 'Mexico Beach'}


def bucket(m):
    m = (m or '').lower()
    for b, rx in METHODS:
        if re.search(rx, m):
            return b
    return 'Other'


def vkey(v):
    v = (v or '').lower()
    v = re.sub(r'\(.*?\)', '', v)
    v = re.sub(r'[.,&]', ' ', v)
    v = re.sub(r'\b(inc|llc|co|corp|corporation|company|the|of|lp|llp|pa|pllc|ltd|dba)\b', ' ', v)
    return re.sub(r'\s+', ' ', v).strip()


def money(n):
    if n is None:
        return '—'
    sign, n = ('\u2212' if n < 0 else ''), abs(n)
    return sign + (f'${n/1e6:,.1f}M' if n >= 1e6 else (f'${n/1e3:,.0f}K' if n >= 1e3 else f'${n:,.0f}'))


def vendor_profiles(d, cs):
    """Everything on the site about each company: awards, change orders, emergency purchases, payments in the
    check registers' top-payee lists, campaign gifts from the company and recorded votes on its contracts."""
    P = {}
    def prof(raw):
        vid, n, t = V.resolve(raw)
        p = P.setdefault(vid, {'id': vid, 'n': n, 't': t, 'aka': set(), 'aw': [], 'co': [], 'em': [], 'paid': [], 'gifts': [], 'votes': []})
        if raw and raw.strip() != n:
            p['aka'].add(re.sub(r'\s*\(.*?\)\s*', ' ', raw).strip())
        return p
    for i, c in enumerate(sorted(cs, key=lambda c: c.get('date') or '', reverse=True)):
        prof(c['vendor'])['aw'].append({'g': SHORT.get(c['government'], c['government']), 'a': c['amount'], 'p': c.get('purpose') or '', 'd': c.get('date') or '',
                                         'm': c['b'], 'u': c.get('source_url') or ''})
    for x in d['change_orders']:
        prof(x.get('vendor'))['co'].append({'g': SHORT.get(x['government'], x['government']), 'a': x.get('change_amount'), 'p': x.get('project') or '',
                                            'pct': x.get('pct_of_original'), 'd': x.get('date') or '', 'u': x.get('source_url') or ''})
    for x in d['emergency_purchases']:
        prof(x.get('vendor'))['em'].append({'g': SHORT.get(x['government'], x['government']), 'a': x.get('amount'), 'p': x.get('purpose') or '',
                                            'd': x.get('date') or '', 'u': x.get('source_url') or ''})
    for r in d['registers']:
        tv = r.get('top_vendors') or []
        for rank, v in enumerate(tv, 1):
            lh = 'Lynn Haven' in r['government']
            prof(v['vendor'])['paid'].append({'g': SHORT.get(r['government'], r['government']), 'fy': r['fy'], 'a': v['amount'], 'rank': rank, 'of': len(tv),
                                              'cover': 'checks of about $10,000 or more' if lh else f'{len(r.get("months_covered") or [])} of 12 months'})
    try:  # campaign gifts and votes come from the money map's data, so both pages agree
        import money_map as mm
        M = mm.map_data()
    except FileNotFoundError:
        M = None
    if M:
        O, DN = M['officials'], {x['id']: x['n'] for x in M['donors']}
        for g in M['gifts']:
            vid = V.resolve(DN[g['d']])[0]
            if vid in P:  # only companies that appear in the contract records
                o = O[g['o']]
                P[vid]['mm'] = DN[g['d']]  # the name the money map uses, for its search link
                P[vid]['gifts'].append({'o': o['n'], 'off': o['off'], 'a': g['a'], 'same': g['same'], 'dates': g['dates']})
        for v in M['vgroups']:
            vid = V.resolve(DN[v['d']])[0]
            if vid in P:
                P[vid]['votes'].append({'d': v['date'], 'g': mm.GSHORT.get(v['g'], v['g']), 'h': v['h'], 'a': v['amount'], 'tally': v['tally'], 'outcome': v['outcome'],
                                        'consent': v['consent'], 'u': v['url'], 'roll': [{'n': m['n'], 'vote': m['vote'], 'gift': m.get('gift')} for m in v['roll']]})
    for p in P.values():
        seen = {V.key(p['n'])}  # one spelling per distinct form; skip ones that differ only by Inc/LLC or punctuation
        aka = []
        for a in sorted(p['aka'], key=len):
            if V.key(a) not in seen and not a.isupper():  # all-caps forms are register truncations
                seen.add(V.key(a)); aka.append(a)
        p['aka'] = sorted(aka)
        p['gifts'].sort(key=lambda g: -g['a'])
        p['tot'] = round(sum(a['a'] for a in p['aw']), 2)
    return P


def contracts_page(out_dir):
    d = json.load(open(SRC))
    cs = [c for c in d['contracts'] if c.get('amount')]
    for c in cs:
        c['b'] = bucket(c.get('method'))
    for c in cs:
        c['vid'], c['vn'], c['vt'] = V.resolve(c['vendor'])
    # vendor totals (awards), one row per company however its name is spelled; other governments and unnamed vendors left out
    def vendor_bars(xs):
        vt = defaultdict(lambda: {'n': 0, 'amt': 0, 'name': '', 'id': '', 'govs': set()})
        for c in xs:
            if c['vt'] != 'business':
                continue
            v = vt[c['vid']]
            v['n'] += 1; v['amt'] += c['amount']; v['name'] = c['vn']; v['id'] = c['vid']; v['govs'].add(SHORT.get(c['government'], c['government']))
        top_v = sorted(vt.values(), key=lambda v: -v['amt'])[:15]
        mx = top_v[0]['amt'] if top_v else 1
        return ''.join(f'''<div class="hb vlink" role="button" tabindex="0" data-v="{e(v["id"])}"><span class="hb-n">{e(v["name"])} <em>{v["n"]} award{"s" if v["n"] > 1 else ""} · {e(", ".join(sorted(v["govs"])))}</em></span><span class="hb-track"><span class="hb-bar" style="width:{max(.5, v["amt"]/mx*100):.1f}%"></span></span><span class="hb-v">{money(v["amt"])}</span></div>''' for v in top_v)
    # the governments with contracts, and each one's own records (the city bar at the top switches between them)
    ORDER = ['county', 'schools', 'pc', 'pcb', 'lh', 'cw', 'sp', 'parker', 'mb']
    gk = sorted({gkey(c['government']) for c in cs} - {None}, key=ORDER.index)
    mine = lambda xs, k: [x for x in xs if gkey(x.get('government')) == k]
    vbars = vendor_bars(cs)
    vbars_by = by_city({'': vbars, **{k: vendor_bars(mine(cs, k)) for k in gk}})
    # methods
    def method_bars(xs):
        mt = defaultdict(lambda: [0, 0])
        for c in xs:
            mt[c['b']][0] += 1; mt[c['b']][1] += c['amount']
        ta = sum(c['amount'] for c in xs) or 1
        mm = max([v[1] for v in mt.values()] or [1]) or 1
        return ''.join(f'''<div class="hb"><span class="hb-n">{e(k)} <em>{v[0]} contracts</em></span><span class="hb-track"><span class="hb-bar" style="width:{max(.5, v[1]/mm*100):.1f}%"></span></span><span class="hb-v">{money(v[1])} <em>{v[1]/ta:.0%}</em></span></div>''' for k, v in sorted(mt.items(), key=lambda x: -x[1][1]))
    mt = defaultdict(lambda: [0, 0])
    for c in cs:
        mt[c['b']][0] += 1; mt[c['b']][1] += c['amount']
    tot_amt = sum(c['amount'] for c in cs)
    mbars = method_bars(cs)
    mbars_by = by_city({'': mbars, **{k: method_bars(mine(cs, k)) for k in gk}})
    def kpi(fn):
        return by_city({'': fn(cs, d['change_orders'], d['emergency_purchases']),
                        **{k: fn(mine(cs, k), mine(d['change_orders'], k), mine(d['emergency_purchases'], k)) for k in gk}})
    bid = lambda xs: sum(c['amount'] for c in xs if c['b'] == 'Competitive bid') / (sum(c['amount'] for c in xs) or 1)
    # check registers
    regs = ''
    for r in d['registers']:
        tv = r.get('top_vendors') or []
        if not tv:
            continue
        rm = tv[0]['amount']
        cover = f'{len(r.get("months_covered", []))} of 12 months' if r.get('months_covered') else ''
        regs += f'''<details class="tbl-toggle"{data_g(r["government"])}{" open" if r is d["registers"][-1] or r.get("fy") == 2025 else ""}><summary>{e(SHORT.get(r["government"], r["government"]))}, FY{e(r["fy"])} {("· " + cover) if cover else ""}</summary><div class="hbars small">''' + ''.join(
            f'''<div class="hb"><span class="hb-n">{e(v["vendor"])}</span><span class="hb-track"><span class="hb-bar" style="width:{max(.5, v["amount"]/rm*100):.1f}%"></span></span><span class="hb-v">{money(v["amount"])}</span></div>''' for v in tv[:15]) + \
            f'''</div><p class="note">{"Lynn Haven's warrant lists in its agenda packets, which show only checks of about $10,000 or more and cut payee names short; smaller checks and electronic payments aren't included. No purpose is given for individual checks." if "Lynn Haven" in r["government"] else "The Bay County Clerk of Court's monthly check register, attached to County Commission agendas."} {f'Missing months: {", ".join(r["months_missing"])}.' if r.get("months_missing") else ""} <a class="src" href="{e(r["url"])}" target="_blank" rel="noopener">Source</a></p></details>'''
    # change orders
    co = sorted(d['change_orders'], key=lambda x: -(x.get('change_amount') or 0))
    co_rows = ''.join(f'''<tr{data_g(x["government"])}><td>{e(SHORT.get(x["government"], x["government"]))}</td><td class="wrap"><b>{e(x.get("vendor"))}</b><br><span class="small muted">{e(x.get("project"))}</span></td><td class="num">{money(x.get("original_amount"))}</td><td class="num">{money(x.get("change_amount"))}</td><td class="num">{f'{x["pct_of_original"]:.0f}%' if isinstance(x.get("pct_of_original"), (int, float)) else "—"}</td><td class="wrap small">{e(x.get("reason"))}</td><td class="small">{e(x.get("date"))} <a class="src" href="{e(x.get("source_url"))}" target="_blank" rel="noopener">Source</a></td></tr>''' for x in co)
    em = ''.join(f'''<li{data_g(x["government"])}><b>{e(SHORT.get(x["government"], x["government"]))}, {e(x.get("date"))}: {money(x.get("amount"))}</b> to {e(x.get("vendor"))} for {e(x.get("purpose"))}. <span class="muted">{e(x.get("basis", ""))}</span> <a class="src" href="{e(x.get("source_url"))}" target="_blank" rel="noopener">Source</a></li>''' for x in sorted(d['emergency_purchases'], key=lambda x: x.get('date') or ''))
    th = ''.join(f'''<li{data_g(x["government"])}><b>{e(SHORT.get(x["government"], x["government"]))}.</b> {e(x["rule"])} <a class="src" href="{e(x.get("source_url"))}" target="_blank" rel="noopener">Source</a></li>''' for x in d['thresholds'])
    # ledger data for JS
    rows = [{'g': SHORT.get(c['government'], c['government']), 'v': c['vendor'], 'id': c['vid'], 'a': c['amount'], 'p': c.get('purpose') or '', 'd': c.get('date') or '', 'm': c['b'], 'mf': c.get('method') or '',
             'u': c.get('source_url') or '', 'n': c.get('notes') or ''} for c in sorted(cs, key=lambda c: -c['amount'])]
    vp = sorted(vendor_profiles(d, cs).values(), key=lambda p: p['n'].lower())
    json.dump({'rows': rows, 'vp': vp}, open(os.path.join(out_dir, 'data', 'contracts-page.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    open(os.path.join(out_dir, 'assets', 'contracts.js'), 'w').write(open(os.path.join(HERE, 'contracts.js')).read())
    govs = sorted(set(r['g'] for r in rows))
    cot = sum(x.get('change_amount') or 0 for x in d['change_orders'])
    T = lambda tid, t: f'<span class="term" data-term="{tid}">{t}</span>'
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Public Money · Contracts</span><h1>Who gets the contracts</h1>
    <p class="lede">The big contracts Bay County and its cities approved since October 2022: who won them, how they were awarded, which ones grew, and who the county actually paid the most.</p></div>
    <div class="stamp"><button type="button" class="pdf-btn" id="pdf"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>Agendas Oct 2022 to Oct 2026<br>Data updated Oct 20, 2026</span></div></header>
  {city_bar(gk, hide=True)}
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>How a government picks a contractor</h2>
    <ol class="ex-steps">
      <li><b>Big purchases must be bid.</b> Above a dollar limit ($150,000 for the county, $100,000 for Panama City), the government advertises the job and usually takes the lowest qualified bid.</li>
      <li><b>Engineers and architects are chosen on qualifications</b> (an RFQ), then the price is negotiated. Many jobs go to firms already under a "continuing services" contract as task orders.</li>
      <li><b>Shortcuts exist, with rules.</b> A government can "piggyback" on another government's bid, use a sole source when only one vendor can do it, or buy in an emergency and get approval afterward.</li>
      <li><b>Contracts can grow.</b> A {T('change-order', 'change order')} adds cost or time after signing, and big ones need board approval.</li>
    </ol></div></section>
  <div class="kpis">
    <div class="kpi"><span class="eyebrow">Contracts tracked</span><span class="v"{kpi(lambda c, o, m: len(c))}>{len(cs)}</span><span class="s"{kpi(lambda c, o, m: money(sum(x["amount"] for x in c)) + " in awards")}>{money(tot_amt)} in awards</span></div>
    <div class="kpi"><span class="eyebrow">Competitively bid</span><span class="v"{kpi(lambda c, o, m: f"{bid(c):.0%}")}>{mt["Competitive bid"][1]/tot_amt:.0%}</span><span class="s">of award dollars</span></div>
    <div class="kpi"><span class="eyebrow">Change orders</span><span class="v"{kpi(lambda c, o, m: len(o))}>{len(d["change_orders"])}</span><span class="s"{kpi(lambda c, o, m: money(sum(x.get("change_amount") or 0 for x in o)) + " added to contracts")}>{money(cot)} added to contracts</span></div>
    <div class="kpi"><span class="eyebrow">Emergency purchases</span><span class="v"{kpi(lambda c, o, m: len(m))}>{len(d["emergency_purchases"])}</span><span class="s">Approved after the fact</span></div>
  </div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="top">Biggest contract winners</h2><span class="muted">Total awards in this list, <span data-city-name="all governments">all governments</span></span></div><div class="hbars"{vbars_by}>{vbars}</div>
    <p class="note">Award amounts as proposed on agendas. Payments to other governments and to insurance pools that governments own (such as FDOT for road work, or the Florida League of Cities and PGIT for insurance) are left out of this ranking. Each company is counted once, however agendas spell its name. Tap a company to see everything on it.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="company">Look up a company</h2><span class="muted">Every record on this site for one company: contracts, payments, change orders, campaign gifts and votes</span></div>
    <div class="filters-row"><input id="vpQ" list="vpList" type="search" placeholder="Type a company name" aria-label="Company name" autocomplete="off"><datalist id="vpList"></datalist></div>
    <div id="vpCard" class="vp-card" aria-live="polite"><p class="muted">Pick a company, or tap a name in the list above or in the contracts table below.</p></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="paid">Who actually got paid the most</h2><span class="muted">From Bay County's check registers and Lynn Haven's warrant lists</span></div><div data-city-empty="{{city}} doesn't publish a check register online, so there's no payee list for it here. It can be requested.">{regs}</div>
    <p class="note">Cash paid in the period covered, not contract value. Payroll, benefits, transfers to other offices and pass-through payments are left out. Other cities don't publish check registers online; they can be requested.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="how">How contracts were awarded</h2><span class="muted">By award dollars</span></div><div class="hbars"{mbars_by}>{mbars}</div>
    <p class="note">Based on how each agenda item describes the award. "Not stated" means the agenda didn't say.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="all">Every contract in this list</h2><span class="muted" id="ctCount" aria-live="polite">Loading contracts…</span></div>
    <div class="filters-row"><select id="ctY" aria-label="Year"><option value="">All years</option></select><input id="ctQ" type="search" data-param="q" placeholder="Search vendor or project" aria-label="Search contracts">
      <select id="ctG" aria-label="Government" data-city-link hidden><option value="">All governments</option>{''.join(f"<option>{e(g)}</option>" for g in govs)}</select>
      <select id="ctM" aria-label="How awarded" data-param="method"><option value="">Any method</option>{''.join(f"<option>{e(k)}</option>" for k, _ in METHODS)}<option>Other</option></select>
      <button type="button" class="pill sm" id="ctCsv">Download CSV</button></div>
    <div class="tablewrap"><table class="tx-table" id="ctT" data-tt="own"><thead><tr><th scope="col">Government</th><th scope="col">Vendor</th><th scope="col">For</th><th scope="col" class="num">Amount</th><th scope="col">How awarded</th><th scope="col">Date</th></tr></thead><tbody><tr><td colspan="6" class="muted">Loading contracts…</td></tr></tbody></table></div>
    <button type="button" class="pill" id="ctMore" hidden>Show more</button></section>
  {growth_section(d, f'''<details class="tbl-toggle"><summary>Every change order in this list ({len(d["change_orders"])})</summary>
    <div class="tablewrap" data-city-empty="No change orders recorded for {{city}} yet."><table class="tx-table"><thead><tr><th scope="col">Gov.</th><th scope="col">Vendor and project</th><th scope="col" class="num">Original</th><th scope="col" class="num">Added</th><th scope="col" class="num">Increase</th><th scope="col">Reason</th><th scope="col">Date</th></tr></thead><tbody>{co_rows}</tbody></table></div></details>''')}
  <section class="tx-sec"><div class="sec-hd"><h2 id="em">Emergency purchases</h2></div><ul class="plain" data-city-empty="No emergency purchases recorded for {{city}}.">{em}</ul></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="rules">The bidding rules</h2></div><ul class="plain" data-city-empty="No bidding rules found for {{city}} yet.">{th}</ul></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">How this was compiled, and gaps</h2></div><ul class="plain">{''.join(f"<li>{e(n)}</li>" for n in d["notes"])}</ul>
    <details class="gaps"><summary>What we couldn't find ({len(d["gaps"])})</summary><ul>{''.join(f"<li>{e(g)}</li>" for g in d["gaps"])}</ul></details></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/contracts.js" defer></script>'''
