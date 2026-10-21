"""2026 local races (/elections): candidates on the ballot, their platforms in their own words, and their campaign money.

Kept separate from /public-money/campaign-money, which covers sitting officials' past campaigns.
Data: data/elections/candidates_2026.json (roster, platforms) + finance_2026.json (SOE filings).
Individual donors are counted, never named (site policy).
"""
import html, json, os, re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data', 'elections')
e = lambda s: html.escape(str(s if s is not None else ''))
GOVN = {'county': 'Bay County', 'schools': 'School Board', 'constitutional': 'County offices', 'special': 'Special districts', 'pc': 'Panama City',
        'pcb': 'Panama City Beach', 'lh': 'Lynn Haven', 'cw': 'Callaway', 'sp': 'Springfield', 'parker': 'Parker', 'mb': 'Mexico Beach'}
PARTY = {'REP': 'Republican', 'DEM': 'Democrat', 'NPA': 'No party', 'LPF': 'Libertarian', 'LIB': 'Libertarian', 'IND': 'Independent', 'WRI': 'Write-in'}
STATUS_LBL = {'filed': 'Filed to run', 'on_ballot': 'On the Nov. 3 ballot', 'won': 'Won', 'elected_unopposed': 'Elected unopposed', 'lost_primary': 'Lost primary', 'withdrew': 'Withdrew', 'lost': 'Lost', 'did_not_qualify': 'Did not qualify', 'appointed': 'Appointed'}


def usd(n):
    return '—' if n is None else f'${n:,.0f}'


def _key(n):
    n = re.sub(r'\(.*?\)|"[^"]*"', ' ', (n or '').lower())
    parts = [p for p in re.findall(r"[a-z']+", n) if p not in ('jr', 'sr', 'ii', 'iii', 'iv', 'dr', 'mr', 'mrs', 'ms') and len(p) > 1]
    return (parts[0] if parts else '', parts[-1] if parts else '')


def _last(n):
    return _key(n)[1]


def load():
    try:
        c = json.load(open(os.path.join(DATA, 'candidates_2026.json')))
    except FileNotFoundError:
        return None, None
    f = json.load(open(os.path.join(DATA, 'finance_2026.json'))) if os.path.exists(os.path.join(DATA, 'finance_2026.json')) else {'candidates': []}
    return c, f


def match_finance(cand, office, fin):
    """Finance record for a roster candidate: same last name, first name or initial agreeing, and an office that agrees."""
    url = (cand.get('soe_finance_url') or '').split('#')[0]
    if url:
        for r in fin:
            if (r.get('report_url') or '').split('#')[0] == url:
                return r
    k = _key(cand['name'])
    best = None
    for r in fin:
        rk = _key(r['name'])
        if rk[1] != k[1]:
            continue
        if not (rk[0] == k[0] or rk[0][:1] == k[0][:1]):
            continue
        dist = re.findall(r'\d+', office or ''), re.findall(r'\d+', r.get('office') or '')
        if dist[0] and dist[1] and dist[0][0] != dist[1][0]:
            continue
        best = r
        break
    return best


def _clean(t):
    t = re.sub(r'\s*SOE status: [^.;]*[.;]?', '', t or '')
    return re.sub(r'\s*Names shown as printed.*$', '', t).strip()


def _notes(r):
    out = []
    for n in r.get('notes') or []:
        if n.startswith('Includes') or 'No campaign finance reports' in n or 'total_spent' in n or 'other three' in n:
            continue
        if 'deletion line' in n:
            n = "One of the campaign's amended reports may count a $1,000 loan from the candidate twice. Figures here follow the Supervisor of Elections' totals."
        n = re.sub(r'Campaign filed a termination report \([^)]*\); account is closed\.', 'The campaign account is closed.', n)
        n = re.sub(r'\s*\(rpt \d+, line \d+\)|\s*\(D/A pair applied\)', '', n)
        out.append(n)
    return out[:3]


