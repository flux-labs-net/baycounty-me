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

// this government's budget, tax rate, actuals, residents, debt and staff by fiscal year: from the database through the API,
// or the same dataset's published file if the API can't be reached
const yearsFor = async () => {
  const api = await get(`/api/v1/datasets/government-years?gov_id=${encodeURIComponent(K)}&sort=fiscal_year&limit=200`);
  if (api && Array.isArray(api.data)) return api.data;
  const f = await get('/downloads/government-years.json');
  return (Array.isArray(f) ? f : []).filter(r => r.gov_id === K);
};
// who held each elected seat, term by term (officeholder-terms dataset), the same way
const termsFor = async () => {
  const api = await get(`/api/v1/datasets/officeholder-terms?gov_id=${encodeURIComponent(K)}&limit=200`);
  if (api && Array.isArray(api.data)) return api.data;
  const f = await get('/downloads/officeholder-terms.json');
  return (Array.isArray(f) ? f : []).filter(r => r.gov_id === K);
};
const [CT, P1, P2, AC, ST, FM, VT, SV, GYr, OHr] = await Promise.all([...['/data/contracts-page.json', '/data/cra-pay-1.json', '/data/cra-pay-2.json',
  '/data/accountability.json', '/data/surtax-projects.json', '/data/michael-page.json', '/data/votes-page.json', '/data/savings.json'].map(get), yearsFor(), termsFor()]);
const OH = (OHr || []).slice().sort((a, b) => a.seat_order - b.seat_order || a.term_order - b.term_order);
const GY = (GYr || []).slice().sort((a, b) => a.fiscal_year - b.fiscal_year);

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
const allYs = [...Object.values(S).flatMap(rs => rs.flatMap(r => r.ys)), ...GY.map(r => r.fiscal_year)];
// every fiscal year the officeholder terms cover is pickable too, so each year back to 2015 shows who was in office
const ohYs = OH.length ? Array.from({length: new Date().getFullYear() - 2014}, (_, i) => 2015 + i) : [];
const YRS = [...new Set([...allYs, ...ohYs])].filter(y => y >= 2000).sort((a, b) => b - a);
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
const gone = id => { const s = document.getElementById(id); if (s) s.remove(); $$(`.ui-tiles a[href="#${id}"], .ui-mini a[href="#${id}"]`).forEach(a => a.remove()); };

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
      `<td class="wrap"><a href="${esc(r.e && window.BC ? BC.href(r.e) : '/public-money/contracts?company=' + encodeURIComponent(r.id) + '#company')}">${esc(r.v)}</a></td><td class="wrap small">${esc(r.p)}</td><td class="num">${usd(r.a)}</td><td class="small">${esc(r.m)}</td><td class="small nowrap">${esc(nice(r.d))}${src(r.u)}</td>`)),
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
      `<td class="wrap">${p.vp && window.BC ? BC.a('vendor:' + p.vp, p.payee) : esc(p.payee)}</td><td class="wrap small">${esc(p.purpose)}${src(p.url)}</td><td class="small">${esc(p.district)}</td><td class="small">${esc(p.status)}${p.count ? '' : ' <span class="muted">(not in totals)</span>'}</td><td class="num">${p.amount ? usd(p.amount) : '—'}</td>`)),
    empty: `No CRA records for ${ylabel()}.`,
    link: `<a href="${dash('/public-money/cra-spending')}">Map and full ledger</a> · <a href="/connections?gov=${K}">Who the city and its CRA paid, and campaign gifts</a>`,
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

/* ---------- top cards: budget, tax rate, residents, debt, staff for the fiscal year in the bar ----------
   Year 2026 in the picker means fiscal year 2026 (Oct 2025 to Sep 2026; schools Jul to Jun). "All years" shows the
   current fiscal year. A figure with no record for that year says so; it never falls back to another year's number.
   Mirrors year_cards() in site/gov_pages.py, which draws the same cards for the current fiscal year before this runs. */
