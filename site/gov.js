/* A government's page (/governments/<slug>): the dashboards' own data, narrowed to this government, for one year.
   Reads the same published files the dashboards use (contracts, CRA ledger, projects, sales tax, FEMA, votes)
   and fills the sections the page marks with data-gx. The Year picker in the bar at the top drives
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
// every budget line for each fiscal year (budget-years): adopted funds and departments, audited revenue and spending
const budgetFor = async () => {
  const api = await get(`/api/v1/datasets/budget-years?gov_id=${encodeURIComponent(K)}&limit=1000`);
  if (api && Array.isArray(api.data)) return api.data;
  const f = await get('/downloads/budget-years.json');
  return Array.isArray(f) ? f.filter(r => r.gov_id === K) : null;
};
// every contract vote in the minutes, checked against the contract list (contract-minutes-check), the same way
const checkFor = async () => {
  const api = await get(`/api/v1/datasets/contract-minutes-check?gov_id=${encodeURIComponent(K)}&limit=5000`);
  if (api && Array.isArray(api.data)) return api.data;
  const f = await get('/downloads/contract-minutes-check.json');
  return Array.isArray(f) ? f.filter(r => r.gov_id === K) : [];
};
const [CT, P1, P2, AC, ST, FM, VT, GYr, OHr, BYr, CKr] = await Promise.all([...['/data/contracts-page.json', '/data/cra-pay-1.json', '/data/cra-pay-2.json',
  '/data/accountability.json', '/data/surtax-projects.json', '/data/michael-page.json', `/data/votes-page/${encodeURIComponent(K)}.json`].map(get), yearsFor(), termsFor(), budgetFor(), checkFor()]);
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
S.check = (CKr || []).map(r => ({...r, ys: [yr(r.date)].filter(Boolean)}));

/* ---------- the year picker ---------- */
const ysel = $('#gxYear');
let pickedYear = false;
const allYs = [...Object.values(S).flatMap(rs => rs.flatMap(r => r.ys)), ...GY.map(r => r.fiscal_year)];
// every fiscal year the officeholder terms cover is pickable too, so each year back to the site's first year (2016) shows who was in office
const ohYs = OH.length ? Array.from({length: new Date().getFullYear() - TT.FIRST_YEAR + 1}, (_, i) => TT.FIRST_YEAR + i) : [];
const YRS = [...new Set([...allYs, ...ohYs])].filter(y => y >= TT.FIRST_YEAR).sort((a, b) => b - a);
ysel.innerHTML = '<option value="all">All years</option>' + YRS.map(y => `<option value="${y}">${y}</option>`).join('');
// opens on the newest year this government has a good share of records for
// (planned project years run into the future, so they don't pick the year; a dated record does)
const doneYs = [...S.contracts, ...S.cra, ...S.votes].flatMap(r => r.ys).filter(y => y >= TT.FIRST_YEAR && y <= new Date().getFullYear());
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
// sections with nothing on file for the year picked: left out of the page and its menu until another year is picked (see trimMenu)
const EMPTY = new Set();
const gone = id => { const s = document.getElementById(id); if (s) s.remove(); $$(`.ui-tiles a[href="#${id}"], .ui-mini a[href="#${id}"]`).forEach(a => a.remove()); };

