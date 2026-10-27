"""The elections hub: results of every Bay County election since 2016 (/elections/results) and where and when to vote,
with what's on your ballot by address (/elections/voting).

Built from the elections, election-results, election-dates and voting-locations datasets (site/civic_data.py) and
candidates-2026 for this year's local races. Local candidates link to their profiles (person_entity_id).
"""
import datetime as dt
import html
import json

from entity_links import a as link, build

e = lambda s: html.escape(str(s if s is not None else ''))
LEVEL_ORDER = ['City', 'County', 'School district', 'Special district', 'Court', 'State', 'Federal', 'Party']
LOCAL = {'City', 'County', 'School district', 'Special district'}
KIND = {'primary': 'Primary', 'general': 'General election', 'municipal': 'City elections', 'runoff': 'Runoff', 'referendum': 'Referendum',
        'recall': 'Recall', 'presidential preference primary': 'Presidential primary'}


def _govs():
    from place import governments
    return {g['key']: g.get('short') or g['name'] for g in governments()}


def _d(s):
    try:
        return dt.date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


def _long(d):
    return d.strftime('%A, %B %-d, %Y') if d else ''


def _short(d):
    return d.strftime('%b %-d, %Y') if d else ''


def _num(n):
    return '—' if n is None else f'{n:,}'


def _tile(d):
    return f'<span class="ui-date" aria-hidden="true"><span class="mo">{d.strftime("%b").upper()}</span><span class="d">{d.day}</span><span class="wd">{d.strftime("%a")}</span></span>'


def _kpi(lab, v, s):
    return f'<div class="kpi"><span class="eyebrow">{lab}</span><span class="v">{v}</span><span class="s">{s}</span></div>'


CSS = r"""
.eh-ctl{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center}
.eh-ctl select{min-height:44px;padding:0 12px;border-radius:12px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font:inherit;max-width:100%}
.eh-sum{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:.9rem;color:var(--muted);margin:4px 0 0}
.eh-sum b{color:var(--ink);font-variant-numeric:tabular-nums}
.eh-lv{font-size:1rem;font-weight:600;margin:18px 0 8px}
.eh-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}
.eh-c{padding:16px 18px;border-radius:20px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.eh-c h4{margin:0;font-size:.98rem;font-weight:600;text-wrap:balance}
.eh-c .eh-tags{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 10px}
.eh-pill{font-size:.72rem;font-weight:600;padding:2px 9px;border-radius:999px;background:var(--sunken);color:var(--muted)}
.eh-pill.g{background:color-mix(in srgb,var(--blue) 14%,transparent);color:var(--blue)}
.eh-ch{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 10px;padding:7px 0;border-top:1px solid var(--line)}
.eh-ch:first-of-type{border-top:0}
.eh-ch .nm{font-size:.9rem;overflow-wrap:anywhere}
.eh-ch .nm small{color:var(--muted);margin-left:4px}
.eh-ch .v{font-size:.88rem;font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.eh-ch .v b{font-weight:600}
.eh-bar{grid-column:1/-1;height:6px;border-radius:6px;background:var(--sunken);overflow:hidden}
.eh-bar span{display:block;height:100%;background:var(--muted);border-radius:6px}
.eh-ch.top .eh-bar span{background:var(--blue)}
.eh-ch .how{grid-column:1/-1;font-size:.76rem;color:var(--muted)}
.eh-win{font-size:.7rem;font-weight:600;color:var(--teal);margin-left:6px;white-space:nowrap}
.eh-foot{font-size:.76rem;color:var(--muted);margin-top:8px}
.eh-tbl td.n,.eh-tbl th.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.eh-next{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.eh-card{padding:18px 20px;border-radius:22px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.eh-card h3{margin:0 0 4px;font-size:1.05rem;font-weight:600}
.eh-card p{margin:4px 0 0;font-size:.9rem;line-height:1.5}
.eh-card .big{font:600 1.6rem var(--f-body);font-variant-numeric:tabular-nums;margin:2px 0}
.eh-dates{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px}
.eh-dates .ui-mc{align-items:flex-start}
.eh-dates .past{opacity:.55}
.eh-find{display:flex;gap:8px;flex-wrap:wrap;position:relative}
.eh-find input{flex:1 1 260px;min-height:46px;padding:0 14px;border-radius:14px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font:inherit}
.eh-find button{min-height:46px}
.eh-sug{list-style:none;margin:6px 0 0;padding:0;display:flex;flex-direction:column;gap:4px}
.eh-sug button{width:100%;text-align:left;padding:10px 12px;border-radius:12px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font:inherit;cursor:pointer}
.eh-sug button:hover{border-color:var(--blue)}
.eh-sug small{color:var(--muted);margin-left:6px}
.eh-res{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:14px}
.eh-res[hidden]{display:none}
.eh-site{display:flex;justify-content:space-between;gap:10px;padding:9px 0;border-top:1px solid var(--line);font-size:.9rem}
.eh-site:first-of-type{border-top:0}
.eh-site small{display:block;color:var(--muted)}
.eh-site .mi{white-space:nowrap;font-variant-numeric:tabular-nums;color:var(--muted)}
.eh-race{padding:9px 0;border-top:1px solid var(--line);font-size:.9rem}
.eh-race:first-of-type{border-top:0}
.eh-race small{display:block;color:var(--muted)}
.eh-res h3{margin:0 0 6px;font-size:1rem;font-weight:600}
@media (max-width:760px){.eh-next,.eh-res{grid-template-columns:1fr}.eh-grid{grid-template-columns:1fr}}
"""


