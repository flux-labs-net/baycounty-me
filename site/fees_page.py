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

# The colors of a bill's parts, the same on the receipts, the bars and the legend.
PART = {'fire': ('Fire fee', 'var(--salmon)'), 'stormwater': ('Stormwater fee', 'var(--teal)'),
        'ws': ('Water and sewer', 'var(--s1)'), 'garbage': ('Garbage', 'var(--s2)'), 'other': ('Other utility charges', 'var(--s4)')}
AREA_NAME = {'county': 'Outside city limits'}  # the chips' name for each area; Bay County's own fees apply countywide


def fee_govs(x):
    """GOVS keys of the government(s) that levy an assessment ('City of Callaway / City of Springfield' -> cw, sp).
    Special districts outside any city get none, so they always show."""
    en = lambda p: re.sub(r'^Ciudad de ', 'City of ', re.sub(r'^Condado de Bay', 'Bay County', p.strip()))  # the Spanish twin's data
    return [k for k in (gkey(en(p.split('(')[0].split(' - ')[0])) for p in x['government'].split('/')) if k]


def roll(x):
    r = x.get('roll_2025')
    return r[0] if isinstance(r, list) and r else (r if isinstance(r, dict) else {})


def common_amount(x):
    return ((roll(x).get('most_common_amounts') or [{}])[0]).get('amount')


def fee_name(x):
    return re.sub(r'\s*\(levy codes? [^)]*\)', '', x['name'])


def home_fees(d):
    """{gov key: [(category, assessment), ...]}: the fire and stormwater fees a typical home pays, by government.
    Bay County's residential stormwater fee is countywide (its FAQ doesn't limit it to unincorporated parcels)."""
    out = {}
    for x in d['assessments']:
        gs = fee_govs(x)
        if x.get('category') not in ('fire', 'stormwater') or len(gs) != 1 or not common_amount(x) or re.search(r'commercial|comercial', x['name'], re.I):
            continue
        out.setdefault(gs[0], []).append((x['category'], x))
    return out


def district_fees(d):
    """{gov key: [assessment, ...]}: CRA and district fees that only parcels inside the district pay."""
    out = {}
    for x in d['assessments']:
        gs = fee_govs(x)
        if len(gs) == 1 and gs[0] != 'county' and 'special district' in (x.get('category') or '') and common_amount(x):
            out.setdefault(gs[0], []).append(x)
    return out


def bills(d):
    """[(gov key, utility row, parts)] for every provider with a worked-out 5,000-gallon bill, highest first."""
    from govs import GOVS
    def key(prov):  # 'City of Panama City Utilities (...)' -> 'pc', never mistaking Panama City Beach for Panama City
        return next((g['key'] for g in sorted(GOVS, key=lambda g: -len(g.get('util') or '')) if g.get('util') and prov.startswith(g['util'])), None)
    ub = [(key(u['provider']), u, u['bill_parts']) for u in d['utility_rates'] if u.get('bill_5000gal') and u.get('bill_parts')]
    ub = [t for t in ub if t[0]]
    return sorted(ub, key=lambda t: -u_total(t[2]))


def u_total(p):
    return p['water_sewer'] + (p['garbage'] or 0) + (p['other'] or 0)


def dot(part):
    return f'<i class="fb-dot" style="background:{PART[part][1]}"></i>'


