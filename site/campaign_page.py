"""Campaign money and contracts (/campaign-money)."""
import html, json, os, re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data', 'campaign')
e = lambda s: html.escape(str(s if s is not None else ''))
GOVN = {'county': 'Bay County Commission', 'constitutional': 'County officers', 'schools': 'School Board & Superintendent', 'pc': 'Panama City', 'pcb': 'Panama City Beach',
        'lh': 'Lynn Haven', 'cw': 'Callaway', 'sp': 'Springfield', 'parker': 'Parker', 'mb': 'Mexico Beach'}
ORDER = list(GOVN)


def usd(n):
    return '—' if n is None else f'${n:,.0f}'


SUFFIX = re.compile(r'[\s,.]*\b(inc|llc|ll|co|corp|corporation|company|pa|pllc|ltd)\b\.?$', re.I)


def _base(n):
    b, suf = n.strip(), ''
    m = SUFFIX.search(b)
    if m:
        suf = m.group(1).lower().replace('ll', 'llc') if m.group(1).lower() == 'll' else m.group(1).lower()
        b = b[:m.start()]
    b = re.sub(r'^committee\s+', '', b, flags=re.I)
    return re.sub(r'[^a-z0-9]', '', b.lower().replace("'", '').replace('&', 'and')), suf


CANON = {}


def _display(names):
    """Pick the clearest spelling: mixed case over ALL CAPS, then the most complete."""
    def score(n):
        return (n[:1].isupper(), n != n.upper() and n != n.lower(), not n.lower().startswith('committee '), len(n))
    n = max(names, key=score)
    return re.sub(r',?\s+LL$', ', LLC', n)


# Names the Supervisor of Elections cut off at 30 characters, or misspelled, completed only where the full name is clear
NAME_FIX = {
    'Able Services of NW Florida, L': 'Able Services of NW Florida, LLC', 'American Sand and Asphalt Pavi': 'American Sand & Asphalt Paving',
    'BK Construction &Devlopment Co': 'BK Construction & Development Co.', 'Blue Water Commercial Group LL': 'Blue Water Commercial Group, LLC',
    'C & G Construction Equipment I': 'C & G Construction Equipment, Inc.', 'Cypress Environmental Of Bay C': 'Cypress Environmental of Bay County',
    'Emerald Coast Civil Constructi': 'Emerald Coast Civil Construction', 'Emerald Coast Federal Credit U': 'Emerald Coast Federal Credit Union',
    'Emerald Coast OBGYN of the Pan': 'Emerald Coast OBGYN of the Panhandle', 'Fiddlers Point Oyster Company': "Fiddler's Point Oyster Co, LLC",
    'Freedom Consulting Services LL': 'Freedom Consulting Services, LLC', 'Garretts Automobile Service Ce': "Garrett's Automotive Service Center",
    'Garretts Automotive Service Ce': "Garrett's Automotive Service Center", 'Harpoon Harrys Harpoon Harrys': "Harpoon Harry's",
    'Holiday Golf & Racque Club, Ic': 'Holiday Golf & Racquet Club, Inc.', 'McKinney Insurance & Investmen': 'McKinney Insurance & Investments',
    'Monolith Construction - Panhan': 'Monolith Construction - Panhandle', 'Palm Realty & Property Managme': 'Palm Realty & Property Management',
    'Panama City Boatman Associatio': 'Panama City Boatman Association', 'Pros Construction & Roofing In': 'Pros Construction & Roofing, Inc.',
    'RX Express Pharmacy of Panama': 'RX Express Pharmacy of Panama City', 'Safe Harbor Insurance Protecti': 'Safe Harbor Insurance Protection',
    'Southerland Family Funeral Hom': 'Southerland Family Funeral Home', 'The Sterling Company of Bay Co': 'The Sterling Company of Bay County',
    'Trumbull Water Services of NWF': 'Trumbull Water Services of NW Florida', 'Property Account Trumbull Water Services of NW': 'Trumbull Water Services of NW Florida',
    'Vittles Companies, Inc Operati': 'Vittles Companies, Inc.', 'Vittles Inc Operating Account': 'Vittles, Inc.',
    'Realtors Polictical Advocacy C': 'Realtors Political Advocacy Committee', 'Realtors Political Advocacy Co': 'Realtors Political Advocacy Committee',
    'Realtors Political Advocacy': 'Realtors Political Advocacy Committee', 'Committee Realtors Political Advocacy': 'Realtors Political Advocacy Committee',
    'committee Realtors Political Advocacy Co': 'Realtors Political Advocacy Committee', 'Realtors Political Act Committ': 'Realtors Political Action Committee',
    'Realtors Political Action Comm': 'Realtors Political Action Committee', 'Nive Vittles': 'Nice Vittles, Inc.', 'Marshall Bothers': 'Marshall Brothers', "Mike's Cafe & Oyster Bar, LL": "Mike's Cafe & Oyster Bar, LLC",
}