# --- /elections/results ----------------------------------------------------------------------------------------------

RESULTS_JS = r"""
(() => {
  const D = JSON.parse(document.getElementById('ehData').textContent), G = D.govs;
  const sel = document.getElementById('ehPick'), box = document.getElementById('ehBox'), sum = document.getElementById('ehSum');
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const n = v => v == null ? '—' : Number(v).toLocaleString('en-US');
  const LOCAL = new Set(['City', 'County', 'School district', 'Special district']);
  let lv = '';
  const name = (c, ch) => ch[2] ? `<a href="${esc(D.ph[ch[2]])}">${esc(ch[0])}</a>` : esc(ch[0]);
  function card(c, el) {
    const tot = c.ch.reduce((s, x) => s + (x[6] || 0), 0), max = Math.max(...c.ch.map(x => x[6] || 0), 1);
    const done = el.status === 'final' && tot > 0;
    const rows = c.ch.slice().sort((a, b) => (b[6] || 0) - (a[6] || 0)).map((x, i) => {
      const pct = x[7] != null ? x[7] : tot ? 100 * (x[6] || 0) / tot : 0;
      const how = [x[3] != null ? 'Election Day ' + n(x[3]) : '', x[4] != null ? 'Early ' + n(x[4]) : '', x[5] != null ? 'Mail ' + n(x[5]) : ''].filter(Boolean).join(' · ');
      return `<div class="eh-ch${i === 0 && tot ? ' top' : ''}"><span class="nm">${name(c, x)}${x[1] && !/^NO[NP]$/.test(x[1]) ? `<small>${esc(x[1])}</small>` : ''}${i === 0 && done ? '<span class="eh-win">Most votes</span>' : ''}</span>
        <span class="v"><b>${pct.toFixed(1)}%</b> · ${n(x[6])}</span><span class="eh-bar"><span style="width:${(100 * (x[6] || 0) / max).toFixed(1)}%"></span></span>${how ? `<span class="how">${how}</span>` : ''}</div>`;
    }).join('');
    const tags = [c.g && G[c.g] ? `<span class="eh-pill g">${esc(G[c.g])}</span>` : '', c.m ? '<span class="eh-pill">Ballot question</span>' : '',
      c.pp ? `<span class="eh-pill">${esc(c.pp === 'REP' ? 'Republican primary' : c.pp === 'DEM' ? 'Democratic primary' : c.pp)}</span>` : '', c.rc ? '<span class="eh-pill">Recount figures</span>' : ''].join('');
    const foot = [c.un != null ? 'Left blank: ' + n(c.un) : '', c.ov != null ? 'Overvotes: ' + n(c.ov) : ''].filter(Boolean).join(' · ');
    return `<article class="eh-c"><h4>${esc(c.o)}</h4><div class="eh-tags">${tags}</div>${rows || '<p class="muted small">No votes reported.</p>'}${foot ? `<p class="eh-foot">${foot}</p>` : ''}</article>`;
  }
  function show() {
    const el = D.elections.find(x => String(x.id) === sel.value) || D.elections[0];
    const cs = (D.contests[el.id] || []).filter(c => !lv || (lv === 'local' ? LOCAL.has(c.lv) || (c.lv === 'Court' && c.g) : !(LOCAL.has(c.lv) || (c.lv === 'Court' && c.g))));
    sum.innerHTML = [`<span><b>${esc(el.long)}</b></span>`, el.bal != null ? `<span>Ballots cast <b>${n(el.bal)}</b></span>` : '', el.turn != null ? `<span>Turnout <b>${el.turn}%</b></span>` : '',
      el.reg != null ? `<span>Registered voters <b>${n(el.reg)}</b></span>` : '', `<span>${el.status === 'final' ? 'Final results' : el.status === 'canceled' ? 'Canceled: no votes were counted' : 'Results still coming in'}</span>`,
      `<a href="${esc(el.src)}" target="_blank" rel="noopener">Official results</a>`].filter(Boolean).join('');
    box.innerHTML = D.levels.map(L => {
      const g = cs.filter(c => c.lv === L); if (!g.length) return '';
      return `<h3 class="eh-lv">${esc(D.levelLabel[L] || L)}</h3><div class="eh-grid">${g.map(c => card(c, el)).join('')}</div>`;
    }).join('') || '<p class="muted">No contests match.</p>';
    const u = new URL(location.href); u.searchParams.set('e', el.id); history.replaceState(null, '', u);
  }
  const q = new URLSearchParams(location.search).get('e'); if (q && D.contests[q]) sel.value = q;
  sel.addEventListener('change', show);
  const chips = document.getElementById('ehLv');
  chips.addEventListener('click', ev => { const b = ev.target.closest('button'); if (!b) return; chips.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); lv = b.dataset.v; show(); });
  show();
})();
"""


