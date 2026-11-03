"""Live election night results (/elections/live).

The page is a shell; its script reads GET /api/v1/election-live every 30 seconds (the API reads the Supervisor of
Elections' results site at most about once a minute and stores each update, see api/_election_live.js) and
/api/v1/election-live/history for how each race moved. Local candidates link to their profiles and show what they
raised, from the candidates-2026 dataset. Past elections: /elections/results.
"""
import json

from entity_links import href, build


def _candidates():
    """[{n, l, g, h, r, i}] for 2026 candidates on the ballot: name, last name, government, profile link, raised, incumbent."""
    from opendata import datasets
    fn = {d[0]: d[3] for d in datasets()}
    ents = build().ents
    out = []
    for r in fn['candidates-2026']():
        if r.get('status') != 'on_ballot':
            continue
        import ids
        pp = r.get('person_id') or ids.person_id(r['candidate'])
        pid = 'person:' + pp if pp else None
        name = r['candidate']
        out.append({'n': name, 'l': name.replace('"', ' ').split()[-1].lower().strip('.,'), 'g': r.get('gov_id') or r.get('government'),
                    'h': href(pid) if pid and pid in ents else None, 'r': r.get('total_raised'), 'i': bool(r.get('incumbent'))})
    return out


CSS = r"""
.el-live .lv-bar{position:sticky;top:var(--sticky-top,0);z-index:5;display:flex;flex-wrap:wrap;align-items:center;gap:10px 18px;padding:12px 16px;margin:0 0 14px;
  border-radius:18px;background:var(--surface);box-shadow:var(--ui-shadow)}
.lv-dot{width:10px;height:10px;border-radius:50%;background:var(--muted);flex:none}
.lv-bar[data-s=counting] .lv-dot{background:#d33;animation:lvp 1.6s ease-in-out infinite}
.lv-bar[data-s=complete] .lv-dot{background:var(--teal)}
@keyframes lvp{0%,100%{opacity:1}50%{opacity:.3}}
@media (prefers-reduced-motion:reduce){.lv-bar[data-s=counting] .lv-dot{animation:none}}
.lv-st{display:flex;align-items:center;gap:8px;font-weight:600}
.lv-when{font-size:.85rem;color:var(--muted)}
.lv-prog{flex:1 1 220px;min-width:180px}
.lv-prog .t{display:flex;justify-content:space-between;font-size:.8rem;color:var(--muted);margin-bottom:4px}
.lv-prog .t b{color:var(--ink);font-variant-numeric:tabular-nums}
.lv-track{height:8px;border-radius:8px;background:var(--sunken);overflow:hidden}
.lv-track span{display:block;height:100%;background:var(--blue);border-radius:8px;transition:width .6s ease}
.lv-types{display:flex;flex-wrap:wrap;gap:6px}
.lv-type{font-size:.74rem;font-weight:600;padding:3px 10px;border-radius:999px;background:var(--sunken);color:var(--muted);white-space:nowrap}
.lv-type.part{background:color-mix(in srgb,var(--amber,#c80) 16%,transparent);color:var(--ink)}
.lv-type.done{background:color-mix(in srgb,var(--teal) 16%,transparent);color:var(--teal)}
.lv-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:0 0 16px}
.lv-k{padding:12px 16px;border-radius:16px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0}
.lv-k .eyebrow{display:block}
.lv-k .v{display:block;font:600 1.45rem var(--f-body);font-variant-numeric:tabular-nums;margin-top:2px}
.lv-k .s{display:block;font-size:.78rem;color:var(--muted)}
.lv-ctl{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center;margin:0 0 6px}
.lv-ctl input{flex:1 1 240px;min-height:44px;padding:0 14px;border-radius:12px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font:inherit}
.lv-wait{padding:14px 18px;border-radius:16px;background:color-mix(in srgb,var(--blue) 8%,var(--surface));margin:0 0 14px;font-size:.93rem;line-height:1.5}
.lv-grp{font-size:1.02rem;font-weight:600;margin:22px 0 10px}
.lv-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.lv-c{padding:16px 18px;border-radius:20px;background:var(--surface);box-shadow:var(--ui-shadow);min-width:0;scroll-margin-top:120px}
.lv-c h3{margin:0;font-size:.98rem;font-weight:600;text-wrap:balance}
.lv-tags{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 8px}
.lv-pill{font-size:.72rem;font-weight:600;padding:2px 9px;border-radius:999px;background:var(--sunken);color:var(--muted)}
.lv-pill.g{background:color-mix(in srgb,var(--blue) 14%,transparent);color:var(--blue)}
.lv-ch{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:3px 10px;padding:8px 0;border-top:1px solid var(--line)}
.lv-ch:first-of-type{border-top:0}
.lv-ch .nm{font-size:.92rem;overflow-wrap:anywhere}
.lv-ch .nm small{color:var(--muted);margin-left:4px;font-size:.76rem}
.lv-ch .v{font-size:.9rem;font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.lv-ch .v b{font-weight:600;font-size:1rem}
.lv-ch .v span{color:var(--muted);margin-left:6px}
.lv-ch .bar{grid-column:1/-1;height:8px;border-radius:8px;background:var(--sunken);overflow:hidden}
.lv-ch .bar span{display:block;height:100%;background:color-mix(in srgb,var(--muted) 70%,transparent);border-radius:8px;transition:width .6s ease}
.lv-ch.top .bar span{background:var(--blue)}
.lv-ch .meta{grid-column:1/-1;font-size:.76rem;color:var(--muted)}
.lv-lead{font-size:.7rem;font-weight:700;margin-left:6px;padding:1px 7px;border-radius:999px;background:color-mix(in srgb,var(--blue) 14%,transparent);color:var(--blue);white-space:nowrap}
.lv-lead.win{background:color-mix(in srgb,var(--teal) 16%,transparent);color:var(--teal)}
.lv-margin{font-size:.82rem;margin:8px 0 0;color:var(--ink)}
.lv-c details{margin-top:8px;font-size:.82rem}
.lv-c summary{cursor:pointer;color:var(--blue);font-weight:600;min-height:32px;display:flex;align-items:center}
.lv-c table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;margin-top:4px}
.lv-c th,.lv-c td{padding:5px 4px;border-top:1px solid var(--line);text-align:right;white-space:nowrap}
.lv-c th:first-child,.lv-c td:first-child{text-align:left;white-space:normal}
.lv-c thead th{border-top:0;color:var(--muted);font-weight:600;font-size:.74rem}
.lv-trend{display:block;width:100%;height:56px;margin-top:8px}
.lv-trend text{font-size:9px;fill:var(--muted)}
.lv-flash{animation:lvf 1.8s ease}
@keyframes lvf{0%{box-shadow:0 0 0 3px color-mix(in srgb,var(--blue) 45%,transparent)}100%{box-shadow:var(--ui-shadow)}}
@media (max-width:760px){.lv-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.lv-grid{grid-template-columns:1fr}.el-live .lv-bar{border-radius:14px;padding:10px 12px}}
"""

