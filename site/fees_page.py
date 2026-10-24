"""Fees & utility bills, and Who runs Bay County, for baycounty.me."""
import json, os, html, re
from city_filter import city_bar, data_g, by_city, gkey, KEYS, LABEL

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'data', 'fees', 'fees_pay_officials.json')
e = lambda s: html.escape(str(s if s is not None else ''))


def money(n, d=0):
    if n is None:
        return '—'
    n = float(n)
    return f'${n/1e6:,.1f}M' if abs(n) >= 1e6 else f'${n:,.{d}f}'


def a(u, t='Source'):
    return f'<a class="src" href="{e(u)}" target="_blank" rel="noopener">{t}</a>' if u else ''


PDF = '''<div class="stamp"><button type="button" class="pdf-btn" id="pdf"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>Data updated Oct 20, 2026</span></div>'''

# Monthly bill at 5,000 gallons split into comparable parts. Arithmetic from each provider's
# published rates as recorded in fees_pay_officials.json ("calc" field).
BILL_PARTS = {
    'Bay County Utility Services': {'ws': 120.70, 'garbage': None, 'other': 0},
    'City of Panama City': {'ws': 137.28, 'garbage': 45.91, 'other': 0},
    'City of Panama City Beach': {'ws': 87.42, 'garbage': None, 'other': 0},
    'City of Lynn Haven': {'ws': 104.90, 'garbage': 24.86, 'other': 0},
    'City of Callaway': {'ws': 99.31, 'garbage': 13.00, 'other': 4.80},
    'City of Springfield': {'ws': 139.53, 'garbage': 37.67, 'other': 3.00},
    'City of Mexico Beach': {'ws': 104.78, 'garbage': 40.00, 'other': 3.12},
}
OTHER_NOTE = {'City of Callaway': '10% franchise fee on water ($3.80) and $1 stormwater', 'City of Springfield': '$3 stormwater', 'City of Mexico Beach': '7% utility tax on water'}


def fee_govs(x):
    """GOVS keys of the government(s) that levy an assessment ('City of Callaway / City of Springfield' -> cw, sp).
    Special districts outside any city get none, so they always show."""
    en = lambda p: re.sub(r'^Ciudad de ', 'City of ', re.sub(r'^Condado de Bay', 'Bay County', p.strip()))  # the Spanish twin's data
    return [k for k in (gkey(en(p.split('(')[0].split(' - ')[0])) for p in x['government'].split('/')) if k]


