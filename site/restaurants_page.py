"""Restaurant inspections (/restaurants) and new businesses (/new-businesses).

/restaurants: every restaurant, food truck and caterer in the county with its state food safety inspections since 2016
(datasets restaurants and restaurant-inspections, site/page_datasets.py, from data/restaurants/<county>/, which
data/restaurants/fetch_dbpr.py refreshes daily). The searchable list reads /data/restaurants-page.json (named apart from the dataset files the apps read), written here from the
same rows, so the page and the API never disagree.

/new-businesses: every company filed with the state since 2016 with its main address in the county (dataset
new-businesses, from the Sunbiz quarterly file) and every newly licensed restaurant. The list reads
/data/new-businesses-page.json (the last 12 months of filings).

License holders and businesses link to their profile (entity_graph.page_url): a company local governments paid, a
nonprofit, or the business's own /profile/business/<doc> page, which the API fills from new-businesses and restaurants.
"""
import datetime as dt
import html
import json
import os
from collections import Counter

from entity_graph import page_url
from ui import ico

e = lambda s: html.escape(str(s if s is not None else ''))
LEVEL_CLS = {'ok': 'ok', 'warning': 'warn', 'fine': 'bad', 'closed': 'bad'}

CSS = r"""
.rs-ctl{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center}
.rs-ctl input[type=search]{flex:1 1 260px;min-width:0;min-height:44px;padding:0 14px;border-radius:14px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font:inherit}
.rs-ctl select{min-height:44px;padding:0 12px;border-radius:14px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font:inherit}
.rs-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;margin-top:14px;align-items:start}
.rs-card{display:flex;flex-direction:column;gap:8px;padding:16px 18px;border-radius:20px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.rs-card[hidden]{display:none}
.rs-card:target{outline:2px solid var(--blue);outline-offset:2px}
.rs-card h3{font-size:1rem;font-weight:600;margin:0;overflow-wrap:anywhere}
.rs-sub{font-size:.82rem;color:var(--muted);margin:0;overflow-wrap:anywhere}
.rs-sub a{color:inherit}
.rs-row{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;font-size:.84rem}
.rs-res{display:inline-block;padding:2px 10px;border-radius:999px;font-weight:600;font-size:.8rem;background:var(--sunken)}
.rs-res.ok{background:color-mix(in srgb,var(--teal) 14%,transparent);color:var(--teal)}
.rs-res.warn{background:color-mix(in srgb,var(--amber) 28%,transparent);color:var(--ink)}
.rs-res.bad{background:color-mix(in srgb,var(--salmon) 16%,transparent);color:var(--accent-ink)}
.rs-meta{color:var(--muted);font-variant-numeric:tabular-nums}
.rs-card button.rs-more{align-self:flex-start;border:0;background:none;color:var(--blue);font:600 .84rem var(--f-body);padding:4px 0;cursor:pointer;min-height:32px}
.rs-hist{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:8px;border-top:1px solid var(--line);padding-top:10px}
.rs-hist li{font-size:.82rem;line-height:1.45}
.rs-hist li b{font-variant-numeric:tabular-nums}
.rs-hist .rs-items{color:var(--muted)}
.rs-count{font-size:.86rem;color:var(--muted);margin:10px 0 0}
.rs-tbl td,.rs-tbl th{vertical-align:top}
.rs-tbl td.n,.rs-tbl th.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.rs-tbl small{display:block;color:var(--muted);font-size:.78rem}
.rs-two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.nb-month{display:flex;align-items:flex-end;gap:2px;height:120px;margin:8px 0 4px}
.nb-month span{flex:1;background:var(--blue);border-radius:3px 3px 0 0;min-height:2px;opacity:.85}
.nb-month span.cur{background:var(--salmon)}
.nb-axis{display:flex;justify-content:space-between;font-size:.76rem;color:var(--muted)}
@media (max-width:760px){.rs-two{grid-template-columns:1fr}.rs-list{grid-template-columns:1fr}}
"""

