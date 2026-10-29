"""Chambers of commerce (/chambers): the Bay County Chamber and the Panama City Beach Chamber, who leads them, what's
coming up, the public money they get and where their boards meet local government business.

Built from the chambers, chamber-leaders and chamber-events datasets (site/page_datasets.py _chamber_rows(), from
data/chambers/<county>/), plus nonprofit-payments for the public money. Every name links to its profile through
entity_links; organizations link only when entity matching found them (organization_entity_id).
"""
import datetime as dt
import html
import os

from entity_links import a as link, build
from ui import avatar, tone_of, ico

e = lambda s: html.escape(str(s if s is not None else ''))
HERE = os.path.dirname(os.path.abspath(__file__))
TONE = {'bay-chamber': 'blue', 'pcb-chamber': 'teal'}

CSS = r"""
.ch-two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.ch-card{display:flex;flex-direction:column;gap:14px;padding:22px;border-radius:24px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.ch-card-hd{display:flex;gap:14px;align-items:center}
.ch-card-hd .ui-av{margin:0;flex:none}
.ch-card h3{font-size:1.15rem;font-weight:600;margin:0;text-wrap:balance}
.ch-card h3 a{color:inherit;text-decoration:none}
.ch-card h3 a:hover{color:var(--blue)}
.ch-tag{font-size:.86rem;color:var(--muted);margin:2px 0 0}
.ch-card p{margin:0;font-size:.92rem;line-height:1.5}
.ch-facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0}
.ch details .ch-ppl{margin-top:12px}
.ch-facts div{padding:10px 12px;border-radius:14px;background:var(--sunken);min-width:0}
.ch-facts dt{font-size:.76rem;color:var(--muted)}
.ch-facts dd{margin:2px 0 0;font:600 1.05rem var(--f-body);font-variant-numeric:tabular-nums}
.ch-acts{display:flex;flex-wrap:wrap;gap:8px}
.ch-acts .ui-btn{min-height:40px;font-size:.86rem}
.ch-meets{font-size:.84rem;color:var(--muted)}
.ch-ctl{display:flex;flex-wrap:wrap;gap:8px 16px}
.ch-ev{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px}
.ch-ev .ui-mc{align-items:flex-start}
.ch-ev .ui-mc b a{color:inherit;text-decoration:none}
.ch-ev .ui-mc b a:hover{color:var(--blue);text-decoration:underline}
.ch-ev [hidden]{display:none!important}
.ch .ch-morebtn{width:auto;border:0;cursor:pointer;font-family:inherit}
.ch .ch-morebtn[hidden]{display:none}
.ch-pill{display:inline-block;margin-top:6px;font-size:.72rem;font-weight:600;padding:2px 9px;border-radius:999px}
.ch-pill.t-blue{background:color-mix(in srgb,var(--blue) 14%,transparent);color:var(--blue)}
.ch-pill.t-teal{background:color-mix(in srgb,var(--teal) 16%,transparent);color:var(--teal)}
.ch-pill.ch-comm{background:var(--sunken);color:var(--muted)}
.ch-progs{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.ch-prog{padding:14px 16px;border-radius:18px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.ch-prog b{display:block;font-size:.94rem;font-weight:600}
.ch-prog b a{color:inherit;text-decoration:none}
.ch-prog b a:hover{color:var(--blue)}
.ch-prog small{display:block;font-size:.8rem;color:var(--muted);margin-top:2px}
.ch-prog p{margin:6px 0 0;font-size:.86rem;line-height:1.45}
.ch-ppl{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.ch-p{display:flex;gap:12px;align-items:center;padding:12px 14px;border-radius:18px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.ch-p .ui-av{margin:0;width:40px;height:40px;font-size:14px;flex:none}
.ch-p > span:last-child{display:flex;flex-direction:column;min-width:0}
.ch-p b{font-size:.92rem;font-weight:600;overflow-wrap:anywhere}
.ch-p b a{color:inherit;text-decoration:none}
.ch-p b a:hover{color:var(--blue);text-decoration:underline}
.ch-p small{font-size:.8rem;color:var(--muted);line-height:1.4;overflow-wrap:anywhere}
.ch-grp{font-size:.95rem;font-weight:600;color:var(--muted);margin:6px 0 -4px}
.ch-board{display:flex;flex-direction:column;gap:14px}
.ch-past{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:.9rem;list-style:none;margin:0;padding:0}
.ch-past li b{font-variant-numeric:tabular-nums;color:var(--muted);font-weight:500;margin-right:6px}
.ch-tbl td,.ch-tbl th{vertical-align:top}
.ch-tbl td.n,.ch-tbl th.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
@media (max-width:760px){.ch-two{grid-template-columns:1fr}.ch-card{padding:18px}.ch-facts{gap:6px}.ch-facts div{padding:8px 10px}.ch-facts dd{font-size:.98rem}}
"""

