"""Vendor profiles: /public-money/vendors/ (index) and /public-money/vendors/<id> (one page per vendor).

A vendor gets a page when it has 2 or more records on the site, or any campaign-gift match. Ids and names come from
data/entities/vendors.json, which uses site/vendors.py company ids, so a profile is the full-page form of the
Contracts page's company card (same id: /public-money/contracts?company=<id>).
Each page: totals by source, every record with its source link, business campaign gifts (businesses only; individual
donors are never named) and the recorded votes that approved its contracts with each member's vote.
Also writes /data/vendor-slugs.json ({"names": {spelling: id}, "ids": {id: name}}) for page scripts.
"""
import html, json, os, re, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
sys.path.insert(0, os.path.join(DATA, 'entities'))
import ids  # noqa: E402
import records  # noqa: E402
from city_filter import city_bar, data_g, by_city, gkey, KEYS  # noqa: E402

e = lambda s: html.escape(str(s if s is not None else ''))
BASE = '/public-money/vendors'
SRC = [('contract', 'Contracts awarded', 'Contract awards approved on agendas since October 2022'),
       ('change_order', 'Change orders', 'Money added to (or taken off) a contract after it was signed'),
       ('emergency', 'Emergency purchases', 'Bought without normal bidding and approved afterward'),
       ('register', 'Check register payments', "Bay County's top-25 and Lynn Haven's top-20 payees, by fiscal year"),
       ('tdc', 'Tourism agency payments', 'Paid by Visit Panama City Beach, Destination Panama City or the Mexico Beach CDC'),
       ('cra', 'CRA spending', 'Redevelopment agency records that name this payee')]
SRC_NAME = {k: n for k, n, _ in SRC}
SHORT = {'contract': 'Contracts', 'change_order': 'Change orders', 'emergency': 'Emergency buys', 'register': 'Check registers', 'tdc': 'Tourism agencies', 'cra': 'CRA'}
NOTE = ("A campaign gift near a vote, or from a company that holds a contract, is a fact in two public records. "
        "It does not show why anyone voted the way they did, or how a contract was awarded.")


def money(n):
    if n is None:
        return '—'
    s, n = ('−' if n < 0 else ''), abs(n)
    return s + (f'${n/1e6:,.2f}M' if n >= 1e6 else f'${n:,.0f}')


def usd(n):
    return '—' if n is None else ('−' if n < 0 else '') + f'${abs(n):,.2f}'


def gname(g):
    x = ids.gov(g or '')
    return x['short'] if x else (g or '')


def _j(*p):
    try:
        return json.load(open(os.path.join(DATA, *p)))
    except FileNotFoundError:
        return None


_CACHE = {}


def build():
    if _CACHE:
        return _CACHE['P']
    V = {v['id']: v for v in (_j('entities', 'vendors.json') or {'vendors': []})['vendors']}
    P = {}
    for r in records.all_records():
        for vid in ids.vendor_ids(r['name']):
            if vid in V:
                P.setdefault(vid, {'v': V[vid], 'recs': [], 'gifts': [], 'votes': []})['recs'].append(r)
    vm = _j('campaign', 'vendor_matches.json') or {'matches': []}
    seen = set()
    for m in vm['matches']:
        k = (m['vendor_id'], m['candidate'], m['gift_source'])
        if m['vendor_id'] in V and k not in seen:
            seen.add(k)
            P.setdefault(m['vendor_id'], {'v': V[m['vendor_id']], 'recs': [], 'gifts': [], 'votes': []})['gifts'].append(m)
    for vid, p in P.items():  # every paying government for this vendor/candidate pair
        govs = defaultdict(set)
        for m in vm['matches']:
            if m['vendor_id'] == vid:
                govs[(m['candidate'], m['gift_source'])].add(m['contract_gov_id'])
        for g in p['gifts']:
            g['_govs'] = sorted(govs[(g['candidate'], g['gift_source'])])
    cv = _j('votes', 'contract_votes.json') or {'links': []}
    votes = (_j('votes', 'votes.json') or {'votes': []})['votes']
    names = {b['id']: re.sub(r'\bCity City\b', 'City', b['name']) for b in (_j('votes', 'votes.json') or {'bodies': []})['bodies']}
    for l in cv['links']:
        for vid in l['vendor_ids']:
            if vid in P:
                v = votes[l['vote_index']]
                P[vid]['votes'].append({'link': l, 'vote': v, 'board': names.get(v['body'], v['body'])})
    keep = {vid: p for vid, p in P.items() if len(p['recs']) >= 2 or p['gifts']}
    for vid, p in keep.items():
        recs = p['recs']
        tot = defaultdict(float); cnt = defaultdict(int)
        for r in recs:
            cnt[r['src']] += 1
            if r['amount'] is not None and not (r['src'] == 'cra' and not r['extra'].get('count')):
                tot[r['src']] += r['amount']
        p['tot'], p['cnt'] = dict(tot), dict(cnt)
        p['awarded'] = tot.get('contract', 0) + tot.get('emergency', 0)
        p['paid'] = tot.get('register', 0) + tot.get('tdc', 0)
        p['sort'] = max(p['awarded'], p['paid']) + tot.get('cra', 0)
        p['govs'] = sorted({r['gov_id'] for r in recs if r['gov_id']}, key=gname)
        p['gk'] = [k for k in KEYS if any(gkey(g) == k for g in p['govs'])]  # city-bar keys (tourism agencies -> county)
    _CACHE['P'] = keep
    _CACHE['V'] = V
    return keep


