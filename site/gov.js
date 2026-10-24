/* A government's page (/governments/<slug>): the dashboards' own data, narrowed to this government, for one year.
   Reads the same published files the dashboards use (contracts, CRA ledger, projects, sales tax, FEMA, votes,
   savings) and fills the sections the page marks with data-gx. The Year picker in the bar at the top drives
   every section; "All years" shows everything. Each section links to its full dashboard on the same city and year. */
(async () => {
const G = window.GOVPAGE; if (!G) return;
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const money = n => n == null || isNaN(n) ? '—' : Math.abs(n) >= 1e9 ? '$' + (n / 1e9).toFixed(1) + 'B' : Math.abs(n) >= 1e6 ? '$' + (n / 1e6).toFixed(1) + 'M'
  : Math.abs(n) >= 1e3 ? '$' + Math.round(n / 1e3) + 'K' : '$' + Math.round(n).toLocaleString('en-US');
const usd = n => n == null ? '—' : '$' + Math.round(n).toLocaleString('en-US');
const plural = (n, w, ws) => `${n.toLocaleString('en-US')} ${n === 1 ? w : (ws || w + 's')}`;
const yr = s => { const m = /(19|20)\d{2}/.exec(s || ''); return m ? +m[0] : null; };
const nice = d => { if (!d) return ''; const t = new Date(d.slice(0, 10) + 'T12:00'); return isNaN(t) ? d : t.toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'}); };
const get = u => fetch(u).then(r => r.ok ? r.json() : null).catch(() => null);
const K = G.key, has = v => BCM.city.has(K, v);

const [CT, P1, P2, AC, ST, FM, VT, SV] = await Promise.all(['/data/contracts-page.json', '/data/cra-pay-1.json', '/data/cra-pay-2.json',
  '/data/accountability.json', '/data/surtax-projects.json', '/data/michael-page.json', '/data/votes-page.json', '/data/savings.json'].map(get));

/* ---------- this government's rows, each with the years it counts in ---------- */
const S = {};
S.contracts = (CT?.rows || []).filter(r => has(r.g)).map(r => ({...r, ys: [yr(r.d)].filter(Boolean)}));
S.cra = G.cra ? [...(P1 || []), ...(P2 || [])].filter(p => p.cra === G.cra).map(p => ({...p, ys: TT.yearsIn(p.when)})) : [];
const span = (a, b) => { a = yr(a); b = yr(b) || a; if (!a) return []; const o = []; for (let y = a; y <= Math.min(b, a + 30); y++) o.push(y); return o; };
S.projects = (AC?.projects || []).filter(p => p.gk === K).map(p => ({...p, ys: span(p.first, p.last)}));
S.salestax = (ST || []).filter(p => has(p.g)).map(p => ({...p, ys: [...new Set([...Object.keys(p.sfy || {}).map(Number), ...TT.yearsIn(p.y)])]}));
S.fema = (FM?.rows || []).filter(r => has(r.a)).map(r => ({...r, ys: [yr(r.d1)].filter(Boolean)}));
S.votes = (VT?.votes || []).filter(v => v.g === K).map(v => ({...v, ys: [yr(v.d)].filter(Boolean)}));
const savings = (SV?.opportunities || []).filter(o => (o.govs || []).includes(K));

/* ---------- the year picker ---------- */
const ysel = $('#gxYear');
const allYs = Object.values(S).flatMap(rs => rs.flatMap(r => r.ys));
const YRS = [...new Set(allYs)].filter(y => y >= 2000).sort((a, b) => b - a);
ysel.innerHTML = '<option value="all">All years</option>' + YRS.map(y => `<option value="${y}">${y}</option>`).join('');
// opens on the newest year this government has a good share of records for
// (planned project years run into the future, so they don't pick the year; a dated record does)
const doneYs = [...S.contracts, ...S.cra, ...S.votes].flatMap(r => r.ys).filter(y => y >= 2000 && y <= new Date().getFullYear());
ysel.value = String(doneYs.length ? TT.startYear([...new Set(doneYs)], TT.countBy(doneYs)) : TT.startYear(YRS, TT.countBy(allYs)) || 'all');
const inYear = r => ysel.value === 'all' || r.ys.includes(+ysel.value);
const ylabel = () => ysel.value === 'all' ? 'all years' : ysel.value;
const dash = (path, extra = '') => `${path}?gov=${K}${ysel.value !== 'all' ? '&year=' + ysel.value : '&year=all'}${extra}`;

/* ---------- section scaffolding ---------- */
const kpi = (l, v, s = '') => `<div class="kpi"><span class="eyebrow">${l}</span><span class="v">${v}</span><span class="s">${s}</span></div>`;
function table(head, rows, n = 8) {
  if (!rows.length) return '';
  const more = rows.length > n;
  return `<div class="tablewrap"><table class="tx-table gx-t" data-tt="off"><thead><tr>${head.map(h => `<th scope="col"${/^(Amount|Cost|Federal|Money)/.test(h) ? ' class="num"' : ''}>${h}</th>`).join('')}</tr></thead>
    <tbody>${rows.map((r, i) => `<tr${i >= n ? ' hidden data-more' : ''}>${r}</tr>`).join('')}</tbody></table></div>
    ${more ? `<button type="button" class="linkbtn gx-more">Show all ${rows.length.toLocaleString('en-US')}</button>` : ''}`;
}
const src = u => u ? ` <a class="src" href="${esc(u)}" target="_blank" rel="noopener">Source</a>` : '';
function fill(id, {sub, kpis, body, link, empty}) {
  const sec = document.getElementById(id); if (!sec) return;
  sec.hidden = false;
  $('[data-gx-sub]', sec).textContent = sub || '';
  $('[data-gx-kpis]', sec).innerHTML = kpis || '';
  $('[data-gx-kpis]', sec).hidden = !kpis;
  $('[data-gx-body]', sec).innerHTML = body || `<p class="muted gx-none">${empty} <button type="button" class="linkbtn" data-allyears>See all years</button></p>`;
  $('[data-gx-link]', sec).innerHTML = link || '';
  $$('.gx-more', sec).forEach(b => b.onclick = () => { $$('tr[data-more]', sec).forEach(t => t.hidden = false); b.remove(); });
}
const gone = id => { const s = document.getElementById(id); if (s) s.remove(); $$(`.scope a[href="#${id}"], .gx-jump a[href="#${id}"]`).forEach(a => a.remove()); };

/* ---------- renderers ---------- */
function contracts() {
  if (!S.contracts.length) return gone('contracts');
  const rs = S.contracts.filter(inYear).sort((a, b) => (b.a || 0) - (a.a || 0)), tot = rs.reduce((s, r) => s + (r.a || 0), 0);
  const comp = rs.filter(r => /^competitive/i.test(r.m || '')).length;
  fill('contracts', {
    sub: `${plural(rs.length, 'major contract')} approved in ${ylabel()}`,
    kpis: rs.length ? kpi('Awarded', money(tot), plural(rs.length, 'contract')) + kpi('Competitively bid', rs.length ? Math.round(comp / rs.length * 100) + '%' : '—', `${comp} of ${rs.length}`)
      + kpi('Largest', money(rs[0].a), esc(rs[0].v)) : '',
    body: table(['Company', 'For', 'Amount', 'How awarded', 'Approved'], rs.map(r =>
      `<td class="wrap"><a href="/public-money/contracts?company=${encodeURIComponent(r.id)}#company">${esc(r.v)}</a></td><td class="wrap small">${esc(r.p)}</td><td class="num">${usd(r.a)}</td><td class="small">${esc(r.m)}</td><td class="small nowrap">${esc(nice(r.d))}${src(r.u)}</td>`)),
    empty: `No major contracts recorded for ${esc(G.short)} in ${ylabel()}.`,
    link: `<a href="${dash('/public-money/contracts')}#all">All ${esc(G.short)} contracts, change orders and payments</a>`,
  });
}
function cra() {
  if (!G.cra) return gone('cra');
  const rs = S.cra.filter(inYear), counted = rs.filter(p => p.count && p.amount);
  const spent = counted.filter(p => /^(Spent|Committed)$/.test(p.status)).reduce((s, p) => s + p.amount, 0);
  const planned = counted.filter(p => p.status === 'Budgeted').reduce((s, p) => s + p.amount, 0);
  const top = rs.slice().sort((a, b) => (b.count - a.count) || (b.amount || 0) - (a.amount || 0));
  fill('cra', {
    sub: `${esc(G.craName)} · ${plural(rs.length, 'record')} in ${ylabel()}`,
    kpis: rs.length ? kpi('Spent or committed', money(spent), 'Payments and awards, each dollar once') + kpi('Budgeted', money(planned), 'Plans, not yet confirmed as paid') + kpi('Records', rs.length, `${new Set(rs.map(p => p.district)).size} district${new Set(rs.map(p => p.district)).size === 1 ? '' : 's'}`) : '',
    body: table(['Paid to', 'For', 'District', 'Status', 'Amount'], top.map(p =>
      `<td class="wrap">${esc(p.payee)}</td><td class="wrap small">${esc(p.purpose)}${src(p.url)}</td><td class="small">${esc(p.district)}</td><td class="small">${esc(p.status)}${p.count ? '' : ' <span class="muted">(not in totals)</span>'}</td><td class="num">${p.amount ? usd(p.amount) : '—'}</td>`)),
    empty: `No CRA records for ${ylabel()}.`,
    link: `<a href="${dash('/public-money/cra-spending')}">Map and full ledger</a> · <a href="/public-money/cra-network?gov=${K}">Who the CRA paid, and their campaign gifts</a>`,
  });
}
const STL = {closed: 'Closed out', complete: 'Complete', completed: 'Completed', under_construction: 'Under construction', under_contract: 'Under contract', budgeted: 'Budgeted', planned: 'Planned', in_progress: 'In progress', not_started: 'Not started', unknown: 'Status unknown'};
const stl = s => STL[s] || String(s || '').replace(/_/g, ' ').replace(/^./, c => c.toUpperCase());
function projects() {
  const a = S.projects.filter(inYear), t = S.salestax.filter(inYear), f = S.fema.filter(inYear);
  if (!S.projects.length && !S.salestax.length && !S.fema.length) return gone('projects');
  const parts = [];
  if (S.projects.length) {
    const flagged = a.filter(p => (p.flags || []).length);
    parts.push(`<h3 class="h4">Big projects, budget to close-out</h3>` + (a.length ? `<div class="gx-cards">${a.sort((x, y) => (y.flags || []).length - (x.flags || []).length || (y.money || 0) - (x.money || 0)).slice(0, 6).map(p =>
      `<a class="gx-card" href="/public-money/accountability?gov=${K}&p=${encodeURIComponent(p.id)}"><span class="eyebrow">${esc(stl(p.status))}</span><b>${esc(p.n)}</b><span class="muted small">${money(p.money)}${p.growth ? ` · ${p.growth > 0 ? '+' : ''}${p.growth}% since award` : ''}</span>${(p.flags || []).length ? `<span class="badge warn">${plural(p.flags.length, 'question')}</span>` : ''}</a>`).join('')}</div>
      <p class="small muted">${plural(a.length, 'project')} in ${ylabel()}, ${flagged.length} with an open question. <a href="${dash('/public-money/accountability')}">See every project</a></p>` : `<p class="muted small">No tracked projects active in ${ylabel()}.</p>`));
  }
  if (S.salestax.length) {
    const n = s => t.filter(p => p.s === s).length;
    parts.push(`<h3 class="h4">Half-cent sales tax projects</h3>` + (t.length ? `<p class="gx-line"><b>${plural(t.length, 'project')}</b> in ${ylabel()}: ${n('completed')} completed · ${n('in_progress')} in progress · ${n('not_started')} not started</p>` +
      table(['Project', 'Type', 'Status', 'Cost'], t.sort((x, y) => (y.k || 0) - (x.k || 0)).map(p => `<td class="wrap">${esc(p.n)}</td><td class="small">${esc(p.c)}</td><td class="small">${esc(stl(p.s))}${p.s === 'in_progress' && p.p != null ? ` (${p.p}%)` : ''}</td><td class="num">${p.k ? usd(p.k) : '—'}</td>`), 5)
      + `<p class="small"><a href="${dash('/public-money/sales-tax-projects')}">Map of every project</a></p>` : `<p class="muted small">No sales tax projects in ${ylabel()}.</p>`));
  }
  if (S.fema.length) {
    const fed = f.reduce((s, r) => s + (r.f || 0), 0);
    parts.push(`<h3 class="h4">Hurricane Michael rebuilding (FEMA)</h3>` + (f.length ? `<p class="gx-line"><b>${money(fed)}</b> federal share for ${plural(f.length, 'project')} first funded in ${ylabel()}</p>` +
      table(['Project', 'Status', 'Federal share'], f.sort((x, y) => (y.f || 0) - (x.f || 0)).map(r => `<td class="wrap">${esc(r.t)}</td><td class="small">${esc(r.st)}</td><td class="num">${usd(r.f)}</td>`), 5)
      + `<p class="small"><a href="${dash('/public-money/hurricane-michael')}#ledger">Every FEMA project</a></p>` : `<p class="muted small">No FEMA projects first funded in ${ylabel()}.</p>`));
  }
  fill('projects', {sub: `Active or funded in ${ylabel()}`, body: parts.join('')});
}
function votes() {
  if (!S.votes.length) return gone('votes');
  const rs = S.votes.filter(inYear).sort((a, b) => (b.d || '').localeCompare(a.d || '')), sp = rs.filter(v => v.x);
  const card = v => `<li class="fd vt"><span class="vt-meta muted">${esc(v.dn)} · ${esc(VT.cat[v.c] || v.c)}${v.a ? ' · ' + usd(v.a) : ''} · ${esc(v.t)} ${esc(v.o || '')}</span><div class="vt-h">${esc(v.h)}</div>${Object.keys(v.m).length ? `<p class="small">Voted no: ${esc(Object.entries(v.m).filter(([, x]) => x === 'no').map(([n]) => n).join(', ') || 'none recorded')}</p>` : ''}${v.u ? `<a class="src" href="${esc(v.u)}" target="_blank" rel="noopener">${esc(v.ul || 'Minutes')}</a>` : ''}</li>`;
  fill('votes', {
    sub: `${plural(rs.length, 'money vote')} recorded in ${ylabel()}`,
    kpis: rs.length ? kpi('Votes recorded', rs.length, 'Budgets, tax rates, contracts, land, borrowing') + kpi('Split votes', sp.length, rs.length ? Math.round(sp.length / rs.length * 100) + '% not unanimous' : '')
      + kpi('Money voted on', money(rs.reduce((s, v) => s + (v.a || 0), 0)), 'where the minutes give an amount') : '',
    body: rs.length ? `<h3 class="h4">${sp.length ? 'Most recent split votes' : 'Most recent votes'}</h3><ol class="findings">${(sp.length ? sp : rs).slice(0, 5).map(card).join('')}</ol>` : '',
    empty: `No money votes recorded in ${ylabel()}.`,
    link: `<a href="${dash('/public-money/votes', `&g=${K}`)}#all">Every ${esc(G.short)} vote, by member</a>`,
  });
}
function savingsSec() {
  if (!savings.length) return gone('savings');
  fill('savings', {
    sub: `${plural(savings.length, 'place')} to look, from records on this site`,
    body: `<div class="gx-cards">${savings.slice(0, 6).map(o => `<a class="gx-card" href="/public-money/savings?gov=${K}#${encodeURIComponent(o.id)}"><span class="eyebrow">${esc(o.lever)}</span><b>${esc(o.title)}</b><span class="muted small">${o.savings_low ? `${money(o.savings_low)}${o.savings_high && o.savings_high !== o.savings_low ? '–' + money(o.savings_high) : ''} possible` : ''}${o.in_play ? ` · ${money(o.in_play)} in play` : ''}</span></a>`).join('')}</div>`,
    link: `<a href="/public-money/savings?gov=${K}">Savings finder</a>`,
  });
}

/* ---------- "this year" strip at the top ---------- */
function glance() {
  const box = $('#gxGlance'); if (!box) return;
  const c = S.contracts.filter(inYear), ra = S.cra.filter(inYear), r = ra.filter(p => p.count && /^(Spent|Committed)$/.test(p.status)), v = S.votes.filter(inYear);
  const pr = S.projects.filter(inYear).length + S.salestax.filter(inYear).length;
  const t = [];
  if (S.contracts.length) t.push(['#contracts', 'Contracts awarded', money(c.reduce((s, x) => s + (x.a || 0), 0)), plural(c.length, 'contract')]);
  if (G.cra) t.push(['#cra', 'CRA spent or committed', money(r.reduce((s, x) => s + (x.amount || 0), 0)), plural(ra.length, 'CRA record')]);
  if (S.votes.length) t.push(['#votes', 'Money votes', v.length.toLocaleString('en-US'), `${v.filter(x => x.x).length} split`]);
  if (S.projects.length || S.salestax.length) t.push(['#projects', 'Projects active', pr.toLocaleString('en-US'), 'tracked and sales tax']);
  $('#gxGlanceH').textContent = ysel.value === 'all' ? 'Across every year on record' : `In ${ysel.value}`;
  box.innerHTML = t.map(([h, l, v2, s]) => `<a class="kpi gx-k" href="${h}"><span class="eyebrow">${l}</span><span class="v">${v2}</span><span class="s">${s}</span></a>`).join('');
  box.closest('section').hidden = !t.length;
}

function render() {
  contracts(); cra(); projects(); votes(); glance();
  BCM.urlState.set({year: ysel.value});
}
ysel.addEventListener('change', render);
document.addEventListener('click', e => { if (e.target.closest('[data-allyears]')) { ysel.value = 'all'; render(); } });
savingsSec(); render();
$$('[data-gx-loading]').forEach(el => el.remove());
// the section links in the bar follow the reader down the page
const links = $$('.gx-jump a'), io = new IntersectionObserver(es => es.forEach(en => { if (en.isIntersecting) links.forEach(a => a.classList.toggle('on', a.getAttribute('href') === '#' + (en.target.id || en.target.querySelector('h2[id]')?.id))); }), {rootMargin: '-35% 0px -60% 0px'});
links.forEach(a => { const t = document.getElementById(a.getAttribute('href').slice(1)); const sec = t && (t.closest('section') || t); if (sec) io.observe(sec); });
})();