def merge_orgs(orgs):
    """Total gifts by organization, treating spelling variants of one name as one donor.
    Names with different legal suffixes (Inc vs LLC) stay separate; a name with no suffix joins its only suffixed match."""
    groups = defaultdict(lambda: defaultdict(lambda: [0.0, []]))
    for x in orgs:
        nm = NAME_FIX.get(x['name'].strip(), x['name'].strip())
        b, suf = _base(nm)
        g = groups[b][suf]; g[0] += x.get('amount') or 0; g[1].append(nm)
    out = []
    for b, by in groups.items():
        sufs = [k for k in by if k]
        if '' in by and len(sufs) == 1:
            bare = by.pop(''); by[sufs[0]][0] += bare[0]; by[sufs[0]][1] += bare[1]
        out += [(CANON.get(_base(v[1][0])) or _display(v[1]), v[0]) for v in by.values()]
    return sorted(out, key=lambda kv: -kv[1])


def campaign_page():
    try:
        d = json.load(open(os.path.join(DATA, 'campaign.json')))
        vm = json.load(open(os.path.join(DATA, 'vendor_matches.json')))
    except FileNotFoundError:
        return '<div class="page prose"><h1>Campaign money</h1><p>Coming soon.</p></div>'
    cands = d['candidates']
    _all = defaultdict(list)
    for c in cands:
        for x in c.get('contributors') or []:
            if x.get('type') not in ('individual', 'candidate'):
                nm = NAME_FIX.get(x['name'].strip(), x['name'].strip()); _all[_base(nm)].append(nm)
    # a name with no legal suffix belongs to its suffixed form when there is only one
    _sufs = defaultdict(set)
    for b, suf in _all:
        if suf:
            _sufs[b].add(suf)
    for (b, suf) in list(_all):
        if not suf and len(_sufs[b]) == 1:
            _all[(b, next(iter(_sufs[b])))] += _all.pop((b, ''))
    CANON.clear(); CANON.update({k: _display(v) for k, v in _all.items()})
    for b, ss in _sufs.items():
        if len(ss) == 1:
            CANON[(b, '')] = CANON[(b, next(iter(ss)))]
    # pairs: one per contributor+candidate (rows repeat per contracting government)
    pairs = defaultdict(lambda: {'govs': [], 'contracts': [], 'urls': []})
    for m in vm['matches']:
        k = (m['contributor'], m['candidate'])
        p = pairs[k]
        p.update({k2: m.get(k2) for k2 in ('contributor', 'candidate', 'office', 'election', 'contribution_amount', 'contribution_dates', 'match_confidence', 'campaign_report_url', 'vendor_entity', 'refunded_by_campaign')})
        p['govs'].append((m.get('contract_government'), m.get('same_government_as_office')))
        p['contracts'] += [(m.get('contract_government'), c) for c in m.get('contract_ids_or_descriptions') or []]
        p['urls'] += m.get('contract_source_urls') or []
    plist = sorted(pairs.values(), key=lambda p: (not any(s for _, s in p['govs']), -(p['contribution_amount'] or 0)))
    same = sum(1 for p in plist if any(s for _, s in p['govs']))
    off_matched = len({p['candidate'] for p in plist})
    tot = sum(c.get('total_raised') or 0 for c in cands)
    org = sum(sum(v for k, v in (c.get('by_type_total') or {}).items() if k not in ('individual', 'candidate_self')) for c in cands)
    ind = sum((c.get('from_individuals') or {}).get('total') or 0 for c in cands)
    # officials table
    rows = ''
    for gk in ORDER:
        cs = [c for c in cands if c.get('gov') == gk]
        if not cs:
            continue
        rows += f'<tr class="grp" data-g="{gk}"><th colspan="6" scope="colgroup">{e(GOVN[gk])}</th></tr>'
        for c in sorted(cs, key=lambda c: -(c.get('total_raised') or 0)):
            bt = c.get('by_type_total') or {}
            orgs = sorted((x for x in c.get('contributors') or [] if x.get('type') not in ('individual', 'candidate')), key=lambda x: -(x.get('amount') or 0))
            top = merge_orgs(orgs)
            orgt = sum(v for k, v in bt.items() if k not in ('individual', 'candidate_self'))
            fi = c.get('from_individuals') or {}
            det = (f'<details class="flds"><summary>{len(top)} organizations</summary><ul class="plain small">' + ''.join(f'<li>{e(n)} · {usd(v)}</li>' for n, v in top) + '</ul></details>') if top else '<span class="muted small">none</span>'
            rows += f'''<tr data-g="{gk}"><th scope="row"><b>{e(c["official"])}</b><small>{e(c.get("office"))} · {e(c.get("election"))}</small></th>
              <td class="num">{usd(c.get("total_raised"))}</td><td class="num">{usd(fi.get("total"))}<small>{fi.get("count") or 0} people</small></td><td class="num">{usd(orgt)}</td>
              <td class="num">{usd(bt.get("candidate_self"))}</td><td class="wrap">{det} <a class="src" href="{e(c.get("report_url"))}" target="_blank" rel="noopener">Report</a>{f'<br><span class="muted small">{e(c["note"])}</span>' if c.get("note") else ""}</td></tr>'''
    # matches table
    mrows = ''
    for p in plist:
        own = [g for g, s in p['govs'] if s]
        by = defaultdict(list)
        for g, c in p['contracts']:
            by[g].append(c)
        amt = lambda c: sum(float(x.replace(',', '')) for x in re.findall(r'\$([\d,]+(?:\.\d+)?)', c)[-1:]) if re.search(r'\$[\d,]', c) else 0
        def part(g, v):
            ks = [c for c in v if re.match(r'(Contract|ITB|RFP|Award|Emergency)', c, re.I)]
            other = len(v) - len(ks)
            t = sum(amt(c) for c in ks)
            return f'{e(g)}: ' + (f'{len(ks)} contract{"s" if len(ks) != 1 else ""}' + (f' totaling {usd(t)}' if t else '') if ks else '') + (f'{", " if ks else ""}{other} change order{"s" if other != 1 else ""} or payment record{"s" if other != 1 else ""}' if other else '')
        summ = '<br>'.join(part(g, v) for g, v in by.items())
        full = ''.join(f'<li>{e(g)}: {e(c)}</li>' for g, c in p['contracts'])
        urls = list(dict.fromkeys(p['urls']))
        mrows += f'''<tr data-g="{e(next((c.get("gov") for c in cands if c["official"] == p["candidate"]), ""))}"><th scope="row"><b>{e(p["contributor"])}</b><small>{e(p.get("vendor_entity") or "")}{" · name spelled differently in the filing" if p.get("match_confidence") == "likely" else ""}</small></th>
          <td class="num">{usd(p["contribution_amount"])}<small>{e(", ".join(p.get("contribution_dates") or []))}</small></td>
          <td><b>{e(p["candidate"])}</b><small>{e(p["office"])}</small></td>
          <td class="wrap small">{"<span class='badge warn'>Same government</span> " if own else ""}{summ}<details class="flds"><summary>See contracts and payments</summary><ul class="plain">{full}</ul><p>{" · ".join(f'<a class="src" href="{e(u)}" target="_blank" rel="noopener">Source {i + 1}</a>' for i, u in enumerate(urls[:6]))}</p></details>
          <a class="src" href="{e(p.get("campaign_report_url"))}" target="_blank" rel="noopener">Campaign report</a></td></tr>'''
    opts = ''.join(f'<option value="{k}">{e(v)}</option>' for k, v in GOVN.items() if any(c.get('gov') == k for c in cands))
    gaps = ''.join(f'<li>{e(g)}</li>' for g in d.get('gaps') or [])
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Accountability · Campaign money</span><h1>Campaign money and contracts</h1>
    <p class="lede">Who paid for the most recent campaigns of Bay County's current elected officials, from the reports they file with the Supervisor of Elections, and which donors also hold local government contracts.</p></div>
    <div class="stamp"><a class="pill" href="/public-money/money-map">See the money map</a><button type="button" class="pdf-btn" id="pdf"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>Reports as of {e(d.get("as_of"))}</span></div></header>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>Reading campaign money</h2>
    <ol class="ex-steps">
      <li><b>Candidates must report every contribution.</b> Florida caps gifts to local candidates at $1,000 per person or business per election, and every report is public.</li>
      <li><b>Businesses that work with government often give.</b> It's legal and common. A donor that also has a contract is a fact in the records, not proof that one led to the other.</li>
      <li><b>We name organizations, not people.</b> Gifts from individuals are shown only as a count and total. The full reports, with every name, are linked for each official.</li>
    </ol></div></section>
  <div class="kpis">
    <div class="kpi"><span class="eyebrow">Officials covered</span><span class="v">{len(cands)}</span><span class="s">current officeholders' latest campaigns</span></div>
    <div class="kpi"><span class="eyebrow">Raised</span><span class="v">${tot/1e6:,.2f}M</span><span class="s">{usd(ind)} from individuals · {usd(org)} from organizations</span></div>
    <div class="kpi"><span class="eyebrow">Donors with contracts</span><span class="v">{len(plist)}</span><span class="s">gifts to {off_matched} officials from contract holders</span></div>
    <div class="kpi"><span class="eyebrow">Same government</span><span class="v">{same}</span><span class="s">gifts where the contract is with the official's own government</span></div>
  </div>
  <div class="vt-filters mt-f"><label class="vf"><span>Government</span><select id="cmG" data-param="gov"><option value="">All</option>{opts}</select></label></div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="matches">Donors who also hold local contracts</h2><span class="muted">Same-government matches first</span></div>
    <div class="tablewrap"><table class="tx-table cm-table" id="cmM"><thead><tr><th scope="col">Contributor</th><th scope="col" class="num">Gave</th><th scope="col">To</th><th scope="col">Local contracts and payments</th></tr></thead><tbody>{mrows}</tbody></table></div>
    <p class="note">Matched by organization name against the contracts and payments on this site. Contracts can come before or after a gift; the dates are shown so you can compare. Gifts from a company's owners or employees as individuals are not matched.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="officials">Every official</h2><span class="muted">Most recent campaign for the seat they hold</span></div>
    <div class="tablewrap"><table class="tx-table cm-table" id="cmO"><thead><tr><th scope="col">Official</th><th scope="col" class="num">Raised</th><th scope="col" class="num">From individuals</th><th scope="col" class="num">From organizations</th><th scope="col" class="num">Own money</th><th scope="col">Donors</th></tr></thead><tbody>{rows}</tbody></table></div>
    <p class="note">"Raised" is the Supervisor of Elections' total of monetary contributions, which includes loans from the candidate. In-kind gifts (goods or services) are counted by type. For finished campaigns, spending includes leftover money given away or returned.</p></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">Sources and gaps</h2></div>
    <p>Every figure comes from the Bay County Supervisor of Elections' campaign finance system, including the itemized reports, which add up to the official totals. Organization names are shown as filed, except that spelling variants of the same name are combined, and names the filing system cut off at 30 characters are completed where the full name is clear. <a class="src" href="https://www.bayvotesfl.gov/candidates/candidate-committee-finances/" target="_blank" rel="noopener">Supervisor of Elections</a></p>
    <ul class="plain">{gaps}</ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>
(() => {{ const s = document.getElementById('cmG'); const run = () => document.querySelectorAll('#cmM tbody tr, #cmO tbody tr').forEach(tr => tr.hidden = !!s.value && tr.dataset.g !== s.value);
  const q = new URLSearchParams(location.search).get('gov'); if (q && [...s.options].some(o => o.value === q)) s.value = q; s.addEventListener('input', run); s.addEventListener('change', run); run(); }})();
</script>'''