def slugs():
    """spelling -> vendor id (lowercased), for page scripts and build-time links; only vendors with a page."""
    P = build()
    names = {}
    for vid, p in P.items():
        for a in p['v']['aliases'] + [p['v']['name']]:
            names.setdefault(a.strip().lower(), vid)
    return {'about': 'Vendor profile pages on BayCounty.me. names: every spelling found in the records (lowercased) -> vendor id; a page is at /public-money/vendors/<id>.',
            'names': names, 'ids': {vid: p['v']['name'] for vid, p in P.items()}}


def link(name, text=None):
    """Build-time link for any spelling of a vendor name ('' when it has no profile)."""
    vids = ids.vendor_ids(name)
    text = ids.biz_case(text if text is not None else name)
    P = build()
    vid = next((v for v in vids if v in P), None)
    if not vid:
        return e(text)
    return f'<a href="{BASE}/{vid}">{e(text)}</a>'


def write_slugs(out_dir):
    json.dump(slugs(), open(os.path.join(out_dir, 'data', 'vendor-slugs.json'), 'w'), ensure_ascii=False, separators=(',', ':'))


# ---------- pages ----------
def index_page(out_dir):
    write_slugs(out_dir)
    P = build()
    from ui import dir_card, directory, avatar, tone_of
    cards, kinds = [], Counter()
    for vid, p in sorted(P.items(), key=lambda kv: -kv[1]['sort']):
        line = ' · '.join(x for x in [f'Awarded {money(p["awarded"])}' if p['awarded'] else '', f'Paid {money(p["paid"])}' if p['paid'] else '',
                                      f'CRA {money(p["tot"]["cra"])}' if p['tot'].get('cra') else '', 'Gave to campaigns' if p['gifts'] else ''] if x)
        ks = [k for k, ok in (('contract', p['awarded']), ('paid', p['paid']), ('cra', p['tot'].get('cra')), ('gift', p['gifts'])) if ok]
        kinds.update(ks)
        n = len(p['recs'])
        cards.append(dir_card(f'{BASE}/{vid}', p['v']['name'], line, e(', '.join(gname(g) for g in p['govs'][:2])) + (f' <b class="ui-more">+{len(p["govs"]) - 2} more</b>' if len(p['govs']) > 2 else ''), f'{n} record{"s" if n != 1 else ""}',
                              ' '.join(ks), '', int(p['sort']), av=avatar(p['v']['name'], tone_of(p['v']['name']), 'store'),
                              also=' '.join(p['v']['aliases']), city=data_g(*p['gk'])))
    ng = sum(1 for p in P.values() if p['gifts'])
    gk = [k for k in KEYS if any(k in p['gk'] for p in P.values())]
    per = lambda f: by_city({'': f(list(P.values())), **{k: f([p for p in P.values() if k in p['gk']]) for k in gk}})
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Public Money · Vendors</span><h1>Who the money goes to</h1>
    <p class="lede">One page for each company or group that Bay County, its cities, their redevelopment agencies or the tourism agencies paid or hired, with every record on this site behind it.</p></div></header>
  {city_bar(gk, hide=True, note='Vendors with a record from that government')}
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>Reading a vendor page</h2>
    <ol class="ex-steps"><li><b>Awarded is not paid.</b> A contract award is a promise to pay up to an amount. Payments come from check registers, which only some governments publish.</li>
      <li><b>One company, many spellings.</b> Agendas, registers and campaign reports spell names differently. We combine spellings only when they are clearly the same company.</li>
      <li><b>Gifts are listed only for businesses.</b> {e(NOTE)}</li></ol></div></section>
  <div class="kpis"><div class="kpi"><span class="eyebrow">Vendors with a page</span><span class="v"{per(len)}>{len(P)}</span><span class="s">2 or more records, or a campaign gift</span></div>
    <div class="kpi"><span class="eyebrow">Gave to a campaign</span><span class="v"{per(lambda ps: sum(1 for p in ps if p['gifts']))}>{ng}</span><span class="s">businesses that also hold local money</span></div></div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="all">Every vendor</h2><span class="muted">{len(cards)} companies and groups</span></div>
    <div data-city-empty="No vendors with records from {{city}} yet.">{directory(cards, "Vendors", [('', 'Every vendor', len(cards)), ('contract', 'Contracts', kinds['contract']), ('paid', 'Paid', kinds['paid']), ('cra', 'CRA', kinds['cra']), ('gift', 'Gave to campaigns', kinds['gift'])], (), 'Search a company or any spelling of it', (('c', 'Largest first'), ('name', 'A to Z')), csv='baycounty-vendors', csv_head='vendor,money,governments,records,link')}</div>
    <p class="note">Awarded adds contract awards and emergency purchases. Paid adds the check-register and tourism-agency payment totals shown in each source; those lists cover only part of each year. CRA counts only records that the CRA ledger includes in its totals. Change orders are on each vendor's page.</p></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">'''