JS = r"""
(() => {
  const C = JSON.parse(document.getElementById('lvData').textContent);
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const n = v => v == null ? '—' : Number(v).toLocaleString('en-US');
  const usd = v => '$' + Math.round(v).toLocaleString('en-US');
  const GOV = [[/Panama City Beach/i, 'pcb'], [/Panama City/i, 'pc'], [/Lynn Haven/i, 'lh'], [/Callaway/i, 'cw'], [/Parker/i, 'parker'], [/Springfield/i, 'sp'], [/Mexico Beach/i, 'mb'],
    [/School Board/i, 'schools'], [/County Commission|Bay County/i, 'county'], [/Community Development District|\bCDD\b|Fire Control|Mosquito|Soil and Water/i, 'special']];
  const GOV_NAME = {pcb: 'Panama City Beach', pc: 'Panama City', lh: 'Lynn Haven', cw: 'Callaway', parker: 'Parker', sp: 'Springfield', mb: 'Mexico Beach', schools: 'School Board', county: 'Bay County', special: 'Special district'};
  const GROUPS = [['local', 'Local races'], ['localq', 'City ballot questions'], ['amend', 'State constitutional amendments'], ['state', 'Governor, Cabinet and Legislature'], ['federal', 'U.S. Senate and Congress'], ['judges', 'Judges on the ballot']];
  const isQ = c => c.choices.length && c.choices.every(x => /^(yes|no|for|against)/i.test(x.choice));
  function kind(c) {
    const t = c.contest;
    const g = (GOV.find(([re]) => re.test(t)) || [])[1] || null;
    if (/United States|Congress|President/i.test(t)) return {grp: 'federal', g: null};
    if (/Retention|Judge|Justice/i.test(t)) return {grp: 'judges', g: null};
    if (/Constitutional Amendment/i.test(t)) return {grp: 'amend', g: null};
    if (/Governor|Attorney General|Chief Financial|Agriculture|State Senator|State Representative/i.test(t)) return {grp: 'state', g: null};
    return {grp: isQ(c) ? 'localq' : 'local', g};
  }
  const norm = s => String(s).toLowerCase().replace(/"[^"]*"/g, ' ').replace(/[^a-z ]/g, ' ').replace(/\s+/g, ' ').trim();
  function cand(name, g) {
    const k = norm(name), last = k.split(' ').pop();
    return C.cands.find(x => norm(x.n) === k) || (() => { const m = C.cands.filter(x => x.l === last && (!g || x.g === g || g === 'special')); return m.length === 1 ? m[0] : null; })();
  }
  let D = null, H = [], lv = 'all', q = '', prev = {}, lastChanged = null;
  const SOE_TIME = s => { const m = String(s || '').match(/(\d+)\/(\d+)\/(\d+) (\d+):(\d+):\d+ ([ap])m/i); return m ? `${+m[4]}:${m[5]} ${m[6].toLowerCase() === 'p' ? 'p.m.' : 'a.m.'}` : ''; };
  const ago = iso => { if (!iso) return ''; const s = Math.max(0, Math.round((Date.now() - new Date(iso)) / 1000)); return s < 60 ? `${s} sec ago` : s < 3600 ? `${Math.round(s / 60)} min ago` : new Date(iso).toLocaleTimeString('en-US', {hour: 'numeric', minute: '2-digit'}); };
  function trend(c) {
    const pts = H.map(h => h.totals && h.totals[c.contest_id]).filter(Boolean);
    if (pts.length < 2) return '';
    const names = c.choices.map(x => x.choice), W = 300, Hh = 50;
    const shares = pts.map(t => { const tot = names.reduce((a, k) => a + (t[k] || 0), 0); return names.map(k => tot ? (t[k] || 0) / tot : 0); });
    const lead = c.choices.slice().sort((a, b) => (b.votes || 0) - (a.votes || 0))[0].choice;
    const lines = names.map((k, i) => {
      const d = shares.map((s, j) => `${(j / (shares.length - 1) * W).toFixed(1)},${(Hh - s[i] * Hh).toFixed(1)}`).join(' ');
      return `<polyline points="${d}" fill="none" stroke="${k === lead ? 'var(--blue)' : 'var(--muted)'}" stroke-width="${k === lead ? 2.2 : 1.4}" stroke-opacity="${k === lead ? 1 : .6}" vector-effect="non-scaling-stroke"/>`;
    }).join('');
    return `<svg class="lv-trend" viewBox="0 0 ${W} ${Hh + 6}" preserveAspectRatio="none" role="img" aria-label="Share of the vote after each of ${pts.length} updates"><line x1="0" x2="${W}" y1="${Hh / 2}" y2="${Hh / 2}" stroke="var(--line)" stroke-dasharray="3 3"/>${lines}</svg>
      <p class="lv-when" style="margin:2px 0 0">Share of the vote after each of ${pts.length} updates tonight (dashed line: 50%)</p>`;
  }
  function card(c) {
    const k = kind(c), tot = c.choices.reduce((a, x) => a + (x.votes || 0), 0);
    const sorted = c.choices.slice().sort((a, b) => (b.votes || 0) - (a.votes || 0));
    const done = D.status === 'complete';
    const types = ['election_day', 'early_voting', 'vote_by_mail', 'provisional'].filter(t => c.choices.some(x => x[t] != null));
    const rows = sorted.map((x, i) => {
      const pct = tot ? 100 * (x.votes || 0) / tot : 0;
      const p = k.grp === 'local' ? cand(x.choice, k.g) : null;
      const nm = p && p.h ? `<a href="${esc(p.h)}">${esc(x.choice)}</a>` : esc(x.choice);
      const party = x.party && !/^NO[NP]$/.test(x.party) ? `<small>${esc(x.party)}</small>` : '';
      const lead = i === 0 && tot > 0 && (x.votes || 0) > (sorted[1] ? sorted[1].votes || 0 : -1) ? `<span class="lv-lead${done ? ' win' : ''}">${done ? 'Most votes' : 'Leading'}</span>` : '';
      const meta = p ? [p.i ? 'Incumbent' : '', p.r != null ? `Raised ${usd(p.r)}` : ''].filter(Boolean).join(' · ') : '';
      return `<div class="lv-ch${i === 0 && tot ? ' top' : ''}"><span class="nm">${nm}${party}${lead}</span><span class="v"><b>${pct.toFixed(1)}%</b><span>${n(x.votes)}</span></span>
        <span class="bar"><span style="width:${pct.toFixed(2)}%"></span></span>${meta ? `<span class="meta">${meta}</span>` : ''}</div>`;
    }).join('');
    let margin = '';
    if (tot && sorted.length > 1) {
      const d = (sorted[0].votes || 0) - (sorted[1].votes || 0);
      margin = d === 0 ? '<p class="lv-margin">Tied.</p>' : `<p class="lv-margin">${esc(sorted[0].choice)} ${done ? 'won by' : 'leads by'} <b>${n(d)}</b> vote${d === 1 ? '' : 's'} (${(100 * d / tot).toFixed(1)} points).</p>`;
    }
    const tl = {election_day: 'Election Day', early_voting: 'Early', vote_by_mail: 'Mail', provisional: 'Provisional'};
    const table = types.length ? `<table><thead><tr><th>Choice</th>${types.map(t => `<th>${tl[t]}</th>`).join('')}<th>Total</th></tr></thead><tbody>${sorted.map(x => `<tr><td>${esc(x.choice)}</td>${types.map(t => `<td>${n(x[t])}</td>`).join('')}<td>${n(x.votes)}</td></tr>`).join('')}</tbody></table>` : '';
    const foot = [c.under_votes != null ? `Left blank: ${n(c.under_votes)}` : '', c.over_votes ? `Overvotes: ${n(c.over_votes)}` : ''].filter(Boolean).join(' · ');
    const tr = trend(c);
    const more = table || tr || foot ? `<details><summary>How people voted</summary>${table}${tr}${foot ? `<p class="lv-when">${foot}</p>` : ''}</details>` : '';
    const tags = [k.g && GOV_NAME[k.g] ? `<span class="lv-pill g">${esc(GOV_NAME[k.g])}</span>` : '', isQ(c) ? '<span class="lv-pill">Ballot question</span>' : ''].join('');
    return `<article class="lv-c" id="r${c.contest_id}" data-share-record><h3>${esc(c.contest)}</h3>${tags ? `<div class="lv-tags">${tags}</div>` : ''}${rows}${margin}${more}</article>`;
  }
  function render() {
    if (!D) return;
    const bar = $('lvBar'); bar.dataset.s = D.status;
    $('lvSt').textContent = D.status === 'complete' ? 'All precincts reported' : D.status === 'counting' ? 'Counting' : 'Waiting for first results';
    const t = SOE_TIME(D.soe_updated);
    $('lvWhen').textContent = [t ? `SOE update ${t}` : '', D.checked_at ? `checked ${ago(D.checked_at)}` : ''].filter(Boolean).join(' · ');
    const pr = D.precincts_reporting || 0, pt = D.precincts_total || 0;
    $('lvPr').textContent = `${pr} of ${pt}`; $('lvTrack').style.width = pt ? `${100 * pr / pt}%` : '0';
    const rep = D.reported || {}, lab = {early_voting: 'Early votes', vote_by_mail: 'Mail votes', election_day: 'Election Day'};
    $('lvTypes').innerHTML = ['early_voting', 'vote_by_mail', 'election_day'].map(k => { const v = rep[k] || ''; const cls = /complete/i.test(v) ? 'done' : /partial|progress/i.test(v) ? 'part' : '';
      return `<span class="lv-type ${cls}" title="${esc(v)}">${lab[k]}: ${/complete/i.test(v) ? 'all in' : /partial|progress/i.test(v) ? 'partly in' : 'not yet'}</span>`; }).join('');
    $('lvBal').textContent = n(D.ballots_cast); $('lvTurn').textContent = D.turnout_pct != null ? `${D.turnout_pct}%` : '—';
    $('lvReg').textContent = n(D.registered_voters); $('lvRaces').textContent = D.contests.length;
    $('lvWait').hidden = D.status !== 'waiting';
    const want = c => { const k = kind(c); if (lv === 'local' && !['local', 'localq'].includes(k.grp)) return false; if (lv === 'state' && ['local', 'localq'].includes(k.grp)) return false;
      if (!q) return true; return (c.contest + ' ' + c.choices.map(x => x.choice).join(' ')).toLowerCase().includes(q); };
    const cs = D.contests.filter(want);
    $('lvBox').innerHTML = GROUPS.map(([g, label]) => { const list = cs.filter(c => kind(c).grp === g); if (!list.length) return '';
      return `<h2 class="lv-grp" id="g-${g}">${label} <span class="muted" style="font-weight:400">(${list.length})</span></h2><div class="lv-grid" data-share-items>${list.map(card).join('')}</div>`; }).join('') || '<p class="muted">No races match.</p>';
    // briefly outline races whose numbers changed since the last refresh
    D.contests.forEach(c => { const sig = c.choices.map(x => x.votes).join(','); if (prev[c.contest_id] != null && prev[c.contest_id] !== sig) { const el = $('r' + c.contest_id); if (el) el.classList.add('lv-flash'); } prev[c.contest_id] = sig; });
  }
  async function history() { try { const r = await fetch(`/api/v1/election-live/history?election=${C.election}`); if (r.ok) H = (await r.json()).data || []; } catch (e) {} }
  async function load() {
    try {
      const r = await fetch(`/api/v1/election-live?election=${C.election}`);
      if (!r.ok) throw new Error(r.status);
      D = (await r.json()).data;
      if (D.changed_at !== lastChanged) { lastChanged = D.changed_at; await history(); }
      $('lvErr').hidden = true;
    } catch (e) { $('lvErr').hidden = false; }
    render();
  }
  const chips = $('lvLv');
  chips.addEventListener('click', ev => { const b = ev.target.closest('button'); if (!b) return; chips.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); lv = b.dataset.v; render(); });
  $('lvQ').addEventListener('input', ev => { q = ev.target.value.trim().toLowerCase(); render(); });
  load();
  setInterval(() => { if (!document.hidden) load(); }, 30000);
  setInterval(() => { if (D && !document.hidden) $('lvWhen').textContent = [SOE_TIME(D.soe_updated) ? `SOE update ${SOE_TIME(D.soe_updated)}` : '', D.checked_at ? `checked ${ago(D.checked_at)}` : ''].filter(Boolean).join(' · '); }, 5000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
})();
"""