def results_page():
    from page_datasets import elections, election_results
    E, R = elections(), election_results()
    if not E:
        return '<div class="page"><h1>Election results</h1><p>No results on file for this place yet.</p></div>'
    govs = _govs()
    contests = {}
    for r in R:
        cs = contests.setdefault(r['election_id'], {})
        c = cs.setdefault(r['contest_id'], {'o': r['office'], 'lv': r['level'], 'g': r['gov_id'], 'm': r['measure'], 'pp': r['party_primary'], 'rc': r['recount'],
                                            'ov': r['over_votes'], 'un': r['under_votes'], 'ch': []})
        pid = r['person_entity_id'] if r['person_entity_id'] in build().ents else None
        c['ch'].append([r['choice'], r['party'], pid, r['election_day'], r['early_voting'], r['vote_by_mail'], r['votes'], r['pct']])
    els = sorted(E, key=lambda x: x['date'], reverse=True)
    from entity_links import href
    ph = {r['person_entity_id']: href(r['person_entity_id']) for r in R if r['person_entity_id'] in build().ents}
    data = {'govs': govs, 'ph': ph, 'levels': LEVEL_ORDER,
            'levelLabel': {'City': 'City races and questions', 'County': 'County offices and questions', 'School district': 'School Board',
                           'Special district': 'Special districts', 'Court': 'Judges', 'State': 'State offices and amendments', 'Federal': 'President and Congress', 'Party': 'Party offices'},
            'elections': [{'id': x['election_id'], 'long': f"{x['name']}, {_long(_d(x['date']))}", 'status': x['status'], 'bal': x['ballots_cast'],
                           'reg': x['registered_voters'], 'turn': x['turnout_pct'], 'src': x['source_url']} for x in els],
            'contests': {k: list(v.values()) for k, v in contests.items()}}
    opts, year = [], None
    for x in els:
        y = x['date'][:4]
        if y != year:
            if year:
                opts.append('</optgroup>')
            opts.append(f'<optgroup label="{y}">')
            year = y
        opts.append(f'<option value="{x["election_id"]}">{e(_short(_d(x["date"])))}: {e(x["name"])}</option>')
    opts.append('</optgroup>')
    local_n = len({(r['election_id'], r['contest_id']) for r in R if r['level'] in LOCAL})
    gens = [x for x in E if x['kind'] == 'general' and x['turnout_pct']]
    last_gen = max(gens, key=lambda x: x['date']) if gens else None
    trows = ''.join(f'<tr><td>{e(_short(_d(x["date"])))}</td><td><a href="?e={x["election_id"]}#results">{e(x["name"])}</a></td><td>{e(KIND.get(x["kind"], x["kind"]))}</td>'
                    f'<td class="n">{_num(x["ballots_cast"])}</td><td class="n">{_num(x["registered_voters"])}</td><td class="n">{"" if x["turnout_pct"] is None else str(x["turnout_pct"]) + "%"}</td></tr>'
                    for x in els if x['status'] != 'canceled')
    kpis = (_kpi('Elections', len(E), 'Since 2016, each with every contest') +
            _kpi('Local contests', local_n, 'City, county, School Board and special district races and questions') +
            _kpi('Last general turnout', f"{last_gen['turnout_pct']}%" if last_gen else '—', f"{_num(last_gen['ballots_cast'])} ballots, {_short(_d(last_gen['date']))}" if last_gen else '') +
            _kpi('All contests', len({(r['election_id'], r['contest_id']) for r in R}), 'Including state, federal and judges'))
    return f'''<style>{CSS}</style>
<div class="page tax eh">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">People · Elections</span><h1>Election results since 2016</h1>
    <p class="lede">Every contest on a Bay County ballot since 2016, from the Supervisor of Elections' official results: who got how many votes, and how they voted (on Election Day, early or by mail).</p></div>
    <div class="stamp"><a class="pill" href="/elections/voting">Where and when to vote →</a><span>Results checked {e(_short(dt.date.today()))}</span></div></header>
  <div class="kpis">{kpis}</div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="results" data-tile="Results">Pick an election</h2><span class="muted">Local races first</span></div>
    <div class="eh-ctl"><label class="sr-only" for="ehPick">Election</label><select id="ehPick">{"".join(opts)}</select>
      <div class="chips" id="ehLv" role="group" aria-label="Which races"><button type="button" class="chip" data-v="" aria-pressed="true">All races</button><button type="button" class="chip" data-v="local" aria-pressed="false">Local</button><button type="button" class="chip" data-v="state" aria-pressed="false">State and federal</button></div></div>
    <p class="eh-sum" id="ehSum"></p>
    <div id="ehBox"></div>
    <p class="note">"Most votes" marks the leader once results are final. In a primary or a race with more than two candidates, the leader may still face a runoff or the general election. A count shown as "—" is 1 to 29 votes, which the law keeps from being reported. Candidate names link to their profiles on this site; for campaign money see <a href="/elections/past">past local elections</a> and <a href="/elections">the 2026 races</a>.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="turnout" data-tile="Turnout">Turnout, election by election</h2></div>
    <details class="tbl-toggle"><summary>Every election since 2016 ({len(E)})</summary><div class="tablewrap"><table class="tx-table eh-tbl"><thead><tr><th>Date</th><th>Election</th><th>Kind</th><th class="n">Ballots cast</th><th class="n">Registered</th><th class="n">Turnout</th></tr></thead><tbody>{trows}</tbody></table></div></details>
    <p class="note">City elections only count the voters in that city, so their turnout is the share of the city's voters. The January 2026 Lynn Haven recall election was canceled before any votes were counted.</p></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>Results</b> are read from the Supervisor of Elections' election results site, the same figures the Supervisor certifies. Elections from the last 60 days are read again every day, and every 20 minutes on election night.</li>
      <li>On a city election day the Supervisor also posts each city's own view of the same contests; those are counted once here. For the 2018 U.S. Senate, Governor and Agriculture Commissioner races, the recount figures replace the first count.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/elections">elections</a> (<a href="/downloads/elections.csv">CSV</a>) · <a href="/api/v1/datasets/election-results">election-results</a> (<a href="/downloads/election-results.csv">CSV</a>).</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script type="application/json" id="ehData">{json.dumps(data, separators=(",", ":")).replace("</", "<\\/")}</script>
<script>{RESULTS_JS}</script>'''


