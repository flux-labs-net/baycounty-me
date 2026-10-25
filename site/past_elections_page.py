"""Past local elections (/elections/past): every local campaign from 2016 through 2025 and its money.

Data: data/campaign/campaign_history.json (data/campaign/history.py), published as the campaign-history and
campaign-contributions-history datasets. Individual donors are counted and summed, never named (site policy);
businesses, committees and parties are named.
"""
import html, json, os, re
from collections import defaultdict
from city_filter import city_bar, data_g, by_city, gkey, KEYS
from entity_links import person, vendor
from vendors import ids

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'data', 'campaign', 'campaign_history.json')
e = lambda s: html.escape(str(s if s is not None else ''))
OUTCOME = {'won': ('Won', 'ok'), 'lost': ('Lost', ''), 'withdrew': ('Withdrew', ''), 'did not qualify': ('Did not qualify', '')}
TYPE = {'business': 'Business', 'pac': 'Political committee', 'committee': 'Candidate committee', 'party': 'Party', 'other': 'Other group'}
GOV_ORDER = ['county', 'schools', 'sheriff', 'clerk', 'property_appraiser', 'tax_collector', 'soe', 'county_court', 'pc', 'pcb', 'lh', 'cw', 'sp', 'parker', 'mb',
             'lake_powell_cdd', 'beach_mosquito']


def usd(n):
    return '—' if n is None else f'${n:,.0f}'


def city(gid):
    """City filter key: county offices and judges count with Bay County; special districts always show."""
    return gkey(gid) or ('county' if gid == 'county_court' else '')


def load():
    try:
        return json.load(open(SRC))
    except FileNotFoundError:
        return None


def _orgs(c):
    agg = defaultdict(float)
    for x in c.get('contributors') or []:
        if x.get('type') not in ('candidate', 'individual') and x.get('kind') != 'interest':
            agg[(x['name'], x.get('type'))] += x.get('amount') or 0
    return sorted(((n, t, round(v, 2)) for (n, t), v in agg.items() if abs(v) > 0.005), key=lambda r: -r[2])


def _org_total(c):
    bt = c.get('by_type_total') or {}
    return round(sum(v for k, v in bt.items() if k not in ('individual', 'candidate_self')), 2)


def race_html(office, cs):
    cs = sorted(cs, key=lambda c: (c.get('outcome') != 'won', c.get('outcome') in ('withdrew', 'did not qualify'), -(c.get('total_raised') or 0)))
    rows, donors = '', ''
    for c in cs:
        fi = c.get('from_individuals') or {}
        lbl, tone = OUTCOME.get(c.get('outcome'), ((c.get('soe_status') or '').replace('Inactive - ', '') or '—', ''))
        party = f'<small>{e(c["party"])}</small>' if c.get('party') and c['party'] != 'Nonpartisan' else ''
        rows += (f'<tr><th scope="row">{person(c["name"])}{party}</th><td><span class="badge {tone}">{e(lbl)}</span></td>'
                 f'<td class="num">{usd(c.get("total_raised"))}</td><td class="num">{usd(fi.get("total"))}<small>{fi.get("count") or 0} gifts</small></td>'
                 f'<td class="num">{usd(_org_total(c))}</td><td class="num">{usd((c.get("by_type_total") or {}).get("candidate_self"))}</td>'
                 f'<td class="num">{usd(c.get("total_spent"))}</td><td><a class="src" href="{e(c.get("report_url"))}" target="_blank" rel="noopener">Report</a></td></tr>')
        orgs = _orgs(c)
        if orgs:
            li = ''.join(f'<li>{vendor(n) if t == "business" else e(ids.biz_case(n))}{"" if t == "business" else " <small>" + e(TYPE.get(t, t)) + "</small>"} · {usd(v)}</li>' for n, t, v in orgs)
            donors += f'<div class="pe-donors"><h5>{e(c["name"])}: {len(orgs)} organization{"s" if len(orgs) != 1 else ""}</h5><ul class="pe-list small">{li}</ul></div>'
    gid = cs[0].get('gov_id')
    det = f'<details class="flds"><summary>Organizations that gave in this race</summary>{donors}</details>' if donors else ''
    return f'''<div class="pe-race"{data_g(city(gid))}><h4>{e(office)}</h4>
      <div class="tablewrap"><table class="tx-table pe-table"><thead><tr><th scope="col">Candidate</th><th scope="col">Result</th><th scope="col" class="num">Raised</th><th scope="col" class="num">From individuals</th><th scope="col" class="num">From organizations</th><th scope="col" class="num">Own money</th><th scope="col" class="num">Spent</th><th scope="col"><span class="sr-only">Source</span></th></tr></thead><tbody>{rows}</tbody></table></div>
      {det}</div>'''


def _elec_title(c):
    m = re.match(r'(\d{4}) ', c['election'])
    kind = 'City elections' if re.search(r'municipal|super tuesday', c['election'], re.I) else 'Primary and general election'
    if 'referendum' in c['election'].lower():
        kind = 'City elections'
    d = c['election_date']
    import datetime
    dt = datetime.date.fromisoformat(d)
    when = dt.strftime('%B ') + str(dt.day) + (', ' + dt.strftime('%Y') if not m else '')
    if c.get('primary_date'):
        p = datetime.date.fromisoformat(c['primary_date'])
        when = p.strftime('%b. ') + str(p.day) + ' primary, ' + dt.strftime('%b. ') + str(dt.day) + ' general'
    return kind, when