/* ---------- renderers ---------- */
// what the contract list covers, and every contract vote in the picked year's minutes that isn't in it
const CKS = {under_threshold: 'Under the list size', no_amount: 'No clear amount in the minutes', after_review: 'Not read in yet', missing: 'Not in the list yet'};
const short = n => n >= 1e6 ? '$' + +(n / 1e6).toFixed(1) + ' million' : '$' + Math.round(n / 1e3) + ',000';
function contractCheck() {
  const all = S.check, rs = all.filter(inYear);
  if (!all.length) return {line: '', body: '', size: ''};
  const th = all[0].list_threshold, thru = all[0].list_reviewed_through, size = th ? `of about ${short(th)} or more` : '';
  const n = k => rs.filter(r => r.status === k).length, out = rs.filter(r => r.status !== 'in_list');
  const parts = [[n('in_list'), 'in this list'], [n('under_threshold'), th ? `under ${short(th)}` : 'small'], [n('no_amount'), 'give no clear dollar amount'],
    [n('after_review'), `came after ${nice(thru)} and aren't read in yet`], [n('missing'), "aren't in the list yet"]].filter(p => p[0]);
  const gapN = n('after_review') + n('missing');
  const line = `<p class="small gx-check${gapN ? ' warn' : ''}"><b>What this list covers.</b> Awards ${size}, read by hand from ${esc(G.short)}'s agendas, packets and minutes through ${esc(nice(thru))}.`
    + (rs.length ? ` The minutes record ${plural(rs.length, 'contract vote')} in ${ylabel()}: ${parts.map(([c, t]) => `${c} ${t}`).join(', ')}.` : '')
    + (gapN ? ` <b>${plural(gapN, 'vote')} still to add, so the total here is low.</b>` : '') + '</p>';
  const lab = r => r.status === 'under_threshold' && r.amount ? 'Under the list size' : CKS[r.status] || r.status;
  const body = out.length ? `<details class="gx-checklist"><summary>Every other contract vote in ${ylabel()} (${out.length})</summary>`
    + table(['Approved', 'What the minutes say', 'Amount', 'Why it isn\'t above'], out.sort((a, b) => b.date.localeCompare(a.date)).map(r =>
      `<td class="small nowrap">${esc(nice(r.date))}${src(r.source_url)}</td><td class="wrap small">${esc(r.headline)}</td><td class="num">${r.amount ? usd(r.amount) + (r.up_to ? ' max' : '') : '—'}</td><td class="wrap small">${esc(lab(r))}${r.checked_note ? `<br><span class="muted">${esc(r.checked_note)}</span>` : ''}</td>`), 25)
    + `<p class="small muted">From the contract-minutes-check dataset (<a href="/api/v1/datasets/contract-minutes-check?gov_id=${K}">API</a>). Consent agendas and votes that approve no spending (mutual aid, interlocal agreements, rejected bids) are left out.</p></details>` : '';
  return {line, body, size, gapN};
}
function contracts() {
  if (!S.contracts.length) return gone('contracts');
  const rs = S.contracts.filter(inYear).sort((a, b) => (b.a || 0) - (a.a || 0)), tot = rs.reduce((s, r) => s + (r.a || 0), 0);
  const comp = rs.filter(r => /^competitive/i.test(r.m || '')).length;
  const ck = contractCheck();
  if (!rs.length && !S.check.some(inYear)) EMPTY.add('contracts');
  fill('contracts', {
    sub: `${plural(rs.length, 'contract')} ${ck.size || 'over the list size'} approved in ${ylabel()}`,
    kpis: rs.length ? kpi('Awarded', money(tot), plural(rs.length, 'contract')) + kpi('Competitively bid', rs.length ? Math.round(comp / rs.length * 100) + '%' : '—', `${comp} of ${rs.length}`)
      + kpi('Largest', money(rs[0].a), esc(rs[0].v)) : '',
    body: ck.line + (rs.length ? table(['Company', 'For', 'Amount', 'How awarded', 'Approved'], rs.map(r =>
      `<td class="wrap"><a href="${esc(r.e && window.BC ? BC.href(r.e) : '/public-money/contracts?company=' + encodeURIComponent(r.id) + '#company')}">${esc(r.v)}</a></td><td class="wrap small">${esc(r.p)}</td><td class="num">${usd(r.a)}</td><td class="small">${esc(r.m)}</td><td class="small nowrap">${esc(nice(r.d))}${src(r.u)}</td>`))
      : `<p class="muted gx-none">No contracts ${ck.size || ''} recorded for ${esc(G.short)} in ${ylabel()}. <button type="button" class="linkbtn" data-allyears>See all years</button></p>`) + ck.body,
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
  if (!rs.length) EMPTY.add('cra');
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
// what "tracked" means, so a short list isn't read as everything the government built
const PJNOTE = 'Tracked projects are ones with a hand-reviewed history from budget to close-out, or a contract in our list that has had change orders; every other award is under Contracts.';
function projects() {
  const a = S.projects.filter(inYear), t = S.salestax.filter(inYear), f = S.fema.filter(inYear);
  if (!S.projects.length && !S.salestax.length && !S.fema.length) return gone('projects');
  if (!a.length && !t.length && !f.length) EMPTY.add('projects');
  const parts = [];
  if (S.projects.length) {
    const flagged = a.filter(p => (p.flags || []).length);
    parts.push(`<h3 class="h4">Big projects, budget to close-out</h3>` + (a.length ? `<div class="gx-cards">${a.sort((x, y) => (y.flags || []).length - (x.flags || []).length || (y.money || 0) - (x.money || 0)).slice(0, 6).map(p =>
      `<a class="gx-card" href="/public-money/accountability?gov=${K}&p=${encodeURIComponent(p.id)}"><span class="eyebrow">${esc(stl(p.status))}</span><b>${esc(p.n)}</b><span class="muted small">${money(p.money)}${p.growth ? ` · ${p.growth > 0 ? '+' : ''}${p.growth}% since award` : ''}</span>${(p.flags || []).length ? `<span class="badge warn">${plural(p.flags.length, 'question')}</span>` : ''}</a>`).join('')}</div>
      <p class="small muted">${plural(a.length, 'project')} in ${ylabel()}, ${flagged.length} with an open question. ${PJNOTE} <a href="${dash('/public-money/accountability')}">See every project</a></p>` : `<p class="muted small">No tracked projects active in ${ylabel()}. ${PJNOTE}</p>`));
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
  if (!rs.length) EMPTY.add('votes');
  const card = v => `<li class="fd vt"><span class="vt-meta muted">${esc(v.dn)} · ${esc(VT.cat[v.c] || v.c)}${v.a ? ' · ' + usd(v.a) : ''} · ${esc(v.t)} ${esc(v.o || '')}</span><div class="vt-h">${esc(v.h)}</div>${Object.keys(v.m).length ? `<p class="small">Voted no: ${esc(Object.entries(v.m).filter(([, x]) => x === 'no').map(([n]) => n).join(', ') || 'none recorded')}</p>` : ''}${v.u ? `<a class="src" href="${esc(v.u)}" target="_blank" rel="noopener">${esc(v.ul || 'Minutes')}</a>` : ''}</li>`;
  fill('votes', {
    sub: `${plural(rs.length, 'vote')} recorded in ${ylabel()}`,
    kpis: rs.length ? kpi('Votes recorded', rs.length, 'Every motion in the minutes') + kpi('Split votes', sp.length, rs.length ? Math.round(sp.length / rs.length * 100) + '% not unanimous' : '')
      + kpi('Money voted on', money(rs.reduce((s, v) => s + (v.a || 0), 0)), 'where the minutes give an amount') : '',
    body: rs.length ? `<h3 class="h4">${sp.length ? 'Most recent split votes' : 'Most recent votes'}</h3><ol class="findings">${(sp.length ? sp : rs).slice(0, 5).map(card).join('')}</ol>` : '',
    empty: `No votes recorded in ${ylabel()}.`,
    link: `<a href="${dash('/public-money/votes', `&g=${K}`)}#all">Every ${esc(G.short)} vote, by member</a>`,
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
// the fiscal year the top cards and the other fiscal-year sections (budget, tax rate, debt, audits) show.
// They open on the current fiscal year; the picker's own default is the newest year with dated records (a calendar year),
// so only a choice the visitor makes (or ?year= in the link) moves them. "All years" shows the current fiscal year.
const GYby = Object.fromEntries(GY.map(r => [r.fiscal_year, r]));
function pickFY() {
  let fy = ysel.value === 'all' || !(pickedYear || new URLSearchParams(location.search).get('year')) ? curFY : +ysel.value;
  if (ysel.value === 'all' && !GYby[fy] && GY.length) fy = GY[GY.length - 1].fiscal_year;
  return fy;
}
function topCards() {
  if (!topBox || !GY.length) return;
  const by = GYby, fy = pickFY();
  const r = by[fy] || {}, prev = by[fy - 1] || {}, has = k => GY.some(x => x[k] != null), schools = K === 'schools';
  const none = (l, why) => topKpi(l, 'No data', why, true);
  const kpi = topKpi;
  const out = [];
  if (!schools && has('population')) out.push(r.population ? kpi('Residents', r.population.toLocaleString('en-US'), r.population_year === fy ? `FY${fy} state figure` : `${r.population_year} state estimate`) : none('Residents', `No count for FY${fy}`));
  if (r.budget_total) {
    const bits = [`FY${fy} · ${esc(r.budget_status || 'adopted')}`];
    if (r.budget_per_resident) bits.push(`${usd(r.budget_per_resident)} per resident`);
    // no change is shown when the two years are not the same kind of total (a draft, or one with and one without interfund transfers)
    if (prev.budget_total && !/draft|tentative/i.test(prev.budget_status || '') && !!r.budget_excludes_transfers === !!prev.budget_excludes_transfers) { const ch = (r.budget_total / prev.budget_total - 1) * 100; bits.push(`${ch >= 0 ? 'up' : 'down'} ${Math.abs(ch).toFixed(0)}% from FY${fy - 1}`); }
    out.push(kpi('Budget', money(r.budget_total), bits.join(' · ') + src(r.budget_source_url)));
  } else if (r.actual_spending) out.push(kpi('Spent (audited)', money(r.actual_spending), `FY${fy} actual spending; no adopted budget on file` + src(r.actuals_source_url)));
  else if (has('budget_total') || has('actual_spending')) out.push(none('Budget', `No FY${fy} budget on file`));
  if (has('millage')) {
    const l = schools ? 'School tax rate' : 'Property tax rate', m = r.millage;
    out.push(m == null ? none(l, `No FY${fy} rate on file`) : !m ? kpi(l, 'None', 'No city property tax')
      : kpi(l, `${+m} mills`, `$${Math.round(m * 100).toLocaleString('en-US')} per $100,000 of taxable value${r.tax_year ? ' · tax year ' + r.tax_year : ''}`));
  }
  if (has('debt_total')) out.push(r.debt_total ? kpi('Debt', money(r.debt_total), `${r.population && !schools ? usd(r.debt_total / r.population) + ' per resident · ' : ''}audited, end of FY${fy}` + src(r.debt_source_url))
    : (() => { const l = GY.filter(x => x.debt_total && x.fiscal_year < fy).sort((a, b) => b.fiscal_year - a.fiscal_year)[0];
        return l ? kpi('Debt', money(l.debt_total), `${l.population && !schools ? usd(l.debt_total / l.population) + ' per resident · ' : ''}latest audit, end of FY${l.fiscal_year}` + src(l.debt_source_url))
          : none('Debt', `Audited total on file for ${GY.filter(x => x.debt_total).map(x => `<button type="button" class="linkbtn" data-fy="${x.fiscal_year}">FY${x.fiscal_year}</button>`).join(', ')} only`); })());
  if (has('employees_fte')) out.push(r.employees_fte ? kpi('Employees', (+r.employees_fte).toLocaleString('en-US'), `FY${fy} budget, staff positions`) : none('Employees', `No FY${fy} count on file`));
  topBox.innerHTML = out.join('') + keep;
  $('#gxTopH').textContent = `Fiscal year ${fy}${r.period ? ' · ' + r.period : ''}`;
}

/* ---------- who held each elected seat in the year (officeholder-terms); "All years" keeps today's roster ---------- */
const boardBox = $('#gxBoard'), boardNote = $('#gxBoardNote'), board0 = boardBox ? boardBox.innerHTML : '', note0 = boardNote ? boardNote.innerHTML : '';
const TONE = ['blue', 'teal', 'amber', 'salmon'];
const initials = n => { const w = String(n || '').replace(/\([^)]*\)?|"[^"]*"?/g, ' ').split(/\s+/).filter(x => /^\p{L}/u.test(x)); return w.length ? (w[0][0] + (w.length > 1 ? w[w.length - 1][0] : '')).toUpperCase() : '?'; };
const mon = d => { const t = new Date(d + 'T12:00'); return t.toLocaleDateString('en-US', {month: 'short', year: 'numeric'}); };
const pad2 = n => String(n).padStart(2, '0');
const staffBox = $('#gxStaff'), staff0 = staffBox ? staffBox.innerHTML : '';
function officials() {
  if (!boardBox || !OH.length) return;
  if (ysel.value === 'all') { boardBox.innerHTML = board0; if (boardNote) boardNote.innerHTML = note0; if (staffBox) staffBox.innerHTML = staff0; return; }
  // the fiscal year's first and last day (FY2026 = Oct 2025 to Sep 2026; schools Jul to Jun), never past today
  const y = +ysel.value, st = G.fyStart || 10, today = new Date().toISOString().slice(0, 10);
  const last = new Date(Date.UTC(y, st - 1, 0)).toISOString().slice(0, 10);
  let from = `${y - 1}-${pad2(st)}-01`, to = last < today ? last : today;
  if (from > today) from = today;
  const on = t => (!t.start_date || t.start_date <= to) && (!t.end_date || t.end_date > from);
  const ap = (d, a) => (a ? 'about ' : '') + mon(d);
  const cardsFor = (seats, tone0, pays = {}) => seats.flatMap((seat, i) => OH.filter(t => t.seat === seat && on(t)).map(t => {
    const part = t.end_date && t.end_date <= to ? `until ${ap(t.end_date, t.end_approx)}` : t.start_date && t.start_date > from ? `from ${ap(t.start_date, t.start_approx)}` : '';
    const sub = [esc(seat), part].filter(Boolean).join(' · ');
    if (!t.person_name)
      return `<div class="ui-person vac"><span class="ui-av t-blue"><span class="ico i-users" aria-hidden="true"></span></span><span><b>${t.vacant ? 'Vacant' : 'Not confirmed'}</b><small>${sub}</small><small>${esc(t.note || '')}</small></span></div>`;
    const how = t.how && !['elected', 'appointed'].includes(t.how) ? (t.how === 'commission' ? 'chosen by the commission' : t.how) : t.how === 'appointed' && !t.appointed ? 'appointed' : '';
    const ph = t.person_id && (G.photos || {})[t.person_id];
    const av = ph ? `<span class="ui-av ui-av-ph t-${TONE[(i + tone0) % 4]}"><img src="${esc(ph)}" alt="" width="160" height="160" loading="lazy" decoding="async"></span>`
      : `<span class="ui-av t-${TONE[(i + tone0) % 4]}" aria-hidden="true">${esc(initials(t.person_name))}</span>`;
    const inner = `${av}<span><b>${esc(t.person_name)}</b><small>${sub}</small>${how ? `<small>${esc(how[0].toUpperCase() + how.slice(1))}</small>` : ''}${pays[t.person_id] || pays[t.person_name] || ''}</span>`;
    const u = t.person_id && window.BC ? BC.href('person:' + t.person_id) : null;
    return u ? `<a class="ui-person" href="${esc(u)}" title="${esc(t.note || '')}">${inner}</a>` : `<div class="ui-person" title="${esc(t.note || '')}">${inner}</div>`;
  }));
  const elected = [...new Set(OH.filter(t => !t.appointed).map(t => t.seat))], mgr = [...new Set(OH.filter(t => t.appointed).map(t => t.seat))];
  boardBox.innerHTML = cardsFor(elected, 0).join('');
  // the manager's card follows the year; other staff (no year record) stay as today's
  if (staffBox && mgr.length) {
    const tmp = document.createElement('div'); tmp.innerHTML = staff0;
    // today's pay line on a manager's card stays with that person when the year's card replaces it
    const pays = {};
    $$('[data-seat]', tmp).forEach(c => {
      if (!mgr.includes(c.dataset.seat)) return;
      const pay = c.querySelector('.gx-pay'), nm = c.querySelector('b');
      if (pay) pays[c.dataset.pid || nm.textContent.trim()] = pay.outerHTML;
      c.remove();
    });
    staffBox.innerHTML = cardsFor(mgr, 1, pays).join('') + tmp.innerHTML;
  }
  const changed = [...elected, ...mgr].filter(seat => OH.filter(t => t.seat === seat && on(t)).length > 1).length;
  if (boardNote) boardNote.innerHTML = `Officials in office in fiscal year ${y} (${esc(nice(from))} to ${esc(nice(to))})${changed ? `; ${plural(changed, 'seat')} changed hands that year, so each person who held it is listed` : ''}.${mgr.length ? ` The ${esc(mgr[0].toLowerCase())} below is that year's too; other staff and pay are today's.` : ' Staff below are today\'s.'} `
    + `<a href="/open-data#officeholder-terms">Every term, with its source</a>`;
}

/* ---------- the sections drawn at build for today, redrawn here for the year picked ----------
   Budget, tax rate, debt and audits follow the fiscal year of the top cards; meetings and connections follow the
   calendar year, like contracts and votes. A year with no record says so, names the nearest years we have and why. */
const BY = Array.isArray(BYr) ? BYr : null;
const today = new Date().toISOString().slice(0, 10);
// a fiscal year's first and last day (FY2026 = Oct 2025 to Sep 2026; schools Jul to Jun)
const fyFrom = y => `${y - 1}-${pad2(G.fyStart || 10)}-01`, fyTo = y => new Date(Date.UTC(y, (G.fyStart || 10) - 1, 0)).toISOString().slice(0, 10);
const fyBtn = y => `<button type="button" class="linkbtn" data-fy="${y}">FY${y}</button>`;
const poss = n => /s$/.test(n) ? n + "'" : n + "'s";
const ask = `<a href="/records-request?gov=${K}">Ask ${esc(G.short)} for it</a>`;
// "No FY2019 audit on file. Nearest we have: FY2023. Why …" (kind: 'audit' for audited figures, 'budget' for adopted ones)
function gap(what, y, have, kind) {
  have = [...new Set(have)].sort((a, b) => a - b);
  const before = have.filter(x => x < y).pop(), after = have.find(x => x > y);
  const near = before && after ? `Nearest we have: ${fyBtn(before)} and ${fyBtn(after)}.` : before ? `Latest we have: ${fyBtn(before)}.` : after ? `Earliest we have: ${fyBtn(after)}.` : '';
  let why;
  if (!have.length) why = `We have no ${what} for ${esc(G.short)} in any year yet. ${ask}.`;
  else if (kind === 'audit' && fyTo(y) >= today) why = `FY${y} runs to ${nice(fyTo(y))}; audited figures come only after the year ends.`;
  else if (kind === 'audit' && y > have[have.length - 1]) why = `Florida gives governments nine months after the year ends to file the audit with the state, and the FY${y} one isn't on file here yet.`;
  // the state Auditor General posts the last five years of audits; older ones only the government has
  else if (kind === 'audit' && y < have[0] && y > have[have.length - 1] - 5) why = `We haven't read it in yet; it is among the last five years of audits the state Auditor General posts online.`;
  else if (kind === 'audit' && y < have[0]) why = `The state Auditor General posts only the last five years of audits; older ones have to come from ${esc(G.short)}. ${ask}.`;
  else if (kind === 'budget' && fyFrom(y) > today) why = `FY${y} hasn't started; ${esc(G.short)} adopts each budget in September.`;
  else if (kind === 'budget' && y < (have[0] || 9999)) why = `Not in ${esc(poss(G.short))} budget documents online or the state audit reports we have. ${ask}.`;
  else why = `Not in the records we have found yet. ${ask}.`;
  return `<span class="gx-gap"><b>No FY${y} ${what} on file.</b> ${near} ${why}</span>`;
}
const yrsWith = (rs, f) => [...new Set(rs.filter(f).map(r => r.fiscal_year))];
const bars = (items, color = 'var(--s1)', max = 10) => {
  let xs = items.filter(x => x.amount > 0).sort((a, b) => b.amount - a.amount);
  if (!xs.length) return '';
  // a long list keeps its largest lines and adds up the rest in one bar
  if (xs.length > max + 1) { const rest = xs.slice(max); xs = [...xs.slice(0, max), {name: `${rest.length} more`, amount: rest.reduce((t, x) => t + x.amount, 0)}]; }
  const mx = xs[0].amount;
  return '<div class="hbars">' + xs.map(x => `<div class="hb"><span class="hb-n">${esc(x.name)}</span><span class="hb-track"><span class="hb-bar" style="width:${Math.max(.5, x.amount / mx * 100).toFixed(1)}%;background:${color}"></span></span><span class="hb-v">${money(x.amount)}</span></div>`).join('') + '</div>';
};

// Money in, money out: the build draws the budget it has in full (G.budgetFY); any other year comes from budget-years
const moneyBox = $('#money')?.closest('section');
const money0 = moneyBox && {sub: $('[data-money-sub]', moneyBox)?.innerHTML, body: $('[data-money-body]', moneyBox)?.innerHTML, src: $('[data-money-src]', moneyBox)?.innerHTML};
function moneySec() {
  if (!moneyBox || !money0.body) return;
  const fy = pickFY(), sub = $('[data-money-sub]', moneyBox), body = $('[data-money-body]', moneyBox), srcBox = $('[data-money-src]', moneyBox);
  if (fy === G.budgetFY || !BY) { sub.innerHTML = money0.sub; body.innerHTML = money0.body; srcBox.innerHTML = money0.src; return; }
  const rs = BY.filter(r => r.fiscal_year === fy);
  const line = k => rs.find(r => r.basis === 'adopted' && r.line_key === k);
  const tot = line('total'), gf = line('general_fund');
  const funds = rs.filter(r => r.section === 'fund'), deps = rs.filter(r => r.section === 'department');
  const rev = rs.filter(r => r.basis === 'actual' && r.section === 'revenue' && r.in_total !== false);
  const spent = rs.filter(r => r.basis === 'actual' && r.section === 'spending' && r.in_total !== false);
  const st = (tot || gf || {}).status;
  if (!tot && !gf && !rev.length && !spent.length && !deps.length && !funds.length) EMPTY.add('money');
  sub.innerHTML = tot || gf ? `FY${fy} ${esc(st && st !== 'adopted' ? st : 'adopted')} budget${tot ? ' ' + money(tot.amount) : ''}${gf ? ' · general fund ' + money(gf.amount) : ''}` : `FY${fy}`;
  const out = [];
  if (!tot && !gf) out.push(`<p class="gx-yr">${gap('adopted budget', fy, yrsWith(BY, r => r.basis === 'adopted' && r.section === 'total'), 'budget')}</p>`);
  const left = rev.length ? `<h3 class="h4">Where the money came from</h3><p class="small muted">Audited, all funds, FY${fy}</p>${bars(rev.map(r => ({name: r.name, amount: r.amount})), 'var(--s3)')}`
    : `<h3 class="h4">Where the money came from</h3><p class="small">${gap('audited revenue', fy, yrsWith(BY, r => r.basis === 'actual' && r.section === 'revenue'), 'audit')}</p>`;
  const right = deps.length ? `<h3 class="h4">What the general fund pays for</h3><p class="small muted">Adopted FY${fy} budget, by department</p>${bars(deps.map(r => ({name: r.name, amount: r.amount})))}`
    : spent.length ? `<h3 class="h4">What it spent the money on</h3><p class="small muted">Audited, all funds, FY${fy}, by service (the FY${fy} budget isn't broken out by department here)</p>${bars(spent.map(r => ({name: r.name, amount: r.amount})))}`
    : `<h3 class="h4">What the general fund pays for</h3><p class="small">${gap('budget by department', fy, yrsWith(BY, r => r.section === 'department' || (r.basis === 'actual' && r.section === 'spending')), 'budget')}</p>`;
  out.push(`<div class="two"><div>${left}</div><div>${right}</div></div>`);
  if (funds.length) out.push(`<details class="tbl-toggle be-full"><summary>The whole FY${fy} budget, fund by fund</summary>${bars(funds.map(r => ({name: r.name, amount: r.amount})))}
    <p class="note small">Funds are separate accounts: money raised for one purpose can only be spent on it. When one fund pays another, both show it, so totals count some money twice.</p></details>`);
  body.innerHTML = out.join('');
  // one link per kind of record: the adopted budget and the audited figures
  const srcs = new Map();
  rs.filter(r => r.source_url).forEach(r => { const t = r.basis === 'actual' ? `FY${fy} audited figures` : `FY${fy} budget`; if (!srcs.has(t)) srcs.set(t, r.source_url); });
  srcBox.innerHTML = [...srcs].map(([t, u]) => `<a class="src" href="${esc(u)}" target="_blank" rel="noopener">${esc(t)}</a>`).join(' · ') || `FY${fy}`;
}

// Property tax rate: the year's rate in words, its bar marked
const rateBox = $('#rate')?.closest('section');
function rateSec() {
  if (!rateBox) return;
  const line = $('[data-rate-yr]', rateBox); $$('.hb[data-ty]', rateBox).forEach(b => b.classList.remove('on'));
  if (ysel.value === 'all' || !line) { if (line) line.hidden = true; return; }
  const fy = pickFY(), r = GYby[fy] || {}, ty = r.tax_year || fy - 1;
  line.hidden = false;
  if (r.millage == null) { line.innerHTML = gap('tax rate', fy, GY.filter(x => x.millage != null).map(x => x.fiscal_year), 'budget'); return; }
  const bar = $(`.hb[data-ty="${ty}"]`, rateBox); if (bar) bar.classList.add('on');
  line.innerHTML = !r.millage ? `<b>FY${fy}: no city property tax.</b>`
    : `<b>FY${fy}: ${+r.millage} mills</b>, set in tax year ${ty} ($${Math.round(r.millage * 100).toLocaleString('en-US')} per $100,000 of taxable value)${bar ? '; its bar is marked below' : ''}.`;
}

// Debt: the audited total at the end of the year picked; the detail below stays the latest audit and says so
const debtBox = $('#debt')?.closest('section');
function debtSec() {
  const line = debtBox && $('[data-debt-yr]', debtBox); if (!line) return;
  if (ysel.value === 'all') { line.hidden = true; return; }
  const fy = pickFY(), r = GYby[fy] || {}, ys = GY.filter(x => x.debt_total).map(x => x.fiscal_year), last = ys[ys.length - 1];
  const rest = last && last !== fy ? ` The details below are from the FY${last} audit, the latest we have.` : '';
  line.hidden = false;
  line.innerHTML = r.debt_total ? `<b>End of FY${fy}: ${money(r.debt_total)} owed</b>, from that year's audit.${src(r.debt_source_url)}${rest}` : gap('audited debt total', fy, ys, 'audit') + rest;
}

// Audits: only the year picked (its report, opinion and findings); "All years" shows every one
const auBox = $('#audits')?.closest('section'), au0 = auBox && $('[data-au-sub]', auBox)?.textContent;
function auditSec() {
  if (!auBox) return;
  const line = $('[data-au-yr]', auBox), sub = $('[data-au-sub]', auBox), lis = $$('li[data-au-fy]', auBox), reps = $$('details[data-date]', auBox);
  if (ysel.value === 'all') { lis.forEach(l => l.hidden = false); reps.forEach(d => d.hidden = false); $$('.au-gov', auBox).forEach(d => d.hidden = false); if (line) line.hidden = true; if (sub) sub.textContent = au0; return; }
  const fy = pickFY(), on = lis.filter(l => +l.dataset.auFy === fy);
  lis.forEach(l => l.hidden = +l.dataset.auFy !== fy);
  $$('.au-gov', auBox).forEach(d => { d.hidden = !$$('li[data-au-fy]', d).some(l => !l.hidden); if (!d.hidden) d.open = true; });
  reps.forEach(d => { const t = d.dataset.date; d.hidden = !t || t.slice(0, 7) < fyFrom(fy).slice(0, 7) || t.slice(0, 7) > fyTo(fy).slice(0, 7); });
  const due = new Date(Date.UTC(+fyTo(fy).slice(0, 4), +fyTo(fy).slice(5, 7) + 9, 1)).toISOString().slice(0, 10);
  if (!on.length && due <= today) EMPTY.add('audits');
  const n = on.reduce((t, l) => t + $$('.fd', l).length, 0);
  if (sub) sub.textContent = on.length ? `${plural(n, 'finding')} in FY${fy}` : `No FY${fy} audit on file`;
  if (line) { line.hidden = on.length > 0; if (!on.length) line.innerHTML = gap('audit', fy, lis.map(l => +l.dataset.auFy), 'audit'); }
}

// Meetings: upcoming ones for this year or "All years"; for a past year, the meetings held that year, from the minutes we read
const meetBox = $('#meet')?.closest('section');
const meet0 = meetBox && {h: $('[data-meet-h]', meetBox).textContent, sub: $('[data-meet-sub]', meetBox).textContent};
function meetSec() {
  if (!meetBox) return;
  const up = $('[data-meet-up]', meetBox), yrBox = $('[data-meet-yr]', meetBox), h = $('[data-meet-h]', meetBox), sub = $('[data-meet-sub]', meetBox);
  const y = +ysel.value;
  if (ysel.value === 'all' || y >= new Date().getFullYear()) { up.hidden = false; yrBox.hidden = true; h.textContent = meet0.h; sub.textContent = meet0.sub; return; }
  const by = new Map();
  S.votes.filter(v => v.ys.includes(y)).forEach(v => { const k = v.d + '|' + v.b; const m = by.get(k) || by.set(k, {d: v.d, dn: v.dn, board: (v.ut || '').replace(/ minutes.*$/i, '') || 'Meeting', u: v.u, ul: v.ul, n: 0, x: 0}).get(k); m.n++; if (v.x) m.x++; if (!m.u && v.u) { m.u = v.u; m.ul = v.ul; } });
  const ms = [...by.values()].sort((a, b) => b.d.localeCompare(a.d));
  if (!ms.length) EMPTY.add('meet');
  h.textContent = `Meetings in ${y}`;
  sub.textContent = ms.length ? `${plural(ms.length, 'meeting')} with votes in the minutes` : '';
  up.hidden = true; yrBox.hidden = false;
  yrBox.innerHTML = ms.length ? table(['Date', 'Board', 'Votes', 'Minutes'], ms.map(m => `<td class="nowrap">${esc(m.dn || nice(m.d))}</td><td class="wrap">${esc(m.board)}</td><td class="num">${m.n}${m.x ? ` <span class="muted small">(${m.x} split)</span>` : ''}</td><td>${m.u ? `<a class="src" href="${esc(m.u)}" target="_blank" rel="noopener">${esc(m.ul || 'Minutes')}</a>` : ''}</td>`), 10)
    + `<p class="small"><a href="${dash('/public-money/votes', `&g=${K}`)}#all">Every vote from these meetings</a></p>`
    : `<p class="muted"><b>No meeting minutes from ${y} read yet.</b> We are reading every board's minutes back to 2016; <a href="/data-sources#progress">see how far along each one is</a>.</p>`;
  $$('.gx-more', yrBox).forEach(b => b.onclick = () => { $$('tr[data-more]', yrBox).forEach(t => t.hidden = false); b.remove(); });
}

// Connections: tell the network and list (profile.js) which calendar year to show
const connBox = $('#pf'), conn0 = connBox && $('.sec-hd .muted', connBox)?.textContent;
function connSec() {
  if (!connBox) return;
  const y = ysel.value === 'all' ? null : +ysel.value;
  window.BCYEAR = y;
  dispatchEvent(new CustomEvent('bc:year', {detail: y}));
  const s = $('.sec-hd .muted', connBox); if (s) s.textContent = y ? `Payments, campaign gifts, votes and service on record in ${y}` : conn0;
}

/* ---------- "this year" strip at the top ---------- */
function glance() {
  const box = $('#gxGlance'); if (!box) return;
  const c = S.contracts.filter(inYear), ra = S.cra.filter(inYear), r = ra.filter(p => p.count && /^(Spent|Committed)$/.test(p.status)), v = S.votes.filter(inYear);
  const pr = S.projects.filter(inYear).length + S.salestax.filter(inYear).length;
  const t = [];
  const ct = money(c.reduce((s, x) => s + (x.a || 0), 0)), cr = money(r.reduce((s, x) => s + (x.amount || 0), 0)), splits = v.filter(x => x.x).length;
  const ck = S.check.filter(inYear), ckGap = ck.filter(r => r.status === 'after_review' || r.status === 'missing').length;
  const ckSub = plural(c.length, 'large contract') + (ckGap ? ` · ${ckGap} still to add` : ck.length ? ` · ${ck.length} votes in minutes` : '');
  if (S.contracts.length && !EMPTY.has('contracts')) t.push(['#contracts', 'Contracts awarded', ct, ckSub, 'file', 'blue']);
  if (G.cra && !EMPTY.has('cra')) t.push(['#cra', 'CRA spent or committed', cr, plural(ra.length, 'CRA record'), 'columns', 'teal']);
  if (S.votes.length && !EMPTY.has('votes')) t.push(['#votes', 'Votes recorded', v.length.toLocaleString('en-US'), `${splits} split`, 'vote', 'amber']);
  if ((S.projects.length || S.salestax.length) && !EMPTY.has('projects')) t.push(['#projects', 'Projects tracked', pr.toLocaleString('en-US'), S.salestax.length ? 'reviewed, change orders, sales tax' : 'reviewed or with change orders', 'crane', 'salmon']);
  $('#gxGlanceH').textContent = ysel.value === 'all' ? 'Across every year on record' : `In ${ysel.value}`;
  box.innerHTML = t.map(([h, l, v2, s, n, tn]) => `<a class="kpi gx-k" href="${h}">${ico(n, tn)}<span class="eyebrow">${l}</span><span class="v">${v2}</span><span class="s">${s}</span></a>`).join('');
  // the one-line previews in the section tiles follow the year too
  const tip = (id, txt) => { const el = $(`.ui-tiles [data-jump="${id}"] small`); if (el) el.textContent = txt; };
  if (S.contracts.length) tip('contracts', c.length || !ck.length ? `${ct} · ${plural(c.length, 'large contract')}` : `${plural(ck.length, 'contract vote')} in the minutes`);
  if (G.cra) tip('cra', `${cr} spent`);
  if (S.votes.length) tip('votes', `${plural(v.length, 'vote')} · ${splits} split`);
  if (S.projects.length || S.salestax.length) tip('projects', `${pr.toLocaleString('en-US')} tracked`);
  box.closest('section').hidden = !t.length;
}

/* ---------- the section menu: only sections with something on file for the year ----------
   A section with nothing for the year picked is left out of the page and the menu, and one line under the menu
   names what was left out, with a way back to every year. "All years" shows every section that has any records. */
const tilesBox = $('.ui-tiles'), offNote = (() => {
  if (!tilesBox) return null;
  const p = document.createElement('p'); p.className = 'gx-off small muted'; p.hidden = true; p.setAttribute('data-report', 'skip');
  tilesBox.after(p); return p;
})();
function trimMenu() {
  const off = [];
  $$('.ui-tiles a[data-jump]').forEach(a => {
    const id = a.dataset.jump, empty = EMPTY.has(id), h = document.getElementById(id), sec = h && h.closest('section');
    a.style.display = empty ? 'none' : '';
    $$(`.ui-mini a[href="#${id}"]`).forEach(m => m.style.display = empty ? 'none' : '');
    if (sec) sec.style.display = empty ? 'none' : '';
    if (empty) off.push($('b', a)?.textContent || id);
  });
  if (!offNote) return;
  offNote.hidden = !off.length;
  offNote.innerHTML = off.length ? `Nothing on file for ${esc(ylabel())} yet: ${esc(off.join(', '))}. <button type="button" class="linkbtn" data-allyears>See all years</button>` : '';
}

function render() {
  EMPTY.clear();
  topCards(); officials(); moneySec(); rateSec(); contracts(); cra(); projects(); votes(); meetSec(); debtSec(); auditSec(); connSec(); glance(); trimMenu();
  BCM.urlState.set({year: ysel.value});
}
ysel.addEventListener('change', () => { pickedYear = true; render(); });
document.addEventListener('click', e => {
  if (e.target.closest('[data-allyears]')) { ysel.value = 'all'; render(); }
  const f = e.target.closest('[data-fy]');
  // a year named in a "no data" note moves the whole page to it, cards included
  if (f && [...ysel.options].some(o => o.value === f.dataset.fy)) { e.preventDefault(); pickedYear = true; ysel.value = f.dataset.fy; render(); }
});
render();

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