# --- /elections/voting -----------------------------------------------------------------------------------------------

VOTING_JS = r"""
(() => {
  const D = JSON.parse(document.getElementById('evData').textContent);
  const GIS = 'https://gis.baycountyfl.gov/arcgis/rest/services';
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const title = s => String(s || '').toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase()).replace(/\b(Ne|Nw|Se|Sw|Us|Cr|Sr)\b/g, m => m.toUpperCase());
  async function q(path, params) {
    const u = new URL(`${GIS}/${path}/query`);
    Object.entries({f: 'json', returnGeometry: 'false', outFields: '*', ...params}).forEach(([k, v]) => u.searchParams.set(k, v));
    const r = await fetch(u, {mode: 'cors'}); const j = await r.json(); if (j.error) throw new Error(j.error.message); return j.features || [];
  }
  const at = (path, pt) => q(path, {geometry: JSON.stringify({x: pt.x, y: pt.y, spatialReference: {wkid: 4326}}), geometryType: 'esriGeometryPoint', inSR: 4326, spatialRel: 'esriSpatialRelIntersects'}).then(f => f.map(x => x.attributes)).catch(() => []);
  const miles = (a, lat, lon) => { if (lat == null) return 1e9; const R = 3958.8, t = Math.PI / 180, dLat = (lat - a.y) * t, dLon = (lon - a.x) * t; const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.y * t) * Math.cos(lat * t) * Math.sin(dLon / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); };
  const dir = s => `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(s.address + ', ' + (s.city || '') + ', FL ' + (s.zip || ''))}`;
  const inp = $('evAddr'), sug = $('evSug');
  async function find() {
    const s = inp.value.toUpperCase().replace(/[^A-Z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
    const m = /^(\d+)\s+(.+)$/.exec(s); sug.innerHTML = '';
    if (!m) { sug.innerHTML = '<li class="muted small">Type a house number and street, for example "830 W 11th St".</li>'; return; }
    const words = m[2].split(' ').filter(w => !/^(ST|AVE|RD|DR|LN|CT|BLVD|N|S|E|W|STREET|AVENUE|ROAD|DRIVE|FL|PANAMA|CITY|BEACH)$/.test(w));
    const w = words.sort((a, b) => b.length - a.length)[0] || m[2].split(' ')[0];
    try {
      const f = await q('Admin_A12/MapServer/3', {where: `ADDRESS LIKE '${m[1]} %${w.replace(/'/g, "''")}%'`, outFields: 'ADDRESS,UNIT,CMNTY,ZIP', returnGeometry: 'true', outSR: 4326, resultRecordCount: 8, orderByFields: 'ADDRESS'});
      const seen = new Set(), uniq = f.filter(x => { const k = x.attributes.ADDRESS + x.attributes.ZIP; if (seen.has(k)) return false; seen.add(k); return true; });
      if (!uniq.length) { sug.innerHTML = '<li class="muted small">No Bay County address matches. Check the house number and street name.</li>'; return; }
      if (uniq.length === 1) return pick(uniq[0]);
      sug.innerHTML = uniq.map((x, i) => `<li><button type="button" data-i="${i}">${esc(title(x.attributes.ADDRESS))}<small>${esc(x.attributes.CMNTY || '')} ${esc(x.attributes.ZIP || '')}</small></button></li>`).join('');
      sug.onclick = ev => { const b = ev.target.closest('button'); if (b) pick(uniq[+b.dataset.i]); };
    } catch (err) { sug.innerHTML = '<li class="muted small">Bay County\'s map server didn\'t answer. Try again in a moment.</li>'; }
  }
  async function pick(f) {
    sug.innerHTML = ''; const a = f.attributes, pt = f.geometry; inp.value = title(a.ADDRESS);
    $('evRes').hidden = false; $('evFor').textContent = title(a.ADDRESS) + ', ' + (a.CMNTY || '') + ' ' + (a.ZIP || '');
    ['evEarly', 'evPoll', 'evBallot'].forEach(id => $(id).innerHTML = '<p class="muted small">Loading…</p>');
    const early = D.sites.filter(s => s.kind === 'early_voting').map(s => ({...s, d: miles(pt, s.lat, s.lon)})).sort((x, y) => x.d - y.d);
    $('evEarly').innerHTML = early.map(s => `<div class="eh-site"><span><b>${esc(s.name)}</b><small>${esc(s.address)}, ${esc(s.city)}${s.hours && s.hours !== D.early.hours ? ' · ' + esc(s.hours) : ''}</small></span><span class="mi">${s.d < 1e8 ? s.d.toFixed(1) + ' mi' : ''}<br><a href="${esc(dir(s))}" target="_blank" rel="noopener">Directions</a></span></div>`).join('');
    const poll = D.sites.filter(s => s.kind === 'polling_place').map(s => ({...s, d: miles(pt, s.lat, s.lon)})).sort((x, y) => x.d - y.d).slice(0, 3);
    $('evPoll').innerHTML = `<p class="small">On Election Day you must vote at your own precinct's polling place. <a href="${esc(D.finder)}" target="_blank" rel="noopener"><b>Look up your precinct with the Supervisor of Elections</b></a>. The closest polling places to this address are:</p>` +
      poll.map(s => `<div class="eh-site"><span><b>${esc(s.name)}</b><small>Precinct ${esc(s.precinct)} · ${esc(s.address)}, ${esc(s.city || '')}</small></span><span class="mi">${s.d.toFixed(1)} mi</span></div>`).join('');
    const [city, house, senate, ush] = await Promise.all([at('Admin_A12/MapServer/26', pt), at('ElectionAdministration/MapServer/3', pt), at('ElectionAdministration/MapServer/4', pt), at('ElectionAdministration/MapServer/5', pt)]);
    const cityName = (city || []).map(c => c.NAME).find(n => n && !/unincorp/i.test(n)) || null;
    const ck = cityName ? Object.keys(D.govs).find(k => D.govs[k] === cityName || D.govs[k].replace(/^City of /, '') === cityName) : null;
    const races = D.races.filter(r => r.gov === 'schools' || r.gov === 'county' || (ck && r.gov === ck) || (r.gov === 'special' && (!ck || ck === 'pcb')));
    const line = r => `<div class="eh-race"><a href="/elections#${esc(r.id)}"><b>${esc(r.office)}</b></a><small>${r.special ? 'Only for voters who live inside the district. ' : ''}${esc(r.cands)}</small></div>`;
    const dist = (x, lab) => x && x[0] ? `<div class="eh-race"><b>${lab}</b><small>${esc(x[0].NAME || '')}${x[0].REPNAME ? ' · now held by ' + esc(x[0].REPNAME) : ''}</small></div>` : '';
    $('evBallot').innerHTML = `<p class="small">${cityName ? 'This address is in the City of ' + esc(cityName) + '.' : 'This address is outside city limits (unincorporated Bay County), so no city races.'} Local races on the ${esc(D.early.election || 'next')} ballot here:</p>` +
      (races.map(r => line({...r, special: r.gov === 'special'})).join('') || '<p class="muted small">No contested local races for this address.</p>') +
      `<p class="small" style="margin-top:10px">State and federal races, and any amendments, are on every ballot too. Your districts:</p>` + dist(ush, 'U.S. House') + dist(senate, 'Florida Senate') + dist(house, 'Florida House') +
      `<p class="small" style="margin-top:10px"><a href="${esc(D.sample)}" target="_blank" rel="noopener"><b>See your exact sample ballot</b></a> from the Supervisor of Elections (it asks for your name and date of birth).</p>`;
  }
  $('evGo').addEventListener('click', find);
  inp.addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); find(); } });
})();
"""

