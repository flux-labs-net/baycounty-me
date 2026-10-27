"""Utilities and trash day (/utilities): who provides water, sewer, electricity, natural gas, garbage, yard waste and
internet at an address, its pickup days and holiday changes, outage lines, and what each city charges.

Built from the utility-providers, trash-pickup, trash-holidays and utility-rates datasets (site/page_datasets.py, from
data/utilities/<county>/utilities.json and fees_pay_officials.json). The address search calls /api/v1/utilities, which
reads the city and route maps live (api/_utilities.js) and keeps no record of the address.
"""
import html
from collections import OrderedDict

from entity_links import a as link

e = lambda s: html.escape(str(s if s is not None else ''))

CSS = r"""
.ut-search{display:flex;flex-direction:column;gap:8px;padding:20px;border-radius:24px;background:var(--surface);box-shadow:var(--ui-shadow);margin:0 0 18px}
.ut-search .ac{position:relative}
.ut-search input{width:100%;font:inherit;font-size:1.05rem;padding:14px 16px;border-radius:14px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
.ut-search input:focus{outline:2px solid var(--blue);outline-offset:1px}
.ut-list{position:absolute;z-index:20;left:0;right:0;top:calc(100% + 4px);margin:0;padding:6px;list-style:none;border-radius:14px;background:var(--surface);box-shadow:var(--ui-shadow);max-height:320px;overflow:auto}
.ut-list li{padding:10px 12px;border-radius:10px;cursor:pointer;display:flex;justify-content:space-between;gap:12px}
.ut-list li span{color:var(--muted);font-size:.86rem}
.ut-list li[aria-selected=true],.ut-list li:hover{background:var(--sunken)}
.ut-list li.ut-empty{cursor:default;color:var(--muted)}
.ut-out[hidden],.ut [hidden]{display:none!important}
.ut-hd h2{margin:0;font-size:1.3rem}
.ut-hd p{margin:4px 0 0}
.ut-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin-top:14px}
.ut-card{display:flex;flex-direction:column;gap:6px;padding:16px 18px;border-radius:20px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.ut-card .eyebrow{font-size:.74rem}
.ut-card b{font-size:1rem;font-weight:600}
.ut-card b a{color:inherit}
.ut-card p{margin:0;font-size:.88rem;line-height:1.45}
.ut-card .ut-acts{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:.88rem;margin-top:2px}
.ut-day{font:600 1.35rem var(--f-body);margin:2px 0}
.ut-next{font-size:.88rem;color:var(--muted)}
.ut-warn{font-size:.86rem;padding:8px 10px;border-radius:12px;background:color-mix(in srgb,var(--amber,#b7791f) 14%,transparent)}
.ut-pick{border-left:4px solid var(--teal)}
.ut-tbl td,.ut-tbl th{vertical-align:top}
.ut-tbl td.n,.ut-tbl th.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.ut-tbl small{display:block;color:var(--muted);font-size:.78rem;line-height:1.35;margin-top:2px}
.ut-out-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
@media (max-width:760px){.ut-search{padding:16px}}
"""

