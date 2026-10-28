"""Military and the bases (/military): Tyndall Air Force Base and Naval Support Activity Panama City, the latest news
from the units on them, and the federal contracts that go to companies based in Bay County.

Built from the military-installations, military-news, federal-contracts and federal-contract-years datasets
(site/page_datasets.py, from data/military/<county>/). Every company name links to its profile (recipient_entity_id).
"""
import datetime as dt
import html
from collections import defaultdict

from entity_links import a as link, build
from ui import avatar, ico

e = lambda s: html.escape(str(s if s is not None else ''))
TONE = {'Air Force': 'blue', 'Navy': 'teal'}

CSS = r"""
.mil-two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.mil-card{display:flex;flex-direction:column;gap:14px;padding:22px;border-radius:24px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.mil-card-hd{display:flex;gap:14px;align-items:center}
.mil-card-hd .ui-av{margin:0;flex:none}
.mil-card h3{font-size:1.15rem;font-weight:600;margin:0;text-wrap:balance}
.mil-tag{font-size:.86rem;color:var(--muted);margin:2px 0 0}
.mil-card p{margin:0;font-size:.92rem;line-height:1.5}
.mil-facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0}
.mil-facts div{padding:10px 12px;border-radius:14px;background:var(--sunken);min-width:0}
.mil-facts dt{font-size:.76rem;color:var(--muted)}
.mil-facts dd{margin:2px 0 0;font:600 1rem var(--f-body);font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.mil-cmd{font-size:.86rem;color:var(--muted)}
.mil-acts{display:flex;flex-wrap:wrap;gap:8px}
.mil-acts .ui-btn{min-height:40px;font-size:.86rem}
.mil-card details summary{cursor:pointer;font-size:.88rem;font-weight:600}
.mil-card details ul{margin:8px 0 0;padding-left:18px;font-size:.88rem;line-height:1.55}
.mil-news{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:14px}
.mil-story{display:flex;flex-direction:column;border-radius:20px;background:var(--surface);box-shadow:var(--ui-shadow);overflow:hidden;min-width:0}
.mil-story[hidden]{display:none}
.mil-story .ph{aspect-ratio:16/9;background:var(--sunken);overflow:hidden}
.mil-story .ph img{width:100%;height:100%;object-fit:cover;display:block}
.mil-story .bd{display:flex;flex-direction:column;gap:6px;padding:14px 16px 16px}
.mil-story b{font-size:.98rem;font-weight:600;line-height:1.35;text-wrap:pretty}
.mil-story b a{color:inherit;text-decoration:none}
.mil-story b a:hover{color:var(--blue);text-decoration:underline}
.mil-story small{font-size:.8rem;color:var(--muted)}
.mil-story p{margin:0;font-size:.86rem;line-height:1.45;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.mil-pill{align-self:flex-start;font-size:.72rem;font-weight:600;padding:2px 9px;border-radius:999px}
.mil-pill.t-blue{background:color-mix(in srgb,var(--blue) 14%,transparent);color:var(--blue)}
.mil-pill.t-teal{background:color-mix(in srgb,var(--teal) 16%,transparent);color:var(--teal)}
.mil .mil-morebtn{width:auto;border:0;cursor:pointer;font-family:inherit}
.mil .mil-morebtn[hidden]{display:none}
.mil-chart{width:100%;height:auto;display:block;overflow:visible}
.mil-chart text{font:12px var(--f-body);fill:var(--muted)}
.mil-chart .v{fill:var(--ink);font-weight:600;font-variant-numeric:tabular-nums}
.mil-chart .def{fill:var(--navy)}
.mil-chart .oth{fill:var(--teal)}
.mil-key{display:flex;gap:16px;flex-wrap:wrap;font-size:.84rem;color:var(--muted);margin:4px 0 0}
.mil-key i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.mil-tbl td,.mil-tbl th{vertical-align:top}
.mil-tbl td.n,.mil-tbl th.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.mil-tbl .sub{display:block;color:var(--muted);font-size:.8rem;margin-top:2px}
.mil-tbl tr[hidden]{display:none}
@media (max-width:760px){.mil-two{grid-template-columns:1fr}.mil-card{padding:18px}.mil-facts{gap:6px}.mil-facts div{padding:8px 10px}
  .mil-tbl .hide-sm{display:none}}
"""