// icon and tint per card label: the same table as KPI_ICON in site/gov_pages.py
const KPI_ICON = {'Residents': ['users', 'teal'], 'Budget': ['wallet', 'blue'], 'Spent (audited)': ['wallet', 'blue'], 'Property tax rate': ['percent', 'amber'],
  'School tax rate': ['percent', 'amber'], 'Debt': ['dollar', 'salmon'], 'Employees': ['briefcase', 'blue'], 'Typical utility bill': ['drop', 'teal']};
const ico = (n, t) => { const i = `<span class="ico i-${n}" aria-hidden="true"></span>`; return t ? `<span class="ui-ti t-${t}">${i}</span>` : i; };
const topKpi = (l, v, s = '', no = false) => { const [n, t] = KPI_ICON[l] || ['grid', 'blue'];
  return `<div class="kpi ui-k${no ? ' kpi-none' : ''}"><span class="kh">${ico(n, t)}<span class="eyebrow">${l}</span></span><span class="v">${v}</span><span class="s">${s}</span></div>`; };
const topBox = $('#gxTop'), keep = topBox ? $$('[data-static]', topBox).map(x => x.outerHTML).join('') : '';
const curFY = (() => { const d = new Date(), st = G.fyStart || 10; return d.getMonth() + 1 >= st ? d.getFullYear() + 1 : d.getFullYear(); })();
function topCards() {
  if (!topBox || !GY.length) return;
  const by = Object.fromEntries(GY.map(r => [r.fiscal_year, r]));
  let fy = ysel.value === 'all' ? curFY : +ysel.value;
  if (ysel.value === 'all' && !by[fy]) fy = GY[GY.length - 1].fiscal_year;
  const r = by[fy] || {}, prev = by[fy - 1] || {}, has = k => GY.some(x => x[k] != null), schools = K === 'schools';
  const none = (l, why) => topKpi(l, 'No data', why, true);
  const kpi = topKpi;
  const out = [];
  if (!schools && has('population')) out.push(r.population ? kpi('Residents', r.population.toLocaleString('en-US'), r.population_year === fy ? `FY${fy} state figure` : `${r.population_year} state estimate`) : none('Residents', `No count for FY${fy}`));
  if (r.budget_total) {
    const bits = [`FY${fy} · ${esc(r.budget_status || 'adopted')}`];
    if (r.budget_per_resident) bits.push(`${usd(r.budget_per_resident)} per resident`);
    if (prev.budget_total) { const ch = (r.budget_total / prev.budget_total - 1) * 100; bits.push(`${ch >= 0 ? 'up' : 'down'} ${Math.abs(ch).toFixed(0)}% from FY${fy - 1}`); }
    out.push(kpi('Budget', money(r.budget_total), bits.join(' · ') + src(r.budget_source_url)));
  } else if (r.actual_spending) out.push(kpi('Spent (audited)', money(r.actual_spending), `FY${fy} actual spending; no adopted budget on file` + src(r.actuals_source_url)));
  else if (has('budget_total') || has('actual_spending')) out.push(none('Budget', `No FY${fy} budget on file`));
  if (has('millage')) {
    const l = schools ? 'School tax rate' : 'Property tax rate', m = r.millage;
    out.push(m == null ? none(l, `No FY${fy} rate on file`) : !m ? kpi(l, 'None', 'No city property tax')
      : kpi(l, `${+m} mills`, `$${Math.round(m * 100).toLocaleString('en-US')} per $100,000 of taxable value${r.tax_year ? ' · tax year ' + r.tax_year : ''}`));
  }
  if (has('debt_total')) out.push(r.debt_total ? kpi('Debt', money(r.debt_total), `${r.population && !schools ? usd(r.debt_total / r.population) + ' per resident · ' : ''}audited, end of FY${fy}` + src(r.debt_source_url))
    : none('Debt', `Audited total on file for ${GY.filter(x => x.debt_total).map(x => `<button type="button" class="linkbtn" data-fy="${x.fiscal_year}">FY${x.fiscal_year}</button>`).join(', ')} only`));
  if (has('employees_fte')) out.push(r.employees_fte ? kpi('Employees', (+r.employees_fte).toLocaleString('en-US'), `FY${fy} budget, staff positions`) : none('Employees', `No FY${fy} count on file`));
  topBox.innerHTML = out.join('') + keep;
  $('#gxTopH').textContent = `Fiscal year ${fy}${r.period ? ' · ' + r.period : ''}`;
}

