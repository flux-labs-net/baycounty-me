"""Hurricane prep (/hurricane-prep): what to do before the season, sandbags, generator safety, when a storm is coming and
after it; live sandbag, shelter and evacuation notices; every federal disaster declaration since 2016; and the FEMA
housing aid and flood insurance money that reached each ZIP code after storms.

Built from the hurricane-prep, disaster-declarations and rebuild-money datasets (site/page_datasets.py, from
data/emergency/<county>/prep.json and rebuild.json). The live notices read /api/v1/emergency, like /emergency.
"""
import html
import json

from emergency_page import CSS as EM_CSS, _notice, _when
from ui import ico

e = lambda s: html.escape(str(s if s is not None else ''))
TOPIC_ICON = {'Before the season': 'calendar', 'Sandbags': 'shield', 'Generator safety': 'bulb', 'When a storm is coming': 'storm', 'After the storm': 'crane'}
LIVE_RE = r'sand|shelter|evacuat|hurricane|tropical|storm surge|curfew|re-?entry|debris'

CSS = r"""
.hp{--s1:#3F6FB0;--s2:#D9902A}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .hp{--s1:#5B88D0;--s2:#B87A22}}
:root[data-theme="dark"] .hp{--s1:#5B88D0;--s2:#B87A22}
.hp-topics{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.hp-t{display:flex;flex-direction:column;gap:10px;padding:18px 20px;border-radius:22px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0;scroll-margin-top:90px}
.hp-t h3{display:flex;gap:10px;align-items:center;margin:0;font-size:1.05rem}
.hp-t ol{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:12px}
.hp-t li b{display:block;font-size:.95rem}
.hp-t li p{margin:3px 0 0;font-size:.9rem;line-height:1.5}
.hp-t li small{color:var(--muted);font-size:.8rem}
.hp-live{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.hp-ctl{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.hp-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.hp-kpi{padding:14px 16px;border-radius:18px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.hp-kpi b{display:block;font:600 1.5rem var(--f-data);font-variant-numeric:tabular-nums;line-height:1.15}
.hp-kpi span{font-size:.8rem;color:var(--muted)}
.hp-legend{display:flex;gap:16px;flex-wrap:wrap;font-size:.84rem;color:var(--muted)}
.hp-legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.hp-bars{display:flex;flex-direction:column;gap:6px;padding:16px 18px;border-radius:22px;background:var(--surface);box-shadow:var(--ui-shadow)}
.hp-row{display:grid;grid-template-columns:minmax(0,15rem) minmax(0,1fr) 6.5rem;gap:12px;align-items:center;padding:3px 4px;border-radius:10px}
.hp-row:hover,.hp-row:focus-within{background:var(--sunken)}
.hp-row .n{font-size:.86rem;line-height:1.25;min-width:0}
.hp-row .n b{font:600 .86rem var(--f-data)}
.hp-row .n small{display:block;color:var(--muted);font-size:.76rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hp-row .track{display:flex;gap:2px;height:16px;align-items:stretch;min-width:0}
.hp-row .track span{display:block;min-width:0;height:100%}
.hp-row .track span:last-child{border-radius:0 4px 4px 0}
.hp-row .track .a{background:var(--s1)}.hp-row .track .b{background:var(--s2)}
.hp-row .v{text-align:right;font:600 .86rem var(--f-data);font-variant-numeric:tabular-nums}
.hp-tip{position:fixed;z-index:50;pointer-events:none;padding:10px 12px;border-radius:12px;background:var(--surface);box-shadow:var(--ui-shadow);font-size:.82rem;line-height:1.45;max-width:280px}
.hp-tip[hidden]{display:none}
.hp-tbl td.num,.hp-tbl th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.hp-tbl td.d{white-space:nowrap}
.hp-yes{color:var(--teal);font-weight:600}
@media (max-width:640px){.hp-kpis{grid-template-columns:1fr}.hp-row{grid-template-columns:minmax(0,1fr) 5.5rem}.hp-row .track{grid-column:1/-1;order:3}.hp-topics{grid-template-columns:1fr}}
"""