RS_JS = r"""
(() => {
  const box = document.getElementById('rsList'); if (!box) return;
  const q = document.getElementById('rsQ'), city = document.getElementById('rsCity'), cnt = document.getElementById('rsCount'), more = document.getElementById('rsMore');
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const CLS = {ok: 'ok', warning: 'warn', fine: 'bad', closed: 'bad'};
  const fmt = d => d ? new Date(d + 'T12:00:00').toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'}) : '';
  let D = null, show = '', N = 24;
  function card(r) {
    // [license, name, kind, city, address, licensed_now, last_date, last_level, last_result, hp_year, closures, opened, licensee, licensee_url, inspections]
    const [lic, name, kind, cty, addr, now, last, lvl, res, hp, clo, opened, who, whoUrl, n] = r;
    const holder = who ? (whoUrl ? `<a href="${esc(whoUrl)}">${esc(who)}</a>` : esc(who)) : '';
    return `<article class="rs-card" id="r${esc(lic)}" data-lic="${esc(lic)}"><h3>${esc(name)}</h3>
      <p class="rs-sub">${esc([kind, addr, cty].filter(Boolean).join(' · '))}${now ? '' : ' · <b>No longer licensed</b>'}</p>
      ${holder ? `<p class="rs-sub">License holder: ${holder}</p>` : ''}
      <div class="rs-row">${res ? `<span class="rs-res ${CLS[lvl] || ''}">${esc(res)}</span>` : '<span class="rs-res">Not inspected yet</span>'}<span class="rs-meta">${esc(fmt(last))}</span></div>
      <div class="rs-row rs-meta">${n} inspection${n === 1 ? '' : 's'} since 2016${hp ? ` · ${hp} high-priority violation${hp === 1 ? '' : 's'} in the last year` : ''}${clo ? ` · <b style="color:var(--accent-ink)">${clo} emergency closure${clo === 1 ? '' : 's'}</b>` : ''}${opened ? ` · opened ${esc(fmt(opened))}` : ''}</div>
      ${n ? '<button type="button" class="rs-more" aria-expanded="false">Inspection history</button>' : ''}</article>`;
  }
  function hist(lic) {
    const rows = D.i[lic] || [];
    // items: "0301 2201" = violation item 03 cited once, 22 once (item names in D.v)
    const named = s => (s || '').split(' ').filter(Boolean).map(t => (D.v[t.slice(0, 2)] || 'Item ' + t.slice(0, 2)) + (t.slice(2) !== '1' ? ` (${t.slice(2)})` : '')).join('; ');
    return '<ul class="rs-hist">' + rows.map(([d, type, visit, res, lvl, hp, im, ba, codes]) => [d, type, visit, res, lvl, hp, im, ba, named(codes)]).map(([d, type, visit, res, lvl, hp, im, ba, items]) =>
      `<li><b>${esc(fmt(d))}</b> · ${esc(visit > 1 ? 'Follow-up visit' : type)} · <span class="rs-res ${CLS[lvl] || ''}">${esc(res)}</span><br>
       ${hp + im + ba ? `${hp} high priority, ${im} intermediate, ${ba} basic${items ? `<br><span class="rs-items">${esc(items)}</span>` : ''}` : 'No violations'}</li>`).join('') + '</ul>';
  }
  function filter() {
    if (!D) return;
    const t = q.value.trim().toLowerCase(), c = city.value, yr = new Date(Date.now() - 365 * 864e5).toISOString().slice(0, 10);
    const ok = D.r.filter(r => (!t || (r[1] + ' ' + (r[12] || '') + ' ' + (r[4] || '')).toLowerCase().includes(t)) && (!c || r[3] === c) &&
      (show === 'closed' ? r[10] > 0 : show === 'warn' ? r[9] > 0 : show === 'new' ? (r[11] || '') >= yr : show === 'gone' ? !r[5] : r[5]));
    box.innerHTML = ok.slice(0, N).map(card).join('');
    cnt.textContent = `${ok.length.toLocaleString('en-US')} match${ok.length === 1 ? '' : 'es'}` + (ok.length > N ? `, showing ${N}` : '');
    more.hidden = ok.length <= N;
  }
  box.addEventListener('click', ev => {
    const b = ev.target.closest('.rs-more'); if (!b) return;
    const c = b.closest('.rs-card'), open = b.getAttribute('aria-expanded') === 'true';
    if (open) { c.querySelector('.rs-hist')?.remove(); b.setAttribute('aria-expanded', 'false'); b.textContent = 'Inspection history'; }
    else { b.insertAdjacentHTML('beforebegin', hist(c.dataset.lic)); b.setAttribute('aria-expanded', 'true'); b.textContent = 'Hide history'; }
  });
  document.getElementById('rsShow').addEventListener('click', ev => {
    const b = ev.target.closest('button'); if (!b) return;
    document.querySelectorAll('#rsShow button').forEach(x => x.setAttribute('aria-pressed', x === b)); show = b.dataset.v; N = 24; filter();
  });
  q.addEventListener('input', () => { N = 24; filter(); }); city.addEventListener('change', () => { N = 24; filter(); });
  more.addEventListener('click', () => { N += 48; filter(); });
  function openHash() {
    const want = location.hash.match(/^#r(\d+)$/); if (!want || !D) return;
    const r = D.r.find(x => x[0] === want[1]); if (!r) return;
    q.value = r[1]; city.value = ''; show = r[5] ? '' : 'gone'; N = 24;
    document.querySelectorAll('#rsShow button').forEach(x => x.setAttribute('aria-pressed', x.dataset.v === show));
    filter();
    const c = document.getElementById(want[0].slice(1));
    if (c) { c.querySelector('.rs-more')?.click(); c.scrollIntoView({block: 'center'}); }
  }
  addEventListener('hashchange', openHash);
  fetch('/data/restaurants-page.json').then(r => r.json()).then(j => { D = j; filter(); openHash(); })
    .catch(() => { cnt.textContent = 'The list could not load. Try again in a moment.'; });
})();
"""