JS = r"""
(() => {
  const box = document.getElementById('chEvents'); if (!box) return;
  const cards = [...box.querySelectorAll('.ui-mc')], more = document.getElementById('chMore'), N = matchMedia('(max-width:760px)').matches ? 6 : 12;
  let ch = '', kind = '', open = false;
  function show() {
    let n = 0;
    for (const c of cards) {
      const ok = (!ch || c.dataset.ch === ch) && (!kind || (kind === 'chamber') === (c.dataset.k === 'chamber'));
      c.hidden = !ok || (!open && n >= N); if (ok) n++;
    }
    const left = cards.filter(c => (!ch || c.dataset.ch === ch) && (!kind || (kind === 'chamber') === (c.dataset.k === 'chamber'))).length - N;
    more.hidden = open || left <= 0; more.textContent = `Show ${left} more`;
    document.getElementById('chNone').hidden = n > 0;
    more.parentNode.hidden = more.hidden;
  }
  function chips(id, set) {
    const g = document.getElementById(id);
    g.addEventListener('click', ev => { const b = ev.target.closest('button'); if (!b) return;
      g.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); set(b.dataset.v); show(); });
  }
  chips('chWho', v => { ch = v; }); chips('chKind', v => { kind = v; });
  more.addEventListener('click', () => { open = true; show(); });
  show();
})();
"""


def _money(n):
    if n is None:
        return '—'
    a = abs(n)
    return f'${a / 1e6:.1f}M' if a >= 1e6 else f'${round(a / 1e3):,}K' if a >= 1e4 else f'${round(a):,}'


def _dt(s):
    try:
        return dt.datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _tile(d):
    return f'<span class="ui-date" aria-hidden="true"><span class="mo">{d.strftime("%b").upper()}</span><span class="d">{d.day}</span><span class="wd">{d.strftime("%a")}</span></span>'


def _when(ev):
    s, en = _dt(ev['starts']), _dt(ev.get('ends'))
    if not s:
        return ''
    if ev.get('all_day') or (s.hour == 0 and s.minute == 0 and en and en.hour == 23):
        if en and en.date() != s.date():
            return f"{s.strftime('%b %-d')} to {en.strftime('%b %-d')}"
        return s.strftime('%A, %B %-d')
    t = lambda d: d.strftime('%-I:%M %p').replace(':00 ', ' ').lower().replace('am', 'a.m.').replace('pm', 'p.m.')
    return s.strftime('%a, %b %-d') + ' · ' + t(s) + (f' to {t(en)}' if en and en.date() == s.date() and en > s else '')


def _name(r):
    return link(r['person_entity_id'], r['person_name']) if r['person_entity_id'] in build().ents else e(r['person_name'])


def _org(r):
    o = r.get('organization')
    if not o:
        return ''
    oid = r.get('organization_entity_id')
    return link(oid, o) if oid and oid in build().ents else e(o)


