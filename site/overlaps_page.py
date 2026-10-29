"""Overlaps: where records from different sources name the same company, organization or person.

Each overlap is a section on the page where people look for it (HOME: votes, meetings, notices, contracts, chambers,
development, past elections and more); build_site adds for_page(path) below that page's own content. The summary page
(/connections/overlaps) shows the headline numbers and the top few of each, linking to where it lives.

Built from the datasets in site/correlations.py. The parts that use hand-confirmed matches or rows only the database
holds are read live from /api/v1/overlaps by assets/overlaps.js. Every name links to its profile.
"""
import html
import math
from collections import defaultdict

from entity_links import a as link, build

e = lambda s: html.escape(str(s if s is not None else ''))

CSS = r"""
.ov-tbl td,.ov-tbl th{vertical-align:top}
.ov-tbl td.n,.ov-tbl th.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.ov-tbl .sub{display:block;color:var(--muted);font-size:.8rem;margin-top:2px}
.ov-tbl td.n .sub{white-space:normal;min-width:9em;max-width:16em;margin-left:auto}
.ov-tbl td:first-child{min-width:150px}
.ov-tbl details summary{cursor:pointer;color:var(--blue);font-size:.84rem;white-space:nowrap}
.ov-tbl details ul{margin:6px 0 0;padding-left:18px;font-size:.84rem;line-height:1.5}
.ov-tag{display:inline-block;font-size:.72rem;font-weight:600;padding:1px 8px;border-radius:999px;background:var(--sunken);color:var(--muted);margin:2px 4px 0 0;white-space:nowrap}
.ov-tag.hot{background:color-mix(in srgb,var(--blue) 14%,transparent);color:var(--blue)}
.ov-steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:0;padding:0;list-style:none}
.ov-steps li{padding:14px 16px;border-radius:16px;background:var(--surface);box-shadow:var(--ui-shadow);font-size:.9rem;line-height:1.45}
.ov-steps b{display:block;font-size:.95rem;margin-bottom:2px}
.ov-live[aria-busy="true"]{opacity:.6}
.ov-empty{color:var(--muted);font-size:.92rem;margin:8px 0}
.ov-cut tr.ov-more{display:none!important}
.ov-sec[hidden]{display:none!important}
.ov-showall{margin:10px 0 0;cursor:pointer}
.ov-here{padding-top:0}
.ov-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.ov-card{display:flex;flex-direction:column;gap:6px;padding:16px 18px;border-radius:16px;background:var(--surface);box-shadow:var(--ui-shadow)}
.ov-card h3{margin:0;font-size:1rem}
.ov-card .ov-stat{margin:0;font-size:.9rem;font-weight:600;color:var(--ink)}
.ov-card ul{margin:2px 0 0;padding-left:18px;font-size:.86rem;line-height:1.5}
.ov-card p.muted{margin:0;font-size:.84rem}
.ov-card .ov-go{margin-top:auto;padding-top:6px;font-size:.88rem;font-weight:600}
.ov-fig{margin:6px 0 10px}
.ov-fig svg{width:100%;max-width:720px;height:auto;display:block}
.ov-grid{stroke:var(--line);stroke-width:1}
.ov-diag{stroke:var(--muted);stroke-width:1.5;stroke-dasharray:4 4}
.ov-ax{fill:var(--muted);font-size:12px}
.ov-axt{fill:var(--ink);font-size:13px}
circle.ov-won{fill:var(--blue);stroke:var(--surface);stroke-width:2}
circle.ov-lost{fill:var(--surface);stroke:var(--muted);stroke-width:2}
.ov-fig figcaption{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;font-size:.86rem}
.ov-key{display:inline-flex;align-items:center;gap:6px}
.ov-key i{width:10px;height:10px;border-radius:50%;display:inline-block}
.ov-key i.ov-won{background:var(--blue)}
.ov-key i.ov-lost{border:2px solid var(--muted);width:8px;height:8px}
.ov-every summary{cursor:pointer;color:var(--blue);font-weight:600;margin:6px 0}
@media (max-width:760px){.ov-tbl .hide-sm{display:none}}
"""