JS = r"""
(() => {
const GIS = 'https://gis.baycountyfl.gov/arcgis/rest/services/Admin_A12/MapServer/3';
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const title = s => String(s || '').toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase()).replace(/\b(Ne|Nw|Se|Sw|Us|Cr|Sr)\b/g, m => m.toUpperCase());
const name = (id, text) => id && window.BC && BC.a ? BC.a(id, text) : esc(text);
const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const inp = $('utQ'), list = $('utList');
let items = [], active = -1, seq = 0, timer;

/* Holiday rules as the cities write them ("3rd Monday in January", "Friday after Thanksgiving") -> a date in a year. */
function easter(y) { const a = y % 19, b = Math.floor(y / 100), c = y % 100, d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25), g = Math.floor((b - f + 1) / 3),
  h = (19 * a + b - d - g + 15) % 30, i = Math.floor(c / 4), k = c % 4, l = (32 + 2 * e + 2 * i - h - k) % 7, m = Math.floor((a + 11 * h + 22 * l) / 451);
  return new Date(y, Math.floor((h + l - 7 * m + 114) / 31) - 1, ((h + l - 7 * m + 114) % 31) + 1); }
function nth(y, mo, dow, n) { if (n < 0) { const d = new Date(y, mo + 1, 0); while (d.getDay() !== dow) d.setDate(d.getDate() - 1); return d; }
  const d = new Date(y, mo, 1); while (d.getDay() !== dow) d.setDate(d.getDate() + 1); d.setDate(d.getDate() + 7 * (n - 1)); return d; }
function holidayDate(when, y) {
  let m = /^(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2})$/.exec(when);
  if (m) return new Date(y, MONTHS.indexOf(m[1]), +m[2]);
  m = /^(1st|2nd|3rd|4th|Last) (\w+day) in (\w+)$/.exec(when);
  if (m) return nth(y, MONTHS.indexOf(m[3]), DAYS.indexOf(m[2]), m[1] === 'Last' ? -1 : parseInt(m[1]));
  if (when === 'Friday before Easter') { const d = easter(y); d.setDate(d.getDate() - 2); return d; }
  if (when === 'Friday after Thanksgiving') { const d = nth(y, 10, 4, 4); d.setDate(d.getDate() + 1); return d; }
  return null;
}
const same = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
const fmtDate = d => `${DAYS[d.getDay()]}, ${MONTHS[d.getMonth()]} ${d.getDate()}`;
/* The next date one of these weekdays comes up (today counts), and any holiday on it that stops this kind of pickup. */
function nextPickup(days, svc, holidays) {
  const want = DAYS.filter(d => new RegExp('\\b' + d + '\\b').test(days || ''));
  if (!want.length) return null;
  const d = new Date(); d.setHours(0, 0, 0, 0);
  for (let i = 0; i < 8; i++, d.setDate(d.getDate() + 1)) {
    if (!want.includes(DAYS[d.getDay()])) continue;
    const key = svc === 'yard_waste' ? 'yard_waste' : 'garbage';
    const h = holidays.find(x => { const hd = holidayDate(x.when_observed, d.getFullYear()); return hd && same(hd, d) && /^No pickup/.test(x[key] || ''); });
    return {date: new Date(d), holiday: h};
  }
  return null;
}

async function gis(params) {
  const u = GIS + '/query?' + new URLSearchParams({f: 'json', returnGeometry: 'true', outSR: '4326', outFields: 'ADDRESS,UNIT,CMNTY,ZIP', resultRecordCount: '10', orderByFields: 'ADDRESS', ...params});
  const r = await fetch(u, {mode: 'cors'}); const j = await r.json(); if (j.error) throw new Error(j.error.message); return j.features || [];
}
const sq = s => s.replace(/'/g, "''");
async function suggest() {
  const s = inp.value.toUpperCase().replace(/[^A-Z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
  const m = /^(\d+)\s+(.+)$/.exec(s);
  if (!m) { hide(); return; }
  const words = m[2].split(' ').filter(w => w.length > 1 && !/^(ST|AVE|RD|DR|LN|CT|BLVD|WAY|CIR|PL|FL|PANAMA|CITY|BEACH|LYNN|HAVEN)$/.test(w)).slice(0, 4);
  if (!words.length) { hide(); return; }
  const my = ++seq;
  const where = [`ADDRESS LIKE '${m[1]} %'`, ...words.slice(0, -1).map(w => `(ADDRESS LIKE '% ${sq(w)} %' OR ADDRESS LIKE '% ${sq(w)}')`), `ADDRESS LIKE '% ${sq(words[words.length - 1])}%'`].join(' AND ');
  try {
    const f = await gis({where});
    if (my !== seq) return;
    items = f; active = -1;
    list.innerHTML = f.length ? f.map((x, i) => `<li role="option" id="ut${i}" data-i="${i}">${esc(title(x.attributes.ADDRESS))}${(x.attributes.UNIT || '').trim() ? ' #' + esc(x.attributes.UNIT) : ''}<span>${esc(x.attributes.CMNTY || '')} ${esc(x.attributes.ZIP || '')}</span></li>`).join('')
      : '<li class="ut-empty">No matching address. Try just the house number and street name.</li>';
    show();
  } catch (e) { if (my === seq) { list.innerHTML = '<li class="ut-empty">Bay County\'s map server didn\'t answer. Try again in a moment.</li>'; show(); } }
}
function show() { list.hidden = false; inp.setAttribute('aria-expanded', 'true'); }
function hide() { list.hidden = true; inp.setAttribute('aria-expanded', 'false'); }
function mark() { list.querySelectorAll('li[role=option]').forEach((li, i) => li.setAttribute('aria-selected', i === active)); if (active >= 0) inp.setAttribute('aria-activedescendant', 'ut' + active); }
function pick(f) {
  hide();
  const a = f.attributes;
  inp.value = title(a.ADDRESS) + ((a.UNIT || '').trim() ? ' #' + a.UNIT : '');
  const u = new URL(location.href); u.searchParams.set('a', a.ADDRESS); history.replaceState(null, '', u);
  run(f.geometry.y, f.geometry.x, inp.value + (a.CMNTY ? ', ' + title(a.CMNTY) : ''));
}

const link = (u, t) => u ? `<a href="${esc(u)}" rel="noopener" target="_blank">${esc(t)}</a>` : '';
const tel = p => p ? `<a href="tel:${esc(p.replace(/[^0-9+]/g, ''))}">${esc(p)}</a>` : '';

/* Render one lookup from /api/v1/utilities into box (this page and the /my-address card share it). */
function render(box, r, opts = {}) {
  const pick = r.pickup.map(p => {
    const sv = ((r.services.find(s => s.service === p.service) || {}).providers || [])[0];
    const nx = p.days && r.holidays ? nextPickup(p.days, p.service, r.holidays) : null;
    const zone = p.zone && p.zone !== p.days ? ` <span class="muted">(${/^\d+$/.test(p.zone) ? (p.zone_label || 'zone') + ' ' : ''}${esc(p.zone)})</span>` : '';
    return `<div class="ut-card ut-pick"><span class="eyebrow">${esc(p.service_label)}</span>
      ${p.days ? `<div class="ut-day">${esc(p.days)}${zone}</div>` : ''}${p.zone_area ? `<p class="muted">${esc(p.zone && !p.days ? p.zone + ': ' : '')}${esc(p.zone_area)}</p>` : ''}
      ${nx ? `<div class="ut-next">Next: ${fmtDate(nx.date)}</div>` : ''}
      ${nx && nx.holiday ? `<div class="ut-warn">${esc(nx.holiday.holiday)}: no pickup that day. Check the holiday changes below.</div>` : ''}
      ${p.rule ? `<p>${esc(p.rule)}</p>` : ''}${p.notes ? `<p>${esc(p.notes)}</p>` : ''}
      ${sv ? `<b style="font-size:.92rem">${name(sv.entity_id, sv.provider)}</b>${sv.notes ? `<p class="muted">${esc(sv.notes)}</p>` : ''}<div class="ut-acts">${tel(sv.phone)}${link(sv.website, 'Website')}</div>` : `<p class="muted">${esc(p.provider)}</p>`}</div>`;
  }).join('');
  // garbage, yard waste and bulk providers show on their trash-day card, not twice
  const svc = r.services.filter(s => !r.pickup.some(p => p.service === s.service)).map(s => s.providers.map((p, i) =>
    `<div class="ut-card"><span class="eyebrow">${esc(s.service_label)}${s.providers.length > 1 ? (i === 0 ? ' · most likely' : ' · or') : ''}</span>
      <b>${name(p.entity_id, p.provider)}</b>${p.notes ? `<p>${esc(p.notes)}</p>` : ''}
      <div class="ut-acts">${tel(p.phone)}${link(p.website, 'Website')}${p.outage_url && p.outage_url !== p.website ? link(p.outage_url, 'Outage map') : ''}</div></div>`).join('')).join('');
  const hol = (r.holidays || []).length ? `<details class="tbl-toggle"><summary>Holiday changes (${r.holidays.length})</summary><div class="tablewrap"><table class="tx-table ut-tbl" data-tt="off"><thead><tr><th>Holiday</th><th>When</th><th>Garbage</th><th>Yard waste</th></tr></thead><tbody>${r.holidays.map(h => `<tr><td>${esc(h.holiday)}</td><td>${esc(h.when_observed)}</td><td>${esc(h.garbage)}</td><td>${esc(h.yard_waste)}</td></tr>`).join('')}</tbody></table></div></details>` : '';
  const bill = (r.rates || []).find(x => x.service === 'bill');
  box.innerHTML = `<div class="ut-hd">${opts.heading === false ? '' : `<h2>${esc(opts.label || '')}</h2>`}<p class="muted">${r.area === 'county' ? 'Unincorporated Bay County' : 'City of ' + esc(r.area_name)}${bill ? ` · typical water and sewer bill $${Number(bill.amount).toFixed(2)} a month at 5,000 gallons` : ''}</p></div>
    ${pick ? `<h3 class="ch-grp" style="margin-top:14px">Trash day</h3><div class="ut-grid">${pick}</div>` : ''}
    <h3 class="ch-grp" style="margin-top:18px">Who provides what</h3><div class="ut-grid">${svc}</div>${hol}
    <p class="note">${esc(r.note)}</p>`;
}
window.BCUtil = {render, nextPickup, holidayDate,
  async card(el, {lat, lon}) {
    el.innerHTML = '<p class="muted small">Loading…</p>';
    try { const j = await (await fetch(`/api/v1/utilities?lat=${lat}&lon=${lon}`)).json(); if (j.error) throw new Error(j.error); render(el, j.data, {heading: false}); }
    catch (e) { el.innerHTML = '<p class="muted small">Utility lookup didn\'t answer. <a href="/utilities">Try the utilities page</a>.</p>'; }
  }};

async function run(lat, lon, label) {
  const out = $('utOut'), err = $('utErr');
  err.hidden = true; out.hidden = false; out.innerHTML = '<p class="muted">Looking up…</p>';
  try {
    const res = await fetch(`/api/v1/utilities?lat=${lat}&lon=${lon}`); const j = await res.json();
    if (j.error) throw new Error(j.error);
    render(out, j.data, {label});
  } catch (e) { out.hidden = true; err.textContent = e.message || 'The lookup didn\'t answer. Try again in a moment.'; err.hidden = false; }
}
if (!inp) return;
inp.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(suggest, 220); });
inp.addEventListener('keydown', ev => {
  if (list.hidden || !items.length) { if (ev.key === 'Enter') { ev.preventDefault(); suggest(); } return; }
  if (ev.key === 'ArrowDown') { ev.preventDefault(); active = Math.min(items.length - 1, active + 1); mark(); }
  else if (ev.key === 'ArrowUp') { ev.preventDefault(); active = Math.max(0, active - 1); mark(); }
  else if (ev.key === 'Enter') { ev.preventDefault(); pick(items[Math.max(0, active)]); }
  else if (ev.key === 'Escape') hide();
});
list.addEventListener('mousedown', ev => { const li = ev.target.closest('li[data-i]'); if (li) { ev.preventDefault(); pick(items[+li.dataset.i]); } });
document.addEventListener('click', ev => { if (!ev.target.closest('.ac')) hide(); });

const qa = new URLSearchParams(location.search).get('a');
if (qa) gis({where: `ADDRESS = '${sq(qa.toUpperCase())}'`, resultRecordCount: '1'}).then(f => f[0] && pick(f[0])).catch(() => {});
})();
"""