def fees_page():
    d = json.load(open(SRC))
    T = lambda tid, t: f'<span class="term" data-term="{tid}">{t}</span>'
    tot = d['assessment_roll_totals']
    # assessments table
    rows, levied = '', []
    for x in d['assessments']:
        r = x.get('roll_2025')
        r = r[0] if isinstance(r, list) and r else (r if isinstance(r, dict) else {})
        if not r.get('total_levied'):
            continue
        common = (r.get('most_common_amounts') or [{}])[0]
        levied.append((fee_govs(x), x.get('category') or '', r['total_levied']))
        rows += f'''<tr{data_g(*fee_govs(x))}><td class="wrap"><b>{e(re.sub(r"\s*\(levy codes? [^)]*\)", "", x["name"]))}</b><br><span class="muted small">{e(x["government"].split("(")[0].strip())}</span></td><td class="wrap small">{e(x.get("rate") or x.get("how_charged", ""))}</td><td class="num">{money(common.get("amount"), 2)}</td><td class="num">{r.get("parcels_billed", 0):,}</td><td class="num">{money(r.get("total_levied"))}</td><td>{a(x.get("source_url"))}</td></tr>'''
    # utility bills
    ub = []
    for u in d['utility_rates']:
        key = next((k for k in sorted(BILL_PARTS, key=len, reverse=True) if u['provider'].startswith(k)), None)
        if not key or not u.get('bill_5000gal'):
            continue
        ub.append((key, u, BILL_PARTS[key]))
    ub.sort(key=lambda t: -(t[2]['ws'] + (t[2]['garbage'] or 0) + t[2]['other']))
    mx = max(p['ws'] + (p['garbage'] or 0) + p['other'] for _, _, p in ub)
    bars = ''
    for k, u, p in ub:
        t = p['ws'] + (p['garbage'] or 0) + p['other']
        segs = [(p['ws'], 'var(--s1)'), (p['garbage'] or 0, 'var(--s2)'), (p['other'], 'var(--s4)')]
        bars += f'''<div class="hb"{data_g(k)}><span class="hb-n">{e(k.replace("City of ", ""))}<em> {"water, sewer" + (", garbage" if p["garbage"] else " (garbage not included)")}</em></span><span class="hb-track"><span class="stackbar mini" style="width:{t/mx*100:.1f}%">{"".join(f'<span class="seg" style="flex:{v} 1 0;background:{c}"></span>' for v, c in segs if v)}</span></span><span class="hb-v">${t:,.2f}</span></div>'''
    utbl = ''.join(f'''<tr{data_g(k)}><th scope="row">{e(u["provider"])}<br><span class="muted small">{e(u.get("area", ""))}</span></th><td class="num">${p["ws"]:,.2f}</td><td class="num">{"$%.2f" % p["garbage"] if p["garbage"] else "—"}</td><td class="num">{"$%.2f" % p["other"] if p["other"] else "—"}</td><td class="num"><b>${p["ws"] + (p["garbage"] or 0) + p["other"]:,.2f}</b></td><td class="wrap small">{e(OTHER_NOTE.get(k, ""))} {e(u.get("calc", ""))}<br><span class="muted">Effective: {e(u.get("effective") or "not stated")}</span> {a(u.get("source_url"))}</td></tr>''' for k, u, p in ub)
    gaps = ''.join(f'<li>{e(g)}</li>' for g in d['gaps'] if not re.search(r'salar|pay|roster|term|school board|manager', g, re.I))
    gk = [k for k in KEYS if any(k in g for g, _, _ in levied) or any(gkey(b) == k for b, _, _ in ub)]
    fee = lambda k, cat=None: sum(v for g, c, v in levied if k in g and (cat is None or c == cat))

    def per(countywide, fn):  # a headline figure per city, from the fee rows on this page
        return by_city({'': countywide, **{k: fn(k) for k in gk}})
    # the line under each figure: its countywide wording, or the chosen government's name once a city is picked.
    # The countywide wording stays as written so the Spanish page's phrase pairs still translate it.
    sub = lambda t: f'<span class="cw-all">{t}</span><span class="s cw-one" data-city-name></span>'
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Public Money · Fees &amp; Bills</span><h1>Fees on your tax bill, and what water and garbage cost</h1>
    <p class="lede">Beyond property tax, your tax bill can carry flat fees for fire service, stormwater and lighting. Your utility bill adds water, sewer and garbage. Here's what each government charges.</p></div>{PDF}</header>
  {city_bar(gk, hide=True)}
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>Taxes vs. fees</h2>
    <ol class="ex-steps">
      <li><b>Property tax depends on your home's value.</b> A bigger taxable value means a bigger tax.</li>
      <li><b>Fees on the tax bill are mostly flat.</b> {T('non-ad-valorem', 'Non-ad valorem assessments')} charge per home, per parcel or by building size for a specific service, like fire protection or stormwater drainage. They're not affected by homestead exemptions or Amendment 3.</li>
      <li><b>Utility bills are separate.</b> Water, sewer and garbage are billed monthly by your city or the county, based on how much you use.</li>
    </ol>
    <p><a href="/my-address/">Look up the exact fees on your parcel →</a></p></div></section>
  <div class="kpis">
    <div class="kpi"><span class="eyebrow">Fees on Bay County tax bills</span><span class="v"{per(money(tot["county_government"]["total"] + tot["municipalities"]["total"] + tot["independent_special_districts"]["total"]), lambda k: money(fee(k)))}>{money(tot["county_government"]["total"] + tot["municipalities"]["total"] + tot["independent_special_districts"]["total"])}</span>{sub('<span class="s">FY2026 tax roll, all governments</span>')}</div>
    <div class="kpi"><span class="eyebrow">City fire assessments</span><span class="v"{per(money(tot["municipalities"]["fire"]), lambda k: money(fee(k, 'fire')))}>{money(tot["municipalities"]["fire"])}</span>{sub('<span class="s">Panama City, PCB and Springfield</span>')}</div>
    <div class="kpi"><span class="eyebrow">Stormwater fees</span><span class="v"{per(money(tot["municipalities"]["drainage_stormwater"] + tot["county_government"]["drainage_stormwater"]), lambda k: money(fee(k, 'stormwater')))}>{money(tot["municipalities"]["drainage_stormwater"] + tot["county_government"]["drainage_stormwater"])}</span>{sub('<span class="s">County and cities</span>')}</div>
    <div class="kpi"><span class="eyebrow">Garbage on the tax bill</span><span class="v">$0</span><span class="s">Billed on utility bills instead</span></div>
  </div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="tb">Fees on the tax bill</h2><span class="muted">FY2026 bills (2025 tax roll)</span></div>
    <div class="tablewrap" data-city-empty="No fees on the tax bill from {{city}}."><table class="tx-table"><thead><tr><th scope="col">Fee</th><th scope="col">How it's charged</th><th scope="col" class="num">Most common bill</th><th scope="col" class="num">Parcels billed</th><th scope="col" class="num">Total</th><th scope="col">Source</th></tr></thead><tbody>{rows}</tbody></table></div>
    <p class="note">Unincorporated Bay County's fire service is a property tax (1.38 mills), not a flat fee, so it's on the <a href="/public-money/tax-dollars">tax dollars page</a>. Counts and totals come from the Florida Department of Revenue's parcel-level file for Bay County. {a("https://floridarevenue.com/property/dataportal/Documents/PTO%20Data%20Portal/Tax%20Roll%20Data%20Files/NAV/2025/NAV%20D/NAVD132506.TXT", "DOR file")}</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="ub">A typical monthly utility bill</h2><span class="muted">5,000 gallons of water, 3/4-inch meter</span></div>
    <div class="hbars" data-city-empty="No utility rates found online for {{city}}.">{bars}</div>
    <ul class="leg mini"><li><i style="background:var(--s1)"></i><span>Water and sewer</span></li><li><i style="background:var(--s2)"></i><span>Garbage</span></li><li><i style="background:var(--s4)"></i><span>Stormwater, fees and utility taxes</span></li></ul>
    <details class="tbl-toggle" open><summary>How each bill is calculated</summary><div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Provider</th><th scope="col" class="num">Water and sewer</th><th scope="col" class="num">Garbage</th><th scope="col" class="num">Other</th><th scope="col" class="num">Total</th><th scope="col">Calculation</th></tr></thead><tbody>{utbl}</tbody></table></div></details>
    <p class="note">Bills are worked out from each provider's published rate sheet. Panama City Beach's garbage rate and Parker's utility rates weren't found online. Panama City's own notice gives an "average" bill equal to its base charges alone, so its usage charges may include an allowance the notice doesn't describe.</p></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="gaps">What we couldn't find</h2></div><ul class="plain">{gaps}</ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<style>.cw-one{{display:none}}:root[data-city]:not([data-city=""]) .cw-all{{display:none}}:root[data-city]:not([data-city=""]) .cw-one{{display:block}}</style>'''


