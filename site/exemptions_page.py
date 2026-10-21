"""Property tax exemptions (/public-money/exemptions), from the 2026 final tax roll (Florida DOR NAL file).
Also writes per-parcel exemption shards for My Address (public/data/ex/<prefix>.json)."""
import html, json, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data', 'exemptions')
e = lambda s: html.escape(str(s if s is not None else ''))
PDF_BTN = '<button type="button" class="pdf-btn" id="pdf"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button>'

# Plain-English names and who qualifies (from Florida Statutes ch. 196 / 193.703). Shown on this page and on My Address.
HOME = [
    ('01', 'Homestead', 'First $25,000 of value', 'Your permanent home, owned and lived in on January 1.', True),
    ('02', 'Additional homestead', 'Value between $50,000 and about $76,000', 'Automatic with the homestead exemption. The amount now rises with inflation each year. Not applied to school taxes.', False),
    ('05', 'Disabled veteran, total and permanent', 'Entire value', 'A veteran with a service-connected, total and permanent disability rated by the VA, or the surviving spouse. Also surviving spouses of service members who died on active duty.', True),
    ('35', 'Disabled veteran, $5,000', '$5,000', 'A veteran with a service-connected disability of 10% or more, or the surviving spouse.', True),
    ('80', 'Combat-disabled veteran discount, 65+', 'Percent equal to the VA disability rating', 'A veteran 65 or older with a combat-related disability.', True),
    ('38', 'Deployed service member', 'Share of value for days deployed', 'Service members deployed outside the U.S. in a qualifying operation during the prior year.', True),
    ('06', 'Disabled veteran in a wheelchair', 'Entire value', 'A veteran with a service-connected disability who uses a wheelchair, or the surviving spouse.', True),
    ('41', 'Disabled first responder', 'Entire value', 'A first responder totally and permanently disabled in the line of duty, or the surviving spouse of one who died in the line of duty.', True),
    ('08', 'Totally and permanently disabled person', 'Entire value', 'Quadriplegics; or paraplegics, people who must use a wheelchair, and legally blind people whose household income is under a state limit.', True),
    ('03', 'Senior, county', 'Up to $50,000 more, county taxes only', 'Homeowners 65+ whose household income is under a state limit that is adjusted each year.', False),
    ('39', 'Long-term senior, county', 'Entire value, county taxes only', 'Homeowners 65+ with limited income who have lived in a home worth less than a set amount for 25 years or more.', False),
    ('33', 'Widow', '$5,000', 'A widow who has not remarried.', True),
    ('32', 'Widower', '$5,000', 'A widower who has not remarried.', True),
    ('34', 'Disabled person, $5,000', '$5,000', 'A Florida resident who is totally and permanently disabled.', True),
    ('31', 'Blind person', '$5,000', 'A Florida resident who is legally blind.', True),
    ('81', 'Granny flat', 'Reduced assessed value', 'Living quarters built for a parent or grandparent 62 or older.', True),
]
OTHER_NAMES = {'20': 'Government property', '09': 'Churches, charities and other nonprofits', '43': 'Affordable housing (state-certified)', '15': 'Affordable housing (nonprofit)',
               '13': 'Nonprofit homes for the aged', '17': 'Charter schools', '22': 'Economic development incentive (county)', '16': 'Private schools', '12': 'Hospitals and nursing homes', '36': 'Conservation land'}
VET = ['05', '35', '80', '38', '06']
DIST_SHORT = {'unincorporated': 'Unincorporated (inland)', 'unincorporated - beach area': 'Unincorporated (beach area)'}


def money(n):
    a = abs(n or 0)
    return f'${n/1e9:,.2f}B' if a >= 1e9 else f'${n/1e6:,.1f}M' if a >= 1e6 else f'${n/1e3:,.0f}K' if a >= 1e4 else f'${n:,.0f}'


def write_shards(out_dir):
    from addr_page import shard_key, SHARDS
    fp = os.path.join(DATA, 'parcels_2026.json')
    if not os.path.exists(fp):
        return 0
    P = json.load(open(fp))
    sh = defaultdict(dict)
    for pid, v in P.items():
        # privacy: only [school taxable, non-school taxable, homestead $, additional homestead $, other exemptions $] may be published
        if not (isinstance(v, list) and len(v) == 5 and all(isinstance(x, (int, float)) for x in v)):
            raise ValueError(f'parcels_2026.json row for {pid} is not the privacy-safe shape; run data/exemptions/build_exemptions.py --migrate')
        sh[shard_key(pid, SHARDS['ex'])][pid] = v
    d = os.path.join(out_dir, 'data', 'ex'); os.makedirs(d, exist_ok=True)
    for k, v in sh.items():
        json.dump(v, open(os.path.join(d, f'{k}.json'), 'w'), separators=(',', ':'))
    return len(sh)


