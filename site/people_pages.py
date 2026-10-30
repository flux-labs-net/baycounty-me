"""Profiles of people and every other entity.

/people                     every official, department leader and 2026 candidate
/people/<id>                one person: roles, pay, 2026 race, campaign money from organizations, votes, votes on
                            donors' contracts, boards and businesses (hand-checked, from the API), and a mini network
/profile/<kind>/<id>        every other company, nonprofit, board member, business and committee: one page shell
                            (vercel.json rewrites the path to /profile) that site/profile.js fills from
                            GET /api/v1/entities/<kind>:<id>

profile_section() is the "Connections" block (mini network + every connection) that vendor and government pages reuse.
Individual campaign donors are named only when they run a registered business (dataset owner-gifts); everyone else
is counted in totals only.
"""
import html, json, os, shutil
from collections import Counter, defaultdict

import entity_graph as EG
from money_map import gift_when_text
from entity_links import a as link, gov as gov_link

HERE = os.path.dirname(os.path.abspath(__file__))
e = lambda s: html.escape(str(s if s is not None else ''))
NOTE = ("A campaign gift and a vote, contract or payment appearing together are facts in two public records. "
        "They do not show why anyone voted the way they did or how a contract was awarded.")


def money(n):
    if n is None:
        return '—'
    s, n = ('−' if n < 0 else ''), abs(n)
    return s + (f'${n/1e6:,.2f}M' if n >= 1e6 else f'${n:,.0f}')


def src(u, label='Source'):
    return f'<a class="src" href="{e(u)}" target="_blank" rel="noopener">{e(label)}</a>' if u else ''


def embed(eid):
    """The entity and its build-time connections, in the API's shape (GET /api/v1/entities/<id>)."""
    from ui import photos
    G = EG.build()
    x = G.ents[eid]
    ph = photos()
    face = lambda i: {'photo': ph[i]['photo_url']} if i in ph else {}
    conns = []
    for l, o, d in EG.neighbors(eid):
        out = d == 'out'
        conns.append({'relation': l['relation'], 'label': EG.RELATION[l['relation']][0 if out else 1], 'direction': d,
                      'other': {'entity_id': o['entity_id'], 'name': o['name'], 'kind': o['kind'], 'kind_label': o.get('label') or EG.KIND_LABEL[o['kind']],
                                'page_url': EG.page_url(o['entity_id']), **face(o['entity_id'])},
                      'amount': round(l['amount'], 2) if l['amount'] is not None else None, 'records': l['records'],
                      'first_date': EG._dates(l['dates'])[0], 'last_date': EG._dates(l['dates'])[1], 'detail': '; '.join(l['detail']) or None,
                      'source_url': l['source_url']})
    ent = _profiles().get(eid) or {'entity_id': eid, 'kind': x['kind'], 'name': x['name'], 'page_url': EG.page_url(eid)}
    if eid in ph:
        ent = {**ent, 'photo': {'url': ph[eid]['photo_url'], 'credit': ph[eid]['credit'], 'source_url': ph[eid]['source_url']}}
    return {'entity': ent, 'connections': conns}


_C = {}


def _profiles():
    if 'profiles' not in _C:
        _C['profiles'] = {r['entity_id']: r for r in EG.profile_rows()}
    return _C['profiles']


