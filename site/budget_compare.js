// Compare budgets across years (/public-money/budget-compare). Reads GET /api/v1/budget-compare; holds no data.
(() => {
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const M = n => { if (n == null) return '—'; const a = Math.abs(n), s = n < 0 ? '−' : ''; return s + (a >= 1e9 ? '$' + (a / 1e9).toFixed(2) + 'B' : a >= 1e6 ? '$' + (a / 1e6).toFixed(1) + 'M' : a >= 1e4 ? '$' + Math.round(a / 1e3).toLocaleString() + 'K' : '$' + Math.round(a).toLocaleString()); };
const D = n => (n > 0 ? '+' : '') + M(n);
const P = p => p == null ? '' : (p > 0 ? '+' : p < 0 ? '−' : '') + Math.abs(p).toLocaleString(undefined, {maximumFractionDigits: Math.abs(p) < 10 ? 1 : 0}) + '%';
const cls = n => n > 0 ? 'bc-up' : n < 0 ? 'bc-dn' : '';
const gov = id => window.BC && BC.href && BC.href('gov:' + id) ? BC.a('gov:' + id, GOVS[id]?.government || id) : esc(GOVS[id]?.government || id);
const Q = new URLSearchParams(location.search);
let GOVS = {}, cov = [], cur = null, basis = Q.get('basis') === 'actual' ? 'actual' : 'adopted', sort = 'change', req = 0;
const api = p => fetch('/api/v1/budget-compare' + p).then(r => r.json().then(j => (r.ok ? j : Promise.reject(j))));

// years on record for the government and basis picked
const yearsOf = g => basis === 'actual' ? g.actual : g.adopted_totals;
function fillYears(g, from, to) {
  const ys = yearsOf(g), det = new Set(basis === 'actual' ? g.actual : g.adopted_detail);
  const opt = y => `<option value="${y}">FY${y}${det.has(y) ? '' : ' (total only)'}</option>`;
  $('bcFrom').innerHTML = ys.map(opt).join(''); $('bcTo').innerHTML = ys.map(opt).join('');
  if (from) $('bcFrom').value = from; if (to) $('bcTo').value = to;
}

function bars(el, list, opts = {}) {
  const xs = [...list];
  if (sort === 'pct' && !opts.fixed) xs.sort((a, b) => Math.abs(b.pct ?? (b.status === 'both' ? 0 : 1e9)) - Math.abs(a.pct ?? (a.status === 'both' ? 0 : 1e9)));
  else if (sort === 'to' && !opts.fixed) xs.sort((a, b) => (b.to || 0) - (a.to || 0));
  const has = xs.filter(l => l.from != null || l.to != null);
  if (!has.length) { el.innerHTML = `<p class="muted">${esc(opts.empty || 'Not broken out for these years.')}</p>`; return; }
  const mx = Math.max(...has.map(l => Math.abs(l.change)), 1);
  el.innerHTML = has.map(l => {
    const w = Math.max(l.change ? .6 : 0, Math.abs(l.change) / mx * 50).toFixed(2);
    const tag = l.status === 'added' ? '<span class="dv-tag add">new</span>' : l.status === 'removed' ? '<span class="dv-tag rem">gone</span>' : '';
    const sub = [l.fund_type, l.in_total === false ? 'not counted in the total' : ''].filter(Boolean).join(' · ');
    const tip = `${l.name}: FY${cur.from} ${M(l.from)} → FY${cur.to} ${M(l.to)}`;
    return `<div class="dv-r" tabindex="0" title="${esc(tip)}"><span class="dv-n">${esc(l.name)}${tag}${sub ? `<small>${esc(sub)}</small>` : ''}</span>
      <span class="dv-t" aria-hidden="true">${l.change ? `<span class="dv-b ${l.change > 0 ? 'up' : 'dn'}" style="width:${w}%"></span>` : ''}</span>
      <span class="dv-v"><span class="${cls(l.change)}">${D(l.change)}</span>${l.pct != null ? ` <span class="muted">${P(l.pct)}</span>` : ''}<small>${M(l.from)} → ${M(l.to)}</small></span></div>`;
  }).join('');
}

function table(el, list, label) {
  if (!list.length) { el.innerHTML = ''; return; }
  const f = list.reduce((s, l) => s + (l.in_total === false ? 0 : l.from || 0), 0), t = list.reduce((s, l) => s + (l.in_total === false ? 0 : l.to || 0), 0);
  el.innerHTML = `<thead><tr><th scope="col">${esc(label)}</th><th scope="col" class="num">FY${cur.from}</th><th scope="col" class="num">FY${cur.to}</th><th scope="col" class="num">Change</th><th scope="col" class="num">%</th></tr></thead><tbody>` +
    list.map(l => `<tr><th scope="row">${esc(l.name)}${l.status === 'added' ? ' <span class="dv-tag add">new</span>' : l.status === 'removed' ? ' <span class="dv-tag rem">gone</span>' : ''}</th><td class="num">${M(l.from)}</td><td class="num">${M(l.to)}</td><td class="num ${cls(l.change)}">${D(l.change)}</td><td class="num">${P(l.pct) || '—'}</td></tr>`).join('') +
    `</tbody><tfoot><tr><th scope="row">Sum of lines${list.some(l => l.in_total === false) ? ' (counted ones)' : ''}</th><td class="num">${M(f)}</td><td class="num">${M(t)}</td><td class="num ${cls(t - f)}">${D(t - f)}</td><td class="num">${f ? P(Math.round((t - f) / Math.abs(f) * 1000) / 10) : '—'}</td></tr></tfoot>`;
}

function drawHistory(r) {
  const ak = basis === 'actual' ? ['revenue_total', 'spending_total'] : ['total', 'general_fund'];
  const lab = basis === 'actual' ? ['Revenue', 'Spending'] : ['Total budget', 'General Fund'];
  const mx = Math.max(...r.history.flatMap(h => ak.map(k => h[k] || 0)), 1);
  $('bcHistLegend').innerHTML = `<span><i style="background:var(--blue)"></i>${lab[0]}</span><span><i style="background:color-mix(in srgb,var(--blue) 50%,var(--surface))"></i>${lab[1]}</span><span>Darker: the two years you picked</span>`;
  $('bcHist').innerHTML = r.history.map(h => `<button type="button" class="yh-c${h.fiscal_year === r.from || h.fiscal_year === r.to ? ' on' : ''}" data-y="${h.fiscal_year}" aria-label="FY${h.fiscal_year}: ${lab[0]} ${M(h[ak[0]])}, ${lab[1]} ${M(h[ak[1]])}">
    <span class="yh-v">${M(h[ak[0]])}</span><span class="yh-bars">${ak.map((k, i) => h[k] ? `<span class="yh-bar${i ? ' gf' : ''}" style="height:${(h[k] / mx * 100).toFixed(1)}%"></span>` : '').join('')}</span>
    <span class="yh-y">FY${h.fiscal_year}</span><small>${h.detail ? '' : 'total only'}${h.status && !/adopted|audited/.test(h.status) ? (h.detail ? '' : ' · ') + esc(h.status) : ''}</small></button>`).join('');
}

function kpis(r) {
  const k = (lab, l, sub) => `<div class="kpi"><span class="eyebrow">${esc(lab)}</span><span class="v">${l ? `<span class="${cls(l.change)}">${D(l.change)}</span>` : '—'}</span><span class="s">${l ? `${P(l.pct) ? P(l.pct) + ' · ' : ''}${M(l.from)} → ${M(l.to)}` : esc(sub || 'Not on record for both years')}</span></div>`;
  const t = r.totals, by = key => t.find(l => l.key === key);
  const big = (l, w) => `<div class="kpi"><span class="eyebrow">${w}</span><span class="v">${l ? `<span class="${cls(l.change)}">${D(l.change)}</span>` : '—'}</span><span class="s">${l ? esc(l.name) + (l.pct != null ? ' · ' + P(l.pct) : '') : 'No line in both years'}</span></div>`;
  $('bcKpis').innerHTML = basis === 'actual'
    ? k('Revenue (audited)', by('revenue_total')) + k('Spending (audited)', by('spending_total')) + big(r.biggest_increase, 'Biggest increase') + big(r.biggest_decrease, 'Biggest decrease')
    : k('Total budget', by('total')) + k('General Fund', by('general_fund')) + big(r.biggest_increase, 'Biggest department increase') + big(r.biggest_decrease, 'Biggest department cut');
  const tl = by(basis === 'actual' ? 'spending_total' : 'total') || by('general_fund');
  const g = r.government.replace(/^City of /, '');
  let s = `<b>${esc(g)}</b>, FY${r.from} to FY${r.to}: `;
  if (tl && tl.from != null && tl.to != null) s += `${basis === 'actual' ? 'audited spending' : 'the adopted budget'} went ${tl.change >= 0 ? 'up' : 'down'} <span class="${cls(tl.change)}">${M(Math.abs(tl.change))}</span>${tl.pct != null ? ` (${P(tl.pct)})` : ''}, from ${M(tl.from)} to ${M(tl.to)}.`;
  else s += 'only one of the two years has a total on record.';
  if (r.biggest_increase) s += ` The biggest increase was ${esc(r.biggest_increase.name)} (${D(r.biggest_increase.change)}).`;
  if (r.biggest_decrease) s += ` The biggest ${basis === 'actual' ? 'decrease' : 'cut'} was ${esc(r.biggest_decrease.name)} (${D(r.biggest_decrease.change)}).`;
  $('bcSum').innerHTML = s;
}

function render(r) {
  cur = r;
  $('bcTitle').textContent = `${r.government.replace(/^City of /, '')} budget: FY${r.from} vs FY${r.to}`;
  kpis(r); drawHistory(r);
  $('bcNotes').hidden = !r.notes.length; $('bcNotes').innerHTML = r.notes.map(n => `<p>${esc(n)}</p>`).join('');
  const A = basis === 'actual' ? r.sections.spending : r.sections.department, B = basis === 'actual' ? r.sections.revenue : r.sections.fund;
  $('departments').textContent = basis === 'actual' ? 'What changed, by what it paid for' : 'What changed, by department';
  $('funds').textContent = basis === 'actual' ? 'What changed, by where the money came from' : 'What changed, by fund';
  $('bcAnote').textContent = basis === 'actual' ? 'Audited spending, all operating funds' : 'General Fund';
  $('bcBnote').textContent = basis === 'actual' ? 'Audited revenue, all operating funds' : 'Every fund';
  bars($('bcA'), A, {empty: 'No department lines on record for these years. Pick years marked without "total only".'}); table($('bcAt'), A, basis === 'actual' ? 'Spending' : 'Department');
  $('secS').hidden = basis === 'actual';
  if (basis !== 'actual') { bars($('bcS'), r.sections.service, {fixed: true}); table($('bcSt'), r.sections.service, 'Service'); }
  bars($('bcB'), B, {fixed: true, empty: 'No fund lines on record for these years.'}); table($('bcBt'), B, basis === 'actual' ? 'Source' : 'Fund');
  const src = (y, us) => us.length ? `<p><b>FY${y}:</b> ${us.map((u, i) => `<a class="src" href="${esc(u)}" target="_blank" rel="noopener">${us.length > 1 ? 'Document ' + (i + 1) : 'Budget document'}</a>`).join(' · ')}</p>` : '';
  $('bcSrc').innerHTML = `<p>${esc(r.about)}</p>` + src(r.from, r.sources.from) + src(r.to, r.sources.to);
}

function load() {
  const g = GOVS[cur && cur.gov_id] || null, id = $('scCity') ? ($('scCity').value || 'lh') : 'lh';
  const gg = GOVS[id] || GOVS.lh || cov[0];
  if (!gg) return;
  if (!yearsOf(gg).length || yearsOf(gg).length < 2) {
    $('bcSum').innerHTML = `${gov(gg.gov_id)} has ${yearsOf(gg).length ? 'only FY' + yearsOf(gg)[0] : 'no year'} on record for ${basis === 'actual' ? 'audited actuals' : 'adopted budgets'}, so there's nothing to compare yet. ${basis === 'adopted' && gg.actual.length > 1 ? 'Try <b>Audited actuals</b>.' : ''}`;
    $('bcKpis').innerHTML = ''; ['bcA', 'bcS', 'bcB', 'bcHist', 'bcAt', 'bcSt', 'bcBt'].forEach(x => { $(x).innerHTML = ''; }); $('bcNotes').hidden = true;
    fillYears(gg); return;
  }
  const from = +$('bcFrom').value || null, to = +$('bcTo').value || null;
  const keep = g && g.gov_id === gg.gov_id && from && to && from !== to && yearsOf(gg).includes(from) && yearsOf(gg).includes(to);
  const qs = `?gov=${gg.gov_id}&basis=${basis}` + (keep ? `&from=${from}&to=${to}` : (!cur && Q.get('from') ? `&from=${+Q.get('from')}` : '') + (!cur && Q.get('to') ? `&to=${+Q.get('to')}` : ''));
  const n = ++req;
  $('bcSum').textContent = 'Loading…';
  api(qs).then(j => {
    if (n !== req) return;
    fillYears(gg, j.data.from, j.data.to); render(j.data);
    const u = new URL(location.href); u.searchParams.set('from', j.data.from); u.searchParams.set('to', j.data.to);
    if (basis === 'actual') u.searchParams.set('basis', 'actual'); else u.searchParams.delete('basis');
    history.replaceState(history.state, '', u.pathname + u.search + u.hash);
  }).catch(e => { if (n === req) { $('bcSum').textContent = (e && e.error) || 'The budget comparison could not be loaded. Try again shortly.'; fillYears(gg); } });
}

function coverageTable() {
  const yrs = a => a.length ? (a.length > 2 && a[a.length - 1] - a[0] === a.length - 1 ? `FY${a[0]}–FY${a[a.length - 1]}` : a.map(y => 'FY' + y).join(', ')) : '<span class="miss">None</span>';
  const all = [...new Set(cov.flatMap(g => g.adopted_totals))].sort();
  $('bcCov').innerHTML = `<thead><tr><th scope="col">Government</th><th scope="col">Adopted budget totals</th><th scope="col">Department and fund lines</th><th scope="col">Audited actuals</th><th scope="col">Missing budget years</th></tr></thead><tbody>` +
    cov.map(g => { const miss = all.filter(y => !g.adopted_totals.includes(y)); return `<tr><th scope="row">${gov(g.gov_id)}</th><td>${yrs(g.adopted_totals)}</td><td>${yrs(g.adopted_detail)}</td><td>${yrs(g.actual)}</td><td class="miss">${miss.length ? miss.map(y => 'FY' + y).join(', ') : 'None'}</td></tr>`; }).join('') + '</tbody>';
}

$('bcFrom').addEventListener('change', load); $('bcTo').addEventListener('change', load);
$('bcSwap').addEventListener('click', () => { const f = $('bcFrom').value; $('bcFrom').value = $('bcTo').value; $('bcTo').value = f; load(); });
$('bcBasis').addEventListener('click', ev => { const b = ev.target.closest('[data-b]'); if (!b || b.dataset.b === basis) return; basis = b.dataset.b;
  $('bcBasis').querySelectorAll('[data-b]').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.b === basis))); cur = null; Q.delete('from'); Q.delete('to'); load(); });