JS = r"""
(() => {
  const $ = id => document.getElementById(id), esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'})[c]);
  const money = v => v >= 1e6 ? '$' + (v / 1e6).toFixed(v >= 1e7 ? 0 : 1) + 'M' : v >= 1e3 ? '$' + Math.round(v / 1e3) + 'K' : '$' + Math.round(v);
  const full = v => '$' + Math.round(v).toLocaleString('en-US');
  const ROWS = JSON.parse($('hpRows').textContent);
  let storm = '';
  const pick = r => !storm || (storm === 'other' ? !['Hurricane Michael', 'Hurricane Sally'].includes(r.e) : r.e === storm);
  function draw() {
    const z = new Map();
    for (const r of ROWS.filter(pick)) {
      const o = z.get(r.z) || {z: r.z, name: r.n, fema: 0, apps: 0, flood: 0, claims: 0};
      if (r.p === 'f') { o.fema += r.a; o.apps += r.c; } else { o.flood += r.a; o.claims += r.c; }
      z.set(r.z, o);
    }
    const list = [...z.values()].map(o => ({...o, t: o.fema + o.flood})).filter(o => o.t > 0).sort((a, b) => (a.z === 'other') - (b.z === 'other') || b.t - a.t);
    const max = Math.max(1, ...list.map(o => o.t));
    $('hpBars').innerHTML = list.map(o => `<div class="hp-row" tabindex="0" data-tip="${esc(JSON.stringify(o))}">
      <div class="n"><b>${o.z === 'other' ? 'Other' : esc(o.z)}</b><small>${esc(o.name)}</small></div>
      <div class="track" aria-hidden="true">${o.fema ? `<span class="a" style="width:${(o.fema / max * 100).toFixed(2)}%"></span>` : ''}${o.flood ? `<span class="b" style="width:${(o.flood / max * 100).toFixed(2)}%"></span>` : ''}</div>
      <div class="v">${money(o.t)}</div></div>`).join('') || '<p class="muted">No money on file for this storm.</p>';
    const sum = k => list.reduce((s, o) => s + o[k], 0);
    $('hpK1').textContent = money(sum('t')); $('hpK2').textContent = money(sum('fema')); $('hpK3').textContent = money(sum('flood'));
    $('hpK2s').textContent = `FEMA housing aid · ${sum('apps').toLocaleString('en-US')} households applied`;
    $('hpK3s').textContent = `Flood insurance paid · ${sum('claims').toLocaleString('en-US')} claims`;
    $('hpTbody').innerHTML = list.map(o => `<tr><td>${o.z === 'other' ? 'Other' : esc(o.z)}</td><td>${esc(o.name)}</td><td class="num">${o.apps.toLocaleString('en-US')}</td><td class="num">${full(o.fema)}</td><td class="num">${o.claims.toLocaleString('en-US')}</td><td class="num">${full(o.flood)}</td><td class="num">${full(o.t)}</td></tr>`).join('');
  }
  $('hpStorm').addEventListener('click', ev => {
    const b = ev.target.closest('.chip'); if (!b) return;
    storm = b.dataset.v; $('hpStorm').querySelectorAll('.chip').forEach(x => x.setAttribute('aria-pressed', x === b ? 'true' : 'false')); draw();
  });
  const tip = $('hpTip');
  const show = (el, x, y) => {
    const o = JSON.parse(el.dataset.tip);
    tip.innerHTML = `<b>${o.z === 'other' ? 'Other ZIP codes' : 'ZIP ' + esc(o.z)}</b><br>${esc(o.name)}<br><span style="color:var(--s1)">■</span> FEMA housing aid ${full(o.fema)} (${o.apps.toLocaleString('en-US')} households applied)<br><span style="color:var(--s2)">■</span> Flood insurance ${full(o.flood)} (${o.claims.toLocaleString('en-US')} claims)`;
    tip.hidden = false; const w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.min(innerWidth - w - 12, x + 14) + 'px'; tip.style.top = Math.max(8, y - h - 12) + 'px';
  };
  $('hpBars').addEventListener('pointermove', ev => { const r = ev.target.closest('.hp-row'); if (r) show(r, ev.clientX, ev.clientY); else tip.hidden = true; });
  $('hpBars').addEventListener('pointerleave', () => { tip.hidden = true; });
  $('hpBars').addEventListener('focusin', ev => { const r = ev.target.closest('.hp-row'); if (r) { const b = r.getBoundingClientRect(); show(r, b.left + b.width / 2, b.top); } });
  $('hpBars').addEventListener('focusout', () => { tip.hidden = true; });
  draw();

  // live sandbag, shelter and evacuation notices
  const RE = new RegExp($('hpLive').dataset.re, 'i');
  fetch('/api/v1/emergency').then(r => r.ok ? r.json() : Promise.reject()).then(d => {
    const n = d.notices.filter(x => ['evacuation', 'shelter'].includes(x.kind) || RE.test(x.title + ' ' + (x.event || '')));
    if (!n.length) { $('hpLive').innerHTML = ''; $('hpNone').hidden = false; return; }
    $('hpNone').hidden = true;
    $('hpLive').innerHTML = n.slice(0, 12).map(x => `<article class="em-n" data-sev="${esc(x.severity)}"><span class="k">${esc(x.kind === 'weather' && x.event ? x.event : (d.labels[x.kind] || 'Notice'))}</span>
      <h3>${esc(x.title)}</h3><small>${esc(x.source)} · <a href="${esc(x.page)}">Details</a>${x.url ? ` · <a href="${esc(x.url)}" target="_blank" rel="noopener">Source</a>` : ''}</small></article>`).join('');
  }).catch(() => {});
})();
"""