def money_block(r, raised_max):
    if not r:
        return '<p class="small muted">No campaign finance report found for this candidate in the Supervisor of Elections system.</p>'
    fi = r.get('from_individuals') or {}
    bt = r.get('by_type_total') or {}
    orgs = [x for x in r.get('contributors') or [] if x.get('type') not in ('candidate',)]
    org_tot = sum(v for k, v in bt.items() if k not in ('individual', 'candidate_self'))
    selfm = (r.get('candidate_self') or {})
    self_tot = (selfm.get('contributions') or 0) + (selfm.get('loans') or 0)
    agg = defaultdict(float)
    for x in orgs:
        agg[(x['name'], x.get('type'))] += x.get('amount') or 0
    top = sorted(agg.items(), key=lambda kv: -kv[1])
    w = lambda v: f'{(v or 0) / raised_max * 100:.1f}%' if raised_max and v else '0%'
    bands = fi.get('bands') or {}
    band_txt = ' · '.join(f'{e(k)}: {v.get("count", v) if isinstance(v, dict) else v}' for k, v in bands.items()) if bands else ''
    inc, outc = fi.get('in_county') or {}, fi.get('out_of_county') or {}
    exp = r.get('top_expenditures') or []
    TYPE = {'business': 'Business', 'pac': 'Political committee', 'party': 'Party', 'committee': 'Committee', 'other': 'Other'}
    return f'''<div class="el-money">
      <div class="el-raised"><b>{usd(r.get("total_raised"))}</b> raised · {usd(r.get("total_spent"))} spent <span class="muted small">through {e(r.get("through") or r.get("latest_report") or "latest report")}</span></div>
      <div class="el-bar" aria-hidden="true"><span class="i" style="width:{w(fi.get('total'))}"></span><span class="o" style="width:{w(org_tot)}"></span><span class="s" style="width:{w(self_tot)}"></span></div>
      <ul class="el-split small"><li><i class="i"></i>{usd(fi.get("total"))} from {fi.get("count") or 0} individuals</li><li><i class="o"></i>{usd(org_tot)} from organizations</li><li><i class="s"></i>{usd(self_tot)} own money{" (incl. " + usd(selfm.get("loans")) + " in loans)" if selfm.get("loans") else ""}</li>{f'<li>{usd(r.get("in_kind"))} of the total is in-kind (goods or services)</li>' if r.get("in_kind") else ""}</ul>
      <details class="flds"><summary>Every organization donor ({len(top)})</summary>{('<table class="tx-table el-dt"><thead><tr><th scope="col">Organization</th><th scope="col" class="num">Gave</th></tr></thead><tbody>' + "".join(f'<tr><th scope="row">{e(n)}<small>{e(TYPE.get(t, t or ""))}</small></th><td class="num">{usd(v)}</td></tr>' for (n, t), v in top) + '</tbody></table>') if top else '<p class="small muted">None reported.</p>'}
        <p class="small muted">Individual donors are counted, not named, on this site.{(" By size: " + band_txt + ".") if band_txt else ""}{f" {inc.get('count', 0)} gave from inside Bay County ({usd(inc.get('total'))}), {outc.get('count', 0)} from outside ({usd(outc.get('total'))})." if inc else ""} Every name is in the <a href="{e(r.get("report_url"))}" target="_blank" rel="noopener">full report</a>.</p></details>
      {f'<details class="flds"><summary>Where the money went</summary><table class="tx-table el-dt"><thead><tr><th scope="col">Paid to</th><th scope="col" class="num">Amount</th></tr></thead><tbody>' + "".join(f'<tr><th scope="row">{e(x["payee"])}<small>{e(x.get("purpose") or "")}</small></th><td class="num">{usd(x.get("total"))}</td></tr>' for x in exp) + '</tbody></table></details>' if exp else ''}
      {"".join(f'<p class="small muted">{e(n)}</p>' for n in _notes(r))}
      <p class="small"><a class="src" href="{e(r.get("report_url"))}" target="_blank" rel="noopener">Campaign finance report</a>{f' · <a class="src" href="{e(r["export_url"])}" target="_blank" rel="noopener">Itemized download</a>' if r.get("export_url") else ""}</p>
    </div>'''