KIND_LABEL = {'registration_deadline': 'Registration deadline', 'election_day': 'Election Day', 'early_voting': 'Early voting',
              'mail_ballot_request_deadline': 'Vote-by-mail request deadline', 'mail_ballot_return_deadline': 'Vote-by-mail return deadline', 'soe_event': 'Supervisor of Elections'}
SAMPLE_BALLOT = 'https://www.bayvotesfl.gov/elections/sample-ballot/'


def voting_page():
    from page_datasets import election_dates, voting_locations
    from civic_data import voting_info
    from opendata import datasets
    dates, sites, info = election_dates(), voting_locations(), voting_info()
    if not sites and not dates:
        return '<div class="page"><h1>Where and when to vote</h1><p>No voting information on file for this place yet.</p></div>'
    govs = _govs()
    today = dt.date.today()
    ev = info['early']
    eday = _d(ev.get('election_date'))
    s0, s1 = _d(ev.get('starts')), _d(ev.get('ends'))
    days = (eday - today).days if eday else None
    if s0 and s1 and s0 <= today <= s1:
        early_line = f"Early voting is open now, through {s1.strftime('%A, %B %-d')}."
    elif s0 and today < s0:
        early_line = f"Early voting runs {s0.strftime('%B %-d')} to {s1.strftime('%B %-d')}."
    else:
        early_line = 'Early voting has ended. On Election Day, vote at your own precinct.'
    # 2026 local races still to be decided (candidates-2026)
    fn = {d[0]: d[3] for d in datasets()}
    races = {}
    for r in fn['candidates-2026']():
        if r['race_status'] != 'on_ballot_nov3' or r['status'] != 'on_ballot':
            continue
        x = races.setdefault(r['race_id'], {'id': r['race_id'], 'office': r['office'], 'gov': r['government'], 'cands': []})
        x['cands'].append(r['candidate'])
    race_list = [{**x, 'cands': ', '.join(x['cands'])} for x in races.values()]
    order = {'schools': 0, 'county': 1, 'special': 9}
    race_list.sort(key=lambda x: (order.get(x['gov'], 5), x['office']))
    data = {'sites': [{k: s[k] for k in ('kind', 'name', 'address', 'city', 'zip', 'lat', 'lon', 'precinct', 'hours')} for s in sites],
            'early': ev, 'finder': info['finder_url'], 'sample': SAMPLE_BALLOT, 'races': race_list,
            'govs': {k: v for k, v in govs.items()}}

    cal = [d for d in dates if d['kind'] != 'soe_event']
    soe = [d for d in dates if d['kind'] == 'soe_event' and (_d(d['date']) or today) >= today]

    def dcard(d):
        dd = _d(d['date'])
        end = _d(d.get('end_date'))
        when = f"{dd.strftime('%b %-d')} to {end.strftime('%b %-d')}" if end else _long(dd)
        t = dt.datetime.fromisoformat(d['starts_at']) if d.get('starts_at') else None
        if t and (t.hour or t.minute):
            when += ' · ' + t.strftime('%-I:%M %p').replace(':00 ', ' ').lower().replace('am', 'a.m.').replace('pm', 'p.m.')
        past = (end or dd) < today
        lnk = f'<a href="{e(d["url"])}" target="_blank" rel="noopener">{e(d["title"])}</a>' if d.get('url') else e(d['title'])
        return (f'<div class="ui-mc{" past" if past else ""}">{_tile(dd)}<div style="min-width:0"><b>{lnk}</b><small>{e(when)}</small>'
                f'<small>{e(KIND_LABEL.get(d["kind"], d["kind"]))}{" · " + e(d["election"]) if d.get("election") else ""}</small></div></div>')

    early_sites = [s for s in sites if s['kind'] == 'early_voting']
    polls = sorted((s for s in sites if s['kind'] == 'polling_place'), key=lambda s: s['precinct'].zfill(4))
    erows = ''.join(f'<tr><td><b>{e(s["name"])}</b></td><td>{e(s["address"])}, {e(s["city"])} {e(s["zip"] or "")}</td><td>{e(s["hours"])}</td></tr>' for s in early_sites)
    prows = ''.join(f'<tr><td class="n">{e(s["precinct"])}</td><td><a href="{e(s["url"])}" target="_blank" rel="noopener">{e(s["name"])}</a></td><td>{e(s["address"])}, {e(s["city"] or "")} {e(s["zip"] or "")}</td></tr>' for s in polls)
    kpis = (_kpi('Next election', eday.strftime('%b %-d') if eday else '—', e(ev.get('election') or '')) +
            _kpi('Days to go', days if days is not None and days >= 0 else '—', 'Polls open 7 a.m. to 7 p.m.') +
            _kpi('Early voting sites', len(early_sites), 'Vote at any of them') +
            _kpi('Precincts', len(polls), 'Each with its own Election Day polling place'))
    return f'''<style>{CSS}</style>
<div class="page tax eh">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">People · Elections</span><h1>Where and when to vote</h1>
    <p class="lede">Key dates, every early voting site, each precinct's polling place, and the local races on your ballot by address. From the Bay County Supervisor of Elections.</p></div>
    <div class="stamp"><a class="pill" href="/elections/results">Past results →</a><span>Checked {e(_short(today))}</span></div></header>
  <div class="kpis">{kpis}</div>
  <section class="tx-sec"><div class="sec-hd"><h2 id="next" data-tile="Next election">{e(ev.get("election") or "Next election")}</h2><span class="muted">{e(_long(eday))}</span></div>
    <div class="eh-next">
      <div class="eh-card"><h3>Early voting</h3><p>{e(early_line)}</p><p>{e(ev.get("hours") or "")}</p><p class="small"><a href="{e(ev.get("live_wait_url"))}" target="_blank" rel="noopener">Live wait times</a></p></div>
      <div class="eh-card"><h3>Election Day</h3><p>Polls are open 7 a.m. to 7 p.m. Vote only at your own precinct's polling place; bring a photo ID with your signature.</p><p class="small"><a href="{e(info["finder_url"])}" target="_blank" rel="noopener">Find your precinct</a></p></div>
      <div class="eh-card"><h3>Vote by mail</h3><p>Your ballot must reach the Elections Office or an early voting drop box by 7 p.m. on Election Day. Precincts don't take mail ballots.</p><p class="small"><a href="https://www.bayvotesfl.gov/voters/vote-by-mail/" target="_blank" rel="noopener">Track or request a mail ballot</a></p></div>
    </div></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="address" data-tile="Your ballot">Your ballot and where to vote, by address</h2></div>
    <div class="eh-find"><label class="sr-only" for="evAddr">Your address</label><input id="evAddr" type="text" autocomplete="street-address" placeholder="House number and street, like 830 W 11th St"><button type="button" class="ui-btn" id="evGo">Look up</button></div>
    <ul class="eh-sug" id="evSug"></ul>
    <p class="small muted" id="evFor"></p>
    <div class="eh-res" id="evRes" hidden>
      <div class="eh-card"><h3>On your ballot</h3><div id="evBallot"></div></div>
      <div class="eh-card"><h3>Early voting sites, closest first</h3><div id="evEarly"></div><h3 style="margin-top:14px">Election Day</h3><div id="evPoll"></div></div>
    </div>
    <p class="note">The address is looked up on Bay County's map, in your browser; nothing is saved. Precinct lines aren't published as a map, so the exact polling place comes from the Supervisor of Elections' lookup.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="dates" data-tile="Key dates">Key dates in {today.year}</h2></div>
    <div class="eh-dates">{"".join(dcard(d) for d in cal)}</div>
    {f'<h3 class="eh-lv">Coming up at the Supervisor of Elections</h3><div class="eh-dates">{"".join(dcard(d) for d in soe)}</div>' if soe else ""}
    <p class="note">Canvassing board meetings and voting equipment tests are open to the public. <a href="{e(info["events_url"])}" target="_blank" rel="noopener">The Supervisor's calendar</a>.</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="early" data-tile="Early voting">Early voting sites</h2><span class="muted">{e(_short(s0))} to {e(_short(s1))}</span></div>
    <div class="tablewrap"><table class="tx-table eh-tbl"><thead><tr><th>Site</th><th>Address</th><th>Hours</th></tr></thead><tbody>{erows}</tbody></table></div>
    <p class="note">{e(ev.get("note") or "")}</p></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="polls" data-tile="Polling places">Election Day polling places</h2><span class="muted">{len(polls)} precincts</span></div>
    <details class="tbl-toggle"><summary>Every precinct's polling place</summary><div class="tablewrap"><table class="tx-table eh-tbl"><thead><tr><th class="n">Precinct</th><th>Polling place</th><th>Address</th></tr></thead><tbody>{prows}</tbody></table></div></details></section>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>Dates</b> come from the Supervisor of Elections' voter guide and early voting page; the Supervisor's events calendar is read every day.</li>
      <li><b>Polling places</b> are read from the Supervisor's precinct directory; <b>early voting sites</b> are copied from the Supervisor's early voting map before each countywide election. Map points come from Bay County's address points.</li>
      <li><b>Races on your ballot</b> are this site's list of 2026 local races still on the ballot (<a href="/elections">2026 races</a>), matched to your city. School Board and County Commission seats are elected countywide.</li>
      <li><b>Data:</b> <a href="/api/v1/datasets/election-dates">election-dates</a> (<a href="/downloads/election-dates.csv">CSV</a>) · <a href="/api/v1/datasets/voting-locations">voting-locations</a> (<a href="/downloads/voting-locations.csv">CSV</a>) · <a href="/api/v1/datasets/candidates-2026">candidates-2026</a>.</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script type="application/json" id="evData">{json.dumps(data, separators=(",", ":")).replace("</", "<\\/")}</script>
<script>{VOTING_JS}</script>'''