def _money(n):
    if n is None:
        return '—'
    a = abs(n)
    return f'${a / 1e9:.1f}B' if a >= 1e9 else f'${a / 1e6:.1f}M' if a >= 1e6 else f'${round(a / 1e3):,}K' if a >= 1e4 else f'${round(a):,}'


def _ent(eid, name):
    import ids
    name = ids.biz_case(name or '') if eid and eid.split(':')[0] in ('vendor', 'business', 'nonprofit') else (name or '')
    return link(eid, name) if eid and (eid in build().ents or eid.startswith('gov:')) else e(name)


def _src(url, text='minutes'):
    return f'<a href="{e(url)}" rel="noopener" target="_blank">{e(text)}</a>' if url else ''


def _to(r):
    if not r.get('gave_to'):
        return ''
    names = r['gave_to'].split('; ')
    more = f' and {len(names) - 3} more' if len(names) > 3 else ''
    return f'<span class="sub">to {e(", ".join(names[:3]))}{more}</span>'


HOT = lambda t: f'<span class="sub"><span class="ov-tag hot">{t}</span></span>'


def _donor_votes(dv):
    """One row per member and company: how often they voted on motions naming it, and the gifts."""
    pairs = {}
    for r in dv:
        k = (r['member_id'], r['company_id'])
        p = pairs.setdefault(k, {'r': r, 'votes': {}, 'gifts': {}, 'timing': set()})
        p['votes'][r['vote_id']] = r
        p['gifts'][r['donor_id']] = (r['donor'], r['donor_kind'], r['gift_amount'] or 0, r.get('report_url'))
        if r.get('gift_timing'):
            p['timing'].add(r['gift_timing'])
    rows = []
    for (mid, cid), p in sorted(pairs.items(), key=lambda kv: (-len(kv[1]['votes']), kv[0])):
        r, vs = p['r'], sorted(p['votes'].values(), key=lambda x: x['date'], reverse=True)
        tally = defaultdict(int)
        for v in vs:
            tally[v['member_vote']] += 1
        gift = sum(g[2] for g in p['gifts'].values())
        who = '; '.join(('the company' if g[1] == 'company' else f'owner {e(g[0])}') for g in p['gifts'].values())
        timing = 'before' if p['timing'] == {'before the vote'} else 'after' if p['timing'] == {'after the vote'} else 'both' if p['timing'] else ''
        items = ''.join(f'<li>{e(v["date"])}: {e(v["headline"] or "")} <span class="ov-tag">{e(v["member_vote"])}</span>'
                        f'{"<span class=ov-tag>consent agenda</span>" if v.get("consent_agenda") else ""} {_src(v.get("source_url"))}</li>' for v in vs[:40])
        more = f'<li>…and {len(vs) - 40} more in the dataset</li>' if len(vs) > 40 else ''
        import ids
        gov = (ids.gov(r['gov_id']) or {}).get('short', r['gov_id'] or '')
        rows.append(f'<tr><td>{_ent(mid, r["member"])}<span class="sub">{e(r["board"] or "")}</span></td><td class="hide-sm">{e(gov)}</td>'
                    f'<td>{_ent(cid, r["company"])}<span class="sub">Gave: {who}</span></td>'
                    f'<td class="n">{_money(gift)}<span class="sub">{e({"before": "before the votes", "after": "after the votes", "both": "before and after"}.get(timing, ""))}</span></td>'
                    f'<td class="n">{len(vs)}<span class="sub">{e(", ".join(f"{n} {k}" for k, n in sorted(tally.items(), key=lambda kv: -kv[1])))}</span></td>'
                    f'<td><details><summary>{e(vs[-1]["date"][:4])}–{e(vs[0]["date"][:4])}</summary><ul>{items}{more}</ul></details></td></tr>')
    return rows, len(pairs)


CUT = 12  # rows shown before "Show all"

_D = {}


def _data():
    """The overlap datasets, built once per site build."""
    if not _D:
        from correlations import (donor_votes, vote_mentions, agenda_parties, development_companies, bid_trail, shared_owner_vendors,
                                  chamber_overlaps, emergency_purchase_donors, campaign_results)
        _D.update(DV=donor_votes(), VM=vote_mentions(), AP=agenda_parties(), DC=development_companies(), BT=bid_trail(), SO=shared_owner_vendors(),
                  CH=chamber_overlaps(), EP=emergency_purchase_donors(), CR=campaign_results())
    return _D