def election_live_page():
    election = {'id': 4078, 'name': 'General Election', 'date': 'Tuesday, November 3, 2026'}
    data = {'election': election['id'], 'cands': _candidates()}
    src = f"https://enr.electionsfl.org/BAY/{election['id']}/Summary/"
    return f'''<style>{CSS}</style>
<div class="page tax el-live">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">People · Elections</span><h1>Election night results</h1>
    <p class="lede">The {election['date']} {election['name'].lower()} in Bay County, as the Supervisor of Elections posts the count. This page refreshes on its own every 30 seconds; results are unofficial until the canvassing board certifies them.</p></div>
    <div class="stamp"><a class="pill" href="/elections/results">Past results →</a><a class="pill" href="{src}" target="_blank" rel="noopener">Official results site</a></div></header>
  <div class="lv-bar" id="lvBar" data-s="waiting" aria-live="polite">
    <span class="lv-st"><span class="lv-dot" aria-hidden="true"></span><span id="lvSt">Loading the count…</span></span>
    <span class="lv-when" id="lvWhen"></span>
    <div class="lv-prog"><div class="t"><span>Precincts reporting</span><b id="lvPr">—</b></div><div class="lv-track"><span id="lvTrack" style="width:0"></span></div></div>
    <div class="lv-types" id="lvTypes"></div>
  </div>
  <p class="lv-wait" id="lvErr" hidden>The results could not be loaded just now. The page will try again in 30 seconds, or see the <a href="{src}" target="_blank" rel="noopener">official results site</a>.</p>
  <p class="lv-wait" id="lvWait" hidden>Polls close at 7 p.m. Central. The first numbers, early and mail votes, usually post shortly after, then Election Day precincts as they are counted. Every race on the ballot is below with its candidates.</p>
  <div class="lv-kpis">
    <div class="lv-k"><span class="eyebrow">Ballots counted</span><span class="v" id="lvBal">—</span><span class="s">So far tonight</span></div>
    <div class="lv-k"><span class="eyebrow">Turnout</span><span class="v" id="lvTurn">—</span><span class="s">Of registered voters</span></div>
    <div class="lv-k"><span class="eyebrow">Registered voters</span><span class="v" id="lvReg">—</span><span class="s">Countywide</span></div>
    <div class="lv-k"><span class="eyebrow">Races and questions</span><span class="v" id="lvRaces">—</span><span class="s">On Bay County ballots</span></div>
  </div>
  <div class="lv-ctl">
    <div class="chips" id="lvLv" role="group" aria-label="Which races"><button type="button" class="chip" data-v="all" aria-pressed="true">All races</button><button type="button" class="chip" data-v="local" aria-pressed="false">Local</button><button type="button" class="chip" data-v="state" aria-pressed="false">State and federal</button></div>
    <input id="lvQ" type="search" aria-label="Find a race or candidate" placeholder="Find a race or candidate" autocomplete="off">
  </div>
  <div id="lvBox"><p class="muted">Loading every race…</p></div>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="method">Where this comes from</h2></div>
    <ul class="plain">
      <li><b>The count</b> is read from the Supervisor of Elections' results site about once a minute while votes are counted, and each update is saved, so the trend lines show how every race moved through the night.</li>
      <li><b>Unofficial</b> until the county canvassing board certifies the results. Provisional and late overseas ballots can still change close races, and a race within half a point may go to a recount.</li>
      <li>A vote-type figure shown as "—" is 1 to 29 votes, which Florida law keeps from being reported. City races and questions are voted only by that city's voters.</li>
      <li>Local candidates link to their profiles, with what each raised from campaign finance reports (<a href="/elections">2026 races</a>).</li>
      <li><b>Data:</b> <a href="/api/v1/election-live">/api/v1/election-live</a> (the latest count) · <a href="/api/v1/election-live/history">/api/v1/election-live/history</a> (every update) · past elections in <a href="/api/v1/datasets/election-results">election-results</a>.</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script type="application/json" id="lvData">{json.dumps(data, separators=(",", ":")).replace("</", "<\\/")}</script>
<script>{JS}</script>'''