/* ---------- who held each elected seat in the year (officeholder-terms); "All years" keeps today's roster ---------- */
const boardBox = $('#gxBoard'), boardNote = $('#gxBoardNote'), board0 = boardBox ? boardBox.innerHTML : '', note0 = boardNote ? boardNote.innerHTML : '';
const TONE = ['blue', 'teal', 'amber', 'salmon'];
const initials = n => { const w = String(n || '').replace(/["(].*/, '').split(/\s+/).filter(x => /^\p{L}/u.test(x)); return w.length ? (w[0][0] + (w.length > 1 ? w[w.length - 1][0] : '')).toUpperCase() : '?'; };
const mon = d => { const t = new Date(d + 'T12:00'); return t.toLocaleDateString('en-US', {month: 'short', year: 'numeric'}); };
const pad2 = n => String(n).padStart(2, '0');
function officials() {
  if (!boardBox || !OH.length) return;
  if (ysel.value === 'all') { boardBox.innerHTML = board0; if (boardNote) boardNote.innerHTML = note0; return; }
  // the fiscal year's first and last day (FY2026 = Oct 2025 to Sep 2026; schools Jul to Jun), never past today
  const y = +ysel.value, st = G.fyStart || 10, today = new Date().toISOString().slice(0, 10);
  const last = new Date(Date.UTC(y, st - 1, 0)).toISOString().slice(0, 10);
  let from = `${y - 1}-${pad2(st)}-01`, to = last < today ? last : today;
  if (from > today) from = today;
  const on = t => (!t.start_date || t.start_date <= to) && (!t.end_date || t.end_date > from);
  const seats = [...new Set(OH.map(t => t.seat))];
  const cards = [];
  seats.forEach((seat, i) => {
    const hs = OH.filter(t => t.seat === seat && on(t));
    hs.forEach(t => {
      const ap = (d, a) => (a ? 'about ' : '') + mon(d);
      const part = t.end_date && t.end_date <= to ? `until ${ap(t.end_date, t.end_approx)}` : t.start_date && t.start_date > from ? `from ${ap(t.start_date, t.start_approx)}` : '';
      const sub = [esc(seat), part].filter(Boolean).join(' · ');
      if (!t.person_name) {
        cards.push(`<div class="ui-person vac"><span class="ui-av t-blue"><span class="ico i-users" aria-hidden="true"></span></span><span><b>${t.vacant ? 'Vacant' : 'Not confirmed'}</b><small>${sub}</small><small>${esc(t.note || '')}</small></span></div>`);
        return;
      }
      const how = t.how && t.how !== 'elected' ? (t.how === 'commission' ? 'chosen by the commission' : t.how) : '';
      const inner = `<span class="ui-av t-${TONE[i % 4]}" aria-hidden="true">${esc(initials(t.person_name))}</span><span><b>${esc(t.person_name)}</b><small>${sub}</small>${how ? `<small>${esc(how[0].toUpperCase() + how.slice(1))}</small>` : ''}</span>`;
      const u = t.person_id && window.BC ? BC.href('person:' + t.person_id) : null;
      cards.push(u ? `<a class="ui-person" href="${esc(u)}" title="${esc(t.note || '')}">${inner}</a>` : `<div class="ui-person" title="${esc(t.note || '')}">${inner}</div>`);
    });
  });
  boardBox.innerHTML = cards.join('');
  const changed = seats.filter(seat => OH.filter(t => t.seat === seat && on(t)).length > 1).length;
  if (boardNote) boardNote.innerHTML = `Elected officials in office in fiscal year ${y} (${esc(nice(from))} to ${esc(nice(to))})${changed ? `; ${plural(changed, 'seat')} changed hands that year, so each person who held it is listed` : ''}. Staff below are today's. `
    + `<a href="/open-data#officeholder-terms">Every term, with its source</a>`;
}

/* ---------- "this year" strip at the top ---------- */
function glance() {
  const box = $('#gxGlance'); if (!box) return;
  const c = S.contracts.filter(inYear), ra = S.cra.filter(inYear), r = ra.filter(p => p.count && /^(Spent|Committed)$/.test(p.status)), v = S.votes.filter(inYear);
  const pr = S.projects.filter(inYear).length + S.salestax.filter(inYear).length;
  const t = [];
  const ct = money(c.reduce((s, x) => s + (x.a || 0), 0)), cr = money(r.reduce((s, x) => s + (x.amount || 0), 0)), splits = v.filter(x => x.x).length;
  if (S.contracts.length) t.push(['#contracts', 'Contracts awarded', ct, plural(c.length, 'contract'), 'file', 'blue']);
  if (G.cra) t.push(['#cra', 'CRA spent or committed', cr, plural(ra.length, 'CRA record'), 'columns', 'teal']);
  if (S.votes.length) t.push(['#votes', 'Money votes', v.length.toLocaleString('en-US'), `${splits} split`, 'vote', 'amber']);
  if (S.projects.length || S.salestax.length) t.push(['#projects', 'Projects active', pr.toLocaleString('en-US'), 'tracked and sales tax', 'crane', 'salmon']);
  $('#gxGlanceH').textContent = ysel.value === 'all' ? 'Across every year on record' : `In ${ysel.value}`;
  box.innerHTML = t.map(([h, l, v2, s, n, tn]) => `<a class="kpi gx-k" href="${h}">${ico(n, tn)}<span class="eyebrow">${l}</span><span class="v">${v2}</span><span class="s">${s}</span></a>`).join('');
  // the one-line previews in the section tiles follow the year too
  const tip = (id, txt) => { const el = $(`.ui-tiles [data-jump="${id}"] small`); if (el) el.textContent = txt; };
  if (S.contracts.length) tip('contracts', `${ct} · ${plural(c.length, 'contract')}`);
  if (G.cra) tip('cra', `${cr} spent`);
  if (S.votes.length) tip('votes', `${plural(v.length, 'vote')} · ${splits} split`);
  if (S.projects.length || S.salestax.length) tip('projects', `${pr.toLocaleString('en-US')} active`);
  box.closest('section').hidden = !t.length;
}

function render() {
  topCards(); officials(); contracts(); cra(); projects(); votes(); glance();
  BCM.urlState.set({year: ysel.value});
}
ysel.addEventListener('change', render);
document.addEventListener('click', e => {
  if (e.target.closest('[data-allyears]')) { ysel.value = 'all'; render(); }
  const f = e.target.closest('[data-fy]');
  if (f && [...ysel.options].some(o => o.value === f.dataset.fy)) { ysel.value = f.dataset.fy; render(); }
});
savingsSec(); render();
if (savings.length) { const el = $('.ui-tiles [data-jump="savings"] small'); if (el) el.textContent = plural(savings.length, 'idea'); }

/* ---------- meetings: drop ones that have passed since the page was built; say how soon the next one is ---------- */
(() => {
  const now = Date.now(), cards = $$('[data-start]');
  cards.forEach(c => { if (Date.parse(c.dataset.start) + 3 * 3600e3 < now) c.hidden = true; });
  const next = cards.find(c => !c.hidden), when = $('[data-when]');
  if (!when) return;
  if (!next || next !== cards[0]) { when.hidden = true; return; }  // the big card has passed; the date cards carry on
  const day = s => { const d = new Date(s); d.setHours(0, 0, 0, 0); return d; };
  const n = Math.round((day(next.dataset.start) - day(now)) / 864e5);
  when.textContent = 'Next meeting · ' + (n <= 0 ? 'today' : n === 1 ? 'tomorrow' : `in ${n} days`);
})();
$$('[data-gx-loading]').forEach(el => el.remove());
})();