NB_JS = r"""
(() => {
  const box = document.getElementById('nbList'); if (!box) return;
  const q = document.getElementById('nbQ'), city = document.getElementById('nbCity'), type = document.getElementById('nbType'), cnt = document.getElementById('nbCount'), more = document.getElementById('nbMore');
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const fmt = d => new Date(d + 'T12:00:00').toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'});
  let D = null, N = 25;
  function filter() {
    if (!D) return;
    const t = q.value.trim().toLowerCase(), c = city.value, ty = type.value;
    // [doc, name, type, filed, active, city, zip, profile_url, sunbiz_url, restaurants]
    const ok = D.b.filter(r => (!t || r[1].toLowerCase().includes(t)) && (!c || r[5] === c) && (!ty || r[2] === ty));
    box.innerHTML = ok.slice(0, N).map(r => `<tr><td><a href="${esc(r[7])}">${esc(r[1])}</a>${r[9] ? `<small>Restaurant: ${esc(r[9])}</small>` : ''}</td><td>${esc(r[2])}<small>${r[4] ? 'Active' : 'Inactive'}</small></td>
      <td>${esc(r[5] || '')} <span class="muted">${esc(r[6] || '')}</span></td><td class="n">${esc(fmt(r[3]))}</td><td><a class="src" href="${esc(r[8])}" target="_blank" rel="noopener">State record</a></td></tr>`).join('')
      || '<tr><td colspan="5" class="muted">No filings match.</td></tr>';
    cnt.textContent = `${ok.length.toLocaleString('en-US')} filing${ok.length === 1 ? '' : 's'} in the last 12 months` + (ok.length > N ? `, showing ${N}` : '');
    more.hidden = ok.length <= N;
  }
  [q, city, type].forEach(x => x.addEventListener(x === q ? 'input' : 'change', () => { N = 25; filter(); }));
  more.addEventListener('click', () => { N += 100; filter(); });
  fetch('/data/new-businesses-page.json').then(r => r.json()).then(j => { D = j; filter(); }).catch(() => { cnt.textContent = 'The list could not load. Try again in a moment.'; });
})();
"""


def _fmt(d):
    try:
        x = dt.date.fromisoformat(d)
        return x.strftime('%b %-d, %Y')
    except (TypeError, ValueError):
        return ''