def _table(head, rows, sort='', empty='Nothing on file yet.'):
    if not rows:
        return f'<p class="ov-empty">{e(empty)}</p>'
    cut = len(rows) > CUT + 3
    body = ''.join(r if i < CUT or not cut else r.replace('<tr>', '<tr class="ov-more">', 1) for i, r in enumerate(rows))
    more = f'<button type="button" class="pill ov-showall" data-ov-more>Show all {len(rows)}</button>' if cut else ''
    return (f'<div class="tablewrap"><table class="tx-table ov-tbl{" ov-cut" if cut else ""}"{f' data-tt-sort="{sort}"' if sort else ""} data-tt-year="off"><thead><tr>'
            + ''.join(f'<th{f' class="{c}"' if c else ""}>{e(h)}</th>' for h, c in head) + f'</tr></thead><tbody>{body}</tbody></table></div>{more}')


def _sec(id_, title, sub, body, note=''):
    return (f'<section class="tx-sec ov-sec"><div class="sec-hd"><h2 id="ov-{id_}" data-tile="{e(title)}">{e(title)}</h2><span class="muted">{e(sub)}</span></div>'
            f'{body}{f'<p class="note">{note}</p>' if note else ""}</section>')


def _live(id_):
    return f'<div class="ov-live" id="{id_}" aria-busy="true" aria-live="polite"><p class="ov-empty">Loading…</p></div>'


NOT_A_FINDING = ' An overlap is two public records naming the same company or person; it is not a finding of wrongdoing.'


# ---- one section per overlap, each placed on the page where it belongs (HOME below) ----

def s_donor_votes():
    D = _data()
    rows, n_pairs = _donor_votes(D['DV'])
    n = len({r['vote_id'] for r in D['DV']})
    return _sec('donor-votes', "Votes naming a member's donor", f'{n:,} votes, {n_pairs} official and company pairs since 2016',
                _table([('Official', ''), ('Government', 'hide-sm'), ('Company', ''), ('Gifts', 'n'), ('Votes', 'n'), ('When', '')], rows, '4:desc'),
                "A vote counts when the minutes name the company in the motion the official voted on, and the company (or a person who runs it) gave to "
                "that official's campaign since 2016. Most of these passed unanimously, many on a consent agenda." + NOT_A_FINDING +
                " Data: <a href='/api/v1/datasets/donor-votes'>donor-votes</a>, every vote naming a company or group: <a href='/api/v1/datasets/vote-mentions'>vote-mentions</a>.")


def s_own_biz():
    return _sec('own-business', "Votes on an official's own business", 'Hand-checked matches only, read live', _live('ovOwnBiz'),
                "A business an official runs, named in a motion they voted on, with what their own government paid it.")


def s_own_np():
    return _sec('own-nonprofit', 'Nonprofits with an official on the board', 'Hand-checked matches only, read live', _live('ovOwnNp'),
                "What the official's own government paid the nonprofit, and votes they cast on motions naming it.")


def s_agenda():
    ap = [r for r in _data()['AP'] if r['entity_id'] and r['entity_kind'] != 'gov']
    ap.sort(key=lambda r: (not r['gave_to_members'], r['meeting_date'] and -int(r['meeting_date'].replace('-', ''))))  # gave to the board first, newest first
    n_gave = len({r['entity_id'] for r in ap if r['gave_to_members']})
    rows = [f'<tr><td>{e(r["meeting_date"])}<span class="sub">{e(r["board"] or "")}</span></td><td>{e(r["title"] or "")}'
            f'{HOT("rezoning or land use") if r["rezoning"] else ""}</td>'
            f'<td>{_ent(r["entity_id"], r["entity_name"] or r["party"])}</td>'
            f'<td class="n">{_money(r["gave_to_members"]) if r["gave_to_members"] else "—"}{_to(r)}</td>'
            f'<td class="hide-sm">{_src(r["source_url"], "agenda")}</td></tr>' for r in ap]
    return _sec('agenda', 'Companies and organizations on agendas', f'{len(ap)} linked to a profile; {n_gave} gave to a member of that board',
                _table([('Meeting', ''), ('Item', ''), ('Named', ''), ('Gave to members', 'n'), ('', 'hide-sm')], rows, '3:desc'),
                "Companies that gave to a member of that board are listed first. "
                "Names are read from the agenda packets and matched to a company, nonprofit or registered business. Rezoning and land-use items are tagged. "
                "Data: <a href='/api/v1/datasets/agenda-parties'>agenda-parties</a>.")