def hurricane_prep_page(out_dir=None):
    import re
    from page_datasets import hurricane_prep, disaster_declarations, rebuild_money, emergency_notices
    P, D, M, N = hurricane_prep(), disaster_declarations(), rebuild_money(), emergency_notices()
    if not P:
        return '<div class="page"><h1>Hurricane prep</h1><p>No hurricane prep information on file for this place yet.</p></div>'
    live = [n for n in N if n['status'] == 'active' and (n['kind'] in ('evacuation', 'shelter') or re.search(LIVE_RE, f"{n['title']} {n.get('event') or ''}", re.I))]

    topics = []
    for t in dict.fromkeys(p['topic'] for p in P):
        steps = ''.join(f'<li><b>{e(p["step"])}</b><p>{e(p["text"])}</p><small>Source: <a href="{e(p["source_url"])}" target="_blank" rel="noopener">{e(p["source"])}</a></small></li>'
                        for p in P if p['topic'] == t)
        slug = re.sub(r'[^a-z]+', '-', t.lower()).strip('-')
        topics.append(f'<section class="hp-t" id="{slug}"><h3>{ico(TOPIC_ICON.get(t, "info"))}{e(t)}</h3><ol>{steps}</ol></section>')

    # rebuild money, compact rows for the chart (p: f = FEMA housing aid, n = flood insurance)
    rows = [{'z': r['zip'], 'n': r['area_name'], 'p': 'f' if r['program'].startswith('FEMA') else 'n', 'e': r['event'], 'y': r['year'],
             'c': r['count'] or 0, 'a': round(r['amount_paid'] or 0)} for r in M]
    total = sum(r['a'] for r in rows)
    fema = sum(r['a'] for r in rows if r['p'] == 'f')
    flood = total - fema
    apps = sum(r['c'] for r in rows if r['p'] == 'f')
    claims = sum(r['c'] for r in rows if r['p'] == 'n')
    money = lambda v: f'${v / 1e6:.0f}M' if v >= 1e7 else f'${v / 1e6:.1f}M' if v >= 1e6 else f'${v / 1e3:.0f}K'
    years = sorted({r['y'] for r in rows})

    drows = ''.join(f'''<tr><td class="d">{_when(d["declared"])}</td><td><a href="{e(d["source_url"])}" target="_blank" rel="noopener">{e(d["title"])}</a></td><td>{e(d["kind"])}</td>
  <td class="num">{e(d["disaster_number"])}</td><td>{'<span class="hp-yes">Yes</span>' if d["individual_aid"] else 'No'}</td><td>{'<span class="hp-yes">Yes</span>' if d["public_aid"] else 'No'}</td></tr>''' for d in D)
    n_major = sum(1 for d in D if d['kind'] == 'Major disaster')

    return f'''<style>{EM_CSS}{CSS}</style>
<div class="page tax em hp">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Take part · Stay safe</span><h1>Hurricane prep</h1>
    <p class="lede">Get ready for hurricane season in Bay County: a plan and a kit, sandbags, generator safety, what to do when a storm is coming and after it passes. Plus every federal disaster declaration since 2016, and how much FEMA housing aid and flood insurance money reached each part of the county after past storms.</p></div>
    <div class="stamp"><a class="pill" href="/emergency#zone">Find my evacuation zone →</a><span>Season runs June 1 to November 30. In an emergency, call 911.</span></div></header>

  <section class="tx-sec"><div class="sec-hd"><h2 id="now" data-tile="Right now">Right now</h2><span class="muted">Sandbags, shelters, evacuations and storm updates</span></div>
    <div class="hp-live" id="hpLive" data-re="{e(LIVE_RE)}">{"".join(_notice(n) for n in live)}</div>
    <p class="em-empty" id="hpNone" {"hidden" if live else ""}>No sandbag sites, shelter openings or evacuation orders posted right now. Bay County and the cities announce sandbag sites when a storm threatens; they'll show here within minutes. Everything else is on <a href="/emergency">Emergencies and alerts</a>.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="steps" data-tile="Prep steps">What to do</h2><span class="muted">From Bay County, Ready.gov, the CDC, the Weather Service and FEMA</span></div>
    <div class="hp-topics">{"".join(topics)}</div>
    <p class="note">Written in plain English from the source on each step; follow the source for the full guidance. Checked {_when(P[0]["as_of"])}.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="rebuild" data-tile="Rebuild money">Rebuild money by neighborhood</h2><span class="muted">By ZIP code, {years[0] if years else ""} to {years[-1] if years else ""}</span></div>
    <p>After a declared disaster, FEMA can pay households to repair homes and rent somewhere while they rebuild. Flood insurance (the National Flood Insurance Program) pays policyholders after any flood. Both are published by FEMA as totals per ZIP code; <b>no household is named</b>.</p>
    <div class="hp-ctl"><div class="chips" id="hpStorm" role="group" aria-label="Storm">
      <button type="button" class="chip" data-v="" aria-pressed="true">Every storm</button><button type="button" class="chip" data-v="Hurricane Michael" aria-pressed="false">Hurricane Michael (2018)</button>
      <button type="button" class="chip" data-v="Hurricane Sally" aria-pressed="false">Hurricane Sally (2020)</button><button type="button" class="chip" data-v="other" aria-pressed="false">Other storms and flooding</button></div></div>
    <div class="hp-kpis"><div class="hp-kpi"><b id="hpK1">{money(total)}</b><span>Total paid</span></div>
      <div class="hp-kpi"><b id="hpK2">{money(fema)}</b><span id="hpK2s">FEMA housing aid · {apps:,} households applied</span></div>
      <div class="hp-kpi"><b id="hpK3">{money(flood)}</b><span id="hpK3s">Flood insurance paid · {claims:,} claims</span></div></div>
    <div class="hp-legend"><span><i style="background:var(--s1)"></i>FEMA housing aid</span><span><i style="background:var(--s2)"></i>Flood insurance claims paid</span></div>
    <div class="hp-bars" id="hpBars" role="img" aria-label="Rebuild money by ZIP code; the table below has every figure"></div>
    <div class="hp-tip" id="hpTip" hidden></div>
    <details class="tbl-toggle"><summary>Table: every ZIP code</summary><div class="tablewrap"><table class="tx-table hp-tbl"><thead><tr><th>ZIP</th><th>Area</th><th class="num">Households applied</th><th class="num">FEMA housing aid</th><th class="num">Flood claims</th><th class="num">Flood insurance paid</th><th class="num">Total</th></tr></thead>
      <tbody id="hpTbody"></tbody></table></div></details>
    <p class="note">FEMA housing aid is the Individuals and Households Program for major disasters that opened it (Hurricane Michael and Hurricane Sally since 2016): dollars approved for repairs, replacement and rent, for owners and renters added together. Flood insurance is building, contents and code-compliance payments on claims for properties in Bay County, by the year of the flood. Some ZIP codes cross the county line; only Bay County applicants and properties are counted. Money to governments (public assistance) isn't in these figures; for that, see <a href="/public-money/hurricane-michael">where the Hurricane Michael money went</a>.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="declarations" data-tile="Declarations">Disaster declarations</h2><span class="muted">{len(D)} since 2016, {n_major} major disasters</span></div>
    <details class="tbl-toggle" open><summary>{len(D)} declarations</summary><div class="tablewrap"><table class="tx-table hp-tbl" data-tt-year="off"><thead><tr><th>Declared</th><th>Event</th><th>Kind</th><th class="num">FEMA number</th><th>Aid to households</th><th>Aid to governments</th></tr></thead>
    <tbody>{drows}</tbody></table></div></details>
    <p class="note">A major disaster declaration opens FEMA programs; an emergency declaration pays for protective steps like evacuations and shelters before and during a storm. Fire management declarations help pay for fighting large wildfires.</p></section>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>Prep steps</b> are summarized by hand from Bay County's Disaster Preparedness Guide and Emergency Services, Ready.gov, the CDC, the National Weather Service, FEMA and the Army Corps of Engineers; each step links its source.</li>
      <li><b>Declarations and rebuild money</b> come from OpenFEMA: Disaster Declarations Summaries, Housing Assistance Program data for owners and renters, and redacted NFIP flood claims, refreshed weekly.</li>
      <li><b>Right now</b> is the same live feed as <a href="/emergency">Emergencies and alerts</a>, checked every 5 minutes.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/hurricane-prep">hurricane-prep</a> · <a href="/api/v1/datasets/disaster-declarations">disaster-declarations</a> · <a href="/api/v1/datasets/rebuild-money">rebuild-money</a> · <a href="/api/v1/emergency">/api/v1/emergency</a> (live).</li>
    </ul></section>
</div>
<script type="application/json" id="hpRows">{json.dumps(rows, separators=(",", ":"))}</script>
<link rel="stylesheet" href="/assets/tax.css">
<script>{JS}</script>'''