def _tel(p):
    return f'<a href="tel:{e("".join(c for c in p if c.isdigit() or c == "+"))}">{e(p)}</a>' if p else ''


def _ext(u, t):
    return f'<a href="{e(u)}" rel="noopener" target="_blank">{e(t)}</a>' if u else ''


def _prov(r):
    return link(r['entity_id'], r.get('entity_name') or r['provider']) if r.get('entity_id') else e(r['provider'])


def utilities_page(out_dir):
    write_js(out_dir)
    from page_datasets import utility_providers, utility_rates, trash_pickup, trash_holidays
    P, R, T, H = utility_providers(), utility_rates(), trash_pickup(), trash_holidays()
    if not P:
        return '<div class="page"><h1>Utilities and trash day</h1><p>No utilities on file for this place yet.</p></div>'
    areas = OrderedDict()
    for r in P + T:
        if r['area'] != 'all':
            areas.setdefault(r['area'], r['area_name'])
    order = [a for a in areas if a != 'county'] + (['county'] if 'county' in areas else [])

    def cell(area, svc):
        ps = [r for r in P if r['area'] == area and r['service'] == svc]
        if not ps:
            return '<span class="muted">—</span>'
        return '<br>'.join(_prov(r) + (f'<small>{e(r["coverage"])}</small>' if r.get('coverage') and r['coverage'] not in ('all', 'most', 'some') else '') for r in ps)

    def days(area, svc):
        rs = [r for r in T if r['area'] == area and r['service'] == svc]
        if not rs:
            return '<span class="muted">—</span>'
        r0 = rs[0]
        if r0.get('lookup_layer'):
            ds = sorted({x['pickup_days'] for x in rs if x.get('pickup_days')})
            return f'By route: {e(" or ".join(ds) if len(ds) <= 3 else "Monday to Friday")}<small>Search your address above for your day</small>'
        if any(x.get('pickup_days') for x in rs):
            return '<br>'.join(f'{e(x["pickup_days"])}' + (f'<small>{e(x["zone"])}{": " + e(x["zone_area"]) if x.get("zone_area") else ""}</small>' if x.get('zone') else '') for x in rs if x.get('pickup_days'))
        return e(r0.get('rule') or '')

    glance = ''.join(f'''<tr><th scope="row">{link("gov:" + a, areas[a]) if a != "county" else link("gov:county", areas[a])}</th>
      <td>{cell(a, "water")}</td><td>{cell(a, "garbage")}<small>{days(a, "garbage")}</small></td><td>{cell(a, "yard_waste")}<small>{days(a, "yard_waste")}</small></td>
      <td>{"<br>".join(_tel(ph) for ph in dict.fromkeys(r["phone"] for r in P if r["area"] == a and r["service"] in ("water", "garbage") and r.get("phone")))}</td></tr>''' for a in order)

    # outages: electric and gas lines for the whole county, plus each city's water line
    outage = ''.join(f'''<div class="ut-card"><span class="eyebrow">{e(r["service_label"])}</span><b>{_prov(r)}</b>
      <p>{e(r.get("provider_kind") or "")}</p><div class="ut-acts">{_tel(r["phone"])}{_ext(r.get("outage_url"), "Outage map") if r.get("outage_url") != r.get("website") else ""}{_ext(r.get("website"), "Website")}</div></div>'''
                     for r in P if r['area'] == 'all' and r['service'] in ('electric', 'gas'))

    # holidays by provider
    hol = ''
    for a in order:
        hs = [h for h in H if h['area'] == a]
        if hs:
            hol += (f'<h3 class="ch-grp">{e(areas[a])} <span class="muted" style="font-weight:400;font-size:.84rem">· {_ext(hs[0]["source_url"], "source")}</span></h3>'
                    '<div class="tablewrap"><table class="tx-table ut-tbl" data-tt="off"><thead><tr><th>Holiday</th><th>When</th><th>Garbage</th><th>Yard waste</th></tr></thead><tbody>'
                    + ''.join(f'<tr><td>{e(h["holiday"])}</td><td>{e(h["when_observed"])}</td><td>{e(h["garbage"])}</td><td>{e(h["yard_waste"])}</td></tr>' for h in hs)
                    + '</tbody></table></div>')
    no_hol = [areas[a] for a in order if not any(h['area'] == a for h in H)]

    # typical bill
    bills = sorted((r for r in R if r['service'] == 'bill'), key=lambda r: r['amount'] or 0)
    bill_rows = ''.join(f'<tr><th scope="row">{link("gov:" + r["area"], r["area_name"])}</th><td>{e(r["provider"])}<small>{e(r.get("notes") or "")}</small></td>'
                        f'<td class="n">${r["amount"]:,.2f}</td></tr>' for r in bills)

    n_prov = len({r['provider'] for r in P if r.get('entity_id')})
    n_map = len({r['area'] for r in T if r.get('lookup_layer')})
    k = lambda lab, v, s: f'<div class="kpi"><span class="eyebrow">{lab}</span><span class="v">{v}</span><span class="s">{s}</span></div>'
    kpis = (k('Areas', len(order), 'Seven cities and the unincorporated county') +
            k('Providers', n_prov, 'Cities, utilities and haulers, each with a profile') +
            k('Pickup maps', n_map, 'Cities whose route maps give your day by address') +
            (k('Typical water bill', f'${bills[0]["amount"]:.0f}–${bills[-1]["amount"]:.0f}', 'Water and sewer at 5,000 gallons a month') if bills else ''))
    as_of = P[0].get('as_of') or ''

    return f'''<link rel="stylesheet" href="/assets/utilities.css">
<div class="page tax ch ut">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Taxes · What you pay</span><h1>Utilities and trash day</h1>
    <p class="lede">Who provides your water, sewer, power, gas and garbage pickup depends on where you live. Search an address to see each provider, your trash and yard waste day, holiday changes and what your city charges.</p></div>
    <div class="stamp"><a class="pill" href="/public-money/fees-and-bills">Fees &amp; bills →</a><span>Providers and schedules as published by each city and the county, {e(as_of)}</span></div></header>

  <section class="ut-search" role="search">
    <label for="utQ" class="fld"><span>Street address</span></label>
    <div class="ac"><input id="utQ" type="search" autocomplete="off" spellcheck="false" placeholder="e.g. 825 Ohio Ave" aria-autocomplete="list" aria-controls="utList" aria-expanded="false">
      <ul id="utList" class="ut-list" role="listbox" hidden></ul></div>
    <p class="muted small">Start with the house number. Pickup routes come straight from each city's route map. BayCounty.me doesn't keep the addresses people look up.</p>
    <p class="err" id="utErr" role="alert" hidden></p>
  </section>
  <section class="ut-out" id="utOut" hidden aria-live="polite"></section>

  <div class="kpis">{kpis}</div>

  <section class="tx-sec"><div class="sec-hd"><h2 id="glance" data-tile="By city">Every city at a glance</h2><span class="muted">Water, garbage and yard waste</span></div>
    <div class="tablewrap"><table class="tx-table ut-tbl"><thead><tr><th>Where you live</th><th>Water and sewer</th><th>Garbage</th><th>Yard waste</th><th>Phone</th></tr></thead><tbody>{glance}</tbody></table></div>
    <p class="note">Where a city doesn't collect garbage, homes hire a licensed private hauler; the county keeps <a href="https://www.baycountyfl.gov/DocumentCenter/View/19009/Solid-Waste-Haulers---Bay-County-updated-11-12-25" rel="noopener" target="_blank">the list of haulers</a>. Curbside recycling stopped across the county after Hurricane Michael.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="outages" data-tile="Outages">Power and gas outages</h2><span class="muted">Countywide</span></div>
    <div class="ut-out-grid">{outage}</div>
    <p class="note">Electric service in Bay County comes from FPL or Gulf Coast Electric Cooperative, depending on the street. Your bill names your provider. For a water main break, call your city's water number in the table above.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="holidays" data-tile="Holidays">Holiday pickup changes</h2></div>
    {hol}
    <p class="note">{e(", ".join(no_hol))}: no published holiday schedule. Private haulers set their own holiday days.</p></section>

  <section class="tx-sec"><div class="sec-hd"><h2 id="rates" data-tile="Rates">What a typical water and sewer bill costs</h2><span class="muted">5,000 gallons a month, inside city limits</span></div>
    <div class="tablewrap"><table class="tx-table ut-tbl" data-tt-sort="2:asc"><thead><tr><th>Where</th><th>Utility, and how it adds up</th><th class="n">Monthly</th></tr></thead><tbody>{bill_rows}</tbody></table></div>
    <p class="note">Each city's council or commission sets its rates by ordinance or resolution; the county commission sets the county's. Every charge (base fees, tiers, garbage, stormwater, franchise fees and utility taxes) is in the <a href="/api/v1/datasets/utility-rates">utility-rates</a> dataset, and the <a href="/public-money/fees-and-bills">Fees &amp; bills</a> page compares them.</p></section>

  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>Providers and rules</b> are copied by hand from each city's and the county's own utility and sanitation pages, rate ordinances and the Florida Public Service Commission's filings. Each row links its source.</li>
      <li><b>Your city</b> comes from the county's city limits map. <b>Your pickup day</b> comes live from the city's route map where it publishes one (Panama City, Lynn Haven, Callaway and Parker). Other cities list their days by side of town, or leave it to your hauler.</li>
      <li><b>Electric co-op</b> territory comes from a national map of electric service areas. FPL and co-op lines can run through the same neighborhood, so your bill is the sure answer.</li>
      <li><b>Internet:</b> providers change by street; the <a href="https://broadbandmap.fcc.gov/" rel="noopener" target="_blank">FCC broadband map</a> lists every one at an address.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/utility-providers">utility-providers</a> (<a href="/downloads/utility-providers.csv">CSV</a>) · <a href="/api/v1/datasets/trash-pickup">trash-pickup</a> (<a href="/downloads/trash-pickup.csv">CSV</a>) · <a href="/api/v1/datasets/trash-holidays">trash-holidays</a> (<a href="/downloads/trash-holidays.csv">CSV</a>) · <a href="/api/v1/datasets/utility-rates">utility-rates</a> (<a href="/downloads/utility-rates.csv">CSV</a>) · one address: <a href="/api/v1/utilities?address=825+Ohio+Ave">/api/v1/utilities</a>.</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/utilities.js" defer></script>'''


def write_js(out_dir):
    import os
    os.makedirs(os.path.join(out_dir, 'assets'), exist_ok=True)
    open(os.path.join(out_dir, 'assets', 'utilities.js'), 'w').write(JS)
    open(os.path.join(out_dir, 'assets', 'utilities.css'), 'w').write(CSS)
