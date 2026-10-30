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
.rs-find input[type=search]{min-height:54px;font-size:1rem;border:2px solid var(--blue);padding:0 16px 0 44px;background:var(--surface) no-repeat 14px 50%/20px url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%233F6FB0' stroke-width='2.2' stroke-linecap='round'%3E%3Ccircle cx='11' cy='11' r='7'/%3E%3Cpath d='m20 20-3.5-3.5'/%3E%3C/svg%3E")}
.rs-find select{min-height:54px}
.rs-week{margin:0;font-size:.9rem;color:var(--muted)}
.rs-week b{color:var(--ink);font-variant-numeric:tabular-nums}
.rs-count{font-size:.86rem;color:var(--muted);margin:0}
.rs-rows{list-style:none;margin:0;padding:0;background:var(--surface);border:1px solid var(--line);border-radius:var(--r);overflow:hidden}
.rs-rows li{border-top:1px solid var(--line)}
.rs-rows li:first-child{border-top:0}
.rs-rows a.rs-r{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 16px;align-items:center;padding:12px 16px;color:inherit;text-decoration:none;min-height:56px}
.rs-rows a.rs-r:hover{background:var(--sunken)}
.rs-r b{font-weight:600;font-size:.95rem;overflow-wrap:anywhere}
.rs-r small{display:block;color:var(--muted);font-size:.8rem;overflow-wrap:anywhere}
.rs-r .rs-side{display:flex;flex-direction:column;align-items:flex-end;gap:5px;text-align:right}
.rs-res{display:inline-block;padding:2px 10px;border-radius:999px;font-weight:600;font-size:.76rem;background:var(--sunken);white-space:nowrap}
.rs-res.ok{background:var(--tint-teal);color:var(--teal)}
.rs-res.warn{background:var(--tint-amber);color:var(--ink);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--amber) 60%,transparent)}
.rs-res.bad{background:var(--tint-salmon);color:var(--accent-ink)}
.rs-dots{display:inline-flex;gap:3px;align-items:center}
.rs-dots i{width:10px;height:10px;border-radius:3px;background:var(--teal)}
.rs-dots i.warn{background:var(--amber)}.rs-dots i.bad{background:var(--salmon)}.rs-dots i.none{background:var(--line)}
.rs-date{font:500 .74rem var(--f-data);color:var(--muted);white-space:nowrap}
.rs-tabs{display:flex;flex-wrap:wrap;gap:6px}
.rs-pane[hidden]{display:none}
.rs-tbl td,.rs-tbl th{vertical-align:top}
.rs-tbl td.n,.rs-tbl th.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.rs-tbl small{display:block;color:var(--muted);font-size:.78rem}
.rs-two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.rs-say{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-lg);padding:16px 18px;font-size:1rem;line-height:1.6;margin:0}
.rs-tl{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--line);border-radius:var(--r);overflow:hidden}
.rs-tl li{display:grid;grid-template-columns:118px minmax(0,1fr);gap:4px 14px;padding:12px 16px;border-top:1px solid var(--line);font-size:.88rem}
.rs-tl li:first-child{border-top:0}
.rs-tl .d{font:500 .78rem var(--f-data);color:var(--muted);padding-top:3px}
.rs-tl .what{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center}
.rs-tl small{display:block;color:var(--muted);font-size:.8rem;margin-top:3px}
.rs-tl li.bad{background:var(--tint-salmon)}
.rs-one .stamp .rs-res{align-self:center;font-size:.92rem;padding:4px 16px}
.nb-month{display:flex;align-items:flex-end;gap:2px;height:120px;margin:8px 0 4px}
.nb-month span{flex:1;background:var(--blue);border-radius:3px 3px 0 0;min-height:2px;opacity:.85}
.nb-month span.cur{background:var(--salmon)}
.nb-axis{display:flex;justify-content:space-between;font-size:.76rem;color:var(--muted)}
@media (max-width:760px){.rs-st{display:none}.rs-two{grid-template-columns:1fr}.rs-find select{flex:1 1 100%}.rs-tl li{grid-template-columns:1fr;gap:2px}.rs-rows a.rs-r{padding:11px 14px}}
"""

# result words short enough for a list row (the full wording is on each restaurant's page)
SHORT = {'Met inspection standards': 'Met standards', 'Warning, follow-up visit set': 'Warning', 'Follow-up visit: fixed': 'Fixed on follow-up',
         'Follow-up visit: more time given': 'More time given', 'Fine recommended (administrative complaint)': 'Fine recommended',
         'Follow-up visit: not fixed, fine recommended': 'Fine recommended', 'Follow-up after complaint: fixed': 'Fixed',
         'Follow-up after complaint: not fixed': 'Not fixed', 'Follow-up after complaint: more time given': 'More time given',
         'Referred for an administrative decision': 'Referred', 'Ordered closed (emergency order)': 'Closed by the state',
         'Allowed to reopen': 'Reopened', 'Stayed closed: not fixed': 'Still closed', 'Stayed closed: more time given': 'Still closed'}
LEVEL_WORD = {'ok': 'met standards', 'warning': 'warning', 'fine': 'fine recommended', 'closed': 'closed'}

RS_JS = r"""
(() => {
  const box = document.getElementById('rsList'); if (!box) return;
  const q = document.getElementById('rsQ'), city = document.getElementById('rsCity'), cnt = document.getElementById('rsCount'), more = document.getElementById('rsMore');
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const CLS = {ok: 'ok', warning: 'warn', fine: 'bad', closed: 'bad'}, WORD = {ok: 'met standards', warning: 'warning', fine: 'fine recommended', closed: 'closed'};
  const fmt = d => d ? new Date(d + 'T12:00:00').toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'}) : '';
  let D = null, show = '', N = 30;
  function dots(s) {
    const lv = (s || '').split(' ').filter(Boolean).reverse();  // oldest on the left, latest on the right
    while (lv.length < 6) lv.unshift('');
    return `<span class="rs-dots" role="img" aria-label="Last ${lv.filter(Boolean).length} inspections, oldest to newest: ${esc(lv.filter(Boolean).map(l => WORD[l]).join(', '))}">` +
      lv.map(l => `<i class="${l ? CLS[l] || '' : 'none'}"></i>`).join('') + '</span>';
  }
  function row(r) {
    // [license, name, kind, city, street, licensed_now, last_date, last_level, last_short, opened, last_closure, recent, url, licensee]
    const [lic, name, kind, cty, street, now, last, lvl, res, opened, clo, recent, url] = r;
    return `<li><a class="rs-r" href="${esc(url)}"><span><b>${esc(name)}</b><small>${esc(kind)}${street ? `<span class="rs-st"> · ${esc(street)}</span>` : ''}${cty ? ' · ' + esc(cty) : ''}${now ? '' : ' · No longer licensed'}</small></span>
      <span class="rs-side">${res ? `<span class="rs-res ${CLS[lvl] || ''}">${esc(res)}</span>` : '<span class="rs-res">Not inspected yet</span>'}
      <span class="rs-date">${esc(fmt(last))}</span>${recent ? dots(recent) : ''}</span></a></li>`;
  }
  function filter() {
    if (!D) return;
    const t = q.value.trim().toLowerCase(), c = city.value, yr = D.year_ago;
    const fit = r => (!t || (r[1] + ' ' + (r[13] || '') + ' ' + (r[4] || '')).toLowerCase().includes(t)) &&
      (show === 'follow' ? r[5] && (r[7] === 'warning' || r[7] === 'fine' || r[7] === 'closed') : show === 'closed' ? (r[10] || '') >= yr :
       show === 'new' ? r[5] && (r[9] || '') >= yr : show === 'gone' ? !r[5] : (t ? true : r[5]));
    let ok = D.r.filter(r => (!c || r[3] === c) && fit(r)), note = '';
    // a city with nothing that matches says so, then shows the rest of the county
    if (c && !ok.length && D.r.some(fit)) { ok = D.r.filter(fit); note = `<li><span class="rs-r"><span><b>None in ${esc(c)}.</b> <span class="muted">Here's the rest of Bay County:</span></span></span></li>`; }
    box.innerHTML = note + ok.slice(0, N).map(row).join('') || '<li><span class="rs-r"><span class="muted">Nothing matches. Try another name or street.</span></span></li>';
    cnt.textContent = `${ok.length.toLocaleString('en-US')} place${ok.length === 1 ? '' : 's'}, latest inspected first` + (ok.length > N ? `. Showing ${N}` : '');
    more.hidden = ok.length <= N;
  }
  document.getElementById('rsShow').addEventListener('click', ev => {
    const b = ev.target.closest('button'); if (!b) return;
    document.querySelectorAll('#rsShow button').forEach(x => x.setAttribute('aria-pressed', x === b)); show = b.dataset.v; N = 30; filter();
  });
  q.addEventListener('input', () => { N = 30; filter(); }); city.addEventListener('change', () => { N = 30; filter(); });
  more.addEventListener('click', () => { N += 60; filter(); });
  document.querySelectorAll('.rs-tabs').forEach(g => g.addEventListener('click', ev => {
    const b = ev.target.closest('button'); if (!b) return;
    g.querySelectorAll('button').forEach(x => { const on = x === b; x.setAttribute('aria-pressed', on); document.getElementById(x.dataset.pane).hidden = !on; });
  }));
  fetch('/data/restaurants-page.json').then(r => r.json()).then(j => {
    D = j;
    // no city picked yet: a signed-in reader starts on their home's city
    const h = window.BCHomeCity && window.BCHomeCity();
    if (h && h.town && !city.value && [...city.options].some(o => o.value === h.town)) city.value = h.town;

    const old = location.hash.match(/^#r(\d+)$/);  // old links to one restaurant on this page now go to its own page
    const hit = old && D.r.find(x => x[0] === old[1]);
    if (hit) { location.replace(hit[12]); return; }
    filter();
  }).catch(() => { cnt.textContent = 'The list could not load. Try again in a moment.'; });
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
    const fit = r => (!t || r[1].toLowerCase().includes(t)) && (!ty || r[2] === ty);
    let ok = D.b.filter(r => (!c || r[5] === c) && fit(r)), note = '';
    if (c && !ok.length && D.b.some(fit)) { ok = D.b.filter(fit); note = `<tr><td colspan="5"><b>None in ${esc(c)}.</b> <span class="muted">Here's the rest of Bay County:</span></td></tr>`; }
    box.innerHTML = note + ok.slice(0, N).map(r => `<tr><td><a href="${esc(r[7])}">${esc(r[1])}</a>${r[9] ? `<small>Restaurant: ${esc(r[9])}</small>` : ''}</td><td>${esc(r[2])}<small>${r[4] ? 'Active' : 'Inactive'}</small></td>
      <td>${esc(r[5] || '')} <span class="muted">${esc(r[6] || '')}</span></td><td class="n">${esc(fmt(r[3]))}</td><td><a class="src" href="${esc(r[8])}" target="_blank" rel="noopener">State record</a></td></tr>`).join('')
      || '<tr><td colspan="5" class="muted">No filings match.</td></tr>';
    cnt.textContent = `${ok.length.toLocaleString('en-US')} filing${ok.length === 1 ? '' : 's'} in the last 12 months` + (ok.length > N ? `, showing ${N}` : '');
    more.hidden = ok.length <= N;
  }
  [q, city, type].forEach(x => x.addEventListener(x === q ? 'input' : 'change', () => { N = 25; filter(); }));
  more.addEventListener('click', () => { N += 100; filter(); });
  fetch('/data/new-businesses-page.json').then(r => r.json()).then(j => { D = j;
    // no city picked yet: a signed-in reader starts on their home's city
    const h = window.BCHomeCity && window.BCHomeCity();
    if (h && h.town && !city.value && [...city.options].some(o => o.value === h.town)) city.value = h.town;
    filter(); }).catch(() => { cnt.textContent = 'The list could not load. Try again in a moment.'; });
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


def _dots(recent):
    lv = list(reversed((recent or '').split()))  # oldest on the left, latest on the right
    words = ', '.join(LEVEL_WORD.get(x, x) for x in lv)
    lv = [''] * (6 - len(lv)) + lv
    return (f'<span class="rs-dots" role="img" aria-label="Last {len(words.split(", ")) if words else 0} inspections, oldest to newest: {e(words)}">'
            + ''.join(f'<i class="{LEVEL_CLS.get(x, "") if x else "none"}"></i>' for x in lv) + '</span>')


def _pill(result, level):
    return f'<span class="rs-res {LEVEL_CLS.get(level, "")}">{e(result)}</span>' if result else '<span class="rs-res">Not inspected yet</span>'


def _hist_type(x):
    t = x['inspection_type'].replace(' - Food', '').replace('Food-Licensing Inspection', 'Licensing inspection').replace('Complaint Full', 'Complaint').replace('Complaint Partial', 'Complaint (partial)')
    return 'Follow-up visit' if x['visit_number'] > 1 else t


def _plural(n, word):
    return f'{n:,} {word}{"" if n == 1 else "s"}'


def _times(n):
    return 'once' if n == 1 else 'twice' if n == 2 else f'{n} times'


def _by_license():
    from page_datasets import restaurants, restaurant_inspections
    R, I = restaurants(), restaurant_inspections()
    by = {}
    for x in I:  # newest first
        by.setdefault(x['license_number'].lstrip('0'), []).append(x)
    return R, I, by


def summary(r, hist, today=None):
    """One plain paragraph about a restaurant's record, for the top of its page (and the app's detail screen)."""
    today = today or dt.date.today()
    year_ago = (today - dt.timedelta(days=365)).isoformat()
    if not hist:
        return f'{r["business_name"]} has no inspections on file since 2016 yet. New licenses are inspected soon after they open.'
    last = hist[0]
    first = next((x for x in hist if x['visit_number'] == 1), last)
    out = [f'Last inspected <b>{_fmt(last["date"])}</b>: {e(last["result"].lower() if last["result"][0].isupper() and last["result"][1:2].islower() else last["result"])}.']
    if last is not first and first['result_level'] != 'ok':
        out.append(f'That was a follow-up to a {_hist_type(first).lower()} on {_fmt(first["date"])} that found {_plural(first["high_priority"], "high-priority violation")}.')
    elif last['visit_number'] == 1 and last['total_violations']:
        out.append(f'The inspector found {_plural(last["high_priority"], "high-priority violation")}, {last["intermediate"]} intermediate and {last["basic"]} basic.')
    clo = [x for x in hist if x['result_level'] == 'closed' and x['disposition'] == 'Emergency order recommended']
    clo_year = [x for x in clo if x['date'] >= year_ago]
    if clo_year:
        out.append(f'The state closed it {_times(len(clo_year))} in the last 12 months (most recently {_fmt(clo_year[0]["date"])}).')
    elif clo:
        out.append(f'It was last closed by the state on {_fmt(clo[0]["date"])}.')
    else:
        out.append('It has never been closed by the state since 2016.')
    out.append(f'{_plural(len(hist), "inspection")} since {hist[-1]["date"][:4]}.')
    return ' '.join(out)


def _share_text(r, hist, where, today):
    """What Share / Copy puts on the clipboard for this restaurant (site/share.js): name, where, the plain summary."""
    import html as _h, re as _re
    say = _h.unescape(_re.sub(r'<[^>]+>', '', summary(r, hist, today)))
    return f'<div hidden data-share-text="{e(r["business_name"] + chr(10) + where + chr(10) + say)}"></div>'


def about(path, _c={}):
    """What a restaurant's page is about, for search engines (build_site.page_about)."""
    if 'm' not in _c:
        from page_datasets import restaurants
        _c['m'] = {r['page_url']: r for r in restaurants() if r.get('page_url')}
    r = _c['m'].get(path)
    if not r:
        return None
    out = {'@type': 'FoodEstablishment', 'name': r['business_name']}
    if r.get('city'):
        out['address'] = {'@type': 'PostalAddress', **({'streetAddress': r['address']} if r.get('address') else {}), 'addressLocality': r['city'], 'addressRegion': 'FL',
                          **({'postalCode': r['zip']} if r.get('zip') and r.get('address') else {})}
    return out


def restaurant_pages():
    """One page per license: /restaurants/<name>-<license> (page_url in the restaurants dataset)."""
    R, I, by = _by_license()
    from collections import Counter
    same = Counter(r['business_name'] for r in R if r.get('page_url'))
    def name(r):  # chains share a name: add the street (or town) so each page has its own title
        if same[r['business_name']] < 2: return r['business_name']
        at = r.get('address') or r.get('city')
        return f'{r["business_name"]}, {at}' if at else r['business_name']
    return [(r['page_url'], f'{name(r)}: restaurant inspections',
             f'{r["business_name"]}{", " + r["city"] if r.get("city") else ""}: every Florida food safety inspection since 2016, the latest result, violations, warnings and emergency closures.',
             (lambda r=r: restaurant_page(r, by.get(r['license_number'], []))))
            for r in R if r.get('page_url')]


def restaurant_page(r, hist):
    from page_datasets import VIOLATION
    today = dt.date.today()
    year_ago = (today - dt.timedelta(days=365)).isoformat()
    lid = r.get('licensee_entity_id')
    where = ' · '.join(x for x in [r['kind'], r.get('address'), r.get('city')] if x)
    holder = f'<p class="lede" style="font-size:.95rem">License holder: {_plink(lid, r["licensee"])}</p>' if r.get('licensee') else ''
    recent = [x for x in hist if x['date'] >= year_ago]
    clo = [x for x in hist if x['disposition'] == 'Emergency order recommended']

    def items(codes):
        return '; '.join(VIOLATION.get(c.split(':')[0], 'Item ' + c.split(':')[0]) + (f' ({c.split(":")[1]})' if c.split(':')[1] != '1' else '')
                         for c in (codes or '').split('; ') if ':' in c)
    tl = ''.join(
        f'<li class="{"bad" if x["result_level"] == "closed" and x["disposition"] == "Emergency order recommended" else ""}"><span class="d">{_fmt(x["date"])}</span>'
        f'<div><div class="what">{_pill(x["result"], x["result_level"])}<span>{e(_hist_type(x))}</span></div>'
        + (f'<small>{x["high_priority"]} high priority, {x["intermediate"]} intermediate, {x["basic"]} basic'
           + (f': {e(items(x["violation_codes"]))}' if x['violation_codes'] else '') + '</small>' if x['total_violations'] else '<small>No violations</small>')
        + '</div></li>' for x in hist)
    kpis = (_kpi('Latest result', e(SHORT.get(r['last_result'], r['last_result'] or 'None yet')), _fmt(r['last_inspection']) or 'Not inspected yet') +
            _kpi('Inspections', f'{len(hist):,}', f'{len(recent)} in the last 12 months') +
            _kpi('High-priority violations', f'{sum(x["high_priority"] for x in recent):,}', 'cited in the last 12 months') +
            _kpi('Emergency closures', f'{len(clo):,}', f'since 2016{"; last " + _fmt(clo[0]["date"]) if clo else ""}'))
    gone = '' if r['licensed_now'] else '<p class="note"><b>No longer licensed.</b> This license is not on the state\'s current list, so the business has closed, moved or changed owners.</p>'
    return f'''<style>{CSS}</style>
<div class="page tax rs rs-one">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow"><a href="/restaurants">Restaurant inspections</a></span><h1>{e(r["business_name"])}</h1>
    <p class="lede">{e(where)}</p>{holder}</div>
    <div class="stamp">{_pill(SHORT.get(r['last_result'], r['last_result']), r['last_result_level'])}<span>{"Last inspected " + _fmt(r['last_inspection']) if r.get('last_inspection') else 'No inspections yet'}. State license {e(r['license_number'])}</span></div></header>
  <p class="rs-say">{summary(r, hist, today)}</p>{_share_text(r, hist, where, today)}
  {gone}
  <div class="kpis">{kpis}</div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="history">Every inspection since 2016</h2><span class="muted">Newest first</span></div>
    {f'<ul class="rs-tl" data-share-items>{tl}</ul>' if tl else '<p>No inspections on file yet.</p>'}
    <p class="note">High-priority violations are the ones most likely to make someone sick. A warning means the inspector comes back to check. Fire safety items are reported to fire officials. The inspector's full notes are on the state's <a href="https://www.myfloridalicense.com/wl11.asp?mode=0&SID=&brd=H" rel="noopener" target="_blank">license search</a> (search license {e(r['license_number'])}).</p></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li>The Florida Department of Business and Professional Regulation, Division of Hotels and Restaurants: its <a href="https://www2.myfloridalicense.com/hotels-restaurants/public-records/" rel="noopener" target="_blank">public inspection files</a> and daily license list. Results are in plain words; the state's original codes are in the data.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/restaurants?license_number={e(r['license_number'])}">this license</a> · <a href="/api/v1/datasets/restaurant-inspections?license_number={e(r['license_number'])}&sort=-date">its inspections</a> · <a href="/restaurants">every restaurant</a></li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">'''


def restaurants_page(out_dir):
    R, I, by = _by_license()
    if not R:
        return '<div class="page"><h1>Restaurant inspections</h1><p>No inspection records on file for this place yet.</p></div>'
    from page_datasets import VIOLATION
    today = dt.date.today()
    year_ago = (today - dt.timedelta(days=365)).isoformat()
    lic_of = {r['license_number']: r for r in R}

    # the page's own data file: one compact row per license, latest inspected first (same rows as the restaurants dataset)
    order = sorted(R, key=lambda r: (r.get('last_inspection') or '', r['business_name']), reverse=True)
    rows = [[r['license_number'], r['business_name'], r['kind'], r['city'], r['address'], r['licensed_now'], r['last_inspection'], r['last_result_level'],
             SHORT.get(r['last_result'], r['last_result']), r['opened'], r['last_closure'], r['recent_results'], r['page_url'], r['licensee']] for r in order]
    os.makedirs(os.path.join(out_dir, 'data'), exist_ok=True)
    json.dump({'r': rows, 'year_ago': year_ago, 'updated': today.isoformat()}, open(os.path.join(out_dir, 'data', 'restaurants-page.json'), 'w'),
              ensure_ascii=False, separators=(',', ':'))

    now = [r for r in R if r['licensed_now']]
    latest = max((x['date'] for x in I), default='')
    wk0 = (dt.date.fromisoformat(latest) - dt.timedelta(days=6)).isoformat() if latest else ''
    week = [x for x in I if x['date'] >= wk0]
    wk_follow = sum(1 for x in week if x['result_level'] in ('warning', 'fine'))
    wk_closed = sum(1 for x in week if x['disposition'] == 'Emergency order recommended')
    recent = [x for x in I if x['date'] >= year_ago]
    closed = [x for x in I if x['disposition'] == 'Emergency order recommended']
    closed_year = [x for x in closed if x['date'] >= year_ago]
    opened = sorted((r for r in R if r.get('opened')), key=lambda r: r['opened'], reverse=True)
    opened_year = [r for r in opened if r['opened'] >= year_ago]

    # first page of the list, so it reads before the script runs (and for search engines)
    first_rows = ''.join(
        f'<li><a class="rs-r" href="{e(r["page_url"])}"><span><b>{e(r["business_name"])}</b><small>{e(r["kind"])}{f'<span class="rs-st"> · {e(r["address"])}</span>' if r.get("address") else ""}{" · " + e(r["city"]) if r.get("city") else ""}</small></span>'
        f'<span class="rs-side">{_pill(SHORT.get(r["last_result"], r["last_result"]), r["last_result_level"])}<span class="rs-date">{_fmt(r["last_inspection"])}</span>{_dots(r["recent_results"]) if r.get("recent_results") else ""}</span></a></li>'
        for r in [r for r in order if r['licensed_now']][:30])

    # most cited violations in the last 12 months (first visits, not follow-ups)
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
    reopen = {}
    for x in I:
        if x['disposition'] == 'Emergency Order Callback Complied':
            reopen.setdefault(x['license_number'], []).append(x['date'])
    clo_rows = ''
    for x in [x for x in closed if x['date'] >= two]:
        r = lic_of.get(x['license_number'].lstrip('0')) or {}
        back = min((d for d in reopen.get(x['license_number'], []) if d >= x['date']), default=None)
        why = x.get('violation_items') or ''
        name = f'<a href="{e(r["page_url"])}">{e(x["business_name"])}</a>' if r.get('page_url') else e(x['business_name'])
        clo_rows += (f'<tr><td>{name}<small>{e(r.get("city") or x["city"])}</small></td>'
                     f'<td class="n">{_fmt(x["date"])}</td><td>{("Reopened " + _fmt(back)) if back else "<span class=muted>No reopening visit on file yet</span>"}</td>'
                     f'<td class="wrap small">{x["high_priority"]} high priority · {e(why[:220] + ("…" if len(why) > 220 else ""))}</td></tr>')
    open_rows = ''.join(f'<tr><td><a href="{e(r["page_url"])}">{e(r["business_name"])}</a><small>{e(r["kind"])}</small></td><td>{e(r["city"] or "")}</td>'
                        f'<td>{_plink(r.get("licensee_entity_id"), r["licensee"]) if r.get("licensee") else ""}</td><td class="n">{_fmt(r["opened"])}</td></tr>' for r in opened[:25])
    cities = sorted({r['city'] for r in now if r.get('city')}, key=lambda c: (-sum(1 for r in now if r['city'] == c), c))
    city_opts = ''.join(f'<option value="{e(c)}">{e(c)}</option>' for c in cities)
    routine_year = [x for x in recent if x['inspection_type'].startswith('Routine') and x['visit_number'] == 1]
    clean = sum(1 for x in routine_year if x['result_level'] == 'ok')

    return f'''<style>{CSS}</style>
<div class="page tax rs">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Living here · Local businesses</span><h1>Restaurant inspections</h1>
    <p class="lede">Look up any restaurant, food truck or caterer in Bay County and see what state food safety inspectors found on every visit since 2016.</p></div>
    <div class="stamp"><a class="pill" href="/new-businesses">New businesses →</a><span>Latest inspection {_fmt(latest)}. From the Florida Department of Business and Professional Regulation</span></div></header>

  <section class="tx-sec"><div class="sec-hd"><h2 id="search">Look up a restaurant</h2></div>
    <div class="rs-ctl rs-find"><input type="search" id="rsQ" placeholder="Restaurant, owner or street" aria-label="Search restaurants by name, owner or street" autocomplete="off">
      <select id="rsCity" aria-label="City"><option value="">All cities</option>{city_opts}</select></div>
    <div class="chips" id="rsShow" role="group" aria-label="Show"><button type="button" class="chip" data-v="" aria-pressed="true">Latest inspected</button><button type="button" class="chip" data-v="follow" aria-pressed="false">Needs a follow-up</button><button type="button" class="chip" data-v="closed" aria-pressed="false">Closed this year</button><button type="button" class="chip" data-v="new" aria-pressed="false">New this year</button><button type="button" class="chip" data-v="gone" aria-pressed="false">No longer licensed</button></div>
    <p class="rs-week">Week of {_fmt(wk0)}: <b>{len(week)}</b> inspections, <b>{wk_follow}</b> needing a follow-up, <b>{wk_closed}</b> {"closure" if wk_closed == 1 else "closures"}. In the last 12 months, {clean / len(routine_year) * 100 if routine_year else 0:.0f}% of routine inspections met standards and the state closed {_plural(len(closed_year), "place")}.</p>
    <p class="rs-count" id="rsCount" aria-live="polite">{len(now):,} places, latest inspected first. Showing 30</p>
    <ul class="rs-rows" id="rsList">{first_rows}</ul>
    <p class="note">The squares are the last six inspections, oldest to newest: <span class="rs-dots" aria-hidden="true"><i></i></span> met standards or fixed, <span class="rs-dots" aria-hidden="true"><i class="warn"></i></span> warning, <span class="rs-dots" aria-hidden="true"><i class="bad"></i></span> closed or fine recommended.</p>
    <div><button type="button" class="ui-btn" id="rsMore">Show more</button></div></section>

  <section class="tx-sec"><div class="sec-hd"><h2>More about local restaurants</h2></div>
    <div class="chips rs-tabs" role="group" aria-label="Pick a list"><button type="button" class="chip" data-pane="rsClo" aria-pressed="true">Closures</button><button type="button" class="chip" data-pane="rsProb" aria-pressed="false">Common problems</button><button type="button" class="chip" data-pane="rsNew" aria-pressed="false">Just opened</button><button type="button" class="chip" data-pane="rsHow" aria-pressed="false">How inspections work</button></div>
    <div class="rs-pane" id="rsClo"><p>An emergency closure is not a penalty: the state closes a place until conditions that put people at risk are fixed, then lets it reopen after a passing visit. Last two years, newest first.</p>
      <div class="tablewrap"><table class="tx-table rs-tbl"><thead><tr><th>Business</th><th class="n">Closed</th><th>Reopened</th><th>What the inspector found</th></tr></thead><tbody>{clo_rows or '<tr><td colspan="4" class="muted">None in the last two years.</td></tr>'}</tbody></table></div></div>
    <div class="rs-pane" id="rsProb" hidden><p class="muted">Share of inspections that cited each problem, last 12 months (first visits, not follow-ups).</p>{vbars}
      <p class="note">Fire safety items are reported to fire officials and don't count against the restaurant.</p></div>
    <div class="rs-pane" id="rsNew" hidden><p class="muted">{len(opened_year):,} new food licenses in the last 12 months.</p>
      <div class="tablewrap"><table class="tx-table rs-tbl"><thead><tr><th>Business</th><th>City</th><th>License holder</th><th class="n">Opened</th></tr></thead><tbody>{open_rows}</tbody></table></div>
      <p class="note">"Opened" is the date of a new license's first inspection. A new owner of an existing restaurant gets a new license, so a change of hands can show up here too.</p></div>
    <div class="rs-pane" id="rsHow" hidden><ol class="ex-steps"><li><b>The state inspects, not the county.</b> Inspectors from the Division of Hotels and Restaurants visit every licensed food business one or more times a year without notice, and again after a complaint.</li>
      <li><b>Violations come in three levels.</b> High priority violations are the ones most likely to make someone sick, like food held at the wrong temperature. Intermediate and basic violations are things like missing thermometers or dirty floors.</li>
      <li><b>Serious problems get a follow-up, a fine or a closure.</b> A warning means the inspector comes back to check. If it isn't fixed, the state can recommend a fine. Roaches, rodents, sewage or no hot water can close a place on the spot until it passes again.</li></ol></div></section>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>Inspections</b> come from the <a href="https://www2.myfloridalicense.com/hotels-restaurants/public-records/" rel="noopener" target="_blank">public inspection files</a> of the Florida Department of Business and Professional Regulation, Division of Hotels and Restaurants: every visit since January 2016. The current year's file is read every day.</li>
      <li><b>Licenses</b> come from the state's daily list of licensed food businesses. A business inspected since 2016 that isn't on today's list is shown as no longer licensed. Food trucks, caterers and event vendors show only their city, since their license address can be a home.</li>
      <li><b>Results in plain words:</b> the state's disposition codes are rewritten, for example "Call Back - Complied" becomes "Follow-up visit: fixed". The original code is in the data.</li>
      <li><b>License holders</b> link to a profile when the name matches a company local governments paid or exactly one state corporate filing. A person is named only when they run a registered business at the license address. A franchise is usually licensed to its operator, not the brand.</li>
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
    open_rows = ''.join(f'<tr><td><a href="{e(r["page_url"])}">{e(r["business_name"])}</a><small>{e(r["kind"])}</small></td><td>{e(r["city"] or "")}</td>'
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