def _rec_line(r):
    a = r['amount']
    amt = (('+' if r['src'] == 'change_order' and a is not None and a >= 0 else '') + money(a)) if a is not None else 'amount not stated'
    extra = ''
    if r['src'] == 'cra':
        extra = f' <span class="muted small">{e(r["extra"]["cra"])} · {e(r["extra"].get("status") or "")}' + ('' if r['extra'].get('count') else ' · not in CRA totals') + '</span>'
    if r['src'] == 'register' and r['extra'].get('months_missing'):
        extra = f' <span class="muted small">months missing: {e(", ".join(r["extra"]["months_missing"]))}</span>'
    if r['src'] == 'tdc':
        extra = f' <span class="muted small">by fiscal year: {e(", ".join(f"{k} {money(v)}" for k, v in sorted((r["extra"].get("by_fy") or {}).items())))}</span>'
    src = f' <a class="src" href="{e(r["url"])}" target="_blank" rel="noopener">Source</a>' if r['url'] else ''
    return f'<tr{data_g(r["gov_id"])}><td>{e(r["date"] or "")}</td><td>{e(gname(r["gov_id"]))}</td><td class="wrap">{e(r["what"] or "")}{extra}<br><span class="muted small">As written: {e(r["name"])}</span></td><td class="num">{amt}</td><td>{src}</td></tr>'