def profile_section(eid, heading='Connections', sub='Everyone and everything this connects to in the records'):
    _profiles()
    d = embed(eid)
    data = json.dumps(d, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    return f'''<section class="tx-sec" id="pf" data-id="{e(eid)}"><div class="sec-hd"><h2 id="connections">{e(heading)}</h2><span class="muted">{e(sub)}</span></div>
    <div class="pf-net" id="pfNet" data-nolink></div>
    <div id="pfLive" class="pf-live small" hidden>Rows marked "checked by hand" come from name matches an editor confirmed against the public filing.</div>
    <details class="pf-all"><summary>Every connection ({len({(c['relation'], c['direction'], c['other']['entity_id']) for c in d['connections']}):,})</summary><div id="pfList" data-nolink></div></details>
    <p class="note">{e(NOTE)} Individual campaign donors are named only when they run a registered business; others are counted in totals. <a href="/api/v1/entities/{e(eid)}">This profile in the API</a>.</p>
    <script type="application/json" id="pfData">{data}</script></section>'''


ASSETS = '<link rel="stylesheet" href="/assets/tax.css"><link rel="stylesheet" href="/assets/connections.css"><link rel="stylesheet" href="/assets/profile.css"><script src="/assets/profile.js" defer></script>'


def copy_assets(out_dir):
    for f in ('profile.js', 'profile.css'):
        shutil.copy(os.path.join(HERE, f), os.path.join(out_dir, 'assets', f))


# ---------- /people/<id> ----------
def _by_person(did, col='person_id'):
    out = defaultdict(list)
    for r in EG._ds(did):
        if r.get(col):
            out[r[col]].append(r)
    return out


def _people():
    return (EG.ids._load('people.json') or {'people': []})['people']


def person_page(pid):
    G = EG.build()
    eid = 'person:' + pid
    p = next(x for x in _people() if x['id'] == pid)
    x = G.ents[eid]
    cand = _by_person('candidates-2026').get(pid, [])
    fin = _by_person('campaign-finance').get(pid, [])
    hist = sorted(_by_person('campaign-history').get(pid, []), key=lambda r: r.get('election_date') or '', reverse=True)  # every campaign since 2016
    pay = _by_person('officials-pay').get(pid, []) + _by_person('salary-leaders').get(pid, [])
    mv = sorted(_by_person('member-votes').get(pid, []), key=lambda r: r.get('date') or '', reverse=True)
    names = {x['name']} | set(x['aliases'])
    mm = [r for r in EG._ds('money-map-votes') if r.get('official') in names]
    nb = EG.neighbors(eid)
    gifts = [(l, o) for l, o, d in nb if l['relation'] == 'gift' and d == 'in' and o['kind'] != 'owner']
    owner_gifts = [(l, o) for l, o, d in nb if l['relation'] == 'gift' and d == 'in' and o['kind'] == 'owner']
    voted = [(l, o) for l, o, d in nb if l['relation'] == 'voted']
    govs = list(dict.fromkeys(g for g in (p.get('gov_ids') or [])))
    kpi = lambda lbl, val, s: f'<div class="kpi"><span class="eyebrow">{e(lbl)}</span><span class="v">{val}</span><span class="s">{e(s)}</span></div>'
    tally = Counter(str(r.get('vote')).lower() for r in mv)
    raised = next((r['total_raised'] for r in cand if r.get('total_raised')), None) or next((r['total_raised'] for r in fin if r.get('total_raised')), None) or next((r['total_raised'] for r in hist if r.get('total_raised')), None)
    sal = next((r.get('annual') or r.get('salary') for r in pay if (r.get('annual') or r.get('salary'))), None)
    kp = ''.join([kpi('Recorded votes', f'{len(mv):,}', ', '.join(f'{n} {k}' for k, n in tally.most_common(3)) or 'money votes on file') if mv else '',
                  kpi('Campaign raised', money(raised), 'most recent campaign on file') if raised else '',
                  kpi('From businesses and groups', money(sum(l['amount'] or 0 for l, _ in gifts)), f'{len(gifts)} donors named on this page') if gifts else '',
                  kpi('From business owners', money(sum(l['amount'] or 0 for l, _ in owner_gifts)), f'{len(owner_gifts)} people who run a business, named') if owner_gifts else '',
                  kpi('Pay', money(sal), 'annual, latest on file') if sal else ''])
    secs = vsecs = ''  # vote sections go right under the connections graph
    # roles
    roles = []
    for g in govs:
        rs = [r for r in p['roles'] if r.get('gov_id') == g and r.get('source') != 'campaign_history']  # past races go under "Ran for"
        if not rs:
            continue
        oh = [f"{r['role']} ({r['years']})" for r in rs if r.get('source') == 'officeholders']  # elected seats since 2016, with years
        best = next((r['role'] for r in rs if r.get('source') in ('salaries', 'officials-pay')), None) or next((r['role'].split(':', 1)[-1].strip() for r in rs if r.get('source') == 'campaign'), None) or (('; '.join(oh)) if oh else (rs[0]['role'] if rs else ''))
        roles.append(f'<li>{e(best[:1].upper() + best[1:])}<span>{gov_link(g)}</span></li>')
    # the facts card at the top right: where they serve, the 2026 race, pay and votes on file
    facts = []
    if roles:
        seat_roles = [r for r in p['roles'] if r.get('source') == 'officeholders'] or [r for r in p['roles'] if r.get('source') == 'votes']  # terms beat vote-record member lists
        former = bool(seat_roles) and all((r.get('role') or '').startswith('former') for r in seat_roles)
        facts.append(('Served' if former and not any(r.get('source') in ('salaries', 'officials-pay', 'campaign') for r in p['roles']) else 'Serves', f'<ul>{"".join(roles)}</ul>'))
    ran = [r for r in p['roles'] if r.get('source') == 'campaign_history']
    if ran:
        ran = sorted(ran, key=lambda r: -(r.get('year') or 0))
        facts.append(('Ran for', '<ul>' + ''.join(f'<li>{e(r["office"])}<span>{r["year"]}{" · " + e(r["outcome"]) if r.get("outcome") else ""}</span></li>' for r in ran[:4]) + '</ul>'))
    for c in cand[:1]:
        facts.append(('On the ballot', f'{e(c["office"])}<span>November 3, 2026{" · incumbent" if c.get("incumbent") else ""}</span>'))
    facts_h = ''.join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in facts)
    # 2026 race
    for c in cand:
        plat = ''.join(f'<li>{e(t)}</li>' for t in (c.get('platform') or []))
        secs += f'''<section class="tx-sec"><div class="sec-hd"><h2 id="race" data-tile="2026 race">On the 2026 ballot: {e(c["office"])}</h2><span class="muted">{e((c.get("status") or "").replace("_", " "))}{" · incumbent" if c.get("incumbent") else ""}</span></div>
    {f'<ul class="pp-plat">{plat}</ul><p class="small muted">Platform in the candidate\'s own words, summarized from their filings and campaign pages.</p>' if plat else ''}
    <p class="small">Raised {money(c.get("total_raised"))} · spent {money(c.get("total_spent"))} · from individuals {money(c.get("from_individuals_total"))} ({c.get("from_individuals_count") or 0} gifts, not named) · from organizations {money(c.get("from_organizations"))} · own money {money(c.get("own_money"))}{f' · <a class="src" href="{e(c["finance_report_url"])}" target="_blank" rel="noopener">Campaign report</a>' if c.get("finance_report_url") else ''}{f' · <a href="{e(c["website"])}" target="_blank" rel="noopener nofollow">Campaign website</a>' if c.get("website") else ''}</p>
    <p class="small"><a href="/elections">Every 2026 race</a></p></section>'''
    # campaign money
    if gifts or fin or hist:
        gr = ''.join(f'<tr><th scope="row">{link(o["entity_id"])}<small>{e(EG.KIND_LABEL[o["kind"]])}</small></th><td class="num">{money(l["amount"])}</td><td class="small">{e(", ".join(sorted(set(l["dates"]))))}</td><td class="small">{e("; ".join(l["detail"]))}</td><td>{src(l["source_url"], "Report")}</td></tr>'
                     for l, o in sorted(gifts, key=lambda t: -(t[0]['amount'] or 0)))
        tot = ''.join(f'<li>{e(r.get("election") or "")}: raised {money(r.get("total_raised"))} from {r.get("n_contributions") or 0} contributions{" · " + src(r.get("report_url"), "Report") if r.get("report_url") else ""}</li>' for r in fin)
        fin_urls = {r.get('report_url') for r in fin}
        tot += ''.join(f'<li>{e(r["election_year"])} · {e(r["office"])}{" (" + e(r["outcome"]) + ")" if r.get("outcome") else ""}: raised {money(r.get("total_raised"))}, {money(r.get("from_individuals_total"))} of it from {r.get("from_individuals_count") or 0} individual gifts (not named){" · " + src(r.get("report_url"), "Report") if r.get("report_url") else ""}</li>'
                       for r in hist if r.get('report_url') not in fin_urls)
        secs += f'''<section class="tx-sec"><div class="sec-hd"><h2 id="gifts" data-tile="Campaign gifts">Campaign gifts from businesses and groups</h2><span class="muted">Supervisor of Elections reports</span></div>
    {f'<ul class="plain">{tot}</ul>' if tot else ''}
    {f'<div class="tablewrap"><table class="tx-table vd-table"><thead><tr><th scope="col">From</th><th scope="col" class="num">Gave</th><th scope="col">Dates</th><th scope="col">Campaign</th><th scope="col">Source</th></tr></thead><tbody>{gr}</tbody></table></div>' if gr else '<p class="muted small">No gifts from businesses, PACs or committees in the reports on file.</p>'}
    <p class="note">Businesses, PACs and committees are named here, and people who run a registered business are listed below. Other gifts from individual people are counted in the totals but never named. <a href="/connections/campaign-gifts">Campaign gifts</a> has every official and <a href="/elections/past">Past elections</a> every local race since 2016.</p></section>'''
    if owner_gifts:
        def runs(oid):
            return [o for l, o, d in EG.neighbors(oid) if l['relation'] == 'runs' and d == 'out']
        orow = ''
        for l, o in sorted(owner_gifts, key=lambda t: (-(t[0]['amount'] or 0), t[1]['name'])):
            bs = runs(o['entity_id'])
            more = f' and {len(bs) - 4} more' if len(bs) > 4 else ''
            orow += (f'<tr><th scope="row">{link(o["entity_id"])}</th><td class="wrap small">{", ".join(link(b["entity_id"]) for b in bs[:4])}{more}</td>'
                     f'<td class="num">{money(l["amount"])}</td><td class="small">{e(", ".join(sorted(set(l["dates"]))))}</td><td>{src(l["source_url"], "Report")}</td></tr>')
        secs += f'''<section class="tx-sec"><div class="sec-hd"><h2 id="owner-gifts" data-tile="Owner gifts">Personal gifts from business owners</h2><span class="muted">{len(owner_gifts)} people</span></div>
    <div class="tablewrap"><table class="tx-table vd-table"><thead><tr><th scope="col">Person</th><th scope="col">Runs</th><th scope="col" class="num">Gave</th><th scope="col">Dates</th><th scope="col">Source</th></tr></thead><tbody>{orow}</tbody></table></div>
    <p class="note">People who gave as individuals and whose name and street address on the filing are the same as an officer, manager or registered agent of a for-profit business on Sunbiz. Addresses are not shown. A gift from a business owner is a fact in the records, not a sign that the business wanted anything.</p></section>'''
    # votes on donors' contracts
    if mm:
        rows = ''.join(f'<li><b>{e(r["vote_date"])}</b>: voted {e(r["vote"])} on {e(r["item"])}{" · " + money(r["amount"]) if r.get("amount") else ""} ({e(r["outcome"])} {e(r["tally"])}{", consent agenda" if r.get("consent_agenda") else ""}). {link_name_vendor(r["donor"])} gave {money(r["gift_amount"])} to {e(r["official"])}’s campaign{(" " + e(gift_when_text(r.get("gift_dates"), r["vote_date"]))) if r.get("gift_dates") else ""}. <a class="src" href="{e(r["source_url"])}" target="_blank" rel="noopener">Minutes</a></li>' for r in sorted(mm, key=lambda r: r['vote_date'], reverse=True))
        vsecs += f'<section class="tx-sec"><div class="sec-hd"><h2 id="donor-votes" data-tile="Donor votes">Votes on contracts with their own donors</h2><span class="muted">From the Money map</span></div><ul class="plain mm-list">{rows}</ul><p class="note">{e(NOTE)}</p></section>'
    # votes on companies' contracts
    if voted:
        vr = ''.join(f'<tr><th scope="row">{link(o["entity_id"])}</th><td class="small">{e("; ".join(l["detail"]))}</td><td class="num">{l["records"]}</td><td class="small">{e(min(l["dates"]) if l["dates"] else "")}{(" to " + e(max(l["dates"]))) if len(set(l["dates"])) > 1 else ""}</td></tr>' for l, o in sorted(voted, key=lambda t: -t[0]['records']))
        vsecs += f'<section class="tx-sec"><div class="sec-hd"><h2 id="contract-votes" data-tile="Contract votes">Votes on companies\' contracts</h2><span class="muted">Contract approvals matched to the minutes</span></div><div class="tablewrap"><table class="tx-table vd-table"><thead><tr><th scope="col">Company</th><th scope="col">Votes</th><th scope="col" class="num">Approvals</th><th scope="col">When</th></tr></thead><tbody>{vr}</tbody></table></div></section>'
    # recent votes
    if mv:
        rv = ''.join(vote_card(r) for r in mv[:12])
        vsecs += f'<section class="tx-sec"><div class="sec-hd"><h2 id="votes" data-tile="Latest votes">Latest recorded votes</h2><span class="muted">{len(mv):,} money votes on file</span></div><ul class="plain ui-votes">{rv}</ul><p class="small"><a href="/public-money/votes">Every recorded vote</a></p></section>'
    if pay:
        pr = ''.join(f'<li>{e(r.get("title"))}{", " + e(r.get("employer") or r.get("government")) if (r.get("employer") or r.get("government")) else ""}: {money(r.get("annual") or r.get("salary"))} ({e(r.get("year") or r.get("fiscal_year") or r.get("as_of") or "")}) <a class="src" href="{e(r.get("source_url"))}" target="_blank" rel="noopener">Source</a></li>' for r in pay)
        secs += f'<section class="tx-sec"><div class="sec-hd"><h2 id="pay">Pay</h2><span class="muted">Elected officials and department leaders only</span></div><ul class="plain">{pr}</ul></section>'
    eyebrow = ' · '.join(gov_link(g) for g in govs)
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow"><a href="/people">People</a>{" · " + eyebrow if eyebrow else ""}</span><h1>{e(x["name"])}</h1>
    {f'<p class="lede">{e(x["subtitle"])}</p>' if x.get("subtitle") else ''}</div>
    <div class="stamp">{f'<dl class="ui-facts">{facts_h}</dl>' if facts_h else ''}<a class="pill" href="/alerts">Get alerts</a><a class="pill" href="/people#co">Officers and pay</a></div></header>
  {f'<div class="kpis">{kp}</div>' if kp else ''}
  {profile_section(eid, 'Connections', 'Companies, groups and governments linked to ' + x['name'] + ' in the records')}
  {vsecs}
  {secs}
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">About this page</h2></div><ul class="plain">
    <li>Names are matched across records on first and last name, with common nicknames. Board seats and businesses are listed only after an editor checks the match against the filing.</li>
    <li>{e(NOTE)}</li>
    <li>Person id <code>{e(pid)}</code> in the <a href="/open-data">downloads</a> (column person_id) and the <a href="/developers">API</a> (entity <code>{e(eid)}</code>).</li></ul></section>