def s_bids():
    by = defaultdict(list)
    for r in _data()['BT']:
        by[r['notice_id']].append(r)
    rows = []
    for rs in by.values():
        n = rs[0]
        steps = [r for r in rs if r['stage'] != 'notice']
        after = '; '.join(f'{e(r["stage"])} {e(r["date"])}' + (f' ({e(r["vendor"])})' if r.get('vendor') else '') + (f' {_money(r["amount"])}' if r.get('amount') else '')
                          for r in steps) or '<span class="muted">No vote or award on file yet</span>'
        rows.append(f'<tr><td>{e(n["reference"] or "")}<span class="sub">{e(n["agency"] or "")}</span></td><td>{e(n["notice_title"] or "")}</td>'
                    f'<td>{e(n["published"])}<span class="sub">due {e(n["due_date"] or "—")}</span></td><td>{after}</td></tr>')
    followed = sum(1 for rs in by.values() if any(r['stage'] != 'notice' for r in rs))
    table = _table([('Bid', ''), ('What', ''), ('Posted', ''), ('What followed', '')], rows)
    if not followed:
        table = (f'<p>None of the {len(by)} bids we are following has a vote or contract on file yet. Each one is checked against the minutes and contract '
                 f'records every day.</p><details class="ov-every"><summary>The {len(by)} bids</summary>{table}</details>')
    return _sec('bids', 'Bids from notice to award', f'{followed} of {len(by)} have a vote or award on file',
                table,
                "Each bid notice matched by its bid number to votes and contract records at the same government. The notice site keeps 30 days, so this grows "
                "as notices are archived. Data: <a href='/api/v1/datasets/bid-trail'>bid-trail</a>.")


def s_checkbook():
    return _sec('checkbook', 'Checkbook payees that gave to campaigns', "From each government's own check register, read live", _live('ovCheckbook'),
                'Payees in a government check register that gave to a local campaign, directly or through an owner who runs the company.')


def s_split():
    return _sec('split', 'Payments just under a purchasing threshold', 'From the check registers, read live', _live('ovSplit'),
                'Purchases above a set amount need quotes, bids or a board vote. Two or more payments to one payee within 30 days, each just under $5,000, '
                '$10,000, $25,000, $35,000 or $50,000, are listed. Each government sets its own limits, and there are ordinary reasons for repeat payments.')


def s_shared():
    groups = defaultdict(list)
    for r in _data()['SO']:
        groups[r['group_id']].append(r)
    merged = {}
    for rs in groups.values():  # two officers of the same companies make one row
        k = (rs[0]['gov_id'], tuple(sorted(r['company_id'] for r in rs)))
        m = merged.setdefault(k, {'rs': rs, 'officers': [], 'address': True})
        m['officers'].append(rs[0]['officer'])
        m['address'] &= rs[0]['match'] == 'same name and address'
    import ids
    rows = [f'<tr><td>{e(" and ".join(m["officers"]))}{"<span class=sub>same address on each filing</span>" if m["address"] else ""}</td>'
            f'<td>{link("gov:" + k[0], (ids.gov(k[0]) or {}).get("short", k[0]))}</td>'
            f'<td>{"<br>".join(_ent(r["company_id"], r["company"]) + " " + _money(r["paid_by_this_government"]) for r in m["rs"])}</td></tr>' for k, m in merged.items()]
    return _sec('shared-vendors', 'Companies paid by one government that share an officer', f'{len(merged)} groups',
                _table([('Shared officer', ''), ('Paid by', ''), ('Companies and what that government paid', '')], rows),
                'From state corporate filings: companies that list the same person as an officer or manager, both paid by the same government. Registered '
                "agents are left out, and a person is matched by name. Related companies often share officers. Data: <a href='/api/v1/datasets/shared-owner-vendors'>shared-owner-vendors</a>.")