JS = r"""
(() => {
  const box = document.getElementById('milNews'); if (!box) return;
  const cards = [...box.querySelectorAll('.mil-story')], more = document.getElementById('milMore'), N = matchMedia('(max-width:760px)').matches ? 4 : 9;
  let base = '', open = false;
  function show() {
    let n = 0; const ok = c => !base || c.dataset.b === base;
    for (const c of cards) { c.hidden = !ok(c) || (!open && n >= N); if (ok(c)) n++; }
    const left = cards.filter(ok).length - N;
    more.hidden = open || left <= 0; more.textContent = `Show ${left} more stories`;
  }
  const g = document.getElementById('milBase');
  g.addEventListener('click', ev => { const b = ev.target.closest('button'); if (!b) return;
    g.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); base = b.dataset.v; show(); });
  more.addEventListener('click', () => { open = true; show(); });
  show();
})();
"""


def _money(n):
    if n is None:
        return '—'
    a, s = abs(n), '-' if n < 0 else ''
    return f'{s}${a / 1e9:.2f}B' if a >= 1e9 else f'{s}${a / 1e6:.1f}M' if a >= 1e6 else f'{s}${round(a / 1e3):,}K' if a >= 1e4 else f'{s}${round(a):,}'


def _date(s):
    try:
        return dt.datetime.fromisoformat(s).strftime('%b %-d, %Y')
    except (TypeError, ValueError):
        return ''


def _co(eid, name):
    import ids
    name = ids.biz_case(name)
    return link(eid, name) if eid and eid in build().ents else e(name)


def _chart(years):
    """Stacked bars, defense on the bottom, one per year."""
    ys = sorted(years)
    if not ys:
        return ''
    W, H, pad, top = 760, 230, 26, 22
    mx = max(sum(years[y].values()) for y in ys) or 1
    bw = (W - 20) / len(ys)
    out = []
    for i, y in enumerate(ys):
        d, o = max(years[y].get('d', 0), 0), max(years[y].get('o', 0), 0)
        x = 10 + i * bw + bw * .18
        w = bw * .64
        hd, ho = (H - pad - top) * d / mx, (H - pad - top) * o / mx
        yb = H - pad
        out.append(f'<rect class="def" x="{x:.1f}" y="{yb - hd:.1f}" width="{w:.1f}" height="{hd:.1f}" rx="3"><title>{y}: {_money(d)} defense</title></rect>')
        out.append(f'<rect class="oth" x="{x:.1f}" y="{yb - hd - ho:.1f}" width="{w:.1f}" height="{ho:.1f}" rx="3"><title>{y}: {_money(o)} other agencies</title></rect>')
        out.append(f'<text class="v" x="{x + w / 2:.1f}" y="{yb - hd - ho - 6:.1f}" text-anchor="middle">{_money(d + o).replace("$", "$")}</text>')
        out.append(f'<text x="{x + w / 2:.1f}" y="{H - 8}" text-anchor="middle">{y if len(ys) < 9 or i % 1 == 0 else ""}</text>')
    return (f'<svg class="mil-chart" viewBox="0 0 {W} {H}" role="img" aria-label="Federal contract money obligated to Bay County companies each year since 2016">'
            + ''.join(out) + '</svg>')