def cand_card(c, r, raised_max, active):
    badges = ''.join(f'<span class="badge">{x}</span>' for x in [PARTY.get(c.get('party') or '', c.get('party')) if c.get('party') else None, 'Incumbent' if c.get('incumbent') else None] if x)
    st = c.get('status')
    stb = f'<span class="badge {"ok" if st in ("won", "elected_unopposed") else ""}">{e(STATUS_LBL.get(st, st))}</span>' if st and not active else ''
    links = [f'<a href="{e(c["website"])}" target="_blank" rel="noopener">Campaign website</a>'] if c.get('website') else []
    links += [f'<a href="{e(u)}" target="_blank" rel="noopener">{e(re.sub(r"^https?://(www\.)?|/.*$", "", u))}</a>' for u in (c.get('social') or [])[:3]]
    plat = ''.join(f'<li>{e(p)}</li>' for p in c.get('platform') or [])
    psrc = ' · '.join(f'<a class="src" href="{e(u)}" target="_blank" rel="noopener">Source {i + 1}</a>' for i, u in enumerate(c.get('platform_sources') or []))
    return f'''<article class="el-cand">
    <header><h4>{e(c["name"])}</h4><div class="el-badges">{badges}{stb}</div>{f'<p class="small muted">{e(c["background"])}</p>' if c.get("background") else ""}{f'<p class="small el-links">{" · ".join(links)}</p>' if links else ""}</header>
    <div class="el-plat"><h5>In their words</h5>{f'<ul>{plat}</ul><p class="small">{psrc}</p>' if plat else f'<p class="small muted">{e(c.get("platform_note") or "No platform statement found.")}</p>'}</div>
    <div><h5>Campaign money</h5>{money_block(r, raised_max)}</div></article>'''


def _okey(o):
    o = (o or '').lower()
    num = re.findall(r'\d+', o)
    kind = next((k for k in ('school', 'judge', 'commission', 'council', 'mayor', 'cdd', 'community development') if k in o), '')
    kind = 'cdd' if kind == 'community development' else kind
    place = next((k for k in ('panama city beach', 'panama city', 'lynn haven', 'callaway', 'springfield', 'parker', 'mexico beach', 'lake powell', 'bay county') if k in o), '')
    return (place if place != 'bay county' else '', kind, num[0] if num else '')


def _soe_status(st, active):
    st = (st or '').lower()
    if 'withdr' in st: return 'withdrew'
    if 'did not qualify' in st or 'not qualif' in st: return 'did_not_qualify'
    if 'defeat' in st: return 'lost'
    if 'elected' in st: return 'won'
    if 'qualified' in st or 'advanced' in st: return 'on_ballot' if active else 'filed'
    return 'filed'


GOV_OF_OFFICE = [('panama city beach', 'pcb'), ('panama city', 'pc'), ('lynn haven', 'lh'), ('callaway', 'cw'), ('springfield', 'sp'), ('parker', 'parker'), ('mexico beach', 'mb')]