def fees_page():
    d = json.load(open(SRC))
    T = lambda tid, t: f'<span class="term" data-term="{tid}">{t}</span>'
    tot = d['assessment_roll_totals']
    hf, df, ub = home_fees(d), district_fees(d), bills(d)
    county = hf.get('county', [])
    areas = [k for k in KEYS if k != 'county' and any(k == b for b, _, _ in ub)] + ['county']
    name = lambda k: AREA_NAME.get(k, LABEL[k])

    def tax_rows(k):
        rows = [(c, x) for c, x in hf.get(k, [])] if k != 'county' else []
        return rows + county  # the county's stormwater fee is on every home's bill

    # one pair of receipts per area: the yearly tax-bill fees and the monthly utility bill
    cards, yearly = '', {}
    for k, u, p in ub:
        tr = tax_rows(k)
        fees = sum(common_amount(x) for _, x in tr)
        yearly[k] = (fees, u_total(p))
        lines = ''.join(f'<li><span>{dot(c)}{e(fee_name(x).replace(" - residential", ""))}<small>{e(x["government"].split("(")[0].strip())}</small></span><b class="num">${common_amount(x):,.2f}</b></li>' for c, x in tr)
        if k == 'county':
            lines += '<li class="fb-none"><span>Fire service<small>A property tax outside city limits (1.38 mills), not a flat fee</small></span><span>tax</span></li>'
        if not any(c == 'fire' for c, _ in tr) and k != 'county':
            lines += '<li class="fb-none"><span>Fire service<small>No fire fee on the tax bill</small></span><span>none</span></li>'
        extra = ''.join(f'<p class="fb-fine">Inside the {e(fee_name(x).replace(" assessment", ""))} area, add ${common_amount(x):,.2f} a year.</p>' for x in df.get(k, []))
        ulines = f'<li><span>{dot("ws")}Water and sewer</span><b class="num">${p["water_sewer"]:,.2f}</b></li>'
        ulines += (f'<li><span>{dot("garbage")}Garbage</span><b class="num">${p["garbage"]:,.2f}</b></li>' if p['garbage']
                   else '<li class="fb-none"><span>Garbage<small>Not on this bill: a private hauler or the city bills it</small></span><span>not included</span></li>')
        if p.get('other'):
            ulines += f'<li><span>{dot("other")}Other charges<small>{e(p.get("other_note") or "")}</small></span><b class="num">${p["other"]:,.2f}</b></li>'
        rank = [b for b, _, _ in ub].index(k) + 1
        place = 'Highest' if rank == 1 else ('Lowest' if rank == len(ub) else f'Number {rank}')
        cards += f'''<div class="fb-area"{data_g(k)} data-k="{k}">
      <div class="fb-receipts">
        <section class="fb-card fb-tax"><span class="eyebrow">On your yearly tax bill</span><h3>Flat fees for {e(name(k)).lower() if k == "county" else "a home in " + e(name(k))}</h3>
          <ul class="fb-lines">{lines}</ul><p class="fb-total"><span>Total a year</span><b class="num">${fees:,.2f}</b></p>
          <p class="fb-fine">The most common bill for a home. The same whatever the home is worth; homestead doesn't lower it.</p>{extra}</section>
        <section class="fb-card"><span class="eyebrow">Your monthly utility bill</span><h3>{e(u["provider"].split("(")[0].strip())}</h3>
          <ul class="fb-lines">{ulines}</ul><p class="fb-total"><span>Total a month</span><b class="num">${u_total(p):,.2f}</b></p>
          <p class="fb-fine">At 5,000 gallons on a 3/4-inch meter. {place} of {len(ub)} areas. {a(u.get("source_url"), "Rate sheet")}</p></section>
      </div>
      <div class="fb-band fb-own"><span>A typical home in {e(name(k)) if k != "county" else "unincorporated Bay County"} pays about<small>tax-bill fees plus 12 months of the utility bill</small></span><b class="num">${fees + 12 * u_total(p):,.0f}<small> a year</small></b></div>
      <div class="fb-band fb-rent"><span>A renter in {e(name(k)) if k != "county" else "unincorporated Bay County"} pays about<small>12 months of the utility bill, if it's in your name</small></span><b class="num">${12 * u_total(p):,.0f}<small> a year</small></b></div>
      <p class="fb-fine fb-rent">Renters don't get a tax bill, but your landlord does: its ${fees:,.2f} in yearly fees is usually part of the rent.</p>
    </div>'''

    # every area side by side, the chosen one highlighted
    order = sorted(yearly, key=lambda k: -(yearly[k][0] + 12 * yearly[k][1]))
    mx = max(yearly[k][0] + 12 * yearly[k][1] for k in order)
    cmp_rows = ''
    for k in order:
        _, u, p = next(t for t in ub if t[0] == k)
        tr = tax_rows(k)
        segs = [(sum(common_amount(x) for c, x in tr if c == 'fire'), 'fire'), (sum(common_amount(x) for c, x in tr if c == 'stormwater'), 'stormwater'),
                (12 * p['water_sewer'], 'ws'), (12 * (p['garbage'] or 0), 'garbage'), (12 * (p['other'] or 0), 'other')]
        t = sum(v for v, _ in segs)
        star = '' if p['garbage'] else '*'
        cmp_rows += f'''<li data-k="{k}"><button type="button" class="fb-cmp-n" data-pick="{k}">{e(name(k))}{star}</button><span class="fb-track"><span class="fb-stack" style="width:{t / mx * 100:.1f}%">{"".join(f'<span style="flex:{v:.2f} 1 0;background:{PART[c][1]}"></span>' for v, c in segs if v)}</span></span><b class="num">${t:,.0f}</b></li>'''
    used = [c for c in PART if any(c == cc for k in order for cc, _ in tax_rows(k)) or c in ('ws', 'garbage', 'other')]
    legend = ''.join(f'<li><i style="background:{PART[c][1]}"></i><span>{PART[c][0]}</span></li>' for c in used)
    chips = ''.join(f'<button type="button" class="fb-chip" data-pick="{k}">{e(name(k))}</button>' for k in areas)

    # the full lists, in fold-downs
    rows = ''
    for x in d['assessments']:
        r = roll(x)
        if not r.get('total_levied'):
            continue
        rows += f'''<tr><td class="wrap"><b>{e(fee_name(x))}</b><br><span class="muted small">{e(x["government"].split("(")[0].strip())}</span></td><td class="wrap small">{e(x.get("rate") or x.get("how_charged", ""))}</td><td class="num">{money(common_amount(x), 2)}</td><td class="num">{r.get("parcels_billed", 0):,}</td><td class="num">{money(r.get("total_levied"))}</td><td>{a(x.get("source_url"))}</td></tr>'''
    n_fees = rows.count('<tr>')
    all_fees = tot["county_government"]["total"] + tot["municipalities"]["total"] + tot["independent_special_districts"]["total"]
    utbl = ''.join(f'''<tr{data_g(k)}><th scope="row">{e(u["provider"])}<br><span class="muted small">{e(u.get("area", ""))}</span></th><td class="num">${p["water_sewer"]:,.2f}</td><td class="num">{"$%.2f" % p["garbage"] if p["garbage"] else "—"}</td><td class="num">{"$%.2f" % p["other"] if p["other"] else "—"}</td><td class="num"><b>${u_total(p):,.2f}</b></td><td class="wrap small">{e(p.get("other_note") or "")} {e(u.get("calc", ""))}<br><span class="muted">Effective: {e(u.get("effective") or "not stated")}</span> {a(u.get("source_url"))}</td></tr>''' for k, u, p in ub)
    gaps = [g for g in d['gaps'] if not re.search(r'salar|pay|roster|term|school board|manager', g, re.I)]
    gk = [k for k in KEYS if k in areas]
    picked = (','.join(f':root[data-city="{k}"] .fb-chip[data-pick="{k}"]' for k in areas) + CHIP_ON
              + ','.join(f':root[data-city="{k}"] .fb-cmp li[data-k="{k}"]' for k in areas) + ROW_ON)
    return f'''<div class="page tax fb">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Public Money · Fees &amp; Bills</span><h1>What fees and utility bills cost where you live</h1>
    <p class="lede">Pick where you live to see the flat fees on your yearly tax bill and a typical monthly water, sewer and garbage bill.</p></div>{PDF}</header>
  {city_bar(gk, hide=True, label='Where you live', all_label='Pick where you live')}
  <div class="fb-tenure" role="group" aria-label="Do you own or rent?"><button type="button" data-tenure="own" aria-pressed="true">I own my home</button><button type="button" data-tenure="rent" aria-pressed="false">I rent</button></div>
  <nav class="fb-chips" aria-label="Pick where you live">{chips}<a class="fb-addr" href="/my-address/">Use my address →</a></nav>
  <div class="fb-pick"><p><b>Pick where you live</b> to see the fees on your tax bill and your monthly utility bill. Every area is compared below.</p></div>
  {cards}
  <section class="tx-sec"><div class="sec-hd"><h2 id="compare" data-tile="Compare">How every area compares</h2><span class="muted fb-own">A typical home, a year</span><span class="muted fb-rent">Owners, a year; renters pay the utility part</span></div>
    <ul class="fb-cmp" data-share-items>{cmp_rows}</ul>
    <ul class="fb-leg">{legend}</ul>
    <p class="note">Tax-bill fees plus 12 months of water, sewer and garbage at 5,000 gallons a month. * Garbage isn't on this utility bill, so the total leaves it out. Parker's utility rates weren't found online.</p></section>
  <section class="tx-sec fb-more"><div class="sec-hd"><h2 id="details" data-tile="Details">The details</h2></div>
    <details class="tbl-toggle"><summary>Every fee on Bay County tax bills <span class="muted">· {n_fees} fees, {money(all_fees)} in all</span></summary>
      <div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Fee</th><th scope="col">How it's charged</th><th scope="col" class="num">Most common bill</th><th scope="col" class="num">Parcels billed</th><th scope="col" class="num">Total</th><th scope="col">Source</th></tr></thead><tbody>{rows}</tbody></table></div>
      <p class="note">FY2026 bills (2025 tax roll). Unincorporated Bay County's fire service is a property tax (1.38 mills), not a flat fee, so it's on the <a href="/public-money/tax-dollars">tax dollars page</a>. No garbage fee is on any Bay County tax bill. Counts and totals come from the Florida Department of Revenue's parcel-level file for Bay County. {a("https://floridarevenue.com/property/dataportal/Documents/PTO%20Data%20Portal/Tax%20Roll%20Data%20Files/NAV/2025/NAV%20D/NAVD132506.TXT", "DOR file")}</p></details>
    <details class="tbl-toggle"><summary>How each utility bill is worked out</summary>
      <div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Provider</th><th scope="col" class="num">Water and sewer</th><th scope="col" class="num">Garbage</th><th scope="col" class="num">Other</th><th scope="col" class="num">Total</th><th scope="col">Calculation</th></tr></thead><tbody>{utbl}</tbody></table></div>
      <p class="note">Bills are worked out from each provider's published rate sheet. Panama City Beach's garbage rate and Parker's utility rates weren't found online. Panama City's own notice gives an "average" bill equal to its base charges alone, so its usage charges may include an allowance the notice doesn't describe.</p></details>
    <details class="tbl-toggle"><summary>Taxes vs. fees, the simple version</summary>
      <ol class="ex-steps">
        <li><b>Property tax depends on your home's value.</b> A bigger taxable value means a bigger tax.</li>
        <li><b>Fees on the tax bill are mostly flat.</b> {T('non-ad-valorem', 'Non-ad valorem assessments')} charge per home, per parcel or by building size for a specific service, like fire protection or stormwater drainage. They're not affected by homestead exemptions or Amendment 3.</li>
        <li><b>Utility bills are separate.</b> Water, sewer and garbage are billed monthly by your city or the county, based on how much you use.</li>
      </ol><p><a href="/my-address/">Look up the exact fees on your parcel →</a></p></details>
    <details class="tbl-toggle"><summary>What we couldn't find <span class="muted">· {len(gaps)}</span></summary><ul class="plain">{''.join(f'<li>{e(g)}</li>' for g in gaps)}</ul></details>
  </section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<style>{CSS}{picked}</style>
<script>{JS}</script>'''


