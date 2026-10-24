/* Accountability console: project list, filters, one project's full timeline, flags, missing records and agency reply.
   Data: /data/accountability.json (built by site/accountability_page.py). ?p=<id> opens one project; filters stay in the link. */
(async () => {
const $ = id => document.getElementById(id);
let D;
try { const r = await fetch('/data/accountability.json'); if (!r.ok) throw new Error(r.status); D = await r.json(); }
catch (e) { $('acList').innerHTML = '<p class="muted">The projects could not be loaded. Please refresh the page.</p>'; return; }
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const big = n => n == null ? '—' : (n < 0 ? '−' : '') + (Math.abs(n) >= 1e6 ? '$' + (Math.abs(n) / 1e6).toFixed(1) + 'M' : Math.abs(n) >= 1e3 ? '$' + Math.round(Math.abs(n) / 1e3) + 'K' : '$' + Math.round(Math.abs(n)));
const usd = n => (n < 0 ? '−' : '') + '$' + Math.abs(n).toLocaleString('en-US', Number.isInteger(n) ? {} : {minimumFractionDigits: 2, maximumFractionDigits: 2});
const RULE = Object.fromEntries(D.rules.map(r => [r.id, r]));
const SEV = {high: 0, warn: 1, info: 2};
const STAGE = {budgeted: 'Budgeted', committed: 'Approved', design: 'In design', contract: 'Under contract', construction: 'Under construction', delayed: 'Delayed',
  'phase-done': 'Phase done', complete: 'Complete', closed: 'Closed out', sale: 'Land sale', removed: 'Removed', unknown: 'Status unclear'};
const KIND = {budget: 'Budget', estimate: 'Estimate', approval: 'Approved', award: 'Contract', change: 'Change order', vote: 'Vote', payment: 'Payment',
  spent: 'Spent to date', complete: 'Done', milestone: 'Milestone', sale: 'Sale'};
const SRC = {reviewed: 'Reviewed history', contracts: 'Contract', surtax: 'Sales tax project'};
const REPLY = {not_sent: 'Not yet sent to the agency', sent: 'Sent to the agency, awaiting a reply', replied: 'Agency replied'};
const P = D.projects, BY = Object.fromEntries(P.map(p => [p.id, p]));
const F = {y: $('acY'), q: $('acQ'), g: $('acG'), f: $('acF'), s: $('acS'), o: $('acO')};
const fmtD = d => { if (!d) return 'Date not stated'; const m = /^(\d{4})-(\d{2})(?:-(\d{2}))?$/.exec(d); if (!m) return d;
  const dt = new Date(+m[1], +m[2] - 1, +(m[3] || 1)); return dt.toLocaleDateString('en-US', m[3] ? {month: 'short', day: 'numeric', year: 'numeric'} : {month: 'short', year: 'numeric'}); };
const yr = s => s && s !== '9999' ? s.slice(0, 4) : '';
const hay = p => (p.n + ' ' + p.g + ' ' + (p.agency || '') + ' ' + (p.where || '') + ' ' + (p.vn || '') + ' ' + p.ev.map(x => (x.payee || '') + ' ' + x.t).join(' ')).toLowerCase();
P.forEach(p => { p._h = hay(p); });
/* year of activity: a project counts in every year it has a dated record up to today (planned dates ahead don't count).
   The page opens on the newest year with activity; ?y= or ?year= (a year or 'all') picks another. */
const TODAY = new Date().toISOString().slice(0, 10);
P.forEach(p => { p._ys = [...new Set(p.ev.filter(x => x.s && x.s !== '9999' && x.s <= TODAY).map(x => +x.s.slice(0, 4)))]; });
const YRS = [...new Set(P.flatMap(p => p._ys))].sort((a, b) => b - a);
F.y.innerHTML += YRS.map(y => `<option value="${y}">${y}</option>`).join('');
F.y.value = String(TT.startYear(YRS, TT.countBy(P.flatMap(p => p._ys))));
const big0 = big;
const inCity = p => !F.g.value || p.g === F.g.value;
function strip() { // the numbers at the top follow the city bar and the year picker
  const y = +F.y.value, ps = P.filter(p => inCity(p) && (!y || p._ys.includes(y)));
  $('acsN').textContent = ps.length.toLocaleString(); $('acsNl').textContent = y ? `projects active in ${y}` : 'projects tracked';
  $('acsM').textContent = big0(ps.reduce((a, p) => a + (p.money || 0), 0));
  $('acsF').textContent = ps.filter(p => p.flags.length).length.toLocaleString();
  $('acsG').textContent = ps.reduce((a, p) => a + p.gaps.length, 0).toLocaleString();
  $('acsR').textContent = ps.filter(p => p.reply.status === 'replied').length.toLocaleString();
}
let shown = 30, cur = [];

function chips(p, max = 3) {
  const f = p.flags.slice(0, max).map(x => `<span class="acct-chip ${x.sev}">${esc(RULE[x.r].title)}</span>`).join('');
  return f + (p.flags.length > max ? `<span class="acct-chip more">+${p.flags.length - max}</span>` : '');
}
function costBar(p) { // first firm figure vs the latest figure on the same basis
  const b = p.base?.a, n = p.now?.a;
  if (!b || !n) return '';
  const mx = Math.max(b, n), up = n > b, pct = (n - b) / b * 100;
  return `<div class="acct-cost" aria-label="${esc(p.base.t)} ${big(b)}, ${esc(p.now.t)} ${big(n)}">
    <div class="acct-cr"><span>${esc(p.base.t)}</span><i style="width:${(b / mx * 100).toFixed(1)}%"></i><b>${big(b)}</b></div>
    <div class="acct-cr now${up && pct > 10 ? ' up' : ''}"><span>${esc(p.now.t)}${p.now.open ? ' (still open)' : ''}</span><i style="width:${(n / mx * 100).toFixed(1)}%"></i><b>${big(n)} <em>${pct >= 0 ? '+' : '−'}${Math.abs(pct).toFixed(1)}%</em></b></div></div>`;
}
function card(p) {
  return `<article class="acct-card${p.sev ? ' s-' + p.sev : ''}" data-id="${esc(p.id)}">
    <button type="button" class="acct-open" aria-expanded="false" aria-controls="d-${esc(p.id)}">
      <span class="acct-top"><span class="acct-stage">${esc(STAGE[p.status] || p.status)}</span><span class="acct-src">${esc(SRC[p.src])}</span></span>
      <span class="acct-n">${esc(p.n)}</span>
      <span class="acct-m">${esc(p.g)}${p.vn ? ' · ' + esc(p.vn) : ''} · ${p.ev.length} record${p.ev.length === 1 ? '' : 's'}${p.first ? ` · ${yr(p.first)}${yr(p.last) !== yr(p.first) ? '–' + yr(p.last) : ''}` : ''}</span>
      <span class="acct-f">${p.flags.length ? chips(p) : '<span class="acct-chip none">No flags</span>'}<b class="acct-amt">${big(p.money)}</b></span>
    </button><div class="acct-d" id="d-${esc(p.id)}" hidden></div></article>`;
}
function phases(p) { // how far the record goes: planned, approved, under way, done
  const first = ks => p.ev.find(x => ks.includes(x.k) && x.s !== '9999');
  const steps = [['Planned', first(['budget', 'estimate'])], ['Approved', first(['approval', 'award', 'vote'])], ['Under way', first(['change', 'payment', 'spent'])],
    ['Done', ['complete', 'closed'].includes(p.status) || p.status === 'phase-done' ? first(['complete']) || {s: p.last} : null]];
  return `<ol class="acct-phase">${steps.map(([l, x]) => `<li class="${x ? 'on' : ''}"><b>${l}</b><span>${x ? esc(yr(x.s) || '') : '—'}</span></li>`).join('')}</ol>`;
}
function detail(p) {
  const ev = p.ev.map(x => {
    const src = x.u ? `<a class="src" href="${esc(x.u)}" target="_blank" rel="noopener">${x.news ? 'News report' : 'Source'}</a>` : '<span class="muted">No link</span>';
    const who = x.payee ? (x.vid ? `<a href="/public-money/vendors/${esc(x.vid)}">${esc(x.payee)}</a>` : esc(x.payee)) : '';
    const mem = x.k === 'vote' && x.members && Object.keys(x.members).length ? `<details class="acct-mem"><summary>How each member voted</summary>${Object.entries(x.members).map(([n, v]) => `${esc(n)}: <b>${esc(v)}</b>`).join(' · ')}</details>` : '';
    return `<li class="k-${x.k}${x.side ? ' side' : ''}"><span class="acct-when">${esc(fmtD(x.d))}</span><span class="acct-what"><em class="acct-k">${esc(KIND[x.k] || x.k)}</em>${x.a != null ? ` <b>${x.approx ? 'about ' : ''}${usd(x.a)}</b>` : ''}
      <span>${esc(x.t)}</span>${who ? `<span class="acct-who">Paid to / with: ${who}</span>` : ''}${mem}
      <span class="acct-s">${src}${x.via ? ' <span class="muted">(figure from the notes on this source record)</span>' : ''}${x.side ? ' <span class="muted">· related cost</span>' : ''}</span></span></li>`;
  }).join('');
  const fl = p.flags.length ? `<ul class="plain acct-flags">${p.flags.map(f => `<li class="${f.sev}"><span class="acct-chip ${f.sev}">${f.sev === 'high' ? 'High' : f.sev === 'warn' ? 'Question' : 'Note'}</span> <b>${esc(RULE[f.r].title)}.</b> ${esc(f.note)} <a href="#rule-${f.r}" class="small">The rule</a></li>`).join('')}</ul>` : '<p class="small muted">No rule raised a question for this project.</p>';
  const gaps = p.gaps.length ? `<ul class="plain acct-gl">${p.gaps.map(g => `<li>${esc(g.q)} <a class="pill sm" href="/records-request?gov=${encodeURIComponent(g.gk)}&d=${encodeURIComponent(g.q)}">Request this record</a></li>`).join('')}</ul>` : '';
  const r = p.reply, rep = r.status === 'replied' ? `<blockquote class="acct-rep">${esc(r.text || '')}${r.u ? ` <a href="${esc(r.u)}" target="_blank" rel="noopener">Read the reply</a>` : ''}<cite>${esc(fmtD(r.date))}</cite></blockquote>` : '';
  const links = [p.vendor ? `<a href="/public-money/vendors/${esc(p.vendor)}">Everything on ${esc(p.vn)}</a>` : '', p.surtax ? `<a href="/public-money/sales-tax-projects?p=${esc(p.surtax)}">On the sales tax map</a>` : '',
    /CRA/.test(p.agency || '') ? `<a href="/public-money/cra-spending">CRA Spending ledger</a>` : '', p.src === 'contracts' ? `<a href="/public-money/contracts">All contracts and change orders</a>` : ''].filter(Boolean).join(' · ');
  return `<div class="acct-body">
    ${p.what || p.where || p.funding ? `<p class="small">${p.what ? esc(p.what) + ' ' : ''}${p.where ? `<b>Where:</b> ${esc(p.where)}. ` : ''}${p.funding ? `<b>Paid for by:</b> ${esc(p.funding)}.` : ''}</p>` : ''}
    ${phases(p)}${costBar(p)}${p.total ? `<p class="small acct-tot"><b>${esc(p.total.t[0].toUpperCase() + p.total.t.slice(1))}:</b> ${big(p.total.a)}. A project total includes design, land and inspection, so it is shown beside the contract, not compared with it.</p>` : ''}
    <h3>Questions</h3>${fl}
    <h3>Timeline</h3><ol class="acct-tl">${ev}</ol>
    ${gaps ? `<h3>Records that would answer them</h3>${gaps}` : ''}
    <h3>Agency reply</h3><p class="small"><span class="acct-rs ${r.status}">${esc(REPLY[r.status])}</span>${r.sent ? ` · sent ${esc(fmtD(r.sent))}` : ''}</p>${rep}
    ${links ? `<p class="small">${links}</p>` : ''}
    <p class="small"><button type="button" class="pill sm acct-share" data-id="${esc(p.id)}">Copy link to this project</button> <a class="small" href="/about#contact">Send a correction</a></p></div>`;
}
function open(el, on, scroll) {
  const p = BY[el.dataset.id], d = el.querySelector('.acct-d'), b = el.querySelector('.acct-open');
  if (on && !d.innerHTML) d.innerHTML = detail(p);
  d.hidden = !on; b.setAttribute('aria-expanded', String(on)); el.classList.toggle('open', on);
  const u = new URL(location.href); on ? u.searchParams.set('p', p.id) : u.searchParams.delete('p'); history.replaceState(null, '', u);
  if (on && scroll) el.scrollIntoView({block: 'start'});
}
const ORDER = {
  flags: (a, b) => (SEV[a.sev] ?? 9) - (SEV[b.sev] ?? 9) || b.flags.length - a.flags.length || (b.money || 0) - (a.money || 0),
  money: (a, b) => (b.money || 0) - (a.money || 0),
  new: (a, b) => (b.last || '').localeCompare(a.last || ''),
  growth: (a, b) => (b.growth ?? -1e9) - (a.growth ?? -1e9)};
function filt(push = true) {
  const q = F.q.value.trim().toLowerCase(), g = F.g.value, f = F.f.value, s = F.s.value, y = +F.y.value;
  cur = P.filter(p => (!y || p._ys.includes(y)) && (!g || p.g === g) && (!s || p.src === s) && (!f || (f === 'any' ? p.flags.length : p.flags.some(x => x.r === f))) && (!q || p._h.includes(q)));
  cur.sort(ORDER[F.o.value] || ORDER.flags);
  const fl = cur.filter(p => p.flags.length).length;
  $('acCount').textContent = `${cur.length} project${cur.length === 1 ? '' : 's'} · ${fl} with a question · ${big(cur.reduce((a, p) => a + (p.money || 0), 0))}`;
  $('acList').innerHTML = cur.length ? cur.slice(0, shown).map(card).join('') : '<p class="muted">No projects match. Try clearing a filter.</p>';
  $('acMore').hidden = cur.length <= shown;
  strip(); gapList();
  if (push) { const u = new URL(location.href); [['y', F.y.value || 'all'], ['q', q], ['g', ''], ['f', f], ['s', s], ['o', F.o.value === 'flags' ? '' : F.o.value]].forEach(([k, v]) => v ? u.searchParams.set(k, v) : u.searchParams.delete(k)); history.replaceState(null, '', u); }
}
$('acList').addEventListener('click', ev => {
  const sh = ev.target.closest('.acct-share');
  if (sh) { const u = location.origin + location.pathname + '?p=' + encodeURIComponent(sh.dataset.id); navigator.clipboard?.writeText(u).then(() => { sh.textContent = 'Link copied'; }, () => { prompt('Copy this link', u); }); return; }
  const b = ev.target.closest('.acct-open'); if (!b) return;
  const el = b.closest('.acct-card'); open(el, b.getAttribute('aria-expanded') !== 'true');
});
Object.values(F).forEach(x => x.addEventListener('input', () => { shown = 30; filt(); }));
$('acMore').addEventListener('click', () => { shown += 40; filt(false); });
$('acCsv').addEventListener('click', () => {
  const head = ['project', 'government', 'agency', 'kind', 'stage', 'first_figure', 'first_figure_is', 'latest_figure', 'latest_figure_is', 'growth_pct', 'project_total', 'flags', 'records_missing', 'agency_reply', 'link'];
  TT.csv('baycounty-accountability', head, cur.map(p => [p.n, p.g, p.agency, SRC[p.src], STAGE[p.status] || p.status, p.base?.a ?? '', p.base?.t ?? '', p.now?.a ?? '', p.now?.t ?? '', p.growth ?? '', p.total?.a ?? '',
    p.flags.map(f => RULE[f.r].title + ': ' + f.note).join(' | '), p.gaps.length, REPLY[p.reply.status], location.origin + location.pathname + '?p=' + p.id]));
});
// missing records, for the projects the city bar and the year picker show
const GALL = P.flatMap(p => p.gaps.map(g => ({...g, p})));
function gapList() {
  const y = +F.y.value, G = GALL.filter(g => inCity(g.p) && (!y || g.p._ys.includes(y)));
  $('acGapCount').textContent = `${G.length} request${G.length === 1 ? '' : 's'}`;
  $('acGaps').innerHTML = G.length ? G.map(g => `<li><span class="muted small">${esc(g.p.g)} · <a href="?p=${esc(g.p.id)}#list" data-go="${esc(g.p.id)}">${esc(g.p.n)}</a></span><br>${esc(g.q)} <a class="pill sm" href="/records-request?gov=${encodeURIComponent(g.gk)}&d=${encodeURIComponent(g.q)}">Request this record</a></li>`).join('') : '<li class="muted">No records outstanding for these projects.</li>';
}
$('acGaps').addEventListener('click', ev => { const a = ev.target.closest('[data-go]'); if (!a) return; ev.preventDefault(); go(a.dataset.go); });
function go(id) { // show one project, clearing filters that would hide it (the city only when it's another city's project)
  const p = BY[id]; if (!p) return;
  Object.entries(F).forEach(([k, x]) => { if (k !== 'o' && k !== 'g') x.value = ''; });
  if (F.g.value && F.g.value !== p.g) { if (window.BCM && BCM.city) BCM.city.set(''); F.g.value = ''; }
  shown = Math.max(shown, cur.length); filt(false);
  let el = document.querySelector(`.acct-card[data-id="${CSS.escape(id)}"]`);
  if (!el) { shown = P.length; filt(false); el = document.querySelector(`.acct-card[data-id="${CSS.escape(id)}"]`); }
  if (el) open(el, true, true);
}
const P0 = new URLSearchParams(location.search);
[['q', 'q'], ['f', 'f'], ['s', 's'], ['o', 'o']].forEach(([k, f]) => { const v = P0.get(k); if (v != null) F[f].value = v; });
{ const v = P0.get('y'); if (v != null) F.y.value = v === 'all' ? '' : v; else if (P0.get('q')) F.y.value = ''; }
filt(false);
// the city bar at the top sets #acG (data-city-link; old ?g= links are read by the bar); keep the year on one the city has projects in
if (window.BCM && BCM.city) BCM.city.on(k => BCM.city.fitYear(F.y, P.filter(p => BCM.city.has(k, p.gk)).flatMap(p => p._ys)));
if (P0.get('p') && BY[P0.get('p')]) go(P0.get('p'));
})();