def elections_page():
    C, F = load()
    if not C:
        return '<div class="page prose"><h1>2026 races</h1><p>Coming soon.</p></div>'
    fin = F.get('candidates') or []
    order = list(GOVN)
    races = sorted(C['races'], key=lambda r: (order.index(r.get('gov')) if r.get('gov') in order else 99, r.get('office') or ''))
    # every campaign the SOE lists for a 2026 race appears, even if the researched roster missed it
    matched = set()
    for r in races:
        for c in r.get('candidates') or []:
            m = match_finance(c, r.get('office'), fin)
            if m:
                matched.add(id(m))
    for m in fin:
        if id(m) in matched or '2026' not in (m.get('election') or ''):
            continue
        k = _okey(m.get('soe_office') or m.get('office'))
        race = next((r for r in races if _okey(r.get('office'))[1:] == k[1:] and (not k[0] or k[0] in (r.get('office') or '').lower())), None)
        if race:
            race.setdefault('candidates', []).append({'name': m['name'], 'party': {'Republican': 'REP', 'Democrat': 'DEM', 'Libertarian': 'LIB', 'No Party Affiliation': 'NPA'}.get(m.get('party'), None),
                'status': _soe_status(m.get('soe_status'), race.get('status') == 'on_ballot_nov3'), 'platform': [], 'soe_finance_url': m.get('report_url'),
                'platform_note': 'Listed in the Supervisor of Elections filings; platform not yet reviewed.'})
            matched.add(id(m))
    upcoming = defaultdict(list)
    for m in fin:
        if '2027' in (m.get('election') or ''):
            upcoming[m.get('office') or m.get('soe_office')].append(m)
    active = [r for r in races if r.get('status') == 'on_ballot_nov3']
    decided = [r for r in races if r.get('status') != 'on_ballot_nov3']
    used = set()

    def race_html(r, is_active):
        cands = sorted(r.get('candidates') or [], key=lambda c: (c.get('status') in ('withdrew',), _last(c['name'])))
        recs = []
        for c in cands:
            m = match_finance(c, r.get('office'), fin)
            if m:
                used.add(id(m))
            recs.append(m)
        mx = max([x.get('total_raised') or 0 for x in recs if x] or [0])
        MAIN = ('on_ballot', 'won', 'elected_unopposed', 'appointed', 'filed')
        main = [(c, m) for c, m in zip(cands, recs) if c.get('status') in MAIN]
        rest = [(c, m) for c, m in zip(cands, recs) if c.get('status') not in MAIN]
        cards = ''.join(cand_card(c, m, mx, is_active) for c, m in main)
        if rest:
            lbl = 'Also ran' if any(c.get('status') in ('lost_primary', 'lost') for c, _ in rest) else 'Also filed'
            cards_rest = ''.join(cand_card(c, m, mx, False) for c, m in rest)
            cards += f'<details class="el-others"><summary>{lbl}: {", ".join(e(c["name"]) for c, _ in rest)}</summary><div class="el-cands">{cards_rest}</div></details>'
        sub = []
        if r.get('incumbent'):
            sub.append(f'Incumbent: {e(r["incumbent"])}')
        if r.get('seat_type'):
            sub.append('Nonpartisan' if r['seat_type'] == 'nonpartisan' else 'Partisan')
        if not is_active:
            lbl = {'decided_primary': 'Decided in the Aug. 18 primary', 'elected_unopposed': 'Elected unopposed', 'decided_earlier_2026': 'Decided earlier in 2026'}.get(r.get('status'), r.get('status'))
            sub.append(e(lbl) + (f' · {e(r["winner"])}' if r.get('winner') else ''))
        res = f' · <a class="src" href="{e(r["result_url"])}" target="_blank" rel="noopener">Official results</a>' if r.get('result_url') else ''
        return f'''<section class="el-race" data-g="{e(r.get("gov"))}" id="{e(r.get("id"))}"><div class="el-rh"><span class="eyebrow">{e(GOVN.get(r.get("gov"), ""))}</span><h3>{e(r["office"])}</h3><p class="small muted">{" · ".join(sub)}{res}</p>{f'<p class="small">{e(_clean(r["notes"]))}</p>' if r.get("notes") else ""}</div>
      <div class="el-cands">{cards}</div></section>''' if is_active else f'''<details class="el-race el-dec" data-g="{e(r.get("gov"))}" id="{e(r.get("id"))}"><summary><span class="eyebrow">{e(GOVN.get(r.get("gov"), ""))}</span><b>{e(r["office"])}</b><span class="small muted">{" · ".join(sub[-1:])}</span></summary><div class="el-rh"><p class="small muted">{" · ".join(sub)}{res}</p>{f'<p class="small">{e(_clean(r["notes"]))}</p>' if r.get("notes") else ""}</div>
      <div class="el-cands">{cards}</div></details>'''

    act = ''.join(race_html(r, True) for r in active)
    U = C.get('upcoming_2027') or {}
    up_races = []
    for office, ms in sorted(upcoming.items()):
        g = next((v for k, v in GOV_OF_OFFICE if k in office.lower()), '')
        info = U.get(office) or {}
        cands = [{'name': m['name'], 'party': None, 'status': _soe_status(m.get('soe_status'), False), 'soe_finance_url': m.get('report_url'),
                  **(info.get('candidates', {}).get(m['name']) or {'platform': [], 'platform_note': 'Platform not yet reviewed.'})} for m in ms]
        up_races.append({'id': 'up-' + re.sub(r'[^a-z0-9]+', '-', office.lower()), 'gov': g, 'office': office, 'status': 'upcoming', 'candidates': cands,
                         'notes': info.get('notes') or 'Filed with the Supervisor of Elections for the April 20, 2027 city election. Qualifying hasn\'t happened yet, so more candidates may file.'})
    up = ''.join(race_html(r, True) for r in up_races)
    up_html = f'<section class="tx-sec" id="next"><div class="sec-hd"><h2>Already running for April 2027</h2><span class="muted">City elections: candidates who have opened a campaign</span></div>{up}</section>' if up else ''
    dec = ''.join(race_html(r, False) for r in decided)
    opts = ''.join(f'<option value="{k}">{e(v)}</option>' for k, v in GOVN.items() if any(r.get('gov') == k for r in races))
    ncand = sum(len(r.get('candidates') or []) for r in active)
    raised = sum((m.get('total_raised') or 0) for m in fin if any(match_finance(c, r.get('office'), [m]) for r in active for c in r.get('candidates') or []))
    gaps = ''.join(f'<li>{e(g)}</li>' for g in (C.get('gaps') or []) + (F.get('gaps') or []))
    return f'''<div class="page tax el">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Get involved · 2026 elections</span><h1>Who's running in 2026</h1>
    <p class="lede">Every local race on Bay County ballots this year: the candidates, what they say they'll do in their own words, links to their campaigns, and where their campaign money comes from. BayCounty.me doesn't endorse or rate candidates.</p></div>
    <div class="stamp"><a class="pill" href="https://www.bayvotesfl.gov/" target="_blank" rel="noopener">Supervisor of Elections ↗</a><span>Campaign reports checked {e(F.get("as_of") or C.get("as_of"))}</span></div></header>
  <div class="kpis">
    <div class="kpi"><span class="eyebrow">On the Nov. 3 ballot</span><span class="v">{len(active)}</span><span class="s">local races · {ncand} candidates</span></div>
    <div class="kpi"><span class="eyebrow">Raised so far</span><span class="v">${raised/1e3:,.0f}K</span><span class="s">by candidates in those races</span></div>
    <div class="kpi"><span class="eyebrow">Already decided</span><span class="v">{len(decided)}</span><span class="s">won in the primary, unopposed or earlier in 2026</span></div>
  </div>
  <div class="callout">To check your registration, find your polling place or see your sample ballot, use the <a href="https://www.bayvotesfl.gov/" target="_blank" rel="noopener">Bay County Supervisor of Elections</a> or <a href="https://vote.gov" target="_blank" rel="noopener">vote.gov</a>. <a href="/my-address">My Address</a> shows your County Commission and School Board districts.</div>
  <nav class="jump" aria-label="On this page"><a href="#active">On the ballot</a>{'<a href="#next">April 2027</a>' if upcoming else ''}<a href="#decided">Already decided</a><a href="#how">How we did this</a></nav>
  <div class="vt-filters mt-f"><label class="vf"><span>Government</span><select id="elG"><option value="">All races</option>{opts}</select></label></div>
  <section class="tx-sec" id="active"><div class="sec-hd"><h2>On the November 3 ballot</h2><span class="muted">Candidates in alphabetical order</span></div>{act or '<p class="muted">No local races found on the ballot.</p>'}</section>
  {up_html}
  <section class="tx-sec el-past" id="decided"><div class="sec-hd"><h2>Already decided in 2026</h2><span class="muted">Shown separately: these campaigns are over</span></div>{dec or '<p class="muted">None.</p>'}</section>
  <section class="tx-sec method" id="how"><div class="sec-hd"><h2>How we did this</h2></div>
    <p><b>Platforms</b> are summarized only from each candidate's own campaign website, campaign social pages or questionnaire answers they wrote, with links to each source. If we couldn't find a statement from the candidate, we say so rather than fill in from news coverage. Candidates are listed alphabetically.</p>
    <p><b>Money</b> comes from the campaign reports candidates file with the Bay County Supervisor of Elections, through the date shown. Organizations are listed by name; gifts from individual people are counted and totaled, and every name is in the linked report. Florida caps gifts to local candidates at $1,000 per person or business per election.</p>
    <p>Sitting officials' past campaigns are on the <a href="/public-money/campaign-money">Campaign Money</a> page.</p>
    {f'<details class="gaps"><summary>What we couldn\'t find</summary><ul>{gaps}</ul></details>' if gaps else ''}</section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>
(() => {{ const s = document.getElementById('elG'), q = new URLSearchParams(location.search).get('gov');
  const run = () => document.querySelectorAll('.el-race').forEach(r => r.hidden = !!s.value && r.dataset.g !== s.value);
  if (q) s.value = q; s.addEventListener('input', () => {{ history.replaceState(null, '', s.value ? '?gov=' + s.value : location.pathname); run(); }}); run(); }})();
</script>'''
