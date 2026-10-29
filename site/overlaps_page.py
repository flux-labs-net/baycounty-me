"""Overlaps (/connections/overlaps): where records from different sources name the same company, organization or person.

Built from the datasets in site/correlations.py (donor-votes, vote-mentions, agenda-parties, development-companies,
bid-trail, shared-owner-vendors, chamber-overlaps, emergency-purchase-donors, campaign-results). The parts that use
hand-confirmed matches or rows only the database holds (officials' own businesses and nonprofits in their votes,
checkbook payees that gave to campaigns, payments just under a purchasing threshold, school spending and grades) are
read live from /api/v1/overlaps by assets/overlaps.js. Every name links to its profile.
"""
import html
from collections import defaultdict

from entity_links import a as link, build

e = lambda s: html.escape(str(s if s is not None else ''))

CSS = r"""
.ov-tbl td,.ov-tbl th{vertical-align:top}
.ov-tbl td.n,.ov-tbl th.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.ov-tbl .sub{display:block;color:var(--muted);font-size:.8rem;margin-top:2px}
.ov-tbl details summary{cursor:pointer;color:var(--blue);font-size:.84rem}
.ov-tbl details ul{margin:6px 0 0;padding-left:18px;font-size:.84rem;line-height:1.5}
.ov-tag{display:inline-block;font-size:.72rem;font-weight:600;padding:1px 8px;border-radius:999px;background:var(--sunken);color:var(--muted);margin:2px 4px 0 0;white-space:nowrap}
.ov-tag.hot{background:color-mix(in srgb,var(--blue) 14%,transparent);color:var(--blue)}
.ov-steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:0;padding:0;list-style:none}
.ov-steps li{padding:14px 16px;border-radius:16px;background:var(--surface);box-shadow:var(--ui-shadow);font-size:.9rem;line-height:1.45}
.ov-steps b{display:block;font-size:.95rem;margin-bottom:2px}
.ov-live[aria-busy="true"]{opacity:.6}
.ov-empty{color:var(--muted);font-size:.92rem;margin:8px 0}
@media (max-width:760px){.ov-tbl .hide-sm{display:none}}
"""


def _money(n):
    if n is None:
        return '—'
    a = abs(n)
    return f'${a / 1e6:.1f}M' if a >= 1e6 else f'${round(a / 1e3):,}K' if a >= 1e4 else f'${round(a):,}'


def _ent(eid, name):
    import ids
    name = ids.biz_case(name or '') if eid and eid.split(':')[0] in ('vendor', 'business', 'nonprofit') else (name or '')
    return link(eid, name) if eid and (eid in build().ents or eid.startswith('gov:')) else e(name)


def _src(url, text='minutes'):
    return f'<a href="{e(url)}" rel="noopener" target="_blank">{e(text)}</a>' if url else ''


def _to(r):
    return f'<span class="sub">to {e(r["gave_to"])}</span>' if r.get('gave_to') else ''


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
        rows.append(f'<tr><td>{_ent(mid, r["member"])}<span class="sub">{e(r["board"] or "")}</span></td>'
                    f'<td>{_ent(cid, r["company"])}<span class="sub">Gave: {who}</span></td>'
                    f'<td class="n">{_money(gift)}<span class="sub">{e({"before": "before the votes", "after": "after the votes", "both": "before and after"}.get(timing, ""))}</span></td>'
                    f'<td class="n">{len(vs)}<span class="sub">{e(", ".join(f"{n} {k}" for k, n in sorted(tally.items(), key=lambda kv: -kv[1])))}</span></td>'
                    f'<td><details><summary>{e(vs[-1]["date"][:4])}–{e(vs[0]["date"][:4])}</summary><ul>{items}{more}</ul></details></td></tr>')
    return rows, len(pairs)