def _plink(eid, text):
    return f'<a href="{e(page_url(eid))}">{e(text)}</a>' if eid else e(text)


def _kpi(lab, v, s):
    return f'<div class="kpi"><span class="eyebrow">{lab}</span><span class="v">{v}</span><span class="s">{s}</span></div>'


def _hbars(rows, total=None, fmt=lambda n: f'{n:,}'):
    top = max((n for _, n, _ in rows), default=1) or 1
    return '<div class="hbars small">' + ''.join(
        f'<div class="hb"><span class="hb-n">{lab}{f" <em>{e(note)}</em>" if note else ""}</span><span class="hb-track"><span class="hb-bar" style="width:{max(n / top * 100, .5):.1f}%"></span></span>'
        f'<span class="hb-v">{fmt(n)}{f" <em>{n / total * 100:.0f}%</em>" if total else ""}</span></div>' for lab, n, note in rows) + '</div>'


def restaurants_page(out_dir):
    from page_datasets import restaurants, restaurant_inspections, VIOLATION
    R, I = restaurants(), restaurant_inspections()
    if not R:
        return '<div class="page"><h1>Restaurant inspections</h1><p>No inspection records on file for this place yet.</p></div>'
    today = dt.date.today()
    year_ago = (today - dt.timedelta(days=365)).isoformat()
    by = {}
    for x in I:
        by.setdefault(x['license_number'], []).append(x)

    # the page's own data file: one compact row per license and its inspections (same rows as the datasets)
    lic_rows = []
    for r in R:
        lid = r.get('licensee_entity_id')
        lic_rows.append([r['license_number'], r['business_name'], r['kind'], r['city'], r['address'], r['licensed_now'], r['last_inspection'],
                         r['last_result_level'], r['last_result'], r['high_priority_last_year'], r['closures'], r['opened'], r['licensee'],
                         page_url(lid) if lid else None, r['inspections']])
    hist = {k: [[x['date'], x['inspection_type'].replace(' - Food', '').replace('Food-Licensing Inspection', 'Licensing inspection').replace('Complaint Full', 'Complaint').replace('Complaint Partial', 'Complaint (partial)'),
                 x['visit_number'], x['result'], x['result_level'], x['high_priority'], x['intermediate'], x['basic'], (x['violation_codes'] or '').replace(':', '').replace('; ', ' ')] for x in v]
            for k, v in by.items()}
    os.makedirs(os.path.join(out_dir, 'data'), exist_ok=True)
    json.dump({'r': lic_rows, 'i': hist, 'v': VIOLATION, 'updated': today.isoformat()}, open(os.path.join(out_dir, 'data', 'restaurants-page.json'), 'w'), ensure_ascii=False, separators=(',', ':'))

    now = [r for r in R if r['licensed_now']]
    recent = [x for x in I if x['date'] >= year_ago]
    closed = [x for x in I if x['disposition'] == 'Emergency order recommended']
    closed_year = [x for x in closed if x['date'] >= year_ago]
    routine_year = [x for x in recent if x['inspection_type'].startswith('Routine') and x['visit_number'] == 1]
    clean = sum(1 for x in routine_year if x['result_level'] == 'ok')
    opened = sorted((r for r in R if r.get('opened')), key=lambda r: r['opened'], reverse=True)
    opened_year = [r for r in opened if r['opened'] >= year_ago]
    latest = max((x['date'] for x in I), default='')

    # most cited violations in the last 12 months (routine and complaint visits, not follow-ups)
    vc = Counter()
    for x in recent:
        if x['visit_number'] == 1:
            for part in (x.get('violation_codes') or '').split('; '):
                if ':' in part:
                    vc[part.split(':')[0]] += 1
    first_visits = sum(1 for x in recent if x['visit_number'] == 1)
    vbars = _hbars([(e(VIOLATION.get(c, 'Item ' + c)), n, None) for c, n in vc.most_common(10)], first_visits)

    # closures: newest first, two years
    two = (today - dt.timedelta(days=730)).isoformat()
    lic_of = {r['license_number']: r for r in R}
    reopen = {}
    for x in I:
        if x['disposition'] == 'Emergency Order Callback Complied':
            reopen.setdefault(x['license_number'], []).append(x['date'])
    clo_rows = ''
    for x in sorted((x for x in closed if x['date'] >= two), key=lambda x: x['date'], reverse=True):
        r = lic_of.get(x['license_number'].lstrip('0')) or {}
        back = min((d for d in reopen.get(x['license_number'], []) if d >= x['date']), default=None)
        why = x.get('violation_items') or ''
        clo_rows += (f'<tr><td><a href="#r{e(x["license_number"].lstrip("0"))}">{e(x["business_name"])}</a><small>{e(r.get("city") or x["city"])}</small></td>'
                     f'<td class="n">{_fmt(x["date"])}</td><td>{("Reopened " + _fmt(back)) if back else "<span class=muted>No reopening visit on file yet</span>"}</td>'
                     f'<td class="wrap small">{x["high_priority"]} high priority · {e(why[:220] + ("…" if len(why) > 220 else ""))}</td></tr>')

    open_rows = ''.join(f'<tr><td><a href="#r{e(r["license_number"])}">{e(r["business_name"])}</a><small>{e(r["kind"])}</small></td><td>{e(r["city"] or "")}</td>'
                        f'<td>{_plink(r.get("licensee_entity_id"), r["licensee"]) if r.get("licensee") else ""}</td><td class="n">{_fmt(r["opened"])}</td></tr>' for r in opened[:25])
    cities = sorted({r['city'] for r in now if r.get('city')}, key=lambda c: (-sum(1 for r in now if r['city'] == c), c))
    city_opts = ''.join(f'<option value="{e(c)}">{e(c)}</option>' for c in cities)
    n_trucks = sum(1 for r in now if r['license_type'] == 'Food truck or cart')

    kpis = (_kpi('Licensed now', f'{len(now):,}', f'Restaurants, food trucks, caterers and more. {n_trucks} are food trucks or carts') +
            _kpi('Inspections, last 12 months', f'{len(recent):,}', f'{len(I):,} since 2016') +
            _kpi('Met standards', f'{clean / len(routine_year) * 100:.0f}%' if routine_year else '—', 'of routine inspections in the last 12 months, with no follow-up needed') +
            _kpi('Emergency closures', f'{len(closed_year):,}', f'in the last 12 months; {len(closed):,} since 2016'))

    return f'''<style>{CSS}</style>
<div class="page tax rs">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">People · Local businesses</span><h1>Restaurant inspections</h1>
    <p class="lede">Every restaurant, food truck and caterer in Bay County, and what state food safety inspectors found on every visit since 2016: warnings, fines recommended and emergency closures.</p></div>
    <div class="stamp"><a class="pill" href="/new-businesses">New businesses →</a><span>Latest inspection {_fmt(latest)}. From the Florida Department of Business and Professional Regulation</span></div></header>
  <div class="kpis">{kpis}</div>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">The simple version</span><h2>How restaurant inspections work</h2>
    <ol class="ex-steps"><li><b>The state inspects, not the county.</b> Inspectors from the Division of Hotels and Restaurants visit every licensed food business one or more times a year without notice, and again after a complaint.</li>
    <li><b>Violations come in three levels.</b> High priority violations are the ones most likely to make someone sick, like food held at the wrong temperature. Intermediate and basic violations are things like missing thermometers or dirty floors.</li>
    <li><b>Serious problems get a follow-up, a fine or a closure.</b> A warning means the inspector comes back to check. If it isn't fixed, the state can recommend a fine. Roaches, rodents, sewage or no hot water can close a place on the spot until it passes again.</li></ol></div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="search" data-tile="Look one up">Look up a restaurant</h2><span class="muted">Tap "Inspection history" for every visit</span></div>
    <div class="rs-ctl"><input type="search" id="rsQ" placeholder="Restaurant, owner or street" aria-label="Search restaurants by name, owner or street">
      <select id="rsCity" aria-label="City"><option value="">All cities</option>{city_opts}</select></div>
    <div class="chips" id="rsShow" role="group" aria-label="Show" style="margin-top:10px"><button type="button" class="chip" data-v="" aria-pressed="true">Licensed now</button><button type="button" class="chip" data-v="warn" aria-pressed="false">High-priority violations this year</button><button type="button" class="chip" data-v="closed" aria-pressed="false">Ever closed</button><button type="button" class="chip" data-v="new" aria-pressed="false">Opened this year</button><button type="button" class="chip" data-v="gone" aria-pressed="false">No longer licensed</button></div>
    <p class="rs-count" id="rsCount" aria-live="polite">Loading…</p>
    <div class="rs-list" id="rsList"></div>
    <div><button type="button" class="ui-btn" id="rsMore" hidden style="margin-top:12px">Show more</button></div></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="closures" data-tile="Closures">Emergency closures</h2><span class="muted">Last two years, newest first</span></div>
    <p>An emergency closure is not a penalty: the state closes a place until conditions that put people at risk are fixed, then lets it reopen after a passing visit.</p>
    <div class="tablewrap"><table class="tx-table rs-tbl"><thead><tr><th>Business</th><th class="n">Closed</th><th>Reopened</th><th>What the inspector found</th></tr></thead><tbody>{clo_rows or '<tr><td colspan="4" class="muted">None in the last two years.</td></tr>'}</tbody></table></div></section>

  <div class="rs-two">
  <section class="tx-sec"><div class="sec-hd"><h2 id="violations" data-tile="Common problems">Most common problems</h2><span class="muted">Share of inspections, last 12 months</span></div>
    {vbars}
    <p class="note">Counts each problem once per inspection (first visits, not follow-ups). Fire safety items are reported to fire officials and don't count against the restaurant.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="opened" data-tile="Just opened">Just opened</h2><span class="muted">{len(opened_year):,} in the last 12 months</span></div>
    <div class="tablewrap"><table class="tx-table rs-tbl"><thead><tr><th>Business</th><th>City</th><th>License holder</th><th class="n">Opened</th></tr></thead><tbody>{open_rows}</tbody></table></div>
    <p class="note">"Opened" is the date of a new license's first inspection. A new owner of an existing restaurant gets a new license, so a change of hands can show up here too.</p></section>
  </div>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>Inspections</b> come from the <a href="https://www2.myfloridalicense.com/hotels-restaurants/public-records/" rel="noopener" target="_blank">public inspection files</a> of the Florida Department of Business and Professional Regulation, Division of Hotels and Restaurants: every visit since January 2016. The current year's file is read every day.</li>
      <li><b>Licenses</b> come from the state's daily list of licensed food businesses. A business inspected since 2016 that isn't on today's list is shown as no longer licensed. Food trucks, caterers and event vendors show only their city, since their license address can be a home.</li>
      <li><b>Results in plain words:</b> the state's disposition codes are rewritten, for example "Call Back - Complied" becomes "Follow-up visit: fixed". The original code is in the data.</li>
      <li><b>License holders</b> link to a profile when the name matches a company local governments paid or exactly one state corporate filing. A franchise is usually licensed to its operator, not the brand.</li>
      <li><b>Inspection reports</b> with the inspector's notes are on the state's <a href="https://www.myfloridalicense.com/wl11.asp?mode=0&SID=&brd=H" rel="noopener" target="_blank">license search</a>.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/restaurants">restaurants</a> (<a href="/downloads/restaurants.csv">CSV</a>) · <a href="/api/v1/datasets/restaurant-inspections">restaurant-inspections</a> (<a href="/downloads/restaurant-inspections.csv">CSV</a>).</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>{RS_JS}</script>'''


