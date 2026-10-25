// Checkbook (/public-money/checkbook). Reads GET /api/v1/checkbook (totals) and the checkbook-payments dataset
// (the payments list); holds no data.
(() => {
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const M = n => { if (n == null) return '—'; const a = Math.abs(n), s = n < 0 ? '−' : ''; return s + (a >= 1e9 ? '$' + (a / 1e9).toFixed(2) + 'B' : a >= 1e6 ? '$' + (a / 1e6).toFixed(1) + 'M' : a >= 1e4 ? '$' + Math.round(a / 1e3).toLocaleString() + 'K' : '$' + Math.round(a).toLocaleString()); };
const USD = n => n == null ? '—' : '$' + Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
const MON = m => new Date(m + '-15T12:00:00Z').toLocaleDateString('en-US', {month: 'short', timeZone: 'UTC'});
const DAY = d => d ? new Date(String(d).slice(0, 10) + 'T12:00:00Z').toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC'}) : '—';
const name = (id, text) => id && window.BC && BC.a ? BC.a(id, text) : esc(text);
const PAGE = 50;
let cur = null, offset = 0, req = 0, listReq = 0, qTimer = null;
const getJ = u => fetch(u).then(r => r.json().then(j => (r.ok ? j : Promise.reject(j))));

function empty(msg) {
  $('cbEmpty').hidden = false; $('cbBody').hidden = true; $('cbEmptyTxt').innerHTML = msg;
  $('cbSum').textContent = ''; $('cbFy').innerHTML = '';
}

function bars(el, list, label, value, sub, link) {
  const mx = Math.max(...list.map(value), 1);
  el.innerHTML = list.length ? list.map(x => `<div class="ob-r"><span class="ob-n">${link ? link(x) : esc(label(x))}${sub ? `<small>${sub(x)}</small>` : ''}</span>
    <span class="ob-t" aria-hidden="true"><span class="ob-b" style="width:${(value(x) / mx * 100).toFixed(2)}%"></span></span>
    <span class="ob-v">${M(value(x))}</span></div>`).join('') : '<p class="muted">Nothing to show.</p>';
}

function render(d) {
  cur = d;
  $('cbEmpty').hidden = true; $('cbBody').hidden = false;
  const g = d.government;
  $('cbTitle').textContent = `${g} checkbook`;
  $('cbFy').innerHTML = d.fiscal_years.map(y => `<option value="${y}">FY${y}</option>`).join(''); $('cbFy').value = d.fiscal_year;
  const top = d.top_payees[0];
  $('cbSum').innerHTML = `<b>${esc(g)}</b> paid <b>${M(d.total)}</b> in ${d.payments.toLocaleString()} payments to ${d.payees.toLocaleString()} companies and agencies in FY${d.fiscal_year}, from ${DAY(d.from)} through ${DAY(d.through)}.` +
    (top ? ` The most went to ${name(top.payee_entity_id, top.payee)} (${M(top.total)}).` : '') +
    (d.individuals.payments ? ` ${d.individuals.payments.toLocaleString()} payments to private individuals (${M(d.individuals.total)}) are counted but not named.` : '');
  const avg = d.by_month.length ? d.total / d.by_month.length : 0;
  $('cbKpis').innerHTML = [['Paid this year', M(d.total), `FY${d.fiscal_year} through ${DAY(d.through)}`], ['Payments', d.payments.toLocaleString(), 'Checks, ACH, wires and cards'],
    ['Payees', d.payees.toLocaleString(), 'Companies and agencies'], ['A typical month', M(avg), `${d.by_month.length} months of records`]]
    .map(([l, v, s]) => `<div class="kpi"><span class="eyebrow">${esc(l)}</span><span class="v">${v}</span><span class="s">${esc(s)}</span></div>`).join('');
  const mx = Math.max(...d.by_month.map(m => m.total), 1);
  $('cbMonths').innerHTML = d.by_month.map(m => `<div class="ob-m" title="${esc(MON(m.month))} ${m.month.slice(0, 4)}: ${USD(m.total)} in ${m.payments} payments"><span class="ob-mv">${M(m.total)}</span>
    <span class="ob-mb" style="height:${(m.total / mx * 130).toFixed(1)}px"></span><span class="ob-ml">${esc(MON(m.month))}</span></div>`).join('');
  $('cbMonthsNote').textContent = d.by_month.length ? `${MON(d.by_month[0].month)} ${d.by_month[0].month.slice(0, 4)} to ${MON(d.by_month[d.by_month.length - 1].month)} ${d.by_month[d.by_month.length - 1].month.slice(0, 4)}` : '';
  bars($('cbPayees'), d.top_payees.slice(0, 15), p => p.payee, p => p.total, p => `${p.payments} payment${p.payments === 1 ? '' : 's'}`, p => name(p.payee_entity_id, p.payee));
  bars($('cbFunds'), d.by_fund, f => f.fund, f => f.total);
  $('cbFiles').textContent = d.source_files.length ? `Files: ${d.source_files.join(', ')}.` : '';
  offset = 0; list();
}

function list() {
  if (!cur) return;
  const n = ++listReq, q = $('cbQ').value.trim();
  const p = new URLSearchParams({gov_id: cur.gov_id, fiscal_year: cur.fiscal_year, sort: '-paid_on,-amount', limit: PAGE, offset});
  if (q) p.set('q', q);
  const csv = new URLSearchParams(p); csv.delete('limit'); csv.delete('offset'); csv.set('format', 'csv');
  $('cbCsv').href = '/api/v1/datasets/checkbook-payments?' + csv;
  $('cbTable').querySelector('tbody').innerHTML = '<tr><td colspan="6" class="muted">Loading…</td></tr>';
  getJ('/api/v1/datasets/checkbook-payments?' + p).then(j => {
    if (n !== listReq) return;
    const t = j.meta.total;
    $('cbTable').querySelector('tbody').innerHTML = j.data.length ? j.data.map(r => `<tr><td style="white-space:nowrap">${DAY(r.paid_on)}</td>
      <td>${r.payee_kind === 'individual' ? `${esc(r.payee)} <span class="ob-tag ind">private</span>` : name(r.payee_entity_id, r.payee)}</td>
      <td>${esc(r.description || '')}${r.invoice_no ? `<br><span class="muted small">Invoice ${esc(r.invoice_no)}</span>` : ''}</td>
      <td>${esc(r.fund || '')}</td><td class="mono small">${esc(r.doc_no || '')}</td><td class="num">${USD(r.amount)}</td></tr>`).join('')
      : `<tr><td colspan="6" class="muted">No payments match${q ? ` “${esc(q)}”` : ''}.</td></tr>`;
    $('cbCount').textContent = `${t.toLocaleString()} payment${t === 1 ? '' : 's'}${q ? ' match' : ''}`;
    $('cbPage').textContent = t ? `${(offset + 1).toLocaleString()}–${Math.min(offset + PAGE, t).toLocaleString()} of ${t.toLocaleString()}` : '';
    $('cbPrev').disabled = offset === 0; $('cbNext').disabled = offset + PAGE >= t;
  }).catch(() => { if (n === listReq) $('cbTable').querySelector('tbody').innerHTML = '<tr><td colspan="6" class="muted">The payments could not be loaded. Try again shortly.</td></tr>'; });
}

function load(fy) {
  const gov = $('scCity') ? $('scCity').value : '';
  const n = ++req;
  $('cbSum').textContent = 'Loading…';
  const p = new URLSearchParams(); if (gov) p.set('gov', gov); if (fy) p.set('fy', fy);
  getJ('/api/v1/checkbook?' + p).then(j => {
    if (n !== req) return;
    const d = j.data;
    if (!d.gov_id) return empty('No government has published its check register yet. Lynn Haven is first: its files are on the way.');
    render(d);
    const u = new URL(location.href); u.searchParams.set('gov', d.gov_id); u.searchParams.set('fy', d.fiscal_year);
    history.replaceState(history.state, '', u.pathname + u.search + u.hash);
  }).catch(e => {
    if (n !== req) return;
    if (e && e.governments) return empty(`${esc(window.BCM && BCM.city ? BCM.city.label(gov) || gov : gov)} hasn't published its check register yet.` +
      (e.governments.length ? ` Published so far: ${e.governments.map(k => `<a href="?gov=${esc(k)}">${esc(window.BCM && BCM.city ? BCM.city.label(k) || k : k)}</a>`).join(', ')}.` : ''));
    $('cbSum').textContent = (e && e.error) || 'The checkbook could not be loaded. Try again shortly.';
  });
}

$('cbFy').addEventListener('change', () => load($('cbFy').value));
$('cbQ').addEventListener('input', () => { clearTimeout(qTimer); qTimer = setTimeout(() => { offset = 0; list(); }, 250); });
$('cbPrev').addEventListener('click', () => { offset = Math.max(0, offset - PAGE); list(); });
$('cbNext').addEventListener('click', () => { offset += PAGE; list(); });
const fy0 = new URLSearchParams(location.search).get('fy');
const go = () => { if (window.BCM && BCM.city) BCM.city.on(() => load(cur ? null : fy0)); else load(fy0); };
if (window.BCM) go(); else addEventListener('DOMContentLoaded', go);
})();