def vendor_page(vid):
    p = build()[vid]
    v = p['v']
    kpi = lambda lbl, val, sub: f'<div class="kpi"><span class="eyebrow">{e(lbl)}</span><span class="v">{val}</span><span class="s">{e(sub)}</span></div>'
    gk = p['gk']

    def tot(k, rs):  # the same sum as build(), for one source and a set of records
        xs = [r for r in rs if r['src'] == k]
        if not xs:
            return '—', '0 records'
        am = [r['amount'] for r in xs if r['amount'] is not None and not (k == 'cra' and not r['extra'].get('count'))]
        return (money(sum(am)) if am else '—'), f'{len(xs)} record{"s" if len(xs) != 1 else ""}'
    def kv(k):
        cs = {g: tot(k, [r for r in p['recs'] if gkey(r['gov_id']) == g]) for g in gk} if len(gk) > 1 else {}
        return (f'<span class="v"{by_city({"": money(p["tot"].get(k)) if k in p["tot"] else "—", **{g: c[0] for g, c in cs.items()}})}>{money(p["tot"].get(k)) if k in p["tot"] else "—"}</span>'
                f'<span class="s"{by_city({"": tot(k, p["recs"])[1], **{g: c[1] for g, c in cs.items()}})}>{tot(k, p["recs"])[1]}</span>')
    # a section (or KPI) hides when none of its rows is from the chosen city; one with a countywide row always shows
    secg = lambda xs: data_g(*xs) if len(gk) > 1 and all(xs) else ''
    srcg = lambda k: secg({r['gov_id'] for r in p['recs'] if r['src'] == k})
    kp = ''.join(f'<div class="kpi"{srcg(k)}><span class="eyebrow">{e(n)}</span>{kv(k)}</div>' for k, n, _ in SRC if p['cnt'].get(k))
    secs = ''
    for k, n, sub in SRC:
        rs = sorted([r for r in p['recs'] if r['src'] == k], key=lambda r: str(r['date'] or ''), reverse=True)
        if not rs:
            continue
        secs += f'''<section class="tx-sec"{secg({r["gov_id"] for r in rs})}><div class="sec-hd"><h2 id="{k}">{e(n)}</h2><span class="muted">{e(sub)}</span></div>
    <div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Date</th><th scope="col">Government</th><th scope="col">What</th><th scope="col" class="num">Amount</th><th scope="col">Source</th></tr></thead><tbody>{"".join(_rec_line(r) for r in rs)}</tbody></table></div></section>'''
    gifts = ''
    if p['gifts']:
        gr = ''.join(f'''<tr{data_g(g.get("office_gov_id"))}><th scope="row">{e(g["candidate"])}<small>{e(g["office"])} · {e("current officeholder" if g["gift_source"].startswith("current") else "2026 candidate" if g["gift_source"].startswith("2026") else (g.get("election") or "past campaign"))}</small></th>
      <td class="num">{usd(g["contribution_amount"])}{f'<small>{usd(g["refunded_by_campaign"])} refunded</small>' if g.get("refunded_by_campaign") else ""}</td><td>{e(", ".join(g["contribution_dates"]))}</td>
      <td class="small">{"<span class='badge warn'>Same government</span> " if any(m == g.get("office_gov_id") for m in g["_govs"]) else ""}{e(", ".join(gname(x) for x in g["_govs"]))}</td>
      <td class="small">{e(ids.biz_case(g["contributor"]))}{" (spelled differently in the filing)" if g["match_confidence"] == "likely" else ""} <a class="src" href="{e(g["campaign_report_url"])}" target="_blank" rel="noopener">Report</a></td></tr>''' for g in sorted(p['gifts'], key=lambda g: (-g['contribution_amount'], g['candidate'])))
        gifts = f'''<section class="tx-sec"{secg({g.get("office_gov_id") for g in p["gifts"]})}><div class="sec-hd"><h2 id="gifts" data-tile="Campaign gifts">Campaign gifts from the business</h2><span class="muted">Business contributions only</span></div>
    <div class="tablewrap"><table class="tx-table vd-table"><thead><tr><th scope="col">To</th><th scope="col" class="num">Gave</th><th scope="col">Dates</th><th scope="col">Governments that pay this vendor</th><th scope="col">Filed as</th></tr></thead><tbody>{gr}</tbody></table></div>
    <p class="note">From the Supervisor of Elections reports of current officeholders and 2026 candidates. Gifts from the company's owners or employees as individuals are not linked to it, and individual donors are never named on this site. "Same government" means the official serves on (or the candidate is running for) a government that pays this vendor. {e(NOTE)}</p></section>'''
    votes = ''
    if p['votes']:
        gave = {g['person_id'] for g in p['gifts'] if g.get('person_id')}
        vr = ''
        for x in sorted(p['votes'], key=lambda x: x['vote']['date'], reverse=True):
            v_, l = x['vote'], x['link']
            roll = ' · '.join((f'<b>{e(n)}</b> {e(val)} (got a gift)' if ids.person_id(n) in gave else f'{e(n)} {e(val)}') for n, val in (v_.get('by_member') or {}).items()) or '<span class="muted">roll call not recorded</span>'
            oc = str(v_.get('outcome') or '')
            tone = 'teal' if re.match(r'(?i)pass|approv|adopt|carr', oc) else 'salmon' if re.match(r'(?i)fail|den|reject', oc) else 'blue'
            vr += f'''<li class="ui-vc"{data_g(v_["body"])}><span class="ui-pill t-{tone}">{e(oc[:1].upper() + oc[1:]) or "Vote"}</span><span class="ui-vc-t"><span>{e(v_.get("headline") or v_.get("item"))}{(" · " + money(v_["amount"])) if v_.get("amount") else ""}</span>
        <small>{e(v_["date"])} · {e(x["board"])}{" · " + e(v_["tally"]) if v_.get("tally") else ""} · <a class="src" href="{e(v_.get("source_url"))}" target="_blank" rel="noopener">Minutes</a></small><span class="small">{roll}</span><small>Approves: {e(l["record_what"])} ({money(l["record_amount"])}, {e(l["record_date"])}). Matched by {e(l["match_method"].replace("_", " ").replace("+", ", "))}.</small></span></li>'''
        votes = f'''<section class="tx-sec"{secg({x["vote"]["body"] for x in p["votes"]})}><div class="sec-hd"><h2 id="votes" data-tile="Votes">Votes that approved its contracts</h2><span class="muted">How each member voted, from the minutes</span></div>
    <ul class="plain ui-votes">{vr}</ul>
    <p class="note">Votes are linked to a contract when the same government voted within 45 days and the minutes agree with the agenda record in at least two ways (company name, bid number, project words or amount). Many contracts are approved on a consent agenda with routine items in one vote. {e(NOTE)}</p></section>'''
    aka = [a for a in v['aliases'] if a != v['name'] and not a.isupper()]
    # the facts card at the top right: who pays it and the years on file
    from entity_links import gov as gov_link
    ds = sorted(m.group(0) for r in p['recs'] for m in [re.search(r'(19|20)\d\d', str(r.get('date') or ''))] if m)
    facts = [('Works for', '<ul>' + ''.join(f'<li>{gov_link(g)}</li>' for g in p['govs'][:6]) + (f'<li class="muted">and {len(p["govs"]) - 6} more</li>' if len(p['govs']) > 6 else '') + '</ul>')] if p['govs'] else []
    if ds:
        facts.append(('On file', f'{ds[0]}{"–" + ds[-1] if ds[-1] != ds[0] else ""}<span>{len(p["recs"])} money record{"s" if len(p["recs"]) != 1 else ""}</span>'))
    facts_h = '<dl class="ui-facts">' + ''.join(f'<div><dt>{k}</dt><dd>{x}</dd></div>' for k, x in facts) + '</dl>' if facts else ''
    card = f'<a class="pill" href="/public-money/contracts?company={e(vid)}#company">Company card on Contracts</a>' if any(p['cnt'].get(k) for k in ('contract', 'change_order', 'emergency', 'register')) else ''
    ev = f'<p class="note">Spellings combined because: {e(v["merge_evidence"])}</p>' if v.get('merge_evidence') else ''
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow"><a href="{BASE}/">Vendors</a> · {e(", ".join(gname(g) for g in p["govs"]))}</span><h1>{e(v["name"])}</h1>
    <p class="lede">Every record on this site that names {e(v["name"])}: {len(p["recs"])} money record{"s" if len(p["recs"]) != 1 else ""}{f", {len(p['gifts'])} campaign gift match{'es' if len(p['gifts']) != 1 else ''}" if p['gifts'] else ""}{f" and {len(p['votes'])} recorded vote{'s' if len(p['votes']) != 1 else ''} on its contracts" if p['votes'] else ""}.</p>
    {f'<p class="small muted">Also written as: {e(" · ".join(aka))}</p>' if aka else ""}</div>
    {f'<div class="stamp">{facts_h}{card}</div>' if facts_h or card else ''}</header>
  {city_bar(gk, hide=True) if len(gk) > 1 else ''}
  <div class="kpis">{kp}</div>
  {secs}{gifts}{votes}
  {_connections(vid, v["name"])}
  <section class="tx-sec method"><div class="sec-hd"><h2 id="src">About this page</h2></div><ul class="plain">
    <li>Awards are agenda amounts, not money paid. Register and tourism-agency payments come from the lists each source publishes, which cover only part of each year.</li>
    <li>CRA records that the ledger leaves out of its totals (parts of a larger project, or not CRA money) are listed but not added up.</li>
    <li>Vendor id <code>{e(vid)}</code> in the <a href="/open-data">downloads</a> (column vendor_id).</li></ul>{ev}</section>