def new_businesses_page(out_dir):
    from page_datasets import new_businesses, restaurants
    B, R = new_businesses(), restaurants()
    if not B:
        return '<div class="page"><h1>New businesses</h1><p>No state corporate filings on file for this place yet.</p></div>'
    latest = B[0]['filed_date']
    last = dt.date.fromisoformat(latest)
    start12 = (last - dt.timedelta(days=365)).isoformat()
    prev12 = (last - dt.timedelta(days=730)).isoformat()
    y12 = [b for b in B if b['filed_date'] > start12]
    p12 = [b for b in B if prev12 < b['filed_date'] <= start12]
    active = sum(1 for b in B if b['status'] == 'Active')

    os.makedirs(os.path.join(out_dir, 'data'), exist_ok=True)
    json.dump({'b': [[b['doc_number'], b['name'], b['filing_type'], b['filed_date'], b['status'] == 'Active', b['city'], b['zip'],
                      page_url(b['entity_id']), b['source_url'], b['restaurants']] for b in y12], 'through': latest},
              open(os.path.join(out_dir, 'data', 'new-businesses-page.json'), 'w'), ensure_ascii=False, separators=(',', ':'))

    # filings per year (the current year is partial) and per month for the last 36 months
    per_year = Counter(b['filed_date'][:4] for b in B)
    yrs = sorted(per_year)
    year_bars = _hbars([(y, per_year[y], f'through {last.strftime("%b %-d")}' if y == yrs[-1] else None) for y in yrs])
    months = []
    y, m = last.year, last.month
    for _ in range(36):
        months.append(f'{y}-{m:02d}')
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    months.reverse()
    per_month = Counter(b['filed_month'] for b in B)
    top = max(per_month[k] for k in months) or 1
    spark = ''.join(f'<span class="{"cur" if k == months[-1] else ""}" style="height:{per_month[k] / top * 100:.1f}%" title="{dt.date(int(k[:4]), int(k[5:]), 1).strftime("%B %Y")}: {per_month[k]:,} filings"></span>' for k in months)
    m0 = dt.date(int(months[0][:4]), int(months[0][5:]), 1).strftime('%b %Y')

    city12 = Counter(b['city'] or 'Not given' for b in y12)
    type12 = Counter(b['filing_type'] for b in y12)
    city_bars = _hbars([(e(c), n, None) for c, n in city12.most_common(8)], len(y12))
    type_bars = _hbars([(e(t), n, None) for t, n in type12.most_common()], len(y12))
    city_opts = ''.join(f'<option value="{e(c)}">{e(c)}</option>' for c, _ in city12.most_common() if c != 'Not given')
    type_opts = ''.join(f'<option value="{e(t)}">{e(t)}</option>' for t, _ in type12.most_common())

    today = dt.date.today()
    year_ago = (today - dt.timedelta(days=365)).isoformat()
    opened = sorted((r for r in R if r.get('opened')), key=lambda r: r['opened'], reverse=True)
    opened_year = [r for r in opened if r['opened'] >= year_ago]
    open_rows = ''.join(f'<tr><td><a href="/restaurants#r{e(r["license_number"])}">{e(r["business_name"])}</a><small>{e(r["kind"])}</small></td><td>{e(r["city"] or "")}</td>'
                        f'<td>{_plink(r.get("licensee_entity_id"), r["licensee"]) if r.get("licensee") else ""}</td><td class="n">{_fmt(r["opened"])}</td></tr>' for r in opened[:15])
    rest_per_year = Counter(r['opened'][:4] for r in opened)

    chg = (len(y12) - len(p12)) / len(p12) * 100 if p12 else 0
    kpis = (_kpi('Filed in the last 12 months', f'{len(y12):,}', f'{"Up" if chg >= 0 else "Down"} {abs(chg):.0f}% from the 12 months before') +
            _kpi(f'Filed in {last.year}', f'{per_year[str(last.year)]:,}', f'Through {last.strftime("%B %-d")}') +
            _kpi('Filed since 2016', f'{len(B):,}', f'{active / len(B) * 100:.0f}% are still active') +
            _kpi('New restaurants', f'{len(opened_year):,}', f'New food licenses in the last 12 months; {rest_per_year.get(str(today.year - 1), 0):,} in {today.year - 1}'))

    return f'''<style>{CSS}</style>
<div class="page tax rs nb">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">People · Local businesses</span><h1>New businesses</h1>
    <p class="lede">Every company, nonprofit and partnership filed with the state since 2016 with its main address in Bay County, and every new restaurant, food truck and caterer.</p></div>
    <div class="stamp"><a class="pill" href="/restaurants">Restaurant inspections →</a><span>State corporate filings through {_fmt(latest)}</span></div></header>
  <div class="kpis">{kpis}</div>

  <section class="tx-sec"><div class="sec-hd"><h2 id="trend" data-tile="By month">New filings by month</h2><span class="muted">Last 36 months</span></div>
    <div class="nb-month" role="img" aria-label="Bar chart of new business filings per month for the last 36 months, from {m0} to {last.strftime('%B %Y')}">{spark}</div>
    <div class="nb-axis"><span>{m0}</span><span>{last.strftime('%b %Y')}</span></div>
    <p class="note">The last month is partial: the state's quarterly file runs through {_fmt(latest)}.</p></section>

  <div class="rs-two">
  <section class="tx-sec"><div class="sec-hd"><h2 id="years" data-tile="By year">By year</h2><span class="muted">Filings with a Bay County main address</span></div>
    {year_bars}</section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="where" data-tile="Where">Where, and what kind</h2><span class="muted">Last 12 months</span></div>
    {city_bars}<div style="height:14px"></div>{type_bars}
    <p class="note">The city is the mailing city on the filing, so places like Southport and unincorporated areas show as Panama City.</p></section>
  </div>

  <section class="tx-sec"><div class="sec-hd"><h2 id="list" data-tile="The list">Every filing in the last 12 months</h2><span class="muted">Newest first</span></div>
    <div class="rs-ctl"><input type="search" id="nbQ" placeholder="Business name" aria-label="Search new businesses by name">
      <select id="nbCity" aria-label="City"><option value="">All cities</option>{city_opts}</select>
      <select id="nbType" aria-label="Type"><option value="">All types</option>{type_opts}</select></div>
    <p class="rs-count" id="nbCount" aria-live="polite">Loading…</p>
    <div class="tablewrap"><table class="tx-table rs-tbl" data-tt="off"><thead><tr><th>Business</th><th>Type</th><th>City</th><th class="n">Filed</th><th>Record</th></tr></thead><tbody id="nbList"></tbody></table></div>
    <div><button type="button" class="ui-btn" id="nbMore" hidden style="margin-top:12px">Show more</button></div>
    <p class="note">Every name opens the business's profile. The state record names its officers and registered agent. Older filings back to 2016 are in the <a href="/api/v1/datasets/new-businesses">new-businesses</a> data.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="restaurants" data-tile="New restaurants">New restaurants</h2><span class="muted">{len(opened_year):,} new food licenses in the last 12 months</span></div>
    <div class="tablewrap"><table class="tx-table rs-tbl"><thead><tr><th>Business</th><th>City</th><th>License holder</th><th class="n">Opened</th></tr></thead><tbody>{open_rows}</tbody></table></div>
    <p class="note">Each one's first inspection, and every one since, is on the <a href="/restaurants">Restaurant inspections</a> page.</p></section>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>New businesses</b> come from the Florida Division of Corporations (Sunbiz) <a href="https://dos.fl.gov/sunbiz/other-services/data-downloads/" rel="noopener" target="_blank">quarterly data file</a>: every LLC, corporation, nonprofit and partnership filed since January 2016 whose main (principal) address is in a Bay County ZIP code. Out-of-state companies count from the day they registered to do business in Florida.</li>
      <li><b>A filing is not an opening.</b> Many new companies are holding companies, rental properties or side businesses with no storefront, and some never start. "Inactive" usually means the company didn't file its annual report and the state dissolved it.</li>
      <li><b>Only the city and ZIP are shown</b>, because many small companies list a home as their address. Officers and registered agents are on each company's state record.</li>
      <li><b>New restaurants</b> come from state food licenses: the date of each new license's first inspection.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/new-businesses">new-businesses</a> (<a href="/downloads/new-businesses.csv">CSV</a>) · <a href="/api/v1/datasets/restaurants">restaurants</a> (<a href="/downloads/restaurants.csv">CSV</a>).</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>{NB_JS}</script>'''