$('bcSort').addEventListener('click', ev => { const c = ev.target.closest('[data-s]'); if (!c || !cur) return; sort = c.dataset.s;
  $('bcSort').querySelectorAll('[data-s]').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.s === sort)));
  bars($('bcA'), basis === 'actual' ? cur.sections.spending : cur.sections.department); });
$('bcHist').addEventListener('click', ev => { const c = ev.target.closest('[data-y]'); if (!c || !cur) return; const y = +c.dataset.y;
  if (y === cur.from || y === cur.to) return;
  // the tapped year replaces the nearer of the two picked years
  if (Math.abs(y - cur.from) <= Math.abs(y - cur.to)) $('bcFrom').value = y; else $('bcTo').value = y;
  if (+$('bcFrom').value > +$('bcTo').value) { const f = $('bcFrom').value; $('bcFrom').value = $('bcTo').value; $('bcTo').value = f; }
  load(); });
$('bcBasis').querySelectorAll('[data-b]').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.b === basis)));

api('').then(j => {
  cov = j.data; GOVS = Object.fromEntries(cov.map(g => [g.gov_id, g])); coverageTable();
  const go = () => { if (window.BCM && BCM.city) BCM.city.on(() => { cur = cur && cur.gov_id === ($('scCity').value || 'lh') ? cur : null; load(); }); else load(); };
  if (window.BCM) go(); else addEventListener('DOMContentLoaded', go);
}).catch(() => { $('bcSum').textContent = 'The budget comparison could not be loaded. Try again shortly.'; $('bcCov').innerHTML = ''; });
})();
