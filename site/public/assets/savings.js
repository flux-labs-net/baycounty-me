/* Savings finder: opportunities, their evidence and the records to request.
   Data: /data/savings.json (built by site/savings_page.py from the Accountability projects and the CRA ledger).
   ?k=<kind of saving> filters the list; #<opportunity id> opens on one opportunity. */
(async () => {
const $ = id => document.getElementById(id);
let D;
try { const r = await fetch('/data/savings.json'); if (!r.ok) throw new Error(r.status); D = await r.json(); }
catch (e) { $('svList').innerHTML = '<p class="muted">The opportunities could not be loaded. Please refresh the page.</p>'; return; }
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const big = n => n == null ? '—' : (n < 0 ? '−' : '') + (Math.abs(n) >= 1e6 ? '$' + (Math.abs(n) / 1e6).toFixed(1) + 'M' : Math.abs(n) >= 1e3 ? '$' + Math.round(Math.abs(n) / 1e3) + 'K' : '$' + Math.round(Math.abs(n)).toLocaleString('en-US'));
const pct = r => r == null ? '—' : (Math.abs(r) < 0.1 ? +(r * 100).toFixed(1) : Math.round(r * 100)) + '%';
const conf = c => ({Medium: 'c-medium', 'Needs records': 'c-records'}[c] || '');

// the city bar at the top: only opportunities for that government, and the totals above add up just those
const C = window.BCM && BCM.city;
let city = C ? C.get() : '';
const mine = o => !city || o.govs.includes(city);
function stats() {
  const xs = D.opportunities.filter(mine), sum = k => xs.reduce((a, o) => a + (o[k] || 0), 0);
  $('svM').textContent = big(sum('in_play')); $('svL').textContent = big(sum('savings_low')); $('svH').textContent = big(sum('savings_high'));
  $('svN').textContent = xs.filter(o => o.estimate === 'records').length.toLocaleString('en-US');
}

const EV = {};
D.evidence.forEach(r => { (EV[r.opportunity_id + '/' + r.group_id] ||= []).push(r); });
const O = D.opportunities;
const BY = Object.fromEntries(O.map(o => [o.id, o]));
const KINDS = ['All', ...new Set(O.map(o => o.lever))];
const params = new URLSearchParams(location.search);
let kind = KINDS.includes(params.get('k')) ? params.get('k') : 'All';

// One record: full label and figure on top, bar underneath. `inner` is the dark part, as a share of `outer`;
// `outer` is the bar's own length, as a share of the longest bar in the group.
function row(label, inner, outer, text, title) {
  const o = Math.max(0, Math.min(1, outer)), w = Math.max(0, Math.min(1, inner));
  return `<div class="sav-row" title="${esc(title || label)}"><div class="sav-row-hd"><span>${esc(label)}</span><b>${text}</b></div>`
    + `<i class="sav-track" style="width:${(o * 100).toFixed(1)}%"><em style="width:${(w * 100).toFixed(1)}%"></em></i></div>`;
}

function group(o, g) {
  const rows = EV[o.id + '/' + g.id] || [];
  if (!rows.length) return '';
  let body = '', key = '';
  if (g.kind === 'project_progress') {
    const mx = Math.max(...rows.map(r => r.compare || 0));
    key = '<div class="sav-key"><span><i></i>Spent so far</span><span><i class="out"></i>Total project cost</span></div>';
    body = rows.map(r => row(r.label, r.amount / r.compare, r.compare / mx, `${big(r.amount)} <small>of ${big(r.compare)}</small>`)).join('');
  } else if (g.kind === 'project_growth') {
    const mx = Math.max(...rows.map(r => r.compare || 0));
    key = '<div class="sav-key"><span><i></i>First firm figure</span><span><i class="out"></i>Final figure</span></div>';
    body = rows.map(r => row(r.label, r.amount / r.compare, r.compare / mx, `${big(r.amount)} → ${big(r.compare)} <small>${r.compare >= r.amount ? '+' : '−'}${pct(Math.abs(r.compare / r.amount - 1))}</small>`, `${r.amount_is} → ${r.compare_is}`)).join('');
  } else if (g.kind === 'budget_vs_spent') {
    key = '<div class="sav-key"><span><i></i>Spent</span><span><i class="out"></i>Budget</span></div>';
    body = rows.map(r => row(r.label, r.ratio, 1, `${pct(r.ratio)} <small>of ${big(r.compare)} spent</small>`)).join('');
  } else if (g.kind === 'ledger_share') {
    key = '<div class="sav-key"><span><i></i>CRA share</span><span><i class="out"></i>Total project cost</span></div>';
    body = rows.slice().sort((a, b) => a.ratio - b.ratio).map(r => row(r.label, r.ratio, 1, `${pct(r.ratio)} <small>of ${big(r.compare)}</small>`, `CRA paid ${big(r.amount)} of ${big(r.compare)}`)).join('');
  } else if (rows.some(r => r.per_unit != null)) {
    const mx = Math.max(...rows.map(r => r.per_unit || 0));
    body = rows.slice().sort((a, b) => b.per_unit - a.per_unit).map(r => row(r.label, 1, r.per_unit / mx, `${big(r.per_unit)} <small>/ ${esc(r.unit)}</small>`, `${big(r.amount)} over ${r.units} ${r.unit}s`)).join('');
  } else {
    const mx = Math.max(...rows.map(r => r.amount || 0));
    body = rows.slice().sort((a, b) => b.amount - a.amount).map(r => row(r.paid_to && r.paid_to.length < 40 ? `${r.paid_to}: ${r.label}` : r.label, 1, r.amount / mx, big(r.amount), r.amount_is)).join('');
  }
  return `<div class="sav-g"><h4>${esc(g.title)}</h4>${key}${body}${g.note ? `<p class="note">${esc(g.note)}</p>` : ''}</div>`;
}

function card(o) {
  const est = o.estimate === 'range'
    ? `<div class="sav-fig"><span>Potential savings</span><b>${big(o.savings_low)} – ${big(o.savings_high)}</b><small>${pct(o.rate_low)} to ${pct(o.rate_high)} of ${esc(o.in_play_is)}</small></div>`
    : `<div class="sav-fig"><span>Potential savings</span><b>${o.estimate === 'records' ? 'Needs records' : 'No estimate'}</b><small>${o.estimate === 'records' ? 'The records below come first' : 'A pattern to repeat, not a cut'}</small></div>`;
  const inPlay = o.in_play != null ? `<div class="sav-fig"><span>In play</span><b>${big(o.in_play)}</b><small>${esc(o.in_play_is)}</small></div>` : '';
  const overlaps = o.overlaps.length ? `<p class="sav-p muted">Overlaps with ${o.overlaps.map(id => `<a href="#${esc(id)}" data-go="${esc(id)}">${esc(BY[id]?.title || id)}</a>`).join(', ')}, so the two estimates shouldn't simply be added.</p>` : '';
  const reqs = o.requests.map(r => `<a class="pill sm" href="/records-request?gov=${encodeURIComponent(r.gk)}&d=${encodeURIComponent(r.q)}" title="${esc(r.q)}">Request the records</a>`).join(' ');
  const srcs = o.sources.slice(0, 6).map((u, i) => `<a href="${esc(u)}" target="_blank" rel="noopener">Source ${i + 1}</a>`).join(' ');
  return `<article class="sav-card" id="${esc(o.id)}">
    <div class="sav-top"><span class="sav-rank">#${o.rank}</span><span>${esc(o.government)}</span><span class="sav-chip">${esc(o.lever)}</span><span class="sav-chip ${conf(o.confidence)}">${esc(o.confidence)}${o.confidence === 'Needs records' || o.confidence === 'Model' ? '' : ' confidence'}</span></div>
    <h3 class="sav-n">${esc(o.title)}</h3>
    <div class="sav-figs">${inPlay}${est}</div>
    <p class="sav-p">${esc(o.basis)}</p>
    ${o.assumption ? `<p class="sav-p muted"><b>Assumes:</b> ${esc(o.assumption)}</p>` : ''}
    <p class="sav-p"><b>Next:</b> ${esc(o.next_step)}</p>
    ${overlaps}
    <div class="sav-ev">${o.groups.map(g => group(o, g)).join('')}</div>
    <div class="sav-more">${reqs}${srcs ? `<span class="muted">${srcs}</span>` : ''}</div>
  </article>`;
}

function filters() {
  const ks = ['All', ...new Set(O.filter(mine).map(o => o.lever))];
  if (!ks.includes(kind)) kind = 'All';
  $('svF').innerHTML = ks.map(k => `<button type="button" class="pill sm" aria-pressed="${k === kind}" data-k="${esc(k)}">${esc(k)}</button>`).join('');
}
function draw() {
  const all = O.filter(mine), list = all.filter(o => kind === 'All' || o.lever === kind);
  $('svList').innerHTML = list.map(card).join('') || `<p class="muted">${all.length ? 'None of this kind yet.' : `No opportunities found for ${esc(C.label(city))} yet.`}</p>`;
  $('svCount').textContent = `${list.length} of ${all.length}`;
  filters(); stats();
}
$('svF').addEventListener('click', ev => {
  const b = ev.target.closest('button[data-k]'); if (!b) return;
  kind = b.dataset.k; const q = new URLSearchParams(location.search);
  kind === 'All' ? q.delete('k') : q.set('k', kind);
  history.replaceState(null, '', (q.toString() ? '?' + q : location.pathname) + location.hash); draw();
});
$('svList').addEventListener('click', ev => {
  const a = ev.target.closest('a[data-go]'); if (!a) return;
  const o = BY[a.dataset.go]; if (o && !mine(o) && C) C.set('');
  if (o && kind !== 'All' && o.lever !== kind) { kind = 'All'; draw(); }
});
draw();
if (C) C.on(k => { if (k !== city) { city = k; draw(); } });
const h = decodeURIComponent(location.hash.slice(1));
if (BY[h] && !mine(BY[h]) && C) C.set('');
if (BY[h]) { if (kind !== 'All' && BY[h].lever !== kind) { kind = 'All'; draw(); } $(h)?.scrollIntoView(); }
})();