def past_elections_page():
    d = load()
    if not d:
        return '<div class="page prose"><h1>Past local elections</h1><p>Coming soon.</p></div>'
    C = d['candidates']
    years = sorted({c['year'] for c in C}, reverse=True)
    secs, jump = '', ''
    for y in years:
        cy = [c for c in C if c['year'] == y]
        by_el = defaultdict(list)
        for c in cy:
            by_el[c['election_date']].append(c)
        body = ''
        for date in sorted(by_el, reverse=True):
            ce = by_el[date]
            kind, when = _elec_title(ce[0])
            races = defaultdict(list)
            for c in ce:
                races[(GOV_ORDER.index(c['gov_id']) if c['gov_id'] in GOV_ORDER else 99, c['office'])].append(c)
            body += f'<div class="pe-el"><h3>{e(kind)} <span class="muted small">{e(when)}</span></h3>' + ''.join(race_html(o, cs) for (_, o), cs in sorted(races.items())) + '</div>'
        sub = lambda cs: f'{len(cs)} campaign{"s" if len(cs) != 1 else ""} · {usd(sum(c.get("total_raised") or 0 for c in cs))} raised' if cs else 'No races'
        yk = {'': sub(cy), **{k: sub([c for c in cy if city(c['gov_id']) in (k, '')]) for k in KEYS}}
        secs += f'''<section class="tx-sec pe-year" id="y{y}" data-city-empty="No {{city}} races in {y}."><div class="sec-hd"><h2>{y}</h2><span class="muted"{by_city(yk)}>{yk['']}</span></div>{body}</section>'''
        jump += f'<a href="#y{y}">{y}</a>'
    gk = [k for k in KEYS if any(city(c['gov_id']) == k for c in C)]
    pick = lambda k: [c for c in C if not k or city(c['gov_id']) == k]
    per = lambda fn: by_city({'': fn(pick('')), **{k: fn(pick(k)) for k in gk}})
    n_camp = lambda cs: f'{len(cs):,}'
    raised = lambda cs: f'${sum(c.get("total_raised") or 0 for c in cs) / 1e6:,.1f}M'
    orgs = lambda cs: f'${sum(_org_total(c) for c in cs) / 1e6:,.1f}M'
    indiv = lambda cs: f'${sum((c.get("from_individuals") or {}).get("total") or 0 for c in cs) / 1e6:,.1f}M'
    gaps = ''.join(f'<li>{e(g)}</li>' for g in d.get('gaps') or [])
    s = d['summary']
    return f'''<div class="page tax pe">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Get involved · Past elections</span><h1>Past local elections, 2016 to 2025</h1>
    <p class="lede">Every candidate who ran for a local office in Bay County from 2016 through 2025, winners and losers, and where their campaign money came from. Businesses and groups that gave are named; gifts from individual people are counted and totaled.</p></div>
    <div class="stamp"><a class="pill" href="/elections">2026 races</a><a class="pill" href="/connections/campaign-gifts">Current officials</a><span>Supervisor of Elections reports, checked {e(d.get("as_of"))}</span></div></header>
  {city_bar(gk, hide=True, note='Bay County includes county offices and judges; special districts always show')}
  <div class="kpis">
    <div class="kpi"><span class="eyebrow">Campaigns</span><span class="v"{per(n_camp)}>{n_camp(C)}</span><span class="s">in {len(years)} years of local elections</span></div>
    <div class="kpi"><span class="eyebrow">Raised</span><span class="v"{per(raised)}>{raised(C)}</span><span class="s">money and in-kind, all campaigns</span></div>
    <div class="kpi"><span class="eyebrow">From individuals</span><span class="v"{per(indiv)}>{indiv(C)}</span><span class="s">counted, not named</span></div>
    <div class="kpi"><span class="eyebrow">From organizations</span><span class="v"{per(orgs)}>{orgs(C)}</span><span class="s">businesses, committees and parties, named</span></div>
  </div>
  <nav class="jump" aria-label="Years">{jump}<a href="#how">How we did this</a></nav>
  {secs}
  <section class="tx-sec method" id="how"><div class="sec-hd"><h2>How we did this</h2></div>
    <p>Every figure comes from the campaign reports candidates filed with the <a href="https://www.bayvotesfl.gov/candidates/candidate-committee-finances/" target="_blank" rel="noopener">Bay County Supervisor of Elections</a>. Raised is money plus in-kind gifts, including any loans from the candidate. Spent includes refunds and leftover money a closed campaign gave away, so it often equals what was raised.</p>
    <p>Each campaign's itemized report was checked against the Supervisor of Elections' totals: {s["reconciled"]} match exactly, {s["no_activity"]} raised nothing, and {s["not_reconciled"]} differ slightly (the Supervisor of Elections' totals are shown). Organizations are named as filed. A filing that coded a person as a business was corrected, so that person is counted with the individuals.</p>
    <p>The 2026 races are on <a href="/elections">Who's running in 2026</a>. Download this data as <a href="/open-data">campaign-history and campaign-contributions-history</a>, or use the <a href="/developers">API</a>.</p>
    {f'<details class="gaps"><summary>What isn\'t here</summary><ul>{gaps}</ul></details>' if gaps else ''}</section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<style>.pe-el{{margin:18px 0 8px}}.pe-el h3{{margin:0 0 10px}}.pe-race{{margin:0 0 18px}}.pe-race h4{{margin:0 0 6px;font-size:1rem}}
.pe-table th small,.pe-table td small{{display:block;color:var(--muted);font-weight:400}}.pe-donors{{margin:8px 0}}.pe-donors h5{{margin:0 0 4px;font-size:.9rem}}
.pe-list{{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px 24px}}.pe-list small{{color:var(--muted)}}@media (max-width:640px){{.pe-list{{grid-template-columns:1fr}}}}</style>
'''