def overlaps_page(out_dir):
    import os
    from correlations import (donor_votes, vote_mentions, agenda_parties, development_companies, bid_trail, shared_owner_vendors,
                              chamber_overlaps, emergency_purchase_donors, campaign_results)
    HERE = os.path.dirname(os.path.abspath(__file__))
    open(os.path.join(out_dir, 'assets', 'overlaps.js'), 'w').write(open(os.path.join(HERE, 'overlaps.js')).read())
    DV, VM, AP, DC, BT, SO, CH, EP, CR = (donor_votes(), vote_mentions(), agenda_parties(), development_companies(), bid_trail(), shared_owner_vendors(),
                                          chamber_overlaps(), emergency_purchase_donors(), campaign_results())

    dv_rows, n_pairs = _donor_votes(DV)
    n_dv_votes = len({r['vote_id'] for r in DV})
    n_vm_votes, n_vm_ents = len({r['vote_id'] for r in VM}), len({r['entity_id'] for r in VM})

    # agendas: linked parties, newest first; rezoning items and parties that gave to the board first in the tags
    ap = [r for r in AP if r['entity_id'] and r['entity_kind'] != 'gov']
    ap_rows = ''.join(
        f'<tr><td>{e(r["meeting_date"])}<span class="sub">{e(r["board"] or "")}</span></td><td>{e(r["title"] or "")}'
        f'{HOT("rezoning or land use") if r["rezoning"] else ""}</td>'
        f'<td>{_ent(r["entity_id"], r["entity_name"] or r["party"])}</td>'
        f'<td class="n">{_money(r["gave_to_members"]) if r["gave_to_members"] else "—"}{_to(r)}</td>'
        f'<td class="hide-sm">{_src(r["source_url"], "agenda")}</td></tr>' for r in ap[:150])
    n_ap_gave = len({r['entity_id'] for r in ap if r['gave_to_members']})

    # bids: one row per notice, with what followed
    by_notice = defaultdict(list)
    for r in BT:
        by_notice[r['notice_id']].append(r)
    bt_rows = []
    for nid, rs in by_notice.items():
        n = rs[0]
        steps = [r for r in rs if r['stage'] != 'notice']
        after = '; '.join(f'{e(r["stage"])} {e(r["date"])}' + (f' ({e(r["vendor"])})' if r.get('vendor') else '') + (f' {_money(r["amount"])}' if r.get('amount') else '') for r in steps) or 'No vote or award on file yet'
        bt_rows.append(f'<tr><td>{e(n["reference"] or "")}<span class="sub">{e(n["agency"] or "")}</span></td><td>{e(n["notice_title"] or "")}</td>'
                       f'<td>{e(n["published"])}<span class="sub">due {e(n["due_date"] or "—")}</span></td><td>{after}</td></tr>')

    so = defaultdict(list)
    for r in SO:
        so[r['group_id']].append(r)
    so_rows = ''.join(
        f'<tr><td>{e(rs[0]["officer"])}<span class="sub">{e(rs[0]["match"])}</span></td><td>{link("gov:" + rs[0]["gov_id"], (__import__("ids").gov(rs[0]["gov_id"]) or {}).get("short", rs[0]["gov_id"]))}</td>'
        f'<td>{"<br>".join(_ent(r["company_id"], r["company"]) + " " + _money(r["paid_by_this_government"]) for r in rs)}</td></tr>' for g, rs in so.items())

    dc_rows = ''.join(
        f'<tr><td>{e(r["project"])}<span class="sub">{e(r["description"] or "")}</span></td><td>{_ent(r["company_id"], r["company"])}</td>'
        f'<td>{e(r["status"] or "")}<span class="sub">{e(r["approved_date"] or r["applied_date"] or "")}</span></td>'
        f'<td class="n">{_money(r["gave_to_members"]) if r["gave_to_members"] else "—"}</td><td class="n">{_money(r["paid_by_this_government"]) if r["paid_by_this_government"] else "—"}</td></tr>' for r in DC)

    ch_rows = ''.join(
        f'<tr><td>{_ent(r["person_id"], r["person"]) if r["person_id"] else e(r["person"])}<span class="sub">{e(r["title"] or "")}, {e(r["chamber"])}</span></td>'
        f'<td>{_ent(r["organization_id"], r["organization"]) if r["organization_id"] else e(r["organization"] or "")}'
        f'{HOT("elected or appointed official") if r["is_official"] else ""}</td>'
        f'<td class="n">{_money(r["organization_paid_by_governments"]) if r["organization_paid_by_governments"] else "—"}</td>'
        f'<td class="n">{_money((r["organization_gave_to_campaigns"] or 0) + (r["person_gave_to_campaigns"] or 0)) if (r["organization_gave_to_campaigns"] or r["person_gave_to_campaigns"]) else "—"}'
        f'{_to(r)}</td></tr>' for r in CH)

    ep_rows = ''.join(
        f'<tr><td>{e(r["date"] or "")}<span class="sub">{e(r["government"] or "")}</span></td><td>{_ent(r["vendor_id"], r["vendor"]) if r["vendor_id"] else e(r["vendor"])}'
        f'<span class="sub">{e((r["purpose"] or "")[:140])}</span></td><td class="n">{_money(r["amount"])}</td>'
        f'<td class="n">{_money(r["gave_to_officials_here"]) if r["gave_to_officials_here"] else "—"}{_to(r)}</td>'
        f'<td class="hide-sm">{_src(r["source_url"], "record")}</td></tr>' for r in EP)
    n_ep_gave = sum(1 for r in EP if r['gave_to_officials_here'])

    # money and votes: did the top fundraiser win?
    races = defaultdict(list)
    for r in CR:
        races[(r['election_date'], r['office'])].append(r)
    contested = {k: rs for k, rs in races.items() if len(rs) > 1}
    top_won = sum(1 for rs in contested.values() if any(r['money_rank'] == 1 and r['vote_rank'] == 1 for r in rs))
    cr_rows = ''.join(
        f'<tr><td>{e(k[0])}<span class="sub">{e(k[1])}</span></td><td>{"<br>".join(_ent("person:" + r["person_id"] if r.get("person_id") else None, r["candidate"]) + (' <span class="ov-tag hot">won</span>' if r["vote_rank"] == 1 else "") for r in sorted(rs, key=lambda r: r["vote_rank"] or 99))}</td>'
        f'<td class="n">{"<br>".join(_money(r["total_raised"]) for r in sorted(rs, key=lambda r: r["vote_rank"] or 99))}</td>'
        f'<td class="n">{"<br>".join(format(r["votes"], ",") for r in sorted(rs, key=lambda r: r["vote_rank"] or 99))}</td>'
        f'<td class="n hide-sm">{"<br>".join(("$" + format(r["cost_per_vote"], ".2f")) if r["cost_per_vote"] else "—" for r in sorted(rs, key=lambda r: r["vote_rank"] or 99))}</td></tr>'
        for k, rs in sorted(contested.items(), reverse=True))

    k = lambda lab, v, s: f'<div class="kpi"><span class="eyebrow">{lab}</span><span class="v">{v}</span><span class="s">{s}</span></div>'
    kpis = (k('Votes naming a donor', f'{n_dv_votes:,}', f'{n_pairs} official and company pairs since 2016') +
            k('Votes naming a company or group', f'{n_vm_votes:,}', f'{n_vm_ents} companies and organizations named') +
            k('Top fundraiser won', f'{top_won} of {len(contested)}', 'contested local races with a report and a result') +
            k('Emergency buys from donors', f'{n_ep_gave} of {len(EP)}', 'bought without bidding from a company that gave here'))

    def sec(id_, tile, title, sub, body, note=''):
        return (f'<section class="tx-sec"><div class="sec-hd"><h2 id="{id_}" data-tile="{e(tile)}">{e(title)}</h2><span class="muted">{e(sub)}</span></div>'
                f'{body}{f'<p class="note">{note}</p>' if note else ""}</section>')

    def table(head, rows, sort='', empty='Nothing on file yet.'):
        if not rows:
            return f'<p class="ov-empty">{e(empty)}</p>'
        return (f'<div class="tablewrap"><table class="tx-table ov-tbl"{f' data-tt-sort="{sort}"' if sort else ""} data-tt-year="off"><thead><tr>'
                + ''.join(f'<th{f' class="{c}"' if c else ""}>{e(h)}</th>' for h, c in head) + f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')

    live = lambda id_: f'<div class="ov-live" id="{id_}" aria-busy="true" aria-live="polite"><p class="ov-empty">Loading…</p></div>'

    return f'''<style>{CSS}</style>
<div class="page tax ov">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Who decides · Connections</span><h1>Where the records overlap</h1>
    <p class="lede">The same company, organization or person often shows up in more than one public record: a campaign report, the minutes, an agenda, a check register, a state business filing. This page puts those records side by side so you can see where they meet.</p></div>
    <div class="stamp"><a class="pill" href="#donor-votes">Votes naming a donor →</a><span>Rebuilt every day from the records on BayCounty.me</span></div></header>
  <div class="kpis">{kpis}</div>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>What an overlap is, and isn't</h2>
    <ol class="ex-steps"><li><b>Two records, one name.</b> A company that gave to a commissioner's campaign is named in a motion that commissioner voted on. Both facts are public; this page lines them up.</li>
    <li><b>It is not a finding.</b> Most of these votes passed unanimously, many on a consent agenda with dozens of routine items. A gift near a vote does not show why anyone voted the way they did.</li>
    <li><b>People are named only where the law makes them public.</b> Officials, candidates and people who run a registered business are named. Individual donors never are.</li></ol></div></section>

  {sec("donor-votes", "Donors and votes", "Votes on motions naming a member's donor", "One row per official and company, most votes first",
       table([("Official", ""), ("Company", ""), ("Gifts", "n"), ("Votes", "n"), ("When", "")], dv_rows, "3:desc"),
       "A vote counts when the minutes name the company in the motion the official voted on, and the company (or a person who runs it) gave to that official's campaign at any time since 2016. Open a row for every vote and its minutes. Data: <a href='/api/v1/datasets/donor-votes'>donor-votes</a>, every vote naming a company or group: <a href='/api/v1/datasets/vote-mentions'>vote-mentions</a>.")}

  {sec("own", "Own businesses", "Officials' own businesses and nonprofits", "Hand-checked matches only, read live",
       live("ovOwn"),
       "An official's business or a nonprofit whose board they sit on, named in a motion they voted on, with what their own government paid it. Only matches checked by hand against state filings are listed (<a href='/connections/business-ties'>Business ties</a>, <a href='/connections/nonprofits'>Nonprofits</a>).")}

  {sec("agenda", "On agendas", "Companies and organizations on agendas", f"{len(ap)} linked to a profile; {n_ap_gave} gave to a member of that board",
       table([("Meeting", ""), ("Item", ""), ("Named", ""), ("Gave to members", "n"), ("", "hide-sm")], [ap_rows] if ap_rows else [], ""),
       "Names are read from the published agenda packets and matched to a company, nonprofit or registered business. Rezoning and land-use items are tagged. Data: <a href='/api/v1/datasets/agenda-parties'>agenda-parties</a>.")}

  {sec("bids", "Bids", "Bids from notice to award", "Followed by bid number to votes and contract records",
       table([("Bid", ""), ("What", ""), ("Posted", ""), ("What followed", "")], bt_rows),
       "Bid and proposal requests from the county's public notice website, matched by bid number to votes and contract records at the same government. The notice site keeps 30 days, so this list grows as notices are archived. Data: <a href='/api/v1/datasets/bid-trail'>bid-trail</a>.")}

  {sec("checkbook", "Checkbook", "Checkbook payees that gave to campaigns", "From each government's own check register, read live",
       live("ovCheckbook") + '<h3 style="margin:22px 0 6px">Payments just under a purchasing threshold</h3>' + live("ovSplit"),
       "Purchases above a set amount need quotes, bids or a board vote. Two or more payments to one payee within 30 days, each just under one of these amounts ($5,000, $10,000, $25,000, $35,000 or $50,000), are listed. Each government sets its own limits, and there are ordinary reasons for repeat payments.")}

  {sec("shared", "Shared officers", "Companies paid by one government that share an officer", f"{len(so)} groups",
       table([("Shared officer", ""), ("Paid by", ""), ("Companies and what that government paid", "")], [so_rows] if so_rows else []),
       "From state corporate filings (Sunbiz): companies that list the same person as an officer or manager, both paid by the same government. Registered agents are left out. Related companies often share officers. Data: <a href='/api/v1/datasets/shared-owner-vendors'>shared-owner-vendors</a>.")}

  {sec("development", "Development", "Development projects and the businesses behind them", "Projects named after a registered business",
       table([("Project", ""), ("Business", ""), ("Status", ""), ("Gave to officials", "n"), ("Paid by that government", "n")], [dc_rows] if dc_rows else []),
       "The planning maps don't list owners or developers, so a project is matched only when its name is exactly the name of one active Bay County business filing. Data: <a href='/api/v1/datasets/development-companies'>development-companies</a>.")}

  {sec("chambers", "Chamber boards", "Chamber board members who are officials, donors or vendors", "From each chamber's own board list",
       table([("Person", ""), ("Organization", ""), ("Paid by local governments", "n"), ("Gave to campaigns", "n")], [ch_rows] if ch_rows else []),
       "A board member's own gifts count only when they run the company the chamber lists them with. Data: <a href='/api/v1/datasets/chamber-overlaps'>chamber-overlaps</a>.")}

  {sec("emergency", "Emergency buys", "Emergency purchases and campaign gifts", "Bought without the usual bidding",
       table([("Date", ""), ("Company and purpose", ""), ("Amount", "n"), ("Gave to officials here", "n"), ("", "hide-sm")], [ep_rows] if ep_rows else []),
       "Data: <a href='/api/v1/datasets/emergency-purchase-donors'>emergency-purchase-donors</a>.")}

  {sec("money-votes", "Money and votes", "Money raised and votes won", f"The top fundraiser won {top_won} of {len(contested)} contested races",
       table([("Election", ""), ("Candidates", ""), ("Raised", "n"), ("Votes", "n"), ("Spent per vote", "n hide-sm")], [cr_rows] if cr_rows else []),
       "Local races since 2016 with a campaign report and an official result for at least two candidates. Money from individuals is summed, never named. Data: <a href='/api/v1/datasets/campaign-results'>campaign-results</a>.")}

  {sec("schools", "Schools", "School spending and school grades", "Per-student spending next to the grade, same year",
       live("ovSchools"), "From the Florida Department of Education's school grades and per-pupil spending files.")}

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">How this works</h2></div>
    <ul class="plain">
      <li><b>Names in votes and agendas</b> are matched to profiles by name: a company's usual spellings, and nonprofits and registered businesses with at least two distinctive words. Names that are also a place (a street, park or dock) or a public body are skipped. A match means the record names the organization.</li>
      <li><b>Gifts</b> come from campaign reports filed with the Supervisor of Elections since 2016: gifts from businesses and committees, and personal gifts from people whose name and address match an officer, manager or registered agent of a registered business.</li>
      <li><b>Live parts</b> (officials' own businesses and nonprofits, checkbook, schools) are read from the database each time the page opens, because their rows arrive when a match is checked by hand or a government publishes a file: <a href="/api/v1/overlaps">/api/v1/overlaps</a>.</li>
      <li><b>Something wrong?</b> <a href="/about#contact">Tell us</a> and we'll fix the match.</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/overlaps.js" defer></script>'''