</div>
<link rel="stylesheet" href="/assets/tax.css"><link rel="stylesheet" href="/assets/connections.css"><link rel="stylesheet" href="/assets/profile.css"><script src="/assets/profile.js" defer></script>'''


def _connections(vid, name):
    from people_pages import profile_section
    return profile_section('vendor:' + vid, 'Connections', f'Governments, officials, nonprofits and businesses linked to {name} in the records')


def pages():
    """(path, title, description, render) for build_site.PAGES."""
    P = build()
    out = [(BASE, 'Vendors: who the money goes to', 'Every company and group paid or hired by Bay County governments, CRAs and tourism agencies, with contracts, payments, campaign gifts and the votes that approved them.', None)]
    for vid, p in sorted(P.items()):
        n = p['v']['name']
        out.append((f'{BASE}/{vid}', f'{n}: contracts, payments and votes', f'Every public record on BayCounty.me naming {n}: contracts, change orders, payments, CRA records, business campaign gifts and how officials voted on its contracts.',
                    (lambda v: (lambda: vendor_page(v)))(vid)))
    return out


def search_rows():
    return [{'k': 'Vendor', 't': p['v']['name'], 's': f'{len(p["recs"])} records · ' + ', '.join(gname(g) for g in p['govs']) + (' · ' + ', '.join(a for a in p['v']['aliases'] if a != p['v']['name'])[:200]),
             'u': f'{BASE}/{vid}'} for vid, p in build().items()]