def chamber_rows(extra=()):
    """Rows for the chambers page's board-business table: every board member who is an official, whose company local
    governments paid or gave to campaigns, or who gave as a business owner; extra = (person html, org html, note) rows."""
    rows = [f'<tr><td>{_ent(r["person_id"], r["person"]) if r["person_id"] else e(r["person"])}<span class="sub">{e(r["title"] or "")}, {e(r["chamber"])}</span></td>'
            f'<td>{_ent(r["organization_id"], r["organization"]) if r["organization_id"] else e(r["organization"] or "")}'
            f'{HOT("elected or appointed official") if r["is_official"] else ""}</td>'
            f'<td class="n">{_money(r["organization_paid_by_governments"]) if r["organization_paid_by_governments"] else "—"}</td>'
            f'<td class="n">{_money((r["organization_gave_to_campaigns"] or 0) + (r["person_gave_to_campaigns"] or 0)) if (r["organization_gave_to_campaigns"] or r["person_gave_to_campaigns"]) else "—"}'
            f'{_to(r)}</td></tr>' for r in sorted(_data()['CH'], key=lambda r: -((r['organization_paid_by_governments'] or 0) + (r['organization_gave_to_campaigns'] or 0) + (r['person_gave_to_campaigns'] or 0)))]
    rows += [f'<tr><td>{p_}</td><td>{o}<span class="sub">{note}</span></td><td class="n">—</td><td class="n">—</td></tr>' for p_, o, note in extra]
    return _table([('Person', ''), ('Organization', ''), ('Paid by local governments', 'n'), ('Gave to campaigns', 'n')], rows, '2:desc', empty='None found.')


def chamber_keys():
    return {(r['person'], r['organization']) for r in _data()['CH']}


def emergency_gift(date, amount):
    """'Gave $X to officials here' tag for one emergency purchase on the contracts page, or ''."""
    if '_EM' not in _D:
        _D['_EM'] = {(r['date'], round(r['amount'] or 0)): r for r in _data()['EP'] if r['gave_to_officials_here']}
    r = _D['_EM'].get((date, round(amount or 0)))
    if not r:
        return ''
    names = (r.get('gave_to') or '').split('; ')
    to = ', '.join(names[:3]) + (f' and {len(names) - 3} more' if len(names) > 3 else '')
    return f' <span class="ov-tag hot">company gave {_money(r["gave_to_officials_here"])}</span> to {e(to)}, officials of this government.'


def development_business(project_id):
    """'Business: <link>' for a development project card, when the project is named after one business filing."""
    if '_DEV' not in _D:
        _D['_DEV'] = {r['project_id']: r for r in _data()['DC']}
    r = _D['_DEV'].get(project_id)
    if not r:
        return ''
    gave = f' · gave {_money(r["gave_to_members"])} to officials' if r.get('gave_to_members') else ''
    return f'<span>Business <b>{_ent(r["company_id"], r["company"])}</b>{gave}</span>'


def _races():
    races = defaultdict(list)
    for r in _data()['CR']:
        races[(r['election_date'], r['office'])].append(r)
    return {k: sorted(rs, key=lambda r: r['vote_rank'] or 99) for k, rs in races.items() if len(rs) > 1}


