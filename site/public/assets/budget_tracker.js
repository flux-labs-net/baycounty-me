// Budget tracker (/public-money/budget-tracker). Reads GET /api/v1/budget-actual; holds no data.
(() => {
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const M = n => { if (n == null) return '—'; const a = Math.abs(n), s = n < 0 ? '−' : ''; return s + (a >= 1e9 ? '$' + (a / 1e9).toFixed(2) + 'B' : a >= 1e6 ? '$' + (a / 1e6).toFixed(1) + 'M' : a >= 1e4 ? '$' + Math.round(a / 1e3).toLocaleString() + 'K' : '$' + Math.round(a).toLocaleString()); };
const P = x => x == null ? '—' : Math.round(x * 100) + '%';
const DAY = d => d ? new Date(String(d).slice(0, 10) + 'T12:00:00Z').toLocaleDateString('en-US', {month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC'}) : '—';
const SHORT = d => new Date(String(d).slice(0, 10) + 'T12:00:00Z').toLocaleDateString('en-US', {month: 'short', year: 'numeric', timeZone: 'UTC'});
const listAnd = a => a.length < 2 ? a.join('') : a.length === 2 ? a.join(' and ') : a.slice(0, -1).join(', ') + ', and ' + a[a.length - 1];
let cur = null, req = 0;
const getJ = u => fetch(u).then(r => r.json().then(j => (r.ok ? j : Promise.reject(j))));

function empty(msg) {
  $('btEmpty').hidden = false; $('btBody').hidden = true; $('btEmptyTxt').innerHTML = msg;
  $('btSum').textContent = ''; $('btFy').innerHTML = ''; $('btAsOf').innerHTML = '';
}

// One bar: spent, then committed, against the budget; the mark is the share of the year gone.
function bar(budget, actual, enc, el) {
  const scale = Math.max(budget, actual + enc, 1), over = actual + enc > budget + 0.5;
  const w = v => (Math.max(0, v) / scale * 100).toFixed(2);
  return `<span class="ob-t" aria-hidden="true"><span class="ob-b${over ? ' over' : ''}" style="width:${w(actual)}%"></span>` +
    (enc > 0 ? `<span class="ob-b enc" style="left:${w(actual)}%;width:${w(enc)}%"></span>` : '') +
    (el != null && budget > 0 ? `<span class="ob-mark" style="left:${(Math.min(budget, scale) * el / scale * 100).toFixed(2)}%"></span>` : '') + '</span>';
}

function render(d) {
  cur = d;
  $('btEmpty').hidden = true; $('btBody').hidden = false;
  const g = d.government, t = d.totals, el = d.elapsed;
  $('btTitle').textContent = `${g} budget tracker`;
  $('btFy').innerHTML = d.fiscal_years.map(y => `<option value="${y}">FY${y}</option>`).join(''); $('btFy').value = d.fiscal_year;
  $('btAsOf').innerHTML = [...d.as_ofs].reverse().map(a => `<option value="${a}">${esc(SHORT(a))}</option>`).join(''); $('btAsOf').value = d.as_of;
  const bits = [];
  if (d.over_budget.length) bits.push(`${d.over_budget.length > 3 ? `<b>${d.over_budget.length} departments</b> are` : `<b>${esc(listAnd(d.over_budget))}</b> ${d.over_budget.length === 1 ? 'is' : 'are'}`} over budget`);
  if (d.running_ahead.length) bits.push(`${d.running_ahead.length > 3 ? `${d.running_ahead.length} departments are` : `${esc(listAnd(d.running_ahead))} ${d.running_ahead.length === 1 ? 'is' : 'are'}`} running well ahead of the year`);
  $('btSum').innerHTML = `Through ${DAY(d.as_of)}, <b>${esc(g)}</b> departments have spent or committed <b>${M(t.spent)}</b> of their <b>${M(t.budget)}</b> FY${d.fiscal_year} budgets (${P(t.used)}), with ${P(el)} of the fiscal year gone. ` +
    (bits.length ? listAnd(bits).replace(/^./, c => c.toUpperCase()) + '.' : '<span class="ob-ok">Every department is within its budget.</span>');
  const k = (l, v, s) => `<div class="kpi"><span class="eyebrow">${esc(l)}</span><span class="v">${v}</span><span class="s">${s}</span></div>`;
  $('btKpis').innerHTML = k('Budget', M(t.budget), t.budget !== t.original ? `Adopted ${M(t.original)}, amended ${t.budget > t.original ? '+' : '−'}${M(Math.abs(t.budget - t.original))}` : 'As adopted') +
    k('Spent so far', M(t.actual), `Plus ${M(t.encumbered)} committed`) +
    k('Used', `<span class="${t.used - el > 0.05 ? 'ob-up' : ''}">${P(t.used)}</span>`, `${P(el)} of the year gone`) +
    (d.revenue ? k('Revenue collected', M(d.revenue.collected), `${P(d.revenue.budget ? d.revenue.collected / d.revenue.budget : null)} of ${M(d.revenue.budget)} expected`) : k('Departments', d.departments.length, `${d.over_budget.length} over budget`));
  const over = new Set(d.over_budget), ahead = new Set(d.running_ahead);
  $('btDepts').innerHTML = d.departments.map((x, i) => `<details class="ob-dept"><summary><div class="ob-r"><span class="ob-n">${esc(x.name)}${over.has(x.name) ? '<span class="ob-tag over">over</span>' : ahead.has(x.name) ? '<span class="ob-tag ahead">ahead</span>' : ''}<small>${esc(x.fund || '')}${x.amended ? ` · amended ${x.amended > 0 ? '+' : '−'}${M(Math.abs(x.amended))}` : ''}</small></span>
    ${bar(x.budget, x.actual, x.encumbered, el)}<span class="ob-v">${P(x.used)}<small>${M(x.spent)} of ${M(x.budget)}</small></span></div></summary>
    <div class="ob-lines tablewrap"><table class="tx-table"><thead><tr><th scope="col">Line</th><th scope="col" class="num">Budget</th><th scope="col" class="num">Spent</th><th scope="col" class="num">Committed</th><th scope="col" class="num">Used</th></tr></thead><tbody>
    ${x.lines.map(l => `<tr><th scope="row">${esc(l.description || l.account || 'Line')}${l.account ? ` <span class="muted small mono">${esc(l.account)}</span>` : ''}</th><td class="num">${M(l.budget)}</td><td class="num">${M(l.actual)}</td><td class="num">${M(l.encumbered)}</td><td class="num${l.actual + l.encumbered > l.budget + 0.5 ? ' ob-up' : ''}">${l.budget > 0 ? P((l.actual + l.encumbered) / l.budget) : '—'}</td></tr>`).join('')}
    </tbody></table></div></details>`).join('') || '<p class="muted">No spending lines in this report.</p>';
  $('btRevSec').hidden = !d.revenue;
  if (d.revenue) {
    const mx = Math.max(...d.revenue.sources.map(s => Math.max(s.budget, s.collected)), 1);
    $('btRev').innerHTML = d.revenue.sources.slice(0, 20).map(s => `<div class="ob-r"><span class="ob-n">${esc(s.name)}</span>
      <span class="ob-t" aria-hidden="true"><span class="ob-b" style="width:${(s.collected / mx * 100).toFixed(2)}%;background:var(--teal)"></span>${el != null && s.budget > 0 ? `<span class="ob-mark" style="left:${(s.budget * el / mx * 100).toFixed(2)}%"></span>` : ''}</span>
      <span class="ob-v">${M(s.collected)}<small>of ${M(s.budget)}</small></span></div>`).join('');
  }
  $('btMonths').innerHTML = `<thead><tr><th scope="col">Report</th><th scope="col" class="num">Budget</th><th scope="col" class="num">Spent and committed</th><th scope="col" class="num">Used</th><th scope="col" class="num">Year gone</th>${d.months.some(m => m.revenue_budget) ? '<th scope="col" class="num">Revenue collected</th>' : ''}</tr></thead><tbody>` +
    d.months.map(m => `<tr${m.as_of === d.as_of ? ' style="font-weight:600"' : ''}><th scope="row">${esc(SHORT(m.as_of))}</th><td class="num">${M(m.budget)}</td><td class="num">${M(m.spent)}</td><td class="num${m.used - m.elapsed > 0.05 ? ' ob-up' : ''}">${P(m.used)}</td><td class="num">${P(m.elapsed)}</td>${d.months.some(x => x.revenue_budget) ? `<td class="num">${M(m.revenue_collected)}</td>` : ''}</tr>`).join('') + '</tbody>';
  $('btFiles').textContent = d.source_files.length ? `File: ${d.source_files.join(', ')}.` : '';
}

function load(fy, asOf) {
  const gov = $('scCity') ? $('scCity').value : '';
  const n = ++req;
  $('btSum').textContent = 'Loading…';
  const p = new URLSearchParams(); if (gov) p.set('gov', gov); if (fy) p.set('fy', fy); if (asOf) p.set('as_of', asOf);
  getJ('/api/v1/budget-actual?' + p).then(j => {
    if (n !== req) return;
    const d = j.data;
    if (!d.gov_id) return empty('No government has published a monthly budget report yet. Lynn Haven is first: its files are on the way.');
    render(d);
    const u = new URL(location.href); u.searchParams.set('gov', d.gov_id); u.searchParams.set('fy', d.fiscal_year);
    history.replaceState(history.state, '', u.pathname + u.search + u.hash);
  }).catch(e => {
    if (n !== req) return;
    const lab = k => esc(window.BCM && BCM.city ? BCM.city.label(k) || k : k);
    if (e && e.governments) return empty(`${lab(gov)} hasn't published a monthly budget report yet.` + (e.governments.length ? ` Published so far: ${e.governments.map(k => `<a href="?gov=${esc(k)}">${lab(k)}</a>`).join(', ')}.` : ''));
    $('btSum').textContent = (e && e.error) || 'The budget tracker could not be loaded. Try again shortly.';
  });
}

$('btFy').addEventListener('change', () => load($('btFy').value));
$('btAsOf').addEventListener('change', () => load($('btFy').value, $('btAsOf').value));
const fy0 = new URLSearchParams(location.search).get('fy');
const go = () => { if (window.BCM && BCM.city) BCM.city.on(() => load(cur ? null : fy0)); else load(fy0); };
if (window.BCM) go(); else addEventListener('DOMContentLoaded', go);
})();