</div>
{ASSETS}'''


def vote_card(r):
    """One recorded vote: the date, the board and item, and how they voted as a colored pill."""
    v = str(r.get('vote') or '')
    tone = 'teal' if v.lower() in ('yes', 'aye', 'yea') else 'salmon' if v.lower() in ('no', 'nay') else 'blue'
    return (f'<li class="ui-vc"><span class="ui-pill t-{tone}">{e(v[:1].upper() + v[1:]) or "?"}</span><span class="ui-vc-t"><span>{e(r.get("headline"))}</span>'
            f'<small>{e(r.get("date"))} · {e(r.get("board"))} · <a class="src" href="{e(r.get("source_url"))}" target="_blank" rel="noopener">Minutes</a></small></span></li>')


def link_name_vendor(name):
    from entity_links import vendor
    return vendor(name)


def _kinds(p):
    """elected / candidate / staff, from where each role came from (a person can be several)."""
    ks = []
    for r in p.get('roles') or []:
        src, role = r.get('source'), (r.get('role') or '').lower()
        if src == 'candidates_2026' or role.startswith('2026 candidate'):
            ks.append('candidate')
        elif src in ('votes', 'officials-pay', 'campaign') and not role.startswith('former'):
            ks.append('elected')
        elif src == 'salaries':
            ks.append('staff')
        elif src == 'campaign_history':
            ks.append('past')
    if 'elected' in ks:
        ks = [k for k in ks if k != 'staff']  # an official's pay row is not a staff job
    if 'past' in ks and ({'elected', 'candidate'} & set(ks)):
        ks = [k for k in ks if k != 'past']  # an official or 2026 candidate who also ran before
    return [k for k in ('elected', 'candidate', 'staff', 'past') if k in ks] or ['elected']


# The People list's order: government, then title, then last name (Jeremy, 2026-10-27).
GOV_ORDER = ['county', 'schools', 'sheriff', 'clerk', 'property_appraiser', 'tax_collector', 'soe', 'county_court',
             'pc', 'pcb', 'lh', 'cw', 'sp', 'parker', 'mb']
TITLE_RANKS = ['Mayor, chair or elected officer', 'Vice chair or mayor pro tem', 'Commissioner or board member', 'Manager or administrator',
               'Assistant manager, clerk or attorney', 'Department leader', '2026 candidate', 'Former official', 'Past candidate']
PAST_RANK = 7  # ranks from here on (former officials, past candidates) are listed as Past; the rest as Current
STATUS = {'current': 'Current', 'past': 'Past'}
_OFFICERS = ('sheriff', 'tax collector', 'property appraiser', 'clerk of circuit court', 'supervisor of elections', 'superintendent')


def title_rank(line):
    """Where one part of a person's line ("Mayor, Lynn Haven", "Former city manager, Panama City") sits in TITLE_RANKS."""
    import re
    t = line.strip().lower()
    if t.startswith('ran for'):
        return 8
    if t.startswith('former') or re.search(r'\(former\b|\bformer,', t):  # 'City Clerk-Treasurer (former, through Aug 10, 2026)'
        return 7
    if t.startswith('2026 candidate') or t.startswith('running'):
        return 6
    if re.search(r'\bvice\b|pro tem', t):
        return 1
    if re.search(r'\bmayor\b|\bchair', t) or t.startswith(_OFFICERS):
        return 0
    if re.search(r'commissioner|council|school board|board member', t):
        return 2
    if re.search(r'assistant|deputy|\bclerk|attorney', t):
        return 4
    if re.search(r'manager|administrator|^executive director(,|$)', t):
        return 3
    return 5


def status_of(rank):
    """'current' (in office, on staff or on the 2026 ballot) or 'past' (former officials and past candidates)."""
    return 'past' if rank >= PAST_RANK else 'current'


def last_name(name):
    """Surname for sorting: "Kenneth L. Ayers, Jr." and "Robert Merritt III" sort under Ayers and Merritt."""
    w = [x for x in name.replace(',', ' ').split() if x.lower().strip('.') not in ('jr', 'sr', 'ii', 'iii', 'iv')]
    return (w[-1] if w else name).lower()


def directory_order(people=None):
    """{person id: (gov id, title rank, position)} for every person: grouped by their main government (the one their
    top title is for), governments in GOV_ORDER then by name, then TITLE_RANKS, then last and first name.
    The site, the apps (people.json) and the people-directory dataset all use this one order."""
    G = EG.build()
    govs = {k[4:]: v['name'] for k, v in G.ents.items() if k.startswith('gov:')}
    by_len = sorted(govs.items(), key=lambda kv: -len(kv[1]))
    keys = []
    for p in people or _people():
        sub = (G.ents.get('person:' + p['id']) or {}).get('subtitle') or ''
        parts = [x for x in sub.split(' · ') if x.strip()] or ['']
        best = min(parts, key=title_rank)
        rank = title_rank(best)
        gids = [g for g in (p.get('gov_ids') or []) if g]
        gov = next((k for k, n in by_len if n in best and k in gids), None) or next((k for k, n in by_len if n in best), None) or (gids[0] if gids else '')
        last = last_name(p['name'])
        gpos = GOV_ORDER.index(gov) if gov in GOV_ORDER else len(GOV_ORDER)
        keys.append(((gpos, govs.get(gov, gov), rank, last, p['name'].lower()), p['id'], gov, rank))
    keys.sort()
    return {pid: (gov, rank, i) for i, (_, pid, gov, rank) in enumerate(keys)}


def people_index():
    from fees_page import who_sections
    from ui import dir_card, directory, ico, avatar, tone_of, photo_of
    G = EG.build()
    cards, kinds, govs = [], Counter(), {}
    total_links = 0
    order = directory_order()
    gname = lambda g: (G.ents.get('gov:' + g) or {}).get('name') or 'Other offices'
    for p in sorted(_people(), key=lambda p: order[p['id']][2]):
        home, rank, pos = order[p['id']]
        x = G.ents['person:' + p['id']]
        n = len(EG.neighbors('person:' + p['id']))
        total_links += n
        ks = _kinds(p)
        kinds.update(ks)
        gids = [g for g in (p.get('gov_ids') or []) if g]
        for g in gids:
            if 'gov:' + g in G.ents:
                govs[g] = G.ents['gov:' + g]['name']
        cards.append(dir_card(f'/people/{p["id"]}', x['name'], x['subtitle'] or '', ' · '.join(gov_link(g) for g in gids),
                              f'{n} link{"s" if n != 1 else ""}', ' '.join(ks), ' '.join(gids), n, also=' '.join(x['aliases']),
                              av=avatar(x['name'], tone_of(x['name']), photo=photo_of(p['id'])), order=pos, group=gname(home),
                              status=status_of(rank), sub_group=STATUS[status_of(rank)]))
    chips = [('', 'Everyone', len(cards)), ('elected', 'Elected', kinds['elected']), ('candidate', '2026 candidates', kinds['candidate']), ('staff', 'Department leaders', kinds['staff']), ('past', 'Past candidates', kinds['past'])]
    k = lambda icon, tone, label, v, sub: f'<div class="kpi ui-k"><span class="kh">{ico(icon, tone)}<span class="eyebrow">{label}</span></span><span class="v">{v}</span><span class="s">{sub}</span></div>'
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Connections · People</span><h1>Officials and candidates</h1>
    <p class="lede">One page for each elected official, department leader and local candidate since 2016 in these records: where they serve, campaign money from businesses and groups, how they voted, and who they connect to. Below: the five countywide officers and what top officials are paid.</p></div>
    <div class="stamp"><a class="pill" href="#co">County officers</a><a class="pill" href="#pay">Officials' pay</a><a class="pill" href="/connections">Connections network</a></div></header>
  <div class="kpis">{k("users", "blue", "Elected officials", kinds["elected"], f"On {len(govs)} boards and offices")}{k("flag", "salmon", "2026 candidates", kinds["candidate"], "On the November 3 ballot")}{k("briefcase", "teal", "Department leaders", kinds["staff"], "Managers, clerks and chiefs")}{k("network", "amber", "Connections", f"{total_links:,}", "Companies, donors, boards and votes")}</div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="all">Everyone</h2><span class="muted">{len(cards)} people</span></div>
    {directory(cards, "People", chips, sorted(govs.items(), key=lambda kv: kv[1]), "Search a name, seat or government", csv="baycounty-people", sorts=(('gov', 'By government'), ('c', 'Most connected'), ('az', 'A to Z')), statuses=(('', 'Current and past'), ('current', 'Current only'), ('past', 'Past only')))}
    <p class="note">Only elected officials, department leaders and candidates have a page here. Nonprofit board members and businesses have a profile reached from the nonprofit, company or <a href="/connections">Connections</a> pages. Individual campaign donors are named only when they run a registered business; others are counted in totals.</p></section>
  {who_sections()}
  <section class="tx-sec" data-records-sent="appointments" hidden></section>
  <section class="tx-sec" data-records-sent="payroll" hidden></section>
</div>
{ASSETS}<script src="/assets/records-sent.js" defer></script>'''