CSS = '''.fb-chips{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.fb-chip{min-height:44px;padding:0 18px;border-radius:999px;border:0;background:var(--surface);box-shadow:var(--ui-shadow);color:var(--ink);font:inherit;font-size:.92rem;font-weight:500;cursor:pointer}
.fb-chip:hover{box-shadow:var(--ui-ring)}
.fb-addr{margin-left:6px;font-size:.9rem;font-weight:500}
.fb-pick{padding:18px 22px;border-radius:18px;background:var(--surface);box-shadow:var(--ui-shadow)}.fb-pick p{margin:0}
.fb-area{display:flex;flex-direction:column;gap:16px}
.fb-area,:root[data-city]:not([data-city=""]) .fb-pick{display:none}
:root[data-city]:not([data-city=""]) .fb-area:not([hidden]){display:flex}
.fb-receipts{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.fb-card{display:flex;flex-direction:column;gap:4px;padding:22px 24px;border-radius:20px;background:var(--surface);box-shadow:var(--ui-shadow)}
.fb-card h3{margin:2px 0 6px;font-size:1.15rem}
.fb-lines{list-style:none;margin:0;padding:0}
.fb-lines li{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding:11px 0;border-bottom:1px solid var(--line)}
.fb-lines li small,.fb-band span small{display:block;font-size:.78rem;color:var(--muted);font-weight:400}
.fb-lines li small{margin-left:20px}
.fb-lines .fb-none{color:var(--muted)}.fb-lines .fb-none > span:last-child{font-size:.85rem}
.fb-dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:10px}
.fb-total{display:flex;justify-content:space-between;align-items:baseline;margin:0;padding-top:10px;font-weight:600}
.fb-total b{font-size:1.4rem}
.fb-card .num{font-family:var(--f-data);font-weight:500}
.fb-fine{margin:6px 0 0;font-size:.82rem;line-height:1.5;color:var(--muted)}
.fb-band{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;padding:20px 24px;border-radius:20px;background:var(--start-bg);color:var(--start-ink)}
.fb-band span small{color:var(--start-sub)}
.fb-band b{font-family:var(--f-data);font-weight:500;font-size:2rem;white-space:nowrap}.fb-band b small{font-size:.9rem;color:var(--start-sub)}
.fb-cmp{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:4px}
.fb-cmp li{display:grid;grid-template-columns:minmax(150px,200px) 1fr 80px;gap:14px;align-items:center;padding:6px 8px;border-radius:10px}
.fb-cmp b{text-align:right;font-family:var(--f-data);font-weight:500}
.fb-cmp-n{all:unset;cursor:pointer;font-size:.92rem}.fb-cmp-n:hover{text-decoration:underline}.fb-cmp-n:focus-visible{box-shadow:var(--ui-ring);border-radius:4px}
.fb-track{height:14px;border-radius:7px;background:color-mix(in srgb,var(--ink) 6%,transparent);overflow:hidden}
.fb-stack{display:flex;height:100%;gap:1px}
.fb-more details .ex-steps{margin:4px 0 12px}
.fb-leg{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:8px 20px;font-size:.88rem}
.fb-leg li{display:flex;align-items:center;gap:8px}.fb-leg i{width:12px;height:12px;border-radius:3px}
.fb-tenure{display:inline-flex;align-items:center;gap:4px;align-self:flex-start;padding:4px;border-radius:14px;background:var(--surface);box-shadow:var(--ui-shadow);font-size:.92rem}
.fb-tenure button{min-height:40px;padding:0 16px;border:0;border-radius:10px;background:transparent;color:var(--ink);font:inherit;font-weight:500;cursor:pointer}
.fb-tenure button[aria-pressed="true"]{background:var(--start-bg);color:var(--start-ink)}
.fb-rent{display:none}
:root[data-tenure="rent"] .fb-tax,:root[data-tenure="rent"] .fb-own{display:none}
:root[data-tenure="rent"] .fb-band.fb-rent{display:flex}:root[data-tenure="rent"] span.fb-rent{display:inline}:root[data-tenure="rent"] p.fb-rent{display:block}
@media (max-width:640px){
  .fb-chips{display:none}
  .fb-card{padding:18px}
  .fb-band b{font-size:1.7rem}
  .fb-cmp li{grid-template-columns:1fr auto;gap:6px 10px}
  .fb-cmp .fb-track{grid-column:1 / -1;grid-row:2;height:10px}
}
'''
# the chosen area: a filled chip and a highlighted compare row (fees_page writes the selectors for each area)
CHIP_ON = '{background:var(--start-bg);color:var(--start-ink);font-weight:600}'
ROW_ON = '{background:var(--tint-blue);font-weight:600}'