def names_for_js():
    out = {c: n for c, n, *_ in HOME}
    out.update(OTHER_NAMES)
    return out


def exemptions_page(out_dir):
    write_shards(out_dir)
    try:
        D = json.load(open(os.path.join(DATA, 'exemptions_2026.json')))
    except FileNotFoundError:
        return '<div class="page prose"><h1>Exemptions</h1><p>Coming soon.</p></div>'
    C, T = D['codes'], D['totals']
    home_codes = [h for h in HOME if h[0] in C]
    home_tax = sum(C[h[0]]['tax'] for h in home_codes)
    vet_tax = sum(C[c]['tax'] for c in VET if c in C)
    full_vet = C.get('05', {}).get('homes', 0)
    mx = max(C[h[0]]['tax'] for h in home_codes)
    rows = ''.join(f'''<tr><th scope="row"><b>{e(n)}</b><small>{e(who)}</small></th><td class="small">{e(amt)}</td><td class="small">{"Yes" if school else "No"}</td>
      <td class="num">{C[c]["homes"]:,}</td><td class="num">{money(C[c]["value"])}</td><td class="num">{money(C[c]["tax"])}</td></tr>''' for c, n, amt, who, school in home_codes)
    vbd = D['veterans_by_district']
    vrows = sorted(vbd.items(), key=lambda kv: -(kv[1].get('05', 0) / max(1, kv[1]['homesteads'])))
    vmx = max(v.get('05', 0) / max(1, v['homesteads']) for _, v in vrows)
    vbars = ''.join(f'''<div class="hb"><span class="hb-n">{e(DIST_SHORT.get(d, d))} <em>{v["homesteads"]:,} homesteads</em></span><span class="hb-track"><span class="hb-bar" style="width:{v.get("05", 0) / v["homesteads"] / vmx * 100:.1f}%"></span></span><span class="hb-v">{v.get("05", 0) / v["homesteads"]:.1%} <em>{v.get("05", 0):,} homes · {money(v["full_exempt_value"])}</em></span></div>''' for d, v in vrows)
    vt = {c: sum(v.get(c, 0) for v in vbd.values()) for c in VET}
    other = sorted(((c, v) for c, v in C.items() if c in OTHER_NAMES), key=lambda kv: -kv[1]['tax'])
    orows = ''.join(f'<tr><th scope="row">{e(OTHER_NAMES[c])}</th><td class="num">{v["parcels"]:,}</td><td class="num">{money(v["value"])}</td><td class="num">{money(v["tax"])}</td></tr>' for c, v in other)
    other_tax = sum(v['tax'] for _, v in other)
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Public Money · Exemptions</span><h1>Property tax exemptions</h1>
    <p class="lede">Who doesn't pay property tax on part or all of their property, and what it adds up to. From the 2026 tax roll for every parcel in Bay County, with a closer look at exemptions for veterans.</p></div>
    <div class="stamp">{PDF_BTN}<span>2026 tax roll</span></div></header>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>How an exemption works</h2>
    <ol class="ex-steps"><li><b>An exemption takes value off the tax bill.</b> A $25,000 exemption means you're taxed as if your home were worth $25,000 less. A full exemption means no property tax at all.</li>
      <li><b>Most are set by the Florida Constitution and state law.</b> Local governments choose only a few, like the extra exemption for seniors with limited income.</li>
      <li><b>Exempt value spreads the cost.</b> When value is exempt, each tax rate raises less from it, so the rest of the tax base carries more of the budget. The dollars here estimate the tax each exemption takes off the bill at current rates.</li></ol></div></section>
  <div class="kpis">
    <div class="kpi"><span class="eyebrow">Homesteads</span><span class="v">{T["homesteads"]:,}</span><span class="s">homes with the homestead exemption in 2026</span></div>
    <div class="kpi"><span class="eyebrow">Homeowner exemptions</span><span class="v">{money(home_tax)}</span><span class="s">estimated tax they take off bills each year</span></div>
    <div class="kpi"><span class="eyebrow">Owe no property tax</span><span class="v">{T["zero_all"]:,}</span><span class="s">homesteads fully exempt from all property tax</span></div>
    <div class="kpi"><span class="eyebrow">Disabled veterans, fully exempt</span><span class="v">{full_vet:,}</span><span class="s">homes · {money(C.get("05", {}).get("value", 0))} in value</span></div>
  </div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="home">Exemptions for homeowners</h2><span class="muted">2026 tax roll · estimated tax at FY{e(str(D["rates"])[-4:])} rates</span></div>
    <div class="tablewrap"><table class="tx-table cm-table ex-table"><thead><tr><th scope="col">Exemption and who qualifies</th><th scope="col">Amount</th><th scope="col">School taxes?</th><th scope="col" class="num">Homes</th><th scope="col" class="num">Value exempted</th><th scope="col" class="num">Tax taken off bills</th></tr></thead><tbody>{rows}</tbody></table></div>
    <p class="note">"School taxes?" says whether the exemption also lowers school taxes. No Bay County city has adopted the city senior exemptions state law allows. A home can have several exemptions; homes are counted under each one.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="veterans">Veterans</h2><span class="muted">{sum(vt.values()):,} veteran exemptions on {T["homesteads"]:,} homesteads</span></div>
    <div class="kpis">
      <div class="kpi"><span class="eyebrow">Fully exempt</span><span class="v">{vt.get("05", 0):,}</span><span class="s">total and permanent service-connected disability, or surviving spouses</span></div>
      <div class="kpi"><span class="eyebrow">$5,000 exemption</span><span class="v">{vt.get("35", 0):,}</span><span class="s">service-connected disability of 10% or more</span></div>
      <div class="kpi"><span class="eyebrow">Combat-disabled, 65+</span><span class="v">{vt.get("80", 0):,}</span><span class="s">discount equal to the disability rating</span></div>
      <div class="kpi"><span class="eyebrow">Tax effect</span><span class="v">{money(vet_tax)}</span><span class="s">estimated a year across all veteran exemptions</span></div>
    </div>
    <h3 class="ex-h">Share of homesteads fully exempt for a disabled veteran</h3>
    <div class="hbars">{vbars}</div>
    <p class="note">Bay County is home to Tyndall Air Force Base and Naval Support Activity Panama City. The full exemption for disabled veterans is set by the Florida Constitution; local governments can't change it.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="other">Other exempt property</h2><span class="muted">{money(other_tax)} a year in estimated tax</span></div>
    <div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Type</th><th scope="col" class="num">Parcels</th><th scope="col" class="num">Value exempted</th><th scope="col" class="num">Tax taken off bills</th></tr></thead><tbody>{orows}</tbody></table></div>
    <p class="note">Government property includes land and buildings owned by the federal, state, county and city governments and the school district, including military land.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="apply">Do you qualify?</h2></div>
    <ul class="plain"><li><b>Apply with the Bay County Property Appraiser.</b> Under state law, applications for most exemptions are due by March 1 for that year's taxes. Once granted, most renew automatically each year as long as you still qualify.</li>
      <li><b>Veterans</b> need a VA letter showing the disability rating; surviving spouses need the veteran's rating and proof of marriage.</li>
      <li><b>Seniors</b> applying for the income-based exemptions file a household income statement each year.</li>
      <li>See what your home gets now on <a href="/my-address">My Address</a>; the property card lists each exemption.</li>
      <li><a href="https://www.baypa.net/" target="_blank" rel="noopener">Bay County Property Appraiser ↗</a></li></ul></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">Sources and method</h2></div>
    <p>Counts and values come from the 2026 final tax roll for Bay County that the Property Appraiser files with the Florida Department of Revenue (the "NAL" file, posted October 16, 2026), which lists each parcel's exemptions by type and its school and non-school taxable values. <a class="src" href="{e(D["source"])}" target="_blank" rel="noopener">Florida DOR data portal</a></p>
    <p>"Tax taken off bills" applies the latest complete set of adopted tax rates (FY{e(str(D["rates"])[-4:])} bills, the same rates My Address uses) to the value each exemption removes, parcel by parcel, using each parcel's own tax district. Where a parcel has several exemptions, the tax is shared among them by amount. It doesn't include the Save Our Homes cap, which limits how fast a homestead's taxed value can rise and is not an exemption. Total for all exemptions, homes and other property: {money(T["tax_removed"])} a year.</p></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">'''