def _scatter(contested):
    """Share of the race's money (x) against share of the vote (y), one dot per candidate; winners filled."""
    W, H, L, B, T, R = 640, 400, 52, 44, 14, 16
    pw, ph = W - L - R, H - T - B
    X = lambda v: L + v / 100 * pw
    Y = lambda v: T + ph - v / 100 * ph
    grid = ''.join(f'<line x1="{L}" x2="{W - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="ov-grid"/><text x="{L - 8}" y="{Y(v) + 4:.1f}" text-anchor="end" class="ov-ax">{v}%</text>'
                   f'<text x="{X(v):.1f}" y="{H - B + 18}" text-anchor="middle" class="ov-ax">{v}%</text>' for v in (0, 25, 50, 75, 100))
    dots = []
    for (date, office), rs in contested.items():
        total = sum(r['total_raised'] or 0 for r in rs)
        if not total:
            continue
        for r in rs:
            if r['vote_pct'] is None:
                continue
            m = (r['total_raised'] or 0) / total * 100
            won = r['vote_rank'] == 1
            tip = f'{r["candidate"]}, {office} {date[:4]}: {m:.0f}% of the money, {r["vote_pct"]:.0f}% of the vote, {"won" if won else "lost"}'
            dots.append(f'<circle cx="{X(m):.1f}" cy="{Y(r["vote_pct"]):.1f}" r="5" class="{"ov-won" if won else "ov-lost"}"><title>{e(tip)}</title></circle>')
    return (f'<figure class="ov-fig"><svg viewBox="0 0 {W} {H}" role="img" aria-label="Share of campaign money against share of the vote for every candidate in a contested local race">'
            f'{grid}<line x1="{X(0)}" y1="{Y(0)}" x2="{X(100)}" y2="{Y(100)}" class="ov-diag"/>'
            f'<text transform="translate({X(88):.1f} {Y(88):.1f}) rotate({-math.degrees(math.atan2(ph, pw)):.1f})" dy="-7" text-anchor="end" class="ov-ax">money share = vote share</text>{"".join(dots)}'
            f'<text x="{L + pw / 2}" y="{H - 6}" text-anchor="middle" class="ov-ax ov-axt">Share of the money raised in the race</text>'
            f'<text transform="translate(14 {T + ph / 2}) rotate(-90)" text-anchor="middle" class="ov-ax ov-axt">Share of the vote</text></svg>'
            f'<figcaption><span class="ov-key"><i class="ov-won"></i>Won</span><span class="ov-key"><i class="ov-lost"></i>Lost</span>'
            '<span class="muted">Hover or tap a dot for the candidate.</span></figcaption></figure>')


def s_money_votes():
    contested = _races()
    top_won = sum(1 for rs in contested.values() if any(r['money_rank'] == 1 and r['vote_rank'] == 1 for r in rs))
    rows = [f'<tr><td>{e(k[0])}<span class="sub">{e(k[1])}</span></td><td>{"<br>".join(_ent("person:" + r["person_id"] if r.get("person_id") else None, r["candidate"]) + (' <span class="ov-tag hot">won</span>' if r["vote_rank"] == 1 else "") for r in rs)}</td>'
            f'<td class="n">{"<br>".join(_money(r["total_raised"]) for r in rs)}</td>'
            f'<td class="n">{"<br>".join(format(r["votes"], ",") for r in rs)}</td>'
            f'<td class="n hide-sm">{"<br>".join(("$" + format(r["cost_per_vote"], ".2f")) if r["cost_per_vote"] else "—" for r in rs)}</td></tr>'
            for k, rs in sorted(contested.items(), reverse=True)]
    return _sec('money-votes', 'Money raised and votes won', f'The top fundraiser won {top_won} of {len(contested)} contested races',
                _scatter(contested) + '<details class="ov-every"><summary>Every race</summary>'
                + _table([('Election', ''), ('Candidates', ''), ('Raised', 'n'), ('Votes', 'n'), ('Spent per vote', 'n hide-sm')], rows) + '</details>',
                'Local races since 2016 with a campaign report and an official result for at least two candidates. Dots above the line won more of the vote '
                "than their share of the money. Data: <a href='/api/v1/datasets/campaign-results'>campaign-results</a>.")


def s_schools():
    return _sec('school-spending', 'Spending per student next to the grade', 'Same school, same year, read live', _live('ovSchools'),
                "From the Florida Department of Education's school grades and per-pupil spending files.")


# path -> the overlap sections shown at the bottom of that page
HOME = {
    '/public-money/votes': [s_donor_votes],
    '/connections/business-ties': [s_own_biz],
    '/connections/nonprofits': [s_own_np],
    '/meetings': [s_agenda],
    '/notices': [s_bids],
    '/connections/campaign-gifts': [s_checkbook],
    '/public-money/contracts': [s_split],
    '/connections/shared-owners': [s_shared],
    '/chambers': [],  # tags and the board-business table are in chambers_page
    '/elections/past': [s_money_votes],
    '/schools': [s_schools],
}
LIVE = {s_own_biz, s_own_np, s_checkbook, s_split, s_schools}


def for_page(path):
    """The overlap sections for one page, added below its own content by build_site."""
    fns = HOME.get(path)
    if fns is None:
        return ''
    return (f'<style>{CSS}</style><div class="page tax ov ov-here">{"".join(f() for f in fns)}</div>'
            '<link rel="stylesheet" href="/assets/tax.css"><script src="/assets/overlaps.js" defer></script>')