STAFF = re.compile(r'manager|clerk|attorney|chief|director|administrator|treasurer', re.I)


def split_note(h):
    """'Doug Moore (stepped down as chairman...)' -> ('Doug Moore', 'stepped down as chairman...')."""
    if not h:
        return None, ''
    h = re.sub(r'\(([A-Z][a-z]+)\)', r'"\1"', h)  # nickname: William (Chuck) Perdue
    m = re.match(r'\s*([^(;]+?)\s*(?=\(|;|$)', h)
    name = m.group(1) if m else h
    rest = h[len(m.group(0)) if m else len(h):].strip()
    rest = re.sub(r'^\(([^()]*)\)', r'\1', rest).lstrip('; ').replace('); ', '. ').replace('; ', '. ').strip()
    return name, rest


def term_txt(t):
    if not t or t == '—':
        return '', ''
    main, note = split_note(t)
    return main, note


def roster_li(s):
    name, note = split_note(s.get('holder'))
    term, tnote = term_txt(s.get('term_end'))
    notes = '. '.join(x for x in (note, tnote) if x)
    if not s.get('elected') and not STAFF.search(s['seat']):
        notes = ('Appointed to the seat. ' + notes).strip()
    who = f'<b>{e(name)}</b>' if name else '<span class="vacant">Not published online</span>'
    return (f'<li><span class="seat">{e(s["seat"])}</span><span class="who">{who}'
            f'{f"<small>{e(notes)}</small>" if notes else ""}</span>'
            f'<span class="r-term">{"until " + e(term) if term else ""}</span></li>')