# Chips pick the area through the shared city filter. Own or rent is remembered in this browser only (a convenience:
# the page reads the same either way until it's picked).
JS = '''document.querySelectorAll('[data-pick]').forEach(b => b.addEventListener('click', () => window.BCM && BCM.city.set(b.dataset.pick, 'user')));
(() => {
  const K = 'bcm-tenure', root = document.documentElement, btns = document.querySelectorAll('[data-tenure]');
  const set = (t, save) => { root.dataset.tenure = t; btns.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.tenure === t))); if (save) try { localStorage.setItem(K, t); } catch (e) {} };
  let t = 'own'; try { t = localStorage.getItem(K) === 'rent' ? 'rent' : 'own'; } catch (e) {}
  set(new URLSearchParams(location.search).get('rent') === '1' ? 'rent' : t);
  btns.forEach(b => b.addEventListener('click', () => set(b.dataset.tenure, true)));
})();'''


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


def who_sections():
    """Countywide officers and officials' pay, as sections of the People page (/people). This was /who-runs-bay-county;
    each government's own seats are on its page (/governments/<slug>, \"Who's in charge\")."""
    d = json.load(open(SRC))
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
    from govs import all_profiles
    glinks = ''.join(f'<a class="ui-tag" href="/governments/{p["slug"]}#who">{e(p["short"])}</a>' for p in all_profiles())
    return f'''<section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>Who's in charge of what</h2>
    <ol class="ex-steps">
      <li><b>Elected boards set policy and budgets.</b> The County Commission, each city commission or council, and the School Board vote on budgets, tax rates and big contracts.</li>
      <li><b>Appointed managers run operations.</b> A county manager or city manager, hired by the board, runs departments and staff. Springfield and Parker have no manager; the board oversees staff directly and a city clerk handles administration.</li>
      <li><b>Five county officers are elected on their own.</b> The Sheriff, Property Appraiser, Tax Collector, Clerk of Court and Supervisor of Elections each run their own office. The County Commission funds most of their budgets. Their pay is set by a state formula.</li>
    </ol>
    <p>Every board's seats, terms and appointed staff are on its government's page:</p><div class="ui-tags">{glinks}</div>
    <p><a href="/my-address/">Find who represents your address →</a></p></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="co">Countywide elected officers</h2><span class="muted">Pay set by state formula</span></div>
    <div class="officers">{co}</div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="pay">What officials are paid</h2><span class="muted">From state salary reports, budgets and contracts</span></div>
    <div class="tablewrap"><table class="tx-table pay-table"><thead><tr><th scope="col">Position</th><th scope="col">Government</th><th scope="col" class="num">Annual</th><th scope="col">Basis</th></tr></thead><tbody>{prow}</tbody></table></div>
    <p class="note">Where a budget shows only one combined line for a whole city commission, that total is listed rather than divided among members. Salary data names only elected officials and department leaders.</p>
    <details class="gaps"><summary>What we couldn't find</summary><ul class="plain">{gaps}</ul></details></section>

'''