# ---- the summary page ----

def overlaps_page(out_dir):
    import os
    HERE = os.path.dirname(os.path.abspath(__file__))
    open(os.path.join(out_dir, 'assets', 'overlaps.js'), 'w').write(open(os.path.join(HERE, 'overlaps.js')).read())
    D = _data()
    DV, VM, AP, DC, BT, SO, CH, EP = (D[k] for k in ('DV', 'VM', 'AP', 'DC', 'BT', 'SO', 'CH', 'EP'))
    contested = _races()
    top_won = sum(1 for rs in contested.values() if any(r['money_rank'] == 1 and r['vote_rank'] == 1 for r in rs))
    _, n_pairs = _donor_votes(DV)
    n_dv = len({r['vote_id'] for r in DV})
    n_vm, n_vm_ents = len({r['vote_id'] for r in VM}), len({r['entity_id'] for r in VM})
    ap = [r for r in AP if r['entity_id'] and r['entity_kind'] != 'gov']
    n_ep_gave = sum(1 for r in EP if r['gave_to_officials_here'])

    # top three for each card
    pairs = defaultdict(set)
    for r in DV:
        pairs[(r['member_id'], r['member'], r['company_id'], r['company'])].add(r['vote_id'])
    top_dv = [f'{_ent(m, mn)} on {_ent(c, cn)}: {len(v)} votes' for (m, mn, c, cn), v in sorted(pairs.items(), key=lambda kv: -len(kv[1]))[:3]]
    named = defaultdict(set)
    for r in ap:
        named[(r['entity_id'], r['entity_name'] or r['party'])].add(r['meeting_date'])
    top_ap = [f'{_ent(i, n)}: {len(d)} meetings' for (i, n), d in sorted(named.items(), key=lambda kv: -len(kv[1]))[:3]]
    so = defaultdict(list)
    for r in SO:
        so[r['group_id']].append(r)
    top_so = [f'{e(rs[0]["officer"])}: {len(rs)} companies' for rs in sorted(so.values(), key=lambda rs: -sum(r["paid_by_this_government"] or 0 for r in rs))[:3]]
    top_ch = [f'{_ent(r["person_id"], r["person"]) if r["person_id"] else e(r["person"])}, {e(r["chamber"])}' for r in
              sorted(CH, key=lambda r: -((r['organization_paid_by_governments'] or 0) + (r['organization_gave_to_campaigns'] or 0)))[:3]]
    top_ep = [f'{_ent(r["vendor_id"], r["vendor"]) if r["vendor_id"] else e(r["vendor"])}: {_money(r["amount"])}' for r in
              sorted((r for r in EP if r['gave_to_officials_here']), key=lambda r: -(r['amount'] or 0))[:3]]
    top_dc = [f'{e(r["project"])}: {_ent(r["company_id"], r["company"])}' for r in DC[:3]]
    top_bt = [e(r["notice_title"] or r["reference"] or "") for r in {r['notice_id']: r for r in BT}.values()][:3]

    def card(title, stat, items, path, anchor, page_name, live=False):
        li = ''.join(f'<li>{x}</li>' for x in items)
        return (f'<article class="ov-card"><h3>{e(title)}</h3><p class="ov-stat">{stat}</p>'
                f'{f"<ul>{li}</ul>" if li else ""}{"<p class=muted>Read live. It shows on that page once a match is on file.</p>" if live else ""}'
                f'<a class="ov-go" href="{path}#{anchor if anchor in ("em", "business", "projects") else "ov-" + anchor}">On {e(page_name)} →</a></article>')

    cards = ''.join([
        card("Votes naming a member's donor", f'{n_dv:,} votes · {n_pairs} official and company pairs', top_dv, '/public-money/votes', 'donor-votes', 'How they voted'),
        card('Companies on agendas', f'{len(ap)} agenda items name a company or group', top_ap, '/meetings', 'agenda', 'Public meetings'),
        card('Bids from notice to award', f'{len({r["notice_id"] for r in BT})} bids followed by number', top_bt, '/notices', 'bids', 'Public notices'),
        card('Emergency purchases from donors', f'{n_ep_gave} of {len(EP)} bought from a company that gave', top_ep, '/public-money/contracts', 'em', 'Who gets the contracts'),
        card('Shared officers among vendors', f'{len(so)} groups paid by one government', top_so, '/connections/shared-owners', 'shared-vendors', 'Shared owners'),
        card('Chamber boards', f'{len(CH)} board members who are officials, donors or vendors', top_ch, '/chambers', 'business', 'Chambers of commerce'),
        card('Developers behind projects', f'{len(DC)} projects named after a business', top_dc, '/development', 'projects', 'Building and development'),
        card('Money raised and votes won', f'The top fundraiser won {top_won} of {len(contested)} contested races',
             [f'{len(contested) - top_won} races went to a candidate who raised less', 'Every candidate on one chart: share of money against share of the vote'], '/elections/past', 'money-votes', 'Past elections'),
        card("Votes on an official's own business", 'Hand-checked matches', [], '/connections/business-ties', 'own-business', "Officials' businesses", True),
        card('Nonprofits with an official on the board', 'Payments and votes', [], '/connections/nonprofits', 'own-nonprofit', 'Nonprofits', True),
        card('Checkbook payees that gave to campaigns', 'From each check register', [], '/connections/campaign-gifts', 'checkbook', 'Campaign gifts', True),
        card('Payments just under a threshold', 'From each check register', [], '/public-money/contracts', 'split', 'Who gets the contracts', True),
        card('School spending and grades', 'Same school, same year', [], '/schools', 'school-spending', 'Public schools', True),
    ])

    k = lambda lab, v, s: f'<div class="kpi"><span class="eyebrow">{lab}</span><span class="v">{v}</span><span class="s">{s}</span></div>'
    kpis = (k('Votes naming a donor', f'{n_dv:,}', f'{n_pairs} official and company pairs since 2016') +
            k('Votes naming a company or group', f'{n_vm:,}', f'{n_vm_ents} companies and organizations named') +
            k('Top fundraiser won', f'{top_won} of {len(contested)}', 'contested local races with a report and a result') +
            k('Emergency buys from donors', f'{n_ep_gave} of {len(EP)}', 'bought without bidding from a company that gave'))

    return f'''<style>{CSS}</style>
<div class="page tax ov">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Who decides · Connections</span><h1>Where the records overlap</h1>
    <p class="lede">The same company, organization or person often shows up in more than one public record: a campaign report, the minutes, an agenda, a check register, a state business filing. Each overlap lives on the page where you'd look for it; this is the summary.</p></div>
    <div class="stamp"><span>Rebuilt every day from the records on BayCounty.me</span></div></header>
  <div class="kpis">{kpis}</div>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>What an overlap is, and isn't</h2>
    <ol class="ex-steps"><li><b>Two records, one name.</b> A company that gave to a commissioner's campaign is named in a motion that commissioner voted on. Both facts are public; these pages line them up.</li>
    <li><b>It is not a finding.</b> Most of these votes passed unanimously, many on a consent agenda with dozens of routine items. A gift near a vote does not show why anyone voted the way they did.</li>
    <li><b>People are named only where the law makes them public.</b> Officials, candidates and people who run a registered business are named. Individual donors never are.</li></ol></div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="all">Every overlap</h2><span class="muted">The top few of each, and where to see the rest</span></div>
    <div class="ov-cards">{cards}</div></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">How this works</h2></div>
    <ul class="plain">
      <li><b>Names in votes and agendas</b> are matched to profiles by name: a company's usual spellings, and nonprofits and registered businesses with at least two distinctive words. Names that are also a place (a street, park or dock) or a public body are skipped. A match means the record names the organization.</li>
      <li><b>Gifts</b> come from campaign reports filed with the Supervisor of Elections since 2016: gifts from businesses and committees, and personal gifts from people whose name and address match an officer, manager or registered agent of a registered business.</li>
      <li><b>Live parts</b> (officials' own businesses and nonprofits, checkbook, schools) are read from the database each time a page opens: <a href="/api/v1/overlaps">/api/v1/overlaps</a>. Every overlap is also a dataset in the <a href="/open-data">open data</a>.</li>
      <li><b>Something wrong?</b> <a href="/about#contact">Tell us</a> and we'll fix the match.</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">'''