def military_page(out_dir):
    from page_datasets import military_installations, military_news, federal_contracts, federal_contract_years
    I, N, A, Y = military_installations(), military_news(), federal_contracts(), federal_contract_years()
    if not I:
        return '<div class="page"><h1>Military and the bases</h1><p>No military installations on file for this place yet.</p></div>'
    tone = {b['installation_id']: TONE.get(b['branch'], 'blue') for b in I}
    short = {b['installation_id']: b['short_name'] for b in I}

    # --- the bases
    cards = []
    for b in I:
        facts = [('Opened', b.get('opened')), ('Acres', f"{b['acres']:,}" if b.get('acres') else None), ('People', f"About {b['personnel']:,}" if b.get('personnel') else None),
                 ('Branch', b['branch'])]
        facts = [f for f in facts if f[1]][:3]
        tenants = ''.join(f'<li>{e(t.strip())}</li>' for t in (b.get('tenants') or '').split(';') if t.strip())
        cmd = (f'<p class="mil-cmd"><b>In command:</b> {e(b["commander"])}, {e(b["commander_title"])}, since '
               f'<a href="{e(b["commander_source_url"])}" rel="noopener" target="_blank">{e(_date(b["commander_since"]))}</a>.</p>') if b.get('commander') else ''
        acts = [('globe', 'Base website', b.get('website')), ('news', 'All its news on DVIDS', b.get('dvids_url'))]
        cards.append(f'''<article class="mil-card" id="{e(b["installation_id"])}">
  <div class="mil-card-hd">{avatar(b["short_name"], tone[b["installation_id"]], "shield")}<div><h3>{e(b["name"])}</h3>
    <p class="mil-tag">{e(b["branch"])} · {e(b["host_unit"])}</p></div></div>
  <p>{e(b["mission"])}</p>
  {f'<p>{e(b["storm"])}</p>' if b.get("storm") else ""}
  {cmd}
  <dl class="mil-facts">{"".join(f"<div><dt>{e(k)}</dt><dd>{e(v)}</dd></div>" for k, v in facts)}</dl>
  {f'<details><summary>Units on the base</summary><ul>{tenants}</ul></details>' if tenants else ""}
  <p class="mil-cmd">{e(b["location"])}.</p>
  <div class="mil-acts">{"".join(f'<a class="ui-btn" href="{e(u)}" rel="noopener" target="_blank">{ico(i)}{t}</a>' for i, t, u in acts if u)}</div>
</article>''')

    # --- news
    stories = sorted(N, key=lambda s: s.get('published') or '', reverse=True)
    st_cards = []
    for s in stories:
        img = f'<div class="ph"><img src="{e(s["image_url"])}" alt="" loading="lazy" decoding="async"></div>' if s.get('image_url') else ''
        st_cards.append(f'''<article class="mil-story" data-b="{e(s["installation_id"])}">{img}<div class="bd">
  <span class="mil-pill t-{tone.get(s["installation_id"], "blue")}">{e(short.get(s["installation_id"], ""))}</span>
  <b><a href="{e(s["url"])}" rel="noopener" target="_blank">{e(s["title"])}</a></b>
  <small>{e(_date(s.get("published")))} · {e(s["unit"])}</small>
  {f"<p>{e(s['summary'])}</p>" if s.get("summary") else ""}</div></article>''')
    base_chips = ''.join(f'<button type="button" class="chip" data-v="{e(b["installation_id"])}" aria-pressed="false">{e(b["short_name"])}</button>' for b in I)
    latest = stories[0]['published'] if stories else None

    # --- federal contracts
    total = sum(r['obligated'] for r in Y)
    defense = sum(r['obligated'] for r in Y if r['defense'])
    years = defaultdict(lambda: {'d': 0.0, 'o': 0.0})
    for r in Y:
        years[r['year']]['d' if r['defense'] else 'o'] += r['obligated']
    co = {}
    for r in Y:
        c = co.setdefault(r['recipient_entity_id'], {'name': r['recipient'], 'total': 0.0, 'defense': 0.0, 'by': defaultdict(float), 'awards': set(), 'city': None})
        c['total'] += r['obligated']
        c['defense'] += r['obligated'] if r['defense'] else 0
        c['by'][r['sub_agency'] or r['agency']] += r['obligated']
    for a in A:
        c = co.get(a['recipient_entity_id'])
        if c:
            c['awards'].add(a['award_key'])
            c['city'] = c['city'] or a.get('recipient_city')
    ranked = sorted((c for c in co.values() if c['total'] > 0), key=lambda c: -c['total'])
    eid_of = {id(c): k for k, c in co.items()}
    co_rows = ''.join(
        f'<tr><td>{_co(eid_of[id(c)], c["name"])}<span class="sub">{e(c["city"] or "")}</span></td>'
        f'<td class="hide-sm">{e(max(c["by"].items(), key=lambda kv: kv[1])[0])}</td><td class="n hide-sm">{len(c["awards"])}</td>'
        f'<td class="n">{round(100 * c["defense"] / c["total"]) if c["total"] else 0}%</td><td class="n">{_money(c["total"])}</td></tr>'
        for c in ranked)
    big = A[:25]
    big_rows = ''.join(
        f'<tr><td>{_co(a["recipient_entity_id"], a["recipient"])}<span class="sub">{link(a.get("agency_entity_id"), a["sub_agency"] or a["agency"])}</span></td>'
        f'<td class="hide-sm">{e((a.get("description") or "").capitalize()[:140])}<span class="sub">{e(a["award_id"])} · {e((a.get("start_date") or "")[:4])}–{e((a.get("end_date") or "")[:4])}</span></td>'
        f'<td class="n"><a href="{e(a["source_url"])}" rel="noopener" target="_blank">{_money(a["obligated"])}</a></td></tr>' for a in big)
    ag = defaultdict(lambda: {'t': 0.0, 'co': set(), 'top': '', 'eid': None})
    for r in Y:
        k = (r['agency'], r['sub_agency'] or r['agency'])
        ag[k]['t'] += r['obligated']
        ag[k]['co'].add(r['recipient_entity_id'])
        ag[k]['eid'] = ag[k]['eid'] or r.get('agency_entity_id')
    ag_rows = ''.join(f'<tr><td>{link(v["eid"], sub)}{f"<span class=sub>{e(agency)}</span>" if sub != agency else ""}</td><td class="n">{len(v["co"])}</td><td class="n">{_money(v["t"])}</td></tr>'
                      for (agency, sub), v in sorted(ag.items(), key=lambda kv: -kv[1]['t']) if v['t'] > 0)
    n_co = len(ranked)
    first_y, last_y = (min(years), max(years)) if years else (2016, 2016)

    k = lambda lab, v, s: f'<div class="kpi"><span class="eyebrow">{lab}</span><span class="v">{v}</span><span class="s">{s}</span></div>'
    kpis = (k('Bases', len(I), ' and '.join(e(b['short_name']) for b in I)) +
            k('News stories', len(stories), f'Latest {e(_date(latest))}' if latest else 'From the units on each base') +
            k('Federal contracts', _money(total), f'To {n_co} Bay County companies, {first_y} to {last_y}') +
            k('From the Defense Department', f'{round(100 * defense / total) if total else 0}%', f'{_money(defense)}; most of the rest is Coast Guard'))

    return f'''<style>{CSS}</style>
<div class="page tax mil">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">People · Bases and military</span><h1>Military and the bases</h1>
    <p class="lede">Bay County is home to Tyndall Air Force Base and Naval Support Activity Panama City. Here is what each base does, the latest news from the units on them, and the federal contracts that go to companies based in the county.</p></div>
    <div class="stamp"><a class="pill" href="#contracts">Federal contracts →</a><span>News read daily from each unit's public feed</span></div></header>
  <div class="kpis">{kpis}</div>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>Why the bases matter here</h2>
    <ol class="ex-steps"><li><b>Two bases, thousands of jobs.</b> Tyndall flies F-35A fighters and runs air defense for the continental U.S. NSA Panama City is home to a Navy research lab and the dive school for every branch.</li>
    <li><b>Federal money reaches local companies.</b> Shipbuilders, engineers and contractors based in Bay County win contracts from the Navy, Air Force, Coast Guard and other agencies. That money is listed below by company.</li>
    <li><b>Rebuilding after Michael.</b> Hurricane Michael wrecked Tyndall in 2018. Its rebuild is one of the largest construction projects in the region.</li></ol></div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="bases" data-tile="The bases">The two bases</h2></div>
    <div class="mil-two">{"".join(cards)}</div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="news" data-tile="News">Latest news from the bases</h2><span class="muted">Stories by each unit's public affairs office</span></div>
    <div class="chips" id="milBase" role="group" aria-label="Base"><button type="button" class="chip" data-v="" aria-pressed="true">Both bases</button>{base_chips}</div>
    <div class="mil-news" id="milNews">{"".join(st_cards)}</div>
    <div><button type="button" class="ui-btn mil-morebtn" id="milMore" hidden>Show more</button></div>
    <p class="note">Stories and photos open on DVIDS, the Defense Department's public media site. New stories are added every day.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="contracts" data-tile="Federal contracts">Federal contracts to Bay County companies</h2><span class="muted">Money obligated each year, {first_y} to {last_y}</span></div>
    {_chart(years)}
    <p class="mil-key"><span><i style="background:var(--navy)"></i>Defense Department (Navy, Air Force, Army and others)</span><span><i style="background:var(--teal)"></i>Other agencies (Coast Guard, VA and others)</span></p>
    <p>{_money(total)} in federal contracts went to {n_co} companies with a business address in Bay County since 2016. These are where the companies are based; the work can happen anywhere.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="companies" data-tile="Companies">Local companies with federal contracts</h2><span class="muted">Since 2016, biggest first</span></div>
    <div class="tablewrap"><table class="tx-table mil-tbl" id="milCo" data-tt-sort="4:desc"><thead><tr><th>Company</th><th class="hide-sm">Paid mostly by</th><th class="n hide-sm">Contracts</th><th class="n">Defense</th><th class="n">Obligated</th></tr></thead><tbody>{co_rows}</tbody></table></div>
    <p class="note">Each company links to its profile, with any local government payments, campaign gifts and board ties on the site. Use the filter box to find a company.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="biggest">Biggest contracts</h2><span class="muted">Money obligated since 2016</span></div>
    <div class="tablewrap"><table class="tx-table mil-tbl" data-tt-sort="2:desc" data-tt-year="off"><thead><tr><th>Company and agency</th><th class="hide-sm">What it buys</th><th class="n">Obligated</th></tr></thead><tbody>{big_rows}</tbody></table></div>
    <p class="note">Each amount opens the contract on USAspending.gov. Contracts that started before 2016 count only the money added in 2016 or later.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="agencies" data-tile="Who pays">Which agencies pay</h2></div>
    <div class="tablewrap"><table class="tx-table mil-tbl" data-tt-sort="2:desc"><thead><tr><th>Agency or branch</th><th class="n">Companies</th><th class="n">Obligated</th></tr></thead><tbody>{ag_rows}</tbody></table></div></section>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>News</b> is read every day from DVIDS, where the public affairs offices of the 325th Fighter Wing, the 601st Air and Space Operations Center, NSA Panama City, Naval Surface Warfare Center Panama City Division and the Navy Experimental Diving Unit post their stories. The base websites turn automated readers away. Each feed shows only its latest stories, so older stories fill in over time.</li>
      <li><b>Base facts and commanders</b> are checked by hand against the units' own stories and public base histories. Commanders change every two to three years.</li>
      <li><b>Federal contracts</b> come from <a href="https://www.usaspending.gov/search" rel="noopener" target="_blank">USAspending.gov</a>: every contract action since January 1, 2016 for a company whose registered business address is in Bay County. Amounts are money obligated (committed), not paid out, and include modifications and cuts. Street addresses are not shown.</li>
      <li><b>Company links:</b> a contractor is joined to a local vendor or a business campaign donor when the names match; otherwise it gets its own profile.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/military-installations">military-installations</a> (<a href="/downloads/military-installations.csv">CSV</a>) · <a href="/api/v1/datasets/military-news">military-news</a> (<a href="/downloads/military-news.csv">CSV</a>) · <a href="/api/v1/datasets/federal-contracts">federal-contracts</a> (<a href="/downloads/federal-contracts.csv">CSV</a>) · <a href="/api/v1/datasets/federal-contract-years">federal-contract-years</a> (<a href="/downloads/federal-contract-years.csv">CSV</a>).</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>{JS}</script>'''