def _person(r):
    sub = [e(r['title'])] if r.get('title') else []
    if r.get('organization') and r['organization'] not in (r.get('title') or ''):
        sub.append(_org(r))
    if r.get('term_ends'):
        sub.append(f"Term ends {r['term_ends'][:4]}")
    return (f'<div class="ch-p">{avatar(r["person_name"], tone_of(r["person_name"]), photo=r.get("photo"))}<span><b>{_name(r)}</b>'
            f'<small>{" · ".join(sub)}</small></span></div>')


def chambers_page(out_dir):
    from page_datasets import chambers, chamber_leaders, chamber_events
    from opendata import datasets
    C, L, E = chambers(), chamber_leaders(), chamber_events()
    if not C:
        return '<div class="page"><h1>Chambers of commerce</h1><p>No chambers on file for this place yet.</p></div>'
    fn = {d[0]: d[3] for d in datasets()}
    ids_np = {c['entity_id'].split(':', 1)[1]: c for c in C}
    pay = [p for p in fn['nonprofit-payments']() if p['nonprofit_id'] in ids_np]
    today = dt.date.today().isoformat()
    events = [x for x in E if x['kind'] == 'event' and (x.get('ends') or x['starts'] or '')[:10] >= today]
    progs = [x for x in E if x['kind'] == 'program']
    board = [r for r in L if r['role_group'] not in ('Staff', 'Past chairs')]
    G = build()

    # --- the two chambers
    cards = []
    for c in C:
        tone = TONE.get(c['chamber_id'], 'blue')
        n_board = sum(1 for r in board if r['chamber_id'] == c['chamber_id'])
        acts = [('globe', 'Website', c['website']), ('users', 'Member directory', c['directory_url']), ('calendar', 'Events', c['events_url']), ('store', 'Join', c['join_url'])]
        cards.append(f'''<article class="ch-card" id="{e(c["chamber_id"])}">
  <div class="ch-card-hd">{avatar(c["short_name"], tone, "store")}<div><h3>{link(c["entity_id"], c["name"])}</h3>
    <p class="ch-tag">{e(c.get("tagline") or "")}{" · " if c.get("tagline") and c.get("founded") else ""}{("Since " + str(c["founded"])) if c.get("founded") else ""}</p></div></div>
  <p>{e(c["about"])}</p>
  <p class="ch-meets"><b>Serves:</b> {e(c["serves"])}.{(" " + e(c["board_meets"])) if c.get("board_meets") else ""}</p>
  <dl class="ch-facts">
    <div><dt>Revenue{f", {c['latest_return_year']}" if c.get("latest_return_year") else ""}</dt><dd>{_money(c.get("revenue"))}</dd></div>
    <div><dt>Staff on its IRS filing</dt><dd>{e(c.get("employees") or "—")}</dd></div>
    <div><dt>Board seats</dt><dd>{n_board}</dd></div>
  </dl>
  <div class="ch-acts">{"".join(f'<a class="ui-btn" href="{e(u)}" rel="noopener" target="_blank">{ico(i)}{t}</a>' for i, t, u in acts if u)}</div>
</article>''')

    # --- events
    short = {c['chamber_id']: c['short_name'] for c in C}
    ev_cards = []
    for x in events:
        d = _dt(x['starts'])
        if not d:
            continue
        where = ', '.join(v for v in [x.get('venue'), x.get('city')] if v)
        is_ch = bool(x.get('chamber_event'))
        pill = (f'<span class="ch-pill t-{TONE.get(x["chamber_id"], "blue")}">{e(short.get(x["chamber_id"]))}</span>' if is_ch
                else '<span class="ch-pill ch-comm">Community event</span>')
        ev_cards.append(f'''<div class="ui-mc" data-ch="{e(x["chamber_id"])}" data-k="{"chamber" if is_ch else "community"}">{_tile(d)}<div style="min-width:0">
  <b><a href="{e(x["url"])}" rel="noopener" target="_blank">{e(x["title"])}</a></b><small>{e(_when(x))}</small>{f"<small>{e(where)}</small>" if where else ""}{pill}</div></div>''')
    no_feed = [c for c in C if not any(x['chamber_id'] == c['chamber_id'] for x in events)]
    feed_note = ''.join(f' The {e(c["name"])} calendar can\'t be read automatically yet; see <a href="{e(c["events_url"])}" rel="noopener" target="_blank">its events calendar</a> and its regular programs below.' for c in no_feed)
    who_chips = ''.join(f'<button type="button" class="chip" data-v="{e(c["chamber_id"])}" aria-pressed="false">{e(c["short_name"])}</button>' for c in C)

    # --- programs
    prog_html = ''
    for c in C:
        ps = [p for p in progs if p['chamber_id'] == c['chamber_id']]
        if ps:
            prog_html += f'<h3 class="ch-grp">{e(c["short_name"])}</h3><div class="ch-progs">' + ''.join(
                f'<div class="ch-prog"><b><a href="{e(p["url"])}" rel="noopener" target="_blank">{e(p["title"])}</a></b><small>{e(p["schedule"])}</small><p>{e(p["about"])}</p></div>' for p in ps) + '</div>'

    # --- boards and staff
    order = ['Executive committee', 'Board', 'Ex officio (non-voting)', 'Honorary', 'Staff']
    label = {'Board': 'Directors', 'Ex officio (non-voting)': 'Ex officio (non-voting)', 'Honorary': 'Honorary members'}
    boards = []
    for c in C:
        rows = [r for r in L if r['chamber_id'] == c['chamber_id']]
        parts = []
        for g in order:
            rs = [r for r in rows if r['role_group'] == g]
            if rs:
                grid = f'<div class="ch-ppl">{"".join(_person(r) for r in rs)}</div>'
                parts.append(f'<h4 class="ch-grp">{e(label.get(g, g))}</h4>{grid}' if g == 'Executive committee'
                             else f'<details class="tbl-toggle"><summary>{e(label.get(g, g))} ({len(rs)})</summary>{grid}</details>')
        past = sorted((r for r in rows if r['role_group'] == 'Past chairs'), key=lambda r: -(r.get('year') or 0))
        if past:
            parts.append(f'<details class="tbl-toggle"><summary>Past chairs since 2016</summary><ul class="ch-past">{"".join("<li><b>" + str(r["year"]) + "</b>" + _name(r) + "</li>" for r in past)}</ul></details>')
        boards.append(f'<div class="ch-board"><h3 class="ch-grp" style="font-size:1.05rem;color:var(--ink)">{e(c["name"])} <span class="muted" style="font-weight:400;font-size:.86rem">as listed on <a href="{e(c["board_url"])}" rel="noopener" target="_blank">its website</a>, {e(c["as_of"])}</span></h3>{"".join(parts)}</div>')

    # --- where boards meet local government business
    biz = [r for r in board if (r.get('organization_entity_id') or '').startswith(('vendor:', 'business:')) and r['organization_entity_id'] in G.ents]
    from overlaps_page import chamber_rows, chamber_keys
    have = chamber_keys()
    biz_table = chamber_rows([(f'{_name(r)}<span class="sub">{e(r["title"])}, {e(r["chamber"])}</span>', _org(r), 'Sunbiz filing under the same name' if r['organization_entity_id'].startswith('business:') else 'No local payments or gifts on file')
                              for r in biz if (r['person_name'], r.get('organization')) not in have])
    gov_rows = [r for r in board if (r.get('organization_entity_id') or '').startswith('gov:') or r['person_entity_id'].startswith('person:')]

    # --- public money
    pay_rows = ''.join(f'<tr><td>{link(ids_np[p["nonprofit_id"]]["entity_id"], ids_np[p["nonprofit_id"]]["short_name"])}</td><td>{e(p["payer"])}</td><td>{e(p.get("date") or "")}</td>'
                       f'<td class="n">{_money(p["amount"])}</td></tr>' for p in sorted(pay, key=lambda p: -(p['amount'] or 0)))
    fin_rows = ''.join(f'<tr><td>{link(c["entity_id"], c["short_name"])}<br><span class="muted" style="font-size:.8rem">{e(c.get("tax_status") or "")}</span></td><td>{e(c.get("latest_return_form") or "")} {e(c.get("latest_return_year") or "")}</td>'
                       f'<td class="n">{_money(c.get("revenue"))}</td><td class="n">{_money(c.get("expenses"))}</td><td class="n">{_money(c.get("assets"))}</td><td class="n">{e(c.get("employees") or "—")}</td></tr>' for c in C)
    fin_rows += ''.join(f'<tr><td>{link(c["foundation_entity_id"], c["foundation_name"])}<br><span class="muted" style="font-size:.8rem">The Bay County Chamber\'s charity</span></td><td></td><td class="n">{_money(c.get("foundation_revenue"))}</td><td class="n"></td><td class="n"></td><td class="n"></td></tr>'
                        for c in C if c.get('foundation_entity_id') and c['foundation_entity_id'] in G.ents)
    total_pay = sum(p['amount'] or 0 for p in pay)
    n_board = len(board)
    n_ch_events = sum(1 for x in events if x.get('chamber_event'))

    k = lambda lab, v, s: f'<div class="kpi"><span class="eyebrow">{lab}</span><span class="v">{v}</span><span class="s">{s}</span></div>'
    kpis = (k('Chambers', len(C), ' and '.join(e(c['short_name']) for c in C)) +
            k('Board seats', n_board, f'Plus {sum(1 for r in L if r["role_group"] == "Staff")} staff. {sum(1 for r in board if r["person_match"])} also show up on other local filings') +
            k('Coming up', len(events), f'{n_ch_events} chamber events, the rest community events they list') +
            k('Paid by tourism agencies', _money(total_pay), 'Event fees and sponsorships, FY2024 to FY2026'))

    return f'''<style>{CSS}</style>
<div class="page tax ch">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">People · Business community</span><h1>Chambers of commerce</h1>
    <p class="lede">Bay County has two main chambers of commerce: the Bay County Chamber, which covers the whole county, and the Panama City Beach Chamber. Here is who leads them, what's coming up, the public money they get and where their boards meet local government business.</p></div>
    <div class="stamp"><a class="pill" href="/connections/nonprofits">All nonprofits →</a><span>Boards and staff as listed on each chamber's website, {e(C[0]["as_of"])}</span></div></header>
  <div class="kpis">{kpis}</div>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>What a chamber of commerce is</h2>
    <ol class="ex-steps"><li><b>A private group of businesses.</b> Members pay dues to belong. A chamber is a nonprofit business league (501(c)(6)), not a government agency, and it isn't part of the U.S. or Florida Chamber.</li>
    <li><b>It connects, promotes and speaks up.</b> Chambers run networking events, leadership classes and ribbon cuttings, keep a member directory, and take positions on local issues such as taxes, roads and the bases.</li>
    <li><b>Why it's on this site.</b> Their boards bring together business owners, public agency heads and military leaders, some of their members do business with local governments, and the tourism agencies pay them for events and sponsorships.</li></ol></div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="chambers" data-tile="The chambers">The two chambers</h2><span class="muted">Figures from each chamber's latest IRS Form 990</span></div>
    <div class="ch-two">{"".join(cards)}</div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="events" data-tile="Coming up">Coming up</h2><span class="muted">From each chamber's public calendar</span></div>
    <div class="ch-ctl">
      <div class="chips" id="chWho" role="group" aria-label="Chamber"><button type="button" class="chip" data-v="" aria-pressed="true">Both chambers</button>{who_chips}</div>
      <div class="chips" id="chKind" role="group" aria-label="Kind of event"><button type="button" class="chip" data-v="" aria-pressed="true">All events</button><button type="button" class="chip" data-v="chamber" aria-pressed="false">Chamber events</button><button type="button" class="chip" data-v="community" aria-pressed="false">Community events</button></div>
    </div>
    <div class="ch-ev" id="chEvents">{"".join(ev_cards)}</div>
    <p class="note" id="chNone" hidden>No upcoming events match.{feed_note}</p>
    <div><button type="button" class="ui-btn ch-morebtn" id="chMore" hidden>Show more</button></div>
    <p class="note">Times are local. Check the chamber's page before you go: details change. Community events are other groups' events that a chamber lists on its calendar.{feed_note}</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="programs" data-tile="Programs">Regular programs</h2><span class="muted">Monthly meetings, yearly events and leadership classes</span></div>
    {prog_html}</section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="boards" data-tile="Who leads them">Who leads them</h2><span class="muted">{n_board} board seats</span></div>
    <p>Each name links to a profile with every other board, business and public record it appears in. A person is matched to another local filing only by the same first and last name; a public official is named as one only where the chamber lists their government post.</p>
    {"".join(boards)}</section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="business" data-tile="Business ties">Board members' businesses, public money and campaign gifts</h2><span class="muted">Board members who are officials, whose organization local governments paid or that gave to campaigns, or with a Sunbiz filing under the same name</span></div>
    {biz_table}
    <p class="note">"Paid" adds every payment by a local government on the site for that company since 2016 (federal contracts are not counted); follow the company's link for each contract and vote. A board member's own gifts count only when they run the company the chamber lists them with. {len(gov_rows)} board seats are held by people representing a local government or public agency. Data: <a href="/api/v1/datasets/chamber-overlaps">chamber-overlaps</a>.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="money" data-tile="Money">Revenue, and what governments paid them</h2></div>
    <div class="tablewrap"><table class="tx-table ch-tbl"><thead><tr><th>Organization</th><th>Latest IRS filing</th><th class="n">Revenue</th><th class="n">Expenses</th><th class="n">Assets</th><th class="n">Employees</th></tr></thead><tbody>{fin_rows}</tbody></table></div>
    <h3 class="ch-grp">Paid by local governments and tourism agencies</h3>
    <div class="tablewrap"><table class="tx-table ch-tbl"><thead><tr><th>Chamber</th><th>Paid by</th><th>Years</th><th class="n">Amount</th></tr></thead><tbody>{pay_rows or '<tr><td colspan="4" class="muted">No payments on record.</td></tr>'}</tbody></table></div>
    <p class="note">Payments come from the tourism agencies' check registers on the site (FY2024 to FY2026); most are sponsorships and event fees. Membership dues paid by governments, if any, are not broken out in the records we have.</p></section>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>Boards, staff and programs</b> are copied from each chamber's own website: names, titles and the organization each board member represents. No phone numbers, emails or addresses.</li>
      <li><b>Photos</b> are the headshots each chamber publishes on its own board and staff pages. To have one taken down, use the <a href="/about#contact">contact form</a>.</li>
      <li><b>Events</b> are read every day from the Panama City Beach Chamber's public calendar feed. The Bay County Chamber's calendar runs on a members platform that turns automated readers away, so its regular programs are listed instead.</li>
      <li><b>Revenue, staff and public money</b> come from IRS Form 990 filings and the tourism agencies' payment records, the same data as the <a href="/connections/nonprofits">Nonprofits</a> page.</li>
      <li><b>Member lists</b> are on each chamber's directory; they aren't copied here yet.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/chambers">chambers</a> (<a href="/downloads/chambers.csv">CSV</a>) · <a href="/api/v1/datasets/chamber-leaders">chamber-leaders</a> (<a href="/downloads/chamber-leaders.csv">CSV</a>) · <a href="/api/v1/datasets/chamber-events">chamber-events</a> (<a href="/downloads/chamber-events.csv">CSV</a>).</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>{JS}</script>'''