def profile_shell():
    """/profile: filled in by profile.js for /profile/<kind>/<id> (vercel.json rewrite)."""
    return f'''<div class="page tax pf-page"><div id="pfHead"><header class="tx-top"><div class="tx-brand"><span class="eyebrow"><a href="/connections">Connections</a></span><h1>Loading profile…</h1></div></header></div>
  <section class="tx-sec" id="pf"><div class="sec-hd"><h2 id="connections">Connections</h2><span class="muted">From public records, each with its source</span></div>
    <div class="pf-net" id="pfNet" data-nolink><p class="muted small">Loading…</p></div>
    <div id="pfLive" class="pf-live small" hidden>Rows marked "checked by hand" come from name matches an editor confirmed against the public filing.</div>
    <div id="pfList" data-nolink></div>
    <p class="note">{e(NOTE)} Board members are named as their nonprofits' public filings list them. Individual campaign donors are named only when they run a registered business; others are counted in totals. Found an error? <a href="/about#contact">Send a correction</a>.</p></section>
</div>
{ASSETS}'''


def pages():
    out = [('/people', 'Officials and candidates', 'Every Bay County elected official, department leader and local candidate since 2016, with campaign money, votes and connections.', people_index),
           ('/profile', 'Profile', 'A profile of a company, nonprofit, board member, business or committee in Bay County public records, with every documented connection.', profile_shell)]
    for p in _people():
        n = p['name']
        out.append((f'/people/{p["id"]}', f'{n}: votes, campaign money and connections',
                    f'{n} in Bay County public records: where they serve, campaign gifts from businesses and groups, recorded votes, votes on donors\' contracts and connections.',
                    (lambda i: (lambda: person_page(i)))(p['id'])))
    return out


def search_rows():
    from ui import photo_of
    G = EG.build()
    # 'p': the person's photo, shown beside the name in the results
    rows = [{'k': 'Person', 't': G.ents['person:' + p['id']]['name'], 's': G.ents['person:' + p['id']]['subtitle'] or '', 'u': f'/people/{p["id"]}',
             **({'p': photo_of(p['id'])} if photo_of(p['id']) else {})} for p in _people()]
    for r in EG.profile_rows():
        if r['kind'] == 'nonprofit' and r['connections'] > 1:
            rows.append({'k': 'Nonprofit', 't': r['name'], 's': r['subtitle'] or '', 'u': r['page_url']})
    return rows