def who_page():
    d = json.load(open(SRC))
    blocks = ''
    for g in d['governments']:
        seats = g.get('seats', [])
        board = [s for s in seats if s.get('elected') or not STAFF.search(s['seat'])]
        staff = [s for s in seats if s not in board]
        ft = g.get('ftes'); ftv = ft.get('value') if isinstance(ft, dict) else ft
        links = ' · '.join(x for x in [
            f'{ftv:,g} employees' if ftv else '',
            f'<a href="{e(g.get("website"))}" target="_blank" rel="noopener">Website</a>' if g.get('website') else '',
            f'<a href="{e(g.get("contact_url"))}" target="_blank" rel="noopener">Contact</a>' if g.get('contact_url') else '',
            a(g.get('source_url'))] if x)
        blocks += f'''<article class="card gov"{data_g(g["name"])}><h3>{e(g["name"])}</h3><p class="muted small">{e(g.get("form", ""))}</p>
          <h4 class="roster-h">Elected board</h4><ul class="roster">{"".join(roster_li(s) for s in board)}</ul>
          {f'<h4 class="roster-h">Appointed staff</h4><ul class="roster">{"".join(roster_li(s) for s in staff)}</ul>' if staff else ""}
          <p class="gov-ft small">{links}</p></article>'''

    def officer(c):
        term, _ = term_txt(c.get('term_end'))
        el, eln = term_txt(c.get('elected'))
        p1, p2 = c.get('salary_fy2025_26'), c.get('salary_fy2026_27')
        return f'''<article class="card officer" data-g="county"><span class="eyebrow">{e(c["office"])}</span><h3>{e(split_note(c["holder"])[0])}</h3>
          <dl class="off-kv"><div><dt>Term ends</dt><dd>{e(term or "—")}</dd></div><div><dt>Chosen</dt><dd>{e(el or "—")}{f' <small>({e(eln)})</small>' if eln else ""}</dd></div>
          <div><dt>Pay FY2026</dt><dd class="num">{money(p1)}</dd></div><div><dt>Pay FY2027</dt><dd class="num">{money(p2)}</dd></div></dl>
          <p class="gov-ft small">{f'<a href="{e(c["website"])}" target="_blank" rel="noopener">Website</a> · ' if c.get("website") else ""}{a(c.get("source_url"))}</p></article>'''
    co = ''.join(officer(c) for c in d['constitutional_officers'])
    seen = set(); prow = ''
    for p in sorted(d['pay'], key=lambda p: -(p['annual'] or 0)):
        k = (p['government'], p['title'], p.get('name'))
        if k in seen or not p.get('annual'):
            continue
        seen.add(k)
        prow += (f'<tr{data_g(p["government"])}><th scope="row"><b>{e(p["title"])}</b>{f"<small>{e(p.get("name"))}</small>" if p.get("name") else ""}</th>'
                 f'<td>{e(p["government"])}<small>{e(p["year"])}</small></td><td class="num">{money(p["annual"])}</td>'
                 f'<td class="wrap small muted">{e(p.get("basis", ""))} {a(p.get("source_url"))}</td></tr>')
    gaps = ''.join(f'<li>{e(g)}</li>' for g in d['gaps'] if re.search(r'salar|pay|roster|term|school board|manager', g, re.I))
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Who Runs Bay County</span><h1>Who runs Bay County</h1>
    <p class="lede">Bay County has one county government, seven cities, a school district and five independently elected county officers. Here's who holds each seat, who's appointed to run things day to day, and what top officials are paid.</p></div>{PDF}</header>
  {city_bar([k for k in KEYS if any(gkey(g["name"]) == k for g in d["governments"])], hide=True, note='Bay County includes the five county officers')}
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>Who's in charge of what</h2>
    <ol class="ex-steps">
      <li><b>Elected boards set policy and budgets.</b> The County Commission, each city commission or council, and the School Board vote on budgets, tax rates and big contracts.</li>
      <li><b>Appointed managers run operations.</b> A county manager or city manager, hired by the board, runs departments and staff. Springfield and Parker have no manager; the board oversees staff directly and a city clerk handles administration.</li>
      <li><b>Five county officers are elected on their own.</b> The Sheriff, Property Appraiser, Tax Collector, Clerk of Court and Supervisor of Elections each run their own office. The County Commission funds most of their budgets. Their pay is set by a state formula.</li>
    </ol>
    <p><a href="/my-address/">Find who represents your address →</a></p></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="co">Countywide elected officers</h2><span class="muted">Pay set by state formula</span></div>
    <div class="officers" data-city-empty="The five county officers serve all of Bay County, {{city}} included. Choose Bay County to see them.">{co}</div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="govs">Governments</h2><span class="muted">Elected boards and the staff they appoint</span></div><div class="gov-grid">{blocks}</div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="pay">What officials are paid</h2><span class="muted">From state salary reports, budgets and contracts</span></div>
    <div class="tablewrap" data-city-empty="No pay records found for {{city}} officials yet."><table class="tx-table pay-table"><thead><tr><th scope="col">Position</th><th scope="col">Government</th><th scope="col" class="num">Annual</th><th scope="col">Basis</th></tr></thead><tbody>{prow}</tbody></table></div>
    <p class="note">Where a budget shows only one combined line for a whole city commission, that total is listed rather than divided among members.</p></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="gaps">What we couldn't find</h2></div><ul class="plain">{gaps}</ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">'''
